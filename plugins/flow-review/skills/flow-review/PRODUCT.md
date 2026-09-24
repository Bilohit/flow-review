# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Vanilla ES modules + CSS, no build step (A-22; revisit only if `app.js` passes
~1k lines). Served locally by the engine's `serve.py` (`ThreadingHTTPServer`,
binds `127.0.0.1`) with SSE live-push (A-11) and a one-file static fallback
that inlines everything, fonts included (A-21). This is an existing-codebase
answer, not a user decision to re-ask.

## Users

The primary user is the tester who just ran (or is watching) a `flow-review`
session against their own product: a developer or QA person, mid-task, who
opened this dashboard to see what the run found and triage it before the run
finishes or right after. They are not a new visitor exploring a marketing
surface -- they came here with a specific job: scan findings by severity,
open evidence (screenshots, action logs) for a specific finding, and mark
findings resolved/false-positive/won't-fix/reopen as they work through the
list. A second, lighter use: watching a run live via SSE while it drives the
product, mostly as ambient status (surfaces, progress, budget) rather than
close reading.

## Product Purpose

`flow-review` drives a product end-to-end the way a first-time user would,
gathers real evidence from the live surface, and returns ranked findings plus
a design critique -- it never fixes anything and never edits product code. The
dashboard is the tester's window into one run's findings: a live-updating,
triage-first console, not a report to read passively.

## Positioning

Unlike a synthetic-monitoring or visual-regression tool, flow-review explores
like a real first-time user (happy path, unhappy paths, interruptions,
alternate routes) and never calls an LLM API from the engine itself -- all
judgment happens in dispatched subagents, the engine stays deterministic,
offline-capable, and holds no API key.

## Operating Context

- Runs entirely on `127.0.0.1`; a CI box or an air-gapped dev machine must be
  able to open this dashboard with no network reachable (no font CDN, no icon
  CDN, no external script).
- Findings are triaged interactively (open/false-positive/won't-fix/accepted/
  refuted/reopen) via `POST /triage`, which calls `flow_review.triage.apply`
  (C6) -- the same call the CLI's `flow-review triage` makes.
  Update in place, never a full reload, when new events arrive over SSE
  mid-run.
- A `not-exercised` section exists alongside findings: skipped steps (missing
  credentials, no test inbox, destructive action not opted in, budget cap)
  are visible, not silently dropped.
- A budget readout (`budget.used(run_dir)` against `cfg.budget["cap_tokens"]`)
  is present so the tester can see spend against the cap while a run is live.

## Capabilities and Constraints

- No subheadings and no descriptions anywhere in the UI -- icons and titles
  must be self-explanatory on their own (spec §11).
- Hover/focus tooltips double as the accessible name for icon-only controls;
  there is no separate visible label to fall back on.
- One findings badge (not one per severity, not per surface) -- severity is
  read from color + icon inside the list, not from a proliferation of counter
  chips.
- Progressive disclosure: the default view is scannable triage; evidence
  (screenshots, full action log, lens rationale) opens on demand, not inline
  by default.
- Eased motion honouring `prefers-reduced-motion` -- every transition has a
  reduced/instant fallback, never assumed off.
- Light/dark follow the OS (`prefers-color-scheme`) with an explicit in-page
  toggle that overrides it per session (not persisted server-side).
- Self-hosted fonts and an inline icon sprite only -- no runtime CDN fetch for
  either, so the dashboard never stalls or degrades waiting on a network
  request mid-run (this is also why the static fallback inlines both, A-21).

## Evidence on Hand

No existing dashboard implementation predates this work (M1 is a rebuild).
Reference points: `docs/concepts.md`, `docs/walkthrough.md`, and spec §11
(dashboard rules) and §3/§9 (engine constraints, GO-gate scope) in the
project's planning materials. No screenshots, testimonials, or third-party
evidence exist yet -- future work must not fabricate any.

## Product Principles

1. Triage is the primary action, not reading -- every design decision favors
   getting from "list of findings" to "this one is handled" in the fewest
   steps.
2. The dashboard never depends on network reachability beyond `127.0.0.1` --
   self-hosted assets, no CDN, works air-gapped.
3. Icons and layout carry meaning on their own; tooltips are accessibility
   infrastructure, not a crutch for an unclear icon.
4. Severity and state are shown, never buried behind an extra click, but
   evidence (the expensive-to-render detail) stays behind progressive
   disclosure.
5. The dashboard reflects a live run truthfully: SSE updates, budget spend,
   and not-exercised steps are first-class, not an afterthought bolted onto a
   static report view.

## Accessibility & Inclusion

`prefers-reduced-motion` is honoured throughout. Tooltips serving as
accessible names must still satisfy keyboard/focus and screen-reader access
(a `title`/`aria-label` alone, not `title` only, since `title` is not
reliably exposed to all assistive tech) -- left as an implementation
constraint for the components that build on these tokens (E4+). No other
product-specific accessibility requirement has been confirmed; treat WCAG AA
as the baseline until told otherwise.

## Design Direction

Confirmed (per spec §11 / the plan header) — **not reopened, not re-derived
here**:

- **Typography:** Schibsted Grotesk for UI text (Regular 400, SemiBold 600);
  IBM Plex Mono for numbers and logs only, never for UI copy.
- **Color:** cool neutrals for surfaces/text, one blue accent reserved for
  interactive elements, and a separate severity palette (`--sev-p0/p1/p2`)
  reserved exclusively for status -- never reused as a decorative or
  categorical color.
- **Shape:** hairline (1px) borders, 4px corner radius everywhere.
- **Icons:** Phosphor (MIT-licensed), hand-picked glyphs inlined as a local
  SVG sprite -- never fetched from a runtime CDN.
- **Theming:** light/dark follow the OS by default, with an explicit in-page
  toggle (`[data-theme]`) that overrides it for the session.

This direction is **not signed off** -- the M1 design pass (E5) finalises it.
E3 records the confirmation and ships the foundation (tokens, fonts, icon
sprite) that direction implies; it does not relitigate the choice.

## Design Mode

**Operate.** This dashboard is a tool the tester completes a task in (scan,
open evidence, triage), not a surface that persuades or narrates. Per
impeccable's mode table, "App UI, dashboards... outrank expression":
scanability, consistency with native/OS expectations (system fonts as
fallback, standard light/dark), and the real triage workflow take priority
over decorative expression. Brand shows up in precise details (the accent
blue, the 4px radius, the type pairing) rather than in bold visual statements.
