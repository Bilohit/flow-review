# evidence.md -- reporting and evidence rules

Two things every tester needs before touching a surface: how to report what happened, and what
counts as proof. Both apply to every surface kind and every driver equally.

## 1. How to report

One JSON object per line, appended to `<RUN>/events.jsonl`, UTF-8, newline terminated.

| type | required keys | meaning |
|---|---|---|
| `run` | ts, state (running/done/halted), mode (fast/deep), flows_total | run start / end -- main thread only |
| `step` | ts, surface, flow, step, state (running/ok/blocked) | one step of a flow |
| `shot` | ts, surface, shot (path relative to run folder) | screenshot captured |
| `finding` | ts, sev (P0/P1/P2), location, text; optional surface, flow, shot | a finding. `location` is required: cross-run repeat demotion fingerprints on `location` plus `text`, so a finding without one cannot be matched against a previous run and headlines again every time |
| `status` | ts, surface, state, text | surface state change, or flow completion -- see the two `state` domains below |
| `withdraw` | ts, finding_ts (the retracted finding's `ts`), text | **main thread only, post-run.** Retracts a finding that did not survive -- usually because the user answered the question it hung on. Decrements the severity counter and strikes the row, so the dashboard header can never disagree with the report below it. The log stays append-only: never edit or delete a `finding` line. |

`surface` names one of the surfaces defined in the project's `.flow-review/config.json`. `ts` is
ISO-8601. Extra keys are legal.

**A `status` event has two `state` domains, told apart by whether a `flow` key is present.**
Without a `flow` key it reports the surface itself and `state` is one of
`running`/`recovering`/`halted`/`degraded`/`done`. With a `flow` key it reports that flow's
completion and `state` is one of `ok`/`blocked`/`skipped`. A validator built from the surface
domain alone will reject every legitimate flow-completion event, which is why the two are
spelled out rather than left to the table. **Flow completion is always a `status` event carrying
a `flow` key** -- never a count of `step` events. Emit one when a flow ends, always.

A screenshot is only visible on the dashboard if it has a `shot` event -- **write the PNG and
emit the event together, every time.** Files alone leave the surface's panel blank.

### The append idiom -- use exactly this

```bash
TS=$(date +%Y-%m-%dT%H:%M:%S)
printf '%s\n' "{\"ts\":\"$TS\",\"type\":\"step\",\"surface\":\"<surface-name>\",\"flow\":\"f1\",\"step\":\"open the target screen\",\"state\":\"ok\"}" >> "$RUN/events.jsonl"
```

- **Bash tool only.** Do NOT use PowerShell `Add-Content` / `Out-File` / `>` for this file -- they
  write a BOM or ANSI bytes and the first line stops parsing as JSON.
- `date +%Y-%m-%dT%H:%M:%S` -- **no timezone offset.** An offset-bearing `ts` breaks elapsed math.
- One line. `>>` only, never `>`. Trailing newline mandatory.
- **Never rewrite the file. Never read it back.** Multiple writers append concurrently; it is not
  yours alone.
- Escape `"` and newlines inside `text`. Keep `text` to one sentence.

## 2. Evidence rules

**Measure first, screenshot second.** A screenshot answers "does this look wrong", never "is this
wrong". Three of four screenshot-derived defects in a past run were false.

| Claim | Valid evidence |
|---|---|
| layout / overlap / clipping | `getBoundingClientRect()` intersection math (overlap = >2px on both axes; clipped = `rect.right > innerWidth`) or native UI-tree bounds |
| token / colour / spacing | `getComputedStyle()` value, compared to the token |
| motion | **computed** `transitionDuration`, never the inline `style` attribute |
| text fit | canvas `measureText` in the real font vs the content box |
| crash / hang / wrong content / failed round trip | the log excerpt or the file itself -- objective, no council vote needed |

- Screenshots go to `<RUN>/shots/<surface>-<flow>-<nn>.png`. Every capture is followed by a `shot`
  event whose path is **relative to the run folder** (`shots/<surface>-f1-03.png`).
- **Screenshots stay in your context.** Never return an image to the main thread except **one**
  failing image when the verdict genuinely depends on seeing it.
- Findings go back as `finding` events plus a short structured verdict -- never narrative.
- Force UTF-8 stdout in any probe script; a locale that cannot render the surface's own characters
  crashes, and a sweep that errors is not a clean sweep.

The event schema above is the whole reporting contract. `testing.md` says how a tester drives each
surface; `stuck.md` says what to do when driving it stops producing a changed state.
