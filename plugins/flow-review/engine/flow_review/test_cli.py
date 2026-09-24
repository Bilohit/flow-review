from __future__ import annotations

import json
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
        "prove",
    ):
        code = cli.main([verb])
        assert code == 2, f"{verb} stub must report not-yet-implemented, not crash or succeed"


def test_triage_cli_applies_the_state_via_flow_review_triage_apply(tmp_path, capsys):
    from flow_review import ledger as ledger_mod
    (tmp_path / ".flow-review").mkdir()
    entry = ledger_mod.LedgerEntry(
        id="f1", fingerprint="abc123", surface_id="web", flow_id="w03",
        rule="identity", route="/settings", locator="role=row,name=Notifications",
        sev="P1", text="border-radius diverges from the token", evidence=["computed 8px"],
    )
    ledger_mod.save(ledger_mod.Ledger(findings={"f1": entry}),
                     tmp_path / ".flow-review" / "findings.json")

    code = cli.main(["triage", "--project", str(tmp_path), "f1", "fixed"])
    assert code == 0
    assert "fixed" in capsys.readouterr().out

    reloaded = ledger_mod.load(tmp_path / ".flow-review" / "findings.json")
    assert reloaded.findings["f1"].state == "fixed"


def test_triage_cli_rejects_refuted_without_a_reason(tmp_path, capsys):
    from flow_review import ledger as ledger_mod
    (tmp_path / ".flow-review").mkdir()
    entry = ledger_mod.LedgerEntry(
        id="f1", fingerprint="abc123", surface_id="web", flow_id="w03",
        rule="identity", route="/settings", locator="role=row,name=Notifications",
        sev="P1", text="border-radius diverges from the token", evidence=["computed 8px"],
    )
    ledger_mod.save(ledger_mod.Ledger(findings={"f1": entry}),
                     tmp_path / ".flow-review" / "findings.json")

    code = cli.main(["triage", "--project", str(tmp_path), "f1", "refuted"])
    assert code == 1


def test_model_prints_resolved_model_for_role(tmp_path, capsys):
    (tmp_path / ".flow-review").mkdir()
    (tmp_path / ".flow-review" / "config.json").write_text(
        '{"schema_version": 2, "generator_version": "t", "surfaces": []}', encoding="utf-8")
    code = cli.main(["model", "--project", str(tmp_path), "verifier"])
    assert code == 0
    assert capsys.readouterr().out.strip() == "opus"


def test_model_honours_role_overrides(tmp_path, capsys):
    (tmp_path / ".flow-review").mkdir()
    (tmp_path / ".flow-review" / "config.json").write_text(
        '{"schema_version": 2, "generator_version": "t", "surfaces": [], '
        '"role_overrides": {"verifier": "sonnet"}}', encoding="utf-8")
    code = cli.main(["model", "--project", str(tmp_path), "verifier"])
    assert code == 0
    assert capsys.readouterr().out.strip() == "sonnet"


def test_budget_check_exits_nonzero_when_cap_would_be_exceeded(tmp_path):
    (tmp_path / ".flow-review").mkdir()
    (tmp_path / ".flow-review" / "config.json").write_text(
        '{"schema_version": 2, "generator_version": "t", "surfaces": [], '
        '"budget": {"cap_tokens": 10000}}', encoding="utf-8")
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    from flow_review import budget
    budget.record_usage(run_dir, "webapp", "lens", 9000)
    code = cli.main([
        "budget", "--project", str(tmp_path), "check",
        "--run", str(run_dir), "--next", "verifier", "--surface", "webapp",
    ])
    assert code == 1


def test_budget_check_exits_zero_when_under_cap(tmp_path):
    (tmp_path / ".flow-review").mkdir()
    (tmp_path / ".flow-review" / "config.json").write_text(
        '{"schema_version": 2, "generator_version": "t", "surfaces": []}', encoding="utf-8")
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    code = cli.main([
        "budget", "--project", str(tmp_path), "check",
        "--run", str(run_dir), "--next", "verifier", "--surface", "webapp",
    ])
    assert code == 0


def test_budget_alone_without_subcommand_exits_two():
    assert cli.main(["budget"]) == 2


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


def test_plan_dispatches_and_prints_json(tmp_path, capsys):
    (tmp_path / ".flow-review").mkdir()
    (tmp_path / ".flow-review" / "config.json").write_text(
        '{"schema_version": 2, "generator_version": "t", "surfaces": []}', encoding="utf-8")
    code = cli.main(["plan", "--project", str(tmp_path), "--mode", "auto"])
    assert code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["mode"] == "auto"
    assert payload["surfaces"] == []


def test_plan_without_project_exits_three(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert cli.main(["plan", "--mode", "auto"]) == 3


def test_plan_missing_goal_exits_two(tmp_path):
    (tmp_path / ".flow-review").mkdir()
    (tmp_path / ".flow-review" / "config.json").write_text(
        '{"schema_version": 2, "generator_version": "t", "surfaces": []}', encoding="utf-8")
    assert cli.main(["plan", "--project", str(tmp_path), "--mode", "goal"]) == 2


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


def test_drive_verb_delegates_to_web_drive_main(monkeypatch, tmp_path):
    from flow_review import cli

    captured = {}

    def _fake_main(argv, project_root=None):
        captured["argv"] = argv
        captured["project_root"] = project_root
        return 0

    monkeypatch.setattr("flow_review.web.drive.main", _fake_main)
    rc = cli.main(["--project", str(tmp_path), "drive", "goto", "--surface", "webapp",
                    "--run", str(tmp_path), "/"])
    assert rc == 0
    assert captured["argv"] == ["goto", "--surface", "webapp", "--run", str(tmp_path), "/"]
    assert captured["project_root"] == tmp_path.resolve()


def test_serve_without_project_exits_three(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    assert cli.main(["serve", "--run", str(run_dir)]) == 3


def test_serve_static_flag_calls_render_static_not_serve(tmp_path, monkeypatch):
    (tmp_path / ".flow-review").mkdir()
    (tmp_path / ".flow-review" / "config.json").write_text(
        '{"schema_version": 2, "generator_version": "t", "surfaces": []}', encoding="utf-8")
    run_dir = tmp_path / "run1"
    run_dir.mkdir()
    out = tmp_path / "out.html"

    seen = {}

    def fake_render_static(project_root, run_dir_arg, cfg, out_path):
        seen["project_root"] = Path(project_root)
        seen["run_dir"] = run_dir_arg
        seen["out_path"] = out_path

    def fake_serve(*a, **k):
        raise AssertionError("serve() must not be called when --static is given")

    from flow_review.dashboard import static as staticmod
    from flow_review.dashboard import serve as servemod
    monkeypatch.setattr(staticmod, "render_static", fake_render_static)
    monkeypatch.setattr(servemod, "serve", fake_serve)

    code = cli.main(["serve", "--project", str(tmp_path), "--run", str(run_dir), "--static", str(out)])
    assert code == 0
    assert seen["project_root"] == tmp_path.resolve()
    assert seen["run_dir"] == run_dir
    assert seen["out_path"] == out


def test_serve_without_static_calls_serve(tmp_path, monkeypatch):
    (tmp_path / ".flow-review").mkdir()
    (tmp_path / ".flow-review" / "config.json").write_text(
        '{"schema_version": 2, "generator_version": "t", "surfaces": []}', encoding="utf-8")
    run_dir = tmp_path / "run1"
    run_dir.mkdir()

    seen = {}

    def fake_serve(project_root, run_dir_arg, cfg, port):
        seen["project_root"] = Path(project_root)
        seen["run_dir"] = run_dir_arg
        seen["port"] = port

    from flow_review.dashboard import serve as servemod
    monkeypatch.setattr(servemod, "serve", fake_serve)

    code = cli.main(["serve", "--project", str(tmp_path), "--run", str(run_dir), "--port", "9999"])
    assert code == 0
    assert seen["project_root"] == tmp_path.resolve()
    assert seen["run_dir"] == run_dir
    assert seen["port"] == 9999


def _ledger_project(tmp_path):
    (tmp_path / ".flow-review").mkdir()
    run = tmp_path / "run"
    run.mkdir()
    return run


def _finding_event(flow_id="login", rule="ui.clarity", **kw):
    return {**dict(type="finding", surface_id="web", flow_id=flow_id, rule=rule, route="/",
                   locator="#go", sev="P1", text="unclear"), **kw}


def test_ledger_reconcile_folds_run_findings_keeping_event_ids(tmp_path):
    from flow_review import events as ev, ledger as ledger_mod
    run = _ledger_project(tmp_path)
    ev.append(run, {"type": "step", "surface_id": "web", "flow_id": "login", "step": "flow-begin"})
    kept = ev.append(run, _finding_event())
    gone = ev.append(run, _finding_event(rule="ui.other"))
    ev.append(run, {"type": "withdraw", "finding_id": gone["id"]})
    code = cli.main(["--project", str(tmp_path), "ledger", "reconcile", "--run", str(run)])
    assert code == 0
    led = ledger_mod.load(tmp_path / ".flow-review" / "findings.json")
    assert list(led.findings) == [kept["id"]]
    assert led.findings[kept["id"]].last_run == "run"


def test_ledger_reconcile_marks_unseen_finding_fixed_only_for_flows_run(tmp_path):
    from flow_review import events as ev, ledger as ledger_mod
    run = _ledger_project(tmp_path)
    path = tmp_path / ".flow-review" / "findings.json"
    led = ledger_mod.reconcile(ledger_mod.Ledger(), [_finding_event(), _finding_event(flow_id="pay")],
                               {"login", "pay"}, "r0")
    ledger_mod.save(led, path)
    ev.append(run, {"type": "step", "surface_id": "web", "flow_id": "login", "step": "flow-begin"})
    assert cli.main(["--project", str(tmp_path), "ledger", "reconcile", "--run", str(run)]) == 0
    states = {e.flow_id: e.state for e in ledger_mod.load(path).findings.values()}
    assert states == {"login": "fixed", "pay": "open"}


def test_ledger_record_miss_prints_count(tmp_path, capsys):
    run = _ledger_project(tmp_path)
    args = ["--project", str(tmp_path), "ledger", "record-miss", "--function", "export", "--run"]
    assert cli.main(args + [str(run)]) == 0
    assert cli.main(args + [str(tmp_path / "run2")]) == 0
    assert capsys.readouterr().out.split() == ["1", "2"]


def test_ledger_suppressions_prints_json(tmp_path, capsys):
    from flow_review import ledger as ledger_mod
    _ledger_project(tmp_path)
    path = tmp_path / ".flow-review" / "findings.json"
    led = ledger_mod.reconcile(ledger_mod.Ledger(), [_finding_event()], {"login"}, "r0")
    next(iter(led.findings.values())).state = "false-positive"
    ledger_mod.save(led, path)
    assert cli.main(["--project", str(tmp_path), "ledger", "suppressions", "--rule", "ui.clarity"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out == [{"route": "/", "locator": "#go", "text": "unclear", "state": "false-positive"}]


def test_manifest_apply_learnings_prints_new_hash(tmp_path, capsys):
    from flow_review import manifest as manifest_mod
    _ledger_project(tmp_path)
    flows = tmp_path / "flows.md"
    flows.write_text("# flows" + chr(10), encoding="utf-8")
    h = manifest_mod.manifest_hash(flows.read_text(encoding="utf-8"))
    code = cli.main(["--project", str(tmp_path), "manifest", "apply-learnings", "--path", str(flows),
                     "--hash", h, "--learning", "login needs 2FA"])
    assert code == 0
    new = capsys.readouterr().out.strip()
    assert new != h and "login needs 2FA" in flows.read_text(encoding="utf-8")


def test_ledger_alias_candidates_and_reconcile_alias(tmp_path, capsys):
    from flow_review import events as ev, ledger as ledger_mod
    run = _ledger_project(tmp_path)
    path = tmp_path / ".flow-review" / "findings.json"
    ledger_mod.save(ledger_mod.reconcile(ledger_mod.Ledger(), [_finding_event()], {"login"}, "r0"), path)
    assert cli.main(["--project", str(tmp_path), "ledger", "alias-candidates", "--flow", "login",
                     "--rule", "ui.clarity", "--route", "/"]) == 0
    cands = json.loads(capsys.readouterr().out)
    assert len(cands) == 1
    canonical = cands[0]["id"]
    moved = ev.append(run, _finding_event(locator="#renamed"))
    fp = ledger_mod.fingerprint("login", "ui.clarity", "/", "#renamed")
    assert cli.main(["--project", str(tmp_path), "ledger", "reconcile", "--run", str(run),
                     "--alias", f"{fp}={canonical}"]) == 0
    led = ledger_mod.load(path)
    assert list(led.findings) == [canonical] and fp in led.findings[canonical].aliases
    assert moved["id"] not in led.findings


def test_validate_resolve_refuted_with_real_evidence(tmp_path, capsys):
    (tmp_path / "m.json").write_text("{}", encoding="utf-8")
    code = cli.main(["validate", "resolve", "--run", str(tmp_path), "--verdict", "refuted",
                     "--reason", "measured 5:1", "--kind", "measurement", "--ref", "m.json"])
    assert code == 0 and capsys.readouterr().out.strip() == "refuted"


def test_validate_resolve_bad_evidence_prints_stands(tmp_path, capsys):
    run = tmp_path / "run"
    run.mkdir()
    (tmp_path / "m.json").write_text("{}", encoding="utf-8")
    code = cli.main(["validate", "resolve", "--run", str(run), "--verdict", "refuted",
                     "--reason", "x", "--kind", "measurement", "--ref", "../m.json"])
    assert code == 0 and capsys.readouterr().out.strip() == "stands"


def test_budget_fold_writes_usage_history(tmp_path):
    from flow_review import budget
    (tmp_path / ".flow-review").mkdir()
    run = tmp_path / "run1"
    run.mkdir()
    budget.record_usage(run, "web", "lens", 1234)
    assert cli.main(["--project", str(tmp_path), "budget", "fold", "--run", str(run)]) == 0
    assert (tmp_path / ".flow-review" / "usage_history.json").exists()
