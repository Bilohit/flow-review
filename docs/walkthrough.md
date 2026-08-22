# Walkthrough

One worked example: from installing the plugin, through a first run's setup interview, to a second
run that demotes a repeat finding. The project used here -- a small web app with a `dev` script and
a CLI with a `--config` flag -- is a stand-in for whatever you point flow-review at; the mechanism
described is the real code, not an invented one.

## 1. Install

Inside your own project, in Claude Code:

```
/plugin marketplace add Bilohit/build-state
/plugin install flow-review
```

## 2. First run -- the setup interview

Run the skill in a project with no `.flow-review/config.json` yet. There is nothing to skip to, so
flow-review sets itself up before it drives anything.

`fr.audit.detect` reads what the project already has: a `package.json` with a `dev`, `start`, or
`serve` script becomes a `ui` candidate driven by `cdp`; a `pyproject.toml` with a
`[project.scripts]` table becomes one `cli` candidate per entry, driven by `shell`; an
`openapi.yaml`/`swagger.json` at the root becomes an `api` candidate driven by `http`. Every
candidate carries the exact citation it came from -- for example `package.json:7 -> "dev": "vite"`
for a script, or `openapi.yaml (file present)` for a whole-file hit that has no single line to
point at.

You are asked to confirm or correct each candidate: rename it, change its kind, or decline it
outright. Nothing is written as proven on your say-so alone -- flow-review actually runs the
confirmed launch command through `fr.prove.prove`. That function watches what really happens and
classifies it as one of four outcomes rather than a single pass/fail bit: `exited_clean`,
`exited_failed`, `running_ready`, or `not_proven`. A dev server is not expected to exit, so it is
proven `running_ready` when a precondition confirms it is actually listening -- never by waiting out
an exit that will never come. Only `exited_clean` or `running_ready` earns the surface a `proven`
provenance in the saved config (`fr.prove.outcome_to_provenance`); anything else is recorded
`audited` and gets asked about again next time.

Once every candidate is resolved, flow-review writes `.flow-review/config.json` and seeds
`.flow-review/flows.md` from `templates/flows.md`.

## 3. First run's report

The first run has no previous findings to compare against, so `fr.findings.demote_repeats` returns
everything as headline -- there is nothing yet to demote against. Say the run comes back with:

```
P1  cli / init / c01   --help documents --config but the flag is rejected with exit code 2 and no message.
```

That is a real bug in the stand-in CLI: the flag is documented but not implemented. Nobody fixes it
between runs -- flow-review never edits product code, only reports on it.

## 4. Second run -- the repeat gets demoted

The bug still reproduces identically on the second run: same location, same text, same severity.
`fr.findings.demote_repeats` fingerprints each finding on its normalized location and text --
whitespace collapsed, case folded, one trailing period stripped, severity deliberately excluded so a
severity change would still re-promote it -- and matches this run's finding against the previous
run's. It is demoted:

```
Repeats -- 1 finding collapsed
P1  cli / init / c01   runs_seen: 2   repeat_of: <the first run's ts>
```

It stays out of the headline on every following run until it either stops reproducing (fixed) or its
severity changes. That is the whole mechanism, and it is the reason a long-lived flow-review report
still says something worth reading on run twenty: what changed gets your attention, and what
didn't gets a running count instead of your patience.
