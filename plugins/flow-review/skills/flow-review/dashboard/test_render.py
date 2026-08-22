"""Tests for the flow-review dashboard renderer.

Run directly: python test_render.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import render  # noqa: E402


def _line(**kw):
    kw.setdefault("ts", "2026-07-29T20:00:00")
    return json.dumps(kw)


# --- parsing and state fold -------------------------------------------------

def test_parse_skips_torn_and_blank_lines():
    """Three concurrent appenders guarantee a torn final line eventually."""
    text = "\n".join([
        _line(type="run", state="running", mode="deep", flows_total=3),
        "",
        '{"ts":"2026-07-29T20:00:01","type":"ste',  # torn write
        _line(type="step", surface="web", flow="w1", step="launch", state="ok"),
        "   ",
    ])
    events = render.parse_events(text)
    assert len(events) == 2
    assert events[0]["type"] == "run"
    assert events[1]["step"] == "launch"


def test_parse_skips_non_object_lines():
    text = "\n".join([
        "[1,2,3]",
        '"a string"',
        _line(type="run", state="running", mode="fast", flows_total=1),
    ])
    assert len(render.parse_events(text)) == 1


def test_surface_view_takes_latest_shot_and_running_step():
    text = "\n".join([
        _line(type="shot", surface="web", shot="shots/a.png"),
        _line(type="step", surface="web", flow="w1", step="open settings", state="ok"),
        _line(type="shot", surface="web", shot="shots/b.png"),
        _line(type="step", surface="web", flow="w1", step="open the settings tab", state="running"),
    ])
    surface = render.build_state(render.parse_events(text)).surfaces["web"]
    assert surface.shot == "shots/b.png"
    assert surface.current == "open the settings tab"


def test_surface_view_keeps_only_last_four_steps_newest_first():
    text = "\n".join(
        _line(type="step", surface="api", flow="a1", step=f"s{i}", state="ok")
        for i in range(6)
    )
    steps = render.build_state(render.parse_events(text)).surfaces["api"].steps
    assert [s["step"] for s in steps] == ["s5", "s4", "s3", "s2"]


def test_surface_state_follows_last_status_event():
    text = "\n".join([
        _line(type="status", surface="cli", state="running", text="surface start"),
        _line(type="status", surface="cli", state="recovering", text="R3 restart surface"),
    ])
    assert render.build_state(render.parse_events(text)).surfaces["cli"].state == "recovering"


def test_no_surfaces_when_none_announced_and_none_emitted():
    """No fixed list under the new model -- no announcement, no events, no surfaces, and
    rendering must still succeed rather than KeyError on a lane that no longer exists."""
    state = render.build_state([])
    assert state.surfaces == {}
    html = render.render_html(state, TEMPLATE, "2026-07-29T20:00:00")
    assert "{{" not in html


def test_severity_counts_and_findings_newest_first():
    text = "\n".join([
        _line(type="finding", sev="P2", text="spacing off", surface="web"),
        _line(type="finding", sev="P0", text="crash on submit", surface="api"),
        _line(type="finding", sev="P1", text="raw error surfaced", surface="cli"),
        _line(type="finding", sev="P0", text="saved record altered", surface="shared"),
    ])
    state = render.build_state(render.parse_events(text))
    assert state.counts == {"P0": 2, "P1": 1, "P2": 1}
    assert state.findings[0]["text"] == "saved record altered"


def test_flows_done_counts_terminal_status_not_steps():
    """Ten steps on one flow is not ten flows done."""
    lines = [_line(type="run", state="running", mode="deep", flows_total=4)]
    lines += [
        _line(type="step", surface="web", flow="w1", step=f"s{i}", state="ok")
        for i in range(10)
    ]
    lines += [
        _line(type="status", surface="web", flow="w1", state="ok", text="done"),
        _line(type="status", surface="api", flow="a1", state="blocked", text="quarantined"),
        _line(type="status", surface="cli", flow="c1", state="skipped", text="not built"),
        _line(type="status", surface="cli", state="running", text="surface start"),
    ]
    state = render.build_state(render.parse_events("\n".join(lines)))
    assert state.flows_total == 4
    assert state.flows_done == 3


def test_run_done_marks_finished():
    text = "\n".join([
        _line(type="run", state="running", mode="deep", flows_total=2),
        _line(type="run", state="done", mode="deep", flows_total=2),
    ])
    state = render.build_state(render.parse_events(text))
    assert state.finished is True
    assert state.mode == "deep"


def test_elapsed_formats_hours_and_minutes():
    assert render.elapsed_str("2026-07-29T20:00:00", "2026-07-29T20:07:30") == "07:30"
    assert render.elapsed_str("2026-07-29T20:00:00", "2026-07-29T22:03:04") == "2:03:04"
    assert render.elapsed_str(None, None) == "00:00"


def test_elapsed_survives_mixed_offset_and_naive_stamps():
    """One tester stamping an offset must not take the whole dashboard down."""
    assert render.elapsed_str("2026-07-29T20:00:00+05:30", "2026-07-29T20:04:00") == "04:00"
    assert render.elapsed_str("2026-07-29T20:00:00", "2026-07-29T20:04:00+05:30") == "04:00"
    assert render.elapsed_str("not a date", "2026-07-29T20:04:00") == "00:00"


# --- templating -------------------------------------------------------------

TEMPLATE = """<head>{{REFRESH}}</head>
<body><span id="mode">{{MODE}}</span><span id="el">{{ELAPSED}}</span>
<span id="flows">{{FLOWS_DONE}}/{{FLOWS_TOTAL}}</span>
<span>{{P0}} {{P1}} {{P2}}</span>
<div id="lanes">{{LANES}}</div>
<!--LANE--><section class="{{LANE_STATE_CLASS}}"><h2>{{LANE_NAME}}</h2><em>{{LANE_STATE}}</em>
{{LANE_SHOT_BLOCK}}<p>{{LANE_CURRENT}}</p><ul>{{LANE_STEPS}}</ul></section><!--/LANE-->
<!--STEP--><li class="{{STEP_STATE}}">{{STEP_FLOW}} {{STEP_LABEL}}</li><!--/STEP-->
<div id="findings">{{FINDINGS}}</div>
<!--FINDING--><div class="{{F_SEV}}">{{F_WHERE}} {{F_TEXT}}</div><!--/FINDING-->
{{REPORT}}</body>"""


def _render(text, now="2026-07-29T20:10:00", report=""):
    state = render.build_state(render.parse_events(text))
    return render.render_html(state, TEMPLATE, now, report)


def test_render_leaves_no_placeholders():
    html = _render("\n".join([
        _line(type="run", state="running", mode="deep", flows_total=2),
        _line(type="step", surface="web", flow="w1", step="launch", state="running"),
        _line(type="shot", surface="web", shot="shots/a.png"),
        _line(type="finding", sev="P1", text="raw error surfaced", surface="web", flow="w1"),
    ]))
    assert "{{" not in html
    assert "<!--LANE-->" not in html and "<!--/LANE-->" not in html


def test_missing_sub_template_block_raises_rather_than_rendering_empty():
    """An empty findings feed must never be mistaken for 'nothing found'."""
    broken = TEMPLATE.replace("<!--FINDING-->", "").replace("<!--/FINDING-->", "")
    try:
        render.render_html(render.build_state([]), broken, "2026-07-29T20:00:00")
    except ValueError as exc:
        assert "FINDING" in str(exc)
    else:
        raise AssertionError("expected ValueError for the missing block")


def test_render_repeats_lane_block_once_per_surface():
    html = _render(_line(type="run", state="running", mode="fast", flows_total=1,
                          surfaces=["web", "api", "cli"]))
    assert html.count("<section") == 3
    for surface in ("web", "api", "cli"):
        assert f"<h2>{surface}</h2>" in html


def test_live_run_gets_meta_refresh_and_finished_run_does_not():
    live = _render(_line(type="run", state="running", mode="deep", flows_total=1))
    assert 'http-equiv="refresh"' in live
    done = _render("\n".join([
        _line(type="run", state="running", mode="deep", flows_total=1),
        _line(type="run", state="done", mode="deep", flows_total=1),
    ]))
    assert "refresh" not in done


def test_empty_shot_renders_placeholder_not_broken_image():
    html = _render(_line(type="status", surface="cli", state="running", text="surface start"))
    assert "<img" not in html
    assert html.count("shot-empty") == 1


def test_findings_and_text_are_html_escaped():
    html = _render(_line(type="finding", sev="P0", text="<script>alert(1)</script> & co"))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html and "&amp;" in html


def test_report_is_injected_when_supplied():
    html = _render(_line(type="run", state="done", mode="deep", flows_total=1),
                   report="<h2>Findings</h2>")
    assert "<h2>Findings</h2>" in html


def test_elapsed_uses_wall_clock_while_live_and_last_event_when_finished():
    live = _render(_line(type="run", state="running", mode="deep", flows_total=1),
                   now="2026-07-29T20:05:00")
    assert "05:00" in live
    done = _render("\n".join([
        _line(type="run", state="running", mode="deep", flows_total=1),
        _line(ts="2026-07-29T20:02:00", type="run", state="done", mode="deep", flows_total=1),
    ]), now="2026-07-29T23:00:00")
    assert "02:00" in done


# --- surfaces model -----------------------------------------------------------

def _events(*objs):
    return [dict(o) for o in objs]


def test_surfaces_come_from_the_run_event_not_a_hardcoded_list():
    state = render.build_state(_events(
        {"ts": "2026-01-01T00:00:00", "type": "run", "state": "running",
         "mode": "deep", "flows_total": 2, "surfaces": ["web", "api"]},
    ))
    assert list(state.surfaces) == ["web", "api"]


def test_an_unannounced_surface_still_gets_a_column():
    state = render.build_state(_events(
        {"ts": "2026-01-01T00:00:00", "type": "run", "state": "running",
         "mode": "deep", "flows_total": 1, "surfaces": ["web"]},
        {"ts": "2026-01-01T00:00:01", "type": "step", "surface": "cli",
         "flow": "c01", "step": "run --help", "state": "ok"},
    ))
    assert "cli" in state.surfaces


def test_no_surfaces_at_all_renders_without_raising():
    template = (Path(render.__file__).parent / "template.html").read_text(encoding="utf-8")
    state = render.build_state([])
    html = render.render_html(state, template, "2026-01-01T00:00:00")
    assert "<html" in html.lower()


def test_findings_and_withdrawals_still_fold_correctly():
    state = render.build_state(_events(
        {"ts": "t1", "type": "finding", "sev": "P1", "text": "one"},
        {"ts": "t2", "type": "withdraw", "finding_ts": "t1", "text": "answered"},
    ))
    assert state.counts["P1"] == 0
    assert state.findings[0]["withdrawn"] is True


if __name__ == "__main__":
    import traceback
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception:
                failures += 1
                print(f"FAIL {name}")
                traceback.print_exc()
    print(f"\n{failures} failure(s)")
    sys.exit(1 if failures else 0)
