# flow-review M5 (watch + planted-bug benchmark) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. Each task names its executor model; dispatch it pinned to that model, never `inherit`. Opus reviews every checkpoint.

**Goal:** Give flow-review a zero-LLM `watch` mode that re-replays affected surfaces on file change, and a planted-bug benchmark (`flow-review bench`) that measures recall and token cost per real finding across model profiles, recalibrating the budget priors and confirming the A-8/A-9 thresholds with real data.

**Architecture:** Two new engine modules, `watch.py` and `bench.py`, sit beside `web/replay.py` and `budget.py` and reuse them unchanged: `watch` calls the existing `replay(cfg, project_root, surface_id=...)` entry point on a debounced mtime-poll loop; `bench` shells out to the headless `claude -p "/flow-review full"` CLI per fixture per profile (never in-process, never during tests) and reads back `.flow-review/findings.json` and `events.jsonl` the same way the dashboard does. Neither module calls an LLM API itself; `bench` only launches `claude` as a subprocess and the tests never let that subprocess run (`--dry-run` + a hand-written `findings.json`).

**Tech Stack:** Python >=3.10, pytest, stdlib only (`os.scandir`, `subprocess`, `statistics`, `json`, `fnmatch`/`Path.match`). No new dependency.

**Spec:** `docs/superpowers/specs/2026-09-23-flow-review-v2-design.md` §12 (M5), §13. Decisions in Appendix A (this plan extends the M2 plan's A-35..A-47; new rows A-65..A-69 below) override the spec where they differ.

## Global Constraints

- The engine never calls an LLM API; `bench` only shells out to `claude -p` as an opt-in, human-triggered subprocess, never from a test.
- flow-review never edits product code.
- Every subagent invoked by `bench`'s `claude -p` runs is pinned to the profile under test; `bench` itself dispatches no subagent directly.
- Secrets are never written to events, the ledger, reports, or `docs/benchmarks/*.json`.
- `watch` never prompts, never blocks on input, and exits 0 on Ctrl-C (`KeyboardInterrupt`).
- No test spends LLM tokens: `bench` tests use `--dry-run` (prints the `claude -p` commands, writes the config, never dispatches) and a hand-written `.flow-review/findings.json` / `events.jsonl` fixture to test the recall/cost math.
- Dashboard is untouched; no task loads impeccable or dataviz.
- Tests are colocated `test_*.py` next to the module, run with `python -m pytest -q -m "web or not web"` from the repo root.
- TDD for every code task: failing test -> run it and see it fail -> minimal implementation -> run it and see it pass -> commit.
- Banned names (never write them): `Ledger.load`, `.upsert(`, `runs_for`, `"severity"`, `viewports`, `refuted_reason`, `lens_or_rule`, `resolve_project_root(`, `envsetup.redact`, `add_suppression`, `_recordings_root`.

## File Structure (target)

```
plugins/flow-review/engine/flow_review/
  watch.py                 # NEW: _snapshot, _changed, _n_changed, watch()
  test_watch.py            # NEW
  bench.py                 # NEW: run, compare, priors_from, _match_planted, _dispatch
  test_bench.py            # NEW
  config.py                # + watch block, _WATCH_KEYS, _CONFIG_KEYS entry
  test_config.py           # APPEND: watch-block tests
  cli.py                   # + `watch` and `bench` verbs
  test_cli.py              # APPEND: watch/bench verb coverage
  web/measure.py           # + RULE_IDS constant (T3)
  api/measure.py           # + RULE_IDS constant (T3)
  shell/measure.py         # + RULE_IDS constant (T3)
  mobile/measure.py        # + RULE_IDS constant (T3)
plugins/flow-review/engine/fixtures/
  webapp/planted.json      # CREATED by T3 from the M1 fixture's known bugs
  tauriapp/planted.json    # assumed to exist post-M2 per shared brief; T3 audits it
  mobileapp/planted.json   # assumed to exist post-M3 per shared brief; T3 audits it
  apiapp/planted.json      # assumed to exist post-M4 per shared brief; T3 audits it
  cliapp/planted.json      # assumed to exist post-M4 per shared brief; T3 audits it
  test_planted.py          # NEW: rule-id cross-check at fixtures/ root
docs/benchmarks/
  README.md                # NEW
  YYYY-MM-DD.json           # written by real bench runs, not by tests
README.md                  # + watch usage, + release-step bench mention
plugins/flow-review/skills/flow-review/references/
  goals.md                 # + A-8/A-9 recalibration paragraph
  setup.md                 # + one line on watch
```

## Task Skeleton

| id | goal (one line) | deps | wave | owner | exec |
|---|---|---|---|---|---|
| T1 | Config `watch` block + `watch.py` (`_snapshot`, `_changed`, `watch`) with tests using a tmp project and an injected fake replay | — | 1 | D1 | sonnet |
| T2 | `flow-review watch` CLI verb + README section; `test_cli_parity` green | T1 | 2 | D1 | haiku |
| T3 | `planted.json` audit across all fixtures + `fixtures/test_planted.py` rule-id cross-check | — | 1 | D2 | haiku |
| T4 | `bench.py::run` with `--dry-run`, fixed-port fixture server start/stop, config writer, ledger-vs-planted matching, JSON writer | T3 | 2 | D2 | sonnet |
| T5 | `flow-review bench` CLI (`run`, `compare`, `priors`) | T2, T4 | 3 | D2 | sonnet |
| T6 | Bench observability for A-8/A-9 (discoverability + path-ratio fields) + `goals.md` recalibration paragraph | T5 | 4 | D3 | sonnet |
| T7 | Docs: `docs/benchmarks/README.md`, README release-step section, `setup.md` watch line | T2, T6 | 5 | D3 | haiku |
| CP1 | M5 checkpoint | T1-T7 | 6 | — | opus |

## Lanes

Phase 1: lane A = T1, lane B = T3 (disjoint files: `config.py`/`watch.py` vs `fixtures/*/planted.json` + `fixtures/test_planted.py`).
Phase 2: lane A = T2 (depends on T1), lane B = T4 (depends on T3). Disjoint: `cli.py`+README vs `bench.py`.
Phase 3: T5 alone (`cli.py` again — must wait for T2 to land first to avoid a `cli.py` merge conflict; T5's wave starts after T2 finishes even though its listed dep is only T4).
Phase 4: T6 alone.
Phase 5: T7 alone.
Lanes merge here: after Phase 2, `cli.py` and README are stable for T5 and T7 to extend serially.

## Canonical Interfaces

Copied from shared context (binding, reused verbatim):

- **Watch**: `flow-review watch [--surface ID] [--interval-s 1]` in `watch.py::watch(cfg, project_root, interval_s, once: bool = False, baselines: dict | None = None) -> int`; `once=True` does one poll+replay cycle (for tests); `baselines` is the caller-owned snapshot dict, so two `once=True` calls sharing one dict see each other's edits.
- **Bench**: `bench.py::run(project_root, profiles, surfaces, out_dir) -> Path` writes `docs/benchmarks/<date>.json` as `{profile: {surface: {recall, true_findings, false_findings, tokens, tokens_per_true}}}`; `bench.py::priors_from(history_paths) -> dict[str, int]` prints a `PRIORS` dict to paste into `budget.py`. Fixture truth: `fixtures/<app>/planted.json` = `[{"rule": "contrast.aa", "route": "/", "locator": "..."}, ...]`.
- **Run id** (M2 debt, reused by `watch` and `bench`): `events.new_run_id() -> str` = `now_iso().replace(":", "-")`.
- **Replay** (M1, reused unchanged by `watch`): `flow-review replay [--surface ID] [--flow ID]` in `web/replay.py::replay(cfg, project_root, surface_id=None, flow_id=None, variants=False, mode="goal", update_baselines=False) -> int`; exit 0 clean, 1 regression, 2 divergence, 3 config/env error.
- **Budget** (M1, read by `bench`): `budget.used(run_dir) -> int`; `budget.PRIORS_TOKENS_PER_UNIT: dict[str, int]` (the dict `priors_from` output is meant to replace).
- **Ledger** (M1, read by `bench`): `ledger.load(path) -> Ledger`; `Ledger.findings: dict[str, LedgerEntry]`; `Ledger.discoverability_misses: dict[str, list[str]]`; `LedgerEntry(id, fingerprint, surface_id, flow_id, rule, route, locator, sev, text, evidence, disposition, state, runs_seen, first_run, last_run, aliases, reason)`.
- **Config** (M1, extended by T1): `config.load(path) -> Config`, `config.save(cfg, path)`; `Config` gains `watch: dict = {"ignore": []}`; unknown-key errors (`ConfigKeyError`) apply to the `watch` block the same as any other block.

New interfaces this plan defines (none needed beyond the ones above; nothing invented outside shared.md).

## Tasks

### Task T1: Config `watch` block + `watch.py`

**Executor:** sonnet · **Depends:** — · **Wave:** 1
**Files:** `plugins/flow-review/engine/flow_review/config.py`, `plugins/flow-review/engine/flow_review/test_config.py`, `plugins/flow-review/engine/flow_review/watch.py` (new), `plugins/flow-review/engine/flow_review/test_watch.py` (new)
**Interfaces:** Consumes `config.Config`, `config._check_keys`, `config._CONFIG_KEYS`, `drift.runnable_surfaces` (from M1). Produces `Config.watch: dict`, `watch.py::_snapshot(root: Path, ignore: list[str]) -> dict[str, float]`, `watch.py::_changed(before: dict, after: dict) -> bool`, `watch.py::watch(cfg, project_root, interval_s=1.0, once=False, baselines: dict | None = None) -> int`.
**Ponytail rung:** 2 (stdlib `os.scandir` mtime polling, no `watchdog` dependency).

- [ ] Write the failing config test in `test_config.py`:

```python
def test_watch_block_defaults_and_rejects_unknown_key(tmp_path):
    from flow_review import config as configmod

    cfg = configmod.Config(schema_version=2, generator_version="test")
    assert cfg.watch == {"ignore": []}

    path = tmp_path / "config.json"
    raw = {
        "schema_version": 2,
        "generator_version": "test",
        "surfaces": [],
        "watch": {"ignore": ["*.log"], "bogus": 1},
    }
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(configmod.ConfigKeyError):
        configmod.load(path)


def test_watch_block_round_trips(tmp_path):
    from flow_review import config as configmod

    cfg = configmod.Config(
        schema_version=2, generator_version="test",
        watch={"ignore": ["*.log", "dist/**"]},
    )
    path = tmp_path / "config.json"
    configmod.save(cfg, path)
    loaded = configmod.load(path)
    assert loaded.watch == {"ignore": ["*.log", "dist/**"]}
```

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/test_config.py -k watch_block`. Expected FAIL: `AttributeError: 'Config' object has no attribute 'watch'` (and `TypeError` for the unexpected `watch=` kwarg).
- [ ] Implement in `config.py`:
  - Add `"watch"` to `_CONFIG_KEYS`.
  - Add `_WATCH_KEYS = {"ignore"}` near `_PRECONDITION_KEYS`.
  - Add a `watch: dict = field(default_factory=lambda: {"ignore": []})` field to `Config` (after `flows_hash`).
  - In `_validate` (or a new `_validate_watch(cfg)` called from it), run `_check_keys(cfg.watch, _WATCH_KEYS, "watch")` and assert `isinstance(cfg.watch.get("ignore", []), list)`, raising `ValueError("watch.ignore must be a list of glob strings")` otherwise.
  - In the raw-loading path (`load`'s dict-to-`Config` construction, alongside where `budget`/`role_overrides` defaults are filled), read `raw.get("watch", {"ignore": []})` the same way other optional blocks are read, and pass it into `Config(...)`.
- [ ] Run the same pytest command. Expected PASS.
- [ ] Write the failing watch test in `test_watch.py`:

```python
"""Tests for flow_review.watch: file-change -> surface -> replay mapping (A-42)."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from flow_review import config as configmod
from flow_review import watch as watchmod


def _cfg(tmp_path: Path) -> configmod.Config:
    surface = configmod.Surface(
        id="webapp", name="webapp", kind="ui", driver="playwright",
        launch="true", cwd=str(tmp_path / "app"),
        options={"base_url": "http://localhost:9"},
    )
    return configmod.Config(schema_version=2, generator_version="test", surfaces=[surface])


def test_snapshot_ignores_flow_review_dir_and_configured_globs(tmp_path):
    app = tmp_path / "app"
    (app / ".flow-review").mkdir(parents=True)
    (app / ".flow-review" / "config.json").write_text("{}", encoding="utf-8")
    (app / "src").mkdir()
    (app / "src" / "index.js").write_text("1", encoding="utf-8")
    (app / "debug.log").write_text("x", encoding="utf-8")

    snap = watchmod._snapshot(app, ignore=["*.log"])

    assert any(p.endswith("index.js") for p in snap)
    assert not any(".flow-review" in p for p in snap)
    assert not any(p.endswith("debug.log") for p in snap)


def test_changed_detects_mtime_or_key_set_difference():
    before = {"a": 1.0, "b": 2.0}
    assert watchmod._changed(before, {"a": 1.0, "b": 2.0}) is False
    assert watchmod._changed(before, {"a": 5.0, "b": 2.0}) is True
    assert watchmod._changed(before, {"a": 1.0}) is True


def test_watch_once_calls_replay_only_for_changed_surface(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    (tmp_path / "app").mkdir(exist_ok=True)
    (tmp_path / "app" / "index.js").write_text("v1", encoding="utf-8")

    calls = []

    def fake_replay(cfg_, project_root, surface_id=None, **kwargs):
        calls.append(surface_id)
        return 0

    monkeypatch.setattr(watchmod, "_replay", fake_replay)
    monkeypatch.setattr(watchmod, "_DEBOUNCE_SLEEP", lambda: None)

    # once=True reads and updates the SAME baselines dict across two calls, exactly the way
    # the CLI's own loop (which owns one long-lived dict) uses it -- the module never keeps
    # hidden module-level state.
    baselines: dict = {}

    # First poll establishes the baseline; nothing changed yet.
    code = watchmod.watch(cfg, tmp_path, interval_s=0.01, once=True, baselines=baselines)
    assert code == 0
    assert calls == []

    (tmp_path / "app" / "index.js").write_text("v2", encoding="utf-8")
    time.sleep(0.02)
    code = watchmod.watch(cfg, tmp_path, interval_s=0.01, once=True, baselines=baselines)
    assert code == 0
    assert calls == ["webapp"]
```

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/test_watch.py`. Expected FAIL: `ModuleNotFoundError: No module named 'flow_review.watch'`.
- [ ] Implement `watch.py`:

```python
"""`flow-review watch`: map a changed file under a surface's cwd to that surface and re-replay
it, deterministically and without ever prompting or calling an LLM (A-42).

State is process-local: each `watch()` call keeps its own baseline snapshot across polls (or,
for `once=True`, across two `watch()` calls made by the caller, per the CLI's own loop). No
watchdog dependency -- `os.scandir` mtime polling is the whole implementation (ponytail rung 2).
"""
from __future__ import annotations

import time
from pathlib import Path

from flow_review.web.replay import replay as _replay  # rebindable for tests

# A-42: only these three are always ignored; anything else goes through `watch.ignore`.
_ALWAYS_IGNORED = (".flow-review", "node_modules", ".git")

# Rebindable for tests, so a debounce loop iteration costs nothing under pytest.
_DEBOUNCE_SLEEP = lambda: time.sleep(2.0)  # noqa: E731 -- rebindable hook, not a real lambda-as-def

# Ponytail: a hard iteration cap bounds the debounce wait instead of adding a deadline/timeout
# config knob nobody asked for; 10 * 2s = 20s is already generous for a save-and-settle edit.
_MAX_DEBOUNCE_ITERATIONS = 10


def _snapshot(root: Path, ignore: list[str]) -> dict[str, float]:
    root = Path(root)
    out: dict[str, float] = {}
    if not root.is_dir():
        return out
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(os_scandir_safe(current))
        except OSError:
            continue
        for entry in entries:
            rel = Path(entry.path).relative_to(root)
            if entry.is_dir(follow_symlinks=False):
                if entry.name in _ALWAYS_IGNORED:
                    continue
                if any(rel.match(pattern) for pattern in ignore):
                    continue
                stack.append(Path(entry.path))
            else:
                if any(rel.match(pattern) for pattern in ignore):
                    continue
                try:
                    out[str(rel)] = entry.stat().st_mtime
                except OSError:
                    continue
    return out


def os_scandir_safe(path: Path):
    import os
    return os.scandir(path)


def _changed(before: dict[str, float], after: dict[str, float]) -> bool:
    return before != after


def _n_changed(before: dict[str, float], after: dict[str, float]) -> int:
    """Symmetric difference of paths, plus paths present in both with a different mtime --
    the count a human editing files would expect to see (A-65)."""
    added_or_removed = set(before) ^ set(after)
    modified = {k for k in before if k in after and before[k] != after[k]}
    return len(added_or_removed | modified)


def watch(cfg, project_root: Path, interval_s: float = 1.0, once: bool = False,
          baselines: dict | None = None) -> int:
    """`baselines` is the caller-owned snapshot-per-surface dict. The CLI's own loop creates one
    dict and passes it to every `watch()` call it makes (including the repeated `once=True`
    calls a test drives), so state lives with the caller, never as hidden module globals."""
    from flow_review import drift

    project_root = Path(project_root)
    surfaces = drift.runnable_surfaces(cfg)
    ignore = cfg.watch.get("ignore", [])
    if baselines is None:
        baselines = {}
    for surface in surfaces:
        baselines.setdefault(surface.id, _snapshot(Path(project_root) / surface.cwd, ignore))

    def poll_once() -> int:
        exit_code = 0
        for surface in surfaces:
            surface_dir = Path(project_root) / surface.cwd
            after = _snapshot(surface_dir, ignore)
            before = baselines[surface.id]
            if not _changed(before, after):
                continue
            # Debounce: wait until no further change for one interval, capped at
            # _MAX_DEBOUNCE_ITERATIONS so a continuously-touched file can't hang watch forever.
            stable = after
            for _ in range(_MAX_DEBOUNCE_ITERATIONS):
                _DEBOUNCE_SLEEP()
                latest = _snapshot(surface_dir, ignore)
                if latest == stable:
                    break
                stable = latest
            n_changed = _n_changed(before, stable)
            baselines[surface.id] = stable
            code = _replay(cfg, project_root, surface_id=surface.id)
            print(f"watch: {surface.id} {n_changed} files changed -> replay exit {code}")
            exit_code = code
        return exit_code

    if once:
        return poll_once()

    try:
        while True:
            code = poll_once()
            time.sleep(interval_s)
    except KeyboardInterrupt:
        return 0
    return code
```

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/test_watch.py plugins/flow-review/engine/flow_review/test_config.py -k watch`. Expected PASS.
- [ ] Verify: `python -m pytest -q -m "web or not web"`.
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/config.py plugins/flow-review/engine/flow_review/test_config.py plugins/flow-review/engine/flow_review/watch.py plugins/flow-review/engine/flow_review/test_watch.py && git commit -m "feat(watch): config watch block + file-change -> replay mapping (A-42)"`

### Task T2: `flow-review watch` CLI verb + README

**Executor:** haiku · **Depends:** T1 · **Wave:** 2
**Files:** `plugins/flow-review/engine/flow_review/cli.py`, `plugins/flow-review/engine/flow_review/test_cli.py`, `README.md`
**Interfaces:** Consumes `watch.py::watch`, `config.load`. Produces the `flow-review watch` argparse subcommand.
**Ponytail rung:** 5 (one dispatch function, mirrors `_run_replay`'s shape).

- [ ] Add the failing case to `test_cli.py` (extends the existing `test_cli_parity` style test that checks every documented verb has a parser entry and every parser entry is documented):

```python
def test_watch_verb_is_registered_and_documented():
    from flow_review import cli

    parser = cli.build_parser()
    sub_actions = [a for a in parser._subparsers._group_actions if a.dest == "verb"]
    verbs = set(sub_actions[0].choices)
    assert "watch" in verbs

    readme = Path(__file__).resolve().parents[4] / "README.md"
    assert "flow-review watch" in readme.read_text(encoding="utf-8")
```

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/test_cli.py -k watch_verb`. Expected FAIL: `AssertionError` (verb not in `verbs`, or file text missing).
- [ ] Implement in `cli.py`: add near `replay_parser`:

```python
    watch_parser = sub.add_parser(
        "watch", parents=[project_after_verb],
        help="poll for file changes and replay the affected surface (A-42, never prompts)",
    )
    watch_parser.add_argument("--surface", default=None)
    watch_parser.add_argument("--interval-s", type=float, default=1.0, dest="interval_s")
    watch_parser.set_defaults(func=_run_watch)
```

  and add the handler function near `_run_replay`:

```python
def _run_watch(args: argparse.Namespace) -> int:
    from flow_review import config as configmod
    from flow_review import watch as watchmod
    project_root = args.project_root
    if project_root is None:
        print("no .flow-review/ found; run /flow-review setup first, or pass --project",
              file=sys.stderr)
        return 3
    try:
        cfg = configmod.load(Path(project_root) / ".flow-review" / "config.json")
    except Exception as exc:  # noqa: BLE001 -- CLI boundary
        print(str(exc), file=sys.stderr)
        return 3
    if args.surface is not None:
        cfg.surfaces = [s for s in cfg.surfaces if s.id == args.surface]
    return watchmod.watch(cfg, project_root, interval_s=args.interval_s)
```

- [ ] Add a "Watch" section to `README.md` (near the existing "Replay" section), stating: `flow-review watch` polls every `--interval-s` (default 1) for file changes under each runnable surface's `cwd`, debounces 2s, and replays the affected surface via the same exit codes as `flow-review replay`; it never prompts and never spends tokens; `flow-review replay` remains the CI verb, `flow-review watch` is for a dev terminal left open while editing.
- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/test_cli.py`. Expected PASS.
- [ ] Verify: `python -m pytest -q -m "web or not web"`.
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/cli.py plugins/flow-review/engine/flow_review/test_cli.py README.md && git commit -m "feat(cli): flow-review watch verb"`

### Task T3: `planted.json` audit across fixtures

**Executor:** haiku · **Depends:** — · **Wave:** 1
**Files:** `plugins/flow-review/engine/fixtures/webapp/planted.json`, `plugins/flow-review/engine/fixtures/tauriapp/planted.json`, `plugins/flow-review/engine/fixtures/mobileapp/planted.json`, `plugins/flow-review/engine/fixtures/apiapp/planted.json`, `plugins/flow-review/engine/fixtures/cliapp/planted.json`, `plugins/flow-review/engine/fixtures/test_planted.py` (new), `plugins/flow-review/engine/flow_review/web/measure.py`, `plugins/flow-review/engine/flow_review/api/measure.py`, `plugins/flow-review/engine/flow_review/shell/measure.py`, `plugins/flow-review/engine/flow_review/mobile/measure.py`
**Interfaces:** Consumes rule ids collected by import from `flow_review.web.measure`, `flow_review.api.measure`, `flow_review.shell.measure`, `flow_review.mobile.measure` (each module's rule-emitting functions; the test collects the string literals those modules can return, via a `RULE_IDS` module constant each measure module is given here). Produces one shared shape for `planted.json`: `[{"rule": str, "route": str, "locator": str}, ...]`.
**Ponytail rung:** 1 (data file audit; no new abstraction).

- [ ] Write the failing test `plugins/flow-review/engine/fixtures/test_planted.py`:

```python
"""Every fixture's planted.json names a rule the engine actually emits, and a route that is
already in ledger.route_template() form (no raw numeric/UUID segments) -- otherwise bench's
(rule, route_template) matching in T4 silently never matches a planted bug."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_ROOT = Path(__file__).resolve().parent
APPS = ["webapp", "tauriapp", "mobileapp", "apiapp", "cliapp"]


def _all_rule_ids() -> set[str]:
    from flow_review.web import measure as web_measure
    from flow_review.api import measure as api_measure
    from flow_review.shell import measure as shell_measure
    from flow_review.mobile import measure as mobile_measure

    ids: set[str] = set()
    for mod in (web_measure, api_measure, shell_measure, mobile_measure):
        ids |= set(getattr(mod, "RULE_IDS"))
    return ids


@pytest.mark.parametrize("app", APPS)
def test_planted_json_shape_and_rule_ids(app):
    from flow_review import ledger

    path = FIXTURES_ROOT / app / "planted.json"
    assert path.exists(), f"{app}/planted.json is missing"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list) and data, f"{app}/planted.json must be a non-empty list"

    known_rules = _all_rule_ids()
    for entry in data:
        assert set(entry) == {"rule", "route", "locator"}, entry
        assert entry["rule"] in known_rules, f"{app}: unknown rule {entry['rule']!r}"
        assert entry["route"] == ledger.route_template(entry["route"]), (
            f"{app}: route {entry['route']!r} is not already templated"
        )
```

- [ ] Run `python -m pytest -q plugins/flow-review/engine/fixtures/test_planted.py`. Expected FAIL: `ModuleNotFoundError` or `AttributeError: module 'flow_review.web.measure' has no attribute 'RULE_IDS'` (and `webapp/planted.json` not existing yet).
- [ ] **Create `plugins/flow-review/engine/fixtures/webapp/planted.json` from the M1 fixture's own known bugs** (read `plugins/flow-review/engine/fixtures/webapp/README.md` and `plugins/flow-review/engine/fixtures/webapp/test_fixture.py` first — do not guess at routes or locators). The README documents: a username/password sign-in form (`#login-form`), a primary "Continue" button (`#cta-button`), two buttons sharing one spot ("Save" `#save-button` / "Cancel" `#cancel-button`, i.e. an overlap), a "Help" button (`#help-button`) that does nothing when clicked, and "Load data" (`#load-button`) which fetches `/api/fail`, always HTTP 500. The M1 plan's R12 checkpoint (line ~12203) additionally confirms this fixture files `contrast.aa`, `token.color`, `rect.overlap`, `rect.target-size` on a normal run. Write:

```json
[
  {"rule": "contrast.aa", "route": "/", "locator": "css:.muted-note"},
  {"rule": "token.color", "route": "/", "locator": "css:#cta-button"},
  {"rule": "rect.overlap", "route": "/", "locator": "css:#save-button"},
  {"rule": "rect.target-size", "route": "/", "locator": "css:#help-button"},
  {"rule": "http.5xx", "route": "/api/fail", "locator": "n/a"}
]
```

- [ ] Implement: add a `RULE_IDS = (...)` tuple constant to each of `web/measure.py`, `api/measure.py`, `shell/measure.py`, `mobile/measure.py`, listing exactly the rule-id string literals that module's check functions can return (read each module's `return [...]`/`findings.append({...})` sites to enumerate them precisely; do not guess — e.g. `web/measure.py`'s set includes `contrast.aa`, `token.color`, `rect.overlap`, `rect.target-size`, `a11y.keyboard-unreachable`, `http.5xx`, `console.error`, `replay.checkpoint`, `visual.changed`; `api/measure.py`'s set is `http.5xx`, `http.status-undeclared`, `http.content-type`, `http.slow`; `shell/measure.py`'s set is `cli.exit-code`, `cli.stderr-on-success`, `cli.json-shape`, `cli.help`; `mobile/measure.py`'s set is whatever `check_hierarchy` returns, e.g. `rect.target-size`, `rect.overlap`, `rect.offscreen`). Then, for each of the other 4 fixtures' `planted.json` (`tauriapp`, `mobileapp`, `apiapp`, `cliapp`, which the M5 brief assumes already exist from M2-M4), normalize each entry to `{"rule": ..., "route": ledger.route_template(<real route>), "locator": ...}` matching the bug already planted in that fixture per shared.md A-36/A-39/A-41 fixture descriptions (e.g. `tauriapp` gets one entry for the swallowed-invoke-error bug using the nearest already-emitted rule id it triggers, e.g. `console.error`, if M2 did not add a dedicated rule — flagged in QUESTIONS below since the real M2 plan is the authority here).
- [ ] Run `python -m pytest -q plugins/flow-review/engine/fixtures/test_planted.py`. Expected PASS.
- [ ] Verify: `python -m pytest -q -m "web or not web"`.
- [ ] Commit: `git add plugins/flow-review/engine/fixtures/*/planted.json plugins/flow-review/engine/fixtures/test_planted.py plugins/flow-review/engine/flow_review/web/measure.py plugins/flow-review/engine/flow_review/api/measure.py plugins/flow-review/engine/flow_review/shell/measure.py plugins/flow-review/engine/flow_review/mobile/measure.py && git commit -m "test(fixtures): planted.json rule-id and route-template audit"`

### Task T4: `bench.py::run` core

**Executor:** sonnet · **Depends:** T3 · **Wave:** 2
**Files:** `plugins/flow-review/engine/flow_review/bench.py` (new), `plugins/flow-review/engine/flow_review/test_bench.py` (new)
**Interfaces:** Consumes `ledger.load`, `ledger.route_template`, `budget.used`, `config.Config`/`config.Surface`/`config.save`, `events.new_run_id`. Produces `bench.py::run(project_root, profiles, surfaces, out_dir) -> Path`, `bench.py::_match_planted(findings: list, planted: list) -> tuple[int, int]` (true, false counts), `bench.py::_dry_run_commands(project_root, profiles, surfaces) -> list[str]`, `bench.py::_write_bench_config(dest_dir, surface, profile, port) -> None`.
**Ponytail rung:** 4 (subprocess is the installed mechanism this needs; no new dependency).

- [ ] Write the failing test in `test_bench.py`:

```python
"""bench.py tests never dispatch `claude -p` -- they use --dry-run and hand-written
findings.json/events.jsonl fixtures, per the plan's "no test spends LLM tokens" rule."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from flow_review import bench as benchmod
from flow_review import config as configmod


def _write_findings(flow_review_dir: Path, entries: list[dict]) -> None:
    flow_review_dir.mkdir(parents=True, exist_ok=True)
    (flow_review_dir / "findings.json").write_text(
        json.dumps({"findings": {e["id"]: e for e in entries}, "discoverability_misses": {}}),
        encoding="utf-8",
    )


def test_match_planted_counts_true_and_false_findings_and_accepts_regressed():
    planted = [
        {"rule": "contrast.aa", "route": "/", "locator": "role:button[name=Submit]"},
        {"rule": "http.5xx", "route": "/api/:id", "locator": "n/a"},
    ]
    findings = [
        {"rule": "contrast.aa", "route": "/", "state": "open"},
        {"rule": "rect.overlap", "route": "/", "state": "open"},  # false positive
        {"rule": "http.5xx", "route": "/api/:id", "state": "regressed"},  # counts as true too
    ]
    true_count, false_count = benchmod._match_planted(findings, planted)
    assert true_count == 2
    assert false_count == 1


def test_write_bench_config_sets_model_profile_and_fixed_base_url(tmp_path):
    dest_dir = tmp_path / "lean" / "webapp"
    dest_dir.mkdir(parents=True)

    benchmod._write_bench_config(dest_dir, "webapp", "lean", 4173)

    cfg = configmod.load(dest_dir / ".flow-review" / "config.json")
    assert cfg.model_profile == "lean"
    assert len(cfg.surfaces) == 1
    assert cfg.surfaces[0].options["base_url"] == "http://localhost:4173"


def test_dry_run_writes_no_json_and_prints_the_real_claude_command(tmp_path, capsys):
    project_root = tmp_path / "proj"
    out_dir = tmp_path / "out"
    path = benchmod.run(
        project_root, profiles=["lean"], surfaces=["webapp"], out_dir=out_dir, dry_run=True,
    )
    captured = capsys.readouterr()
    assert "claude" in captured.out
    assert "/flow-review full" in captured.out
    assert "model_profile='lean'" in captured.out
    assert path is None  # dry-run writes no JSON


def test_run_computes_recall_and_tokens_from_prewritten_findings(tmp_path, monkeypatch):
    project_root = tmp_path / "proj"
    out_dir = tmp_path / "out"
    fixture_copy = tmp_path / "proj" / "lean" / "webapp"
    flow_review_dir = fixture_copy / ".flow-review"
    _write_findings(flow_review_dir, [
        {"id": "f1", "rule": "contrast.aa", "route": "/", "state": "open"},
        {"id": "f2", "rule": "rect.overlap", "route": "/", "state": "open"},
    ])
    run_dir = flow_review_dir / "runs" / "2026-01-01T00-00-00.000Z"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in [
            {"type": "usage", "surface": "webapp", "role": "explorer", "tokens": 1000},
        ]),
        encoding="utf-8",
    )

    def fake_dispatch(profile, surface, dest_dir, port=None):
        return fixture_copy, run_dir

    monkeypatch.setattr(benchmod, "_dispatch", fake_dispatch)
    monkeypatch.setattr(benchmod, "_load_planted", lambda surface: [
        {"rule": "contrast.aa", "route": "/", "locator": "x"},
    ])
    monkeypatch.setattr(benchmod, "_start_fixture_server", lambda surface, root: None)
    monkeypatch.setattr(benchmod, "_stop_fixture_server", lambda handle: None)

    path = benchmod.run(project_root, profiles=["lean"], surfaces=["webapp"], out_dir=out_dir)

    data = json.loads(path.read_text(encoding="utf-8"))
    entry = data["lean"]["webapp"]
    assert entry["recall"] == 1.0
    assert entry["true_findings"] == 1
    assert entry["false_findings"] == 1
    assert entry["tokens"] == 1000
    assert entry["tokens_per_true"] == 1000.0
    assert entry["run_dir"] == str(run_dir)


def test_priors_from_reads_run_dir_and_medians_tokens_per_role(tmp_path):
    run_dir_a = tmp_path / "run-a"
    run_dir_a.mkdir()
    (run_dir_a / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in [
            {"type": "usage", "surface": "webapp", "role": "explorer", "tokens": 100_000},
            {"type": "usage", "surface": "webapp", "role": "verifier", "tokens": 40_000},
        ]),
        encoding="utf-8",
    )
    run_dir_b = tmp_path / "run-b"
    run_dir_b.mkdir()
    (run_dir_b / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in [
            {"type": "usage", "surface": "apiapp", "role": "explorer", "tokens": 120_000},
        ]),
        encoding="utf-8",
    )
    history_path = tmp_path / "2026-01-01.json"
    history_path.write_text(json.dumps({
        "lean": {
            "webapp": {"run_dir": str(run_dir_a)},
            "apiapp": {"run_dir": str(run_dir_b)},
        },
    }), encoding="utf-8")

    priors = benchmod.priors_from([history_path])

    assert priors["explorer"] == 110_000  # median(100_000, 120_000)
    assert priors["verifier"] == 40_000
```

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/test_bench.py`. Expected FAIL: `ModuleNotFoundError: No module named 'flow_review.bench'`.
- [ ] Implement `bench.py`:

```python
"""`flow-review bench`: run the headless skill against fixtures with planted bugs, per model
profile, and score recall and token cost per true finding (A-43). Never runs from a test --
every test uses `dry_run=True` or monkeypatches `_dispatch`/fixture-server hooks, so `claude -p`
never actually launches under pytest.

ASSUMPTION (flag at review): the `claude -p` permission flag below is not spelled out anywhere
in this repo's docs (the M1 plan's R12 task says only "a permission mode that lets it run
flow-review and the file tools"). `--dangerously-skip-permissions` is used here as the
unattended-headless flag; confirm against the actual flag used when R12 was executed and fix
this constant if it differs (see QUESTIONS).
"""
from __future__ import annotations

import json
import shutil
import statistics
import subprocess
import sys
from datetime import date
from pathlib import Path

from flow_review import budget, config as configmod, ledger

DEFAULT_PROFILES = ["lean", "default", "max"]
DEFAULT_SURFACES = ["webapp", "apiapp", "cliapp"]

_FIXTURES_ROOT = Path(__file__).resolve().parent.parent / "fixtures"
_PLUGIN_DIR = Path(__file__).resolve().parents[2]  # plugins/flow-review

_CLAUDE_GOAL = "/flow-review full"
_PERMISSION_FLAG = "--dangerously-skip-permissions"  # see module docstring ASSUMPTION
_DISPATCH_TIMEOUT_S = 1800

_DRIVER_BY_SURFACE = {
    "webapp": "playwright", "tauriapp": "tauri", "mobileapp": "maestro",
    "apiapp": "http", "cliapp": "shell",
}
_KIND_BY_DRIVER = {"playwright": "ui", "tauri": "ui", "maestro": "ui", "http": "api", "shell": "cli"}

# Fixed ports so bench runs are reproducible and never collide with a developer's own dev
# server. cliapp needs no server/port (it is invoked as a subprocess per action).
_FIXED_PORTS = {"webapp": 4173, "apiapp": 4174}


def _load_planted(surface: str) -> list[dict]:
    path = _FIXTURES_ROOT / surface / "planted.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _match_planted(findings: list[dict], planted: list[dict]) -> tuple[int, int]:
    """A planted bug counts as found by any ledger entry that is still `open` or has
    `regressed` back into view -- both mean the engine currently flags it; `fixed`,
    `refuted`, etc. do not."""
    countable_states = {"open", "regressed"}
    countable = [f for f in findings if f.get("state", "open") in countable_states]
    planted_keys = {(p["rule"], p["route"]) for p in planted}
    true_count = 0
    matched_keys: set[tuple[str, str]] = set()
    false_count = 0
    for finding in countable:
        key = (finding["rule"], finding["route"])
        if key in planted_keys and key not in matched_keys:
            true_count += 1
            matched_keys.add(key)
        else:
            false_count += 1
    return true_count, false_count


def _fixture_surface(surface: str, port: int | None) -> configmod.Surface:
    driver = _DRIVER_BY_SURFACE[surface]
    if driver in ("playwright", "http"):
        options = {"base_url": f"http://localhost:{port}"}
    elif driver == "shell":
        # ponytail: cliapp's own README/entry point names its command; bench assumes the
        # fixture is invoked as `python cli.py` from its own directory, matching the M4
        # cliapp fixture layout. No generic command-discovery mechanism is added here.
        options = {"command": f"{sys.executable} cli.py", "cwd": "."}
    else:
        options = {}
    return configmod.Surface(
        id=surface, name=surface, kind=_KIND_BY_DRIVER[driver], driver=driver,
        launch="true", options=options,
    )


def _write_bench_config(dest_dir: Path, surface: str, profile: str, port: int | None) -> None:
    cfg = configmod.Config(
        schema_version=2, generator_version="bench",
        surfaces=[_fixture_surface(surface, port)],
        model_profile=profile,
    )
    config_path = dest_dir / ".flow-review" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    configmod.save(cfg, config_path)


def _claude_command() -> list[str]:
    return ["claude", "-p", _CLAUDE_GOAL, "--plugin-dir", str(_PLUGIN_DIR), _PERMISSION_FLAG]


def _dry_run_commands(project_root: Path, profiles: list[str], surfaces: list[str]) -> list[str]:
    commands = []
    for profile in profiles:
        for surface in surfaces:
            dest = Path(project_root) / profile / surface
            port = _FIXED_PORTS.get(surface)
            commands.append(
                f"# writes {dest / '.flow-review' / 'config.json'} with "
                f"model_profile={profile!r}, base_url={f'http://localhost:{port}' if port else None!r}"
            )
            commands.append(" ".join(_claude_command()))
    return commands


def _start_fixture_server(surface: str, dest_dir: Path):
    if surface == "webapp":
        port = _FIXED_PORTS["webapp"]
        return subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port), "--directory", str(dest_dir)],
        )
    if surface == "apiapp":
        port = _FIXED_PORTS["apiapp"]
        # ASSUMPTION (flag at review): apiapp's server.py is assumed to accept `--port`, added
        # by the M4 plan's HTTP-driver fixture task. Verify against the actual M4 fixture and
        # adjust this invocation if its flag name differs.
        return subprocess.Popen(
            [sys.executable, "server.py", "--port", str(port)], cwd=dest_dir,
        )
    return None  # cliapp: no server


def _stop_fixture_server(handle) -> None:
    if handle is not None:
        handle.terminate()
        handle.wait(timeout=5)


def _dispatch(profile: str, surface: str, dest_dir: Path) -> tuple[Path, Path]:
    """Copy the fixture, write its config (model_profile + fixed base_url), start the fixture
    server, run the real headless skill, return (project_dir, run_dir). Only ever called when
    dry_run is False; every test monkeypatches this function instead of letting it run."""
    src = _FIXTURES_ROOT / surface
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest_dir, dirs_exist_ok=True)
    port = _FIXED_PORTS.get(surface)
    _write_bench_config(dest_dir, surface, profile, port)
    handle = _start_fixture_server(surface, dest_dir)
    try:
        subprocess.run(
            _claude_command(), cwd=dest_dir, timeout=_DISPATCH_TIMEOUT_S, check=False,
        )
    finally:
        _stop_fixture_server(handle)
    flow_review_dir = dest_dir / ".flow-review"
    runs_dir = flow_review_dir / "runs"
    run_dir = sorted(runs_dir.iterdir())[-1]
    return dest_dir, run_dir


def run(project_root, profiles=None, surfaces=None, out_dir=None, dry_run: bool = False) -> Path | None:
    profiles = profiles or DEFAULT_PROFILES
    surfaces = surfaces or DEFAULT_SURFACES
    project_root = Path(project_root)
    out_dir = Path(out_dir) if out_dir is not None else Path("docs/benchmarks")

    if dry_run:
        for line in _dry_run_commands(project_root, profiles, surfaces):
            print(line)
        return None

    result: dict[str, dict[str, dict]] = {}
    for profile in profiles:
        result[profile] = {}
        for surface in surfaces:
            dest_dir = project_root / profile / surface
            project_dir, run_dir = _dispatch(profile, surface, dest_dir)
            ledger_ = ledger.load(project_dir / ".flow-review" / "findings.json")
            findings = [
                {"rule": e.rule, "route": e.route, "state": e.state}
                for e in ledger_.findings.values()
            ]
            planted = _load_planted(surface)
            true_count, false_count = _match_planted(findings, planted)
            tokens = budget.used(run_dir)
            recall = true_count / len(planted) if planted else 0.0
            tokens_per_true = (tokens / true_count) if true_count else None
            result[profile][surface] = {
                "recall": recall,
                "true_findings": true_count,
                "false_findings": false_count,
                "tokens": tokens,
                "tokens_per_true": tokens_per_true,
                "run_dir": str(run_dir),
            }

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date.today().isoformat()}.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return out_path


def compare(path_a: Path, path_b: Path) -> str:
    data_a = json.loads(Path(path_a).read_text(encoding="utf-8"))
    data_b = json.loads(Path(path_b).read_text(encoding="utf-8"))
    lines = [f"{'profile':<10}{'surface':<12}{'recall Δ':>10}{'tok/true Δ':>14}"]
    for profile in sorted(set(data_a) | set(data_b)):
        for surface in sorted(set(data_a.get(profile, {})) | set(data_b.get(profile, {}))):
            a = data_a.get(profile, {}).get(surface, {})
            b = data_b.get(profile, {}).get(surface, {})
            recall_delta = (b.get("recall", 0) or 0) - (a.get("recall", 0) or 0)
            tok_a = a.get("tokens_per_true")
            tok_b = b.get("tokens_per_true")
            tok_delta = (tok_b - tok_a) if (tok_a is not None and tok_b is not None) else None
            lines.append(
                f"{profile:<10}{surface:<12}{recall_delta:>+10.2f}"
                f"{'n/a' if tok_delta is None else f'{tok_delta:+.0f}':>14}"
            )
    text = "\n".join(lines)
    print(text)
    return text


def priors_from(history_paths: list[Path]) -> dict[str, int]:
    """Read the `run_dir` recorded in each bench-history JSON, re-open that run's
    events.jsonl, and take the per-role median of its `usage` events' `tokens` field --
    exactly what `budget.PRIORS_TOKENS_PER_UNIT` needs, computed from real bench runs
    instead of the 2026-09-23 planning-session guesses it ships with."""
    per_role: dict[str, list[int]] = {}
    for history_path in history_paths:
        data = json.loads(Path(history_path).read_text(encoding="utf-8"))
        for surface_data in data.values():
            if not isinstance(surface_data, dict):
                continue
            for surface_result in surface_data.values():
                run_dir = surface_result.get("run_dir")
                if not run_dir:
                    continue
                log_path = Path(run_dir) / budget.EVENTS_FILENAME
                if not log_path.exists():
                    continue
                for line in log_path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    if record.get("type") != "usage":
                        continue
                    role = record["role"]
                    per_role.setdefault(role, []).append(int(record["tokens"]))
    priors = {role: int(statistics.median(values)) for role, values in per_role.items()}
    print("PRIORS = " + json.dumps(priors, indent=4))
    return priors
```

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/test_bench.py`. Expected PASS.
- [ ] Verify: `python -m pytest -q -m "web or not web"`.
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/bench.py plugins/flow-review/engine/flow_review/test_bench.py && git commit -m "feat(bench): planted-bug benchmark run/compare/priors core (A-43)"`

### Task T5: `flow-review bench` CLI

**Executor:** sonnet · **Depends:** T2, T4 · **Wave:** 3
**Files:** `plugins/flow-review/engine/flow_review/cli.py`, `plugins/flow-review/engine/flow_review/test_cli.py`
**Interfaces:** Consumes `bench.run`, `bench.compare`, `bench.priors_from`. Produces `flow-review bench run|compare|priors` argparse subcommands.
**Ponytail rung:** 5.

- [ ] Add the failing test to `test_cli.py`:

```python
def test_bench_verbs_are_registered():
    from flow_review import cli

    parser = cli.build_parser()
    sub_actions = [a for a in parser._subparsers._group_actions if a.dest == "verb"]
    assert "bench" in sub_actions[0].choices

    args = parser.parse_args(["bench", "run", "--dry-run", "--profile", "lean"])
    assert args.func is not None
    assert args.dry_run is True
    assert args.profile == ["lean"]

    args = parser.parse_args(["bench", "compare", "a.json", "b.json"])
    assert args.a == "a.json" and args.b == "b.json"

    args = parser.parse_args(["bench", "priors", "h1.json", "h2.json"])
    assert args.history == ["h1.json", "h2.json"]
```

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/test_cli.py -k bench_verbs`. Expected FAIL: `argparse.ArgumentError` / `SystemExit` (unknown verb `bench`).
- [ ] Implement in `cli.py`, near `budget_parser`:

```python
    bench_parser = sub.add_parser("bench", parents=[project_after_verb])
    bench_sub = bench_parser.add_subparsers(dest="bench_verb")

    bench_run_parser = bench_sub.add_parser("run", parents=[project_after_verb])
    bench_run_parser.add_argument("--profile", dest="profile", nargs="*", default=None)
    bench_run_parser.add_argument("--surface", dest="surface", nargs="*", default=None)
    bench_run_parser.add_argument("--out-dir", dest="out_dir", default=None)
    bench_run_parser.add_argument("--dry-run", dest="dry_run", action="store_true")
    bench_run_parser.set_defaults(func=_run_bench_run)

    bench_compare_parser = bench_sub.add_parser("compare")
    bench_compare_parser.add_argument("a")
    bench_compare_parser.add_argument("b")
    bench_compare_parser.set_defaults(func=_run_bench_compare)

    bench_priors_parser = bench_sub.add_parser("priors")
    bench_priors_parser.add_argument("history", nargs="+")
    bench_priors_parser.set_defaults(func=_run_bench_priors)
```

  and the three handlers near `_run_replay`:

```python
def _run_bench_run(args: argparse.Namespace) -> int:
    from flow_review import bench as benchmod
    project_root = args.project_root or Path.cwd()
    out_dir = Path(args.out_dir) if args.out_dir else None
    benchmod.run(
        project_root, profiles=args.profile, surfaces=args.surface,
        out_dir=out_dir, dry_run=args.dry_run,
    )
    return 0


def _run_bench_compare(args: argparse.Namespace) -> int:
    from flow_review import bench as benchmod
    benchmod.compare(Path(args.a), Path(args.b))
    return 0


def _run_bench_priors(args: argparse.Namespace) -> int:
    from flow_review import bench as benchmod
    benchmod.priors_from([Path(p) for p in args.history])
    return 0
```

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/test_cli.py`. Expected PASS.
- [ ] Verify: `python -m pytest -q -m "web or not web"`.
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/cli.py plugins/flow-review/engine/flow_review/test_cli.py && git commit -m "feat(cli): flow-review bench run/compare/priors verbs"`

### Task T6: A-8/A-9 recalibration observability

**Executor:** sonnet · **Depends:** T5 · **Wave:** 4
**Files:** `plugins/flow-review/engine/flow_review/bench.py`, `plugins/flow-review/engine/flow_review/test_bench.py`, `plugins/flow-review/skills/flow-review/references/goals.md`
**Interfaces:** Consumes `Ledger.discoverability_misses`, the `goal` events written to `events.jsonl` (fields `surface_id`, `flow_id`, `actions`, `shortest`, matching the `surface_id`/`flow_id` naming every other event type already uses — the same fields the goal-card metric in `references/goals.md` §3-4 reads). Produces an extra `discoverability` and `path_ratio` block per surface in the bench JSON.
**Ponytail rung:** 1 (read-only aggregation of data the engine already writes; no new config knob).

- [ ] Add the failing test in `test_bench.py`:

```python
def test_run_includes_discoverability_and_path_ratio_observability(tmp_path, monkeypatch):
    project_root = tmp_path / "proj"
    out_dir = tmp_path / "out"
    fixture_copy = tmp_path / "proj" / "lean" / "webapp"
    flow_review_dir = fixture_copy / ".flow-review"
    _write_findings(flow_review_dir, [])
    run_dir = flow_review_dir / "runs" / "2026-01-01T00-00-00.000Z"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in [
            {"type": "goal", "surface_id": "webapp", "flow_id": "sign-in", "actions": 6, "shortest": 3},
        ]),
        encoding="utf-8",
    )
    flow_review_dir.mkdir(parents=True, exist_ok=True)
    (flow_review_dir / "findings.json").write_text(
        json.dumps({
            "findings": {},
            "discoverability_misses": {"loadData": ["run-a", "run-b"]},
        }),
        encoding="utf-8",
    )

    def fake_dispatch(profile, surface, dest_dir):
        return fixture_copy, run_dir

    monkeypatch.setattr(benchmod, "_dispatch", fake_dispatch)
    monkeypatch.setattr(benchmod, "_load_planted", lambda surface: [])
    monkeypatch.setattr(benchmod, "_start_fixture_server", lambda surface, root: None)
    monkeypatch.setattr(benchmod, "_stop_fixture_server", lambda handle: None)

    path = benchmod.run(project_root, profiles=["lean"], surfaces=["webapp"], out_dir=out_dir)
    data = json.loads(path.read_text(encoding="utf-8"))
    entry = data["lean"]["webapp"]
    assert entry["discoverability_misses"] == {"loadData": 2}
    assert entry["path_ratios"] == [2.0]
```

(`_write_findings` and the `benchmod` import already exist in `test_bench.py` from T4; reuse them.)

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/test_bench.py -k discoverability`. Expected FAIL: `KeyError: 'discoverability_misses'`.
- [ ] Implement: in `bench.py::run`, after computing `ledger_` for a surface, add:

```python
            discoverability = {
                fn: len(runs) for fn, runs in ledger_.discoverability_misses.items()
            }
            path_ratios = []
            log_path = run_dir / "events.jsonl"
            if log_path.exists():
                for line in log_path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    if record.get("type") == "goal" and record.get("shortest"):
                        path_ratios.append(record["actions"] / record["shortest"])
```

  and add `"discoverability_misses": discoverability, "path_ratios": path_ratios,` to the per-surface `result[profile][surface] = {...}` dict.
- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/test_bench.py`. Expected PASS.
- [ ] Add a paragraph to `references/goals.md` (after its existing §3-4 A-8/A-9 description): state that the 2-miss rule (A-8) and the path-ratio metric (A-9) stay unchanged until two consecutive `docs/benchmarks/<date>.json` releases show `discoverability_misses` or `path_ratios` distributions disagreeing with the current thresholds across at least two fixtures; name the exact JSON fields to read (`<profile>.<surface>.discoverability_misses`, `<profile>.<surface>.path_ratios`).
- [ ] Verify: `python -m pytest -q -m "web or not web"`.
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/bench.py plugins/flow-review/engine/flow_review/test_bench.py plugins/flow-review/skills/flow-review/references/goals.md && git commit -m "feat(bench): surface discoverability/path-ratio data for A-8/A-9 recalibration"`

### Task T7: Docs

**Executor:** haiku · **Depends:** T2, T6 · **Wave:** 5
**Files:** `docs/benchmarks/README.md` (new), `README.md`, `plugins/flow-review/skills/flow-review/references/setup.md`
**Interfaces:** Consumes nothing new; documents T1-T6's shipped behaviour only.
**Ponytail rung:** 1.

- [ ] Write the failing test (extend the existing README/reference doc test, `test_readme` or `test_cli_parity`, whichever already asserts every documented verb is real):

```python
def test_bench_and_watch_documented_in_readme_and_benchmarks_readme():
    readme = Path(__file__).resolve().parents[4] / "README.md"
    text = readme.read_text(encoding="utf-8")
    assert "flow-review bench" in text
    assert "flow-review watch" in text

    bench_readme = Path(__file__).resolve().parents[4] / "docs" / "benchmarks" / "README.md"
    assert bench_readme.exists()
    bench_text = bench_readme.read_text(encoding="utf-8")
    assert "recall" in bench_text
    assert "tokens_per_true" in bench_text
```

(Place this in `test_cli.py` alongside the existing README-parity assertions if one already exists in the repo — use whichever file the M1 plan's parity tests already live in.)

- [ ] Run `python -m pytest -q -k bench_and_watch_documented`. Expected FAIL: `bench_readme.exists()` is `False` and/or the README strings are missing.
- [ ] Write `docs/benchmarks/README.md`:

```markdown
# Benchmark releases

`flow-review bench run [--profile lean|default|max ...] [--surface webapp apiapp cliapp ...] [--out-dir docs/benchmarks]`
runs the real headless skill (`claude -p "/flow-review full"`) against each named fixture, once
per profile, and writes `docs/benchmarks/<YYYY-MM-DD>.json`:

    {
      "<profile>": {
        "<surface>": {
          "recall": 0.0-1.0,
          "true_findings": int,
          "false_findings": int,
          "tokens": int,
          "tokens_per_true": float | null,
          "discoverability_misses": {"<function>": <miss count>, ...},
          "path_ratios": [float, ...]
        }
      }
    }

`recall` = true findings / planted bugs for that fixture. `tokens_per_true` is `null` when a
profile found zero true findings for that surface. `discoverability_misses` and `path_ratios`
feed the A-8/A-9 recalibration described in `references/goals.md`; they do not change any
threshold automatically.

This is a manual release step, never run in CI (it dispatches real subagents and spends real
tokens). Run it before tagging a release:

    flow-review bench run --profile lean default max --surface webapp apiapp cliapp
    flow-review bench compare docs/benchmarks/<previous-date>.json docs/benchmarks/<today>.json
    flow-review bench priors docs/benchmarks/*.json   # paste the printed dict into budget.py by hand

Tauri and mobile fixtures are opt-in only (`--surface tauriapp` / `--surface mobileapp`); they
need a running WebView2/emulator host and are not part of the default surface set.
```

- [ ] Add a "Benchmarks" bullet to `README.md`'s release-checklist section (create one if none exists, right after the Install section): "Before tagging a release, run `flow-review bench run --profile lean default max` and `flow-review bench compare` against the previous release's JSON (see `docs/benchmarks/README.md`)."; confirm the "Watch" section from T2 is present (it should already be, from T2's commit).
- [ ] Add one line to `plugins/flow-review/skills/flow-review/references/setup.md`: "For iterative local development, `flow-review watch` re-replays a surface's recorded flows whenever its files change; it is not part of the skill's own flow and is run manually in a spare terminal."
- [ ] Run `python -m pytest -q -k bench_and_watch_documented`. Expected PASS.
- [ ] Verify: `python -m pytest -q -m "web or not web"`.
- [ ] Commit: `git add docs/benchmarks/README.md README.md plugins/flow-review/skills/flow-review/references/setup.md plugins/flow-review/engine/flow_review/test_cli.py && git commit -m "docs: watch and bench release-step documentation"`

## Checkpoints

### Task CP1: M5 checkpoint

**Executor:** opus · **Depends:** T1-T7 · **Wave:** 6

- [ ] Full suite: `python -m playwright install chromium` (if not already installed), then `python -m pytest -q -m "web or not web"`. Expected: 0 failed, 0 errors. Quote the summary line.
- [ ] Clean-venv install: `uv venv <tmp>/frv` (or `python -m venv` if uv is absent); `<tmp>/frv` pip-installs `"plugins/flow-review/engine[web]"`. From a directory outside the repo, `<tmp>/frv/Scripts/flow-review --help` exits 0 and lists `watch` and `bench` among the verbs.
- [ ] Real watch run: copy `plugins/flow-review/engine/fixtures/webapp` to a scratch project with one recorded flow already present (reuse the M1 fixture's recording or record one with `flow-review drive` + `flow-end`). Start `flow-review watch --interval-s 1` in the background. Edit `app.css` to break the planted contrast finding further (lower the contrast ratio on the already-flagged element). Expect one `watch: webapp <n> files changed -> replay exit 1` line within ~5 seconds of the debounce window elapsing. Ctrl-C the watch process; confirm it exits 0.
- [ ] Real bench run: `flow-review bench run --profile default --surface webapp apiapp cliapp` (three real headless `claude -p` dispatches — this is the one place in the whole plan that spends tokens, and it is a manual checkpoint step, never a pytest test). Quote the resulting JSON's `recall` per surface and `tokens_per_true`. Recall must be >= 0.75 on every fixture; if any fixture is below that, file a bug against that surface's driver (link the finding it should have caught but did not) rather than lowering the bar.
- [ ] `flow-review bench priors docs/benchmarks/<today>.json` prints a `PRIORS = {...}` dict.
- [ ] `flow-review bench compare docs/benchmarks/<today>.json docs/benchmarks/<today>.json` (against itself) prints all-zero deltas.
- [ ] Run superpowers:verification-before-completion before declaring M5 done.

## Appendix A: Decisions log

Extends the M2 plan's Appendix A (A-35..A-47), the M3 plan's (A-53..A-58) and the M4 plan's (A-59..A-64).

| # | Topic | Decision |
|---|---|---|
| A-65 | `watch` debounce measurement (drafter proposal, confirm at review) | The "files changed" count printed in `watch: <surface> <n> files changed -> replay exit <code>` is the symmetric difference of changed/added/removed relative paths between the pre-change and post-debounce snapshots, not a raw mtime-event count; this is the simplest count that matches what a human editing files would expect to see. |
| A-66 | `planted.json` matching key (drafter proposal, confirm at review) | `bench` matches a ledger finding to a planted bug on `(rule, route)` only, ignoring `locator`, because the M1 `route_template` fingerprint already treats different locators on the same route as the same fingerprint only when they also share flow_id; requiring locator equality in `bench` would make recall depend on exact selector strings the benchmark should be robust to. `locator` in `planted.json` remains documentation only. |
| A-67 | Fixture server lifecycle in `bench` (drafter proposal, confirm at review) | `bench.run` starts and stops each fixture's server itself (`_SERVER_START`/`_stop_fixture_server`) rather than requiring the fixture already be running, so `bench run` is a single command with no manual pre-step, matching the M1 plan's "sample app" pattern for R12. |
| A-68 | `bench compare`/`priors` scope (drafter proposal, confirm at review) | Both are read-only over already-written `docs/benchmarks/*.json` files and never re-run `bench run`; `priors_from` prints a dict for a human to paste into `budget.py` rather than writing to `budget.py` itself, per A-43's "no self-modifying code" rule. |
| A-69 | `RULE_IDS` constants (drafter proposal, confirm at review) | Each measure module (`web/measure.py`, `api/measure.py`, `shell/measure.py`, `mobile/measure.py`) gains one `RULE_IDS: tuple[str, ...]` module constant enumerating its own rule ids, so `fixtures/test_planted.py` (T3) and any future consumer can validate a rule id without importing private internals or duplicating the list; this is the minimum shared surface, not a new registry/plugin system. |

## QUESTIONS

- Q1: T3 assumes M2-M4 fixtures (`tauriapp`, `mobileapp`, `apiapp`, `cliapp`) and their `planted.json` files already exist per the M5 brief's "Assume M2-M4 have landed" line. If any of those milestones shipped a different planted-bug shape or a different rule id for the Tauri swallowed-invoke-error bug than `console.error` (T3's placeholder guess), T3's specific `planted.json` rewrite needs the real M2 plan's rule id substituted in.
- Q2: A-42's `watch` mapping is "surface-level" (any change under a surface's `cwd` re-replays every recorded flow of that surface), not file-to-flow. T1 implements exactly that. If a later reviewer wants file-to-flow granularity (source maps/coverage, mentioned only as a dropped idea in the M1 plan's "Later milestones" paragraph, not in A-42), that is a scope change beyond this plan.
- Q3: CP1's real bench run is the only step in this plan that spends LLM tokens; it dispatches three `claude -p "/flow-review full"` runs per surface × profile combination requested. Confirm at review that `--profile default --surface webapp apiapp cliapp` (3 runs) is the intended checkpoint scope rather than all three profiles (9 runs), to keep the checkpoint's token cost bounded.
- Q4: `bench.py`'s `_PERMISSION_FLAG = "--dangerously-skip-permissions"` (T4) is a drafter guess. Neither the M1 plan's R12 task nor `docs/` state the exact flag used for the real headless `claude -p` run; confirm the actual flag against how R12 was executed and correct the constant if it differs.
- Q5: T4's `apiapp` server start command assumes `server.py --port <N>` is a valid invocation (the M4 plan is assumed to have shipped it that way). If the real M4 `apiapp` fixture's server takes a different flag or reads its port from an env var instead, `_start_fixture_server`'s apiapp branch needs updating to match.
