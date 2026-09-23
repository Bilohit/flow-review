"""Propose surfaces from what the repository actually contains (A-14).

This module PROPOSES and never PROVES -- fr.prove owns launching. A pending-driver candidate
(Tauri/Expo/Electron) proposes only that a surface EXISTS; M1 has no driver for it, so its
launch is always blank and setup shows it as detected-but-not-yet-testable.

A candidate exists only where the repository itself declares a runnable entry point in
machine-readable form. Inferring a launch command from a convention or a Makefile target is the
guessed citation this module refuses; workspace members and Poetry's own scripts table are
still machine-readable declarations, not conventions, so they are in scope the same way the
single-package case always was.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

EVIDENCE_FORMAT = "{path}:{line} -> {snippet}"
EVIDENCE_FORMAT_NO_LINE = "{path} (file present)"

_DEV_SCRIPTS = ("dev", "start", "serve")
_SCRIPTS_KEY = re.compile(r'"scripts"\s*:')
_OPENAPI_NAMES = ("openapi.yaml", "openapi.yml", "openapi.json", "swagger.yaml", "swagger.json")

WORKSPACE_FRAMEWORK_PORTS = {"vite": 5173, "next": 3000, "react-scripts": 3000}


@dataclass
class Candidate:
    name: str
    kind: str
    driver: str
    launch: str
    evidence: str
    default_port: int | None = None


def _evidence(path: Path, root: Path, line: int | None, snippet: str) -> str:
    rel = path.relative_to(root).as_posix()
    if line is None:
        return EVIDENCE_FORMAT_NO_LINE.format(path=rel)
    return EVIDENCE_FORMAT.format(path=rel, line=line, snippet=snippet.strip())


def _default_port(data: dict) -> int | None:
    deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
    for framework, port in WORKSPACE_FRAMEWORK_PORTS.items():
        if framework in deps:
            return port
    return None


def _from_package_json(pkg_dir: Path, evidence_root: Path, name: str = "web") -> list[Candidate]:
    path = pkg_dir / "package.json"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except ValueError:
        return []
    scripts = data.get("scripts") or {}
    lines = text.splitlines()
    first = next((i for i, line in enumerate(lines) if _SCRIPTS_KEY.search(line)), 0)
    for script_name in _DEV_SCRIPTS:
        if script_name in scripts:
            key = re.compile(r'"%s"\s*:' % re.escape(script_name))
            number, snippet = next(
                ((i + 1, line) for i, line in enumerate(lines[first:], first) if key.search(line)),
                (None, ""),
            )
            return [Candidate(
                name=name,
                kind="ui",
                driver="playwright",
                launch=f"npm run {script_name}",
                evidence=_evidence(path, evidence_root, number, snippet),
                default_port=_default_port(data),
            )]
    return []


def _workspace_globs(root: Path) -> list[str]:
    patterns: list[str] = []
    pkg = root / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except ValueError:
            data = {}
        workspaces = data.get("workspaces")
        if isinstance(workspaces, dict):
            workspaces = workspaces.get("packages")
        if isinstance(workspaces, list):
            patterns.extend(str(p) for p in workspaces)
    pnpm = root / "pnpm-workspace.yaml"
    if pnpm.is_file():
        for line in pnpm.read_text(encoding="utf-8").splitlines():
            stripped = line.strip().lstrip("-").strip().strip("'\"")
            if stripped and stripped != "packages:":
                patterns.append(stripped)
    return patterns


def _from_workspaces(root: Path) -> list[Candidate]:
    found: list[Candidate] = []
    for pattern in _workspace_globs(root):
        for member in sorted(root.glob(pattern)):
            if member.is_dir() and (member / "package.json").is_file():
                found.extend(_from_package_json(member, root, name=member.name))
    return found


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
        offset = section.count("\n", 0, match.start(1))
        line_number = header_lines + 1 + offset
        out.append(Candidate(
            name=command, kind="cli", driver="shell", launch=command,
            evidence=_evidence(path, root, line_number, section_lines[offset]),
        ))
    return out


def _from_poetry(root: Path, already: set[str]) -> list[Candidate]:
    path = root / "pyproject.toml"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    if "[tool.poetry.scripts]" not in text:
        return []
    out = []
    header, rest = text.split("[tool.poetry.scripts]", 1)
    header_lines = header.count("\n")
    section = rest.split("\n[", 1)[0]
    section_lines = section.splitlines()
    for match in re.finditer(r"^\s*([A-Za-z0-9_.-]+)\s*=", section, re.M):
        command = match.group(1)
        if command in already:
            continue
        offset = section.count("\n", 0, match.start(1))
        line_number = header_lines + 1 + offset
        out.append(Candidate(
            name=command, kind="cli", driver="shell", launch=command,
            evidence=_evidence(path, root, line_number, section_lines[offset]),
        ))
    return out


def _from_openapi(root: Path) -> list[Candidate]:
    for name in _OPENAPI_NAMES:
        path = root / name
        if not path.is_file():
            continue
        return [Candidate(name="api", kind="api", driver="http", launch="", evidence=_evidence(path, root, None, ""))]
    return []


def _from_tauri(root: Path) -> list[Candidate]:
    src_tauri = root / "src-tauri"
    if not src_tauri.is_dir():
        return []
    conf = src_tauri / "tauri.conf.json"
    evidence = _evidence(conf, root, None, "") if conf.is_file() else _evidence(src_tauri, root, None, "")
    return [Candidate(name="desktop", kind="ui", driver="pending", launch="", evidence=evidence)]


def _from_expo(root: Path) -> list[Candidate]:
    path = root / "app.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return []
    if "expo" not in data:
        return []
    return [Candidate(name="mobile", kind="ui", driver="pending", launch="", evidence=_evidence(path, root, None, ""))]


def _from_electron(root: Path) -> list[Candidate]:
    path = root / "package.json"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except ValueError:
        return []
    deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
    if "electron" not in deps:
        return []
    key = re.compile(r'"electron"\s*:')
    lines = text.splitlines()
    number, snippet = next(
        ((i + 1, line) for i, line in enumerate(lines) if key.search(line)), (None, ""),
    )
    evidence = _evidence(path, root, number, snippet) if number else _evidence(path, root, None, "")
    return [Candidate(name="desktop-electron", kind="ui", driver="pending", launch="", evidence=evidence)]


def detect(root: Path) -> list[Candidate]:
    root = Path(root)
    found: list[Candidate] = []
    found.extend(_from_package_json(root, root))
    found.extend(_from_workspaces(root))
    pyproject_found = _from_pyproject(root)
    found.extend(pyproject_found)
    found.extend(_from_poetry(root, already={c.name for c in pyproject_found}))
    found.extend(_from_openapi(root))
    found.extend(_from_tauri(root))
    found.extend(_from_expo(root))
    found.extend(_from_electron(root))
    return found
