from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from fr.audit import Candidate
from fr import prove as provemod


def _candidate(launch: str) -> Candidate:
    return Candidate(name="x", kind="cli", driver="shell", launch=launch, evidence="test:1 -> x")


def _script(tmp_path: Path, name: str, body: str) -> str:
    """A real .py file, not a -c one-liner.

    Quoting a -c payload that itself contains quotes has to survive an f-string, the shell,
    and cmd.exe on Windows. That is three escaping layers to get a test fixture wrong in.
    """
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return f'"{sys.executable}" "{path}"'


def _process_alive(pid: int) -> bool:
    if os.name == "nt":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True, text=True,
        )
        return str(pid) in out.stdout
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def test_exit_zero_is_exited_clean(tmp_path):
    launch = _script(tmp_path, "ok.py", "print(1)\n")
    proof = provemod.prove(_candidate(launch), tmp_path)
    assert proof.outcome == provemod.EXITED_CLEAN
    assert proof.exit_code == 0
    assert proof.teardown_ok is True
    assert proof.duration_s >= 0
    assert provemod.outcome_to_provenance(proof.outcome) == provemod.PROVEN


def test_exit_nonzero_is_exited_failed_with_tail(tmp_path):
    launch = _script(
        tmp_path, "bad.py",
        "import sys\nsys.stderr.write('boom')\nsys.exit(3)\n",
    )
    proof = provemod.prove(_candidate(launch), tmp_path)
    assert proof.outcome == provemod.EXITED_FAILED
    assert proof.exit_code == 3
    assert "boom" in proof.output_tail
    assert provemod.outcome_to_provenance(proof.outcome) == provemod.UNPROVEN


def test_blank_launch_is_not_proven_and_nothing_started(tmp_path):
    # A blank launch is rejected before anything is spawned -- there is no command to start
    # a marker with, so this test only checks the Proof prove() actually returns, not an
    # on-disk side effect that a blank launch could never produce under any implementation.
    proof = provemod.prove(_candidate("   "), tmp_path)
    assert proof.outcome == provemod.NOT_PROVEN
    assert proof.exit_code is None
    assert "no launch command" in proof.reason
    assert proof.teardown_ok is True


def test_long_running_with_passing_precondition_is_running_ready(tmp_path):
    marker = tmp_path / "ready.marker"
    launch = _script(
        tmp_path, "server.py",
        "import pathlib, time\n"
        f"marker = pathlib.Path({str(marker)!r})\n"
        "time.sleep(0.3)\n"
        "marker.write_text('ready')\n"
        "time.sleep(30)\n",
    )
    precond_cmd = _script(
        tmp_path, "check_ready.py",
        "import pathlib, sys\n"
        f"marker = pathlib.Path({str(marker)!r})\n"
        "sys.exit(0 if marker.exists() else 1)\n",
    )
    proof = provemod.prove(
        _candidate(launch), tmp_path,
        preconditions=[{"name": "server ready", "cmd": precond_cmd}],
        ready_timeout_s=3,
    )
    assert proof.outcome == provemod.RUNNING_READY
    assert proof.precondition == "server ready"
    assert proof.exit_code is None
    assert proof.teardown_ok is True
    assert provemod.outcome_to_provenance(proof.outcome) == provemod.PROVEN


def test_long_running_no_precondition_is_not_proven_does_not_terminate(tmp_path):
    launch = _script(tmp_path, "hang.py", "import time\ntime.sleep(30)\n")
    proof = provemod.prove(_candidate(launch), tmp_path, exit_timeout_s=1)
    assert proof.outcome == provemod.NOT_PROVEN
    assert proof.exit_code is None
    assert "does not terminate" in proof.reason
    assert proof.teardown_ok is True


def test_long_running_precondition_never_passes_is_not_proven(tmp_path):
    launch = _script(tmp_path, "hang.py", "import time\ntime.sleep(30)\n")
    precond_cmd = _script(tmp_path, "never.py", "import sys\nsys.exit(1)\n")
    proof = provemod.prove(
        _candidate(launch), tmp_path,
        preconditions=[{"name": "never", "cmd": precond_cmd}],
        ready_timeout_s=1,
    )
    assert proof.outcome == provemod.NOT_PROVEN
    assert proof.precondition == ""
    assert proof.teardown_ok is True


def test_precondition_already_passing_at_baseline_prevents_launch(tmp_path):
    started_marker = tmp_path / "started.txt"
    launch = _script(
        tmp_path, "would_start.py",
        f"import pathlib\npathlib.Path({str(started_marker)!r}).write_text('started')\n",
    )
    precond_cmd = _script(tmp_path, "always.py", "import sys\nsys.exit(0)\n")
    proof = provemod.prove(
        _candidate(launch), tmp_path,
        preconditions=[{"name": "already up", "cmd": precond_cmd}],
    )
    assert proof.outcome == provemod.NOT_PROVEN
    assert "already up" in proof.reason
    assert proof.teardown_ok is True
    assert not started_marker.exists(), "the launch command must never have been started"


def test_regression_grandchild_process_and_tempfile_are_cleaned_up(tmp_path, monkeypatch):
    # This is the test that would have caught the original bug: shell=True makes the
    # process tree cmd.exe/sh -> the real program, and killing only the direct child
    # (Popen.kill()) leaves the grandchild running with the temp file still open.
    pidfile = tmp_path / "grandchild.pid"
    launch = _script(
        tmp_path, "grandchild.py",
        "import os, pathlib, time\n"
        f"pathlib.Path({str(pidfile)!r}).write_text(str(os.getpid()))\n"
        "time.sleep(30)\n",
    )

    created_paths: list[str] = []
    real_ntf = provemod.tempfile.NamedTemporaryFile

    def _spying_ntf(*args, **kwargs):
        handle = real_ntf(*args, **kwargs)
        created_paths.append(handle.name)
        return handle

    monkeypatch.setattr(provemod.tempfile, "NamedTemporaryFile", _spying_ntf)

    proof = provemod.prove(_candidate(launch), tmp_path, exit_timeout_s=1)

    assert proof.outcome == provemod.NOT_PROVEN
    assert proof.teardown_ok is True
    assert pidfile.exists(), "the grandchild should have had time to record its own pid"
    grandchild_pid = int(pidfile.read_text().strip())
    assert not _process_alive(grandchild_pid), "the grandchild must not survive prove()"

    assert len(created_paths) == 1
    assert not Path(created_paths[0]).exists(), "the temp output file must be removed"


def test_output_head_and_tail_are_both_captured(tmp_path):
    launch = _script(
        tmp_path, "chatty.py",
        "import sys\n"
        "sys.stdout.write('H' * 100)\n"
        "sys.stdout.write('M' * 6000)\n"
        "sys.stdout.write('T' * 100)\n",
    )
    proof = provemod.prove(_candidate(launch), tmp_path)
    assert proof.outcome == provemod.EXITED_CLEAN
    assert proof.output_head.startswith("H" * 50)
    assert proof.output_tail.endswith("T" * 50)
    assert proof.output_head != proof.output_tail


def _force_kill_real_pid(pid: int) -> None:
    """Clean up a process the test deliberately let _teardown fail to kill.

    Bypasses provemod entirely -- this calls the real OS kill directly, not the module's
    (monkeypatched, in this test) _kill_tree, so it works regardless of what the test did
    to the module under test.
    """
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(pid)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    else:
        try:
            os.killpg(pid, 9)
        except ProcessLookupError:
            pass


def test_teardown_failure_is_folded_into_reason(tmp_path, monkeypatch):
    # A no-op kill helper is the deterministic way to make teardown fail: the process is
    # still alive when prove() gives up on it, exactly like a kill that silently did nothing.
    pidfile = tmp_path / "leftover.pid"
    launch = _script(
        tmp_path, "hang.py",
        "import os, pathlib, time\n"
        f"pathlib.Path({str(pidfile)!r}).write_text(str(os.getpid()))\n"
        "time.sleep(30)\n",
    )
    monkeypatch.setattr(provemod, "_kill_tree", lambda process: True)
    monkeypatch.setattr(provemod, "_TEARDOWN_WAIT_S", 0.2)
    try:
        proof = provemod.prove(_candidate(launch), tmp_path, exit_timeout_s=0.5)
        assert proof.outcome == provemod.NOT_PROVEN
        assert proof.teardown_ok is False
        assert "could not be confirmed dead" in proof.reason
        # The original reason survives -- teardown failure is an addition, not a replacement.
        assert "does not terminate" in proof.reason
    finally:
        assert pidfile.exists(), "the script should have recorded its pid before sleeping"
        _force_kill_real_pid(int(pidfile.read_text().strip()))


def test_slow_precondition_does_not_blow_through_ready_deadline(tmp_path):
    launch = _script(tmp_path, "server.py", "import time\ntime.sleep(30)\n")
    # The baseline check (run once, uncapped, before anything is launched) must fail fast so
    # this test isolates the loop's capping behaviour rather than the baseline's -- the same
    # command runs in both places, so it only sleeps once a marker shows it has run before.
    marker = tmp_path / "precondition_seen.marker"
    slow_precondition = _script(
        tmp_path, "slow_check.py",
        "import pathlib, sys, time\n"
        f"marker = pathlib.Path({str(marker)!r})\n"
        "if marker.exists():\n"
        "    time.sleep(2)\n"
        "else:\n"
        "    marker.write_text('seen')\n"
        "sys.exit(1)\n",
    )
    ready_timeout_s = 0.3

    check_started = time.monotonic()
    proof = provemod.prove(
        _candidate(launch), tmp_path,
        preconditions=[{"name": "slow", "cmd": slow_precondition}],
        ready_timeout_s=ready_timeout_s,
    )
    elapsed = time.monotonic() - check_started

    assert proof.outcome == provemod.NOT_PROVEN
    # Bounded against the 0.3s deadline (plus generous poll/teardown slack), never against
    # the precondition's own 2s sleep or the 5s _PRECONDITION_TIMEOUT_S ceiling -- either of
    # those overshooting would be exactly the bug this test catches.
    assert elapsed < 1.5


def test_popen_failure_returns_not_proven_instead_of_raising(tmp_path):
    missing_root = tmp_path / "does_not_exist"
    launch = _script(tmp_path, "ok.py", "print(1)\n")

    proof = provemod.prove(_candidate(launch), missing_root)

    assert proof.outcome == provemod.NOT_PROVEN
    assert proof.exit_code is None
    assert proof.teardown_ok is True
    assert "failed to launch" in proof.reason
