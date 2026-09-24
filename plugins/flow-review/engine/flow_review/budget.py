"""Budget: per-role token priors, usage log, history medians, cap gate (A-7).

`used()` re-derives from `events.append`'s own `events.jsonl` rather than keeping a separate
running total, so the usage log has exactly one writer (events.append) and one source of truth,
matching the Canonical Budget bullet. `fold_history` is the only writer of usage_history.json;
the ledger holds no usage (A-23).
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import TypedDict

from flow_review import events

EVENTS_FILENAME = "events.jsonl"

# One unit = ONE subagent dispatch (the usage Claude Code reports per Agent result, cache
# reads included). Priors seeded from the 2026-09-23 planning session: a single-turn, no-tool
# Sonnet subagent reported ~47k tokens; tool-heavy drafters 90-300k. Priors only -- replaced
# by per-surface medians after 3 runs (A-7); recalibrated by the M5 benchmark.
PRIORS_TOKENS_PER_UNIT = {
    "explorer": 150_000,      # per goal explored (multi-step drive session)
    "replay-repair": 60_000,  # per divergence repaired
    "lens": 50_000,           # per screen, one call (evidence bundle first)
    "cold-eyes": 120_000,     # per cold-eyes pass over one surface
    "triage": 50_000,         # per triage batch
    "verifier": 60_000,       # per P0/P1 judgment finding
}


class PlanUnit(TypedDict):
    surface_id: str
    role: str
    count: int


def record_usage(run_dir: Path, surface_id: str, role: str, tokens: int) -> dict:
    return events.append(Path(run_dir), {
        "type": "usage",
        "surface": surface_id,
        "role": role,
        "tokens": tokens,
    })


def used(run_dir: Path) -> int:
    log_path = Path(run_dir) / EVENTS_FILENAME
    if not log_path.exists():
        return 0
    total = 0
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("type") == "usage":
            total += int(record.get("tokens", 0))  # event CLI k=v gives strings
    return total


def fold_history(project_root: Path, run_dir: Path) -> Path:
    history_path = Path(project_root) / ".flow-review" / "usage_history.json"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history: dict = {}
    if history_path.exists():
        history = json.loads(history_path.read_text(encoding="utf-8"))

    per_surface_roles: dict[str, dict[str, list[int]]] = {}
    log_path = Path(run_dir) / EVENTS_FILENAME
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("type") != "usage":
                continue
            surface_id = record["surface"]
            role = record["role"]
            tokens = record["tokens"]
            per_surface_roles.setdefault(surface_id, {}).setdefault(role, []).append(tokens)

    for surface_id, roles in per_surface_roles.items():
        surface_history = history.setdefault(surface_id, {"runs": []})
        surface_history["runs"].append({
            "run_id": Path(run_dir).name,
            "roles": {
                role: {"count": len(tok_list), "tokens": tok_list}
                for role, tok_list in roles.items()
            },
        })

    history_path.write_text(json.dumps(history, indent=2), encoding="utf-8")
    return history_path


def _prior(role: str) -> int:
    return PRIORS_TOKENS_PER_UNIT.get(role, 0)


def _load_history(project_root: Path) -> dict:
    history_path = Path(project_root) / ".flow-review" / "usage_history.json"
    if not history_path.exists():
        return {}
    return json.loads(history_path.read_text(encoding="utf-8"))


def _per_unit_estimate(surface_id: str, role: str, project_root: Path) -> int:
    history = _load_history(project_root)
    runs = history.get(surface_id, {}).get("runs", [])
    if len(runs) < 3:
        return _prior(role)
    all_tokens: list[int] = []
    for run in runs:
        role_data = run.get("roles", {}).get(role)
        if role_data:
            all_tokens.extend(role_data["tokens"])
    if not all_tokens:
        return _prior(role)
    return int(statistics.median(all_tokens))


def role_unit_counts(surface_id: str, role: str, project_root: Path) -> list[int]:
    """Per-run unit counts for a role; used by plan.py's A-19 median refinement."""
    history = _load_history(project_root)
    runs = history.get(surface_id, {}).get("runs", [])
    counts = []
    for run in runs:
        role_data = run.get("roles", {}).get(role)
        if role_data:
            counts.append(role_data["count"])
    return counts


def estimate(plan_units: list[PlanUnit], project_root: Path) -> dict[str, int]:
    totals: dict[str, int] = {}
    for unit in plan_units:
        surface_id = unit["surface_id"]
        role = unit["role"]
        count = unit["count"]
        per_unit = _per_unit_estimate(surface_id, role, project_root)
        totals[surface_id] = totals.get(surface_id, 0) + per_unit * count
    return totals


def check(project_root: Path, run_dir: Path, next_role: str, cap_tokens: int | None) -> int:
    if cap_tokens is None:
        return 0
    projected = used(run_dir) + _prior(next_role)
    return 1 if projected > cap_tokens else 0
