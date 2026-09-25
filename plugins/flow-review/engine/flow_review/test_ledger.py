from __future__ import annotations

from flow_review import ledger


def _finding(surface_id="web-app", flow_id="checkout", rule="contrast", route="/cart",
             locator="button[name=Pay]", sev="P1", text="low contrast", evidence=None):
    return dict(
        surface_id=surface_id, flow_id=flow_id, rule=rule, route=route, locator=locator,
        sev=sev, text=text, evidence=evidence if evidence is not None else ["shots/01.png"],
    )


def test_a_new_entry_keeps_the_finding_disposition():
    led = ledger.reconcile(ledger.Ledger(), [dict(_finding(), disposition="judgment")],
                           {"checkout"}, "run-1")
    assert next(iter(led.findings.values())).disposition == "judgment"


def test_fingerprint_is_stable_for_the_same_four_inputs():
    a = ledger.fingerprint("checkout", "contrast", "/cart", "button[name=Pay]")
    b = ledger.fingerprint("checkout", "contrast", "/cart", "button[name=Pay]")
    assert a == b


def test_fingerprint_changes_when_locator_changes():
    a = ledger.fingerprint("checkout", "contrast", "/cart", "button[name=Pay]")
    b = ledger.fingerprint("checkout", "contrast", "/cart", "button[name=Cancel]")
    assert a != b


def test_round_trip_preserves_entries(tmp_path):
    led = ledger.Ledger()
    led = ledger.reconcile(led, [_finding()], flows_run={"checkout"}, run_id="run-1")
    path = tmp_path / "findings.json"
    ledger.save(led, path)
    back = ledger.load(path)
    assert back == led


def test_missing_ledger_file_loads_as_empty(tmp_path):
    led = ledger.load(tmp_path / "does-not-exist.json")
    assert led == ledger.Ledger()


def test_a_new_finding_opens_with_runs_seen_one_and_carries_surface_id_and_evidence(tmp_path):
    led = ledger.reconcile(ledger.Ledger(), [_finding()], {"checkout"}, "run-1")
    (entry,) = led.findings.values()
    assert entry.state == "open"
    assert entry.runs_seen == 1
    assert entry.first_run == entry.last_run == "run-1"
    assert entry.surface_id == "web-app"
    assert entry.evidence == ["shots/01.png"]


def test_seen_again_increments_runs_seen_and_stays_open(tmp_path):
    led = ledger.Ledger()
    led = ledger.reconcile(led, [_finding()], {"checkout"}, "run-1")
    led = ledger.reconcile(led, [_finding()], {"checkout"}, "run-2")
    (entry,) = led.findings.values()
    assert entry.state == "open"
    assert entry.runs_seen == 2
    assert entry.last_run == "run-2"
    assert entry.first_run == "run-1"


def test_not_seen_on_a_flow_that_ran_becomes_fixed(tmp_path):
    led = ledger.reconcile(ledger.Ledger(), [_finding()], {"checkout"}, "run-1")
    led = ledger.reconcile(led, [], {"checkout"}, "run-2")
    (entry,) = led.findings.values()
    assert entry.state == "fixed"


def test_flow_that_did_not_run_is_untouched(tmp_path):
    led = ledger.reconcile(ledger.Ledger(), [_finding()], {"checkout"}, "run-1")
    led = ledger.reconcile(led, [], flows_run=set(), run_id="run-2")
    (entry,) = led.findings.values()
    assert entry.state == "open"
    assert entry.runs_seen == 1
    assert entry.last_run == "run-1"


def test_reappearing_after_fixed_is_regressed(tmp_path):
    led = ledger.reconcile(ledger.Ledger(), [_finding()], {"checkout"}, "run-1")
    led = ledger.reconcile(led, [], {"checkout"}, "run-2")  # -> fixed
    led = ledger.reconcile(led, [_finding()], {"checkout"}, "run-3")  # -> regressed
    (entry,) = led.findings.values()
    assert entry.state == "regressed"
    assert entry.runs_seen == 2


def test_a_refuted_finding_reappearing_stays_refuted_not_resurfaced(tmp_path):
    # A-15: triaged states (false-positive, wont-fix, accepted) and refuted are sticky; the
    # finding stays visible with its reason, runs_seen keeps counting, and only a manual
    # reopen (drawer or `flow-review triage ID open`) changes the state.
    led = ledger.reconcile(ledger.Ledger(), [_finding()], {"checkout"}, "run-1")
    (entry,) = led.findings.values()
    entry.state = "refuted"
    entry.reason = "measured contrast was 4.6:1, above the token requirement"
    led = ledger.reconcile(led, [_finding()], {"checkout"}, "run-2")
    (entry,) = led.findings.values()
    assert entry.state == "refuted"
    assert entry.reason == "measured contrast was 4.6:1, above the token requirement"
    assert entry.runs_seen == 2  # still tracked, per A-15


def test_evidence_refreshes_to_the_latest_run_when_a_finding_reappears(tmp_path):
    led = ledger.reconcile(ledger.Ledger(), [_finding(evidence=["shots/run1.png"])], {"checkout"}, "run-1")
    led = ledger.reconcile(led, [_finding(evidence=["shots/run2.png"])], {"checkout"}, "run-2")
    (entry,) = led.findings.values()
    assert entry.evidence == ["shots/run2.png"]


def test_find_alias_candidates_matches_same_flow_rule_route_different_locator():
    led = ledger.reconcile(ledger.Ledger(), [_finding(locator="button[name=Pay]")], {"checkout"}, "run-1")
    candidates = ledger.find_alias_candidates(led, "checkout", "contrast", "/cart")
    assert len(candidates) == 1
    assert candidates[0].locator == "button[name=Pay]"


def test_alias_decision_folds_a_new_fingerprint_into_the_canonical_entry(tmp_path):
    led = ledger.reconcile(ledger.Ledger(), [_finding(locator="button[name=Pay]")], {"checkout"}, "run-1")
    (canonical,) = led.findings.values()
    renamed = _finding(locator="button[name=\"Pay now\"]")
    new_fp = ledger.fingerprint(renamed["flow_id"], renamed["rule"], renamed["route"], renamed["locator"])
    led = ledger.reconcile(
        led, [renamed], {"checkout"}, "run-2",
        alias_decisions={new_fp: canonical.id},
    )
    assert len(led.findings) == 1
    entry = led.findings[canonical.id]
    assert new_fp in entry.aliases
    assert entry.runs_seen == 2


def test_record_alias_is_idempotent_and_raises_for_unknown_canonical():
    led = ledger.reconcile(ledger.Ledger(), [_finding()], {"checkout"}, "run-1")
    (entry,) = led.findings.values()
    ledger.record_alias(led, entry.id, "some-fp")
    ledger.record_alias(led, entry.id, "some-fp")
    assert led.findings[entry.id].aliases == ["some-fp"]
    import pytest
    with pytest.raises(KeyError):
        ledger.record_alias(led, "no-such-id", "fp")


def test_suppressions_for_returns_only_false_positive_and_wont_fix_entries_of_that_rule():
    led = ledger.reconcile(ledger.Ledger(), [
        _finding(rule="contrast", locator="a"),
        _finding(rule="contrast", locator="b"),
        _finding(rule="copy", locator="c"),
    ], {"checkout"}, "run-1")
    ids = list(led.findings)
    led.findings[ids[0]].state = "false-positive"
    led.findings[ids[1]].state = "wont-fix"
    suppressed = ledger.suppressions_for(led, "contrast")
    assert len(suppressed) == 2
    assert all(s["locator"] in ("a", "b") for s in suppressed)


def test_record_miss_counts_distinct_runs_not_calls():
    led = ledger.Ledger()
    ledger.record_miss(led, "export-csv", "run-1")
    ledger.record_miss(led, "export-csv", "run-1")  # same run, no double count
    assert ledger.missed_twice(led, "export-csv") is False
    ledger.record_miss(led, "export-csv", "run-2")
    assert ledger.missed_twice(led, "export-csv") is True


def test_same_run_duplicate_fingerprints_merge_keeping_most_severe_and_all_evidence():
    led = ledger.reconcile(ledger.Ledger(), [
        _finding(sev="P2", text="minor", evidence=["a"]),
        _finding(sev="P1", text="major", evidence=["b"]),
    ], {"checkout"}, "run-1")
    (entry,) = led.findings.values()
    assert entry.sev == "P1"
    assert entry.text == "major"
    assert entry.evidence == ["a", "b"]


def test_save_redacts_registered_secrets(tmp_path):
    from flow_review import events
    events.register_secret("hunter2secret")
    try:
        f = _finding(route="/cart?token=hunter2secret")
        led = ledger.reconcile(ledger.Ledger(), [f], flows_run={"checkout"}, run_id="run-1")
        path = tmp_path / "findings.json"
        ledger.save(led, path)
        assert "hunter2secret" not in path.read_text(encoding="utf-8")
    finally:
        events.clear_secrets()


def test_route_template_replaces_numeric_and_uuid_segments():
    from flow_review.ledger import route_template
    assert route_template("/orders/41") == "/orders/:id"
    assert route_template("/users/3fa85f64-5717-4562-b3fc-2c963f66afa6/edit") == "/users/:id/edit"
    assert route_template("/") == "/"
    assert route_template("/settings") == "/settings"


def test_fingerprint_uses_route_template_for_numeric_ids():
    from flow_review.ledger import fingerprint, route_template
    fp_a = fingerprint("flow-1", "contrast.aa", route_template("/orders/41"), "#save")
    fp_b = fingerprint("flow-1", "contrast.aa", route_template("/orders/42"), "#save")
    assert fp_a == fp_b
    fp_static = fingerprint("flow-1", "contrast.aa", route_template("/settings"), "#save")
    assert fp_static == fingerprint("flow-1", "contrast.aa", "/settings", "#save")


def test_severity_order_is_an_explicit_tuple_not_string_comparison():
    # A-44 row 6 (A5): locks in that severity ranking goes through SEVERITY_ORDER's index,
    # not a bare string comparison of "P0"/"P1"/"P2" (which happens to sort right today but
    # is not the intended rule).
    assert ledger.SEVERITY_ORDER == ("P0", "P1", "P2")
    assert ledger.SEVERITY_ORDER.index("P0") < ledger.SEVERITY_ORDER.index("P2")


def test_same_run_duplicate_keeps_p0_over_p2_via_explicit_severity_order():
    led = ledger.reconcile(ledger.Ledger(), [
        _finding(sev="P2", text="minor", evidence=["a"]),
        _finding(sev="P0", text="critical", evidence=["b"]),
    ], {"checkout"}, "run-1")
    (entry,) = led.findings.values()
    assert entry.sev == "P0"
    assert entry.text == "critical"


def test_reconcile_upgrades_legacy_raw_route_fingerprint_to_templated_one(tmp_path):
    # Legacy entry: fingerprinted from the raw route (e.g. "/orders/41") before route_template
    # existed. After the upgrade, current findings fingerprint from the templated route
    # ("/orders/:id"), so a stale ledger entry must be migrated on load or it silently gets
    # marked "fixed" while the same defect is re-inserted as a duplicate.
    raw_fp = ledger.fingerprint("checkout", "contrast", "/orders/41", "button[name=Pay]")
    entry = ledger.LedgerEntry(
        id="legacy-1", fingerprint=raw_fp, surface_id="web-app", flow_id="checkout",
        rule="contrast", route="/orders/41", locator="button[name=Pay]", sev="P1",
        text="low contrast", state="open", runs_seen=1, first_run="run-1", last_run="run-1",
    )
    led = ledger.Ledger(findings={"legacy-1": entry})
    path = tmp_path / "findings.json"
    ledger.save(led, path)
    led = ledger.load(path)

    finding = _finding(route=ledger.route_template("/orders/41"))
    led = ledger.reconcile(led, [finding], {"checkout"}, "run-2")

    assert list(led.findings) == ["legacy-1"]
    assert led.findings["legacy-1"].runs_seen == 2
    assert led.findings["legacy-1"].state != "fixed"


def test_a_new_entry_keeps_the_finding_event_id():
    led = ledger.reconcile(ledger.Ledger(), [dict(_finding(), id="evt-123")], {"checkout"}, "run-1")
    assert list(led.findings) == ["evt-123"]
    assert led.findings["evt-123"].id == "evt-123"
    led = ledger.reconcile(led, [dict(_finding(), id="evt-999")], {"checkout"}, "run-2")
    assert list(led.findings) == ["evt-123"]  # existing entry keeps its id
