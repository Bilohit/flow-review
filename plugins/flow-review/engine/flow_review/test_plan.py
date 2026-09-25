import json

from flow_review import plan as plan_mod


def _write_project(tmp_path, creds=None, state="disposable"):
    fr_dir = tmp_path / ".flow-review"
    fr_dir.mkdir()
    cfg = {
        "schema_version": 2,
        "generator_version": "2.0.0",
        "surfaces": [
            {
                "id": "webapp", "name": "webapp", "kind": "ui", "driver": "playwright",
                "launch": "npm run dev", "cwd": ".", "env": {},
                "options": {
                    "base_url": "http://127.0.0.1:9", "health_path": "/",
                    "ready_timeout_s": 5,
                    "viewport": [{"width": 375, "height": 812}],
                },
                "preconditions": [], "state": state, "reset": None,
                "creds": creds or {}, "record": False, "provenance": {}, "declined": False,
            }
        ],
        "model_profile": "default", "role_overrides": {},
        "budget": {"cap_tokens": None}, "test_inbox": None, "flows_hash": "",
    }
    (fr_dir / "config.json").write_text(json.dumps(cfg))
    return tmp_path


def test_plan_goal_mode_reports_missing_creds_gap(tmp_path, monkeypatch):
    monkeypatch.delenv("WEBAPP_PASSWORD", raising=False)
    project_root = _write_project(tmp_path, creds={"password": "WEBAPP_PASSWORD"})
    result = plan_mod.plan(project_root, mode="goal", goal="checkout")
    surf = result["surfaces"][0]
    assert any(g["type"] == "missing_creds" and g["name"] == "WEBAPP_PASSWORD" for g in surf["gaps"])
    assert result["total_estimate_tokens"] == surf["estimate_tokens"]


def test_plan_skip_removes_surface(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_PASSWORD", "x")
    project_root = _write_project(tmp_path, creds={"password": "WEBAPP_PASSWORD"})
    result = plan_mod.plan(project_root, mode="auto", skip=["webapp"])
    assert result["surfaces"] == []
    assert result["skipped_surfaces"] == ["webapp"]


def test_plan_persistent_surface_gets_one_destructive_optin_gap(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_PASSWORD", "x")
    project_root = _write_project(tmp_path, creds={"password": "WEBAPP_PASSWORD"}, state="persistent")
    result = plan_mod.plan(project_root, mode="full")
    assert len(result["gaps"]) == 1
    gap = result["gaps"][0]
    assert gap["type"] == "destructive_optin"
    assert gap["surfaces"] == ["webapp"]
    assert gap["opt_in_default"] is False


def test_plan_quick_mode_has_no_lens_units(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_PASSWORD", "x")
    project_root = _write_project(tmp_path, creds={"password": "WEBAPP_PASSWORD"})
    result = plan_mod.plan(project_root, mode="quick", goal="sign in")
    surf = result["surfaces"][0]
    roles = {u["role"] for u in surf["units"]}
    assert "lens" not in roles


def test_plan_destructive_optin_present_in_quick_mode_too(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_PASSWORD", "x")
    project_root = _write_project(tmp_path, creds={"password": "WEBAPP_PASSWORD"}, state="persistent")
    result = plan_mod.plan(project_root, mode="quick", goal="sign in")
    assert any(g["type"] == "destructive_optin" for g in result["gaps"])


def test_plan_no_persistent_surfaces_omits_destructive_gap(tmp_path, monkeypatch):
    monkeypatch.setenv("WEBAPP_PASSWORD", "x")
    project_root = _write_project(tmp_path, creds={"password": "WEBAPP_PASSWORD"})
    result = plan_mod.plan(project_root, mode="full")
    assert result["gaps"] == []


def test_plan_adds_zero_cost_confirm_unit_for_tauri_surface_with_open_p1(tmp_path):
    from flow_review import config as configmod
    from flow_review import ledger as ledger_mod
    from flow_review import plan as planmod

    (tmp_path / ".flow-review").mkdir()
    cfg = configmod.Config(
        schema_version=2, generator_version="test",
        surfaces=[configmod.Surface(id="desktop", name="desktop", kind="ui", driver="tauri",
                                     launch="", options={"binary": "app.exe",
                                                          "dev_url": "http://127.0.0.1:1421"})],
    )
    configmod.save(cfg, tmp_path / ".flow-review" / "config.json")
    entry = ledger_mod.LedgerEntry(
        id="f1", fingerprint="fp1", surface_id="desktop", flow_id="flow-1",
        rule="console.error", route="/", locator="css:#save-note-button", sev="P1",
        text="swallowed",
    )
    ledger_mod.save(ledger_mod.Ledger(findings={"f1": entry}),
                     tmp_path / ".flow-review" / "findings.json")

    result = planmod.plan(tmp_path, "goal", goal="save a note")
    desktop = next(s for s in result["surfaces"] if s["surface_id"] == "desktop")
    confirm_units = [u for u in desktop["units"] if u["role"] == "confirm"]
    assert confirm_units == [{"role": "confirm", "count": 1}]


def test_plan_omits_confirm_unit_when_no_open_p0_p1(tmp_path):
    from flow_review import config as configmod
    from flow_review import plan as planmod

    (tmp_path / ".flow-review").mkdir()
    cfg = configmod.Config(
        schema_version=2, generator_version="test",
        surfaces=[configmod.Surface(id="desktop", name="desktop", kind="ui", driver="tauri",
                                     launch="", options={"binary": "app.exe",
                                                          "dev_url": "http://127.0.0.1:1421"})],
    )
    configmod.save(cfg, tmp_path / ".flow-review" / "config.json")

    result = planmod.plan(tmp_path, "goal", goal="save a note")
    desktop = next(s for s in result["surfaces"] if s["surface_id"] == "desktop")
    assert [u for u in desktop["units"] if u["role"] == "confirm"] == []
