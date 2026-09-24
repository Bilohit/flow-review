from flow_review.web import actionlog


def test_locator_key_prefers_role_then_testid_then_css():
    assert actionlog.locator_key({"role": "button", "name": "Sign in"}) == "role:button:Sign in"
    assert actionlog.locator_key({"testid": "pw-input"}) == "testid:pw-input"
    assert actionlog.locator_key({"css": "#cta-button"}) == "css:#cta-button"
    assert actionlog.locator_key({"role": "button", "name": "Sign in", "testid": "x"}) \
        == "role:button:Sign in"


def test_record_step_redacts_secret_value():
    log = actionlog.new_log("webapp", "login-happy-path")
    actionlog.record_step(log, "goto", url="/")
    actionlog.record_step(
        log, "fill", locator={"testid": "pw-input", "secret": True},
        value="hunter2", url="/",
    )
    assert log["steps"][1]["value"] == "[redacted]"
    assert log["schema_version"] == 1


def test_save_respects_record_flag_and_project_root(tmp_path):
    log = actionlog.new_log("webapp", "login-happy-path")
    actionlog.record_step(log, "goto", url="/")

    project_root = tmp_path / "project"
    run_dir = tmp_path / "runs" / "run1"
    run_dir.mkdir(parents=True)

    p_ephemeral = actionlog.save(log, run_dir, project_root, record_enabled=False)
    assert p_ephemeral == run_dir / "repro" / "login-happy-path.json"
    assert p_ephemeral.exists()

    p_recorded = actionlog.save(log, run_dir, project_root, record_enabled=True)
    assert p_recorded == project_root / ".flow-review" / "recordings" / "webapp" / "login-happy-path.json"
    loaded = actionlog.load(p_recorded)
    assert loaded["schema_version"] == 1
    assert loaded["surface_id"] == "webapp"
