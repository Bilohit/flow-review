# testing.md -- the tester's manual

You are a tester in a flow-review run, assigned to one configured surface. `flows.md` (the
project's `.flow-review/flows.md`) says *what* to test; this file says *how* a run actually drives
and measures a surface, whatever kind it is. Read this file plus `evidence.md` and `stuck.md`.

Rungs above R1 are not yours -- see `stuck.md` for the full escalation ladder and who owns it.

## 1. Before you start

- Read the surface's entry in `.flow-review/config.json`: its `kind`, `driver`, `launch` command,
  and any device or environment identifiers it names. **Never hardcode a value that config already
  carries** -- a device serial, a port, a path, a credential. Read those from config at run time,
  every run; a value copied into a reference file goes stale the moment the project's environment
  changes.
- Build or launch fresh per the config's `launch` command before driving. A stale artifact that
  does not reflect the current source is not evidence about the current source -- it is evidence
  about an earlier one. If the project's setup does not already guarantee freshness, compare the
  artifact's modification time against the source tree's before trusting a live result.
- Confirm the surface is actually attached (`surfaces.md`, "Proven attached when") before driving
  it. Do not proceed on the assumption that a launch succeeded.

## 2. Interaction discipline

1. **Inspect the view or DOM before any tap and before any typed input.** No "obvious" coordinates
   guessed from a screenshot. A guessed tap can produce a confident, wrong verdict; a pass driven
   from real inspected bounds hits the intended control.
2. A log line showing input reached the surface's process proves the input reached the window, not
   the element you aimed at. It is not evidence against a miss.
3. **One action per command until positioning against a new screen is known.** Verify, then move
   on.
4. **Once positioning is known, batch several actions between screenshots.** Screenshot only at
   decision points, not after every action.
5. **Verify the preconditions actually held before believing a verdict.** Was the target screen
   really on screen? Did the previous action finish? Was the surface actually attached? A check run
   against the wrong state produces a confident wrong answer.
6. **Silence is not evidence that nothing is running.** Measure a background operation from a log,
   a data store, or another independent witness -- never from a poll that happened to see nothing.
7. **The same wrong result twice is stuck** (`stuck.md`) -- never a reason to retry the same thing
   a third time.

## 3. Stuck: detection

Capture a **state signature** before and after every action expected to change state:

| Surface kind | Signature |
|---|---|
| ui (mobile) | normalized view-tree dump hash |
| ui (web / desktop) | app-root DOM hash + current route |
| cli | stdout/stderr hash + exit code |
| api | response body hash + status code |

Declare stuck when any of these is true:

| Trigger | Detail |
|---|---|
| no-op | signature unchanged **twice in a row** after an action that should have changed it |
| repeat failure | the same step fails **twice** with the same error |
| silence | no event appended for the configured watchdog window |
| overrun | an awaited async result exceeds its stated bound |

**Two crashes on the same flow skip the ladder entirely.** Capture the crash log **immediately** --
that is the evidence -- file a `finding` at `P0`, emit the flow's `status` as `blocked`, and move
on to the next flow. Laddering a crash loop only buys more crashes.

**A slow result is not a stuck result.** Exceeding a bounded wait is a **finding** ("the operation
never completed"), logged with evidence, and the run continues. Batched or eventually-consistent
behaviour is not a hang; check the config's stated interval before concluding one.

## 4. Per-driver notes

Launch, attach-proof and evidence capabilities for each driver live in `surfaces.md`. These are
the extra gotchas that only show up once you are actually driving one.

### cdp

- Top-level `const`/`let` persist across separate `Runtime.evaluate` calls made in one execution
  context, and a second declaration throws `SyntaxError`. Wrap every expression in an IIFE.
- `Runtime.enable` **replays the whole console buffer** on attach. Compare *new* entries against a
  baseline taken at connect time; a non-empty result immediately after attaching does not mean
  something just happened.
- Object arguments to console calls arrive as remote handles, not values. Resolve each with
  `Runtime.callFunctionOn` (`returnByValue: true`), or you get the literal string `"Object"`.
- A `getBoundingClientRect()` result returned through `Runtime.evaluate` arrives as `{}` once
  serialized -- its properties are non-enumerable. Destructure the fields you need
  (`{x:r.x,y:r.y,w:r.width,h:r.height}`) before returning them.
- `document.hasFocus()` reading `true` does not prove OS-level keyboard focus; some focus-traversal
  behaviour only responds to real OS foreground focus, not a dispatched key event.

### adb (android)

- Pin the target serial on every call once more than one Android device can be attached at once;
  an unpinned command can silently hit the wrong one.
- A view-tree dump can fail to reach an idle state on a screen driven by a continuous animation
  loop (an idle-state error, or a stale previous-screen snapshot returned instead). There, and only
  there, fall back to screenshot-measured coordinates with a before/after screenshot per action --
  never a guessed coordinate anywhere else.
- A dump tool can throw internally on some Android builds and still write a valid result file.
  Check the file itself, not the tool's own stderr, before concluding the read failed.
- A synthetic swipe cannot complete a hold-then-drag gesture (an "activate after long press"
  interaction) or a latch-class swipe-to-reveal control; both need a real touch session to arm.
  Mark that leg unverified/harness-blocked rather than filing it as a broken interaction.

### shell / http

- Capture the exit code and stdout and stderr **separately**. A tool that writes its real error to
  stderr and a generic message to stdout reads as a clean success if only one stream is checked.
- For a long-running server surface, distinguish "process exited", "process hung", and "process is
  running but its health check fails" -- they are three different findings, not one.

These per-driver notes grow with the same discipline as the run's stuck-episode table: a novel
harness trap earns one new line here, symptom first, so the next run does not rediscover it.
