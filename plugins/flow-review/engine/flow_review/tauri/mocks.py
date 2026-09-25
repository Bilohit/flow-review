"""Invoke mocks for a Tauri surface (A-37). The engine only writes stubs it can discover from
the Rust source; a human or the setup agent fills plausible responses. An unfilled command
resolves to null at runtime and drive.py files a not-exercised status once per flow. A value
shaped exactly `{"$reject": msg}` makes invoke reject with msg, to exercise the error path."""
from __future__ import annotations

import json
import re
from pathlib import Path

_COMMAND_FN = re.compile(
    r"^[ \t]*#\[tauri::command\b[^\]]*\]\s*\n"
    r"(?:[ \t]*#\[[^\]]*\]\s*\n)*"
    r"[ \t]*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+(\w+)",
    re.MULTILINE,
)


def scan_commands(src_tauri: Path) -> list[str]:
    names: list[str] = []
    for rs_file in sorted(src_tauri.rglob("*.rs")):
        text = rs_file.read_text(encoding="utf-8")
        for match in _COMMAND_FN.finditer(text):
            name = match.group(1)
            if name not in names:
                names.append(name)
    return names


def write_stubs(path: Path, commands: list[str]) -> int:
    existing: dict = {}
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path} is not a JSON object of command -> mock") from exc
        if not isinstance(existing, dict):
            raise ValueError(f"{path} is not a JSON object of command -> mock")
    added = 0
    for command in commands:
        if command not in existing:
            existing[command] = None
            added += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, indent=2, sort_keys=True), encoding="utf-8")
    return added


def init_script(mocks: dict) -> str:
    payload = json.dumps(mocks)
    return (
        "window.__flowReviewMissingMocks = [];\n"
        "window.__TAURI_INTERNALS__ = {\n"
        f"  invoke: (cmd, args) => {{\n"
        f"    const mocks = {payload};\n"
        "    const has = Object.prototype.hasOwnProperty.call(mocks, cmd);\n"
        "    const value = has ? mocks[cmd] : null;\n"
        "    if (has && value === null) { window.__flowReviewMissingMocks.push(cmd); }\n"
        # {"$reject": msg} -> the command's Err path (a Result<_, E> backend failing), A-36
        "    if (value !== null && typeof value === 'object' && !Array.isArray(value)\n"
        "        && Object.keys(value).length === 1 && '$reject' in value) {\n"
        "      return Promise.reject(value['$reject']);\n"
        "    }\n"
        "    return Promise.resolve(value);\n"
        "  },\n"
        "  transformCallback: (callback) => callback,\n"
        "  convertFileSrc: (path) => path,\n"
        "};"
    )
