from flow_review.web import actionlog


def test_save_slugs_a_path_traversal_flow_id_so_it_lands_inside_the_run_dir(tmp_path):
    log = actionlog.new_log("webapp", "../../x")
    actionlog.record_step(log, "goto", url="/")

    project_root = tmp_path / "project"
    run_dir = tmp_path / "runs" / "run1"
    run_dir.mkdir(parents=True)

    out = actionlog.save(log, run_dir, project_root, record_enabled=False)

    repro_root = (run_dir / "repro").resolve()
    assert repro_root in out.resolve().parents
    assert out.exists()
    loaded = actionlog.load(out)
    assert loaded["flow_id"] == "../../x"  # the content is untouched -- only the filename is slugged


def test_save_slugs_a_path_traversal_surface_id_so_it_lands_inside_recordings(tmp_path):
    log = actionlog.new_log("../../evil", "login")
    actionlog.record_step(log, "goto", url="/")

    project_root = tmp_path / "project"
    run_dir = tmp_path / "runs" / "run1"
    run_dir.mkdir(parents=True)

    out = actionlog.save(log, run_dir, project_root, record_enabled=True)

    recordings_root = (project_root / ".flow-review" / "recordings").resolve()
    assert recordings_root in out.resolve().parents
    assert out.exists()


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
    assert p_ephemeral == run_dir / "repro" / "webapp" / "login-happy-path.json"
    assert p_ephemeral.exists()

    p_recorded = actionlog.save(log, run_dir, project_root, record_enabled=True)
    assert p_recorded == project_root / ".flow-review" / "recordings" / "webapp" / "login-happy-path.json"
    loaded = actionlog.load(p_recorded)
    assert loaded["schema_version"] == 1
    assert loaded["surface_id"] == "webapp"


def test_save_ephemeral_repro_is_keyed_by_surface_so_same_flow_ids_do_not_collide(tmp_path):
    # a web and a tauri surface can run the same flow id in one run
    run_dir = tmp_path / "runs" / "run1"
    run_dir.mkdir(parents=True)
    paths = set()
    for surface_id in ("webapp", "desktop"):
        log = actionlog.new_log(surface_id, "checkout")
        actionlog.record_step(log, "goto", url="/")
        paths.add(actionlog.save(log, run_dir, tmp_path / "project", record_enabled=False))
    assert paths == {run_dir / "repro" / "webapp" / "checkout.json",
                     run_dir / "repro" / "desktop" / "checkout.json"}


def test_slug_leaves_safe_ids_unchanged_and_disambiguates_rewritten_ones():
    assert actionlog._slug("login-happy_path.1") == "login-happy_path.1"
    a, b = actionlog._slug("a/b"), actionlog._slug("a b")
    assert a != b  # both would collapse to "a-b" without the hash suffix
    assert a.startswith("a-b-") and len(a) == len("a-b-") + 6
    assert "/" not in actionlog._slug("../../x") and not actionlog._slug("../../x").startswith(".")
