from __future__ import annotations

from pathlib import Path

import pytest

from flow_review import ledger as ledger_mod
from flow_review.triage import apply, alias_candidates


@pytest.fixture
def ledger_path(tmp_path: Path) -> Path:
    path = tmp_path / "findings.json"
    entry = ledger_mod.LedgerEntry(
        id="f1", fingerprint="abc123", surface_id="web", flow_id="w03",
        rule="identity", route="/settings", locator="role=row,name=Notifications",
        sev="P1", text="border-radius diverges from the token", evidence=["computed 8px"],
        state="open", runs_seen=1, first_run="2026-09-23T00:00:00.000Z",
        last_run="2026-09-23T00:00:00.000Z", aliases=[], reason="",
    )
    lgr = ledger_mod.Ledger(findings={"f1": entry})
    ledger_mod.save(lgr, path)
    return path


def test_apply_rejects_an_unknown_state(ledger_path):
    with pytest.raises(ValueError):
        apply(ledger_path, "f1", "not-a-real-state")


def test_apply_rejects_an_unknown_finding_id(ledger_path):
    with pytest.raises(KeyError):
        apply(ledger_path, "does-not-exist", "fixed")


def test_apply_writes_the_new_state_and_returns_the_entry(ledger_path):
    entry = apply(ledger_path, "f1", "fixed")
    assert entry.state == "fixed"
    reloaded = ledger_mod.load(ledger_path)
    saved = reloaded.findings["f1"]
    assert saved.state == "fixed"


def test_refuted_requires_a_non_empty_reason(ledger_path):
    with pytest.raises(ValueError):
        apply(ledger_path, "f1", "refuted", reason="")
    with pytest.raises(ValueError):
        apply(ledger_path, "f1", "refuted")


def test_refuted_with_a_reason_is_saved_with_it(ledger_path):
    entry = apply(ledger_path, "f1", "refuted",
                   reason="replayed: contrast 5.1:1, claim of 3.8:1 not reproduced")
    assert entry.state == "refuted"
    assert "5.1:1" in entry.reason


def test_other_states_do_not_require_a_reason(ledger_path):
    for state in ("false-positive", "wont-fix", "accepted", "fixed", "regressed", "open"):
        entry = apply(ledger_path, "f1", state)
        assert entry.state == state


def test_apply_never_calls_a_separate_suppression_store():
    """There is no add_suppression/upsert in this module -- suppressions derive from state via
    ledger.suppressions_for, exercised by fr-lens, not written here."""
    import flow_review.triage as triage_mod
    assert not hasattr(triage_mod, "upsert")
    assert not hasattr(triage_mod, "add_suppression")


def test_reopen_is_just_apply_open(ledger_path):
    apply(ledger_path, "f1", "false-positive", reason="documented exception")
    entry = apply(ledger_path, "f1", "open")
    assert entry.state == "open"


def test_alias_candidates_excludes_the_exact_match_entry_itself(ledger_path):
    """Extra requirement (earlier review): ledger.find_alias_candidates includes the
    exact-match entry itself among the candidates. flow_review.triage.alias_candidates wraps
    it and filters out the entry whose fingerprint equals the one being checked."""
    reloaded = ledger_mod.load(ledger_path)
    entry = reloaded.findings["f1"]
    fp = entry.fingerprint

    # The raw ledger helper still includes the self-match (documenting the known bug).
    raw = ledger_mod.find_alias_candidates(reloaded, entry.flow_id, entry.rule, entry.route)
    assert entry.id in [c.id for c in raw]

    # triage.alias_candidates filters it out.
    candidates = alias_candidates(reloaded, entry.flow_id, entry.rule, entry.route, fp)
    assert entry.id not in [c.id for c in candidates]
