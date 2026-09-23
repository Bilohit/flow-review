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
    "prove", "plan", "replay", "serve", "triage", "ledger",
    "budget", "model",
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

    event_parser = sub.add_parser("event", parents=[project_after_verb])
    event_parser.add_argument("--run", required=True, dest="run_dir")
    event_parser.add_argument("--type", required=True, dest="type_")
    event_parser.add_argument("--json", default=None)
    event_parser.add_argument("fields", nargs="*")
    event_parser.set_defaults(func=_run_event)

    return parser


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
