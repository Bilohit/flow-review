from __future__ import annotations

import json

from fr import config as cfgmod
from fr import drift


def _cfg(*surfaces):
    return cfgmod.Config(
        schema_version=cfgmod.SCHEMA_VERSION, generator_version="1.0.0",
        surfaces=list(surfaces), lens_sets={}, tester_agent="general-purpose",
        evidence_types=[], flows_hash="",
    )


def _web(launch="npm run dev"):
    return cfgmod.Surface(name="web", kind="ui", driver="cdp", launch=launch)


def test_no_drift_when_config_matches_the_repo(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}), encoding="utf-8")
    assert drift.detect_drift(_cfg(_web()), tmp_path) == []


def test_reports_a_changed_launch_command(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"start": "vite"}}), encoding="utf-8")
    messages = drift.detect_drift(_cfg(_web("npm run dev")), tmp_path)
    assert len(messages) == 1
    assert "web" in messages[0] and "launch command" in messages[0]


def test_reports_a_surface_the_repo_gained(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}), encoding="utf-8")
    (tmp_path / "openapi.yaml").write_text("openapi: 3.0.0\n", encoding="utf-8")
    messages = drift.detect_drift(_cfg(_web()), tmp_path)
    assert any("api" in m and "not in config" in m for m in messages)


def test_a_user_declined_surface_is_not_reported_twice(tmp_path):
    """A surface the user deliberately left out is recorded as declined, not re-nagged."""
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}), encoding="utf-8")
    (tmp_path / "openapi.yaml").write_text("openapi: 3.0.0\n", encoding="utf-8")
    cfg = _cfg(_web())
    cfg.lens_sets = {}
    declined = cfgmod.Surface(name="api", kind="api", driver="http", launch="",
                              provenance={"declined": "user"})
    cfg.surfaces.append(declined)
    messages = drift.detect_drift(cfg, tmp_path)
    assert not any("api" in m and "not in config" in m for m in messages)


def test_a_removed_detector_originated_surface_is_reported(tmp_path):
    """The dev script was deleted from the repo; a surface flow-review found on its own no
    longer has anything to point at, and the config keeps describing a repo that no longer
    exists until someone re-runs setup."""
    cfg = _cfg(cfgmod.Surface(
        name="web", kind="ui", driver="cdp", launch="npm run dev",
        provenance={drift.DETECTED_PROVENANCE_KEY: drift.DETECTED_PROVENANCE_VALUE},
    ))
    messages = drift.detect_drift(cfg, tmp_path)
    assert any("web" in m and "gone" in m and "reconfigure" in m for m in messages)


def test_a_hand_added_surface_with_no_match_is_never_reported(tmp_path):
    """A surface configured by hand (an adb device, a `custom` driver) has no detector
    provenance, so audit.detect never could have seen it -- its absence from `detected` proves
    nothing and must never be reported, on any run."""
    cfg = _cfg(cfgmod.Surface(name="device", kind="cli", driver="adb", launch="adb shell"))
    for _ in range(2):
        messages = drift.detect_drift(cfg, tmp_path)
        assert not any("device" in m for m in messages)
