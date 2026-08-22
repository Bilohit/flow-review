# Concepts

The vocabulary flow-review uses, and where each term lives in the code.

## Surface

One thing a run can drive: a UI, a CLI, an API, or a library. Defined per project in
`.flow-review/config.json` as a `Surface` -- `name`, `kind`, `driver`, `launch`, `preconditions`,
`destructive`, `provenance`. `plugins/flow-review/skills/flow-review/fr/config.py`.

## Kind

What a surface is: `ui`, `cli`, `api`, or `library` (`VALID_KINDS` in `fr/config.py`). Kind decides
which lens set applies to a surface -- see Lens below.

## Driver

How a surface is actually attached to and driven: `cdp`, `playwright`, `adb`, `ios-sim`, `shell`,
`http`, or `custom`. Each driver is documented once, with what it launches, how it proves it is
attached, and what evidence it can produce --
`plugins/flow-review/skills/flow-review/references/surfaces.md`.

## Lens

A critique question plus the evidence it is allowed to answer from -- nothing more. Lenses are data,
not code, keyed by surface kind, and never universal: a `ui` lens set differs from a `cli` lens set
because the interface itself differs. `library` gets no lens set at all -- code called only by other
code has no human-facing edge to critique.
`plugins/flow-review/skills/flow-review/fr/lenses.py`.

## Flow

One end-to-end path through a surface: an entry point, a sequence of steps, an expected outcome, and
the evidence to capture proving it. The base list is a project's own `.flow-review/flows.md`,
hand-edited and reconciled -- never guessed at, never overwritten wholesale --
`plugins/flow-review/skills/flow-review/fr/manifest.py` and
`plugins/flow-review/skills/flow-review/templates/flows.md`.

## Finding

One thing a run observed: a severity (`P0`, `P1`, `P2`), a location, and text. Findings that repeat
unchanged from the previous run demote to a count instead of re-headlining --
`plugins/flow-review/skills/flow-review/fr/findings.py`. The reporting schema for how a finding is
appended during a run is `plugins/flow-review/skills/flow-review/references/evidence.md`.

## Evidence

What backs a finding: a measured bounding-rect intersection, a `getComputedStyle()` value compared
to a token, an HTTP status code, a log excerpt -- never a screenshot standing alone. A screenshot
answers "does this look wrong", never "is this wrong". `references/evidence.md`.

## Provenance

How sure flow-review is about a fact it recorded about a surface, one of `audited` (detected in the
repo but never run), `proven` (actually run and confirmed working), or `user` (a person said so) --
`VALID_PROVENANCE` in `fr/config.py`. `audited` versus `proven` is decided by
`fr.prove.outcome_to_provenance`, which only awards `proven` to a launch command that was actually
witnessed exiting clean or reaching a confirmed-ready running state.

## Drift

A structural mismatch between the saved config and what the repository currently contains: a
surface's evidence appeared that was not configured, a configured launch command changed, or a
configured surface's evidence disappeared. The comparison stays deliberately dumb and structural --
surface set and launch command, never meaning -- because a drift check that flags a harmless rename
every run trains a user to click through the gate, which loses the gate entirely.
`plugins/flow-review/skills/flow-review/fr/drift.py`.

## The two phases

**First run.** `.flow-review/config.json` does not exist, so flow-review interviews you: it proposes
candidate surfaces detected from the project's own files (`fr/audit.py`), proves each confirmed
launch command actually works before recording it (`fr/prove.py`), and writes the config plus a
seeded `flows.md`.

**Every run after.** The config exists, so the interview is skipped. flow-review reports structural
drift, reconciles and drives the configured flows through whichever lens set applies to each
surface's kind, and folds findings through repeat demotion before they reach the report.
