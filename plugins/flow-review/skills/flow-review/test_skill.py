from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKILL = ROOT / "SKILL.md"
SETUP = ROOT / "references" / "setup.md"


def test_skill_has_valid_frontmatter_with_name_and_description():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    front = text.split("---", 2)[1]
    assert re.search(r"^name:\s*flow-review\s*$", front, re.M)
    assert re.search(r"^description:\s*\S", front, re.M)


def test_skill_names_every_reference_it_relies_on():
    text = SKILL.read_text(encoding="utf-8")
    for name in ("setup.md", "surfaces.md", "testing.md", "evidence.md", "stuck.md"):
        assert name in text, f"SKILL.md never points at {name}"


def test_skill_declares_both_phases_and_how_it_chooses():
    text = SKILL.read_text(encoding="utf-8")
    assert ".flow-review/config.json" in text
    assert "--reconfigure" in text


def test_setup_recommends_audit_and_prove_and_offers_preset():
    text = SETUP.read_text(encoding="utf-8")
    assert "preset" in text.lower()
    assert "audit" in text.lower()
    assert "recommend" in text.lower()


def test_setup_handles_zero_candidates_from_audit():
    """`fr.audit.detect` returns an empty list for any codebase that does not declare its entry
    point in a form the three detectors read -- Go, Rust, Java, Ruby, .NET, PHP, Elixir, and more.
    Without an explicit passage for that case, a user on one of those stacks sees an empty list
    printed into a script that assumes candidates exist, concludes the tool is broken or not for
    them, and never learns the interview is how their surfaces get configured -- neither
    impression is recoverable after the fact. This guards the passage that heads that off.
    """
    text = SETUP.read_text(encoding="utf-8")
    assert re.search(r"nothing (was|is) detected", text, re.I)
    assert re.search(r"runnable entry point", text, re.I)
    assert re.search(r"interview", text, re.I)


def test_no_setup_detail_is_hardcoded():
    """A driver's port or command belongs in a project's own config, never in the skill.

    Hardcoding one project's debugging port or device command is how a generic tool quietly
    becomes usable by exactly one project again.
    """
    for path in (SKILL, SETUP):
        text = path.read_text(encoding="utf-8")
        for needle in ("9222", "adb devices"):
            assert needle not in text, f"{path} hardcodes {needle}"


def test_never_fix_only_log_survived():
    text = SKILL.read_text(encoding="utf-8")
    assert "never edits product code" in text or "never fixes" in text


def test_skill_names_all_three_lens_files():
    # Critical 1: dispatch names ui.md but silently dropped cli.md and api.md, so a cli/api
    # tester never learned those rubrics exist. All three must be named in the run procedure.
    text = SKILL.read_text(encoding="utf-8")
    for name in ("lenses/ui.md", "lenses/cli.md", "lenses/api.md"):
        assert name in text, f"SKILL.md never points at {name}"


def test_skill_names_manifest_write_back():
    text = SKILL.read_text(encoding="utf-8")
    assert "fr.manifest.apply_learnings" in text
    assert "flows_hash" in text


# --- Contract 1: prove.py returns a four-value outcome, not a bool -----------------------


def test_setup_states_running_ready_counts_as_proven_success():
    text = SETUP.read_text(encoding="utf-8")
    assert "RUNNING_READY" in text
    # The specific fact that must survive: a dev server that never exits is the SUCCESS case,
    # not a failure to observe an exit.
    assert re.search(r"never exits|does not exit|no exit", text, re.I)
    assert re.search(r"(is|counts as|treated as)\s+proven", text, re.I)


def test_setup_states_not_proven_means_ask_for_readiness_command():
    text = SETUP.read_text(encoding="utf-8")
    assert "NOT_PROVEN" in text
    # Must state the specific recovery: ask the user for a readiness command and retry --
    # never silently record a failure.
    assert re.search(r"ask\b.{0,60}(readiness|ready)\b", text, re.I | re.S)


def test_setup_states_teardown_failure_is_reported_to_user():
    text = SETUP.read_text(encoding="utf-8")
    assert "teardown_ok" in text
    assert re.search(r"teardown_ok.{0,120}(false|report|user)", text, re.I | re.S)


# --- Contract 2: origin provenance stamp gates drift detection ---------------------------


def test_setup_states_origin_audited_stamp_and_who_gets_it():
    text = SETUP.read_text(encoding="utf-8")
    assert re.search(r'origin["\']?\s*[:=]\s*["\']?audited', text, re.I)
    # Must draw the line: a hand-typed surface does NOT get the stamp.
    assert re.search(r"hand[- ]?(added|typed)", text, re.I)


# --- Contract 3: flows.md is append-only; flows_hash is an ownership token ---------------


def test_setup_states_flows_manifest_append_only_with_hash():
    text = SETUP.read_text(encoding="utf-8")
    assert "flows_hash" in text
    assert re.search(r"append-only|never (truncat|rewrit)e", text, re.I)
    # The "learned nothing" case must be named explicitly, or the rule reads as decorative.
    assert re.search(r"learned nothing", text, re.I)


# --- Contract 4: a library surface gets QA and no critique, stated in words --------------


def test_setup_states_library_surface_gets_qa_and_no_critique():
    text = SETUP.read_text(encoding="utf-8")
    assert re.search(r"library.{0,200}no critique", text, re.I | re.S) or re.search(
        r"no critique.{0,200}library", text, re.I | re.S
    )
    assert re.search(r"has_critique", text)
