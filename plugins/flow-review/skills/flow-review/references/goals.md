# goals.md -- what to test, and how a goal is found

This is `fr-explorer`'s and `fr-cold-eyes`'s procedure for deciding what "the flow and everything
around it" means, and for generating a goal when none was given. `testing.md` covers how to drive
a surface once you know what to drive; this file covers what to drive.

## 1. A goal was given (goal mode, full mode)

Test the stated goal, and everything around it -- **all of the following are on by default**,
except in quick mode, which tests only the stated goal's happy path and none of what follows:

- **Unhappy paths.** Bad input, a server error or the network going offline partway through, a
  double submit -- inject with `flow-review drive fault --kind offline|5xx|slow --pattern GLOB
  --delay-ms N`, then `flow-review drive fault --clear` to restore normal behaviour.
- **Interruptions.** Back, refresh, reopen, rotate (mobile), backgrounding and returning.
- **Alternate routes and adjacent features.** Other ways to reach the same outcome, and features
  the goal sits next to that a real user would notice along the way.
- **Device/persona variants.** Widths, light/dark, keyboard-only, screen reader, new vs returning
  user (via stored session state). Where a variant is a pure replay of an already-recorded flow
  under different conditions, it is run by the engine (`flow-review replay --variants --mode MODE`,
  B7/R6) rather than re-explored -- check whether an action log already exists for the base flow
  first.

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
with `flow-review ledger record-miss --function NAME --run DIR` (backed by `ledger.record_miss`;
it prints the miss count). It becomes a `P2` discoverability finding only
once that count reaches 2 (`ledger.missed_twice`) for that function (i.e. it has now been
missed by cold-eyes on 2 separate runs). It is never `P1`, and it is never sent to `fr-verifier` --
`missed_twice` is the only gate on this, not lens discretion.

## 4. Path-ratio (intuitiveness) metric (A-9)

For each goal reached, record the number of actions actually taken against the shortest known
route to the same outcome (the shortest route observed across any run so far). This is a
**goal-card metric only**, never a severity-bearing finding on its own in M1; revisited at M5 with
benchmark data.

Report each goal's outcome once, through the CLI's `event` subcommand, as a `goal` event with
exactly these fields (the dashboard goal card reads them):
`--type goal --json '{"flow_id": "<flow id>", "text": "<goal text>", "reached": true|false, "actions": N, "shortest": M, "from_docs": true|false}'`.
`flow_id` is required: the dashboard keys goal cards by it and drops a goal event without one.
`from_docs` is true only when the goal was reached on the docs pass after a cold miss (section 3).

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
via the CLI's `event --run DIR --type finding ...` subcommand, never by writing to `events.jsonl`
directly.

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
