# plugins/flow-review/engine/flow_review/web/test_drive.py
import argparse
import json
import os
import threading
import time
from pathlib import Path

import pytest

from flow_review import events
from flow_review.web import actionlog, drive
from flow_review.web.drive import DriveSession

_REAL_CHECK_PAGE = drive.measure.check_page  # the autouse stub replaces it; e2e restores it


class FakePage:
    def __init__(self):
        self.url = "http://fake/"
        self.keyboard = self

    def press(self, key):
        self.pressed = key

    def title(self):
        return "Fake Page"


class FakeDriver:
    def __init__(self):
        self.page = FakePage()
        self.closed = False
        self.clicked = []
        self.filled = []
        self._shots = []

    def launch(self, base_url):
        self.base_url = base_url

    def goto(self, path):
        self.page.url = "http://fake" + path

    def click(self, locator):
        self.clicked.append(locator)

    def fill(self, locator, value):
        self.filled.append((locator, value))

    def press(self, key):
        self.page.keyboard.press(key)

    def is_password(self, locator):
        return locator.get("testid") == "pw-input"

    def snapshot(self):
        return {"role": "WebArea", "name": "Fake"}

    def console_errors(self):
        return []

    def network_log(self):
        return []

    def begin_step(self, step_index):
        self._step = step_index

    def end_step(self):
        self._step = None

    def screenshot(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"fake-png")
        self._shots.append(path)
        return path

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def _stub_check_page(monkeypatch):
    monkeypatch.setattr(drive.measure, "check_page", lambda *a, **k: [])


def _dirs(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    return run_dir, tmp_path / "project"


def test_fill_password_redacts_even_with_text(tmp_path):
    run_dir, project_root = _dirs(tmp_path)
    driver = FakeDriver()
    session = DriveSession(driver, "webapp", run_dir, project_root, record_enabled=True)
    session.flow_begin("login")
    session.fill({"testid": "pw-input"}, text="hunter2")
    result = session.flow_end("login", "ok")
    saved = actionlog.load(Path(result["log_path"]))
    dumped = json.dumps(saved)
    assert "hunter2" not in dumped
    assert saved["steps"][0]["value"] == events.REDACTED
    assert driver.filled[0][1] == "hunter2"  # the real page still got filled


def test_fill_from_env_reads_environ_and_redacts(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "s3cret")
    run_dir, project_root = _dirs(tmp_path)
    driver = FakeDriver()
    session = DriveSession(driver, "webapp", run_dir, project_root, record_enabled=False)
    session.flow_begin("login")
    session.fill({"css": "#password"}, from_env="ADMIN_PASSWORD")
    result = session.flow_end("login", "ok")
    saved = actionlog.load(Path(result["log_path"]))
    assert "s3cret" not in json.dumps(saved)
    assert driver.filled[0][1] == "s3cret"


def test_click_calls_check_page_with_route_tokens_step_index_and_appends_findings(
    tmp_path, monkeypatch,
):
    run_dir, project_root = _dirs(tmp_path)
    calls = []
    finding = {
        "rule": "http.5xx", "sev": "P0", "locator": None, "route": "http://fake/",
        "text": "boom", "evidence": [], "disposition": "engine",
    }

    def _fake_check_page(driver, surface_id, flow_id, route, tokens, step_index):
        calls.append(dict(
            surface_id=surface_id, flow_id=flow_id, route=route,
            tokens=tokens, step_index=step_index,
        ))
        return [finding]

    monkeypatch.setattr(drive.measure, "check_page", _fake_check_page)

    driver = FakeDriver()
    session = DriveSession(
        driver, "webapp", run_dir, project_root, record_enabled=False,
        tokens={"color.primary": "#1a56db"},
    )
    session.flow_begin("f1")
    result = session.click({"testid": "load-button"})

    assert result["new_findings"]
    assert calls[0]["surface_id"] == "webapp"
    assert calls[0]["flow_id"] == "f1"
    assert calls[0]["tokens"] == {"color.primary": "#1a56db"}
    assert calls[0]["step_index"] == 0
    written = (run_dir / "events.jsonl").read_text(encoding="utf-8")
    assert "http.5xx" in written


def test_look_passes_step_index_none():
    calls = []

    def _fake_check_page(driver, surface_id, flow_id, route, tokens, step_index):
        calls.append(step_index)
        return []

    import flow_review.web.drive as drive_mod
    orig = drive_mod.measure.check_page
    drive_mod.measure.check_page = _fake_check_page
    try:
        driver = FakeDriver()
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            run_dir.mkdir()
            session = DriveSession(driver, "webapp", run_dir, Path(td) / "project",
                                    record_enabled=False)
            session.look()
    finally:
        drive_mod.measure.check_page = orig
    assert calls == [None]


def test_snapshot_is_trimmed_to_4000_chars(tmp_path):
    run_dir, project_root = _dirs(tmp_path)
    driver = FakeDriver()
    driver.snapshot = lambda: {"role": "WebArea", "name": "x" * 10000}
    session = DriveSession(driver, "webapp", run_dir, project_root, record_enabled=False)
    result = session.goto("/")
    assert len(result["snapshot"]) <= 4000


def test_flow_end_saves_recording_when_record_enabled(tmp_path):
    run_dir, project_root = _dirs(tmp_path)
    driver = FakeDriver()
    session = DriveSession(driver, "webapp", run_dir, project_root, record_enabled=True)
    session.flow_begin("f1")
    session.goto("/")
    result = session.flow_end("f1", "ok")
    assert Path(result["log_path"]) == (
        project_root / ".flow-review" / "recordings" / "webapp" / "f1.json"
    )


def test_flow_end_saves_ephemeral_repro_when_record_disabled(tmp_path):
    run_dir, project_root = _dirs(tmp_path)
    driver = FakeDriver()
    session = DriveSession(driver, "webapp", run_dir, project_root, record_enabled=False)
    session.flow_begin("f1")
    session.goto("/")
    result = session.flow_end("f1", "ok")
    assert Path(result["log_path"]) == run_dir / "repro" / "f1.json"


def test_press_and_click_return_compact_result_shape(tmp_path):
    run_dir, project_root = _dirs(tmp_path)
    driver = FakeDriver()
    session = DriveSession(driver, "webapp", run_dir, project_root, record_enabled=False)
    result = session.press("Enter")
    assert set(result) == {"url", "title", "snapshot", "shot", "new_findings", "console_errors"}
    assert driver.page.pressed == "Enter"

# appended to plugins/flow-review/engine/flow_review/web/test_drive.py

def _start_fake_server(tmp_path, record_enabled=False):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    project_root = tmp_path / "project"

    def factory(headless, viewport):
        return FakeDriver()

    thread = threading.Thread(
        target=drive.serve,
        args=("webapp", run_dir, project_root, "http://fake/"),
        kwargs={"record_enabled": record_enabled, "driver_factory": factory},
        daemon=True,
    )
    thread.start()

    state_path = run_dir / "drive" / "webapp.json"
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not state_path.exists():
        time.sleep(0.05)
    assert state_path.exists(), "drive server did not write its state file in time"
    return run_dir, project_root, json.loads(state_path.read_text())


def test_server_dispatches_actions_over_http_and_stops_cleanly(tmp_path):
    run_dir, project_root, state = _start_fake_server(tmp_path)

    begin = drive._post(state["port"], "flow-begin", {"flow": "f1"})
    assert begin["flow_id"] == "f1"

    goto = drive._post(state["port"], "goto", {"path": "/"})
    assert goto["url"] == "http://fake/"

    click = drive._post(state["port"], "click", {"locator": {"testid": "x"}})
    assert "new_findings" in click

    end = drive._post(state["port"], "flow-end", {"flow": "f1", "status": "ok"})
    assert end["status"] == "ok"

    stopped = drive._post(state["port"], "stop", {})
    assert stopped["stopped"] is True

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and (run_dir / "drive" / "webapp.json").exists():
        time.sleep(0.05)
    assert not (run_dir / "drive" / "webapp.json").exists()


def test_cli_client_reads_state_file_and_posts(tmp_path):
    run_dir, project_root, state = _start_fake_server(tmp_path)
    ns = argparse.Namespace(surface="webapp", run_dir=str(run_dir), path="/dashboard")
    result = drive.cmd_goto(ns)
    assert result["url"] == "http://fake/dashboard"
    drive._post(state["port"], "stop", {})


def test_cli_client_raises_when_no_session_started(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    ns = argparse.Namespace(surface="webapp", run_dir=str(run_dir), path="/")
    with pytest.raises(RuntimeError):
        drive.cmd_goto(ns)


def test_start_reuses_live_state_file_without_spawning(tmp_path, monkeypatch):
    run_dir = tmp_path / "run"
    (run_dir / "drive").mkdir(parents=True)
    (run_dir / "drive" / "webapp.json").write_text(
        json.dumps({"port": 9999, "pid": os.getpid()})
    )

    def _boom(*a, **kw):
        raise AssertionError("must not spawn a new server when a live state file exists")

    monkeypatch.setattr(drive.subprocess, "Popen", _boom)

    ns = argparse.Namespace(surface="webapp", run_dir=str(run_dir),
                             project_root=str(tmp_path / "project"), record=False)
    result = drive.cmd_start(ns)
    assert result == {"surface_id": "webapp", "port": 9999}


def test_start_resolves_base_url_tokens_and_record_from_config(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    (project_root / ".flow-review").mkdir(parents=True)
    (project_root / ".flow-review" / "config.json").write_text(json.dumps({
        "schema_version": 2, "generator_version": "2.0.0", "model_profile": "default",
        "role_overrides": {}, "budget": {"cap_tokens": None}, "test_inbox": None,
        "flows_hash": "", "surfaces": [{
            "id": "webapp", "name": "Web app", "kind": "ui", "driver": "playwright",
            "launch": "npm run dev", "cwd": ".", "env": {},
            "options": {
                "base_url": "http://localhost:5173", "health_path": "/healthz",
                "ready_timeout_s": 15, "exit_timeout_s": 60,
                "viewport": [{"width": 1280, "height": 800}], "tokens_file": None,
            },
            "preconditions": [], "state": "disposable", "reset": None, "creds": {},
            "record": True, "provenance": {}, "declined": False,
        }],
    }))
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    captured = {}

    def _fake_popen(cmd, **kw):
        captured["cmd"] = cmd
        (run_dir / "drive").mkdir(parents=True, exist_ok=True)
        (run_dir / "drive" / "webapp.json").write_text(
            json.dumps({"port": 4321, "pid": os.getpid()})
        )
        return None

    monkeypatch.setattr(drive.subprocess, "Popen", _fake_popen)

    ns = argparse.Namespace(surface="webapp", run_dir=str(run_dir),
                             project_root=str(project_root), record=False)
    result = drive.cmd_start(ns)
    assert result == {"surface_id": "webapp", "port": 4321}
    assert "--base-url" in captured["cmd"]
    assert "http://localhost:5173" in captured["cmd"]
    assert "--record" in captured["cmd"]  # from surface.record, not args.record
    assert "--viewport-width" in captured["cmd"]

# appended to plugins/flow-review/engine/flow_review/web/test_drive.py
import pytest
pytest.importorskip("playwright")


@pytest.mark.web
def test_drive_e2e_sign_in_finds_low_contrast(tmp_path, webapp_server, monkeypatch):
    monkeypatch.setattr(drive.measure, "check_page", _REAL_CHECK_PAGE)
    base_url, _ = webapp_server
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    project_root = tmp_path / "project"

    thread = threading.Thread(
        target=drive.serve,
        args=("webapp", run_dir, project_root, base_url),
        kwargs={"record_enabled": False},
        daemon=True,
    )
    thread.start()

    state_path = run_dir / "drive" / "webapp.json"
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and not state_path.exists():
        time.sleep(0.1)
    assert state_path.exists()
    state = json.loads(state_path.read_text())

    drive._post(state["port"], "flow-begin", {"flow": "sign-in"})
    drive._post(state["port"], "goto", {"path": "/"})
    look = drive._post(state["port"], "look", {"shot": False})
    drive._post(state["port"], "flow-end", {"flow": "sign-in", "status": "ok"})
    drive._post(state["port"], "stop", {})
    thread.join(timeout=15)
    assert not thread.is_alive()

    written = (run_dir / "events.jsonl").read_text(encoding="utf-8")
    assert "contrast.aa" in written
    assert look["new_findings"] or "contrast.aa" in written
