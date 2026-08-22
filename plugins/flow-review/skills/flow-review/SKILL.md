---
name: flow-review
description: Use when the user asks for an end-to-end flow review, a UX review, a new-user review, a QA pass, or a full flow review of a product across its real surfaces -- an autonomous run that drives the product like a first-time user, gathers real evidence, and returns ranked findings plus a design critique. Also triggers on the literal invocation /flow-review.
---

# flow-review

`flow-review` drives a product end to end the way a first-time user would, gathers evidence from
the real surface rather than an impression of it, and returns ranked findings plus a design
critique. It never fixes anything and never edits product code -- it only logs what it found.

## 1. Which phase am I in

Read `.flow-review/config.json` in the project root before doing anything else.

- **Absent, or `--reconfigure` was passed** -> **setup mode**. State this in one line, then hand
  off to `references/setup.md` and follow it start to finish. Nothing below this section applies
  until setup has written a config.
- **Present, and `--reconfigure` was not passed** -> **run mode**. State this in one line, then
  continue with section 3 below.

Never guess which mode applies from context or from what the user said last session -- read the
file, every time.

## 2. Setup mode

Setup mode is the whole of `references/setup.md`: audit or preset, confirm every candidate, prove
each accepted surface, stamp provenance, pick lens sets, choose the tester agent, seed the flows
manifest, and write `config.json`. Do not duplicate that procedure here -- load the reference and
run it.

## 3. Run mode

1. **Scope resolution.** Reconcile `.flow-review/flows.md` against the project's own state docs
   (named in config): a built feature missing from the manifest becomes a `NEW` stub; a dead or
   superseded flow is dropped and logged. Probe every `NEW`/unverified stub against the project's
   own route or command registry. A stub that does not resolve becomes `SKIPPED-NOT-BUILT` --
   logged, never handed to a tester, never guessed at.
2. **Preconditions and drift.** Before driving anything, walk every configured surface and run
   `fr.drift.detect_drift` against the current repository: a surface whose evidence has vanished
   from the repo, a surface the repo now contains but the config does not, or a launch command
   that changed underneath the config. Report every line it returns.
3. **The GO gate.** Present scope, drift, and any open questions once, together, before any
   surface is driven. **The interview closes permanently at GO** -- no further questions reach
   the user for the rest of the run, including recovery (`references/stuck.md` R2-R5 are decided
   by the main thread alone). Fast mode's narrow interrupt right covers credentials and
   destructive authority only, never recovery, never clarification.
4. **Dispatch.** One tester per surface, each reading `references/testing.md`,
   `references/evidence.md`, and `references/stuck.md`, plus its own `references/surfaces.md`
   driver section and the critique lens file matching its surface's `kind` --
   `references/lenses/ui.md` for a `ui` surface, `references/lenses/cli.md` for a `cli` surface,
   `references/lenses/api.md` for an `api` surface. A `library` surface reads none of the three:
   `fr.lenses.has_critique` is `False` for it, so there is no lens file to point at. Each tester
   drives only the surface it was assigned and reports structured events, never narrative, to
   `<RUN>/events.jsonl` (`evidence.md` section 1 is the exact schema).
5. **Dashboard.** The live dashboard reads `events.jsonl` as testers append to it -- `run`,
   `step`, `shot`, `finding`, `status`, `withdraw` events. A screenshot only ever shows up there
   if its `shot` event was emitted alongside the file.
6. **Arbitration.** For a surface with a critique lens set (`fr.lenses.has_critique`), candidate
   findings that two or more lenses independently agree on go to a separate arbitration pass that
   sets final severity, merges duplicates, and kills any claim an objective measurement
   contradicts. A finding held by exactly one lens is kept verbatim as a minority opinion, never
   silently dropped. Objective failures -- crash, hang, data loss, wrong content, a failed round
   trip, or a project-declared lock violation -- bypass this vote entirely: one reproduction files
   at the severity the rule sets, and no lens may soften it.
7. **Manifest write-back.** What was learned during this run -- resolved stubs, dropped dead
   flows, step and entry-point corrections -- is written back now, at the end, since learnings are
   only known once driving and arbitration are done. Call `fr.manifest.apply_learnings` with the
   manifest path, the recorded `Config.flows_hash`, and the learnings collected above, then store
   its return value as the new `Config.flows_hash`. A run that learned nothing calls it with an
   empty list and writes nothing -- `apply_learnings` returns the recorded hash unchanged in that
   case, so `flows_hash` never moves without a reason.
8. **Report.** Section 5 below.

## 4. Agent tiering

The main thread never runs a screenshot-look-tap loop itself. Every surface is driven by a
dispatched tester; the main thread reads back structured verdicts and stuck reports, never a
transcript of taps. **Screenshots never reach the main thread** -- a tester keeps every capture in
its own context and returns at most one failing image, and only when a verdict genuinely depends
on seeing it. This is what keeps a multi-surface run from drowning the coordinating thread in
image tokens it cannot act on anyway.

## 5. The report

In order:

1. **Headline findings.** Every finding that is new or has changed severity since the previous
   run. A finding identical to the previous run's -- same location, same claim, same severity --
   is never headlined twice; `fr.findings.demote_repeats` does this demotion mechanically, keyed
   on a fingerprint that is coarse about whitespace and punctuation but exact about severity, so a
   severity change always re-promotes a finding even when its wording did not move.
2. **Repeats, collapsed to a count.** Everything `demote_repeats` classified as a repeat is listed
   once, by location, with how many runs it has now been seen on -- never repeated in full. A
   report that opens with the same three findings every run teaches its reader to skip it.
3. **What was skipped, and why.** Every `SKIPPED-NOT-BUILT` flow, every quarantined
   (`BLOCKED`) flow with its stuck report, every surface that halted on three consecutive
   quarantines, and every surface with no critique lens set -- named as such, in words ("this
   surface gets QA and no design critique"), never as a silently empty section.

Carried forward from the whole design, restated here because a report that violates any of these
is not this tool's report:

- the skill never fixes anything and never edits product code -- it only logs what it found;
- a finding produced on a cheap surface must reproduce on the real one before it is filed;
- the interview closes permanently at GO;
- screenshots never reach the main thread;
- stuck is evidence about the product, not merely an obstacle to route around;
- nothing is faked to keep a surface alive -- a surface that cannot be proven is reported as such,
  never propped up to make the run look clean.
