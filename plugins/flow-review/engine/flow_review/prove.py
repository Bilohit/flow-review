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
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from flow_review.audit import Candidate
from flow_review.config import validate_preconditions

_IS_WINDOWS = os.name == "nt"

if _IS_WINDOWS:
    # ctypes.wintypes does not exist on POSIX, so this import must stay behind the platform
    # guard -- importing it unconditionally would break the module on Linux/macOS.
    import ctypes
    from ctypes import wintypes

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
# ponytail: each snapshot shells out to PowerShell -- measured at ~1.1-1.3s per call on a
# loaded machine, not the "a few hundred ms" this constant's throttle was originally sized for
# (see test_slow_precondition_does_not_blow_through_ready_deadline, which caught a real prod
# machine slow enough that a single snapshot could eat a whole short ready_timeout_s budget).
# Throttled to once per _DESCENDANT_SNAPSHOT_S so it is not called on every _POLL_INTERVAL_S
# poll. This snapshot is no longer load-bearing for correctness -- reaping the whole tree is
# now the Windows Job Object's job (see _create_kill_on_close_job / _assign_to_job below,
# JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE): a process assigned to a job automatically pulls every
# child IT spawns into the same job, with no PowerShell walk involved and no window in which a
# fast-spawned grandchild can be born and orphaned before anything notices it. What remains
# here is reporting/fallback only: windows_descendants collected via this snapshot is still fed
# to _teardown as a best-effort cross-check, and still helps if the job could not be created or
# assigned (accepted race: it is assigned immediately after Popen, not before, since Popen
# offers no CREATE_SUSPENDED hook).
_DESCENDANT_SNAPSHOT_S = 1.0

if _IS_WINDOWS:
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _JobObjectExtendedLimitInformation = 9
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    _PROCESS_TERMINATE = 0x0001
    _PROCESS_SET_QUOTA = 0x0100

    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", _IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    # restype must be set explicitly on every HANDLE-returning function: ctypes defaults to
    # c_int, which truncates a 64-bit HANDLE on 64-bit Windows and hands back garbage.
    _kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    _kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _kernel32.SetInformationJobObject.restype = wintypes.BOOL
    _kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
    ]
    _kernel32.TerminateJobObject.restype = wintypes.BOOL
    _kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    def _create_kill_on_close_job() -> int | None:
        """A Windows Job Object with JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE.

        Any process assigned to this job -- and, critically, every child THAT process later
        spawns, since job membership propagates to children automatically unless a process
        explicitly opts out with CREATE_BREAKAWAY_FROM_JOB -- dies the instant the job is
        terminated or its last handle is closed. This is what makes the whole descendant tree
        reapable without ever having to discover its membership by walking the process table.
        """
        job = _kernel32.CreateJobObjectW(None, None)
        if not job:
            return None
        info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = _kernel32.SetInformationJobObject(
            job, _JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info),
        )
        if not ok:
            _kernel32.CloseHandle(job)
            return None
        return job

    def _assign_to_job(job: int, pid: int) -> bool:
        # PROCESS_TERMINATE + PROCESS_SET_QUOTA are the access rights
        # AssignProcessToJobObject itself requires on the process handle.
        process_handle = _kernel32.OpenProcess(
            _PROCESS_TERMINATE | _PROCESS_SET_QUOTA, False, pid,
        )
        if not process_handle:
            # The process may already have exited (it was spawned via shell=True and could be
            # a wrapper that exits almost immediately) -- not assignable, not a crash.
            return False
        try:
            return bool(_kernel32.AssignProcessToJobObject(job, process_handle))
        finally:
            _kernel32.CloseHandle(process_handle)

    def _new_kill_on_close_job_for(pid: int) -> int | None:
        """Best-effort: create a job and assign pid to it, or return None on any failure.

        Never raises -- a launched process this could not wrap into a job still gets torn down
        by the existing taskkill /T fallback in _kill_tree, just without the job's stronger
        guarantee against a fast-spawned, fast-orphaned grandchild.
        """
        job = _create_kill_on_close_job()
        if job is None:
            return None
        if not _assign_to_job(job, pid):
            _kernel32.CloseHandle(job)
            return None
        return job


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
        process = subprocess.Popen(
            launch, cwd=str(root), shell=True, stdout=handle, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        # Popen offers no CREATE_SUSPENDED hook, so the job is assigned immediately after
        # Popen returns rather than before the process starts running -- a process that spawns
        # and orphans a child in the few microseconds before this line runs would still escape
        # the job. Accepted per the task: narrower than any PowerShell-walk window it replaces,
        # and the taskkill /T fallback in _kill_tree still covers it either way.
        process._fr_job = _new_kill_on_close_job_for(process.pid)
        return process
    return subprocess.Popen(
        launch, cwd=str(root), shell=True, stdout=handle, stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def _child_pids_of(pid: int) -> set[int]:
    # wmic is removed on current Windows 11 builds; Get-CimInstance is its supported
    # replacement and gives the same ParentProcessId lineage taskkill /T itself cannot
    # re-derive once the parent's own process-table entry is gone (H3).
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-NonInteractive", "-Command",
                f"(Get-CimInstance Win32_Process -Filter \"ParentProcessId={pid}\")"
                ".ProcessId",
            ],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError):
        return set()
    return {int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()}


def _descendant_pids(root_pid: int) -> set[int]:
    """Breadth-first walk of the Windows process table for every live descendant of root_pid.

    taskkill /T only walks a tree it can still locate STARTING FROM root_pid's own process
    entry -- once that entry is gone (the direct child, cmd.exe, already exited on its own),
    /T finds nothing, even though whatever cmd.exe spawned is still running (H3). Each
    descendant's own entry keeps recording its immediate parent's pid regardless of whether
    that parent still exists, so this walk finds every survivor /T would have found had
    root_pid still been alive, and still works when it is not.
    """
    seen: set[int] = set()
    frontier = {root_pid}
    while frontier:
        next_frontier: set[int] = set()
        for pid in frontier:
            for child in _child_pids_of(pid):
                if child not in seen:
                    seen.add(child)
                    next_frontier.add(child)
        frontier = next_frontier
    return seen


class _DescendantWatcher:
    """Collects the throttled Windows descendant snapshot on a background thread.

    test_slow_precondition_does_not_blow_through_ready_deadline caught the real defect this
    fixes: running the snapshot inline in prove()'s observe loop meant a single slow
    Get-CimInstance call (~1.1-1.3s measured, not the "a few hundred ms" the throttle was
    originally sized for) could by itself consume a whole short ready_timeout_s budget before
    the capped precondition check ever got a chance to run. The snapshot is no longer needed
    for correctness -- a Windows Job Object (_new_kill_on_close_job_for) is what actually
    guarantees every descendant gets reaped -- so it now runs off the deadline-critical path
    entirely and is read as a best-effort, non-blocking cross-check/fallback.
    """

    def __init__(self, pid: int) -> None:
        self._pid = pid
        self._lock = threading.Lock()
        self._seen: set[int] = set()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            found = _descendant_pids(self._pid)
            with self._lock:
                self._seen |= found
            self._stop.wait(_DESCENDANT_SNAPSHOT_S)

    def snapshot(self) -> set[int]:
        with self._lock:
            return set(self._seen)

    def stop(self) -> None:
        # No join: the in-flight PowerShell call (if any) is left to finish on its own daemon
        # thread rather than have prove()'s return wait on it -- it is a short-lived read-only
        # query with nothing left in this process to report back to once stopped.
        self._stop.set()


def _windows_pid_alive(pid: int) -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return str(pid) in result.stdout


def _kill_tree(process: subprocess.Popen) -> tuple[bool, set[int]]:
    """Send the kill and report (signal succeeded, descendants observed at kill time).

    On Windows the primary kill is TerminateJobObject on the job _start_process assigned this
    process to (see _new_kill_on_close_job_for): every descendant is a member of that job
    automatically, so this does not need its own fresh process-table walk to find them first --
    the walk that used to live here was exactly the blocking PowerShell call
    test_slow_precondition_does_not_blow_through_ready_deadline caught eating a whole short
    ready_timeout_s budget. taskkill /T still runs as a fallback for the case the job could not
    be created or assigned. The descendants set returned is empty by design; _teardown's own
    verification instead uses known_descendants, the throttled snapshot the caller already
    collected during the observe loop.
    """
    if _IS_WINDOWS:
        job = getattr(process, "_fr_job", None)
        job_killed = False
        if job is not None:
            job_killed = bool(_kernel32.TerminateJobObject(job, 1))
            _kernel32.CloseHandle(job)
            process._fr_job = None
        tree_result = subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return job_killed or tree_result.returncode == 0, set()
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass  # already gone before we could signal it -- not a kill failure
    return True, set()


def _posix_group_is_gone(pgid: int) -> bool:
    # signal 0 sends nothing; it only asks the kernel whether the target still exists.
    # ProcessLookupError here means every process in the group is gone -- the group-level
    # fact poll() cannot give, since poll() only ever observes the direct child (cmd.exe/sh).
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True
    return False


def _teardown(process: subprocess.Popen, known_descendants: set[int] = frozenset()) -> bool:
    """Kill whatever is left of the process tree and confirm it is actually gone.

    Never trusts `process.poll() is not None` as proof the whole tree is dead (H3) -- poll()
    only ever observes the direct child (cmd.exe/sh under shell=True). A kill and an
    independent liveness check always run, whether or not the direct child had already exited
    on its own by the time this is called.

    known_descendants (Windows only) is a set the caller may have accumulated by walking the
    process table *while the tree was still alive* (the throttled snapshot in prove()'s observe
    loop). The Windows Job Object _kill_tree terminates is the actual guarantee that every
    descendant -- including one spawned and orphaned between snapshots, or one whose only link
    back to process.pid had already vanished from the table by the time of the last walk (H3) --
    is reaped, since job membership is inherited by every child a job member spawns regardless
    of whether this module ever walked the table far enough to see it. known_descendants is used
    here only as an independent, best-effort cross-check and as the fallback path for a process
    the job could not be assigned to.
    """
    kill_ok, descendants = _kill_tree(process)
    if process.poll() is None:
        try:
            process.wait(timeout=_TEARDOWN_WAIT_S)
        except subprocess.TimeoutExpired:
            pass
    if process.poll() is None:
        # The direct child itself never went away -- whatever _kill_tree did (or, in a test,
        # was mocked into a no-op) did not work. known_descendants is moot: a kill that could
        # not even bring down the direct child cannot be trusted to have reached anything past
        # it, so this stays a plain teardown failure exactly as it always has.
        return False
    all_descendants = descendants | set(known_descendants)
    if _IS_WINDOWS:
        # Backstop: the job kill in _kill_tree should already have reaped everything, but
        # taskkill each pid the snapshot happened to see anyway, in case the job could not be
        # created/assigned for this process (see _new_kill_on_close_job_for).
        for pid in all_descendants - descendants:
            if _windows_pid_alive(pid):
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
        # kill_ok alone is not proof: taskkill /T can report failure purely because it had no
        # live root left to walk from, while every descendant was still killed individually
        # just above. The only trustworthy confirmation is asking the process table again.
        return kill_ok or not any(_windows_pid_alive(pid) for pid in all_descendants)
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

    preconditions = list(preconditions)
    validate_preconditions(preconditions)

    if candidate.kind == "api" and not candidate.launch.strip():
        # M3: an api surface proves reachability alone -- never "no launch command", and
        # nothing is ever spawned to prove it (spec Section 6).
        if not preconditions:
            return Proof(
                candidate, NOT_PROVEN, None, time.monotonic() - started, "", "", "", True,
                "api surface has no launch command and no reachability precondition to prove it",
            )
        passed = _first_passing(preconditions, root)
        if passed is not None:
            return Proof(
                candidate, RUNNING_READY, None, time.monotonic() - started, "", "", passed, True,
                "api reachable via precondition; nothing was launched",
            )
        return Proof(
            candidate, NOT_PROVEN, None, time.monotonic() - started, "", "", "", True,
            "no reachability precondition passed for this api surface; nothing was launched",
        )

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
    # H3: accumulated while the tree is still alive, because a descendant's link back to
    # process.pid can vanish from the Windows process table the instant an intermediate
    # process (e.g. the launched command itself, running under cmd.exe) exits on its own --
    # possibly before _teardown ever gets a chance to walk the tree fresh. A pid observed here
    # remains a real process to hunt down at teardown even once that walk can no longer find it.
    # Collected on a background thread (_DescendantWatcher), not inline in the loop below --
    # see its docstring for why a call this slow can never be allowed back onto the
    # deadline-critical path.
    watcher = _DescendantWatcher(process.pid) if _IS_WINDOWS else None

    try:
        while True:
            status = process.poll()
            if status is not None:
                exit_code = status
                if preconditions and status == 0:
                    # H4: preconditions exist to OBSERVE readiness -- a clean exit before any
                    # of them ever passed proves nothing about what they were asked to confirm.
                    outcome = NOT_PROVEN
                    reason = (
                        "process exited cleanly before any precondition passed; a clean exit "
                        "does not prove readiness when preconditions were configured to prove it"
                    )
                else:
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
        # No extra snapshot is taken here right before teardown: _kill_tree's primary kill on
        # Windows is TerminateJobObject on the job the process was assigned to at launch, which
        # needs no process-table walk at all to reach every descendant (see _kill_tree). The
        # watcher's own last snapshot is passed through only as a best-effort cross-check /
        # fallback, not because a fresh walk is needed here.
        windows_descendants: set[int] = set()
        if watcher is not None:
            windows_descendants = watcher.snapshot()
            watcher.stop()
        teardown_ok = _teardown(process, windows_descendants)

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
