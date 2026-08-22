"""Propose surfaces from what the repository actually contains.

This module PROPOSES and never PROVES. Nothing here launches anything -- fr.prove owns that,
and the split is what lets the drift check reuse detection without re-running launches.

Every candidate carries the file it came from, and a line when the finding is one line rather
than a whole file, because the interview asks a stranger to confirm these and a stranger
cannot audit a summary.

A candidate exists only where the repository itself declares a runnable entry point in
machine-readable form -- today that means an npm `dev`/`start`/`serve` script, a
`pyproject.toml` `[project.scripts]` entry, or an OpenAPI/Swagger document. That is the whole
extent of what this module detects: a Go, Rust, Java, Ruby, .NET, PHP or Elixir project has no
such declaration in a form this reads, so `detect()` returns nothing for it, and that is a
boundary, not an oversight -- inferring a launch command from a convention (`cargo run`) or a
`Makefile` target that might be a build, a test, or a deploy is exactly the guessed citation
this module exists to refuse. Anything outside this extent is configured through the setup
interview instead (`references/setup.md` section 1), never guessed here.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EVIDENCE_FORMAT = "{path}:{line} -> {snippet}"
# A whole-file finding (a file's mere existence) has no line to cite; forcing one onto it is
# what invented a fake needle in the first place, so this shape is deliberately not "path:line".
EVIDENCE_FORMAT_NO_LINE = "{path} (file present)"

_DEV_SCRIPTS = ("dev", "start", "serve")
_SCRIPTS_KEY = re.compile(r'"scripts"\s*:')
_OPENAPI_NAMES = ("openapi.yaml", "openapi.yml", "openapi.json", "swagger.yaml", "swagger.json")


@dataclass
class Candidate:
    name: str
    kind: str
    driver: str
    launch: str
    evidence: str


def _evidence(path: Path, root: Path, line: int | None, snippet: str) -> str:
    # Callers already know where their finding came from -- this only formats it, it never
    # searches for it. A search re-derives a location that can drift from the real one.
    rel = path.relative_to(root).as_posix()
    if line is None:
        return EVIDENCE_FORMAT_NO_LINE.format(path=rel)
    return EVIDENCE_FORMAT.format(path=rel, line=line, snippet=snippet.strip())


def _from_package_json(root: Path) -> list[Candidate]:
    path = root / "package.json"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except ValueError:
        return []
    scripts = data.get("scripts") or {}
    lines = text.splitlines()
    # Start looking at the "scripts" key, the way _from_pyproject starts at its table header.
    # Quoting the key already rules out "devDependencies", but an unrelated object earlier in
    # the file may hold a literal "dev" key of its own, and citing that is the same wrong-line
    # bug in a narrower disguise.
    first = next((i for i, line in enumerate(lines) if _SCRIPTS_KEY.search(line)), 0)
    for name in _DEV_SCRIPTS:
        if name in scripts:
            key = re.compile(r'"%s"\s*:' % re.escape(name))
            number, snippet = next(
                ((i + 1, line) for i, line in enumerate(lines[first:], first) if key.search(line)),
                (None, ""),
            )
            # json.loads found the script, so the candidate is real even when the raw text will
            # not yield a line for it. Cite the file rather than dropping the surface.
            return [Candidate(
                name="web",
                kind="ui",
                driver="cdp",
                launch=f"npm run {name}",
                evidence=_evidence(path, root, number, snippet),
            )]
    return []


def _from_pyproject(root: Path) -> list[Candidate]:
    path = root / "pyproject.toml"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    if "[project.scripts]" not in text:
        return []
    out = []
    header, rest = text.split("[project.scripts]", 1)
    header_lines = header.count("\n")
    section = rest.split("\n[", 1)[0]
    section_lines = section.splitlines()
    for match in re.finditer(r"^\s*([A-Za-z0-9_.-]+)\s*=", section, re.M):
        command = match.group(1)
        # The regex already ran against `section` at a known offset -- recover the absolute
        # line from that offset instead of searching the file again for `command`, which can
        # also appear on the `[project]` name line above this table. Count from group(1),
        # not the whole match: `\s*` matches newlines too, so it can swallow the blank line
        # left by "[project.scripts]" itself and shift the whole-match start up by one line.
        offset = section.count("\n", 0, match.start(1))
        line_number = header_lines + 1 + offset
        out.append(Candidate(
            name=command,
            kind="cli",
            driver="shell",
            launch=command,
            evidence=_evidence(path, root, line_number, section_lines[offset]),
        ))
    return out


def _from_openapi(root: Path) -> list[Candidate]:
    for name in _OPENAPI_NAMES:
        path = root / name
        if not path.is_file():
            continue
        return [Candidate(
            name="api",
            kind="api",
            driver="http",
            launch="",
            evidence=_evidence(path, root, None, ""),
        )]
    return []


def detect(root: Path) -> list[Candidate]:
    root = Path(root)
    found: list[Candidate] = []
    for finder in (_from_package_json, _from_pyproject, _from_openapi):
        found.extend(finder(root))
    return found
