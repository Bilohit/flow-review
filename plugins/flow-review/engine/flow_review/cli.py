"""flow-review console entry point: `flow-review <verb> ...`.

This is the ONLY module in the flow_review package that touches stdout encoding. Every other
module is imported by both the CLI and by pytest collection; reconfiguring stdout as an
import-time side effect there means importing a module for its functions silently mutates the
test runner's own stdout. main() does it once, as the first statement, so every subcommand
(including a bare `--help`) gets a Windows-safe UTF-8 stdout, and nothing else needs to.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# One entry per verb this milestone plan adds a subcommand for. Each later task (A3 migrate,
# A4 event, A10 setup-env, B3 replay, B9 plan, C1 model, C6 triage, B8 budget, E1 serve,
# A5 ledger) replaces exactly one function here with real behaviour; the parser wiring does not
# change.
_STUB_VERBS = (
    "setup-env", "prove", "plan", "event", "replay", "serve", "triage", "ledger",
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
    sub = parser.add_subparsers(dest="verb")
    for verb in _STUB_VERBS:
        verb_parser = sub.add_parser(verb)
        verb_parser.set_defaults(func=_stub(verb))
    migrate_parser = sub.add_parser("migrate")
    migrate_parser.add_argument("--path", default=None)
    migrate_parser.add_argument("--quiet", action="store_true")
    migrate_parser.set_defaults(func=_run_migrate)
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
