"""GO-gate plan (B9): pure data, no prompts, no LLM calls (A-19/A-20).

`plan()` computes per-surface unit templates (priors, replaced by per-surface medians once
usage_history.json has >= 3 runs), token estimates, and the gap list the SKILL/CLI layer uses to
ask the user about missing credentials and destructive opt-ins.
"""
from __future__ import annotations

import os
import statistics
from pathlib import Path

from flow_review import budget, config, drift, envsetup

UNIT_TEMPLATES = {
    "quick": {"explorer": 1, "verifier": 1},
    "goal": {"explorer": 1, "lens": 3, "verifier": 1},
    "auto": {"explorer": 2, "cold-eyes": 1, "lens": 3, "verifier": 1},
    "full": {"explorer": 3, "cold-eyes": 1, "lens": 6, "verifier": 2},
}


def _unit_counts_for(surface_id: str, mode: str, project_root: Path) -> dict[str, int]:
    template = dict(UNIT_TEMPLATES[mode])
    for role in list(template.keys()):
        counts = budget.role_unit_counts(surface_id, role, project_root)
        if len(counts) >= 3:
            template[role] = int(statistics.median(counts))
    return template


def plan(project_root: Path, mode: str, goal: str | None = None,
         record: bool = False, skip: list[str] | None = None) -> dict:
    if mode not in UNIT_TEMPLATES:
        raise ValueError(f"unknown mode: {mode!r}")
    if mode in ("goal", "quick") and not goal:
        raise ValueError(f"--goal is required for mode {mode!r}")

    cfg = config.load(project_root / ".flow-review" / "config.json")
    runnable = drift.runnable_surfaces(cfg)
    skip = skip or []
    skipped = [s.id for s in runnable if s.id in skip]
    runnable = [s for s in runnable if s.id not in skip]

    dotenv_path = project_root / ".flow-review" / ".env"
    combined_env = dict(os.environ)
    if dotenv_path.exists():
        envsetup.load_dotenv(dotenv_path, environ=combined_env)

    surfaces_out = []
    persistent_ids = []
    total_tokens = 0
    for surface in runnable:
        if surface.state == "persistent":
            persistent_ids.append(surface.id)

        counts = _unit_counts_for(surface.id, mode, project_root)
        units = [{"role": role, "count": count} for role, count in counts.items() if count > 0]
        plan_units = [
            {"surface_id": surface.id, "role": u["role"], "count": u["count"]}
            for u in units
        ]
        estimate_map = budget.estimate(plan_units, project_root)
        estimate_tokens = estimate_map.get(surface.id, 0)
        total_tokens += estimate_tokens

        gaps = []
        for _logical, env_name in (surface.creds or {}).items():
            if env_name not in combined_env:
                gaps.append({"type": "missing_creds", "name": env_name, "offer_save": True})

        surfaces_out.append({
            "surface_id": surface.id,
            "units": units,
            "estimate_tokens": estimate_tokens,
            "gaps": gaps,
        })

    top_gaps = []
    if persistent_ids:
        top_gaps.append({
            "type": "destructive_optin",
            "surfaces": persistent_ids,
            "opt_in_default": False,
        })

    return {
        "schema_version": 1,
        "mode": mode,
        "goal": goal,
        "record": record,
        "surfaces": surfaces_out,
        "skipped_surfaces": skipped,
        "gaps": top_gaps,
        "total_estimate_tokens": total_tokens,
    }
