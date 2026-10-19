# flow-review M3 (Android) Implementation Plan, revised

> Supersedes `2026-09-24-flow-review-m3-plan.md` (branch `plans/m2-m5`). That plan was drafted before
> M2 landed. It assumed Expo Go and drove every step through `maestro test`. This revision follows a
> real-device spike on 2026-10-19 (emulator-5554, Android 15, density 420, a dev-client Expo app),
> which measured `uiautomator dump` at about 2.3s and `screencap` at about 0.3s.
> Executor: superpowers:subagent-driven-development. Each task names its executor model. Opus
> (orchestrator) reviews each wave.

**Goal:** Drive any installed Android app (Expo Go, Expo dev-client or prebuild, bare React Native,
native Kotlin/Java) through the existing `drive`/`replay` verb set. The explorer, lens and
cold-eyes agents should then work on mobile the same way they work on web.

**Architecture:** A new `flow_review/android/` package uses the adb transport only:
- `uiautomator dump` for the hierarchy, `input` for actions, `screencap` for evidence, and
  `am start` for launches and deep links.
- `AndroidDriver` has the same duck-typed method set as `WebDriver`, so `DriveSession` and `replay`
  each gain one dispatch point.
- Maestro is **not** a runtime dependency. Recorded flows are also exported as Maestro YAML, so a
  team can replay them in its own CI.

**Tech stack:** Python stdlib only: `subprocess`, `xml.etree`, `shutil`, `urllib`. No new
dependency.

## Global Constraints

- The engine never calls an LLM API, never edits product code, never boots an emulator, and never
  installs or uninstalls an app.
- **No-wipe invariant.** The engine never issues `pm clear`, `uninstall`, `clearState` or
  `clearKeychain`, and never writes them into exported YAML. A test asserts this. Any app-state
  reset belongs to a later milestone and must read `surface.state` and the destructive opt-in.
- The engine can launch the app (`monkey -p <app> -c LAUNCHER 1`), but it never force-stops it.
  `launch` attaches when `pidof` shows the app already running.
- Every adb call goes through `android/adb.py::run`:
  - The `adb` path is resolved once, with `shutil.which`, then `$ANDROID_HOME`, then
    `%LOCALAPPDATA%\Android\Sdk\platform-tools`.
  - `-s <device>` is always passed when a device is known.
  - Calls use `encoding="utf-8", errors="replace"` and a timeout of 20s, or 60s for the launch wait.
  - The runner is injectable, so tests use recorded strings and never need a real device.
- Ponytail rung is stated per task. A deliberate ceiling gets a `# ponytail:` comment.
- Tests run from the repo root: `rtk proxy python -m pytest -q -p no:cacheprovider`. The baseline
  is 626 passed, 1 skipped.
- Test fixtures are synthetic hierarchies. A recorded real dump of a user's app is never
  committed, because it contains their data.

## Decisions (A-73..A-84; these override the old M3 plan's A-38..A-40 and A-53..A-58 where they differ)

| id | decision |
|---|---|
| A-73 | The driver is named `android`, not `maestro`. `drift.RUNNABLE_DRIVERS` becomes `("playwright","tauri","android","http","shell")`. Where the M4 and M5 plans say "maestro", they mean "android". |
| A-74 | Transport is adb only (spike data above). Ceiling: `uiautomator dump` can fail with "could not get idle state" on endlessly animating screens. Mitigation: retry once, then raise `AdbError`, which the drive session reports as a `blocked` status (reason `hierarchy-unavailable`), not as a finding. Upgrade path: a fallback to `maestro hierarchy` when it is on PATH. |
| A-75 | `ANDROID_OPTION_KEYS = ("app_id","device","start_cmd","scheme","metro_url")`. `app_id` is required for a runnable surface. |
| A-76 | Detection (`audit._from_android`) triggers on any of: `app.json` or `app.config.{js,ts}` with expo, `android/app/build.gradle(.kts)`, or `app/build.gradle(.kts)` with `com.android.application`. `app_id` is resolved in this order: gradle `applicationId`, then gradle `namespace` (when an `android/` folder exists, gradle is authoritative), then `expo.android.package`, then `host.exp.exponent` (expo, no `android/` folder, no `expo-dev-client`), then `None`. When `app_id` is `None`, the candidate is `pending` with the evidence "set options.app_id". |
| A-77 | `start_cmd` is advisory; the engine never runs it. It is `npx expo start --dev-client` when `expo-dev-client` is a dependency, `npx expo start` for other expo apps, `npx react-native start` for bare RN, and `""` for native. `metro_url = "http://127.0.0.1:8081"` whenever `start_cmd` is non-empty. |
| A-78 | Readiness (`prove`) checks these in order: adb found; device resolved (`options.device`, else exactly one `device`-state serial, else NOT_PROVEN "ambiguous: set options.device"); app installed (`pm list packages`); if `metro_url` is set, `GET <metro_url>/status` returns `packager-status:running` and `adb reverse tcp:8081 tcp:8081` is run (benign); the app launched and is in the foreground; the hierarchy does not contain dev-launcher or red-box text ("Could not connect to development server", "Unable to load script", "Development servers"). |
| A-79 | Locators: `{"testid": x}` matches `resource-id == x` or ends with `:id/x` (RN `testID`). `{"role","name"}` matches `name` against `text`, then `content-desc` (exact first, then case-insensitive), for any interactive node; `role` narrows by class (button: Button or any clickable; textbox: EditText; checkbox: CheckBox; switch: Switch). `{"text": x}` is the same name match with no role. `{"css": ...}` raises `LocatorNotFound`. A miss raises `LocatorNotFound` naming the foreground package and the first 10 visible labels, so the agent can see a permission dialog and tap "Allow" itself. |
| A-80 | Mobile rules are computed from hierarchy bounds (px / (density/160) = dp). `rect.target-size` (P2) fires when either side of an interactive node is under 48dp. "Interactive" means `clickable`, or `focusable` with a non-empty `content-desc` and not scrollable. `rect.overlap` (P1) fires for overlapping interactive nodes, skipping pairs where one contains the other. `rect.offscreen` (P2) fires for an interactive node that lies partly outside the screen bounds. Ignored nodes: other packages, `resource-id` matching `dev-menu`, `dev_launcher` or `devmenu`, and zero-area nodes. Findings use the same `Finding` shape as `web/measure.py`. |
| A-81 | Route: `android://<app_id>/<route>`. `<route>` is the slug of the first text or content-desc among app nodes whose top edge lies in the top 20% of the screen, ordered by `(y, x)`; it falls back to `app`. Ceiling: a screen whose header shows data, not a title, gets an unstable route. Upgrade path: `options.route_ids`. |
| A-82 | `console_errors*()` and `network_log_since_check()` return `[]` (no logcat parsing until there is a real need). `fault` verbs on an android surface raise `ValueError("faults unsupported on android driver")`. Replay `--variants` gives a `not-exercised` status with reason `variants-unsupported`. |
| A-83 | Text input uses `input text` with spaces encoded as `%s` and shell metacharacters escaped. Non-ASCII raises `ValueError` (adb limitation, documented). After a fill, the IME is dismissed with `KEYCODE_BACK` only when `dumpsys input_method` shows `mInputShown=true`, because a blind Back would navigate away. Clearing a field uses `KEYCODE_MOVE_END`, then `KEYCODE_DEL` repeated once per character of the node's current text. |
| A-84 | Maestro export: `android/maestro_export.py::to_maestro(log, app_id)` writes `appId` then `---`, then `launchApp` (never `clearState`), then `tapOn`/`inputText`/`pressKey`/`openLink` steps. Every scalar is emitted with `json.dumps`. A secret or `from_env` fill becomes `inputText: ${ENV_NAME}`. `flow_end` writes `<flow_slug>.maestro.yaml` next to the saved recording, only for android surfaces with recording on. |

## Code facts that bind every task (from the drift review against `m2-tauri`)

- `web/driver.py` imports playwright at the top of the module, and playwright is only in the `[web]` extra. Android code must
  never import `flow_review.web.driver`. `LocatorNotFound` moves to a new neutral module
  `flow_review/locators.py`; `web/driver.py` re-exports it with `from flow_review.locators import LocatorNotFound`. `web/drive.py`
  imports `WebDriver` lazily (inside `_default_driver_factory`/`_tauri_driver_factory`).
- `serve()` takes `driver_factory=`. `cmd_start` already passes `--driver` and `--options-json`, but it
  requires `options.base_url`, and `serve --base-url` is `required=True` (drive.py:542-552, 738).
- `DriveSession._result` calls `driver.console_errors()`, and `fault`/`clear_faults` use `driver.page`.
  `flow_begin` guards `clear_faults` with `self._active_fault`. Edit these places surgically and never
  rewrite `__init__`/`flow_begin`/`_run_checks`. The web branch keeps `ledger.route_template`.
- Status events use the key `"state"`, not `"status"` (drive.py:244). `replay()` does not create
  `run_dir`, so call `mkdir(parents=True, exist_ok=True)` before `events.append`.
- In replay, `_browser_surfaces` filters on `("playwright","tauri")` (replay.py:342), and `_no_app_url`,
  `_health_ok` and `_launch_driver` assume a URL. `replay_log` (478-507) has the same shape. `assert_url`
  is a recorded action.
- Test-module idioms to follow: `from flow_review import config as cfgmod`, `prove as provemod`,
  `plan as plan_mod`, `drift.RUNNABLE_DRIVERS`. `test_audit.py:212`/`:218` already hold expo tests, so
  edit those rather than duplicating them. The parity test lives at `skills/flow-review/test_cli_parity.py`.
- Python floor is 3.10: no `tomllib`, and no `typing.Protocol.__protocol_attrs__`. No Protocol class is
  added (YAGNI); the driver is duck-typed, and `test_driver.py` asserts `hasattr` for each method name that
  `DriveSession`/`replay_one` call.
- `prove` and `check_*_tools` have no CLI surface today, and `setup.md` tells the agent to call Python
  (B2). T6 adds a `prove` verb.

## Plan-review resolutions (these bind and override the text below)

- **R1 (driver name):** `config.VALID_DRIVERS` already holds `"adb"`, so the driver is **`adb`**
  everywhere, never `android`. The package stays `flow_review/android/`.
  `drift.RUNNABLE_DRIVERS = ("playwright","tauri","adb","http","shell")`. The option tuple is named
  `ADB_OPTION_KEYS`.
- **R2 (no new status state):** where this plan says "blocked", use the existing
  `{"type":"status","state":"not-exercised","reason":"hierarchy-unavailable",...}`. The drive verb
  returns `{"not_exercised": "hierarchy-unavailable"}` and does not raise.
- **R3 (ownership):** T5 alone owns all of `web/drive.py`, including `cmd_start`/`serve`.
  `serve(base_url=None)` is allowed for adb, and `cmd_start` omits `--base-url` for adb.
- **R4 (evidence):** an adb step that files a finding captures one screenshot, using the existing
  `look` naming `drive/<surface>/shot-NNNN.png`, and appends its path string to that finding's
  `evidence` list before `events.append`.
- **R5 (route):** the adb route is `hierarchy.screen_route(...)` as-is, and `route_template` is not
  applied. `AndroidDriver.current_url` is `f"android://{app_id}/{route}"`. `_run_checks` reads the route
  from `driver.route` when `kind == "adb"`.
- **R6 (driver attributes):** `AndroidDriver` exposes `density`, `screen_wh` (both read once in
  `launch`), `route`, `nodes()`, `kind = "adb"`, `page = None` and `init_script = None`.
- **R7 (adb transport):** `android/adb.py` is a small `class Adb(device=None, runner=subprocess.run)`,
  and every method uses its device and runner.
  - Hierarchy: one call, `exec-out uiautomator dump /dev/tty`. Slice from `<?xml` or `<hierarchy`
    through `</hierarchy>`. On `ParseError` or no XML, retry once, then raise `AdbError`.
  - Text: substitute `%s` for spaces, then `shlex.quote` the value. `%` and non-ASCII raise
    `ValueError`.
  - Key deletion: one call, `input keyevent 67 67 ...`.
  - Launch: `monkey -p <pkg> -c android.intent.category.LAUNCHER 1`. Output containing
    "No activities found" raises `AdbError`.
  - Install check: exact line match `package:<pkg>`.
  - Foreground app: tolerate `mCurrentFocus=null` and fall back to `mFocusedApp`. Poll every 0.5s up to
    60s (the poll sleep is injectable).
  - IME: parse `mInputShown=true` in Python (there is no host grep).
  - Screenshots: `binary=True` gives raw bytes. `text`/`encoding` apply only to text calls.
  - Density: parse `Override density` first, then `Physical density`.
- **R8 (prove):** add `prove.prove_android(candidate, runner=subprocess.run) -> Proof`. It returns
  `outcome=RUNNING_READY` or `NOT_PROVEN`, fills the remaining `Proof` fields with empty values, and is
  dispatched in `prove()` for `driver == "adb"`. The CLI verb builds `audit.Candidate(**json)` and prints
  `{"outcome","reason","provenance": outcome_to_provenance(...)}`.
- **R9 (cuts):** drop `plan.py`'s `device-missing` gap (setup-env covers it). Keep the key map to
  Enter, Back, Del and MoveEnd. Metro `reverse` runs in `launch` only, and prove calls launch. The
  Maestro export (A-84) is kept, because the user named Maestro for M3 and it is small.
- **R10 (files):** T4's files are `web/actionlog.py`, `web/replay.py` (lines ~530-537 only) and the
  M2 plan doc. B3 changes the path to `replay/<surface_slug>/<stem>.result.json`. B4 adds a
  6-hex-digit sha1 suffix only when the slug differs from the raw value. Existing safe ids are unchanged.
- **R11 (models):** T8's agent briefs (`agents/*.md`) use sonnet. The references can stay on haiku.

## Tasks

The lanes in a wave touch disjoint files. A wave runs its tasks in parallel; Opus reviews and runs
the suite once per wave.

### Wave 1

**T1 — config, drift and detection** (sonnet; rung 6). Files: `config.py`, `drift.py`, `audit.py`,
and their tests.
- `VALID_DRIVERS` gains `android`; `ANDROID_OPTION_KEYS` (A-75) is wired into `_validate_options`
  the same way tauri's keys are. `RUNNABLE_DRIVERS` changes per A-73.
- `_from_android(root)` replaces `_from_expo` (A-76, A-77). It fills `scheme` from `expo.scheme`,
  string or list; for a list, it takes the first entry without a dot.
- **B1:** `_from_package_json` skips a dev script whose command starts with `tauri dev`,
  `react-native start`, or `expo start` without `--web`, and moves on to the next script name.
- Tests cover:
  - the four app classes (Expo Go; dev-client with `android/`; bare RN; native kts);
  - `app.config.ts` with no static id, which becomes `pending`;
  - the gradle `applicationId` winning over `app.json`;
  - the scheme list;
  - B1 for `tauri dev` and for `expo start`.

**T2 — `android/adb.py`** (sonnet; rung 2). Files: `android/__init__.py`, `android/adb.py`,
`android/test_adb.py`.
- `class AdbError(RuntimeError)`.
- `adb_path() -> str | None`.
- `run(args, device=None, *, timeout=20, runner=subprocess.run) -> str`. It raises `AdbError` on a
  nonzero exit or when adb is missing.
- `devices(runner) -> list[str]`, keeping only serials in `device` state.
- `density(device) -> int`, from `wm density` (the override wins over physical); 160 when the value
  can't be parsed.
- `screen_size(device) -> tuple[int, int]`, from `wm size`.
- `dump(device) -> str`, the XML: `uiautomator dump /sdcard/flow-review.xml`, then
  `exec-out cat /sdcard/flow-review.xml`. It retries once when the output lacks `<hierarchy`
  (A-74).
- `tap(x, y)`, `text(value)` (A-83 escaping), `key(name_or_code)`. The key map is Enter 66, Back 4,
  Tab 61, Escape 111, Home 3, Del 67, MoveEnd 123; an int is passed through.
- `screencap(path, device) -> Path`, using `exec-out screencap -p` with raw bytes (not text). It
  checks the PNG magic number and raises `AdbError` otherwise.
- `start(app_id)`, using monkey launcher; `open_link(url, app_id)`, using
  `am start -a android.intent.action.VIEW -d <url> <app_id>`.
- `foreground_package()`, parsed from the `dumpsys window` line `mCurrentFocus`; `pidof(app_id)`;
  `is_installed(app_id)`; `ime_shown()`; `reverse(port)`.
- `screencap` uses a bytes runner path, so `run` gets `binary=True`.

**T3 — `android/hierarchy.py`** (sonnet; rung 6, pure functions). Files: `flow_review/locators.py`
(new, holds `LocatorNotFound`), `web/driver.py` (only the re-export line), `android/hierarchy.py`,
`android/test_hierarchy.py`, `android/fixtures/*.xml` (synthetic, 2–3 screens modeled on the spike
structure: a header with icon Buttons carrying content-desc, a scrollable list of row Buttons,
small focusable badges, a bottom tab bar, plus one EditText password field).
- `parse(xml) -> list[dict]`. Each node has the keys
  `cls, text, desc, rid, pkg, bounds(x1,y1,x2,y2), clickable, focusable, scrollable, password,
  enabled, depth, index`.
- `resolve(nodes, locator) -> dict` (A-79).
- `interactive(node)`.
- `screen_route(nodes, app_id, screen_h)` (A-81).
- `outline(nodes, app_id) -> str`: an aria-like text outline, `- button "Calendar"` /
  `- text "Notes"` / `- textbox "Password" [password]`.
- `check(nodes, route, density, app_id, screen_wh) -> list[Finding]` (A-80).
- Tests: every A-79 match path; the containment pair skip; a 39px badge at density 420 fires
  target-size; a full-width row does not; other-package nodes are ignored.

**T4 — pending bug batch** (sonnet; rung 5–6). Files are disjoint from T1–T3, as the drift review
confirmed. It holds the bugs carried over from the M2 review, plus any the drift review turns up:
- (B2, `prove` has no CLI verb, moved to T6. Its doc half moves to T8.)
- **B3:** the `replay_log` result path collides across surfaces. Key it by surface slug.
- **B4:** `_slug` maps `a/b` and `a-b` to the same name. Add a short hash suffix only when the
  slug differs from the raw id.
- **B5:** record the unrecorded M2 deviations in the M2 plan's Appendix A (doc only).

### Wave 2

**T5 — `android/driver.py::AndroidDriver` + drive dispatch** (sonnet; rung 6). Files:
`android/driver.py`, `android/test_driver.py`, `web/drive.py`.
- `AndroidDriver(app_id, device=None, options=None, runner=subprocess.run)`. Attributes:
  `page = None`, `kind = "android"`, `init_script = None`.
- `launch(base_url=None)`:
  - Run `reverse(8081)` if `metro_url` is set.
  - If `pidof` is empty, call `start`.
  - Wait until `foreground_package() == app_id`, for up to 60s.
- `goto(path)`: when a scheme is set and `path` is not `"/"` or `""`, call
  `open_link(f"{scheme}://{path.lstrip('/')}")`; otherwise call `start` (bring to the foreground).
- `click(loc)`: tap the center of the resolved node.
- `fill(loc, value, secret)`: tap, then clear (A-83), `text`, and dismiss the IME.
- `press`; `screenshot(path)` uses `screencap`.
- `snapshot()` returns `{"aria": outline}`.
- `is_password(loc)`: the node's `password` attribute; if there is no node, true when the
  locator's name or testid matches `password|passcode|pin|secret`.
- `begin_step`/`end_step` drop the cached dump. `nodes()` dumps lazily and caches.
- `current_url` is a property, per A-81.
- `console_errors()`, `console_errors_since_check()` and `network_log_since_check()` return `[]`.
- `close()` does nothing (the app stays running).
- `web/drive.py` changes:
  - `DRIVER_FACTORIES["android"] = lambda headless, viewport, options=None: AndroidDriver(options["app_id"], options.get("device"), options)`.
  - `_current_url` falls back to `driver.current_url`.
  - `_run_checks`, when `getattr(driver, "kind", "") == "android"`, calls `hierarchy.check(...)`
    (with density and screen size cached on the driver) instead of `measure.check_page`.
  - Every finding filed on an android step gets the evidence ref `drive/<surface>/step-<n>.png`
    (captured once per step, only when a finding exists).
  - `fault`/`clear_faults` raise per A-82.
  - An `AdbError` raised from the hierarchy is reported as a `blocked` status (A-74).
  - `cmd_start`/`serve` get an android branch: no `base_url` or health path. `--base-url` becomes
    optional for `--driver android` only.
  - `WebDriver` is imported lazily.
  - The `_http` error path redacts with `events.redact(str(exc))` (it currently leaks).

**T6 — prove, setup-env, CLI** (sonnet; rung 6). Files: `prove.py`, `envsetup.py`, `cli.py`,
`plan.py`, and their tests. It does not touch `web/drive.py`, which belongs to T5.
- **B2:** add a new verb `flow-review prove --candidate-json <json|@file>`. It prints
  `{"outcome": ..., "reason": ..., "provenance": ...}` and exits 0 when proven, 1 when NOT_PROVEN, and
  3 on bad input. `setup-env` prints the adb gap.
- `prove` for an `android` candidate follows A-78. Each failed check returns NOT_PROVEN with a
  one-line, user-actionable reason, such as "start Metro: npx expo start --dev-client" or
  "install the app: npx expo run:android".
- `envsetup` gains an adb gap, with the install line "Android SDK Platform-Tools; add
  platform-tools to PATH". Maestro is listed as optional (only for running exported YAML).
- `cmd_start` with an android surface takes no `base_url` and needs no health path (mirror the
  tauri branch).
- `plan.py` gets a GO-gate gap `device-missing` when an android surface is present and
  `adb.devices()` is empty. The gap only, with a mockable runner.

### Wave 3

**T7 — replay + Maestro export** (sonnet; rung 6). Files: `web/replay.py`,
`android/maestro_export.py`, `android/test_maestro_export.py`, `web/drive.py` (only `flow_end`),
`web/test_replay.py`.
- `replay` and `replay_log` include android surfaces. The android branch comes before the URL,
  health and launch checks (`app_id` stands in). Replay uses the factory and the android check hook,
  and reports variants per A-82 with `state=`, after `run_dir.mkdir`.
- The JSON action log is the single source of truth for replay. The `.maestro.yaml` is an export
  only and is never read back. `to_maestro` skips `assert_url`.
- `to_maestro` follows A-84, with tests for: a value containing `a: b`; the secret becoming
  `${ENV}`; the no-wipe invariant (no forbidden command anywhere in the output, for any log); and a
  deep link becoming `openLink`.

**T8 — docs and briefs** (haiku). Files: `plugins/flow-review/skills/flow-review/SKILL.md`,
`references/{surfaces,testing,evidence,setup}.md`, `plugins/flow-review/agents/{fr-explorer,fr-lens}.md`.
- Cover:
  - the android driver and its options;
  - the prerequisites (device/emulator, app installed, Metro for debug builds);
  - persistent data (never wipe; avoid destructive taps unless opt-in);
  - permission dialogs: tap "Allow" or "While using the app" by text with `click`;
  - `goto` = deep link or foreground;
  - about 3s per step;
  - non-ASCII fill is unsupported;
  - the Maestro YAML export.
- The `test_cli_parity` and `test_repo_hygiene` tests must be green.

### Wave 4 — CP (Opus)

1. Full suite green. Review the whole `m3-android` diff (`code-review` + `ponytail-review` lenses).
2. Real-device run. It is read-only and non-destructive.
   - Target: emulator-5554 with an installed dev-client app (the user's reference app; nothing in
     the code is specific to it).
   - Steps:
     - `audit` gives an `android` candidate with the right `app_id`, `start_cmd` and `scheme`.
     - `prove` passes once Metro is up.
     - `drive`: begin, a `look` with a shot, a `click` on a tab, `press Back`, end.
     - The findings include `rect.target-size` for sub-48dp controls.
     - `replay` reproduces the flow.
     - The `.maestro.yaml` is written.
   - No fill, delete or settings change on the real app.
3. Update the memory index; push the branch. Merging stays the user's decision.

## Deferred (YAGNI, with the trigger to add each)

- iOS: needs a macOS host.
- logcat `console.error`: when a real run misses a crash the hierarchy can't see.
- `maestro hierarchy` fallback: when idle-state failures show up on a real app.
- The Expo planted-defect fixture app: M5 bench needs it, so it is built there.
- Non-ASCII input: an ADBKeyboard-style IME, once a user needs it.
- `app.config.js` evaluation: when a project has no static id and the user won't set `app_id`.

## Execution notes (decisions made from real-device runs, 2026-10-19)

| id | decision |
|---|---|
| A-85m | `prove` requires Metro only when the installed build is debuggable (`Adb.is_debuggable` reads `pkgFlags` for `DEBUGGABLE`). A release build of a dev-client project embeds its bundle; the reference device had one, and the first real `prove` wrongly asked for Metro. |
| A-86m | `AndroidDriver.end_step` waits a fixed 1.0s for the screen to settle (ponytail: polling dumps until two match is the upgrade path; at ~2s per dump it costs more than it saves). |
| A-87m | The post-action dump stays cached across `begin_step`. `click`/`fill` re-dump once on a locator miss. This takes a real click from ~5.5s to ~3.3s. |
| A-88m | Hierarchy outline drops a text node that repeats its containing control's name, and `screen_route` prefers text over content-desc-only nodes, so an icon button above the title can't name the screen. |
