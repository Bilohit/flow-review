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


def test_engine_package_data_ships_every_dashboard_asset():
    import fnmatch
    import tomllib
    engine = ROOT / "plugins" / "flow-review" / "engine"
    cfg = tomllib.loads((engine / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = cfg["tool"]["setuptools"]["package-data"]["flow_review.dashboard"]
    dash = engine / "flow_review" / "dashboard"
    needed = [p for p in dash.rglob("*") if p.is_file() and p.suffix != ".py"
              and "__pycache__" not in p.parts and ".impeccable" not in p.parts]
    missing = [str(p.relative_to(dash)) for p in needed
               if not any(fnmatch.fnmatch(p.relative_to(dash).as_posix(), pat) for pat in patterns)]
    assert not missing, f"not packaged: {missing}"
    assert cfg["project"].get("readme"), "PyPI page would be blank"
