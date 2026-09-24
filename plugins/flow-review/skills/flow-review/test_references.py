"""The markdown half and the Python half must not drift.

A lens named in fr/lenses.py but absent from its reference file is a lens the critique agent
was told to run and given no rubric for.

The binding-rule checker here is deliberately PART-aware rather than LINE-aware. An earlier
version counted physical lines and could not see the project's own rules: they sit indented
inside docstrings, and their third part is one sentence soft-wrapped across two lines. A rule
that is present and readable to a human was invisible to the checker written to count it.
Prose gets re-wrapped by every editor; a checker keyed on physical lines is keyed on the one
thing that changes freely.
"""
from __future__ import annotations

import re
from pathlib import Path

from flow_review import lenses

ROOT = Path(__file__).resolve().parent
REFS = ROOT / "references"

REQUIRED = [
    REFS / "surfaces.md", REFS / "testing.md", REFS / "evidence.md", REFS / "stuck.md",
    REFS / "goals.md", REFS / "validation.md",
    REFS / "lenses" / "ui.md", REFS / "lenses" / "cli.md", REFS / "lenses" / "api.md",
    ROOT / "templates" / "flows.md",
]

# Every shipped module and document, for the rules audit. A rule in a docstring is a rule, and a
# rule in the skill's own entry point is a rule -- an audit that covers only the files one task
# happened to add is an audit that shrinks as the package grows. Globbed rather than listed so a
# file added later is scanned without anyone remembering to add it here.
ENGINE = ROOT.parent.parent / "engine" / "flow_review"

ENGINE_SCANNED = sorted(
    p for p in ENGINE.rglob("*.py")
    if p.name != "__init__.py" and not p.name.startswith("test_")
)

SCANNED = (
    REQUIRED
    + [ROOT / "SKILL.md"]
    + sorted((ROOT / "references").glob("*.md"))
    + ENGINE_SCANNED
)
SCANNED = sorted({path for path in SCANNED if path.is_file()})

MARKER = "BINDING -- "
# Built from its codepoint rather than written as the glyph: this file sits inside
# the tree a house-style census scans, and a checker that has to skip its own source
# is an allowlist rather than a checker.
EM_DASH_MARKER = "BINDING " + chr(0x2014)
WHY = "why:"
# A rule that has not reached its pointer within this many lines has lost its shape.
WINDOW = 8
MIN_BODY_LINES = 2


def _lens_anchor(name: str) -> str:
    """The machine-readable declaration a rubric makes about a lens.

    Grepping the bare name would pass on prose that merely mentions it -- "the copy reads well"
    is not a rubric for the `copy` lens. The heading is the file declaring what it covers,
    which is a claim a document can make rather than one a substring search has to infer.
    """
    return f"### Lens -- `{name}`"


def _binding_rule_is_whole(lines: list[str], start: int) -> bool:
    """A rule runs from its marker through its `why:` pointer.

    Leading whitespace is allowed, so a rule may live indented in a docstring. Wrapping is
    allowed, so a long clause may span lines. A blank line ends the block, so a rule cannot
    silently absorb the paragraph after it.
    """
    for offset in range(1, WINDOW + 1):
        index = start + offset
        if index >= len(lines):
            return False
        line = lines[index].strip()
        if not line or line.startswith(MARKER):
            return False
        if line.startswith(WHY):
            return offset - 1 >= MIN_BODY_LINES
    return False


def _binding_rules(text: str) -> tuple[int, int]:
    lines = text.splitlines()
    declared = whole = 0
    for index, line in enumerate(lines):
        if line.strip().startswith(MARKER):
            declared += 1
            whole += 1 if _binding_rule_is_whole(lines, index) else 0
    return declared, whole


def test_every_reference_file_exists_and_is_not_a_stub():
    for path in REQUIRED:
        assert path.is_file(), f"missing {path}"
        assert len(path.read_text(encoding="utf-8")) > 400, f"{path} is a stub"


def test_every_lens_in_the_registry_declares_a_rubric_in_its_reference_file():
    for kind in ("ui", "cli", "api"):
        text = (REFS / "lenses" / f"{kind}.md").read_text(encoding="utf-8")
        for lens in lenses.for_kind(kind):
            anchor = _lens_anchor(lens.name)
            assert anchor in text, f"lenses/{kind}.md has no rubric declared as {anchor!r}"


def test_a_rubric_declares_no_lens_the_registry_does_not_have():
    """The contract runs both ways: a rubric for a lens nobody dispatches is dead prose."""
    for kind in ("ui", "cli", "api"):
        text = (REFS / "lenses" / f"{kind}.md").read_text(encoding="utf-8")
        declared = {
            line.split("`")[1]
            for line in text.splitlines()
            if line.startswith("### Lens -- `")
        }
        registered = {lens.name for lens in lenses.for_kind(kind)}
        assert declared == registered, (
            f"lenses/{kind}.md declares {sorted(declared - registered)} "
            f"and is missing {sorted(registered - declared)}"
        )


def test_no_emoji_in_any_reference_file():
    for path in REQUIRED:
        for ch in path.read_text(encoding="utf-8"):
            assert ord(ch) < 0x2190, f"non-ascii symbol {ch!r} in {path}"


def test_no_reference_file_carries_a_byte_order_mark():
    """A BOM survives a copy and breaks the first parser that meets it."""
    for path in REQUIRED:
        assert not path.read_bytes().startswith(b"\xef\xbb\xbf"), f"BOM in {path}"


def test_evidence_file_keeps_the_append_idiom_rules():
    text = (REFS / "evidence.md").read_text(encoding="utf-8")
    assert "events.jsonl" in text
    assert "flow-review event" in text
    assert "printf" not in text


def test_binding_rules_carry_all_four_parts():
    """A binding rule states the imperative, the exception it forecloses, the failure that
    earned it, and a why: pointer. Three parts is a rule someone will relitigate."""
    for path in SCANNED:
        declared, whole = _binding_rules(path.read_text(encoding="utf-8"))
        assert declared == whole, f"{path}: {declared - whole} binding rule(s) missing parts"


def test_the_codebase_actually_declares_binding_rules():
    """Guards the check above from passing because it found nothing to check."""
    total = sum(_binding_rules(p.read_text(encoding="utf-8"))[0] for p in SCANNED)
    assert total >= 3, f"only {total} binding rules found across {len(SCANNED)} files"


def test_no_em_dash_binding_marker_slipped_in():
    """One marker spelling, or half the rules go uncounted by every grep that checks them."""
    for path in SCANNED:
        assert EM_DASH_MARKER not in path.read_text(encoding="utf-8"), f"em-dash marker in {path}"


def test_no_module_reconfigures_stdout_at_import():
    """Only cli.main() may touch stdout encoding. Any other module doing it at import time
    means importing that module for its functions -- exactly what every test file in this
    suite does -- silently mutates the test runner's own stdout, which is the defect the
    previous per-module guard actually caused."""
    for path in ENGINE_SCANNED:
        if path.name == "cli.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert "sys.stdout.reconfigure" not in text, (
            f"{path} reconfigures stdout outside cli.main()"
        )


def test_cli_reconfigures_stdout_only_inside_main():
    text = (ENGINE / "cli.py").read_text(encoding="utf-8")
    assert "sys.stdout.reconfigure" in text
    before_main = text.split("def main(", 1)[0]
    assert "sys.stdout.reconfigure" not in before_main, (
        "the guard must live inside main(), not at module import time"
    )


def test_goals_reference_exists_and_is_required():
    assert (REFS / "goals.md") in REQUIRED


def test_goals_file_states_the_around_set_and_default_on():
    text = (REFS / "goals.md").read_text(encoding="utf-8")
    for phrase in ("unhappy path", "interruption", "alternate route", "variant"):
        assert phrase in text.lower()
    assert re.search(r"on by default", text, re.I)
    assert re.search(r"quick mode", text, re.I)


def test_goals_file_states_cold_eyes_then_docs_pass():
    text = (REFS / "goals.md").read_text(encoding="utf-8")
    assert re.search(r"pass 1", text, re.I)
    assert re.search(r"pass 2", text, re.I)
    assert re.search(r"no code|not read.{0,20}code|read no code", text, re.I)


def test_goals_file_uses_the_canonical_ledger_functions_for_discoverability():
    text = (REFS / "goals.md").read_text(encoding="utf-8")
    assert "record_miss" in text
    assert "missed_twice" in text
    assert re.search(r"\bP2\b", text)
    assert "P1" not in text.split("record_miss")[0].split("Hidden-feature")[-1]


def test_goals_file_states_path_ratio_metric():
    text = (REFS / "goals.md").read_text(encoding="utf-8")
    assert re.search(r"path.{0,10}ratio|shortest.{0,20}route", text, re.I)


def test_goals_file_states_the_safety_limits():
    text = (REFS / "goals.md").read_text(encoding="utf-8")
    for phrase in ("sandbox only", "test_inbox", "no-test-inbox", "payment-not-sandboxed",
                   "destructive-no-optin", "not-exercised"):
        assert phrase in text, phrase


def test_goals_file_names_the_drive_cli_and_secret_handling():
    text = (REFS / "goals.md").read_text(encoding="utf-8")
    assert "flow-review drive" in text
    assert "--from-env" in text


def test_goals_file_never_claims_the_explorer_writes_its_own_action_log_or_step_events():
    text = (REFS / "goals.md").read_text(encoding="utf-8")
    assert "events.append" not in text
    assert "flow-review event" not in text
    assert re.search(r"explorer.{0,60}(writes|emits|hand-writes).{0,40}(action log|step event)",
                      text, re.I) is None
