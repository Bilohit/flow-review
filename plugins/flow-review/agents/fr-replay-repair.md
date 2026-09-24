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
