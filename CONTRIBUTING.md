# Contributing

flow-review is standard-library Python -- no dependencies to install, no build step.

## Running the tests

From the repository root:

```
python -m pytest -q
```

This runs every test in the repository, including `test_readme.py` and `test_manifests.py` at the
root, and the `fr/`, `dashboard/` and skill-level suites under
`plugins/flow-review/skills/flow-review/`. `pytest.ini` already puts both locations on
`pythonpath`, so no extra setup is needed.

To run only this repository's own documentation checks:

```
python -m pytest test_readme.py -q
```

## What to change and where

- `plugins/flow-review/skills/flow-review/fr/` -- the tool itself: `config.py` (the per-project
  schema), `audit.py` (proposes candidate surfaces), `prove.py` (actually runs and classifies a
  launch command), `lenses.py` (the critique lens sets, kept as data), `findings.py` (repeat
  demotion), `drift.py` (structural drift), `manifest.py` (the human-owned flow manifest).
- `plugins/flow-review/skills/flow-review/references/` -- the reference docs the skill reads at run
  time: drivers (`surfaces.md`), evidence and reporting rules (`evidence.md`), the stuck protocol
  (`stuck.md`). Keep these in sync with the modules they document -- a reference that drifts from
  the code it describes is worse than no reference at all.
- `plugins/flow-review/skills/flow-review/templates/flows.md` -- the seed flow manifest copied into
  a new project on its first run.
- `plugins/flow-review/skills/flow-review/dashboard/` -- the live HTML dashboard folded from a run's
  `events.jsonl`.
- `assets/`, `docs/`, `README.md`, this file -- the page a stranger decides on.

## Ground rules

- Every non-trivial module keeps a sibling test (`test_*.py` next to it). Read the module's own
  docstring before changing it -- several of these modules exist specifically because an earlier,
  simpler version was proven wrong by a real failure, and the docstring names which one.
- A lens set is data (`fr/lenses.py`), never code -- add or change one there, never by special-
  casing a surface kind somewhere else. A new lens set is added when a real user asks for one, never
  on a hunch.
- The flow manifest (`.flow-review/flows.md` in a consuming project, `templates/flows.md` here) is a
  human's document. Nothing in this repository may overwrite it unconditionally -- `fr/manifest.py`
  is the mechanism that protects a hand edit.
- No emoji, no arrow characters, no typographic dashes in anything you write here -- use `->` and
  `--`. Keep the register plain: this is a QA tool, not a pitch.
- A comment starting `ponytail:` marks a deliberate simplification with a known ceiling -- it names
  the shortcut and the upgrade path. Do not "fix" one silently; either the ceiling is being hit and
  the named upgrade goes in, or the comment stays.
- Do not vendor third-party code without an upstream URL and an author credit in `README.md`'s
  Credits section -- see that section for the current status.

## Before opening a pull request

Run `python -m pytest -q` from the repository root and make sure it is clean. If you touched
`README.md`, `assets/`, `docs/`, or this file, also run `python -m pytest test_readme.py -q`
directly, and check the changed files by eye for a stray emoji, arrow, or a leading byte-order
mark -- `test_readme.py` only checks `README.md` and the SVGs in `assets/` for these, not every
file you might touch.
