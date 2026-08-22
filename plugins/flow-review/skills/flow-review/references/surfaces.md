# surfaces.md -- driver reference

A **surface** is one thing a `flow-review` run can drive: a web UI, a desktop app, a mobile app, a
CLI, an HTTP API, or a library. Each surface in the project's `.flow-review/config.json` names a
`kind` (`ui`, `cli`, `api`, `library`) and a `driver` (one of the sections below). This file states,
per driver, what it drives, how it is launched, how a tester proves it is actually attached before
driving it, and what evidence it can produce. `testing.md` covers how to drive one once attached;
`evidence.md` covers how to report what you found.

## Driver: cdp

Drives a Chromium-backed surface over the Chrome DevTools Protocol -- a web app in a browser,
or an Electron or Tauri application.

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

## Driver: adb

Drives an Android surface -- an emulator or a physical device -- over the Android Debug Bridge.

**Launch.** The config's package name (and activity, if not the default launcher activity), via
`adb shell am start`. An emulator surface first boots the AVD named in config; a physical device
surface is expected already connected and unlocked.

**Proven attached when.** `adb devices` lists the configured serial as `device` (not `offline` or
`unauthorized`), and, for an emulator, `adb shell getprop sys.boot_completed` reads `1`.

**Evidence it can produce.** View-tree dump bounds (or a semantic accessibility-tree tool, where
the project has one wired in), `screencap` screenshots, `logcat` excerpts, `dumpsys` output.

BINDING -- Dump the view tree before any tap or typed input.
Applies even when the coordinates look obvious from a screenshot or from where a label visibly sits.
A guessed tap once produced a report of a serious regression that did not exist; a pass using real inspected bounds hit every control on the first try.
why: testing.md, interaction discipline

## Driver: ios-sim

Drives an iOS Simulator surface.

**Launch.** `xcrun simctl boot <device>` for the simulator named in config, then
`xcrun simctl launch <device> <bundle-id>` for the app under test.

**Proven attached when.** `xcrun simctl list devices` shows the target device as `Booted` and the
app's process is running on it.

**Evidence it can produce.** The simulator's accessibility tree, `simctl io <device> screenshot`,
and device logs via `simctl spawn <device> log stream`.

## Driver: shell

Drives a CLI surface: one command, its stdout/stderr and exit code observed directly, with no
persistent process or protocol in between.

**Launch.** The config's command line, run as a subprocess with the config's working directory
and environment.

**Proven attached when.** The process starts and its first expected output -- a prompt, a banner,
a fixed opening line -- appears within the config's timeout.

**Evidence it can produce.** Captured stdout and stderr (kept separate), exit code, wall-clock
duration, and any files the command wrote.

## Driver: http

Drives an HTTP API surface.

**Launch.** Nothing to launch if the service is already reachable at the config's base URL;
otherwise the config's `launch` command starts it first, and setup records how long it takes to
become reachable.

**Proven attached when.** A request to the config's health-check path returns a success status
within the config's timeout.

**Evidence it can produce.** Response status, headers, and body (compared structurally, never by
raw string match), latency, and server-side logs where the project makes them reachable.

## Driver: custom

For a surface with no built-in driver -- a game engine, an embedded device, a proprietary
protocol, anything the drivers above do not cover.

**Launch, attach-proof, and evidence capture** are all defined in the project's own config, as
commands or scripts it supplies. Setup records what "attached" means for this surface the first
time it is configured, since no default answer applies here the way it does for the named drivers.

**Evidence it can produce** is whatever the project's own tooling can produce. Hold it to the same
measure-first discipline as every other driver (`evidence.md`): a custom surface earns no
exception just because its evidence format is bespoke.
