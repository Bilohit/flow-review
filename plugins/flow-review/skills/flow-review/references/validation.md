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
   log (or the flow it came from) is replayed only within this run (variants, then the
   verifier) into `<run_dir>/repro/` -- ephemeral: never persisted or reused on later runs,
   never feeds `flow-review replay` (A-3). The verifier then returns exactly one of two verdicts:
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
`lenses/ui.md` section 4 -- never by this pipeline. This pipeline only decides whether a
filed finding survives, and how.
