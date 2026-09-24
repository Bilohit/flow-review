from __future__ import annotations

import json

import pytest

from flow_review import config as cfgmod


def _surface_dict(**over):
    base = dict(
        id="web-app", name="Web app", kind="ui", driver="playwright",
        launch="npm run dev", cwd=".", env={},
        options={"base_url": "http://localhost:5173"},
        preconditions=[{"name": "port 5173", "cmd": "curl -sf localhost:5173"}],
        state="disposable", reset=None, creds={}, record=False,
        provenance={"launch": "proven", "origin": "audited"}, declined=False,
    )
    base.update(over)
    return base


def _surface(**over):
    return cfgmod.Surface(**_surface_dict(**over))


def _raw_config(**over):
    base = dict(
        schema_version=cfgmod.SCHEMA_VERSION, generator_version="2.0.0",
        model_profile="default", role_overrides={}, budget={"cap_tokens": None},
        test_inbox=None, flows_hash="", surfaces=[_surface_dict()],
    )
    base.update(over)
    return base


def test_round_trip_preserves_every_field(tmp_path):
    cfg = cfgmod.Config(
        schema_version=cfgmod.SCHEMA_VERSION, generator_version="2.0.0",
        surfaces=[_surface()], model_profile="max",
        role_overrides={"verifier": "opus"}, budget={"cap_tokens": 100000},
        test_inbox={"provider": "mailpit", "base_url": "http://localhost:8025"},
        flows_hash="abc123",
    )
    path = tmp_path / "config.json"
    cfgmod.save(cfg, path)
    back = cfgmod.load(path)
    assert back == cfg


def test_load_rejects_a_newer_schema_rather_than_guessing(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"schema_version": cfgmod.SCHEMA_VERSION + 1}), encoding="utf-8")
    with pytest.raises(cfgmod.ConfigVersionError, match="newer"):
        cfgmod.load(path)


def test_surface_id_is_required_and_separate_from_name(tmp_path):
    raw = _raw_config(surfaces=[_surface_dict(id="checkout-flow", name="Checkout (v2)")])
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    cfg = cfgmod.load(path)
    assert cfg.surfaces[0].id == "checkout-flow"
    assert cfg.surfaces[0].name == "Checkout (v2)"


def test_unknown_top_level_key_raises_friendly_error_with_close_match(tmp_path):
    raw = _raw_config()
    raw["modle_profile"] = "default"  # typo for model_profile
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(cfgmod.ConfigKeyError) as exc:
        cfgmod.load(path)
    assert "modle_profile" in str(exc.value)
    assert "model_profile" in str(exc.value)


def test_unknown_surface_key_raises_friendly_error_naming_the_surface(tmp_path):
    bad = _surface_dict(id="checkout")
    bad["destructive"] = True  # a v1 field, dropped per A-5
    raw = _raw_config(surfaces=[bad])
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(cfgmod.ConfigKeyError, match="checkout"):
        cfgmod.load(path)


def test_unknown_web_option_key_raises_friendly_error(tmp_path):
    bad = _surface_dict(options={"base_urll": "http://x"})
    raw = _raw_config(surfaces=[bad])
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(cfgmod.ConfigKeyError) as exc:
        cfgmod.load(path)
    assert "base_urll" in str(exc.value)
    assert "base_url" in str(exc.value)


def test_a_non_web_surface_rejects_any_options(tmp_path):
    bad = _surface_dict(id="cli-tool", kind="cli", driver="shell", options={"timeout": 5})
    raw = _raw_config(surfaces=[bad])
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(cfgmod.ConfigKeyError, match="timeout"):
        cfgmod.load(path)


def test_unknown_state_value_is_rejected(tmp_path):
    raw = _raw_config(surfaces=[_surface_dict(state="ephemeral")])
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="ephemeral"):
        cfgmod.load(path)


def test_unknown_model_profile_is_rejected(tmp_path):
    raw = _raw_config(model_profile="turbo")
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="turbo"):
        cfgmod.load(path)


def test_unknown_role_override_key_is_rejected(tmp_path):
    raw = _raw_config(role_overrides={"orchestrator": "opus"})
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="orchestrator"):
        cfgmod.load(path)


def test_unknown_role_override_model_is_rejected(tmp_path):
    raw = _raw_config(role_overrides={"verifier": "gpt-5"})
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="gpt-5"):
        cfgmod.load(path)


def test_preconditions_must_be_a_list_of_cmd_carrying_dicts(tmp_path):
    raw = _raw_config(surfaces=[_surface_dict(preconditions=[{"name": "x"}])])
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="cmd"):
        cfgmod.load(path)


def test_preconditions_reject_an_unknown_item_key(tmp_path):
    raw = _raw_config(surfaces=[_surface_dict(
        preconditions=[{"name": "x", "cmd": "true", "retries": 3}]
    )])
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(cfgmod.ConfigKeyError, match="retries"):
        cfgmod.load(path)


def test_creds_are_env_var_names_never_values(tmp_path):
    # A2 does not (and cannot) forbid a value shaped like a secret -- that is an authoring
    # discipline, not a checkable schema fact. It only asserts the field round-trips as
    # name -> name-of-env-var, which is what A10's .env loader consumes.
    raw = _raw_config(surfaces=[_surface_dict(creds={"ADMIN_PASSWORD": "ADMIN_PASSWORD"})])
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    cfg = cfgmod.load(path)
    assert cfg.surfaces[0].creds == {"ADMIN_PASSWORD": "ADMIN_PASSWORD"}


def test_v1_fields_are_gone_from_config(tmp_path):
    raw = _raw_config()
    raw["lens_sets"] = {}
    path = tmp_path / "config.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(cfgmod.ConfigKeyError, match="lens_sets"):
        cfgmod.load(path)


def test_save_rejects_unknown_surface_kind(tmp_path):
    cfg = cfgmod.Config(
        schema_version=cfgmod.SCHEMA_VERSION, generator_version="2.0.0",
        surfaces=[_surface(kind="hologram")],
    )
    path = tmp_path / "config.json"
    with pytest.raises(ValueError, match="hologram"):
        cfgmod.save(cfg, path)
    assert not path.exists()


def test_saved_json_is_stable_and_human_editable(tmp_path):
    cfg = cfgmod.Config(
        schema_version=cfgmod.SCHEMA_VERSION, generator_version="2.0.0", surfaces=[_surface()],
    )
    path = tmp_path / "config.json"
    cfgmod.save(cfg, path)
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert '  "schema_version"' in text
