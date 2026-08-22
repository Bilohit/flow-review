"""Execute a candidate's launch command and record what was actually observed.

A command that has never been seen succeed is never written into the config as wired -- it is
asked about instead. The failure this forecloses: a detected-but-wrong launch command becomes
a gate that reports green while testing nothing, which is worse than having no gate at all.
fr.audit PROPOSES surfaces and never launches; this module EXECUTES and never proposes.

An earlier version of this module ran the command and set ok = (exit_code == 0). Two verified
defects killed that design. First, with shell=True the process tree is cmd.exe (or sh) -> the
real program; a timeout that kills only the direct child leaves the grandchild running, still
holding the output file open, so cleanup raises PermissionError on Windows. Two orphaned
processes were observed still running after a "successful" timeout. Second, exit code is the
wrong evidence for the headline case this proves: a dev server never exits on its own, so it
always timed out and was recorded as NOT proven, while ok=True would have required the server
to have crashed. The fix is not a better exit code -- a server is proven by *still running*
while something observes it is ready, which is why an outcome needs four values, not one bool.

Child output goes to a temporary FILE, never a pipe read after exit: a pipe that fills while
nobody drains it deadlocks, and the symptom is indistinguishable from the child hanging.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from fr.audit import Candidate

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Provenance vocabulary fr.config validates against (VALID_PROVENANCE). Kept here at their
# existing values so a Proof's outcome can be translated straight into a Surface's field
# without either module having to know the other's naming.
PROVEN = "proven"
UNPROVEN = "audited"

# The outcome an earlier boolean collapsed and lost information doing so. "running ready" is
# the case a dev server needs: a command that never exits is proven by something else
# observing it is ready, not by waiting for an exit that will never come.
EXITED_CLEAN = "exited_clean"
EXITED_FAILED = "exited_failed"
RUNNING_READY = "running_ready"
NOT_PROVEN = "not_proven"
OUTCOMES = (EXITED_CLEAN, EXITED_FAILED, RUNNING_READY, NOT_PROVEN)

_IS_WINDOWS = os.name == "nt"

_HEAD_CHARS = 2000
_TAIL_CHARS = 2000
# Coarse enough not to busy-loop spawning precondition checks, fine enough that a readiness
# deadline of a few seconds still gets several chances to observe it.
_POLL_INTERVAL_S = 0.1
_PRECONDITION_TIMEOUT_S = 5.0
_TEARDOWN_WAIT_S = 5.0
# A kill can leave the child's duplicated file handle open a moment longer than the parent
# sees the process die -- Windows then reports the temp file busy. Retry briefly rather than
# raising out of prove(); a leftover temp file is a nuisance, not a defect worth crashing over.
_UNLINK_RETRIES = 5
_UNLINK_RETRY_DELAY_S = 0.1


@dataclass
class Proof:
    candidate: Candidate
    outcome: str
    exit_code: int | None
    duration_s: float
    output_head: str
    output_tail: str
    # The name of the precondition that proved readiness; empty when nothing proved it.
    precondition: str
    # A process prove() could not confirm dead is a finding, not a footnote -- it is kept
    # separate from outcome because the outcome vocabulary is closed at four values and a
    # stuck process is an orthogonal fact about teardown, not a fifth thing that happened.
    teardown_ok: bool
    reason: str


def outcome_to_provenance(outcome: str) -> str:
    """Map a Proof's outcome onto the provenance vocabulary fr.config validates against.

    Only an outcome that was actually witnessed working -- a clean exit or a running process
    an independent precondition confirmed ready -- earns PROVEN. Everything else, including a
    command that merely failed to prove anything either way, stays UNPROVEN: silence is not
    evidence.
    """
    return PROVEN if outcome in (EXITED_CLEAN, RUNNING_READY) else UNPROVEN


def _check_precondition(cmd: str, root: Path, timeout: float = _PRECONDITION_TIMEOUT_S) -> bool:
    try:
        result = subprocess.run(
            cmd, cwd=str(root), shell=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0


def _first_passing(preconditions, root: Path, budget_s: float | None = None) -> str | None:
    """Try each precondition in order, capping each check at the time actually left.

    budget_s is None for the baseline check the caller runs before anything is started --
    there is no deadline yet, so each precondition gets the full _PRECONDITION_TIMEOUT_S.
    Once the observe loop is running, the caller passes the time left before its own
    deadline: without that cap, a single slow precondition (or several, since the budget is
    shared across the whole list) could block up to _PRECONDITION_TIMEOUT_S past a caller
    deadline shorter than 5s, turning a bound meant to be firm into a mere suggestion.
    """
    for precondition in preconditions:
        if budget_s is not None:
            if budget_s <= 0:
                return None
            timeout = min(_PRECONDITION_TIMEOUT_S, budget_s)
        else:
            timeout = _PRECONDITION_TIMEOUT_S
        check_started = time.monotonic()
        if _check_precondition(precondition["cmd"], root, timeout):
            return precondition.get("name", "")
        if budget_s is not None:
            budget_s -= time.monotonic() - check_started
    return None


def _start_process(launch: str, root: Path, handle) -> subprocess.Popen:
    # Both branches exist so a group/tree kill can actually reach the grandchild that
    # shell=True interposes: cmd.exe or sh is the direct child, the real program is not.
    if _IS_WINDOWS:
        return subprocess.Popen(
            launch, cwd=str(root), shell=True, stdout=handle, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    return subprocess.Popen(
        launch, cwd=str(root), shell=True, stdout=handle, stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def _kill_tree(process: subprocess.Popen) -> bool:
    """Send the kill and report whether the kill signal itself succeeded.

    A successful signal is necessary but not sufficient -- _teardown still confirms the
    outcome afterwards. On Windows that confirmation is poll(), because taskkill /T /F
    already reports tree-wide success in its own return code. On POSIX, killpg's success
    only means the signal was delivered, not that anything died yet; _teardown separately
    probes the group's actual liveness, which poll() on the direct child cannot do.
    """
    if _IS_WINDOWS:
        # taskkill /T walks the process tree by PID lineage, which is what reaches the
        # grandchild through cmd.exe. Popen.kill() only terminates cmd.exe itself and is
        # the original bug: the grandchild survives, keeping the output file open.
        result = subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass  # already gone before we could signal it -- not a kill failure
    return True


def _posix_group_is_gone(pgid: int) -> bool:
    # signal 0 sends nothing; it only asks the kernel whether the target still exists.
    # ProcessLookupError here means every process in the group is gone -- the group-level
    # fact poll() cannot give, since poll() only ever observes the direct child (cmd.exe/sh).
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True
    return False


def _teardown(process: subprocess.Popen) -> bool:
    """Kill whatever is left of the process tree and confirm it is actually gone.

    prove() owns the full lifecycle and must never leave a process running on any exit
    path. Killing is not enough to claim that on its own -- report whether the process was
    confirmed dead, so a process that survived the kill is a visible finding. Confirming
    only the direct child (what poll() sees) would miss a tree kill that partially failed
    while the direct child happened to exit on its own -- the grandchild is the entire bug
    this function exists to prevent, so its death is checked too, not assumed.
    """
    if process.poll() is not None:
        return True
    kill_ok = _kill_tree(process)
    try:
        process.wait(timeout=_TEARDOWN_WAIT_S)
    except subprocess.TimeoutExpired:
        pass
    if not kill_ok or process.poll() is None:
        return False
    if _IS_WINDOWS:
        return True
    return _posix_group_is_gone(process.pid)


def _read_output(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    # A crash explains itself in its last lines; a startup failure explains itself in its
    # first. Keeping only a tail misjudges the second case just as exit code alone did.
    return text[:_HEAD_CHARS], text[-_TAIL_CHARS:]


def _cleanup_sink(path: Path) -> None:
    for _ in range(_UNLINK_RETRIES):
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError:
            time.sleep(_UNLINK_RETRY_DELAY_S)


def prove(
    candidate: Candidate,
    root: Path,
    preconditions=(),
    ready_timeout_s: float = 15,
    exit_timeout_s: float = 60,
) -> Proof:
    started = time.monotonic()

    if not candidate.launch.strip():
        return Proof(
            candidate, NOT_PROVEN, None, time.monotonic() - started, "", "", "", True,
            "no launch command to prove",
        )

    # If a precondition already passes before anything here has started, something else is
    # already listening (a leftover server from a previous run, a port another tool owns).
    # Proving readiness against it would attribute someone else's process to this launch --
    # a false positive worse than the "not proven" it is replacing.
    baseline = _first_passing(preconditions, root) if preconditions else None
    if baseline is not None:
        return Proof(
            candidate, NOT_PROVEN, None, time.monotonic() - started, "", "", "", True,
            f"precondition {baseline!r} already passes before launch; nothing was started",
        )

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        sink_path = Path(tmp.name)

    handle = sink_path.open("w", encoding="utf-8", errors="replace")
    try:
        process = _start_process(candidate.launch, root, handle)
    except OSError as exc:
        # Popen itself can fail before there is any process to observe -- e.g. `root` does
        # not exist, so cwd is invalid. Every other failure mode here returns a NOT_PROVEN
        # Proof explaining itself; letting this one crash out of prove() instead would also
        # orphan the temp sink just created above, since the cleanup below would never run.
        handle.close()
        _cleanup_sink(sink_path)
        return Proof(
            candidate, NOT_PROVEN, None, time.monotonic() - started, "", "", "", True,
            f"failed to launch: {exc}",
        )
    finally:
        # The OS-level descriptor was duplicated into the child at Popen(); this object can
        # close immediately without cutting off the child's own writes to the same file.
        handle.close()

    outcome = NOT_PROVEN
    exit_code: int | None = None
    precondition_name = ""
    reason = ""
    # Two deadlines answer two different questions. A terminating command is judged against
    # exit_timeout_s. Once preconditions are in play the question changes to "is it ready",
    # so the shorter ready_timeout_s governs instead -- waiting the full exit deadline for a
    # dev server that will never exit is exactly the original bug.
    deadline = ready_timeout_s if preconditions else exit_timeout_s

    try:
        while True:
            status = process.poll()
            if status is not None:
                exit_code = status
                outcome = EXITED_CLEAN if status == 0 else EXITED_FAILED
                break
            elapsed = time.monotonic() - started
            if preconditions:
                # Cap this check at whatever time is actually left before the deadline.
                # Calling _first_passing with no cap let one slow precondition (or several,
                # tried in sequence) block up to _PRECONDITION_TIMEOUT_S past a deadline the
                # caller set deliberately short -- a bound is not a bound if one iteration
                # can blow through it by seconds.
                passed = _first_passing(preconditions, root, budget_s=deadline - elapsed)
                if passed is not None:
                    outcome = RUNNING_READY
                    precondition_name = passed
                    break
                elapsed = time.monotonic() - started
            if elapsed >= deadline:
                if preconditions:
                    reason = (
                        f"no precondition passed within {ready_timeout_s}s; "
                        "process still running"
                    )
                else:
                    reason = (
                        "command does not terminate and no precondition was given to "
                        "prove readiness"
                    )
                break
            time.sleep(min(_POLL_INTERVAL_S, deadline - elapsed))
    finally:
        teardown_ok = _teardown(process)

    if not teardown_ok:
        # A process that survived the kill is a finding, not a footnote -- fold it into the
        # same reason the caller already reads, rather than leaving it visible only on the
        # boolean, where an earlier version of this function left it (sometimes blank).
        addition = "process could not be confirmed dead after the kill"
        reason = f"{reason}; {addition}" if reason else addition

    duration = time.monotonic() - started
    output_head, output_tail = _read_output(sink_path)
    _cleanup_sink(sink_path)

    return Proof(
        candidate=candidate,
        outcome=outcome,
        exit_code=exit_code,
        duration_s=duration,
        output_head=output_head,
        output_tail=output_tail,
        precondition=precondition_name,
        teardown_ok=teardown_ok,
        reason=reason,
    )
