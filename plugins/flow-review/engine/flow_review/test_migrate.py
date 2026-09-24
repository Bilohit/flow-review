from __future__ import annotations

import json

from flow_review import config as cfgmod
from flow_review import migrate


def _v1_raw(**over):
    base = dict(
        schema_version=1, generator_version="1.4.0",
        surfaces=[
            dict(
                name="Web App", kind="ui", driver="cdp", launch="npm run dev",
                preconditions=[{"name": "port 5173", "cmd": "curl -sf localhost:5173"}],
                destructive=False, provenance={"launch": "proven", "kind": "audited"},
            ),
            dict(
                name="Admin Panel!!", kind="ui", driver="cdp", launch="npm run admin",
                preconditions=[], destructive=True, provenance={},
            ),
        ],
        lens_sets={"web": ["identity"]}, tester_agent="general-purpose",
        evidence_types=["screenshot"], flows_hash="deadbeef",
    )
    base.update(over)
    return base


def test_is_v1_detects_schema_1_and_missing_schema_version():
    assert migrate.is_v1(_v1_raw())
    raw = _v1_raw()
    del raw["schema_version"]
    assert migrate.is_v1(raw)
    assert not migrate.is_v1({"schema_version": 2})


def test_migrate_carries_over_core_fields_and_derives_ids():
    cfg, summary = migrate.migrate(_v1_raw())
    assert [s.name for s in cfg.surfaces] == ["Web App", "Admin Panel!!"]
    assert cfg.surfaces[0].id == "web-app"
    assert cfg.surfaces[1].id == "admin-panel"
    assert cfg.surfaces[0].kind == "ui"
    assert cfg.surfaces[0].launch == "npm run dev"
    assert cfg.surfaces[0].preconditions == [{"name": "port 5173", "cmd": "curl -sf localhost:5173"}]
    assert summary.surfaces_migrated == 2


def test_destructive_true_becomes_state_persistent():
    cfg, summary = migrate.migrate(_v1_raw())
    assert cfg.surfaces[0].state == "disposable"
    assert cfg.surfaces[1].state == "persistent"
    assert summary.destructive_to_persistent == ["admin-panel"]


def test_dead_v1_keys_are_reported_and_dropped():
    cfg, summary = migrate.migrate(_v1_raw())
    assert set(summary.dropped_keys) >= {"lens_sets", "tester_agent", "evidence_types"}
    assert not hasattr(cfg, "lens_sets")


def test_id_collisions_are_deduplicated():
    raw = _v1_raw(surfaces=[
        dict(name="web", kind="ui", driver="cdp", launch="a", preconditions=[], destructive=False, provenance={}),
        dict(name="Web", kind="ui", driver="cdp", launch="b", preconditions=[], destructive=False, provenance={}),
    ])
    cfg, summary = migrate.migrate(raw)
    assert cfg.surfaces[0].id == "web"
    assert cfg.surfaces[1].id == "web-2"
    assert summary.id_collisions_resolved == {"Web": "web-2"}


def test_migrated_config_is_valid_v2(tmp_path):
    cfg, _ = migrate.migrate(_v1_raw())
    path = tmp_path / "config.json"
    cfgmod.save(cfg, path)
    back = cfgmod.load(path)
    assert back == cfg


def test_summary_render_lists_destructive_and_dropped():
    _, summary = migrate.migrate(_v1_raw())
    text = summary.render()
    assert "2 surface(s) migrated" in text
    assert "admin-panel" in text
    assert "lens_sets" in text


def test_migrate_file_writes_backup_and_v2_config(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(_v1_raw()), encoding="utf-8")
    summary = migrate.migrate_file(path, quiet=True)
    assert summary is not None
    backup = tmp_path / "config.v1.bak"
    assert backup.exists()
    assert json.loads(backup.read_text(encoding="utf-8")) == _v1_raw()
    cfg = cfgmod.load(path)  # must now load cleanly as v2
    assert cfg.surfaces[0].id == "web-app"


def test_migrate_file_is_a_noop_on_an_already_v2_config(tmp_path):
    cfg = cfgmod.Config(schema_version=cfgmod.SCHEMA_VERSION, generator_version="2.0.0")
    path = tmp_path / "config.json"
    cfgmod.save(cfg, path)
    before = path.read_bytes()
    assert migrate.migrate_file(path, quiet=True) is None
    assert path.read_bytes() == before
    assert not (tmp_path / "config.v1.bak").exists()


def test_migrate_file_quiet_suppresses_the_summary_print(tmp_path, capsys):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(_v1_raw()), encoding="utf-8")
    migrate.migrate_file(path, quiet=True)
    assert capsys.readouterr().out == ""


def test_migrate_file_prints_the_summary_when_not_quiet(tmp_path, capsys):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(_v1_raw()), encoding="utf-8")
    migrate.migrate_file(path, quiet=False)
    assert "migrated config from schema v1 to v2" in capsys.readouterr().out
