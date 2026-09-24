"""Docs<->CLI flag parity.

Every `flow-review <verb> ...` span in a doc names a real verb (plus nested sub-verb) and only
flags that verb's argparse subparser actually accepts. Docs drift from the CLI silently -- a
renamed flag still reads fine in prose -- so this walks argparse itself rather than trusting a
second, hand-maintained list of verbs and flags.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from flow_review.cli import build_parser
from flow_review.web.drive import build_drive_parser

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent.parent.parent.parent

DOC_FILES = [p for p in (
    [ROOT / "SKILL.md"]
    + sorted((ROOT / "references").rglob("*.md"))
    + sorted((ROOT.parent.parent / "agents").glob("*.md"))
    + [REPO_ROOT / "README.md"]
    + sorted((REPO_ROOT / "docs").glob("*.md"))
) if p.is_file()]

SPAN_RE = re.compile(r"`(flow-review [^`\n]*)`")
FLAG_RE = re.compile(r"--[A-Za-z][\w-]*")


def _subparser_choices(parser: argparse.ArgumentParser) -> dict | None:
    """The verb -> subparser map one level below `parser`, or None if it has no sub-verbs."""
    if parser._subparsers is None:
        return None
    for action in parser._subparsers._group_actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices
    return None


def _spans(text: str) -> list[tuple[int, str]]:
    """(1-based line number, span text) for every backtick span and fenced code line that
    starts with `flow-review `."""
    found = [(text[: m.start()].count("\n") + 1, m.group(1)) for m in SPAN_RE.finditer(text)]
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence and line.strip().startswith("flow-review "):
            found.append((lineno, line.strip()))
    return found


def _check(path: Path, top_choices: dict, drive_root: argparse.ArgumentParser):
    text = path.read_text(encoding="utf-8")
    for lineno, span in _spans(text):
        rest = span[len("flow-review "):].strip()
        tokens = rest.split()
        flags = FLAG_RE.findall(span)
        if not tokens:
            continue
        verb = tokens[0]
        if verb not in top_choices:
            assert not flags, f"{path}:{lineno}: unknown verb {verb!r} in {span!r}"
            continue
        parser = drive_root if verb == "drive" else top_choices[verb]
        idx = 1
        sub_choices = _subparser_choices(parser)
        while sub_choices and idx < len(tokens) and tokens[idx] in sub_choices:
            parser = sub_choices[tokens[idx]]
            idx += 1
            sub_choices = _subparser_choices(parser)
        valid = {opt for action in parser._actions for opt in action.option_strings}
        for flag in flags:
            assert flag in valid, (
                f"{path}:{lineno}: {flag!r} is not an option of "
                f"`flow-review {' '.join(tokens[:idx])}` in {span!r}"
            )


def test_every_flow_review_command_in_the_docs_matches_the_cli():
    top_choices = _subparser_choices(build_parser())
    drive_root = build_drive_parser()
    assert DOC_FILES, "no doc files found to scan"
    for path in DOC_FILES:
        _check(path, top_choices, drive_root)
