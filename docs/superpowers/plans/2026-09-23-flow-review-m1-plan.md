# flow-review M1 (web end to end, plus foundations) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Each task names its executor model; dispatch it pinned to that model, never `inherit`. Opus reviews every checkpoint (CP1-CP4).

**Goal:** Rebuild flow-review v1 into the v2 architecture for web surfaces: fix the critical audit items, add the v2 config schema, the event writer and the ledger, and deliver the full Playwright loop (goals, cold eyes, opt-in recording, replay, measurement, validation, report, triage, live dashboard, GO-gate estimate and cap).

**Architecture:** A deterministic Python engine (`flow_review` package, `flow-review` console script) does everything that can be done without judgment: launch/prove, drive Playwright, record/replay, measure, visual diff, fingerprint, ledger, budget, and serving the dashboard. The Claude Code plugin (SKILL.md, references and pinned-model agent definitions) does all LLM work through subagents. The engine never calls an LLM API.

**Tech Stack:** Python >=3.10 (dev runs 3.14), pytest, Playwright for Python, Pillow, stdlib `http.server` (SSE), `uv` (pip fallback), and a Claude Code plugin (Markdown skill and agents).

**Spec:** `docs/superpowers/specs/2026-09-23-flow-review-v2-design.md` (cited as §N). Decisions made after the spec are in Appendix A and override the spec where they differ.

## Global Constraints

- The engine never calls an LLM API, holds no API key and has no headless LLM path (§3).
- flow-review never edits product code. Fix briefs are report content only (§1, §8).
- Every subagent is pinned to a model per role. `inherit` is never used. Profiles `lean|default|max` are overridable in config (§4).
- Secrets are never written to events, the ledger, reports or screenshots. Password fields are masked in screenshots. Credentials live in config as env-var NAMES only; values go in the gitignored `.flow-review/.env` (§9).
- Unattended runs (`replay`, CI, `serve`) never prompt (§9).
- The GO gate asks only about gaps: missing credentials (with an offer to save them), and destructive actions on a `persistent` surface (per-run opt-in, default no, never remembered) (§9).
- Payments are sandbox-only. Email verification goes through a configured test inbox; without one, it's marked `not-exercised` (§9).
- Recording is OFF by default (A-1).
- Token levers, in order: deterministic work in the engine; text before images (crop and downscale, send changed regions only); replay beats re-exploring; model tier per role (§4).
- Dashboard: no subheadings and no descriptions anywhere; icons and titles are self-explanatory; hover/focus tooltips double as accessible names; progressive disclosure; eased motion honouring `prefers-reduced-motion`; light/dark follow the OS, with a toggle (§11).
- Dashboard direction: Schibsted Grotesk (UI), IBM Plex Mono (numbers and logs only), cool neutrals, hairline borders, 4px radius, one blue accent, Phosphor icons (§11). Not signed off; the M1 design pass finalises it.
- No module prints or reconfigures stdout at import time (audit M9). The UTF-8 stdout setup lives only in `cli.main()`.
- Tests are colocated `test_*.py` next to the module, run with pytest from the repo root.
- TDD for every code task: failing test → run it and see it fail → minimal implementation → run it and see it pass → commit. Every task ends with its verify command; every checkpoint ends with superpowers:verification-before-completion.

## File Structure (target at end of M1)

```text
pytest.ini                                  # pythonpath -> plugins/flow-review/engine
plugins/flow-review/
  .claude-plugin/plugin.json
  agents/                                   # Claude Code agent defs, model pinned in frontmatter
    fr-explorer.md  fr-cold-eyes.md  fr-lens.md  fr-verifier.md  fr-triage.md  fr-replay-repair.md
  engine/
    pyproject.toml                          # name "flow-review", script flow-review=flow_review.cli:main, extras [web]
    flow_review/
      __init__.py
      cli.py            # argparse dispatcher: setup-env, prove, plan, event, replay, serve, triage, ledger, budget, migrate
      config.py         # v2 schema, typed per-kind options, friendly errors (A1/A2)
      migrate.py        # v1 -> v2 (A3)
      events.py         # JSON-safe event writer, ms ts, finding ids (A4)
      ledger.py         # findings.json, states, fingerprint, aliases, suppressions (A5)
      manifest.py       # flows.md ownership + idempotent annotation block (A6)
      drift.py          # id-keyed drift, declined filtering (A7)
      prove.py          # launch/prove fixes (A8)
      audit.py          # detection incl. monorepo + Poetry + web frameworks (A9)
      envsetup.py       # managed venv + .flow-review scaffolding + .env loader + redaction (A10)
      lenses.py         # lens sets as data (kept; fast/deep removed)
      web/
        driver.py       # Playwright driver, semantic locators, masking (B1)
        actionlog.py    # action-log format, recorder, ephemeral repro (B2)
        replay.py       # replay + divergence (B3)
        measure.py      # contrast, tokens, rects, status/console (B4)
        visual.py       # visual diff, crop/downscale (B5)
        faults.py       # network fault injection (B6)
        variants.py     # widths/theme/keyboard/reduced-motion variants (B7)
      budget.py         # priors, ledger medians, usage log, cap (B8)
      plan.py           # GO-gate plan + gaps (B9)
      validate.py       # validation state machine (C5)
      triage.py         # triage transitions + fix briefs (C6)
      dashboard/
        serve.py        # ThreadingHTTPServer + SSE + triage POST (E1)
        state.py        # fold events+ledger -> page state (E2)
        static.py       # static-file fallback render (E2)
        page/           # index.html, app.js, app.css, fonts/icons (E4/E5)
    fixtures/webapp/    # tiny static app with planted bugs for e2e tests (B0)
  skills/flow-review/
    SKILL.md
    PRODUCT.md          # impeccable init output (E3)
    references/ setup.md surfaces.md testing.md evidence.md stuck.md goals.md validation.md
                lenses/ui.md lenses/api.md lenses/cli.md
    templates/flows.md
```

`fr/` and `skills/flow-review/dashboard/` are moved (git mv) into `engine/flow_review/` in A1; their tests move with them.

## Task Skeleton

Owner areas: **D1** foundations · **D2** engine web loop · **D3** agent side · **D4** dashboard. The ordering puts the critical audit fixes (C1 schema, C4 fingerprint/ledger, C5 manifest) and the new config schema first; the other critical fixes (C2 consensus vote, C3 lens dispatch) land in C3/C2 once the validation pipeline they point to exists.

| id | goal (one line) | deps | wave | owner | exec |
|---|---|---|---|---|---|
| A1 | Package scaffold: git mv to `engine/flow_review`, pyproject + `flow-review` script + `cli.py` stub, remove import-time stdout side effect, rewrite the `test_references` guard | — | 1 | D1 | sonnet |
| A2 | Config v2 schema: surface `id`, typed per-kind options, state/reset/creds/record, model profile + role overrides, budget cap, friendly unknown-key errors with close match, preconditions validated (audit C1, H10, H11, M1) | A1 | 2 | D1 | opus |
| A3 | v1→v2 auto-migration + `config.v1.bak` + change summary; `flow-review migrate` | A2 | 3 | D1 | opus |
| A4 | Event writer: `flow-review event` CLI + `events.append()`, JSON-safe, ms UTC timestamps, finding ids, secret redaction hook; replaces the printf idiom (audit H8) | A1 | 2 | D1 | sonnet |
| A5 | Ledger `.flow-review/findings.json`: stable ids, semantic fingerprint, states + transitions, aliases, suppressions export; replaces prose `demote_repeats` (audit C4) | A4 | 3 | D1 | opus |
| A6 | Manifest write-back: idempotent annotation block and row edits, never touching human bytes; rewrite the locking test (audit C5) | A1 | 2 | D1 | sonnet |
| A7 | Drift keyed by surface `id`; declined surfaces excluded from the run plan (audit H1, H2) | A2 | 3 | D1 | sonnet |
| A8 | prove fixes: tree teardown even when the direct child exited (H3); clean exit with preconditions ≠ proven (H4); api reachability-only proving (M3) | A2 | 3 | D1 | sonnet |
| A9 | Detection: monorepo workspaces, Poetry, Vite/Next/React web apps with dev-server port; Tauri/Expo/Electron parked as `pending-driver` (A-14) | A2 | 3 | D1 | sonnet |
| A10 | Managed venv (`flow-review setup-env`, uv→pip), `.flow-review/` scaffolding + `.gitignore`, `.env` loader, redaction registry | A2, A4 | 3 | D1 | sonnet |
| CP1 | Checkpoint: foundations green, audit C1/C4/C5/H1-H4/H7-H11/M1/M3/M8/M9 closed | A1-A10 | 4 | — | opus |
| B0 | Fixture web app with planted bugs (low contrast, off-token color, overlapping rects, dead button, 500 route, hidden docs-only page) + README/docs | A1 | 2 | D2 | haiku |
| B1 | Playwright driver: launch/attach, semantic locators (role+name → testid → css), actions, a11y snapshot, masked screenshots, console/network capture | A10, B0 | 4 | D2 | sonnet |
| B2 | Action-log format + recorder (only when record is on) + ephemeral repro log for validation | B1 | 5 | D2 | opus |
| B3 | Replay + per-step divergence detection; `flow-review replay` exits non-zero on regressions and writes `divergences.json` for the next session | B2, B4, A5 | 7 | D2 | opus |
| B4 | Measurement engine checks → findings with rule ids: WCAG contrast, computed styles vs tokens, rects (overlap/offscreen/target size), HTTP status, console errors | B1, B2, A5 | 6 | D2 | sonnet |
| B5 | Visual diff vs baseline (Pillow), changed-region crop + downscale for LLM input | B1 | 5 | D2 | sonnet |
| B6 | Network fault injection for unhappy paths (offline, 5xx, slow) via `page.route` | B1 | 5 | D2 | sonnet |
| B7 | Variant runner: widths, light/dark, keyboard-only, reduced motion, new vs returning (storage state) as engine replays of an action log | B3 | 8 | D2 | sonnet |
| B10 | Drive CLI for agents (A-24): `flow-review drive start/goto/click/fill/press/look/flow-begin/flow-end/stop`, a per-surface localhost session server holding one WebDriver; writes the action log itself (password auto-redaction), stamps step windows, runs B4 checks after each step, returns a compact text snapshot | B1, B2, B4, A4 | 7 | D2 | opus |
| B8 | Budget: per-role token priors, ledger-median refinement (≥3 runs), usage log, `flow-review budget check` cap gate | A5 | 4 | D2 | sonnet |
| B9 | GO-gate plan: `flow-review plan` → planned work + estimate per surface + gaps (missing creds, destructive-on-persistent), trimmable | B8, A7, A10 | 5 | D2 | sonnet |
| CP2 | Checkpoint: engine loop e2e on the fixture (drive→record→replay→measure→diff→ledger) | B0-B10 | 9 | — | opus |
| C1 | Agent definitions with pinned models + profile table; the orchestrator resolves role→model from config | A2 | 3 | D3 | sonnet |
| C2 | SKILL.md rewrite: setup/run modes, goal/auto/full/quick, `record`, GO gate via `plan`, dispatch, cap checks, `serve` launch, report (audit C3, H5, H6, H9) | C1, C3, C4, C5, B9 | 10 | D3 | opus |
| C3 | Lens references rewrite: one call per screen, evidence bundle first, cross-rubric notes as context, no vote, suppressions injected, P2 = opinion (audit C2, C3) | C5 | 9 | D3 | sonnet |
| C4 | Explorer + goals: `references/goals.md` (goal-around set), cold-eyes pass 1 + docs pass 2, driving via `flow-review drive` (B10), hidden-feature metric + 2-miss P2 rule, path-ratio metric, safety limits | B10, A5 | 8 | D3 | sonnet |
| C5 | Validation pipeline: `validate.py` state machine + `references/validation.md` + verifier agent brief (refute only with measured/replayed evidence) | A5, B3 | 8 | D3 | opus |
| C6 | Triage + fix briefs: `flow-review triage`, FP → suppressions, fix brief (repro, evidence, suspected file:line via source maps), Haiku triage brief for fuzzy dedup/stuck | A5, B2 | 6 | D3 | sonnet |
| C7 | Docs sync: setup/surfaces/testing/stuck/evidence refresh, harness traps → `.flow-review/traps.md` (M5), stale refs (M6), README/concepts/walkthrough/CONTRIBUTING v2 | C2 | 11 | D3 | haiku |
| CP3 | Checkpoint: plugin-side dry run on the fixture via `/flow-review quick` | C1-C7 | 12 | — | opus |
| E1 | `flow-review serve`: ThreadingHTTPServer, SSE tailing events, `/state` JSON, triage POST, localhost only | A4, A5 | 4 | D4 | sonnet |
| E2 | Page state fold v2 + static fallback: lanes, progress, budget, one badge, hybrid report sections, withdraw by finding id (audit H7, M8) | A4, A5, B8 | 5 | D4 | sonnet |
| E3 | Design foundation: impeccable init (PRODUCT.md) + direction confirm, tokens, fonts, icons | — | 1 | D4 | sonnet |
| E4 | Run page build: auto-grid lanes (M7), header, badge, drawer (evidence per type), report, triage icons + keys, theme toggle, live update preserving scroll/drawer | E1, E2, E3 | 6 | D4 | sonnet |
| E5 | Design pass: impeccable new-work + polish, taste-skill, uiux-pro-max, hallmark audit, animotion; rule-lint test (no subheadings/descriptions) | E4 | 7 | D4 | sonnet |
| CP4 | M1 release checkpoint: full suite, fixture e2e through `/flow-review`, `python -m build` + `twine check`, publish only on user go | all | 13 | — | opus |

Parallel groups: each wave runs its tasks in parallel once their deps are met. The E3 design foundation has no dependencies and starts at wave 1.

## Canonical Interfaces

Cross-task names and shapes. They win over anything written inside a task. Every task's Consumes block must match this list.

- **Events** (A4): `flow_review.events.append(run_dir: Path, event: dict) -> dict` fills `ts` (UTC ISO-8601, ms, `Z`) and a finding `id`, applies `redact()`, and writes via `json.dumps` only. `events.now_iso() -> str`, `events.register_secret(value: str)`, `events.redact(value)`, `events.REDACTED = "[redacted]"`. CLI: `flow-review event --run DIR --type T [--json J] [k=v ...]`. Event types: `run, step, shot, output, finding, status, withdraw (finding_id), usage (surface, role, tokens), goal`. A skipped step is `{"type": "status", "state": "not-exercised", "surface_id", "flow_id", "step", "reason": "payment-not-sandboxed"|"no-test-inbox"|"destructive-no-optin"|"budget-cap"}`; the report lists these under not-exercised.
- **Config** (A2): `config.load(path) -> Config`, `config.save(cfg, path)`. `Surface(id, name, kind, driver, launch, cwd=".", env={}, options={}, preconditions=[], state="disposable", reset=None, creds={logical: ENV_NAME}, record=False, provenance={}, declined=False)`. Web options are a dict with keys `WEB_OPTION_KEYS = (base_url, health_path, ready_timeout_s, exit_timeout_s, viewport: list[{"width","height"}], tokens_file)`. `Config(schema_version, generator_version, surfaces, model_profile="default", role_overrides={}, budget={"cap_tokens": None}, test_inbox=None, flows_hash="")`. Read the cap as `cfg.budget["cap_tokens"]`.
- **Model routing** (C1 adds to config.py): `config.PROFILES: dict[str, dict[str, str]]` (profile → role → model) and `config.resolve_model(cfg, role) -> "haiku"|"sonnet"|"opus"` (role_overrides win; the verifier is never below sonnet). CLI: `flow-review model ROLE` prints it. The Python dict is the single source; agent Markdown files mirror it.
- **Ledger** (A5), module functions only (there is no `Ledger.load`, `upsert` or `runs_for`): `ledger.load(path) -> Ledger`, `ledger.save(ledger, path)`, `ledger.fingerprint(flow_id, rule, route, locator) -> str`, `ledger.reconcile(ledger, findings, flows_run, run_id, alias_decisions=None) -> Ledger`, `ledger.find_alias_candidates(ledger, flow_id, rule, route)`, `ledger.record_alias(ledger, canonical_id, alias_fingerprint)`, `ledger.suppressions_for(ledger, rule) -> list[dict]`, `ledger.record_miss(ledger, function, run_id) -> int`, `ledger.missed_twice(ledger, function) -> bool`. `LedgerEntry(id, fingerprint, surface_id, flow_id, rule, route, locator, sev, text, evidence: list[str] = [], disposition="engine", state="open", runs_seen=1, first_run="", last_run="", aliases=[], reason="")`. `reason` holds the refute reason or the triage note. The path is always `<project_root>/.flow-review/findings.json`. Suppressions derive from state (false-positive, wont-fix); there is no separate suppression store.
- **Triage** (C6): `flow_review.triage.apply(ledger_path: Path, finding_id: str, state: str, reason: str | None = None) -> LedgerEntry` loads, validates the state against `ledger.STATES`, sets state and reason, and saves. `reason` is required only for `refuted` (it comes from the verifier); triage clicks don't need one. The CLI `flow-review triage ID STATE [--reason]` and the dashboard `POST /triage` both call `apply`. Reopen = `apply(..., "open")`.
- **Budget** (B8): `budget.record_usage(run_dir, surface_id, role, tokens)` appends a `usage` event through `events.append`, the one source of truth. `budget.used(run_dir) -> int` sums the usage events. `budget.fold_history(project_root, run_dir)` runs at run end and appends per-surface, per-unit actuals to `<project_root>/.flow-review/usage_history.json` (budget-owned; the ledger holds no usage). `budget.estimate(plan_units, project_root) -> dict[surface_id, int]` uses priors until a surface has ≥3 runs in the history, then medians. `flow-review budget check --run DIR --next ROLE --surface ID` exits 1 when the cap would be exceeded. The dashboard shows `budget.used(run_dir)` against `cap_tokens`.
- **Ledger container**: `Ledger.findings: dict[str, LedgerEntry]` (keyed by id; iterate `.findings.values()`), `Ledger.discoverability_misses: dict[str, list[str]]`.
- **Finding payload** (the `finding` event, the `reconcile` input and the validation input share one shape): `{id, surface_id, flow_id, rule, route, locator, sev, text, evidence: list[str], disposition: "engine"|"objective"|"judgment"}`. `rule` is the engine rule id (e.g. `contrast.aa`) or the lens name.
- **Config path**: `<project_root>/.flow-review/config.json`. The CLI loads it once and hands `cfg` to the callees (the dashboard never calls `config.load` itself).
- **Project root**: every engine function that touches `.flow-review/` takes `project_root: Path` explicitly. The CLI resolves it by walking up from cwd to the nearest `.flow-review/` (or uses `--project`).
- **Env** (A10): `envsetup.setup_env(project_dir, engine_path, extras="web", runner, which)`, `envsetup.write_gitignore(flow_review_dir, commit_recordings=True)`, `envsetup.load_dotenv(path, environ=None)` (registers every value via `events.register_secret`).
- **Drift** (A7): `drift.runnable_surfaces(cfg) -> list[Surface]` excludes declined and `pending-driver` surfaces.
- **Manifest** (A6): `manifest.apply_learnings(path, recorded_hash, learnings) -> str` (the new hash).
- **Drive** (B10, A-24): `flow-review drive start --surface ID --run DIR [--record]` starts one localhost session server per surface (a single-threaded `http.server`, since Playwright's sync API is thread-bound) and prints `{"surface_id", "port"}`. Its state lives in `<run_dir>/drive/<surface_id>.json`. Verbs (all take `--surface ID --run DIR`): `goto PATH`, `click LOC`, `fill LOC (--text T | --from-env NAME)`, `press KEY`, `look [--shot]`, `flow-begin --flow ID`, `flow-end --flow ID --status ok|blocked`, `stop`. `LOC` = `--role R --name N | --testid T | --css C`. Every action returns one compact JSON object `{url, title, snapshot (trimmed a11y text, ≤4k chars), shot (path or null), new_findings: [ids], console_errors: int}`. The engine writes the action log itself (the password field is detected → value redacted; secrets only via `--from-env`), stamps the step window (A-17), runs the B4 checks after the page settles, and appends step/shot/finding events. `flow-end` saves the log per A-1..A-3.
- **Measure** (B4): `measure.check_page(driver, surface_id, flow_id, route, tokens: dict | None, step_index: int | None) -> list[dict]` runs every engine rule on the current page (contrast, token colors when `tokens` is given, rects, HTTP status and console since the last call) and returns canonical finding payloads with `disposition: "engine"`. Both `drive` (B10, after each action) and `replay` (B3, after each goto/click) call it; nothing else aggregates rules.
- **Replay** (B3): `flow-review replay [--surface ID] [--flow ID]` replays recordings of `drift.runnable_surfaces` with the playwright driver, runs `check_page` after each goto/click, verifies `assert_url` checkpoints (a mismatch is an objective regression finding `replay.checkpoint`), reconciles all findings into the ledger (`ledger.reconcile`; flows_run = the replayed flows) so the next session sees them, writes `divergences.json` whenever any divergence happened, and exits 1 if any entry became `regressed` or a new open P0/P1 appeared; else 2 if any divergence; else 0; and 3 on config/env errors. `flow-review replay --log PATH --run DIR` replays ONE action log once (the validation repro, A-3): it writes `<PATH>.result.json` (a ReplayResult plus findings, usable as verifier evidence with kind `replay`), never touches the ledger or `divergences.json`, and exits 0 when it reproduced cleanly, 1 when the findings reproduced, 2 on divergence.
- **Action log** (B2): the JSON format is defined in B2. Recordings go to `<project_root>/.flow-review/recordings/<surface_id>/<flow_id>.json` only when recording is on; otherwise to `<run_dir>/repro/`.

## Tasks

Task blocks in dependency order. The Canonical Interfaces section above wins over any conflicting name inside a task.

### Task A1: Package scaffold -- move to `engine/flow_review`, `flow-review` console script, kill the import-time stdout guard

**Executor:** sonnet · **Depends:** -- · **Wave:** 1

**Files:**
- Create: `plugins/flow-review/engine/pyproject.toml`
- Create: `plugins/flow-review/engine/flow_review/__init__.py`
- Create: `plugins/flow-review/engine/flow_review/cli.py`
- Move (git mv, preserving history): `plugins/flow-review/skills/flow-review/fr/*.py` (all 7 modules
  + all `test_*.py`) -> `plugins/flow-review/engine/flow_review/*.py`
- Move (git mv): `plugins/flow-review/skills/flow-review/dashboard/render.py` and
  `dashboard/test_render.py` -> `plugins/flow-review/engine/flow_review/dashboard/render.py` and
  `dashboard/test_render.py`; create `plugins/flow-review/engine/flow_review/dashboard/__init__.py`
- Move (git mv): `plugins/flow-review/skills/flow-review/dashboard/template.html` ->
  `plugins/flow-review/engine/flow_review/dashboard/template.html`
- Modify: `pytest.ini` (repo root)
- Modify: `plugins/flow-review/skills/flow-review/test_references.py` (imports, `SCANNED`,
  `GUARD_SCANNED`, the stdout-guard test)
- Modify: `plugins/flow-review/skills/flow-review/test_skill.py` (no path changes expected --
  verify, do not touch if it still passes)
- Modify (import fix only, no logic change): every moved module's `from fr import ...` /
  `from fr.X import ...` -> `from flow_review import ...` / `from flow_review.X import ...`;
  every moved test's `from fr import X` -> `from flow_review import X`;
  `dashboard/test_render.py`'s `sys.path.insert` + `import render` -> `from flow_review.dashboard
  import render`
- Modify (delete the 8-line guard block, see Step 3 below): every moved production module
  (`config.py`, `findings.py`, `manifest.py`, `drift.py`, `prove.py`, `audit.py`, `lenses.py`,
  `dashboard/render.py`) -- remove the top-of-file
  ```python
  if hasattr(sys.stdout, "reconfigure"):
      sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  ```
  block (and the now-unused `import sys` where nothing else in the file needs it -- check each
  file; `drift.py`, `manifest.py`, `lenses.py` have no other `sys` use and lose the import,
  `prove.py`, `audit.py`, `config.py`, `dashboard/render.py` use `sys` elsewhere and keep the
  import)
- Test: `plugins/flow-review/engine/flow_review/test_cli.py` (new)

**Interfaces:**
- Consumes: nothing (first task).
- Produces:
  - Console script `flow-review = flow_review.cli:main`, declared in
    `plugins/flow-review/engine/pyproject.toml` under `[project.scripts]`.
  - `flow_review.cli.main(argv: list[str] | None = None) -> int` -- an `argparse` dispatcher.
    In A1 it has subparsers for every verb later tasks add (`setup-env`, `prove`, `plan`, `event`,
    `replay`, `serve`, `triage`, `ledger`, `budget`, `migrate`, `model`), each currently only
    calling a stub that prints `"<verb>: not yet implemented"` to stderr and returns 2. This lets
    later tasks (A3, A4, A10, B-series, C1, C-series) fill in one subcommand each without
    touching the parser wiring. `model` is C1's per Canonical Interfaces (`flow-review model
    ROLE` prints the resolved model) -- A1 only reserves the verb name so C1 does not need to
    touch `build_parser()`'s subparser-registration loop at all.
  - `main()` is the ONLY place in the whole `flow_review` package (and in `dashboard/render.py`,
    which stays a `python -m` / direct-run entry point moved under the package) that calls
    `sys.stdout.reconfigure(...)`, and it does so as the first statement, before any argument
    parsing or subcommand dispatch, so every code path (including `--help`) gets it.
  - `flow_review.cli.find_project_root(start: Path) -> Path | None` -- walks up from `start`
    (inclusive) to the nearest ancestor directory that contains a `.flow-review/` folder and
    returns THAT ancestor (the project root, not the `.flow-review/` path itself); `None` if no
    ancestor has one (a fresh checkout before `setup-env`/first run). Per Canonical Interfaces
    ("Project root": "The CLI resolves it by walking up from cwd to the nearest `.flow-review/`
    (or uses `--project`)"), the top-level parser also gains a global `--project PATH` option
    (available before the verb, e.g. `flow-review --project /path/to/app prove ...`); `main()`
    resolves `args.project_root = Path(args.project).resolve() if args.project else
    find_project_root(Path.cwd())` right after parsing and before dispatch, and stores it on
    `args` for the subcommand function to read. A1 only ships the resolution plumbing and the
    helper itself -- A3/A4/A10 (already specified in this draft with their own explicit
    `--path`/`--run` arguments) are not rewired here to consume `args.project_root` instead;
    that is a later cleanup, not a blocker, since each of those subcommands already resolves a
    concrete path one way or another and `args.project_root` is additive infrastructure this
    task introduces for subsequent tasks (ledger CLI, budget, triage, serve) to use directly.
  - `pytest.ini` `pythonpath` becomes:
    ```ini
    [pytest]
    pythonpath =
        .
        plugins/flow-review/engine
    testpaths = .
    ```
    (the separate `dashboard` pythonpath entry is dropped -- `dashboard` is now the subpackage
    `flow_review.dashboard`, imported by its full dotted path everywhere.)

- [ ] **Step 1: Write the failing test (full pytest code).**

Create `plugins/flow-review/engine/flow_review/test_cli.py`:

```python
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
```

- [ ] **Step 2: Run it; expected FAIL.** `python -m pytest plugins/flow-review/engine/flow_review/test_cli.py -q`
fails with `ModuleNotFoundError: No module named 'flow_review'` (package does not exist yet).

- [ ] **Step 3: Minimal implementation.**

`plugins/flow-review/engine/pyproject.toml`:

```toml
[project]
name = "flow-review"
version = "2.0.0"
description = "flow-review engine: deterministic launch/prove/replay/measure/ledger for the flow-review Claude Code plugin"
requires-python = ">=3.10"
dependencies = []

[project.optional-dependencies]
web = ["playwright>=1.40", "pillow>=10.0"]

[project.scripts]
flow-review = "flow_review.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["flow_review*"]
```

`plugins/flow-review/engine/flow_review/__init__.py`: empty file.

`plugins/flow-review/engine/flow_review/cli.py`:

```python
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
    "budget", "migrate", "model",
)


def _stub(verb: str):
    def _run(args: argparse.Namespace) -> int:
        print(f"{verb}: not yet implemented", file=sys.stderr)
        return 2
    return _run


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
    args = parser.parse_args(argv)
    if getattr(args, "verb", None) is None:
        parser.print_usage(sys.stderr)
        return 2
    _resolve_project_root(args)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

Then, mechanically:
1. `git mv plugins/flow-review/skills/flow-review/fr plugins/flow-review/engine/flow_review_tmp`
   is wrong (would nest); instead `git mv` each of the 7 `fr/*.py` production files and 7
   `fr/test_*.py` files individually (or `git mv plugins/flow-review/skills/flow-review/fr/*.py
   plugins/flow-review/engine/flow_review/`) so they land flat in
   `plugins/flow-review/engine/flow_review/`, then `git rm` the now-empty `fr/` directory (git
   does not track empty dirs, nothing further needed).
2. `git mv plugins/flow-review/skills/flow-review/dashboard/render.py
   plugins/flow-review/engine/flow_review/dashboard/render.py`,
   same for `test_render.py` and `template.html`; create
   `plugins/flow-review/engine/flow_review/dashboard/__init__.py` (empty).
3. In every moved file, replace `from fr import X` -> `from flow_review import X`,
   `from fr.X import Y` -> `from flow_review.X import Y`, `from fr.config import Z` ->
   `from flow_review.config import Z`, etc. (mechanical, same identifiers, new package name).
4. Delete the stdout-guard block (the `if hasattr(sys.stdout, "reconfigure"): ...` two-liner)
   from the top of `config.py`, `findings.py`, `manifest.py`, `drift.py`, `prove.py`, `audit.py`,
   `lenses.py`, `dashboard/render.py`. Leave `import sys` in place wherever the file uses `sys`
   for something else (all of them except `manifest.py`, `drift.py`, `lenses.py`, which lose the
   now-dead `import sys`).
5. In `dashboard/test_render.py`, replace the `sys.path.insert(0, ...); import render` prologue
   with `from flow_review.dashboard import render`, and drop the now-unused `sys`/`Path` imports
   if nothing else in the file needs them.
6. Rewrite `pytest.ini` as shown in Interfaces above.
7. Rewrite `plugins/flow-review/skills/flow-review/test_references.py`'s stdout-guard section:
   replace `GUARD_SCANNED`, `STDOUT_GUARD`, and
   `test_every_production_module_guards_stdout_encoding` with:
   ```python
   ENGINE = ROOT.parent / "engine" / "flow_review"

   ENGINE_SCANNED = sorted(
       p for p in ENGINE.rglob("*.py")
       if p.name != "__init__.py" and not p.name.startswith("test_")
   )


   def test_no_module_reconfigures_stdout_at_import():
       """Only cli.main() may touch stdout encoding. Any other module doing it at import time
       means importing that module for its functions -- exactly what every test file in this
       suite does -- silently mutates the test runner's own stdout, which is the defect the
       previous per-module guard actually caused."""
       for path in ENGINE_SCANNED:
           if path.name == "cli.py":
               continue
           text = path.read_text(encoding="utf-8")
           assert "sys.stdout.reconfigure" not in text, (
               f"{path} reconfigures stdout outside cli.main()"
           )


   def test_cli_reconfigures_stdout_only_inside_main():
       text = (ENGINE / "cli.py").read_text(encoding="utf-8")
       assert "sys.stdout.reconfigure" in text
       before_main = text.split("def main(", 1)[0]
       assert "sys.stdout.reconfigure" not in before_main, (
           "the guard must live inside main(), not at module import time"
       )
   ```
   Also fix the `from fr import lenses` import at the top of `test_references.py` to
   `from flow_review import lenses`, and change `SCANNED` to walk `ENGINE.rglob("*.py")` (minus
   `test_*` and `__init__.py`) in place of the old `(ROOT / "fr").glob("*.py")` +
   `(ROOT / "dashboard").glob("*.py")` terms.
   `test_evidence_file_keeps_the_append_idiom_rules` is rewritten fully in A4, not here -- leave
   it as-is in A1 (it will fail once A4 changes `evidence.md`'s wording, which is A4's job to fix
   together with the test).

- [ ] **Step 4: Run; expected PASS.**
`python -m pytest -q` from repo root -> all 131 pre-existing tests plus the new `test_cli.py`
tests pass (131 + 9 = 140, modulo any renumbering from the `test_references.py` rewrite, which
nets to the same count: one test removed, two added).

- [ ] **Step 5: Verify.**
```
python -m pytest -q
```
Expected: all green, no `ModuleNotFoundError`, no leftover `fr` package anywhere
(`grep -rn "from fr" plugins/flow-review` returns nothing outside historical docs/plan prose).

- [ ] **Commit:**
```
git add plugins/flow-review/engine plugins/flow-review/skills/flow-review/fr plugins/flow-review/skills/flow-review/dashboard plugins/flow-review/skills/flow-review/test_references.py pytest.ini
git commit -m "refactor(engine): move fr/ and dashboard/ to engine/flow_review, add flow-review console script"
```
(git will record the moves as renames since content is mostly unchanged.)

---

### Task A2: Config v2 schema -- surface `id`, typed per-kind options, state/creds/model routing, friendly errors

**Executor:** opus · **Depends:** A1 · **Wave:** 2

**Files:**
- Modify: `plugins/flow-review/engine/flow_review/config.py` (full rewrite, replaces lines 1-117
  of the moved file)
- Modify: `plugins/flow-review/engine/flow_review/test_config.py` (full rewrite of the v1
  fixtures/tests to the v2 shape; old tests deleted, not kept alongside)

**Interfaces:**
- Consumes: nothing new (this is the schema every later task reads).
- Produces (relied on by A3, A5, A6, A7, A8, A9, A10, and every B/C/D-series task):
  - `flow_review.config.SCHEMA_VERSION = 2`
  - `flow_review.config.VALID_KINDS = ("ui", "cli", "api", "library")` (unchanged)
  - `flow_review.config.VALID_DRIVERS = ("cdp", "playwright", "adb", "ios-sim", "shell", "http",
    "custom")` (unchanged; A9 will not add new values here -- `pending-driver` surfaces get
    `driver: "pending"`, added to this tuple by A9)
  - `flow_review.config.VALID_PROVENANCE = ("audited", "proven", "user")` (unchanged)
  - `flow_review.config.VALID_STATE = ("disposable", "persistent")`
  - `flow_review.config.VALID_MODEL_PROFILE = ("lean", "default", "max")`
  - `flow_review.config.VALID_ROLES = ("explorer", "replay-repair", "lens", "cold-eyes",
    "triage", "verifier")` (the six subagent roles from spec Section 4; "engine" and
    "orchestrator" are never in `role_overrides` because neither ever calls an LLM/uses a
    pinned model config can override)
  - `class Surface` (dataclass): `id: str, name: str, kind: str, driver: str, launch: str,
    cwd: str = ".", env: dict[str, str] = field(default_factory=dict), options: dict = field(
    default_factory=dict), preconditions: list[dict] = field(default_factory=list), state: str =
    "disposable", reset: str | None = None, creds: dict[str, str] = field(default_factory=dict),
    record: bool = False, provenance: dict[str, str] = field(default_factory=dict), declined:
    bool = False`
  - `class Config` (dataclass): `schema_version: int, generator_version: str, surfaces:
    list[Surface] = field(default_factory=list), model_profile: str = "default", role_overrides:
    dict[str, str] = field(default_factory=dict), budget: dict = field(default_factory=lambda:
    {"cap_tokens": None}), test_inbox: dict | None = None, flows_hash: str = ""`
  - `class ConfigVersionError(Exception)` (unchanged)
  - `class ConfigKeyError(ValueError)` -- the friendly unknown-key error; carries `.key`,
    `.valid_keys`, `.closest` (the `difflib.get_close_matches` result, possibly empty) and a
    `str()` of the form: `"unknown key 'foo' at surfaces[0].options; valid keys are: base_url,
    health_path, ready_timeout_s, exit_timeout_s, viewport, tokens_file. Did you mean 'base_ur'?
    -> 'base_url'"` (the "Did you mean" clause is only appended when `closest` is non-empty).
  - `flow_review.config.load(path: Path) -> Config`
  - `flow_review.config.save(cfg: Config, path: Path) -> None`
  - `flow_review.config.WEB_OPTION_KEYS = ("base_url", "health_path", "ready_timeout_s",
    "exit_timeout_s", "viewport", "tokens_file")` -- the only recognized `options` keys when
    `driver == "playwright"`. Other drivers accept an empty `options` dict in M1 (no typed
    options shipped yet for cli/api/library; A8/A9 do not add any this milestone) and reject any
    non-empty one with `ConfigKeyError` naming `WEB_OPTION_KEYS` as the (only) valid set is a
    contradiction for a non-web surface -- instead a non-web `options` dict with any key raises
    `ConfigKeyError` with `valid_keys=()`, i.e. "this driver takes no options".
  - `flow_review.config.validate_preconditions(preconditions: list) -> None` -- raises
    `ValueError` if `preconditions` is not a list, or any item is not a dict, or any item is
    missing `"cmd"`, or any item has a key outside `{"name", "cmd"}` (via `ConfigKeyError`). This
    function is the ONE place precondition shape is validated; A8 calls it too (from `prove.py`,
    before using `preconditions` at runtime) rather than re-validating, per the task-ownership
    note below.

  **Example v2 config** (`.flow-review/config.json`), the shape `load`/`save` round-trip:
  ```json
  {
    "schema_version": 2,
    "generator_version": "2.0.0",
    "model_profile": "default",
    "role_overrides": {
      "verifier": "opus",
      "triage": "haiku"
    },
    "budget": {
      "cap_tokens": 500000
    },
    "test_inbox": null,
    "flows_hash": "",
    "surfaces": [
      {
        "id": "web-app",
        "name": "Web app",
        "kind": "ui",
        "driver": "playwright",
        "launch": "npm run dev",
        "cwd": ".",
        "env": {},
        "options": {
          "base_url": "http://localhost:5173",
          "health_path": "/healthz",
          "ready_timeout_s": 15,
          "exit_timeout_s": 60,
          "viewport": [
            {"width": 1280, "height": 800},
            {"width": 390, "height": 844}
          ],
          "tokens_file": "src/tokens.css"
        },
        "preconditions": [
          {"name": "port 5173", "cmd": "curl -sf localhost:5173"}
        ],
        "state": "disposable",
        "reset": null,
        "creds": {
          "ADMIN_PASSWORD": "ADMIN_PASSWORD"
        },
        "record": false,
        "provenance": {"origin": "audited", "launch": "proven"},
        "declined": false
      }
    ]
  }
  ```
  (`creds` maps a logical name to the **env-var name** holding the value -- per Global
  Constraints, the value itself never appears in config; A10's `.env` loader resolves it at
  runtime. In the common case the two strings are identical, as above.)

**Ownership split with A8** (both touch precondition validation): A2 owns and ships
`validate_preconditions()` and calls it from `config.load()`/`config.save()` so a malformed
config is rejected at load time with a friendly message. A8 owns calling
`validate_preconditions()` from `prove.py` at the start of `prove()` (defense in depth for a
`Proof` built without going through `config.load()`, e.g. in a test or a future non-config
caller) and owns the *runtime* precondition-related prove.py fixes (H3/H4/M3) themselves --
teardown, exit-vs-precondition semantics, api reachability. A8 does not change
`validate_preconditions()`'s shape or location.

- [ ] **Step 1: Write the failing test (full pytest code).**

Replace `plugins/flow-review/engine/flow_review/test_config.py` in full:

```python
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
```

- [ ] **Step 2: Run it; expected FAIL.**
`python -m pytest plugins/flow-review/engine/flow_review/test_config.py -q` fails: v1 `Surface`
has no `id`/`options`/`state`/... fields, `Config` has no `model_profile`, `ConfigKeyError` does
not exist.

- [ ] **Step 3: Minimal implementation.**

Replace `plugins/flow-review/engine/flow_review/config.py` in full:

```python
"""The per-project configuration flow-review writes on first run and reads forever after.

v2 schema (A-4). The version gate exists because a config generated by an older skill and read
by a newer one is the drift case nobody notices: every field still parses, and one rule
silently means something else. Refusing a NEWER schema is the direction that matters -- an old
skill cannot know what a field added later means.

Unknown-key errors are friendly by design (A-4): every rejected key names the valid set and, via
difflib, its closest match, because the reader is a person editing this file by hand or a v1
config walking through A3's auto-migration, not a machine that already knows the schema.
"""
from __future__ import annotations

import difflib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

SCHEMA_VERSION = 2
VALID_KINDS = ("ui", "cli", "api", "library")
VALID_PROVENANCE = ("audited", "proven", "user")
VALID_DRIVERS = ("cdp", "playwright", "adb", "ios-sim", "shell", "http", "custom")
VALID_STATE = ("disposable", "persistent")
VALID_MODEL_PROFILE = ("lean", "default", "max")
VALID_ROLES = ("explorer", "replay-repair", "lens", "cold-eyes", "triage", "verifier")
VALID_ROLE_MODELS = ("haiku", "sonnet", "opus")

WEB_OPTION_KEYS = (
    "base_url", "health_path", "ready_timeout_s", "exit_timeout_s", "viewport", "tokens_file",
)

_SURFACE_KEYS = {
    "id", "name", "kind", "driver", "launch", "cwd", "env", "options", "preconditions",
    "state", "reset", "creds", "record", "provenance", "declined",
}
_CONFIG_KEYS = {
    "schema_version", "generator_version", "surfaces", "model_profile", "role_overrides",
    "budget", "test_inbox", "flows_hash",
}
_PRECONDITION_KEYS = {"name", "cmd"}


class ConfigVersionError(Exception):
    """The config on disk was written by a newer flow-review than this one."""


class ConfigKeyError(ValueError):
    def __init__(self, key: str, valid_keys, where: str):
        self.key = key
        self.valid_keys = tuple(valid_keys)
        self.where = where
        self.closest = difflib.get_close_matches(key, self.valid_keys, n=1)
        message = (
            f"unknown key {key!r} at {where}; "
            f"valid keys are: {', '.join(self.valid_keys) if self.valid_keys else '(none)'}."
        )
        if self.closest:
            message += f" Did you mean {self.closest[0]!r}?"
        super().__init__(message)


def _check_keys(data: dict, allowed: set[str], where: str) -> None:
    for key in data:
        if key not in allowed:
            raise ConfigKeyError(key, sorted(allowed), where)


@dataclass
class Surface:
    id: str
    name: str
    kind: str
    driver: str
    launch: str
    cwd: str = "."
    env: dict[str, str] = field(default_factory=dict)
    options: dict = field(default_factory=dict)
    preconditions: list[dict] = field(default_factory=list)
    state: str = "disposable"
    reset: str | None = None
    creds: dict[str, str] = field(default_factory=dict)
    record: bool = False
    provenance: dict[str, str] = field(default_factory=dict)
    declined: bool = False


@dataclass
class Config:
    schema_version: int
    generator_version: str
    surfaces: list[Surface] = field(default_factory=list)
    model_profile: str = "default"
    role_overrides: dict[str, str] = field(default_factory=dict)
    budget: dict = field(default_factory=lambda: {"cap_tokens": None})
    test_inbox: dict | None = None
    flows_hash: str = ""


def validate_preconditions(preconditions) -> None:
    if not isinstance(preconditions, list):
        raise ValueError(f"preconditions must be a list, got {type(preconditions).__name__}")
    for index, item in enumerate(preconditions):
        if not isinstance(item, dict):
            raise ValueError(f"preconditions[{index}] must be an object")
        if "cmd" not in item:
            raise ValueError(f"preconditions[{index}] is missing required key 'cmd'")
        _check_keys(item, _PRECONDITION_KEYS, f"preconditions[{index}]")


def _validate_options(surface: Surface) -> None:
    where = f"surfaces[{surface.id!r}].options"
    if surface.driver == "playwright":
        _check_keys(surface.options, set(WEB_OPTION_KEYS), where)
    elif surface.options:
        _check_keys(surface.options, set(), where)


def _validate_surface(surface: Surface) -> None:
    if surface.kind not in VALID_KINDS:
        raise ValueError(
            f"surface {surface.id!r} has unknown kind {surface.kind!r}; expected one of {VALID_KINDS}"
        )
    if surface.driver not in VALID_DRIVERS:
        raise ValueError(
            f"surface {surface.id!r} has unknown driver {surface.driver!r}; expected one of {VALID_DRIVERS}"
        )
    if surface.state not in VALID_STATE:
        raise ValueError(
            f"surface {surface.id!r} has unknown state {surface.state!r}; expected one of {VALID_STATE}"
        )
    for key, value in surface.provenance.items():
        if value not in VALID_PROVENANCE:
            raise ValueError(
                f"surface {surface.id!r} field {key!r} has unknown provenance {value!r}; "
                f"expected one of {VALID_PROVENANCE}"
            )
    validate_preconditions(surface.preconditions)
    _validate_options(surface)


def _validate(cfg: Config) -> None:
    if cfg.model_profile not in VALID_MODEL_PROFILE:
        raise ValueError(
            f"model_profile {cfg.model_profile!r} is unknown; expected one of {VALID_MODEL_PROFILE}"
        )
    for role, model in cfg.role_overrides.items():
        if role not in VALID_ROLES:
            raise ValueError(f"role_overrides has unknown role {role!r}; expected one of {VALID_ROLES}")
        if model not in VALID_ROLE_MODELS:
            raise ValueError(
                f"role_overrides[{role!r}] has unknown model {model!r}; "
                f"expected one of {VALID_ROLE_MODELS}"
            )
    ids = [s.id for s in cfg.surfaces]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"surface id(s) reused across surfaces: {sorted(dupes)}")
    for surface in cfg.surfaces:
        _validate_surface(surface)


def _surface_from_raw(entry, index: int) -> Surface:
    if not isinstance(entry, dict):
        raise ValueError(f"surface at index {index} is not an object")
    name = entry.get("name") or entry.get("id")
    where = f"surfaces[{index}]" + (f" ({name!r})" if name else "")
    _check_keys(entry, _SURFACE_KEYS, where)
    try:
        return Surface(**entry)
    except TypeError as exc:
        raise ValueError(f"surface at {where} is malformed: {exc}") from exc


def load(path: Path) -> Config:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    found = raw.get("schema_version", 0)
    if found > SCHEMA_VERSION:
        raise ConfigVersionError(
            f"{path} was written by a newer flow-review (schema {found} > {SCHEMA_VERSION}). "
            "Update the plugin rather than editing the file."
        )
    _check_keys(raw, _CONFIG_KEYS, "config")
    surfaces = [_surface_from_raw(entry, i) for i, entry in enumerate(raw.get("surfaces", []))]
    cfg = Config(
        schema_version=SCHEMA_VERSION,
        generator_version=raw.get("generator_version", ""),
        surfaces=surfaces,
        model_profile=raw.get("model_profile", "default"),
        role_overrides=raw.get("role_overrides", {}),
        budget=raw.get("budget", {"cap_tokens": None}),
        test_inbox=raw.get("test_inbox"),
        flows_hash=raw.get("flows_hash", ""),
    )
    _validate(cfg)
    return cfg


def save(cfg: Config, path: Path) -> None:
    _validate(cfg)
    text = json.dumps(asdict(cfg), indent=2, ensure_ascii=True) + "\n"
    Path(path).write_text(text, encoding="utf-8")
```

- [ ] **Step 4: Run; expected PASS.**
`python -m pytest plugins/flow-review/engine/flow_review/test_config.py -q` -- all green.

- [ ] **Step 5: Fix the fan-out.** `config.Surface`'s constructor signature changed (`name` no longer
first positional-required-only, `id` is new and required). Every other moved module that builds a
`Surface` directly in its own tests (`test_drift.py`, `test_audit.py`'s `VALID_KINDS` import is
fine, unaffected) breaks. This task does NOT fix `drift.py`/`prove.py`/`audit.py`/`lenses.py`
callers -- that is A7/A8/A9's job in wave 3, since they depend on A2 and run after it. Leaving
`test_drift.py` red between A2 landing and A7 landing is expected and is why A7 is in the same
wave immediately after, not a later one; A2's own verify step (Step 6) scopes the green
requirement to files this task owns.

- [ ] **Step 6: Verify.**
```
python -m pytest plugins/flow-review/engine/flow_review/test_config.py plugins/flow-review/engine/flow_review/test_cli.py -q
```
Expected: green. (Full-suite green is CP1's job, once A7/A8/A9 land in wave 3.)

- [ ] **Commit:**
```
git add plugins/flow-review/engine/flow_review/config.py plugins/flow-review/engine/flow_review/test_config.py
git commit -m "feat(config): v2 schema with surface id, typed web options, model routing, friendly unknown-key errors"
```

---

### Task A3: v1 -> v2 auto-migration, `config.v1.bak`, `flow-review migrate`

**Executor:** opus · **Depends:** A2 · **Wave:** 3

**Files:**
- Create: `plugins/flow-review/engine/flow_review/migrate.py`
- Create: `plugins/flow-review/engine/flow_review/test_migrate.py`
- Modify: `plugins/flow-review/engine/flow_review/cli.py` (replace the `migrate` stub with a real
  subcommand; add `--path` argument, default `.flow-review/config.json` relative to cwd)

**Interfaces:**
- Consumes: `flow_review.config.Surface`, `flow_review.config.Config`,
  `flow_review.config.save` (A2). Reads raw v1 JSON directly (does not go through
  `config.load`, since v1 JSON is not v2-shaped and `load` would reject it).
- Produces:
  - `flow_review.migrate.is_v1(raw: dict) -> bool` -- `True` when `raw.get("schema_version", 1)
    <= 1` (a v1 file never had `schema_version` at all in the original `fr/config.py`, so a
    missing key also means v1; a present `1` is explicit v1; `0`, per `config.py`'s existing
    `test_load_converges_an_older_schema_to_current`, is also treated as pre-v2 and migrated).
  - `flow_review.migrate.migrate(raw: dict) -> tuple[Config, MigrationSummary]` -- pure function,
    no I/O. Builds one v2 `Surface` per v1 surface entry:
    - `id`: `re.sub(r"[^a-z0-9]+", "-", v1_name.lower()).strip("-")`, deduplicated by appending
      `-2`, `-3`, ... on collision (stable, deterministic order = input order).
    - `name`: the v1 `name`, unchanged (this is what makes the migration the origin of the
      id/name split -- id is now derived, name keeps being what the user typed).
    - `kind`, `driver`, `launch`, `preconditions`, `provenance`: carried over unchanged.
    - `destructive: true` -> `state: "persistent"`; `destructive: false`/absent -> `state:
      "disposable"` (A-5, literally).
    - `cwd`, `env`, `options`, `reset`, `creds`, `record`, `declined`: not present in v1, so they
      take their v2 defaults (`"."`, `{}`, `{}`, `None`, `{}`, `False`, `False`).
    - `flow_review.migrate.MigrationSummary` (dataclass): `surfaces_migrated: int, dropped_keys:
      list[str], destructive_to_persistent: list[str]` (surface ids), `id_collisions_resolved:
      dict[str, str]` (v1 name -> final id, only entries that needed de-duplication).
      `dropped_keys` collects, from the top-level v1 object and each surface, any key not
      recognized by v1 OR v2 (i.e. genuinely dead: `lens_sets`, `tester_agent`,
      `evidence_types`, and any `destructive` key IS consumed, not dropped -- it is reported
      separately via `destructive_to_persistent`).
  - `flow_review.migrate.MigrationSummary.render() -> str` -- the one-screen human summary
    (A-5: "print a one-screen summary"), ASCII only (consistent with the rest of the CLI output
    on Windows consoles), format:
    ```
    flow-review: migrated config from schema v1 to v2.
      3 surface(s) migrated.
      destructive -> persistent: checkout, admin-panel
      dropped (no longer used): lens_sets, tester_agent, evidence_types
      a backup of the old file was saved to config.v1.bak
    ```
    (Sections with nothing to report are omitted -- a migration with no destructive surfaces and
    nothing dropped prints only the first two lines.)
  - `flow_review.migrate.migrate_file(path: Path) -> MigrationSummary | None` -- the file-level
    entry point A4/A10/the SKILL's setup flow call before every `config.load()`: reads `path`, if
    `is_v1(raw)` writes `path.with_name(path.name + ".v1.bak")`-- i.e. `config.v1.bak` next to
    `config.json` -- with the untouched original bytes, calls `migrate()`, `config.save()`s the
    v2 result to `path`, prints `summary.render()` to stdout UNLESS `quiet=True` (the unattended
    path -- A-5 "unattended runs migrate silently" -- still migrates and still backs up, it only
    skips the print), and returns the summary. Returns `None` (does nothing, prints nothing) when
    the file at `path` is already v2 or does not exist.
  - `flow-review migrate [--path PATH] [--quiet]` CLI subcommand: calls `migrate_file`, exits 0
    whether or not a migration happened (idempotent: running it twice is a no-op the second
    time), exits 1 on any exception with the exception message on stderr.

- [ ] **Step 1: Write the failing test (full pytest code).**

Create `plugins/flow-review/engine/flow_review/test_migrate.py`:

```python
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
```

- [ ] **Step 2: Run it; expected FAIL.** `ModuleNotFoundError: No module named 'flow_review.migrate'`.

- [ ] **Step 3: Minimal implementation.**

`plugins/flow-review/engine/flow_review/migrate.py`:

```python
"""v1 -> v2 config auto-migration (A-5).

Runs on load, silently on unattended paths. Never guesses at a v1 field's meaning beyond what
A-5 states explicitly: name/kind/driver/launch/preconditions/provenance carry over as-is,
destructive becomes state, lens_sets/evidence_types/tester_agent are dropped. A backup of the
untouched original bytes is always written first, because an auto-migration that cannot be
undone is a rewrite, not a migration.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from flow_review import config as cfgmod

_V1_SURFACE_KNOWN = {
    "name", "kind", "driver", "launch", "preconditions", "destructive", "provenance",
}
_V1_TOP_KNOWN = {
    "schema_version", "generator_version", "surfaces", "lens_sets", "tester_agent",
    "evidence_types", "flows_hash",
}


def is_v1(raw: dict) -> bool:
    return raw.get("schema_version", 1) <= 1


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "surface"


@dataclass
class MigrationSummary:
    surfaces_migrated: int = 0
    dropped_keys: list[str] = field(default_factory=list)
    destructive_to_persistent: list[str] = field(default_factory=list)
    id_collisions_resolved: dict[str, str] = field(default_factory=dict)

    def render(self) -> str:
        lines = [
            "flow-review: migrated config from schema v1 to v2.",
            f"  {self.surfaces_migrated} surface(s) migrated.",
        ]
        if self.destructive_to_persistent:
            lines.append("  destructive -> persistent: " + ", ".join(self.destructive_to_persistent))
        if self.dropped_keys:
            lines.append("  dropped (no longer used): " + ", ".join(self.dropped_keys))
        lines.append("  a backup of the old file was saved to config.v1.bak")
        return "\n".join(lines)


def migrate(raw: dict) -> tuple[cfgmod.Config, MigrationSummary]:
    summary = MigrationSummary()
    dropped: set[str] = set()
    for key in raw:
        if key not in _V1_TOP_KNOWN:
            dropped.add(key)
    for key in ("lens_sets", "tester_agent", "evidence_types"):
        if key in raw:
            dropped.add(key)
    summary.dropped_keys = sorted(dropped)

    surfaces: list[cfgmod.Surface] = []
    used_ids: dict[str, int] = {}
    for entry in raw.get("surfaces", []):
        for key in entry:
            if key not in _V1_SURFACE_KNOWN:
                if key not in summary.dropped_keys:
                    summary.dropped_keys.append(key)

        name = entry.get("name", "")
        base_id = _slug(name)
        count = used_ids.get(base_id, 0) + 1
        used_ids[base_id] = count
        surface_id = base_id if count == 1 else f"{base_id}-{count}"
        if count > 1:
            summary.id_collisions_resolved[name] = surface_id

        state = "persistent" if entry.get("destructive") else "disposable"
        if entry.get("destructive"):
            summary.destructive_to_persistent.append(surface_id)

        surfaces.append(cfgmod.Surface(
            id=surface_id,
            name=name,
            kind=entry.get("kind", ""),
            driver=entry.get("driver", ""),
            launch=entry.get("launch", ""),
            preconditions=entry.get("preconditions", []),
            state=state,
            provenance=entry.get("provenance", {}),
        ))
        summary.surfaces_migrated += 1

    summary.dropped_keys = sorted(set(summary.dropped_keys))
    cfg = cfgmod.Config(
        schema_version=cfgmod.SCHEMA_VERSION,
        generator_version=raw.get("generator_version", ""),
        surfaces=surfaces,
        flows_hash=raw.get("flows_hash", ""),
    )
    return cfg, summary


def migrate_file(path: Path, quiet: bool = False) -> MigrationSummary | None:
    path = Path(path)
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not is_v1(raw):
        return None

    backup = path.with_name(path.name + ".v1.bak")
    backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    cfg, summary = migrate(raw)
    cfgmod.save(cfg, path)
    if not quiet:
        print(summary.render())
    return summary
```

Wire the CLI subcommand in `cli.py`: replace the `migrate` entry in `_STUB_VERBS`'s loop with a
dedicated parser:

```python
# in build_parser(), instead of the generic stub loop entry for "migrate":
migrate_parser = sub.add_parser("migrate")
migrate_parser.add_argument("--path", default=".flow-review/config.json")
migrate_parser.add_argument("--quiet", action="store_true")
migrate_parser.set_defaults(func=_run_migrate)
```
and add:
```python
def _run_migrate(args: argparse.Namespace) -> int:
    from pathlib import Path
    from flow_review import migrate as migratemod
    try:
        migratemod.migrate_file(Path(args.path), quiet=args.quiet)
    except Exception as exc:  # noqa: BLE001 -- CLI boundary, report and exit, never traceback
        print(str(exc), file=sys.stderr)
        return 1
    return 0
```
(remove `"migrate"` from `_STUB_VERBS`.)

- [ ] **Step 4: Run; expected PASS.**
`python -m pytest plugins/flow-review/engine/flow_review/test_migrate.py plugins/flow-review/engine/flow_review/test_cli.py -q`

- [ ] **Step 5: Verify.**
```
python -m pytest -q
```
Expected: green (A3 does not touch any file A2 left red -- `test_drift.py` etc. are still A7/A8/A9's job).

- [ ] **Commit:**
```
git add plugins/flow-review/engine/flow_review/migrate.py plugins/flow-review/engine/flow_review/test_migrate.py plugins/flow-review/engine/flow_review/cli.py
git commit -m "feat(migrate): auto-migrate v1 config to v2 with backup and one-screen summary"
```

---

### Task A4: Event writer -- `events.append()`, `flow-review event` CLI, ms UTC timestamps, finding ids, secret redaction hook

**Executor:** sonnet · **Depends:** A1 · **Wave:** 2

**Files:**
- Create: `plugins/flow-review/engine/flow_review/events.py`
- Create: `plugins/flow-review/engine/flow_review/test_events.py`
- Modify: `plugins/flow-review/engine/flow_review/cli.py` (replace the `event` stub with a real
  subcommand)
- Modify: `plugins/flow-review/skills/flow-review/references/evidence.md` (lines 33-46, the
  append idiom section -- replaced in full, see Step 5)
- Modify: `plugins/flow-review/skills/flow-review/test_references.py`
  (`test_evidence_file_keeps_the_append_idiom_rules`, rewritten to match the new wording)

**Interfaces:**
- Consumes: nothing from other A-tasks (only needs A1's package layout).
- Produces (relied on by A5, A6/A10 redaction wiring, B-series event emission, E1/E2 dashboard):
  - `flow_review.events.now_iso() -> str` -- UTC, millisecond precision, `Z` suffix, e.g.
    `"2026-09-23T14:05:07.123Z"`. Implemented as
    `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{microsecond // 1000:03d}Z"`
    style formatting (exact form below in Step 3).
  - `flow_review.events.register_secret(value: str) -> None` -- adds a literal string to the
    module-level redaction registry. A10 calls this once per credential value it resolves from
    `.env` at startup; nothing else populates it in M1.
  - `flow_review.events.clear_secrets() -> None` -- empties the registry; test-only, also useful
    for a long-lived process (the dashboard server, `serve.py` in E1) that reloads config.
  - `flow_review.events.redact(value)` -- recursively walks a JSON-safe value (dict/list/str/
    other); every string that CONTAINS a registered secret as a substring has that substring
    replaced with `flow_review.events.REDACTED = "[redacted]"`, applied longest-secret-first so a
    short secret that is a substring of a longer one never partially un-redacts it. Non-string,
    non-container values pass through unchanged.
  - `flow_review.events.append(run_dir: Path, event: dict) -> dict` -- the one writer every
    caller (CLI, engine modules, later the ledger) uses. Behavior:
    - Copies `event` (never mutates the caller's dict).
    - Sets `ts = now_iso()` if `event` did not already carry a `ts` (a caller replaying a
      recorded event, e.g. `flow-review replay` re-emitting a historical line, supplies its own).
    - If `event.get("type") == "finding"` and no `id` key is present, sets `id =
      uuid.uuid4().hex`. A caller that already knows the ledger fingerprint id (A5, once it
      exists) passes `id` itself and this path is a no-op -- A4 never computes a fingerprint
      itself, it only guarantees every finding event HAS an id, computed or supplied.
    - Applies `redact()` to the whole event dict.
    - Serializes with `json.dumps(event, ensure_ascii=True)` only (never string formatting,
      never an f-string of the payload -- the H8 defect this task fixes) and appends
      `line + "\n"` to `<run_dir>/events.jsonl`, opened `"a"`, `encoding="utf-8"`, and closed
      before returning (one open/append/close per call -- concurrent writers from multiple
      testers is an existing, unchanged assumption per evidence.md).
    - Returns the final dict actually written (with `ts`/`id` filled and redaction applied), so
      a caller that wants to also mirror the event elsewhere (a future in-memory tail) has the
      real value.
  - `flow-review event --run RUN_DIR --type TYPE [--json JSON] [key=value ...]` CLI subcommand.
    Precedence: start from `json.loads(args.json)` if `--json` given (else `{}`), then apply each
    `key=value` positional as a string-valued override (so `--json '{"sev":"P1"}' text="oops"`
    is `{"sev": "P1", "text": "oops"}`), then set `event["type"] = args.type` last (the `--type`
    flag always wins, so a `--json` blob accidentally carrying its own `type` cannot silently
    diverge from the flag a script author actually meant). Calls `events.append`. Prints nothing
    on success (exit 0); a malformed `--json` or a `key=value` argument with no `=` exits 2 with
    a one-line message on stderr.

- [ ] **Step 1: Write the failing test (full pytest code).**

Create `plugins/flow-review/engine/flow_review/test_events.py`:

```python
from __future__ import annotations

import json
import re
import uuid

import pytest

from flow_review import events


@pytest.fixture(autouse=True)
def _clean_registry():
    events.clear_secrets()
    yield
    events.clear_secrets()


def test_now_iso_has_millisecond_precision_and_z_suffix():
    ts = events.now_iso()
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$", ts), ts


def test_append_writes_one_json_line_built_with_json_dumps(tmp_path):
    written = events.append(tmp_path, {"type": "step", "surface": "web", "state": "ok"})
    text = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert text.count("\n") == 1
    line = json.loads(text.strip())
    assert line == written
    assert line["type"] == "step"
    assert "ts" in line


def test_append_fills_ts_only_when_absent(tmp_path):
    written = events.append(tmp_path, {"type": "step", "ts": "2020-01-01T00:00:00.000Z"})
    assert written["ts"] == "2020-01-01T00:00:00.000Z"


def test_append_never_mutates_the_caller_dict(tmp_path):
    original = {"type": "step"}
    events.append(tmp_path, original)
    assert original == {"type": "step"}


def test_finding_event_gets_a_uuid_id_when_none_supplied(tmp_path):
    written = events.append(tmp_path, {"type": "finding", "sev": "P1", "text": "x"})
    assert "id" in written
    assert uuid.UUID(written["id"])  # a valid uuid4 hex round-trips


def test_finding_event_keeps_a_supplied_id(tmp_path):
    written = events.append(tmp_path, {"type": "finding", "id": "ledger-fp-123", "text": "x"})
    assert written["id"] == "ledger-fp-123"


def test_non_finding_events_get_no_id(tmp_path):
    written = events.append(tmp_path, {"type": "step"})
    assert "id" not in written


def test_registered_secret_is_redacted_in_event_values(tmp_path):
    events.register_secret("hunter2")
    written = events.append(tmp_path, {"type": "step", "text": "logged in with hunter2 ok"})
    assert "hunter2" not in written["text"]
    assert events.REDACTED in written["text"]
    on_disk = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert "hunter2" not in on_disk


def test_redaction_applies_to_nested_values(tmp_path):
    events.register_secret("s3cr3t")
    written = events.append(tmp_path, {"type": "step", "detail": {"body": ["contains s3cr3t here"]}})
    assert "s3cr3t" not in json.dumps(written)


def test_longer_secret_redacted_before_a_shorter_substring_of_it(tmp_path):
    events.register_secret("ab")
    events.register_secret("abcdef")
    written = events.append(tmp_path, {"type": "step", "text": "value is abcdef exactly"})
    assert written["text"] == f"value is {events.REDACTED} exactly"


def test_clear_secrets_empties_the_registry(tmp_path):
    events.register_secret("topsecret")
    events.clear_secrets()
    written = events.append(tmp_path, {"type": "step", "text": "topsecret shown"})
    assert written["text"] == "topsecret shown"


def test_multiple_appends_are_all_present_and_line_delimited(tmp_path):
    events.append(tmp_path, {"type": "step", "n": 1})
    events.append(tmp_path, {"type": "step", "n": 2})
    lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(l)["n"] for l in lines] == [1, 2]
```

- [ ] **Step 2: Run it; expected FAIL.** `ModuleNotFoundError: No module named 'flow_review.events'`.

- [ ] **Step 3: Minimal implementation.**

`plugins/flow-review/engine/flow_review/events.py`:

```python
"""The append-only event writer every tester and the engine itself use (A-4 / audit H8).

Every line is built with json.dumps and nothing else -- the v1 `printf "$TEXT"` idiom this
replaces was shell-injectable the moment `text` contained a double quote, and interpolating a
finding's own words into a shell string is exactly the kind of value that will eventually
contain one. This module is the only writer; the CLI subcommand is the only caller a tester
needs, so no script ever hand-builds a JSON string again.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

REDACTED = "[redacted]"

_secrets: set[str] = set()


def register_secret(value: str) -> None:
    if value:
        _secrets.add(value)


def clear_secrets() -> None:
    _secrets.clear()


def now_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _redact_str(text: str) -> str:
    if not _secrets:
        return text
    for secret in sorted(_secrets, key=len, reverse=True):
        if secret in text:
            text = text.replace(secret, REDACTED)
    return text


def redact(value):
    if isinstance(value, str):
        return _redact_str(value)
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def append(run_dir: Path, event: dict) -> dict:
    out = dict(event)
    out.setdefault("ts", now_iso())
    if out.get("type") == "finding" and "id" not in out:
        out["id"] = uuid.uuid4().hex
    out = redact(out)

    run_dir = Path(run_dir)
    line = json.dumps(out, ensure_ascii=True)
    with (run_dir / "events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    return out
```

Wire the CLI subcommand in `cli.py`: replace the generic `event` stub entry with:

```python
event_parser = sub.add_parser("event")
event_parser.add_argument("--run", required=True, dest="run_dir")
event_parser.add_argument("--type", required=True, dest="type_")
event_parser.add_argument("--json", default=None)
event_parser.add_argument("fields", nargs="*")
event_parser.set_defaults(func=_run_event)
```
and:
```python
def _run_event(args: argparse.Namespace) -> int:
    from pathlib import Path
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
```
(add `import json` at the top of `cli.py`; remove `"event"` from `_STUB_VERBS`.)

- [ ] **Step 4: Run; expected PASS.**
`python -m pytest plugins/flow-review/engine/flow_review/test_events.py plugins/flow-review/engine/flow_review/test_cli.py -q`

- [ ] **Step 5: Update the reference doc.** Replace lines 33-46 of
`plugins/flow-review/skills/flow-review/references/evidence.md` (the `### The append idiom`
section) with:

````markdown
### The append idiom -- use exactly this

```bash
flow-review event --run "$RUN" --type step surface=<surface-name> flow=f1 step="open the target screen" state=ok
```

- The `flow-review event` CLI is the only way to write to `events.jsonl`. Never hand-build a
  JSON line and never use `printf`/`>>`/`Add-Content` directly -- the CLI owns the timestamp
  (millisecond UTC, `Z` suffix), assigns every `finding` event its id, and redacts any
  registered secret before the line touches disk.
- Pass `--json '{"sev":"P1","text":"..."}'` for a payload with nested values, or plain
  `key=value` arguments for the common flat case -- both may be combined; `--type` always wins
  over a `type` key inside `--json`.
- Escape `"` and newlines inside a `text` value the normal way for your shell; the CLI itself
  never shells out to build the line.
- **Never rewrite the file. Never read it back.** Multiple writers append concurrently; it is
  not yours alone.
````

(The rest of `evidence.md` -- sections 1's table and section 2's evidence rules -- is unchanged;
only the append-idiom subsection is replaced.)

Update `test_evidence_file_keeps_the_append_idiom_rules` in
`plugins/flow-review/skills/flow-review/test_references.py`:

```python
def test_evidence_file_keeps_the_append_idiom_rules():
    text = (REFS / "evidence.md").read_text(encoding="utf-8")
    assert "events.jsonl" in text
    assert "flow-review event" in text
    assert "printf" not in text
```

- [ ] **Step 6: Run; expected PASS.**
`python -m pytest plugins/flow-review/skills/flow-review/test_references.py -q`

- [ ] **Step 7: Verify.**
```
python -m pytest -q
```
Expected: green (scoped the same way A2/A3 are -- the drift/prove/audit/lenses fan-out from A2
is still owned by A7/A8/A9, unaffected by A4).

- [ ] **Commit:**
```
git add plugins/flow-review/engine/flow_review/events.py plugins/flow-review/engine/flow_review/test_events.py plugins/flow-review/engine/flow_review/cli.py plugins/flow-review/skills/flow-review/references/evidence.md plugins/flow-review/skills/flow-review/test_references.py
git commit -m "feat(events): JSON-safe event writer with ms timestamps, finding ids, secret redaction; retire the printf idiom"
```

---

### Task A5: Ledger -- `.flow-review/findings.json`, sha1 fingerprint, states + transitions, aliases, suppressions, discoverability tally

**Executor:** opus · **Depends:** A4 · **Wave:** 3

**Files:**
- Create: `plugins/flow-review/engine/flow_review/ledger.py`
- Create: `plugins/flow-review/engine/flow_review/test_ledger.py`
- Delete: `plugins/flow-review/engine/flow_review/findings.py`,
  `plugins/flow-review/engine/flow_review/test_findings.py` (the v1 prose `demote_repeats` and
  its tests -- audit C4; superseded in full by this task)

**Interfaces (per the plan's Canonical Interfaces section -- binding, matched exactly):**
- Consumes: `flow_review.events.now_iso` (A4), for `first_run`/`last_run` timestamps when a
  caller does not supply its own `run_id`.
- Produces (relied on by A6 (nothing directly), B3 replay, B8 budget medians, C3/C5/C6
  triage/validation/suppressions, E2 dashboard state fold):
  - `flow_review.ledger.STATES = ("open", "fixed", "regressed", "refuted", "false-positive",
    "wont-fix", "accepted")`
  - `flow_review.ledger.fingerprint(flow_id: str, rule: str, route: str, locator: str) -> str`
    -- `hashlib.sha1("|".join((flow_id, rule, route, locator)).encode("utf-8")).hexdigest()`
    (A-6, literally: flow_id, lens-or-engine-rule-id, route template, semantic locator). Note
    this signature does NOT take `surface_id` -- the Canonical Interfaces entry for `ledger.
    fingerprint` lists exactly these four arguments; `surface_id` is carried on `LedgerEntry` as
    informational/filtering data, never part of the identity hash.
  - `class LedgerEntry` (dataclass), field order and names exactly per Canonical Interfaces:
    `id: str, fingerprint: str, surface_id: str, flow_id: str, rule: str, route: str, locator:
    str, sev: str, text: str, evidence: list[str] = field(default_factory=list), disposition: str
    = "engine" ("engine"|"objective"|"judgment", copied from the finding payload), state: str =
    "open", runs_seen: int = 1, first_run: str = "", last_run: str = "", aliases: list[str] =
    field(default_factory=list), reason: str = ""`. `reason` (renamed from an earlier draft's
    `refuted_reason`) holds either the verifier's refute reason OR a triage note -- it is not
    refute-only; C6's `triage.apply(..., reason=...)` writes it for any state, required only
    when the target state is `refuted`.
  - `class Ledger` (dataclass): `findings: dict[str, LedgerEntry] = field(default_factory=dict)`
    (keyed by `LedgerEntry.id`), `discoverability_misses: dict[str, list[str]] = field(
    default_factory=dict)` (function/goal name -> list of distinct cold-run ids that missed it,
    per A-8).
  - `flow_review.ledger.load(path: Path) -> Ledger` / `flow_review.ledger.save(ledger: Ledger,
    path: Path) -> None` -- JSON round-trip; `load` of a missing file returns an empty `Ledger()`
    (a first run has no ledger yet, same "nothing to protect" stance as A6's manifest module).
    `path` is always `<project_root>/.flow-review/findings.json` by convention (Canonical
    Interfaces); the caller assembles that path, `ledger.load`/`save` take it as given.

  **Example `.flow-review/findings.json`:**
  ```json
  {
    "schema_version": 1,
    "findings": {
      "9f2c1a...": {
        "id": "9f2c1a...",
        "fingerprint": "b7e1...",
        "surface_id": "web-app",
        "flow_id": "checkout",
        "rule": "contrast",
        "route": "/cart",
        "locator": "role=button[name=\"Checkout\"]",
        "sev": "P1",
        "text": "3.1:1 contrast on the checkout button, token requires 4.5:1",
        "evidence": ["shots/web-app-checkout-01.png"],
        "disposition": "engine",
        "state": "open",
        "runs_seen": 3,
        "first_run": "2026-09-01T10:00:00.000Z",
        "last_run": "2026-09-23T10:00:00.000Z",
        "aliases": [],
        "reason": ""
      }
    },
    "discoverability_misses": {
      "export-csv": ["run-2026-09-01", "run-2026-09-10"]
    }
  }
  ```

  - `flow_review.ledger.reconcile(ledger: Ledger, findings: list[dict], flows_run: set[str],
    run_id: str, alias_decisions: dict[str, str] | None = None) -> Ledger` -- the transition
    engine (A-6 + A-4's "seen again -> open/regressed; not seen on a flow that ran -> fixed; the
    flow didn't run -> unchanged"). Each item of `findings` is `{"surface_id", "flow_id", "rule",
    "route", "locator", "sev", "text", "evidence"}` for one finding observed THIS run (`evidence`
    is a `list[str]`, defaulting to `[]` when a caller omits it). `alias_decisions` maps a new
    finding's computed fingerprint to an EXISTING entry id it should be folded into (the
    mechanism the Haiku triage step, C6, drives; A5 does not decide same/new itself, it only
    executes the decision once made -- reconcile called with no `alias_decisions` never
    auto-aliases, and an unmatched new fingerprint always becomes its own new entry). Rules,
    applied per existing entry first, then per new/unmatched finding:
    1. **Entry's flow did not run this run** (`entry.flow_id not in flows_run`): entry is
       untouched -- no state change, no `runs_seen` change, no `last_run` change. (The
       "the flow didn't run -> unchanged" case.)
    2. **Entry's flow ran and its fingerprint IS in this run's findings**: `runs_seen += 1`,
       `last_run = run_id`, `evidence` is replaced with this run's freshly observed `evidence`
       list (stale evidence pointing at a since-cleaned-up run folder is worse than none; the
       CLAIM's identity is the fingerprint, not the evidence paths, so refreshing evidence never
       creates a new entry). State transition: `fixed -> regressed` (a reappearance after being
       marked fixed is a regression); `open`, `regressed`, `accepted` stay as they are;
       `refuted`, `false-positive`, `wont-fix` ALSO stay as they are -- this is decision **A-15**
       (Appendix A), stated exactly: "Triaged states (false-positive, wont-fix, accepted) and
       refuted are sticky; `runs_seen` keeps counting; the finding stays in the collapsed
       sections. The user reopens it manually (drawer or `flow-review triage ID open`)." A5
       ships the sticky-state half of A-15 (this rule) and the "stays in the collapsed sections"
       half is E2's job (dashboard state fold), not this module's.
    3. **Entry's flow ran and its fingerprint is NOT in this run's findings**: if state was
       `open` or `regressed`, state becomes `fixed`, `last_run = run_id`. Any other state is
       untouched (a `refuted`/`false-positive`/`wont-fix`/`accepted` finding not reproducing
       this run is not news -- it was never expected to reproduce; this is also A-15's
       stickiness, applied to the non-reappearance side).
    4. **A finding this run has no matching existing fingerprint**: if `alias_decisions` maps its
       fingerprint to an existing entry id, that entry's `aliases` list gains a synthetic alias
       id (see `record_alias` below) and its `runs_seen`/`last_run`/`evidence` update as in rule
       2 instead of a new entry being created. Otherwise a new `LedgerEntry` is created: `id =
       uuid.uuid4().hex`, `state = "open"`, `runs_seen = 1`, `first_run = last_run = run_id`,
       `surface_id`/`evidence` copied straight from the finding dict.
    Returns the same `Ledger` object, mutated in place (and returned for chaining/assignment
    convenience).
  - `flow_review.ledger.find_alias_candidates(ledger: Ledger, flow_id: str, rule: str, route:
    str) -> list[LedgerEntry]` -- open-ish (`state in ("open", "regressed")`) entries sharing
    `flow_id` + `rule` + `route` but a DIFFERENT `locator`. This is the candidate set a triage
    step (C6) hands to Haiku to decide same-claim-different-selector vs genuinely new; A5 only
    surfaces the candidates, never judges them.
  - `flow_review.ledger.record_alias(ledger: Ledger, canonical_id: str, alias_fingerprint: str)
    -> None` -- appends `alias_fingerprint` to `ledger.findings[canonical_id].aliases` if not
    already present. Raises `KeyError` if `canonical_id` is not in the ledger.
  - `flow_review.ledger.suppressions_for(ledger: Ledger, rule: str) -> list[dict]` -- returns
    `[{"route": e.route, "locator": e.locator, "text": e.text, "state": e.state} for e in
    ledger.findings.values() if e.rule == rule and e.state in ("false-positive", "wont-fix")]`,
    ordered by `last_run` ascending. This is what feeds back into a lens prompt as a suppression
    list (spec Section 8: "False-positive marks feed back into the lens prompts as
    suppressions") -- C3 (lens rewrite) consumes it, A5 only produces it. Per Canonical
    Interfaces ("there is no separate suppression store"), this is a live filter over
    `ledger.findings`, never a second persisted collection.
  - `flow_review.ledger.record_miss(ledger: Ledger, function: str, run_id: str) -> int` -- adds
    `run_id` to `ledger.discoverability_misses.setdefault(function, [])` if not already present
    (idempotent per run_id -- calling it twice in the same run does not double-count), returns
    the resulting distinct-run count.
  - `flow_review.ledger.missed_twice(ledger: Ledger, function: str) -> bool` -- `len(
    ledger.discoverability_misses.get(function, [])) >= 2` (A-8: "a P2 discoverability finding
    once the ledger shows the same function missed in 2 cold runs" -- A5 ships the counter and
    the threshold check; C4 (explorer/goals) is the caller that turns a `True` here into an
    actual P2 finding, never P1, never Opus-verified, per A-8).

- [ ] **Step 1: Write the failing test (full pytest code).**

Create `plugins/flow-review/engine/flow_review/test_ledger.py`:

```python
from __future__ import annotations

from flow_review import ledger


def _finding(surface_id="web-app", flow_id="checkout", rule="contrast", route="/cart",
             locator="button[name=Pay]", sev="P1", text="low contrast", evidence=None):
    return dict(
        surface_id=surface_id, flow_id=flow_id, rule=rule, route=route, locator=locator,
        sev=sev, text=text, evidence=evidence if evidence is not None else ["shots/01.png"],
    )


def test_a_new_entry_keeps_the_finding_disposition():
    led = ledger.reconcile(ledger.Ledger(), [dict(_finding(), disposition="judgment")],
                           {"checkout"}, "run-1")
    assert next(iter(led.findings.values())).disposition == "judgment"


def test_fingerprint_is_stable_for_the_same_four_inputs():
    a = ledger.fingerprint("checkout", "contrast", "/cart", "button[name=Pay]")
    b = ledger.fingerprint("checkout", "contrast", "/cart", "button[name=Pay]")
    assert a == b


def test_fingerprint_changes_when_locator_changes():
    a = ledger.fingerprint("checkout", "contrast", "/cart", "button[name=Pay]")
    b = ledger.fingerprint("checkout", "contrast", "/cart", "button[name=Cancel]")
    assert a != b


def test_round_trip_preserves_entries(tmp_path):
    led = ledger.Ledger()
    led = ledger.reconcile(led, [_finding()], flows_run={"checkout"}, run_id="run-1")
    path = tmp_path / "findings.json"
    ledger.save(led, path)
    back = ledger.load(path)
    assert back == led


def test_missing_ledger_file_loads_as_empty(tmp_path):
    led = ledger.load(tmp_path / "does-not-exist.json")
    assert led == ledger.Ledger()


def test_a_new_finding_opens_with_runs_seen_one_and_carries_surface_id_and_evidence(tmp_path):
    led = ledger.reconcile(ledger.Ledger(), [_finding()], {"checkout"}, "run-1")
    (entry,) = led.findings.values()
    assert entry.state == "open"
    assert entry.runs_seen == 1
    assert entry.first_run == entry.last_run == "run-1"
    assert entry.surface_id == "web-app"
    assert entry.evidence == ["shots/01.png"]


def test_seen_again_increments_runs_seen_and_stays_open(tmp_path):
    led = ledger.Ledger()
    led = ledger.reconcile(led, [_finding()], {"checkout"}, "run-1")
    led = ledger.reconcile(led, [_finding()], {"checkout"}, "run-2")
    (entry,) = led.findings.values()
    assert entry.state == "open"
    assert entry.runs_seen == 2
    assert entry.last_run == "run-2"
    assert entry.first_run == "run-1"


def test_not_seen_on_a_flow_that_ran_becomes_fixed(tmp_path):
    led = ledger.reconcile(ledger.Ledger(), [_finding()], {"checkout"}, "run-1")
    led = ledger.reconcile(led, [], {"checkout"}, "run-2")
    (entry,) = led.findings.values()
    assert entry.state == "fixed"


def test_flow_that_did_not_run_is_untouched(tmp_path):
    led = ledger.reconcile(ledger.Ledger(), [_finding()], {"checkout"}, "run-1")
    led = ledger.reconcile(led, [], flows_run=set(), run_id="run-2")
    (entry,) = led.findings.values()
    assert entry.state == "open"
    assert entry.runs_seen == 1
    assert entry.last_run == "run-1"


def test_reappearing_after_fixed_is_regressed(tmp_path):
    led = ledger.reconcile(ledger.Ledger(), [_finding()], {"checkout"}, "run-1")
    led = ledger.reconcile(led, [], {"checkout"}, "run-2")  # -> fixed
    led = ledger.reconcile(led, [_finding()], {"checkout"}, "run-3")  # -> regressed
    (entry,) = led.findings.values()
    assert entry.state == "regressed"
    assert entry.runs_seen == 2


def test_a_refuted_finding_reappearing_stays_refuted_not_resurfaced(tmp_path):
    # A-15: triaged states (false-positive, wont-fix, accepted) and refuted are sticky; the
    # finding stays visible with its reason, runs_seen keeps counting, and only a manual
    # reopen (drawer or `flow-review triage ID open`) changes the state.
    led = ledger.reconcile(ledger.Ledger(), [_finding()], {"checkout"}, "run-1")
    (entry,) = led.findings.values()
    entry.state = "refuted"
    entry.reason = "measured contrast was 4.6:1, above the token requirement"
    led = ledger.reconcile(led, [_finding()], {"checkout"}, "run-2")
    (entry,) = led.findings.values()
    assert entry.state == "refuted"
    assert entry.reason == "measured contrast was 4.6:1, above the token requirement"
    assert entry.runs_seen == 2  # still tracked, per A-15


def test_evidence_refreshes_to_the_latest_run_when_a_finding_reappears(tmp_path):
    led = ledger.reconcile(ledger.Ledger(), [_finding(evidence=["shots/run1.png"])], {"checkout"}, "run-1")
    led = ledger.reconcile(led, [_finding(evidence=["shots/run2.png"])], {"checkout"}, "run-2")
    (entry,) = led.findings.values()
    assert entry.evidence == ["shots/run2.png"]


def test_find_alias_candidates_matches_same_flow_rule_route_different_locator():
    led = ledger.reconcile(ledger.Ledger(), [_finding(locator="button[name=Pay]")], {"checkout"}, "run-1")
    candidates = ledger.find_alias_candidates(led, "checkout", "contrast", "/cart")
    assert len(candidates) == 1
    assert candidates[0].locator == "button[name=Pay]"


def test_alias_decision_folds_a_new_fingerprint_into_the_canonical_entry(tmp_path):
    led = ledger.reconcile(ledger.Ledger(), [_finding(locator="button[name=Pay]")], {"checkout"}, "run-1")
    (canonical,) = led.findings.values()
    renamed = _finding(locator="button[name=\"Pay now\"]")
    new_fp = ledger.fingerprint(renamed["flow_id"], renamed["rule"], renamed["route"], renamed["locator"])
    led = ledger.reconcile(
        led, [renamed], {"checkout"}, "run-2",
        alias_decisions={new_fp: canonical.id},
    )
    assert len(led.findings) == 1
    entry = led.findings[canonical.id]
    assert new_fp in entry.aliases
    assert entry.runs_seen == 2


def test_record_alias_is_idempotent_and_raises_for_unknown_canonical():
    led = ledger.reconcile(ledger.Ledger(), [_finding()], {"checkout"}, "run-1")
    (entry,) = led.findings.values()
    ledger.record_alias(led, entry.id, "some-fp")
    ledger.record_alias(led, entry.id, "some-fp")
    assert led.findings[entry.id].aliases == ["some-fp"]
    import pytest
    with pytest.raises(KeyError):
        ledger.record_alias(led, "no-such-id", "fp")


def test_suppressions_for_returns_only_false_positive_and_wont_fix_entries_of_that_rule():
    led = ledger.reconcile(ledger.Ledger(), [
        _finding(rule="contrast", locator="a"),
        _finding(rule="contrast", locator="b"),
        _finding(rule="copy", locator="c"),
    ], {"checkout"}, "run-1")
    ids = list(led.findings)
    led.findings[ids[0]].state = "false-positive"
    led.findings[ids[1]].state = "wont-fix"
    suppressed = ledger.suppressions_for(led, "contrast")
    assert len(suppressed) == 2
    assert all(s["locator"] in ("a", "b") for s in suppressed)


def test_record_miss_counts_distinct_runs_not_calls():
    led = ledger.Ledger()
    ledger.record_miss(led, "export-csv", "run-1")
    ledger.record_miss(led, "export-csv", "run-1")  # same run, no double count
    assert ledger.missed_twice(led, "export-csv") is False
    ledger.record_miss(led, "export-csv", "run-2")
    assert ledger.missed_twice(led, "export-csv") is True
```

- [ ] **Step 2: Run it; expected FAIL.** `ModuleNotFoundError: No module named 'flow_review.ledger'`.

- [ ] **Step 3: Minimal implementation.**

`plugins/flow-review/engine/flow_review/ledger.py`:

```python
"""The findings ledger (A-6, audit C4). Stable ids, a semantic fingerprint (never prose), the
seven-state lifecycle, aliasing for a renamed selector, suppressions for the lens prompts, and
the cross-run discoverability tally A-8 needs. Replaces fr.findings' exact-prose fingerprint,
which could never accumulate runs_seen past 2 because nothing persisted between runs.

Sticky-state reappearance (A-15): a finding whose state is a human's triage call
(false-positive, wont-fix, accepted) or the verifier's `refuted` never flips back to `open` on
its own just because it was observed again -- only a manual reopen does that. `reconcile` is
where this rule lives.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

STATES = ("open", "fixed", "regressed", "refuted", "false-positive", "wont-fix", "accepted")
_REAPPEARING_STAYS = {"open", "regressed", "accepted", "refuted", "false-positive", "wont-fix"}
_FIXABLE = {"open", "regressed"}


def fingerprint(flow_id: str, rule: str, route: str, locator: str) -> str:
    return hashlib.sha1("|".join((flow_id, rule, route, locator)).encode("utf-8")).hexdigest()


@dataclass
class LedgerEntry:
    id: str
    fingerprint: str
    surface_id: str
    flow_id: str
    rule: str
    route: str
    locator: str
    sev: str
    text: str
    evidence: list[str] = field(default_factory=list)
    disposition: str = "engine"
    state: str = "open"
    runs_seen: int = 1
    first_run: str = ""
    last_run: str = ""
    aliases: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class Ledger:
    findings: dict[str, LedgerEntry] = field(default_factory=dict)
    discoverability_misses: dict[str, list[str]] = field(default_factory=dict)


def load(path: Path) -> Ledger:
    path = Path(path)
    if not path.exists():
        return Ledger()
    raw = json.loads(path.read_text(encoding="utf-8"))
    findings = {k: LedgerEntry(**v) for k, v in raw.get("findings", {}).items()}
    return Ledger(findings=findings, discoverability_misses=raw.get("discoverability_misses", {}))


def save(ledger_: Ledger, path: Path) -> None:
    raw = {
        "schema_version": 1,
        "findings": {k: asdict(v) for k, v in ledger_.findings.items()},
        "discoverability_misses": ledger_.discoverability_misses,
    }
    Path(path).write_text(json.dumps(raw, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def reconcile(
    ledger_: Ledger, findings: list[dict], flows_run: set[str], run_id: str,
    alias_decisions: dict[str, str] | None = None,
) -> Ledger:
    alias_decisions = alias_decisions or {}
    current_fps = {
        fingerprint(f["flow_id"], f["rule"], f["route"], f["locator"]): f for f in findings
    }

    # Rule 1-3: transition every EXISTING entry against this run's observations.
    for entry in ledger_.findings.values():
        if entry.flow_id not in flows_run:
            continue  # rule 1: flow did not run -> untouched
        if entry.fingerprint in current_fps:
            f = current_fps[entry.fingerprint]
            entry.runs_seen += 1
            entry.last_run = run_id
            entry.evidence = f.get("evidence", entry.evidence)
            if entry.state == "fixed":
                entry.state = "regressed"
            # else: open/regressed/accepted/refuted/false-positive/wont-fix all stay as-is,
            # per A-15 -- a human's triage call is never silently overridden by a reappearance.
            del current_fps[entry.fingerprint]  # consumed: not a "new" finding below
        else:
            if entry.state in _FIXABLE:
                entry.state = "fixed"
                entry.last_run = run_id

    # Rule 4: whatever fingerprint is left in current_fps had no existing entry this run.
    for fp, f in current_fps.items():
        canonical_id = alias_decisions.get(fp)
        if canonical_id and canonical_id in ledger_.findings:
            record_alias(ledger_, canonical_id, fp)
            entry = ledger_.findings[canonical_id]
            entry.runs_seen += 1
            entry.last_run = run_id
            entry.evidence = f.get("evidence", entry.evidence)
            continue
        new_id = uuid.uuid4().hex
        ledger_.findings[new_id] = LedgerEntry(
            id=new_id, fingerprint=fp, surface_id=f["surface_id"], flow_id=f["flow_id"],
            rule=f["rule"], route=f["route"], locator=f["locator"], sev=f["sev"], text=f["text"],
            evidence=f.get("evidence", []), disposition=f.get("disposition", "engine"),
            state="open", runs_seen=1,
            first_run=run_id, last_run=run_id,
        )

    return ledger_


def find_alias_candidates(ledger_: Ledger, flow_id: str, rule: str, route: str) -> list[LedgerEntry]:
    return [
        e for e in ledger_.findings.values()
        if e.flow_id == flow_id and e.rule == rule and e.route == route
        and e.state in ("open", "regressed")
    ]


def record_alias(ledger_: Ledger, canonical_id: str, alias_fingerprint: str) -> None:
    entry = ledger_.findings[canonical_id]
    if alias_fingerprint not in entry.aliases:
        entry.aliases.append(alias_fingerprint)


def suppressions_for(ledger_: Ledger, rule: str) -> list[dict]:
    matches = [
        e for e in ledger_.findings.values()
        if e.rule == rule and e.state in ("false-positive", "wont-fix")
    ]
    matches.sort(key=lambda e: e.last_run)
    return [{"route": e.route, "locator": e.locator, "text": e.text, "state": e.state} for e in matches]


def record_miss(ledger_: Ledger, function: str, run_id: str) -> int:
    runs = ledger_.discoverability_misses.setdefault(function, [])
    if run_id not in runs:
        runs.append(run_id)
    return len(runs)


def missed_twice(ledger_: Ledger, function: str) -> bool:
    return len(ledger_.discoverability_misses.get(function, [])) >= 2
```

Delete the v1 module and its tests:
```
git rm plugins/flow-review/engine/flow_review/findings.py plugins/flow-review/engine/flow_review/test_findings.py
```

- [ ] **Step 4: Run; expected PASS.**
`python -m pytest plugins/flow-review/engine/flow_review/test_ledger.py -q`

- [ ] **Step 5: Verify.**
```
python -m pytest -q
```
Expected: green. `test_references.py`'s rules-audit `SCANNED`/binding-rule scan picks up
`ledger.py` automatically (it globs `ENGINE.rglob("*.py")`) and `findings.py`'s removal drops out
of the scan the same way -- no manual list edit needed there, confirm `grep -rn
"fr.findings\|flow_review.findings\|demote_repeats" plugins/flow-review` is empty afterward.

- [ ] **Commit:**
```
git add plugins/flow-review/engine/flow_review/ledger.py plugins/flow-review/engine/flow_review/test_ledger.py
git rm plugins/flow-review/engine/flow_review/findings.py plugins/flow-review/engine/flow_review/test_findings.py
git commit -m "feat(ledger): findings.json with sha1 fingerprint, state transitions, aliases, suppressions; retire prose demote_repeats"
```

---

### Task A6: Manifest write-back -- kill the unbounded bare-bullet append, block replace-in-place always, human bytes untouched

**Executor:** sonnet · **Depends:** A1 · **Wave:** 2

**Files:**
- Modify: `plugins/flow-review/engine/flow_review/manifest.py` (lines 92-119 of the moved file,
  `apply_learnings`)
- Modify: `plugins/flow-review/engine/flow_review/test_manifest.py` (the locking test at ~line
  27-35, `test_learnings_rewrite_in_place_when_untouched`, plus one new regression test)

**Interfaces:**
- Consumes: nothing new (only A1's move).
- Produces (unchanged surface, relied on by C4/C7 and the SKILL's write-back step): the four
  public names stay exactly as they are -- `manifest_hash(text: str) -> str`,
  `is_human_edited(path: Path, recorded_hash: str) -> bool`, `apply_learnings(path: Path,
  recorded_hash: str, learnings: list[str]) -> str`, `ANNOTATION_HEADER`, `ANNOTATION_FOOTER`.
  Only `apply_learnings`'s INTERNAL behavior changes: it no longer branches on
  `is_human_edited()` to decide between a bare bullet-list append and a block replace. It always
  uses the block (`_replace_annotation_block`, unchanged from the current file), whether the
  file is human-edited or not. This is the audit-C5 fix: the bare-append branch was what grew
  the file by one unbounded bullet list every single run when nobody had touched it between
  runs; replacing the same one block every time is bounded regardless of who touched the file
  last, and the header/footer splice logic already guarantees human bytes outside the block are
  never touched (that guarantee predates this task and is not being changed, only extended to
  cover the previously-bare-append case too).

- [ ] **Step 1: Write the failing test (full pytest code).**

Replace lines 27-35 of `plugins/flow-review/engine/flow_review/test_manifest.py` (the
`test_learnings_rewrite_in_place_when_untouched` test) with:

```python
def test_learnings_always_use_the_annotation_block_even_when_the_file_is_untouched(tmp_path):
    """The block mechanism is the ONLY path now -- an untouched file no longer gets a bare
    bullet appended straight onto the end. That bare-append path was what grew unbounded across
    runs (audit C5); every run's learnings now replace the same one block, whether or not a
    human has edited the file since."""
    path = tmp_path / "flows.md"
    path.write_text("# flows\n", encoding="utf-8")
    recorded = manifest.manifest_hash(path.read_text(encoding="utf-8"))
    new_hash = manifest.apply_learnings(path, recorded, ["f01 resolved to /settings"])
    text = path.read_text(encoding="utf-8")
    assert "f01 resolved to /settings" in text
    assert manifest.ANNOTATION_HEADER in text
    assert manifest.ANNOTATION_FOOTER in text
    assert new_hash == manifest.manifest_hash(text)


def test_a_second_run_on_an_untouched_file_replaces_the_block_rather_than_growing_it(tmp_path):
    """The regression test for the unbounded-append bug itself: two runs in a row on a file
    nobody hand-edited between them must leave exactly one block, not two bullet lists stacked
    on top of each other growing forever."""
    path = tmp_path / "flows.md"
    path.write_text("# flows\n", encoding="utf-8")
    recorded = manifest.manifest_hash(path.read_text(encoding="utf-8"))
    first_hash = manifest.apply_learnings(path, recorded, ["one"])
    manifest.apply_learnings(path, first_hash, ["two"])
    text = path.read_text(encoding="utf-8")
    assert text.count(manifest.ANNOTATION_HEADER) == 1
    assert text.count(manifest.ANNOTATION_FOOTER) == 1
    assert "two" in text and "one" not in text
```

(Every other existing test in the file -- `test_learnings_never_overwrite_a_human_edit`,
`test_annotation_block_replaced_in_place_when_human_text_follows`,
`test_malformed_block_without_footer_is_treated_as_human_content`,
`test_a_second_run_after_a_malformed_block_still_keeps_every_human_byte`,
`test_the_tools_own_block_is_replaced_rather_than_accumulated`,
`test_no_learnings_leaves_the_file_byte_identical`,
`test_no_learnings_never_transfers_ownership_of_a_human_edited_file`,
`test_missing_file_is_not_human_edited`, `test_a_learning_carrying_a_sentinel_is_refused` --
already exercise the block path or the no-op path and are unaffected by this change; leave them
as-is.)

- [ ] **Step 2: Run it; expected FAIL.** The new
`test_learnings_always_use_the_annotation_block_even_when_the_file_is_untouched` fails: today's
`apply_learnings` takes the bare-append branch for an untouched file, so
`manifest.ANNOTATION_HEADER in text` is `False`.

- [ ] **Step 3: Minimal implementation.**

In `plugins/flow-review/engine/flow_review/manifest.py`, replace `apply_learnings` (the current
lines 92-119) with:

```python
def apply_learnings(path: Path, recorded_hash: str, learnings: list[str]) -> str:
    if not learnings:
        # A no-op run must never transfer ownership: return the recorded hash unchanged,
        # before reading or writing anything, so a human-owned file stays human-owned.
        return recorded_hash

    for line in learnings:
        if ANNOTATION_HEADER in line or ANNOTATION_FOOTER in line:
            raise ValueError(
                "a learning may not contain the annotation header or footer: " f"{line!r}"
            )

    path = Path(path)
    text = path.read_text(encoding="utf-8")
    body = "\n".join(f"- {line}" for line in learnings)

    # Always the block path -- whether or not the file is human-edited. The old branch that
    # bare-appended a bullet list when the file was untouched is what grew the file by one
    # unbounded list every run (audit C5); replacing the same block every time is bounded no
    # matter who touched the file between runs, and _replace_annotation_block already leaves
    # every byte outside the block untouched either way.
    new_text = _replace_annotation_block(text, body)

    path.write_text(new_text, encoding="utf-8")
    return manifest_hash(new_text)
```

`is_human_edited` stays exactly as it is (still a real, independently useful, independently
tested function -- callers such as the SKILL's write-back step may still want to know and report
whether the file was human-edited, it simply no longer gates which code path `apply_learnings`
takes).

- [ ] **Step 4: Run; expected PASS.**
`python -m pytest plugins/flow-review/engine/flow_review/test_manifest.py -q`

- [ ] **Step 5: Verify.**
```
python -m pytest -q
```
Expected: green.

- [ ] **Commit:**
```
git add plugins/flow-review/engine/flow_review/manifest.py plugins/flow-review/engine/flow_review/test_manifest.py
git commit -m "fix(manifest): always replace the annotation block in place, retiring the unbounded bare-bullet append (audit C5)"
```

---

### Task A7: Drift keyed by surface `id`, declined surfaces excluded from the run plan

**Executor:** sonnet · **Depends:** A2 · **Wave:** 3

**Files:**
- Modify: `plugins/flow-review/engine/flow_review/drift.py` (full rewrite of `detect_drift`,
  lines 37-73 of the moved file)
- Modify: `plugins/flow-review/engine/flow_review/test_drift.py` (full rewrite of fixtures to the
  v2 `Surface` shape, plus the rename-survives-drift regression test and `runnable_surfaces`
  tests)

**Interfaces:**
- Consumes: `flow_review.config.Config`, `flow_review.config.Surface` (A2, `id`/`declined`
  fields), `flow_review.audit.detect`, `flow_review.audit.Candidate` (unchanged this task --
  A9 extends `audit.py`'s detectors in the same wave, not this file; `Candidate` here is used
  only for its existing `name`/`kind`/`driver`/`launch`/`evidence` fields).
- Produces (relied on by B9's GO-gate plan and C2's SKILL run procedure):
  - `flow_review.drift.detect_drift(cfg: Config, root: Path) -> list[str]` -- same signature and
    return shape as before (a list of human-readable drift messages), but every message now
    names the surface by its **`id`**, never its `name`, and matching a detected `Candidate` to
    a configured `Surface` is done by **id, not display name** (H2's actual fix): a candidate's
    own `name` (e.g. `"web"`, `"api"`, or a `pyproject.toml` script name -- always the same
    deterministic string audit.py derives from the repo, unaffected by anything a user later
    renames in config) is slugified with the same scheme A3's migration uses
    (`re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")`) and looked up against
    `Surface.id`, never `Surface.name`. A surface whose `name` the user has since edited in
    config keeps matching, because `id` is never touched by a rename -- this is the whole point
    of A2 splitting `id` from `name`, and this task is where that split first pays for itself.
  - `flow_review.drift.runnable_surfaces(cfg: Config) -> list[Surface]` -- `[s for s in
    cfg.surfaces if not s.declined and s.driver != "pending"]`, in config order. `s.declined`
    is A2's boolean field (not the old provenance-dict `"declined": "user"` marker, which this
    task retires in favor of the typed field -- H1's fix: a declined surface must never reach
    the run plan, and a typed bool is what a scheduler checks, not a string buried in a free-form
    provenance dict). The `driver != "pending"` string check is deliberately NOT
    `driver != config.PENDING_DRIVER` or similar named constant -- A9 (same wave, no dependency
    on A7) is what introduces the `"pending"` driver value into `VALID_DRIVERS`, and this task
    must not assume A9 has landed first. The literal string is the stable contract between the
    two tasks; A9's task block below defines the same literal.
  - `DETECTED_PROVENANCE_KEY = "origin"`, `DETECTED_PROVENANCE_VALUE = "audited"` (unchanged from
    the current file -- still how a hand-added surface is told apart from a detected one for the
    "gone from the repo" check).
  - The old `DECLINED_PROVENANCE_KEY`/`DECLINED_PROVENANCE_VALUE` constants are DELETED (declined
    is now `Surface.declined: bool`, set by A2; nothing reads the provenance-dict marker anymore).

- [ ] **Step 1: Write the failing test (full pytest code).**

Replace `plugins/flow-review/engine/flow_review/test_drift.py` in full:

```python
from __future__ import annotations

import json

from flow_review import config as cfgmod
from flow_review import drift


def _cfg(*surfaces):
    return cfgmod.Config(schema_version=cfgmod.SCHEMA_VERSION, generator_version="2.0.0",
                          surfaces=list(surfaces))


def _web(surface_id="web", name="Web", launch="npm run dev", **over):
    base = dict(id=surface_id, name=name, kind="ui", driver="playwright", launch=launch)
    base.update(over)
    return cfgmod.Surface(**base)


def test_no_drift_when_config_matches_the_repo(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}), encoding="utf-8")
    assert drift.detect_drift(_cfg(_web()), tmp_path) == []


def test_reports_a_changed_launch_command_naming_the_surface_by_id(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"start": "vite"}}), encoding="utf-8")
    messages = drift.detect_drift(_cfg(_web(surface_id="web", launch="npm run dev")), tmp_path)
    assert len(messages) == 1
    assert "web" in messages[0] and "launch command" in messages[0]


def test_reports_a_surface_the_repo_gained(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}), encoding="utf-8")
    (tmp_path / "openapi.yaml").write_text("openapi: 3.0.0\n", encoding="utf-8")
    messages = drift.detect_drift(_cfg(_web()), tmp_path)
    assert any("api" in m and "not in config" in m for m in messages)


def test_a_renamed_surface_is_not_reported_as_drift(tmp_path):
    """H2's actual regression test: the id 'web' still matches the detected candidate 'web'
    even though the user renamed the surface's DISPLAY name -- the old name-keyed match broke
    exactly this case."""
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}), encoding="utf-8")
    cfg = _cfg(_web(surface_id="web", name="Marketing site (renamed by hand)"))
    assert drift.detect_drift(cfg, tmp_path) == []


def test_a_declined_surface_is_not_reported_twice(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}), encoding="utf-8")
    (tmp_path / "openapi.yaml").write_text("openapi: 3.0.0\n", encoding="utf-8")
    cfg = _cfg(_web(), cfgmod.Surface(
        id="api", name="api", kind="api", driver="http", launch="", declined=True,
    ))
    messages = drift.detect_drift(cfg, tmp_path)
    assert not any("api" in m and "not in config" in m for m in messages)


def test_a_removed_detector_originated_surface_is_reported(tmp_path):
    cfg = _cfg(cfgmod.Surface(
        id="web", name="Web", kind="ui", driver="playwright", launch="npm run dev",
        provenance={drift.DETECTED_PROVENANCE_KEY: drift.DETECTED_PROVENANCE_VALUE},
    ))
    messages = drift.detect_drift(cfg, tmp_path)
    assert any("web" in m and "gone" in m and "reconfigure" in m for m in messages)


def test_a_hand_added_surface_with_no_match_is_never_reported(tmp_path):
    cfg = _cfg(cfgmod.Surface(id="device", name="Device", kind="cli", driver="adb", launch="adb shell"))
    for _ in range(2):
        messages = drift.detect_drift(cfg, tmp_path)
        assert not any("device" in m for m in messages)


def test_runnable_surfaces_excludes_declined():
    cfg = _cfg(
        _web(surface_id="a", declined=False),
        _web(surface_id="b", declined=True),
    )
    ids = {s.id for s in drift.runnable_surfaces(cfg)}
    assert ids == {"a"}


def test_runnable_surfaces_excludes_pending_driver():
    cfg = _cfg(
        _web(surface_id="a"),
        cfgmod.Surface(id="b", name="Desktop app", kind="ui", driver="pending", launch=""),
    )
    ids = {s.id for s in drift.runnable_surfaces(cfg)}
    assert ids == {"a"}


def test_runnable_surfaces_keeps_config_order():
    cfg = _cfg(_web(surface_id="z"), _web(surface_id="a"))
    assert [s.id for s in drift.runnable_surfaces(cfg)] == ["z", "a"]
```

- [ ] **Step 2: Run it; expected FAIL.** `TypeError: Surface.__init__() missing 1 required positional
argument: 'id'` (the current file's `_web`/`_cfg` fixtures predate A2), and
`drift.runnable_surfaces` does not exist yet.

- [ ] **Step 3: Minimal implementation.**

Replace `plugins/flow-review/engine/flow_review/drift.py` in full:

```python
"""Compare the config against the repository's current shape (H1, H2).

Matching a detected candidate to a configured surface is done by id, never by display name
(H2): a surface's `name` is free text a user may rename at any time: A2 spun `id` out
specifically so this comparison has something stable to key on. `runnable_surfaces` is the one
place "should this surface be in the run plan at all" is decided (H1): declined and
pending-driver surfaces never reach it.
"""
from __future__ import annotations

import re
from pathlib import Path

from flow_review import audit
from flow_review.config import Config, Surface

DETECTED_PROVENANCE_KEY = "origin"
DETECTED_PROVENANCE_VALUE = "audited"

# The literal "pending" driver value: A9 (same wave, no dependency between the two tasks) is
# what starts writing this value into VALID_DRIVERS/Surface.driver. This module does not import
# a shared constant for it so neither task depends on the other having landed first; the string
# itself is the contract.
_PENDING_DRIVER = "pending"


def _slug(name: str) -> str:
    # Mirrors migrate.py's _slug exactly -- both derive a surface id from a human-facing name
    # the same way, so a candidate freshly detected from the repo and an id a config was
    # migrated with land on the same string.
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "surface"


def detect_drift(cfg: Config, root: Path) -> list[str]:
    detected = audit.detect(Path(root))
    by_id = {s.id: s for s in cfg.surfaces}
    messages: list[str] = []

    for candidate in detected:
        candidate_id = _slug(candidate.name)
        surface = by_id.get(candidate_id)
        if surface is None:
            messages.append(
                f"drift: surface {candidate_id!r} detected in the repo but not in config "
                f"({candidate.evidence}) -- run /flow-review --reconfigure to add it"
            )
            continue
        if surface.declined:
            continue
        if candidate.launch and surface.launch and candidate.launch != surface.launch:
            messages.append(
                f"drift: surface {surface.id!r} launch command changed "
                f"({surface.launch!r} -> {candidate.launch!r}) -- run /flow-review --reconfigure"
            )

    detected_ids = {_slug(c.name) for c in detected}
    for surface in cfg.surfaces:
        if surface.provenance.get(DETECTED_PROVENANCE_KEY) != DETECTED_PROVENANCE_VALUE:
            continue
        if surface.id not in detected_ids:
            messages.append(
                f"drift: surface {surface.id!r} is configured but its evidence is gone from "
                f"the repo -- run /flow-review --reconfigure to remove or update it"
            )

    return messages


def runnable_surfaces(cfg: Config) -> list[Surface]:
    return [s for s in cfg.surfaces if not s.declined and s.driver != _PENDING_DRIVER]
```

- [ ] **Step 4: Run; expected PASS.**
`python -m pytest plugins/flow-review/engine/flow_review/test_drift.py -q`

- [ ] **Step 5: Verify.**
```
python -m pytest -q
```
Expected: green (this is the task that clears `test_drift.py` out of the red state A2 left it
in).

- [ ] **Commit:**
```
git add plugins/flow-review/engine/flow_review/drift.py plugins/flow-review/engine/flow_review/test_drift.py
git commit -m "fix(drift): match candidates to surfaces by id not name, exclude declined/pending-driver from the run plan"
```

---

### Task A8: prove fixes -- honest tree teardown when the direct child already exited (H3), preconditions govern proof over a clean exit (H4), api reachability-only proving (M3)

**Executor:** sonnet · **Depends:** A2 · **Wave:** 3

**Files:**
- Modify: `plugins/flow-review/engine/flow_review/prove.py` (full rewrite of the Windows kill
  path, `_teardown`, and the main polling loop in `prove()`; `_check_precondition`,
  `_first_passing`, `_start_process`, `_posix_group_is_gone`, `_read_output`, `_cleanup_sink`
  are unchanged)
- Modify: `plugins/flow-review/engine/flow_review/test_prove.py` (one existing test's monkeypatch
  signature updated; several new tests added)

**Interfaces:**
- Consumes: `flow_review.config.validate_preconditions` (A2 -- called once at the top of
  `prove()`, per the ownership split stated in A2's task block: A2 owns the function's shape and
  its use from `config.load`/`config.save`, A8 owns calling it from `prove()` too).
  `flow_review.audit.Candidate` (unchanged; `Candidate.kind` is what M3's api branch reads).
- Produces: `Proof`, `prove()`, `outcome_to_provenance()`, `PROVEN`, `UNPROVEN`, `EXITED_CLEAN`,
  `EXITED_FAILED`, `RUNNING_READY`, `NOT_PROVEN`, `OUTCOMES` all keep their existing names,
  shapes and meanings (relied on by B1's driver launch, B9's plan). Only the BEHAVIOR changes:
  - **H3**: `_teardown` no longer trusts `process.poll() is not None` as proof the whole tree is
    gone -- it always attempts a kill and always independently confirms. On Windows this means
    walking the process table for every live descendant of the launched pid BEFORE relying on
    `taskkill /T`, because `taskkill /T /F /PID X` can only walk a tree it can still locate
    starting from `X`'s own (possibly already-exited) process entry -- if the direct child
    (`cmd.exe`) exited on its own before teardown runs, `/T` finds nothing, even though a
    grandchild it spawned is still running. Each descendant's own process-table entry still
    records its immediate parent's pid regardless of whether that parent is still alive, so a
    breadth-first walk from the launched pid finds every survivor `/T` would have found had the
    direct child still been alive, and still works when it is not.
  - **H4**: when `preconditions` were given to `prove()`, a clean process exit (`status == 0`)
    before any precondition ever passed is `NOT_PROVEN`, never `EXITED_CLEAN`. Preconditions were
    configured precisely because readiness has to be OBSERVED, not inferred from an exit code;
    an exit proves nothing about the thing the precondition exists to confirm. `prove()` called
    with no preconditions is unaffected -- a clean exit stays `EXITED_CLEAN`/proven, same as
    before.
  - **M3**: `prove()` called with `candidate.kind == "api"` and a blank `launch` no longer
    returns the generic `"no launch command to prove"` `NOT_PROVEN` -- it proves (or fails to
    prove) reachability alone, via the given `preconditions`, without spawning any process at
    all: a passing precondition is `RUNNING_READY`/proven, a non-passing one (or no preconditions
    given at all) is `NOT_PROVEN` with a reason naming the api case specifically. This matches
    spec Section 6 ("API: HTTP with reachability-only proving") and is the only kind-aware branch
    in this module; every other kind keeps the existing launch-and-observe behavior.

- [ ] **Step 1: Write the failing test (full pytest code).**

Add to `plugins/flow-review/engine/flow_review/test_prove.py` (append; keep every existing test
except the one named below):

```python
def _api_candidate(launch: str = "") -> Candidate:
    return Candidate(name="api", kind="api", driver="http", launch=launch, evidence="test:1 -> api")


# --- M3: api reachability-only proving --------------------------------------------------


def test_api_surface_with_passing_precondition_is_proven_without_launching_anything(tmp_path):
    marker = tmp_path / "should_not_exist.txt"
    precond_cmd = _script(tmp_path, "reachable.py", "import sys\nsys.exit(0)\n")
    proof = provemod.prove(
        _api_candidate(), tmp_path, preconditions=[{"name": "reachable", "cmd": precond_cmd}],
    )
    assert proof.outcome == provemod.RUNNING_READY
    assert proof.precondition == "reachable"
    assert provemod.outcome_to_provenance(proof.outcome) == provemod.PROVEN
    assert not marker.exists()


def test_api_surface_with_failing_precondition_is_not_proven(tmp_path):
    precond_cmd = _script(tmp_path, "unreachable.py", "import sys\nsys.exit(1)\n")
    proof = provemod.prove(
        _api_candidate(), tmp_path, preconditions=[{"name": "reachable", "cmd": precond_cmd}],
    )
    assert proof.outcome == provemod.NOT_PROVEN
    assert "api" in proof.reason.lower()


def test_api_surface_with_no_preconditions_is_not_proven_never_launches(tmp_path):
    proof = provemod.prove(_api_candidate(), tmp_path, preconditions=[])
    assert proof.outcome == provemod.NOT_PROVEN
    assert "reachability" in proof.reason.lower() or "precondition" in proof.reason.lower()


def test_a_non_api_blank_launch_still_reports_no_launch_command(tmp_path):
    proof = provemod.prove(_candidate("   "), tmp_path)
    assert proof.outcome == provemod.NOT_PROVEN
    assert "no launch command" in proof.reason


# --- H4: preconditions govern proof over a clean exit ------------------------------------


def test_a_clean_exit_before_any_precondition_passes_is_not_proven(tmp_path):
    # The launched command exits 0 almost immediately -- a wrapper that daemonizes and quits,
    # for example -- while the precondition that was supposed to confirm real readiness never
    # once passes. A clean exit code must not be mistaken for the readiness it never observed.
    launch = _script(tmp_path, "quits_clean.py", "import sys\nsys.exit(0)\n")
    precond_cmd = _script(tmp_path, "never_ready.py", "import sys\nsys.exit(1)\n")
    proof = provemod.prove(
        _candidate(launch), tmp_path,
        preconditions=[{"name": "ready", "cmd": precond_cmd}], ready_timeout_s=1,
    )
    assert proof.outcome == provemod.NOT_PROVEN
    assert provemod.outcome_to_provenance(proof.outcome) == provemod.UNPROVEN
    assert "exited cleanly" in proof.reason or "does not prove readiness" in proof.reason


def test_a_clean_exit_with_no_preconditions_is_still_proven(tmp_path):
    # Unaffected case: no preconditions were ever asked to prove anything, so the exit code is
    # still the whole story, exactly as before H4.
    launch = _script(tmp_path, "quits_clean2.py", "import sys\nsys.exit(0)\n")
    proof = provemod.prove(_candidate(launch), tmp_path)
    assert proof.outcome == provemod.EXITED_CLEAN


# --- H3: honest teardown when the direct child already exited ----------------------------


def test_a_grandchild_orphaned_by_an_already_exited_direct_child_is_still_reaped(tmp_path):
    """The regression H3 fixes: the launched command (run via shell=True, so its direct OS
    child is cmd.exe/sh) itself spawns a further child and then exits almost immediately,
    orphaning that grandchild. The old _teardown trusted `process.poll() is not None` as proof
    the whole tree was gone and returned early -- exactly wrong, since poll() only ever sees
    the direct child. teardown_ok must reflect the grandchild's ACTUAL fate, and the grandchild
    must actually be dead afterward."""
    pidfile = tmp_path / "orphan.pid"
    launch = _script(
        tmp_path, "quits_after_spawning.py",
        "import subprocess, sys, pathlib, time\n"
        f"child = subprocess.Popen([{str(sys.executable)!r}, '-c', "
        "'import pathlib,time; pathlib.Path(r\"" + str(pidfile).replace("\\", "\\\\") + "\").write_text(str(__import__(\"os\").getpid())); time.sleep(30)'])\n"
        "time.sleep(0.3)\n"
        "sys.exit(0)\n",
    )
    proof = provemod.prove(_candidate(launch), tmp_path, exit_timeout_s=5)
    assert proof.outcome == provemod.EXITED_CLEAN
    # Give the grandchild a moment to have written its own pidfile before asserting on it.
    for _ in range(20):
        if pidfile.exists():
            break
        time.sleep(0.1)
    assert pidfile.exists(), "the grandchild should have had time to record its own pid"
    orphan_pid = int(pidfile.read_text().strip())
    assert not _process_alive(orphan_pid), "the orphaned grandchild must not survive prove()"
    assert proof.teardown_ok is True
```

Update the ONE existing test whose monkeypatch signature this task's `_kill_tree` change breaks
(`test_teardown_failure_is_folded_into_reason`): change

```python
    monkeypatch.setattr(provemod, "_kill_tree", lambda process: True)
```

to

```python
    monkeypatch.setattr(provemod, "_kill_tree", lambda process: (True, set()))
```

(`_kill_tree` now returns `(signal_succeeded: bool, descendants_observed: set[int])` instead of a
bare bool -- see Step 3. No other existing test touches `_kill_tree` directly.)

- [ ] **Step 2: Run it; expected FAIL.** The four new M3 tests fail with `AssertionError` (an api
candidate with blank launch currently returns `"no launch command to prove"` regardless of
kind). The two H4 tests fail (`test_a_clean_exit_before_any_precondition_passes_is_not_proven`
gets `EXITED_CLEAN`, not `NOT_PROVEN`). The H3 test is flaky-to-failing on the current code (the
orphan sometimes survives, since `_teardown` returns `True` the instant `cmd.exe`/the launched
python process itself exits, without ever looking for what it spawned).

- [ ] **Step 3: Minimal implementation.**

In `plugins/flow-review/engine/flow_review/prove.py`:

1. Replace the `_kill_tree` and `_teardown` functions (current lines 147-204) with:

```python
def _child_pids_of(pid: int) -> set[int]:
    try:
        result = subprocess.run(
            ["wmic", "process", "where", f"(ParentProcessId={pid})", "get", "ProcessId"],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError):
        return set()
    return {int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()}


def _descendant_pids(root_pid: int) -> set[int]:
    """Breadth-first walk of the Windows process table for every live descendant of root_pid.

    taskkill /T only walks a tree it can still locate STARTING FROM root_pid's own process
    entry -- once that entry is gone (the direct child, cmd.exe, already exited on its own),
    /T finds nothing, even though whatever cmd.exe spawned is still running (H3). Each
    descendant's own entry keeps recording its immediate parent's pid regardless of whether
    that parent still exists, so this walk finds every survivor /T would have found had
    root_pid still been alive, and still works when it is not.
    """
    seen: set[int] = set()
    frontier = {root_pid}
    while frontier:
        next_frontier: set[int] = set()
        for pid in frontier:
            for child in _child_pids_of(pid):
                if child not in seen:
                    seen.add(child)
                    next_frontier.add(child)
        frontier = next_frontier
    return seen


def _windows_pid_alive(pid: int) -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return str(pid) in result.stdout


def _kill_tree(process: subprocess.Popen) -> tuple[bool, set[int]]:
    """Send the kill and report (signal succeeded, descendants observed at kill time).

    The descendants are handed back so _teardown can independently confirm each one is
    actually gone -- on Windows, taskkill /T's own return code only speaks to the walk it could
    still perform FROM process.pid; it says nothing about a descendant killed individually
    below, and nothing at all once process.pid's own entry is already gone.
    """
    if _IS_WINDOWS:
        descendants = _descendant_pids(process.pid)
        tree_result = subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for pid in descendants:
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        return tree_result.returncode == 0, descendants
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass  # already gone before we could signal it -- not a kill failure
    return True, set()


def _teardown(process: subprocess.Popen) -> bool:
    """Kill whatever is left of the process tree and confirm it is actually gone.

    Never trusts `process.poll() is not None` as proof the whole tree is dead (H3) -- poll()
    only ever observes the direct child (cmd.exe/sh under shell=True). A kill and an
    independent liveness check always run, whether or not the direct child had already exited
    on its own by the time this is called.
    """
    kill_ok, descendants = _kill_tree(process)
    if process.poll() is None:
        try:
            process.wait(timeout=_TEARDOWN_WAIT_S)
        except subprocess.TimeoutExpired:
            pass
    if process.poll() is None:
        return False
    if _IS_WINDOWS:
        # kill_ok alone is not proof: taskkill /T can report failure purely because it had no
        # live root left to walk from, while every descendant was still killed individually
        # just above. The only trustworthy confirmation is asking the process table again.
        return kill_ok or not any(_windows_pid_alive(pid) for pid in descendants)
    return _posix_group_is_gone(process.pid)
```

2. Add, right after the imports (`from flow_review.audit import Candidate`), a second import:
   `from flow_review.config import validate_preconditions`.

3. In `prove()`, immediately after the `started = time.monotonic()` line, insert:
   ```python
    preconditions = list(preconditions)
    validate_preconditions(preconditions)

    if candidate.kind == "api" and not candidate.launch.strip():
        # M3: an api surface proves reachability alone -- never "no launch command", and
        # nothing is ever spawned to prove it (spec Section 6).
        if not preconditions:
            return Proof(
                candidate, NOT_PROVEN, None, time.monotonic() - started, "", "", "", True,
                "api surface has no launch command and no reachability precondition to prove it",
            )
        passed = _first_passing(preconditions, root)
        if passed is not None:
            return Proof(
                candidate, RUNNING_READY, None, time.monotonic() - started, "", "", passed, True,
                "api reachable via precondition; nothing was launched",
            )
        return Proof(
            candidate, NOT_PROVEN, None, time.monotonic() - started, "", "", "", True,
            "no reachability precondition passed for this api surface; nothing was launched",
        )
   ```
   (this replaces the function's existing first two lines of logic-adjacent code; the following
   `if not candidate.launch.strip():` block for the NON-api case is unchanged and stays exactly
   as it is, right after the new block above).

4. In the main polling loop, replace:
   ```python
            status = process.poll()
            if status is not None:
                exit_code = status
                outcome = EXITED_CLEAN if status == 0 else EXITED_FAILED
                break
   ```
   with:
   ```python
            status = process.poll()
            if status is not None:
                exit_code = status
                if preconditions and status == 0:
                    # H4: preconditions exist to OBSERVE readiness -- a clean exit before any
                    # of them ever passed proves nothing about what they were asked to confirm.
                    outcome = NOT_PROVEN
                    reason = (
                        "process exited cleanly before any precondition passed; a clean exit "
                        "does not prove readiness when preconditions were configured to prove it"
                    )
                else:
                    outcome = EXITED_CLEAN if status == 0 else EXITED_FAILED
                break
   ```

- [ ] **Step 4: Run; expected PASS.**
`python -m pytest plugins/flow-review/engine/flow_review/test_prove.py -q`

- [ ] **Step 5: Verify.**
```
python -m pytest -q
```
Expected: green.

- [ ] **Commit:**
```
git add plugins/flow-review/engine/flow_review/prove.py plugins/flow-review/engine/flow_review/test_prove.py
git commit -m "fix(prove): honest tree teardown past an early direct-child exit, preconditions over exit code, api reachability-only proving (H3/H4/M3)"
```

---

### Task A9: Detection -- monorepo workspaces, Poetry, web frameworks with dev-server port, Tauri/Expo/Electron as pending-driver

**Executor:** sonnet · **Depends:** A2 · **Wave:** 3

**Files:**
- Modify: `plugins/flow-review/engine/flow_review/audit.py` (full rewrite of `detect()` and
  `_from_package_json`; new finders added; `_from_pyproject`, `_from_openapi`, `_evidence`
  unchanged)
- Modify: `plugins/flow-review/engine/flow_review/test_audit.py` (existing tests updated for the
  `driver` change; new tests added for each new finder)
- Modify: `plugins/flow-review/engine/flow_review/config.py` (one-line addition: `"pending"`
  appended to `VALID_DRIVERS`, per A2's note that A9 owns introducing this value)

**Interfaces:**
- Consumes: `flow_review.config.VALID_DRIVERS`, `flow_review.config.VALID_KINDS` (A2; this task
  is what actually exercises `driver="pending"` for the first time, hence A9 owns adding it to
  `VALID_DRIVERS`, not A2 or A7 -- A7 only assumed the literal string `"pending"` would
  eventually mean this).
- Produces (relied on by the setup interview referenced in `references/setup.md`, and by A7's
  `runnable_surfaces`, already shipped, which already excludes `driver == "pending"`):
  - `class Candidate` gains one new optional field: `default_port: int | None = None` -- a
    well-known dev-server port for a recognized framework, so the setup interview can prefill
    `options.base_url` instead of asking. `None` when nothing is recognized (unchanged existing
    behavior for a generic `npm run dev` with no known framework in `devDependencies`).
  - `_from_package_json` candidates now carry `driver="playwright"`, not the old `"cdp"` --
    this is what makes a detected web surface actually satisfy A2's `WEB_OPTION_KEYS`
    validation (which only accepts `options` on `driver == "playwright"`); a detected surface
    that could never legally carry `base_url` etc. was a gap between A2 and A9 landing in the
    same wave, closed here.
  - `flow_review.audit.WORKSPACE_FRAMEWORK_PORTS = {"vite": 5173, "next": 3000, "react-scripts":
    3000}` -- looked up against the union of `dependencies`/`devDependencies` keys in the
    relevant `package.json`; the first match in this dict's iteration order (Python dicts are
    insertion-ordered) wins when more than one framework is present, which in practice never
    happens for these three.
  - `detect(root: Path) -> list[Candidate]` gains, beyond the existing package.json/pyproject/
    openapi finders (kept, now also applied per-workspace-member -- see below):
    - **Monorepo workspaces**: a root `package.json` with a `"workspaces"` array (npm/yarn) OR a
      root `pnpm-workspace.yaml` with a top-level `packages:` list. Each glob pattern (e.g.
      `"packages/*"` or `"apps/**"`) is resolved with `Path.glob(pattern)` directly -- per A-23
      ("workspace globs use `Path.glob` (so `**` works, brace lists don't)"), `**` is supported
      because it is `Path.glob`'s own native recursive-match syntax, requiring no special-casing
      in this module; a brace-list pattern (`"packages/{web,api}"`) is NOT supported (`Path.glob`
      has no brace-expansion of its own) and simply matches nothing extra for that pattern,
      never crashes. Each matched member directory with its own `package.json` gets its own
      candidate(s) via the same dev-script detection as the root, with its `name` set to the
      member directory's own basename (e.g. `packages/web` -> `"web"`, `packages/api` ->
      `"api"`) rather than the fixed `"web"` the single-package path uses, and its evidence
      still cited relative to the repository ROOT, not the member directory.
    - **Poetry**: `[tool.poetry.scripts]` in `pyproject.toml` (Poetry's own table, distinct from
      PEP 621's `[project.scripts]`, which the existing `_from_pyproject` already reads) is
      parsed with the same line-locating approach as `_from_pyproject`, producing `kind="cli",
      driver="shell"` candidates. A command name already found via `[project.scripts]` is not
      duplicated if the same pyproject.toml happens to declare both tables (rare, but a project
      migrating from Poetry to PEP 621 might, briefly).
    - **Web frameworks with a dev-server port**: folded into `_from_package_json` itself (see
      `default_port` above) rather than being a separate finder -- it augments the existing web
      candidate, it does not create a new one.
    - **Tauri**: a `src-tauri/` directory at the repo root -> one candidate, `kind="ui",
      driver="pending", launch=""`, evidence citing `src-tauri/tauri.conf.json` if present, else
      the bare directory (`EVIDENCE_FORMAT_NO_LINE`-shaped, using the directory path).
    - **Expo**: a root `app.json` whose parsed JSON has an `"expo"` top-level key -> one
      candidate, `kind="ui", driver="pending", launch=""`.
    - **Electron**: a root `package.json` whose `dependencies` or `devDependencies` contains the
      key `"electron"` -> one candidate, `kind="ui", driver="pending", launch=""`, evidence
      citing the line the `"electron"` key appears on (same line-locating technique as the
      existing dev-script search).
    Every `pending-driver` candidate's `launch` is deliberately blank -- A9 proposes that the
    surface EXISTS, never a launch command for a driver M1 does not implement; the setup
    interview (`references/setup.md`, unchanged by this task) is what tells the user these are
    shown but not tested until M2/M3, per A-14.

- [ ] **Step 1: Write the failing test (full pytest code).**

Append to `plugins/flow-review/engine/flow_review/test_audit.py` (keep all existing tests; update
only where noted):

```python
def test_web_candidate_driver_is_playwright_not_cdp(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}), encoding="utf-8")
    web = [c for c in audit.detect(tmp_path) if c.kind == "ui"]
    assert web[0].driver == "playwright"


def test_vite_devdependency_sets_the_known_default_port(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({
        "scripts": {"dev": "vite"}, "devDependencies": {"vite": "^5.0.0"},
    }), encoding="utf-8")
    web = [c for c in audit.detect(tmp_path) if c.kind == "ui"]
    assert web[0].default_port == 5173


def test_an_unrecognized_framework_has_no_default_port(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"dev": "custom-server"}}), encoding="utf-8")
    web = [c for c in audit.detect(tmp_path) if c.kind == "ui"]
    assert web[0].default_port is None


def test_poetry_scripts_table_is_detected(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[tool.poetry]\nname = "demo"\n\n[tool.poetry.scripts]\ndemo = "demo.cli:main"\n',
        encoding="utf-8",
    )
    cli = [c for c in audit.detect(tmp_path) if c.kind == "cli"]
    assert cli
    assert cli[0].launch == "demo"
    assert "pyproject.toml:" in cli[0].evidence


def test_poetry_and_pep621_scripts_are_not_duplicated(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project.scripts]\ndemo = "demo.cli:main"\n\n'
        '[tool.poetry.scripts]\ndemo = "demo.cli:main"\n',
        encoding="utf-8",
    )
    cli = [c for c in audit.detect(tmp_path) if c.kind == "cli" and c.launch == "demo"]
    assert len(cli) == 1


def test_npm_workspace_member_is_detected_with_its_own_name(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"workspaces": ["packages/*"]}), encoding="utf-8")
    member = tmp_path / "packages" / "web"
    member.mkdir(parents=True)
    (member / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}), encoding="utf-8")
    web = [c for c in audit.detect(tmp_path) if c.kind == "ui"]
    assert web
    assert web[0].name == "web"
    assert web[0].evidence.startswith("packages")


def test_pnpm_workspace_yaml_member_is_detected(tmp_path):
    (tmp_path / "pnpm-workspace.yaml").write_text("packages:\n  - 'apps/*'\n", encoding="utf-8")
    member = tmp_path / "apps" / "site"
    member.mkdir(parents=True)
    (member / "package.json").write_text(json.dumps({"scripts": {"dev": "next dev"}}), encoding="utf-8")
    web = [c for c in audit.detect(tmp_path) if c.kind == "ui"]
    assert any(c.name == "site" for c in web)


def test_workspace_double_star_glob_finds_a_nested_member(tmp_path):
    # A-23: workspace globs use Path.glob directly, so ** works exactly as Path.glob's own
    # recursive-match syntax -- no special-casing needed for it in this module.
    (tmp_path / "package.json").write_text(json.dumps({"workspaces": ["packages/**"]}), encoding="utf-8")
    member = tmp_path / "packages" / "group" / "web"
    member.mkdir(parents=True)
    (member / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}), encoding="utf-8")
    web = [c for c in audit.detect(tmp_path) if c.kind == "ui"]
    assert any(c.name == "web" for c in web)


def test_workspace_brace_list_glob_is_unsupported_and_matches_nothing(tmp_path):
    # A-23: brace lists ("{a,b}") are not Path.glob syntax and are not special-cased here --
    # the pattern simply matches nothing extra, it never raises.
    (tmp_path / "package.json").write_text(json.dumps({"workspaces": ["packages/{web,api}"]}), encoding="utf-8")
    member = tmp_path / "packages" / "web"
    member.mkdir(parents=True)
    (member / "package.json").write_text(json.dumps({"scripts": {"dev": "vite"}}), encoding="utf-8")
    web = [c for c in audit.detect(tmp_path) if c.kind == "ui"]
    assert web == []


def test_tauri_src_tauri_dir_is_pending_driver(tmp_path):
    (tmp_path / "src-tauri").mkdir()
    found = audit.detect(tmp_path)
    tauri = [c for c in found if c.driver == "pending" and "tauri" in c.evidence.lower() or "src-tauri" in c.evidence]
    assert tauri
    assert tauri[0].launch == ""


def test_expo_app_json_is_pending_driver(tmp_path):
    (tmp_path / "app.json").write_text(json.dumps({"expo": {"name": "demo"}}), encoding="utf-8")
    found = audit.detect(tmp_path)
    assert any(c.driver == "pending" and "app.json" in c.evidence for c in found)


def test_a_plain_app_json_with_no_expo_key_is_not_detected(tmp_path):
    (tmp_path / "app.json").write_text(json.dumps({"name": "demo"}), encoding="utf-8")
    found = audit.detect(tmp_path)
    assert not any(c.driver == "pending" and "app.json" in c.evidence for c in found)


def test_electron_dependency_is_pending_driver(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({
        "devDependencies": {"electron": "^30.0.0"},
    }, indent=2), encoding="utf-8")
    found = audit.detect(tmp_path)
    electron = [c for c in found if c.driver == "pending" and "electron" not in c.name]
    assert any(c.driver == "pending" for c in found)


def test_pending_driver_is_valid_per_config():
    from flow_review.config import VALID_DRIVERS
    assert "pending" in VALID_DRIVERS
```

- [ ] **Step 2: Run it; expected FAIL.** `test_web_candidate_driver_is_playwright_not_cdp` fails
(`driver == "cdp"` today); every new-finder test fails with `AssertionError` (nothing detected)
or the module has no `default_port`/`WORKSPACE_FRAMEWORK_PORTS`; `test_pending_driver_is_valid_per_config`
fails (`"pending" not in VALID_DRIVERS`).

- [ ] **Step 3: Minimal implementation.**

In `plugins/flow-review/engine/flow_review/config.py`, change:
```python
VALID_DRIVERS = ("cdp", "playwright", "adb", "ios-sim", "shell", "http", "custom")
```
to:
```python
VALID_DRIVERS = ("cdp", "playwright", "adb", "ios-sim", "shell", "http", "custom", "pending")
```

Replace `plugins/flow-review/engine/flow_review/audit.py` in full:

```python
"""Propose surfaces from what the repository actually contains (A-14).

This module PROPOSES and never PROVES -- fr.prove owns launching. A pending-driver candidate
(Tauri/Expo/Electron) proposes only that a surface EXISTS; M1 has no driver for it, so its
launch is always blank and setup shows it as detected-but-not-yet-testable.

A candidate exists only where the repository itself declares a runnable entry point in
machine-readable form. Inferring a launch command from a convention or a Makefile target is the
guessed citation this module refuses; workspace members and Poetry's own scripts table are
still machine-readable declarations, not conventions, so they are in scope the same way the
single-package case always was.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

EVIDENCE_FORMAT = "{path}:{line} -> {snippet}"
EVIDENCE_FORMAT_NO_LINE = "{path} (file present)"

_DEV_SCRIPTS = ("dev", "start", "serve")
_SCRIPTS_KEY = re.compile(r'"scripts"\s*:')
_OPENAPI_NAMES = ("openapi.yaml", "openapi.yml", "openapi.json", "swagger.yaml", "swagger.json")

WORKSPACE_FRAMEWORK_PORTS = {"vite": 5173, "next": 3000, "react-scripts": 3000}


@dataclass
class Candidate:
    name: str
    kind: str
    driver: str
    launch: str
    evidence: str
    default_port: int | None = None


def _evidence(path: Path, root: Path, line: int | None, snippet: str) -> str:
    rel = path.relative_to(root).as_posix()
    if line is None:
        return EVIDENCE_FORMAT_NO_LINE.format(path=rel)
    return EVIDENCE_FORMAT.format(path=rel, line=line, snippet=snippet.strip())


def _default_port(data: dict) -> int | None:
    deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
    for framework, port in WORKSPACE_FRAMEWORK_PORTS.items():
        if framework in deps:
            return port
    return None


def _from_package_json(pkg_dir: Path, evidence_root: Path, name: str = "web") -> list[Candidate]:
    path = pkg_dir / "package.json"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except ValueError:
        return []
    scripts = data.get("scripts") or {}
    lines = text.splitlines()
    first = next((i for i, line in enumerate(lines) if _SCRIPTS_KEY.search(line)), 0)
    for script_name in _DEV_SCRIPTS:
        if script_name in scripts:
            key = re.compile(r'"%s"\s*:' % re.escape(script_name))
            number, snippet = next(
                ((i + 1, line) for i, line in enumerate(lines[first:], first) if key.search(line)),
                (None, ""),
            )
            return [Candidate(
                name=name,
                kind="ui",
                driver="playwright",
                launch=f"npm run {script_name}",
                evidence=_evidence(path, evidence_root, number, snippet),
                default_port=_default_port(data),
            )]
    return []


def _workspace_globs(root: Path) -> list[str]:
    patterns: list[str] = []
    pkg = root / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except ValueError:
            data = {}
        workspaces = data.get("workspaces")
        if isinstance(workspaces, dict):
            workspaces = workspaces.get("packages")
        if isinstance(workspaces, list):
            patterns.extend(str(p) for p in workspaces)
    pnpm = root / "pnpm-workspace.yaml"
    if pnpm.is_file():
        for line in pnpm.read_text(encoding="utf-8").splitlines():
            stripped = line.strip().lstrip("-").strip().strip("'\"")
            if stripped and stripped != "packages:":
                patterns.append(stripped)
    return patterns


def _from_workspaces(root: Path) -> list[Candidate]:
    found: list[Candidate] = []
    for pattern in _workspace_globs(root):
        for member in sorted(root.glob(pattern)):
            if member.is_dir() and (member / "package.json").is_file():
                found.extend(_from_package_json(member, root, name=member.name))
    return found


def _from_pyproject(root: Path) -> list[Candidate]:
    path = root / "pyproject.toml"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    if "[project.scripts]" not in text:
        return []
    out = []
    header, rest = text.split("[project.scripts]", 1)
    header_lines = header.count("\n")
    section = rest.split("\n[", 1)[0]
    section_lines = section.splitlines()
    for match in re.finditer(r"^\s*([A-Za-z0-9_.-]+)\s*=", section, re.M):
        command = match.group(1)
        offset = section.count("\n", 0, match.start(1))
        line_number = header_lines + 1 + offset
        out.append(Candidate(
            name=command, kind="cli", driver="shell", launch=command,
            evidence=_evidence(path, root, line_number, section_lines[offset]),
        ))
    return out


def _from_poetry(root: Path, already: set[str]) -> list[Candidate]:
    path = root / "pyproject.toml"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    if "[tool.poetry.scripts]" not in text:
        return []
    out = []
    header, rest = text.split("[tool.poetry.scripts]", 1)
    header_lines = header.count("\n")
    section = rest.split("\n[", 1)[0]
    section_lines = section.splitlines()
    for match in re.finditer(r"^\s*([A-Za-z0-9_.-]+)\s*=", section, re.M):
        command = match.group(1)
        if command in already:
            continue
        offset = section.count("\n", 0, match.start(1))
        line_number = header_lines + 1 + offset
        out.append(Candidate(
            name=command, kind="cli", driver="shell", launch=command,
            evidence=_evidence(path, root, line_number, section_lines[offset]),
        ))
    return out


def _from_openapi(root: Path) -> list[Candidate]:
    for name in _OPENAPI_NAMES:
        path = root / name
        if not path.is_file():
            continue
        return [Candidate(name="api", kind="api", driver="http", launch="", evidence=_evidence(path, root, None, ""))]
    return []


def _from_tauri(root: Path) -> list[Candidate]:
    src_tauri = root / "src-tauri"
    if not src_tauri.is_dir():
        return []
    conf = src_tauri / "tauri.conf.json"
    evidence = _evidence(conf, root, None, "") if conf.is_file() else _evidence(src_tauri, root, None, "")
    return [Candidate(name="desktop", kind="ui", driver="pending", launch="", evidence=evidence)]


def _from_expo(root: Path) -> list[Candidate]:
    path = root / "app.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return []
    if "expo" not in data:
        return []
    return [Candidate(name="mobile", kind="ui", driver="pending", launch="", evidence=_evidence(path, root, None, ""))]


def _from_electron(root: Path) -> list[Candidate]:
    path = root / "package.json"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except ValueError:
        return []
    deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
    if "electron" not in deps:
        return []
    key = re.compile(r'"electron"\s*:')
    lines = text.splitlines()
    number, snippet = next(
        ((i + 1, line) for i, line in enumerate(lines) if key.search(line)), (None, ""),
    )
    evidence = _evidence(path, root, number, snippet) if number else _evidence(path, root, None, "")
    return [Candidate(name="desktop-electron", kind="ui", driver="pending", launch="", evidence=evidence)]


def detect(root: Path) -> list[Candidate]:
    root = Path(root)
    found: list[Candidate] = []
    found.extend(_from_package_json(root, root))
    found.extend(_from_workspaces(root))
    pyproject_found = _from_pyproject(root)
    found.extend(pyproject_found)
    found.extend(_from_poetry(root, already={c.name for c in pyproject_found}))
    found.extend(_from_openapi(root))
    found.extend(_from_tauri(root))
    found.extend(_from_expo(root))
    found.extend(_from_electron(root))
    return found
```

- [ ] **Step 4: Run; expected PASS.**
`python -m pytest plugins/flow-review/engine/flow_review/test_audit.py plugins/flow-review/engine/flow_review/test_config.py -q`

- [ ] **Step 5: Verify.**
```
python -m pytest -q
```
Expected: green -- this is also the task that finally closes the loop on `test_drift.py`'s
`test_reports_a_surface_the_repo_gained` (an `openapi.yaml` producing an `"api"` candidate) now
that `detect()`'s shape has changed; re-run the full suite, not just `test_audit.py`, to confirm
A7's drift tests still pass unchanged against the new `detect()`.

- [ ] **Commit:**
```
git add plugins/flow-review/engine/flow_review/audit.py plugins/flow-review/engine/flow_review/test_audit.py plugins/flow-review/engine/flow_review/config.py
git commit -m "feat(audit): detect workspaces, Poetry, web-framework ports, and Tauri/Expo/Electron as pending-driver (A-14)"
```

---

### Task A10: Managed venv (`flow-review setup-env`), `.flow-review/.gitignore`, `.env` loader, redaction registry wiring

**Executor:** sonnet · **Depends:** A2, A4 · **Wave:** 3

**Files:**
- Create: `plugins/flow-review/engine/flow_review/envsetup.py`
- Create: `plugins/flow-review/engine/flow_review/test_envsetup.py`
- Modify: `plugins/flow-review/engine/flow_review/cli.py` (replace the `setup-env` stub with a
  real subcommand)

**Interfaces:**
- Consumes: `flow_review.events.register_secret` (A4 -- the `.env` loader is the one real
  populator of the redaction registry in M1; nothing else calls it).
- Produces (relied on by C2's SKILL setup flow and by CI usage per A-10, `uvx --from
  'flow-review[web]' flow-review replay`):
  - `flow_review.envsetup.VENV_DIRNAME = ".venv"` (created under the project's `.flow-review/`
    directory, i.e. `.flow-review/.venv`).
  - `class SetupResult` (dataclass): `created: bool, used_uv: bool, venv_path: Path,
    commands_run: list[list[str]]`. `created=False` means setup was a no-op (already set up with
    the same extras against the same engine path -- idempotent, per A-10's requirement).
  - `flow_review.envsetup.find_uv(which=shutil.which) -> str | None` -- `which("uv")`, injectable
    so a test can force either the uv or the pip-fallback branch without depending on whether
    the CI/dev box actually has uv installed.
  - `flow_review.envsetup.setup_env(project_dir: Path, engine_path: Path, extras: str = "web",
    runner=subprocess.run, which=shutil.which) -> SetupResult` -- creates
    `<project_dir>/.flow-review/.venv` (via `uv venv` if `find_uv(which)` finds one, else
    `python -m venv`) and installs `<engine_path>[<extras>]` into it (via `uv pip install
    --python <venv-python> ...` or `<venv-python> -m pip install ...`). Every subprocess call
    goes through the injected `runner` (defaulting to the real `subprocess.run`, but every test
    in this task injects a recording fake instead -- **no test in this suite ever spawns a real
    `uv`/`pip`/`venv` process or touches the network**, per this task's own requirement).
    `runner` is called as `runner(cmd_list, ...)` and must return an object with `.returncode`;
    any non-zero return raises `RuntimeError(f"command failed: {cmd_list}")`. Idempotency: a
    marker file `.flow-review/.venv/.flow-review-setup.json` records `{"extras": extras,
    "engine_path": str(engine_path)}` after a successful setup; a second call with the same
    `extras`/`engine_path` and an existing matching marker returns `SetupResult(created=False,
    ...)` without invoking `runner` at all.
  - `flow_review.envsetup.write_gitignore(flow_review_dir: Path, commit_recordings: bool = True)
    -> None` -- writes `<flow_review_dir>/.gitignore` (i.e. `.flow-review/.gitignore`) listing
    `.env` and `.venv/` and `runs/` always, plus `recordings/` ONLY when `commit_recordings` is
    `False` (the default, `True`, means recordings ARE committed -- per the task instruction "commit
    recordings" is the default, so `.gitignore` does NOT exclude them unless the user opts out).
    Idempotent/deterministic: always rewrites the whole file (this is a tool-owned generated
    file, not the human-owned flows manifest A6 protects -- no lock-hash mechanism here).
  - `flow_review.envsetup.load_dotenv(path: Path, environ: dict | None = None) -> dict[str, str]`
    -- a dependency-free `KEY=VALUE` parser (no `python-dotenv`): skips blank lines and lines
    starting with `#`, splits on the first `=`, strips surrounding matched `'` or `"` quotes from
    the value. Every parsed value is passed to `flow_review.events.register_secret` (wiring the
    redaction registry A4 defined). Every parsed pair is also written into `environ` (defaulting
    to `os.environ` in real use; every test in this task passes its own plain `dict` instead, so
    no test mutates the real process environment). Returns the parsed dict either way.
  - `flow-review setup-env [--extras web] [--engine-path PATH] [--no-commit-recordings]` CLI
    subcommand: resolves `engine_path` to the bundled engine's own directory when not given
    (`Path(__file__).resolve().parent.parent`, i.e. the `engine/` directory this file's package
    lives under), calls `setup_env` then `write_gitignore(Path(".flow-review"),
    commit_recordings=not args.no_commit_recordings)`, prints one summary line, exits 0. Any
    exception is caught at the CLI boundary and reported on stderr with exit 1 (same pattern as
    `_run_migrate` in A3).

- [ ] **Step 1: Write the failing test (full pytest code).**

Create `plugins/flow-review/engine/flow_review/test_envsetup.py`:

```python
from __future__ import annotations

import json
import sys

import pytest

from flow_review import envsetup, events


class _FakeCompleted:
    def __init__(self, returncode=0):
        self.returncode = returncode


class _RecordingRunner:
    def __init__(self, returncode=0):
        self.calls: list[list[str]] = []
        self.returncode = returncode

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        return _FakeCompleted(self.returncode)


@pytest.fixture(autouse=True)
def _clean_registry():
    events.clear_secrets()
    yield
    events.clear_secrets()


def test_find_uv_uses_the_injected_which():
    assert envsetup.find_uv(which=lambda name: "/usr/bin/uv" if name == "uv" else None) == "/usr/bin/uv"
    assert envsetup.find_uv(which=lambda name: None) is None


def test_setup_env_uses_uv_when_found(tmp_path):
    runner = _RecordingRunner()
    result = envsetup.setup_env(
        tmp_path, tmp_path / "engine", runner=runner, which=lambda n: "/usr/bin/uv" if n == "uv" else None,
    )
    assert result.created is True
    assert result.used_uv is True
    assert any("uv" in cmd[0] or cmd[0].endswith("uv") for cmd in runner.calls)
    assert (tmp_path / ".flow-review" / ".venv").exists()


def test_setup_env_falls_back_to_stdlib_venv_and_pip_without_uv(tmp_path):
    runner = _RecordingRunner()
    result = envsetup.setup_env(tmp_path, tmp_path / "engine", runner=runner, which=lambda n: None)
    assert result.used_uv is False
    assert any(sys.executable in cmd or "python" in cmd[0].lower() for cmd in runner.calls)


def test_setup_env_never_spawns_a_real_process(tmp_path):
    # The requirement this test locks in: every subprocess interaction goes through `runner`.
    calls = []
    def spy_runner(cmd, **kwargs):
        calls.append(cmd)
        return _FakeCompleted(0)
    envsetup.setup_env(tmp_path, tmp_path / "engine", runner=spy_runner, which=lambda n: None)
    assert calls, "setup_env must have invoked the injected runner, not a real subprocess"


def test_a_failing_command_raises(tmp_path):
    runner = _RecordingRunner(returncode=1)
    with pytest.raises(RuntimeError):
        envsetup.setup_env(tmp_path, tmp_path / "engine", runner=runner, which=lambda n: None)


def test_setup_env_is_idempotent_for_the_same_extras_and_engine_path(tmp_path):
    runner = _RecordingRunner()
    first = envsetup.setup_env(tmp_path, tmp_path / "engine", runner=runner, which=lambda n: None)
    second = envsetup.setup_env(tmp_path, tmp_path / "engine", runner=runner, which=lambda n: None)
    assert first.created is True
    assert second.created is False
    assert len(runner.calls) == 2  # no new calls on the second, no-op run


def test_setup_env_reruns_when_extras_change(tmp_path):
    runner = _RecordingRunner()
    envsetup.setup_env(tmp_path, tmp_path / "engine", extras="web", runner=runner, which=lambda n: None)
    calls_after_first = len(runner.calls)
    result = envsetup.setup_env(tmp_path, tmp_path / "engine", extras="web,mobile", runner=runner, which=lambda n: None)
    assert result.created is True
    assert len(runner.calls) > calls_after_first


def test_gitignore_commits_recordings_by_default(tmp_path):
    envsetup.write_gitignore(tmp_path)
    text = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in text
    assert ".venv/" in text
    assert "runs/" in text
    assert "recordings/" not in text


def test_gitignore_excludes_recordings_when_opted_out(tmp_path):
    envsetup.write_gitignore(tmp_path, commit_recordings=False)
    text = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert "recordings/" in text


def test_load_dotenv_parses_key_value_pairs_skipping_comments_and_blanks(tmp_path):
    path = tmp_path / ".env"
    path.write_text("# a comment\n\nADMIN_PASSWORD=hunter2\nQUOTED=\"has spaces\"\n", encoding="utf-8")
    env = {}
    result = envsetup.load_dotenv(path, environ=env)
    assert result == {"ADMIN_PASSWORD": "hunter2", "QUOTED": "has spaces"}
    assert env == result


def test_load_dotenv_registers_every_value_for_redaction(tmp_path):
    path = tmp_path / ".env"
    path.write_text("ADMIN_PASSWORD=hunter2\n", encoding="utf-8")
    envsetup.load_dotenv(path, environ={})
    written = events.append(tmp_path, {"type": "step", "text": "logged in with hunter2"})
    assert "hunter2" not in written["text"]


def test_load_dotenv_defaults_to_os_environ_when_none_given(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("SOME_VAR=abc\n", encoding="utf-8")
    monkeypatch.delenv("SOME_VAR", raising=False)
    envsetup.load_dotenv(path)
    import os
    assert os.environ["SOME_VAR"] == "abc"
```

- [ ] **Step 2: Run it; expected FAIL.** `ModuleNotFoundError: No module named 'flow_review.envsetup'`.

- [ ] **Step 3: Minimal implementation.**

`plugins/flow-review/engine/flow_review/envsetup.py`:

```python
"""Managed venv setup, .flow-review scaffolding, and a dependency-free .env loader (A-10).

Every subprocess interaction is injected (`runner`) and every `which` lookup is injected too --
this module is exercised entirely against fakes; nothing here ever spawns uv/pip/venv for real
or touches the network in this suite. That is a requirement of this task, not an incidental
convenience: setup-env is exactly the kind of command a CI run or a sandboxed test box cannot
actually execute, so the logic that decides WHAT to run has to be testable independently of
actually running it.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

VENV_DIRNAME = ".venv"
_MARKER_NAME = ".flow-review-setup.json"


@dataclass
class SetupResult:
    created: bool
    used_uv: bool
    venv_path: Path
    commands_run: list[list[str]] = field(default_factory=list)


def find_uv(which=shutil.which) -> str | None:
    return which("uv")


def _venv_python(venv_path: Path) -> Path:
    if os.name == "nt":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def _run(runner, cmd: list[str]) -> None:
    result = runner(cmd)
    if getattr(result, "returncode", 1) != 0:
        raise RuntimeError(f"command failed: {cmd}")


def setup_env(
    project_dir: Path, engine_path: Path, extras: str = "web",
    runner=subprocess.run, which=shutil.which,
) -> SetupResult:
    project_dir = Path(project_dir)
    engine_path = Path(engine_path)
    flow_review_dir = project_dir / ".flow-review"
    venv_path = flow_review_dir / VENV_DIRNAME
    marker = venv_path / _MARKER_NAME

    desired = {"extras": extras, "engine_path": str(engine_path)}
    if marker.exists():
        try:
            existing = json.loads(marker.read_text(encoding="utf-8"))
        except ValueError:
            existing = None
        if existing == desired:
            return SetupResult(created=False, used_uv=False, venv_path=venv_path)

    flow_review_dir.mkdir(parents=True, exist_ok=True)
    commands: list[list[str]] = []
    uv = find_uv(which)

    if uv:
        create_cmd = [uv, "venv", str(venv_path)]
        _run(runner, create_cmd)
        commands.append(create_cmd)
        install_cmd = [uv, "pip", "install", "--python", str(_venv_python(venv_path)), f"{engine_path}[{extras}]"]
        _run(runner, install_cmd)
        commands.append(install_cmd)
        used_uv = True
    else:
        create_cmd = [sys.executable, "-m", "venv", str(venv_path)]
        _run(runner, create_cmd)
        commands.append(create_cmd)
        install_cmd = [str(_venv_python(venv_path)), "-m", "pip", "install", f"{engine_path}[{extras}]"]
        _run(runner, install_cmd)
        commands.append(install_cmd)
        used_uv = False

    venv_path.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps(desired), encoding="utf-8")
    return SetupResult(created=True, used_uv=used_uv, venv_path=venv_path, commands_run=commands)


def write_gitignore(flow_review_dir: Path, commit_recordings: bool = True) -> None:
    flow_review_dir = Path(flow_review_dir)
    flow_review_dir.mkdir(parents=True, exist_ok=True)
    lines = [".env", ".venv/", "runs/"]
    if not commit_recordings:
        lines.append("recordings/")
    (flow_review_dir / ".gitignore").write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_dotenv(path: Path, environ: dict | None = None) -> dict[str, str]:
    from flow_review import events  # local import: envsetup must not force events' import cost
                                     # onto every caller that only wants the .gitignore writer

    target = os.environ if environ is None else environ
    path = Path(path)
    parsed: dict[str, str] = {}
    if not path.exists():
        return parsed
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        parsed[key] = value
        events.register_secret(value)
        target[key] = value
    return parsed
```

Wire the CLI subcommand in `cli.py`: replace the generic `setup-env` stub entry with:

```python
setup_env_parser = sub.add_parser("setup-env")
setup_env_parser.add_argument("--extras", default="web")
setup_env_parser.add_argument("--engine-path", default=None)
setup_env_parser.add_argument("--no-commit-recordings", action="store_true")
setup_env_parser.set_defaults(func=_run_setup_env)
```
and:
```python
def _run_setup_env(args: argparse.Namespace) -> int:
    from pathlib import Path
    from flow_review import envsetup as envsetupmod
    engine_path = Path(args.engine_path) if args.engine_path else Path(__file__).resolve().parent.parent
    try:
        envsetupmod.setup_env(Path("."), engine_path, extras=args.extras)
        envsetupmod.write_gitignore(Path(".flow-review"), commit_recordings=not args.no_commit_recordings)
    except Exception as exc:  # noqa: BLE001 -- CLI boundary
        print(str(exc), file=sys.stderr)
        return 1
    print(f"flow-review: environment ready at .flow-review/.venv (extras={args.extras})")
    return 0
```
(remove `"setup-env"` from `_STUB_VERBS`.)

- [ ] **Step 4: Run; expected PASS.**
`python -m pytest plugins/flow-review/engine/flow_review/test_envsetup.py plugins/flow-review/engine/flow_review/test_cli.py -q`

- [ ] **Step 5: Verify.**
```
python -m pytest -q
```
Expected: all green -- this is CP1's gate (A1 through A10 all landed). Also confirm no test in
`test_envsetup.py` needed network access or a real `uv`/`pip`/`venv` invocation:
```
python -m pytest plugins/flow-review/engine/flow_review/test_envsetup.py -q -p no:cacheprovider --tb=short
```
(no `--disable-socket`-style plugin is assumed installed; the manual check is reading the test
file itself -- every test constructs a `runner`/`which` fake and never calls the real
`subprocess.run`/`shutil.which` defaults.)

- [ ] **Commit:**
```
git add plugins/flow-review/engine/flow_review/envsetup.py plugins/flow-review/engine/flow_review/test_envsetup.py plugins/flow-review/engine/flow_review/cli.py
git commit -m "feat(envsetup): managed venv setup (uv/pip), .flow-review/.gitignore, dependency-free .env loader wired to redaction"
```


---

### Task B0: Fixture web app with planted bugs

**Executor:** haiku · **Depends:** A1 · **Wave:** 2
**Files:**
- `plugins/flow-review/engine/fixtures/webapp/index.html`
- `plugins/flow-review/engine/fixtures/webapp/docs.html`
- `plugins/flow-review/engine/fixtures/webapp/app.js`
- `plugins/flow-review/engine/fixtures/webapp/app.css`
- `plugins/flow-review/engine/fixtures/webapp/tokens.json`
- `plugins/flow-review/engine/fixtures/webapp/README.md`
- `plugins/flow-review/engine/fixtures/webapp/test_fixture.py`
- `plugins/flow-review/engine/conftest.py` (new — shared `webapp_server` fixture, stdlib
  `http.server` subclass)
- `pytest.ini` (new, repo root)

**Interfaces:**
- Consumes: nothing (no code dependency; A1 only supplies the repo layout).
- Produces (consumed by B1-B4 and later B5-B9):
  - `webapp_server() -> tuple[str, list[dict]]`, function-scoped, yields
    `(base_url, requests_log)`; `requests_log` accumulates
    `{"method": str, "path": str, "status": int}` per request.
  - Static pages at `base_url + "/"` (index) and `base_url + "/docs.html"` (orphan — no link to
    it exists anywhere in `index.html`).
  - `GET {base_url}/api/fail` → HTTP 500, JSON body `{"error": "boom"}`.
  - `GET {base_url}/tokens.json` → the token source `app.css` is supposed to honor.
  - Planted bugs, one per line, cited by rule id for B4:
    1. Low-contrast text `#muted-note` (`.muted { color:#999999; background:#ffffff; }`,
       ratio ≈2.85:1) — `contrast.aa`.
    2. Off-token color: `tokens.json` has `"color.primary": "#1a56db"`; `#cta-button` uses
       `background: #1a57dc` — `token.color`.
    3. Overlapping buttons: `#save-button` and `#cancel-button`, both
       `position:absolute; top:40px; left:20px; width:80px; height:30px` — `rect.overlap`.
    4. Dead button: `#help-button` exists in the DOM with no click handler in `app.js`.
    5. Fetch to a 5xx route: `#load-button` click handler calls `fetch('/api/fail')` — `http.5xx`.
    6. Docs-only page: `docs.html` documents an "Export" feature never linked from `index.html`
       — discoverability metric (owned by D3/C4, fixture only carries the bug).
    7. Password field: `<input type="password" id="pw" data-testid="pw-input">` inside
       `#login-form` — exercises B1 screenshot masking and B2 action-log redaction.
    8. Sign-in flow: `#login-form` submit handler shows `#signin-status` when both fields are
       non-empty — the flow B1/B2/B3 record and replay against.

- [ ] **Step 1: failing test.** Create `plugins/flow-review/engine/conftest.py` with the
  fixture stubbed to raise, then write the test:
  ```python
  # plugins/flow-review/engine/fixtures/webapp/test_fixture.py
  import json
  import urllib.error
  import urllib.request


  def test_webapp_server_serves_fixture_and_fail_route(webapp_server):
      base_url, requests_log = webapp_server

      body = urllib.request.urlopen(base_url + "/").read().decode()
      assert "muted-note" in body
      assert "cta-button" in body
      assert 'id="pw"' in body and 'data-testid="pw-input"' in body
      assert 'href="docs.html"' not in body  # orphan: docs.html not linked from index

      docs = urllib.request.urlopen(base_url + "/docs.html").read().decode()
      assert "export" in docs.lower()

      tokens = json.loads(urllib.request.urlopen(base_url + "/tokens.json").read())
      assert tokens["color.primary"] == "#1a56db"

      try:
          urllib.request.urlopen(base_url + "/api/fail")
          assert False, "expected HTTPError"
      except urllib.error.HTTPError as exc:
          assert exc.code == 500

      assert any(r["path"] == "/api/fail" and r["status"] == 500 for r in requests_log)
  ```
  Add `pytest.ini` at the repo root:
  ```ini
  [pytest]
  pythonpath = plugins/flow-review/engine
  markers =
      web: requires Playwright and a real browser (pytest.importorskip("playwright"))
  ```
  Stub `conftest.py`:
  ```python
  # plugins/flow-review/engine/conftest.py
  import pytest


  @pytest.fixture
  def webapp_server():
      raise NotImplementedError
  ```
- [ ] **Step 2: run, expect FAIL.**
  `pytest plugins/flow-review/engine/fixtures/webapp/test_fixture.py -x`
  Expected: `NotImplementedError` from the stub fixture.
- [ ] **Step 3: implementation.** Write the five fixture files:
  ```html
  <!-- plugins/flow-review/engine/fixtures/webapp/index.html -->
  <!doctype html>
  <html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Flow Review Fixture App</title>
    <link rel="stylesheet" href="app.css">
  </head>
  <body>
    <header>
      <nav><a href="/">Home</a></nav>
    </header>
    <main>
      <h1>Fixture App</h1>
      <p id="muted-note" class="muted">This note is intentionally low contrast.</p>

      <section id="login" aria-label="Sign in">
        <form id="login-form">
          <label for="username">Username</label>
          <input type="text" id="username" data-testid="username-input" name="username">
          <label for="pw">Password</label>
          <input type="password" id="pw" data-testid="pw-input" name="password">
          <button type="submit" id="signin-button" data-testid="signin-button">Sign in</button>
        </form>
        <p id="signin-status" hidden>Signed in.</p>
      </section>

      <section id="actions">
        <button id="cta-button" data-testid="cta-button">Continue</button>
        <div class="button-stack">
          <button id="save-button" data-testid="save-button">Save</button>
          <button id="cancel-button" data-testid="cancel-button">Cancel</button>
        </div>
        <button id="help-button" data-testid="help-button">Help</button>
        <button id="load-button" data-testid="load-button">Load data</button>
        <p id="load-status" hidden></p>
      </section>
    </main>
    <script src="app.js"></script>
  </body>
  </html>
  ```
  ```html
  <!-- plugins/flow-review/engine/fixtures/webapp/docs.html -->
  <!doctype html>
  <html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Fixture App Docs</title>
  </head>
  <body>
    <h1>Fixture App Documentation</h1>
    <h2>Export</h2>
    <p>The Export feature lets a signed-in user download their data as JSON. It has no
       link from the app UI; discovering it requires reading these docs.</p>
    <h2>Sign in</h2>
    <p>Enter a username and password and submit the form to sign in.</p>
  </body>
  </html>
  ```
  ```css
  /* plugins/flow-review/engine/fixtures/webapp/app.css */
  body { font-family: sans-serif; margin: 2rem; background: #ffffff; color: #1a1a1a; }

  .muted { color: #999999; background: #ffffff; }

  #cta-button {
    background: #1a57dc; /* one hex digit off tokens.json's color.primary #1a56db */
    color: #ffffff;
    border: none;
    padding: 8px 16px;
  }

  .button-stack { position: relative; height: 80px; }

  #save-button, #cancel-button {
    position: absolute;
    top: 40px;
    left: 20px;
    width: 80px;
    height: 30px;
  }

  #help-button, #load-button { margin-top: 12px; }
  ```
  ```javascript
  // plugins/flow-review/engine/fixtures/webapp/app.js
  document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("login-form");
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const username = document.getElementById("username").value;
      const password = document.getElementById("pw").value;
      if (username && password) {
        document.getElementById("signin-status").hidden = false;
      }
    });

    document.getElementById("save-button").addEventListener("click", () => {
      console.log("saved");
    });
    document.getElementById("cancel-button").addEventListener("click", () => {
      console.log("cancelled");
    });
    // #help-button is intentionally left without a click handler (planted dead-button bug).

    document.getElementById("load-button").addEventListener("click", () => {
      fetch("/api/fail")
        .then((res) => {
          if (!res.ok) {
            console.error("load failed: " + res.status);
          }
        })
        .catch((err) => console.error("load error: " + err));
    });
  });
  ```
  ```json
  {
    "color.primary": "#1a56db",
    "color.text": "#1a1a1a",
    "color.bg": "#ffffff"
  }
  ```
  ```markdown
  # Fixture App

  A tiny static app used only by flow-review's own engine tests. It exists to exercise
  every measurement rule and the explorer's docs pass.

  ## Features

  - **Sign in** — a username/password form (`#login-form`). Submitting with both fields
    filled shows "Signed in."
  - **Continue** (`#cta-button`) — a primary action button.
  - **Save** / **Cancel** (`#save-button`, `#cancel-button`) — two buttons that sit in the
    same spot.
  - **Help** (`#help-button`) — present in the UI, does nothing when clicked.
  - **Load data** (`#load-button`) — fetches `/api/fail`, which always returns HTTP 500.
  - **Export** — download your data as JSON. Not linked from the app UI; see `docs.html`.
  ```
  Implement `conftest.py`:
  ```python
  # plugins/flow-review/engine/conftest.py
  import json
  import threading
  from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
  from pathlib import Path

  import pytest

  WEBAPP_DIR = Path(__file__).parent / "fixtures" / "webapp"

  _CONTENT_TYPES = {
      ".html": "text/html", ".js": "application/javascript",
      ".css": "text/css", ".json": "application/json",
  }


  def _make_handler(requests_log: list[dict]):
      class FixtureHandler(BaseHTTPRequestHandler):
          def log_message(self, *args):  # silence stdlib access log
              pass

          def do_GET(self):
              path = self.path.split("?", 1)[0]
              if path == "/api/fail":
                  body = json.dumps({"error": "boom"}).encode()
                  self.send_response(500)
                  self.send_header("Content-Type", "application/json")
                  self.send_header("Content-Length", str(len(body)))
                  self.end_headers()
                  self.wfile.write(body)
                  requests_log.append({"method": "GET", "path": path, "status": 500})
                  return
              fs_path = WEBAPP_DIR / (path.lstrip("/") or "index.html")
              if fs_path.is_file():
                  data = fs_path.read_bytes()
                  ctype = _CONTENT_TYPES.get(fs_path.suffix, "application/octet-stream")
                  self.send_response(200)
                  self.send_header("Content-Type", ctype)
                  self.send_header("Content-Length", str(len(data)))
                  self.end_headers()
                  self.wfile.write(data)
                  requests_log.append({"method": "GET", "path": path, "status": 200})
              else:
                  self.send_response(404)
                  self.end_headers()
                  requests_log.append({"method": "GET", "path": path, "status": 404})

      return FixtureHandler


  @pytest.fixture
  def webapp_server():
      requests_log: list[dict] = []
      server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(requests_log))
      port = server.server_address[1]
      thread = threading.Thread(target=server.serve_forever, daemon=True)
      thread.start()
      try:
          yield f"http://127.0.0.1:{port}", requests_log
      finally:
          server.shutdown()
          thread.join(timeout=5)
  ```
- [ ] **Step 4: run, expect PASS.**
  `pytest plugins/flow-review/engine/fixtures/webapp/test_fixture.py -x`
- **Verify:** `pytest plugins/flow-review/engine/fixtures/webapp/test_fixture.py -v`
- **Commit:** `git add pytest.ini plugins/flow-review/engine/conftest.py plugins/flow-review/engine/fixtures/webapp/` then
  `git commit -m "test: fixture webapp with planted bugs + shared server fixture"`

---

### Task B1: Playwright driver — semantic locators, actions, masking, capture

**Executor:** sonnet · **Depends:** A10, B0 · **Wave:** 4
**Files:**
- `plugins/flow-review/engine/flow_review/web/__init__.py` (new, empty)
- `plugins/flow-review/engine/flow_review/web/driver.py`
- `plugins/flow-review/engine/flow_review/web/test_driver.py`

**Interfaces:**
- Consumes: `webapp_server` (B0, via root conftest); nothing from A10 at import time (A10's
  env only ensures Playwright's browsers are installed on the machine running these tests).
- Produces:
  ```python
  from pathlib import Path
  from typing import TypedDict


  class Locator(TypedDict, total=False):
      role: str
      name: str
      testid: str
      css: str


  class LocatorNotFound(Exception):
      def __init__(self, locator: dict):
          super().__init__(f"could not resolve locator: {locator!r}")
          self.locator = locator


  class WebDriver:
      def __init__(self, headless: bool = True, viewport: dict | None = None): ...
      def launch(self, base_url: str) -> None: ...
      def close(self) -> None: ...
      def goto(self, path: str) -> None: ...
      def resolve(self, locator: dict): ...            # -> playwright Locator; raises LocatorNotFound
      def click(self, locator: dict) -> None: ...
      def fill(self, locator: dict, value: str) -> None: ...
      def screenshot(self, path: Path) -> Path: ...      # masks password inputs via Playwright mask=
      def snapshot(self) -> dict: ...                    # page.accessibility.snapshot()
      def console_errors(self) -> list[dict]: ...         # [{"text","location","step_index": int|None}]
      def network_log(self) -> list[dict]: ...            # [{"method","url","status"}]
      def begin_step(self, step_index: int) -> None: ...  # opens the A-17 step window
      def end_step(self) -> None: ...                     # closes it; later console entries tag None
  ```
  Resolution order inside `resolve()`, per A-1: (1) `role`+`name` via `page.get_by_role`;
  (2) `testid` via `page.get_by_test_id`; (3) `css` via `page.locator`. First populated key
  wins; if it does not resolve to exactly one element, raise `LocatorNotFound(locator)` (B3
  catches this to file a divergence). `viewport`, when given, is a single
  `{"width": int, "height": int}` dict — the caller picks one entry out of
  `Surface.options["viewport"]` (a list) before constructing `WebDriver`.

- [ ] **Step 1: failing test.**
  ```python
  # plugins/flow-review/engine/flow_review/web/test_driver.py
  import pytest
  pytest.importorskip("playwright")

  from flow_review.web.driver import WebDriver, LocatorNotFound


  @pytest.mark.web
  def test_resolve_order_and_click(webapp_server):
      base_url, _ = webapp_server
      d = WebDriver(headless=True)
      d.launch(base_url)
      d.goto("/")
      d.click({"testid": "load-button"})
      assert any(n["status"] == 500 for n in d.network_log())
      d.close()


  @pytest.mark.web
  def test_resolve_missing_raises(webapp_server):
      base_url, _ = webapp_server
      d = WebDriver(headless=True)
      d.launch(base_url)
      d.goto("/")
      with pytest.raises(LocatorNotFound):
          d.resolve({"testid": "does-not-exist"})
      d.close()


  @pytest.mark.web
  def test_screenshot_masks_password_field(tmp_path, webapp_server):
      base_url, _ = webapp_server
      d = WebDriver(headless=True)
      d.launch(base_url)
      d.goto("/")
      d.fill({"testid": "pw-input"}, "hunter2")
      out = d.screenshot(tmp_path / "shot.png")
      assert out.exists() and out.stat().st_size > 0
      snap = d.snapshot()
      assert "hunter2" not in str(snap)
      d.close()


  @pytest.mark.web
  def test_console_errors_tagged_with_step_window(webapp_server):
      base_url, _ = webapp_server
      d = WebDriver(headless=True)
      d.launch(base_url)
      d.goto("/")
      d.page.evaluate("console.error('outside step')")
      d.begin_step(3)
      d.page.evaluate("console.error('inside step 3')")
      d.end_step()
      d.page.evaluate("console.error('outside again')")
      errors = d.console_errors()
      d.close()
      tagged = {e["text"]: e["step_index"] for e in errors}
      assert tagged["outside step"] is None
      assert tagged["inside step 3"] == 3
      assert tagged["outside again"] is None
  ```
- [ ] **Step 2: run, expect FAIL.**
  `pytest plugins/flow-review/engine/flow_review/web/test_driver.py -m web -x`
  Expected: `ModuleNotFoundError: flow_review.web.driver`.
- [ ] **Step 3: implementation.**
  ```python
  # plugins/flow-review/engine/flow_review/web/driver.py
  from pathlib import Path
  from typing import TypedDict

  from playwright.sync_api import sync_playwright


  class Locator(TypedDict, total=False):
      role: str
      name: str
      testid: str
      css: str


  class LocatorNotFound(Exception):
      def __init__(self, locator: dict):
          super().__init__(f"could not resolve locator: {locator!r}")
          self.locator = locator


  class WebDriver:
      def __init__(self, headless: bool = True, viewport: dict | None = None):
          self.headless = headless
          self.viewport = viewport
          self._playwright = None
          self.browser = None
          self.page = None
          self._console_errors: list[dict] = []
          self._network_log: list[dict] = []
          self._current_step: int | None = None

      def launch(self, base_url: str) -> None:
          self.base_url = base_url.rstrip("/")
          self._playwright = sync_playwright().start()
          self.browser = self._playwright.chromium.launch(headless=self.headless)
          self.page = self.browser.new_page(viewport=self.viewport)
          self.page.on("console", self._on_console)
          self.page.on("response", self._on_response)

      def close(self) -> None:
          if self.browser is not None:
              self.browser.close()
          if self._playwright is not None:
              self._playwright.stop()

      def goto(self, path: str) -> None:
          self.page.goto(self.base_url + path)

      def resolve(self, locator: dict):
          if locator.get("role"):
              loc = self.page.get_by_role(locator["role"], name=locator.get("name"))
          elif locator.get("testid"):
              loc = self.page.get_by_test_id(locator["testid"])
          elif locator.get("css"):
              loc = self.page.locator(locator["css"])
          else:
              raise LocatorNotFound(locator)
          if loc.count() != 1:
              raise LocatorNotFound(locator)
          return loc

      def click(self, locator: dict) -> None:
          self.resolve(locator).click()

      def fill(self, locator: dict, value: str) -> None:
          self.resolve(locator).fill(value)

      def screenshot(self, path: Path) -> Path:
          password_inputs = self.page.locator("input[type=password]")
          mask = [password_inputs.nth(i) for i in range(password_inputs.count())]
          self.page.screenshot(path=str(path), mask=mask, mask_color="#000000")
          return path

      def snapshot(self) -> dict:
          return self.page.accessibility.snapshot() or {}

      def console_errors(self) -> list[dict]:
          return list(self._console_errors)

      def network_log(self) -> list[dict]:
          return list(self._network_log)

      def begin_step(self, step_index: int) -> None:
          self._current_step = step_index

      def end_step(self) -> None:
          self._current_step = None

      def _on_console(self, msg) -> None:
          if msg.type == "error":
              self._console_errors.append({
                  "text": msg.text,
                  "location": str(msg.location),
                  "step_index": self._current_step,
              })

      def _on_response(self, response) -> None:
          self._network_log.append({
              "method": response.request.method,
              "url": response.url,
              "status": response.status,
          })
  ```
  ```python
  # plugins/flow-review/engine/flow_review/web/__init__.py
  ```
- [ ] **Step 4: run, expect PASS.**
  `pytest plugins/flow-review/engine/flow_review/web/test_driver.py -m web -v`
- **Verify:** `pytest plugins/flow-review/engine/flow_review/web/test_driver.py -m web -v`
- **Commit:** `git add plugins/flow-review/engine/flow_review/web/__init__.py plugins/flow-review/engine/flow_review/web/driver.py plugins/flow-review/engine/flow_review/web/test_driver.py` then
  `git commit -m "feat(web): Playwright driver, semantic locators, step-window console tagging, password masking"`

---

### Task B2: Action-log format + recorder + ephemeral repro log

**Executor:** opus · **Depends:** B1 · **Wave:** 5
**Files:**
- `plugins/flow-review/engine/flow_review/web/actionlog.py`
- `plugins/flow-review/engine/flow_review/web/test_actionlog.py`

**Interfaces:**
- Consumes: `flow_review.events.REDACTED`, `flow_review.events.register_secret` (A4, already
  built by wave 2). No dependency on `flow_review.web.driver` symbols at import time — a
  `locator` here is a plain dict, same shape B1's `Locator` produces.
- Produces:
  ```python
  from pathlib import Path

  SCHEMA_VERSION = 1


  def locator_key(locator: dict) -> str: ...
  # canonical string form used by ledger.fingerprint (A5): role+name -> testid -> css.
  #   {"role": "button", "name": "Sign in"} -> "role:button:Sign in"
  #   {"testid": "pw-input"}                -> "testid:pw-input"
  #   {"css": "#cta-button"}                -> "css:#cta-button"

  def new_log(surface_id: str, flow_id: str) -> dict: ...

  def record_step(log: dict, action: str, locator: dict | None = None,
                   value: str | None = None, url: str | None = None,
                   checkpoint: str | None = None) -> dict: ...
  # appends a step, redacts `value` to events.REDACTED when locator.get("secret") is truthy
  # (after calling events.register_secret(value) so the raw value is also caught elsewhere),
  # returns the log.

  def save(log: dict, run_dir: Path, project_root: Path, record_enabled: bool) -> Path: ...
  # record_enabled=True  -> <project_root>/.flow-review/recordings/<surface_id>/<flow_id>.json
  # record_enabled=False -> <run_dir>/repro/<flow_id>.json (ephemeral, per A-3)

  def load(path: Path) -> dict: ...
  ```
  File format (`schema_version: 1`):
  ```json
  {
    "schema_version": 1,
    "surface_id": "webapp",
    "flow_id": "login-happy-path",
    "recorded_at": "2026-09-23T12:00:00.123Z",
    "steps": [
      {"action": "goto", "url": "/", "locator": null, "value": null, "checkpoint": null},
      {"action": "fill", "url": "/", "locator": {"testid": "pw-input", "secret": true},
       "value": "[redacted]", "checkpoint": null},
      {"action": "click", "url": "/", "locator": {"role": "button", "name": "Sign in"},
       "value": null, "checkpoint": null},
      {"action": "assert_url", "url": "/dashboard", "locator": null, "value": null,
       "checkpoint": "post-login"}
    ]
  }
  ```

- [ ] **Step 1: failing test.**
  ```python
  # plugins/flow-review/engine/flow_review/web/test_actionlog.py
  from flow_review.web import actionlog


  def test_locator_key_prefers_role_then_testid_then_css():
      assert actionlog.locator_key({"role": "button", "name": "Sign in"}) == "role:button:Sign in"
      assert actionlog.locator_key({"testid": "pw-input"}) == "testid:pw-input"
      assert actionlog.locator_key({"css": "#cta-button"}) == "css:#cta-button"
      assert actionlog.locator_key({"role": "button", "name": "Sign in", "testid": "x"}) \
          == "role:button:Sign in"


  def test_record_step_redacts_secret_value():
      log = actionlog.new_log("webapp", "login-happy-path")
      actionlog.record_step(log, "goto", url="/")
      actionlog.record_step(
          log, "fill", locator={"testid": "pw-input", "secret": True},
          value="hunter2", url="/",
      )
      assert log["steps"][1]["value"] == "[redacted]"
      assert log["schema_version"] == 1


  def test_save_respects_record_flag_and_project_root(tmp_path):
      log = actionlog.new_log("webapp", "login-happy-path")
      actionlog.record_step(log, "goto", url="/")

      project_root = tmp_path / "project"
      run_dir = tmp_path / "runs" / "run1"
      run_dir.mkdir(parents=True)

      p_ephemeral = actionlog.save(log, run_dir, project_root, record_enabled=False)
      assert p_ephemeral == run_dir / "repro" / "login-happy-path.json"
      assert p_ephemeral.exists()

      p_recorded = actionlog.save(log, run_dir, project_root, record_enabled=True)
      assert p_recorded == project_root / ".flow-review" / "recordings" / "webapp" / "login-happy-path.json"
      loaded = actionlog.load(p_recorded)
      assert loaded["schema_version"] == 1
      assert loaded["surface_id"] == "webapp"
  ```
- [ ] **Step 2: run, expect FAIL.**
  `pytest plugins/flow-review/engine/flow_review/web/test_actionlog.py -x`
  Expected: `ModuleNotFoundError: flow_review.web.actionlog`.
- [ ] **Step 3: implementation.**
  ```python
  # plugins/flow-review/engine/flow_review/web/actionlog.py
  import json
  from pathlib import Path

  from flow_review import events

  SCHEMA_VERSION = 1


  def locator_key(locator: dict) -> str:
      if locator.get("role"):
          return f"role:{locator['role']}:{locator.get('name', '')}"
      if locator.get("testid"):
          return f"testid:{locator['testid']}"
      if locator.get("css"):
          return f"css:{locator['css']}"
      return "css:"


  def new_log(surface_id: str, flow_id: str) -> dict:
      return {
          "schema_version": SCHEMA_VERSION,
          "surface_id": surface_id,
          "flow_id": flow_id,
          "recorded_at": events.now_iso(),
          "steps": [],
      }


  def record_step(log: dict, action: str, locator: dict | None = None,
                   value: str | None = None, url: str | None = None,
                   checkpoint: str | None = None) -> dict:
      if locator is not None and locator.get("secret") and value is not None:
          events.register_secret(value)
          value = events.REDACTED
      log["steps"].append({
          "action": action,
          "url": url,
          "locator": locator,
          "value": value,
          "checkpoint": checkpoint,
      })
      return log


  def save(log: dict, run_dir: Path, project_root: Path, record_enabled: bool) -> Path:
      if record_enabled:
          out = (project_root / ".flow-review" / "recordings"
                 / log["surface_id"] / f"{log['flow_id']}.json")
      else:
          out = run_dir / "repro" / f"{log['flow_id']}.json"
      out.parent.mkdir(parents=True, exist_ok=True)
      out.write_text(json.dumps(log, ensure_ascii=False, indent=2))
      return out


  def load(path: Path) -> dict:
      return json.loads(path.read_text())
  ```
- [ ] **Step 4: run, expect PASS.**
  `pytest plugins/flow-review/engine/flow_review/web/test_actionlog.py -v`
- **Verify:** `pytest plugins/flow-review/engine/flow_review/web/test_actionlog.py -v`
- **Commit:** `git add plugins/flow-review/engine/flow_review/web/actionlog.py plugins/flow-review/engine/flow_review/web/test_actionlog.py` then
  `git commit -m "feat(web): action-log schema v1, locator_key, recorder, ephemeral repro log (A-1/A-3)"`

---

### Task B3: Replay + divergence detection, `flow-review replay` CLI

**Executor:** opus · **Depends:** B2, B4, A5 · **Wave:** 7
**Files:**
- `plugins/flow-review/engine/flow_review/web/replay.py`
- `plugins/flow-review/engine/flow_review/web/test_replay.py`
- `plugins/flow-review/engine/flow_review/cli.py` (edit — add the `replay` subcommand)

**Interfaces:**
- Consumes: `flow_review.web.actionlog.load/save`; `flow_review.web.driver.WebDriver`,
  `.LocatorNotFound`; `flow_review.web.measure.check_page` (B4, the measure hook — bound with
  the surface's `tokens`); `flow_review.drift.runnable_surfaces` (A7); `flow_review.ledger.load
  /save/reconcile` (A5, module functions, **not** `Ledger.load`/`.upsert`); `flow_review.events
  .now_iso`; `flow_review.config.Config`, `.Surface`, `.load` (config path resolution is the
  CLI's job, per Canonical Interfaces — `replay()`/`replay_log()` themselves take an
  already-loaded `cfg`); `flow_review.cli.find_project_root` (A1, already defined in `cli.py` —
  there is no separate `resolve_project_root` helper).
- Produces:
  ```python
  from pathlib import Path
  from typing import Callable, TypedDict

  # exit codes: 0 clean, 1 regression, 2 divergence-only, 3 config/env error
  def replay(cfg, project_root: Path, surface_id: str | None = None,
             flow_id: str | None = None) -> int: ...

  # replays ONE action log once (the validation repro, A-3): writes <log_path>.result.json,
  # never touches the ledger or divergences.json. Exit codes: 0 clean, 1 findings reproduced,
  # 2 divergence, 3 config/env error.
  def replay_log(cfg, project_root: Path, log_path: Path, run_dir: Path) -> int: ...

  # MeasureHook: called after each goto/click with (driver, surface_id, flow_id, route,
  # step_index) -> list[dict] of canonical finding payloads (B4's check_page shape). Optional --
  # replay() and replay_log() always pass one; tests may pass None or a stub.
  MeasureHook = Callable[..., list[dict]]

  def replay_one(driver, log: dict, measure: "MeasureHook | None" = None) -> "ReplayResult": ...


  class ReplayResult(TypedDict):
      flow_id: str
      status: str              # "clean" | "regression" | "divergence"
      steps_run: int
      divergence: dict | None  # {"step_index": int, "locator": dict, "reason": str, "url": str | None}
      findings: list[dict]     # canonical finding payloads raised mid-replay (measure hook +
                                # replay.checkpoint / replay.step_failed)
  ```
  `<project_root>/.flow-review/divergences.json`, written whenever `replay()` observed at least
  one divergence in this run (independent of whether it also exits 1 for a regression):
  ```json
  {
    "schema_version": 1,
    "generated_at": "2026-09-23T12:05:00.000Z",
    "divergences": [
      {"flow_id": "login-happy-path", "step_index": 2,
       "locator": {"role": "button", "name": "Sign in"},
       "reason": "locator_not_found", "url": "/"}
    ]
  }
  ```
  This file is read by D3's Haiku replay-repair agent in a later Claude Code session; `replay()`
  only writes it and never repairs the log, and it never prompts (Global Constraints).

  `replay()` walks `drift.runnable_surfaces(cfg)` filtered to `s.driver == "playwright"` (never
  `s.kind == "web"` — `kind` is `"ui"`/`"cli"`/`"api"`/`"library"` per A2; `driver` is what
  names the Playwright surface). For each matching surface with a recordings directory, every
  flow's action log is replayed with `check_page` wired in as the measure hook (bound to that
  surface's `tokens`, loaded from `options["tokens_file"]` when set). All findings from every
  replayed flow are collected, then reconciled into the ledger in one call:
  `ledger.reconcile(ledger.load(...), all_findings, flows_run={replayed flow ids}, run_id=...)`,
  and saved. Exit code: **1** if any ledger entry has `state == "regressed"` after reconcile, or
  any entry has `state == "open"`, `sev` in `("P0", "P1")` and `first_run == run_id` (a finding
  new to this run); **else 2** if any divergence occurred this run; **else 0**. No recordings
  found under any matched surface → print how to enable recording and return 0 (no ledger
  touched). Unknown `--surface` → return 3. A driver/browser launch failure → return 3.

  `replay_log(cfg, project_root, log_path, run_dir)` loads the one log at `log_path`, finds its
  `driver == "playwright"` surface by `log["surface_id"]` in `cfg`, replays it once with the
  same `check_page` measure hook, and writes `<log_path>.result.json` — the `ReplayResult` dict
  plus its `findings`, exactly as returned by `replay_one` (usable as verifier evidence with
  kind `replay`, per the Replay canonical bullet). It never calls `ledger.load`/`reconcile`/
  `save` and never writes `divergences.json`. Exit 2 when `result["status"] == "divergence"`;
  else exit 1 when `result["findings"]` is non-empty (a reproduced finding, whether from the
  measure hook, a `replay.checkpoint` mismatch, or a `replay.step_failed` exception); else 0.
  `run_dir` is accepted (mirrors the ephemeral-repro path convention from B2/A-3, and callers —
  the verifier — pass the run's own directory) but is not read by `replay_log` itself; the
  result lives next to the log, not under `run_dir`. Unknown surface for the log's
  `surface_id`, or a driver/browser launch failure → return 3.

  `replay_one`'s `assert_url` step compares **paths only** (`urllib.parse.urlparse(...).path`,
  so `http://host/dashboard?x=1` and `/dashboard` match): a mismatch appends an **objective**
  finding `{"rule": "replay.checkpoint", "sev": "P1", "disposition": "objective", ...}` to the
  step's findings and marks the flow's final `status` as `"regression"` (steps continue running
  after a checkpoint mismatch — it is not fatal like `LocatorNotFound` or an unexpected
  exception, both of which stop the flow immediately per the existing per-step try/except).

- [ ] **Step 1: failing test.**
  ```python
  # plugins/flow-review/engine/flow_review/web/test_replay.py
  import json
  from types import SimpleNamespace

  import pytest
  pytest.importorskip("playwright")

  from flow_review import config
  from flow_review.web import actionlog, replay as replay_mod
  from flow_review.web.driver import LocatorNotFound


  def _surface(base_url: str, surface_id: str = "webapp", **options) -> "config.Surface":
      opts = {"base_url": base_url, "viewport": [{"width": 1280, "height": 800}]}
      opts.update(options)
      return config.Surface(
          id=surface_id, name="Fixture App", kind="ui", driver="playwright", launch="",
          options=opts,
      )


  # ---------- replay_one: fake driver, no browser ----------

  class _FakeDriver:
      """Simulates just enough of WebDriver for replay_one: goto/click/fill and .page.url."""

      def __init__(self, fail_locators: set[str] | None = None,
                   click_target: str = "/dashboard"):
          self._fail_locators = fail_locators or set()
          self._click_target = click_target
          self.page = SimpleNamespace(url="http://x/")

      def _key(self, locator: dict) -> str:
          return locator.get("testid") or locator.get("css") or locator.get("role", "")

      def goto(self, path: str) -> None:
          self.page.url = "http://x" + path

      def click(self, locator: dict) -> None:
          if self._key(locator) in self._fail_locators:
              raise LocatorNotFound(locator)
          self.page.url = "http://x" + self._click_target

      def fill(self, locator: dict, value: str) -> None:
          pass


  def test_replay_one_clean_flow_calls_measure_after_goto_and_click():
      log = actionlog.new_log("webapp", "load-and-click")
      actionlog.record_step(log, "goto", url="/")
      actionlog.record_step(log, "click", locator={"testid": "load-button"}, url="/")

      calls = []

      def spy_measure(driver, surface_id, flow_id, route, step_index):
          calls.append((surface_id, flow_id, route, step_index))
          return []

      result = replay_mod.replay_one(_FakeDriver(click_target="/"), log, measure=spy_measure)

      assert result["status"] == "clean"
      assert result["divergence"] is None
      assert result["findings"] == []
      assert calls == [("webapp", "load-and-click", "/", 0), ("webapp", "load-and-click", "/", 1)]


  def test_replay_one_without_measure_hook_still_runs():
      log = actionlog.new_log("webapp", "no-hook")
      actionlog.record_step(log, "goto", url="/")
      result = replay_mod.replay_one(_FakeDriver(), log, measure=None)
      assert result["status"] == "clean"
      assert result["steps_run"] == 1


  def test_replay_one_divergence_on_missing_locator():
      log = actionlog.new_log("webapp", "ghost-flow")
      actionlog.record_step(log, "goto", url="/")
      actionlog.record_step(log, "click", locator={"testid": "does-not-exist"}, url="/")

      result = replay_mod.replay_one(
          _FakeDriver(fail_locators={"does-not-exist"}), log, measure=lambda *a: [],
      )
      assert result["status"] == "divergence"
      assert result["divergence"]["step_index"] == 1
      assert result["divergence"]["reason"] == "locator_not_found"
      assert result["findings"] == []


  def test_replay_one_checkpoint_mismatch_files_objective_p1_and_marks_regression():
      log = actionlog.new_log("webapp", "wrong-redirect")
      actionlog.record_step(log, "goto", url="/")
      actionlog.record_step(log, "click", locator={"testid": "signin-button"}, url="/")
      actionlog.record_step(log, "assert_url", url="/settings", checkpoint="post-login")

      result = replay_mod.replay_one(
          _FakeDriver(click_target="/dashboard"), log, measure=lambda *a: [],
      )
      assert result["status"] == "regression"
      assert len(result["findings"]) == 1
      f = result["findings"][0]
      assert f["rule"] == "replay.checkpoint"
      assert f["sev"] == "P1"
      assert f["disposition"] == "objective"
      assert "/settings" in f["text"] and "/dashboard" in f["text"]


  def test_replay_one_checkpoint_match_stays_clean():
      log = actionlog.new_log("webapp", "right-redirect")
      actionlog.record_step(log, "goto", url="/")
      actionlog.record_step(log, "click", locator={"testid": "signin-button"}, url="/")
      actionlog.record_step(log, "assert_url", url="/dashboard", checkpoint="post-login")

      result = replay_mod.replay_one(
          _FakeDriver(click_target="/dashboard"), log, measure=lambda *a: [],
      )
      assert result["status"] == "clean"
      assert result["findings"] == []


  def test_replay_one_unexpected_exception_files_objective_regression():
      log = actionlog.new_log("webapp", "boom-flow")
      actionlog.record_step(log, "goto", url="/")

      class _ExplodingDriver(_FakeDriver):
          def goto(self, path):
              raise RuntimeError("navigation timed out")

      result = replay_mod.replay_one(_ExplodingDriver(), log, measure=lambda *a: [])
      assert result["status"] == "regression"
      assert result["findings"][0]["rule"] == "replay.step_failed"
      assert result["findings"][0]["disposition"] == "objective"


  # ---------- replay(): pure paths (no browser) ----------

  def test_replay_no_recordings_prints_howto_and_exits_zero(tmp_path, capsys):
      cfg = config.Config(schema_version=2, generator_version="test",
                           surfaces=[_surface("http://127.0.0.1:1")])
      code = replay_mod.replay(cfg, tmp_path)
      assert code == 0
      assert "record" in capsys.readouterr().out.lower()


  def test_replay_unknown_surface_exits_three(tmp_path, capsys):
      cfg = config.Config(schema_version=2, generator_version="test",
                           surfaces=[_surface("http://127.0.0.1:1")])
      code = replay_mod.replay(cfg, tmp_path, surface_id="does-not-exist")
      assert code == 3


  def test_replay_ignores_non_playwright_surfaces(tmp_path):
      # driver="shell" (a cli surface) with a same-named recordings dir must never be replayed.
      recordings = tmp_path / ".flow-review" / "recordings" / "cli-tool"
      recordings.mkdir(parents=True)
      (recordings / "flow.json").write_text(json.dumps(actionlog.new_log("cli-tool", "flow")))
      cfg = config.Config(
          schema_version=2, generator_version="test",
          surfaces=[config.Surface(id="cli-tool", name="CLI", kind="cli", driver="shell",
                                    launch="")],
      )
      code = replay_mod.replay(cfg, tmp_path)
      assert code == 0  # treated as "no recordings" for any playwright surface


  # ---------- e2e against the B0 fixture (real browser) ----------

  @pytest.mark.web
  def test_replay_e2e_http_5xx_reconciles_new_open_p0_and_exits_one(tmp_path, webapp_server):
      base_url, _ = webapp_server
      project_root = tmp_path / "project"
      run_dir = tmp_path / "runs" / "run1"
      run_dir.mkdir(parents=True)

      log = actionlog.new_log("webapp", "trigger-500")
      actionlog.record_step(log, "goto", url="/")
      actionlog.record_step(log, "click", locator={"testid": "load-button"}, url="/")
      actionlog.save(log, run_dir, project_root, record_enabled=True)

      cfg = config.Config(schema_version=2, generator_version="test",
                           surfaces=[_surface(base_url)])
      code = replay_mod.replay(cfg, project_root)
      assert code == 1

      from flow_review import ledger
      ledger_ = ledger.load(project_root / ".flow-review" / "findings.json")
      assert any(e.rule == "http.5xx" and e.state == "open" and e.sev == "P0"
                 for e in ledger_.findings.values())


  @pytest.mark.web
  def test_replay_e2e_missing_locator_writes_divergences_and_exits_two(tmp_path, webapp_server):
      base_url, _ = webapp_server
      project_root = tmp_path / "project"
      run_dir = tmp_path / "runs" / "run1"
      run_dir.mkdir(parents=True)

      log = actionlog.new_log("webapp", "ghost-flow")
      actionlog.record_step(log, "goto", url="/")
      actionlog.record_step(log, "click", locator={"testid": "does-not-exist"}, url="/")
      actionlog.save(log, run_dir, project_root, record_enabled=True)

      cfg = config.Config(schema_version=2, generator_version="test",
                           surfaces=[_surface(base_url)])
      code = replay_mod.replay(cfg, project_root)
      assert code == 2
      div_path = project_root / ".flow-review" / "divergences.json"
      assert div_path.exists()
      data = json.loads(div_path.read_text())
      assert data["divergences"][0]["flow_id"] == "ghost-flow"
      assert data["divergences"][0]["reason"] == "locator_not_found"


  @pytest.mark.web
  def test_replay_log_mode_writes_result_json_and_never_touches_ledger(tmp_path, webapp_server):
      base_url, _ = webapp_server
      project_root = tmp_path / "project"
      run_dir = tmp_path / "runs" / "run1"
      run_dir.mkdir(parents=True)

      log = actionlog.new_log("webapp", "trigger-500")
      actionlog.record_step(log, "goto", url="/")
      actionlog.record_step(log, "click", locator={"testid": "load-button"}, url="/")
      log_path = actionlog.save(log, run_dir, project_root, record_enabled=False)

      cfg = config.Config(schema_version=2, generator_version="test",
                           surfaces=[_surface(base_url)])
      code = replay_mod.replay_log(cfg, project_root, log_path, run_dir)
      assert code == 1

      result_path = log_path.with_name(log_path.name + ".result.json")
      assert result_path.exists()
      data = json.loads(result_path.read_text())
      assert any(f["rule"] == "http.5xx" for f in data["findings"])
      assert not (project_root / ".flow-review" / "findings.json").exists()
      assert not (project_root / ".flow-review" / "divergences.json").exists()
  ```
- [ ] **Step 2: run, expect FAIL.**
  `pytest plugins/flow-review/engine/flow_review/web/test_replay.py -x`
  Expected: `ModuleNotFoundError: flow_review.web.replay`.
- [ ] **Step 3: implementation.**
  ```python
  # plugins/flow-review/engine/flow_review/web/replay.py
  import json
  import sys
  from pathlib import Path
  from typing import Callable, TypedDict
  from urllib.parse import urlparse

  from flow_review import drift, events, ledger
  from flow_review.web import actionlog
  from flow_review.web import measure as measure_mod
  from flow_review.web.driver import LocatorNotFound, WebDriver

  MeasureHook = Callable[..., list[dict]]


  class ReplayResult(TypedDict):
      flow_id: str
      status: str
      steps_run: int
      divergence: dict | None
      findings: list[dict]


  def _url_path(url: str | None) -> str:
      if not url:
          return "/"
      return urlparse(url).path or "/"


  def _current_path(driver) -> str:
      return _url_path(getattr(driver.page, "url", None))


  def replay_one(driver, log: dict, measure: MeasureHook | None = None) -> ReplayResult:
      steps_run = 0
      findings: list[dict] = []
      surface_id, flow_id = log["surface_id"], log["flow_id"]

      for index, step in enumerate(log["steps"]):
          action = step["action"]
          try:
              if action == "goto":
                  driver.goto(step["url"])
                  if measure is not None:
                      route = _current_path(driver) or _url_path(step["url"])
                      findings.extend(measure(driver, surface_id, flow_id, route, index))
              elif action == "click":
                  driver.click(step["locator"])
                  if measure is not None:
                      findings.extend(
                          measure(driver, surface_id, flow_id, _current_path(driver), index)
                      )
              elif action == "fill":
                  driver.fill(step["locator"], step["value"] or "")
              elif action == "assert_url":
                  expected = _url_path(step["url"])
                  actual = _current_path(driver)
                  if actual != expected:
                      findings.append({
                          "surface_id": surface_id, "flow_id": flow_id,
                          "rule": "replay.checkpoint", "route": expected, "locator": "",
                          "sev": "P1",
                          "text": f"checkpoint {step.get('checkpoint')!r}: expected url path "
                                  f"{expected!r}, got {actual!r}",
                          "evidence": [f"expected={expected}", f"actual={actual}"],
                          "disposition": "objective",
                      })
              steps_run += 1
          except LocatorNotFound:
              return ReplayResult(
                  flow_id=flow_id, status="divergence", steps_run=steps_run,
                  divergence={
                      "step_index": index, "locator": step.get("locator"),
                      "reason": "locator_not_found", "url": step.get("url"),
                  },
                  findings=findings,
              )
          except Exception as exc:
              findings.append({
                  "surface_id": surface_id, "flow_id": flow_id,
                  "rule": "replay.step_failed", "route": step.get("url"), "locator": "",
                  "sev": "P1", "text": f"step {index} ({action}) raised: {exc}",
                  "evidence": [], "disposition": "objective",
              })
              return ReplayResult(flow_id=flow_id, status="regression", steps_run=steps_run,
                                   divergence=None, findings=findings)

      status = "regression" if any(f["rule"] == "replay.checkpoint" for f in findings) else "clean"
      return ReplayResult(flow_id=flow_id, status=status, steps_run=steps_run,
                           divergence=None, findings=findings)


  def _load_tokens(surface, project_root: Path) -> dict[str, str] | None:
      tokens_file = surface.options.get("tokens_file")
      if not tokens_file:
          return None
      path = Path(tokens_file)
      if not path.is_absolute():
          path = project_root / tokens_file
      if not path.is_file():
          return None
      return measure_mod.load_tokens(path)  # .css/.scss custom properties or .json (A-25)


  def _measure_hook(tokens: dict[str, str] | None) -> MeasureHook:
      def hook(driver, surface_id, flow_id, route, step_index):
          return measure_mod.check_page(driver, surface_id, flow_id, route, tokens, step_index)
      return hook


  def _launch_driver(surface) -> WebDriver:
      viewport = (surface.options.get("viewport") or [None])[0]
      driver = WebDriver(headless=True, viewport=viewport)
      driver.launch(surface.options["base_url"])
      return driver


  def _playwright_surfaces(cfg, surface_id: str | None):
      surfaces = [s for s in drift.runnable_surfaces(cfg) if s.driver == "playwright"]
      if surface_id is not None:
          surfaces = [s for s in surfaces if s.id == surface_id]
      return surfaces


  def replay(cfg, project_root: Path, surface_id: str | None = None,
             flow_id: str | None = None) -> int:
      surfaces = _playwright_surfaces(cfg, surface_id)
      if surface_id is not None and not surfaces:
          print(f"no playwright surface named {surface_id!r} in config", file=sys.stderr)
          return 3

      recordings_root = project_root / ".flow-review" / "recordings"
      all_findings: list[dict] = []
      divergences: list[dict] = []
      flows_run: set[str] = set()
      found_any_recording = False

      for surface in surfaces:
          surface_dir = recordings_root / surface.id
          if not surface_dir.is_dir():
              continue
          flow_files = sorted(surface_dir.glob("*.json"))
          if flow_id is not None:
              flow_files = [p for p in flow_files if p.stem == flow_id]
          if not flow_files:
              continue

          try:
              driver = _launch_driver(surface)
          except Exception as exc:
              print(f"could not launch driver for surface {surface.id!r}: {exc}", file=sys.stderr)
              return 3

          hook = _measure_hook(_load_tokens(surface, project_root))
          try:
              for flow_path in flow_files:
                  found_any_recording = True
                  log = actionlog.load(flow_path)
                  flows_run.add(log["flow_id"])
                  result = replay_one(driver, log, measure=hook)
                  all_findings.extend(result["findings"])
                  if result["status"] == "divergence":
                      d = result["divergence"]
                      divergences.append({
                          "flow_id": result["flow_id"], "step_index": d["step_index"],
                          "locator": d["locator"], "reason": d["reason"], "url": d["url"],
                      })
          finally:
              driver.close()

      if not found_any_recording:
          print(
              "no recordings found under .flow-review/recordings/. Enable recording with "
              "`record: true` on the surface in config, or `/flow-review record <surface> "
              "<flow>` from the Claude Code plugin, then re-run `flow-review replay`."
          )
          return 0

      ledger_path = project_root / ".flow-review" / "findings.json"
      ledger_ = ledger.load(ledger_path)
      run_id = events.now_iso()
      ledger_ = ledger.reconcile(ledger_, all_findings, flows_run, run_id)
      ledger.save(ledger_, ledger_path)

      if divergences:
          out = {
              "schema_version": 1,
              "generated_at": events.now_iso(),
              "divergences": divergences,
          }
          div_path = project_root / ".flow-review" / "divergences.json"
          div_path.parent.mkdir(parents=True, exist_ok=True)
          div_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))

      # Only entries that reproduced in THIS replay count; a stale regression from an earlier
      # run stays visible in the ledger but does not fail today's exit code.
      has_regression = any(e.state == "regressed" and e.last_run == run_id
                           for e in ledger_.findings.values())
      has_new_open_critical = any(
          e.state == "open" and e.sev in ("P0", "P1") and e.first_run == run_id
          for e in ledger_.findings.values()
      )
      if has_regression or has_new_open_critical:
          return 1
      if divergences:
          return 2
      return 0


  def replay_log(cfg, project_root: Path, log_path: Path, run_dir: Path) -> int:
      log = actionlog.load(log_path)
      surfaces = [
          s for s in _playwright_surfaces(cfg, None) if s.id == log["surface_id"]
      ]
      if not surfaces:
          print(f"no playwright surface named {log['surface_id']!r} in config", file=sys.stderr)
          return 3

      try:
          driver = _launch_driver(surfaces[0])
      except Exception as exc:
          print(f"could not launch driver for surface {surfaces[0].id!r}: {exc}", file=sys.stderr)
          return 3

      hook = _measure_hook(_load_tokens(surfaces[0], project_root))
      try:
          result = replay_one(driver, log, measure=hook)
      finally:
          driver.close()

      result_path = log_path.with_name(log_path.name + ".result.json")
      result_path.write_text(json.dumps(dict(result), ensure_ascii=False, indent=2))

      if result["status"] == "divergence":
          return 2
      if result["findings"]:
          return 1
      return 0
  ```
  In `cli.py`, add the subparser (inside the existing `subparsers = parser.add_subparsers(...)`
  block) and the dispatch branch (inside the existing command dispatch). `find_project_root` is
  already defined at module scope in `cli.py` (A1); this only calls it:
  ```python
  # plugins/flow-review/engine/flow_review/cli.py  (additions)
  replay_parser = subparsers.add_parser(
      "replay", help="replay recorded flows and check for regressions/divergences",
  )
  replay_parser.add_argument("--surface", default=None)
  replay_parser.add_argument("--flow", default=None)
  replay_parser.add_argument("--log", type=Path, default=None)
  replay_parser.add_argument("--run", dest="run_dir", type=Path, default=None)
  replay_parser.add_argument("--project", type=Path, default=None)
  ```
  ```python
  elif args.command == "replay":
      from flow_review.web import replay as replay_mod

      project_root = args.project or find_project_root(Path.cwd())
      if project_root is None:
          print("no .flow-review/ found; run /flow-review setup first, or pass --project",
                file=sys.stderr)
          sys.exit(3)
      cfg = config.load(project_root / ".flow-review" / "config.json")
      if args.log is not None:
          if args.run_dir is None:
              print("--log requires --run DIR", file=sys.stderr)
              sys.exit(3)
          sys.exit(replay_mod.replay_log(cfg, project_root, args.log, args.run_dir))
      sys.exit(replay_mod.replay(cfg, project_root, args.surface, args.flow))
  ```
- [ ] **Step 4: run, expect PASS.**
  `pytest plugins/flow-review/engine/flow_review/web/test_replay.py -v`
- **Verify:** `pytest plugins/flow-review/engine/flow_review/web/test_replay.py -v -m "web or not web"`
- **Commit:** `git add plugins/flow-review/engine/flow_review/web/replay.py plugins/flow-review/engine/flow_review/web/test_replay.py plugins/flow-review/engine/flow_review/cli.py` then
  `git commit -m "feat(web): replay with divergence detection + ledger reconcile, replay --log/--run repro mode"`

---

### Task B4: Measurement engine — contrast, tokens, rects, status, console, `check_page`

**Executor:** sonnet · **Depends:** B1, B2, A5 · **Wave:** 6
**Files:**
- `plugins/flow-review/engine/flow_review/web/measure.py`
- `plugins/flow-review/engine/flow_review/web/test_measure.py`
- `plugins/flow-review/engine/flow_review/web/driver.py` (edit — B1 addendum: two cursor
  methods `check_page` needs for "since last call" http/console checks)

**Interfaces:**
- Consumes: `flow_review.web.driver.WebDriver` (browser-backed checks, and the two cursor
  methods added below); `flow_review.web.actionlog.locator_key` (B2) — `check_page` is the one
  place in this module that calls it, to turn a dict locator into the canonical string form the
  ledger expects. The per-rule pure/browser-backed functions below are unchanged from the prior
  draft and keep returning `locator: dict | None`; `measure.py` still never calls
  `ledger.fingerprint` itself for those. `check_page`, by contrast, returns the canonical
  finding-payload shape from the Canonical Interfaces (`locator` already a string, no `id` —
  the caller reconciling into the ledger, e.g. `replay()` in B3, computes fingerprint/id).
- Produces:
  ```python
  from typing import TypedDict


  class Finding(TypedDict):
      rule: str            # e.g. "contrast.aa"
      sev: str              # "P0" | "P1" | "P2"
      locator: dict | None
      route: str | None
      text: str
      evidence: list[str]
      disposition: str      # always "engine" for every finding this module returns

  def ciede2000(lab1: tuple[float, float, float], lab2: tuple[float, float, float]) -> float: ...  # pure
  def hex_to_lab(hex_color: str) -> tuple[float, float, float]: ...                                 # pure
  def normalize_hex(hex_color: str) -> str: ...                                                     # pure
  def contrast_ratio(fg_rgb: tuple[int, int, int], bg_rgb: tuple[int, int, int]) -> float: ...       # pure

  def check_contrast_pair(fg: tuple[int, int, int], bg: tuple[int, int, int], large_text: bool,
                           locator: dict, route: str) -> list[Finding]: ...                          # pure
  def check_contrast(driver, selector: str = "body *", route: str = "/") -> list[Finding]: ...       # browser-backed
  def check_tokens(computed: dict[str, str], tokens: dict[str, str],
                    locator: dict, route: str) -> list[Finding]: ...                                 # pure
  def check_rects(rects: list[dict], route: str) -> list[Finding]: ...                               # pure
  def check_http_status(network_log: list[dict], route: str) -> list[Finding]: ...                   # pure
  def check_console(console_errors: list[dict], route: str) -> list[Finding]: ...                    # pure

  # The one aggregate. Both `drive` (B10, after each action) and `replay` (B3, after each
  # goto/click) call this; nothing else aggregates rules (Canonical Interfaces › Measure).
  def check_page(driver, surface_id: str, flow_id: str, route: str,
                  tokens: dict[str, str] | None, step_index: int | None) -> list[dict]: ...
  ```
  `check_page` gathers computed style + geometry for the whole page in **one**
  `driver.page.evaluate(...)` call (not a per-element round trip like `check_contrast`'s
  existing `el.evaluate()` loop, which stays as-is for its own narrower use), then runs every
  rule against that snapshot plus the driver's http/console cursors:
  1. `driver.page.evaluate(_PAGE_SCAN_JS)` → `{"text": [...], "interactive": [...]}` (JS below).
  2. For every `text` entry with a resolvable fg/bg color pair → `check_contrast_pair`.
  3. All `interactive` entries' rects → one `check_rects` call.
  4. When `tokens is not None`: every `text` + `interactive` entry's resolvable color/
     background-color, converted back to hex → `check_tokens`, one call per entry.
  5. `driver.network_log_since_check()` → `check_http_status`.
  6. `driver.console_errors_since_check()` → `check_console` (severity already follows the
     step window the entries were tagged with at capture time in B1's `begin_step`/`end_step`;
     `check_page`'s own `step_index` argument is not re-applied to old entries — it exists so
     callers can pass it through when useful and so the signature matches the Canonical
     Interfaces bullet, not because this function needs it internally).
  7. Every `Finding` from steps 2-6 is converted to the canonical payload: `locator` becomes
     `actionlog.locator_key(f["locator"])` if `f["locator"]` else `""`; `id` is never set (the
     ledger computes id + fingerprint on reconcile); `disposition` stays `"engine"`.

  **B1 addendum** (driver.py): `check_page` needs two "since last call" cursors on the driver
  itself, because `replay()`/`drive` call it once per step and each call must see only what
  happened since the previous one.
  ```python
  # plugins/flow-review/engine/flow_review/web/driver.py  (edit)

  # in WebDriver.__init__, add two lines alongside the existing _console_errors/_network_log init:
          self._network_cursor = 0
          self._console_cursor = 0

  # two new methods on WebDriver:
      def network_log_since_check(self) -> list[dict]:
          """Network entries appended since the last call to this method. Advances the
          cursor; a second call right after returns []."""
          new_entries = self._network_log[self._network_cursor:]
          self._network_cursor = len(self._network_log)
          return new_entries

      def console_errors_since_check(self) -> list[dict]:
          """Console-error entries appended since the last call to this method. Advances
          the cursor; a second call right after returns []."""
          new_entries = self._console_errors[self._console_cursor:]
          self._console_cursor = len(self._console_errors)
          return new_entries
  ```

  Rule id / severity table (final, per A-16 and A-17):

  | rule id | trigger | sev |
  |---|---|---|
  | `contrast.aa` | text contrast ratio < 4.5:1 (normal text) or < 3:1 (large text: ≥24px, or ≥18.66px and bold) | P1 |
  | `token.color` | computed color, after `normalize_hex`, does not exactly equal any token value; ΔE2000 (CIEDE2000) to the nearest token < 3 → names that token; ΔE2000 ≥ 3 → "off-palette" | P2 (both cases) |
  | `rect.overlap` | two interactive elements' bounding boxes intersect with positive area | P1 |
  | `rect.target-size` | an interactive element's bounding box is smaller than 24×24 CSS px | P2 |
  | `http.5xx` | a captured network response has `status >= 500` | P0 |
  | `console.error` | a `console.error` entry: `step_index is not None` (fired inside a user action's step window) | P1 |
  | `console.error` | a `console.error` entry: `step_index is None` (on load / in the background) | P2 |

- [ ] **Step 1: failing test — CIEDE2000 reference pair and pure checks.**
  ```python
  # plugins/flow-review/engine/flow_review/web/test_measure.py
  from flow_review.web import measure


  def test_ciede2000_matches_sharma_reference_pair():
      # Sharma, Wu, Dalal (2005) test-data table, row 1.
      de = measure.ciede2000((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485))
      assert round(de, 4) == 2.0425


  def test_contrast_ratio_matches_known_value():
      ratio = measure.contrast_ratio((0x99, 0x99, 0x99), (0xFF, 0xFF, 0xFF))
      assert 2.8 < ratio < 2.9


  def test_check_contrast_pair_flags_low_contrast():
      findings = measure.check_contrast_pair(
          fg=(0x99, 0x99, 0x99), bg=(0xFF, 0xFF, 0xFF), large_text=False,
          locator={"css": "#muted-note"}, route="/",
      )
      assert findings and findings[0]["rule"] == "contrast.aa"
      assert findings[0]["sev"] == "P1"
      assert findings[0]["disposition"] == "engine"


  def test_check_contrast_pair_passes_large_text_at_3to1():
      findings = measure.check_contrast_pair(
          fg=(0x76, 0x76, 0x76), bg=(0xFF, 0xFF, 0xFF), large_text=True,
          locator={"css": "h1"}, route="/",
      )
      assert findings == []


  def test_check_tokens_flags_near_miss_naming_the_token():
      findings = measure.check_tokens(
          computed={"background-color": "#1a57dc"},
          tokens={"color.primary": "#1a56db"},
          locator={"css": "#cta-button"}, route="/",
      )
      assert findings[0]["rule"] == "token.color"
      assert findings[0]["sev"] == "P2"
      assert "color.primary" in findings[0]["text"]


  def test_check_tokens_flags_off_palette_when_far():
      findings = measure.check_tokens(
          computed={"background-color": "#00ff00"},
          tokens={"color.primary": "#1a56db"},
          locator={"css": "#x"}, route="/",
      )
      assert "off-palette" in findings[0]["text"]


  def test_check_tokens_passes_exact_match():
      findings = measure.check_tokens(
          computed={"background-color": "#1A56DB"},
          tokens={"color.primary": "#1a56db"},
          locator={"css": "#x"}, route="/",
      )
      assert findings == []


  def test_check_rects_flags_overlap_and_target_size():
      rects = [
          {"locator": {"css": "#save-button"}, "x": 20, "y": 40, "w": 80, "h": 30},
          {"locator": {"css": "#cancel-button"}, "x": 20, "y": 40, "w": 80, "h": 30},
          {"locator": {"css": "#tiny-icon"}, "x": 200, "y": 200, "w": 16, "h": 16},
      ]
      findings = measure.check_rects(rects, route="/")
      assert any(f["rule"] == "rect.overlap" and f["sev"] == "P1" for f in findings)
      assert any(f["rule"] == "rect.target-size" and f["sev"] == "P2" for f in findings)


  def test_check_http_status_flags_5xx():
      findings = measure.check_http_status(
          [{"method": "GET", "url": "/api/fail", "status": 500}], route="/",
      )
      assert findings[0]["rule"] == "http.5xx" and findings[0]["sev"] == "P0"


  def test_check_console_severity_follows_step_window():
      findings = measure.check_console(
          [
              {"text": "outside", "location": "", "step_index": None},
              {"text": "inside", "location": "", "step_index": 2},
          ],
          route="/",
      )
      sev_by_text = {f["text"]: f["sev"] for f in findings}
      assert sev_by_text["outside"] == "P2"
      assert sev_by_text["inside"] == "P1"


  # ---------- check_page: fake driver, no browser ----------

  class _FakePage:
      def __init__(self, scan):
          self._scan = scan

      def evaluate(self, script):
          return self._scan


  class _FakeDriver:
      def __init__(self, scan, network=None, console=None):
          self.page = _FakePage(scan)
          self._network = network or []
          self._console = console or []

      def network_log_since_check(self):
          return self._network

      def console_errors_since_check(self):
          return self._console


  def test_check_page_aggregates_every_rule_family():
      scan = {
          "text": [
              {"locator": {"css": "#muted-note"}, "color": "rgb(153, 153, 153)",
               "backgroundColor": "rgb(255, 255, 255)", "fontSize": 16.0, "fontWeight": "400"},
          ],
          "interactive": [
              {"locator": {"css": "#save-button"}, "rect": {"x": 20, "y": 40, "w": 80, "h": 30},
               "color": "rgb(0, 0, 0)", "backgroundColor": "rgb(26, 87, 220)"},
              {"locator": {"css": "#cancel-button"}, "rect": {"x": 20, "y": 40, "w": 80, "h": 30},
               "color": "rgb(0, 0, 0)", "backgroundColor": "rgb(255, 255, 255)"},
          ],
      }
      driver = _FakeDriver(
          scan,
          network=[{"method": "GET", "url": "/api/fail", "status": 500}],
          console=[{"text": "boom", "location": "", "step_index": 4}],
      )
      tokens = {"color.primary": "#1a56db"}

      payloads = measure.check_page(driver, "webapp", "login-happy-path", "/", tokens, 4)

      rules = {p["rule"] for p in payloads}
      assert rules == {"contrast.aa", "rect.overlap", "token.color", "http.5xx", "console.error"}
      for p in payloads:
          assert set(p) == {
              "surface_id", "flow_id", "rule", "route", "locator", "sev", "text",
              "evidence", "disposition",
          }
          assert "id" not in p
          assert p["disposition"] == "engine"
          assert p["surface_id"] == "webapp"
          assert p["flow_id"] == "login-happy-path"
          assert isinstance(p["locator"], str)  # canonical string form, never a dict


  def test_check_page_skips_token_checks_when_tokens_none():
      scan = {
          "text": [],
          "interactive": [
              {"locator": {"css": "#cta-button"}, "rect": {"x": 0, "y": 0, "w": 40, "h": 40},
               "color": "rgb(255, 255, 255)", "backgroundColor": "rgb(26, 87, 220)"},
          ],
      }
      payloads = measure.check_page(_FakeDriver(scan), "webapp", "flow", "/", None, None)
      assert not any(p["rule"] == "token.color" for p in payloads)


  def test_check_page_locator_is_the_canonical_string_key():
      from flow_review.web import actionlog

      scan = {
          "text": [],
          "interactive": [
              {"locator": {"testid": "save-button"}, "rect": {"x": 0, "y": 0, "w": 10, "h": 10},
               "color": "rgb(0, 0, 0)", "backgroundColor": "rgb(255, 255, 255)"},
          ],
      }
      payloads = measure.check_page(_FakeDriver(scan), "webapp", "flow", "/", None, None)
      rect_findings = [p for p in payloads if p["rule"] == "rect.target-size"]
      assert rect_findings
      assert rect_findings[0]["locator"] == actionlog.locator_key({"testid": "save-button"})


  def test_check_page_uses_http_and_console_cursors_not_full_history():
      scan = {"text": [], "interactive": []}
      driver = _FakeDriver(scan, network=[], console=[])
      # network_log_since_check()/console_errors_since_check() are the driver's job to filter;
      # check_page must not re-derive "since last call" itself.
      payloads = measure.check_page(driver, "webapp", "flow", "/", None, None)
      assert payloads == []
  ```
- [ ] **Step 2: run, expect FAIL.**
  `pytest plugins/flow-review/engine/flow_review/web/test_measure.py -x`
  Expected: `ModuleNotFoundError: flow_review.web.measure`.
- [ ] **Step 3: implementation.**
  ```python
  # plugins/flow-review/engine/flow_review/web/measure.py
  import json
  import math
  import re
  from typing import TypedDict


  class Finding(TypedDict):
      rule: str
      sev: str
      locator: dict | None
      route: str | None
      text: str
      evidence: list[str]
      disposition: str


  # ---------- CIEDE2000 (Sharma, Wu, Dalal 2005) ----------

  def ciede2000(lab1: tuple[float, float, float], lab2: tuple[float, float, float]) -> float:
      L1, a1, b1 = lab1
      L2, a2, b2 = lab2

      C1 = math.hypot(a1, b1)
      C2 = math.hypot(a2, b2)
      Cbar = (C1 + C2) / 2.0

      G = 0.5 * (1 - math.sqrt(Cbar ** 7 / (Cbar ** 7 + 25.0 ** 7)))
      a1p = (1 + G) * a1
      a2p = (1 + G) * a2

      C1p = math.hypot(a1p, b1)
      C2p = math.hypot(a2p, b2)

      def _hue(ap: float, b: float) -> float:
          if ap == 0 and b == 0:
              return 0.0
          h = math.degrees(math.atan2(b, ap))
          return h + 360.0 if h < 0 else h

      h1p = _hue(a1p, b1)
      h2p = _hue(a2p, b2)

      dLp = L2 - L1
      dCp = C2p - C1p

      if C1p * C2p == 0:
          dhp = 0.0
      else:
          dh = h2p - h1p
          if dh > 180.0:
              dh -= 360.0
          elif dh < -180.0:
              dh += 360.0
          dhp = dh
      dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp) / 2.0)

      Lbarp = (L1 + L2) / 2.0
      Cbarp = (C1p + C2p) / 2.0

      if C1p * C2p == 0:
          hbarp = h1p + h2p
      elif abs(h1p - h2p) > 180.0:
          hbarp = (h1p + h2p + 360.0) / 2.0 if h1p + h2p < 360.0 else (h1p + h2p - 360.0) / 2.0
      else:
          hbarp = (h1p + h2p) / 2.0

      T = (
          1
          - 0.17 * math.cos(math.radians(hbarp - 30))
          + 0.24 * math.cos(math.radians(2 * hbarp))
          + 0.32 * math.cos(math.radians(3 * hbarp + 6))
          - 0.20 * math.cos(math.radians(4 * hbarp - 63))
      )

      d_theta = 30 * math.exp(-(((hbarp - 275) / 25) ** 2))
      Rc = 2 * math.sqrt(Cbarp ** 7 / (Cbarp ** 7 + 25.0 ** 7))
      Sl = 1 + (0.015 * (Lbarp - 50) ** 2) / math.sqrt(20 + (Lbarp - 50) ** 2)
      Sc = 1 + 0.045 * Cbarp
      Sh = 1 + 0.015 * Cbarp * T
      Rt = -math.sin(math.radians(2 * d_theta)) * Rc

      term_L = dLp / Sl
      term_C = dCp / Sc
      term_H = dHp / Sh
      return math.sqrt(term_L ** 2 + term_C ** 2 + term_H ** 2 + Rt * term_C * term_H)


  def _srgb_to_linear(c: float) -> float:
      return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


  def normalize_hex(hex_color: str) -> str:
      h = hex_color.lstrip("#").lower()
      if len(h) == 3:
          h = "".join(ch * 2 for ch in h)
      return "#" + h


  def hex_to_lab(hex_color: str) -> tuple[float, float, float]:
      h = normalize_hex(hex_color).lstrip("#")
      r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
      r, g, b = _srgb_to_linear(r), _srgb_to_linear(g), _srgb_to_linear(b)
      x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
      y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
      z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041
      xn, yn, zn = 0.95047, 1.0, 1.08883

      def f(t: float) -> float:
          return t ** (1 / 3) if t > (6 / 29) ** 3 else t / (3 * (6 / 29) ** 2) + 4 / 29

      fx, fy, fz = f(x / xn), f(y / yn), f(z / zn)
      L = 116 * fy - 16
      a = 500 * (fx - fy)
      b_ = 200 * (fy - fz)
      return (L, a, b_)


  # ---------- contrast.aa ----------

  def _relative_luminance(rgb: tuple[int, int, int]) -> float:
      def chan(c: int) -> float:
          c = c / 255.0
          return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

      r, g, b = rgb
      return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


  def contrast_ratio(fg_rgb: tuple[int, int, int], bg_rgb: tuple[int, int, int]) -> float:
      l1 = _relative_luminance(fg_rgb)
      l2 = _relative_luminance(bg_rgb)
      lighter, darker = max(l1, l2), min(l1, l2)
      return (lighter + 0.05) / (darker + 0.05)


  def check_contrast_pair(fg: tuple[int, int, int], bg: tuple[int, int, int], large_text: bool,
                           locator: dict, route: str) -> list[Finding]:
      ratio = contrast_ratio(fg, bg)
      threshold = 3.0 if large_text else 4.5
      if ratio >= threshold:
          return []
      return [Finding(
          rule="contrast.aa", sev="P1", locator=locator, route=route,
          text=f"text contrast {ratio:.2f}:1 is below WCAG AA {threshold}:1",
          evidence=[f"ratio={ratio:.2f}", f"required={threshold}"],
          disposition="engine",
      )]


  _RGB_RE = re.compile(r"rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)")


  def _css_color_to_rgb(css: str) -> tuple[int, int, int] | None:
      m = _RGB_RE.match(css or "")
      if not m:
          return None
      r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
      a = float(m.group(4)) if m.group(4) is not None else 1.0
      return None if a == 0 else (r, g, b)


  def check_contrast(driver, selector: str = "body *", route: str = "/") -> list[Finding]:
      findings: list[Finding] = []
      elements = driver.page.locator(selector)
      for i in range(elements.count()):
          el = elements.nth(i)
          style = el.evaluate(
              "el => { const s = getComputedStyle(el); return {color: s.color, "
              "bg: s.backgroundColor, fontSize: parseFloat(s.fontSize), fontWeight: s.fontWeight}; }"
          )
          fg = _css_color_to_rgb(style["color"])
          bg = _css_color_to_rgb(style["bg"])
          if fg is None or bg is None:
              continue
          large = style["fontSize"] >= 24 or (
              style["fontSize"] >= 18.66 and style["fontWeight"] in ("bold", "700", "800", "900")
          )
          locator = {"css": f"{selector}:nth-of-type({i + 1})"}
          findings.extend(check_contrast_pair(fg, bg, large, locator, route))
      return findings


  # ---------- token.color ----------

  def check_tokens(computed: dict[str, str], tokens: dict[str, str],
                    locator: dict, route: str) -> list[Finding]:
      findings: list[Finding] = []
      token_hexes = {name: normalize_hex(v) for name, v in tokens.items()}
      for prop, raw in computed.items():
          norm = normalize_hex(raw)
          if norm in token_hexes.values():
              continue
          lab_c = hex_to_lab(norm)
          best_name, best_de = None, float("inf")
          for name, thex in token_hexes.items():
              de = ciede2000(lab_c, hex_to_lab(thex))
              if de < best_de:
                  best_de, best_name = de, name
          if best_de < 3:
              findings.append(Finding(
                  rule="token.color", sev="P2", locator=locator, route=route,
                  text=f"{prop} {norm} is close to token {best_name} ({token_hexes[best_name]}) "
                       f"but not exact (\u0394E={best_de:.2f})",
                  evidence=[f"computed={norm}", f"nearest_token={best_name}"],
                  disposition="engine",
              ))
          else:
              findings.append(Finding(
                  rule="token.color", sev="P2", locator=locator, route=route,
                  text=f"{prop} {norm} does not match any design token (off-palette)",
                  evidence=[f"computed={norm}"],
                  disposition="engine",
              ))
      return findings


  # ---------- rect.overlap / rect.target-size ----------

  def _overlaps(a: dict, b: dict) -> bool:
      ax2, ay2 = a["x"] + a["w"], a["y"] + a["h"]
      bx2, by2 = b["x"] + b["w"], b["y"] + b["h"]
      return a["x"] < bx2 and ax2 > b["x"] and a["y"] < by2 and ay2 > b["y"]


  def _locator_str(locator: dict) -> str:
      return locator.get("css") or locator.get("testid") or locator.get("role", "?")


  def check_rects(rects: list[dict], route: str) -> list[Finding]:
      findings: list[Finding] = []
      for r in rects:
          if r["w"] < 24 or r["h"] < 24:
              findings.append(Finding(
                  rule="rect.target-size", sev="P2", locator=r["locator"], route=route,
                  text=f"{_locator_str(r['locator'])} is {r['w']}x{r['h']}px, below the 24x24 minimum",
                  evidence=[f"w={r['w']}", f"h={r['h']}"], disposition="engine",
              ))
      for i in range(len(rects)):
          for j in range(i + 1, len(rects)):
              a, b = rects[i], rects[j]
              if _overlaps(a, b):
                  findings.append(Finding(
                      rule="rect.overlap", sev="P1", locator=a["locator"], route=route,
                      text=f"{_locator_str(a['locator'])} overlaps {_locator_str(b['locator'])}",
                      evidence=[json.dumps(a), json.dumps(b)], disposition="engine",
                  ))
      return findings


  # ---------- http.5xx ----------

  def check_http_status(network_log: list[dict], route: str) -> list[Finding]:
      findings: list[Finding] = []
      for entry in network_log:
          if entry["status"] >= 500:
              findings.append(Finding(
                  rule="http.5xx", sev="P0", locator=None, route=route,
                  text=f"{entry['method']} {entry['url']} returned {entry['status']}",
                  evidence=[json.dumps(entry)], disposition="engine",
              ))
      return findings


  # ---------- console.error ----------

  def check_console(console_errors: list[dict], route: str) -> list[Finding]:
      findings: list[Finding] = []
      for entry in console_errors:
          in_step = entry.get("step_index") is not None
          findings.append(Finding(
              rule="console.error", sev="P1" if in_step else "P2", locator=None, route=route,
              text=entry["text"], evidence=[json.dumps(entry)], disposition="engine",
          ))
      return findings


  # ---------- check_page: the one aggregate ----------

  _PAGE_SCAN_JS = """
  () => {
    function locatorFor(el, index) {
      if (el.dataset && el.dataset.testid) {
        return {testid: el.dataset.testid};
      }
      if (el.id) {
        return {css: '#' + el.id};
      }
      return {css: el.tagName.toLowerCase() + ':nth-of-type(' + (index + 1) + ')'};
    }

    function isVisible(el) {
      const rect = el.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return false;
      const style = getComputedStyle(el);
      if (style.visibility === 'hidden' || style.display === 'none') return false;
      if (parseFloat(style.opacity) === 0) return false;
      return true;
    }

    const INTERACTIVE_TAGS = new Set(['BUTTON', 'A', 'INPUT', 'SELECT', 'TEXTAREA']);
    const text = [];
    const interactive = [];
    let textIndex = 0;
    let interactiveIndex = 0;

    document.querySelectorAll('body *').forEach((el) => {
      if (!isVisible(el)) return;
      const rect = el.getBoundingClientRect();
      const style = getComputedStyle(el);

      const hasOwnText = Array.from(el.childNodes).some(
        (n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim().length > 0
      );
      if (hasOwnText) {
        text.push({
          locator: locatorFor(el, textIndex++),
          color: style.color,
          backgroundColor: style.backgroundColor,
          fontSize: parseFloat(style.fontSize),
          fontWeight: style.fontWeight,
        });
      }

      const isInteractive = INTERACTIVE_TAGS.has(el.tagName)
        || el.hasAttribute('role')
        || el.hasAttribute('tabindex');
      if (isInteractive) {
        interactive.push({
          locator: locatorFor(el, interactiveIndex++),
          rect: {x: rect.x, y: rect.y, w: rect.width, h: rect.height},
          color: style.color,
          backgroundColor: style.backgroundColor,
        });
      }
    });

    return {text: text, interactive: interactive};
  }
  """


  def _rgb_to_hex(css: str | None) -> str | None:
      rgb = _css_color_to_rgb(css)
      if rgb is None:
          return None
      return "#{:02x}{:02x}{:02x}".format(*rgb)


  def check_page(driver, surface_id: str, flow_id: str, route: str,
                  tokens: dict[str, str] | None, step_index: int | None) -> list[dict]:
      from flow_review.web import actionlog

      scan = driver.page.evaluate(_PAGE_SCAN_JS)
      findings: list[Finding] = []

      for item in scan["text"]:
          fg = _css_color_to_rgb(item["color"])
          bg = _css_color_to_rgb(item["backgroundColor"])
          if fg is None or bg is None:
              continue
          large = item["fontSize"] >= 24 or (
              item["fontSize"] >= 18.66 and item["fontWeight"] in ("bold", "700", "800", "900")
          )
          findings.extend(check_contrast_pair(fg, bg, large, item["locator"], route))

      rects = [
          {"locator": item["locator"], "x": item["rect"]["x"], "y": item["rect"]["y"],
           "w": item["rect"]["w"], "h": item["rect"]["h"]}
          for item in scan["interactive"]
      ]
      findings.extend(check_rects(rects, route))

      if tokens is not None:
          for item in scan["text"] + scan["interactive"]:
              computed: dict[str, str] = {}
              fg_hex = _rgb_to_hex(item.get("color"))
              if fg_hex:
                  computed["color"] = fg_hex
              bg_hex = _rgb_to_hex(item.get("backgroundColor"))
              if bg_hex:
                  computed["background-color"] = bg_hex
              if computed:
                  findings.extend(check_tokens(computed, tokens, item["locator"], route))

      findings.extend(check_http_status(driver.network_log_since_check(), route))
      findings.extend(check_console(driver.console_errors_since_check(), route))

      payloads: list[dict] = []
      for f in findings:
          loc = f["locator"]
          payloads.append({
              "surface_id": surface_id,
              "flow_id": flow_id,
              "rule": f["rule"],
              "route": route,
              "locator": actionlog.locator_key(loc) if loc else "",
              "sev": f["sev"],
              "text": f["text"],
              "evidence": f["evidence"],
              "disposition": "engine",
          })
      return payloads
  ```
  Edit `driver.py` per the B1 addendum documented above (two `__init__` lines, two methods):
  ```python
  # plugins/flow-review/engine/flow_review/web/driver.py  (edit — apply inside WebDriver)
  #
  # in __init__, next to self._console_errors / self._network_log:
  #     self._network_cursor = 0
  #     self._console_cursor = 0
  #
  # new methods:
  #     def network_log_since_check(self) -> list[dict]:
  #         new_entries = self._network_log[self._network_cursor:]
  #         self._network_cursor = len(self._network_log)
  #         return new_entries
  #
  #     def console_errors_since_check(self) -> list[dict]:
  #         new_entries = self._console_errors[self._console_cursor:]
  #         self._console_cursor = len(self._console_errors)
  #         return new_entries
  ```
- [ ] **Step 4: run, expect PASS.** `pytest plugins/flow-review/engine/flow_review/web/test_measure.py -x`
  (this covers the pure per-rule tests, the CIEDE2000 reference-pair test, and the fake-driver
  `check_page` tests — none of them need a browser.)
- [ ] **Step 5: web-marked cycle — the fixture's planted contrast bug end to end.** Add and run:
  ```python
  # appended to test_measure.py
  import pytest
  pytest.importorskip("playwright")


  @pytest.mark.web
  def test_check_contrast_catches_fixture_muted_note(webapp_server):
      from flow_review.web.driver import WebDriver

      base_url, _ = webapp_server
      d = WebDriver(headless=True)
      d.launch(base_url)
      d.goto("/")
      findings = measure.check_contrast(d, selector="#muted-note", route="/")
      d.close()
      assert any(f["rule"] == "contrast.aa" for f in findings)


  @pytest.mark.web
  def test_check_page_catches_fixture_bugs_end_to_end(webapp_server):
      from flow_review.web.driver import WebDriver

      base_url, _ = webapp_server
      d = WebDriver(headless=True)
      d.launch(base_url)
      d.goto("/")
      tokens = {"color.primary": "#1a56db"}
      findings = measure.check_page(d, "webapp", "smoke", "/", tokens, None)
      d.click({"testid": "load-button"})
      findings += measure.check_page(d, "webapp", "smoke", "/", tokens, None)
      d.close()

      rules = {f["rule"] for f in findings}
      assert "contrast.aa" in rules   # #muted-note
      assert "rect.overlap" in rules  # #save-button / #cancel-button
      assert "token.color" in rules   # #cta-button's off-token background
      assert "http.5xx" in rules      # /api/fail via #load-button
      for f in findings:
          assert isinstance(f["locator"], str)
          assert f["disposition"] == "engine"
  ```
  Run: `pytest plugins/flow-review/engine/flow_review/web/test_measure.py -m web -x` → PASS.
- [ ] **Step 6: red — token file loading (A-25).** Append to `test_measure.py` and run `pytest plugins/flow-review/engine/flow_review/web/test_measure.py -k load_tokens -x` → FAIL (`AttributeError: load_tokens`):
  ```python
  def test_load_tokens_reads_css_custom_properties(tmp_path):
      p = tmp_path / "tokens.css"
      p.write_text(":root {\n  --brand: #1a56db; /* --ghost: #000 */\n  --space-2: 8px;\n"
                   "  --ink: rgb(17, 24, 39);\n}\n", encoding="utf-8")
      assert measure.load_tokens(p) == {"--brand": "#1a56db", "--ink": "rgb(17, 24, 39)"}


  def test_load_tokens_reads_flat_and_dtcg_json(tmp_path):
      flat = tmp_path / "flat.json"
      flat.write_text('{"color.primary": "#1a56db", "radius": "4px"}', encoding="utf-8")
      assert measure.load_tokens(flat) == {"color.primary": "#1a56db"}
      dtcg = tmp_path / "dtcg.json"
      dtcg.write_text('{"color": {"primary": {"$value": "#1a56db", "$type": "color"},'
                      ' "$description": "brand"}}', encoding="utf-8")
      assert measure.load_tokens(dtcg) == {"color.primary": "#1a56db"}


  def test_load_tokens_rejects_an_unknown_extension(tmp_path):
      p = tmp_path / "tokens.yaml"
      p.write_text("a: b", encoding="utf-8")
      with pytest.raises(ValueError):
          measure.load_tokens(p)
  ```
- [ ] **Step 7: green — add to `measure.py`** (with `import json` and `import re` at the top of the module if not already present):
  ```python
  _CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
  _CSS_VAR = re.compile(r"(--[\w-]+)\s*:\s*([^;{}]+)")
  _COLORISH = re.compile(r"^(#[0-9a-fA-F]{3,8}$|rgba?\(|hsla?\()")


  def load_tokens(path: Path) -> dict[str, str]:
      """Color design tokens as {name: css color}.

      .css/.scss: color custom properties (`--brand: #1a56db`). .json: a flat map or W3C design
      tokens (`$value`), nested keys joined with dots. Non-color values are dropped, never guessed.
      """
      text = path.read_text(encoding="utf-8")
      if path.suffix in (".css", ".scss"):
          pairs = ((name, value.strip()) for name, value in _CSS_VAR.findall(_CSS_COMMENT.sub("", text)))
      elif path.suffix == ".json":
          pairs = _walk_json_tokens(json.loads(text), "")
      else:
          raise ValueError(f"tokens_file must be .css, .scss or .json, got {path.name!r}")
      return {name: value for name, value in pairs if _COLORISH.match(value)}


  def _walk_json_tokens(node, prefix: str):
      if isinstance(node, dict):
          if isinstance(node.get("$value"), str):
              yield prefix, node["$value"].strip()
              return
          for key, value in node.items():
              if not key.startswith("$"):
                  yield from _walk_json_tokens(value, f"{prefix}.{key}" if prefix else key)
      elif isinstance(node, str):
          yield prefix, node.strip()
  ```
  Run the Step 6 command → PASS.
- **Verify:** `pytest plugins/flow-review/engine/flow_review/web/test_measure.py -v -m "web or not web"`
- **Commit:** `git add plugins/flow-review/engine/flow_review/web/measure.py plugins/flow-review/engine/flow_review/web/test_measure.py plugins/flow-review/engine/flow_review/web/driver.py` then
  `git commit -m "feat(web): measurement engine — contrast/tokens/rects/http/console rules + check_page aggregate"`


---

### Task B5: Visual diff — baseline compare, changed-region crop/downscale

**Executor:** sonnet · **Depends:** B1 · **Wave:** 5
**Files:**
- `plugins/flow-review/engine/flow_review/web/visual.py`
- `plugins/flow-review/engine/flow_review/web/test_visual.py`

**Interfaces:**
- Consumes: `Pillow` (`PIL.Image`, `PIL.ImageChops`).
- Produces:
  ```python
  DEFAULT_THRESHOLD = 0.02      # fraction of pixels differing beyond DEFAULT_PIXEL_DELTA
  DEFAULT_PIXEL_DELTA = 24      # per-channel delta treated as "changed"
  DEFAULT_MAX_EDGE = 768        # px, evidence-bundle crop/downscale cap

  class DiffResult(TypedDict):
      changed: bool
      diff_ratio: float
      regions: list[dict]      # [{"x":int,"y":int,"w":int,"h":int}], merged bounding boxes

  def diff(baseline_path: Path, current_path: Path,
            threshold: float = DEFAULT_THRESHOLD,
            pixel_delta: int = DEFAULT_PIXEL_DELTA) -> DiffResult: ...

  def crop_regions(image_path: Path, regions: list[dict], out_dir: Path,
                    max_edge: int = DEFAULT_MAX_EDGE) -> list[Path]: ...
  ```
  Baselines live at `<project_root>/.flow-review/recordings/<surface_id>/baselines/<flow_id>/<step_index>.png`
  — under `recordings/`, so (per A-1/A-2) they exist only when recording is on; `diff()` never
  creates a baseline itself, only compares against one the caller passes.

- [ ] **Step 1: failing test.**
  ```python
  # plugins/flow-review/engine/flow_review/web/test_visual.py
  from PIL import Image
  from flow_review.web import visual


  def _save(path, color, size=(100, 100)):
      Image.new("RGB", size, color).save(path)


  def test_diff_identical_images_not_changed(tmp_path):
      a, b = tmp_path / "a.png", tmp_path / "b.png"
      _save(a, (255, 255, 255))
      _save(b, (255, 255, 255))
      result = visual.diff(a, b)
      assert result["changed"] is False
      assert result["diff_ratio"] == 0.0
      assert result["regions"] == []


  def test_diff_flags_changed_region(tmp_path):
      a, b = tmp_path / "a.png", tmp_path / "b.png"
      img_a = Image.new("RGB", (100, 100), (255, 255, 255))
      img_a.save(a)
      img_b = img_a.copy()
      for x in range(10, 30):
          for y in range(10, 30):
              img_b.putpixel((x, y), (255, 0, 0))
      img_b.save(b)
      result = visual.diff(a, b)
      assert result["changed"] is True
      assert result["regions"], "expected at least one bounding box"
      r = result["regions"][0]
      assert r["x"] <= 10 and r["y"] <= 10
      assert r["x"] + r["w"] >= 30 and r["y"] + r["h"] >= 30


  def test_crop_regions_downscales_to_max_edge(tmp_path):
      img = Image.new("RGB", (1000, 1000), (0, 0, 0))
      src = tmp_path / "src.png"
      img.save(src)
      out_dir = tmp_path / "crops"
      paths = visual.crop_regions(src, [{"x": 0, "y": 0, "w": 800, "h": 800}], out_dir, max_edge=200)
      assert len(paths) == 1
      with Image.open(paths[0]) as cropped:
          assert max(cropped.size) <= 200
  ```
- [ ] **Step 2: run.** `pytest plugins/flow-review/engine/flow_review/web/test_visual.py -v` → FAIL (`ModuleNotFoundError` / `AttributeError`, `visual.py` does not exist yet).
- [ ] **Step 3: implementation.**
  ```python
  # plugins/flow-review/engine/flow_review/web/visual.py
  from pathlib import Path
  from typing import TypedDict

  from PIL import Image, ImageChops

  DEFAULT_THRESHOLD = 0.02
  DEFAULT_PIXEL_DELTA = 24
  DEFAULT_MAX_EDGE = 768
  _GRID = 32


  class DiffResult(TypedDict):
      changed: bool
      diff_ratio: float
      regions: list[dict]


  def diff(baseline_path: Path, current_path: Path,
            threshold: float = DEFAULT_THRESHOLD,
            pixel_delta: int = DEFAULT_PIXEL_DELTA) -> DiffResult:
      with Image.open(baseline_path) as base_img, Image.open(current_path) as cur_img:
          base_img = base_img.convert("RGB")
          cur_img = cur_img.convert("RGB")
          if cur_img.size != base_img.size:
              cur_img = cur_img.resize(base_img.size)
          width, height = base_img.size
          raw_diff = ImageChops.difference(base_img, cur_img)
          r, g, b = raw_diff.split()
          combined = ImageChops.lighter(ImageChops.lighter(r, g), b)
          mask = combined.point(lambda p: 255 if p > pixel_delta else 0)
          histogram = mask.histogram()
          changed_count = histogram[255]
          total = width * height
          diff_ratio = changed_count / total if total else 0.0
          regions = _find_regions(mask, width, height)
      return {
          "changed": diff_ratio > threshold,
          "diff_ratio": diff_ratio,
          "regions": regions,
      }


  def _find_regions(mask: Image.Image, width: int, height: int) -> list[dict]:
      dirty_cells = set()
      for cy in range(0, height, _GRID):
          for cx in range(0, width, _GRID):
              box = (cx, cy, min(cx + _GRID, width), min(cy + _GRID, height))
              if mask.crop(box).getbbox() is not None:
                  dirty_cells.add((cx // _GRID, cy // _GRID))
      if not dirty_cells:
          return []
      visited: set = set()
      regions: list[dict] = []
      for cell in sorted(dirty_cells):
          if cell in visited:
              continue
          component = _flood_fill(cell, dirty_cells, visited)
          min_cx = min(c[0] for c in component) * _GRID
          min_cy = min(c[1] for c in component) * _GRID
          max_cx = min((max(c[0] for c in component) + 1) * _GRID, width)
          max_cy = min((max(c[1] for c in component) + 1) * _GRID, height)
          block = mask.crop((min_cx, min_cy, max_cx, max_cy))
          bbox = block.getbbox()
          if bbox is None:
              continue
          bx0, by0, bx1, by1 = bbox
          regions.append({
              "x": min_cx + bx0,
              "y": min_cy + by0,
              "w": bx1 - bx0,
              "h": by1 - by0,
          })
      return regions


  def _flood_fill(start, dirty_cells, visited):
      stack = [start]
      component = []
      while stack:
          cell = stack.pop()
          if cell in visited or cell not in dirty_cells:
              continue
          visited.add(cell)
          component.append(cell)
          cx, cy = cell
          for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
              neighbor = (cx + dx, cy + dy)
              if neighbor in dirty_cells and neighbor not in visited:
                  stack.append(neighbor)
      return component


  def crop_regions(image_path: Path, regions: list[dict], out_dir: Path,
                    max_edge: int = DEFAULT_MAX_EDGE) -> list[Path]:
      out_dir.mkdir(parents=True, exist_ok=True)
      paths: list[Path] = []
      with Image.open(image_path) as img:
          img = img.convert("RGB")
          width, height = img.size
          for i, region in enumerate(regions):
              pad = 8
              x0 = max(region["x"] - pad, 0)
              y0 = max(region["y"] - pad, 0)
              x1 = min(region["x"] + region["w"] + pad, width)
              y1 = min(region["y"] + region["h"] + pad, height)
              crop = img.crop((x0, y0, x1, y1))
              crop.thumbnail((max_edge, max_edge))
              out_path = out_dir / f"region_{i}.png"
              crop.save(out_path)
              paths.append(out_path)
      return paths
  ```
- [ ] **Step 4: run.** `pytest plugins/flow-review/engine/flow_review/web/test_visual.py -v` → PASS.
- [ ] **Step 5: verify.** `python -m pytest -q` from the repo root → all pass, no new skips.
- [ ] **Step 6: commit.**
  `git add plugins/flow-review/engine/flow_review/web/visual.py plugins/flow-review/engine/flow_review/web/test_visual.py`
  `git commit -m "feat(web): pixel diff with changed-region bounding boxes and crop/downscale"`

---

### Task B6: Network fault injection (offline, 5xx, slow)

**Executor:** sonnet · **Depends:** B1 · **Wave:** 5
**Files:**
- `plugins/flow-review/engine/flow_review/web/faults.py`
- `plugins/flow-review/engine/flow_review/web/test_faults.py`

**Interfaces:**
- Consumes: a live `playwright.sync_api.Page`, reached via a `driver.page` accessor. B1's given
  method list (`goto, click, fill, press, resolve, screenshot, snapshot, console_errors,
  network_log, set_viewport, emulate, storage_state`) does not include a raw page accessor;
  this task assumes `WebDriver.page` exists as a property so fault injection and variant
  handling (B7) can call Playwright's `page.route` directly. Flagged in QUESTIONS.
- Produces:
  ```python
  def match_pattern(url: str, pattern: str) -> bool: ...                 # pure, fnmatch-based
  def inject_offline(page) -> None: ...                                  # page.route("**/*", abort)
  def inject_5xx(page, url_pattern: str) -> None: ...                    # matching routes -> 500
  def inject_slow(page, url_pattern: str, delay_ms: int) -> None: ...    # matching routes delayed
  def clear_faults(page) -> None: ...                                    # page.unroute_all()
  ```

- [ ] **Step 1: failing test.**
  ```python
  # plugins/flow-review/engine/flow_review/web/test_faults.py
  from flow_review.web import faults


  def test_match_pattern_glob():
      assert faults.match_pattern("http://x/api/broken", "**/api/*")
      assert not faults.match_pattern("http://x/other", "**/api/*")


  class FakeRequest:
      def __init__(self, url):
          self.url = url


  class FakeRoute:
      def __init__(self, url):
          self.request = FakeRequest(url)
          self.aborted = False
          self.fulfilled = None
          self.continued = False

      def abort(self):
          self.aborted = True

      def fulfill(self, **kwargs):
          self.fulfilled = kwargs

      def continue_(self):
          self.continued = True


  class FakePage:
      def __init__(self):
          self.handlers = {}
          self.unrouted = False

      def route(self, pattern, handler):
          self.handlers[pattern] = handler

      def unroute_all(self):
          self.unrouted = True


  def test_inject_5xx_fulfills_matching_and_continues_others():
      page = FakePage()
      faults.inject_5xx(page, "**/api/broken")
      handler = page.handlers["**/api/broken"]

      matching = FakeRoute("http://x/api/broken")
      handler(matching)
      assert matching.fulfilled["status"] == 500

      other = FakeRoute("http://x/other")
      handler(other)
      assert other.continued is True
      assert other.fulfilled is None


  def test_inject_offline_aborts_every_request():
      page = FakePage()
      faults.inject_offline(page)
      handler = page.handlers["**/*"]
      route = FakeRoute("http://x/anything")
      handler(route)
      assert route.aborted is True


  def test_inject_slow_delays_then_continues(monkeypatch):
      page = FakePage()
      slept = {}
      monkeypatch.setattr(faults.time, "sleep", lambda s: slept.setdefault("seconds", s))
      faults.inject_slow(page, "**/api/broken", delay_ms=250)
      handler = page.handlers["**/api/broken"]
      route = FakeRoute("http://x/api/broken")
      handler(route)
      assert slept["seconds"] == 0.25
      assert route.continued is True


  def test_clear_faults_calls_unroute_all():
      page = FakePage()
      faults.clear_faults(page)
      assert page.unrouted is True
  ```
- [ ] **Step 2: run.** `pytest plugins/flow-review/engine/flow_review/web/test_faults.py -v` → FAIL.
- [ ] **Step 3: implementation.**
  ```python
  # plugins/flow-review/engine/flow_review/web/faults.py
  import fnmatch
  import time


  def match_pattern(url: str, pattern: str) -> bool:
      return fnmatch.fnmatch(url, pattern)


  def inject_offline(page) -> None:
      def _handler(route):
          route.abort()
      page.route("**/*", _handler)


  def inject_5xx(page, url_pattern: str) -> None:
      def _handler(route):
          if match_pattern(route.request.url, url_pattern):
              route.fulfill(status=500, content_type="text/plain", body="Internal Server Error")
          else:
              route.continue_()
      page.route(url_pattern, _handler)


  def inject_slow(page, url_pattern: str, delay_ms: int) -> None:
      def _handler(route):
          if match_pattern(route.request.url, url_pattern):
              time.sleep(delay_ms / 1000)
          route.continue_()
      page.route(url_pattern, _handler)


  def clear_faults(page) -> None:
      page.unroute_all()
  ```
- [ ] **Step 4: run.** `pytest plugins/flow-review/engine/flow_review/web/test_faults.py -v` → PASS.
- [ ] **Step 5: browser-backed check (`web` marker).**
  ```python
  # appended to plugins/flow-review/engine/flow_review/web/test_faults.py
  import pytest

  pytest.importorskip("playwright")


  @pytest.mark.web
  def test_inject_5xx_overrides_route_live(webapp_server):
      from flow_review.web.driver import WebDriver
      base_url, _ = webapp_server
      d = WebDriver(headless=True)
      d.launch(base_url)
      faults.inject_5xx(d.page, "**/api/broken")
      d.goto("/")
      d.click({"testid": "load-button"})
      assert any(n["status"] == 500 for n in d.network_log())
      d.close()
  ```
  Run: `pytest plugins/flow-review/engine/flow_review/web/test_faults.py -v -m web` (needs
  `python -m playwright install chromium` and the `webapp_server` fixture from B0/B1) → PASS.
- [ ] **Step 6: verify.** `python -m pytest -q -m "not web"` from the repo root → all pass.
- [ ] **Step 7: commit.**
  `git add plugins/flow-review/engine/flow_review/web/faults.py plugins/flow-review/engine/flow_review/web/test_faults.py`
  `git commit -m "feat(web): network fault injection (offline/5xx/slow) via page.route"`

---

### Task B7: Variant runner (viewport, theme, keyboard-only, reduced motion, new/returning)

**Executor:** sonnet · **Depends:** B3 · **Wave:** 8
**Files:**
- `plugins/flow-review/engine/flow_review/web/variants.py`
- `plugins/flow-review/engine/flow_review/web/test_variants.py`

**Interfaces:**
- Consumes: `flow_review.web.actionlog.load`; `flow_review.web.replay.replay_one(driver, log) ->
  ReplayResult`; `flow_review.web.driver.WebDriver`; `Surface.options["viewport"]` (list of
  `{"width","height"}`, per Canonical `WEB_OPTION_KEYS`). This task assumes `ReplayResult`
  carries a `divergences: list[dict]` field (per B3's stated purpose, "per-step divergence
  detection"); flagged in QUESTIONS since B3's exact shape isn't visible here.
- Produces:
  ```python
  class Variant(TypedDict):
      kind: str            # "viewport" | "color-scheme" | "keyboard-only" | "reduced-motion" | "storage-state"
      params: dict          # e.g. {"width":375,"height":812} or {"scheme":"dark"} or {"state":"returning"}

  def plan_variants(surface: "Surface", mode: str) -> list[Variant]: ...
      # pure: expands surface.options["viewport"] + fixed modes into the variant list.
      # mode == "quick" -> [] (A-12: quick is happy-path only, no around-variants).

  def run_variant(driver_factory, base_url: str, log: dict, variant: Variant,
                    storage_state_path: Path | None = None) -> "ReplayResult": ...

  def run_all(driver_factory, base_url: str, log: dict, surface: "Surface",
               storage_state_dir: Path) -> list[tuple[Variant, "ReplayResult"]]: ...
  ```
  `plan_variants` builds: one entry per `surface.options["viewport"]` item (kind `"viewport"`);
  one `color-scheme` entry each for `light`/`dark`; one `keyboard-only` entry; one
  `reduced-motion` entry; two `storage-state` entries (`new` = no storage state file passed,
  `returning` = a `storage_state.json` captured after the flow's first clean run and reused) —
  unless `mode == "quick"`, in which case the list is empty.
  `run_variant`'s `keyboard-only` branch drives every `click` step via `page.keyboard.press`
  instead of `locator.click()`. Per A-18: the Tab cap is `max(20, 2 * focusable_count)`
  (focusable elements counted via a DOM query); the walk stops early once focus cycles back to
  the first focused element; a target never focused within the cap is recorded as an
  `unreachable_control` divergence.

- [ ] **Step 1: failing test, pure half.**
  ```python
  # plugins/flow-review/engine/flow_review/web/test_variants.py
  from flow_review.web import variants


  class _FakeSurface:
      def __init__(self, options):
          self.options = options


  def test_plan_variants_quick_mode_returns_none():
      surface = _FakeSurface({"viewport": [{"width": 375, "height": 812}]})
      assert variants.plan_variants(surface, "quick") == []


  def test_plan_variants_expands_viewport_and_modes():
      surface = _FakeSurface({
          "viewport": [{"width": 375, "height": 812}, {"width": 1280, "height": 800}],
      })
      plan = variants.plan_variants(surface, "full")
      kinds = [v["kind"] for v in plan]
      assert kinds.count("viewport") == 2
      assert kinds.count("color-scheme") == 2
      assert kinds.count("keyboard-only") == 1
      assert kinds.count("reduced-motion") == 1
      assert kinds.count("storage-state") == 2


  def test_plan_variants_goal_and_auto_and_full_all_expand():
      surface = _FakeSurface({"viewport": [{"width": 1280, "height": 800}]})
      for mode in ("goal", "auto", "full"):
          assert len(variants.plan_variants(surface, mode)) == 6
  ```
- [ ] **Step 2: run.** `pytest plugins/flow-review/engine/flow_review/web/test_variants.py -v` → FAIL.
- [ ] **Step 3: implementation.**
  ```python
  # plugins/flow-review/engine/flow_review/web/variants.py
  from __future__ import annotations

  from pathlib import Path
  from typing import Any, Callable, TypedDict

  from flow_review.web import actionlog
  from flow_review.web.replay import replay_one

  _FOCUSABLE_JS = """
  () => {
    const sel = 'a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])';
    return Array.from(document.querySelectorAll(sel)).filter(
      el => !el.disabled && el.offsetParent !== null
    ).length;
  }
  """

  _ACTIVE_ELEMENT_JS = """
  () => {
    const el = document.activeElement;
    if (!el) return null;
    return el.outerHTML.slice(0, 200);
  }
  """


  class Variant(TypedDict):
      kind: str
      params: dict


  def plan_variants(surface: Any, mode: str) -> list[Variant]:
      if mode == "quick":
          return []
      variants_out: list[Variant] = []
      options = getattr(surface, "options", None) or {}
      for vp in options.get("viewport", []):
          variants_out.append({
              "kind": "viewport",
              "params": {"width": vp["width"], "height": vp["height"]},
          })
      for scheme in ("light", "dark"):
          variants_out.append({"kind": "color-scheme", "params": {"scheme": scheme}})
      variants_out.append({"kind": "keyboard-only", "params": {}})
      variants_out.append({"kind": "reduced-motion", "params": {}})
      variants_out.append({"kind": "storage-state", "params": {"state": "new"}})
      variants_out.append({"kind": "storage-state", "params": {"state": "returning"}})
      return variants_out


  def run_variant(driver_factory: Callable[..., Any], base_url: str, log: dict,
                   variant: Variant, storage_state_path: Path | None = None):
      kind = variant["kind"]
      kwargs: dict = {}
      if kind == "viewport":
          kwargs["viewport"] = {
              "width": variant["params"]["width"],
              "height": variant["params"]["height"],
          }
      elif kind == "color-scheme":
          kwargs["color_scheme"] = variant["params"]["scheme"]
      elif kind == "reduced-motion":
          kwargs["reduced_motion"] = "reduce"
      elif kind == "storage-state":
          if (variant["params"]["state"] == "returning"
                  and storage_state_path is not None and storage_state_path.exists()):
              kwargs["storage_state"] = str(storage_state_path)

      driver = driver_factory(**kwargs)
      driver.launch(base_url)
      try:
          if kind == "keyboard-only":
              return _replay_keyboard_only(driver, log)
          return replay_one(driver, log)
      finally:
          if (kind == "storage-state" and variant["params"]["state"] == "new"
                  and storage_state_path is not None):
              storage_state_path.parent.mkdir(parents=True, exist_ok=True)
              storage_state_path.write_text(driver.storage_state())
          driver.close()


  def _replay_keyboard_only(driver: Any, log: dict):
      page = driver.page
      focusable_count = page.evaluate(_FOCUSABLE_JS)
      tab_cap = max(20, 2 * focusable_count)
      unreachable: list[str] = []
      for step in log.get("steps", []):
          if step.get("action") != "click":
              continue
          target = step.get("locator", {})
          found = False
          first_html = None
          for _ in range(tab_cap):
              page.keyboard.press("Tab")
              html = page.evaluate(_ACTIVE_ELEMENT_JS)
              if first_html is None:
                  first_html = html
              elif html == first_html:
                  break
              if target.get("testid") and target["testid"] in (html or ""):
                  found = True
                  break
              if target.get("name") and target["name"] in (html or ""):
                  found = True
                  break
          if found:
              page.keyboard.press("Enter")
          else:
              # WCAG 2.1.1 (Level A): an engine finding, filed directly (spec §7.1).
              unreachable.append({
                  "surface_id": log.get("surface_id", ""), "flow_id": log.get("flow_id", ""),
                  "rule": "a11y.keyboard-unreachable", "route": step.get("url") or "",
                  "locator": actionlog.locator_key(target), "sev": "P1",
                  "text": f"not reachable by Tab within {tab_cap} presses",
                  "evidence": [], "disposition": "engine",
              })
      return {  # B3's ReplayResult shape
          "flow_id": log.get("flow_id", ""),
          "status": "regression" if unreachable else "clean",
          "steps_run": len(log.get("steps", [])),
          "divergence": None,
          "findings": unreachable,
      }


  def run_all(driver_factory: Callable[..., Any], base_url: str, log: dict, surface: Any,
              storage_state_dir: Path) -> list[tuple[Variant, Any]]:
      results = []
      for variant in plan_variants(surface, "full"):
          storage_state_path = (
              storage_state_dir / "storage_state.json"
              if variant["kind"] == "storage-state" else None
          )
          result = run_variant(driver_factory, base_url, log, variant,
                                storage_state_path=storage_state_path)
          results.append((variant, result))
      return results
  ```
- [ ] **Step 4: run.** `pytest plugins/flow-review/engine/flow_review/web/test_variants.py -v` → PASS.
- [ ] **Step 5: browser-backed check (`web` marker).**
  ```python
  # appended to plugins/flow-review/engine/flow_review/web/test_variants.py
  import pytest

  pytest.importorskip("playwright")


  @pytest.mark.web
  def test_run_variant_keyboard_only_reaches_load_button(webapp_server, tmp_path):
      from flow_review.web.driver import WebDriver
      base_url, _ = webapp_server
      log = {"steps": [{"action": "click", "locator": {"testid": "load-button"}}]}
      result = variants.run_variant(
          lambda **kw: WebDriver(headless=True, **kw), base_url, log,
          {"kind": "keyboard-only", "params": {}},
      )
      assert result["findings"] == [] and result["status"] == "clean"
  ```
  Run: `pytest plugins/flow-review/engine/flow_review/web/test_variants.py -v -m web` → PASS.
- [ ] **Step 6: verify.** `python -m pytest -q -m "not web"` from the repo root → all pass.
- [ ] **Step 7: commit.**
  `git add plugins/flow-review/engine/flow_review/web/variants.py plugins/flow-review/engine/flow_review/web/test_variants.py`
  `git commit -m "feat(web): variant runner (viewport/theme/keyboard/reduced-motion/storage-state)"`

---

### Task B8: Budget — priors, usage log, history medians, cap gate

**Executor:** sonnet · **Depends:** A5 · **Wave:** 4
**Files:**
- `plugins/flow-review/engine/flow_review/budget.py`
- `plugins/flow-review/engine/flow_review/test_budget.py`
- `plugins/flow-review/engine/flow_review/cli.py` (edit — add `budget check` subcommand)

**Interfaces:**
- Consumes: `flow_review.events.append(run_dir: Path, event: dict) -> dict` (fills `ts`/`id`,
  applies `redact()`, JSON-safe). This task assumes `events.append` writes newline-delimited
  JSON to `<run_dir>/events.jsonl`, since that filename isn't given in the Canonical Interfaces
  list; flagged in QUESTIONS.
- Produces (matches the Canonical Budget bullet exactly):
  ```python
  # Per-role, per-unit token priors (propose; calibrate from real runs, A-7/A-19).
  # One unit = ONE subagent dispatch (the usage Claude Code reports per Agent result, cache
  # reads included). Priors seeded from the 2026-09-23 planning session: a single-turn, no-tool
  # Sonnet subagent reported ~47k tokens; tool-heavy drafters 90-300k. Priors only -- replaced
  # by per-surface medians after 3 runs (A-7); recalibrated by the M5 benchmark.
  PRIORS_TOKENS_PER_UNIT = {
      "explorer": 150_000,      # per goal explored (multi-step drive session)
      "replay-repair": 60_000,  # per divergence repaired
      "lens": 50_000,           # per screen, one call (evidence bundle first)
      "cold-eyes": 120_000,     # per cold-eyes pass over one surface
      "triage": 50_000,         # per triage batch
      "verifier": 60_000,       # per P0/P1 judgment finding
  }

  class PlanUnit(TypedDict):
      surface_id: str
      role: str
      count: int

  def record_usage(run_dir: Path, surface_id: str, role: str, tokens: int) -> dict: ...
      # events.append(run_dir, {"type": "usage", "surface": surface_id, "role": role, "tokens": tokens})

  def used(run_dir: Path) -> int: ...
      # sums the tokens of every "usage" event under run_dir

  def fold_history(project_root: Path, run_dir: Path) -> Path: ...
      # appends run_dir's usage events, grouped by surface/role, to
      # <project_root>/.flow-review/usage_history.json; returns that path

  def estimate(plan_units: list[PlanUnit], project_root: Path) -> dict[str, int]: ...
      # -> {surface_id: total_estimated_tokens}; per surface+role, uses the median of
      #    history[surface]["runs"][*]["roles"][role]["tokens"] once that surface has
      #    >= 3 recorded runs (A-7), else PRIORS_TOKENS_PER_UNIT[role]

  def check(project_root: Path, run_dir: Path, next_role: str, cap_tokens: int | None) -> int: ...
      # 0 if cap_tokens is None or used(run_dir) + PRIORS_TOKENS_PER_UNIT[next_role] <= cap_tokens,
      # else 1. Engine work (replay/measure) never calls this -- only LLM-role dispatch does.
  ```
  `usage_history.json` shape:
  ```json
  {
    "webapp": {
      "runs": [
        {"run_id": "run-20260923-1", "roles": {"lens": {"count": 3, "tokens": [2000, 2100, 2050]}}}
      ]
    }
  }
  ```
  CLI: `flow-review budget check --run DIR --next ROLE --surface ID` loads `cfg.budget["cap_tokens"]`
  and the project root, then `sys.exit(budget.check(project_root, DIR, ROLE, cap))`. `--surface`
  is accepted (matches the required CLI shape) but not used inside `check()` itself, since the
  Canonical Budget bullet's cap test (`used + prior(ROLE) > cap`) has no per-surface term.

- [ ] **Step 1: failing test.**
  ```python
  # plugins/flow-review/engine/flow_review/test_budget.py
  from flow_review import budget


  def test_record_usage_and_used(tmp_path):
      run_dir = tmp_path / "run1"
      run_dir.mkdir()
      budget.record_usage(run_dir, "webapp", "lens", 2000)
      budget.record_usage(run_dir, "webapp", "verifier", 3500)
      assert budget.used(run_dir) == 5500


  def test_check_exits_nonzero_when_cap_would_be_exceeded(tmp_path):
      run_dir = tmp_path / "run1"
      run_dir.mkdir()
      budget.record_usage(run_dir, "webapp", "lens", 9000)
      assert budget.check(tmp_path, run_dir, next_role="verifier", cap_tokens=10000) == 1
      assert budget.check(tmp_path, run_dir, next_role="verifier", cap_tokens=None) == 0
      exact_fit = 9000 + budget.PRIORS_TOKENS_PER_UNIT["verifier"]
      assert budget.check(tmp_path, run_dir, next_role="verifier", cap_tokens=exact_fit) == 0


  def test_estimate_uses_priors_with_no_history(tmp_path):
      plan_units = [
          {"surface_id": "webapp", "role": "explorer", "count": 4},
          {"surface_id": "webapp", "role": "lens", "count": 4},
      ]
      est = budget.estimate(plan_units, tmp_path)
      expected = 4 * budget.PRIORS_TOKENS_PER_UNIT["explorer"] + 4 * budget.PRIORS_TOKENS_PER_UNIT["lens"]
      assert est["webapp"] == expected


  def test_fold_history_writes_usage_history_json(tmp_path):
      run_dir = tmp_path / "run1"
      run_dir.mkdir()
      budget.record_usage(run_dir, "webapp", "lens", 2000)
      budget.record_usage(run_dir, "webapp", "lens", 2200)
      history_path = budget.fold_history(tmp_path, run_dir)
      assert history_path == tmp_path / ".flow-review" / "usage_history.json"
      import json
      history = json.loads(history_path.read_text())
      assert history["webapp"]["runs"][0]["roles"]["lens"]["tokens"] == [2000, 2200]
      assert history["webapp"]["runs"][0]["roles"]["lens"]["count"] == 2


  def test_estimate_uses_history_median_after_three_runs(tmp_path):
      for i in range(3):
          run_dir = tmp_path / f"run{i}"
          run_dir.mkdir()
          budget.record_usage(run_dir, "webapp", "lens", 2000 + i * 100)
          budget.fold_history(tmp_path, run_dir)
      plan_units = [{"surface_id": "webapp", "role": "lens", "count": 2}]
      est = budget.estimate(plan_units, tmp_path)
      assert est["webapp"] == 2 * 2100
  ```
- [ ] **Step 2: run.** `pytest plugins/flow-review/engine/flow_review/test_budget.py -v` → FAIL.
- [ ] **Step 3: implementation.**
  ```python
  # plugins/flow-review/engine/flow_review/budget.py
  from __future__ import annotations

  import json
  import statistics
  from pathlib import Path
  from typing import TypedDict

  from flow_review import events

  EVENTS_FILENAME = "events.jsonl"

  # One unit = ONE subagent dispatch (the usage Claude Code reports per Agent result, cache
  # reads included). Priors seeded from the 2026-09-23 planning session: a single-turn, no-tool
  # Sonnet subagent reported ~47k tokens; tool-heavy drafters 90-300k. Priors only -- replaced
  # by per-surface medians after 3 runs (A-7); recalibrated by the M5 benchmark.
  PRIORS_TOKENS_PER_UNIT = {
      "explorer": 150_000,      # per goal explored (multi-step drive session)
      "replay-repair": 60_000,  # per divergence repaired
      "lens": 50_000,           # per screen, one call (evidence bundle first)
      "cold-eyes": 120_000,     # per cold-eyes pass over one surface
      "triage": 50_000,         # per triage batch
      "verifier": 60_000,       # per P0/P1 judgment finding
  }


  class PlanUnit(TypedDict):
      surface_id: str
      role: str
      count: int


  def record_usage(run_dir: Path, surface_id: str, role: str, tokens: int) -> dict:
      return events.append(run_dir, {
          "type": "usage",
          "surface": surface_id,
          "role": role,
          "tokens": tokens,
      })


  def used(run_dir: Path) -> int:
      log_path = run_dir / EVENTS_FILENAME
      if not log_path.exists():
          return 0
      total = 0
      for line in log_path.read_text().splitlines():
          if not line.strip():
              continue
          record = json.loads(line)
          if record.get("type") == "usage":
              total += record.get("tokens", 0)
      return total


  def fold_history(project_root: Path, run_dir: Path) -> Path:
      history_path = project_root / ".flow-review" / "usage_history.json"
      history_path.parent.mkdir(parents=True, exist_ok=True)
      history: dict = {}
      if history_path.exists():
          history = json.loads(history_path.read_text())

      per_surface_roles: dict[str, dict[str, list[int]]] = {}
      log_path = run_dir / EVENTS_FILENAME
      if log_path.exists():
          for line in log_path.read_text().splitlines():
              if not line.strip():
                  continue
              record = json.loads(line)
              if record.get("type") != "usage":
                  continue
              surface_id = record["surface"]
              role = record["role"]
              tokens = record["tokens"]
              per_surface_roles.setdefault(surface_id, {}).setdefault(role, []).append(tokens)

      for surface_id, roles in per_surface_roles.items():
          surface_history = history.setdefault(surface_id, {"runs": []})
          surface_history["runs"].append({
              "run_id": run_dir.name,
              "roles": {
                  role: {"count": len(tok_list), "tokens": tok_list}
                  for role, tok_list in roles.items()
              },
          })

      history_path.write_text(json.dumps(history, indent=2))
      return history_path


  def _prior(role: str) -> int:
      return PRIORS_TOKENS_PER_UNIT.get(role, 0)


  def _load_history(project_root: Path) -> dict:
      history_path = project_root / ".flow-review" / "usage_history.json"
      if not history_path.exists():
          return {}
      return json.loads(history_path.read_text())


  def _per_unit_estimate(surface_id: str, role: str, project_root: Path) -> int:
      history = _load_history(project_root)
      runs = history.get(surface_id, {}).get("runs", [])
      if len(runs) < 3:
          return _prior(role)
      all_tokens: list[int] = []
      for run in runs:
          role_data = run.get("roles", {}).get(role)
          if role_data:
              all_tokens.extend(role_data["tokens"])
      if not all_tokens:
          return _prior(role)
      return int(statistics.median(all_tokens))


  def role_unit_counts(surface_id: str, role: str, project_root: Path) -> list[int]:
      """Per-run unit counts for a role; used by plan.py's A-19 median refinement."""
      history = _load_history(project_root)
      runs = history.get(surface_id, {}).get("runs", [])
      counts = []
      for run in runs:
          role_data = run.get("roles", {}).get(role)
          if role_data:
              counts.append(role_data["count"])
      return counts


  def estimate(plan_units: list[PlanUnit], project_root: Path) -> dict[str, int]:
      totals: dict[str, int] = {}
      for unit in plan_units:
          surface_id = unit["surface_id"]
          role = unit["role"]
          count = unit["count"]
          per_unit = _per_unit_estimate(surface_id, role, project_root)
          totals[surface_id] = totals.get(surface_id, 0) + per_unit * count
      return totals


  def check(project_root: Path, run_dir: Path, next_role: str, cap_tokens: int | None) -> int:
      if cap_tokens is None:
          return 0
      projected = used(run_dir) + _prior(next_role)
      return 1 if projected > cap_tokens else 0
  ```
  CLI edit (`cli.py`):
  ```python
  # in build_parser()
  budget_parser = subparsers.add_parser("budget")
  budget_sub = budget_parser.add_subparsers(dest="budget_cmd", required=True)
  check_parser = budget_sub.add_parser("check")
  check_parser.add_argument("--run", required=True, type=Path)
  check_parser.add_argument("--next", required=True, dest="next_role")
  check_parser.add_argument("--surface", required=True)
  check_parser.add_argument("--project", type=Path, default=None)

  # in dispatch
  elif args.command == "budget" and args.budget_cmd == "check":
      project_root = args.project_root  # set by A1's _resolve_project_root before dispatch
      cfg = config.load(project_root / ".flow-review" / "config.json")
      cap = cfg.budget.get("cap_tokens")
      sys.exit(budget.check(project_root, args.run, args.next_role, cap))
  ```
- [ ] **Step 4: run.** `pytest plugins/flow-review/engine/flow_review/test_budget.py -v` → PASS.
- [ ] **Step 5: verify.** `python -m pytest -q` from the repo root → all pass.
- [ ] **Step 6: commit.**
  `git add plugins/flow-review/engine/flow_review/budget.py plugins/flow-review/engine/flow_review/test_budget.py plugins/flow-review/engine/flow_review/cli.py`
  `git commit -m "feat: budget priors, usage log, history medians, cap gate (A-7)"`

---

### Task B9: GO-gate plan — `flow-review plan`

**Executor:** sonnet · **Depends:** B8, A7, A10 · **Wave:** 5
**Files:**
- `plugins/flow-review/engine/flow_review/plan.py`
- `plugins/flow-review/engine/flow_review/test_plan.py`
- `plugins/flow-review/engine/flow_review/cli.py` (edit — add `plan` subcommand)

**Interfaces:**
- Consumes: `flow_review.config.load`, `Config.surfaces`, `Surface.creds` (dict
  `{logical: ENV_NAME}`), `.record`, `.state`; `flow_review.drift.runnable_surfaces(cfg) ->
  list[Surface]`; `flow_review.budget.estimate`, `budget.role_unit_counts`,
  `budget.PRIORS_TOKENS_PER_UNIT`; `flow_review.envsetup.load_dotenv(path, environ=None)` (used
  against a private dict copy of `os.environ`, so credential-gap checking never mutates or
  prints real process env, and secret values themselves never appear in `plan()`'s output —
  only env-var *names*).
- Produces:
  ```python
  def plan(project_root: Path, mode: str, goal: str | None = None,
            record: bool = False, skip: list[str] | None = None) -> dict: ...
  ```
  `mode` is one of `goal|auto|full|quick` (A-12); `goal` is required for `goal`/`quick`, absent
  for `auto`/`full`. `skip` removes surface ids from `drift.runnable_surfaces(cfg)` before
  planning. Per-mode unit-count templates are priors (`UNIT_TEMPLATES` below), replaced per
  role by the surface's median actual count from `usage_history.json` once that surface has
  `>= 3` runs (A-19, via `budget.role_unit_counts`). `plan()` is pure data and never prompts —
  the SKILL/CLI layer is what asks the user about gaps.

  Output JSON (`flow-review plan --mode goal --goal "checkout" --json`):
  ```json
  {
    "schema_version": 1,
    "mode": "goal",
    "goal": "checkout",
    "record": false,
    "surfaces": [
      {
        "surface_id": "webapp",
        "units": [
          {"role": "explorer", "count": 1},
          {"role": "lens", "count": 3},
          {"role": "verifier", "count": 1}
        ],
        "estimate_tokens": 10500,
        "gaps": [
          {"type": "missing_creds", "name": "WEBAPP_PASSWORD", "offer_save": true}
        ]
      }
    ],
    "skipped_surfaces": [],
    "gaps": [
      {"type": "destructive_optin", "surfaces": ["webapp"], "opt_in_default": false}
    ],
    "total_estimate_tokens": 10500
  }
  ```
  `missing_creds` is a per-surface gap: one entry per `Surface.creds` value whose named env var
  is absent from both `os.environ` and `<project_root>/.flow-review/.env`, each with
  `"offer_save": true`. `destructive_optin` is a single top-level gap (not per-surface) listing
  every runnable surface with `state == "persistent"`, present in **every** mode including
  `quick`, `"opt_in_default": false`, omitted only when no persistent surface is runnable.

  CLI wiring (`cli.py`):
  ```python
  # in build_parser()
  plan_parser = subparsers.add_parser("plan")
  plan_parser.add_argument("--mode", required=True, choices=["goal", "auto", "full", "quick"])
  plan_parser.add_argument("--goal")
  plan_parser.add_argument("--record", action="store_true")
  plan_parser.add_argument("--skip", action="append", default=[])
  plan_parser.add_argument("--json", action="store_true")  # M1 always prints JSON; flag kept
  plan_parser.add_argument("--project", type=Path, default=None)  # forward compat, see QUESTIONS

  # in dispatch
  elif args.command == "plan":
      import json as _json
      project_root = args.project_root  # set by A1's _resolve_project_root before dispatch
      result = plan_mod.plan(project_root, mode=args.mode, goal=args.goal,
                              record=args.record, skip=args.skip)
      print(_json.dumps(result))
  ```

- [ ] **Step 1: failing test.**
  ```python
  # plugins/flow-review/engine/flow_review/test_plan.py
  import json

  from flow_review import plan as plan_mod


  def _write_project(tmp_path, creds=None, state="disposable"):
      fr_dir = tmp_path / ".flow-review"
      fr_dir.mkdir()
      cfg = {
          "schema_version": 2,
          "generator_version": "2.0.0",
          "surfaces": [
              {
                  "id": "webapp", "name": "webapp", "kind": "web", "driver": "web",
                  "launch": "npm run dev", "cwd": ".", "env": {},
                  "options": {
                      "base_url": "http://127.0.0.1:9", "health_path": "/",
                      "ready_timeout_s": 5,
                      "viewport": [{"width": 375, "height": 812}],
                  },
                  "preconditions": [], "state": state, "reset": None,
                  "creds": creds or {}, "record": False, "provenance": {}, "declined": False,
              }
          ],
          "model_profile": "default", "role_overrides": {},
          "budget": {"cap_tokens": None}, "test_inbox": None, "flows_hash": "",
      }
      (fr_dir / "config.json").write_text(json.dumps(cfg))
      return tmp_path


  def test_plan_goal_mode_reports_missing_creds_gap(tmp_path, monkeypatch):
      monkeypatch.delenv("WEBAPP_PASSWORD", raising=False)
      project_root = _write_project(tmp_path, creds={"password": "WEBAPP_PASSWORD"})
      result = plan_mod.plan(project_root, mode="goal", goal="checkout")
      surf = result["surfaces"][0]
      assert any(g["type"] == "missing_creds" and g["name"] == "WEBAPP_PASSWORD" for g in surf["gaps"])
      assert result["total_estimate_tokens"] == surf["estimate_tokens"]


  def test_plan_skip_removes_surface(tmp_path, monkeypatch):
      monkeypatch.setenv("WEBAPP_PASSWORD", "x")
      project_root = _write_project(tmp_path, creds={"password": "WEBAPP_PASSWORD"})
      result = plan_mod.plan(project_root, mode="auto", skip=["webapp"])
      assert result["surfaces"] == []
      assert result["skipped_surfaces"] == ["webapp"]


  def test_plan_persistent_surface_gets_one_destructive_optin_gap(tmp_path, monkeypatch):
      monkeypatch.setenv("WEBAPP_PASSWORD", "x")
      project_root = _write_project(tmp_path, creds={"password": "WEBAPP_PASSWORD"}, state="persistent")
      result = plan_mod.plan(project_root, mode="full")
      assert len(result["gaps"]) == 1
      gap = result["gaps"][0]
      assert gap["type"] == "destructive_optin"
      assert gap["surfaces"] == ["webapp"]
      assert gap["opt_in_default"] is False


  def test_plan_quick_mode_has_no_lens_units(tmp_path, monkeypatch):
      monkeypatch.setenv("WEBAPP_PASSWORD", "x")
      project_root = _write_project(tmp_path, creds={"password": "WEBAPP_PASSWORD"})
      result = plan_mod.plan(project_root, mode="quick", goal="sign in")
      surf = result["surfaces"][0]
      roles = {u["role"] for u in surf["units"]}
      assert "lens" not in roles


  def test_plan_destructive_optin_present_in_quick_mode_too(tmp_path, monkeypatch):
      monkeypatch.setenv("WEBAPP_PASSWORD", "x")
      project_root = _write_project(tmp_path, creds={"password": "WEBAPP_PASSWORD"}, state="persistent")
      result = plan_mod.plan(project_root, mode="quick", goal="sign in")
      assert any(g["type"] == "destructive_optin" for g in result["gaps"])


  def test_plan_no_persistent_surfaces_omits_destructive_gap(tmp_path, monkeypatch):
      monkeypatch.setenv("WEBAPP_PASSWORD", "x")
      project_root = _write_project(tmp_path, creds={"password": "WEBAPP_PASSWORD"})
      result = plan_mod.plan(project_root, mode="full")
      assert result["gaps"] == []
  ```
- [ ] **Step 2: run.** `pytest plugins/flow-review/engine/flow_review/test_plan.py -v` → FAIL.
- [ ] **Step 3: implementation.**
  ```python
  # plugins/flow-review/engine/flow_review/plan.py
  from __future__ import annotations

  import os
  import statistics
  from pathlib import Path

  from flow_review import budget, config, drift, envsetup

  UNIT_TEMPLATES = {
      "quick": {"explorer": 1, "verifier": 1},
      "goal": {"explorer": 1, "lens": 3, "verifier": 1},
      "auto": {"explorer": 2, "cold-eyes": 1, "lens": 3, "verifier": 1},
      "full": {"explorer": 3, "cold-eyes": 1, "lens": 6, "verifier": 2},
  }


  def _unit_counts_for(surface_id: str, mode: str, project_root: Path) -> dict[str, int]:
      template = dict(UNIT_TEMPLATES[mode])
      for role in list(template.keys()):
          counts = budget.role_unit_counts(surface_id, role, project_root)
          if len(counts) >= 3:
              template[role] = int(statistics.median(counts))
      return template


  def plan(project_root: Path, mode: str, goal: str | None = None,
           record: bool = False, skip: list[str] | None = None) -> dict:
      if mode not in UNIT_TEMPLATES:
          raise ValueError(f"unknown mode: {mode!r}")
      if mode in ("goal", "quick") and not goal:
          raise ValueError(f"--goal is required for mode {mode!r}")

      cfg = config.load(project_root / ".flow-review" / "config.json")
      runnable = drift.runnable_surfaces(cfg)
      skip = skip or []
      skipped = [s.id for s in runnable if s.id in skip]
      runnable = [s for s in runnable if s.id not in skip]

      dotenv_path = project_root / ".flow-review" / ".env"
      combined_env = dict(os.environ)
      if dotenv_path.exists():
          envsetup.load_dotenv(dotenv_path, environ=combined_env)

      surfaces_out = []
      persistent_ids = []
      total_tokens = 0
      for surface in runnable:
          if surface.state == "persistent":
              persistent_ids.append(surface.id)

          counts = _unit_counts_for(surface.id, mode, project_root)
          units = [{"role": role, "count": count} for role, count in counts.items() if count > 0]
          plan_units = [
              {"surface_id": surface.id, "role": u["role"], "count": u["count"]}
              for u in units
          ]
          estimate_map = budget.estimate(plan_units, project_root)
          estimate_tokens = estimate_map.get(surface.id, 0)
          total_tokens += estimate_tokens

          gaps = []
          for _logical, env_name in (surface.creds or {}).items():
              if env_name not in combined_env:
                  gaps.append({"type": "missing_creds", "name": env_name, "offer_save": True})

          surfaces_out.append({
              "surface_id": surface.id,
              "units": units,
              "estimate_tokens": estimate_tokens,
              "gaps": gaps,
          })

      top_gaps = []
      if persistent_ids:
          top_gaps.append({
              "type": "destructive_optin",
              "surfaces": persistent_ids,
              "opt_in_default": False,
          })

      return {
          "schema_version": 1,
          "mode": mode,
          "goal": goal,
          "record": record,
          "surfaces": surfaces_out,
          "skipped_surfaces": skipped,
          "gaps": top_gaps,
          "total_estimate_tokens": total_tokens,
      }
  ```
  (CLI wiring is shown in the Interfaces block above.)
- [ ] **Step 4: run.** `pytest plugins/flow-review/engine/flow_review/test_plan.py -v` → PASS.
- [ ] **Step 5: verify.** `python -m pytest -q` from the repo root → all pass.
- [ ] **Step 6: commit.**
  `git add plugins/flow-review/engine/flow_review/plan.py plugins/flow-review/engine/flow_review/test_plan.py plugins/flow-review/engine/flow_review/cli.py`
  `git commit -m "feat: GO-gate plan (flow-review plan --mode goal|auto|full|quick, A-19/A-20)"`


---

### Task B10: Drive CLI for agents — localhost session server, DriveSession, thin client

**Executor:** opus · **Depends:** B1, B2, B4, A4 · **Wave:** 7
**Files:**
- `plugins/flow-review/engine/flow_review/web/drive.py` (new)
- `plugins/flow-review/engine/flow_review/web/test_drive.py` (new)
- `plugins/flow-review/engine/flow_review/web/driver.py` (modify — B1 addendum, `is_password`)
- `plugins/flow-review/engine/flow_review/web/test_driver.py` (modify — test for `is_password`)
- `plugins/flow-review/engine/flow_review/cli.py` (modify — wire the `drive` verb)
- `plugins/flow-review/engine/flow_review/test_cli.py` (modify — `drive` dispatch test)

**Interfaces:**
- Consumes: `flow_review.web.driver.WebDriver` (B1, incl. `.page`, `begin_step`/`end_step`,
  `screenshot`, `snapshot`, `console_errors`, `network_log`, `close`, and the `is_password`
  addendum below), `flow_review.web.actionlog.new_log`/`record_step`/`save`/`locator_key` (B2),
  `flow_review.web.measure.check_page` (B4 — the single entry point; **B10 never composes**
  `check_contrast`/`check_tokens`/`check_rects`/`check_http_status`/`check_console` itself),
  `flow_review.events.append`/`register_secret`/`REDACTED` (A4), `flow_review.config.load`
  (A2, already merged by wave 2, for `cmd_start`'s surface lookup).
- Produces — matches the Canonical Interfaces **Drive** bullet exactly:
  ```python
  from pathlib import Path

  class DriveSession:
      def __init__(self, driver, surface_id: str, run_dir: Path, project_root: Path,
                   record_enabled: bool, tokens: dict | None = None): ...
      def flow_begin(self, flow_id: str) -> dict: ...
      def flow_end(self, flow_id: str, status: str) -> dict: ...        # "ok" | "blocked"
      def goto(self, path: str) -> dict: ...
      def click(self, locator: dict) -> dict: ...
      def fill(self, locator: dict, text: str | None = None, from_env: str | None = None) -> dict: ...
      def press(self, key: str) -> dict: ...
      def look(self, shot: bool = False) -> dict: ...
      # every verb returns {"url", "title", "snapshot" (<=4000 chars), "shot" (path or None),
      # "new_findings": [ids], "console_errors": int} — the compact JSON result

  def serve(surface_id: str, run_dir: Path, project_root: Path, base_url: str, *,
            record_enabled: bool = False, headless: bool = True, viewport: dict | None = None,
            tokens: dict | None = None, driver_factory=...) -> None: ...
  # binds http.server.HTTPServer(("127.0.0.1", 0), ...), writes
  # <run_dir>/drive/<surface_id>.json = {"port": N, "pid": os.getpid()}, then serve_forever()

  def build_drive_parser() -> "argparse.ArgumentParser": ...
  def main(argv: list[str] | None = None, project_root: Path | None = None) -> int: ...
  # `python -m flow_review.web.drive <verb> ...` entry point (also called by cli.py's `drive` verb)
  ```
  **B1 addendum** (append to `driver.py`; B1 is otherwise final — this is the one post-hoc change
  the Drive bullet requires, "ask the driver whether the target is `input[type=password]`"):
  ```python
  # plugins/flow-review/engine/flow_review/web/driver.py — add to class WebDriver
  def is_password(self, locator: dict) -> bool:
      try:
          loc = self.resolve(locator)
      except LocatorNotFound:
          return False
      return bool(loc.evaluate("el => el.tagName === 'INPUT' && el.type === 'password'"))
  ```
  **Tokens**: loaded once, at `start`, from `surface.options.get("tokens_file")` — read with `measure.load_tokens` (.css/.scss custom properties or .json, A-25)
  (`None` when the key is absent or the surface has none) — and threaded into `DriveSession` as
  `tokens`, passed unchanged into every `measure.check_page(...)` call. B10 never re-reads it
  per-action.
  **Step window / severity**: `DriveSession` passes the integer `step_index` it just opened via
  `driver.begin_step`/`end_step` for `goto`/`click`/`fill`/`press` (a user action), and `None`
  for `look` (a background observation, not a user action) — `check_page` uses this exactly like
  B4's `check_console` step-window rule (A-17): `step_index is not None` → the console-error path
  is P1, else P2.
  **Route**: always `driver.page.url` at the moment the check runs (fall back to `"/"` before the
  first `goto`).

- [ ] **Step 1: failing test — B1 addendum, `is_password`.**
  ```python
  # appended to plugins/flow-review/engine/flow_review/web/test_driver.py
  @pytest.mark.web
  def test_is_password_detects_password_input_and_false_for_others(webapp_server):
      base_url, _ = webapp_server
      d = WebDriver(headless=True)
      d.launch(base_url)
      d.goto("/")
      assert d.is_password({"testid": "pw-input"}) is True
      assert d.is_password({"testid": "load-button"}) is False
      d.close()


  @pytest.mark.web
  def test_is_password_false_for_unresolvable_locator(webapp_server):
      base_url, _ = webapp_server
      d = WebDriver(headless=True)
      d.launch(base_url)
      d.goto("/")
      assert d.is_password({"testid": "does-not-exist"}) is False
      d.close()
  ```
- [ ] **Step 2: run, expect FAIL.**
  `pytest plugins/flow-review/engine/flow_review/web/test_driver.py -m web -k is_password -x`
  Expected: `AttributeError: 'WebDriver' object has no attribute 'is_password'`.
- [ ] **Step 3: implementation.** Add the `is_password` method shown in the B1 addendum above to
  `WebDriver` in `driver.py` (after `snapshot`, before `console_errors`).
- [ ] **Step 4: run, expect PASS.**
  `pytest plugins/flow-review/engine/flow_review/web/test_driver.py -m web -k is_password -v`

- [ ] **Step 5: failing test — `DriveSession`, pure logic, FAKE driver, no browser.**
  ```python
  # plugins/flow-review/engine/flow_review/web/test_drive.py
  import argparse
  import json
  import os
  import threading
  import time
  from pathlib import Path

  import pytest

  from flow_review import events
  from flow_review.web import actionlog, drive
  from flow_review.web.drive import DriveSession


  class FakePage:
      def __init__(self):
          self.url = "http://fake/"
          self.keyboard = self

      def press(self, key):
          self.pressed = key

      def title(self):
          return "Fake Page"


  class FakeDriver:
      def __init__(self):
          self.page = FakePage()
          self.closed = False
          self.clicked = []
          self.filled = []
          self._shots = []

      def goto(self, path):
          self.page.url = "http://fake" + path

      def click(self, locator):
          self.clicked.append(locator)

      def fill(self, locator, value):
          self.filled.append((locator, value))

      def is_password(self, locator):
          return locator.get("testid") == "pw-input"

      def snapshot(self):
          return {"role": "WebArea", "name": "Fake"}

      def console_errors(self):
          return []

      def network_log(self):
          return []

      def begin_step(self, step_index):
          self._step = step_index

      def end_step(self):
          self._step = None

      def screenshot(self, path):
          Path(path).parent.mkdir(parents=True, exist_ok=True)
          Path(path).write_bytes(b"fake-png")
          self._shots.append(path)
          return path

      def close(self):
          self.closed = True


  @pytest.fixture(autouse=True)
  def _stub_check_page(monkeypatch):
      monkeypatch.setattr(drive.measure, "check_page", lambda *a, **k: [])


  def _dirs(tmp_path):
      run_dir = tmp_path / "run"
      run_dir.mkdir()
      return run_dir, tmp_path / "project"


  def test_fill_password_redacts_even_with_text(tmp_path):
      run_dir, project_root = _dirs(tmp_path)
      driver = FakeDriver()
      session = DriveSession(driver, "webapp", run_dir, project_root, record_enabled=True)
      session.flow_begin("login")
      session.fill({"testid": "pw-input"}, text="hunter2")
      result = session.flow_end("login", "ok")
      saved = actionlog.load(Path(result["log_path"]))
      dumped = json.dumps(saved)
      assert "hunter2" not in dumped
      assert saved["steps"][0]["value"] == events.REDACTED
      assert driver.filled[0][1] == "hunter2"  # the real page still got filled


  def test_fill_from_env_reads_environ_and_redacts(tmp_path, monkeypatch):
      monkeypatch.setenv("ADMIN_PASSWORD", "s3cret")
      run_dir, project_root = _dirs(tmp_path)
      driver = FakeDriver()
      session = DriveSession(driver, "webapp", run_dir, project_root, record_enabled=False)
      session.flow_begin("login")
      session.fill({"css": "#password"}, from_env="ADMIN_PASSWORD")
      result = session.flow_end("login", "ok")
      saved = actionlog.load(Path(result["log_path"]))
      assert "s3cret" not in json.dumps(saved)
      assert driver.filled[0][1] == "s3cret"


  def test_click_calls_check_page_with_route_tokens_step_index_and_appends_findings(
      tmp_path, monkeypatch,
  ):
      run_dir, project_root = _dirs(tmp_path)
      calls = []
      finding = {
          "rule": "http.5xx", "sev": "P0", "locator": None, "route": "http://fake/",
          "text": "boom", "evidence": [], "disposition": "engine",
      }

      def _fake_check_page(driver, surface_id, flow_id, route, tokens, step_index):
          calls.append(dict(
              surface_id=surface_id, flow_id=flow_id, route=route,
              tokens=tokens, step_index=step_index,
          ))
          return [finding]

      monkeypatch.setattr(drive.measure, "check_page", _fake_check_page)

      driver = FakeDriver()
      session = DriveSession(
          driver, "webapp", run_dir, project_root, record_enabled=False,
          tokens={"color.primary": "#1a56db"},
      )
      session.flow_begin("f1")
      result = session.click({"testid": "load-button"})

      assert result["new_findings"]
      assert calls[0]["surface_id"] == "webapp"
      assert calls[0]["flow_id"] == "f1"
      assert calls[0]["tokens"] == {"color.primary": "#1a56db"}
      assert calls[0]["step_index"] == 0
      written = (run_dir / "events.jsonl").read_text(encoding="utf-8")
      assert "http.5xx" in written


  def test_look_passes_step_index_none():
      calls = []

      def _fake_check_page(driver, surface_id, flow_id, route, tokens, step_index):
          calls.append(step_index)
          return []

      import flow_review.web.drive as drive_mod
      orig = drive_mod.measure.check_page
      drive_mod.measure.check_page = _fake_check_page
      try:
          driver = FakeDriver()
          import tempfile
          with tempfile.TemporaryDirectory() as td:
              run_dir = Path(td) / "run"
              run_dir.mkdir()
              session = DriveSession(driver, "webapp", run_dir, Path(td) / "project",
                                      record_enabled=False)
              session.look()
      finally:
          drive_mod.measure.check_page = orig
      assert calls == [None]


  def test_snapshot_is_trimmed_to_4000_chars(tmp_path):
      run_dir, project_root = _dirs(tmp_path)
      driver = FakeDriver()
      driver.snapshot = lambda: {"role": "WebArea", "name": "x" * 10000}
      session = DriveSession(driver, "webapp", run_dir, project_root, record_enabled=False)
      result = session.goto("/")
      assert len(result["snapshot"]) <= 4000


  def test_flow_end_saves_recording_when_record_enabled(tmp_path):
      run_dir, project_root = _dirs(tmp_path)
      driver = FakeDriver()
      session = DriveSession(driver, "webapp", run_dir, project_root, record_enabled=True)
      session.flow_begin("f1")
      session.goto("/")
      result = session.flow_end("f1", "ok")
      assert Path(result["log_path"]) == (
          project_root / ".flow-review" / "recordings" / "webapp" / "f1.json"
      )


  def test_flow_end_saves_ephemeral_repro_when_record_disabled(tmp_path):
      run_dir, project_root = _dirs(tmp_path)
      driver = FakeDriver()
      session = DriveSession(driver, "webapp", run_dir, project_root, record_enabled=False)
      session.flow_begin("f1")
      session.goto("/")
      result = session.flow_end("f1", "ok")
      assert Path(result["log_path"]) == run_dir / "repro" / "f1.json"


  def test_press_and_click_return_compact_result_shape(tmp_path):
      run_dir, project_root = _dirs(tmp_path)
      driver = FakeDriver()
      session = DriveSession(driver, "webapp", run_dir, project_root, record_enabled=False)
      result = session.press("Enter")
      assert set(result) == {"url", "title", "snapshot", "shot", "new_findings", "console_errors"}
      assert driver.page.pressed == "Enter"
  ```
- [ ] **Step 6: run, expect FAIL.**
  `pytest plugins/flow-review/engine/flow_review/web/test_drive.py -x`
  Expected: `ModuleNotFoundError: flow_review.web.drive`.
- [ ] **Step 7: implementation — `DriveSession` (drive.py, part 1).**
  ```python
  # plugins/flow-review/engine/flow_review/web/drive.py
  import argparse
  import json
  import os
  import subprocess
  import sys
  import threading
  import time
  import urllib.request
  from http.server import BaseHTTPRequestHandler, HTTPServer
  from pathlib import Path

  from flow_review import events
  from flow_review.web import actionlog, measure


  class DriveSession:
      def __init__(self, driver, surface_id: str, run_dir, project_root, record_enabled: bool,
                   tokens: dict | None = None):
          self.driver = driver
          self.surface_id = surface_id
          self.run_dir = Path(run_dir)
          self.project_root = Path(project_root)
          self.record_enabled = record_enabled
          self.tokens = tokens
          self.log = None
          self.flow_id = None
          self.step_index = 0

      def flow_begin(self, flow_id: str) -> dict:
          self.flow_id = flow_id
          self.log = actionlog.new_log(self.surface_id, flow_id)
          self.step_index = 0
          events.append(self.run_dir, {
              "type": "step", "surface_id": self.surface_id, "flow_id": flow_id,
              "step": "flow-begin",
          })
          return {"flow_id": flow_id}

      def flow_end(self, flow_id: str, status: str) -> dict:
          log_path = None
          if self.log is not None:
              log_path = actionlog.save(self.log, self.run_dir, self.project_root,
                                         self.record_enabled)
          events.append(self.run_dir, {
              "type": "step", "surface_id": self.surface_id, "flow_id": flow_id,
              "step": "flow-end", "status": status,
          })
          self.log = None
          self.flow_id = None
          return {"flow_id": flow_id, "status": status,
                  "log_path": str(log_path) if log_path else None}

      def goto(self, path: str) -> dict:
          return self._act("goto", lambda: self.driver.goto(path), url_hint=path)

      def click(self, locator: dict) -> dict:
          return self._act("click", lambda: self.driver.click(locator), locator=locator)

      def fill(self, locator: dict, text: str | None = None, from_env: str | None = None) -> dict:
          is_secret = bool(self.driver.is_password(locator))
          if from_env is not None:
              value = os.environ.get(from_env, "")
              events.register_secret(value)
              is_secret = True
          else:
              value = text or ""
              if is_secret:
                  events.register_secret(value)
          return self._act("fill", lambda: self.driver.fill(locator, value),
                            locator=locator, value=value, secret=is_secret)

      def press(self, key: str) -> dict:
          return self._act("press", lambda: self.driver.page.keyboard.press(key), value=key)

      def look(self, shot: bool = False) -> dict:
          result = self._after("look", step_index=None, record=False)
          if shot:
              self.step_index += 1
              path = self.run_dir / "drive" / self.surface_id / f"shot-{self.step_index:04d}.png"
              self.driver.screenshot(path)
              events.append(self.run_dir, {
                  "type": "shot", "surface_id": self.surface_id, "step": self.step_index,
                  "path": str(path),
              })
              result["shot"] = str(path)
          return result

      def _act(self, action, op, *, locator=None, value=None, secret=False, url_hint=None):
          step = self.step_index
          self.step_index += 1
          self.driver.begin_step(step)
          try:
              op()
          finally:
              self.driver.end_step()
          return self._after(action, step_index=step, locator=locator, value=value,
                              secret=secret, url_hint=url_hint)

      def _after(self, action, *, step_index, locator=None, value=None, secret=False,
                 url_hint=None, record=True):
          if record and self.log is not None:
              log_locator = dict(locator) if locator else None
              if log_locator is not None and secret:
                  log_locator["secret"] = True
              actionlog.record_step(
                  self.log, action, locator=log_locator,
                  value=events.REDACTED if secret else value,
                  url=url_hint or self._current_url(),
              )
          new_ids = self._run_checks(step_index)
          return self._result(new_ids)

      def _run_checks(self, step_index) -> list:
          route = self._current_url() or "/"
          findings = measure.check_page(
              self.driver, self.surface_id, self.flow_id, route, self.tokens, step_index,
          )
          new_ids = []
          for finding in findings:
              event = events.append(self.run_dir, {
                  "type": "finding", "surface_id": self.surface_id, "flow_id": self.flow_id,
                  **finding,
              })
              new_ids.append(event["id"])
          return new_ids

      def _current_url(self) -> str | None:
          page = getattr(self.driver, "page", None)
          return getattr(page, "url", None) if page is not None else None

      def _result(self, new_ids: list) -> dict:
          page = getattr(self.driver, "page", None)
          title = None
          if page is not None:
              title_fn = getattr(page, "title", None)
              title = title_fn() if callable(title_fn) else None
          snapshot = json.dumps(self.driver.snapshot(), ensure_ascii=False)[:4000]
          return {
              "url": self._current_url(),
              "title": title,
              "snapshot": snapshot,
              "shot": None,
              "new_findings": new_ids,
              "console_errors": len(self.driver.console_errors()),
          }
  ```
- [ ] **Step 8: run, expect PASS.**
  `pytest plugins/flow-review/engine/flow_review/web/test_drive.py -v`

- [ ] **Step 9: failing test — server + thin CLI client, in-process, FAKE driver factory (no browser, no subprocess).**
  ```python
  # appended to plugins/flow-review/engine/flow_review/web/test_drive.py

  def _start_fake_server(tmp_path, record_enabled=False):
      run_dir = tmp_path / "run"
      run_dir.mkdir()
      project_root = tmp_path / "project"

      def factory(headless, viewport):
          return FakeDriver()

      thread = threading.Thread(
          target=drive.serve,
          args=("webapp", run_dir, project_root, "http://fake/"),
          kwargs={"record_enabled": record_enabled, "driver_factory": factory},
          daemon=True,
      )
      thread.start()

      state_path = run_dir / "drive" / "webapp.json"
      deadline = time.monotonic() + 5
      while time.monotonic() < deadline and not state_path.exists():
          time.sleep(0.05)
      assert state_path.exists(), "drive server did not write its state file in time"
      return run_dir, project_root, json.loads(state_path.read_text())


  def test_server_dispatches_actions_over_http_and_stops_cleanly(tmp_path):
      run_dir, project_root, state = _start_fake_server(tmp_path)

      begin = drive._post(state["port"], "flow-begin", {"flow": "f1"})
      assert begin["flow_id"] == "f1"

      goto = drive._post(state["port"], "goto", {"path": "/"})
      assert goto["url"] == "http://fake/"

      click = drive._post(state["port"], "click", {"locator": {"testid": "x"}})
      assert "new_findings" in click

      end = drive._post(state["port"], "flow-end", {"flow": "f1", "status": "ok"})
      assert end["status"] == "ok"

      stopped = drive._post(state["port"], "stop", {})
      assert stopped["stopped"] is True

      deadline = time.monotonic() + 5
      while time.monotonic() < deadline and (run_dir / "drive" / "webapp.json").exists():
          time.sleep(0.05)
      assert not (run_dir / "drive" / "webapp.json").exists()


  def test_cli_client_reads_state_file_and_posts(tmp_path):
      run_dir, project_root, state = _start_fake_server(tmp_path)
      ns = argparse.Namespace(surface="webapp", run_dir=str(run_dir), path="/dashboard")
      result = drive.cmd_goto(ns)
      assert result["url"] == "http://fake/dashboard"
      drive._post(state["port"], "stop", {})


  def test_cli_client_raises_when_no_session_started(tmp_path):
      run_dir = tmp_path / "run"
      run_dir.mkdir()
      ns = argparse.Namespace(surface="webapp", run_dir=str(run_dir), path="/")
      with pytest.raises(RuntimeError):
          drive.cmd_goto(ns)


  def test_start_reuses_live_state_file_without_spawning(tmp_path, monkeypatch):
      run_dir = tmp_path / "run"
      (run_dir / "drive").mkdir(parents=True)
      (run_dir / "drive" / "webapp.json").write_text(
          json.dumps({"port": 9999, "pid": os.getpid()})
      )

      def _boom(*a, **kw):
          raise AssertionError("must not spawn a new server when a live state file exists")

      monkeypatch.setattr(drive.subprocess, "Popen", _boom)

      ns = argparse.Namespace(surface="webapp", run_dir=str(run_dir),
                               project_root=str(tmp_path / "project"), record=False)
      result = drive.cmd_start(ns)
      assert result == {"surface_id": "webapp", "port": 9999}


  def test_start_resolves_base_url_tokens_and_record_from_config(tmp_path, monkeypatch):
      project_root = tmp_path / "project"
      (project_root / ".flow-review").mkdir(parents=True)
      (project_root / ".flow-review" / "config.json").write_text(json.dumps({
          "schema_version": 2, "generator_version": "2.0.0", "model_profile": "default",
          "role_overrides": {}, "budget": {"cap_tokens": None}, "test_inbox": None,
          "flows_hash": "", "surfaces": [{
              "id": "webapp", "name": "Web app", "kind": "ui", "driver": "playwright",
              "launch": "npm run dev", "cwd": ".", "env": {},
              "options": {
                  "base_url": "http://localhost:5173", "health_path": "/healthz",
                  "ready_timeout_s": 15, "exit_timeout_s": 60,
                  "viewport": [{"width": 1280, "height": 800}], "tokens_file": None,
              },
              "preconditions": [], "state": "disposable", "reset": None, "creds": {},
              "record": True, "provenance": {}, "declined": False,
          }],
      }))
      run_dir = tmp_path / "run"
      run_dir.mkdir()

      captured = {}

      def _fake_popen(cmd, **kw):
          captured["cmd"] = cmd
          (run_dir / "drive").mkdir(parents=True, exist_ok=True)
          (run_dir / "drive" / "webapp.json").write_text(
              json.dumps({"port": 4321, "pid": os.getpid()})
          )
          return None

      monkeypatch.setattr(drive.subprocess, "Popen", _fake_popen)

      ns = argparse.Namespace(surface="webapp", run_dir=str(run_dir),
                               project_root=str(project_root), record=False)
      result = drive.cmd_start(ns)
      assert result == {"surface_id": "webapp", "port": 4321}
      assert "--base-url" in captured["cmd"]
      assert "http://localhost:5173" in captured["cmd"]
      assert "--record" in captured["cmd"]  # from surface.record, not args.record
      assert "--viewport-width" in captured["cmd"]
  ```
- [ ] **Step 10: run, expect FAIL.**
  `pytest plugins/flow-review/engine/flow_review/web/test_drive.py -k "server or cli_client or start_" -x`
  Expected: `AttributeError: module 'flow_review.web.drive' has no attribute '_post'` (and siblings).
- [ ] **Step 11: implementation — server + thin client (drive.py, part 2, appended to the same file).**
  ```python
  # plugins/flow-review/engine/flow_review/web/drive.py (continued)

  def _default_driver_factory(headless: bool, viewport: dict | None):
      from flow_review.web.driver import WebDriver
      return WebDriver(headless=headless, viewport=viewport)


  class _ActionHandler(BaseHTTPRequestHandler):
      session: "DriveSession" = None
      server_ref: HTTPServer = None

      def log_message(self, fmt, *args) -> None:
          pass  # request bodies may carry secrets; never let BaseHTTPRequestHandler log them

      def do_POST(self) -> None:
          length = int(self.headers.get("Content-Length", 0))
          body = self.rfile.read(length) if length else b"{}"
          try:
              payload = json.loads(body.decode("utf-8"))
          except ValueError:
              self._respond(400, {"error": "invalid JSON"})
              return
          verb = payload.get("verb")
          args = payload.get("args", {})
          try:
              result = self._dispatch(verb, args)
          except Exception as exc:
              self._respond(500, {"error": str(exc)})
              return
          self._respond(200, result)
          if verb == "stop":
              threading.Thread(target=type(self).server_ref.shutdown, daemon=True).start()

      def _dispatch(self, verb: str, args: dict) -> dict:
          session = type(self).session
          if verb == "goto":
              return session.goto(args["path"])
          if verb == "click":
              return session.click(args["locator"])
          if verb == "fill":
              return session.fill(args["locator"], text=args.get("text"),
                                   from_env=args.get("from_env"))
          if verb == "press":
              return session.press(args["key"])
          if verb == "look":
              return session.look(shot=args.get("shot", False))
          if verb == "flow-begin":
              return session.flow_begin(args["flow"])
          if verb == "flow-end":
              return session.flow_end(args["flow"], args.get("status", "ok"))
          if verb == "stop":
              try:
                  session.driver.close()
              except Exception:
                  pass
              return {"stopped": True}
          raise ValueError(f"unknown verb {verb!r}")

      def _respond(self, code: int, payload: dict) -> None:
          body = json.dumps(payload).encode("utf-8")
          self.send_response(code)
          self.send_header("Content-Type", "application/json")
          self.send_header("Content-Length", str(len(body)))
          self.end_headers()
          self.wfile.write(body)


  def make_server(host: str, port: int, session: DriveSession) -> HTTPServer:
      handler = type("_BoundActionHandler", (_ActionHandler,), {"session": session})
      httpd = HTTPServer((host, port), handler)
      handler.server_ref = httpd
      return httpd


  def serve(surface_id: str, run_dir, project_root, base_url: str, *,
            record_enabled: bool = False, headless: bool = True, viewport: dict | None = None,
            tokens: dict | None = None, driver_factory=_default_driver_factory) -> None:
      run_dir = Path(run_dir)
      driver = driver_factory(headless, viewport)
      driver.launch(base_url)
      session = DriveSession(driver, surface_id, run_dir, Path(project_root), record_enabled,
                              tokens=tokens)

      httpd = make_server("127.0.0.1", 0, session)
      port = httpd.server_address[1]

      state_dir = run_dir / "drive"
      state_dir.mkdir(parents=True, exist_ok=True)
      state_path = state_dir / f"{surface_id}.json"
      state_path.write_text(json.dumps({"port": port, "pid": os.getpid()}))

      try:
          httpd.serve_forever(poll_interval=0.1)
      finally:
          try:
              driver.close()
          except Exception:
              pass
          state_path.unlink(missing_ok=True)


  def _state_path(run_dir, surface_id: str) -> Path:
      return Path(run_dir) / "drive" / f"{surface_id}.json"


  def _read_state(run_dir, surface_id: str) -> dict | None:
      path = _state_path(run_dir, surface_id)
      if not path.exists():
          return None
      return json.loads(path.read_text())


  def _pid_alive(pid: int) -> bool:
      try:
          os.kill(pid, 0)
      except OSError:
          return False
      except AttributeError:
          return True
      return True


  def _post(port: int, verb: str, args: dict) -> dict:
      body = json.dumps({"verb": verb, "args": args}).encode("utf-8")
      req = urllib.request.Request(
          f"http://127.0.0.1:{port}/action", data=body,
          headers={"Content-Type": "application/json"}, method="POST",
      )
      with urllib.request.urlopen(req, timeout=30) as resp:
          return json.loads(resp.read().decode("utf-8"))


  def _client_call(args: argparse.Namespace, verb: str, payload: dict) -> dict:
      state = _read_state(args.run_dir, args.surface)
      if state is None:
          raise RuntimeError(
              f"no drive session for {args.surface!r}; run 'flow-review drive start' first"
          )
      return _post(state["port"], verb, payload)


  def _locator_from_args(args: argparse.Namespace) -> dict:
      if getattr(args, "role", None):
          return {"role": args.role, "name": args.name}
      if getattr(args, "testid", None):
          return {"testid": args.testid}
      if getattr(args, "css", None):
          return {"css": args.css}
      raise ValueError("one of --role/--name, --testid or --css is required")


  def cmd_start(args: argparse.Namespace) -> dict:
      from flow_review import config as configmod

      run_dir = Path(args.run_dir)
      project_root = Path(args.project_root)

      state = _read_state(run_dir, args.surface)
      if state is not None and _pid_alive(state["pid"]):
          return {"surface_id": args.surface, "port": state["port"]}

      cfg = configmod.load(project_root / ".flow-review" / "config.json")
      surface = next((s for s in cfg.surfaces if s.id == args.surface), None)
      if surface is None:
          raise ValueError(f"no surface {args.surface!r} in config")
      base_url = surface.options.get("base_url")
      if not base_url:
          raise ValueError(f"surface {args.surface!r} has no options.base_url")
      record_enabled = bool(args.record or surface.record)
      viewport_list = surface.options.get("viewport") or []
      viewport = viewport_list[0] if viewport_list else None
      tokens_file = surface.options.get("tokens_file")
      tokens_path = (project_root / tokens_file) if tokens_file else None

      (run_dir / "drive").mkdir(parents=True, exist_ok=True)
      cmd = [
          sys.executable, "-m", "flow_review.web.drive", "serve",
          "--surface", args.surface, "--run", str(run_dir), "--project", str(project_root),
          "--base-url", base_url,
      ]
      if record_enabled:
          cmd.append("--record")
      if viewport is not None:
          cmd += ["--viewport-width", str(viewport["width"]),
                   "--viewport-height", str(viewport["height"])]
      if tokens_path is not None:
          cmd += ["--tokens-file", str(tokens_path)]

      popen_kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
      if os.name == "nt":
          popen_kwargs["creationflags"] = subprocess.DETACHED_PROCESS
      else:
          popen_kwargs["start_new_session"] = True
      subprocess.Popen(cmd, **popen_kwargs)

      deadline = time.monotonic() + 30
      while time.monotonic() < deadline:
          state = _read_state(run_dir, args.surface)
          if state is not None:
              return {"surface_id": args.surface, "port": state["port"]}
          time.sleep(0.1)
      raise TimeoutError(f"drive server for {args.surface!r} did not start in time")


  def cmd_stop(args: argparse.Namespace) -> dict:
      state = _read_state(args.run_dir, args.surface)
      if state is None:
          return {"stopped": True, "already_stopped": True}
      try:
          _post(state["port"], "stop", {})
      except OSError:
          pass
      _state_path(args.run_dir, args.surface).unlink(missing_ok=True)
      return {"stopped": True}


  def cmd_goto(args: argparse.Namespace) -> dict:
      return _client_call(args, "goto", {"path": args.path})


  def cmd_click(args: argparse.Namespace) -> dict:
      return _client_call(args, "click", {"locator": _locator_from_args(args)})


  def cmd_fill(args: argparse.Namespace) -> dict:
      payload = {"locator": _locator_from_args(args)}
      if args.from_env:
          payload["from_env"] = args.from_env
      else:
          payload["text"] = args.text
      return _client_call(args, "fill", payload)


  def cmd_press(args: argparse.Namespace) -> dict:
      return _client_call(args, "press", {"key": args.key})


  def cmd_look(args: argparse.Namespace) -> dict:
      return _client_call(args, "look", {"shot": args.shot})


  def cmd_flow_begin(args: argparse.Namespace) -> dict:
      return _client_call(args, "flow-begin", {"flow": args.flow})


  def cmd_flow_end(args: argparse.Namespace) -> dict:
      return _client_call(args, "flow-end", {"flow": args.flow, "status": args.status})


  def cmd_serve(args: argparse.Namespace) -> None:
      viewport = None
      if args.viewport_width and args.viewport_height:
          viewport = {"width": args.viewport_width, "height": args.viewport_height}
      tokens = None
      if args.tokens_file:
          tokens = measure.load_tokens(Path(args.tokens_file))  # B4, A-25
      serve(args.surface, Path(args.run_dir), Path(args.project_root), args.base_url,
            record_enabled=args.record, headless=args.headless, viewport=viewport, tokens=tokens)


  def build_drive_parser() -> argparse.ArgumentParser:
      parser = argparse.ArgumentParser(prog="flow-review drive")
      sub = parser.add_subparsers(dest="drive_verb", required=True)

      def _common(p):
          p.add_argument("--surface", required=True)
          p.add_argument("--run", required=True, dest="run_dir")

      def _locator_args(p):
          p.add_argument("--role")
          p.add_argument("--name")
          p.add_argument("--testid")
          p.add_argument("--css")

      p = sub.add_parser("start")
      _common(p)
      p.add_argument("--record", action="store_true")
      p.set_defaults(func=cmd_start)

      p = sub.add_parser("stop")
      _common(p)
      p.set_defaults(func=cmd_stop)

      p = sub.add_parser("goto")
      _common(p)
      p.add_argument("path")
      p.set_defaults(func=cmd_goto)

      p = sub.add_parser("click")
      _common(p)
      _locator_args(p)
      p.set_defaults(func=cmd_click)

      p = sub.add_parser("fill")
      _common(p)
      _locator_args(p)
      p.add_argument("--text")
      p.add_argument("--from-env")
      p.set_defaults(func=cmd_fill)

      p = sub.add_parser("press")
      _common(p)
      p.add_argument("key")
      p.set_defaults(func=cmd_press)

      p = sub.add_parser("look")
      _common(p)
      p.add_argument("--shot", action="store_true")
      p.set_defaults(func=cmd_look)

      p = sub.add_parser("flow-begin")
      _common(p)
      p.add_argument("--flow", required=True)
      p.set_defaults(func=cmd_flow_begin)

      p = sub.add_parser("flow-end")
      _common(p)
      p.add_argument("--flow", required=True)
      p.add_argument("--status", choices=("ok", "blocked"), default="ok")
      p.set_defaults(func=cmd_flow_end)

      p = sub.add_parser("serve")
      p.add_argument("--surface", required=True)
      p.add_argument("--run", required=True, dest="run_dir")
      p.add_argument("--project", required=True, dest="project_root")
      p.add_argument("--base-url", required=True)
      p.add_argument("--record", action="store_true")
      p.add_argument("--headless", dest="headless", action="store_true", default=True)
      p.add_argument("--no-headless", dest="headless", action="store_false")
      p.add_argument("--viewport-width", type=int, default=None)
      p.add_argument("--viewport-height", type=int, default=None)
      p.add_argument("--tokens-file", default=None)
      p.set_defaults(func=cmd_serve)

      return parser


  def main(argv: list[str] | None = None, project_root: Path | None = None) -> int:
      parser = build_drive_parser()
      args = parser.parse_args(argv)
      if args.func is cmd_start:
          args.project_root = project_root
      result = args.func(args)
      if result is not None:
          print(json.dumps(result))
      return 0


  if __name__ == "__main__":
      raise SystemExit(main())
  ```
- [ ] **Step 12: run, expect PASS.**
  `pytest plugins/flow-review/engine/flow_review/web/test_drive.py -v`

- [ ] **Step 13: failing test — `cli.py` wires the `drive` verb.**
  ```python
  # appended to plugins/flow-review/engine/flow_review/test_cli.py
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
  ```
- [ ] **Step 14: run, expect FAIL.**
  `pytest plugins/flow-review/engine/flow_review/test_cli.py -k drive -x`
  Expected: `SystemExit: 2` (argparse rejects the unknown `drive` verb) or a KeyError on
  `_stub("drive")`, since `"drive"` is not in `_STUB_VERBS`.
- [ ] **Step 15: implementation — wire `drive` in `cli.py`.**
  In `plugins/flow-review/engine/flow_review/cli.py`, remove `"drive"` from nowhere (it was
  never in `_STUB_VERBS` — leave that tuple as-is) and add, next to the other explicit verb
  wiring (alongside `event_parser` from A4):
  ```python
  drive_parser = sub.add_parser("drive")
  drive_parser.add_argument("drive_args", nargs=argparse.REMAINDER)
  drive_parser.set_defaults(func=_run_drive)
  ```
  and:
  ```python
  def _run_drive(args: argparse.Namespace) -> int:
      from flow_review.web import drive
      return drive.main(args.drive_args, project_root=args.project_root)
  ```
  (`args.project_root` is already set by `_resolve_project_root` before `args.func(args)` runs,
  per A1's `main()`.)
- [ ] **Step 16: run, expect PASS.**
  `pytest plugins/flow-review/engine/flow_review/test_cli.py -k drive -v`

- [ ] **Step 17: web-marked end-to-end cycle against the B0 fixture — sign-in reveals the low-contrast note.**
  ```python
  # appended to plugins/flow-review/engine/flow_review/web/test_drive.py
  import pytest
  pytest.importorskip("playwright")


  @pytest.mark.web
  def test_drive_e2e_sign_in_finds_low_contrast(tmp_path, webapp_server):
      base_url, _ = webapp_server
      run_dir = tmp_path / "run"
      run_dir.mkdir()
      project_root = tmp_path / "project"

      thread = threading.Thread(
          target=drive.serve,
          args=("webapp", run_dir, project_root, base_url),
          kwargs={"record_enabled": False},
          daemon=True,
      )
      thread.start()

      state_path = run_dir / "drive" / "webapp.json"
      deadline = time.monotonic() + 15
      while time.monotonic() < deadline and not state_path.exists():
          time.sleep(0.1)
      assert state_path.exists()
      state = json.loads(state_path.read_text())

      drive._post(state["port"], "flow-begin", {"flow": "sign-in"})
      drive._post(state["port"], "goto", {"path": "/"})
      look = drive._post(state["port"], "look", {"shot": False})
      drive._post(state["port"], "flow-end", {"flow": "sign-in", "status": "ok"})
      drive._post(state["port"], "stop", {})

      written = (run_dir / "events.jsonl").read_text(encoding="utf-8")
      assert "contrast.aa" in written
      assert look["new_findings"] or "contrast.aa" in written
  ```
  Run: `pytest plugins/flow-review/engine/flow_review/web/test_drive.py -m web -k e2e_sign_in -x`
  → PASS.

- **Verify:**
  ```
  pytest plugins/flow-review/engine/flow_review/web/test_driver.py plugins/flow-review/engine/flow_review/web/test_drive.py plugins/flow-review/engine/flow_review/test_cli.py -m "web or not web" -v
  ```
- **Commit:**
  ```
  git add plugins/flow-review/engine/flow_review/web/drive.py plugins/flow-review/engine/flow_review/web/test_drive.py plugins/flow-review/engine/flow_review/web/driver.py plugins/flow-review/engine/flow_review/web/test_driver.py plugins/flow-review/engine/flow_review/cli.py plugins/flow-review/engine/flow_review/test_cli.py
  git commit -m "feat(web): drive CLI — DriveSession, localhost session server, thin client (A-24/B10)"
  ```


---

### Task C1: Model routing in `config.py` + agent definitions that mirror it

**Executor:** sonnet · **Depends:** A2 · **Wave:** 3
**Files:**
- `plugins/flow-review/engine/flow_review/config.py` (edit -- add `PROFILES`, `ROLES`, `resolve_model`)
- `plugins/flow-review/engine/flow_review/test_config_profiles.py` (new)
- `plugins/flow-review/engine/flow_review/cli.py` (edit -- add the `model` subcommand)
- `plugins/flow-review/agents/fr-explorer.md`
- `plugins/flow-review/agents/fr-cold-eyes.md`
- `plugins/flow-review/agents/fr-lens.md`
- `plugins/flow-review/agents/fr-replay-repair.md`
- `plugins/flow-review/agents/fr-triage.md`
- `plugins/flow-review/agents/fr-verifier.md`
- `plugins/flow-review/test_agents.py` (new)

**Interfaces:**
- Consumes: `config.Config` (`model_profile="default"`, `role_overrides={}`) from A2; the `drive`
  CLI (Canonical Interfaces "Drive", B10, A-24) is named as the sole browser interface in
  `fr-explorer.md` and `fr-cold-eyes.md`'s bodies below -- those two agents never name Playwright
  or an MCP browser tool.
- Produces (Canonical Interfaces, "Model routing"): `config.PROFILES: dict[str, dict[str, str]]`
  (profile -> role -> model); `config.resolve_model(cfg, role) -> "haiku"|"sonnet"|"opus"`
  (`role_overrides` win; the verifier is never below sonnet); CLI `flow-review model ROLE` prints
  it. **The Python dict is the single source of truth; every agent file's Markdown table is a
  mirror of it, never the other way round.**

- [ ] **Step 1: failing test first -- `test_config_profiles.py`:**

```python
from __future__ import annotations

import pytest

from flow_review.config import PROFILES, ROLES, Config, resolve_model

EXPECTED_ROLES = {"explorer", "cold-eyes", "lens", "replay-repair", "triage", "verifier"}


def _cfg(profile="default", overrides=None):
    return Config(schema_version=2, generator_version="0", surfaces=[],
                  model_profile=profile, role_overrides=overrides or {})


def test_profiles_has_exactly_lean_default_max():
    assert set(PROFILES) == {"lean", "default", "max"}


def test_every_profile_covers_every_role():
    for profile, mapping in PROFILES.items():
        assert set(mapping) == EXPECTED_ROLES, f"profile {profile!r} covers {set(mapping)}"


def test_roles_constant_matches_the_role_set():
    assert set(ROLES) == EXPECTED_ROLES


def test_every_model_is_a_real_tier():
    for mapping in PROFILES.values():
        for model in mapping.values():
            assert model in {"haiku", "sonnet", "opus"}


def test_verifier_is_never_below_sonnet_in_any_profile():
    for profile, mapping in PROFILES.items():
        assert mapping["verifier"] in {"sonnet", "opus"}, (
            f"{profile} drops verifier to {mapping['verifier']!r}"
        )


def test_resolve_model_reads_the_configured_profile():
    cfg = _cfg(profile="lean")
    assert resolve_model(cfg, "explorer") == PROFILES["lean"]["explorer"]


def test_resolve_model_role_override_wins_over_profile():
    cfg = _cfg(profile="default", overrides={"lens": "opus"})
    assert resolve_model(cfg, "lens") == "opus"


def test_resolve_model_rejects_an_unknown_role():
    cfg = _cfg()
    with pytest.raises(ValueError):
        resolve_model(cfg, "fr-lens")  # the fr- prefix is a file-naming convention, not a role


def test_resolve_model_never_returns_inherit():
    for profile in PROFILES:
        cfg = _cfg(profile=profile)
        for role in ROLES:
            assert resolve_model(cfg, role) != "inherit"
```

  Step 2: run `python -m pytest plugins/flow-review/engine/flow_review/test_config_profiles.py -q`
  -> FAIL (`PROFILES`/`ROLES`/`resolve_model` do not exist in `config.py` yet).

- [ ] **Step 3: the content.**

  Append to `plugins/flow-review/engine/flow_review/config.py` (after `Config` and `Surface` land
  from A2; this is additive, never touching A2's own definitions):

```python
# --- Model routing (C1; Canonical Interfaces "Model routing") -----------------------------
#
# Profiles are shipped as data, never as a parsed Markdown table: every agents/fr-*.md file's
# "## Model profile" table is a documentation mirror of PROFILES below, generated to match it --
# never the other direction. The engine never reads Markdown at runtime.

ROLES: tuple[str, ...] = (
    "explorer", "cold-eyes", "lens", "replay-repair", "triage", "verifier",
)

PROFILES: dict[str, dict[str, str]] = {
    "lean": {
        "explorer": "haiku",
        "cold-eyes": "haiku",
        "lens": "haiku",
        "replay-repair": "haiku",
        "triage": "haiku",
        "verifier": "sonnet",
    },
    "default": {
        "explorer": "sonnet",
        "cold-eyes": "sonnet",
        "lens": "sonnet",
        "replay-repair": "haiku",
        "triage": "haiku",
        "verifier": "opus",
    },
    "max": {
        "explorer": "opus",
        "cold-eyes": "opus",
        "lens": "opus",
        "replay-repair": "sonnet",
        "triage": "sonnet",
        "verifier": "opus",
    },
}


def resolve_model(cfg: "Config", role: str) -> str:
    """The model to dispatch `role` at, honouring `cfg.role_overrides` first.

    `role` must be one of `ROLES` -- the bare role name, never an `fr-` prefixed agent filename;
    the prefix is a Claude Code agent-file naming convention, not part of the role's identity.
    """
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r}, must be one of {ROLES}")
    override = cfg.role_overrides.get(role)
    if override:
        return override
    return PROFILES[cfg.model_profile][role]
```

  Add the CLI subcommand to `plugins/flow-review/engine/flow_review/cli.py` (additive, alongside
  whatever subparsers A1/A2 already registered):

```python
def _cmd_model(args: argparse.Namespace) -> int:
    cfg = config.load(_project_root(args) / ".flow-review" / "config.json")
    print(config.resolve_model(cfg, args.role))
    return 0


# in the subparser registration block:
model_parser = subparsers.add_parser("model", help="print the resolved model for ROLE")
model_parser.add_argument("role", choices=list(config.ROLES))
model_parser.set_defaults(func=_cmd_model)
```

  The six agent files, full text. Each frontmatter `model:` is `PROFILES["default"][role]`; each
  body's `## Model profile` table is `PROFILES[*][role]` for that role, verbatim:

`plugins/flow-review/agents/fr-explorer.md`:

````markdown
---
name: fr-explorer
description: Goal-driven flow explorer. Drives one surface toward a stated goal (goal mode) or
  cold with no prior knowledge of code or docs (auto mode's pass 1), plus everything the goal
  implies around it -- unhappy paths, interruptions, alternate routes, variants. Drives the
  browser exclusively through `flow-review drive`; never returns a screenshot to the orchestrator
  except the one failing image a verdict depends on.
model: sonnet
tools: Read, Bash, Glob, Grep
---

# fr-explorer

Role key: `explorer`. You drive exactly one surface toward exactly one goal (or, with no goal,
cold-eyes exploration -- see `references/goals.md` pass 1). Read `references/goals.md` (section 5,
"Driving", is your entire browser interface) plus `references/testing.md`,
`references/evidence.md`, and `references/stuck.md` before driving anything; they are the whole
contract, not a summary of it.

**Your only interface to a web surface is the `flow-review drive` CLI** (A-24): `start` (run once
by the orchestrator before you are dispatched, per `SKILL.md` section 3, never by you), `goto`,
`click`, `fill`, `press`, `look`, `flow-begin`, `flow-end`, `stop` (run once by the orchestrator
at run end, never by you). **You do not have, and must never reach for, Playwright, Puppeteer, an
MCP browser tool, or any other means of touching a browser.** Your `tools` frontmatter is
`Read, Bash, Glob, Grep` -- `Bash` is how you invoke `flow-review drive ...`, and there is no
browser tool in that list for a reason.

**Consumes:** the surface's config entry (kind, driver, launch, preconditions, `state`, `reset`,
`creds`) only to know which surface `--surface ID` names; `flow-review drive`'s compact JSON
response (`{url, title, snapshot, shot, new_findings, console_errors}`) after every call.

**Produces:** nothing written by hand -- `drive` writes the action log, redacts secrets, stamps
the step window, runs the engine's measurement checks, and appends every step/shot/finding event
itself (`references/goals.md` section 5). Your own output is limited to a *judgment* finding you
personally observed and the engine's own checks would not catch, filed via `flow-review event
--run DIR --type finding ...`, and at most one failing screenshot returned to the orchestrator,
only when a verdict genuinely depends on seeing it.

You never fix anything, never edit product code, never talk to the user, and never vote on
severity.

## Model profile

| profile | model |
|---|---|
| lean | haiku |
| default | sonnet |
| max | opus |

The orchestrator resolves your dispatch model by calling `flow-review model explorer` (or
`config.resolve_model(cfg, "explorer")` directly), never by reading this table at runtime -- this
table is a mirror of `config.PROFILES["*"]["explorer"]` in `flow_review/config.py`, kept here so a
human reading this file does not have to open the engine source to know your tier.
````

`plugins/flow-review/agents/fr-cold-eyes.md`:

````markdown
---
name: fr-cold-eyes
description: Auto-mode pass 1. A UI-only explorer that has read no code and no docs, writing down
  what it thinks the app is for from the interface alone. Drives the browser exclusively through
  `flow-review drive`. Feeds fr-explorer's pass 2 (docs) and the hidden-feature discoverability
  metric (a function only pass 2 revealed).
model: sonnet
tools: Read, Bash, Glob, Grep
---

# fr-cold-eyes

Role key: `cold-eyes`. You are the first pass of auto mode (`references/goals.md`). You have not
read this project's code, README, or docs -- only the running surface in front of you. Explore it
as a brand-new user would; drive what you find with the same evidence and stuck discipline as
`fr-explorer` (`references/testing.md`, `references/evidence.md`, `references/stuck.md`).

**Your only interface to a web surface is the `flow-review drive` CLI** (A-24), exactly as
`fr-explorer` uses it (`references/goals.md` section 5): `goto`, `click`, `fill`, `press`, `look`,
`flow-begin`, `flow-end`. **You do not have, and must never reach for, Playwright, Puppeteer, an
MCP browser tool, or any other means of touching a browser.** Your `tools` frontmatter is
`Read, Bash, Glob, Grep` -- `Bash` is how you invoke `flow-review drive ...`.

**Consumes:** the surface's config entry, nothing else -- no doc paths, no route registry, no
OpenAPI spec; `flow-review drive`'s compact JSON response after every call.

**Produces:** nothing written by hand, same as `fr-explorer` -- `drive` writes the action log,
redacts, measures, and emits every step/shot/finding event itself; a goal list (what you believe
the app is for) that pass 2 diffs against the real docs. A function pass 2 finds that you missed
is recorded by the orchestrator via `ledger.record_miss(ledger, function, run_id)`; once
`ledger.missed_twice(ledger, function)` is true for that function, it becomes a `P2`
discoverability finding (A-8) -- never `P1`, never sent to `fr-verifier`.

## Model profile

| profile | model |
|---|---|
| lean | haiku |
| default | sonnet |
| max | opus |
````

`plugins/flow-review/agents/fr-lens.md`:

````markdown
---
name: fr-lens
description: Judgment critique over one screen's evidence bundle, evaluated against every lens the
  surface's kind defines in a single call (never one dispatch per lens). Evidence text comes first
  in the prompt for cache reuse, crops second. Files P2 findings directly as opinion; hands P0/P1
  to validation, never votes on them itself.
model: sonnet
tools: Read
---

# fr-lens

Role key: `lens`. You are handed one screen's evidence bundle for one surface and evaluate it
against every lens `references/lenses/{ui,api,cli}.md` defines for that surface's `kind`, in this
single call -- never dispatched once per lens.

**Consumes:** the evidence bundle, text first (measurements, computed styles, captured bodies,
stdout/stderr) then screenshot crops second, so the text portion stays cacheable across repeated
calls on the same screen; suppressions for your surface via
`ledger.suppressions_for(ledger, rule)` -- these derive from finding state (`false-positive`,
`wont-fix`), there is no separate suppression store -- injected before you run.

**Produces:** a JSON array of finding objects shaped `{surface_id, flow_id, rule, route, locator,
sev, text, evidence, disposition}` -- `disposition: opinion` for `sev: P2`, `disposition: judgment`
for `P0`/`P1`. Cross-rubric observations outside your own lens are `context` notes, never votes --
there is no consensus rule in this design.

## Model profile

| profile | model |
|---|---|
| lean | haiku |
| default | sonnet |
| max | opus |
````

`plugins/flow-review/agents/fr-replay-repair.md`:

````markdown
---
name: fr-replay-repair
description: Repairs a recorded action log when `flow-review replay` reports a divergence --
  the recorded semantic locator no longer resolves, or a step's checkpoint no longer matches.
  Starts on Haiku; escalates to Sonnet only when the divergence is not a simple locator drift.
model: haiku
tools: Read, Bash
---

# fr-replay-repair

Role key: `replay-repair`. `flow-review replay` runs with no LLM in the loop and exits non-zero on
a divergence, writing `divergences.json`. You are dispatched only when that file is non-empty, one
call per diverging flow.

**Consumes:** `divergences.json` for your flow; the live surface, to re-locate the diverging step;
the action-log format (B2).

**Produces:** either a corrected action-log step, or an escalation report if the divergence is not
a locator problem. On escalation the orchestrator re-dispatches you at `sonnet`
(`flow-review model replay-repair` under the `max` profile, or an explicit `role_overrides`
escalation) for the same flow with the same context.

## Model profile

| profile | model |
|---|---|
| lean | haiku |
| default | haiku |
| max | sonnet |
````

`plugins/flow-review/agents/fr-triage.md`:

````markdown
---
name: fr-triage
description: Haiku triage -- stuck classification (product vs harness vs unknown), fuzzy dedup
  when a fingerprint misses but an open finding exists on the same flow+rule+route (A-6), and
  ledger reconciliation after a batch of transitions. Cheap and high-volume by design.
model: haiku
tools: Read
---

# fr-triage

Role key: `triage`. You run the classification calls that do not need a strong model: stuck-episode
classification (`references/stuck.md`, PRODUCT-stuck / HARNESS-stuck / UNKNOWN), the fuzzy-dedup
decision when `ledger.fingerprint` misses but `ledger.find_alias_candidates(ledger, flow_id, rule,
route)` returns a candidate (A-6 -- you decide same/new and the orchestrator records your verdict
via `ledger.record_alias(ledger, canonical_id, alias_fingerprint)`), and reconciliation
(`ledger.reconcile(ledger, findings, flows_run, run_id, alias_decisions=None)`).

**Consumes:** the stuck report; the candidate pair for a dedup call; `ledger.fingerprint`,
`ledger.find_alias_candidates`.

**Produces:** a classification (`PRODUCT-stuck` / `HARNESS-stuck` / `UNKNOWN`) or a same/new dedup
verdict. You never set final severity on a `P0`/`P1` judgment finding -- that is `fr-verifier`'s
call; a `P2` finding's severity stands as the lens proposed it.

## Model profile

| profile | model |
|---|---|
| lean | haiku |
| default | haiku |
| max | sonnet |
````

`plugins/flow-review/agents/fr-verifier.md`:

````markdown
---
name: fr-verifier
description: Verifies P0/P1 judgment findings after their ephemeral replay. May refute a finding
  ONLY with measured or replayed evidence -- never with taste, never by re-reading the same
  screenshot and disagreeing. If it cannot refute that way, the finding stands. Opus by default;
  never drops below Sonnet even on the lean profile.
model: opus
tools: Read, Bash
---

# fr-verifier

Role key: `verifier`. You are dispatched once per `P0`/`P1` judgment finding, after the ephemeral
repro replay (A-3, `<run_dir>/repro/`) has already run.

**Consumes:** the original finding; the ephemeral replay's result; the live surface, if you need
one more measurement.

**Produces:** a verdict of `stands` or `refuted`. A `refuted` verdict is not just a reason string --
`resolve_after_verifier` (C5, `flow_review/validate.py`) requires you to also supply
`evidence = {"kind": "measurement" | "replay", "ref": "<path relative to run_dir>"}`, where `ref`
names a real file you actually produced (a fresh measurement you took, or the replay's own
output) under the run folder. **If you cannot point at such a file, you cannot return `refuted` --
return `stands` instead.** A `reason` with no matching `evidence` file raises inside
`resolve_after_verifier` and the orchestrator treats that exactly like a `stands` verdict, so
there is no benefit to asserting a refutation you cannot back with a file: the finding stands
either way, and an honest `stands` is the more useful signal to whoever reads the report.

Once you do supply a valid `evidence` ref, both your `reason` and the `evidence["ref"]` are passed
to `flow_review.triage.apply` (the one case where `apply`'s `reason` argument is required) --
`reason` lands in `LedgerEntry.reason`, and the evidence ref is appended into `LedgerEntry.evidence`.
A refuted finding is never deleted -- it stays in the ledger and in the report's collapsed
sections, reason and evidence ref both visible.

## Model profile

| profile | model |
|---|---|
| lean | sonnet |
| default | opus |
| max | opus |
````

  `plugins/flow-review/test_agents.py` -- asserts the Markdown mirror matches `config.PROFILES`
  exactly, so the two can never silently drift apart:

```python
from __future__ import annotations

import re
from pathlib import Path

import pytest

from flow_review.config import PROFILES, ROLES

ROOT = Path(__file__).resolve().parent
AGENTS = ROOT / "agents"

VALID_MODELS = {"haiku", "sonnet", "opus"}
ROLE_TO_FILE = {role: f"fr-{role}.md" for role in ROLES}


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} has no frontmatter"
    front = text.split("---", 2)[1]
    out: dict[str, str] = {}
    for line in front.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip()
    return out


def _profile_table(text: str) -> dict[str, str]:
    body = text.split("## Model profile", 1)[1]
    table: dict[str, str] = {}
    for line in body.splitlines():
        m = re.match(r"\|\s*(lean|default|max)\s*\|\s*(haiku|sonnet|opus)\s*\|", line.strip(), re.I)
        if m:
            table[m.group(1).lower()] = m.group(2).lower()
    return table


@pytest.mark.parametrize("role", ROLES)
def test_agent_file_exists(role):
    assert (AGENTS / ROLE_TO_FILE[role]).is_file(), f"missing agents/{ROLE_TO_FILE[role]}"


@pytest.mark.parametrize("role", ROLES)
def test_agent_has_required_frontmatter(role):
    front = _frontmatter(AGENTS / ROLE_TO_FILE[role])
    for key in ("name", "description", "model", "tools"):
        assert key in front, f"{ROLE_TO_FILE[role]} frontmatter missing {key!r}"
    assert front["model"] in VALID_MODELS
    assert front["model"] != "inherit"


@pytest.mark.parametrize("role", ROLES)
def test_agent_frontmatter_model_mirrors_default_profile(role):
    front = _frontmatter(AGENTS / ROLE_TO_FILE[role])
    assert front["model"] == PROFILES["default"][role]


@pytest.mark.parametrize("role", ROLES)
def test_agent_profile_table_mirrors_config_profiles_exactly(role):
    text = (AGENTS / ROLE_TO_FILE[role]).read_text(encoding="utf-8")
    assert "## Model profile" in text
    table = _profile_table(text)
    for profile in ("lean", "default", "max"):
        assert table.get(profile) == PROFILES[profile][role], (
            f"{ROLE_TO_FILE[role]} {profile!r} row is {table.get(profile)!r}, "
            f"config.PROFILES says {PROFILES[profile][role]!r}"
        )


def test_verifier_never_drops_below_sonnet_in_any_profile():
    text = (AGENTS / "fr-verifier.md").read_text(encoding="utf-8")
    table = _profile_table(text)
    assert table["lean"] in {"sonnet", "opus"}


def test_no_agent_uses_inherit_anywhere():
    for role in ROLES:
        text = (AGENTS / ROLE_TO_FILE[role]).read_text(encoding="utf-8")
        assert re.search(r"model:\s*inherit", text, re.I) is None


# --- A-24: the drive CLI is the only browser interface -----------------------------------

BANNED_BROWSER_TOOLS = (
    "playwright", "puppeteer", "mcp__playwright", "mcp__puppeteer", "mcp__browser",
    "browser_navigate", "browser_click", "browser_screenshot",
)


@pytest.mark.parametrize("role", ["explorer", "cold-eyes"])
def test_explorer_and_cold_eyes_name_the_drive_cli_as_their_browser_interface(role):
    text = (AGENTS / ROLE_TO_FILE[role]).read_text(encoding="utf-8")
    assert "flow-review drive" in text


@pytest.mark.parametrize("role", ["explorer", "cold-eyes"])
def test_explorer_and_cold_eyes_tools_frontmatter_includes_bash(role):
    front = _frontmatter(AGENTS / ROLE_TO_FILE[role])
    tools = [t.strip() for t in front["tools"].split(",")]
    assert "Bash" in tools


@pytest.mark.parametrize("role", ["explorer", "cold-eyes"])
def test_explorer_and_cold_eyes_never_name_an_mcp_or_direct_browser_tool(role):
    front = _frontmatter(AGENTS / ROLE_TO_FILE[role])
    tools_lower = front["tools"].lower()
    body_lower = (AGENTS / ROLE_TO_FILE[role]).read_text(encoding="utf-8").lower()
    for banned in BANNED_BROWSER_TOOLS:
        assert banned not in tools_lower, f"{ROLE_TO_FILE[role]} tools frontmatter names {banned!r}"
        # the body may only ever mention a banned tool to say it is forbidden -- "never" or
        # "must not" must appear on the same line as the mention, or the mention itself must not
        # exist at all; the simplest correct check is that the banned name never appears at all,
        # since this draft's fr-explorer/fr-cold-eyes text never needs to name a competing
        # browser tool even to prohibit it (it says "an MCP browser tool" generically instead).
        assert banned not in body_lower, f"{ROLE_TO_FILE[role]} body names {banned!r}"
```

- [ ] **Step 4: run all three new test files -> PASS.**
- [ ] **Step 5 (verify): `python -m pytest plugins/flow-review/engine/flow_review/test_config_profiles.py plugins/flow-review/test_agents.py -q`; also `flow-review model verifier` on a config with no override prints `opus`, and with `role_overrides={"verifier":"sonnet"}` prints `sonnet` (manual smoke check, not a unit test, since it exercises the CLI end to end).**
- [ ] **Step 6 (commit): `feat(config,agents): add PROFILES/resolve_model and pinned-model agent definitions that mirror it`.**

- [ ] **Step 7: Commit.**
  ```bash
  git add plugins/flow-review/engine/flow_review/config.py plugins/flow-review/engine/flow_review/test_config_profiles.py plugins/flow-review/engine/flow_review/cli.py plugins/flow-review/agents/fr-explorer.md plugins/flow-review/agents/fr-cold-eyes.md plugins/flow-review/agents/fr-lens.md plugins/flow-review/agents/fr-replay-repair.md plugins/flow-review/agents/fr-triage.md plugins/flow-review/agents/fr-verifier.md plugins/flow-review/test_agents.py
  git commit -m "feat(plugin): model routing in config.py + agent definitions that mirror i (C1)"
  ```


---

### Task C2: SKILL.md orchestrator rewrite

**Executor:** opus · **Depends:** C1, C3, C4, C5, B9 · **Wave:** 10
**Files:**
- `plugins/flow-review/skills/flow-review/SKILL.md` (full rewrite)
- `plugins/flow-review/skills/flow-review/test_skill.py` (full rewrite)

**Interfaces:**
- Consumes: `flow-review plan --mode goal|auto|full|quick [--goal] [--record] --json`;
  `flow-review serve --run DIR`; `flow-review budget check --run DIR --next ROLE --surface ID`;
  `budget.record_usage(run_dir, surface_id, role, tokens)` via `flow-review event --run DIR --type
  usage surface=ID role=ROLE tokens=N`; `flow-review model ROLE`
  (`config.resolve_model`/`config.PROFILES`, C1); `manifest.apply_learnings(path, recorded_hash,
  learnings) -> str` (A6, exact name); `flow-review drive start --surface ID --run DIR [--record]`
  / `flow-review drive stop --surface ID --run DIR` (Canonical Interfaces "Drive", B10, A-24) --
  the orchestrator's own two touches of the drive CLI; every other `drive` verb belongs to the
  dispatched explorer, never to the orchestrator itself; the six agents (C1); the validation
  pipeline (C5); A-20's destructive-opt-in question shape.
- Produces: the orchestrator's run procedure and end-of-run report shape.

- [ ] **Step 1: failing test first, full replacement of `test_skill.py`:**

```python
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILL = ROOT / "SKILL.md"


def _text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_skill_has_valid_frontmatter_with_name_and_description():
    text = _text()
    assert text.startswith("---\n")
    front = text.split("---", 2)[1]
    assert re.search(r"^name:\s*flow-review\s*$", front, re.M)
    assert re.search(r"^description:\s*\S", front, re.M)


def test_skill_declares_both_phases_and_how_it_chooses():
    text = _text()
    assert ".flow-review/config.json" in text
    assert "--reconfigure" in text


def test_skill_names_every_run_mode():
    text = _text()
    for mode in ("goal", "auto", "full", "quick"):
        assert re.search(rf"\b{mode}\b", text), f"SKILL.md never names the {mode!r} mode"


def test_skill_names_every_reference_it_relies_on():
    text = _text()
    for name in (
        "setup.md", "goals.md", "testing.md", "evidence.md", "stuck.md", "validation.md",
        "lenses/ui.md", "lenses/cli.md", "lenses/api.md",
    ):
        assert name in text, f"SKILL.md never points at {name}"


def test_skill_names_the_plan_command_for_the_go_gate():
    text = _text()
    assert "flow-review plan" in text
    assert "--mode" in text


def test_skill_launches_serve_and_prints_the_url():
    text = _text()
    assert "flow-review serve" in text
    assert re.search(r"print.{0,60}(url|link|address)", text, re.I)


def test_skill_starts_drive_per_web_surface_before_dispatching_explorers():
    text = _text()
    assert "flow-review drive start" in text
    assert "--surface" in text.split("flow-review drive start", 1)[1][:120]


def test_skill_stops_drive_at_run_end():
    text = _text()
    assert "flow-review drive stop" in text


def test_skill_checks_budget_before_every_dispatch_with_surface():
    text = _text()
    assert "flow-review budget check" in text
    assert "--next" in text and "--surface" in text
    assert re.search(r"before every dispatch|before each dispatch|before dispatching", text, re.I)


def test_skill_logs_usage_via_the_usage_event():
    text = _text()
    assert re.search(r"--type usage", text)
    assert "record_usage" in text or "budget.record_usage" in text


def test_skill_resolves_model_via_the_model_command():
    text = _text()
    assert "flow-review model" in text


def test_skill_names_manifest_apply_learnings_explicitly():
    text = _text()
    assert "manifest.apply_learnings" in text


def test_skill_states_record_is_opt_in():
    text = _text()
    assert re.search(r"record.{0,80}(opt-in|off by default)", text, re.I | re.S)


def test_skill_states_no_interview_after_go():
    text = _text()
    assert re.search(r"no (further )?(question|interview).{0,80}after (the )?go", text, re.I | re.S)


def test_skill_states_one_multiselect_destructive_question_in_every_mode():
    text = _text()
    assert re.search(r"multi-select", text, re.I)
    assert re.search(r"persistent", text, re.I)
    assert re.search(r"quick", text, re.I)
    assert re.search(r"default.{0,10}no", text, re.I)


def test_skill_states_missing_creds_offers_to_save_to_env_file():
    text = _text()
    assert ".flow-review/.env" in text
    assert re.search(r"offer.{0,40}save", text, re.I)


def test_skill_names_all_six_agents():
    text = _text()
    for role in (
        "fr-explorer", "fr-cold-eyes", "fr-lens", "fr-replay-repair", "fr-triage", "fr-verifier",
    ):
        assert role in text, f"SKILL.md never dispatches {role}"


def test_skill_never_mentions_a_consensus_vote():
    text = _text()
    for banned in ("2 or more lenses agree", "consensus", "arbitration pass"):
        assert banned.lower() not in text.lower(), f"SKILL.md still references {banned!r}"


def test_skill_never_fixes_only_logs():
    text = _text()
    assert "never edits product code" in text or "never fixes" in text


def test_skill_report_names_the_hybrid_sections():
    text = _text()
    for phrase in ("needs-attention", "goal card", "opinion", "refuted", "not-exercised"):
        assert phrase.lower() in text.lower(), f"SKILL.md report section missing {phrase!r}"
```

  Step 2: run `python -m pytest plugins/flow-review/skills/flow-review/test_skill.py -q` -> FAIL.

- [ ] **Step 3: the content. Full replacement of**
  `plugins/flow-review/skills/flow-review/SKILL.md`:

````markdown
---
name: flow-review
description: Use when the user asks for an end-to-end flow review, a UX review, a new-user review, a QA pass, or a full flow review of a product across its real surfaces -- an autonomous run that drives the product like a first-time user, gathers real evidence, and returns ranked findings plus a design critique. Also triggers on the literal invocation /flow-review.
---

# flow-review

`flow-review` drives a product end to end the way a first-time user would, gathers evidence from
the real surface rather than an impression of it, and returns ranked findings plus a design
critique. It never fixes anything and never edits product code -- it only logs what it found. The
engine (`flow_review`, invoked as `flow-review <subcommand>`) does every deterministic step; this
skill and its subagents do only the judgment work the engine cannot.

## 1. Which phase am I in

Read `.flow-review/config.json` in the project root before doing anything else.

- **Absent, or `--reconfigure` was passed** -> **setup mode**. State this in one line, hand off to
  `references/setup.md`, and follow it start to finish. Setup also runs `flow-review setup-env`
  and, for a pre-v2 config, `flow-review migrate`.
- **Present, and `--reconfigure` was not passed** -> **run mode**. State this in one line and
  continue with section 2.

Never guess which mode applies from context -- read the file, every time.

## 2. Choosing a mode

`/flow-review <goal>` -- **goal mode**: the stated goal and everything around it (unhappy paths,
interruptions, alternate routes and adjacent features, device/persona variants), all on by
default.

`/flow-review` with no goal -- **auto mode**: `fr-cold-eyes` pass 1 (UI-only, no code, no docs)
then a docs pass 2 (README/docs/routes/OpenAPI); a function only pass 2 found is a discoverability
observation (A-8; `references/goals.md`).

`/flow-review full` -- **full mode**: everything, deep -- every lens, every variant, no trimming.

`/flow-review quick <goal>` -- **quick mode**: the happy path only. No around-variants, no
judgment lenses dispatched. Engine checks, objective failures, and the P0/P1 verifier path still
run in full.

Recording is **off by default** (A-1); it turns on only per run (`record` in the invocation, or a
yes at the GO gate) or sticky per surface (`record: true`). Without either, nothing is written to
`.flow-review/recordings/`.

## 3. Run mode procedure

1. **Plan.** Run `flow-review plan --mode <mode> [--goal "<goal>"] [--record] --json`. It returns
   the planned work per surface, a token estimate per surface (A-19: per-mode unit priors, refined
   by `budget.estimate` once `usage_history.json` has >=3 runs), and gaps: missing credentials, and
   every `persistent`-state surface a destructive action was planned against.
2. **The GO gate.** Present scope, estimate, and gaps once, together, before any surface is
   driven. Exactly two kinds of question are ever asked here, or anywhere else in the run:
   - **Missing credentials** -- named, with an offer to save each one to the gitignored
     `.flow-review/.env` once supplied.
   - **Destructive authority** -- **one multi-select question** listing every `persistent`-state
     surface the plan would touch destructively, asked together, in every mode including `quick`
     (A-20). Default is no for every surface on the list; without an opt-in for a given surface,
     the explorer skips destructive actions there and files them `not-exercised`.
   The user may trim planned work here. **The interview closes permanently at GO** -- no further
   questions reach the user for the rest of the run. Recovery decisions (`references/stuck.md`)
   are never a question.
3. **Serve.** Immediately after GO, launch `flow-review serve --run <RUN_DIR>` and print the URL
   it returns.
4. **Drive sessions.** For every runnable web surface the plan touches, start its drive session
   before any explorer is dispatched against it: `flow-review drive start --surface ID --run DIR
   [--record]` (the `--record` flag mirrors whatever the GO gate resolved for that surface, A-1/
   A-2). This is the orchestrator's only direct use of `drive` -- every other verb (`goto`,
   `click`, `fill`, `press`, `look`, `flow-begin`, `flow-end`) belongs to the dispatched
   `fr-explorer`/`fr-cold-eyes` agent, never to the orchestrator itself (A-24). At run end, after
   the report is assembled (step 7), stop every session that was started: `flow-review drive stop
   --surface ID --run DIR`.
5. **Dispatch, one role at a time, per the plan's schedule.** Before every dispatch run
   `flow-review budget check --run DIR --next ROLE --surface ID`. If the cap
   (`cfg.budget["cap_tokens"]`) would be exceeded, no new LLM work is dispatched for the rest of
   the run; replays and measurements (engine-only) continue regardless, and the report lists what
   was skipped: record each skipped dispatch with
   `flow-review event --run DIR --type status state=not-exercised surface_id=ID flow_id=FLOW
   step=ROLE reason=budget-cap` (the dashboard's not-exercised section reads these). Resolve the dispatch model with `flow-review model ROLE` (backed by
   `config.resolve_model`, C1 -- `role_overrides` win over the profile) and pass it explicitly on
   the dispatch, never `inherit`. After every subagent call returns, log its reported usage with
   `flow-review event --run DIR --type usage surface=ID role=ROLE tokens=N`, which is exactly
   `budget.record_usage` -- the event log is the one source of truth for usage, there is no
   separate usage store the orchestrator writes to directly.
   - **Exploration.** `fr-explorer` per surface toward the goal (goal/full mode), or `fr-cold-eyes`
     pass 1 then `fr-explorer` pass 2 for docs (auto mode) -- `references/goals.md`.
   - **Replay repair.** Where a recorded action log exists and `flow-review replay` reports a
     divergence, `fr-replay-repair` runs once at Haiku, escalating to Sonnet only on a real
     escalation report.
   - **Judgment.** For every screen a `ui`/`api`/`cli` surface produced evidence for (skipped
     entirely in `quick` mode), `fr-lens` runs once per screen against every lens that surface
     kind defines -- never once per lens. `references/lenses/{ui,api,cli}.md` is the rubric;
     suppressions via `ledger.suppressions_for(ledger, rule)` are injected first.
   - **Validation.** Every judgment finding routes through `references/validation.md` (C5): an
     engine check or objective failure is filed on one reproduction; a `P2` judgment finding is
     filed directly as an opinion; a `P0`/`P1` judgment finding gets an ephemeral replay, then
     `fr-verifier` at Opus, which may refute it only with measured or replayed evidence -- enforced
     by `validate.resolve_after_verifier` requiring a real evidence file under the run folder, not
     a reason string alone. If the verifier cannot supply that file, `resolve_after_verifier`
     raises `ValueError`; **catch it and treat the finding as `stands`**, exactly as if the
     verifier had returned `stands` directly -- never let a failed refutation crash the run. A
     successful refutation stays in the ledger with the reason and the evidence ref, never
     deleted.
   - **Triage.** `fr-triage` at Haiku classifies stuck episodes, resolves fuzzy-dedup ties
     (`ledger.find_alias_candidates` / `ledger.record_alias`, A-6), and reconciles the ledger
     (`ledger.reconcile`) after a batch of transitions.
6. **Manifest write-back.** What was learned this run is written back by calling
   `manifest.apply_learnings(path, recorded_hash, learnings)` explicitly -- never a hand-rolled
   rewrite of `flows.md`, and never touching a human-edited file (see `references/setup.md`
   section 8 for the append-only mechanism this reuses). A run that learned nothing calls it with
   an empty `learnings` list; the returned hash only moves when there was something to record.
7. **Report.** Section 4 below. Stop every drive session (step 4) once the report is assembled.

## 4. Agent tiering

The main thread never runs a screenshot-look-tap loop itself. Every surface is driven by a
dispatched subagent; the main thread reads back structured verdicts and stuck reports, never a
transcript of taps. **Screenshots never reach the main thread** -- a subagent keeps every capture
in its own context and returns at most one failing image, only when a verdict genuinely depends on
seeing it.

## 5. The report

The hybrid report, in order (§11 of the design):

1. **Needs-attention list.** Every finding that is new or regressed this run, by severity.
2. **Goal cards.** Reached/blocked per goal, actions taken vs the shortest known route (A-9, a
   goal-card metric only in M1), found cold vs found only from docs (A-8).
3. **Collapsed sections**, each named plainly even when empty: opinions (`P2` judgment findings),
   repeats (unchanged findings folded to a count, `runs_seen`), refuted findings (with the
   verifier's reason), not-exercised items (destructive actions with no opt-in, email verification
   with no configured test inbox, and anything the budget cap caused to be skipped).

A suppressed finding (`false-positive`, `wont-fix`, `accepted`, or `refuted`) is sticky (A-15):
`runs_seen` keeps counting and it stays in the collapsed sections on every later run until a human
reopens it (`flow-review triage ID open`, or the drawer) -- never silently re-promoted by the tool
itself.

Carried forward from the whole design, restated here because a report that violates any of these
is not this tool's report:

- the skill never fixes anything and never edits product code -- it only logs what it found;
- a judgment finding at `P0`/`P1` must survive replay and the verifier before it is filed;
- the interview closes permanently at GO;
- screenshots never reach the main thread;
- stuck is evidence about the product, not merely an obstacle to route around;
- nothing is faked to keep a surface alive.
````

- [ ] **Step 4: re-run both test files -> PASS.**
- [ ] **Step 5 (verify): `python -m pytest plugins/flow-review/skills/flow-review/test_skill.py -q`; grep SKILL.md for every CLI subcommand and Python name it cites (`flow-review plan`, `flow-review serve`, `flow-review budget check`, `flow-review model`, `flow-review event --type usage`, `ledger.suppressions_for`, `ledger.find_alias_candidates`, `ledger.record_alias`, `ledger.reconcile`, `manifest.apply_learnings`) against the Canonical Interfaces block to confirm none drifted while writing.**
- [ ] **Step 6 (commit): `feat(skill): rewrite SKILL.md orchestrator for v2 modes, plan/serve/budget/model, and the hybrid report`.**

- [ ] **Step 7: Commit.**
  ```bash
  git add plugins/flow-review/skills/flow-review/SKILL.md plugins/flow-review/skills/flow-review/test_skill.py
  git commit -m "docs(plugin): skill.md orchestrator rewrite (C2)"
  ```


---

### Task C3: Lens references rewrite (drop the consensus vote, one call per screen, canonical finding shape)

**Executor:** sonnet · **Depends:** C5 · **Wave:** 9
**Files:**
- `plugins/flow-review/skills/flow-review/references/lenses/ui.md`
- `plugins/flow-review/skills/flow-review/references/lenses/api.md`
- `plugins/flow-review/skills/flow-review/references/lenses/cli.md`
- `plugins/flow-review/skills/flow-review/test_references.py` (edit: consensus-language + schema guards)

**Interfaces:**
- Consumes: `ledger.suppressions_for(ledger, rule)`; `references/validation.md` (C5) as the
  destination for `P0`/`P1`.
- Produces: the rubric `fr-lens` (C1) reads; the canonical finding shape
  `{surface_id, flow_id, rule, route, locator, sev, text, evidence, disposition}`.

- [ ] **Step 1: failing test first -- add to `test_references.py`:**

```python
def test_no_lens_file_claims_it_runs_alone_or_never_drives_the_flow():
    for kind in ("ui", "cli", "api"):
        text = (REFS / "lenses" / f"{kind}.md").read_text(encoding="utf-8")
        assert "do not run the flows" not in text.lower()
        assert "you are one lens" not in text.lower()


def test_no_lens_file_requires_two_lenses_to_agree():
    for kind in ("ui", "cli", "api"):
        text = (REFS / "lenses" / f"{kind}.md").read_text(encoding="utf-8")
        assert "2 or more lenses agree" not in text
        assert "consensus" not in text.lower()
        assert "arbitration pass" not in text.lower()


def test_every_lens_file_uses_the_canonical_finding_field_names():
    for kind in ("ui", "cli", "api"):
        text = (REFS / "lenses" / f"{kind}.md").read_text(encoding="utf-8")
        for field in ("surface_id", "flow_id", "rule", "route", "locator", "sev", "text",
                      "evidence", "disposition"):
            assert f'"{field}"' in text, f"lenses/{kind}.md missing field {field!r}"
        # the old v1 field names must be gone, not merely supplemented
        for old in ('"lens"', '"severity"', '"claim"', '"location"'):
            assert old not in text, f"lenses/{kind}.md still uses old field {old!r}"


def test_every_lens_file_states_evidence_text_before_crops():
    for kind in ("ui", "cli", "api"):
        text = (REFS / "lenses" / f"{kind}.md").read_text(encoding="utf-8")
        assert re.search(r"text.{0,40}(before|first).{0,40}(crop|screenshot|image)", text, re.I)


def test_every_lens_file_states_suppressions_are_injected():
    for kind in ("ui", "cli", "api"):
        text = (REFS / "lenses" / f"{kind}.md").read_text(encoding="utf-8")
        assert "suppressions_for" in text


def test_every_lens_file_points_at_validation_not_arbitration():
    for kind in ("ui", "cli", "api"):
        text = (REFS / "lenses" / f"{kind}.md").read_text(encoding="utf-8")
        assert "validation.md" in text
```

  Step 2: run `python -m pytest plugins/flow-review/skills/flow-review/test_references.py -q` ->
  FAIL.

- [ ] **Step 3: the content. Exact section replacements in all three lens files.**

  **`lenses/ui.md`, replace lines 1-9 (the opening) with:**

````markdown
# lenses/ui.md -- UI surface critique lenses

You are handed the evidence bundle for one screen of a UI surface (a web app in a browser, or a
desktop app driven over CDP) and evaluate it in this single call against every lens below --
never dispatched once per lens. `fr-explorer` (or `fr-cold-eyes`) already drove the flow and
captured this evidence; you never drive the surface yourself. You have read nothing else about the
product beyond this file and the evidence you were handed.

The evidence bundle is ordered **text first, crops second**: measurements, computed styles, and
logs come before any screenshot crop, so the text portion of the prompt stays reusable across
repeated calls on the same screen (prompt caching). Suppressions for this surface, from
`ledger.suppressions_for(ledger, rule)`, are injected into your context before you run --
suppressions derive from a finding's state (`false-positive`, `wont-fix`; there is no separate
suppression store) -- a suppressed claim is never re-filed by you.

This project's own visual identity -- its type scale, colour tokens, radius scale and icon system
-- lives wherever the project's config names its token source. Read that source before judging the
`token.color`/`identity`-style lenses below. Do not assume any particular font, colour, or radius
convention holds here; measure against what the project itself declares.
````

  **`lenses/ui.md`, replace the whole of section 1 (the finding schema example and field table)
  with the canonical shape:**

````markdown
## 1. How to file an opinion

One object per finding. Nothing else. No preamble, no summary paragraph, no praise.

```json
{
  "surface_id": "web",
  "flow_id": "d13",
  "rule": "identity",
  "route": "/settings",
  "locator": "role=row,name=Notifications",
  "sev": "P1",
  "text": "The settings toggle row uses an 8px border-radius although the project's token file sets card radius to 0.",
  "evidence": ["shots/settings-d13-04.png", "computed border-radius 8px on div.settings-row (CDP)"],
  "disposition": "judgment"
}
```

| Field | Rule |
|---|---|
| `surface_id` | the surface's `id` from config, exactly |
| `flow_id` | the flow id the finding was observed on. Never omit it. |
| `rule` | your lens name, exactly as titled below (`fingerprint()`'s `rule` argument) |
| `route` | the route template the finding sits on (a URL path, a command, an endpoint) |
| `locator` | the semantic locator (role+name -> testid -> css) for the element, where applicable |
| `sev` | proposed only -- `P0` / `P1` / `P2` |
| `text` | ONE sentence. What is wrong, stated as fact. Not a suggestion, not a question. |
| `evidence` | a list: screenshot paths and/or concrete measurements. "It feels cluttered" is not evidence. |
| `disposition` | mechanically derived from `sev`, never a free choice: `opinion` when `sev` is `P2`; `judgment` when `sev` is `P0` or `P1`. |

`(surface_id, flow_id, rule, route, locator)` is exactly what `ledger.fingerprint(flow_id, rule,
route, locator)` hashes on (A-6) -- get any of the five wrong and the finding fingerprints
differently from what a human reading the report expects.

**Imperatives.**

- Return a JSON array. A lens that finds nothing returns `[]`.
- Silence is not agreement. An empty list means "this lens found nothing in scope", never "this
  surface is approved".
- Never pad. An empty list is a valid, respected result.
- One claim per object. If you have two complaints about one element, file two objects.
- Stay in your rubric. If you notice something outside your lens, it becomes a `context` note
  (section 3), never a finding filed under the wrong `rule`.
- If your claim rests on an impression and a measurement was available and you did not take it,
  say so in `text` and keep `evidence` honest about what was actually measured.

A `P2` finding is filed as `opinion` straight into the ledger -- no replay, no verifier. A `P0` or
`P1` finding routes to `references/validation.md`: an ephemeral replay first, then `fr-verifier`,
which may refute it only with measured or replayed evidence. You never see the outcome of that
routing; your job ends at filing the finding with the correct `sev` and `disposition`.
````

  **`lenses/ui.md`, replace the whole of section 3 (`## 3. Consensus and arbitration` through
  the paragraph before `## 4. Severity ladder`) with:**

````markdown
## 3. No vote -- context notes and validation handoff

There is no consensus rule and no arbitration pass. Every lens's findings stand on their own,
routed by `sev`/`disposition` as above -- not by how many lenses noticed the same thing.

**Objective failures still bypass judgment entirely.** Crash, hang, data loss, wrong content, a
hard rule the project itself marks as a lock, or a failed round trip is an engine-checked or
objective-failure finding, filed on one reproduction -- not yours to file as a lens opinion, and
never softened by one.

**Cross-rubric observations are context, not votes.** If you notice something clearly outside your
own lens's rubric, do not drop it and do not file it under your own `rule`. Attach it as a
`context` note on the finding object nearest it (or a standalone `context`-only object with no
`sev` if nothing else fits) so a human reading the report sees it, without it inflating any lens's
finding count.

See `references/validation.md` for the full pipeline your `P0`/`P1` findings enter after you file
them.
````

  Apply the identical set of edits (opening paragraph, section-1 schema, section-3 replacement) to
  `lenses/api.md` and `lenses/cli.md`, substituting only the surface-specific nouns already present
  in each file's own opening paragraph and worked examples (API: `route` is the method+path,
  `locator` is empty or the field path; CLI: `route` is the subcommand invoked, `locator` is empty
  or the flag name). The section-3 text is identical across all three files -- copy it verbatim.

- [ ] **Step 4: re-run `python -m pytest plugins/flow-review/skills/flow-review/test_references.py -q` -> PASS.**
- [ ] **Step 5 (verify): also re-run the pre-existing lens-registry-parity tests in the same file (`test_every_lens_in_the_registry_declares_a_rubric_in_its_reference_file`, `test_a_rubric_declares_no_lens_the_registry_does_not_have`) to confirm the section edits did not touch any `### Lens -- \`name\`` heading.**
- [ ] **Step 6 (commit): `docs(lenses): drop the consensus vote, adopt the canonical finding shape and disposition routing`.**

- [ ] **Step 7: Commit.**
  ```bash
  git add plugins/flow-review/skills/flow-review/references/lenses/ui.md plugins/flow-review/skills/flow-review/references/lenses/api.md plugins/flow-review/skills/flow-review/references/lenses/cli.md plugins/flow-review/skills/flow-review/test_references.py
  git commit -m "docs(plugin): lens references rewrite (drop the consensus vote, one call p (C3)"
  ```


---

### Task C4: Explorer + goals reference

**Executor:** sonnet · **Depends:** B10, A5 · **Wave:** 8
**Files:**
- `plugins/flow-review/skills/flow-review/references/goals.md` (new)
- `plugins/flow-review/skills/flow-review/test_references.py` (edit: add `goals.md` to `REQUIRED`)

**Interfaces:**
- Consumes (Canonical Interfaces "Drive", B10, A-24): `flow-review drive start --surface ID --run
  DIR [--record]` (one localhost session server per surface, prints `{"surface_id", "port"}`);
  verbs `goto PATH`, `click LOC`, `fill LOC (--text T | --from-env NAME)`, `press KEY`, `look
  [--shot]`, `flow-begin --flow ID`, `flow-end --flow ID --status ok|blocked`, `stop` (all take
  `--surface ID --run DIR`); `LOC` = `--role R --name N | --testid T | --css C`; every call
  returns `{url, title, snapshot, shot, new_findings, console_errors}`. The engine -- never the
  agent -- writes the action log, redacts secrets, stamps the step window, runs the B4 checks, and
  appends step/shot/finding events; `flow-end` saves the log per A-1..A-3. Also:
  `ledger.record_miss(ledger, function, run_id) -> int`, `ledger.missed_twice(ledger, function) ->
  bool` (A-8); `ledger.find_alias_candidates`, `ledger.record_alias` (A-6, exercised by
  `fr-triage`, named here for the explorer's awareness of what happens to a near-miss).
- Produces: the procedure `fr-explorer` and `fr-cold-eyes` (C1) follow. Agents never touch
  Playwright or MCP browser tools directly (A-24) -- `drive` is the only browser interface named
  in this file.

- [ ] **Step 1: failing test first -- extend `test_references.py`:**

```python
def test_goals_reference_exists_and_is_required():
    assert (REFS / "goals.md") in REQUIRED


def test_goals_file_states_the_around_set_and_default_on():
    text = (REFS / "goals.md").read_text(encoding="utf-8")
    for phrase in ("unhappy path", "interruption", "alternate route", "variant"):
        assert phrase in text.lower()
    assert re.search(r"on by default", text, re.I)
    assert re.search(r"quick mode", text, re.I)


def test_goals_file_states_cold_eyes_then_docs_pass():
    text = (REFS / "goals.md").read_text(encoding="utf-8")
    assert re.search(r"pass 1", text, re.I)
    assert re.search(r"pass 2", text, re.I)
    assert re.search(r"no code|not read.{0,20}code|read no code", text, re.I)


def test_goals_file_uses_the_canonical_ledger_functions_for_discoverability():
    text = (REFS / "goals.md").read_text(encoding="utf-8")
    assert "record_miss" in text
    assert "missed_twice" in text
    assert re.search(r"\bP2\b", text)
    assert "P1" not in text.split("record_miss")[0].split("Hidden-feature")[-1]


def test_goals_file_states_path_ratio_metric():
    text = (REFS / "goals.md").read_text(encoding="utf-8")
    assert re.search(r"path.{0,10}ratio|shortest.{0,20}route", text, re.I)


def test_goals_file_states_the_safety_limits():
    text = (REFS / "goals.md").read_text(encoding="utf-8")
    for phrase in ("sandbox only", "test_inbox", "no-test-inbox", "payment-not-sandboxed",
                   "destructive-no-optin", "not-exercised"):
        assert phrase in text, phrase


def test_goals_file_names_the_drive_cli_and_secret_handling():
    text = (REFS / "goals.md").read_text(encoding="utf-8")
    assert "flow-review drive" in text
    assert "--from-env" in text


def test_goals_file_never_claims_the_explorer_writes_its_own_action_log_or_step_events():
    text = (REFS / "goals.md").read_text(encoding="utf-8")
    assert "events.append" not in text
    assert "flow-review event" not in text
    assert re.search(r"explorer.{0,60}(writes|emits|hand-writes).{0,40}(action log|step event)",
                      text, re.I) is None
```

  Step 2: run `python -m pytest plugins/flow-review/skills/flow-review/test_references.py -q` ->
  FAIL.

- [ ] **Step 3: the content.**

  First, edit `test_references.py`'s `REQUIRED` list (owned jointly with C3's and C5's edits to
  the same file -- whichever of C3/C4/C5 merges last rebases onto the others' additions rather
  than overwriting them):

```python
REQUIRED = [
    REFS / "surfaces.md", REFS / "testing.md", REFS / "evidence.md", REFS / "stuck.md",
    REFS / "goals.md", REFS / "validation.md",
    REFS / "lenses" / "ui.md", REFS / "lenses" / "cli.md", REFS / "lenses" / "api.md",
    ROOT / "templates" / "flows.md",
]
```

  New file, `plugins/flow-review/skills/flow-review/references/goals.md`:

````markdown
# goals.md -- what to test, and how a goal is found

This is `fr-explorer`'s and `fr-cold-eyes`'s procedure for deciding what "the flow and everything
around it" means, and for generating a goal when none was given. `testing.md` covers how to drive
a surface once you know what to drive; this file covers what to drive.

## 1. A goal was given (goal mode, full mode)

Test the stated goal, and everything around it -- **all of the following are on by default**,
except in `quick` mode, which tests only the stated goal's happy path and none of what follows:

- **Unhappy paths.** Bad input, a server error or the network going offline partway through, a
  double submit.
- **Interruptions.** Back, refresh, reopen, rotate (mobile), backgrounding and returning.
- **Alternate routes and adjacent features.** Other ways to reach the same outcome, and features
  the goal sits next to that a real user would notice along the way.
- **Device/persona variants.** Widths, light/dark, keyboard-only, screen reader, new vs returning
  user (via stored session state). Where a variant is a pure replay of an already-recorded flow
  under different conditions, it is run by the engine (`flow_review.web.variants`, B7) rather than
  re-explored -- check whether an action log already exists for the base flow first.

## 2. No goal was given (auto mode)

Two passes, always in this order, never merged into one call:

**Pass 1 -- cold eyes (`fr-cold-eyes`).** A UI-only explorer that has read no code and no docs.
Explore the running surface as a brand-new user would and write down what you believe the
product is for and what its main flows are, driving each one with the same evidence and stuck
discipline as goal mode. This pass never opens the README, never greps the source, never reads a
route table.

**Pass 2 -- docs (`fr-explorer`, reusing pass 1's action logs where they resolve cleanly).** Read
the project's README, its own docs, its route table or OpenAPI spec, and diff what they describe
against what pass 1 found. Drive whatever pass 2 adds using the goal-around set from section 1.

## 3. Hidden-feature severity (A-8)

A function pass 2 reveals that no cold-eyes pass has found yet is filed, on its first miss, as a
**goal-card metric only** -- labelled "from docs", never a severity-bearing finding -- and recorded
with `ledger.record_miss(ledger, function, run_id)`. It becomes a `P2` discoverability finding only
once `ledger.missed_twice(ledger, function)` returns true for that function (i.e. it has now been
missed by cold-eyes on 2 separate runs). It is never `P1`, and it is never sent to `fr-verifier` --
`missed_twice` is the only gate on this, not lens discretion.

## 4. Path-ratio (intuitiveness) metric (A-9)

For each goal reached, record the number of actions actually taken against the shortest known
route to the same outcome (the shortest route observed across any run so far). This is a
**goal-card metric only**, never a severity-bearing finding on its own in M1; revisited at M5 with
benchmark data.

## 5. Driving (A-24, B10)

You never touch Playwright or an MCP browser tool directly -- for a web surface, `flow-review
drive` is your only interface to the browser, full stop. It is a localhost session server the
orchestrator starts once per surface before dispatching you (`SKILL.md` section 3); every verb
below talks to that running session, not to a browser you launch yourself.

**Verbs**, all taking `--surface ID --run DIR`:

- `flow-review drive goto PATH` -- navigate.
- `flow-review drive click LOC` -- click an element.
- `flow-review drive fill LOC (--text T | --from-env NAME)` -- fill a field. **Any credential or
  secret value is passed with `--from-env NAME`, naming the config's env-var, never with
  `--text`** -- `--text` is for ordinary, non-secret input only; the engine reads the named
  environment variable itself and the value never appears in your context, your output, or an
  event.
- `flow-review drive press KEY` -- a key press (Enter, Tab, Escape, arrows).
- `flow-review drive look [--shot]` -- read the current state without acting. Plain `look` returns
  the trimmed accessibility-tree text snapshot; add `--shot` only when the text snapshot is
  genuinely insufficient to judge what is on screen (visual layout, colour, an image) -- this is a
  token lever (§4 lever 2, text before images), not a habit. Reach for `--shot` deliberately, not
  on every step.
- `flow-review drive flow-begin --flow ID` / `flow-review drive flow-end --flow ID --status
  ok|blocked` -- bracket every goal (or sub-flow within a goal) you drive. `flow-begin` opens the
  step window the engine stamps against (A-17); `flow-end` is what actually saves the recorded
  action log (A-1..A-3, persisted under `.flow-review/recordings/` when recording is on, otherwise
  as an ephemeral repro in `<run_dir>/repro/` that validation replays once and that dies with the
  run) and closes the window. **Every goal you drive is wrapped in exactly one
  `flow-begin`/`flow-end` pair** -- a goal driven with no `flow-end` never gets recorded or
  measured as a completed flow.

`LOC` (the locator argument to `click`/`fill`) is `--role R --name N | --testid T | --css C`, tried
in that preference order -- the same role+name -> testid -> css hierarchy the whole design uses
elsewhere (A-1).

**Example -- driving a login goal:**

```
flow-review drive flow-begin --surface web --run "$RUN" --flow w03
flow-review drive goto --surface web --run "$RUN" /login
flow-review drive fill --surface web --run "$RUN" --role textbox --name Email --text new-user@example.com
flow-review drive fill --surface web --run "$RUN" --role textbox --name Password --from-env DEMO_PASSWORD
flow-review drive click --surface web --run "$RUN" --role button --name "Sign in"
flow-review drive look --surface web --run "$RUN"
flow-review drive flow-end --surface web --run "$RUN" --flow w03 --status ok
```

**What the engine does that you never do yourself.** Every `drive` call returns one compact JSON
object: `{url, title, snapshot, shot, new_findings, console_errors}`. Read `new_findings` and
`console_errors` off that response -- they are the engine's own measurement of what just happened,
already filed if they cross a threshold. **You never hand-write an action log, and you never emit
a `step` or `shot` event yourself** -- `drive` writes the action log, redacts secrets, stamps the
step window, runs the B4 measurement checks, and appends the step/shot/finding events, all inside
the engine, before the JSON response ever reaches you. Your only remaining reporting job is filing
a *judgment* finding yourself when you observe one the engine's own checks would not catch (an
objective failure you witnessed, or something worth flagging for `fr-lens` to evaluate later) --
via `flow-review event --run DIR --type finding ...`, never by writing to `events.jsonl` directly.

`references/evidence.md` and `references/testing.md` cover the rest of the reporting and driving
discipline; this file only covers scope and the drive verbs themselves. A near-miss on the
fingerprint (`ledger.fingerprint(flow_id, rule, route, locator)`) is not yours to resolve -- that
dedup call is `fr-triage`'s (`ledger.find_alias_candidates` / `ledger.record_alias`, A-6); you just
file the finding honestly and let triage sort out whether it is new.

## 6. Safety limits

- Payments: sandbox only. If a flow needs a real payment method, stop at the payment step and
  file it `not-exercised` (reason: `payment-not-sandboxed`).
- Email verification: use the configured `test_inbox` (Mailpit, Ethereal) to read the message.
  With no `test_inbox` configured, file the verification step `not-exercised` (reason:
  `no-test-inbox`) and continue with the rest of the goal where possible.
- Destructive actions (delete, pay, send, bulk-edit) on a `persistent` surface without this run's
  opt-in: skip them and file them `not-exercised` (reason: `destructive-no-optin`, A-20).
- Credentials come only from the env-var names in config. Never type, echo or log a secret value;
  password fields are masked in every screenshot by the driver.
````

- [ ] **Step 4: re-run `python -m pytest plugins/flow-review/skills/flow-review/test_references.py -q` -> PASS.**
- [ ] **Step 5 (verify): confirm `goals.md` is > 400 chars and has no emoji/BOM (existing `REQUIRED`-file tests already cover this once it's in the list).**
- [ ] **Step 6 (commit): `docs(goals): add the goal-around set, cold-eyes/docs passes, and A-8/A-9 metrics via the canonical ledger functions`.**

- [ ] **Step 7: Commit.**
  ```bash
  git add plugins/flow-review/skills/flow-review/references/goals.md plugins/flow-review/skills/flow-review/test_references.py
  git commit -m "docs(plugin): explorer + goals reference (C4)"
  ```


---

### Task C5: Validation pipeline

**Executor:** opus · **Depends:** A5, B3 · **Wave:** 8
**Files:**
- `plugins/flow-review/engine/flow_review/validate.py` (new)
- `plugins/flow-review/engine/flow_review/test_validate.py` (new)
- `plugins/flow-review/skills/flow-review/references/validation.md` (new)

**Interfaces:**
- Consumes: `LedgerEntry(id, fingerprint, surface_id, flow_id, rule, route, locator, sev, text,
  evidence: list[str] = [], state="open", runs_seen=1, first_run="", last_run="", aliases=[],
  reason="")` and `ledger.fingerprint(flow_id, rule, route, locator)`; the ephemeral repro log
  under `<run_dir>/repro/` (A-3).
- Produces: `route()` / `resolve_after_replay()` / `resolve_after_verifier()`, called by the
  orchestrator (C2) and used by `fr-verifier` (C1) as its brief's mechanism;
  `references/validation.md`, the human-readable mirror.

- [ ] **Step 1: failing test first, `plugins/flow-review/engine/flow_review/test_validate.py`:**

```python
from __future__ import annotations

import pytest

from flow_review.validate import (
    Disposition,
    Verdict,
    resolve_after_replay,
    resolve_after_verifier,
    route,
)


def _finding(disposition: Disposition, sev: str = "P1") -> dict:
    return {
        "disposition": disposition, "sev": sev,
        "surface_id": "web", "flow_id": "w03", "rule": "identity",
        "route": "/settings", "locator": "role=row,name=Notifications",
        "text": "example claim", "evidence": ["example evidence"],
    }


def test_engine_check_routes_straight_to_filed():
    assert route(_finding(Disposition.ENGINE, "P1")) == "file"


def test_objective_failure_routes_straight_to_filed():
    assert route(_finding(Disposition.OBJECTIVE, "P0")) == "file"


def test_judgment_p2_routes_to_opinion_never_replay():
    assert route(_finding(Disposition.JUDGMENT, "P2")) == "opinion"


@pytest.mark.parametrize("sev", ["P0", "P1"])
def test_judgment_p0_p1_routes_to_replay(sev):
    assert route(_finding(Disposition.JUDGMENT, sev)) == "replay"


def test_unreplayable_p0_p1_still_reaches_the_verifier():
    finding = _finding(Disposition.JUDGMENT, "P0")
    assert resolve_after_replay(finding, replay_result=None) == "verify"


def test_replay_confirming_the_claim_still_goes_to_the_verifier():
    finding = _finding(Disposition.JUDGMENT, "P1")
    assert resolve_after_replay(finding, replay_result={"confirmed": True}) == "verify"


def test_resolve_after_replay_rejects_a_non_replay_route():
    finding = _finding(Disposition.JUDGMENT, "P2")
    with pytest.raises(ValueError):
        resolve_after_replay(finding, replay_result=None)


def test_verifier_stands_returns_the_stands_verdict_with_no_reason_or_evidence_required(tmp_path):
    finding = _finding(Disposition.JUDGMENT, "P0")
    verdict, reason = resolve_after_verifier(
        finding, verifier_verdict="stands", reason=None, evidence=None, run_dir=tmp_path,
    )
    assert verdict == Verdict.STANDS
    assert reason is None


def test_verifier_refuted_requires_a_reason(tmp_path):
    finding = _finding(Disposition.JUDGMENT, "P0")
    evidence = {"kind": "measurement", "ref": "repro/contrast.json"}
    (tmp_path / "repro").mkdir()
    (tmp_path / "repro" / "contrast.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        resolve_after_verifier(
            finding, verifier_verdict="refuted", reason="", evidence=evidence, run_dir=tmp_path,
        )


def test_verifier_refuted_requires_evidence_at_all():
    """A "refuted" verdict with evidence=None is exactly the "taste" refutation the brief
    forbids -- it must raise, never silently pass through as a bare reason string."""
    finding = _finding(Disposition.JUDGMENT, "P0")
    with pytest.raises(ValueError):
        resolve_after_verifier(
            finding, verifier_verdict="refuted", reason="looked wrong to me",
            evidence=None, run_dir=None,
        )


def test_verifier_refuted_rejects_an_evidence_kind_outside_the_two_known_values(tmp_path):
    finding = _finding(Disposition.JUDGMENT, "P0")
    (tmp_path / "shot.png").write_bytes(b"")
    evidence = {"kind": "impression", "ref": "shot.png"}
    with pytest.raises(ValueError):
        resolve_after_verifier(
            finding, verifier_verdict="refuted", reason="it looks off",
            evidence=evidence, run_dir=tmp_path,
        )


def test_verifier_refuted_rejects_a_missing_evidence_file(tmp_path):
    finding = _finding(Disposition.JUDGMENT, "P0")
    evidence = {"kind": "replay", "ref": "repro/does-not-exist.json"}
    with pytest.raises(ValueError):
        resolve_after_verifier(
            finding, verifier_verdict="refuted",
            reason="replayed and it completed cleanly",
            evidence=evidence, run_dir=tmp_path,
        )


def test_verifier_refuted_with_a_real_evidence_file_returns_refuted(tmp_path):
    finding = _finding(Disposition.JUDGMENT, "P0")
    (tmp_path / "repro").mkdir()
    (tmp_path / "repro" / "contrast.json").write_text('{"ratio": 5.1}', encoding="utf-8")
    evidence = {"kind": "measurement", "ref": "repro/contrast.json"}
    verdict, reason = resolve_after_verifier(
        finding, verifier_verdict="refuted",
        reason="replayed measurement: contrast ratio 5.1:1, claim of 3.8:1 not reproduced",
        evidence=evidence, run_dir=tmp_path,
    )
    assert verdict == Verdict.REFUTED
    assert reason
    # the orchestrator is responsible for writing `reason` into LedgerEntry.reason and
    # appending `evidence["ref"]` into LedgerEntry.evidence -- this module only validates and
    # returns them; it does not touch the ledger itself (see C6, `triage.apply`).


def test_verifier_verdict_outside_the_two_known_values_is_rejected(tmp_path):
    finding = _finding(Disposition.JUDGMENT, "P0")
    with pytest.raises(ValueError):
        resolve_after_verifier(
            finding, verifier_verdict="probably fine", reason="taste",
            evidence=None, run_dir=tmp_path,
        )


def test_orchestrator_catches_a_bad_refutation_and_the_finding_stands(tmp_path):
    """This is the documented fallback (validation.md): if the verifier cannot supply a real
    evidence ref, resolve_after_verifier raises ValueError, and the ORCHESTRATOR is responsible
    for catching it and treating the finding as `stands` rather than propagating the exception
    into a crashed run. This test only proves the raise happens; the catch-and-stand behavior
    lives in the orchestrator (SKILL.md, C2), not in this module."""
    finding = _finding(Disposition.JUDGMENT, "P0")
    try:
        resolve_after_verifier(
            finding, verifier_verdict="refuted", reason="it just looks wrong",
            evidence=None, run_dir=tmp_path,
        )
        raised = False
    except ValueError:
        raised = True
    assert raised
```

  Step 2: run `python -m pytest plugins/flow-review/engine/flow_review/test_validate.py -q` ->
  FAIL.

- [ ] **Step 3: the content.**

  `plugins/flow-review/engine/flow_review/validate.py`:

```python
"""The validation state machine (v2 design §7).

Every finding that reaches the ledger has already been through exactly one of three routes:

1. An engine check or an objective failure (crash, hang, data loss, wrong content, a failed
   round trip) is filed on one reproduction. No judgment, no vote, no replay.
2. A judgment finding at P2 is filed directly as an opinion.
3. A judgment finding at P0/P1 is replayed once (free, ephemeral -- `<run_dir>/repro/`, never
   reused, never fed to `flow-review replay`, A-3), then handed to `fr-verifier`, who may refute
   it ONLY by attaching new measured or replayed evidence -- enforced mechanically by requiring an
   `evidence = {"kind": "measurement"|"replay", "ref": "<path under run_dir>"}` object whose `ref`
   must exist on disk, not merely a persuasive `reason` string. A refuted finding is never
   deleted: `flow_review.triage.apply(ledger_path, finding_id, "refuted", reason=verifier_reason)`
   is how the verdict actually lands in the ledger (C6) -- this module only decides routing, not
   I/O.

Findings here are plain dicts shaped `{surface_id, flow_id, rule, route, locator, sev, text,
evidence, disposition}` -- the same shape `fr-lens` files and `ledger.fingerprint(flow_id, rule,
route, locator)` hashes on -- so nothing here needs its own parallel finding type.
"""
from __future__ import annotations

from enum import Enum

VALID_SEVERITIES = ("P0", "P1", "P2")


class Disposition(str, Enum):
    ENGINE = "engine"
    OBJECTIVE = "objective"
    JUDGMENT = "judgment"


class Verdict(str, Enum):
    FILED = "filed"
    OPINION = "opinion"
    STANDS = "stands"
    REFUTED = "refuted"


def route(finding: dict) -> str:
    """Where a freshly-filed finding goes next, before any replay or verifier call has run.

    Returns "file" (engine/objective), "opinion" (P2 judgment), or "replay" (P0/P1 judgment).
    """
    sev = finding["sev"]
    if sev not in VALID_SEVERITIES:
        raise ValueError(f"sev must be one of {VALID_SEVERITIES}, got {sev!r}")
    disposition = finding["disposition"]
    if disposition in (Disposition.ENGINE, Disposition.OBJECTIVE):
        return "file"
    if sev == "P2":
        return "opinion"
    return "replay"


def resolve_after_replay(finding: dict, replay_result: dict | None) -> str:
    """Always "verify" for a P0/P1 judgment finding, regardless of what the replay found.

    The replay's outcome is evidence the verifier will weigh -- never itself a filing decision. A
    replay that could not run at all (`replay_result=None`) still goes to the verifier rather than
    being silently filed or dropped.
    """
    if route(finding) != "replay":
        raise ValueError("resolve_after_replay is only for P0/P1 judgment findings")
    return "verify"


EVIDENCE_KINDS = ("measurement", "replay")


def resolve_after_verifier(
    finding: dict,
    verifier_verdict: str,
    reason: str | None,
    evidence: dict | None,
    run_dir,
) -> tuple[Verdict, str | None]:
    """The final verdict for a P0/P1 judgment finding, after the verifier has looked at it.

    `verifier_verdict` is exactly "stands" or "refuted". "A non-empty reason string" is not
    mechanically enforceable -- nothing stops a verifier typing "it just looks wrong" into
    `reason` and calling that a refutation. §7.3 says the verifier may refute ONLY with measured
    or replayed evidence, so refutation is gated on a real artifact, not on prose: a "refuted"
    verdict requires `evidence = {"kind": "measurement" | "replay", "ref": "<path relative to
    run_dir>"}`, and `run_dir / evidence["ref"]` must actually exist on disk. Any of the following
    raises `ValueError` instead of returning `REFUTED`: `evidence` is `None`; `evidence["kind"]`
    is not one of `EVIDENCE_KINDS`; the referenced file does not exist under `run_dir`.

    The orchestrator (SKILL.md, C2) is responsible for catching that `ValueError` and treating the
    finding as `stands` -- a verifier that cannot produce a real evidence ref has, by definition,
    not refuted anything, and a run must not crash because one subagent's refutation attempt was
    unfounded. This function only validates and raises; it never itself falls back to `stands` on
    a bad evidence object, so the fallback path is visible to (and owned by) the caller.
    """
    if verifier_verdict == "stands":
        return Verdict.STANDS, reason
    if verifier_verdict == "refuted":
        if not reason:
            raise ValueError("a refuted verdict must carry a non-empty reason")
        if evidence is None:
            raise ValueError("a refuted verdict must carry a measured or replayed evidence ref")
        if evidence.get("kind") not in EVIDENCE_KINDS:
            raise ValueError(
                f"evidence kind must be one of {EVIDENCE_KINDS}, got {evidence.get('kind')!r}"
            )
        ref = evidence.get("ref")
        if not ref or not (run_dir / ref).is_file():
            raise ValueError(f"evidence ref {ref!r} does not exist under {run_dir}")
        return Verdict.REFUTED, reason
    raise ValueError(f"verifier_verdict must be 'stands' or 'refuted', got {verifier_verdict!r}")
```

  New file, `plugins/flow-review/skills/flow-review/references/validation.md`:

````markdown
# validation.md -- how a finding earns its place in the ledger

This is the human-readable mirror of `flow_review.validate`'s state machine (§7 of the design).
`fr-lens` files findings; this file (and `validate.py`) decides what happens to them next.
`fr-verifier` reads this file as its brief, alongside `agents/fr-verifier.md`.

## The three routes

1. **Engine check or objective failure -> filed, no judgment involved.** Contrast, token
   adherence, rect overlap/offscreen/target-size, HTTP status, exit codes, and objective failures
   (crash, hang, data loss, wrong content, a failed round trip) are filed on one reproduction.
2. **A `P2` judgment finding -> filed as opinion.** Straight to the ledger with
   `disposition: opinion`. No replay, no verifier.
3. **A `P0`/`P1` judgment finding -> ephemeral replay, then the verifier.** The finding's action
   log (or the flow it came from) replays once against the live surface, free, into
   `<run_dir>/repro/` -- ephemeral: never reused, never feeds `flow-review replay` (A-3). The
   verifier then returns exactly one of two verdicts:
   - **stands** -- the default outcome. The finding is filed as-is.
   - **refuted** -- only ever returned with a mandatory `evidence` object attached, shaped
     `{"kind": "measurement" | "replay", "ref": "<path relative to run_dir>"}`, where
     `run_dir / ref` is a real file the verifier actually produced or replayed against.
     `resolve_after_verifier` checks the file exists before it will return `REFUTED` at all -- a
     `reason` string alone, however persuasive, is not mechanically checkable and is never
     sufficient on its own. Taste is never a valid refutation, and now cannot even masquerade as
     one: there is no code path that accepts `refuted` without a verified evidence ref.

**If the verifier cannot supply a real evidence ref**, `resolve_after_verifier` raises
`ValueError` rather than silently returning `STANDS` itself. **The orchestrator catches that
`ValueError` and treats the finding as `stands`** -- a failed refutation attempt is not a crash,
it is exactly the same outcome as the verifier calling `stands` directly. This split (the module
raises, the orchestrator decides what a raise means) keeps `validate.py` free of any I/O or
run-level error-handling policy.

The verdict lands in the ledger via `flow_review.triage.apply(ledger_path, finding_id, state,
reason=None)` -- `state="refuted"` with the verifier's `reason` written into `LedgerEntry.reason`,
and the evidence object's `ref` appended into `LedgerEntry.evidence` (the orchestrator's job, once
`resolve_after_verifier` has returned `REFUTED`; the finding is otherwise simply left `open`).

## Refuted findings are never deleted

A refuted finding stays in the ledger (`LedgerEntry.state == "refuted"`, `reason` holding the
verifier's explanation, `evidence` holding the measured/replayed ref that backs it). The report's
collapsed "refuted" section shows it, reason and evidence ref included. This is also how the
planted-bug benchmark app (§7.6, M5) measures recall on every release: a refutation that quietly
disappeared, or that rested on an unverifiable claim, would be unfalsifiable.

## What this file does not decide

Severity (`sev`) is set by the lens that filed the finding, or by the product-stuck floor rule in
`lenses/{ui,api,cli}.md` section 4 -- never by this pipeline. This pipeline only decides whether a
filed finding survives, and how.
````

- [ ] **Step 4: re-run `python -m pytest plugins/flow-review/engine/flow_review/test_validate.py -q` -> PASS.**
- [ ] **Step 5 (verify): `python -m pytest plugins/flow-review/engine/flow_review/test_validate.py -q` plus `plugins/flow-review/skills/flow-review/test_references.py -q` (once C4's `REQUIRED` edit has landed, `validation.md`'s presence and stub-guard are covered there too).**
- [ ] **Step 6 (commit): `feat(validate): add the P0/P1 replay-then-verify state machine and its reference doc`.**

- [ ] **Step 7: Commit.**
  ```bash
  git add plugins/flow-review/engine/flow_review/validate.py plugins/flow-review/engine/flow_review/test_validate.py plugins/flow-review/skills/flow-review/references/validation.md
  git commit -m "feat(plugin): validation pipeline (C5)"
  ```


---

### Task C6: Triage + fix briefs

**Executor:** sonnet · **Depends:** A5, B2 · **Wave:** 6
**Files:**
- `plugins/flow-review/engine/flow_review/triage.py` (new)
- `plugins/flow-review/engine/flow_review/test_triage.py` (new)
- `plugins/flow-review/agents/fr-triage.md` (extend the C1 scaffold with the operational brief)

**Interfaces:**
- Consumes: `ledger.load(path) -> Ledger`, `ledger.save(ledger, path)`, `ledger.STATES`,
  `LedgerEntry` fields exactly as given (`id, fingerprint, surface_id, flow_id, rule, route,
  locator, sev, text, evidence, state, runs_seen, first_run, last_run, aliases, reason`); the path
  is always `<project_root>/.flow-review/findings.json`.
- Produces (Canonical Interfaces, "Triage"): `flow_review.triage.apply(ledger_path: Path,
  finding_id: str, state: str, reason: str | None = None) -> LedgerEntry` -- loads, validates
  `state` against `ledger.STATES`, sets state and reason, and saves. `reason` required only for
  `refuted`. The CLI `flow-review triage ID STATE [--reason]` and the dashboard `POST /triage` both
  call `apply` directly -- there is exactly one triage code path. Reopen = `apply(..., "open")`
  (A-15).

- [ ] **Step 1: failing test first, `plugins/flow-review/engine/flow_review/test_triage.py`:**

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from flow_review import ledger as ledger_mod
from flow_review.triage import build_fix_brief, apply


@pytest.fixture
def ledger_path(tmp_path: Path) -> Path:
    path = tmp_path / "findings.json"
    entry = ledger_mod.LedgerEntry(
        id="f1", fingerprint="abc123", surface_id="web", flow_id="w03",
        rule="identity", route="/settings", locator="role=row,name=Notifications",
        sev="P1", text="border-radius diverges from the token", evidence=["computed 8px"],
        state="open", runs_seen=1, first_run="2026-09-23T00:00:00.000Z",
        last_run="2026-09-23T00:00:00.000Z", aliases=[], reason="",
    )
    empty = ledger_mod.Ledger(entries=[entry]) if hasattr(ledger_mod, "Ledger") else None
    ledger_mod.save(empty if empty is not None else [entry], path)
    return path


def test_apply_rejects_an_unknown_state(ledger_path):
    with pytest.raises(ValueError):
        apply(ledger_path, "f1", "not-a-real-state")


def test_apply_rejects_an_unknown_finding_id(ledger_path):
    with pytest.raises(KeyError):
        apply(ledger_path, "does-not-exist", "fixed")


def test_apply_writes_the_new_state_and_returns_the_entry(ledger_path):
    entry = apply(ledger_path, "f1", "fixed")
    assert entry.state == "fixed"
    reloaded = ledger_mod.load(ledger_path)
    saved = [e for e in reloaded.entries if e.id == "f1"][0]
    assert saved.state == "fixed"


def test_refuted_requires_a_non_empty_reason(ledger_path):
    with pytest.raises(ValueError):
        apply(ledger_path, "f1", "refuted", reason="")
    with pytest.raises(ValueError):
        apply(ledger_path, "f1", "refuted")


def test_refuted_with_a_reason_is_saved_with_it(ledger_path):
    entry = apply(ledger_path, "f1", "refuted",
                   reason="replayed: contrast 5.1:1, claim of 3.8:1 not reproduced")
    assert entry.state == "refuted"
    assert "5.1:1" in entry.reason


def test_other_states_do_not_require_a_reason(ledger_path):
    for state in ("false-positive", "wont-fix", "accepted", "fixed", "regressed", "open"):
        entry = apply(ledger_path, "f1", state)
        assert entry.state == state


def test_apply_never_calls_a_separate_suppression_store():
    """There is no add_suppression/upsert in this module -- suppressions derive from state via
    ledger.suppressions_for, exercised by fr-lens, not written here."""
    import flow_review.triage as triage_mod
    assert not hasattr(triage_mod, "upsert")
    assert not hasattr(triage_mod, "add_suppression")


def test_reopen_is_just_apply_open(ledger_path):
    apply(ledger_path, "f1", "false-positive", reason="documented exception")
    entry = apply(ledger_path, "f1", "open")
    assert entry.state == "open"


def test_build_fix_brief_uses_ledger_entry_fields(ledger_path):
    reloaded = ledger_mod.load(ledger_path)
    entry = [e for e in reloaded.entries if e.id == "f1"][0]
    brief = build_fix_brief(entry, repro_steps=["open Settings", "inspect the row"], source_map=None)
    assert brief.repro_steps == ["open Settings", "inspect the row"]
    assert brief.evidence == entry.evidence
    assert brief.suspected_location == "unknown"


def test_build_fix_brief_uses_the_source_map_when_available(ledger_path):
    reloaded = ledger_mod.load(ledger_path)
    entry = [e for e in reloaded.entries if e.id == "f1"][0]
    source_map = {f"{entry.route}|{entry.locator}": "src/settings/Row.tsx:42"}
    brief = build_fix_brief(entry, repro_steps=["open Settings"], source_map=source_map)
    assert brief.suspected_location == "src/settings/Row.tsx:42"


def test_build_fix_brief_is_report_content_only(ledger_path):
    reloaded = ledger_mod.load(ledger_path)
    entry = [e for e in reloaded.entries if e.id == "f1"][0]
    brief = build_fix_brief(entry, repro_steps=["x"], source_map=None)
    for field_name in ("repro_steps", "evidence", "suspected_location"):
        assert hasattr(brief, field_name)
    assert not hasattr(brief, "patch")
    assert not hasattr(brief, "diff")
```

  (The `ledger_path` fixture's exact call shape for `ledger.save`/the container type
  (`Ledger(entries=[...])` vs a bare list) depends on A5's final `Ledger` shape, which was not in
  this drafter's read set beyond the Canonical Interfaces line -- see QUESTIONS is not needed here
  since the interface line gives `ledger.load(path) -> Ledger` / `ledger.save(ledger, path)`
  explicitly; the executor writes the fixture against A5's actual `Ledger` type once merged, and
  the `hasattr` fallback above is a placeholder to delete at that point, not a design decision.)

  Step 2: run `python -m pytest plugins/flow-review/engine/flow_review/test_triage.py -q` -> FAIL.

- [ ] **Step 3: the content.**

  `plugins/flow-review/engine/flow_review/triage.py`:

```python
"""Triage transitions and fix briefs (v2 design §8; Canonical Interfaces "Triage").

`apply()` is the one function both `flow-review triage ID STATE [--reason]` and the dashboard's
`POST /triage` call -- there is exactly one triage code path, never two that could drift apart.
There is no `upsert` and no `add_suppression` here: a false-positive (or wont-fix) transition is
just a state write, and `ledger.suppressions_for(ledger, rule)` derives the suppression list from
state at read time (`fr-lens`'s consumer, not this module's producer).

`build_fix_brief()` is report content only: repro steps, evidence references, and a suspected
`file:line` via source maps where available, else the literal string "unknown". It never
constructs anything resembling a patch or a diff -- flow-review never edits product code.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from flow_review import ledger as ledger_mod

_REASON_REQUIRED = {"refuted"}


def apply(ledger_path: Path, finding_id: str, state: str, reason: str | None = None):
    if state not in ledger_mod.STATES:
        raise ValueError(f"unknown triage state {state!r}, must be one of {sorted(ledger_mod.STATES)}")

    lgr = ledger_mod.load(ledger_path)
    entry = next((e for e in lgr.entries if e.id == finding_id), None)
    if entry is None:
        raise KeyError(f"no finding {finding_id!r} in {ledger_path}")

    if state in _REASON_REQUIRED and not reason:
        raise ValueError(f"transitioning to {state!r} requires a non-empty reason")

    entry.state = state
    entry.reason = reason or ""

    ledger_mod.save(lgr, ledger_path)
    return entry


@dataclass
class FixBrief:
    repro_steps: list[str]
    evidence: list[str]
    suspected_location: str


def build_fix_brief(entry, repro_steps: list[str], source_map: dict | None) -> FixBrief:
    location = "unknown"
    if source_map is not None:
        key = f"{entry.route}|{entry.locator}"
        location = source_map.get(key, "unknown")
    return FixBrief(
        repro_steps=repro_steps,
        evidence=entry.evidence,
        suspected_location=location,
    )
```

  Extend `plugins/flow-review/agents/fr-triage.md` (append after C1's frontmatter and profile
  table -- do not replace either) with the operational brief:

````markdown

## Stuck classification

Read `references/stuck.md` in full. You classify a stuck report as `PRODUCT-stuck`,
`HARNESS-stuck`, or `UNKNOWN`. Severity for a `PRODUCT-stuck` classification is set by the
product-stuck floor table in `references/lenses/{ui,api,cli}.md` section 4 -- you apply that
table, you do not set severity by independent judgment.

## Fuzzy dedup (A-6)

When `ledger.fingerprint(flow_id, rule, route, locator)` misses but
`ledger.find_alias_candidates(ledger, flow_id, rule, route)` returns a candidate, you decide: same
finding under a changed locator, or genuinely new. Either verdict is recorded via
`ledger.record_alias(ledger, canonical_id, alias_fingerprint)` -- a "new" verdict still records
that you considered and rejected the match.

## Reconciliation

After a batch of triage transitions (`flow_review.triage.apply`), reconcile the ledger via
`ledger.reconcile(ledger, findings, flows_run, run_id, alias_decisions=None)` -- a consistency pass
over writes that already happened, not a new judgment call.
````

- [ ] **Step 4: re-run `python -m pytest plugins/flow-review/engine/flow_review/test_triage.py -q` -> PASS.**
- [ ] **Step 5 (verify): `python -m pytest plugins/flow-review/engine/flow_review/test_triage.py -q`; grep `dashboard/serve.py` (E1, owned by D4) for `POST /triage` and confirm it imports and calls `flow_review.triage.apply` directly rather than shelling out to the CLI -- flag at merge if E1's draft does otherwise, since the Canonical Interfaces line is explicit that both callers hit the same function.**
- [ ] **Step 6 (commit): `feat(triage): add the shared apply() transition, reason-required refutation, and the fix brief`.**

- [ ] **Step 7: Commit.**
  ```bash
  git add plugins/flow-review/engine/flow_review/triage.py plugins/flow-review/engine/flow_review/test_triage.py plugins/flow-review/agents/fr-triage.md
  git commit -m "feat(plugin): triage + fix briefs (C6)"
  ```


---

### Task C7: Docs sync

**Executor:** haiku · **Depends:** C2 · **Wave:** 11
**Files:**
- `plugins/flow-review/skills/flow-review/references/setup.md` (edit)
- `plugins/flow-review/skills/flow-review/references/testing.md` (edit)
- `plugins/flow-review/skills/flow-review/references/stuck.md` (edit)
- `plugins/flow-review/skills/flow-review/references/evidence.md` (edit)
- `plugins/flow-review/skills/flow-review/templates/flows.md` (edit)
- `README.md`, `docs/concepts.md`, `docs/walkthrough.md`, `CONTRIBUTING.md` (v2 fact pass)
- `test_readme.py` (edit: drop the stdlib-only promise, update for v2 install/packaging)

**Interfaces:**
- Consumes: everything landed by A1-A10, B0-B9, C1-C6 (this task only documents; it introduces no
  new engine or agent behavior).
- Produces: a docs set that matches the shipped v2 tool.

This task keeps the fact-checklist approach (each fact below is a checkbox with the exact old
string, the exact new string where known, and a verify grep) rather than full replacement text for
the four top-level docs, because their accurate final prose depends on module locations and CLI
names from A1-C6 that settle only once those tasks are merged -- the haiku executor runs this task
last (wave 11) specifically so it can grep the real merged files rather than a drafted guess.

- [ ] **Step 1: failing test first -- edit `test_readme.py`:**

```python
def test_readme_no_longer_claims_stdlib_only():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Standard library only" not in text
    assert "no third-party packages" not in text.lower()


def test_readme_states_the_managed_venv_and_pypi_package():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "flow-review setup-env" in text
    assert re.search(r"\bpypi\b", text, re.I)


def test_contributing_no_longer_claims_stdlib_only():
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "no dependencies to install" not in text.lower()


def test_readme_points_at_the_engine_package_location():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "engine/flow_review" in text or "flow_review" in text


def test_docs_reference_the_ledger_not_the_v1_findings_module():
    text = (ROOT / "docs" / "concepts.md").read_text(encoding="utf-8")
    assert "fr/findings.py" not in text
    assert "ledger" in text.lower()
```

  (These five functions are added to the existing `test_readme.py`; every pre-existing function --
  banner, credits, no-emoji, no-BOM, lens table -- is kept as-is and must still pass against the
  rewritten docs.)

  Step 2: run `python -m pytest test_readme.py -q` -> FAIL (README/CONTRIBUTING/concepts.md still
  carry v1 facts).

- [ ] **Step 3: the checklist. Each box is one fact to change; do them in order, each with a
  verify grep run immediately after.**

  - [ ] **3a. `README.md` -- drop the stdlib-only claim.**
    - Old: `## Requirements\n\nPython 3.10+. Standard library only -- no \`pip install\`, no third-party packages.`
    - New: `## Requirements\n\nPython 3.10+. Setup runs \`flow-review setup-env\`, which creates a managed venv (uv, pip fallback) and installs only what the detected surfaces need -- Playwright and Pillow for \`[web]\`, more per surface at M2+. The engine itself is the \`flow-review\` PyPI package.`
    - Verify: `grep -n "Standard library only" README.md` -> no output.

  - [ ] **3b. `README.md` -- fix the module path in "See it" / "What it writes".**
    - Old: any occurrence of `fr/findings.py`, `fr/prove.py`, `fr/drift.py`, `fr/config.py`,
      `fr/manifest.py`, `fr/lenses.py`.
    - New: `engine/flow_review/{ledger,prove,drift,config,manifest,lenses}.py` respectively
      (`fr.findings.demote_repeats` specifically becomes `ledger.reconcile` -- v1's standalone
      demotion module is gone; demotion is now a ledger concern).
    - Verify: `grep -n "fr/" README.md` -> no output outside a code fence showing historical
      output (none should remain; if the "Before/After" demotion example still references v1
      event shape `{"ts", "sev", "location", "text"}`, update it to the canonical
      `{surface_id, flow_id, rule, route, locator, sev, text, evidence}` shape too).

  - [ ] **3c. `README.md` -- Install section stays as-is** (the two `/plugin` commands are
    unchanged by v2); no edit, but verify: `grep -n "/plugin marketplace add Bilohit/flow-review" README.md`
    still present.

  - [ ] **3d. `docs/concepts.md` -- Surface entry drops v1-only fields.**
    - Old: ``name`, `kind`, `driver`, `launch`, `preconditions`, `destructive`, `provenance`.``
    - New: ``id`, `name`, `kind`, `driver`, `launch`, `cwd`, `env`, `options`, `preconditions`,
      `state`, `reset`, `creds`, `record`, `provenance` (A-4/A-5 -- `destructive: true` migrates to
      `state: persistent`).``
    - Verify: `grep -n '"destructive"' docs/concepts.md` -> no output (except inside a sentence
      explicitly describing the v1-to-v2 migration, if kept for context).

  - [ ] **3e. `docs/concepts.md` -- add `Ledger`, `Fingerprint`, `Budget`, `Validation` entries.**
    - New paragraphs, each one sentence plus a module pointer, matching the file's existing style:
      `Ledger` -> `flow_review/ledger.py`, findings keyed by `LedgerEntry`, states include
      `false-positive`/`wont-fix`/`accepted`/`refuted` (sticky, A-15); `Fingerprint` ->
      `ledger.fingerprint(flow_id, rule, route, locator)` (A-6); `Budget` -> `flow_review/budget.py`,
      `budget.used`/`budget.estimate`/`budget.record_usage`; `Validation`/`Disposition` ->
      `flow_review/validate.py` (C5), the engine/objective/judgment split and the P0/P1
      replay-then-verify pipeline.
    - Verify: `grep -n "^## Ledger$\|^## Fingerprint$\|^## Budget$\|^## Validation$" docs/concepts.md`
      -> four matches.

  - [ ] **3f. `docs/concepts.md` -- Finding entry stops citing `fr/findings.py`.**
    - Old: `plugins/flow-review/skills/flow-review/fr/findings.py`.
    - New: `plugins/flow-review/engine/flow_review/ledger.py` (`ledger.reconcile` folds repeat
      demotion into the ledger; there is no standalone `findings.py` in v2).
    - Verify: `grep -n "fr/findings.py" docs/concepts.md` -> no output.

  - [ ] **3g. `docs/walkthrough.md` -- rewrite the worked example to a `goal`-mode run.**
    - Old: the walkthrough drives an unnamed default run with no GO-gate estimate shown and no
      dashboard URL.
    - New: add, after "2. First run -- the setup interview", a step showing `flow-review plan
      --mode goal --goal "..." --json`'s estimate at the GO gate, the `flow-review serve` URL being
      printed right after GO, and a triage-driven `flow-review triage <id> false-positive --reason
      "..."` suppressing a repeat on the following run (replacing the old
      `fr.findings.demote_repeats`-only story).
    - Verify: `grep -n "flow-review plan\|flow-review serve\|flow-review triage" docs/walkthrough.md`
      -> at least one match each.

  - [ ] **3h. `CONTRIBUTING.md` -- drop the stdlib-only opening line and update the module table.**
    - Old: `flow-review is standard-library Python -- no dependencies to install, no build step.`
    - New: `flow-review's engine (\`plugins/flow-review/engine/flow_review/\`) is a managed-venv
      Python package (uv, pip fallback) with per-surface extras; the skill and agent files
      (\`plugins/flow-review/skills/flow-review/\`, \`plugins/flow-review/agents/\`) are plain
      Markdown with no build step.`
    - Also add one row per new engine module to "What to change and where":
      `validate.py` (the P0/P1 replay-then-verify state machine), `triage.py` (transitions and fix
      briefs), `ledger.py` (findings, fingerprint, suppressions, A-6 aliases), `budget.py` (token
      estimate and cap), `plan.py` (the GO-gate plan). Replace every remaining `fr/` path in the
      table with `engine/flow_review/`.
    - Verify: `grep -n "no dependencies to install" CONTRIBUTING.md` -> no output;
      `grep -n "validate.py\|triage.py\|ledger.py\|budget.py\|plan.py" CONTRIBUTING.md` -> five
      matches.

  - [ ] **3i. `references/testing.md` -- stop appending harness traps into the plugin's own
    install directory (audit M5).**
    - Old (closing paragraph of the per-driver-notes section): `These per-driver notes grow with
      the same discipline as the run's stuck-episode table: a novel harness trap earns one new
      line here, symptom first, so the next run does not rediscover it.`
    - New:
      ```
      These per-driver notes are the plugin's own shipped reference and are never appended to at
      runtime. A novel harness trap discovered during a run is written instead to the project's
      own `.flow-review/traps.md` (created by `flow-review setup-env` if it does not already
      exist), symptom first, so the next run on this project does not rediscover it -- without
      polluting the plugin's install directory, which every project sharing that plugin install
      would otherwise see.
      ```
    - Verify: `grep -n "earns one new line here" plugins/flow-review/skills/flow-review/references/testing.md`
      -> no output; `grep -n ".flow-review/traps.md" plugins/flow-review/skills/flow-review/references/testing.md`
      -> at least one match.

  - [ ] **3j. `references/stuck.md` -- same fix for the `HARNESS-stuck` line.**
    - Old: `Not a product finding -- record it as an infra note, and **if the trap is novel,
      append it to \`testing.md\`** so the next run does not rediscover it.`
    - New: `Not a product finding -- record it as an infra note, and **if the trap is novel,
      append it to the project's \`.flow-review/traps.md\`** (never the plugin's own
      \`references/testing.md\`) so the next run on this project does not rediscover it.`
    - Verify: `grep -n "append it to \`testing.md\`" plugins/flow-review/skills/flow-review/references/stuck.md`
      -> no output.

  - [ ] **3k. `references/evidence.md` -- replace the shell `printf` append idiom (audit item, the
    idiom is shell-injectable) with the engine event writer.**
    - Old: the whole `### The append idiom -- use exactly this` subsection (the `TS=$(date ...)` /
      `printf` block and its four bullet points).
    - New:
      ```
      ### How to append an event -- use the engine, never a hand-rolled append

      ```
      flow-review event --run "$RUN" --type step surface=<surface-id> flow=f1 step="open the target screen" state=ok
      ```

      - **Always the CLI (or `events.append` if called from Python), never a hand-rolled shell
        append.** The v1 `printf "$TEXT" >> events.jsonl` idiom is shell-injectable the moment
        `text` contains a double quote from captured product output.
      - `k=v` pairs become JSON fields; `ts` (ms, UTC, trailing `Z`) and secret redaction
        (`events.redact`) are applied by the writer, not the caller.
      - Multiple writers still append concurrently; the file is still never read back or
        rewritten by a tester.
      ```
    - Verify: `grep -n "printf '%s\\\\n'" plugins/flow-review/skills/flow-review/references/evidence.md`
      -> no output; `grep -n "flow-review event --run" plugins/flow-review/skills/flow-review/references/evidence.md`
      -> at least one match.

  - [ ] **3l. `references/setup.md` -- resolve the self-contradiction on unproven surfaces (audit
    item) and drop the dead v1 config vocabulary from sections 6-7.**
    - Old (end of section 4's `NOT_PROVEN` passage, no closing sentence currently present):
      nothing -- the contradiction is an omission, not a wrong sentence, so this is an addition,
      not a replace.
    - New (append at the end of section 4): `An \`audited\`-only surface (never reaching
      \`proven\`) is not blocked from being written into \`config.json\` -- section 1's binding
      rule is about being *proven or declined*, and \`audited\` is neither; the surface is written
      with \`provenance["launch"] = "audited"\` and is asked about again at the top of every
      subsequent setup or \`--reconfigure\` pass. What is never allowed is skipping proving
      entirely and writing a surface with no \`provenance["launch"]\` value at all.`
    - Old (section 6, "Pick lens sets per surface" and section 7, "Choose the tester agent and
      evidence types" -- both reference dropped v1 fields `lens_sets`, `tester_agent`,
      `evidence_types`).
    - New: delete both sections' body text and replace with one short paragraph: `Lens sets are no
      longer chosen at setup -- \`references/lenses/{ui,api,cli}.md\` fixes the lens set by
      surface \`kind\` (A-5 drops \`lens_sets\`/\`tester_agent\`/\`evidence_types\` from config on
      migration). Setup instead records the surface's \`state\`, optional \`reset\` command, and
      credential env-var names (\`creds\`) -- see \`references/setup.md\` section 8 for the flows
      manifest and \`docs/concepts.md\`'s Surface entry for the full v2 field list.` Renumber the
      remaining sections (old 8-10 become 7-9) and fix every internal cross-reference to the old
      numbering.
    - Verify: `grep -n "lens_sets\|tester_agent\|evidence_types" plugins/flow-review/skills/flow-review/references/setup.md`
      -> no output.

  - [ ] **3m. `templates/flows.md` -- note the row format is unchanged from v1.**
    - Old: nothing -- this is an addition after the "Row format" section's closing `BINDING` box.
    - New: `This row format is unchanged from v1 -- only \`config.json\` migrates (A-5); an
      existing \`.flow-review/flows.md\` in a project already using flow-review needs no changes
      at all.`
    - Verify: `grep -n "unchanged from v1" plugins/flow-review/skills/flow-review/templates/flows.md`
      -> one match.

- [ ] **Step 4: re-run `python -m pytest test_readme.py -q` and `python -m pytest plugins/flow-review/skills/flow-review/test_references.py -q` -> PASS.**
- [ ] **Step 5 (verify): `python -m pytest -q` from the repo root, full suite green; re-run every
  grep in 3a-3m in one pass as a final sweep, since edits made later in the checklist (e.g. 3l's
  renumbering) can reintroduce a stale cross-reference an earlier grep already cleared.**
- [ ] **Step 6 (commit): `docs: sync setup/testing/stuck/evidence references and top-level docs to v2`.**

- [ ] **Step 7: Commit.**
  ```bash
  git add plugins/flow-review/skills/flow-review/references/setup.md plugins/flow-review/skills/flow-review/references/testing.md plugins/flow-review/skills/flow-review/references/stuck.md plugins/flow-review/skills/flow-review/references/evidence.md plugins/flow-review/skills/flow-review/templates/flows.md README.md docs/concepts.md docs/walkthrough.md CONTRIBUTING.md test_readme.py
  git commit -m "docs(plugin): docs sync (C7)"
  ```


---

### Task E1: `flow-review serve` — ThreadingHTTPServer + SSE + triage POST

**Executor:** sonnet · **Depends:** A4, A5 · **Wave:** 4

**Files:**
- `plugins/flow-review/engine/flow_review/dashboard/serve.py`
- `plugins/flow-review/engine/flow_review/dashboard/test_serve.py`
- (touch, if A1's `cli.py` stub does not already list `serve`) `plugins/flow-review/engine/flow_review/cli.py` — add a `serve` subcommand resolving `project_root`, `run_dir`, and `cfg = config.load(...)`, then calling `dashboard.serve.serve(project_root, run_dir, cfg, port)`; `--static OUT.html` calls `dashboard.static.render_static` (E2). Skip if A1 already wires this dispatch.

**Interfaces:**

Consumes (Canonical Interfaces block, verbatim signatures):
- `flow_review.dashboard.state.fold(project_root: Path, run_dir: Path, cfg: Config) -> dict` (E2, produces the `/state` JSON body)
- `flow_review.triage.apply(ledger_path: Path, finding_id: str, state: str, reason: str | None = None) -> LedgerEntry`
- `flow_review.ledger.load(path) -> Ledger` (indirectly, via `fold`)
- `flow_review.config.Config` (type only — `cfg` is loaded by the CLI/caller and handed to `serve()`, this module never calls `config.load` itself)

Produces — HTTP endpoints, `127.0.0.1` only, ephemeral port (`0`) by default so multiple runs never collide:

- `GET /` → `page/index.html` (E4), `text/html; charset=utf-8`.
- `GET /state` → 200 JSON, the full page-state document. Example:
  ```json
  {
    "run": {"id": "2026-09-23T10-00-00Z", "mode": "goal", "started": "2026-09-23T10:00:00.000Z",
             "finished": false, "flows_total": 12, "flows_done": 5, "elapsed_s": 187},
    "budget": {"cap_tokens": 200000, "used_tokens": 41230, "pct": 0.206},
    "badge": {"total": 4, "worst_sev": "P1", "counts": {"P0": 0, "P1": 2, "P2": 2}},
    "lanes": [
      {"surface_id": "web-app", "kind": "web", "state": "running",
       "shot": "shots/web-app-0042.png", "output": null,
       "current_step": "click Submit", "flow_id": "checkout",
       "history": [{"step": "fill email", "state": "ok"}, {"step": "click Submit", "state": "running"}]},
      {"surface_id": "billing-api", "kind": "api", "state": "idle",
       "shot": null, "output": "POST /v1/charges -> 200 {\"id\":\"ch_1\"}",
       "current_step": null, "flow_id": null, "history": []}
    ],
    "header": {
      "sparkline": [{"run_id": "2026-09-20T.._Z", "p0": 1, "p1": 3, "p2": 5},
                    {"run_id": "2026-09-23T.._Z", "p0": 0, "p1": 2, "p2": 2}],
      "surface_dots": [{"surface_id": "web-app", "status": "warn"},
                        {"surface_id": "billing-api", "status": "ok"}]
    },
    "report": null,
    "findings": [
      {"id": "f_a1b2", "fingerprint": "sha1:...", "state": "open", "sev": "P1", "rule": "contrast",
       "flow_id": "checkout", "surface_id": "web-app", "route": "/checkout", "locator": "role=button[name=Submit]",
       "text": "Submit button fails WCAG AA", "evidence": ["shots/web-app-0031.png"],
       "runs_seen": 2, "first_run": "2026-09-20T.._Z", "last_run": "2026-09-23T.._Z",
       "aliases": [], "reason": ""}
    ]
  }
  ```
  `report` is `null` while `run.finished` is false; once true it holds `{needs_attention, goal_cards, collapsed}` per E2's `fold`.

- `GET /events` → SSE (`text/event-stream`). Tails `events.jsonl` (poll every 0.5s — stdlib has no inotify), and on any growth re-folds and sends one delta:
  ```
  event: state
  data: {"run": {...}, "budget": {...}, ...same shape as /state...}

  ```
  A `: heartbeat\n\n` comment every 15s with no growth, so `EventSource` (which auto-reconnects on silence/drop) never times out through a proxy. The client (E4) uses `new EventSource('/events')` and patches the DOM from `state` messages — no manual reconnect logic needed.

- `POST /triage` — request `{"finding_id": "f_a1b2", "state": "false-positive", "reason": "expected behavior"}` (`reason` optional, required only for `refuted` — `triage.apply` enforces it) → calls `triage.apply(ledger_path, finding_id, state, reason)`. Response `{"ok": true, "finding": {...LedgerEntry as dict...}}` (200) or `{"error": "<message>"}` (400) on missing fields or an exception from `triage.apply`. Reopening a finding is the same endpoint with `"state": "open"`.

- `GET /<path>` → static files under `page/` (fonts, icons, css, js), traversal-guarded (resolved path must stay under `page/`).

**Steps:**

- [ ] **Step 1: red.** Write the test below. Run `pytest plugins/flow-review/engine/flow_review/dashboard/test_serve.py -q` → FAIL (`serve.py` doesn't exist).

```python
# plugins/flow-review/engine/flow_review/dashboard/test_serve.py
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

from flow_review.dashboard.serve import make_server


class _FakeCfg:
    budget = {"cap_tokens": 200000}


def _start(tmp_path):
    project_root = tmp_path / "proj"
    (project_root / ".flow-review").mkdir(parents=True)
    (project_root / ".flow-review" / "findings.json").write_text("{}", encoding="utf-8")
    run_dir = project_root / ".flow-review" / "runs" / "r1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text("", encoding="utf-8")
    server = make_server(project_root, run_dir, _FakeCfg(), port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    return server, port


def test_state_endpoint_returns_json_with_required_keys(tmp_path):
    server, port = _start(tmp_path)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/state", timeout=5) as resp:
            assert resp.status == 200
            assert resp.headers["Content-Type"] == "application/json"
            body = json.loads(resp.read())
        for key in ("run", "budget", "badge", "lanes", "header", "report", "findings"):
            assert key in body
        assert body["budget"]["cap_tokens"] == 200000
    finally:
        server.shutdown()


def test_triage_post_invokes_apply_and_returns_ok(tmp_path, monkeypatch):
    server, port = _start(tmp_path)

    class _FakeEntry:
        def __init__(self):
            self.id, self.state, self.reason = "f1", "false-positive", None

    calls = []

    def fake_apply(ledger_path, finding_id, state, reason=None):
        calls.append((ledger_path, finding_id, state, reason))
        return _FakeEntry()

    import flow_review.dashboard.serve as serve_mod
    monkeypatch.setattr(serve_mod.triage, "apply", fake_apply)

    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/triage",
            data=json.dumps({"finding_id": "f1", "state": "false-positive"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            assert json.loads(resp.read())["ok"] is True
        assert len(calls) == 1
        assert calls[0][1:] == ("f1", "false-positive", None)
    finally:
        server.shutdown()


def test_triage_post_missing_fields_is_400(tmp_path):
    server, port = _start(tmp_path)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/triage",
            data=json.dumps({"finding_id": "f1"}).encode(),
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            assert False, "expected HTTPError"
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
    finally:
        server.shutdown()


def test_server_binds_localhost_only(tmp_path):
    server, port = _start(tmp_path)
    try:
        assert server.server_address[0] == "127.0.0.1"
    finally:
        server.shutdown()
```

- [ ] **Step 2: green.** Implement `serve.py`, run the test again → PASS.

```python
# plugins/flow-review/engine/flow_review/dashboard/serve.py
"""flow-review serve: local HTTP server for the live dashboard.

ThreadingHTTPServer bound to 127.0.0.1 only (never exposed on the network).
Endpoints: GET / (page), GET /state (JSON), GET /events (SSE), POST /triage,
GET /<path> (static assets under page/).
"""
from __future__ import annotations

import dataclasses
import json
import mimetypes
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from flow_review import triage
from flow_review.dashboard.state import fold

PAGE_DIR = Path(__file__).parent / "page"
HEARTBEAT_S = 15
POLL_S = 0.5


def _ledger_path(project_root: Path) -> Path:
    return project_root / ".flow-review" / "findings.json"


class Handler(BaseHTTPRequestHandler):
    project_root: Path
    run_dir: Path
    cfg: object

    def log_message(self, fmt, *args):  # noqa: A002 — silence default stderr access log
        pass

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str):
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 — stdlib handler name
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_file(PAGE_DIR / "index.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/state":
            self._send_json(fold(self.project_root, self.run_dir, self.cfg))
            return
        if parsed.path == "/events":
            self._stream_events()
            return
        rel = parsed.path.lstrip("/")
        candidate = (PAGE_DIR / rel).resolve()
        page_root = PAGE_DIR.resolve()
        if page_root in candidate.parents and candidate.is_file():
            ctype = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
            self._send_file(candidate, ctype)
            return
        self.send_response(404)
        self.end_headers()

    def _stream_events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        events_path = self.run_dir / "events.jsonl"
        last_size = -1
        last_beat = time.monotonic()
        try:
            while True:
                size = events_path.stat().st_size if events_path.exists() else 0
                if size != last_size:
                    last_size = size
                    payload = json.dumps(fold(self.project_root, self.run_dir, self.cfg))
                    self.wfile.write(f"event: state\ndata: {payload}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    last_beat = time.monotonic()
                elif time.monotonic() - last_beat > HEARTBEAT_S:
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
                    last_beat = time.monotonic()
                time.sleep(POLL_S)
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_POST(self):  # noqa: N802
        if urlparse(self.path).path != "/triage":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            self._send_json({"error": "invalid json"}, status=400)
            return
        finding_id = body.get("finding_id")
        state = body.get("state")
        reason = body.get("reason")
        if not finding_id or not state:
            self._send_json({"error": "finding_id and state are required"}, status=400)
            return
        try:
            entry = triage.apply(_ledger_path(self.project_root), finding_id, state, reason=reason)
        except Exception as exc:  # triage.apply's own errors are user-facing (bad state name etc.)
            self._send_json({"error": str(exc)}, status=400)
            return
        self._send_json({"ok": True, "finding": dataclasses.asdict(entry)})


def make_server(project_root: Path, run_dir: Path, cfg, port: int = 0) -> ThreadingHTTPServer:
    bound = type("BoundHandler", (Handler,), {
        "project_root": project_root, "run_dir": run_dir, "cfg": cfg,
    })
    return ThreadingHTTPServer(("127.0.0.1", port), bound)


def serve(project_root: Path, run_dir: Path, cfg, port: int = 0) -> None:
    server = make_server(project_root, run_dir, cfg, port)
    _, bound_port = server.server_address
    print(f"flow-review dashboard: http://127.0.0.1:{bound_port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
```

**Verify:** `pytest plugins/flow-review/engine/flow_review/dashboard/test_serve.py -q` green; manual smoke `python -m flow_review.cli serve <run_dir>` opens and `curl 127.0.0.1:<port>/state` returns JSON.

**Commit:** `feat(dashboard): serve.py — localhost HTTP server, SSE, triage POST`

- [ ] **Step 3: Commit.**
  ```bash
  git add plugins/flow-review/engine/flow_review/dashboard/serve.py plugins/flow-review/engine/flow_review/dashboard/test_serve.py plugins/flow-review/engine/flow_review/cli.py
  git commit -m "feat(dashboard): flow-review serve (E1)"
  ```


---

### Task E2: page-state fold (events + ledger + budget) and static fallback

**Executor:** sonnet · **Depends:** A4, A5, B8 · **Wave:** 5

**Files:**
- `plugins/flow-review/engine/flow_review/dashboard/state.py`
- `plugins/flow-review/engine/flow_review/dashboard/test_state.py`
- `plugins/flow-review/engine/flow_review/dashboard/static.py`
- `plugins/flow-review/engine/flow_review/dashboard/test_static.py`

**Interfaces:**

Consumes (Canonical Interfaces block):
- `run_dir/events.jsonl` lines written by `flow_review.events.append`, each `{"ts": "...Z", "id": "...", "type": "run"|"step"|"shot"|"output"|"finding"|"status"|"withdraw"|"usage"|"goal", ...}`. `usage` events carry `{surface, role, tokens}`; `withdraw` carries `finding_id`.
- `flow_review.ledger.load(path) -> Ledger`, `Ledger.findings: dict[str, LedgerEntry]` keyed by id.
- `flow_review.budget.used(run_dir: Path) -> int`.
- `cfg: Config` (already loaded by the caller) → `cfg.budget["cap_tokens"]`.

Produces:
- `fold(project_root: Path, run_dir: Path, cfg) -> dict` — the `/state` JSON shape documented in E1 (`run, budget, badge, lanes, header, report, findings`).
- `render_static(project_root: Path, run_dir: Path, cfg, out_path: Path) -> None` — **A-21: one fully self-contained file.** CSS, JS, the icon sprite and the subsetted `.woff2` fonts (E3) are inlined into `<style>`/`<script>` as base64 data; screenshots referenced by any lane or finding evidence are embedded as small downscaled JPEG data-URI thumbnails (**max edge 320px, JPEG quality 70** — proposed default, tunable) wrapped in an `<a href="<relative-path-to-full-res-shot>">` so the full-resolution PNG in the run folder is one click away, never itself inlined (keeps the single file small). `app.js` reads `#state-data` and skips `fetch`/`EventSource` when it's present.
- CLI: `flow-review serve --static OUT.html` (wired in E1) calls `render_static`.

**Fold rules (binding):**
- **Withdraw matches by `finding_id`, not by timestamp** (fixes H7 — the old `render.py:115` matched the prior finding by `ts == finding_ts`, which breaks under concurrent surfaces writing the same millisecond). A `withdraw` event's `finding_id` is the **finding event's own `id`** (the id `events.append` assigned when the finding was first written, *before* it is reconciled into the ledger). Scope: this only retracts a finding **within the same run, before `ledger.reconcile` has run** — an already-reconciled finding from a prior run is corrected through `triage.apply(..., "refuted", reason=...)` instead, a distinct, deliberate action, not a `withdraw` event.
- **No string-template placeholder expansion of user text** (fixes M8 — the old `_fill` at `render.py:179` does `block.replace("{{KEY}}", value)`, so a finding whose text happens to contain literal `{{...}}` gets expanded against unrelated keys). `state.py` only ever produces a data structure; user text (finding `text`, step labels, API/CLI `output`) passes through unmodified in the JSON. Insertion into the DOM is the client's job via `textContent` (E4). `static.py`'s one server-side escape is of the whole embedded JSON blob against `</script>` injection — never a per-field template substitution.
- Badge counts and the `findings` list are the ledger's `open` + `regressed` entries (a `false-positive`/`refuted`/`wont-fix`/`accepted` entry does not tint the badge — matches A-15, those states are sticky and live only in the report's collapsed sections), merged with any in-run `finding` events not yet reconciled into the ledger (keyed by the finding event's `id`) minus any ids removed by a same-run `withdraw`.
- `report` is populated (`needs_attention` / `goal_cards` / `collapsed`) only once the `run` event's `state` is `done` or `halted`.
- `budget.used_tokens` is **always** `flow_review.budget.used(run_dir)` — `state.py` never re-derives it by summing `usage` events itself (A-23).
- A live `finding` event's `disposition` (`"engine"|"objective"|"judgment"`) is carried straight through onto the finding's dict entry so the drawer/report can show which pipeline stage produced it; reconciled ledger entries don't carry `disposition` (it's a pre-reconcile field only), so it's `None`/absent on anything read from `ledger.load`.

**Steps:**

- [ ] **Step 1: red (fold).** Write the test below. Run `pytest plugins/flow-review/engine/flow_review/dashboard/test_state.py -q` → FAIL (`state.py` missing).

```python
# plugins/flow-review/engine/flow_review/dashboard/test_state.py
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from flow_review.dashboard.state import fold


@dataclass
class _Entry:
    id: str
    fingerprint: str = ""
    surface_id: str = ""
    flow_id: str = ""
    rule: str = ""
    route: str = ""
    locator: str = ""
    sev: str = "P2"
    text: str = ""
    evidence: list = field(default_factory=list)
    state: str = "open"
    runs_seen: int = 1
    first_run: str = ""
    last_run: str = ""
    aliases: list = field(default_factory=list)
    reason: str = ""


class _FakeLedger:
    def __init__(self, findings):
        # Canonical: Ledger.findings is dict[str, LedgerEntry] keyed by id.
        self.findings = {e.id: e for e in findings}


class _FakeCfg:
    budget = {"cap_tokens": 200000}


def _write_events(run_dir: Path, events: list[dict]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "events.jsonl").open("w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")


def _patch_common(monkeypatch, findings=(), used_tokens=0):
    monkeypatch.setattr("flow_review.dashboard.state.ledger.load",
                         lambda path: _FakeLedger(list(findings)))
    monkeypatch.setattr("flow_review.dashboard.state.budget.used",
                         lambda run_dir: used_tokens)


def test_withdraw_matches_by_finding_id_not_timestamp(tmp_path, monkeypatch):
    _patch_common(monkeypatch)
    run_dir = tmp_path / "run"
    _write_events(run_dir, [
        {"ts": "2026-09-23T10:00:00.000Z", "id": "e1", "type": "run", "mode": "goal",
         "surfaces": [{"id": "web-app", "kind": "web"}]},
        {"ts": "2026-09-23T10:00:01.000Z", "id": "f1", "type": "finding",
         "sev": "P1", "surface_id": "web-app", "text": "low contrast", "disposition": "judgment"},
        # A second finding stamped at the SAME ts as the withdraw below -- H7 regression bait.
        {"ts": "2026-09-23T10:00:02.000Z", "id": "f2", "type": "finding",
         "sev": "P1", "surface_id": "web-app", "text": "unrelated finding", "disposition": "objective"},
        {"ts": "2026-09-23T10:00:02.000Z", "id": "e4", "type": "withdraw", "finding_id": "f1"},
    ])
    state = fold(tmp_path, run_dir, _FakeCfg())
    ids = {f["id"] for f in state["findings"]}
    assert "f1" not in ids       # withdrawn finding is gone
    assert "f2" in ids           # the co-timestamped finding survives (H7)


def test_no_placeholder_expansion_of_user_text(tmp_path, monkeypatch):
    _patch_common(monkeypatch)
    run_dir = tmp_path / "run"
    _write_events(run_dir, [
        {"ts": "2026-09-23T10:00:00.000Z", "id": "e1", "type": "run", "mode": "goal", "surfaces": []},
        {"ts": "2026-09-23T10:00:01.000Z", "id": "f1", "type": "finding", "disposition": "engine",
         "sev": "P2", "surface_id": "web-app", "text": "literal {{P0}} in copy confuses users"},
    ])
    state = fold(tmp_path, run_dir, _FakeCfg())
    texts = [f["text"] for f in state["findings"]]
    assert "literal {{P0}} in copy confuses users" in texts  # untouched, not template-expanded


def test_report_absent_while_running_present_when_done(tmp_path, monkeypatch):
    _patch_common(monkeypatch)
    running_dir = tmp_path / "running"
    _write_events(running_dir, [
        {"ts": "2026-09-23T10:00:00.000Z", "id": "e1", "type": "run", "mode": "goal",
         "surfaces": [], "state": "running"},
    ])
    assert fold(tmp_path, running_dir, _FakeCfg())["report"] is None

    done_dir = tmp_path / "done"
    _write_events(done_dir, [
        {"ts": "2026-09-23T10:00:00.000Z", "id": "e1", "type": "run", "mode": "goal",
         "surfaces": [], "state": "done"},
    ])
    assert fold(tmp_path, done_dir, _FakeCfg())["report"] is not None


def test_report_groups_findings_per_spec_section_11():
    from flow_review.dashboard.state import _build_report
    new_p1 = {"id": "a", "state": "open", "runs_seen": 1, "sev": "P1", "disposition": "engine"}
    regressed = {"id": "b", "state": "regressed", "runs_seen": 4, "sev": "P0", "disposition": "objective"}
    repeat = {"id": "c", "state": "open", "runs_seen": 3, "sev": "P1", "disposition": "engine"}
    opinion = {"id": "d", "state": "open", "runs_seen": 1, "sev": "P2", "disposition": "judgment"}
    refuted = {"id": "e", "state": "refuted", "runs_seen": 1, "sev": "P1", "disposition": "judgment"}
    skipped = {"type": "status", "state": "not-exercised", "reason": "no-test-inbox", "flow_id": "signup"}
    report = _build_report([new_p1, regressed, repeat, opinion, refuted], {}, [skipped])
    assert [f["id"] for f in report["needs_attention"]] == ["b", "a"]  # by severity, P0 first
    assert [f["id"] for f in report["collapsed"]["opinions"]] == ["d"]
    assert [f["id"] for f in report["collapsed"]["repeats"]] == ["c"]
    assert [f["id"] for f in report["collapsed"]["refuted"]] == ["e"]
    assert report["collapsed"]["not_exercised"] == [skipped]


def test_budget_used_comes_from_budget_module_not_summed_locally(tmp_path, monkeypatch):
    _patch_common(monkeypatch, used_tokens=41230)
    run_dir = tmp_path / "run"
    _write_events(run_dir, [
        {"ts": "2026-09-23T10:00:00.000Z", "id": "e1", "type": "run", "mode": "goal", "surfaces": []},
        # a usage event that would sum to something else if state.py summed it itself --
        # asserts fold() calls budget.used() instead of re-deriving the total.
        {"ts": "2026-09-23T10:00:01.000Z", "id": "e2", "type": "usage",
         "surface": "web-app", "role": "explorer", "tokens": 999},
    ])
    body = fold(tmp_path, run_dir, _FakeCfg())
    assert body["budget"]["used_tokens"] == 41230
    assert body["budget"]["cap_tokens"] == 200000


def test_ledger_findings_pass_through_with_canonical_field_names(tmp_path, monkeypatch):
    entry = _Entry(id="f_a1b2", sev="P1", rule="contrast", surface_id="web-app",
                    flow_id="checkout", text="Submit button fails WCAG AA", state="open")
    _patch_common(monkeypatch, findings=[entry])
    run_dir = tmp_path / "run"
    _write_events(run_dir, [
        {"ts": "2026-09-23T10:00:00.000Z", "id": "e1", "type": "run", "mode": "goal", "surfaces": []},
    ])
    body = fold(tmp_path, run_dir, _FakeCfg())
    assert body["findings"][0]["rule"] == "contrast"
    assert body["findings"][0]["text"] == "Submit button fails WCAG AA"
    assert body["badge"]["counts"]["P1"] == 1
```

- [ ] **Step 2: green (fold).** Implement `state.py`, run again → PASS.

```python
# plugins/flow-review/engine/flow_review/dashboard/state.py
"""Fold events.jsonl + the ledger + the budget module into the dashboard's
page-state JSON. Pure function of (events, ledger, cfg): no mutation, no
templating of user text. Torn/malformed JSONL lines are dropped -- several
surfaces write concurrently.
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from flow_review import budget, ledger

SEVERITIES = ("P0", "P1", "P2")
LIVE_STATES = ("open", "regressed")
HISTORY_WINDOW = 8


def _parse_events(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            events.append(obj)
    return events


@dataclass
class _Lane:
    surface_id: str
    kind: str = "web"
    state: str = "idle"
    shot: str | None = None
    output: str | None = None
    current_step: str | None = None
    flow_id: str | None = None
    history: list[dict] = field(default_factory=list)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def fold(project_root: Path, run_dir: Path, cfg) -> dict:
    events_path = run_dir / "events.jsonl"
    text = events_path.read_text(encoding="utf-8") if events_path.exists() else ""
    events = _parse_events(text)

    run = {"id": run_dir.name, "mode": "auto", "started": None, "finished": False,
           "flows_total": 0, "flows_done": 0, "elapsed_s": 0}
    lanes: dict[str, _Lane] = {}
    done_flows: set[str] = set()
    live_findings: dict[str, dict] = {}
    withdrawn: set[str] = set()
    goals: dict[str, dict] = {}
    not_exercised: list[dict] = []
    header_history: list[dict] = []
    last_ts: str | None = None

    def lane(surface_id: str | None, kind: str = "web") -> _Lane | None:
        if not surface_id:
            return None
        if surface_id not in lanes:
            lanes[surface_id] = _Lane(surface_id, kind=kind)
        return lanes[surface_id]

    for ev in events:
        ts = ev.get("ts")
        if ts:
            last_ts = ts
            if run["started"] is None:
                run["started"] = ts
        kind = ev.get("type")

        if kind == "run":
            run["mode"] = ev.get("mode", run["mode"])
            run["flows_total"] = ev.get("flows_total", run["flows_total"])
            for surf in ev.get("surfaces", []) or []:
                if isinstance(surf, dict):
                    lane(surf.get("id"), surf.get("kind", "web"))
                else:
                    lane(str(surf))
            if ev.get("state") in ("done", "halted"):
                run["finished"] = True
            continue

        if kind == "finding":
            # Canonical finding-event payload: {id, surface_id, flow_id, rule, route, locator,
            # sev, text, evidence, disposition}. disposition ("engine"|"objective"|"judgment")
            # is pre-reconcile only -- it rides along on the live dict, not on LedgerEntry.
            fid = ev.get("id")
            live_findings[fid] = {
                "id": fid, "fingerprint": "", "state": "open", "sev": ev.get("sev"),
                "rule": ev.get("rule"), "flow_id": ev.get("flow_id"),
                "surface_id": ev.get("surface_id"), "route": ev.get("route", ""),
                "locator": ev.get("locator", ""), "text": ev.get("text", ""),
                "evidence": ev.get("evidence", []), "runs_seen": 1,
                "first_run": ts, "last_run": ts, "aliases": [], "reason": "",
                "disposition": ev.get("disposition"),
            }
            continue

        if kind == "withdraw":
            fid = ev.get("finding_id")
            withdrawn.add(fid)
            live_findings.pop(fid, None)
            continue

        if kind == "goal":
            gid = ev.get("flow_id")
            if gid:
                goals[gid] = ev
            continue

        surf_id = ev.get("surface_id") or ev.get("surface")
        if kind == "status":
            if ev.get("state") == "not-exercised":
                # payment-not-sandboxed / no-test-inbox / destructive-no-optin / budget-cap skips
                not_exercised.append(ev)
                continue
            flow = ev.get("flow_id")
            if flow and ev.get("state") in ("ok", "blocked", "skipped"):
                done_flows.add(flow)
            elif surf_id:
                lane(surf_id).state = ev.get("state", lanes[surf_id].state)
            continue

        ln = lane(surf_id) if surf_id else None
        if ln is None:
            continue
        if kind == "shot":
            ln.shot = ev.get("shot") or ln.shot
        elif kind == "output":
            ln.output = ev.get("text") or ln.output
        elif kind == "step":
            ln.flow_id = ev.get("flow_id", ln.flow_id)
            entry = {"step": ev.get("step"), "state": ev.get("state")}
            ln.history.append(entry)
            ln.history[:] = ln.history[-HISTORY_WINDOW:]
            ln.current_step = ev.get("step") if ev.get("state") == "running" else None
        # "usage" events are intentionally not read here -- budget.used(run_dir) is the
        # one source of truth (A-23); summing them again here would be a second truth.

    run["flows_done"] = len(done_flows)
    run["flows_total"] = max(run["flows_total"], run["flows_done"])
    if run["started"] and (last_ts or run["finished"]):
        end = last_ts if run["finished"] else _now_iso()
        run["elapsed_s"] = _elapsed_seconds(run["started"], end)

    led = ledger.load(project_root / ".flow-review" / "findings.json")
    # Canonical: Ledger.findings is dict[str, LedgerEntry] keyed by id -- iterate .values(),
    # never assume a list.
    ledger_findings = [dataclasses.asdict(e) for e in led.findings.values() if e.id not in withdrawn]
    ledger_ids = {f["id"] for f in ledger_findings}
    findings = ledger_findings + [f for fid, f in live_findings.items()
                                   if fid not in ledger_ids and fid not in withdrawn]

    counts = {s: 0 for s in SEVERITIES}
    for f in findings:
        if f.get("state") in LIVE_STATES and f.get("sev") in counts:
            counts[f["sev"]] += 1
    total = sum(counts.values())
    worst = next((s for s in SEVERITIES if counts[s] > 0), None)

    used_tokens = budget.used(run_dir)
    cap_tokens = cfg.budget.get("cap_tokens") if getattr(cfg, "budget", None) else None
    pct = round(used_tokens / cap_tokens, 3) if cap_tokens else None

    return {
        "run": run,
        "budget": {"cap_tokens": cap_tokens, "used_tokens": used_tokens, "pct": pct},
        "badge": {"total": total, "worst_sev": worst, "counts": counts},
        "lanes": [
            {"surface_id": l.surface_id, "kind": l.kind, "state": l.state, "shot": l.shot,
             "output": l.output, "current_step": l.current_step, "flow_id": l.flow_id,
             "history": l.history}
            for l in lanes.values()
        ],
        "header": {"sparkline": header_history, "surface_dots": [
            {"surface_id": l.surface_id, "status": _dot_status(l.state)} for l in lanes.values()
        ]},
        "report": _build_report(findings, goals, not_exercised) if run["finished"] else None,
        "findings": findings,
    }


def _elapsed_seconds(start_iso: str, end_iso: str) -> int:
    try:
        start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
    except ValueError:
        return 0
    return max(0, int((end - start).total_seconds()))


def _dot_status(lane_state: str) -> str:
    return "error" if lane_state in ("blocked", "error") else "ok"


def _is_opinion(f: dict) -> bool:
    return f.get("disposition") == "judgment" and f.get("sev") == "P2"


def _build_report(findings: list[dict], goals: dict[str, dict], not_exercised: list[dict]) -> dict:
    # Spec §11: needs-attention = NEW (open, first seen this run) and REGRESSED, by severity.
    # Judgment P2 (opinions) and open repeats are collapsed, never headline.
    def _new_or_regressed(f):
        return f.get("state") == "regressed" or (f.get("state") == "open" and f.get("runs_seen", 1) == 1)

    needs_attention = sorted(
        (f for f in findings if _new_or_regressed(f) and not _is_opinion(f)),
        key=lambda f: SEVERITIES.index(f.get("sev", "P2")) if f.get("sev") in SEVERITIES else 9,
    )
    return {
        "needs_attention": needs_attention,
        "goal_cards": list(goals.values()),
        "collapsed": {
            "opinions": [f for f in findings if _is_opinion(f) and f.get("state") in ("open", "regressed")],
            "repeats": [f for f in findings if f.get("state") == "open" and f.get("runs_seen", 1) > 1
                        and not _is_opinion(f)],
            "refuted": [f for f in findings if f.get("state") == "refuted"],
            "not_exercised": not_exercised,
        },
    }
```

- [ ] **Step 3: red (static).** Write the test below. Run `pytest plugins/flow-review/engine/flow_review/dashboard/test_static.py -q` → FAIL (`static.py` missing).

```python
# plugins/flow-review/engine/flow_review/dashboard/test_static.py
from __future__ import annotations

import base64
import json
from pathlib import Path

from PIL import Image

from flow_review.dashboard.static import render_static


class _FakeLedger:
    def __init__(self, findings):
        # Canonical: Ledger.findings is dict[str, LedgerEntry] keyed by id.
        self.findings = {e.id: e for e in findings}


class _FakeCfg:
    budget = {"cap_tokens": 200000}


def _seed(tmp_path, extra_events=""):
    project_root = tmp_path / "proj"
    (project_root / ".flow-review").mkdir(parents=True)
    (project_root / ".flow-review" / "findings.json").write_text("{}", encoding="utf-8")
    run_dir = project_root / ".flow-review" / "runs" / "r1"
    run_dir.mkdir(parents=True)
    base = json.dumps({"ts": "2026-09-23T10:00:00.000Z", "id": "e1", "type": "run",
                        "mode": "goal", "surfaces": [], "state": "done"})
    (run_dir / "events.jsonl").write_text(base + "\n" + extra_events, encoding="utf-8")
    return project_root, run_dir


def test_static_is_one_file_with_css_js_and_fonts_inlined(tmp_path, monkeypatch):
    project_root, run_dir = _seed(tmp_path)
    monkeypatch.setattr("flow_review.dashboard.static.ledger.load", lambda p: _FakeLedger([]))
    monkeypatch.setattr("flow_review.dashboard.static.budget.used", lambda rd: 0)
    out_path = tmp_path / "dashboard.html"
    render_static(project_root, run_dir, _FakeCfg(), out_path)
    html = out_path.read_text(encoding="utf-8")

    assert '<script id="state-data" type="application/json">' in html
    assert html.index('id="state-data"') < html.rindex("</body>")
    # no <link rel="stylesheet"> / <script src="..."> to an external page/ file --
    # everything is inlined, A-21.
    assert "<link rel=\"stylesheet\"" not in html
    assert "<script src=\"app.js\"" not in html
    assert "font/woff2;base64," in html  # subsetted fonts inlined
    assert "<svg" in html and "<symbol" in html  # icon sprite inlined, not fetched


def test_static_escapes_script_close_in_user_text(tmp_path, monkeypatch):
    finding_ev = json.dumps({"ts": "2026-09-23T10:00:01.000Z", "id": "f1", "type": "finding",
                              "sev": "P2", "surface_id": "s",
                              "text": "</script><script>alert(1)</script>"})
    project_root, run_dir = _seed(tmp_path, extra_events=finding_ev + "\n")
    monkeypatch.setattr("flow_review.dashboard.static.ledger.load", lambda p: _FakeLedger([]))
    monkeypatch.setattr("flow_review.dashboard.static.budget.used", lambda rd: 0)
    out_path = tmp_path / "dashboard.html"
    render_static(project_root, run_dir, _FakeCfg(), out_path)
    html = out_path.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html


def test_static_thumbnails_are_downscaled_jpeg_data_uris_linking_to_full_res(tmp_path, monkeypatch):
    project_root, run_dir = _seed(tmp_path)
    shots_dir = run_dir / "shots"
    shots_dir.mkdir()
    Image.new("RGB", (1600, 1200), "white").save(shots_dir / "web-app-0042.png")
    shot_ev = json.dumps({"ts": "2026-09-23T10:00:01.000Z", "id": "e2", "type": "shot",
                           "surface_id": "web-app", "shot": "shots/web-app-0042.png"})
    (run_dir / "events.jsonl").open("a", encoding="utf-8").write(shot_ev + "\n")
    monkeypatch.setattr("flow_review.dashboard.static.ledger.load", lambda p: _FakeLedger([]))
    monkeypatch.setattr("flow_review.dashboard.static.budget.used", lambda rd: 0)
    out_path = tmp_path / "dashboard.html"
    render_static(project_root, run_dir, _FakeCfg(), out_path)
    html = out_path.read_text(encoding="utf-8")

    assert 'href="shots/web-app-0042.png"' in html  # links to the full-res file, relative
    assert "data:image/jpeg;base64," in html
    b64 = html.split("data:image/jpeg;base64,")[1].split('"')[0]
    thumb = Image.open(__import__("io").BytesIO(base64.b64decode(b64)))
    assert max(thumb.size) <= 320  # proposed max edge
```

- [ ] **Step 4: green (static).** Implement `static.py`, run again → PASS.

```python
# plugins/flow-review/engine/flow_review/dashboard/static.py
"""flow-review serve --static OUT.html: ONE self-contained snapshot for when
`serve` is not running (attach to a bug report, archive a run). Per A-21:
CSS, JS, the icon sprite and the subsetted fonts (E3) are inlined; screenshots
are embedded as small downscaled JPEG thumbnails that link out to the
full-resolution file in the run folder, never inlined at full size.
"""
from __future__ import annotations

import base64
import io
import json
import re
from pathlib import Path

from PIL import Image

from flow_review import budget, ledger
from flow_review.dashboard.state import fold

PAGE_DIR = Path(__file__).parent / "page"
THUMB_MAX_EDGE = 320   # px, longest edge -- proposed default, tune once real shots are seen
THUMB_QUALITY = 70      # JPEG quality


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _inline_fonts_css() -> str:
    """@font-face rules with base64 data URIs for every subsetted .woff2 in page/fonts/."""
    fonts_dir = PAGE_DIR / "fonts"
    rules = []
    for woff2 in sorted(fonts_dir.glob("*.woff2")):
        family = "Schibsted Grotesk" if "SchibstedGrotesk" in woff2.name else "IBM Plex Mono"
        weight = "600" if "SemiBold" in woff2.name or "Medium" in woff2.name else "400"
        data_uri = f"data:font/woff2;base64,{_b64(woff2.read_bytes())}"
        rules.append(
            f'@font-face{{font-family:"{family}";font-weight:{weight};'
            f'src:url({data_uri}) format("woff2");font-display:swap;}}'
        )
    return "\n".join(rules)


def _thumbnail_data_uri(image_path: Path) -> str | None:
    if not image_path.exists():
        return None
    with Image.open(image_path) as im:
        im = im.convert("RGB")
        im.thumbnail((THUMB_MAX_EDGE, THUMB_MAX_EDGE))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=THUMB_QUALITY)
        return f"data:image/jpeg;base64,{_b64(buf.getvalue())}"


def _thumbnail_block(rel_path: str, run_dir: Path) -> str:
    """A thumbnail linking to the full-res file, or an empty string if the file is missing."""
    full = run_dir / rel_path
    data_uri = _thumbnail_data_uri(full)
    if not data_uri:
        return ""
    return f'<a href="{rel_path}"><img src="{data_uri}" alt=""></a>'


def render_static(project_root: Path, run_dir: Path, cfg, out_path: Path) -> None:
    state = fold(project_root, run_dir, cfg)

    for lane in state["lanes"]:
        if lane.get("shot"):
            lane["shot_thumb_html"] = _thumbnail_block(lane["shot"], run_dir)
    for f in state["findings"]:
        f["evidence_thumbs_html"] = [
            _thumbnail_block(ev, run_dir) for ev in f.get("evidence", [])
            if ev.lower().endswith((".png", ".jpg", ".jpeg"))
        ]

    # JSON is embedded inside an HTML <script> element: escape "</" so user text
    # (a finding title, API output) can never close the tag early. This is the
    # ONE server-side escape this module does -- of the JSON string as a whole,
    # never a template substitution of individual fields (see M8 fix in E2).
    payload = json.dumps(state).replace("</", "<\\/")

    app_css = (PAGE_DIR / "app.css").read_text(encoding="utf-8")
    tokens_css = (PAGE_DIR / "tokens.css").read_text(encoding="utf-8")
    app_js = (PAGE_DIR / "app.js").read_text(encoding="utf-8")
    sprite_svg = (PAGE_DIR / "icons" / "sprite.svg").read_text(encoding="utf-8")
    fonts_css = _inline_fonts_css()

    html = (PAGE_DIR / "index.html").read_text(encoding="utf-8")
    # Strip the external asset links the served page uses; replace with inline equivalents.
    html = re.sub(r'<link rel="stylesheet"[^>]*>\n?', "", html)
    html = re.sub(r'<script src="app\.js"[^>]*></script>\n?', "", html)
    if "<head>" not in html or "</body>" not in html:
        raise ValueError("page/index.html is missing <head> or </body>")

    html = html.replace(
        "<head>",
        f"<head>\n<style>{tokens_css}\n{fonts_css}\n{app_css}</style>",
        1,
    )
    # Icon sprite inlined directly in the body (app.js's <use href="/icons/sprite.svg#x">
    # becomes <use href="#x"> against this inline sprite -- app.js is unchanged either way
    # since <use> resolves a bare fragment against the current document).
    snippet = (
        f'{sprite_svg}\n'
        f'<script id="state-data" type="application/json">{payload}</script>\n'
        f'<script>{app_js}</script>\n</body>'
    )
    html = html.replace("</body>", snippet, 1)

    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(html, encoding="utf-8")
    tmp.replace(out_path)  # atomic-ish: no reader ever sees a half-written file
```

**Verify:** `pytest plugins/flow-review/engine/flow_review/dashboard/test_state.py plugins/flow-review/engine/flow_review/dashboard/test_static.py -q`; open the produced `dashboard.html` with network disabled and confirm it renders (proves it is truly self-contained).

**Commit:** `feat(dashboard): state fold (canonical field names, id-matched withdraw, budget.used) + one-file static fallback (A-21)`

- [ ] **Step 5: Commit.**
  ```bash
  git add plugins/flow-review/engine/flow_review/dashboard/state.py plugins/flow-review/engine/flow_review/dashboard/test_state.py plugins/flow-review/engine/flow_review/dashboard/static.py plugins/flow-review/engine/flow_review/dashboard/test_static.py
  git commit -m "feat(dashboard): page-state fold (events + ledger + budget) and static fallba (E2)"
  ```


---

### Task E3: Design foundation — PRODUCT.md, tokens, fonts, icons

**Executor:** sonnet · **Depends:** — · **Wave:** 1 (can start immediately, parallel with A/B work)

**Files:**
- `plugins/flow-review/skills/flow-review/PRODUCT.md` (impeccable `init` output — outside `dashboard/`, per the File Structure)
- `plugins/flow-review/engine/flow_review/dashboard/page/tokens.css`
- `plugins/flow-review/engine/flow_review/dashboard/page/fonts/` (self-hosted, subsetted `.woff2` files)
- `plugins/flow-review/engine/flow_review/dashboard/page/icons/sprite.svg`
- `plugins/flow-review/engine/flow_review/dashboard/test_tokens.py`

**Interfaces:** none new (styling/static-asset scaffolding). Confirms the direction in the plan header and spec §11 rather than re-deriving it: Schibsted Grotesk (UI), IBM Plex Mono (numbers/logs only), cool neutrals, hairline borders, 4px radius, one blue accent, Phosphor icons — not signed off; E5 finalises it.

**Steps:**

- [ ] **Step 1: `impeccable init`.** Mode = **Operate** (a dashboard the tester watches and triages from, per `impeccable`'s mode table: "App UI, dashboards... outrank expression"). Deliverable: `plugins/flow-review/skills/flow-review/PRODUCT.md` capturing what flow-review is, who watches this dashboard, the Operate mode choice, and the locked design rules from spec §11 (no subheadings/descriptions, tooltips as accessible names, one findings badge, progressive disclosure) as durable constraints. Exit criterion: `PRODUCT.md` exists and states the mode + the locked rules.

- [ ] **Step 2: confirm the direction** (do not reopen it) — Schibsted Grotesk / IBM Plex Mono / cool neutrals / hairlines / 4px radius / one blue accent / Phosphor icons. Deliverable: a design-direction section in `PRODUCT.md` recording the confirmation. Exit criterion: present in `PRODUCT.md`.

- [ ] **Step 3: font download + subset (concrete commands).** Deliverable: `page/fonts/*.woff2`, two weights of Schibsted Grotesk (Regular 400, SemiBold 600) and one of IBM Plex Mono (Regular 400) — a UI face needs a body/emphasis pair, the mono face is numbers/logs only and needs no emphasis weight. Exit criterion: the four (3) files exist and are the **Latin subset only** (this is a dashboard, not an i18n product at M1).
  ```bash
  pip install fonttools brotli
  # Google Fonts' standard "latin" unicode range:
  LATIN="U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD"

  pyftsubset SchibstedGrotesk-Regular.ttf \
    --output-file=plugins/flow-review/engine/flow_review/dashboard/page/fonts/SchibstedGrotesk-Regular-latin.woff2 \
    --flavor=woff2 --unicodes="$LATIN"
  pyftsubset SchibstedGrotesk-SemiBold.ttf \
    --output-file=plugins/flow-review/engine/flow_review/dashboard/page/fonts/SchibstedGrotesk-SemiBold-latin.woff2 \
    --flavor=woff2 --unicodes="$LATIN"
  pyftsubset IBMPlexMono-Regular.ttf \
    --output-file=plugins/flow-review/engine/flow_review/dashboard/page/fonts/IBMPlexMono-Regular-latin.woff2 \
    --flavor=woff2 --unicodes="$LATIN"
  ```
  **Why self-hosted, not a Google Fonts `<link>`:** `serve.py` binds `127.0.0.1` and the whole engine principle is "never calls an LLM API" / works offline — a CI box or an air-gapped dev machine running `flow-review serve` must not depend on a font CDN being reachable, and a live-push dashboard that stalls on a font request mid-run is exactly the kind of failure this rebuild is fixing. Both families are OFL-licensed, self-hosting is explicitly permitted.

- [ ] **Step 4: icons — inline SVG sprite, no runtime CDN.** Deliverable: `page/icons/sprite.svg`, a single `<svg>` with one `<symbol id="...">` per Phosphor glyph actually used (severity, triage actions, theme toggle, drawer close, ...), hand-picked from Phosphor's SVG source (MIT-licensed) — not fetched at runtime. Referenced from markup as `<svg><use href="/icons/sprite.svg#name"></use></svg>` when served, and inlined directly by `static.py` (E2) for the one-file fallback. Exit criterion: `sprite.svg` exists with at least the glyphs E4 needs (severity dot, check/x/flag/reopen for triage, sun/moon for theme, x for drawer close).

- [ ] **Step 5: tokens — red.** Write the test below. Run `pytest plugins/flow-review/engine/flow_review/dashboard/test_tokens.py -q` → FAIL (`tokens.css` missing).

```python
# plugins/flow-review/engine/flow_review/dashboard/test_tokens.py
from __future__ import annotations

import re
from pathlib import Path

TOKENS = Path(__file__).parent / "page" / "tokens.css"

REQUIRED_TOKENS = [
    "--bg", "--panel", "--border", "--text-1", "--text-2", "--accent", "--radius",
    "--sev-p0", "--sev-p1", "--sev-p2", "--font-ui", "--font-mono",
]


def test_tokens_file_exists():
    assert TOKENS.exists(), "page/tokens.css must exist (E3)"


def test_root_defines_all_required_tokens():
    css = TOKENS.read_text(encoding="utf-8")
    root_block = re.search(r":root\s*\{([^}]*)\}", css, re.DOTALL)
    assert root_block, "tokens.css must define a base :root block"
    body = root_block.group(1)
    missing = [t for t in REQUIRED_TOKENS if t not in body]
    assert not missing, f"missing tokens in :root: {missing}"


def test_dark_theme_overrides_are_present_both_ways():
    css = TOKENS.read_text(encoding="utf-8")
    assert "@media (prefers-color-scheme: dark)" in css, "OS-driven dark mode is missing"
    assert '[data-theme="dark"]' in css, "explicit dark-toggle override is missing"


def test_radius_is_4px():
    css = TOKENS.read_text(encoding="utf-8")
    match = re.search(r"--radius:\s*([^;]+);", css)
    assert match and match.group(1).strip() == "4px"


def test_palette_validator_run_is_recorded_in_a_comment():
    css = TOKENS.read_text(encoding="utf-8")
    assert "validate_palette.js" in css, (
        "A-23: the severity palette validator is a one-time MANUAL check -- its command "
        "and PASS result must be recorded in a tokens.css comment, not re-run in CI."
    )
```

- [ ] **Step 6: tokens — green.** Write `page/tokens.css` (one token set on `:root`, dark overrides under both `@media (prefers-color-scheme: dark)` guarded by `:root:not([data-theme="light"])` and an explicit `:root[data-theme="dark"]` block for the in-page toggle from E4). Minimum surface: `--bg`, `--panel`, `--border`, `--text-1`, `--text-2`, `--accent` (the one blue), `--radius: 4px`, `--sev-p0/p1/p2` (status colors — reserved, never reused per dataviz's non-negotiables), `--font-ui` (Schibsted Grotesk stack incl. the self-hosted `@font-face`s from Step 3), `--font-mono` (IBM Plex Mono stack), plus a spacing scale (`--space-1..6`).

  **One-time manual palette validation (A-23) — run once when the severity hex values are picked, then record the exact command and result as a comment in `tokens.css`** (never re-run in CI; re-run only if the hex values themselves change):
  ```css
  /* --sev-p0/p1/p2 validated 2026-09-23 via dataviz's validator:
     node <dataviz-skill-dir>/scripts/validate_palette.js "<p0-hex>,<p1-hex>,<p2-hex>" --mode light
     node <dataviz-skill-dir>/scripts/validate_palette.js "<p0-hex>,<p1-hex>,<p2-hex>" --mode dark
     Both PASS: lightness band, chroma floor, adjacent-pair CVD Delta E >= 8, contrast.
     One-time manual check (A-23) -- re-run only if these hex values change. */
  ```
  Run the test again → PASS.

**Verify:** `pytest plugins/flow-review/engine/flow_review/dashboard/test_tokens.py -q`; visually open a throwaway HTML file linking `tokens.css` with OS light/dark toggled, confirm both render and the self-hosted fonts load with network disabled.

**Commit:** `feat(dashboard): design foundation — PRODUCT.md, tokens.css (both themes, validated severity palette), subsetted self-hosted fonts, icon sprite`

- [ ] **Step 7: Commit.**
  ```bash
  git add plugins/flow-review/skills/flow-review/PRODUCT.md plugins/flow-review/engine/flow_review/dashboard/page/tokens.css plugins/flow-review/engine/flow_review/dashboard/page/icons/sprite.svg plugins/flow-review/engine/flow_review/dashboard/test_tokens.py
  git commit -m "feat(dashboard): design foundation (E3)"
  ```


---

### Task E4: run page build — lanes, header, badge, drawer, report, triage, live updates

**Executor:** sonnet · **Depends:** E1, E2, E3 · **Wave:** 6

**Files:**
- `plugins/flow-review/engine/flow_review/dashboard/page/index.html`
- `plugins/flow-review/engine/flow_review/dashboard/page/app.js`
- `plugins/flow-review/engine/flow_review/dashboard/page/app.css`
- `plugins/flow-review/engine/flow_review/dashboard/test_page_build.py`

**Interfaces:**

Consumes: `GET /state`, `GET /events` (SSE `state` messages), `POST /triage` (E1); the state JSON shape (E2); `page/tokens.css`, fonts, `icons/sprite.svg` (E3). Falls back to `#state-data` (E2's `static.py`) when present, skipping `fetch`/`EventSource` entirely.

Produces: the rendered page — no new server interface, this is the client.

**Stack: vanilla ES modules + CSS, no build step (A-22, confirmed).** Revisit only if `app.js` passes ~1k lines.

`app.js` is built up across the six steps below; each step's code block is additive — by Step 6 the file contains everything shown. Tests are structural (regex over the source) rather than a headless-browser harness per step, matching the rest of this task list's pattern; true rendered-DOM/visual correctness is exercised by E5's Playwright screenshot pass and this task's own manual Verify.

- [ ] **Step 1: bootstrap & state load — red.** Write the test, run it → FAIL.

```python
# plugins/flow-review/engine/flow_review/dashboard/test_page_build.py (grows across steps 1-6)
from __future__ import annotations

import re
from pathlib import Path

PAGE = Path(__file__).parent / "page"


def _js() -> str:
    return (PAGE / "app.js").read_text(encoding="utf-8")


def _html() -> str:
    return (PAGE / "index.html").read_text(encoding="utf-8")


def _css() -> str:
    return (PAGE / "app.css").read_text(encoding="utf-8")


# ---- Step 1: bootstrap & state load --------------------------------------

def test_bootstraps_from_embedded_state_or_fetches_and_streams():
    js = _js()
    assert "getElementById('state-data')" in js or 'getElementById("state-data")' in js
    assert "fetch('/state')" in js or 'fetch("/state")' in js
    assert "new EventSource('/events')" in js or 'new EventSource("/events")' in js
    assert re.search(r"function patch\s*\(", js)


# ---- Step 2: no subheadings / descriptions in the static shell -----------

def test_index_has_no_h2_to_h6_or_description_markup():
    html = _html()
    assert not re.search(r"<h[2-6][\s>]", html, re.IGNORECASE), "no subheadings anywhere (spec §11)"
    assert "<p " not in html and "<p>" not in html, "no description paragraphs in the shell"
```

- [ ] **Step 1: bootstrap & state load — green.**

```javascript
// page/app.js (grows across all 6 steps -- this is the top of the file)
'use strict';

let state = null;
let openDrawerId = null;   // preserved across patches (Step 2)
let prevBadgeTotal = 0;    // for the new-P0 flash (Step 4)

function patch(newState) {
  state = newState;
  render();
}

function render() {
  renderHeader(state);
  renderBadge(state.badge);
  renderLanes(state.lanes);
  if (state.run.finished) renderReport(state.report);
}

function boot() {
  const embedded = document.getElementById('state-data');
  if (embedded) {
    // Static fallback (E2's static.py): no server exists, never open EventSource.
    patch(JSON.parse(embedded.textContent));
    return;
  }
  fetch('/state').then(r => r.json()).then(patch);
  const es = new EventSource('/events');   // auto-reconnects on drop, no manual retry logic
  es.addEventListener('state', e => patch(JSON.parse(e.data)));
}

document.addEventListener('DOMContentLoaded', boot);
```

```html
<!-- page/index.html (shell only -- lanes/header/drawer content is rendered by app.js) -->
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>flow-review</title>
  <link rel="preload" href="fonts/SchibstedGrotesk-Regular-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="tokens.css">
  <link rel="stylesheet" href="app.css">
</head>
<body>
  <header class="topbar">
    <div class="stat" data-role="progress"></div>
    <div class="stat" data-role="elapsed"></div>
    <div class="meter" data-role="budget"></div>
    <button class="badge" data-role="badge" aria-label="findings" title=""></button>
    <div class="sparkline" data-role="sparkline" hidden></div>
    <div class="dots" data-role="surface-dots" hidden></div>
    <button class="icon-btn" data-role="theme-toggle" aria-label="toggle theme" title="toggle theme">
      <svg><use href="icons/sprite.svg#sun-moon"></use></svg>
    </button>
  </header>
  <main class="lanes" data-role="lanes"></main>
  <section class="report" data-role="report" hidden></section>
  <aside class="drawer" data-role="drawer" hidden></aside>
  <script src="app.js"></script>
</body>
</html>
```

Run Step 1's test → PASS.

- [ ] **Step 2: live patch preserving scroll + open drawer — red.**

```python
def test_patch_preserves_lane_scroll_and_open_drawer():
    js = _js()
    assert "scrollTop" in js, "scroll position must be saved/restored across a patch"
    assert "openDrawerId" in js
    # the lane container is diffed by key (surface_id), never wiped wholesale
    assert "innerHTML = ''" not in js and 'innerHTML = ""' not in js
```

- [ ] **Step 2: green.**

```javascript
// replaces the earlier patch()/render() in app.js
function patch(newState) {
  const laneEl = document.querySelector('[data-role="lanes"]');
  const savedScroll = laneEl ? laneEl.scrollTop : 0;
  state = newState;
  render();
  if (laneEl) laneEl.scrollTop = savedScroll;
  if (openDrawerId) hydrateDrawer(openDrawerId);   // re-hydrate content, don't re-open/re-animate
}
```

Run → PASS.

- [ ] **Step 3: lane grid render (auto-fit, keyed, text-safe) — red.**

```python
def test_lanes_grid_uses_auto_fit_minmax_not_fixed_columns():
    css = _css()
    lanes_block = re.search(r"\.lanes\s*\{([^}]*)\}", css, re.DOTALL)
    assert lanes_block, "app.css must define a .lanes grid"
    body = lanes_block.group(1)
    assert "auto-fit" in body or "auto-fill" in body, "fixes M7: must not be a hardcoded 3-col grid"
    assert re.search(r"minmax\(", body), "auto-grid needs minmax() to size lanes"
    assert not re.search(r"repeat\(\s*\d+\s*,", body), "no hardcoded lane count"


def test_render_lanes_is_keyed_and_uses_textcontent_for_user_text():
    js = _js()
    assert re.search(r"function renderLanes\s*\(", js)
    assert "dataset.surfaceId" in js
    assert ".textContent =" in js
    assert ".innerHTML =" not in js, "user text (step labels, API/CLI output) must never use innerHTML (M8)"
```

- [ ] **Step 3: green.**

```css
/* page/app.css -- structural only, every color a var(--token) from tokens.css */
.lanes{
  display:grid;
  grid-template-columns:repeat(auto-fit, minmax(280px, 1fr));
  gap:1px;
  background:var(--border);
}
.lane{ background:var(--panel); border-radius:var(--radius); padding:var(--space-3); }
```

```javascript
function renderLanes(lanes) {
  const root = document.querySelector('[data-role="lanes"]');
  const seen = new Set();
  for (const lane of lanes) {
    seen.add(lane.surface_id);
    let el = root.querySelector(`[data-surface-id="${CSS.escape(lane.surface_id)}"]`);
    if (!el) {
      el = document.createElement('section');
      el.className = 'lane';
      el.dataset.surfaceId = lane.surface_id;
      el.innerHTML = `
        <div class="lane-head"><span class="lane-name"></span></div>
        <div class="shot"></div>
        <div class="output mono"></div>
        <div class="current-step"></div>`;
      root.appendChild(el);
    }
    el.querySelector('.lane-name').textContent = lane.surface_id;
    el.className = `lane lane-${lane.state}`;
    const shotEl = el.querySelector('.shot');
    if (lane.shot) {
      shotEl.innerHTML = '';
      const img = document.createElement('img');
      img.src = lane.shot;
      img.alt = lane.surface_id + ' latest screen';
      shotEl.appendChild(img);
    } else if (lane.output != null) {
      el.querySelector('.output').textContent = lane.output;   // API/CLI lanes: text, not a shot
    }
    el.querySelector('.current-step').textContent = lane.current_step || '';
  }
  for (const stale of root.querySelectorAll('[data-surface-id]')) {
    if (!seen.has(stale.dataset.surfaceId)) stale.remove();
  }
}
```

Run → PASS.

- [ ] **Step 4: badge (tint, hover split, click list, one eased P0 flash) — red.**

```python
def test_badge_tint_hover_click_and_p0_flash():
    js = _js()
    assert re.search(r"function renderBadge\s*\(", js)
    assert re.search(r"`sev-\$\{.*worst_sev", js), "badge class must tint by worst_sev"
    assert "el.title =" in js, "hover split (P0/P1/P2) is the accessible title, not a tooltip lib"
    assert "badge-flash" in js
    assert "animationend" in js, "the P0 highlight is one eased animation, removed after it plays"
    assert "addEventListener('click'" in js or 'addEventListener("click"' in js
```

- [ ] **Step 4: green.**

```javascript
function renderBadge(badge) {
  const el = document.querySelector('[data-role="badge"]');
  const prevTotal = prevBadgeTotal;
  prevBadgeTotal = badge.total;
  el.className = `badge sev-${badge.worst_sev || 'none'}`;
  el.textContent = String(badge.total);                 // textContent, never innerHTML -- M8 fix
  el.title = `P0 ${badge.counts.P0} · P1 ${badge.counts.P1} · P2 ${badge.counts.P2}`;
  if (badge.counts.P0 > 0 && badge.total > prevTotal) {
    el.classList.add('badge-flash');                    // one eased highlight on a new P0
    el.addEventListener('animationend', () => el.classList.remove('badge-flash'), { once: true });
  }
}

document.querySelector('[data-role="badge"]').addEventListener('click', () => {
  toggleFindingsList(state.findings);   // click opens the list (defined alongside the drawer, Step 5)
});
```

```css
.badge{ border-radius:var(--radius); border:1px solid var(--border); background:var(--panel); }
.badge.sev-P0{ color:var(--sev-p0); border-color:var(--sev-p0); }
.badge.sev-P1{ color:var(--sev-p1); border-color:var(--sev-p1); }
.badge.sev-P2{ color:var(--sev-p2); border-color:var(--sev-p2); }
@keyframes badge-flash{ 0%{ transform:scale(1); } 40%{ transform:scale(1.18); } 100%{ transform:scale(1); } }
.badge-flash{ animation:badge-flash 420ms ease-out; }
@media (prefers-reduced-motion: reduce){ .badge-flash{ animation:none; } }
```

Run → PASS.

- [ ] **Step 5: drawer (evidence per type) + triage icon buttons + keyboard shortcuts — red.**

```python
def test_drawer_evidence_dispatch_and_triage_and_keyboard_shortcuts():
    js = _js()
    assert re.search(r"function openDrawer\s*\(", js)
    assert re.search(r"function renderEvidence\s*\(", js)
    assert "before/after" in js or "beforeAfter" in js or "before_after" in js
    assert re.search(r"function triage\s*\(", js)
    assert "'/triage'" in js or '"/triage"' in js
    assert "finding_id" in js and "state" in js
    assert "addEventListener('keydown'" in js or 'addEventListener("keydown"' in js
    assert "if (!openDrawerId) return" in js, "triage keys must be scoped to an open drawer, never lane rows"
    assert "'Escape'" in js or '"Escape"' in js
```

- [ ] **Step 5: green.**

```javascript
function openDrawer(findingId) {
  openDrawerId = findingId;
  hydrateDrawer(findingId);
  document.querySelector('[data-role="drawer"]').hidden = false;
}

function closeDrawer() {
  openDrawerId = null;
  document.querySelector('[data-role="drawer"]').hidden = true;
}

function hydrateDrawer(findingId) {
  const finding = state.findings.find(f => f.id === findingId);
  const root = document.querySelector('[data-role="drawer"]');
  if (!finding) { closeDrawer(); return; }
  root.innerHTML = `
    <div class="drawer-head"></div>
    <div class="drawer-evidence"></div>
    <div class="drawer-triage">
      <button data-triage="fixed" aria-label="mark fixed" title="mark fixed"><svg><use href="icons/sprite.svg#check"></use></svg></button>
      <button data-triage="false-positive" aria-label="false positive" title="false positive (f)"><svg><use href="icons/sprite.svg#flag-off"></use></svg></button>
      <button data-triage="wont-fix" aria-label="won't fix" title="won't fix (w)"><svg><use href="icons/sprite.svg#x"></use></svg></button>
      <button data-triage="accepted" aria-label="accept" title="accept (a)"><svg><use href="icons/sprite.svg#thumbs-up"></use></svg></button>
      <button data-triage="open" aria-label="reopen" title="reopen"><svg><use href="icons/sprite.svg#arrow-counter-clockwise"></use></svg></button>
    </div>`;
  root.querySelector('.drawer-head').textContent = finding.text;   // textContent -- M8 fix
  renderEvidence(finding, root.querySelector('.drawer-evidence'));
  for (const btn of root.querySelectorAll('[data-triage]')) {
    btn.addEventListener('click', () => triage(finding.id, btn.dataset.triage));
  }
}

// Evidence per type: before/after for regressions, an annotated shot for visual findings,
// text first for API/CLI (spec §11).
function renderEvidence(finding, container) {
  container.innerHTML = '';
  if (finding.rule === 'regression' && finding.evidence.length >= 2) {
    const wrap = document.createElement('div');
    wrap.className = 'before-after';
    for (const src of finding.evidence.slice(0, 2)) {
      const img = document.createElement('img');
      img.src = src;
      wrap.appendChild(img);
    }
    container.appendChild(wrap);
  } else if (finding.surface_id && isVisual(finding)) {
    const img = document.createElement('img');
    img.className = 'annotated-shot';
    img.src = finding.evidence[0] || '';
    container.appendChild(img);
  } else {
    const pre = document.createElement('pre');
    pre.className = 'mono';
    pre.textContent = (finding.evidence[0] || '');   // API/CLI text first, textContent only
    container.appendChild(pre);
  }
}

function isVisual(finding) {
  return ['contrast', 'layout', 'visual-diff'].includes(finding.rule);
}

function triage(findingId, newState) {
  fetch('/triage', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ finding_id: findingId, state: newState }),
  }).then(r => r.json()).then(res => { if (res.error) showTriageError(res.error); });
}

function showTriageError(message) {
  const el = document.querySelector('[data-role="drawer"] .drawer-head');
  if (el) el.title = message;   // no toast subheading -- an accessible-name-style hint only
}

// Triage keys + drawer navigation -- ONLY act when a drawer is open, never on lane/finding rows.
document.addEventListener('keydown', (e) => {
  if (!openDrawerId) return;
  const key = { f: 'false-positive', w: 'wont-fix', a: 'accepted', x: 'fixed' }[e.key];
  if (key) { triage(openDrawerId, key); return; }
  if (e.key === 'Escape') { closeDrawer(); return; }
  if (e.key === 'j' || e.key === 'k') focusAdjacentFinding(e.key === 'j' ? 1 : -1);
});

function focusAdjacentFinding(delta) {
  const ids = state.findings.map(f => f.id);
  const i = ids.indexOf(openDrawerId);
  if (i === -1) return;
  const next = ids[(i + delta + ids.length) % ids.length];
  openDrawer(next);
}
```

Run → PASS.

- [ ] **Step 6: theme toggle (OS + explicit, persisted) — red.**

```python
def test_theme_toggle_sets_data_theme_and_persists():
    js = _js()
    assert "data-role=\"theme-toggle\"" in _html() or "data-role='theme-toggle'" in _html()
    assert "documentElement.dataset.theme" in js or "documentElement.setAttribute('data-theme'" in js
    assert "localStorage" in js
    assert "try {" in js and "catch" in js, "storage access must be wrapped -- private windows can throw"
```

- [ ] **Step 6: green.**

```javascript
function applyStoredTheme() {
  try {
    const saved = localStorage.getItem('flow-review-theme');
    if (saved) document.documentElement.dataset.theme = saved;
  } catch (_) { /* private window / blocked storage: fall through to OS preference */ }
}

document.querySelector('[data-role="theme-toggle"]').addEventListener('click', () => {
  const current = document.documentElement.dataset.theme
    || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem('flow-review-theme', next); } catch (_) { /* best effort only */ }
});

applyStoredTheme();
```

Run all of `test_page_build.py` → PASS.

**Verify:** `pytest plugins/flow-review/engine/flow_review/dashboard/test_page_build.py -q`; `flow-review serve <fixture-run-dir>` and manually confirm live SSE patch (append a fake event line, see the DOM update with scroll/drawer preserved), 1-lane and 4-lane layouts, theme toggle, and drawer keyboard shortcuts (f/w/a/x/Escape/j/k).

**Commit:** `feat(dashboard): run page — auto-grid lanes, badge, drawer, live SSE patching, triage shortcuts, theme toggle`

- [ ] **Step 7: Commit.**
  ```bash
  git add plugins/flow-review/engine/flow_review/dashboard/page/index.html plugins/flow-review/engine/flow_review/dashboard/page/app.js plugins/flow-review/engine/flow_review/dashboard/page/app.css plugins/flow-review/engine/flow_review/dashboard/test_page_build.py
  git commit -m "feat(dashboard): run page build (E4)"
  ```


---

### Task E5: full design pass + mechanical rule-lint + screenshot review

**Executor:** sonnet · **Depends:** E4 · **Wave:** 7

**Files:**
- Edits across `plugins/flow-review/engine/flow_review/dashboard/page/{index.html,app.css,app.js,tokens.css}` (no new paths — this task refines E3/E4's output)
- `plugins/flow-review/engine/flow_review/dashboard/test_rule_lint.py`
- `plugins/flow-review/engine/flow_review/dashboard/test_screenshots.py` (Playwright, manual-review harness)

**Interfaces:** none new — consumes the finished E4 page; produces no runtime interface, only the polished page plus a permanent lint gate.

**Ordered design-pass steps (each a Skill invocation with its deliverable and exit criterion):**

- [ ] **Step 1: `impeccable` — new-work pass, then `polish`.** Target: the served run page (point it at `page/index.html` running under `flow-review serve` against the fixture app from B0, so it has real data to render, not an empty shell). Deliverable: edits to `app.css`/`app.js`/`index.html`. Exit criterion: a second `impeccable audit` (or the same command's own pass/fail) reports no craft-floor violations; spot-check against `reference/craft-floor.md`'s absolute bans.
- [ ] **Step 2: `taste-skill:taste-skill`.** Anti-slop check against the same page. Deliverable: direct edits removing any templated/generic-AI visual tells. Exit criterion: taste-skill's own pre-flight check passes clean.
- [ ] **Step 3: `uiux-pro-max`.** Design-intelligence review: visual hierarchy, micro-interactions, accessibility, modern-aesthetic standards. Deliverable: a findings list, applied. Exit criterion: no open "critical" or "serious" findings remain.
- [ ] **Step 4: `hallmark` (audit mode).** Anti-AI-slop audit specifically. Deliverable: audit findings, applied. Exit criterion: hallmark's audit re-run is clean.
- [ ] **Step 5: `animotion`.** Motion library/patterns for the badge's eased P0 highlight, drawer open/close, live-patch transitions. Deliverable: CSS transitions/keyframes wired, all gated behind `@media (prefers-reduced-motion: reduce)`. Exit criterion: every animation added has a reduced-motion counterpart (checked mechanically below).

**Mechanical rule-lint — TDD, full code:**

- [ ] **Step 6: rule-lint — red.** Write the test below. Run `pytest plugins/flow-review/engine/flow_review/dashboard/test_rule_lint.py -q` → FAIL (pre-existing E4 output likely still has gaps: no reduced-motion query yet on every animation, animotion not yet applied).

```python
# plugins/flow-review/engine/flow_review/dashboard/test_rule_lint.py
from __future__ import annotations

import re
from pathlib import Path

PAGE = Path(__file__).parent / "page"


def _all_markup_text() -> str:
    # index.html plus any innerHTML/template strings app.js might build client-side --
    # scanned as text since app.js has no build step to statically render.
    html = (PAGE / "index.html").read_text(encoding="utf-8")
    js = (PAGE / "app.js").read_text(encoding="utf-8")
    return html + "\n" + js


def test_no_subheading_or_description_elements_anywhere():
    text = _all_markup_text()
    assert not re.search(r"<h[2-6][\s>]", text, re.IGNORECASE)
    assert not re.search(r"<p[\s>]", text, re.IGNORECASE)
    assert "class=\"description\"" not in text and "class='description'" not in text


def test_every_icon_only_button_has_aria_label_and_title():
    text = _all_markup_text()
    for m in re.finditer(r"<button[^>]*>(.*?)</button>", text, re.DOTALL):
        attrs, inner = m.group(0), m.group(1)
        if "<svg" in inner and not re.search(r">\s*\S", inner):
            assert 'aria-label="' in attrs
            assert 'title="' in attrs


def test_no_hardcoded_colors_outside_tokens_css():
    for path in PAGE.glob("*.css"):
        if path.name == "tokens.css":
            continue
        css = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
        assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", css), f"hex color in {path.name}"
        assert not re.findall(r"\brgba?\([^)]*\)", css), f"rgb()/rgba() in {path.name}"


def test_reduced_motion_media_query_present():
    css = (PAGE / "app.css").read_text(encoding="utf-8")
    assert "@media (prefers-reduced-motion: reduce)" in css


def test_both_themes_defined_in_tokens():
    css = (PAGE / "tokens.css").read_text(encoding="utf-8")
    assert "@media (prefers-color-scheme: dark)" in css
    assert '[data-theme="dark"]' in css
    assert '[data-theme="light"]' in css or ':root:not([data-theme="dark"])' in css
```

- [ ] **Step 7: rule-lint — green.** Apply the design-pass fixes from Steps 1-5 until every assertion holds. Run again → PASS.

**Manual screenshot review (Playwright, human/agent-reviewed, not pass/fail asserted beyond "captured"):**

- [ ] **Step 8: screenshot capture harness.**

```python
# plugins/flow-review/engine/flow_review/dashboard/test_screenshots.py
"""Not a correctness gate -- captures reference screenshots for a manual look.
Requires `playwright install chromium` and a running fixture-backed `flow-review serve`.
Run explicitly: pytest test_screenshots.py -q -m manual
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.manual

SCENARIOS = [
    ("light", 1), ("dark", 1), ("light", 4), ("dark", 4),
]


@pytest.mark.parametrize("theme,lane_count", SCENARIOS)
def test_capture_theme_and_lane_variants(theme, lane_count, dashboard_server, tmp_path):
    # `dashboard_server` fixture (conftest.py, owned by this task): starts `flow-review serve`
    # against a fixture run folder seeded with `lane_count` surfaces via events.append, and
    # tears it down after the test.
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(color_scheme=theme)
        page.goto(dashboard_server.url)
        page.wait_for_selector('[data-role="lanes"]')
        out = tmp_path / f"{theme}-{lane_count}lane.png"
        page.screenshot(path=str(out), full_page=True)
        browser.close()
    assert out.exists() and out.stat().st_size > 0
    # No pixel assertions here -- the exit criterion is a human (or the impeccable-finish-reviewer
    # agent) looking at these four PNGs and confirming: no subheadings/descriptions, badge tint
    # correct, auto-grid looks right at 1 and 4 lanes, both themes legible.
```

**Verify (checkpoint for this task):** `pytest plugins/flow-review/engine/flow_review/dashboard/test_rule_lint.py -q` green; `pytest plugins/flow-review/engine/flow_review/dashboard/test_screenshots.py -q -m manual` produces 4 PNGs; a human (or `impeccable-finish-reviewer`) looks at all 4 and confirms the design-pass exit criteria above.

**Commit:** `polish(dashboard): design pass (impeccable/taste-skill/uiux-pro-max/hallmark/animotion) + rule-lint gate`

- [ ] **Step 9: Commit.**
  ```bash
  git add plugins/flow-review/engine/flow_review/dashboard/test_rule_lint.py plugins/flow-review/engine/flow_review/dashboard/test_screenshots.py
  git commit -m "feat(dashboard): full design pass + mechanical rule-lint + screenshot review (E5)"
  ```


## Checkpoints

Each checkpoint is run by an **opus** reviewer using superpowers:verification-before-completion (evidence before assertions) and superpowers:requesting-code-review. A checkpoint fails when any command below fails. Fix forward in the owning task, then re-run the whole checkpoint.

### Task CP1: Foundations checkpoint
**Executor:** opus · **Depends:** A1-A10 · **Wave:** 4
- [ ] **Step 1: Full suite.** Run `python -m pytest -q` from the repo root. Expected: all pass, 0 errors, no skips except `web`-marked tests.
- [ ] **Step 2: No import-time stdout side effects.** Run `python -m pytest -q plugins/flow-review/skills/flow-review/test_references.py -k stdout`. Expected: PASS.
- [ ] **Step 3: CLI smoke.** Run `python -m flow_review.cli --help`. Expected: exit 0, listing `setup-env migrate prove plan event replay serve triage ledger budget model`.
- [ ] **Step 4: v1 migration end to end.** Write the v1 config fixture from A3's test module into `<tmp>/.flow-review/config.json`, then run `flow-review migrate --project <tmp>`. Expected: `<tmp>/.flow-review/config.v1.bak` equals the original bytes, `config.json` has `"schema_version": 2`, and a change summary is printed.
- [ ] **Step 5: Audit closure table.** For each audit item C1, C4, C5, H1-H4, H7-H11, M1, M3, M8, M9, name the test that now fails if the defect returns. Any item without a test = checkpoint fail.
- [ ] **Step 6: Review.** Code-review the A-series diff against the spec §2 and Canonical Interfaces. Record the findings in the PR/commit notes.

### Task CP2: Engine loop checkpoint
**Executor:** opus · **Depends:** B0-B10, CP1 · **Wave:** 9
- [ ] **Step 1: Browser install.** Run `python -m playwright install chromium`. Expected: exit 0.
- [ ] **Step 2: Full suite including web.** Run `python -m pytest -q -m "web or not web"`. Expected: all pass.
- [ ] **Step 3: Fixture e2e without recording.** Run `flow-review plan --mode quick --goal "sign in" --json` against the fixture project. Expected: the JSON has the estimate and gaps; nothing is written under `.flow-review/recordings/`.
- [ ] **Step 4: Fixture e2e with recording.** Record the fixture's sign-in flow (B2 test helper), then run `flow-review replay`. Expected: exit 1, with findings for each planted measurable bug (`contrast.aa`, `token.color` near-miss, `rect.overlap`, `http.5xx`). Then break a locator in the fixture copy and run it again. Expected: exit 2 and `.flow-review/divergences.json` written.
- [ ] **Step 5: Secrets.** Grep the run folder, ledger and recordings for the fixture password value. Expected: no match.
- [ ] **Step 6: Review.** Opus review of the B-series against spec §3, §5, §6, §9, §10 and A-1..A-3, A-7, A-16..A-20.

### Task CP3: Plugin dry-run checkpoint
**Executor:** opus · **Depends:** C1-C7, E1-E5, CP2 · **Wave:** 12
- [ ] **Step 1: Suite.** Run `python -m pytest -q -m "web or not web"`. Expected: all pass.
- [ ] **Step 2: Install the plugin locally.** From the repo root in a fresh Claude Code session: `/plugin marketplace add ./` then `/plugin install flow-review@flow-review`. Expected: the agents are listed with pinned models (`/agents`).
- [ ] **Step 3: Quick run.** In a copy of the fixture project: `/flow-review quick sign in`. Expected: the GO gate shows the estimate + one destructive multi-select (if any persistent surface) + the creds gap; `serve` prints a localhost URL; the page updates live; the ledger contains the planted measurable findings; no model is `inherit` in the dispatch log.
- [ ] **Step 4: Auto run.** `/flow-review` (no goal). Expected: cold-eyes then docs pass; the docs-only page appears as a goal-card metric "from docs" (first miss, A-8), not as a finding.
- [ ] **Step 5: Triage round trip.** Mark one finding false-positive in the drawer with a keyboard shortcut; re-run quick. Expected: it stays collapsed with runs_seen+1 (A-15), and the lens prompt shows it as a suppression.
- [ ] **Step 6: Review.** Opus review of the C- and E-series against spec §4, §5, §7, §8, §11 and the dashboard rules.

### Task CP4: M1 release checkpoint
**Executor:** opus · **Depends:** all · **Wave:** 13
- [ ] **Step 1: Build.** `cd plugins/flow-review/engine && python -m build && python -m twine check dist/*`. Expected: both pass.
- [ ] **Step 2: Clean-venv install.** `uv venv /tmp/frv && uv pip install --python /tmp/frv "plugins/flow-review/engine[web]"`, then `flow-review --help` from that venv. Expected: exit 0.
- [ ] **Step 3: Version bump.** Set `plugin.json` `version` to `2.0.0` and the pyproject version to match; `test_manifests.py` passes.
- [ ] **Step 4: Publish gate.** Ask the user before `twine upload` (A-10). Do not publish without an explicit go.
- [ ] **Step 5: Final verification.** superpowers:verification-before-completion over the whole M1: the suite, CP2 Step 4, CP3 Step 3, all re-run fresh, with output quoted.

## Later milestones (direction only)

**M2: Tauri.** Promote `pending-driver` Tauri surfaces to runnable. Explore and measure web-first in Chromium against the dev server with `invoke` mocked via `@tauri-apps/api/mocks` (mock fixtures recorded per command), reusing the whole M1 web loop unchanged. Then add a native-confirm stage that replays each finding's repro on the real app: WebView2 over CDP on Windows, tauri-driver on Linux, and the macOS accessibility API plus screenshots (no computed-style checks there). Drift and detection already know Tauri from A9; the config gains a `tauri` options block.

**M3: Mobile (Maestro).** Maestro YAML becomes the recording format for mobile surfaces, mapped from the same action-log concepts (semantic locators → Maestro selectors). `maestro hierarchy` supplies the view tree for measurement (tap-target size, overlap, text contrast from screenshots). Covers Expo/React Native on the emulator and a device; iOS only on macOS hosts. The explorer and lenses get mobile evidence bundles; the dashboard lanes already handle any surface kind.

**M4: API and CLI.** An HTTP driver with reachability-only proving (A8 already proves api surfaces that way), OpenAPI-derived goals, and request/response action logs for replay; a shell driver for CLIs with exit-code, stderr and output-shape checks. Unhappy paths reuse the fault-injection idea at the HTTP layer. Lanes show the last request or terminal output, text first (already specified for E4).

**M5: `watch` and the planted-bug benchmark.** `flow-review watch` maps changed files to affected flows via source maps/coverage and re-replays only those, never prompting. A planted-bug benchmark suite (grown from the B0 fixture into per-surface apps) measures recall and cost per real finding per model profile (lean/default/max) on every release. Its data recalibrates the budget priors (A-7, A-19) and revisits the path-ratio and hidden-feature thresholds (A-8, A-9).

## Appendix A: Decisions log

Answered by the user on 2026-09-23 in the planning session. Never re-ask these.

| # | Topic | Decision |
|---|---|---|
| A-1 | Web recording format | Own JSON action log, one file per flow: steps of {action, semantic locator (role+name → testid → css), value, url, checkpoint}. A Playwright trace.zip is kept only as failure evidence. **Recording is OFF by default**; the user must ask for it explicitly. |
| A-2 | Recording opt-in | Per run (`/flow-review record …` or a yes at the GO gate) plus sticky per surface (`record: true`). Without either, nothing is written to `.flow-review/recordings/`. |
| A-3 | Validation replay when recording is off | Ephemeral repro log: the explorer's action log for a finding stays in the run folder only long enough to replay once. Never reused on later runs; never feeds `flow-review replay`. |
| A-4 | Config schema | JSON, `schema_version: 2`. Common surface fields + a per-kind typed `options` block. Unknown key → a friendly error naming the valid keys and the closest match. Holds state policy, reset, creds env names, record, model profile + per-role overrides, budget cap. |
| A-5 | v1 migration | Auto-migrate on load: name/kind/driver/launch/preconditions/provenance carry over; `destructive: true` → `state: persistent`; `lens_sets`/`evidence_types`/`tester_agent` dropped. Write `config.v1.bak`, save v2, print a one-screen summary. Unattended runs migrate silently. |
| A-6 | Fingerprint | sha1 of (flow_id, lens or engine rule id, route template, semantic locator role+name → data-testid → css). When an exact match misses but an open finding exists on the same flow+lens+route, Haiku triage decides same/new and the ledger records an alias. |
| A-7 | Budget | Unit is tokens. Estimate = planned units × per-role token priors shipped in the engine; once the ledger has ≥3 runs for a surface, per-unit medians of actuals replace the priors. Actuals come from each subagent result's reported usage, logged by the orchestrator. The cap is checked before every LLM dispatch; replays and measurements continue past it. |
| A-8 | Hidden-feature severity (council) | First miss → goal-card metric only ("from docs"). A P2 discoverability finding once the ledger shows the same function missed in 2 cold runs. Never P1, never Opus-verified. |
| A-9 | Intuitiveness severity (council) | Actions vs shortest path is a goal-card metric only in M1 (baseline = best observed across runs). Revisit at M5 with benchmark data. |
| A-10 | Packaging | PyPI package `flow-review` with extras per surface (`[web]` = playwright, pillow). Setup creates `.flow-review/.venv` with uv (pip fallback) from the plugin's bundled engine source. CI: `uvx --from 'flow-review[web]' flow-review replay`. The PyPI publish is an M1 release step gated on the user's go. |
| A-11 | Live push | SSE on stdlib `ThreadingHTTPServer`. Triage via a small JSON POST endpoint. |
| A-12 | Run modes | `goal` (goal + everything around it), `auto` (no goal: cold eyes, then docs), `full` (everything, deep), and `quick <goal>` (happy path only; no around-variants, no judgment lenses; engine checks, objective failures and the P0/P1 verifier still run). v1 fast/deep is removed. |
| A-14 | Detection scope | M1 detects everything in §6 (monorepo workspaces, Poetry, web frameworks, `src-tauri/`, Expo `app.json`, electron in deps). Non-web hits are recorded as `pending-driver` surfaces: shown at setup and in drift, never tested until M2/M3. |
| A-15 | Suppressed finding reappears | Triaged states (false-positive, wont-fix, accepted) and `refuted` are sticky; `runs_seen` keeps counting; the finding stays in the collapsed sections. The user reopens it manually (drawer or `flow-review triage ID open`). |
| A-16 | `token.color` | A computed color is on-token only on an exact match after normalization. Within ΔE2000 < 3 of a token but not equal → P2 naming the intended token. Farther away → P2 "off-palette". |
| A-17 | `console.error` | P1 when fired inside a user action's step window (action → settle); P2 on load or in the background. |
| A-18 | Keyboard reachability | Tab cap = 2× the focusable elements on the page (min 20). Stop early when focus cycles back to the start; a control never focused is unreachable. |
| A-19 | Plan unit counts | Per-mode unit templates shipped as priors, replaced by the surface's median actual counts once `usage_history.json` has ≥3 runs. No preview pass; `plan` stays pure data. |
| A-20 | Destructive gap | One multi-select question at the GO gate listing every `persistent` surface, asked together in every mode (quick included). Default no. Without an opt-in, the explorer skips destructive actions and files them `not-exercised`. Confirmed by the user. |
| A-21 | Static fallback | One file: CSS, JS, icon sprite and subsetted fonts inlined, plus small inline screenshot thumbnails (downscaled JPEG data URIs) linking to the full-res shots in the run folder. Confirmed by the user. |
| A-22 | Page tech | Vanilla ES modules + CSS, no build step. Revisit only if app.js passes ~1k lines. |
| A-23 | Internal calls (orchestrator) | Profiles live in `config.PROFILES` (Python is authoritative); the dashboard budget is `budget.used(run_dir)`; usage history is budget-owned; the project root is passed explicitly; the palette validator is a one-time manual check in E3; keyboard-unreachable controls are a P1 engine finding `a11y.keyboard-unreachable` (WCAG 2.1.1 Level A); one budget unit = one subagent dispatch, with priors seeded from this session's measured subagent usage (~47k tokens for a single-turn, no-tool dispatch; explorer 150k, cold-eyes 120k, lens/triage 50k, verifier/replay-repair 60k); font download + subset is an E3 step; workspace globs use `Path.glob` (so `**` works, brace lists don't); non-web drivers take no options in M1; replay exit 1 counts only regressions that reproduced in that replay; locators for untagged elements fall back to `css:nth-of-type` (a known fingerprint-stability ceiling, revisit at M5); triage `reason` is optional except for `refuted`. |
| A-24 | Agent↔browser | The engine `drive` CLI (see Canonical Interfaces › Drive). Agents never touch Playwright or MCP browser tools directly; the engine records, redacts and measures every action. |
| A-25 | Token sources | `options.tokens_file` may be `.css`/`.scss` (color custom properties) or `.json` (a flat map or W3C design tokens `$value`), read by `measure.load_tokens`. No tokens_file → the token check is skipped, never guessed. |
| A-13 | Audit recon correction | The Haiku recon marked C2/C3/C5/H3/H8/M7-M9 as not true; the orchestrator spot-check shows all are still true (`lenses/ui.md:48,214`; `prove.py:193`; `evidence.md:37` interpolates into a double-quoted shell string; `template.html:77`; `render.py:179`; stdout reconfigure in every module, locked by `test_references.py:45-56`). |

Orchestrator conventions (not user decisions; flag at review if wrong): engine package at `plugins/flow-review/engine/flow_review`; agents at `plugins/flow-review/agents/`; `requires-python >=3.10`; tests colocated.
