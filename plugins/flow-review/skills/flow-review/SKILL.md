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
observation (A-8; `references/goals.md`), recorded with `flow-review ledger record-miss
--function NAME --run DIR` (prints the miss count; at 2 it becomes a `P2` discoverability finding).

`/flow-review full` -- **full mode**: everything, deep -- every lens, every variant, no trimming.

`/flow-review quick <goal>` -- **quick mode**: the happy path only. No around-variants, no
judgment lenses dispatched. Engine checks, objective failures, and the P0/P1 verifier path still
run in full.

Recording is **off by default** (A-1); it turns on only per run (`record` in the invocation, or a
yes at the GO gate) or sticky per surface (`record: true`). Without either, nothing is written to
`.flow-review/recordings/`.

## 3. Run mode procedure

1. **Plan.** Run `flow-review plan --mode <mode> [--goal "<goal>"] [--record]` (M1 always prints
   JSON). It returns
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
   questions reach the user for the rest of the run: no question, no interview after the GO. Recovery decisions (`references/stuck.md`)
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
   `flow-review event --run DIR --type usage --json '{"surface": "ID", "role": "ROLE", "tokens": N}'`
   (pass `tokens` through `--json` so it stays an integer; `k=v` fields arrive as strings), which
   is exactly the event `budget.record_usage` writes -- the event log is the one source of truth for usage, there is no
   separate usage store the orchestrator writes to directly.
   - **Exploration.** `fr-explorer` per surface toward the goal (goal/full mode), or `fr-cold-eyes`
     pass 1 then `fr-explorer` pass 2 for docs (auto mode) -- `references/goals.md`. Every
     explorer works from `references/testing.md` (how to drive and measure),
     `references/evidence.md` (what counts as proof) and `references/stuck.md` (recovery).
   - **Replay repair.** Where a recorded action log exists and `flow-review replay` reports a
     divergence, `fr-replay-repair` runs once at Haiku, escalating to Sonnet only on a real
     escalation report.
   - **Judgment.** For every screen a `ui`/`api`/`cli` surface produced evidence for (skipped
     entirely in `quick` mode), `fr-lens` runs once per screen against every lens that surface
     kind defines -- never once per lens. `references/lenses/ui.md` is the rubric (API and CLI
     lenses return with M4); suppressions from `flow-review ledger suppressions --rule RULE`
     (JSON) are injected first.
   - **Validation.** Every judgment finding routes through `references/validation.md` (C5): an
     engine check or objective failure is filed on one reproduction; a `P2` judgment finding is
     filed directly as an opinion; a `P0`/`P1` judgment finding gets an ephemeral replay, then
     `fr-verifier` at Opus, resolved via `flow-review validate resolve --run DIR --verdict
     stands|refuted --reason R --kind measurement|replay --ref PATH`. Refute only with a real
     evidence ref -- the rule and its enforcement are in `references/validation.md`. A successful
     refutation stays in the ledger with the reason and the evidence ref, never deleted.
   - **Triage.** `fr-triage` at Haiku classifies stuck episodes, resolves fuzzy-dedup ties
     (`flow-review ledger alias-candidates --flow F --rule R --route P` lists candidates; a chosen
     alias is passed as `--alias FINGERPRINT=ID` to reconcile, A-6). After the run's findings are
     in, reconcile the ledger with `flow-review ledger reconcile --run DIR` (folds the run's
     `finding` events, minus `withdraw`n ones, into `.flow-review/findings.json`).
6. **Manifest write-back.** What was learned this run is written back by calling
   `flow-review manifest apply-learnings --path FILE --hash RECORDED_HASH --learning TEXT` (one
   `--learning` per line; prints the new hash to store as `flows_hash`) -- never a hand-rolled
   rewrite of `flows.md`, and never touching a human-edited file (see `references/setup.md`
   section 8 for the append-only mechanism this reuses). A run that learned nothing calls it with
   no `--learning`; the printed hash only moves when there was something to record.
7. **Report.** After `flow-review ledger reconcile --run DIR`, run
   `flow-review budget fold --run DIR` to fold this run's usage into `usage_history.json`. Then the report: section 4 below. Stop every drive session (step 4) once the report is assembled.

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
   repeats (ledger entries whose state after `flow-review ledger reconcile` is still `open` and were already
   seen on an earlier run -- folded to a count via `runs_seen`; a `regressed` entry is never a
   repeat, it goes to the needs-attention list), refuted findings (with the
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
