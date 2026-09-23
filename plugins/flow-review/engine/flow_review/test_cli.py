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
        "setup-env", "prove", "plan", "event", "replay", "serve", "triage", "ledger",
        "budget", "migrate", "model",
    ):
        code = cli.main([verb])
        assert code == 2, f"{verb} stub must report not-yet-implemented, not crash or succeed"


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
