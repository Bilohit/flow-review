import json
import re
from pathlib import Path

from flow_review import events

SCHEMA_VERSION = 1

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def _slug(value: str) -> str:
    """flow_id/surface_id come from `flow-begin --flow`/config, or over the unauthenticated
    drive socket -- used raw, a "../../x" id writes outside the run dir. Keep only
    [A-Za-z0-9._-], replace everything else (path separators included) with "-", and strip
    leading dots so the result can never be "." or start a ".." traversal segment."""
    slug = _UNSAFE_CHARS.sub("-", value).lstrip(".")
    return slug or "_"


def locator_key(locator: dict) -> str:
    if locator.get("role"):
        return f"role:{locator['role']}:{locator.get('name', '')}"
    if locator.get("testid"):
        return f"testid:{locator['testid']}"
    if locator.get("css"):
        return f"css:{locator['css']}"
    return "css:"


def new_log(surface_id: str, flow_id: str) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "surface_id": surface_id,
        "flow_id": flow_id,
        "recorded_at": events.now_iso(),
        "steps": [],
    }


def record_step(log: dict, action: str, locator: dict | None = None,
                value: str | None = None, url: str | None = None,
                checkpoint: str | None = None, from_env: str | None = None) -> dict:
    step: dict = {}
    if from_env is not None:
        # store only the env-var NAME; replay resolves it again. Never the value (spec 9, CP2 I3).
        value = None
        step["from_env"] = from_env
    if locator is not None and locator.get("secret") and value is not None:
        events.register_secret(value)
        value = events.REDACTED
    log["steps"].append({
        "action": action,
        "url": url,
        "locator": locator,
        "value": value,
        "checkpoint": checkpoint,
        **step,
    })
    return log


def save(log: dict, run_dir: Path, project_root: Path, record_enabled: bool) -> Path:
    surface_slug = _slug(log["surface_id"])
    flow_slug = _slug(log["flow_id"])
    if record_enabled:
        out = (project_root / ".flow-review" / "recordings"
               / surface_slug / f"{flow_slug}.json")
    else:
        out = run_dir / "repro" / f"{flow_slug}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
