# setup.md -- first-run and `--reconfigure` procedure

You are running `flow-review` in setup mode: `.flow-review/config.json` is absent, or the user
passed `--reconfigure`. This file is the whole procedure. Follow it in order; do not skip ahead to
proving a surface before it has been confirmed, and do not write `config.json` before every
surface in it has been proven or explicitly declined.

## 1. Ask preset or audit-and-prove

Ask the user which they want, or let what the repository declares decide it:

- **Audit-and-prove** -- detect real candidates from the repository itself, confirm each one with
  the user, then actually launch and observe each accepted surface before it goes in the config.
  This is the route when the repository declares a runnable entry point the detector reads (see
  section 2).
- **Preset** -- the user hands you the surfaces directly (kind, driver, launch command) with no
  detection pass. This is the route when it does not, or when the user already knows exactly what
  they want configured and wants to skip the interview either way; it still goes through proving
  (section 4) and provenance stamping (section 5), because a preset surface is no more trustworthy
  unproven than a detected one.

Neither path is recommended over the other -- which one applies is a fact about the repository
(section 2), not a judgment call between them. Both are proven and provenance-stamped identically.

## 2. Audit

Run `fr.audit.detect(root)`. It proposes candidates from what the repository actually contains --
a `package.json` `dev`/`start`/`serve` script becomes a `ui` surface driven by `cdp`, a
`pyproject.toml` `[project.scripts]` entry becomes a `cli` surface driven by `shell`, an OpenAPI or
Swagger file becomes an `api` surface driven by `http`. `fr.audit` only proposes; it never launches
anything itself -- that split is what lets drift detection later reuse the same detection without
re-running a launch.

Print every candidate with its citation exactly as `fr.audit` formatted it:

- `path:line -> snippet` for a finding that came from one line of a file.
- `path (file present)` for a finding whose evidence is the file's mere existence -- an OpenAPI
  spec, for instance, has no single line to cite. **This form with no line number is deliberate,
  not a bug in the detector** -- do not invent a fake line number to make it look like the other
  form.

If `fr.audit.detect(root)` returns an empty list, say so plainly and move straight to the
interview -- do not print an empty list and stop. Nothing was detected because this repository
does not declare a runnable entry point in a form the detector reads: no npm `dev`/`start`/`serve`
script, no `pyproject.toml` `[project.scripts]` table, no OpenAPI or Swagger document. That is a
fact about this repository -- a Go, Rust, Java, Ruby, .NET, PHP or Elixir codebase reads exactly
this way to the detector, and always will, because none of those declare their entry point in a
machine-readable form the detector can cite -- it is not a failure of the detector or a sign this
tool is the wrong fit. Tell the user directly and move to the preset path from section 1: the
interview is how their surfaces get configured, the normal route for a repository shaped like
theirs, not a fallback for one that failed.

## 3. Confirm each candidate

Show the user every candidate's citation and ask them to confirm, decline, or correct it, one at a
time. **A stranger confirms citations, never a summary** -- do not collapse three candidates into
"found a web app, a CLI, and an API, keep them?" and take one yes. Each candidate is its own
question, because the citation is the only thing standing between a real surface and a wrong guess
promoted into the config.

A declined candidate is recorded with `provenance: {"declined": "user"}` so that a later drift
check (section 5) never re-proposes it as newly detected on every subsequent run.

## 4. Prove each accepted surface

Every accepted surface -- audited or hand-typed via the preset path -- is proven before it can be
written into `config.json`, using `fr.prove.prove(candidate, root, preconditions=surface.preconditions)`.

**Proving a launch is not a pass/fail exit code.** `fr.prove.prove` returns a `Proof` whose
`outcome` is one of four values, never a boolean:

| Outcome | Meaning |
|---|---|
| `EXITED_CLEAN` | the command ran to completion and exited zero |
| `EXITED_FAILED` | the command ran to completion and exited non-zero |
| `RUNNING_READY` | the command never exited, and an independent precondition confirmed it is ready |
| `NOT_PROVEN` | neither of the above happened before the deadline |

Feed the surface's own `preconditions` list into `prove()` -- readiness comes from those and
nothing else. A dev server or any other long-lived process **never exits** on its own; waiting for
an exit that will never come is the bug this design replaces. `RUNNING_READY` **is proven** -- for
a `ui` surface backed by a server, still-running-and-ready is not a partial result, it **is** the
success case, and it must be treated as proven exactly like a clean exit.

Convert the outcome with `fr.prove.outcome_to_provenance(outcome)` rather than reading any
boolean -- it returns `"proven"` for `EXITED_CLEAN` and `RUNNING_READY`, and `"audited"` (i.e.
still unproven) for everything else, including `EXITED_FAILED`. Write that value into
`surface.provenance["launch"]`; never derive it yourself from the outcome by hand.

When the outcome is `NOT_PROVEN` because the launch never exits and no precondition was given --
the common case for a web UI that has no health endpoint yet -- **do not record it as a failure.**
Ask the user for a readiness command (a URL that returns 200, a log line to watch for, a port to
poll) and retry `prove()` with it as a precondition. This is the expected path for a plain web UI,
not an edge case.

Report to the user, by name, any surface whose `Proof.teardown_ok` came back `False`. A process
`prove()` could not confirm dead after the kill is now the user's problem to check manually --
silently discarding that fact and moving on is how an orphaned process outlives the setup run that
started it.

## 5. Stamp provenance

Every surface accepted from the audit in section 2 -- and only those -- gets
`surface.provenance["origin"] = "audited"` written alongside whatever `fr.prove` recorded. A
surface the user typed in by hand through the preset path never carries this key.

This is the exact marker `fr.drift.detect_drift` keys on (`DETECTED_PROVENANCE_KEY` /
`DETECTED_PROVENANCE_VALUE` in `fr/drift.py`): only a surface stamped `origin: audited` is ever
reported missing when its evidence later disappears from the repo. Get this backwards in either
direction and the drift gate breaks in one of two ways:

- **Miss the stamp on an audited surface** -> its removal from the repo is never detected. The
  config silently keeps trying to prove a surface that no longer exists.
- **Stamp a hand-added surface anyway** -> `fr.audit.detect` can never see it in the repository
  (it wasn't found there in the first place), so it is reported as newly "removed" on every single
  run. The gate cries wolf and the user learns to click through it -- which loses the gate
  entirely for the surfaces that actually matter.

## 6. Pick lens sets per surface

For each surface, call `fr.lenses.for_kind(surface.kind)` and record the returned lens names under
`config.lens_sets[surface.name]`. `ui`, `cli`, and `api` each get a real lens set (see
`references/lenses/ui.md` for the `ui` set in full; `cli` and `api` lenses live in `fr/lenses.py`
alongside it). A `library` surface's lens set is always empty -- `fr.lenses.has_critique("library")`
returns `False` -- because a surface called only from code has no human-facing edge to critique.

**Tell the user plainly, in the setup summary, that a `library` surface gets QA and no critique.**
It still gets the full QA pass: flows driven, evidence gathered, and objective failures (crash,
wrong output, a broken contract) surfaced as findings and ranked exactly like any other surface.
What it never gets is a design-critique pass, and the eventual report says so in words rather than
printing an empty critique section for it.

## 7. Choose the tester agent and evidence types

Ask the user (or accept a default) for which agent type dispatches as the tester for each surface,
and which evidence types that surface's tester is expected to produce (screenshots, view-tree
dumps, response bodies, logs -- per its driver in `references/surfaces.md`). Record these as
`config.tester_agent` and `config.evidence_types`.

## 8. Seed the flows manifest

Copy `templates/flows.md` into `.flow-review/flows.md` if it does not already exist. Interview the
user for the first few real flows -- replace the template's example section with real entry
points, steps, and expected outcomes for this project's actual surfaces, following the row format
`templates/flows.md` documents.

Record the seeded file's hash as `config.flows_hash` -- `fr.manifest.manifest_hash(text)` is what
the tool last wrote. This hash is an **ownership token**, not a cache-busting detail:

BINDING -- Never overwrite the flows manifest when a human has edited it.
Applies even when a run learns something that would correct a row in it; append an annotation
block instead of rewriting.
A version that rewrote the file unconditionally at run end destroyed hand-written flow notes the
first time someone edited the file between runs.
why: fr/manifest.py, BINDING rule at the top of the module

A **run that learned nothing writes nothing** -- `fr.manifest.apply_learnings` returns the
recorded hash unchanged, before reading or writing the file at all, so a no-op run never
transfers ownership away from a human who has never touched the file. Only when there is
something to record does the tool check `fr.manifest.is_human_edited`: if the file still hashes to
what was recorded, the tool wrote it last and may extend it directly; if the hash has moved, a
human owns the file now, and the tool's contribution lands inside the delimited
`<!-- flow-review learnings -->` ... `<!-- /flow-review learnings -->` block -- a header and a
footer bracketing exactly the tool's own lines -- leaving every byte outside that block untouched.
The manifest is append-only either way: it is never truncated, and a prior well-formed block is
replaced precisely, never the surrounding human content.

## 9. Keep run artifacts out of the host project's git history

`.flow-review/runs/` fills up with screenshots and `events.jsonl` on every pass. This repository's
own `.gitignore` covers its own `.flow-review/runs/`, but a project you are setting up has no such
line until you write one -- without it, the first `git add .` a stranger runs commits a folder of
screenshots.

Check the project root for a `.gitignore`. If one exists and does not already cover
`.flow-review/runs/` (a literal line, `.flow-review/`, or an equivalent pattern), append a
`.flow-review/runs/` line to it -- append only; never rewrite or reorder a file the user owns. If
the project has no root `.gitignore` at all, create `.flow-review/.gitignore` containing `runs/`
instead of inventing a root one on the user's behalf.

## 10. Write config.json

Assemble the `Config` (schema_version, generator_version, surfaces with their launch commands,
preconditions, and provenance, lens_sets, tester_agent, evidence_types, flows_hash) and write it
with `fr.config.save`. `generator_version` is the flow-review plugin's own version: read the
`"version"` string from this plugin's `plugin.json` at write time -- never hardcode it, never
carry it forward from an older config. It is provenance for debugging, not a compatibility gate;
`schema_version` is the gate. Then `save` re-validates every surface's `kind` and every provenance value before
a single byte reaches disk.

Print, in this order:

1. What was created -- the config path, every accepted surface by name and kind, and which ones
   are proven versus still audited-only.
2. The one command to run a real pass now that setup is done.
