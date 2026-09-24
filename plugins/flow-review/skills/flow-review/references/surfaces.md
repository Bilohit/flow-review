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

pending-driver until M2/M3/M4 (A-14).

## Driver: ios-sim

pending-driver until M2/M3/M4 (A-14).

## Driver: shell

pending-driver until M2/M3/M4 (A-14).

## Driver: http

pending-driver until M2/M3/M4 (A-14).

## Driver: custom

pending-driver until M2/M3/M4 (A-14).
