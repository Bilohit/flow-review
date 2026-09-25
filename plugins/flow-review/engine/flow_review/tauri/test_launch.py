import os
import time
from pathlib import Path

import pytest

_FIXTURE_BINARY = (Path(__file__).resolve().parents[2] / "fixtures" / "tauriapp" / "src-tauri"
                   / "target" / "release" / "tauriapp.exe")


def test_launch_native_sets_remote_debugging_port(monkeypatch, tmp_path):
    from flow_review.tauri.launch import launch_native
    captured = {}

    class FakePopen:
        def __init__(self, args, env=None, **kwargs):
            captured["args"] = args
            captured["env"] = env

    monkeypatch.setattr("subprocess.Popen", FakePopen)
    binary = tmp_path / "app.exe"
    binary.write_bytes(b"")
    launch_native(binary, port=9333)
    assert captured["args"][0] == str(binary)
    assert captured["env"]["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] == "--remote-debugging-port=9333"


def test_stop_native_kills_the_whole_process_tree(monkeypatch):
    from flow_review.tauri import launch as launch_mod
    ran = []
    monkeypatch.setattr(launch_mod.subprocess, "run", lambda args, **kw: ran.append(args))

    class FakeProc:
        pid = 4242
        killed = waited = False
        def kill(self):
            self.killed = True
        def wait(self, timeout=None):
            self.waited = True

    proc = FakeProc()
    launch_mod.stop_native(proc)
    assert proc.killed and proc.waited
    if os.name == "nt":
        assert ran == [["taskkill", "/F", "/T", "/PID", "4242"]]


@pytest.mark.web
@pytest.mark.skipif(os.name != "nt" or not _FIXTURE_BINARY.is_file(),
                    reason="needs the tauriapp release binary (CP1 builds it) on Windows")
def test_real_native_attach_sees_the_planted_console_error_and_leaves_no_process():
    pytest.importorskip("playwright")
    from flow_review.tauri.launch import launch_native, stop_native
    from flow_review.web.driver import WebDriver

    port = 9339
    proc = launch_native(_FIXTURE_BINARY, port)
    driver = None
    try:
        deadline = time.monotonic() + 20
        while driver is None:
            try:
                driver = WebDriver.attach(f"http://127.0.0.1:{port}")
            except Exception:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.5)
        driver.goto("/")
        driver.click({"css": "#save-note-button"})
        assert driver.console_errors_since_check()
    finally:
        if driver is not None:
            driver.close()
        stop_native(proc)
    assert proc.poll() is not None


def test_stop_native_never_raises_when_wait_times_out(monkeypatch):
    import subprocess
    from flow_review.tauri import launch as launch_mod
    monkeypatch.setattr(launch_mod.subprocess, "run", lambda args, **kw: None)

    class StuckProc:
        pid = 4243
        kills = 0
        def kill(self):
            self.kills += 1
        def wait(self, timeout=None):
            raise subprocess.TimeoutExpired("app.exe", timeout)

    proc = StuckProc()
    launch_mod.stop_native(proc)  # must not raise
    assert proc.kills >= 1


def test_stop_native_never_raises_on_oserror(monkeypatch):
    from flow_review.tauri import launch as launch_mod

    def boom(args, **kw):
        raise OSError("taskkill missing")
    monkeypatch.setattr(launch_mod.subprocess, "run", boom)

    class GoneProc:
        pid = 4244
        def kill(self):
            raise OSError("no such process")
        def wait(self, timeout=None):
            return 0

    launch_mod.stop_native(GoneProc())  # must not raise
