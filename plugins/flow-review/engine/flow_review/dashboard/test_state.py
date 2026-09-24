from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from flow_review.dashboard.state import fold


@dataclass
class _Entry:
    id: str
    fingerprint: str = ""
    surface_id: str = ""
    flow_id: str = ""
    rule: str = ""
    route: str = ""
    locator: str = ""
    sev: str = "P2"
    text: str = ""
    evidence: list = field(default_factory=list)
    state: str = "open"
    runs_seen: int = 1
    first_run: str = ""
    last_run: str = ""
    aliases: list = field(default_factory=list)
    reason: str = ""


class _FakeLedger:
    def __init__(self, findings):
        # Canonical: Ledger.findings is dict[str, LedgerEntry] keyed by id.
        self.findings = {e.id: e for e in findings}


class _FakeCfg:
    budget = {"cap_tokens": 200000}


def _write_events(run_dir: Path, events: list[dict]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "events.jsonl").open("w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")


def _patch_common(monkeypatch, findings=(), used_tokens=0):
    monkeypatch.setattr("flow_review.dashboard.state.ledger.load",
                         lambda path: _FakeLedger(list(findings)))
    monkeypatch.setattr("flow_review.dashboard.state.budget.used",
                         lambda run_dir: used_tokens)


def test_withdraw_matches_by_finding_id_not_timestamp(tmp_path, monkeypatch):
    _patch_common(monkeypatch)
    run_dir = tmp_path / "run"
    _write_events(run_dir, [
        {"ts": "2026-09-23T10:00:00.000Z", "id": "e1", "type": "run", "mode": "goal",
         "surfaces": [{"id": "web-app", "kind": "web"}]},
        {"ts": "2026-09-23T10:00:01.000Z", "id": "f1", "type": "finding",
         "sev": "P1", "surface_id": "web-app", "text": "low contrast", "disposition": "judgment"},
        # A second finding stamped at the SAME ts as the withdraw below -- H7 regression bait.
        {"ts": "2026-09-23T10:00:02.000Z", "id": "f2", "type": "finding",
         "sev": "P1", "surface_id": "web-app", "text": "unrelated finding", "disposition": "objective"},
        {"ts": "2026-09-23T10:00:02.000Z", "id": "e4", "type": "withdraw", "finding_id": "f1"},
    ])
    state = fold(tmp_path, run_dir, _FakeCfg())
    ids = {f["id"] for f in state["findings"]}
    assert "f1" not in ids       # withdrawn finding is gone
    assert "f2" in ids           # the co-timestamped finding survives (H7)


def test_no_placeholder_expansion_of_user_text(tmp_path, monkeypatch):
    _patch_common(monkeypatch)
    run_dir = tmp_path / "run"
    _write_events(run_dir, [
        {"ts": "2026-09-23T10:00:00.000Z", "id": "e1", "type": "run", "mode": "goal", "surfaces": []},
        {"ts": "2026-09-23T10:00:01.000Z", "id": "f1", "type": "finding", "disposition": "engine",
         "sev": "P2", "surface_id": "web-app", "text": "literal {{P0}} in copy confuses users"},
    ])
    state = fold(tmp_path, run_dir, _FakeCfg())
    texts = [f["text"] for f in state["findings"]]
    assert "literal {{P0}} in copy confuses users" in texts  # untouched, not template-expanded


def test_report_absent_while_running_present_when_done(tmp_path, monkeypatch):
    _patch_common(monkeypatch)
    running_dir = tmp_path / "running"
    _write_events(running_dir, [
        {"ts": "2026-09-23T10:00:00.000Z", "id": "e1", "type": "run", "mode": "goal",
         "surfaces": [], "state": "running"},
    ])
    assert fold(tmp_path, running_dir, _FakeCfg())["report"] is None

    done_dir = tmp_path / "done"
    _write_events(done_dir, [
        {"ts": "2026-09-23T10:00:00.000Z", "id": "e1", "type": "run", "mode": "goal",
         "surfaces": [], "state": "done"},
    ])
    assert fold(tmp_path, done_dir, _FakeCfg())["report"] is not None


def test_report_groups_findings_per_spec_section_11():
    from flow_review.dashboard.state import _build_report
    new_p1 = {"id": "a", "state": "open", "runs_seen": 1, "sev": "P1", "disposition": "engine"}
    regressed = {"id": "b", "state": "regressed", "runs_seen": 4, "sev": "P0", "disposition": "objective"}
    repeat = {"id": "c", "state": "open", "runs_seen": 3, "sev": "P1", "disposition": "engine"}
    opinion = {"id": "d", "state": "open", "runs_seen": 1, "sev": "P2", "disposition": "judgment"}
    refuted = {"id": "e", "state": "refuted", "runs_seen": 1, "sev": "P1", "disposition": "judgment"}
    skipped = {"type": "status", "state": "not-exercised", "reason": "no-test-inbox", "flow_id": "signup"}
    report = _build_report([new_p1, regressed, repeat, opinion, refuted], {}, [skipped])
    assert [f["id"] for f in report["needs_attention"]] == ["b", "a"]  # by severity, P0 first
    assert [f["id"] for f in report["collapsed"]["opinions"]] == ["d"]
    assert [f["id"] for f in report["collapsed"]["repeats"]] == ["c"]
    assert [f["id"] for f in report["collapsed"]["refuted"]] == ["e"]
    assert report["collapsed"]["not_exercised"] == [skipped]


def test_budget_used_comes_from_budget_module_not_summed_locally(tmp_path, monkeypatch):
    _patch_common(monkeypatch, used_tokens=41230)
    run_dir = tmp_path / "run"
    _write_events(run_dir, [
        {"ts": "2026-09-23T10:00:00.000Z", "id": "e1", "type": "run", "mode": "goal", "surfaces": []},
        # a usage event that would sum to something else if state.py summed it itself --
        # asserts fold() calls budget.used() instead of re-deriving the total.
        {"ts": "2026-09-23T10:00:01.000Z", "id": "e2", "type": "usage",
         "surface": "web-app", "role": "explorer", "tokens": 999},
    ])
    body = fold(tmp_path, run_dir, _FakeCfg())
    assert body["budget"]["used_tokens"] == 41230
    assert body["budget"]["cap_tokens"] == 200000


def test_triaged_findings_get_their_own_collapsed_group():
    # A-15: false-positive/wont-fix/accepted are sticky and stay visible in the report,
    # each in the same collapsed-group shape as opinions/repeats/refuted -- never dropped.
    from flow_review.dashboard.state import _build_report
    fp = {"id": "a", "state": "false-positive", "runs_seen": 2, "sev": "P1", "disposition": "engine"}
    wf = {"id": "b", "state": "wont-fix", "runs_seen": 3, "sev": "P2", "disposition": "engine"}
    acc = {"id": "c", "state": "accepted", "runs_seen": 1, "sev": "P1", "disposition": "engine"}
    report = _build_report([fp, wf, acc], {}, [])
    triaged_ids = {f["id"] for f in report["collapsed"]["triaged"]}
    assert triaged_ids == {"a", "b", "c"}
    # never silently vanish: not counted as needs-attention, not dropped from the report entirely.
    assert report["needs_attention"] == []


def test_report_only_includes_findings_seen_this_run(tmp_path, monkeypatch):
    # CP3 minor finding 7: state.py:162 must scope the *report* to this run's findings --
    # a ledger entry last touched by an older run (different surface/flow this run didn't
    # exercise) stays out of the report, while a live (not-yet-reconciled) finding from this
    # run is always included.
    run_dir = tmp_path / "run"
    this_run_entry = _Entry(id="f_this", sev="P1", rule="contrast", surface_id="web-app",
                             flow_id="checkout", text="this run's reconciled finding",
                             state="open", last_run=run_dir.name)
    other_run_entry = _Entry(id="f_other", sev="P1", rule="contrast", surface_id="web-app",
                              flow_id="signup", text="stale finding from an older run",
                              state="open", last_run="some-other-run-id")
    _patch_common(monkeypatch, findings=[this_run_entry, other_run_entry])
    _write_events(run_dir, [
        {"ts": "2026-09-23T10:00:00.000Z", "id": "e1", "type": "run", "mode": "goal",
         "surfaces": [], "state": "done"},
        {"ts": "2026-09-23T10:00:01.000Z", "id": "f_live", "type": "finding", "disposition": "engine",
         "sev": "P1", "surface_id": "web-app", "flow_id": "cart", "text": "live, not yet reconciled"},
    ])
    body = fold(tmp_path, run_dir, _FakeCfg())
    report_ids = {f["id"] for f in body["report"]["needs_attention"]}
    assert "f_this" in report_ids
    assert "f_live" in report_ids
    assert "f_other" not in report_ids
    # the top-level findings list (badge/drawer) is unaffected -- still carries every open entry.
    all_ids = {f["id"] for f in body["findings"]}
    assert {"f_this", "f_other", "f_live"} <= all_ids


def test_run_event_flows_total_arrives_as_string_from_cli_and_still_counts(tmp_path, monkeypatch):
    # RC2: `flow-review event --run DIR --type run mode=quick flows_total=1` writes flows_total
    # as a string (cli.py's `event` verb never coerces k=v values) -- fold must still surface it
    # as a usable int, and a later `type run state=done` event must mark the run finished.
    _patch_common(monkeypatch)
    run_dir = tmp_path / "run"
    _write_events(run_dir, [
        {"ts": "2026-09-23T10:00:00.000Z", "id": "e1", "type": "run", "mode": "quick",
         "flows_total": "1"},
        {"ts": "2026-09-23T10:00:05.000Z", "id": "e2", "type": "run", "state": "done"},
    ])
    body = fold(tmp_path, run_dir, _FakeCfg())
    assert body["run"]["mode"] == "quick"
    assert body["run"]["flows_total"] == 1
    assert body["run"]["finished"] is True


def test_run_event_junk_flows_total_is_ignored_not_crashed_on(tmp_path, monkeypatch):
    _patch_common(monkeypatch)
    run_dir = tmp_path / "run"
    _write_events(run_dir, [
        {"ts": "2026-09-23T10:00:00.000Z", "id": "e1", "type": "run", "mode": "quick",
         "flows_total": "not-a-number"},
    ])
    body = fold(tmp_path, run_dir, _FakeCfg())
    assert body["run"]["flows_total"] == 0


def test_flow_end_step_event_counts_toward_done_flows(tmp_path, monkeypatch):
    # RC3: drive's flow_end emits {"type": "step", "step": "flow-end", "status": ok|blocked},
    # never a `type: status` event -- fold must read this exact shape to count the flow done.
    _patch_common(monkeypatch)
    run_dir = tmp_path / "run"
    _write_events(run_dir, [
        {"ts": "2026-09-23T10:00:00.000Z", "id": "e1", "type": "run", "mode": "quick",
         "flows_total": 1},
        {"ts": "2026-09-23T10:00:01.000Z", "id": "e2", "type": "step",
         "surface_id": "webapp", "flow_id": "w01", "step": "flow-begin"},
        {"ts": "2026-09-23T10:00:02.000Z", "id": "e3", "type": "step",
         "surface_id": "webapp", "flow_id": "w01", "step": "flow-end", "status": "ok"},
    ])
    body = fold(tmp_path, run_dir, _FakeCfg())
    assert body["run"]["flows_done"] == 1


def test_ledger_findings_pass_through_with_canonical_field_names(tmp_path, monkeypatch):
    entry = _Entry(id="f_a1b2", sev="P1", rule="contrast", surface_id="web-app",
                    flow_id="checkout", text="Submit button fails WCAG AA", state="open")
    _patch_common(monkeypatch, findings=[entry])
    run_dir = tmp_path / "run"
    _write_events(run_dir, [
        {"ts": "2026-09-23T10:00:00.000Z", "id": "e1", "type": "run", "mode": "goal", "surfaces": []},
    ])
    body = fold(tmp_path, run_dir, _FakeCfg())
    assert body["findings"][0]["rule"] == "contrast"
    assert body["findings"][0]["text"] == "Submit button fails WCAG AA"
    assert body["badge"]["counts"]["P1"] == 1


def test_repeat_finding_matching_a_ledger_fingerprint_is_counted_once(tmp_path, monkeypatch):
    # R12 run 2: a finding the ledger already holds (id from its first run) re-appears as a live
    # event with a fresh id; the badge and the report must count it once, by fingerprint.
    from flow_review.ledger import fingerprint
    fp = fingerprint("w01", "contrast.aa", "/", "css:#muted")
    _patch_common(monkeypatch, findings=[_Entry(
        id="first-run-id", fingerprint=fp, flow_id="w01", rule="contrast.aa", route="/",
        locator="css:#muted", sev="P1", last_run="run")])
    run_dir = tmp_path / "run"
    _write_events(run_dir, [
        {"ts": "2026-09-23T10:00:00.000Z", "id": "fresh-id", "type": "finding",
         "surface_id": "web", "flow_id": "w01", "rule": "contrast.aa", "route": "/",
         "locator": "css:#muted", "sev": "P1", "text": "low contrast"},
        {"ts": "2026-09-23T10:00:01.000Z", "id": "e2", "type": "run", "state": "done"},
    ])
    body = fold(tmp_path, run_dir, _FakeCfg())
    assert body["badge"]["total"] == 1
    report_ids = [f["id"] for group in body["report"].values() if isinstance(group, list)
                  for f in group if isinstance(f, dict)]
    assert report_ids.count("fresh-id") == 0
