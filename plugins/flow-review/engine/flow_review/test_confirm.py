import json
from pathlib import Path

from flow_review import config as configmod
from flow_review import confirm as confirmmod
from flow_review import ledger as ledger_mod


def _write_config(project_root: Path, native) -> None:
    cfg = configmod.Config(
        schema_version=2, generator_version="test",
        surfaces=[configmod.Surface(
            id="desktop", name="desktop", kind="ui", driver="tauri", launch="",
            options={"native": native, "binary": "app.exe", "dev_url": "http://127.0.0.1:1421"},
        )],
    )
    (project_root / ".flow-review").mkdir(parents=True, exist_ok=True)
    configmod.save(cfg, project_root / ".flow-review" / "config.json")
    (project_root / "app.exe").write_bytes(b"")  # confirm refuses a binary that is not built


def _write_ledger(project_root: Path, last_run: str = "run1") -> None:
    entry = ledger_mod.LedgerEntry(
        id="f1", fingerprint="fp1", surface_id="desktop", flow_id="flow-1",
        rule="console.error", route="/", locator="css:#save-note-button", sev="P1",
        text="save_note swallowed into console.error", last_run=last_run,
    )
    ledger_mod.save(ledger_mod.Ledger(findings={"f1": entry}),
                     project_root / ".flow-review" / "findings.json")


def _write_repro(run_dir: Path, steps: list[dict]) -> None:
    (run_dir / "repro").mkdir(parents=True)
    (run_dir / "repro" / "flow-1.json").write_text(
        json.dumps({"surface_id": "desktop", "flow_id": "flow-1", "steps": steps}),
        encoding="utf-8",
    )


class FakeProc:
    pass


class FakeDriver:
    def __init__(self):
        self.actions = []
        self.closed = False

    def goto(self, path):
        self.actions.append(("goto", path))

    def click(self, locator):
        self.actions.append(("click", locator))

    def screenshot(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"fake-png")
        return path

    def close(self):
        self.closed = True


def _fake_check_page(rule):
    def check_page(driver, surface_id, flow_id, route, tokens, step_index):
        return [{"surface_id": surface_id, "flow_id": flow_id, "rule": rule, "route": route,
                 "locator": "", "sev": "P1", "text": "swallowed",
                 "evidence": [], "disposition": "engine"}]
    return check_page


def test_confirm_native_pending_writes_no_result_and_never_attaches(tmp_path, monkeypatch):
    _write_config(tmp_path, native="pending")
    _write_ledger(tmp_path)
    run_dir = tmp_path / "run1"
    run_dir.mkdir()

    def _boom(*a, **k):
        raise AssertionError("attach must never be called for a native: pending surface")

    monkeypatch.setattr(confirmmod.WebDriver, "attach", staticmethod(_boom))
    exit_code = confirmmod.confirm(tmp_path, run_dir)
    assert exit_code == 0
    assert not (run_dir / "native" / "f1" / "result.json").exists()
    lines = (run_dir / "events.jsonl").read_text(encoding="utf-8").strip().splitlines()
    payloads = [json.loads(line) for line in lines]
    assert any(
        p["type"] == "status" and p["state"] == "not-exercised" and p["reason"] == "native-pending"
        and p["surface_id"] == "desktop" and p["flow_id"] == "flow-1" and p["step"] == "confirm"
        for p in payloads
    )


def test_confirm_attach_failure_exits_3_kills_the_app_and_writes_no_ledger(tmp_path, monkeypatch):
    _write_config(tmp_path, native="webview2")
    _write_ledger(tmp_path)
    run_dir = tmp_path / "run1"
    _write_repro(run_dir, [{"action": "goto", "url": "/"}])
    ledger_path = tmp_path / ".flow-review" / "findings.json"
    before = ledger_path.read_bytes()

    launched, stopped = [], []
    proc = FakeProc()
    monkeypatch.setattr(confirmmod.tauri_launch, "launch_native",
                         lambda binary, port: launched.append((binary, port)) or proc)
    monkeypatch.setattr(confirmmod.tauri_launch, "stop_native", stopped.append)
    monkeypatch.setattr(confirmmod.WebDriver, "attach",
                         staticmethod(lambda cdp_url: (_ for _ in ()).throw(RuntimeError("no"))))
    monkeypatch.setattr(confirmmod, "ATTACH_RETRIES", 2)
    monkeypatch.setattr(confirmmod, "ATTACH_POLL_S", 0.01)

    exit_code = confirmmod.confirm(tmp_path, run_dir)
    assert exit_code == 3
    assert ledger_path.read_bytes() == before
    assert launched == [(tmp_path / "app.exe", 9333)]  # binary resolves against project_root
    assert stopped == [proc]


def test_confirm_reproduces_writes_result_and_appends_evidence(tmp_path, monkeypatch):
    _write_config(tmp_path, native="webview2")
    _write_ledger(tmp_path)
    run_dir = tmp_path / "run1"
    _write_repro(run_dir, [{"action": "goto", "url": "/"},
                           {"action": "click", "locator": {"testid": "save-note-button"}}])

    driver, stopped = FakeDriver(), []
    monkeypatch.setattr(confirmmod.tauri_launch, "launch_native", lambda binary, port: FakeProc())
    monkeypatch.setattr(confirmmod.tauri_launch, "stop_native", stopped.append)
    monkeypatch.setattr(confirmmod.WebDriver, "attach", staticmethod(lambda cdp_url: driver))
    monkeypatch.setattr(confirmmod.measure, "check_page", _fake_check_page("console.error"))

    exit_code = confirmmod.confirm(tmp_path, run_dir, port=9333)
    assert exit_code == 0
    assert driver.actions == [("goto", "/"), ("click", {"testid": "save-note-button"})]
    result = json.loads((run_dir / "native" / "f1" / "result.json").read_text(encoding="utf-8"))
    assert result["finding_id"] == "f1"
    assert result["reproduced"] is True
    assert (run_dir / "native" / "f1" / "shot.png").exists()
    lgr = ledger_mod.load(tmp_path / ".flow-review" / "findings.json")
    assert lgr.findings["f1"].evidence == ["native/f1/shot.png"]
    assert driver.closed and len(stopped) == 1


def test_confirm_not_reproduced_exits_1(tmp_path, monkeypatch):
    _write_config(tmp_path, native="webview2")
    _write_ledger(tmp_path)
    run_dir = tmp_path / "run1"
    _write_repro(run_dir, [{"action": "goto", "url": "/"}])

    stopped = []
    monkeypatch.setattr(confirmmod.tauri_launch, "launch_native", lambda binary, port: FakeProc())
    monkeypatch.setattr(confirmmod.tauri_launch, "stop_native", stopped.append)
    monkeypatch.setattr(confirmmod.WebDriver, "attach", staticmethod(lambda cdp_url: FakeDriver()))
    monkeypatch.setattr(confirmmod.measure, "check_page", _fake_check_page("contrast.aa"))

    assert confirmmod.confirm(tmp_path, run_dir) == 1
    result = json.loads((run_dir / "native" / "f1" / "result.json").read_text(encoding="utf-8"))
    assert result["reproduced"] is False
    assert len(stopped) == 1


def test_confirm_missing_repro_log_is_skipped_as_not_exercised_and_never_launches(tmp_path,
                                                                                   monkeypatch):
    # I2: an entry with no repro log in this run (nor a recording) cannot be replayed -- it is
    # skipped and reported not-exercised, never counted as "not reproduced"
    _write_config(tmp_path, native="webview2")
    _write_ledger(tmp_path)
    run_dir = tmp_path / "run1"
    run_dir.mkdir()

    def _boom(*a, **k):
        raise AssertionError("no repro log -> nothing to launch")

    monkeypatch.setattr(confirmmod.tauri_launch, "launch_native", _boom)
    assert confirmmod.confirm(tmp_path, run_dir) == 0
    payloads = [json.loads(line) for line in
                (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(p["state"], p["reason"], p["flow_id"], p["step"]) for p in payloads] == [
        ("not-exercised", "no-repro-log", "flow-1", "confirm")]


def test_confirm_skips_entries_not_seen_this_run(tmp_path, monkeypatch):
    # I2: an older open P0/P1 whose last_run is another run is not this run's to confirm
    _write_config(tmp_path, native="webview2")
    _write_ledger(tmp_path, last_run="run0")
    run_dir = tmp_path / "run1"
    _write_repro(run_dir, [{"action": "goto", "url": "/"}])

    def _boom(*a, **k):
        raise AssertionError("an entry from another run must not launch the app")

    monkeypatch.setattr(confirmmod.tauri_launch, "launch_native", _boom)
    assert confirmmod.confirm(tmp_path, run_dir) == 0
    assert not (run_dir / "native").exists()


def test_confirm_falls_back_to_the_recordings_path(tmp_path, monkeypatch):
    # I3: with recording on, actionlog.save writes .flow-review/recordings/<surface>/<flow>.json
    _write_config(tmp_path, native="webview2")
    _write_ledger(tmp_path)
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    rec = tmp_path / ".flow-review" / "recordings" / "desktop" / "flow-1.json"
    rec.parent.mkdir(parents=True)
    rec.write_text(json.dumps({"surface_id": "desktop", "flow_id": "flow-1",
                               "steps": [{"action": "goto", "url": "/rec"}]}), encoding="utf-8")

    driver = FakeDriver()
    monkeypatch.setattr(confirmmod.tauri_launch, "launch_native", lambda binary, port: FakeProc())
    monkeypatch.setattr(confirmmod.tauri_launch, "stop_native", lambda proc: None)
    monkeypatch.setattr(confirmmod.WebDriver, "attach", staticmethod(lambda cdp_url: driver))
    monkeypatch.setattr(confirmmod.measure, "check_page", _fake_check_page("console.error"))
    assert confirmmod.confirm(tmp_path, run_dir) == 0
    assert driver.actions == [("goto", "/rec")]


def test_confirm_port_in_use_exits_3_before_launching(tmp_path, monkeypatch, capsys):
    # I4: something already listening on the CDP port would be attached to instead of the app
    import socket
    _write_config(tmp_path, native="webview2")
    _write_ledger(tmp_path)
    run_dir = tmp_path / "run1"
    _write_repro(run_dir, [{"action": "goto", "url": "/"}])
    ledger_path = tmp_path / ".flow-review" / "findings.json"
    before = ledger_path.read_bytes()

    def _boom(*a, **k):
        raise AssertionError("must not launch onto a busy port")

    monkeypatch.setattr(confirmmod.tauri_launch, "launch_native", _boom)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        assert confirmmod.confirm(tmp_path, run_dir, port=port) == 3
    err = capsys.readouterr().err
    assert str(port) in err and "--port" in err
    assert ledger_path.read_bytes() == before


def test_confirm_missing_binary_option_or_file_exits_3_with_a_message(tmp_path, monkeypatch,
                                                                     capsys):
    # I5: "not built yet" is a config/env error (exit 3), never a traceback
    _write_config(tmp_path, native="webview2")
    _write_ledger(tmp_path)
    run_dir = tmp_path / "run1"
    _write_repro(run_dir, [{"action": "goto", "url": "/"}])
    ledger_path = tmp_path / ".flow-review" / "findings.json"
    before = ledger_path.read_bytes()

    def _boom(*a, **k):
        raise AssertionError("must not launch a missing binary")

    monkeypatch.setattr(confirmmod.tauri_launch, "launch_native", _boom)
    (tmp_path / "app.exe").unlink()
    assert confirmmod.confirm(tmp_path, run_dir) == 3
    assert "app.exe" in capsys.readouterr().err

    cfg = configmod.load(tmp_path / ".flow-review" / "config.json")
    del cfg.surfaces[0].options["binary"]
    configmod.save(cfg, tmp_path / ".flow-review" / "config.json")
    assert confirmmod.confirm(tmp_path, run_dir) == 3
    assert "binary" in capsys.readouterr().err
    assert ledger_path.read_bytes() == before


def test_confirm_replay_error_still_closes_and_stops(tmp_path, monkeypatch):
    _write_config(tmp_path, native="webview2")
    _write_ledger(tmp_path)
    run_dir = tmp_path / "run1"
    _write_repro(run_dir, [{"action": "goto", "url": "/"}])

    class ExplodingDriver(FakeDriver):
        def goto(self, path):
            raise RuntimeError("page crashed")

    driver, stopped = ExplodingDriver(), []
    monkeypatch.setattr(confirmmod.tauri_launch, "launch_native", lambda binary, port: FakeProc())
    monkeypatch.setattr(confirmmod.tauri_launch, "stop_native", stopped.append)
    monkeypatch.setattr(confirmmod.WebDriver, "attach", staticmethod(lambda cdp_url: driver))

    assert confirmmod.confirm(tmp_path, run_dir) == 1
    result = json.loads((run_dir / "native" / "f1" / "result.json").read_text(encoding="utf-8"))
    assert result["reproduced"] is False and "page crashed" in result["error"]
    assert driver.closed and len(stopped) == 1


def test_confirm_redacts_registered_secrets_in_result_json(tmp_path, monkeypatch):
    from flow_review import events
    _write_config(tmp_path, native="webview2")
    _write_ledger(tmp_path)
    run_dir = tmp_path / "run1"
    _write_repro(run_dir, [{"action": "goto", "url": "/"}])

    def leaky_check_page(driver, surface_id, flow_id, route, tokens, step_index):
        return [{"surface_id": surface_id, "flow_id": flow_id, "rule": "console.error",
                 "route": route, "locator": "", "sev": "P1",
                 "text": "login failed for pw=hunter2secret", "evidence": [],
                 "disposition": "engine"}]

    monkeypatch.setattr(confirmmod.tauri_launch, "launch_native", lambda binary, port: FakeProc())
    monkeypatch.setattr(confirmmod.tauri_launch, "stop_native", lambda proc: None)
    monkeypatch.setattr(confirmmod.WebDriver, "attach", staticmethod(lambda cdp_url: FakeDriver()))
    monkeypatch.setattr(confirmmod.measure, "check_page", leaky_check_page)
    events.register_secret("hunter2secret")
    try:
        assert confirmmod.confirm(tmp_path, run_dir) == 0
    finally:
        events.clear_secrets()
    raw = (run_dir / "native" / "f1" / "result.json").read_text(encoding="utf-8")
    assert "hunter2secret" not in raw
    assert events.REDACTED in raw


def test_confirm_corrupt_repro_log_is_not_reproduced_not_a_crash(tmp_path, monkeypatch):
    _write_config(tmp_path, native="webview2")
    _write_ledger(tmp_path)
    run_dir = tmp_path / "run1"
    (run_dir / "repro").mkdir(parents=True)
    (run_dir / "repro" / "flow-1.json").write_text("{not json", encoding="utf-8")

    stopped = []
    monkeypatch.setattr(confirmmod.tauri_launch, "launch_native", lambda binary, port: FakeProc())
    monkeypatch.setattr(confirmmod.tauri_launch, "stop_native", stopped.append)
    monkeypatch.setattr(confirmmod.WebDriver, "attach", staticmethod(lambda cdp_url: FakeDriver()))

    assert confirmmod.confirm(tmp_path, run_dir) == 1
    result = json.loads((run_dir / "native" / "f1" / "result.json").read_text(encoding="utf-8"))
    assert result["reproduced"] is False and "JSONDecodeError" in result["error"]
    assert len(stopped) == 1


def test_confirm_repro_log_missing_steps_is_not_reproduced(tmp_path, monkeypatch):
    _write_config(tmp_path, native="webview2")
    _write_ledger(tmp_path)
    run_dir = tmp_path / "run1"
    (run_dir / "repro").mkdir(parents=True)
    (run_dir / "repro" / "flow-1.json").write_text('{"flow_id": "flow-1"}', encoding="utf-8")

    monkeypatch.setattr(confirmmod.tauri_launch, "launch_native", lambda binary, port: FakeProc())
    monkeypatch.setattr(confirmmod.tauri_launch, "stop_native", lambda proc: None)
    monkeypatch.setattr(confirmmod.WebDriver, "attach", staticmethod(lambda cdp_url: FakeDriver()))

    assert confirmmod.confirm(tmp_path, run_dir) == 1
    result = json.loads((run_dir / "native" / "f1" / "result.json").read_text(encoding="utf-8"))
    assert result["reproduced"] is False and "KeyError" in result["error"]


def test_confirm_two_surfaces_stops_first_app_before_launching_second(tmp_path, monkeypatch):
    cfg = configmod.Config(
        schema_version=2, generator_version="test",
        surfaces=[configmod.Surface(
            id=sid, name=sid, kind="ui", driver="tauri", launch="",
            options={"native": "webview2", "binary": f"{sid}.exe",
                     "dev_url": "http://127.0.0.1:1421"},
        ) for sid in ("desk-a", "desk-b")],
    )
    (tmp_path / ".flow-review").mkdir(parents=True)
    configmod.save(cfg, tmp_path / ".flow-review" / "config.json")
    for sid in ("desk-a", "desk-b"):
        (tmp_path / f"{sid}.exe").write_bytes(b"")
    entries = {
        f"f{i}": ledger_mod.LedgerEntry(
            id=f"f{i}", fingerprint=f"fp{i}", surface_id=sid, flow_id=f"flow-{i}",
            rule="console.error", route="/", locator="", sev="P1", text="swallowed",
            last_run="run1",
        ) for i, sid in ((1, "desk-a"), (2, "desk-b"))
    }
    ledger_mod.save(ledger_mod.Ledger(findings=entries), tmp_path / ".flow-review" / "findings.json")
    run_dir = tmp_path / "run1"
    (run_dir / "repro").mkdir(parents=True)
    for i in (1, 2):
        (run_dir / "repro" / f"flow-{i}.json").write_text(
            json.dumps({"flow_id": f"flow-{i}", "steps": [{"action": "goto", "url": "/"}]}),
            encoding="utf-8")

    calls = []

    def launch(binary, port):
        proc = FakeProc()
        proc.name = Path(binary).stem
        calls.append(("launch", proc.name))
        return proc

    monkeypatch.setattr(confirmmod.tauri_launch, "launch_native", launch)
    monkeypatch.setattr(confirmmod.tauri_launch, "stop_native",
                        lambda proc: calls.append(("stop", proc.name)))
    monkeypatch.setattr(confirmmod.WebDriver, "attach", staticmethod(lambda cdp_url: FakeDriver()))
    monkeypatch.setattr(confirmmod.measure, "check_page", _fake_check_page("console.error"))

    assert confirmmod.confirm(tmp_path, run_dir) == 0
    assert calls == [("launch", "desk-a"), ("stop", "desk-a"),
                     ("launch", "desk-b"), ("stop", "desk-b")]
