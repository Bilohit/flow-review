# Walkthrough

One worked example: from installing the plugin, through a first run's setup interview, to a second
run that demotes a repeat finding. The project used here -- a small web app with a `dev` script and
a CLI with a `--config` flag -- is a stand-in for whatever you point flow-review at; the mechanism
described is the real code, not an invented one.

## 1. Install

Inside your own project, in Claude Code:

```
/plugin marketplace add Bilohit/flow-review
/plugin install flow-review
```

## 2. First run -- the setup interview

Run the skill in a project with no `.flow-review/config.json` yet. There is nothing to skip to, so
flow-review sets itself up before it drives anything.

The audit reads what the project already has: a `package.json` with a `dev`, `start`, or
`serve` script becomes a `ui` candidate driven by `cdp`; a `pyproject.toml` with a
`[project.scripts]` table becomes one `cli` candidate per entry, driven by `shell`; an
`openapi.yaml`/`swagger.json` at the root becomes an `api` candidate driven by `http`. Every
candidate carries the exact citation it came from -- for example `package.json:7 -> "dev": "vite"`
for a script, or `openapi.yaml (file present)` for a whole-file hit that has no single line to
point at.

You are asked to confirm or correct each candidate: rename it, change its kind, or decline it
outright. Nothing is written as proven on your say-so alone -- flow-review actually runs the
confirmed launch command and classifies it as one of four outcomes rather than a single pass/fail bit:
`exited_clean`, `exited_failed`, `running_ready`, or `not_proven`. A dev server is not expected to exit,
so it is proven `running_ready` when a precondition confirms it is actually listening -- never by waiting out
an exit that will never come. Only `exited_clean` or `running_ready` earns the surface a `proven`
provenance in the saved config; anything else is recorded `audited` and gets asked about again next time.

Once every candidate is resolved, flow-review writes `.flow-review/config.json` and seeds
`.flow-review/flows.md` from `templates/flows.md`.

## 3. Second run -- planning with a goal

Now you run flow-review again with a goal in mind: you want to test the checkout flow end to end.

```
flow-review plan --mode goal --goal "Complete a purchase with a credit card" --json
```

The planner estimates tokens needed at the GO gate:

```json
{
  "surface_id": "web",
  "estimated_tokens": 47000,
  "status": "ready",
  "url": "http://localhost:5173"
}
```

The estimate is under your token cap. flow-review starts the run. When ready, `flow-review serve` starts
the live dashboard:

```
http://localhost:3000  (live dashboard)
```

You open that URL in your browser and watch as the run proceeds. At the end of the run, the report shows:

```
P1  web / checkout / c01   Filling in --config documents but the flag is rejected with exit code 2 and no message.
P2  web / checkout / w03   GET /users and GET /users/:id disagree on field casing (userId vs user_id).
```

## 4. Suppressing the repeat on the next run

You recognize the P1 as a known limitation you plan to fix later. Rather than seeing it again, you
suppress it as a known issue:

```
flow-review triage <finding-id> wont-fix --reason "Planned for Q4"
```

On the next run, that finding remains in the ledger with its suppressed state. The report shows it
in a collapsed section with the triage note, and it no longer headline. It stays out of the headline
on every following run until you reopen it manually or it stops reproducing (then it transitions to
`fixed`). That is the whole mechanism: what changed gets your attention, and what didn't gets a
running count and a reason instead of your patience.
