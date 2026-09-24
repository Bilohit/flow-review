# flow-review v2 design

Date: 2026-09-23. Status: design approved in interview, not implemented. Source: an audit plus an interview
session (no code changed). Next step: an implementation plan for M1.

## 1. Goal

Turn flow-review from a harness built for one app into a general-public tool. It autonomously tests any app under
development (web, Tauri desktop, Expo/React Native mobile, HTTP APIs, CLIs) for correctness, UX, accessibility,
intuitiveness and visual quality, so a solo developer never re-clicks the whole app by hand before a release.

flow-review is **only an investigation and reporting system**. It never edits product code.

## 2. Audit of v1 (what the rebuild must fix or drop)

Critical:

1. The config schema cannot hold what the docs require. `Surface(**entry)` rejects unknown keys
   (`fr/config.py:85`), yet the docs need base URL, health path, timeouts, cwd/env, package/bundle ids, token
   source, state docs, route registry, locks, watchdog and bounded waits.
2. The consensus rule never fires. Lenses are told to stay inside disjoint rubrics (`lenses/ui.md:51`) but
   opinion findings need 2+ lenses agreeing (`lenses/ui.md:214`). Even measured contrast failures end up as
   "minority opinions".
3. Lens dispatch is undefined. SKILL.md has one tester per surface reading the lens file, while the lens file
   says "you are one lens... do not run the flows" (`lenses/ui.md:3-9`).
4. Repeat demotion can't work. It uses an exact prose fingerprint (`fr/findings.py:24-31`), no previous findings
   are persisted, `runs_seen` can never pass 2, lens opinions use `severity/claim` while events use `sev/text`,
   and the docs disagree about punctuation.
5. Manifest write-back appends bare bullets every run and grows forever (`fr/manifest.py:116`). No row edits
   exist despite the docs promising them, and a test locks the no-header behaviour in.

High: declined surfaces still get tested; renaming a surface breaks drift (name-keyed, `fr/drift.py:42`);
`_teardown` returns early and orphans grandchildren (`fr/prove.py:193`); a clean exit counts as proven even when
readiness preconditions were given (`fr/prove.py:283`); setup contradicts itself on unproven surfaces; nothing
launches the dashboard; `withdraw` matches by 1-second timestamps (`dashboard/render.py:115`); the
`printf "$TEXT"` append idiom is shell-injectable (`references/evidence.md:37`); fast/deep mode can't be
selected; `lens_sets`, `evidence_types` and `destructive` are dead config; preconditions are unvalidated.

Medium/low: unfriendly config load errors; the audit scans the repo root only and misses Tauri, Expo, Electron,
monorepos and Poetry; an OpenAPI surface can never be proven; the report has no place for minority, flaky,
unknown or harness findings; harness traps get appended into the plugin's own install directory; stale
references; a hardcoded 3-column dashboard grid with leftover CSS; `_fill` expands placeholders found in user
text; an import-time stdout side effect in every module.

## 3. Architecture

- **Deterministic Python engine**: launch/prove, replay recorded flows, measure (contrast, computed styles vs
  tokens, rects, status codes, exit codes), visual diff, fingerprint/dedup, the ledger and the dashboard.
- **Claude Code plugin** as the front end. All LLM work (exploration, judgment critique, verification, triage)
  runs as Claude Code subagents.
- **The engine never calls an LLM API.** No API key, no headless LLM path.
- **Dependencies**: a managed venv (uv/pip) created at setup, installing only what the detected surfaces need
  (Playwright, Pillow, Maestro, and so on). The v1 "stdlib only" promise is dropped.
- **Entry points**:
  - `/flow-review` in Claude Code, for full runs with LLM work.
  - `flow-review replay`, a standalone CLI with no LLM, for CI and git hooks. It exits non-zero on regressions
    and flags divergences for the next Claude Code session.
  - `flow-review watch`, which re-replays the affected flows on file change, mapping files to flows via
    source maps/coverage.
  - `flow-review serve`, which serves the dashboard.

## 4. Model routing (token efficiency is a priority)

Subagents pin their model per role; `inherit` is never used. The config can override, with `lean`, `default`
and `max` profiles.

| Role | Model |
|---|---|
| Engine work | none |
| Orchestrator | user's model, kept light |
| Explorer (goal-driven, new flows) | Sonnet, medium effort |
| Replay repair on divergence | Haiku, escalate to Sonnet |
| Judgment lenses (first-time-user, hierarchy, craft, copy, discoverability, help usability) | Sonnet, one call per screen, evidence bundle first for caching |
| Cold-eyes vision explorer | Sonnet |
| Triage (stuck classification, fuzzy dedup, reconciliation) | Haiku |
| Verifier (P0/P1 judgment only) | Opus |

Token levers, in order:
1. Deterministic work stays in the engine.
2. Text before images; crop and downscale screenshots, and only send regions that changed.
3. Replay beats re-exploring.
4. Pick the model tier per role.

## 5. Flows and goals

- **Goal given**: test the goal and everything **around** it, all on by default:
  - unhappy paths (bad input, server error or offline partway through, double submit);
  - interruptions (back, refresh, reopen, rotate, backgrounding);
  - alternate routes and adjacent features;
  - device/persona variants (widths, light/dark, keyboard-only, screen reader, new vs returning user).
  Variants are engine replays where possible.
- **No goal**: generate goals from what the app does, as a new user would want to use it:
  - Pass 1: a cold-eyes, UI-only explorer (it has not read code or docs) writes what it thinks the app is for.
  - Pass 2: the README, docs, routes and OpenAPI add what pass 1 missed. A function only the docs revealed is a
    discoverability finding.
- **`full`**: everything, deep.
- **Recording**: a successful explored path is recorded and replayed for free on later runs. The LLM returns
  only on divergence.
- The flows manifest remains human-owned: goals are listed there, and the tool never overwrites human edits.

## 6. Drivers (per surface, in milestone order)

- **Web**: Playwright.
- **Tauri**: web-first, meaning explore and measure in Chromium via the dev server with `invoke` mocked
  (`@tauri-apps/api/mocks`), then confirm every finding on the native app:
  - Windows: WebView2 over CDP;
  - Linux: tauri-driver;
  - macOS: accessibility API plus screenshots, without computed-style checks.
- **Mobile**: Maestro. Its YAML is the recording format; `maestro hierarchy` gives the view tree. iOS needs macOS.
- **API**: HTTP with reachability-only proving. **CLI**: shell.
- **Detection** extends to Tauri, Expo, Electron, monorepo workspaces and Poetry.

## 7. Finding validation (adopted from a Sonnet council)

1. **Anything measurable is an engine check** (contrast, tokens, rects, status/exit codes) and is filed
   directly, with no vote.
2. **Lenses may note observations outside their own rubric**, as context, not as votes.
3. **Judgment P0/P1 findings**:
   - First, replay on the real surface (free).
   - Then a verifier that may refute **only** with measured or replayed evidence, never with taste. If it
     cannot refute that way, the finding stands.
4. **Judgment P2 findings** are filed as "opinion".
5. **Objective failures** (crash, hang, data loss, wrong content, failed round trip) are filed on one
   reproduction.
6. **Refuted findings stay visible** in the ledger with the reason. A planted-bug benchmark app measures recall
   on every release of the tool.

## 8. Findings ledger and triage

- `.flow-review/findings.json` gives each finding a stable id and a state: open, fixed, regressed, refuted,
  false-positive, won't-fix or accepted.
- The fingerprint uses flow id, lens and element selector, not prose.
- **Triage** happens in the dashboard drawer (icon buttons plus keyboard shortcuts) or from the CLI.
- **False-positive marks feed back into the lens prompts** as suppressions.
- **Each finding carries a fix brief**: repro steps, evidence, and a suspected `file:line` via source maps. It is
  report content only.

## 9. State, auth and safety

- Config holds a per-surface policy:
  - `state: disposable | persistent`;
  - an optional `reset` command;
  - credentials as env-var **names**, with values in a gitignored `.flow-review/.env`.
- Unattended runs (replay, watch, CI) never ask anything.
- The GO gate asks only about gaps: missing credentials (with an offer to save them), and destructive actions on
  a persistent surface (a per-run opt-in, default no, never remembered).
- Email verification goes through a configured test inbox (Mailpit, Ethereal); otherwise it is marked "not
  exercised".
- Payments are sandbox-only. Secrets are never written to events, the ledger or reports. Password fields are
  masked in screenshots.

## 10. Cost control

The GO gate shows the planned work and an estimated token cost per surface. The user can trim before confirming.
A hard cap in config stops new LLM work once it's reached; replays and measurements continue, and the report
lists what was skipped.

## 11. Dashboard

**Structure:**
- One **run page** served by `serve`, updated by **live push** (no reload; scroll position and the open drawer
  stay put), with a static-file fallback.
- **Lanes** in an auto-grid that adapts to 1..N surfaces of any kind. API/CLI lanes show the last request or
  terminal output instead of a screenshot.
- **While running, visible at a glance** (utterly minimal):
  - lanes (the live shot or output plus the current step; history on hover or click);
  - progress and elapsed time;
  - the budget meter;
  - **one findings badge**: the total count, tinted by the worst severity so far. Hover shows the P0/P1/P2
    split; click opens the list; a new P0 gets one eased highlight.
- **After the run**, the hybrid report:
  1. a needs-attention list (new and regressed, by severity);
  2. goal cards (reached/blocked, actions vs shortest path, found cold vs from docs);
  3. collapsed opinions, repeats, refuted and not-exercised sections.

  The severity-count trend sparkline and surface status dots live in the header, but not at a glance while a
  run is going.
- **A finding opens in a side drawer.** Evidence is chosen per type: before/after for regressions, an annotated
  screenshot for visual findings, text first for API/CLI.

**Design rules (strict):**
- Simple, clutter-free, progressive disclosure.
- **No subheadings and no descriptions anywhere.** Icons and titles must be self-explanatory; hover/focus
  tooltips are allowed and double as accessible names.
- Smooth, well-eased motion throughout, honouring reduced-motion.
- Light and dark follow the OS, with a toggle.

**Direction (quick check, D1 "Instrument")**: Schibsted Grotesk for UI, IBM Plex Mono for numbers and logs only,
cool neutrals, hairline borders, 4px radius, a single blue accent, Phosphor icons. Reference mock:
`direction-v3.html` in the session's brainstorm scratchpad. It is not in the repo and is not signed off.

**Required at M1**: a full design pass invoking impeccable (including `init` for PRODUCT.md), taste-skill,
uiux-pro-max, hallmark and animotion.

## 12. Milestones

- **M1: web end to end, plus foundations.** Fix the critical audit items, a new config schema (per-surface
  options, state policy, model profiles), a JSON-safe event writer with ms timestamps and finding ids, the
  ledger, and the full loop on Playwright: goals, cold eyes, recording, replay, measurement, validation, report,
  triage, dashboard, and the GO-gate estimate and cap.
- **M2: Tauri** (web-first, then native confirm).
- **M3: Mobile** (Maestro).
- **M4: API and CLI.**
- **M5: `watch` mode, and the planted-bug benchmark suite** (recall plus cost per real finding, per model
  profile).

## 13. Dropped

The v1 consensus vote; stdlib-only; an LLM API path in the engine; session video; a chaos/performance suite
(only the network fault injection that unhappy paths need is kept); cross-surface consistency checks; a
past-runs switcher.

## 14. Open items for the M1 plan

- The recording format for web (a Playwright trace vs our own action log).
- The exact config schema and its migration from v1 `config.json`.
- The fingerprint's details for stable finding ids across UI changes.
- How the budget estimate is computed (per-step token priors, refined from the ledger's history).
- Where "hidden feature" and intuitiveness metrics sit in the severity ladder.
