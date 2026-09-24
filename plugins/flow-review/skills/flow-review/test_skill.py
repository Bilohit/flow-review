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


def test_skill_names_every_reference_it_relies_on():
    text = _text()
    for name in (
        "setup.md", "goals.md", "testing.md", "evidence.md", "stuck.md", "validation.md",
        "lenses/ui.md",
    ):
        assert name in text, f"SKILL.md never points at {name}"


def test_skill_never_calls_ledger_or_manifest_as_python():
    text = _text()
    assert not re.search(r"`(ledger|manifest)\.\w+\(", text)


def test_skill_never_mentions_a_consensus_vote():
    text = _text()
    for banned in ("2 or more lenses agree", "consensus", "arbitration pass"):
        assert banned.lower() not in text.lower(), f"SKILL.md still references {banned!r}"


def test_skill_never_fixes_only_logs():
    text = _text()
    assert "never edits product code" in text or "never fixes" in text


def test_skill_never_calls_validate_or_budget_as_python():
    text = _text()
    assert not re.search(r"`(validate|budget)\.\w+\(", text)
    assert "catch" not in text.lower() or "ValueError" not in text
