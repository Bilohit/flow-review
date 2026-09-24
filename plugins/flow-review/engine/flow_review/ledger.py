"""The findings ledger (A-6, audit C4). Stable ids, a semantic fingerprint (never prose), the
seven-state lifecycle, aliasing for a renamed selector, suppressions for the lens prompts, and
the cross-run discoverability tally A-8 needs. Replaces fr.findings' exact-prose fingerprint,
which could never accumulate runs_seen past 2 because nothing persisted between runs.

Sticky-state reappearance (A-15): a finding whose state is a human's triage call
(false-positive, wont-fix, accepted) or the verifier's `refuted` never flips back to `open` on
its own just because it was observed again -- only a manual reopen does that. `reconcile` is
where this rule lives.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from flow_review import events

STATES = ("open", "fixed", "regressed", "refuted", "false-positive", "wont-fix", "accepted")
_REAPPEARING_STAYS = {"open", "regressed", "accepted", "refuted", "false-positive", "wont-fix"}
_FIXABLE = {"open", "regressed"}


def fingerprint(flow_id: str, rule: str, route: str, locator: str) -> str:
    return hashlib.sha1("|".join((flow_id, rule, route, locator)).encode("utf-8")).hexdigest()


@dataclass
class LedgerEntry:
    id: str
    fingerprint: str
    surface_id: str
    flow_id: str
    rule: str
    route: str
    locator: str
    sev: str
    text: str
    evidence: list[str] = field(default_factory=list)
    disposition: str = "engine"
    state: str = "open"
    runs_seen: int = 1
    first_run: str = ""
    last_run: str = ""
    aliases: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class Ledger:
    findings: dict[str, LedgerEntry] = field(default_factory=dict)
    discoverability_misses: dict[str, list[str]] = field(default_factory=dict)


def load(path: Path) -> Ledger:
    path = Path(path)
    if not path.exists():
        return Ledger()
    raw = json.loads(path.read_text(encoding="utf-8"))
    findings = {k: LedgerEntry(**v) for k, v in raw.get("findings", {}).items()}
    return Ledger(findings=findings, discoverability_misses=raw.get("discoverability_misses", {}))


def save(ledger_: Ledger, path: Path) -> None:
    raw = {
        "schema_version": 1,
        "findings": {k: asdict(v) for k, v in ledger_.findings.items()},
        "discoverability_misses": ledger_.discoverability_misses,
    }
    raw = events.redact(raw)  # secrets never reach the ledger
    Path(path).write_text(json.dumps(raw, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def reconcile(
    ledger_: Ledger, findings: list[dict], flows_run: set[str], run_id: str,
    alias_decisions: dict[str, str] | None = None,
) -> Ledger:
    alias_decisions = alias_decisions or {}
    current_fps: dict[str, dict] = {}
    for f in findings:
        fp = fingerprint(f["flow_id"], f["rule"], f["route"], f["locator"])
        prev = current_fps.get(fp)
        if prev is None:
            current_fps[fp] = dict(f, evidence=list(f.get("evidence", [])))
            continue
        # Same-run duplicate: keep the most severe sev (P0 < P1 < P2) + its text; union evidence.
        evidence = prev["evidence"] + [e for e in f.get("evidence", []) if e not in prev["evidence"]]
        if f["sev"] < prev["sev"]:
            prev = dict(f)
        current_fps[fp] = dict(prev, evidence=evidence)

    # Rule 1-3: transition every EXISTING entry against this run's observations.
    for entry in ledger_.findings.values():
        if entry.flow_id not in flows_run:
            continue  # rule 1: flow did not run -> untouched
        if entry.fingerprint in current_fps:
            f = current_fps[entry.fingerprint]
            entry.runs_seen += 1
            entry.last_run = run_id
            entry.evidence = f.get("evidence", entry.evidence)
            if entry.state == "fixed":
                entry.state = "regressed"
            # else: open/regressed/accepted/refuted/false-positive/wont-fix all stay as-is,
            # per A-15 -- a human's triage call is never silently overridden by a reappearance.
            del current_fps[entry.fingerprint]  # consumed: not a "new" finding below
        else:
            if entry.state in _FIXABLE:
                entry.state = "fixed"
                entry.last_run = run_id

    # Rule 4: whatever fingerprint is left in current_fps had no existing entry this run.
    for fp, f in current_fps.items():
        canonical_id = alias_decisions.get(fp)
        if canonical_id and canonical_id in ledger_.findings:
            record_alias(ledger_, canonical_id, fp)
            entry = ledger_.findings[canonical_id]
            entry.runs_seen += 1
            entry.last_run = run_id
            entry.evidence = f.get("evidence", entry.evidence)
            continue
        new_id = f.get("id") or uuid.uuid4().hex  # keep the finding event's id
        ledger_.findings[new_id] = LedgerEntry(
            id=new_id, fingerprint=fp, surface_id=f["surface_id"], flow_id=f["flow_id"],
            rule=f["rule"], route=f["route"], locator=f["locator"], sev=f["sev"], text=f["text"],
            evidence=f.get("evidence", []), disposition=f.get("disposition", "engine"),
            state="open", runs_seen=1,
            first_run=run_id, last_run=run_id,
        )

    return ledger_


def find_alias_candidates(ledger_: Ledger, flow_id: str, rule: str, route: str) -> list[LedgerEntry]:
    return [
        e for e in ledger_.findings.values()
        if e.flow_id == flow_id and e.rule == rule and e.route == route
        and e.state in ("open", "regressed")
    ]


def record_alias(ledger_: Ledger, canonical_id: str, alias_fingerprint: str) -> None:
    entry = ledger_.findings[canonical_id]
    if alias_fingerprint not in entry.aliases:
        entry.aliases.append(alias_fingerprint)


def suppressions_for(ledger_: Ledger, rule: str) -> list[dict]:
    matches = [
        e for e in ledger_.findings.values()
        if e.rule == rule and e.state in ("false-positive", "wont-fix")
    ]
    matches.sort(key=lambda e: e.last_run)
    return [{"route": e.route, "locator": e.locator, "text": e.text, "state": e.state} for e in matches]


def record_miss(ledger_: Ledger, function: str, run_id: str) -> int:
    runs = ledger_.discoverability_misses.setdefault(function, [])
    if run_id not in runs:
        runs.append(run_id)
    return len(runs)


def missed_twice(ledger_: Ledger, function: str) -> bool:
    return len(ledger_.discoverability_misses.get(function, [])) >= 2
