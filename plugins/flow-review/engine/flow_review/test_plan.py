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
