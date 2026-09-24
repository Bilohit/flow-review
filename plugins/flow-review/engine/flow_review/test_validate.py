from __future__ import annotations

import pytest

from flow_review.validate import (
    Disposition,
    Verdict,
    resolve_after_replay,
    resolve_after_verifier,
    route,
)


def _finding(disposition: Disposition, sev: str = "P1") -> dict:
    return {
        "disposition": disposition, "sev": sev,
        "surface_id": "web", "flow_id": "w03", "rule": "identity",
        "route": "/settings", "locator": "role=row,name=Notifications",
        "text": "example claim", "evidence": ["example evidence"],
    }


def test_engine_check_routes_straight_to_filed():
    assert route(_finding(Disposition.ENGINE, "P1")) == "file"


def test_objective_failure_routes_straight_to_filed():
    assert route(_finding(Disposition.OBJECTIVE, "P0")) == "file"


def test_judgment_p2_routes_to_opinion_never_replay():
    assert route(_finding(Disposition.JUDGMENT, "P2")) == "opinion"


@pytest.mark.parametrize("sev", ["P0", "P1"])
def test_judgment_p0_p1_routes_to_replay(sev):
    assert route(_finding(Disposition.JUDGMENT, sev)) == "replay"


def test_unreplayable_p0_p1_still_reaches_the_verifier():
    finding = _finding(Disposition.JUDGMENT, "P0")
    assert resolve_after_replay(finding, replay_result=None) == "verify"


def test_replay_confirming_the_claim_still_goes_to_the_verifier():
    finding = _finding(Disposition.JUDGMENT, "P1")
    assert resolve_after_replay(finding, replay_result={"confirmed": True}) == "verify"


def test_resolve_after_replay_rejects_a_non_replay_route():
    finding = _finding(Disposition.JUDGMENT, "P2")
    with pytest.raises(ValueError):
        resolve_after_replay(finding, replay_result=None)


def test_verifier_stands_returns_the_stands_verdict_with_no_reason_or_evidence_required(tmp_path):
    finding = _finding(Disposition.JUDGMENT, "P0")
    verdict, reason = resolve_after_verifier(
        finding, verifier_verdict="stands", reason=None, evidence=None, run_dir=tmp_path,
    )
    assert verdict == Verdict.STANDS
    assert reason is None


def test_verifier_refuted_requires_a_reason(tmp_path):
    finding = _finding(Disposition.JUDGMENT, "P0")
    evidence = {"kind": "measurement", "ref": "repro/contrast.json"}
    (tmp_path / "repro").mkdir()
    (tmp_path / "repro" / "contrast.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        resolve_after_verifier(
            finding, verifier_verdict="refuted", reason="", evidence=evidence, run_dir=tmp_path,
        )


def test_verifier_refuted_requires_evidence_at_all():
    """A "refuted" verdict with evidence=None is exactly the "taste" refutation the brief
    forbids -- it must raise, never silently pass through as a bare reason string."""
    finding = _finding(Disposition.JUDGMENT, "P0")
    with pytest.raises(ValueError):
        resolve_after_verifier(
            finding, verifier_verdict="refuted", reason="looked wrong to me",
            evidence=None, run_dir=None,
        )


def test_verifier_refuted_rejects_an_evidence_kind_outside_the_two_known_values(tmp_path):
    finding = _finding(Disposition.JUDGMENT, "P0")
    (tmp_path / "shot.png").write_bytes(b"")
    evidence = {"kind": "impression", "ref": "shot.png"}
    with pytest.raises(ValueError):
        resolve_after_verifier(
            finding, verifier_verdict="refuted", reason="it looks off",
            evidence=evidence, run_dir=tmp_path,
        )


def test_verifier_refuted_rejects_a_missing_evidence_file(tmp_path):
    finding = _finding(Disposition.JUDGMENT, "P0")
    evidence = {"kind": "replay", "ref": "repro/does-not-exist.json"}
    with pytest.raises(ValueError):
        resolve_after_verifier(
            finding, verifier_verdict="refuted",
            reason="replayed and it completed cleanly",
            evidence=evidence, run_dir=tmp_path,
        )


def test_verifier_refuted_with_a_real_evidence_file_returns_refuted(tmp_path):
    finding = _finding(Disposition.JUDGMENT, "P0")
    (tmp_path / "repro").mkdir()
    (tmp_path / "repro" / "contrast.json").write_text('{"ratio": 5.1}', encoding="utf-8")
    evidence = {"kind": "measurement", "ref": "repro/contrast.json"}
    verdict, reason = resolve_after_verifier(
        finding, verifier_verdict="refuted",
        reason="replayed measurement: contrast ratio 5.1:1, claim of 3.8:1 not reproduced",
        evidence=evidence, run_dir=tmp_path,
    )
    assert verdict == Verdict.REFUTED
    assert reason
    # the orchestrator is responsible for writing `reason` into LedgerEntry.reason and
    # appending `evidence["ref"]` into LedgerEntry.evidence -- this module only validates and
    # returns them; it does not touch the ledger itself (see C6, `triage.apply`).


def test_verifier_verdict_outside_the_two_known_values_is_rejected(tmp_path):
    finding = _finding(Disposition.JUDGMENT, "P0")
    with pytest.raises(ValueError):
        resolve_after_verifier(
            finding, verifier_verdict="probably fine", reason="taste",
            evidence=None, run_dir=tmp_path,
        )


def test_orchestrator_catches_a_bad_refutation_and_the_finding_stands(tmp_path):
    """This is the documented fallback (validation.md): if the verifier cannot supply a real
    evidence ref, resolve_after_verifier raises ValueError, and the ORCHESTRATOR is responsible
    for catching it and treating the finding as `stands` rather than propagating the exception
    into a crashed run. This test only proves the raise happens; the catch-and-stand behavior
    lives in the orchestrator (SKILL.md, C2), not in this module."""
    finding = _finding(Disposition.JUDGMENT, "P0")
    try:
        resolve_after_verifier(
            finding, verifier_verdict="refuted", reason="it just looks wrong",
            evidence=None, run_dir=tmp_path,
        )
        raised = False
    except ValueError:
        raised = True
    assert raised


@pytest.mark.parametrize("escape", ["../outside.json", "ABS"])
def test_verifier_refuted_rejects_an_evidence_ref_outside_run_dir(tmp_path, escape):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    ref = str(outside) if escape == "ABS" else escape
    with pytest.raises(ValueError):
        resolve_after_verifier(
            _finding(Disposition.JUDGMENT, "P0"), verifier_verdict="refuted",
            reason="measured", evidence={"kind": "measurement", "ref": ref}, run_dir=run_dir,
        )
