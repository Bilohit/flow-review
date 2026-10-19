from __future__ import annotations

import os
import subprocess
import sys
import time

import pytest
from pathlib import Path

from flow_review.audit import Candidate
from flow_review import prove as provemod


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
    monkeypatch.setattr(provemod, "_kill_tree", lambda process: (True, set()))
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
    capped_marker = tmp_path / "capped_check_ran.marker"
    slow_precondition = _script(
        tmp_path, "slow_check.py",
        "import pathlib, sys, time\n"
        f"marker = pathlib.Path({str(marker)!r})\n"
        "if marker.exists():\n"
        f"    pathlib.Path({str(capped_marker)!r}).write_text('ran')\n"
        "    time.sleep(30)\n"
        "else:\n"
        "    marker.write_text('seen')\n"
        "sys.exit(1)\n",
    )
    # Long enough that the observe loop is still inside its deadline after the baseline check,
    # the launch and the first Windows descendant snapshot -- otherwise the loop sees a spent
    # budget and never runs the check, and the test would pass without exercising the cap.
    ready_timeout_s = 1.5

    check_started = time.monotonic()
    proof = provemod.prove(
        _candidate(launch), tmp_path,
        preconditions=[{"name": "slow", "cmd": slow_precondition}],
        ready_timeout_s=ready_timeout_s,
    )
    elapsed = time.monotonic() - check_started

    assert proof.outcome == provemod.NOT_PROVEN
    assert capped_marker.exists(), "the capped in-loop check never ran; test proves nothing"
    # Measured against the configured deadline plus a documented tolerance, never against the
    # precondition's own 30s sleep or the _PRECONDITION_TIMEOUT_S ceiling -- reaching that
    # ceiling is exactly the bug this test catches. The tolerance covers the work prove() does
    # outside the capped check, which on Windows is dominated by PowerShell process walks: one
    # throttled descendant snapshot (_DESCENDANT_SNAPSHOT_S) plus _kill_tree's fresh walk at
    # teardown, each a few hundred ms idle and ~1s under a loaded full-suite run (a flat 1.5s
    # bound failed once at 1.96s that way). The tolerance stays strictly below the ceiling, so
    # an uncapped check still fails this assertion.
    tolerance_s = 2.0
    assert ready_timeout_s + tolerance_s < provemod._PRECONDITION_TIMEOUT_S
    assert elapsed < ready_timeout_s + tolerance_s


def test_popen_failure_returns_not_proven_instead_of_raising(tmp_path):
    missing_root = tmp_path / "does_not_exist"
    launch = _script(tmp_path, "ok.py", "print(1)\n")

    proof = provemod.prove(_candidate(launch), missing_root)

    assert proof.outcome == provemod.NOT_PROVEN
    assert proof.exit_code is None
    assert proof.teardown_ok is True
    assert "failed to launch" in proof.reason


def _api_candidate(launch: str = "") -> Candidate:
    return Candidate(name="api", kind="api", driver="http", launch=launch, evidence="test:1 -> api")


# --- M3: api reachability-only proving --------------------------------------------------


def test_api_surface_with_passing_precondition_is_proven_without_launching_anything(tmp_path):
    marker = tmp_path / "should_not_exist.txt"
    precond_cmd = _script(tmp_path, "reachable.py", "import sys\nsys.exit(0)\n")
    proof = provemod.prove(
        _api_candidate(), tmp_path, preconditions=[{"name": "reachable", "cmd": precond_cmd}],
    )
    assert proof.outcome == provemod.RUNNING_READY
    assert proof.precondition == "reachable"
    assert provemod.outcome_to_provenance(proof.outcome) == provemod.PROVEN
    assert not marker.exists()


def test_api_surface_with_failing_precondition_is_not_proven(tmp_path):
    precond_cmd = _script(tmp_path, "unreachable.py", "import sys\nsys.exit(1)\n")
    proof = provemod.prove(
        _api_candidate(), tmp_path, preconditions=[{"name": "reachable", "cmd": precond_cmd}],
    )
    assert proof.outcome == provemod.NOT_PROVEN
    assert "api" in proof.reason.lower()


def test_api_surface_with_no_preconditions_is_not_proven_never_launches(tmp_path):
    proof = provemod.prove(_api_candidate(), tmp_path, preconditions=[])
    assert proof.outcome == provemod.NOT_PROVEN
    assert "reachability" in proof.reason.lower() or "precondition" in proof.reason.lower()


def test_a_non_api_blank_launch_still_reports_no_launch_command(tmp_path):
    proof = provemod.prove(_candidate("   "), tmp_path)
    assert proof.outcome == provemod.NOT_PROVEN
    assert "no launch command" in proof.reason


# --- H4: preconditions govern proof over a clean exit ------------------------------------


def test_a_clean_exit_before_any_precondition_passes_is_not_proven(tmp_path):
    # The launched command exits 0 almost immediately -- a wrapper that daemonizes and quits,
    # for example -- while the precondition that was supposed to confirm real readiness never
    # once passes. A clean exit code must not be mistaken for the readiness it never observed.
    launch = _script(tmp_path, "quits_clean.py", "import sys\nsys.exit(0)\n")
    precond_cmd = _script(tmp_path, "never_ready.py", "import sys\nsys.exit(1)\n")
    proof = provemod.prove(
        _candidate(launch), tmp_path,
        preconditions=[{"name": "ready", "cmd": precond_cmd}], ready_timeout_s=1,
    )
    assert proof.outcome == provemod.NOT_PROVEN
    assert provemod.outcome_to_provenance(proof.outcome) == provemod.UNPROVEN
    assert "exited cleanly" in proof.reason or "does not prove readiness" in proof.reason


def test_a_clean_exit_with_no_preconditions_is_still_proven(tmp_path):
    # Unaffected case: no preconditions were ever asked to prove anything, so the exit code is
    # still the whole story, exactly as before H4.
    launch = _script(tmp_path, "quits_clean2.py", "import sys\nsys.exit(0)\n")
    proof = provemod.prove(_candidate(launch), tmp_path)
    assert proof.outcome == provemod.EXITED_CLEAN


# --- H3: honest teardown when the direct child already exited ----------------------------


def test_a_grandchild_orphaned_by_an_already_exited_direct_child_is_still_reaped(tmp_path):
    """The regression H3 fixes: the launched command (run via shell=True, so its direct OS
    child is cmd.exe/sh) itself spawns a further child and then exits almost immediately,
    orphaning that grandchild. The old _teardown trusted `process.poll() is not None` as proof
    the whole tree was gone and returned early -- exactly wrong, since poll() only ever sees
    the direct child. teardown_ok must reflect the grandchild's ACTUAL fate, and the grandchild
    must actually be dead afterward."""
    pidfile = tmp_path / "orphan.pid"
    launch = _script(
        tmp_path, "quits_after_spawning.py",
        "import subprocess, sys, pathlib, time\n"
        f"child = subprocess.Popen([{str(sys.executable)!r}, '-c', "
        "'import pathlib,time; pathlib.Path(r\"" + str(pidfile).replace("\\", "\\\\") + "\").write_text(str(__import__(\"os\").getpid())); time.sleep(30)'])\n"
        "time.sleep(0.3)\n"
        "sys.exit(0)\n",
    )
    proof = provemod.prove(_candidate(launch), tmp_path, exit_timeout_s=5)
    assert proof.outcome == provemod.EXITED_CLEAN
    # Give the grandchild a moment to have written its own pidfile before asserting on it.
    for _ in range(20):
        if pidfile.exists():
            break
        time.sleep(0.1)
    assert pidfile.exists(), "the grandchild should have had time to record its own pid"
    orphan_pid = int(pidfile.read_text().strip())
    assert not _process_alive(orphan_pid), "the orphaned grandchild must not survive prove()"
    assert proof.teardown_ok is True


def test_descendant_snapshot_is_throttled_over_a_multi_second_prove(tmp_path, monkeypatch):
    # perf(prove): the Windows descendant walk shells out to PowerShell -- a few hundred ms --
    # so calling it on every _POLL_INTERVAL_S (0.1s) poll for the life of a multi-second launch
    # was needless cost. It should fire roughly once per _DESCENDANT_SNAPSHOT_S, plus one extra
    # snapshot right before teardown, not once per poll. On POSIX, _descendant_pids is never
    # called at all (the Windows-only branch), so this asserts the ceiling trivially there too.
    import math

    launch = _script(tmp_path, "wait_two_seconds.py", "import time\ntime.sleep(2)\n")
    calls = {"n": 0}
    real_descendant_pids = provemod._descendant_pids

    def _counting_descendant_pids(pid):
        calls["n"] += 1
        return real_descendant_pids(pid)

    monkeypatch.setattr(provemod, "_descendant_pids", _counting_descendant_pids)

    proof = provemod.prove(_candidate(launch), tmp_path, exit_timeout_s=5)

    assert proof.outcome == provemod.EXITED_CLEAN
    assert calls["n"] <= math.ceil(proof.duration_s) + 2


# ---- adb candidates (A-78) -------------------------------------------------------------------

from types import SimpleNamespace as _NS  # noqa: E402

from flow_review.android import adb as _adbmod  # noqa: E402

_FOCUS = "mCurrentFocus=Window{abc u0 com.x.app/com.x.app.Main}"
_OK_XML = '<hierarchy rotation="0"><node text="Home" /></hierarchy>'


def _adb_candidate(**opts) -> Candidate:
    base = {"app_id": "com.x.app", "device": "", "start_cmd": "", "metro_url": ""}
    base.update(opts)
    return Candidate(name="app", kind="ui", driver="adb", launch="", evidence="test:1 -> x",
                     options=base)


class _FakeAdb:
    """Recorded-output runner keyed on the adb args after the exe (and optional -s serial)."""

    def __init__(self, devices="List of devices attached\nemu-1\tdevice\n", installed=True,
                 pid="123", xml=_OK_XML, debuggable=True):
        self.calls: list[list[str]] = []
        self.debuggable = debuggable
        self.devices, self.installed, self.pid, self.xml = devices, installed, pid, xml

    def __call__(self, cmd, **kw):
        args = cmd[1:]
        if args[:1] == ["-s"]:
            args = args[2:]
        self.calls.append(args)
        out = ""
        if args == ["devices"]:
            out = self.devices
        elif args[:3] == ["shell", "pm", "list"]:
            out = "package:com.x.app\n" if self.installed else ""
        elif args[:3] == ["shell", "dumpsys", "package"]:
            out = "  pkgFlags=[ %sHAS_CODE ]\n" % ("DEBUGGABLE " if self.debuggable else "")
        elif args[:2] == ["shell", "dumpsys"]:
            out = _FOCUS
        elif args[0] == "shell" and "pidof" in args[1]:
            out = self.pid
        elif args[:2] == ["exec-out", "uiautomator"]:
            out = self.xml
        return _NS(returncode=0, stdout=out, stderr="")

    def ran(self, *prefix) -> bool:
        return any(c[:len(prefix)] == list(prefix) for c in self.calls)


@pytest.fixture
def _adb_present(monkeypatch):
    monkeypatch.setattr(_adbmod, "adb_path", lambda: "adb")


def _prove_adb(cand, fake):
    return provemod.prove_android(cand, runner=fake, sleep=lambda s: None)


def test_adb_ready_when_installed_foreground_and_clean_hierarchy(_adb_present):
    fake = _FakeAdb()
    proof = _prove_adb(_adb_candidate(), fake)
    assert proof.outcome == provemod.RUNNING_READY
    assert provemod.outcome_to_provenance(proof.outcome) == provemod.PROVEN
    assert fake.ran("shell", "monkey")  # monkey fronts a running app without a restart


def test_adb_starts_app_when_not_running(_adb_present):
    fake = _FakeAdb(pid="")
    assert _prove_adb(_adb_candidate(), fake).outcome == provemod.RUNNING_READY
    assert fake.ran("shell", "monkey", "-p", "com.x.app")


def test_adb_missing(monkeypatch):
    monkeypatch.setattr(_adbmod, "adb_path", lambda: None)
    proof = _prove_adb(_adb_candidate(), _FakeAdb())
    assert proof.outcome == provemod.NOT_PROVEN and "adb not found" in proof.reason


def test_adb_no_device(_adb_present):
    proof = _prove_adb(_adb_candidate(), _FakeAdb(devices="List of devices attached\n"))
    assert proof.outcome == provemod.NOT_PROVEN
    assert proof.reason == "no device: start an emulator or plug in a phone (adb devices)"


def test_adb_ambiguous_devices(_adb_present):
    two = "List of devices attached\na\tdevice\nb\tdevice\n"
    proof = _prove_adb(_adb_candidate(), _FakeAdb(devices=two))
    assert proof.outcome == provemod.NOT_PROVEN
    assert proof.reason == "ambiguous: set options.device to one of a, b"


def test_adb_explicit_device_skips_listing_and_is_passed(_adb_present):
    fake = _FakeAdb()
    _prove_adb(_adb_candidate(device="emu-9"), fake)
    assert not fake.ran("devices")


def test_adb_not_installed_expo_hint_and_plain_hint(_adb_present):
    p = _prove_adb(_adb_candidate(start_cmd="npx expo start"), _FakeAdb(installed=False))
    assert p.outcome == provemod.NOT_PROVEN and "npx expo run:android" in p.reason
    p = _prove_adb(_adb_candidate(), _FakeAdb(installed=False))
    assert "install the app on the device" in p.reason


def test_adb_metro_down(_adb_present, monkeypatch):
    monkeypatch.setattr(provemod, "_metro_running", lambda url: False)
    fake = _FakeAdb()
    p = _prove_adb(_adb_candidate(metro_url="http://127.0.0.1:8081",
                                  start_cmd="npx expo start --dev-client"), fake)
    assert p.outcome == provemod.NOT_PROVEN
    assert p.reason == "start Metro: npx expo start --dev-client"
    assert not fake.ran("reverse")


def test_adb_release_build_needs_no_metro(_adb_present, monkeypatch):
    monkeypatch.setattr(provemod, "_metro_running", lambda url: False)
    fake = _FakeAdb(debuggable=False)
    p = _prove_adb(_adb_candidate(metro_url="http://127.0.0.1:8081",
                                  start_cmd="npx expo start --dev-client"), fake)
    assert p.outcome == provemod.RUNNING_READY
    assert not fake.ran("reverse")


def test_adb_always_starts_and_uses_metro_url_port(_adb_present, monkeypatch):
    monkeypatch.setattr(provemod, "_metro_running", lambda url: True)
    fake = _FakeAdb(pid="123")
    p = _prove_adb(_adb_candidate(metro_url="http://127.0.0.1:19000", start_cmd="x"), fake)
    assert p.outcome == provemod.RUNNING_READY
    assert fake.ran("reverse", "tcp:19000", "tcp:19000")
    assert fake.ran("shell", "monkey")


def test_adb_metro_up_reverses_port(_adb_present, monkeypatch):
    monkeypatch.setattr(provemod, "_metro_running", lambda url: True)
    fake = _FakeAdb()
    p = _prove_adb(_adb_candidate(metro_url="http://127.0.0.1:8081", start_cmd="npx expo start"),
                   fake)
    assert p.outcome == provemod.RUNNING_READY
    assert fake.ran("reverse", "tcp:8081", "tcp:8081")


@pytest.mark.parametrize("text", ["Could not connect to development server",
                                  "Unable to load script", "Development servers"])
def test_adb_dev_launcher_or_red_box_is_not_proven(_adb_present, text):
    xml = f'<hierarchy><node text="{text}" /></hierarchy>'
    p = _prove_adb(_adb_candidate(), _FakeAdb(xml=xml))
    assert p.outcome == provemod.NOT_PROVEN and text in p.reason


def test_adb_never_issues_destructive_commands(_adb_present):
    fake = _FakeAdb(pid="")
    _prove_adb(_adb_candidate(), fake)
    flat = " ".join(" ".join(c) for c in fake.calls)
    for bad in ("force-stop", "pm clear", "uninstall", "install "):
        assert bad not in flat


def test_prove_dispatches_adb_candidates(monkeypatch, tmp_path):
    cand = _adb_candidate()
    monkeypatch.setattr(provemod, "prove_android", lambda c: "sentinel")
    assert provemod.prove(cand, tmp_path) == "sentinel"
