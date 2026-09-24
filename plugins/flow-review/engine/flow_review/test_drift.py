from __future__ import annotations

import json

from flow_review import config as cfgmod
from flow_review import drift


def _cfg(*surfaces):
    return cfgmod.Config(schema_version=cfgmod.SCHEMA_VERSION, generator_version="2.0.0",
                          surfaces=list(surfaces))


def _web(surface_id="web", name="Web", launch="npm run dev", **over):
    base = dict(id=surface_id, name=name, kind="ui", driver="playwright", launch=launch)
    base.update(over)
    return cfgmod.Surface(**base)


def test_no_drift_when_config_matches_the_repo(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}), encoding="utf-8")
    assert drift.detect_drift(_cfg(_web()), tmp_path) == []


def test_reports_a_changed_launch_command_naming_the_surface_by_id(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"start": "vite"}}), encoding="utf-8")
    messages = drift.detect_drift(_cfg(_web(surface_id="web", launch="npm run dev")), tmp_path)
    assert len(messages) == 1
    assert "web" in messages[0] and "launch command" in messages[0]


def test_reports_a_surface_the_repo_gained(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}), encoding="utf-8")
    (tmp_path / "openapi.yaml").write_text("openapi: 3.0.0\n", encoding="utf-8")
    messages = drift.detect_drift(_cfg(_web()), tmp_path)
    assert any("api" in m and "not in config" in m for m in messages)


def test_a_renamed_surface_is_not_reported_as_drift(tmp_path):
    """H2's actual regression test: the id 'web' still matches the detected candidate 'web'
    even though the user renamed the surface's DISPLAY name -- the old name-keyed match broke
    exactly this case."""
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}), encoding="utf-8")
    cfg = _cfg(_web(surface_id="web", name="Marketing site (renamed by hand)"))
    assert drift.detect_drift(cfg, tmp_path) == []


def test_a_declined_surface_is_not_reported_twice(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}), encoding="utf-8")
    (tmp_path / "openapi.yaml").write_text("openapi: 3.0.0\n", encoding="utf-8")
    cfg = _cfg(_web(), cfgmod.Surface(
        id="api", name="api", kind="api", driver="http", launch="", declined=True,
    ))
    messages = drift.detect_drift(cfg, tmp_path)
    assert not any("api" in m and "not in config" in m for m in messages)


def test_a_removed_detector_originated_surface_is_reported(tmp_path):
    cfg = _cfg(cfgmod.Surface(
        id="web", name="Web", kind="ui", driver="playwright", launch="npm run dev",
        provenance={drift.DETECTED_PROVENANCE_KEY: drift.DETECTED_PROVENANCE_VALUE},
    ))
    messages = drift.detect_drift(cfg, tmp_path)
    assert any("web" in m and "gone" in m and "reconfigure" in m for m in messages)


def test_a_hand_added_surface_with_no_match_is_never_reported(tmp_path):
    cfg = _cfg(cfgmod.Surface(id="device", name="Device", kind="cli", driver="adb", launch="adb shell"))
    for _ in range(2):
        messages = drift.detect_drift(cfg, tmp_path)
        assert not any("device" in m for m in messages)


def test_runnable_surfaces_excludes_declined():
    cfg = _cfg(
        _web(surface_id="a", declined=False),
        _web(surface_id="b", declined=True),
    )
    ids = {s.id for s in drift.runnable_surfaces(cfg)}
    assert ids == {"a"}


def test_runnable_surfaces_excludes_pending_driver():
    cfg = _cfg(
        _web(surface_id="a"),
        cfgmod.Surface(id="b", name="Desktop app", kind="ui", driver="pending", launch=""),
    )
    ids = {s.id for s in drift.runnable_surfaces(cfg)}
    assert ids == {"a"}


def test_runnable_surfaces_keeps_config_order():
    cfg = _cfg(_web(surface_id="z"), _web(surface_id="a"))
    assert [s.id for s in drift.runnable_surfaces(cfg)] == ["z", "a"]
