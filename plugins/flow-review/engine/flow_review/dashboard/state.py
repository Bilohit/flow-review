"""Fold events.jsonl + the ledger + the budget module into the dashboard's
page-state JSON. Pure function of (events, ledger, cfg): no mutation, no
templating of user text. Torn/malformed JSONL lines are dropped -- several
surfaces write concurrently.
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from flow_review import budget, ledger

SEVERITIES = ("P0", "P1", "P2")
LIVE_STATES = ("open", "regressed")
HISTORY_WINDOW = 8


def _parse_events(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            events.append(obj)
    return events


@dataclass
class _Lane:
    surface_id: str
    kind: str = "web"
    state: str = "idle"
    shot: str | None = None
    output: str | None = None
    current_step: str | None = None
    flow_id: str | None = None
    history: list[dict] = field(default_factory=list)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def fold(project_root: Path, run_dir: Path, cfg) -> dict:
    events_path = run_dir / "events.jsonl"
    text = events_path.read_text(encoding="utf-8") if events_path.exists() else ""
    events = _parse_events(text)

    run = {"id": run_dir.name, "mode": "auto", "started": None, "finished": False,
           "flows_total": 0, "flows_done": 0, "elapsed_s": 0}
    lanes: dict[str, _Lane] = {}
    done_flows: set[str] = set()
    live_findings: dict[str, dict] = {}
    withdrawn: set[str] = set()
    goals: dict[str, dict] = {}
    not_exercised: list[dict] = []
    header_history: list[dict] = []
    last_ts: str | None = None

    def lane(surface_id: str | None, kind: str = "web") -> _Lane | None:
        if not surface_id:
            return None
        if surface_id not in lanes:
            lanes[surface_id] = _Lane(surface_id, kind=kind)
        return lanes[surface_id]

    for ev in events:
        ts = ev.get("ts")
        if ts:
            last_ts = ts
            if run["started"] is None:
                run["started"] = ts
        kind = ev.get("type")

        if kind == "run":
            run["mode"] = ev.get("mode", run["mode"])
            if "flows_total" in ev:
                # RC2: `flow-review event ... flows_total=N` (the k=v CLI form) always writes a
                # string -- cli.py's event verb never coerces. Coerce here so max() below never
                # crashes on an int/str comparison; junk leaves the previous value untouched.
                try:
                    run["flows_total"] = int(ev["flows_total"])
                except (TypeError, ValueError):
                    pass
            for surf in ev.get("surfaces", []) or []:
                if isinstance(surf, dict):
                    lane(surf.get("id"), surf.get("kind", "web"))
                else:
                    lane(str(surf))
            if ev.get("state") in ("done", "halted"):
                run["finished"] = True
            continue

        if kind == "finding":
            # Canonical finding-event payload: {id, surface_id, flow_id, rule, route, locator,
            # sev, text, evidence, disposition}. disposition ("engine"|"objective"|"judgment")
            # is pre-reconcile only -- it rides along on the live dict, not on LedgerEntry.
            fid = ev.get("id")
            live_findings[fid] = {
                "id": fid, "fingerprint": "", "state": "open", "sev": ev.get("sev"),
                "rule": ev.get("rule"), "flow_id": ev.get("flow_id"),
                "surface_id": ev.get("surface_id"), "route": ev.get("route", ""),
                "locator": ev.get("locator", ""), "text": ev.get("text", ""),
                "evidence": ev.get("evidence", []), "runs_seen": 1,
                "first_run": ts, "last_run": ts, "aliases": [], "reason": "",
                "disposition": ev.get("disposition"),
            }
            continue

        if kind == "withdraw":
            fid = ev.get("finding_id")
            withdrawn.add(fid)
            live_findings.pop(fid, None)
            continue

        if kind == "goal":
            gid = ev.get("flow_id")
            if gid:
                goals[gid] = ev
            continue

        surf_id = ev.get("surface_id") or ev.get("surface")
        if kind == "status":
            if ev.get("state") == "not-exercised":
                # payment-not-sandboxed / no-test-inbox / destructive-no-optin / budget-cap skips
                not_exercised.append(ev)
                continue
            flow = ev.get("flow_id")
            if flow and ev.get("state") in ("ok", "blocked", "skipped"):
                done_flows.add(flow)
            elif surf_id:
                lane(surf_id).state = ev.get("state", lanes[surf_id].state)
            continue

        ln = lane(surf_id) if surf_id else None
        if ln is None:
            continue
        if kind == "shot":
            ln.shot = ev.get("shot") or ln.shot
        elif kind == "output":
            ln.output = ev.get("text") or ln.output
        elif kind == "step":
            ln.flow_id = ev.get("flow_id", ln.flow_id)
            if ev.get("step") == "flow-end":
                # RC3: drive's flow_end emits {"type": "step", "step": "flow-end",
                # "status": ok|blocked}, never a `type: status` event -- count it here too.
                flow = ev.get("flow_id")
                if flow:
                    done_flows.add(flow)
            entry = {"step": ev.get("step"), "state": ev.get("state")}
            ln.history.append(entry)
            ln.history[:] = ln.history[-HISTORY_WINDOW:]
            ln.current_step = ev.get("step") if ev.get("state") == "running" else None
        # "usage" events are intentionally not read here -- budget.used(run_dir) is the
        # one source of truth (A-23); summing them again here would be a second truth.

    run["flows_done"] = len(done_flows)
    run["flows_total"] = max(run["flows_total"], run["flows_done"])
    if run["started"] and (last_ts or run["finished"]):
        end = last_ts if run["finished"] else _now_iso()
        run["elapsed_s"] = _elapsed_seconds(run["started"], end)

    led = ledger.load(project_root / ".flow-review" / "findings.json")
    # Canonical: Ledger.findings is dict[str, LedgerEntry] keyed by id -- iterate .values(),
    # never assume a list.
    ledger_findings = [dataclasses.asdict(e) for e in led.findings.values() if e.id not in withdrawn]
    ledger_ids = {f["id"] for f in ledger_findings}
    findings = ledger_findings + [f for fid, f in live_findings.items()
                                   if fid not in ledger_ids and fid not in withdrawn]

    counts = {s: 0 for s in SEVERITIES}
    for f in findings:
        if f.get("state") in LIVE_STATES and f.get("sev") in counts:
            counts[f["sev"]] += 1
    total = sum(counts.values())
    worst = next((s for s in SEVERITIES if counts[s] > 0), None)

    used_tokens = budget.used(run_dir)
    cap_tokens = cfg.budget.get("cap_tokens") if getattr(cfg, "budget", None) else None
    pct = round(used_tokens / cap_tokens, 3) if cap_tokens else None

    return {
        "run": run,
        "budget": {"cap_tokens": cap_tokens, "used_tokens": used_tokens, "pct": pct},
        "badge": {"total": total, "worst_sev": worst, "counts": counts},
        "lanes": [
            {"surface_id": l.surface_id, "kind": l.kind, "state": l.state, "shot": l.shot,
             "output": l.output, "current_step": l.current_step, "flow_id": l.flow_id,
             "history": l.history}
            for l in lanes.values()
        ],
        "header": {"sparkline": header_history, "surface_dots": [
            {"surface_id": l.surface_id, "status": _dot_status(l.state)} for l in lanes.values()
        ]},
        "report": _build_report(_this_run_findings(ledger_findings, ledger_ids, live_findings,
                                                     withdrawn, run["id"]),
                                 goals, not_exercised) if run["finished"] else None,
        "findings": findings,
    }


def _elapsed_seconds(start_iso: str, end_iso: str) -> int:
    try:
        start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
    except ValueError:
        return 0
    return max(0, int((end - start).total_seconds()))


def _dot_status(lane_state: str) -> str:
    return "error" if lane_state in ("blocked", "error") else "ok"


def _this_run_findings(ledger_findings: list[dict], ledger_ids: set[str],
                        live_findings: dict[str, dict], withdrawn: set[str], run_id: str) -> list[dict]:
    # CP3 minor finding 7: the report is scoped to *this run* -- a reconciled ledger entry
    # whose last_run isn't this run's id (a different surface/flow this run didn't touch)
    # stays out of it, while any live, not-yet-reconciled finding from this run always shows.
    return [f for f in ledger_findings if f.get("last_run") == run_id] + [
        f for fid, f in live_findings.items() if fid not in ledger_ids and fid not in withdrawn
    ]


def _is_opinion(f: dict) -> bool:
    return f.get("disposition") == "judgment" and f.get("sev") == "P2"


def _build_report(findings: list[dict], goals: dict[str, dict], not_exercised: list[dict]) -> dict:
    # Spec §11: needs-attention = NEW (open, first seen this run) and REGRESSED, by severity.
    # Judgment P2 (opinions) and open repeats are collapsed, never headline.
    def _new_or_regressed(f):
        return f.get("state") == "regressed" or (f.get("state") == "open" and f.get("runs_seen", 1) == 1)

    needs_attention = sorted(
        (f for f in findings if _new_or_regressed(f) and not _is_opinion(f)),
        key=lambda f: SEVERITIES.index(f.get("sev", "P2")) if f.get("sev") in SEVERITIES else 9,
    )
    return {
        "needs_attention": needs_attention,
        "goal_cards": list(goals.values()),
        "collapsed": {
            "opinions": [f for f in findings if _is_opinion(f) and f.get("state") in ("open", "regressed")],
            "repeats": [f for f in findings if f.get("state") == "open" and f.get("runs_seen", 1) > 1
                        and not _is_opinion(f)],
            "refuted": [f for f in findings if f.get("state") == "refuted"],
            # A-15: a human's triage call (false-positive/wont-fix/accepted) is sticky -- it
            # never vanishes, it gets its own collapsed group instead of falling into no section.
            "triaged": [f for f in findings if f.get("state") in ("false-positive", "wont-fix", "accepted")],
            "not_exercised": not_exercised,
        },
    }
