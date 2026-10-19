"""Export a recorded action log as a Maestro flow (A-84). Export only: replay reads the JSON log.
Never emits anything that wipes app data (clearState, clearKeychain, killApp, a bare `stopApp: true`, ...);
launchApp is always `stopApp: false` so a run never force-stops the app."""
from __future__ import annotations

import json
import re

_KEYS = {"Enter": "Enter", "Back": "back"}
_LAUNCH = ["- launchApp:", "    stopApp: false"]
_REGEX_META = re.compile(r"([\\.*+?^${}()|\[\]])")


def _rx(value: str) -> str:
    """tapOn text/id are regexes in Maestro: match the recorded string literally."""
    return json.dumps(_REGEX_META.sub(r"\\\1", value))


def _locator(locator: dict | None) -> list[str] | None:
    locator = locator or {}
    if locator.get("testid"):
        return [f"id: {_rx(locator['testid'])}"]
    text = locator.get("name") or locator.get("text")
    if text:
        return [f"text: {_rx(text)}"]
    return None  # css (or empty): no Maestro equivalent


def _tap(locator: dict | None) -> list[str]:
    fields = _locator(locator)
    if fields is None:
        return ["# unsupported locator"]
    return ["- tapOn:", *(f"    {f}" for f in fields)]


def to_maestro(log: dict, app_id: str, scheme: str | None = None) -> str:
    lines = [f"appId: {json.dumps(app_id)}", "---", *_LAUNCH]
    for index, step in enumerate(log["steps"]):
        action = step["action"]
        if action == "click":
            lines += _tap(step.get("locator"))
        elif action == "fill":
            tap = _tap(step.get("locator"))
            lines += tap
            if tap[0].startswith("#"):
                continue
            locator = step.get("locator") or {}
            if step.get("from_env"):
                value = "${%s}" % step["from_env"]
            elif locator.get("secret"):
                value = "${FLOW_REVIEW_SECRET_%d}" % index  # the recorded value is redacted
            else:
                value = step.get("value") or ""
            lines.append(f"- inputText: {json.dumps(value)}")
        elif action == "press":
            key = _KEYS.get(step.get("value"))
            lines.append(f"- pressKey: {json.dumps(key)}" if key else "# unsupported key")
        elif action == "goto":
            path = step.get("url") or "/"
            if path in ("/", ""):
                lines += _LAUNCH
            elif scheme:
                link = f"{scheme}://{path.lstrip('/')}"
                lines.append(f"- openLink: {json.dumps(link)}")
            else:
                lines.append("# unsupported goto (no scheme)")
        # assert_url: no Maestro equivalent, skipped
    return "\n".join(lines) + "\n"
