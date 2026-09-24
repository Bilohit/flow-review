# Ponytail audit: whole repo, 2026-09-24

Branch `m1-v2` at `e9a61f9`. Baseline: `python -m pytest -q -m "web or not web"` → 526 passed.
Scope: engine, web driver, dashboard, skill, agents, docs, tests. The M1 plan doc was excluded.
Only over-engineering was in scope. Bugs are listed separately at the end.
Every "zero callers" claim was checked with a repo-wide grep that covered `.py`, `.md` and `.js`. The skill and the agents call some engine functions straight from prose (for example `fr.prove.prove`), so the markdown files were searched too.

## Ranked findings

| # | Tag | What to cut | Replacement | Where | Size |
|---|---|---|---|---|---|
| 1 | delete | The legacy string-template renderer: `render.py`, `template.html` and their test. It has no production importer. It was superseded by `state.fold` + `static.py` + `page/`. | nothing | `engine/flow_review/dashboard/render.py`, `template.html`, `test_render.py` | ~-850 |
| 2 | delete **or wire** | B5, B6 and B7 were built but never wired in. `web/visual.py` (baseline diff), `web/variants.py` (viewport/theme/keyboard variants) and `web/faults.py` (offline/5xx/slow) each have zero importers outside their own tests. No CLI verb reaches them. `references/goals.md:19` tells agents that "the engine runs" variants, but no agent can do so. | Needs a user decision: delete them and fix the docs, or add `drive` verbs | `engine/flow_review/web/{visual,variants,faults}.py` + tests | ~-480 if deleted |
| 3 | yagni | The `api.md` and `cli.md` lens rubrics ship in M1. M1 tests web only: A-14 makes non-web surfaces `pending-driver`, never tested. They are referenced by SKILL.md:96, fr-lens.md:14 and fr-triage.md:38, and they are ~90% duplicates of `ui.md` sections 1, 3 and 4. | Keep `ui.md` only and restore the other two at M4 from git | `skills/flow-review/references/lenses/{api,cli}.md` | ~-385 |
| 4 | delete | `lenses.py`: a Python re-encoding of the lens markdown. No code or doc calls it. README.md:125 and concepts.md:29 still point readers to it. | the `references/lenses/*.md` files, which are the real source | `engine/flow_review/lenses.py` + `test_lenses.py` | ~-130 |
| 5 | shrink | Driver notes for drivers that M1 cannot run: `adb` and `shell/http` in `testing.md` (loaded on every explorer dispatch), and `adb/ios-sim/shell/http/custom` in `surfaces.md`. | Drop them and add them back at M3/M4 | `references/testing.md:90-110`, `references/surfaces.md:44-116` | ~-90 (fewer tokens per dispatch) |
| 6 | delete | Dead parts of `validate.py`: `route()`, `resolve_after_replay()`, the `Disposition` enum and `Verdict.FILED/OPINION`. Only `resolve_after_verifier` is wired (`flow-review validate resolve`). concepts.md:82 describes the dead state machine. | nothing | `engine/flow_review/validate.py:29-67` | ~-35 |
| 7 | delete | `measure.check_contrast`, the per-element round-trip prototype. The only caller is its own test. The live path is `check_page`'s batched scan. | `check_page` | `engine/flow_review/web/measure.py:163-181` | ~-25 |
| 8 | shrink | The verifier's "refuted needs a real evidence ref" rule is stated three times, and fr-verifier loads two of the copies. | Keep it in `validation.md` and point to it from the others | `SKILL.md:100-107`, `agents/fr-verifier.md:19-29` | ~-25 |
| 9 | delete | `triage.build_fix_brief` + `FixBrief`. Nothing calls them. The fix brief is written by the triage agent from prose. | nothing | `engine/flow_review/triage.py:46-62` | ~-20 |
| 10 | delete | The `prove` CLI stub. It prints "not implemented", but `--help` still lists it. setup.md calls `fr.prove.prove` directly. | remove the stub | `engine/flow_review/cli.py:20-22,147-149` | ~-8 |
| 11 | delete | `audit.default_port`, `WORKSPACE_FRAMEWORK_PORTS` and `_default_port()`. They are computed but never read. | nothing | `engine/flow_review/audit.py:27-80` | ~-10 |
| 12 | shrink | `_slug` exists as three copies: `drift.py`, `migrate.py` and `web/actionlog.py`. | one helper in `config.py` | as listed | ~-6 |
| 13 | shrink | `app.js`'s `toggleFindingsList` rebuilds the `_findingRow` markup. | `_findingRow(f, onClick)` | `dashboard/page/app.js:75-87,365-383` | ~-8 |
| 14 | yagni | `plan --json` is parsed but never read ("M1 always prints JSON"). | drop the flag and its doc mentions | `engine/flow_review/cli.py:197` | ~-1 |
| 15 | yagni | `SetupResult.commands_run` and `.used_uv` are returned, but the CLI never reads them. | drop them, or print them | `engine/flow_review/envsetup.py:24-29` | ~-4 |
| 16 | shrink | Prose-wording tests (`assert phrase in text`) in `test_skill.py`, part of `test_references.py` and `test_readme.py`. They lock the wording, not behaviour. | Keep the structural tests. Consolidate the rest. | as listed | ~-100 to -150 |
| 17 | shrink | The "only interface is `flow-review drive`" paragraph appears in both `fr-explorer.md` and `fr-cold-eyes.md`. | leave it: each agent loads only its own file | as listed | 0 |

Checked and lean, with no finding: `prove.py` (every piece cites an observed defect), `config.py`, `ledger.py`, `budget.py`, `manifest.py`, `events.py`, `plan.py`, `drift.py`, `migrate.py` (A-5 requires it), `driver.py`, `replay.py`, `actionlog.py`, `drive.py` (all 9 subcommands are used), and `serve.py` + the drive server (two different jobs, A-11). The hand-rolled `.env` parser is deliberate, since the engine has no dependencies. `PRODUCT.md`'s location is fixed by Task E3. Every other CLI verb has a doc or agent caller.

net: about -1,700 lines if #2 is deleted, about -1,200 if #2 is wired. -0 deps (the engine core has none, and `[web]` = playwright + pillow are both used).

## Bugs noticed along the way (out of scope for ponytail; send to a normal fix)

- CONTRIBUTING.md says the dashboard lives at `skills/flow-review/dashboard/`. It actually lives at `engine/flow_review/dashboard/`.
- README.md:125 and docs/concepts.md:29 and :82 point readers to the dead `lenses.py` and the dead `validate` routing.
- `references/goals.md:19` promises engine-run variants that no agent can trigger (see #2).
