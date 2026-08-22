from __future__ import annotations

import json

import pytest

from fr import config as cfgmod


def _surface_dict(**over):
    base = dict(
        name="web", kind="ui", driver="cdp",
        launch="npm run dev", preconditions=[{"name": "port 5173", "cmd": "curl -sf localhost:5173"}],
        destructive=False, provenance={"launch": "proven", "kind": "audited"},
    )
    base.update(over)
    return base


def _surface(**over):
    return cfgmod.Surface(**_surface_dict(**over))


def _raw_config(**over):
    base = dict(
        schema_version=cfgmod.SCHEMA_VERSION,
        generator_version="1.0.0",
        surfaces=[_surface_dict()],
        lens_sets={},
        tester_agent="general-purpose",
        evidence_types=[],
        flows_hash="",
    )
    base.update(over)
    return base


def test_round_trip_preserves_every_field(tmp_path):
    cfg = cfgmod.Config(
        schema_version=cfgmod.SCHEMA_VERSION,
        generator_version="1.0.0",
        surfaces=[_surface()],
        lens_sets={"web": ["identity", "first-time-user"]},
        tester_agent="general-purpose",
        evidence_types=["screenshot", "rect", "computed-style"],
        flows_hash="abc123",
    )
    path = tmp_path / "config.json"
    cfgmod.save(cfg, path)
    back = cfgmod.load(path)
    assert back == cfg


def test_load_rejects_a_newer_schema_rather_than_guessing(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"schema_version": cfgmod.SCHEMA_VERSION + 1}), encoding="utf-8")
    with pytest.raises(cfgmod.ConfigVersionError) as exc:
        cfgmod.load(path)
    assert "newer" in str(exc.value)


def test_unknown_surface_kind_is_rejected(tmp_path):
    # save() now rejects this value itself (see test_save_rejects_unknown_surface_kind),
    # so the bad file is written directly here to exercise load()'s own validation.
    raw = _raw_config(surfaces=[_surface_dict(kind="hologram")])
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="hologram"):
        cfgmod.load(path)


def test_unknown_surface_driver_is_rejected(tmp_path):
    # save() now rejects this value itself (see test_save_rejects_unknown_surface_driver),
    # so the bad file is written directly here to exercise load()'s own validation.
    raw = _raw_config(surfaces=[_surface_dict(driver="cpd")])
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="cpd"):
        cfgmod.load(path)


def test_unknown_provenance_value_is_rejected(tmp_path):
    # save() now rejects this value itself (see test_save_rejects_unknown_provenance_value),
    # so the bad file is written directly here to exercise load()'s own validation.
    raw = _raw_config(surfaces=[_surface_dict(provenance={"launch": "vibes"})])
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="vibes"):
        cfgmod.load(path)


def test_save_rejects_unknown_surface_kind(tmp_path):
    cfg = cfgmod.Config(
        schema_version=cfgmod.SCHEMA_VERSION, generator_version="1.0.0",
        surfaces=[_surface(kind="hologram")], lens_sets={}, tester_agent="general-purpose",
        evidence_types=[], flows_hash="",
    )
    path = tmp_path / "config.json"
    with pytest.raises(ValueError, match="hologram"):
        cfgmod.save(cfg, path)
    assert not path.exists()


def test_save_rejects_unknown_surface_driver(tmp_path):
    cfg = cfgmod.Config(
        schema_version=cfgmod.SCHEMA_VERSION, generator_version="1.0.0",
        surfaces=[_surface(driver="cpd")], lens_sets={}, tester_agent="general-purpose",
        evidence_types=[], flows_hash="",
    )
    path = tmp_path / "config.json"
    with pytest.raises(ValueError, match="cpd"):
        cfgmod.save(cfg, path)
    assert not path.exists()


def test_save_rejects_unknown_provenance_value(tmp_path):
    cfg = cfgmod.Config(
        schema_version=cfgmod.SCHEMA_VERSION, generator_version="1.0.0",
        surfaces=[_surface(provenance={"launch": "vibes"})], lens_sets={},
        tester_agent="general-purpose", evidence_types=[], flows_hash="",
    )
    path = tmp_path / "config.json"
    with pytest.raises(ValueError, match="vibes"):
        cfgmod.save(cfg, path)
    assert not path.exists()


def test_load_converges_an_older_schema_to_current(tmp_path):
    raw = _raw_config(schema_version=0)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    cfg = cfgmod.load(path)
    assert cfg.schema_version == cfgmod.SCHEMA_VERSION


def test_load_treats_a_missing_schema_version_as_current_once_read(tmp_path):
    raw = _raw_config()
    del raw["schema_version"]
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    cfg = cfgmod.load(path)
    assert cfg.schema_version == cfgmod.SCHEMA_VERSION


def test_load_names_the_surface_missing_a_required_key(tmp_path):
    bad = _surface_dict(name="checkout")
    del bad["driver"]
    raw = _raw_config(surfaces=[_surface_dict(), bad])
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="checkout") as exc:
        cfgmod.load(path)
    # "index 1", not "1": the wrapped TypeError already says "missing 1 required positional
    # argument", so a bare "1" passes even when the reported index is wrong.
    assert "index 1" in str(exc.value)


def test_load_names_the_surface_with_an_unknown_key(tmp_path):
    bad = _surface_dict(name="checkout")
    bad["unexpected_field"] = "oops"
    raw = _raw_config(surfaces=[bad])
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="checkout"):
        cfgmod.load(path)


def test_load_names_the_surface_that_is_not_an_object(tmp_path):
    raw = _raw_config(surfaces=["not-a-surface"])
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="index 0"):
        cfgmod.load(path)


def test_saved_json_is_stable_and_human_editable(tmp_path):
    cfg = cfgmod.Config(
        schema_version=cfgmod.SCHEMA_VERSION, generator_version="1.0.0",
        surfaces=[_surface()], lens_sets={}, tester_agent="general-purpose",
        evidence_types=[], flows_hash="",
    )
    path = tmp_path / "config.json"
    cfgmod.save(cfg, path)
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert '  "schema_version"' in text
