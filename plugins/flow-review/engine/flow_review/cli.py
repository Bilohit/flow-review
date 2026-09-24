"""flow-review console entry point: `flow-review <verb> ...`.

This is the ONLY module in the flow_review package that touches stdout encoding. Every other
module is imported by both the CLI and by pytest collection; reconfiguring stdout as an
import-time side effect there means importing a module for its functions silently mutates the
test runner's own stdout. main() does it once, as the first statement, so every subcommand
(including a bare `--help`) gets a Windows-safe UTF-8 stdout, and nothing else needs to.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

def _run_migrate(args: argparse.Namespace) -> int:
    from flow_review import migrate as migratemod
    if args.path:
        path = Path(args.path)
    elif getattr(args, "project_root", None) is not None:
        path = Path(args.project_root) / ".flow-review" / "config.json"
    else:
        print("no .flow-review/ found", file=sys.stderr)
        return 1
    try:
        migratemod.migrate_file(path, quiet=args.quiet)
    except Exception as exc:  # noqa: BLE001 -- CLI boundary, report and exit, never traceback
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def _run_event(args: argparse.Namespace) -> int:
    from flow_review import events as eventsmod
    payload = {}
    if args.json is not None:
        try:
            payload = json.loads(args.json)
        except ValueError as exc:
            print(f"--json is not valid JSON: {exc}", file=sys.stderr)
            return 2
    for field in args.fields:
        if "=" not in field:
            print(f"expected key=value, got {field!r}", file=sys.stderr)
            return 2
        key, _, value = field.partition("=")
        payload[key] = value
    payload["type"] = args.type_
    eventsmod.append(Path(args.run_dir), payload)
    return 0


def _run_replay(args: argparse.Namespace) -> int:
    from flow_review import config as configmod
    from flow_review.web import replay as replay_mod
    project_root = args.project_root
    if project_root is None:
        print("no .flow-review/ found; run /flow-review setup first, or pass --project",
              file=sys.stderr)
        return 3
    try:
        cfg = configmod.load(Path(project_root) / ".flow-review" / "config.json")
    except Exception as exc:  # noqa: BLE001 -- CLI boundary: config error -> exit 3
        print(str(exc), file=sys.stderr)
        return 3
    if args.log is not None:
        if args.run_dir is None:
            print("--log requires --run DIR", file=sys.stderr)
            return 3
        return replay_mod.replay_log(cfg, Path(project_root), args.log, args.run_dir,
                                      variants=args.variants, mode=args.mode)
    return replay_mod.replay(cfg, Path(project_root), args.surface, args.flow,
                              variants=args.variants, mode=args.mode)


def _run_budget_check(args: argparse.Namespace) -> int:
    from flow_review import budget as budgetmod
    from flow_review import config as configmod
    project_root = args.project_root
    if project_root is None:
        print("no .flow-review/ found; run /flow-review setup first, or pass --project",
              file=sys.stderr)
        return 3
    try:
        cfg = configmod.load(Path(project_root) / ".flow-review" / "config.json")
    except Exception as exc:  # noqa: BLE001 -- CLI boundary: config error -> exit 3
        print(str(exc), file=sys.stderr)
        return 3
    cap = cfg.budget.get("cap_tokens")
    return budgetmod.check(Path(project_root), args.run_dir, args.next_role, cap)


def _run_setup_env(args: argparse.Namespace) -> int:
    from pathlib import Path as _Path
    from flow_review import envsetup as envsetupmod
    engine_path = _Path(args.engine_path) if args.engine_path else _Path(__file__).resolve().parent.parent
    try:
        # A fresh project has no .flow-review/ yet, so the walk-up finds nothing: fall back to cwd.
        project_dir = args.project_root if args.project_root is not None else _Path.cwd()
        envsetupmod.setup_env(project_dir, engine_path, extras=args.extras)
        envsetupmod.write_gitignore(project_dir / ".flow-review", commit_recordings=not args.no_commit_recordings)
    except Exception as exc:  # noqa: BLE001 -- CLI boundary
        print(str(exc), file=sys.stderr)
        return 1
    print(f"flow-review: environment ready at .flow-review/.venv (extras={args.extras})")
    return 0


def find_project_root(start: Path) -> Path | None:
    """Walk up from `start` (inclusive) to the nearest ancestor holding a `.flow-review/` dir.

    Returns the ancestor itself (the project root), never the `.flow-review/` path. `None`
    means no ancestor has one yet -- a fresh checkout before `setup-env`/first run.
    """
    current = Path(start).resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".flow-review").is_dir():
            return candidate
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="flow-review", description=__doc__)
    parser.add_argument(
        "--project", default=None,
        help="project root; defaults to walking up from cwd to the nearest .flow-review/",
    )
    # Also accepted after the verb (`flow-review migrate --project DIR`). SUPPRESS keeps a
    # subparser from overwriting a top-level --project with its own default.
    project_after_verb = argparse.ArgumentParser(add_help=False)
    project_after_verb.add_argument("--project", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="verb")
    setup_env_parser = sub.add_parser("setup-env", parents=[project_after_verb])
    setup_env_parser.add_argument("--extras", default="web")
    setup_env_parser.add_argument("--engine-path", default=None)
    setup_env_parser.add_argument("--no-commit-recordings", action="store_true")
    setup_env_parser.set_defaults(func=_run_setup_env)

    migrate_parser = sub.add_parser("migrate", parents=[project_after_verb])
    migrate_parser.add_argument("--path", default=None)
    migrate_parser.add_argument("--quiet", action="store_true")
    migrate_parser.set_defaults(func=_run_migrate)

    replay_parser = sub.add_parser(
        "replay", parents=[project_after_verb],
        help="replay recorded flows and check for regressions/divergences",
    )
    replay_parser.add_argument("--surface", default=None)
    replay_parser.add_argument("--flow", default=None)
    replay_parser.add_argument("--log", type=Path, default=None)
    replay_parser.add_argument("--run", dest="run_dir", type=Path, default=None)
    replay_parser.add_argument("--variants", action="store_true",
                                help="also run the device/persona variant set (B7/A-28)")
    replay_parser.add_argument("--mode", default="goal",
                                choices=["goal", "auto", "full", "quick"],
                                help="variant mode; quick runs no variants (A-12)")
    replay_parser.set_defaults(func=_run_replay)

    budget_parser = sub.add_parser("budget", parents=[project_after_verb])
    budget_sub = budget_parser.add_subparsers(dest="budget_cmd", required=True)
    budget_check_parser = budget_sub.add_parser("check", parents=[project_after_verb])
    budget_check_parser.add_argument("--run", required=True, dest="run_dir", type=Path)
    budget_check_parser.add_argument("--next", required=True, dest="next_role")
    budget_check_parser.add_argument("--surface", required=True)
    budget_check_parser.set_defaults(func=_run_budget_check)
    budget_fold_parser = budget_sub.add_parser("fold", parents=[project_after_verb])
    budget_fold_parser.add_argument("--run", required=True, dest="run_dir", type=Path)
    budget_fold_parser.set_defaults(func=_run_budget_fold)

    validate_parser = sub.add_parser("validate", parents=[project_after_verb])
    validate_sub = validate_parser.add_subparsers(dest="validate_cmd", required=True)
    p = validate_sub.add_parser("resolve", parents=[project_after_verb])
    p.add_argument("--run", required=True, dest="run_dir", type=Path)
    p.add_argument("--verdict", required=True, choices=["stands", "refuted"])
    p.add_argument("--reason", default=None)
    p.add_argument("--kind", default=None)
    p.add_argument("--ref", default=None)
    p.set_defaults(func=_run_validate_resolve)

    plan_parser = sub.add_parser("plan", parents=[project_after_verb])
    plan_parser.add_argument("--mode", required=True, choices=["goal", "auto", "full", "quick"])
    plan_parser.add_argument("--goal")
    plan_parser.add_argument("--record", action="store_true")
    plan_parser.add_argument("--skip", action="append", default=[])
    plan_parser.set_defaults(func=_run_plan)

    event_parser = sub.add_parser("event", parents=[project_after_verb])
    event_parser.add_argument("--run", required=True, dest="run_dir")
    event_parser.add_argument("--type", required=True, dest="type_")
    event_parser.add_argument("--json", default=None)
    event_parser.add_argument("fields", nargs="*")
    event_parser.set_defaults(func=_run_event)

    model_parser = sub.add_parser("model", parents=[project_after_verb])
    from flow_review import config as configmod
    model_parser.add_argument("role", choices=list(configmod.ROLES))
    model_parser.set_defaults(func=_run_model)

    triage_parser = sub.add_parser("triage", parents=[project_after_verb])
    triage_parser.add_argument("finding_id")
    triage_parser.add_argument("state")
    triage_parser.add_argument("--reason", default=None)
    triage_parser.set_defaults(func=_run_triage)

    drive_parser = sub.add_parser("drive")
    drive_parser.add_argument("drive_args", nargs=argparse.REMAINDER)
    drive_parser.set_defaults(func=_run_drive)

    serve_parser = sub.add_parser(
        "serve", parents=[project_after_verb],
        help="serve the live dashboard (or render a static snapshot with --static)",
    )
    serve_parser.add_argument("--run", required=True, dest="run_dir", type=Path)
    serve_parser.add_argument("--port", type=int, default=0)
    serve_parser.add_argument("--static", default=None, type=Path,
                               help="render one self-contained HTML snapshot to this path instead of serving")
    serve_parser.set_defaults(func=_run_serve)

    ledger_parser = sub.add_parser("ledger", parents=[project_after_verb])
    ledger_sub = ledger_parser.add_subparsers(dest="ledger_cmd", required=True)
    p = ledger_sub.add_parser("reconcile", parents=[project_after_verb])
    p.add_argument("--run", required=True, dest="run_dir", type=Path)
    p.add_argument("--alias", action="append", default=[], metavar="FINGERPRINT=ID")
    p.set_defaults(func=_run_ledger_reconcile)
    p = ledger_sub.add_parser("alias-candidates", parents=[project_after_verb])
    p.add_argument("--flow", required=True)
    p.add_argument("--rule", required=True)
    p.add_argument("--route", required=True)
    p.set_defaults(func=_run_ledger_alias_candidates)
    p = ledger_sub.add_parser("record-miss", parents=[project_after_verb])
    p.add_argument("--function", required=True)
    p.add_argument("--run", required=True, dest="run_dir", type=Path)
    p.set_defaults(func=_run_ledger_record_miss)
    p = ledger_sub.add_parser("suppressions", parents=[project_after_verb])
    p.add_argument("--rule", required=True)
    p.set_defaults(func=_run_ledger_suppressions)

    manifest_parser = sub.add_parser("manifest", parents=[project_after_verb])
    manifest_sub = manifest_parser.add_subparsers(dest="manifest_cmd", required=True)
    p = manifest_sub.add_parser("apply-learnings", parents=[project_after_verb])
    p.add_argument("--path", required=True, type=Path)
    p.add_argument("--hash", required=True, dest="recorded_hash")
    p.add_argument("--learning", action="append", default=[])
    p.set_defaults(func=_run_manifest_apply_learnings)

    return parser


def _run_budget_fold(args: argparse.Namespace) -> int:
    from flow_review import budget as budgetmod
    if args.project_root is None:
        print("no .flow-review/ found; run /flow-review setup first, or pass --project",
              file=sys.stderr)
        return 3
    budgetmod.fold_history(Path(args.project_root), args.run_dir)
    return 0


def _run_validate_resolve(args: argparse.Namespace) -> int:
    """Prints the final verdict. Invalid refutation evidence means the finding stands (C5), so
    the orchestrator never has to catch a Python exception."""
    from flow_review import validate as validatemod
    evidence = None
    if args.kind is not None or args.ref is not None:
        evidence = {"kind": args.kind, "ref": args.ref}
    try:
        verdict, _ = validatemod.resolve_after_verifier(
            {}, args.verdict, args.reason, evidence, args.run_dir)
    except ValueError as exc:
        print(f"refutation rejected: {exc}", file=sys.stderr)
        verdict = validatemod.Verdict.STANDS
    print(verdict.value)
    return 0


def _ledger_path(args: argparse.Namespace) -> Path | None:
    if args.project_root is None:
        print("no .flow-review/ found; run /flow-review setup first, or pass --project",
              file=sys.stderr)
        return None
    return Path(args.project_root) / ".flow-review" / "findings.json"


def _run_ledger_reconcile(args: argparse.Namespace) -> int:
    from flow_review import ledger as ledgermod
    path = _ledger_path(args)
    if path is None:
        return 3
    findings: list[dict] = []
    withdrawn: set[str] = set()
    flows_run: set[str] = set()
    log = Path(args.run_dir) / "events.jsonl"
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("type") == "finding":
                findings.append(event)
                flows_run.add(event["flow_id"])
            elif event.get("type") == "withdraw":
                withdrawn.add(event.get("finding_id"))
            elif event.get("type") == "step" and event.get("step") == "flow-begin":
                flows_run.add(event["flow_id"])
    findings = [f for f in findings if f.get("id") not in withdrawn]
    aliases = dict(a.split("=", 1) for a in args.alias if "=" in a)
    ledger_ = ledgermod.reconcile(ledgermod.load(path), findings, flows_run,
                                  Path(args.run_dir).name, alias_decisions=aliases)
    ledgermod.save(ledger_, path)
    return 0


def _run_ledger_alias_candidates(args: argparse.Namespace) -> int:
    from dataclasses import asdict
    from flow_review import ledger as ledgermod
    path = _ledger_path(args)
    if path is None:
        return 3
    cands = ledgermod.find_alias_candidates(ledgermod.load(path), args.flow, args.rule, args.route)
    print(json.dumps([asdict(c) for c in cands]))
    return 0


def _run_ledger_record_miss(args: argparse.Namespace) -> int:
    from flow_review import ledger as ledgermod
    path = _ledger_path(args)
    if path is None:
        return 3
    ledger_ = ledgermod.load(path)
    count = ledgermod.record_miss(ledger_, args.function, Path(args.run_dir).name)
    ledgermod.save(ledger_, path)
    print(count)
    return 0


def _run_ledger_suppressions(args: argparse.Namespace) -> int:
    from flow_review import ledger as ledgermod
    path = _ledger_path(args)
    if path is None:
        return 3
    print(json.dumps(ledgermod.suppressions_for(ledgermod.load(path), args.rule)))
    return 0


def _run_manifest_apply_learnings(args: argparse.Namespace) -> int:
    from flow_review import manifest as manifestmod
    try:
        print(manifestmod.apply_learnings(args.path, args.recorded_hash, args.learning))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def _run_triage(args: argparse.Namespace) -> int:
    from flow_review import triage as triagemod
    project_root = args.project_root
    if project_root is None:
        print("no .flow-review/ found; run /flow-review setup first, or pass --project",
              file=sys.stderr)
        return 3
    ledger_path = Path(project_root) / ".flow-review" / "findings.json"
    try:
        entry = triagemod.apply(ledger_path, args.finding_id, args.state, reason=args.reason)
    except (ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"{entry.id}: {entry.state}")
    return 0


def _run_model(args: argparse.Namespace) -> int:
    from flow_review import config as configmod
    project_root = args.project_root
    if project_root is None:
        print("no .flow-review/ found; run /flow-review setup first, or pass --project",
              file=sys.stderr)
        return 3
    try:
        cfg = configmod.load(Path(project_root) / ".flow-review" / "config.json")
    except Exception as exc:  # noqa: BLE001 -- CLI boundary, report and exit, never traceback
        print(str(exc), file=sys.stderr)
        return 3
    print(configmod.resolve_model(cfg, args.role))
    return 0


def _run_serve(args: argparse.Namespace) -> int:
    from flow_review import config as configmod
    project_root = args.project_root
    if project_root is None:
        print("no .flow-review/ found; run /flow-review setup first, or pass --project",
              file=sys.stderr)
        return 3
    try:
        cfg = configmod.load(Path(project_root) / ".flow-review" / "config.json")
    except Exception as exc:  # noqa: BLE001 -- CLI boundary, report and exit, never traceback
        print(str(exc), file=sys.stderr)
        return 3
    if args.static is not None:
        from flow_review.dashboard import static as staticmod
        staticmod.render_static(Path(project_root), args.run_dir, cfg, args.static)
        return 0
    from flow_review.dashboard import serve as servemod
    servemod.serve(Path(project_root), args.run_dir, cfg, args.port)
    return 0


def _run_drive(args: argparse.Namespace) -> int:
    from flow_review.web import drive
    return drive.main(args.drive_args, project_root=args.project_root)


def _run_plan(args: argparse.Namespace) -> int:
    from flow_review import plan as plan_mod
    project_root = args.project_root
    if project_root is None:
        print("no .flow-review/ found; run /flow-review setup first, or pass --project",
              file=sys.stderr)
        return 3
    try:
        result = plan_mod.plan(project_root, mode=args.mode, goal=args.goal,
                                record=args.record, skip=args.skip)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 0


def _resolve_project_root(args: argparse.Namespace) -> None:
    """Set args.project_root from --project, or by walking up from cwd. Mutates args in place
    so every subcommand function (present and future) can read args.project_root directly,
    per Canonical Interfaces' "Project root" entry."""
    if getattr(args, "project", None):
        args.project_root = Path(args.project).resolve()
    else:
        args.project_root = find_project_root(Path.cwd())


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    if getattr(args, "verb", None) is None:
        parser.print_usage(sys.stderr)
        return 2
    _resolve_project_root(args)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
