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
import platform
import re
from dataclasses import dataclass, field
from pathlib import Path

EVIDENCE_FORMAT = "{path}:{line} -> {snippet}"
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
    options: dict = field(default_factory=dict)


def _evidence(path: Path, root: Path, line: int | None, snippet: str) -> str:
    rel = path.relative_to(root).as_posix()
    if line is None:
        return EVIDENCE_FORMAT_NO_LINE.format(path=rel)
    return EVIDENCE_FORMAT.format(path=rel, line=line, snippet=snippet.strip())


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
        command = str(scripts.get(script_name, "")).strip()
        # a native/mobile dev server is not a web surface (B1)
        if command.startswith(("tauri dev", "react-native start")) or (
                command.startswith("expo start") and "--web" not in command):
            continue
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


# py3.10 floor: no tomllib. `name` inside [package], before the next `[table]` header line.
_CARGO_PACKAGE_NAME = re.compile(r'^\[\s*package\s*\][ \t]*(?:#.*)?$(?:(?!^\s*\[).)*?'
                                 r'^\s*name\s*=\s*["\']([^"\']+)["\']',
                                 re.MULTILINE | re.DOTALL)


def _cargo_package_name(path: Path) -> str | None:
    if not path.is_file():
        return None
    match = _CARGO_PACKAGE_NAME.search(path.read_text(encoding="utf-8", errors="replace"))
    return match.group(1) if match else None


def _from_tauri(root: Path) -> list[Candidate]:
    src_tauri = root / "src-tauri"
    if not src_tauri.is_dir():
        return []
    conf_path = src_tauri / "tauri.conf.json"
    dev_url = None
    product_name = "app"
    main_binary_name = None
    if conf_path.is_file():
        try:
            conf = json.loads(conf_path.read_text(encoding="utf-8"))
        except ValueError:
            conf = {}
        dev_url = conf.get("build", {}).get("devUrl")
        product_name = conf.get("productName", product_name)
        main_binary_name = conf.get("mainBinaryName")
    # Tauri v2 names the exe after mainBinaryName, else the Cargo [package] name
    binary_name = (main_binary_name or _cargo_package_name(src_tauri / "Cargo.toml")
                   or product_name)
    if dev_url:
        native = "webview2" if platform.system() == "Windows" else "pending"
        options = {"native": native, "dev_url": dev_url,
                   "binary": f"src-tauri/target/release/{binary_name}.exe"}
        driver = "tauri"
    else:
        options = {}  # a pending driver takes no options (config._validate_options)
        driver = "pending"  # no dev server configured yet -- nothing runnable to point at
    evidence = _evidence(conf_path, root, None, "") if conf_path.is_file() else _evidence(src_tauri, root, None, "")
    return [Candidate(name="desktop", kind="ui", driver=driver, launch="", evidence=evidence, options=options)]


# `applicationId` wins over `namespace`; both `x "id"` (groovy) and `x = "id"` (kts) forms.
_GRADLE_ID = re.compile(r"""^\s*(applicationId|namespace)\s*=?\s*["']([^"']+)["']""", re.MULTILINE)
_GRADLE_FILES = ("android/app/build.gradle", "android/app/build.gradle.kts",
                 "app/build.gradle", "app/build.gradle.kts")
_METRO_URL = "http://127.0.0.1:8081"


def _gradle_app(root: Path) -> tuple[Path | None, str | None]:
    for rel in _GRADLE_FILES:
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if not rel.startswith("android/") and "com.android.application" not in text:
            continue
        ids = dict(_GRADLE_ID.findall(text))
        return path, ids.get("applicationId") or ids.get("namespace")
    return None, None


def _from_android(root: Path) -> list[Candidate]:
    gradle, gradle_id = _gradle_app(root)
    expo, expo_path = None, None
    app_json = root / "app.json"
    if app_json.is_file():
        try:
            expo = json.loads(app_json.read_text(encoding="utf-8")).get("expo")
        except (ValueError, AttributeError):
            expo = None
        if expo is not None:
            expo_path = app_json
            expo = expo if isinstance(expo, dict) else {}
    if expo is None:
        # ponytail: app.config.js/ts is code, never evaluated -- no static id, so no Expo Go fallback either
        expo_path = next((p for p in (root / "app.config.js", root / "app.config.ts") if p.is_file()), None)
        expo = {} if expo_path else None
    if gradle is None and expo is None:
        return []
    try:
        pkg = json.loads((root / "package.json").read_text(encoding="utf-8"))
        deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
    except (OSError, ValueError, AttributeError):
        deps = {}
    app_id = gradle_id or (expo or {}).get("android", {}).get("package")
    if not app_id and expo_path == app_json and not (root / "android").is_dir() and "expo-dev-client" not in deps:
        app_id = "host.exp.exponent"  # Expo Go hosts the project
    if expo is not None:
        start_cmd = "npx expo start --dev-client" if "expo-dev-client" in deps else "npx expo start"
    elif "react-native" in deps:
        start_cmd = "npx react-native start"
    else:
        start_cmd = ""
    scheme = (expo or {}).get("scheme")
    if isinstance(scheme, list):
        scheme = next((x for x in scheme if "." not in x), None)
    evidence = _evidence(gradle or expo_path, root, None, "")
    if not app_id:
        return [Candidate(name="mobile", kind="ui", driver="pending", launch="",
                          evidence=f"{evidence}; set options.app_id")]
    options = {"app_id": app_id, "start_cmd": start_cmd, "metro_url": _METRO_URL if start_cmd else "",
               "scheme": scheme or ""}
    options = {k: v for k, v in options.items() if v}
    return [Candidate(name="mobile", kind="ui", driver="adb", launch="", evidence=evidence, options=options)]


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
    found.extend(_from_android(root))
    found.extend(_from_electron(root))
    return found
