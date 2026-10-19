# surfaces.md -- driver reference

A **surface** is one thing a `flow-review` run can drive: a web UI, a desktop app, a mobile app, a
CLI, an HTTP API, or a library. Each surface in the project's `.flow-review/config.json` names a
`kind` (`ui`, `cli`, `api`, `library`) and a `driver` (one of the sections below). This file states,
per driver, what it drives, how it is launched, how a tester proves it is actually attached before
driving it, and what evidence it can produce. `testing.md` covers how to drive one once attached;
`evidence.md` covers how to report what you found.

## Driver: cdp

Drives a Chromium-backed surface over the Chrome DevTools Protocol -- a web app in a browser
or an Electron application. (Tauri applications use the `tauri` driver instead; see below.)

**Launch.** The config's `launch` command, with the remote debugging port bound. For a packaged
desktop application the port is usually bound by an environment variable rather than an argument;
setup proves which one works and records it.

**Proven attached when.** A request to `http://localhost:<port>/json/version` returns JSON
naming the target.

**Evidence it can produce.** `getBoundingClientRect()` intersections, `getComputedStyle()`
values, `document.title`, console messages, screenshots, `measureText` in the real font.

BINDING -- Measure before you screenshot.
Applies even when the defect looks obvious in the image; capture the rect or computed value too.
Three of four screenshot-derived defects in a past run were false, because an image answers "does this look wrong" and never "is this wrong".
why: evidence.md, the evidence table

## Driver: playwright

Drives a web UI in a real browser that Playwright itself launches and owns, rather than one
already running that a debugging port is attached to.

**Launch.** `playwright.chromium.launch()` (or `firefox` / `webkit`, per config), then
`browser.new_page()` navigated to the config's base URL. Headless or headed per config.

**Proven attached when.** The returned page resolves `page.title()` without throwing and the
loaded URL matches the config's base URL.

**Evidence it can produce.** `locator.bounding_box()`, `page.evaluate()` for computed style and
DOM state, `page.screenshot()`, console and network events via `page.on(...)`, and a full trace
file if tracing is enabled.

## Driver: tauri

Drives a Tauri application in development or as a native binary. Tauri surfaces are driven
over the dev server (same as `playwright`, using `goto`, `click`, `fill`, `press`, `look`) when
the app is running in dev mode, and over the Chrome DevTools Protocol when confirming P0/P1
findings on the native Windows binary.

**Launch.** The app's own dev server (`build.beforeDevCommand`, e.g. `npm run dev`) for
development flows -- not `npm run tauri dev` / `cargo tauri dev`, which open the native window
(see setup.md section 5.5). For native
confirmation, `flow-review confirm --run DIR [--surface ID] [--finding ID]` launches the binary
named in the `binary` config option.

**Proven attached when.** The dev server responds to navigation; the native binary attaches over
CDP when the debugger port is available.

**Options.** `dev_url` (dev server URL, e.g. `http://localhost:1420`), `mocks_file` (path to
`tauri-mocks.json`), `binary` (path to the built binary for native confirmation on Windows --
relative paths resolve against the project root), `native` (`pending` or `webview2`; audit sets
`webview2` on Windows and `pending` elsewhere, and `confirm` skips only `pending` surfaces).

**Evidence it can produce.** Same as `playwright` during dev flows. During native confirmation:
`measure.check_page` runs the full engine ruleset on the native binary and writes evidence refs
to the ledger; `flow-review confirm` also produces a screenshot at `<run_dir>/native/<finding_id>/shot.png`.

## Driver: adb

Drives an Android app on one emulator or phone over `adb` (UI hierarchy dump, input events,
screencap). Same verbs as web (`goto`, `click`, `fill`, `press`, `look`); Maestro is not required.

**Launch.** Nothing is launched by config. `flow-review prove` starts the installed app if it is
not running (never force-stops, clears or uninstalls it). `start_cmd` is advisory text (e.g. the
Metro command) -- the engine never runs it.

**Options.** `app_id` (package name; required), `device` (adb serial; required when more than one
device is attached), `start_cmd`, `scheme` (deep-link scheme, enables `goto /x`), `metro_url`
(e.g. `http://localhost:8081`; Metro is needed only when the installed build is debuggable).

**Proven attached when.** `flow-review prove` finds exactly one device (or `options.device`), the
app is installed, Metro answers at `metro_url` if the build is debuggable, the app is foreground
and its hierarchy dumps, and the screen is not a dev launcher or red box.

**Driving.**
- Each action costs about 3-5s (hierarchy dump ~2s + 1s settle).
- Route is the screen-title slug; url is `android://<app_id>/<route>`. `goto /` brings the app to
  front; `goto /x` opens deep link `<scheme>://x` when `scheme` is set.
- Locators: `{"role":"button","name":...}` matches content-desc or visible text
  (accessibilityLabel); `{"testid": x}` matches RN `testID` / resource-id. `css` is unsupported.
- `LocatorNotFound` lists the foreground package and visible labels. If a system permission
  dialog is up, `click` its button by text ("Allow", "While using the app").
- `fill` is ASCII only and cannot contain `%`.
- No console or network signals, and no `fault` verbs.

**Evidence it can produce.** UI-tree bounds in dp via rules `rect.target-size` (<48dp),
`rect.overlap`, `rect.offscreen`; screenshots at `drive/<surface>/shot-NNNN.png`, attached to
each finding. When `uiautomator` cannot dump (animated screen) the step is `not-exercised` with
reason `hierarchy-unavailable`.

**Recordings.** Each recording is also exported as Maestro YAML (`<flow>.maestro.yaml`),
runnable with `maestro test`. Optional; nothing depends on it.

## Driver: ios-sim

pending-driver until M2/M3/M4 (A-14).

## Driver: shell

pending-driver until M2/M3/M4 (A-14).

## Driver: http

pending-driver until M2/M3/M4 (A-14).

## Driver: custom

pending-driver until M2/M3/M4 (A-14).
