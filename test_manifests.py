"""The manifests are load-bearing: a malformed one makes the plugin uninstallable
and the failure surfaces to a stranger, not to us."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def test_marketplace_is_valid_json_and_lists_flow_review():
    data = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert data["name"] == "flow-review"
    names = [p["name"] for p in data["plugins"]]
    assert "flow-review" in names


def test_every_listed_plugin_has_a_manifest_at_its_source():
    data = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    for entry in data["plugins"]:
        manifest = ROOT / entry["source"].lstrip("./") / ".claude-plugin" / "plugin.json"
        assert manifest.is_file(), f"{entry['name']} has no plugin.json at {manifest}"
        assert json.loads(manifest.read_text(encoding="utf-8"))["name"] == entry["name"]


def test_no_emoji_in_manifests():
    for path in ROOT.rglob(".claude-plugin/*.json"):
        text = path.read_text(encoding="utf-8")
        assert all(ord(ch) < 0x2190 for ch in text), f"non-ascii symbol in {path}"
