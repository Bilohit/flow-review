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

import sys
from pathlib import Path

from fr import lenses

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REFS = ROOT / "references"

REQUIRED = [
    REFS / "surfaces.md", REFS / "testing.md", REFS / "evidence.md", REFS / "stuck.md",
    REFS / "lenses" / "ui.md", REFS / "lenses" / "cli.md", REFS / "lenses" / "api.md",
    ROOT / "templates" / "flows.md",
]

# Every shipped module and document, for the rules audit. A rule in a docstring is a rule, and a
# rule in the skill's own entry point is a rule -- an audit that covers only the files one task
# happened to add is an audit that shrinks as the package grows. Globbed rather than listed so a
# file added later is scanned without anyone remembering to add it here.
SCANNED = (
    REQUIRED
    + [ROOT / "SKILL.md"]
    + sorted((ROOT / "references").glob("*.md"))
    + sorted((ROOT / "fr").glob("*.py"))
    + sorted((ROOT / "dashboard").glob("*.py"))
)
SCANNED = sorted({path for path in SCANNED if path.is_file()})

# Every shipped production module -- never a test file, never __init__.py -- must reconfigure
# stdout to UTF-8 before it prints, because a Windows console mangles anything else. This is
# the file list for that one check, not the rules audit above: a test module has nothing to
# print in production and __init__.py never runs as a script, so neither carries the guard.
GUARD_SCANNED = sorted(
    p for p in (ROOT / "fr").glob("*.py")
    if p.name != "__init__.py" and not p.name.startswith("test_")
) + [ROOT / "dashboard" / "render.py"]

STDOUT_GUARD = (
    'if hasattr(sys.stdout, "reconfigure"):\n'
    '    sys.stdout.reconfigure(encoding="utf-8", errors="replace")'
)

MARKER = "BINDING -- "
EM_DASH_MARKER = "BINDING —"
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
    assert ">>" in text
    assert "BOM" in text


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


def test_every_production_module_guards_stdout_encoding():
    """dashboard/render.py is the one module that actually prints on every pass, and it is a
    CLI entry point invoked directly rather than imported -- exactly the module a missing guard
    would break first on a Windows console. Every other production module already carries this;
    this test is what stops a future one from shipping without it."""
    for path in GUARD_SCANNED:
        text = path.read_text(encoding="utf-8")
        assert STDOUT_GUARD in text, f"{path} is missing the stdout encoding guard"
