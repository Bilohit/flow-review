"""flow-review dashboard: fold an append-only event log into HTML.

The dashboard is a pure function of events.jsonl. Several surface testers
append to that log concurrently, so parsing tolerates torn and malformed
lines by design.

Usage:  python render.py <run-folder> [--report <html-fragment-file>]
"""
from __future__ import annotations

import html as _html
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# No fixed surface list. Surfaces come from the run event's `surfaces` key when the main thread
# announces them, and any surface that emits an event gets a column whether announced or not --
# an unannounced surface with a blank panel is how a whole surface went invisible before.
SEVERITIES = ("P0", "P1", "P2")
STEP_WINDOW = 4
REFRESH_TAG = '<meta http-equiv="refresh" content="3">'


@dataclass
class SurfaceView:
    name: str
    state: str = "idle"
    shot: str | None = None
    current: str | None = None
    steps: list[dict] = field(default_factory=list)


@dataclass
class RunState:
    mode: str = "deep"
    flows_total: int = 0
    flows_done: int = 0
    started: str | None = None
    last_ts: str | None = None
    finished: bool = False
    counts: dict[str, int] = field(default_factory=lambda: {s: 0 for s in SEVERITIES})
    surfaces: dict[str, SurfaceView] = field(default_factory=dict)
    findings: list[dict] = field(default_factory=list)


# --- fold -------------------------------------------------------------------

def parse_events(text: str) -> list[dict]:
    """Parse JSONL, dropping anything that is not a complete JSON object."""
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


def _surface_name(ev: dict) -> str:
    value = ev.get("surface")
    return str(value) if value else ""


def _surface_view(state: RunState, name: str) -> SurfaceView | None:
    """Create a column on first sight. A surface that emits is a surface that exists."""
    if not name:
        return None
    if name not in state.surfaces:
        state.surfaces[name] = SurfaceView(name)
    return state.surfaces[name]


def build_state(events: list[dict], surfaces: list[str] | None = None) -> RunState:
    state = RunState(surfaces={name: SurfaceView(name) for name in (surfaces or [])})
    done_flows: set[str] = set()

    for ev in events:
        ts = ev.get("ts")
        if ts:
            state.last_ts = ts
            if state.started is None:
                state.started = ts

        kind = ev.get("type")
        if kind == "run":
            state.mode = ev.get("mode", state.mode)
            state.flows_total = ev.get("flows_total", state.flows_total)
            for name in ev.get("surfaces", []) or []:
                _surface_view(state, str(name))
            if ev.get("state") in ("done", "halted"):
                state.finished = True
            continue

        if kind == "finding":
            sev = ev.get("sev")
            if sev in state.counts:
                state.counts[sev] += 1
            state.findings.append(ev)
        if kind == "withdraw":
            # A post-run correction (usually: the user answered and the finding did not survive).
            # Append-only stays append-only -- the retraction is its own event, matched to the
            # original by ts, so the header can never disagree with the report below it.
            for prior in state.findings:
                if prior.get("ts") == ev.get("finding_ts") and not prior.get("withdrawn"):
                    prior["withdrawn"] = True
                    prior["text"] = "WITHDRAWN -- " + (ev.get("text") or "") + " | was: " + prior.get("text", "")
                    if prior.get("sev") in state.counts:
                        state.counts[prior["sev"]] -= 1
                    break
            continue

        surface = _surface_view(state, _surface_name(ev))

        if kind == "status":
            # a status carrying a flow id is that flow's terminal event
            flow = ev.get("flow")
            if flow and ev.get("state") in ("ok", "blocked", "skipped"):
                done_flows.add(flow)
            elif surface is not None:
                surface.state = ev.get("state", surface.state)
            continue

        if surface is None:
            continue

        if kind == "shot":
            surface.shot = ev.get("shot") or surface.shot
        elif kind == "step":
            surface.steps.append(ev)
            surface.current = ev.get("step") if ev.get("state") == "running" else None

    for surface in state.surfaces.values():
        surface.steps = list(reversed(surface.steps[-STEP_WINDOW:]))

    state.flows_done = len(done_flows)
    state.flows_total = max(state.flows_total, state.flows_done)
    state.findings.reverse()
    return state


def elapsed_str(start_iso: str | None, end_iso: str | None) -> str:
    """MM:SS under an hour, H:MM:SS past it. Unparseable input reads 00:00."""
    if not start_iso or not end_iso:
        return "00:00"
    try:
        start = datetime.fromisoformat(start_iso)
        end = datetime.fromisoformat(end_iso)
    except ValueError:
        return "00:00"
    # a tester that stamps an offset alongside naive ones would otherwise
    # raise TypeError on subtraction and take the whole dashboard down
    if (start.tzinfo is None) != (end.tzinfo is None):
        start, end = start.replace(tzinfo=None), end.replace(tzinfo=None)
    total = max(0, int((end - start).total_seconds()))
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


# --- templating -------------------------------------------------------------

def _esc(value) -> str:
    return _html.escape(str(value if value is not None else ""))


def _fill(block: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        block = block.replace("{{" + key + "}}", value)
    return block


def extract_block(template: str, name: str) -> tuple[str, str]:
    """Pull a <!--NAME-->...<!--/NAME--> sub-template out of the template.

    Raises rather than degrading: a missing block would render an empty lane
    column or an empty findings feed, which reads as "nothing found" on an
    unattended overnight run. Fails on the first render, at GO, not mid-run.
    """
    pattern = re.compile(f"<!--{name}-->(.*?)<!--/{name}-->", re.DOTALL)
    match = pattern.search(template)
    if not match:
        raise ValueError(f"template.html is missing the <!--{name}--> block")
    return match.group(1), pattern.sub("", template, count=1)


def _render_steps(surface: SurfaceView, step_tpl: str) -> str:
    return "".join(
        _fill(step_tpl, {
            "STEP_STATE": _esc(step.get("state", "")),
            "STEP_LABEL": _esc(step.get("step", "")),
            "STEP_FLOW": _esc(step.get("flow", "")),
        })
        for step in surface.steps
    )


def _render_findings(state: RunState, finding_tpl: str) -> str:
    rows = []
    for finding in state.findings:
        where = " / ".join(p for p in (finding.get("surface"), finding.get("flow")) if p)
        rows.append(_fill(finding_tpl, {
            "F_SEV": _esc(finding.get("sev", "")),
            "F_WHERE": _esc(where),
            "F_TEXT": _esc(finding.get("text", "")),
        }))
    return "".join(rows)


def render_html(state: RunState, template: str, now_iso: str, report: str = "") -> str:
    lane_tpl, template = extract_block(template, "LANE")
    step_tpl, template = extract_block(template, "STEP")
    finding_tpl, template = extract_block(template, "FINDING")

    lanes = ""
    for name, surface in state.surfaces.items():
        shot_block = (
            f'<div class="shot"><img src="{_esc(surface.shot)}" '
            f'alt="{_esc(name)} latest screen"></div>'
            if surface.shot else '<div class="shot shot-empty"></div>'
        )
        lanes += _fill(lane_tpl, {
            "LANE_NAME": _esc(name),
            "LANE_STATE": _esc(surface.state),
            "LANE_STATE_CLASS": f"lane lane-{_esc(surface.state)}",
            "LANE_SHOT": _esc(surface.shot or ""),
            "LANE_SHOT_BLOCK": shot_block,
            "LANE_CURRENT": _esc(surface.current) if surface.current else "&mdash;",
            "LANE_STEPS": _render_steps(surface, step_tpl),
        })

    end = state.last_ts if state.finished else now_iso
    return _fill(template, {
        "REFRESH": "" if state.finished else REFRESH_TAG,
        "MODE": _esc(state.mode),
        "ELAPSED": elapsed_str(state.started, end),
        "FLOWS_DONE": str(state.flows_done),
        "FLOWS_TOTAL": str(state.flows_total),
        "P0": str(state.counts["P0"]),
        "P1": str(state.counts["P1"]),
        "P2": str(state.counts["P2"]),
        "LANES": lanes,
        "FINDINGS": _render_findings(state, finding_tpl),
        "REPORT": report,
    })


# --- cli --------------------------------------------------------------------

def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2

    run_dir = Path(argv[0])
    report = ""
    if "--report" in argv:
        report = Path(argv[argv.index("--report") + 1]).read_text(encoding="utf-8")

    events_path = run_dir / "events.jsonl"
    text = events_path.read_text(encoding="utf-8") if events_path.exists() else ""
    template = (Path(__file__).parent / "template.html").read_text(encoding="utf-8")

    state = build_state(parse_events(text))
    now = datetime.now().isoformat(timespec="seconds")
    out = run_dir / "dashboard.html"
    # ponytail: write-then-replace so a browser mid-refresh never reads a half-written page
    tmp = out.with_suffix(".html.tmp")
    tmp.write_text(render_html(state, template, now, report), encoding="utf-8")
    tmp.replace(out)
    # ascii only: this line lands in a Windows console that mangles anything else
    print(f"{out} | {state.flows_done}/{state.flows_total} flows | "
          f"P0={state.counts['P0']} P1={state.counts['P1']} P2={state.counts['P2']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
