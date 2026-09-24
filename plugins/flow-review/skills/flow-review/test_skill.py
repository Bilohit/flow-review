from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILL = ROOT / "SKILL.md"


def _text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_skill_has_valid_frontmatter_with_name_and_description():
    text = _text()
    assert text.startswith("---\n")
    front = text.split("---", 2)[1]
    assert re.search(r"^name:\s*flow-review\s*$", front, re.M)
    assert re.search(r"^description:\s*\S", front, re.M)


def test_skill_declares_both_phases_and_how_it_chooses():
    text = _text()
    assert ".flow-review/config.json" in text
    assert "--reconfigure" in text


def test_skill_names_every_run_mode():
    text = _text()
    for mode in ("goal", "auto", "full", "quick"):
        assert re.search(rf"\b{mode}\b", text), f"SKILL.md never names the {mode!r} mode"


def test_skill_names_every_reference_it_relies_on():
    text = _text()
    for name in (
        "setup.md", "goals.md", "testing.md", "evidence.md", "stuck.md", "validation.md",
        "lenses/ui.md",
    ):
        assert name in text, f"SKILL.md never points at {name}"


def test_skill_names_the_plan_command_for_the_go_gate():
    text = _text()
    assert "flow-review plan" in text
    assert "--mode" in text


def test_skill_launches_serve_and_prints_the_url():
    text = _text()
    assert "flow-review serve" in text
    assert re.search(r"print.{0,60}(url|link|address)", text, re.I)


def test_skill_starts_drive_per_web_surface_before_dispatching_explorers():
    text = _text()
    assert "flow-review drive start" in text
    assert "--surface" in text.split("flow-review drive start", 1)[1][:120]


def test_skill_stops_drive_at_run_end():
    text = _text()
    assert "flow-review drive stop" in text


def test_skill_checks_budget_before_every_dispatch_with_surface():
    text = _text()
    assert "flow-review budget check" in text
    assert "--next" in text and "--surface" in text
    assert re.search(r"before every dispatch|before each dispatch|before dispatching", text, re.I)


def test_skill_logs_usage_via_the_usage_event():
    text = _text()
    assert re.search(r"--type usage", text)
    assert "record_usage" in text or "budget.record_usage" in text


def test_skill_resolves_model_via_the_model_command():
    text = _text()
    assert "flow-review model" in text


def test_skill_names_manifest_apply_learnings_explicitly():
    text = _text()
    assert "flow-review manifest apply-learnings" in text


def test_skill_uses_ledger_cli_verbs_never_python_calls():
    text = _text()
    for cmd in ("flow-review ledger reconcile --run", "flow-review ledger suppressions --rule",
                "flow-review ledger alias-candidates", "flow-review ledger record-miss"):
        assert cmd in text, cmd
    assert not re.search(r"`(ledger|manifest)\.\w+\(", text)


def test_skill_states_record_is_opt_in():
    text = _text()
    assert re.search(r"record.{0,80}(opt-in|off by default)", text, re.I | re.S)


def test_skill_states_no_interview_after_go():
    text = _text()
    assert re.search(r"no (further )?(question|interview).{0,80}after (the )?go", text, re.I | re.S)


def test_skill_states_one_multiselect_destructive_question_in_every_mode():
    text = _text()
    assert re.search(r"multi-select", text, re.I)
    assert re.search(r"persistent", text, re.I)
    assert re.search(r"quick", text, re.I)
    assert re.search(r"default.{0,10}no", text, re.I)


def test_skill_states_missing_creds_offers_to_save_to_env_file():
    text = _text()
    assert ".flow-review/.env" in text
    assert re.search(r"offer.{0,40}save", text, re.I)


def test_skill_names_all_six_agents():
    text = _text()
    for role in (
        "fr-explorer", "fr-cold-eyes", "fr-lens", "fr-replay-repair", "fr-triage", "fr-verifier",
    ):
        assert role in text, f"SKILL.md never dispatches {role}"


def test_skill_never_mentions_a_consensus_vote():
    text = _text()
    for banned in ("2 or more lenses agree", "consensus", "arbitration pass"):
        assert banned.lower() not in text.lower(), f"SKILL.md still references {banned!r}"


def test_skill_never_fixes_only_logs():
    text = _text()
    assert "never edits product code" in text or "never fixes" in text


def test_skill_report_names_the_hybrid_sections():
    text = _text()
    for phrase in ("needs-attention", "goal card", "opinion", "refuted", "not-exercised"):
        assert phrase.lower() in text.lower(), f"SKILL.md report section missing {phrase!r}"


def test_skill_uses_validate_and_budget_cli_verbs_never_python_calls():
    text = _text()
    assert "flow-review validate resolve --run" in text
    assert "flow-review budget fold --run" in text
    assert not re.search(r"`(validate|budget)\.\w+\(", text)
    assert "catch" not in text.lower() or "ValueError" not in text
