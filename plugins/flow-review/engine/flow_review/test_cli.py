from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from flow_review import cli

ENGINE_ROOT = Path(__file__).resolve().parent.parent  # plugins/flow-review/engine


def test_main_with_no_args_prints_usage_and_exits_nonzero(capsys):
    code = cli.main([])
    assert code != 0
    captured = capsys.readouterr()
    assert "flow-review" in (captured.out + captured.err)


def test_main_dispatches_known_stub_subcommands():
    for verb in (
        "prove", "plan", "serve", "triage", "ledger",
        "budget", "model",
    ):
        code = cli.main([verb])
        assert code == 2, f"{verb} stub must report not-yet-implemented, not crash or succeed"


def test_replay_without_project_exits_three(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert cli.main(["replay"]) == 3


def test_replay_log_without_run_exits_three(tmp_path):
    (tmp_path / ".flow-review").mkdir()
    (tmp_path / ".flow-review" / "config.json").write_text(
        '{"schema_version": 2, "generator_version": "t", "surfaces": []}', encoding="utf-8")
    assert cli.main(["replay", "--project", str(tmp_path), "--log", "x.json"]) == 3


def test_replay_no_recordings_exits_zero(tmp_path):
    (tmp_path / ".flow-review").mkdir()
    (tmp_path / ".flow-review" / "config.json").write_text(
        '{"schema_version": 2, "generator_version": "t", "surfaces": []}', encoding="utf-8")
    assert cli.main(["replay", "--project", str(tmp_path)]) == 0


def test_event_subcommand_appends_via_events_module(tmp_path):
    code = cli.main(["event", "--run", str(tmp_path), "--type", "step", "surface=web", "state=ok"])
    assert code == 0
    text = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert '"type": "step"' in text
    assert '"surface": "web"' in text


def test_event_subcommand_type_flag_wins_over_json_type(tmp_path):
    code = cli.main([
        "event", "--run", str(tmp_path), "--type", "finding",
        "--json", '{"type": "step", "sev": "P1"}',
    ])
    assert code == 0
    text = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert '"type": "finding"' in text


def test_event_subcommand_exits_two_on_bad_json(tmp_path, capsys):
    code = cli.main(["event", "--run", str(tmp_path), "--type", "step", "--json", "{not json"])
    assert code == 2
    assert capsys.readouterr().err.strip()


def test_event_subcommand_exits_two_on_field_without_equals(tmp_path, capsys):
    code = cli.main(["event", "--run", str(tmp_path), "--type", "step", "noequals"])
    assert code == 2
    assert capsys.readouterr().err.strip()


def test_main_rejects_an_unknown_subcommand():
    code = cli.main(["not-a-real-verb"])
    assert code == 2


def test_console_script_is_declared_in_pyproject():
    text = (ENGINE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "flow-review" in text
    assert "flow_review.cli:main" in text


def test_main_reconfigures_stdout_before_anything_else_runs(monkeypatch):
    calls = []
    original = sys.stdout.reconfigure if hasattr(sys.stdout, "reconfigure") else None
    def _spy(*a, **kw):
        calls.append((a, kw))
        if original:
            return original(*a, **kw)
    monkeypatch.setattr(sys.stdout, "reconfigure", _spy, raising=False)
    cli.main([])
    assert calls, "cli.main() must call sys.stdout.reconfigure()"


def test_find_project_root_walks_up_to_the_nearest_flow_review_dir(tmp_path):
    (tmp_path / ".flow-review").mkdir()
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert cli.find_project_root(nested) == tmp_path.resolve()


def test_find_project_root_returns_none_when_no_ancestor_has_one(tmp_path):
    lonely = tmp_path / "nowhere"
    lonely.mkdir()
    assert cli.find_project_root(lonely) is None


def test_find_project_root_matches_the_start_dir_itself(tmp_path):
    (tmp_path / ".flow-review").mkdir()
    assert cli.find_project_root(tmp_path) == tmp_path.resolve()


def test_project_option_resolves_project_root_on_args(tmp_path):
    (tmp_path / ".flow-review").mkdir()
    parser = cli.build_parser()
    args = parser.parse_args(["--project", str(tmp_path), "prove"])
    cli._resolve_project_root(args)
    assert args.project_root == tmp_path.resolve()


def test_migrate_subcommand_is_idempotent_and_exits_zero(tmp_path, capsys):
    path = tmp_path / "config.json"
    path.write_text('{"schema_version": 1, "surfaces": []}', encoding="utf-8")
    assert cli.main(["migrate", "--path", str(path), "--quiet"]) == 0
    assert (tmp_path / "config.v1.bak").exists()
    assert cli.main(["migrate", "--path", str(path)]) == 0
    assert capsys.readouterr().out == ""


def test_migrate_subcommand_exits_one_on_bad_json(tmp_path, capsys):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    assert cli.main(["migrate", "--path", str(path)]) == 1
    assert capsys.readouterr().err.strip()


def test_migrate_resolves_config_from_project_root_not_cwd(tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    (proj / ".flow-review").mkdir(parents=True)
    cfg = proj / ".flow-review" / "config.json"
    cfg.write_text('{"schema_version": 1, "surfaces": []}', encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert cli.main(["--project", str(proj), "migrate", "--quiet"]) == 0
    assert (proj / ".flow-review" / "config.v1.bak").exists()


def test_migrate_without_project_or_path_exits_one(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "find_project_root", lambda start: None)
    assert cli.main(["migrate"]) == 1
    assert "no .flow-review/ found" in capsys.readouterr().err


def test_migrate_summary_names_the_real_backup_file(tmp_path, capsys):
    from flow_review import migrate
    path = tmp_path / "other.json"
    path.write_text('{"schema_version": 1, "surfaces": []}', encoding="utf-8")
    migrate.migrate_file(path)
    assert "other.v1.bak" in capsys.readouterr().out


def test_project_option_is_accepted_after_the_verb(tmp_path):
    # CP1: the documented form is `flow-review migrate --project <dir>`; argparse rejected it
    # because --project existed only on the top-level parser.
    (tmp_path / ".flow-review").mkdir()
    cfg = tmp_path / ".flow-review" / "config.json"
    cfg.write_text('{"schema_version": 1, "surfaces": []}', encoding="utf-8")
    assert cli.main(["migrate", "--project", str(tmp_path), "--quiet"]) == 0
    assert (tmp_path / ".flow-review" / "config.v1.bak").exists()


def test_setup_env_targets_the_resolved_project_root_not_cwd(tmp_path, monkeypatch):
    from flow_review import envsetup
    proj = tmp_path / "proj"
    proj.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    seen = {}
    monkeypatch.setattr(envsetup, "setup_env", lambda project_dir, *a, **k: seen.setdefault("dir", Path(project_dir)))
    monkeypatch.setattr(envsetup, "write_gitignore", lambda d, **k: seen.setdefault("gi", Path(d)))
    assert cli.main(["setup-env", "--project", str(proj)]) == 0
    assert seen["dir"].resolve() == proj.resolve()
    assert seen["gi"].resolve() == (proj / ".flow-review").resolve()
