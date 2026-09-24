from flow_review import budget


def test_record_usage_and_used(tmp_path):
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    budget.record_usage(run_dir, "webapp", "lens", 2000)
    budget.record_usage(run_dir, "webapp", "verifier", 3500)
    assert budget.used(run_dir) == 5500


def test_check_exits_nonzero_when_cap_would_be_exceeded(tmp_path):
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    budget.record_usage(run_dir, "webapp", "lens", 9000)
    assert budget.check(tmp_path, run_dir, next_role="verifier", cap_tokens=10000) == 1
    assert budget.check(tmp_path, run_dir, next_role="verifier", cap_tokens=None) == 0
    exact_fit = 9000 + budget.PRIORS_TOKENS_PER_UNIT["verifier"]
    assert budget.check(tmp_path, run_dir, next_role="verifier", cap_tokens=exact_fit) == 0


def test_estimate_uses_priors_with_no_history(tmp_path):
    plan_units = [
        {"surface_id": "webapp", "role": "explorer", "count": 4},
        {"surface_id": "webapp", "role": "lens", "count": 4},
    ]
    est = budget.estimate(plan_units, tmp_path)
    expected = 4 * budget.PRIORS_TOKENS_PER_UNIT["explorer"] + 4 * budget.PRIORS_TOKENS_PER_UNIT["lens"]
    assert est["webapp"] == expected


def test_fold_history_writes_usage_history_json(tmp_path):
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    budget.record_usage(run_dir, "webapp", "lens", 2000)
    budget.record_usage(run_dir, "webapp", "lens", 2200)
    history_path = budget.fold_history(tmp_path, run_dir)
    assert history_path == tmp_path / ".flow-review" / "usage_history.json"
    import json
    history = json.loads(history_path.read_text())
    assert history["webapp"]["runs"][0]["roles"]["lens"]["tokens"] == [2000, 2200]
    assert history["webapp"]["runs"][0]["roles"]["lens"]["count"] == 2


def test_estimate_uses_history_median_after_three_runs(tmp_path):
    for i in range(3):
        run_dir = tmp_path / f"run{i}"
        run_dir.mkdir()
        budget.record_usage(run_dir, "webapp", "lens", 2000 + i * 100)
        budget.fold_history(tmp_path, run_dir)
    plan_units = [{"surface_id": "webapp", "role": "lens", "count": 2}]
    est = budget.estimate(plan_units, tmp_path)
    assert est["webapp"] == 2 * 2100


def test_used_accepts_string_tokens_from_the_event_cli(tmp_path):
    (tmp_path / budget.EVENTS_FILENAME).write_text(
        '{"type": "usage", "tokens": "1200"}\n{"type": "usage", "tokens": 300}\n', encoding="utf-8")
    assert budget.used(tmp_path) == 1500
