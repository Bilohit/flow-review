"""The validation state machine (v2 design §7).

Every finding that reaches the ledger has already been through exactly one of three routes:

1. An engine check or an objective failure (crash, hang, data loss, wrong content, a failed
   round trip) is filed on one reproduction. No judgment, no vote, no replay.
2. A judgment finding at P2 is filed directly as an opinion.
3. A judgment finding at P0/P1 is replayed once (free, ephemeral -- `<run_dir>/repro/`, never
   reused, never fed to `flow-review replay`, A-3), then handed to `fr-verifier`, who may refute
   it ONLY by attaching new measured or replayed evidence -- enforced mechanically by requiring an
   `evidence = {"kind": "measurement"|"replay", "ref": "<path under run_dir>"}` object whose `ref`
   must exist on disk, not merely a persuasive `reason` string. A refuted finding is never
   deleted: `flow_review.triage.apply(ledger_path, finding_id, "refuted", reason=verifier_reason)`
   is how the verdict actually lands in the ledger (C6) -- this module only decides routing, not
   I/O.

Findings here are plain dicts shaped `{surface_id, flow_id, rule, route, locator, sev, text,
evidence, disposition}` -- the same shape `fr-lens` files and `ledger.fingerprint(flow_id, rule,
route, locator)` hashes on -- so nothing here needs its own parallel finding type.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path

VALID_SEVERITIES = ("P0", "P1", "P2")


class Disposition(str, Enum):
    ENGINE = "engine"
    OBJECTIVE = "objective"
    JUDGMENT = "judgment"


class Verdict(str, Enum):
    FILED = "filed"
    OPINION = "opinion"
    STANDS = "stands"
    REFUTED = "refuted"


def route(finding: dict) -> str:
    """Where a freshly-filed finding goes next, before any replay or verifier call has run.

    Returns "file" (engine/objective), "opinion" (P2 judgment), or "replay" (P0/P1 judgment).
    """
    sev = finding["sev"]
    if sev not in VALID_SEVERITIES:
        raise ValueError(f"sev must be one of {VALID_SEVERITIES}, got {sev!r}")
    disposition = finding["disposition"]
    if disposition in (Disposition.ENGINE, Disposition.OBJECTIVE):
        return "file"
    if sev == "P2":
        return "opinion"
    return "replay"


def resolve_after_replay(finding: dict, replay_result: dict | None) -> str:
    """Always "verify" for a P0/P1 judgment finding, regardless of what the replay found.

    The replay's outcome is evidence the verifier will weigh -- never itself a filing decision. A
    replay that could not run at all (`replay_result=None`) still goes to the verifier rather than
    being silently filed or dropped.
    """
    if route(finding) != "replay":
        raise ValueError("resolve_after_replay is only for P0/P1 judgment findings")
    return "verify"


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
