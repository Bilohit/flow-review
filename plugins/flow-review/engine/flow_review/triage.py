"""Triage transitions and fix briefs (v2 design §8; Canonical Interfaces "Triage").

`apply()` is the one function both `flow-review triage ID STATE [--reason]` and the dashboard's
`POST /triage` call -- there is exactly one triage code path, never two that could drift apart.
There is no `upsert` and no `add_suppression` here: a false-positive (or wont-fix) transition is
just a state write, and `ledger.suppressions_for(ledger, rule)` derives the suppression list from
state at read time (`fr-lens`'s consumer, not this module's producer).

`build_fix_brief()` is report content only: repro steps, evidence references, and a suspected
`file:line` via source maps where available, else the literal string "unknown". It never
constructs anything resembling a patch or a diff -- flow-review never edits product code.

`alias_candidates()` wraps `ledger.find_alias_candidates` and filters out the entry whose
fingerprint equals the one being checked -- the raw ledger helper includes that exact-match
entry itself, which is never a useful dedup candidate for its own fingerprint.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from flow_review import ledger as ledger_mod

_REASON_REQUIRED = {"refuted"}


def apply(ledger_path: Path, finding_id: str, state: str, reason: str | None = None):
    if state not in ledger_mod.STATES:
        raise ValueError(f"unknown triage state {state!r}, must be one of {sorted(ledger_mod.STATES)}")

    lgr = ledger_mod.load(ledger_path)
    entry = lgr.findings.get(finding_id)
    if entry is None:
        raise KeyError(f"no finding {finding_id!r} in {ledger_path}")

    if state in _REASON_REQUIRED and not reason:
        raise ValueError(f"transitioning to {state!r} requires a non-empty reason")

    entry.state = state
    entry.reason = reason or ""

    ledger_mod.save(lgr, ledger_path)
    return entry


@dataclass
class FixBrief:
    repro_steps: list[str]
    evidence: list[str]
    suspected_location: str


def build_fix_brief(entry, repro_steps: list[str], source_map: dict | None) -> FixBrief:
    location = "unknown"
    if source_map is not None:
        key = f"{entry.route}|{entry.locator}"
        location = source_map.get(key, "unknown")
    return FixBrief(
        repro_steps=repro_steps,
        evidence=entry.evidence,
        suspected_location=location,
    )


def alias_candidates(ledger_, flow_id: str, rule: str, route: str, exclude_fingerprint: str):
    return [
        e for e in ledger_mod.find_alias_candidates(ledger_, flow_id, rule, route)
        if e.fingerprint != exclude_fingerprint
    ]
