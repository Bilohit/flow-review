"""The append-only event writer every tester and the engine itself use (A-4 / audit H8).

Every line is built with json.dumps and nothing else -- the v1 `printf "$TEXT"` idiom this
replaces was shell-injectable the moment `text` contained a double quote, and interpolating a
finding's own words into a shell string is exactly the kind of value that will eventually
contain one. This module is the only writer; the CLI subcommand is the only caller a tester
needs, so no script ever hand-builds a JSON string again.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

REDACTED = "[redacted]"

_secrets: set[str] = set()


def register_secret(value: str) -> None:
    if value:
        _secrets.add(value)


def clear_secrets() -> None:
    _secrets.clear()


def now_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _redact_str(text: str) -> str:
    if not _secrets:
        return text
    for secret in sorted(_secrets, key=len, reverse=True):
        if secret in text:
            text = text.replace(secret, REDACTED)
    return text


def redact(value):
    if isinstance(value, str):
        return _redact_str(value)
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def append(run_dir: Path, event: dict) -> dict:
    out = dict(event)
    out.setdefault("ts", now_iso())
    if out.get("type") == "finding" and "id" not in out:
        out["id"] = uuid.uuid4().hex
    out = redact(out)

    run_dir = Path(run_dir)
    line = json.dumps(out, ensure_ascii=True)
    with (run_dir / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return out
