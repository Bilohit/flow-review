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

# One entry per verb this milestone plan adds a subcommand for. Each later task (A3 migrate,
# A4 event, A10 setup-env, B3 replay, B9 plan, C1 model, C6 triage, B8 budget, E1 serve,
# A5 ledger) replaces exactly one function here with real behaviour; the parser wiring does not
# change.
_STUB_VERBS = (
    "prove", "ledger",
)


def _stub(verb: str):
    def _run(args: argparse.Namespace) -> int:
        print(f"{verb}: not yet implemented", file=sys.stderr)
        return 2
    return _run


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
        return replay_mod.replay_log(cfg, Path(project_root), args.log, args.run_dir)
    return replay_mod.replay(cfg, Path(project_root), args.surface, args.flow)


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
    for verb in _STUB_VERBS:
        verb_parser = sub.add_parser(verb, parents=[project_after_verb])
        verb_parser.set_defaults(func=_stub(verb))
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
    replay_parser.set_defaults(func=_run_replay)

    budget_parser = sub.add_parser("budget", parents=[project_after_verb])
    budget_sub = budget_parser.add_subparsers(dest="budget_cmd", required=True)
    budget_check_parser = budget_sub.add_parser("check", parents=[project_after_verb])
    budget_check_parser.add_argument("--run", required=True, dest="run_dir", type=Path)
    budget_check_parser.add_argument("--next", required=True, dest="next_role")
    budget_check_parser.add_argument("--surface", required=True)
    budget_check_parser.set_defaults(func=_run_budget_check)

    plan_parser = sub.add_parser("plan", parents=[project_after_verb])
    plan_parser.add_argument("--mode", required=True, choices=["goal", "auto", "full", "quick"])
    plan_parser.add_argument("--goal")
    plan_parser.add_argument("--record", action="store_true")
    plan_parser.add_argument("--skip", action="append", default=[])
    plan_parser.add_argument("--json", action="store_true")  # M1 always prints JSON; flag kept
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

    return parser


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
