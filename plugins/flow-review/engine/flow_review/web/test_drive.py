# plugins/flow-review/engine/flow_review/web/test_drive.py
import argparse
import json
import os
import threading
import time
import urllib.error
import urllib.request
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

    def unroute_all(self):
        pass


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

    def fill(self, locator, value, secret=False):
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
    # A-26: only names the surface's `creds` points at may be resolved -- stand in for that
    # config with a monkeypatch rather than a full config.json, since fill() asks
    # envsetup.project_secret_names() for the allowed set.
    monkeypatch.setattr(drive.envsetup, "project_secret_names", lambda root: {"ADMIN_PASSWORD"})
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


def test_fill_from_env_falls_back_to_dotenv_and_records_name_only(tmp_path, monkeypatch):
    monkeypatch.setattr(drive.envsetup, "project_secret_names", lambda root: {"CP2_PW"})
    monkeypatch.delenv("CP2_PW", raising=False)
    run_dir, project_root = _dirs(tmp_path)
    (project_root / ".flow-review").mkdir(parents=True)
    (project_root / ".flow-review" / ".env").write_text("CP2_PW=Zq7hunter\n", encoding="utf-8")
    driver = FakeDriver()
    session = DriveSession(driver, "webapp", run_dir, project_root, record_enabled=True)
    session.flow_begin("login")
    session.fill({"css": "#pw"}, from_env="CP2_PW")
    result = session.flow_end("login", "ok")
    assert driver.filled[0][1] == "Zq7hunter"
    saved = actionlog.load(Path(result["log_path"]))
    assert "Zq7hunter" not in json.dumps(saved)
    assert saved["steps"][0]["from_env"] == "CP2_PW"
    assert saved["steps"][0]["value"] is None
    assert "Zq7hunter" not in json.dumps(events.redact("x Zq7hunter x"))


def test_fill_from_env_missing_raises_and_never_types_empty(tmp_path, monkeypatch):
    monkeypatch.delenv("NOPE_PW", raising=False)
    run_dir, project_root = _dirs(tmp_path)
    driver = FakeDriver()
    session = DriveSession(driver, "webapp", run_dir, project_root, record_enabled=False)
    with pytest.raises(Exception, match="NOPE_PW"):
        session.fill({"css": "#pw"}, from_env="NOPE_PW")
    assert driver.filled == []


def test_check_page_route_is_url_path_without_scheme_host_port(tmp_path, monkeypatch):
    run_dir, project_root = _dirs(tmp_path)
    routes = []
    monkeypatch.setattr(drive.measure, "check_page",
                        lambda d, s, f, route, t, i: routes.append(route) or [])
    driver = FakeDriver()
    driver.goto = lambda p: setattr(driver.page, "url", "http://127.0.0.1:8765" + p)
    session = DriveSession(driver, "webapp", run_dir, project_root, record_enabled=False)
    session.goto("/dash?x=1")
    assert routes == ["/dash"]


def test_client_post_surfaces_server_json_error_body(tmp_path):
    session = DriveSession(FakeDriver(), "webapp", *_dirs(tmp_path), record_enabled=False)
    httpd = drive.make_server("127.0.0.1", 0, session)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        with pytest.raises(Exception, match="unknown verb 'bogus'"):
            drive._post(httpd.server_address[1], "bogus", {})
    finally:
        httpd.shutdown()


def _raw_post(port, body_bytes, headers):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/action", data=body_bytes,
        headers=headers, method="POST",
    )
    return urllib.request.urlopen(req, timeout=5)


def test_server_rejects_any_request_carrying_an_origin_header(tmp_path):
    run_dir, project_root, state = _start_fake_server(tmp_path)
    body = json.dumps({"verb": "look", "args": {}}).encode("utf-8")
    try:
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _raw_post(state["port"], body, {
                "Content-Type": "application/json",
                "Origin": "http://127.0.0.1:9",  # even a same-host Origin: CLI never sends one
            })
        assert exc_info.value.code == 403
    finally:
        drive._post(state["port"], "stop", {})


def test_server_accepts_request_with_no_origin_header(tmp_path):
    run_dir, project_root, state = _start_fake_server(tmp_path)
    body = json.dumps({"verb": "look", "args": {}}).encode("utf-8")
    resp = _raw_post(state["port"], body, {"Content-Type": "application/json"})
    assert resp.status == 200
    drive._post(state["port"], "stop", {})


def test_server_rejects_oversized_body(tmp_path):
    import http.client
    run_dir, project_root, state = _start_fake_server(tmp_path)
    try:
        # Claim an oversized body via Content-Length but never write it: the server must
        # reject on the length alone, without waiting to read a body that was never sent.
        conn = http.client.HTTPConnection("127.0.0.1", state["port"], timeout=5)
        conn.putrequest("POST", "/action")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", str(drive.MAX_BODY + 1))
        conn.endheaders()
        assert conn.getresponse().status == 413
        conn.close()
    finally:
        drive._post(state["port"], "stop", {})


# --- R5: `drive fault` (B6, A-28) --------------------------------------------------------


def _fault_events(run_dir):
    lines = (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if json.loads(line).get("type") == "fault"]


@pytest.mark.web
def test_fault_offline_blocks_goto(tmp_path, webapp_server):
    from flow_review.web.driver import WebDriver
    base_url, _ = webapp_server
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    driver = WebDriver(headless=True)
    driver.launch(base_url)
    session = DriveSession(driver, "webapp", run_dir, tmp_path / "project", record_enabled=False)
    try:
        result = session.fault("offline", pattern=None, delay_ms=None)
        assert result == {"ok": True, "fault": {"kind": "offline", "pattern": None,
                                                  "delay_ms": None}}
        with pytest.raises(Exception):
            session.goto("/")
        fault_events = _fault_events(run_dir)
        assert fault_events and fault_events[0]["fault"]["kind"] == "offline"
    finally:
        driver.close()


@pytest.mark.web
def test_fault_5xx_matching_request_returns_503(tmp_path, webapp_server):
    from flow_review.web.driver import WebDriver
    base_url, _ = webapp_server
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    driver = WebDriver(headless=True)
    driver.launch(base_url)
    session = DriveSession(driver, "webapp", run_dir, tmp_path / "project", record_enabled=False)
    try:
        session.goto("/")
        session.fault("5xx", pattern="**/api/fail", delay_ms=None)
        session.click({"testid": "load-button"})
        assert any(n["status"] == 503 for n in driver.network_log())
    finally:
        driver.close()


@pytest.mark.web
def test_fault_slow_delays_matching_request(tmp_path, webapp_server):
    from flow_review.web.driver import WebDriver
    base_url, _ = webapp_server
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    driver = WebDriver(headless=True)
    driver.launch(base_url)
    session = DriveSession(driver, "webapp", run_dir, tmp_path / "project", record_enabled=False)
    try:
        session.goto("/")
        session.fault("slow", pattern="**/api/fail", delay_ms=1500)
        start = time.monotonic()
        session.click({"testid": "load-button"})
        elapsed = time.monotonic() - start
        assert elapsed >= 1.5
    finally:
        driver.close()


@pytest.mark.web
def test_fault_clear_restores_normal_behaviour(tmp_path, webapp_server):
    from flow_review.web.driver import WebDriver
    base_url, _ = webapp_server
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    driver = WebDriver(headless=True)
    driver.launch(base_url)
    session = DriveSession(driver, "webapp", run_dir, tmp_path / "project", record_enabled=False)
    try:
        session.fault("offline", pattern=None, delay_ms=None)
        result = session.clear_faults()
        assert result == {"ok": True, "fault": {"kind": "clear"}}
        session.goto("/")  # no longer aborted
        fault_events = _fault_events(run_dir)
        assert fault_events[-1]["fault"]["kind"] == "clear"
    finally:
        driver.close()


def test_fault_bad_args_rejected_with_json_error_style():
    def _ns(**overrides):
        base = {"surface": "webapp", "run_dir": "run", "kind": None, "pattern": None,
                "delay_ms": None, "clear": False}
        base.update(overrides)
        return argparse.Namespace(**base)

    with pytest.raises(ValueError, match="--kind"):
        drive.cmd_fault(_ns())
    with pytest.raises(ValueError, match="--pattern"):
        drive.cmd_fault(_ns(kind="5xx"))
    with pytest.raises(ValueError, match="--pattern"):
        drive.cmd_fault(_ns(kind="slow", delay_ms=1500))
    with pytest.raises(ValueError, match="--delay-ms"):
        drive.cmd_fault(_ns(kind="slow", pattern="**/api/*"))
    with pytest.raises(ValueError, match="--clear"):
        drive.cmd_fault(_ns(kind="offline", clear=True))


def test_dispatch_rejects_bad_fault_args_with_json_error_never_installing_a_handler(tmp_path):
    # m2: the drive server's own `_dispatch` must re-validate a `fault` verb's args the way
    # `cmd_fault` does client-side -- a malformed request must come back as a JSON error, never
    # reach `session.fault` and install a broken/partial fault handler.
    run_dir, project_root = _dirs(tmp_path)
    session = DriveSession(FakeDriver(), "webapp", run_dir, project_root, record_enabled=False)
    bound_cls = type("_BoundActionHandler", (drive._ActionHandler,), {"session": session})
    handler = object.__new__(bound_cls)  # skip BaseHTTPRequestHandler.__init__ (no real socket)
    with pytest.raises(ValueError, match="fault kind"):
        handler._dispatch("fault", {"kind": "bogus"})
    with pytest.raises(ValueError, match="pattern"):
        handler._dispatch("fault", {"kind": "5xx"})
    with pytest.raises(ValueError, match="delay_ms"):
        handler._dispatch("fault", {"kind": "slow", "pattern": "**/api/*"})
    with pytest.raises(ValueError, match="delay_ms"):
        handler._dispatch("fault", {"kind": "slow", "pattern": "**/api/*", "delay_ms": -5})
    assert session._active_5xx_patterns == []  # no partial fault ever got installed


def _findings(run_dir, rule=None):
    lines = (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    out = [json.loads(line) for line in lines if json.loads(line).get("type") == "finding"]
    return [f for f in out if rule is None or f.get("rule") == rule]


@pytest.mark.web
def test_fault_5xx_active_pattern_suppresses_its_own_http_5xx_finding(
    tmp_path, webapp_server, monkeypatch,
):
    monkeypatch.setattr(drive.measure, "check_page", _REAL_CHECK_PAGE)
    from flow_review.web.driver import WebDriver
    base_url, _ = webapp_server
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    driver = WebDriver(headless=True)
    driver.launch(base_url)
    session = DriveSession(driver, "webapp", run_dir, tmp_path / "project", record_enabled=False)
    try:
        session.goto("/")
        session.fault("5xx", pattern="**/api/fail", delay_ms=None)
        session.click({"testid": "load-button"})
        assert any(n["status"] == 503 for n in driver.network_log())
        assert _findings(run_dir, "http.5xx") == []
    finally:
        driver.close()


@pytest.mark.web
def test_fault_5xx_non_matching_url_genuine_5xx_still_filed(
    tmp_path, webapp_server, monkeypatch,
):
    monkeypatch.setattr(drive.measure, "check_page", _REAL_CHECK_PAGE)
    from flow_review.web.driver import WebDriver
    base_url, _ = webapp_server
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    driver = WebDriver(headless=True)
    driver.launch(base_url)
    session = DriveSession(driver, "webapp", run_dir, tmp_path / "project", record_enabled=False)
    try:
        session.goto("/")
        # An active 5xx fault for a URL that never matches /api/fail: the real backend's own
        # 500 (fixture always returns 500 for /api/fail, unrelated to any fault) must still be
        # reported -- only self-injected 5xx are suppressed.
        session.fault("5xx", pattern="**/api/broken", delay_ms=None)
        session.click({"testid": "load-button"})
        assert any(n["status"] == 500 for n in driver.network_log())
        assert any(f["rule"] == "http.5xx" for f in _findings(run_dir))
    finally:
        driver.close()


@pytest.mark.web
def test_fault_offline_suppresses_self_inflicted_console_error(
    tmp_path, webapp_server, monkeypatch,
):
    monkeypatch.setattr(drive.measure, "check_page", _REAL_CHECK_PAGE)
    from flow_review.web.driver import WebDriver
    base_url, _ = webapp_server
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    driver = WebDriver(headless=True)
    driver.launch(base_url)
    session = DriveSession(driver, "webapp", run_dir, tmp_path / "project", record_enabled=False)
    try:
        session.goto("/")
        session.fault("offline", pattern=None, delay_ms=None)
        try:
            session.click({"testid": "load-button"})
        except Exception:
            pass  # the click itself may fail while offline; only the finding suppression matters
        texts = [f["text"] for f in _findings(run_dir, "console.error")]
        assert not any(t.startswith("Failed to load resource") for t in texts)
        assert any(t.startswith("load error:") for t in texts)  # the app's own error still files
        assert _findings(run_dir, "http.5xx") == []
    finally:
        driver.close()


# --- fingerprint-based dedup of re-emitted findings --------------------------------------


def test_unchanged_finding_emitted_once_across_two_actions(tmp_path, monkeypatch):
    # measure.check_page runs on every action; an unfixed page defect (e.g. persistent low
    # contrast) comes back on every call. drive must only append its first occurrence per flow.
    run_dir, project_root = _dirs(tmp_path)
    finding = {
        "rule": "contrast.aa", "sev": "P1", "locator": "role:button[name=Pay]",
        "route": "/checkout", "text": "low contrast", "evidence": [], "disposition": "engine",
    }
    monkeypatch.setattr(drive.measure, "check_page", lambda *a, **k: [dict(finding)])

    driver = FakeDriver()
    session = DriveSession(driver, "webapp", run_dir, project_root, record_enabled=False)
    session.flow_begin("f1")
    first = session.click({"testid": "a"})
    second = session.click({"testid": "b"})

    assert len(first["new_findings"]) == 1
    assert second["new_findings"] == []
    assert len(_findings(run_dir, "contrast.aa")) == 1


def test_new_finding_on_second_action_still_emits(tmp_path, monkeypatch):
    run_dir, project_root = _dirs(tmp_path)
    repeated = {
        "rule": "contrast.aa", "sev": "P1", "locator": "role:button[name=Pay]",
        "route": "/checkout", "text": "low contrast", "evidence": [], "disposition": "engine",
    }
    fresh = {
        "rule": "http.5xx", "sev": "P0", "locator": None,
        "route": "/checkout", "text": "boom", "evidence": [], "disposition": "engine",
    }
    calls = {"n": 0}

    def _fake_check_page(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            return [dict(repeated)]
        return [dict(repeated), dict(fresh)]

    monkeypatch.setattr(drive.measure, "check_page", _fake_check_page)
    driver = FakeDriver()
    session = DriveSession(driver, "webapp", run_dir, project_root, record_enabled=False)
    session.flow_begin("f1")
    session.click({"testid": "a"})
    second = session.click({"testid": "b"})

    assert len(second["new_findings"]) == 1
    assert len(_findings(run_dir, "contrast.aa")) == 1
    assert len(_findings(run_dir, "http.5xx")) == 1


def test_p2_then_p1_console_error_on_same_route_both_emit(tmp_path, monkeypatch):
    # Console.error/http.5xx carry an empty locator, so the fingerprint alone (which does
    # not include sev/text) would collapse two genuinely distinct errors on the same route --
    # and would drop a later, more severe P1 as if it were an already-seen repeat.
    run_dir, project_root = _dirs(tmp_path)
    low = {"rule": "console.error", "sev": "P2", "locator": "", "route": "/checkout",
           "text": "warning: deprecated API", "evidence": [], "disposition": "engine"}
    high = {"rule": "console.error", "sev": "P1", "locator": "", "route": "/checkout",
            "text": "Uncaught TypeError: boom", "evidence": [], "disposition": "engine"}
    calls = {"n": 0}

    def _fake_check_page(*a, **k):
        calls["n"] += 1
        return [dict(low)] if calls["n"] == 1 else [dict(low), dict(high)]

    monkeypatch.setattr(drive.measure, "check_page", _fake_check_page)
    driver = FakeDriver()
    session = DriveSession(driver, "webapp", run_dir, project_root, record_enabled=False)
    session.flow_begin("f1")
    first = session.click({"testid": "a"})
    second = session.click({"testid": "b"})

    assert len(first["new_findings"]) == 1
    assert len(second["new_findings"]) == 1
    assert len(_findings(run_dir, "console.error")) == 2
    sevs = {f["sev"] for f in _findings(run_dir, "console.error")}
    assert sevs == {"P1", "P2"}


def test_identical_console_error_repeat_still_emitted_once(tmp_path, monkeypatch):
    run_dir, project_root = _dirs(tmp_path)
    finding = {"rule": "console.error", "sev": "P1", "locator": "", "route": "/checkout",
               "text": "Uncaught TypeError: boom", "evidence": [], "disposition": "engine"}
    monkeypatch.setattr(drive.measure, "check_page", lambda *a, **k: [dict(finding)])
    driver = FakeDriver()
    session = DriveSession(driver, "webapp", run_dir, project_root, record_enabled=False)
    session.flow_begin("f1")
    first = session.click({"testid": "a"})
    second = session.click({"testid": "b"})

    assert len(first["new_findings"]) == 1
    assert second["new_findings"] == []
    assert len(_findings(run_dir, "console.error")) == 1


def test_flow_begin_clears_faults_from_an_earlier_flow(tmp_path):
    # m1: a fault set during one flow must not outlive it into the next flow.
    run_dir, project_root = _dirs(tmp_path)
    session = DriveSession(FakeDriver(), "webapp", run_dir, project_root, record_enabled=False)
    session.flow_begin("f1")
    session._offline_active = True
    session._active_5xx_patterns = ["**/api/broken"]

    session.flow_begin("f2")

    assert session._offline_active is False
    assert session._active_5xx_patterns == []


def test_new_flow_re_reports_a_finding_seen_in_a_prior_flow(tmp_path, monkeypatch):
    # flow_begin resets the seen-set: the fingerprint includes flow_id anyway, so a new flow
    # must re-report a finding that looks the same as one already emitted this session.
    run_dir, project_root = _dirs(tmp_path)
    finding = {
        "rule": "contrast.aa", "sev": "P1", "locator": "role:button[name=Pay]",
        "route": "/checkout", "text": "low contrast", "evidence": [], "disposition": "engine",
    }
    monkeypatch.setattr(drive.measure, "check_page", lambda *a, **k: [dict(finding)])
    driver = FakeDriver()
    session = DriveSession(driver, "webapp", run_dir, project_root, record_enabled=False)
    session.flow_begin("f1")
    session.click({"testid": "a"})
    session.flow_end("f1", "ok")
    session.flow_begin("f2")
    result = session.click({"testid": "a"})

    assert len(result["new_findings"]) == 1
    assert len(_findings(run_dir, "contrast.aa")) == 2


def test_is_self_inflicted_matches_active_5xx_pattern_via_evidence_url(tmp_path):
    run_dir, project_root = _dirs(tmp_path)
    session = DriveSession(FakeDriver(), "webapp", run_dir, project_root, record_enabled=False)
    session._active_5xx_patterns = ["**/api/broken"]
    finding = {
        "rule": "http.5xx",
        "evidence": [json.dumps({"method": "GET", "url": "http://x/api/broken", "status": 503})],
    }
    assert session._is_self_inflicted(finding) is True
    other = {
        "rule": "http.5xx",
        "evidence": [json.dumps({"method": "GET", "url": "http://x/api/fail", "status": 500})],
    }
    assert session._is_self_inflicted(other) is False


def test_is_self_inflicted_keeps_real_app_console_errors_during_a_fault(tmp_path):
    run_dir, project_root = _dirs(tmp_path)
    session = DriveSession(FakeDriver(), "webapp", run_dir, project_root, record_enabled=False)
    session._offline_active = True
    browser_notice = {"rule": "console.error",
                      "text": "Failed to load resource: net::ERR_FAILED"}
    app_crash = {"rule": "console.error",
                 "text": "Uncaught (in promise) TypeError: Failed to fetch"}
    assert session._is_self_inflicted(browser_notice) is True
    assert session._is_self_inflicted(app_crash) is False
    session._offline_active = False
    session._active_5xx_patterns = ["**/api/broken"]
    assert session._is_self_inflicted(
        {"rule": "console.error",
         "text": "Failed to load resource: the server responded with a status of 503 ()"}) is True
    assert session._is_self_inflicted(app_crash) is False
