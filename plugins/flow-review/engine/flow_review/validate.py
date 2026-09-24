"""The verifier's refute/stand gate (v2 design §7).

Which of the three routes a fresh finding takes -- filed straight (engine/objective, or a P2
judgment), or replayed then verified (a P0/P1 judgment) -- is the orchestrator's decision, made
per `references/validation.md`; nothing in this module implements or re-derives that routing.

This module implements only what happens once a P0/P1 judgment finding has already been replayed
and handed to `fr-verifier`: `resolve_after_verifier` turns the verifier's "stands"/"refuted" call
into a `Verdict`, reached via `flow-review validate resolve`. A refute is accepted ONLY when it
attaches new measured or replayed evidence -- enforced mechanically by requiring an
`evidence = {"kind": "measurement"|"replay", "ref": "<path under run_dir>"}` object whose `ref`
must exist on disk, not merely a persuasive `reason` string. A refuted finding is never deleted:
`flow_review.triage.apply(ledger_path, finding_id, "refuted", reason=verifier_reason)` is how the
verdict actually lands in the ledger (C6) -- this module only validates and returns the verdict,
not I/O.

Findings are plain dicts shaped `{surface_id, flow_id, rule, route, locator, sev, text, evidence,
disposition}` -- the same shape `fr-lens` files and `ledger.fingerprint(flow_id, rule, route,
locator)` hashes on. `disposition` is one of "engine", "objective" or "judgment" (Canonical
Interfaces); this module has no code that routes on it.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path

VALID_SEVERITIES = ("P0", "P1", "P2")


class Verdict(str, Enum):
    STANDS = "stands"
    REFUTED = "refuted"


EVIDENCE_KINDS = ("measurement", "replay")


def resolve_after_verifier(
    finding: dict,
    verifier_verdict: str,
    reason: str | None,
    evidence: dict | None,
    run_dir,
) -> tuple[Verdict, str | None]:
    """The final verdict for a P0/P1 judgment finding, after the verifier has looked at it.

    `verifier_verdict` is exactly "stands" or "refuted". "A non-empty reason string" is not
    mechanically enforceable -- nothing stops a verifier typing "it just looks wrong" into
    `reason` and calling that a refutation. §7.3 says the verifier may refute ONLY with measured
    or replayed evidence, so refutation is gated on a real artifact, not on prose: a "refuted"
    verdict requires `evidence = {"kind": "measurement" | "replay", "ref": "<path relative to
    run_dir>"}`, and `run_dir / evidence["ref"]` must actually exist on disk. Any of the following
    raises `ValueError` instead of returning `REFUTED`: `evidence` is `None`; `evidence["kind"]`
    is not one of `EVIDENCE_KINDS`; the referenced file does not exist under `run_dir`.

    The orchestrator (SKILL.md, C2) is responsible for catching that `ValueError` and treating the
    finding as `stands` -- a verifier that cannot produce a real evidence ref has, by definition,
    not refuted anything, and a run must not crash because one subagent's refutation attempt was
    unfounded. This function only validates and raises; it never itself falls back to `stands` on
    a bad evidence object, so the fallback path is visible to (and owned by) the caller.
    """
    if verifier_verdict == "stands":
        return Verdict.STANDS, reason
    if verifier_verdict == "refuted":
        if not reason:
            raise ValueError("a refuted verdict must carry a non-empty reason")
        if evidence is None:
            raise ValueError("a refuted verdict must carry a measured or replayed evidence ref")
        if evidence.get("kind") not in EVIDENCE_KINDS:
            raise ValueError(
                f"evidence kind must be one of {EVIDENCE_KINDS}, got {evidence.get('kind')!r}"
            )
        ref = evidence.get("ref")
        root = Path(run_dir).resolve()
        target = (root / ref).resolve() if ref else None
        if target is None or not target.is_relative_to(root) or not target.is_file():
            raise ValueError(f"evidence ref {ref!r} does not exist under {run_dir}")
        return Verdict.REFUTED, reason
    raise ValueError(f"verifier_verdict must be 'stands' or 'refuted', got {verifier_verdict!r}")
