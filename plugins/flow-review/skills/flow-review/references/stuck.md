# stuck.md -- the stuck protocol

**Stuck is evidence, not just an obstacle.** A tester that cannot get through a flow -- with the
product, the manual, and infinite patience -- is telling you something about a real user who has
none of those. Classify every episode; never merely survive it.

**The user is never asked.** Not in deep mode, not in fast mode. Fast mode's narrow interrupt
right covers credentials and destructive authority only, never recovery. Human input is for plans
and decisions, not for unsticking a run.

## Your half: R0 and R1

A tester may self-serve exactly these two rungs, and only these two:

| Rung | Action |
|---|---|
| **R0** | Re-inspect the view/DOM, re-screenshot, verify the element was actually where the action was aimed. Half of all "stuck" is an action that never landed -- confirm perception before blaming the surface. |
| **R1** | Change **exactly one** input variable: a different point inside the element, a key event instead of a tap, scroll into view first, wait for idle, a slower cadence. One variable at a time keeps the result diagnostic. |

Each rung runs **once per flow**. Repeating an action verbatim *is* the definition of stuck.

**Above R1 you stop and report.** You never invent a rung. **You never ask the user** -- not for
recovery, not for clarification, not at all.

### Stuck report -- send this to the main thread, exactly these fields

```
STUCK
flow:        <flow id>
step:        <step label>
rung:        R0 | R1  (highest reached)
sig_before:  <state signature before the action>
sig_after:   <state signature after the action>
shots:       <last three shot paths, relative to the run folder>
error:       <verbatim error text, no paraphrase>
read:        product | harness | unknown  -- plus one sentence of why
```

Then append a `status` event for your surface and wait. The main thread decides everything from
R2 up. While waiting, do not retry, do not improvise, and do not start the next flow until told.

## The main thread's half: R2-R5

| Rung | Action |
|---|---|
| **R2** | Backtrack to the flow's entry point, replay with the R1 variable. Clears modal/navigation state without disturbing app state. |
| **R3** | Restart the surface -- stop and relaunch its process (a UI surface: close/force-stop and relaunch; a CLI or API surface: kill and re-run). Clears process state, keeps app data. |
| **R4** | Reset the environment for that surface, per what it allows: a disposable or emulated surface can be wiped freely; a surface holding real state gets its cache cleared first and a full reset only if that fails, then re-paired or re-authenticated as part of recovery. Any surface: reset the transport (a device bridge, a websocket, an HTTP client) if it is itself the suspect. |
| **R5** | **Quarantine.** Stop the flow, mark `BLOCKED`, attach the stuck report, the last three screenshots, and both state signatures. Move to the next flow on that surface. |

- **No rung repeats within a flow.** The ladder resets per flow, not per attempt.
- **Every rung from R2 up emits a `status` event** with `state: recovering` and the rung named, so
  a watching user always knows why a surface went quiet.
- **Whole-episode budget: 6 recovery actions or 5 minutes wall clock**, whichever comes first, then
  jump straight to R5 regardless of remaining rungs.
- **A stuck surface never blocks another surface.**
- **Two crashes on the same flow skip the ladder entirely** -- capture the crash log
  **immediately**, that is the evidence, file P0, quarantine. Laddering a crash loop only buys
  more crashes.

**End-of-run retry.** Every quarantined flow gets **one** more attempt from a freshly restarted,
clean surface after all surfaces finish -- always in deep mode, in fast mode only if the run is
still inside its time target.

- Passes on retry -> logged as **order-dependent / flaky**, itself a finding (P1 by default): a
  flow that only works from a clean start is a flow a real user will hit broken.
- Fails again -> `BLOCKED` stands, with both attempts' evidence.

## Classification

At quarantine, the main thread classifies. This is a runtime fact, not a council matter.

- **PRODUCT-stuck** -- the product caused it: dead end with no exit, no back affordance, silent
  failure, a disabled control with no explanation, an infinite spinner, an unreachable next step.
  -> **`P0` if blocking, `P1` otherwise. Never lower, never council-voted.** *Blocking* means the
  flow's stated expected outcome was not reachable by any route tried through R4; reachable only
  by backtracking or restarting is `P1`.
- **HARNESS-stuck** -- tooling or environment: a transport dropped, a wedged emulator or
  simulator, a stale or missing build, a driver never proved attached, a dev server dead, a path
  or permission quirk. Not a product finding -- record it as an infra note, and **if the trap is
  novel, append it to `testing.md`** so the next run does not rediscover it.
- **UNKNOWN** -- evidence supports both readings. Log it both ways, tag it **NEEDS USER INPUT**.
  Do not resolve it.

## Watchdog

If a surface appends no event for the configured watchdog window, ping that tester. No useful
response -> treat as HARNESS-stuck: restart the tester **once**, handing it the surface's
remaining flow list and last known state. A second silence halts that surface.

## Bounded waits are not stuck

Every awaited async result carries an explicit bound, read from config wherever the project
defines one -- a round trip, a background job, a fixed per-operation ceiling. Exceeding the bound
is a **finding** ("the operation never completed"), logged with evidence, and the run continues.
A product that batches or defers by design is not hung; do not misread batching as a hang.

## Circuit breakers

- **Per surface:** 3 consecutive quarantines halts that surface. Remaining flows are marked
  `NOT-RUN (surface halted)` with the reason. Three in a row is systemic -- a bad build, a wedged
  device -- and pushing on only manufactures noise. Other surfaces continue untouched.
- **Global:** all active surfaces halted -> end the run early, write the report from what exists,
  run the hygiene pass, and state plainly that the run was cut short and why.
