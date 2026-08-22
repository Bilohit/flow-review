# flow-review -- flow manifest

The base flow list: the flows this project has decided to test end to end, one row per flow.
`flow-review` reconciles this file against the project's own state docs (named in config) and
probes any row it cannot resolve on its own, but this file is the seed you edit by hand.

**This file is yours, and a run never overwrites what you wrote.** The tool records a hash of
what it last wrote here. While the file still matches that hash the tool wrote it last and may
update rows in place. The moment you edit it, you own it: your bytes stay exactly as they are,
and whatever the run learned arrives instead as a marked block between
`<!-- flow-review learnings -->` and `<!-- /flow-review learnings -->` that you can accept, edit
or delete. Text above or below that block is never touched, and a run that learned nothing
leaves the file byte-identical. Flows observe only -- a run never fixes anything and never edits
product code.

## Row format

Stated once, used by every row. Each section header fixes **surface** and **driver**; each row
carries the remaining six fields as columns:

`id . surface . driver . mode tag . entry point . steps . expected outcome . evidence to capture`

- **id** -- stable and short, one prefix letter per surface (for example `w##` web, `c##` cli,
  `a##` api). A dropped flow's id is retired, never reused.
- **mode** -- `fast` runs in both modes; blank is deep-only.
- **`NEW`** -- entry point not established from the project's own docs. The cell holds a **probe
  target**, not a route. Scope resolution probes it; a tester never guesses. Unresolved ->
  `SKIPPED-NOT-BUILT`.
- **bounded wait** -- stated inline on any row that awaits an async operation (a sync, an upload,
  a background job, a transcription). Exceeding it is a FINDING ("the operation never completed"),
  not a stuck episode.
- How a driver is set up, launched, and driven is `surfaces.md` and `testing.md`. A row says only
  *what* to test.
- A row tests one thing end to end -- one entry point to one expected outcome. Two rows covering
  the same entry point but a different outcome are two rows, not one.

BINDING -- Never renumber or reuse a flow id.
Applies even when the flow it named is deleted or fully rewritten; retire the id and open a new one instead.
A prior run renumbered ids after a cleanup pass, and every finding filed against the old numbers silently pointed at the wrong flow in the next report.
why: this file, the Row format section, field `id`

---

## Example: web signup -- replace this section with your own

| id | mode | entry point | steps | expected outcome | evidence |
|---|---|---|---|---|---|
| w01 | fast | Landing page, primary "Sign up" button | 1. Load the landing page cold (no session). 2. Click "Sign up". 3. Fill the form with a fresh email. 4. Submit. 5. Confirm the account (email link or code, whichever the project uses) | The signup form renders with no console errors; submitting a valid form lands the user in a signed-in state with an explicit welcome or onboarding step, never a blank page; a duplicate email is rejected with a stated reason | Landing, form and post-submit shots; console error count; response body of the signup request |

Delete this row before recording real ones -- it exists only to show the six columns in use. Add
one section per surface, one row per flow, using the id scheme from Row format above. A flow with
no established entry point yet gets a `NEW` stub instead of a guess:

| id | mode | entry point | steps | expected outcome | evidence |
|---|---|---|---|---|---|
| w02 | | `NEW` -- probe target: the project's own billing settings screen, if one exists | -- | -- | -- |

If scope resolution cannot find a real route behind that probe target, `w02` becomes
`SKIPPED-NOT-BUILT` at the end of the run rather than being handed to a tester to guess at.

---

## Resolution rules

1. **Source 1 -- manifest.** This file is the base list. Ids are stable; never renumber.
2. **Source 2 -- reconcile** against the project's own state doc (named in config): a feature
   marked built but absent here gets a stub tagged `NEW`; a flow whose feature is dead, dropped, or
   superseded is removed and logged.
3. **Source 3 -- probe** `NEW`/unverified stubs only, against the project's own route or command
   registry -- a web route table, a CLI's own `--help` tree, an API's route list, wherever config
   points. Resolves -> testable.
4. **Does not resolve -> `SKIPPED-NOT-BUILT`**, logged, never handed to a tester, never guessed at.
   `SKIPPED-NOT-BUILT` is distinct from `BLOCKED` (a quarantined flow) and `NOT-RUN` (the lane
   halted before reaching it).
5. **End of run: what was learned is written back, but never over you.** If you have not touched
   this file since the tool last wrote it, resolved `NEW` stubs become full rows, dead flows are
   dropped, and step and entry-point corrections are applied in place. If you have touched it,
   the same learnings arrive as a marked block instead and your text is left alone. Ids survive
   either way.
6. Record what changed once, at the end of this section, in place of a running log: the current
   flow count by surface, how many are `fast`, how many are still `NEW`. Replace that note rather
   than appending endless revision history -- the learnings block is delimited at both ends so it
   is replaced in place and does not grow a little longer every run.

Total this revision: 2 flows (w01, w02) -- 1 `fast` -- 1 `NEW`. This line is a template; replace it
with your own project's real count after the first run.
