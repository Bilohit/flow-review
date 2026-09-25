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

# A-26: never register a value shorter than this floor, so a 1-3 char "secret" doesn't blank
# that substring out of every event ever written. The single constant every caller shares
# (drive.fill, envsetup.load_dotenv/resolve_env, actionlog.record_step) -- none of them guard
# length themselves, so register_secret enforces it by silently skipping short values rather
# than raising (a short fill value must not hard-fail the action that produced it).
MIN_SECRET_LEN = 4

_secrets: set[str] = set()


def register_secret(value: str) -> None:
    if not value or len(value) < MIN_SECRET_LEN:
        return
    _secrets.add(value)


def clear_secrets() -> None:
    _secrets.clear()


def now_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def new_run_id() -> str:
    """Windows directory names cannot contain ':'; every run-dir creator uses this id."""
    return now_iso().replace(":", "-")


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
    # A4/A-44 row 5: concurrent same-millisecond appends on Windows are not lock-guarded;
    # accepted per spec (single-writer-per-run in practice). Revisit if multi-process writers
    # to one run dir become real.
    with (run_dir / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return out
