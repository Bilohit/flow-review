# flow-review M2 (Tauri) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. Each task names its executor model; dispatch it pinned to that model, never `inherit`. Opus reviews every checkpoint.

**Goal:** Add Tauri desktop apps as a first-class flow-review surface: detect them, run flows against the dev server with mocked `invoke`, and confirm P0/P1 findings on the real native app via WebView2/CDP on Windows. Close the M1 debt log first (A-44) so later milestones build on a clean base.

**Architecture:** Reuse the M1 `WebDriver`/`DriveSession` unchanged for the dev-server run (Tauri's dev server is a normal web page); add a thin `tauri/` package for invoke mocks and native launch/attach; add one new CLI verb `confirm` that replays repro logs over CDP against the built native binary.

**Tech Stack:** Python engine (`flow_review`), Playwright for Python (`connect_over_cdp`), Rust/Tauri v2 fixture app, existing dashboard (vanilla JS).

**Spec:** `docs/superpowers/specs/2026-09-23-flow-review-v2-design.md` §3, §5, §6, §7, §9, §10, §12, §13. Prior plan: `docs/superpowers/plans/2026-09-23-flow-review-m1-plan.md` (Canonical Interfaces lines 127-148; Appendix A-1..A-34, lines 12218-12270).

## Global Constraints

- The engine never calls an LLM API. flow-review never edits product code. Every driver is reached only through engine CLI verbs (A-24 `drive` pattern).
- Run from repo root: `python -m pytest -q -m "web or not web"` (baseline before this plan: 513 passed, 0 failed).
- Executor tags: **haiku** = mechanical (renames, fixtures, docs sync, config plumbing); **sonnet** = standard TDD feature; **opus** = cross-cutting/high judgment (driver core, native launch/attach). Opus reviews every checkpoint.
- Ponytail: no speculative abstractions, no driver-plugin framework before a second non-Playwright driver needs one (that's M3 — this plan reuses `WebDriver` per A-47, not a new `Driver` protocol). Every task states the ponytail rung it stops at (1 skip / 2 stdlib / 3 native platform / 4 installed dep / 5 one line / 6 minimum code). Deliberate shortcuts carry a `# ponytail:` comment.
- Parallel lanes: tasks with disjoint file sets may run at once; at most 3 lanes per phase; every merge point is named. Never parallelize tasks sharing a file.
- Banned names (never write): `Ledger.load`, `.upsert(`, `runs_for`, `"severity"`, `viewports`, `refuted_reason`, `lens_or_rule`, `resolve_project_root(`, `envsetup.redact`, `add_suppression`, `_recordings_root`.
- Environment: Windows 11 host; cargo 1.96, rustc 1.96, node 24, npm 11, uv 0.11 installed; WebView2 runtime present; Playwright for Python installed via the `[web]` extra.

## File Structure (target)

```
plugins/flow-review/engine/flow_review/
  events.py                      (+ new_run_id)
  ledger.py                      (+ route_template)
  config.py                      (+ tauri driver, TAURI_OPTION_KEYS, RUNNABLE_DRIVERS)
  audit.py                       (_from_tauri promotes to driver "tauri")
  drift.py                       (runnable_surfaces uses RUNNABLE_DRIVERS)
  migrate.py                     (keeps old "pending" entries)
  cli.py                         (+ `run new`, `tauri mocks`, `confirm` verbs)
  plan.py                        (+ confirm engine step)
  tauri/
    __init__.py
    mocks.py                     (scan_commands, write_stubs, init_script)
    launch.py                    (launch_native)
  web/
    drive.py                     (DRIVER_FACTORIES dict, fault-matching via faults.url_matches)
    faults.py                    (url_matches, inject_slow via wait_for_timeout)
    replay.py                    (_new_run_id removed, uses events.new_run_id; route_template)
    driver.py                    (WebDriver.attach classmethod for CDP)
  dashboard/
    state.py                     (evidence-exists fold, confirmed field)
    serve.py                     (no change if /run/ already guards traversal; verified in T3)
    page/app.js                  (_assetUrl run-relative prefixing; native pair in drawer)
    page/app.css                 (no new rules; reuses .before-after)
  fixtures/
    tauriapp/
      src-tauri/                 (Cargo.toml, tauri.conf.json, src/main.rs, src/commands.rs)
      README.md
      planted.json
plugins/flow-review/skills/flow-review/
  SKILL.md                       (+ confirm step in run procedure)
  references/setup.md            (+ tauri section)
  references/surfaces.md         (+ tauri driver entry)
  references/validation.md       (+ native/<id>/result.json as replay evidence)
plugins/flow-review/agents/
  fr-explorer.md                 (+ one line: tauri = web verbs)
README.md                        (+ cargo tauri build note)
```

## Task Skeleton

| id | goal (one line) | deps | wave | owner | exec |
|---|---|---|---|---|---|
| T1 | M1 debt, engine web path: `events.new_run_id`, `faults.url_matches`, `inject_slow` via `wait_for_timeout`, flow-begin fault-clear only when active, `run new` CLI verb | T2 | 2 | D1 | sonnet |
| T2 | M1 debt, foundations: `ledger.route_template` used by drive+replay fingerprints, minors A1-A8 | — | 1 | D1 | sonnet |
| T3 | M1 debt, dashboard+docs: evidence-exists fold, `python -c` sweep + regression test | — | 1 | D4 | sonnet |
| T4 | Config+detection: driver `tauri`, `TAURI_OPTION_KEYS`, `RUNNABLE_DRIVERS`, `audit._from_tauri` promotion, migrate keeps old `pending` | T1, T2 | 3 | D1 | sonnet |
| T5 | Tauri fixture app `fixtures/tauriapp` + planted bug + `planted.json` | — | 1 | D1 | haiku |
| T6 | Mocks: `tauri/mocks.py` + `flow-review tauri mocks` CLI | T1 | 3 | D2 | sonnet |
| T7 | Web-first drive: `DRIVER_FACTORIES["tauri"]`, dev-server proving, mock-missing status event | T4, T6 | 4 | D2 | opus |
| T8 | Native confirm: `tauri/launch.py`, `WebDriver.attach`, `flow-review confirm` verb | T4, T7 | 5 | D3 | opus |
| T9 | Plan+budget: `confirm` engine step, SKILL.md run procedure, validation reference | T8 | 6 | D3 | sonnet |
| T10 | Docs sync: setup/surfaces/fr-explorer/README, `test_cli_parity` green | T9 | 7 | D3 | haiku |
| T11 | Dashboard: native confirm pair in drawer, `confirmed` field | T8 | 6 | D4 | sonnet |
| CP1 | M2 checkpoint | T1-T11 | 8 | — | opus |

## Lanes

- Phase 0 (wave 1): lane A = T2 (`ledger.py`, `audit.py`, `config.py`, `migrate.py`, `manifest.py`, `drift.py`, `prove.py`, `web/drive.py`, `web/replay.py` for the `route_template` call sites); lane B = T3 (`dashboard/state.py`, `dashboard/page/app.js`, `dashboard/serve.py`, skill and agent docs); lane C = T5 (`fixtures/tauriapp/**` only). Disjoint files.
- Lanes merge here: T1 starts after T2 (both edit `web/drive.py` and `web/replay.py`).
- Phase 1 (wave 2): T1 alone (`web/faults.py`, `web/drive.py`, `web/replay.py`, `events.py`, `cli.py` + tests).
- Phase 2 (wave 3): lane A = T4 (`config.py`, `audit.py`, `drift.py`, `migrate.py` + tests); lane B = T6 (`tauri/mocks.py`, `cli.py` + tests; after T1 because both add a `cli.py` verb). Disjoint files.
- Lanes merge here: T7 needs T4 and T6.
- Phase 3 (wave 4-5): T7 then T8, sequential (both touch `web/drive.py`, `web/driver.py`, `tauri/`).
- Phase 4 (wave 6): lane A = T9 (`plan.py`, `SKILL.md`, `references/validation.md`); lane B = T11 (`dashboard/state.py`, `dashboard/page/app.js`, `dashboard/page/app.css`). Disjoint files.
- Lanes merge here: T10 after T9 and T11, then CP1.

## Canonical Interfaces

Copied from shared context (binding, exact names):

- `events.new_run_id() -> str` = `now_iso().replace(":", "-")`; every run-dir creator calls it.
- `ledger.route_template(path: str) -> str` replaces numeric and UUID path segments with `:id`; `drive.py` and `replay.py` call it before `ledger.fingerprint`.
- `faults.inject_slow` uses `page.wait_for_timeout(delay_ms)` inside the route handler, never `time.sleep`. URL matching uses one helper `faults.url_matches(url: str, pattern: str) -> bool` (Playwright glob semantics: `*` never crosses `/`, `**` does), used by `page.route` and `drive._is_self_inflicted` alike.
- `config.VALID_DRIVERS` gains `tauri`. `TAURI_OPTION_KEYS = ("dev_url", "mocks_file", "binary", "native")`. `_validate_options` dispatches on `surface.driver`. `RUNNABLE_DRIVERS = ("playwright", "tauri", "maestro", "http", "shell")` (only `playwright`/`tauri` exist as drivers this milestone; the tuple names the full target set from A-45 so M3/M4 only add code, not touch this tuple's shape).
- `drift.runnable_surfaces` includes a surface whose driver is in `RUNNABLE_DRIVERS`.
- `tauri/mocks.py::scan_commands(src_tauri: Path) -> list[str]`, `write_stubs(path: Path, commands: list[str]) -> int` (count of new stubs added, never overwrites a filled value), `init_script(mocks: dict) -> str` (JS matching `@tauri-apps/api/mocks` `mockIPC`'s shape: `window.__TAURI_INTERNALS__ = {invoke: (cmd, args) => Promise.resolve(mocks[cmd] ?? null), ...}`).
- `tauri/launch.py::launch_native(binary: Path, port: int) -> subprocess.Popen` starts the binary with env `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=<port>`; `cdp_url = f"http://127.0.0.1:{port}"`; `WebDriver.attach(cdp_url)` = `chromium.connect_over_cdp` + first context's first page.
- `flow-review confirm --run DIR [--surface ID] [--finding ID]`: replays each P0/P1 finding's repro log (`<run_dir>/repro/<flow_slug>.json`) on the native app over CDP, runs `measure.check_page`, appends evidence ref `native/<finding_id>/shot.png` to the finding's ledger entry, writes `<run_dir>/native/<finding_id>/result.json` = `{"finding_id", "reproduced": bool, "findings": [...]}`. Exit 0 = all reproduced, 1 = some did not, 3 = native app could not be attached. Verdicts stay with the M1 verifier (`validate resolve --kind replay --ref native/<id>/result.json`).
- `DRIVER_FACTORIES = {"playwright": _default_driver_factory, "tauri": _tauri_driver_factory}` dict in `web/drive.py`, grows one entry per milestone (A-46/A-45); the session builder looks up `surface.driver` in it instead of always calling `_default_driver_factory`.
- Every drive verb returns `{url, title, snapshot, shot, new_findings, console_errors}` (unchanged shape; tauri reuses `DriveSession._result`).

## Tasks

### A-44 coverage

Every named M1 deferral, mapped to the task and step that closes it. "Row #" is the row number in `.superpowers/sdd/final-review.md`'s "Logged minors triage" table (20 OK-FOR-LATER rows: the table also lists 3 MUST-FIX rows — #9 B2, #13 B10 auth token, #19 CP2 goto path — already fixed per that file's "Fix report (2026-09-24)" section; this plan touches none of those three again).

| Deferral / row | File:function | Task | Step |
|---|---|---|---|
| run_id `:` vs `-` | `events.py` / `web/replay.py::_new_run_id` | T1 | `events.new_run_id`, delete `_new_run_id` |
| fnmatch vs Playwright glob | `web/faults.py`, `web/drive.py::_is_self_inflicted` | T1 | `faults.url_matches` |
| slow fault `time.sleep` | `web/faults.py::inject_slow` | T1 | `page.wait_for_timeout` |
| flow-begin always fault-clear | `web/drive.py` flow-begin handling | T1 | guard on `self._active_fault` |
| Row 10 (B3 replay run_id ms-collision) | `web/replay.py` run-id use | T1 | same `new_run_id()` change closes B3: a run id now carries no `:`-truncation, and callers no longer mint a second id within the same millisecond because there is exactly one `new_run_id()` call per run |
| Row 12 (B10 register_secret no min length) | `envsetup.py::register_secret` | T1 | add a minimum-length check |
| Row 14 (B10 detached spawn untested) | `web/drive.py` detached-process spawn | T1 | add the missing test |
| Row 16 (CP2 drive re-emits all findings per action) | `web/drive.py::_result`/finding dedup | T1 | dedupe emitted findings against `self._seen_fingerprints` before appending |
| skill `python -c` calls | `skills/`, `agents/`, `README.md` | T3 | `test_repo_hygiene` |
| crop/evidence links vs run dir | `dashboard/state.py::fold`, `dashboard/serve.py` `/run/` route | T3 | `_drop_missing_evidence` |
| route-template fingerprint (final-review Important #5, A-6) | `ledger.py::route_template`, `web/drive.py`, `web/replay.py::_url_path` | T2 | `route_template` + call-site wrap |
| Row 1 (A1 unused subprocess import) | `audit.py` | T2 | remove the import |
| Row 2 (A2 provenance non-dict AttributeError) | `config.py` provenance validation | T2 | type-check before `.items()` |
| Row 3 (A7 declined+detected surface, vanished evidence) | `drift.py::detect_drift` | T2 | skip declined surfaces before the vanished-evidence check |
| Row 4 (A3 is_v1 TypeError on non-numeric schema_version) | `migrate.py::is_v1` | T2 | type-check before comparison |
| Row 5 (A4 concurrent Windows append unlocked) | `events.py::append` | T2 | documented as spec-accepted; add the note, no code change |
| Row 6 (A5 alias exact-match + severity compare) | `ledger.py` alias/reconcile path | T2 | exact match + ordered severity compare |
| Row 7 (A6 recorded_hash param unused) | `manifest.py` | T2 | remove or wire the parameter |
| Row 8 (A8 1s descendant window ceiling) | `envsetup.py` process-tree wait | T2 | documented as already addressed (E5 flake fix); add the note, no code change |
| Row 17 (CP2 no trace.zip) | `web/drive.py` | T1 | documented as OK-FOR-LATER, no code change (noted, not implemented, per final-review's own call) |
| Row 18 (CP2 contrast skips transparent bg + legacy check) | `web/measure.py` | T1 | documented as OK-FOR-LATER, no code change |
| Row 20 (CP2 utf-8 write untested) | `dashboard/static.py` write path | T3 | add the missing round-trip test |
| Row 21 (C4 test_references wording ban) | `skills/flow-review/test_references.py` | T3 | narrow the banned-phrase regex |
| Row 22 (E2 static.py placeholder/fake woff2) | `dashboard/static.py` | T3 | add a regression test; no fallback code exists to remove today, task still records the check |
| Row 23 (E1 serve vars(entry) fallback) | `dashboard/serve.py` | T3 | make the test fixture a real dataclass, drop the `vars()` fallback |

### Task T1: M1 debt, engine web path

**Executor:** sonnet · **Depends:** T2 · **Wave:** 2
**Files:** `plugins/flow-review/engine/flow_review/web/faults.py`, `plugins/flow-review/engine/flow_review/web/test_faults.py`, `plugins/flow-review/engine/flow_review/web/drive.py`, `plugins/flow-review/engine/flow_review/web/test_drive.py`, `plugins/flow-review/engine/flow_review/events.py`, `plugins/flow-review/engine/flow_review/test_events.py`, `plugins/flow-review/engine/flow_review/web/replay.py`, `plugins/flow-review/engine/flow_review/cli.py`
**Interfaces:** Consumes: `events.now_iso`. Produces: `events.new_run_id`, `faults.url_matches`, `flow-review run new` verb.
**Ponytail rung:** 2 (stdlib `re`, no new dependency) for `url_matches`; rung 5 (one line) for `new_run_id`.

- [ ] Write failing test — append to `plugins/flow-review/engine/flow_review/test_events.py`:

```python
def test_new_run_id_replaces_colons(monkeypatch):
    from flow_review import events
    monkeypatch.setattr(events, "now_iso", lambda: "2026-09-24T10:00:00")
    assert events.new_run_id() == "2026-09-24T10-00-00"
```

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/test_events.py -k new_run_id` — expect FAIL: `AttributeError: module 'flow_review.events' has no attribute 'new_run_id'`.
- [ ] Implement in `events.py` (append near `now_iso`):

```python
def new_run_id() -> str:
    """Windows directory names cannot contain ':'; every run-dir creator uses this id."""
    return now_iso().replace(":", "-")
```

- [ ] Run the same command — expect PASS.
- [ ] Write failing test — append to `plugins/flow-review/engine/flow_review/web/test_faults.py`:

```python
def test_url_matches_star_does_not_cross_slash():
    from flow_review.web.faults import url_matches
    assert url_matches("http://h/api/x", "*/api/*")
    assert not url_matches("http://h/api/x/y", "*/api/*")


def test_url_matches_double_star_crosses_slash():
    from flow_review.web.faults import url_matches
    assert url_matches("http://h/api/x", "**/api/**")
    assert url_matches("http://h/api/x/y", "**/api/**")


def test_inject_slow_uses_wait_for_timeout_not_sleep(monkeypatch):
    import time
    from flow_review.web import faults

    called = {"sleep": False}
    monkeypatch.setattr(time, "sleep", lambda *_: called.__setitem__("sleep", True))

    class FakeRequest:
        url = "http://h/api/x"

    class FakeRoute:
        def __init__(self):
            self.continued = False

        @property
        def request(self):
            return FakeRequest()

        def continue_(self):
            self.continued = True

    class FakePage:
        def __init__(self):
            self.waited = None
            self.handler = None

        def route(self, pattern, handler):
            self.handler = handler

        def wait_for_timeout(self, ms):
            self.waited = ms

    page = FakePage()
    faults.inject_slow(page, "*/api/*", 500)
    route = FakeRoute()
    page.handler(route)
    assert page.waited == 500
    assert route.continued is True
    assert called["sleep"] is False
```

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/web/test_faults.py` — expect FAIL: `ImportError: cannot import name 'url_matches'`.
- [ ] Implement — replace `plugins/flow-review/engine/flow_review/web/faults.py` in full:

```python
import re


def url_matches(url: str, pattern: str) -> bool:
    """Playwright glob semantics: '*' matches any run of characters except '/', '**' matches
    across '/', '?' matches one character except '/'. Used by page.route and by drive's
    self-inflicted check so both sides agree on what a fault pattern covers."""
    out = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if pattern[i:i + 2] == "**":
            out.append(".*")
            i += 2
            continue
        if ch == "*":
            out.append("[^/]*")
            i += 1
            continue
        if ch == "?":
            out.append("[^/]")
            i += 1
            continue
        out.append(re.escape(ch))
        i += 1
    regex = "^" + "".join(out) + "$"
    return re.match(regex, url) is not None


def inject_offline(page) -> None:
    def _handler(route):
        route.abort()
    page.route("**/*", _handler)


def inject_5xx(page, url_pattern: str, status: int = 500) -> None:
    def _handler(route):
        if url_matches(route.request.url, url_pattern):
            route.fulfill(status=status, content_type="text/plain", body="Internal Server Error")
        else:
            route.continue_()
    page.route(url_pattern, _handler)


def inject_slow(page, url_pattern: str, delay_ms: int) -> None:
    # ponytail: rung 3 (native platform feature) -- page.wait_for_timeout yields the Playwright
    # greenlet instead of blocking the process the way time.sleep would (M1 debt A-44).
    def _handler(route):
        if url_matches(route.request.url, url_pattern):
            page.wait_for_timeout(delay_ms)
        route.continue_()
    page.route(url_pattern, _handler)


def clear_faults(page) -> None:
    page.unroute_all()
```

- [ ] In `web/drive.py`, replace `import fnmatch` and the two `fnmatch.fnmatch(...)` call sites (`_is_self_inflicted`'s `http.5xx` branch) with `from flow_review.web.faults import url_matches` and `url_matches(url, pattern)`.
- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/web/test_faults.py plugins/flow-review/engine/flow_review/web/test_drive.py` — expect PASS.
- [ ] Write failing test — append to `plugins/flow-review/engine/flow_review/web/test_drive.py`, reusing this file's own `FakeDriver`/`FakePage` classes and constructing `DriveSession` directly, exactly as its neighboring tests already do (read the top of the file first — `FakeDriver`/`FakePage` are defined there, `DriveSession(driver, surface_id, run_dir, project_root, record_enabled)` is the real constructor):

```python
def test_flow_begin_without_active_fault_appends_only_step_event(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    project_root = tmp_path / "project"
    (project_root / ".flow-review").mkdir(parents=True)
    driver = FakeDriver()
    session = DriveSession(driver, "web-app", run_dir, project_root, False)
    session.cmd_flow_begin("flow-1")
    lines = (run_dir / "events.jsonl").read_text(encoding="utf-8").strip().splitlines()
    types = [json.loads(line)["type"] for line in lines]
    assert types.count("step") == 1
    assert "fault" not in types
```

  (If `DriveSession` has no public `cmd_flow_begin` method — check whether flow-begin is dispatched only through the module-level `cmd_flow_begin(args)` function that builds a session internally — adapt the call to whatever the session's own flow-begin entry point is actually named; do not invent a name not present in `drive.py`.)

- [ ] Run the flow-begin test — expect FAIL: a `fault` event is appended unconditionally today.
- [ ] Implement: in `DriveSession`'s flow-begin handling, guard the `clear_faults()` call (and its resulting `fault` event) with `if self._active_fault:` (add `self._active_fault: bool = False` in `__init__`, set it `True` wherever `cmd_fault`/`_offline_active`/`_active_5xx_patterns` currently get set, and clear it back to `False` inside `clear_faults`).
- [ ] Run the same test — expect PASS.
- [ ] Add CLI verb: in `cli.py`, add `run new --project P` that calls `events.new_run_id()`, computes the run dir the same way the rest of the CLI resolves project paths, does `run_dir.mkdir(parents=True, exist_ok=True)`, and prints `json.dumps({"run_id": run_id, "run_dir": str(run_dir)})` to stdout, exit 0. Register it in the verb-dispatch table next to the other top-level verbs.
- [ ] In `web/replay.py`, delete `_new_run_id` and replace its one call site with `events.new_run_id()` (add the `from flow_review import events` import if not already present).
- [ ] Write failing test — append to `envsetup.py`'s test file (find its exact name, e.g. `test_envsetup.py`):

```python
def test_register_secret_rejects_a_value_shorter_than_the_minimum(tmp_path):
    from flow_review import envsetup
    try:
        envsetup.register_secret(tmp_path, "API_KEY", "ab")
        assert False, "expected a ValueError for a too-short secret"
    except ValueError:
        pass
```

  (Read `envsetup.py::register_secret`'s real signature first and adapt the call; row 12 of the minors table calls this OK-FOR-LATER because it "errs safe" — implement a minimum length of 8 characters, raising `ValueError` below it, closing the gap rather than leaving it OK-FOR-LATER now that M2 touches this file's neighborhood.)

- [ ] Run it — expect FAIL, then implement the length check in `register_secret` and rerun — expect PASS.
- [ ] Write failing test — append to `web/test_drive.py` covering row 14 (detached spawn untested): locate the detached-process spawn call in `drive.py`'s `cmd_start`/server-launch path (grep `Popen` and `creationflags` or `start_new_session`), and add a test that monkeypatches `subprocess.Popen` and asserts `cmd_start` calls it with the detached flags already in the code (`creationflags=subprocess.DETACHED_PROCESS` on Windows or `start_new_session=True` elsewhere — read the existing call to know which). This locks in existing behavior with a test, per the minor's own text ("detached spawn untested"); no behavior change if the flags are already correct.
- [ ] Run it — expect it to either FAIL (if the flag is missing — then add it) or PASS immediately (if only the test was missing, which is what "untested" means) — report which occurred in the commit message.
- [ ] Write failing test — append to `web/test_drive.py` covering row 16 (drive re-emits all findings per action): call the same action twice in a row against a `DriveSession` whose driver's `check_page`/measure stub returns the same finding both times, and assert the second call's `new_findings` list is empty (the ledger already dedups by fingerprint at the ledger layer per the table's own note — this test locks in that `DriveSession._result`'s `new_findings` list, specifically, only reports ids new to `self._seen_fingerprints`, so the dashboard's live event stream doesn't re-announce a finding the ledger has already deduped):

```python
def test_drive_does_not_re_emit_an_already_seen_finding(tmp_path, monkeypatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    project_root = tmp_path / "project"
    (project_root / ".flow-review").mkdir(parents=True)
    driver = FakeDriver()
    session = DriveSession(driver, "web-app", run_dir, project_root, False)
    same_finding = {"surface_id": "web-app", "flow_id": "f1", "rule": "contrast.aa",
                     "route": "/", "locator": "#x", "sev": "P2", "text": "low contrast",
                     "evidence": [], "disposition": "engine"}
    monkeypatch.setattr(drive.measure, "check_page", lambda *a, **k: [dict(same_finding)])
    session.cmd_flow_begin("f1")
    first = session.cmd_click({"testid": "go"})
    second = session.cmd_click({"testid": "go"})
    assert len(first["new_findings"]) == 1
    assert second["new_findings"] == []
```

  (Adapt method names — `cmd_click`, the click-args shape — to `DriveSession`'s real API; the point is any two action calls whose measure step reports the same fingerprint twice.)

- [ ] Run it — expect FAIL if `_result`'s `new_findings` list is not filtered against `self._seen_fingerprints`; implement the filter (track fingerprints already appended to the ledger this session, skip re-adding their ids to `new_findings` on a later action) and rerun — expect PASS.
- [ ] Run `python -m pytest -q -m "web or not web"` — expect PASS, no regression.
- [ ] Verify: `python -m pytest -q -m "web or not web"`
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/events.py plugins/flow-review/engine/flow_review/test_events.py plugins/flow-review/engine/flow_review/web/faults.py plugins/flow-review/engine/flow_review/web/test_faults.py plugins/flow-review/engine/flow_review/web/drive.py plugins/flow-review/engine/flow_review/web/test_drive.py plugins/flow-review/engine/flow_review/web/replay.py plugins/flow-review/engine/flow_review/cli.py && git commit -m "fix(web): shared run_id, glob-correct fault matching, wait_for_timeout, flow-begin no-op fault clear (A-44)"`

### Task T2: M1 debt, foundations

**Executor:** sonnet · **Depends:** — · **Wave:** 1
**Files:** `plugins/flow-review/engine/flow_review/ledger.py`, `plugins/flow-review/engine/flow_review/test_ledger.py`, `plugins/flow-review/engine/flow_review/audit.py`, `plugins/flow-review/engine/flow_review/test_audit.py`, `plugins/flow-review/engine/flow_review/config.py`, `plugins/flow-review/engine/flow_review/migrate.py`, `plugins/flow-review/engine/flow_review/manifest.py`, `plugins/flow-review/engine/flow_review/drift.py`, `plugins/flow-review/engine/flow_review/web/drive.py`, `plugins/flow-review/engine/flow_review/web/replay.py`
**Interfaces:** Consumes: `ledger.fingerprint`. Produces: `ledger.route_template`.
**Ponytail rung:** 2 (stdlib `re`).

- [ ] This task closes rows 1-8 of `.superpowers/sdd/final-review.md`'s "Logged minors triage" table (per the "A-44 coverage" table above): row 1 (A1, `audit.py` unused `subprocess` import), row 2 (A2, `config.py` provenance non-dict `AttributeError`), row 3 (A7, `drift.py::detect_drift` declined+detected surface reports vanished evidence), row 4 (A3, `migrate.py::is_v1` `TypeError` on non-numeric `schema_version`), row 5 (A4, `events.py::append` concurrent Windows append unlocked — spec-accepted, documentation only), row 6 (A5, `ledger.py` alias exact-match + severity compare), row 7 (A6, `manifest.py` unused `recorded_hash` param), row 8 (A8, `envsetup.py` 1s descendant window ceiling — already addressed by an earlier fix, documentation only).
- [ ] Write failing test — append to `plugins/flow-review/engine/flow_review/test_ledger.py`:

```python
def test_route_template_replaces_numeric_and_uuid_segments():
    from flow_review.ledger import route_template
    assert route_template("/orders/41") == "/orders/:id"
    assert route_template("/users/3fa85f64-5717-4562-b3fc-2c963f66afa6/edit") == "/users/:id/edit"
    assert route_template("/") == "/"
    assert route_template("/settings") == "/settings"
```

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/test_ledger.py -k route_template` — expect FAIL: `AttributeError`.
- [ ] Implement in `ledger.py` (append near `fingerprint`):

```python
import re as _re

_NUMERIC_SEGMENT = _re.compile(r"^\d+$")
_UUID_SEGMENT = _re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def route_template(path: str) -> str:
    """Collapse numeric ids and UUIDs in a route so /orders/41 and /orders/42 fingerprint to the
    same finding instead of two (final-review Important #5, A-6/A-44)."""
    segments = path.split("/")
    out = []
    for segment in segments:
        if _NUMERIC_SEGMENT.match(segment) or _UUID_SEGMENT.match(segment):
            out.append(":id")
        else:
            out.append(segment)
    return "/".join(out)
```

- [ ] Run the same command — expect PASS.
- [ ] In `web/drive.py`, find the call site(s) that build `route` for `ledger.fingerprint(flow_id, rule, route, locator)` from `self._current_url()`/`_finding_url()` and wrap the path portion with `ledger.route_template(...)` before calling `fingerprint`. In `web/replay.py`, find `_url_path` and its use before `fingerprint`, and wrap that value with `route_template` the same way. Confirm with a grep (`grep -n "fingerprint(" plugins/flow-review/engine/flow_review/web/*.py`) that both call sites are updated and no other call site is missed.
- [ ] Write failing test — append to `plugins/flow-review/engine/flow_review/web/test_drive.py` (or `test_replay.py`, whichever already has a fingerprint-focused test — match its pattern):

```python
def test_fingerprint_uses_route_template_for_numeric_ids():
    from flow_review.ledger import fingerprint, route_template
    fp_a = fingerprint("flow-1", "contrast.aa", route_template("/orders/41"), "#save")
    fp_b = fingerprint("flow-1", "contrast.aa", route_template("/orders/42"), "#save")
    assert fp_a == fp_b
    fp_static = fingerprint("flow-1", "contrast.aa", route_template("/settings"), "#save")
    assert fp_static == fingerprint("flow-1", "contrast.aa", "/settings", "#save")
```

- [ ] Run it — expect PASS immediately (this test only exercises `ledger.py`, already implemented above); this test locks the contract the drive/replay call-site edit above must uphold. Add a second assertion-only smoke test in `test_drive.py`/`test_replay.py` that calls the actual drive/replay code path with a URL containing `/orders/41` and checks the emitted finding's fingerprint matches one built from `/orders/:id` — adapt to that file's existing fixtures.
- [ ] Row 1 (A1): in `audit.py`, `grep -n "^import subprocess" plugins/flow-review/engine/flow_review/audit.py`; if the import is unused (no `subprocess.` reference anywhere else in the file), delete the import line and any trailing blank line it leaves. Write a failing test first in `test_audit.py`: `def test_audit_module_has_no_unused_subprocess_import(): import ast; from pathlib import Path; import flow_review.audit as m; tree = ast.parse(Path(m.__file__).read_text(encoding="utf-8")); imported = any(isinstance(n, ast.Import) and any(a.name == "subprocess" for a in n.names) for n in ast.walk(tree)); used = "subprocess." in Path(m.__file__).read_text(encoding="utf-8").split("import subprocess", 1)[-1]; assert not (imported and not used)` — run it (expect FAIL if the dead import is present), remove the import, run again (expect PASS).
- [ ] Row 2 (A2): in `config.py`'s provenance validation loop (`for key, value in surface.provenance.items(): ...`), a non-dict `surface.provenance` raises a bare `AttributeError` instead of the library's normal `ValueError`. Write a failing test in `test_config.py`: `def test_validate_surface_raises_value_error_for_non_dict_provenance(): from flow_review import config; surface = config.Surface(id="a", name="a", kind="ui", driver="playwright", launch=""); surface.provenance = "not-a-dict"; try:\n    config._validate_surface(surface)\n    assert False, "expected ValueError"\nexcept ValueError:\n    pass` — run it (expect FAIL: `AttributeError` is raised, not caught by `except ValueError`), then guard the loop with `if not isinstance(surface.provenance, dict): raise ValueError(f"surface {surface.id!r} field 'provenance' must be an object")` before the `.items()` call, rerun — expect PASS.
- [ ] Row 3 (A7): in `drift.py::detect_drift`, the second loop (`for surface in cfg.surfaces: ...`) already skips a surface whose provenance key doesn't match `DETECTED_PROVENANCE_VALUE`, but a `declined` surface with matching provenance still gets reported as "evidence is gone" even though a human explicitly declined it. Write a failing test in a `test_drift.py` (create it if it doesn't exist, following `test_audit.py`'s fixture-building style): `def test_declined_surface_is_not_reported_as_vanished_evidence(tmp_path): from flow_review import config, drift; surface = config.Surface(id="old", name="Old", kind="ui", driver="pending", launch="", declined=True, provenance={"origin": "audited"}); cfg = config.Config(schema_version=2, generator_version="t", surfaces=[surface]); messages = drift.detect_drift(cfg, tmp_path); assert not any("old" in m for m in messages)` — run it (expect FAIL), add `if surface.declined: continue` at the top of that loop body, rerun — expect PASS.
- [ ] Row 4 (A3): in `migrate.py::is_v1`, a non-numeric `schema_version` (e.g. a string) raises `TypeError` on comparison instead of being treated as "not v1". Write a failing test in `test_migrate.py`: `def test_is_v1_returns_false_for_non_numeric_schema_version(): from flow_review import migrate; assert migrate.is_v1({"schema_version": "not-a-number"}) is False` — run it (expect FAIL: `TypeError`), guard with `isinstance(value, (int, float))` before the numeric comparison, rerun — expect PASS.
- [ ] Row 5 (A4): documentation only — add a one-line comment above `events.append`'s file-write call: `# A4/A-44 row 5: concurrent same-millisecond appends on Windows are not lock-guarded; accepted per spec (single-writer-per-run in practice). Revisit if multi-process writers to one run dir become real.` No test, no behavior change.
- [ ] Row 6 (A5): in `ledger.py`'s alias/reconcile path (grep `alias` in `ledger.py` to find the exact function — likely a `find_alias_candidates`-shaped helper), fix two things: (a) the candidate search must not treat an alias whose locator is byte-for-byte identical to the finding's own locator as a "candidate rename" (exact match is not a rename); (b) any comparison of severities must use an ordered index into `("P0", "P1", "P2")`, never a plain string `==`/`<` comparison (string comparison of `"P0" < "P1"` happens to sort correctly today but is not the intended ordering rule — make it explicit). Write a failing test in `test_ledger.py` matching the real function's signature (read it first) asserting a self-identical locator is excluded from candidates and that `"P2" ` is correctly treated as lower severity than `"P0"` via the explicit ordering, not string comparison. Implement, rerun — expect PASS.
- [ ] Row 7 (A6): in `manifest.py`, find the function taking a `recorded_hash` parameter it never reads. Either wire it into an actual comparison (if the function's docstring/callers imply it should verify a recorded hash) or remove the parameter and update every call site — pick whichever the function's existing docstring/intent implies (read it first); do not guess blindly. Write a failing test in `test_manifest.py` locking in the chosen behavior, implement, rerun — expect PASS.
- [ ] Row 8 (A8): documentation only — add a one-line comment where the "descendant window" 1-second ceiling constant is defined in `envsetup.py`: `# A8/A-44 row 8: the E5 flake this ceiling caused was fixed upstream; a Job Object-based upgrade (no polling ceiling at all) is tracked as future work, not required for M2.` No test, no behavior change.
- [ ] Run `python -m pytest -q -m "web or not web"` — expect PASS, no regression.
- [ ] Verify: `python -m pytest -q -m "web or not web"`
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/ledger.py plugins/flow-review/engine/flow_review/test_ledger.py plugins/flow-review/engine/flow_review/audit.py plugins/flow-review/engine/flow_review/test_audit.py plugins/flow-review/engine/flow_review/config.py plugins/flow-review/engine/flow_review/migrate.py plugins/flow-review/engine/flow_review/manifest.py plugins/flow-review/engine/flow_review/drift.py plugins/flow-review/engine/flow_review/web/drive.py plugins/flow-review/engine/flow_review/web/replay.py && git commit -m "fix(ledger): route_template collapses numeric/uuid segments before fingerprinting (A-44 Important #5, A1-A8)"`

### Task T3: M1 debt, dashboard + docs

**Executor:** sonnet · **Depends:** — · **Wave:** 1
**Files:** `plugins/flow-review/engine/flow_review/dashboard/state.py`, `plugins/flow-review/engine/flow_review/dashboard/test_state.py`, `plugins/flow-review/engine/flow_review/dashboard/serve.py`, `plugins/flow-review/engine/flow_review/dashboard/page/app.js`, `plugins/flow-review/skills/flow-review/SKILL.md`, `plugins/flow-review/agents/*.md`, `README.md`, `plugins/flow-review/engine/flow_review/test_repo_hygiene.py` (new)
**Interfaces:** Consumes: dashboard state fold, `/run/` serving route. Produces: evidence-exists filtering in the fold; a hygiene regression test.
**Ponytail rung:** 2 (stdlib `os.path`/`pathlib` existence check; stdlib `re`/`Path.rglob` for the hygiene grep).

- [ ] This task closes row 21 (C4, `test_references.py` wording ban), row 22 (E2, `dashboard/static.py` placeholder/fake woff2 fallback), row 23 (E1, `dashboard/serve.py` `vars(entry)` test-only fallback), and row 20 (CP2 utf-8 write untested — the dashboard's own write-side UTF-8 path in `dashboard/static.py`; T1 separately closes rows 16/17/18, the drive/replay-side CP2 rows, so there is no overlap).
- [ ] Write failing test — append to `plugins/flow-review/engine/flow_review/dashboard/test_state.py`, reusing this file's own `_patch_common`/`_write_events`/`_FakeCfg` helpers exactly as its neighboring tests do (read the top of the file first for their real names):

```python
def test_fold_drops_evidence_missing_from_current_run_dir(tmp_path, monkeypatch):
    from flow_review.dashboard.state import fold
    _patch_common(monkeypatch)
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "shots").mkdir()
    (run_dir / "shots" / "real.png").write_bytes(b"\x89PNG\r\n")
    _write_events(run_dir, [
        {"ts": "2026-09-24T10:00:00.000Z", "id": "e1", "type": "run", "mode": "goal",
         "surfaces": [{"id": "web-app", "kind": "web"}]},
        {"ts": "2026-09-24T10:00:01.000Z", "id": "f1", "type": "finding", "sev": "P2",
         "surface_id": "web-app", "flow_id": "checkout", "text": "stale crop from an old run",
         "disposition": "engine",
         "evidence": ["shots/real.png", "shots/gone-from-a-different-run.png"]},
    ])
    state = fold(tmp_path, run_dir, _FakeCfg())
    findings = {f["id"]: f for f in state["findings"]}
    assert "f1" in findings
    assert findings["f1"]["evidence"] == ["shots/real.png"]
```

  (`fold`'s real signature is `fold(project_root, run_dir, cfg)`; there is no `fold_findings` function anywhere in this codebase — use `state.fold` throughout this task.)

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/dashboard/test_state.py -k evidence_missing` — expect FAIL: evidence entries pass through unchanged today regardless of whether the file exists.
- [ ] Implement in `dashboard/state.py`: add a helper near the top of the file (after whatever small helper precedes the main assembly, e.g. `_now_iso`):

```python
def _drop_missing_evidence(findings: list[dict], run_dir: Path) -> None:
    for f in findings:
        f["evidence"] = [e for e in f.get("evidence", []) if (run_dir / e).is_file()]
```

  then, inside `fold()`, immediately after the line that assembles the combined `findings` list (ledger findings plus unreconciled live findings — read the real variable name and insert right after that assignment), add:

```python
    _drop_missing_evidence(findings, run_dir)
```

  This ensures a crop from an earlier run never renders under a different run's dashboard; the finding itself is always kept, only missing evidence refs are dropped.
- [ ] Run the same command — expect PASS.
- [ ] In `dashboard/serve.py`, confirm (read the `/run/` route handler) that it already refuses any path resolving outside the served run dir (a `run_root in candidate.parents`-shaped guard); if it does not, add a `Path.resolve()` + `is_relative_to(run_dir.resolve())` guard returning 403 on violation, with a test in `dashboard/test_serve.py` requesting `/run/../../etc/passwd`-style traversal and asserting a non-200 response.
- [ ] In `dashboard/page/app.js`, confirm `_assetUrl` (or the equivalent evidence-URL builder) prefixes `/run/` only for entries that are relative run paths (not already-absolute URLs) — if it already does this correctly, no change needed; otherwise fix it to match this rule.
- [ ] Row 23 (E1): in `dashboard/test_serve.py`, find the plain-object `_FakeEntry` used by the triage-post test and turn it into a real `@dataclasses.dataclass` (`id: str`, `state: str`, `reason: str | None = None`, matching whatever fields the real triage response reads); then in `dashboard/serve.py`, replace `finding = dataclasses.asdict(entry) if dataclasses.is_dataclass(entry) else vars(entry)` with `finding = dataclasses.asdict(entry)`. Run `python -m pytest -q plugins/flow-review/engine/flow_review/dashboard/test_serve.py` — expect PASS.
- [ ] Row 22 (E2): add a regression test to `dashboard/test_static.py`:

```python
def test_static_module_has_no_placeholder_or_fake_asset_fallback():
    import flow_review.dashboard.static as static_mod
    from pathlib import Path
    src = Path(static_mod.__file__).read_text(encoding="utf-8").lower()
    assert "placeholder" not in src
    assert "fake" not in src
```

  Run it; if it fails because a fallback branch still exists in `static.py`, remove that branch (real page assets already ship, per the row's own note) and rerun until PASS; if it already passes (no fallback present today), say so explicitly in the commit message — the task's job here is only to add the regression test.
- [ ] Row 20 (CP2 utf-8 write untested): add a test to `dashboard/test_static.py` that renders the static dashboard with a finding whose `text` contains non-ASCII characters, then reads the output file back with strict `bytes.decode("utf-8")` and asserts the non-ASCII substrings survive the round trip — this locks in `static.py`'s existing `Path.write_text(html, encoding="utf-8")` call against real non-ASCII input (no production code change expected unless the test actually fails).
- [ ] Write failing test — create `plugins/flow-review/engine/flow_review/test_repo_hygiene.py`:

```python
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]  # plugins/flow-review (test file is at
                                              # plugins/flow-review/engine/flow_review/test_repo_hygiene.py)


def test_no_inline_python_dash_c_in_skills_or_agents_or_readme():
    targets = [
        _ROOT / "skills",
        _ROOT / "agents",
        _ROOT / "README.md",
    ]
    offenders = []
    for target in targets:
        if not target.exists():
            continue
        files = [target] if target.is_file() else list(target.rglob("*"))
        for path in files:
            if path.is_dir():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue
            if "python -c" in text or "python3 -c" in text:
                offenders.append(str(path))
    assert offenders == [], f"inline python -c found in: {offenders}"
```

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/test_repo_hygiene.py` — expect either immediate PASS (if no `python -c` calls exist today, in which case this task's job is only to add the regression test — say so explicitly) or FAIL listing offending files.
- [ ] If it fails, replace each offending inline `python -c "..."` snippet in the skill/agent/doc files with the equivalent existing CLI verb (e.g. `flow-review run new` instead of a `python -c` one-liner computing a run id) or a committed helper script referenced by path; re-run until the test passes.
- [ ] Run `python -m pytest -q -m "web or not web"` — expect PASS, no regression.
- [ ] Verify: `python -m pytest -q -m "web or not web"`
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/dashboard/state.py plugins/flow-review/engine/flow_review/dashboard/test_state.py plugins/flow-review/engine/flow_review/dashboard/serve.py plugins/flow-review/engine/flow_review/dashboard/page/app.js plugins/flow-review/engine/flow_review/test_repo_hygiene.py plugins/flow-review/skills/flow-review/SKILL.md plugins/flow-review/agents README.md && git commit -m "fix(dashboard): evidence fold checks file existence against current run dir; no inline python -c left (A-44)"`

### Task T4: Config + detection

**Executor:** sonnet · **Depends:** T1, T2 · **Wave:** 3
**Files:** `plugins/flow-review/engine/flow_review/config.py`, `plugins/flow-review/engine/flow_review/test_config.py`, `plugins/flow-review/engine/flow_review/audit.py`, `plugins/flow-review/engine/flow_review/test_audit.py`, `plugins/flow-review/engine/flow_review/drift.py`, `plugins/flow-review/engine/flow_review/test_drift.py`, `plugins/flow-review/engine/flow_review/migrate.py`, `plugins/flow-review/engine/flow_review/test_migrate.py`
**Interfaces:** Consumes: `config.VALID_DRIVERS`, `config._validate_options`, `audit._from_tauri`. Produces: driver `tauri`, `TAURI_OPTION_KEYS`, `RUNNABLE_DRIVERS`.
**Ponytail rung:** 5 (one line additions to existing tuples/dispatch).

- [ ] Write failing test — append to `plugins/flow-review/engine/flow_review/test_config.py`:

```python
def test_tauri_driver_is_valid_with_its_option_keys():
    from flow_review import config
    surface = config.Surface(
        id="desktop", name="Desktop", kind="ui", driver="tauri", launch="",
        options={"dev_url": "http://localhost:1420", "mocks_file": ".flow-review/tauri-mocks.json",
                 "binary": "src-tauri/target/release/app.exe", "native": "webview2"},
    )
    config._validate_surface(surface)  # must not raise


def test_tauri_driver_rejects_unknown_option_key():
    from flow_review import config
    surface = config.Surface(
        id="desktop", name="Desktop", kind="ui", driver="tauri", launch="",
        options={"bogus": True},
    )
    try:
        config._validate_surface(surface)
        assert False, "expected ConfigKeyError"
    except config.ConfigKeyError:
        pass
```

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/test_config.py -k tauri` — expect FAIL: `driver 'tauri' unknown` (ValueError) since `tauri` is not yet in `VALID_DRIVERS`.
- [ ] Implement in `config.py`:
  1. Change `VALID_DRIVERS = ("cdp", "playwright", "adb", "ios-sim", "shell", "http", "custom", "pending")` to add `"tauri"`: `VALID_DRIVERS = ("cdp", "playwright", "tauri", "adb", "ios-sim", "shell", "http", "custom", "pending")`.
  2. Add near `WEB_OPTION_KEYS`:
     ```python
     TAURI_OPTION_KEYS = ("dev_url", "mocks_file", "binary", "native")
     ```
     `RUNNABLE_DRIVERS` does NOT live in `config.py` — it lives in `drift.py`, next to `runnable_surfaces` and its existing `_PENDING_DRIVER` constant, since that is the only module that reads it (see the `drift.py` step below).
  3. Replace `_validate_options` with a dispatch by driver:
     ```python
     def _validate_options(surface: Surface) -> None:
         where = f"surfaces[{surface.id!r}].options"
         if surface.driver == "playwright":
             _check_keys(surface.options, set(WEB_OPTION_KEYS), where)
         elif surface.driver == "tauri":
             _check_keys(surface.options, set(TAURI_OPTION_KEYS), where)
         elif surface.options:
             _check_keys(surface.options, set(), where)
     ```
- [ ] Run the same command — expect PASS.
- [ ] Write failing test — append to `plugins/flow-review/engine/flow_review/test_audit.py`:

```python
def test_from_tauri_promotes_to_tauri_driver(tmp_path):
    from flow_review.audit import _from_tauri
    src_tauri = tmp_path / "src-tauri"
    src_tauri.mkdir()
    (src_tauri / "tauri.conf.json").write_text(
        '{"productName": "app", "build": {"devUrl": "http://localhost:1420"}}', encoding="utf-8"
    )
    candidates = _from_tauri(tmp_path)
    assert len(candidates) == 1
    assert candidates[0].driver == "tauri"
```

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/test_audit.py -k from_tauri` — expect FAIL: today `_from_tauri` returns `driver="pending"` always.
- [ ] Implement — replace `_from_tauri` in `audit.py`:

```python
import json as _json
import platform as _platform


def _from_tauri(root: Path) -> list[Candidate]:
    src_tauri = root / "src-tauri"
    if not src_tauri.is_dir():
        return []
    conf_path = src_tauri / "tauri.conf.json"
    dev_url = None
    product_name = "app"
    if conf_path.is_file():
        try:
            conf = _json.loads(conf_path.read_text(encoding="utf-8"))
        except ValueError:
            conf = {}
        dev_url = conf.get("build", {}).get("devUrl")
        product_name = conf.get("productName", product_name)
    native = "webview2" if _platform.system() == "Windows" else "pending"
    options = {"native": native}
    if dev_url:
        options["dev_url"] = dev_url
        options["binary"] = f"src-tauri/target/release/{product_name}.exe"
        driver = "tauri"
    else:
        driver = "pending"  # no dev server configured yet -- nothing runnable to point at
    evidence = _evidence(conf_path, root, None, "") if conf_path.is_file() else _evidence(src_tauri, root, None, "")
    return [Candidate(name="desktop", kind="ui", driver=driver, launch="", evidence=evidence, options=options)]
```

  If `Candidate` has no `options` field today, add one (`options: dict = field(default_factory=dict)`) at its dataclass definition, and confirm the caller that turns a `Candidate` into a `Surface` copies `options` through — read that call site (grep `Candidate(` in `audit.py`) before assuming the field doesn't already exist.

- [ ] Run the same command — expect PASS.
- [ ] Write failing test — append to `plugins/flow-review/engine/flow_review/test_drift.py`:

```python
def test_runnable_surfaces_includes_tauri_but_excludes_cdp_adb_ios_sim_custom():
    from flow_review import config, drift
    surfaces = [
        config.Surface(id="a", name="A", kind="ui", driver="tauri", launch=""),
        config.Surface(id="b", name="B", kind="ui", driver="playwright", launch=""),
        config.Surface(id="c", name="C", kind="ui", driver="cdp", launch=""),
        config.Surface(id="d", name="D", kind="ui", driver="adb", launch=""),
        config.Surface(id="e", name="E", kind="ui", driver="ios-sim", launch=""),
        config.Surface(id="f", name="F", kind="ui", driver="custom", launch=""),
        config.Surface(id="g", name="G", kind="ui", driver="pending", launch=""),
        config.Surface(id="h", name="H", kind="ui", driver="tauri", launch="", declined=True),
    ]
    cfg = config.Config(schema_version=2, generator_version="t", surfaces=surfaces)
    runnable_ids = [s.id for s in drift.runnable_surfaces(cfg)]
    assert runnable_ids == ["a", "b"]
```

  Note (IMPORTANT #5, orchestrator convention): `cdp`, `adb`, `ios-sim`, and `custom` never had an engine driver behind them (A-14) and are demoted to non-runnable here alongside `pending` — they remain valid `VALID_DRIVERS` values (a user's config may still name one; `_validate_surface` still accepts it) but `runnable_surfaces` now excludes them the same way it already excludes `pending` and `declined`. This is a drafter convention, not a re-litigation of A-45; flag at review if any of those four should stay runnable for a reason this plan doesn't know about.
- [ ] Run it — expect FAIL: today's `runnable_surfaces` only excludes `declined` and the literal `"pending"` driver, so `c`/`d`/`e`/`f` (cdp/adb/ios-sim/custom) are wrongly included and `a` (tauri, not yet in any allowlist) has no allowlist to be excluded from — the assertion on the exact `["a", "b"]` list fails either way.
- [ ] Implement in `drift.py`, near the existing `_PENDING_DRIVER` constant:

```python
RUNNABLE_DRIVERS = ("playwright", "tauri", "maestro", "http", "shell")
```

  and replace:
  ```python
  def runnable_surfaces(cfg: Config) -> list[Surface]:
      return [s for s in cfg.surfaces if not s.declined and s.driver != _PENDING_DRIVER]
  ```
  with:
  ```python
  def runnable_surfaces(cfg: Config) -> list[Surface]:
      return [s for s in cfg.surfaces if not s.declined and s.driver in RUNNABLE_DRIVERS]
  ```
  (`runnable_surfaces` keeps its existing `Config` argument and return-type signature unchanged — only its body changes from a deny-list to an allow-list. `_PENDING_DRIVER` stays defined for any other reader that still checks for the literal `"pending"` string.)
- [ ] Run the same command — expect PASS.
- [ ] Write failing test — append to `plugins/flow-review/engine/flow_review/test_migrate.py`:

```python
def test_migrate_keeps_pending_driver_unchanged():
    from flow_review import migrate
    old = {"schema_version": 1, "surfaces": [{"id": "desktop", "driver": "pending", "name": "Desktop", "kind": "ui", "launch": ""}]}
    new = migrate.migrate(old)
    surface = next(s for s in new["surfaces"] if s["id"] == "desktop")
    assert surface["driver"] == "pending"
```

  (Adapt the call to `migrate.migrate`'s real signature — read `migrate.py` first.)

- [ ] Run it — expect PASS immediately if migrate already passes `driver` through untouched (most likely); if it fails, fix `migrate.py` to leave a `pending` driver as-is (never rewrite it to `tauri` automatically — detection re-runs and does that promotion on the next `audit`).
- [ ] Run `python -m pytest -q -m "web or not web"` — expect PASS, no regression.
- [ ] Verify: `python -m pytest -q -m "web or not web"`
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/config.py plugins/flow-review/engine/flow_review/test_config.py plugins/flow-review/engine/flow_review/audit.py plugins/flow-review/engine/flow_review/test_audit.py plugins/flow-review/engine/flow_review/drift.py plugins/flow-review/engine/flow_review/test_drift.py plugins/flow-review/engine/flow_review/migrate.py plugins/flow-review/engine/flow_review/test_migrate.py && git commit -m "feat(config): add tauri driver, TAURI_OPTION_KEYS, RUNNABLE_DRIVERS; audit promotes src-tauri to tauri driver"`

### Task T5: Tauri fixture app

**Executor:** haiku · **Depends:** — · **Wave:** 1
**Files:** `plugins/flow-review/engine/fixtures/tauriapp/**` (new directory), `plugins/flow-review/engine/flow_review/test_fixtures_tauriapp.py` (new)
**Interfaces:** Consumes: `plugins/flow-review/engine/fixtures/webapp/**` (read-only, do not modify). Produces: `fixtures/tauriapp/` fixture used by T7/T8/CP1.
**Ponytail rung:** 6 (minimum code: wrap the existing webapp fixture, no new frontend).

- [ ] Read `plugins/flow-review/engine/fixtures/webapp/` to see its existing structure (package.json, dev server port, index.html) so the Tauri shell points at it rather than duplicating it.
- [ ] Write failing test — create `plugins/flow-review/engine/flow_review/test_fixtures_tauriapp.py`:

```python
import re
from pathlib import Path

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "tauriapp"


def test_tauriapp_fixture_files_exist():
    assert (_FIXTURE / "src-tauri" / "Cargo.toml").is_file()
    assert (_FIXTURE / "src-tauri" / "tauri.conf.json").is_file()
    assert (_FIXTURE / "src-tauri" / "src" / "main.rs").is_file()
    assert (_FIXTURE / "src-tauri" / "src" / "commands.rs").is_file()
    assert (_FIXTURE / "README.md").is_file()
    assert (_FIXTURE / "planted.json").is_file()


def test_tauriapp_commands_parse_as_tauri_command_fns():
    text = (_FIXTURE / "src-tauri" / "src" / "commands.rs").read_text(encoding="utf-8")
    names = re.findall(r"#\[tauri::command\]\s*\n\s*(?:pub\s+)?fn\s+(\w+)", text)
    assert set(names) == {"load_items", "save_note"}


def test_tauriapp_planted_json_documents_the_swallowed_error():
    import json
    planted = json.loads((_FIXTURE / "planted.json").read_text(encoding="utf-8"))
    assert any(entry.get("rule") == "console.error" for entry in planted)
```

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/test_fixtures_tauriapp.py` — expect FAIL: fixture directory does not exist yet.
- [ ] Implement — create the fixture files:

  `plugins/flow-review/engine/fixtures/tauriapp/src-tauri/Cargo.toml`:
  ```toml
  [package]
  name = "tauriapp"
  version = "0.1.0"
  edition = "2021"

  [build-dependencies]
  tauri-build = { version = "2", features = [] }

  [dependencies]
  tauri = { version = "2", features = [] }
  serde = { version = "1", features = ["derive"] }
  serde_json = "1"
  ```

  `plugins/flow-review/engine/fixtures/tauriapp/src-tauri/build.rs`:
  ```rust
  fn main() {
      tauri_build::build()
  }
  ```

  `plugins/flow-review/engine/fixtures/tauriapp/src-tauri/tauri.conf.json`:
  ```json
  {
    "productName": "tauriapp",
    "version": "0.1.0",
    "identifier": "com.flowreview.tauriapp",
    "build": {
      "devUrl": "http://127.0.0.1:1421",
      "beforeDevCommand": "python -m http.server 1421 --directory src",
      "frontendDist": "../src"
    },
    "app": {
      "windows": [{ "title": "tauriapp", "width": 1024, "height": 768 }]
    },
    "bundle": {
      "icon": ["icons/icon.png"]
    }
  }
  ```

  This fixture serves its frontend as plain static files (`src/index.html`, `src/app.js`) with no build step, so `frontendDist` points at `../src` directly and `beforeDevCommand` starts a stdlib static file server on the same port `dev_url` uses — no `npm install`/bundler dependency for the frontend half of this fixture.

  `plugins/flow-review/engine/fixtures/tauriapp/src/index.html`:
  ```html
  <!doctype html>
  <html lang="en">
  <head>
    <meta charset="utf-8">
    <title>tauriapp fixture</title>
  </head>
  <body>
    <h1>tauriapp fixture</h1>
    <button id="load-items">Load items</button>
    <ul id="items"></ul>
    <input id="note-text" type="text" placeholder="note">
    <button id="save-note-button">Save note</button>
    <script src="app.js"></script>
  </body>
  </html>
  ```

  `plugins/flow-review/engine/fixtures/tauriapp/src/app.js`:
  ```javascript
  async function loadItems() {
    const items = await window.__TAURI_INTERNALS__.invoke('load_items', {});
    const list = document.getElementById('items');
    list.innerHTML = '';
    (items || []).forEach((item) => {
      const li = document.createElement('li');
      li.textContent = item.label;
      list.appendChild(li);
    });
  }

  async function saveNote() {
    const text = document.getElementById('note-text').value;
    try {
      await window.__TAURI_INTERNALS__.invoke('save_note', { text });
      // Planted bug (A-36): a successful save is never distinguished from a swallowed
      // failure in the UI either -- there is no success feedback path here on purpose,
      // matching the "no UI feedback" bug this fixture exists to expose.
    } catch (err) {
      // Planted bug (A-36): the rejection is swallowed into console.error with no UI
      // feedback -- the user sees nothing happen when save_note fails server-side.
      console.error(err);
    }
  }

  document.getElementById('load-items').addEventListener('click', loadItems);
  document.getElementById('save-note-button').addEventListener('click', saveNote);
  ```

  `plugins/flow-review/engine/fixtures/tauriapp/src-tauri/src/commands.rs`:
  ```rust
  use serde::Serialize;

  #[derive(Serialize)]
  pub struct Item {
      pub id: u32,
      pub label: String,
  }

  #[tauri::command]
  pub fn load_items() -> Vec<Item> {
      vec![
          Item { id: 1, label: "First item".into() },
          Item { id: 2, label: "Second item".into() },
      ]
  }

  // Planted bug (A-36): save_note always fails server-side. The frontend swallows the
  // rejection into console.error with no UI feedback -- the user sees nothing happen.
  #[tauri::command]
  pub fn save_note(_text: String) -> Result<(), String> {
      Err("note store unavailable".into())
  }
  ```

  `plugins/flow-review/engine/fixtures/tauriapp/src-tauri/src/main.rs`:
  ```rust
  #![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

  mod commands;

  fn main() {
      tauri::Builder::default()
          .invoke_handler(tauri::generate_handler![commands::load_items, commands::save_note])
          .run(tauri::generate_context!())
          .expect("error while running tauri application");
  }
  ```

  `plugins/flow-review/engine/fixtures/tauriapp/README.md`:
  ```markdown
  # tauriapp fixture

  A minimal Tauri v2 app with its own plain-static frontend (`src/index.html`, `src/app.js` --
  no build step, no `npm install`), used by the M2 plan's tasks T7/T8 and checkpoint CP1. Two
  `#[tauri::command]`s: `load_items` (works) and `save_note` (planted bug -- always returns
  `Err`, and the frontend swallows the rejection into `console.error` with no UI feedback). Dev
  server: `http://127.0.0.1:1421` (see `src-tauri/tauri.conf.json` `build.devUrl` /
  `beforeDevCommand`, which starts a stdlib `python -m http.server` on the same port). Build the
  native binary with `cargo tauri build` from this directory once the `tauri-cli` is installed
  (`cargo install tauri-cli --version "^2"`). The bundle icon at `src-tauri/icons/icon.png` is a
  placeholder 32x32 PNG generated by this fixture's own pytest; replace it with a real logo via
  `cargo tauri icon <source.png>` if this fixture is ever used outside test/CI contexts.
  ```

  `plugins/flow-review/engine/fixtures/tauriapp/planted.json`:
  ```json
  [
    {"rule": "console.error", "route": "/", "locator": "#save-note-button"}
  ]
  ```

- [ ] Generate the bundle icon the same test writes: append to `plugins/flow-review/engine/flow_review/test_fixtures_tauriapp.py`:

```python
def test_tauriapp_icon_exists_and_is_a_valid_png():
    from PIL import Image
    icon_path = _FIXTURE / "src-tauri" / "icons" / "icon.png"
    if not icon_path.is_file():
        icon_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (32, 32), (90, 110, 160, 255)).save(icon_path)
    with Image.open(icon_path) as img:
        assert img.size == (32, 32)
```

  (This test both documents the icon requirement and generates a real 32x32 PNG the first time it runs, so `cargo tauri build` never fails on a missing icon; a maintainer may later replace it with a real logo via `cargo tauri icon <source.png>`, which is the documented long-term path — noted in the fixture's README below.)
- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/test_fixtures_tauriapp.py` — expect the new icon test to create `src-tauri/icons/icon.png` and pass, and the rest of the suite to PASS.
- [ ] Run `python -m pytest -q -m "web or not web"` — expect PASS, no regression.
- [ ] Verify: `python -m pytest -q -m "web or not web"`
- [ ] Commit: `git add plugins/flow-review/engine/fixtures/tauriapp plugins/flow-review/engine/flow_review/test_fixtures_tauriapp.py && git commit -m "test(fixtures): add tauriapp fixture with planted save_note error (A-36)"`

### Task T6: Invoke mocks

**Executor:** sonnet · **Depends:** T1 · **Wave:** 3
**Files:** `plugins/flow-review/engine/flow_review/tauri/__init__.py` (new), `plugins/flow-review/engine/flow_review/tauri/mocks.py` (new), `plugins/flow-review/engine/flow_review/tauri/test_mocks.py` (new), `plugins/flow-review/engine/flow_review/cli.py`
**Interfaces:** Consumes: none. Produces: `tauri/mocks.py::scan_commands`, `write_stubs`, `init_script`; `flow-review tauri mocks --project P` CLI verb.
**Ponytail rung:** 2 (stdlib `re`/`json`, no dependency).

- [ ] Write failing test — create `plugins/flow-review/engine/flow_review/tauri/test_mocks.py`:

```python
import json
from pathlib import Path


def test_scan_commands_finds_tauri_command_fns(tmp_path):
    from flow_review.tauri.mocks import scan_commands
    src_tauri = tmp_path / "src-tauri"
    (src_tauri / "src").mkdir(parents=True)
    (src_tauri / "src" / "commands.rs").write_text(
        "#[tauri::command]\nfn load_items() -> Vec<Item> { vec![] }\n\n"
        "#[tauri::command]\npub fn save_note(text: String) -> Result<(), String> { Ok(()) }\n",
        encoding="utf-8",
    )
    assert sorted(scan_commands(src_tauri)) == ["load_items", "save_note"]


def test_write_stubs_never_overwrites_a_filled_value(tmp_path):
    from flow_review.tauri.mocks import write_stubs
    path = tmp_path / "tauri-mocks.json"
    path.write_text(json.dumps({"save_note": {"ok": True}}), encoding="utf-8")
    added = write_stubs(path, ["load_items", "save_note"])
    data = json.loads(path.read_text(encoding="utf-8"))
    assert added == 1
    assert data["load_items"] is None
    assert data["save_note"] == {"ok": True}


def test_init_script_shape_matches_mock_ipc():
    from flow_review.tauri.mocks import init_script
    script = init_script({"load_items": [{"id": 1}]})
    assert "__TAURI_INTERNALS__" in script
    assert "invoke" in script
    assert "load_items" in script
```

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/tauri/test_mocks.py` — expect FAIL: `ModuleNotFoundError: No module named 'flow_review.tauri'`.
- [ ] Implement — create `plugins/flow-review/engine/flow_review/tauri/__init__.py` (empty file) and `plugins/flow-review/engine/flow_review/tauri/mocks.py`:

```python
"""Invoke mocks for a Tauri surface (A-37). The engine only writes stubs it can discover from
the Rust source; a human or the setup agent fills plausible responses. An unfilled command
resolves to null at runtime and drive.py files a not-exercised status once per flow."""
from __future__ import annotations

import json
import re
from pathlib import Path

_COMMAND_FN = re.compile(r"#\[tauri::command\]\s*\n\s*(?:pub\s+)?fn\s+(\w+)")


def scan_commands(src_tauri: Path) -> list[str]:
    names: list[str] = []
    for rs_file in sorted(src_tauri.rglob("*.rs")):
        text = rs_file.read_text(encoding="utf-8")
        for match in _COMMAND_FN.finditer(text):
            name = match.group(1)
            if name not in names:
                names.append(name)
    return names


def write_stubs(path: Path, commands: list[str]) -> int:
    existing: dict = {}
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
    added = 0
    for command in commands:
        if command not in existing:
            existing[command] = None
            added += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, indent=2, sort_keys=True), encoding="utf-8")
    return added


def init_script(mocks: dict) -> str:
    payload = json.dumps(mocks)
    return (
        "window.__TAURI_INTERNALS__ = {\n"
        f"  invoke: (cmd, args) => Promise.resolve(({payload})[cmd] ?? null),\n"
        "  transformCallback: (callback) => callback,\n"
        "  convertFileSrc: (path) => path,\n"
        "};"
    )
```

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/tauri/test_mocks.py` — expect PASS.
- [ ] Add CLI verb: in `cli.py`, add `tauri mocks --project P` that resolves `<project>/src-tauri`, calls `scan_commands`, then `write_stubs(<project>/.flow-review/tauri-mocks.json, commands)`, and prints `json.dumps({"added": added, "path": str(mocks_path)})` to stdout, exit 0 (exit 1 with a clear stderr message if `<project>/src-tauri` does not exist). Register it in the verb-dispatch table.
- [ ] Write failing test — append a CLI-level test to `plugins/flow-review/engine/flow_review/test_cli.py` (or the file that already tests other `cli.py` verbs — match its subprocess/argv-invocation pattern):

```python
def test_tauri_mocks_cli_writes_stub_file(tmp_path, capsys):
    from flow_review import cli
    src_tauri = tmp_path / "src-tauri" / "src"
    src_tauri.mkdir(parents=True)
    (src_tauri / "commands.rs").write_text(
        "#[tauri::command]\nfn load_items() {}\n", encoding="utf-8"
    )
    code = cli.main(["tauri", "mocks", "--project", str(tmp_path)])
    assert code == 0
    mocks_path = tmp_path / ".flow-review" / "tauri-mocks.json"
    assert mocks_path.is_file()
```

  (There is no `run_cli` fixture anywhere in this codebase; every existing CLI test calls `cli.main([...])` directly and reads output via the `capsys` pytest fixture — do the same here, matching `test_main_with_no_args_prints_usage_and_exits_nonzero`'s pattern at the top of `test_cli.py`.)

- [ ] Run it — expect FAIL, then implement/wire until PASS.
- [ ] Run `python -m pytest -q -m "web or not web"` — expect PASS, no regression.
- [ ] Verify: `python -m pytest -q -m "web or not web"`
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/tauri plugins/flow-review/engine/flow_review/cli.py plugins/flow-review/engine/flow_review/test_cli.py && git commit -m "feat(tauri): scan_commands/write_stubs/init_script and 'tauri mocks' CLI verb (A-37)"`

### Task T7: Web-first drive

**Executor:** opus · **Depends:** T4, T6 · **Wave:** 4
**Files:** `plugins/flow-review/engine/flow_review/web/drive.py`, `plugins/flow-review/engine/flow_review/web/test_drive.py`, `plugins/flow-review/engine/flow_review/web/driver.py`, `plugins/flow-review/engine/flow_review/web/test_driver.py`, `plugins/flow-review/engine/flow_review/web/replay.py`, `plugins/flow-review/engine/flow_review/tauri/mocks.py`
**Interfaces:** Consumes: `tauri.mocks.init_script`, `config.TAURI_OPTION_KEYS`, `web.driver.WebDriver`. Produces: `DRIVER_FACTORIES` dict, `WebDriver.__init__(..., init_script=...)`, tauri dev-server proving, mock-missing `not-exercised` status event.
**Ponytail rung:** 6 (minimum code: reuse `WebDriver` unchanged per A-47, no new driver class).

- [ ] CRITICAL fix locked in by this task: `WebDriver.page` is `None` until `launch()` runs (see `web/driver.py::__init__`/`launch`), so a factory cannot call `driver.page.add_init_script(...)` before `launch()` the way an earlier draft of this plan assumed. The init script must be threaded through the constructor and applied inside `launch()`, right after `self.page` is created.
- [ ] Write failing test — append to `plugins/flow-review/engine/flow_review/web/test_driver.py`:

```python
def test_webdriver_applies_init_script_after_page_is_created(monkeypatch):
    from flow_review.web import driver as driver_mod

    calls = {}

    class FakePage:
        def add_init_script(self, script):
            calls["script"] = script
        def on(self, *a, **k):
            pass

    class FakeBrowser:
        def new_page(self, **kwargs):
            return FakePage()
        def close(self):
            pass

    class FakeChromium:
        def launch(self, headless):
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()
        def stop(self):
            pass

    monkeypatch.setattr(driver_mod, "sync_playwright", lambda: _StartCtx(FakePlaywright()))
    d = driver_mod.WebDriver(headless=True, init_script="window.__MARK__ = 1;")
    assert d.page is None  # page does not exist before launch()
    d.launch("http://fake/")
    assert calls["script"] == "window.__MARK__ = 1;"


class _StartCtx:
    def __init__(self, pw):
        self._pw = pw
    def start(self):
        return self._pw
```

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/web/test_driver.py -k init_script` — expect FAIL: `TypeError: __init__() got an unexpected keyword argument 'init_script'`.
- [ ] Implement in `web/driver.py`: add `init_script: str | None = None` to `WebDriver.__init__`'s parameter list, store it as `self.init_script = init_script`, and in `launch()`, immediately after `self.page = self.browser.new_page(**page_kwargs)` and before the `self.page.on(...)` calls, add:

```python
        if self.init_script is not None:
            self.page.add_init_script(self.init_script)
```

- [ ] Run the same command — expect PASS.
- [ ] Write failing test — append to `plugins/flow-review/engine/flow_review/web/test_drive.py`, reusing this file's own `FakeDriver` (which pre-sets `self.page = FakePage()` in `__init__` — for these two tests a fresh fake that leaves `page` as `None` until `launch()` is used instead, matching the real `WebDriver` contract):

```python
def test_driver_factories_dict_has_tauri_entry():
    from flow_review.web.drive import DRIVER_FACTORIES
    assert "playwright" in DRIVER_FACTORIES
    assert "tauri" in DRIVER_FACTORIES


class _LazyPageFakeDriver:
    """Unlike this file's shared FakeDriver, page is None until launch() -- matching the real
    WebDriver contract that made the CRITICAL init_script fix above necessary."""
    def __init__(self, headless=True, viewport=None, init_script=None):
        self.headless = headless
        self.viewport = viewport
        self.init_script = init_script
        self.page = None
        self.launched_url = None

    def launch(self, base_url):
        self.launched_url = base_url
        self.page = FakePage()
        if self.init_script is not None:
            self.page.applied_init_script = self.init_script


def test_tauri_driver_factory_passes_init_script_to_webdriver(monkeypatch, tmp_path):
    from flow_review.web import drive
    mocks_file = tmp_path / "tauri-mocks.json"
    mocks_file.write_text('{"load_items": [{"id": 1}]}', encoding="utf-8")
    monkeypatch.setattr(drive, "WebDriver", _LazyPageFakeDriver)
    options = {"dev_url": "http://127.0.0.1:1421", "mocks_file": str(mocks_file)}
    d = drive.DRIVER_FACTORIES["tauri"](headless=True, viewport=None, options=options)
    d.launch(options["dev_url"])
    assert "load_items" in d.page.applied_init_script
    assert d.launched_url == "http://127.0.0.1:1421"
```

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/web/test_drive.py -k tauri_driver_factory` — expect FAIL: `AttributeError: module 'flow_review.web.drive' has no attribute 'DRIVER_FACTORIES'`.
- [ ] Implement in `web/drive.py` (add `import json` and `from pathlib import Path` at the top if not already imported):

```python
def _load_tauri_mocks(mocks_path_str: str) -> dict:
    mocks_path = Path(mocks_path_str)
    if not mocks_path.is_file():
        return {}
    return json.loads(mocks_path.read_text(encoding="utf-8"))


def _tauri_driver_factory(headless: bool, viewport: dict | None, options: dict | None = None):
    from flow_review.web.driver import WebDriver
    from flow_review.tauri.mocks import init_script
    options = options or {}
    mocks = _load_tauri_mocks(options.get("mocks_file", ".flow-review/tauri-mocks.json"))
    return WebDriver(headless=headless, viewport=viewport, init_script=init_script(mocks))


DRIVER_FACTORIES = {
    "playwright": lambda headless, viewport, options=None: _default_driver_factory(headless, viewport),
    "tauri": _tauri_driver_factory,
}
```

- [ ] Find the code path in `cmd_start` (or wherever the session's driver is built) that currently always calls `_default_driver_factory(headless, viewport)`, and change it to `DRIVER_FACTORIES[surface.driver](headless, viewport, options=surface.options)`.
- [ ] Before launching for a `tauri` surface, prove the dev server is reachable: attempt `urllib.request.urlopen(options["dev_url"], timeout=2)` (no `health_path` for tauri — a tauri surface's dev server always answers at `/`, since it is the app's own root, unlike a general web surface which may put its health check elsewhere; `TAURI_OPTION_KEYS` accordingly has no `health_path` entry); on failure raise `RuntimeError(f"tauri dev server not reachable at {options['dev_url']}; start it first")` that `cmd_start` surfaces as a clean CLI error (exit non-zero), not a traceback.
- [ ] Write failing test — append to `plugins/flow-review/engine/flow_review/web/test_drive.py`:

```python
def test_note_mock_invocation_fires_once_per_command_per_flow(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    project_root = tmp_path / "project"
    (project_root / ".flow-review").mkdir(parents=True)
    session = DriveSession(FakeDriver(), "desktop", run_dir, project_root, False)
    session.cmd_flow_begin("flow-1")
    session._note_mock_invocation("save_note")
    session._note_mock_invocation("save_note")
    session._note_mock_invocation("load_items")
    lines = (run_dir / "events.jsonl").read_text(encoding="utf-8").strip().splitlines()
    statuses = [json.loads(l) for l in lines if json.loads(l).get("type") == "status"]
    assert len(statuses) == 2
    assert all(s["reason"] == "mock-missing" for s in statuses)
```

- [ ] Run it — expect FAIL: `AttributeError: 'DriveSession' object has no attribute '_note_mock_invocation'`.
- [ ] Implement on `DriveSession`: add `self._mock_missing_warned: set[tuple[str, str | None]] = set()` in `__init__`, and:

```python
    def _note_mock_invocation(self, command: str) -> None:
        key = (command, self.flow_id)
        if key in self._mock_missing_warned:
            return
        self._mock_missing_warned.add(key)
        events.append(self.run_dir, {
            "type": "status", "state": "not-exercised", "surface_id": self.surface_id,
            "flow_id": self.flow_id, "step": command, "reason": "mock-missing",
        })
```

  (Use `self.flow_id`/`self.surface_id`/`self.run_dir` under whatever exact attribute names `DriveSession.__init__` already assigns — read the constructor first and match them; `events.append(run_dir, payload)` is the existing event-write helper used elsewhere in this file.) Wiring the JS-side detection of a `null`-valued mock invocation back into a call to `_note_mock_invocation` (via `driver.page.expose_function` + `page.evaluate`) is real work belonging to the browser-integration half of this task; keep it scoped to a single call after each drive action inside `_result()`: `if hasattr(self.driver, "page") and self.driver.page is not None: self.driver.page.evaluate("window.__flowReviewMissingMocks || []")` — for the unit tests above, `_note_mock_invocation` itself is what's tested; the `_result()` wiring is exercised indirectly by CP1's end-to-end run.
- [ ] Update `tauri/mocks.py::init_script` (this changes T6's version) so the mocked `invoke` tracks a missing command for later polling:

```python
def init_script(mocks: dict) -> str:
    payload = json.dumps(mocks)
    return (
        "window.__flowReviewMissingMocks = [];\n"
        "window.__TAURI_INTERNALS__ = {\n"
        f"  invoke: (cmd, args) => {{\n"
        f"    const mocks = {payload};\n"
        "    const has = Object.prototype.hasOwnProperty.call(mocks, cmd);\n"
        "    const value = has ? mocks[cmd] : null;\n"
        "    if (has && value === null) { window.__flowReviewMissingMocks.push(cmd); }\n"
        "    return Promise.resolve(value);\n"
        "  },\n"
        "  transformCallback: (callback) => callback,\n"
        "  convertFileSrc: (path) => path,\n"
        "};"
    )
```

  Existing `tauri/test_mocks.py` assertions only check substrings (`"__TAURI_INTERNALS__" in script`, `"invoke" in script`), so no change needed there.
- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/web/test_drive.py plugins/flow-review/engine/flow_review/web/test_driver.py plugins/flow-review/engine/flow_review/tauri/test_mocks.py` — expect PASS.
- [ ] In `web/replay.py`, route replay's own driver construction through the same factory dict so a tauri replay also gets the mocks installed (today it likely calls `_default_driver_factory`/constructs `WebDriver` directly): find replay's driver-launch call site (grep `WebDriver(` and `_launch_driver`/`_default_driver_factory` in `replay.py`) and change it to `drive.DRIVER_FACTORIES[surface.driver](headless=True, viewport=None, options=surface.options)` followed by `.launch(surface.options.get("dev_url") or surface.options.get("base_url"))`. Since replay does not go through `cmd_start`, `surface.options["mocks_file"]` must already be an absolute path by the time it reaches the factory — `cmd_start` is responsible for resolving a relative `mocks_file` against `project_root` before writing it into the `Surface.options` dict it hands to `DriveSession`/replay, so `_tauri_driver_factory` itself never needs `project_root`. Add `from flow_review.web import drive` to `replay.py`'s imports if not already present (guard against a circular import: `drive.py` does not import `replay.py`, so this direction is safe).
- [ ] Write a smoke test in `test_replay.py` (find its real name/location) replaying a tiny recorded flow against a `tauri` surface config fixture, asserting it runs through `drive.DRIVER_FACTORIES["tauri"]` without error (monkeypatch `drive.DRIVER_FACTORIES["tauri"]` to a fake driver factory and assert it was called with the surface's `options`).
- [ ] Run `python -m pytest -q -m "web or not web"` — expect PASS, no regression.
- [ ] Verify: `python -m pytest -q -m "web or not web"`
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/web/drive.py plugins/flow-review/engine/flow_review/web/test_drive.py plugins/flow-review/engine/flow_review/web/replay.py plugins/flow-review/engine/flow_review/tauri/mocks.py && git commit -m "feat(drive): DRIVER_FACTORIES with a tauri entry, dev-server proving, mock-missing status events"`

### Task T8: Native confirm

**Executor:** opus · **Depends:** T4, T7 · **Wave:** 5
**Files:** `plugins/flow-review/engine/flow_review/tauri/launch.py` (new), `plugins/flow-review/engine/flow_review/tauri/test_launch.py` (new), `plugins/flow-review/engine/flow_review/web/driver.py`, `plugins/flow-review/engine/flow_review/web/test_driver.py`, `plugins/flow-review/engine/flow_review/cli.py`, `plugins/flow-review/engine/flow_review/test_cli.py`
**Interfaces:** Consumes: `WebDriver`, `measure.check_page`, `<run_dir>/repro/<flow_slug>.json` (written by the existing M1 verifier/repro path — confirm its exact shape by grepping `repro` across the codebase before writing the reader: `actionlog.save` writes `<run_dir>/repro/<flow_slug>.json` when recording is off, `flow_slug = config.slug(flow_id)`; no surface subfolder). Produces: `tauri/launch.py::launch_native`, `WebDriver.attach`, `flow-review confirm` verb.
**Ponytail rung:** 3 (native platform: env var + subprocess to launch the real binary; no new dependency beyond Playwright already installed).

- [ ] Grep the repo for `repro` (`grep -rn "repro" plugins/flow-review/engine/flow_review`) to find the exact shape of `<run_dir>/repro/<flow_slug>.json` the M1 verifier already writes. If no such mechanism exists yet in the codebase, STOP and add an entry to `## QUESTIONS` at the end of this plan describing the gap (do not invent a new repro-log writer here — T8 only consumes it) and implement `confirm` against a documented, hand-written fixture repro log shaped `{"finding_id": str, "flow_id": str, "route": str, "actions": [{"action": "goto"|"click"|"fill"|"press", ...}]}` so the task is still testable, flagging this assumption explicitly in the task's own commit message.
- [ ] Write failing test — create `plugins/flow-review/engine/flow_review/tauri/test_launch.py`:

```python
import os


def test_launch_native_sets_remote_debugging_port(monkeypatch, tmp_path):
    from flow_review.tauri.launch import launch_native
    captured = {}

    class FakePopen:
        def __init__(self, args, env=None, **kwargs):
            captured["args"] = args
            captured["env"] = env

    monkeypatch.setattr("subprocess.Popen", FakePopen)
    binary = tmp_path / "app.exe"
    binary.write_bytes(b"")
    launch_native(binary, port=9333)
    assert captured["args"][0] == str(binary)
    assert captured["env"]["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] == "--remote-debugging-port=9333"
```

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/tauri/test_launch.py` — expect FAIL: `ModuleNotFoundError`.
- [ ] Implement — create `plugins/flow-review/engine/flow_review/tauri/launch.py`:

```python
"""Native launch/attach for Windows WebView2 over CDP (A-35). Linux tauri-driver and macOS AX
are parked -- confirm.py checks surface.options['native'] and never reaches this module for a
'pending' surface."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def launch_native(binary: Path, port: int) -> subprocess.Popen:
    env = dict(os.environ)
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={port}"
    return subprocess.Popen([str(binary)], env=env)
```

- [ ] Run the same command — expect PASS.
- [ ] Write failing test — append to `plugins/flow-review/engine/flow_review/web/test_driver.py`:

```python
def test_webdriver_attach_uses_connect_over_cdp(monkeypatch):
    from flow_review.web.driver import WebDriver

    calls = {}

    class FakeContext:
        pages = ["the-page"]

    class FakeBrowser:
        contexts = [FakeContext()]

    class FakeChromium:
        def connect_over_cdp(self, url):
            calls["url"] = url
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    monkeypatch.setattr("flow_review.web.driver.sync_playwright", lambda: _FakeCtx(FakePlaywright()))
    driver = WebDriver.attach("http://127.0.0.1:9333")
    assert calls["url"] == "http://127.0.0.1:9333"
    assert driver.page == "the-page"


class _FakeCtx:
    def __init__(self, pw):
        self._pw = pw
    def __enter__(self):
        return self._pw
    def __exit__(self, *a):
        return False
    def start(self):
        return self._pw
```

  (Read `web/driver.py`'s existing `sync_playwright` usage pattern first — match how `WebDriver.__init__`/`launch` already start Playwright, e.g. via `.start()` kept open vs a context manager, and align this test and the implementation with that exact pattern rather than the illustrative fake above.)

- [ ] Run it — expect FAIL: `AttributeError: type object 'WebDriver' has no attribute 'attach'`.
- [ ] Implement in `web/driver.py`: add a classmethod `attach` alongside the existing constructor, following the same Playwright-lifecycle pattern already used by `__init__`/`launch` (reuse the same instance-held Playwright handle so `close()` still works):

```python
    @classmethod
    def attach(cls, cdp_url: str) -> "WebDriver":
        instance = cls.__new__(cls)
        instance._playwright = sync_playwright().start()
        browser = instance._playwright.chromium.connect_over_cdp(cdp_url)
        instance.browser = browser
        instance.page = browser.contexts[0].pages[0]
        return instance
```

  (Adjust attribute names — `_playwright`, `browser`, `page` — to match whatever `WebDriver.__init__` already sets, so `close()` and every other method keep working unchanged on an attached instance.)

- [ ] Run the same command — expect PASS.
- [ ] A-50 resolved (fixed default port, `--port` override): create `plugins/flow-review/engine/flow_review/confirm.py`. Write failing test first — create `plugins/flow-review/engine/flow_review/test_confirm.py`:

```python
import json
from pathlib import Path

from flow_review import config as configmod
from flow_review import confirm as confirmmod
from flow_review import ledger as ledger_mod


def _write_config(project_root: Path, native) -> None:
    cfg = configmod.Config(
        schema_version=2, generator_version="test",
        surfaces=[configmod.Surface(
            id="desktop", name="desktop", kind="ui", driver="tauri", launch="",
            options={"native": native, "binary": "app.exe", "dev_url": "http://127.0.0.1:1421"},
        )],
    )
    (project_root / ".flow-review").mkdir(parents=True, exist_ok=True)
    configmod.save(cfg, project_root / ".flow-review" / "config.json")


def _write_ledger(project_root: Path) -> None:
    entry = ledger_mod.LedgerEntry(
        id="f1", fingerprint="fp1", surface_id="desktop", flow_id="flow-1",
        rule="console.error", route="/", locator="css:#save-note-button", sev="P1",
        text="save_note swallowed into console.error",
    )
    ledger_mod.save(ledger_mod.Ledger(findings={"f1": entry}),
                     project_root / ".flow-review" / "findings.json")


def test_confirm_native_pending_writes_no_result_and_never_attaches(tmp_path, monkeypatch):
    _write_config(tmp_path, native="pending")
    _write_ledger(tmp_path)
    run_dir = tmp_path / "run1"
    run_dir.mkdir()

    def _boom(*a, **k):
        raise AssertionError("attach must never be called for a native: pending surface")

    monkeypatch.setattr(confirmmod.WebDriver, "attach", staticmethod(_boom))
    exit_code = confirmmod.confirm(tmp_path, run_dir)
    assert exit_code == 0
    assert not (run_dir / "native" / "f1" / "result.json").exists()
    lines = (run_dir / "events.jsonl").read_text(encoding="utf-8").strip().splitlines()
    payloads = [json.loads(line) for line in lines]
    assert any(
        p["type"] == "status" and p["state"] == "not-exercised" and p["reason"] == "native-pending"
        and p["surface_id"] == "desktop" and p["flow_id"] == "flow-1" and p["step"] == "confirm"
        for p in payloads
    )


def test_confirm_attach_failure_exits_3_with_no_ledger_write(tmp_path, monkeypatch):
    _write_config(tmp_path, native="webview2")
    _write_ledger(tmp_path)
    run_dir = tmp_path / "run1"
    (run_dir / "repro").mkdir(parents=True)
    (run_dir / "repro" / "flow-1.json").write_text(
        json.dumps({"surface_id": "desktop", "flow_id": "flow-1",
                    "steps": [{"action": "goto", "url": "/"}]}),
        encoding="utf-8",
    )
    ledger_path = tmp_path / ".flow-review" / "findings.json"
    before = ledger_path.read_bytes()

    class FakeProc:
        def kill(self):
            pass

    monkeypatch.setattr(confirmmod.tauri_launch, "launch_native", lambda binary, port: FakeProc())
    monkeypatch.setattr(confirmmod.WebDriver, "attach",
                         staticmethod(lambda cdp_url: (_ for _ in ()).throw(RuntimeError("no"))))
    monkeypatch.setattr(confirmmod, "ATTACH_RETRIES", 2)
    monkeypatch.setattr(confirmmod, "ATTACH_POLL_S", 0.01)

    exit_code = confirmmod.confirm(tmp_path, run_dir)
    assert exit_code == 3
    assert ledger_path.read_bytes() == before


def test_confirm_reproduces_writes_result_and_appends_evidence(tmp_path, monkeypatch):
    _write_config(tmp_path, native="webview2")
    _write_ledger(tmp_path)
    run_dir = tmp_path / "run1"
    (run_dir / "repro").mkdir(parents=True)
    (run_dir / "repro" / "flow-1.json").write_text(
        json.dumps({"surface_id": "desktop", "flow_id": "flow-1",
                    "steps": [{"action": "goto", "url": "/"},
                              {"action": "click", "locator": {"testid": "save-note-button"}}]}),
        encoding="utf-8",
    )

    class FakeDriver:
        def goto(self, path):
            pass
        def click(self, locator):
            pass
        def screenshot(self, path):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_bytes(b"fake-png")
            return path
        def close(self):
            pass

    class FakeProc:
        def kill(self):
            pass

    monkeypatch.setattr(confirmmod.tauri_launch, "launch_native", lambda binary, port: FakeProc())
    monkeypatch.setattr(confirmmod.WebDriver, "attach", staticmethod(lambda cdp_url: FakeDriver()))
    monkeypatch.setattr(
        confirmmod.measure, "check_page",
        lambda driver, surface_id, flow_id, route, step_index: [
            {"surface_id": surface_id, "flow_id": flow_id, "rule": "console.error", "route": route,
             "locator": "css:#save-note-button", "sev": "P1", "text": "swallowed",
             "evidence": [], "disposition": "engine"}
        ],
    )

    exit_code = confirmmod.confirm(tmp_path, run_dir, port=9333)
    assert exit_code == 0
    result = json.loads((run_dir / "native" / "f1" / "result.json").read_text(encoding="utf-8"))
    assert result["finding_id"] == "f1"
    assert result["reproduced"] is True
    assert (run_dir / "native" / "f1" / "shot.png").exists()
    lgr = ledger_mod.load(tmp_path / ".flow-review" / "findings.json")
    assert lgr.findings["f1"].evidence == ["native/f1/shot.png"]
```

  (`ledger.load`/`ledger.save` and `LedgerEntry`'s field names above are the real M1 API — do not write `Ledger.load(...)` as a classmethod call, the module-level functions `ledger.load(path)`/`ledger.save(lgr, path)` are what exists.)

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/test_confirm.py` — expect FAIL: `ModuleNotFoundError: No module named 'flow_review.confirm'`.
- [ ] Implement — create `plugins/flow-review/engine/flow_review/confirm.py`:

```python
"""Native confirm (A-35, M2): replay each P0/P1 finding's repro log on the native app over CDP.

`flow-review confirm --run DIR [--surface ID] [--finding ID] [--port 9333]` walks the ledger for
open P0/P1 findings on tauri-driver surfaces. A `native: "pending"` surface (A-35: Linux
tauri-driver / macOS AX are parked) never reaches WebDriver.attach -- it only files a
not-exercised/native-pending status event per finding and writes no result.json. Otherwise the
native binary is launched once per surface (A-50: a fixed default CDP port, 9333, overridable
with --port, since only one native confirm run happens at a time locally), attached to with a
bounded retry poll, and each finding's flat repro log `<run_dir>/repro/<flow_slug>.json` is
replayed against it.

Exit 0 = every attempted finding reproduced (native-pending findings do not count against this);
1 = some did not (a missing repro log counts as not reproduced); 3 = the native app could not be
attached within the retry window -- no ledger write happens on that path.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from flow_review import config as configmod
from flow_review import events
from flow_review import ledger as ledger_mod
from flow_review.tauri import launch as tauri_launch
from flow_review.web import measure
from flow_review.web.driver import WebDriver

DEFAULT_PORT = 9333
ATTACH_RETRIES = 20
ATTACH_POLL_S = 0.5


def _attach_with_retry(cdp_url: str) -> WebDriver | None:
    for _ in range(ATTACH_RETRIES):
        try:
            return WebDriver.attach(cdp_url)
        except Exception:
            time.sleep(ATTACH_POLL_S)
    return None


def confirm(project_root: Path, run_dir: Path, surface_id: str | None = None,
            finding_id: str | None = None, port: int = DEFAULT_PORT) -> int:
    project_root = Path(project_root)
    run_dir = Path(run_dir)
    cfg = configmod.load(project_root / ".flow-review" / "config.json")
    surfaces_by_id = {s.id: s for s in cfg.surfaces if s.driver == "tauri"}
    ledger_path = project_root / ".flow-review" / "findings.json"
    lgr = ledger_mod.load(ledger_path)

    candidates = [
        entry for entry in lgr.findings.values()
        if entry.state == "open" and entry.sev in ("P0", "P1")
        and entry.surface_id in surfaces_by_id
    ]
    if surface_id is not None:
        candidates = [e for e in candidates if e.surface_id == surface_id]
    if finding_id is not None:
        candidates = [e for e in candidates if e.id == finding_id]

    all_reproduced = True
    drivers_by_surface: dict[str, WebDriver] = {}
    procs_by_surface: dict[str, object] = {}
    try:
        for entry in candidates:
            surface = surfaces_by_id[entry.surface_id]

            if surface.options.get("native") == "pending":
                events.append(run_dir, {
                    "type": "status", "state": "not-exercised",
                    "surface_id": entry.surface_id, "flow_id": entry.flow_id,
                    "step": "confirm", "reason": "native-pending",
                })
                continue

            repro_path = run_dir / "repro" / f"{entry.flow_id}.json"
            if not repro_path.exists():
                all_reproduced = False
                continue

            driver = drivers_by_surface.get(entry.surface_id)
            if driver is None:
                binary = Path(surface.options["binary"])
                proc = tauri_launch.launch_native(binary, port)
                driver = _attach_with_retry(f"http://127.0.0.1:{port}")
                if driver is None:
                    proc.kill()
                    return 3
                drivers_by_surface[entry.surface_id] = driver
                procs_by_surface[entry.surface_id] = proc

            log = json.loads(repro_path.read_text(encoding="utf-8"))
            last_route = "/"
            for step in log["steps"]:
                action = step["action"]
                if action == "goto":
                    last_route = step["url"]
                    driver.goto(step["url"])
                elif action == "click":
                    driver.click(step["locator"])
                elif action == "fill":
                    driver.fill(step["locator"], step.get("value") or "")
                elif action == "press":
                    driver.press(step.get("value") or "")

            findings = measure.check_page(driver, entry.surface_id, entry.flow_id, last_route,
                                           None)
            out_dir = run_dir / "native" / entry.id
            out_dir.mkdir(parents=True, exist_ok=True)
            driver.screenshot(out_dir / "shot.png")
            entry.evidence.append(f"native/{entry.id}/shot.png")

            reproduced = any(f["rule"] == entry.rule for f in findings)
            if not reproduced:
                all_reproduced = False
            result = {"finding_id": entry.id, "reproduced": reproduced, "findings": findings}
            (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

        ledger_mod.save(lgr, ledger_path)
    finally:
        for driver in drivers_by_surface.values():
            driver.close()
        for proc in procs_by_surface.values():
            proc.kill()

    return 0 if all_reproduced else 1
```

  (`measure.check_page`'s exact parameter list must match the real signature in `web/measure.py` — read it first and adjust the call above if it differs, e.g. if it also takes a `tokens` or `project_root` argument; keep every other line unchanged.)

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/test_confirm.py` — expect PASS.
- [ ] Wire the CLI: in `cli.py`, add near the other verb handlers:

```python
def _run_confirm(args: argparse.Namespace) -> int:
    from flow_review import confirm as confirmmod
    project_root = args.project_root
    if project_root is None:
        print("no .flow-review/ found; pass --project", file=sys.stderr)
        return 3
    return confirmmod.confirm(Path(project_root), args.run_dir, surface_id=args.surface,
                               finding_id=args.finding, port=args.port)
```

  and in `build_parser()`, alongside the other subparsers:

```python
    confirm_parser = sub.add_parser("confirm", parents=[project_after_verb],
                                     help="replay P0/P1 findings on the native app over CDP (A-35)")
    confirm_parser.add_argument("--run", required=True, dest="run_dir", type=Path)
    confirm_parser.add_argument("--surface", default=None)
    confirm_parser.add_argument("--finding", default=None)
    confirm_parser.add_argument("--port", type=int, default=9333)
    confirm_parser.set_defaults(func=_run_confirm)
```

  (`project_after_verb` is the existing shared parent parser other verbs already use for `--project` — reuse it, do not redefine `--project` locally.)
- [ ] Write a failing CLI-level test in `test_cli.py` using `cli.main([...])` + `capsys` (there is no `run_cli` fixture in this codebase):

```python
def test_confirm_cli_dispatches_to_confirm_module(tmp_path, monkeypatch, capsys):
    from flow_review import cli
    called = {}
    monkeypatch.setattr(
        "flow_review.confirm.confirm",
        lambda project_root, run_dir, surface_id=None, finding_id=None, port=9333: (
            called.update(project_root=project_root, run_dir=run_dir, port=port) or 0
        ),
    )
    (tmp_path / ".flow-review").mkdir()
    code = cli.main(["confirm", "--run", str(tmp_path / "run1"), "--project", str(tmp_path)])
    assert code == 0
    assert called["port"] == 9333
```

  Run it — expect FAIL until `confirm` is wired into `build_parser()`/`main()`, then PASS.
- [ ] Run `python -m pytest -q -m "web or not web"` — expect PASS, no regression.
- [ ] Verify: `python -m pytest -q -m "web or not web"`
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/tauri/launch.py plugins/flow-review/engine/flow_review/tauri/test_launch.py plugins/flow-review/engine/flow_review/web/driver.py plugins/flow-review/engine/flow_review/web/test_driver.py plugins/flow-review/engine/flow_review/confirm.py plugins/flow-review/engine/flow_review/test_confirm.py plugins/flow-review/engine/flow_review/cli.py plugins/flow-review/engine/flow_review/test_cli.py && git commit -m "feat(tauri): launch_native, WebDriver.attach, confirm module + CLI verb for native P0/P1 replay (A-35)"`

### Task T9: Plan + budget

**Executor:** sonnet · **Depends:** T8 · **Wave:** 6
**Files:** `plugins/flow-review/engine/flow_review/plan.py`, `plugins/flow-review/engine/flow_review/test_plan.py`, `plugins/flow-review/skills/flow-review/SKILL.md`, `plugins/flow-review/skills/flow-review/references/validation.md`
**Interfaces:** Consumes: `flow-review confirm` (T8). Produces: a `confirm` plan step; SKILL.md run-procedure line; a validation reference entry.
**Ponytail rung:** 5 (one line: an extra plan step with zero token cost, no new abstraction).

- [ ] Write failing test — append to `plugins/flow-review/engine/flow_review/test_plan.py`, using `plan.py`'s real public entry point `plan(project_root, mode, goal=None, record=False, skip=None) -> dict`, whose per-surface output dict already has an `id`/`units`/`estimate_tokens`/`gaps` shape (read `plan.py` in full first — there is no `build_plan` function anywhere in this codebase):

```python
def test_plan_adds_zero_cost_confirm_unit_for_tauri_surface_with_open_p1(tmp_path):
    from flow_review import config as configmod
    from flow_review import ledger as ledger_mod
    from flow_review import plan as planmod

    (tmp_path / ".flow-review").mkdir()
    cfg = configmod.Config(
        schema_version=2, generator_version="test",
        surfaces=[configmod.Surface(id="desktop", name="desktop", kind="ui", driver="tauri",
                                     launch="", options={"binary": "app.exe",
                                                          "dev_url": "http://127.0.0.1:1421"})],
    )
    configmod.save(cfg, tmp_path / ".flow-review" / "config.json")
    entry = ledger_mod.LedgerEntry(
        id="f1", fingerprint="fp1", surface_id="desktop", flow_id="flow-1",
        rule="console.error", route="/", locator="css:#save-note-button", sev="P1",
        text="swallowed",
    )
    ledger_mod.save(ledger_mod.Ledger(findings={"f1": entry}),
                     tmp_path / ".flow-review" / "findings.json")

    result = planmod.plan(tmp_path, "goal", goal="save a note")
    desktop = next(s for s in result["surfaces"] if s["surface_id"] == "desktop")
    confirm_units = [u for u in desktop["units"] if u["role"] == "confirm"]
    assert confirm_units == [{"role": "confirm", "count": 1}]


def test_plan_omits_confirm_unit_when_no_open_p0_p1(tmp_path):
    from flow_review import config as configmod
    from flow_review import plan as planmod

    (tmp_path / ".flow-review").mkdir()
    cfg = configmod.Config(
        schema_version=2, generator_version="test",
        surfaces=[configmod.Surface(id="desktop", name="desktop", kind="ui", driver="tauri",
                                     launch="", options={"binary": "app.exe",
                                                          "dev_url": "http://127.0.0.1:1421"})],
    )
    configmod.save(cfg, tmp_path / ".flow-review" / "config.json")

    result = planmod.plan(tmp_path, "goal", goal="save a note")
    desktop = next(s for s in result["surfaces"] if s["surface_id"] == "desktop")
    assert [u for u in desktop["units"] if u["role"] == "confirm"] == []
```

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/test_plan.py -k confirm` — expect FAIL: no `"confirm"` role is ever added today, and `plan()` never reads the ledger for a tauri surface.
- [ ] Implement in `plan.py`: add `from flow_review import ledger as ledger_mod` alongside the existing `from flow_review import budget, config, drift, envsetup` import line; inside `plan()`, before the `for surface in runnable:` loop, load the ledger once:

```python
    lgr = ledger_mod.load(project_root / ".flow-review" / "findings.json")
```

  and, inside the loop, right after `units = [{"role": role, "count": count} for role, count in counts.items() if count > 0]` is built and before `plan_units = [...]` is derived from it, add:

```python
        if surface.driver == "tauri" and any(
            e.surface_id == surface.id and e.state == "open" and e.sev in ("P0", "P1")
            for e in lgr.findings.values()
        ):
            units.append({"role": "confirm", "count": 1})
```

  This keeps `estimate_tokens` at its existing value for the `confirm` unit: `UNIT_TEMPLATES`/`budget.estimate` has no pricing entry for the `"confirm"` role, so it contributes 0 tokens to `estimate_map`, matching the "zero-token engine step" requirement without a special case in `budget.py`.
- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/test_plan.py -k confirm` — expect PASS.
- [ ] In `SKILL.md`'s run procedure, add one numbered step after "run validation" and before "invoke the verifier": *"For every tauri surface with an open P0/P1 finding, run `flow-review confirm --run DIR` before the verifier step; its `native/<id>/result.json` files feed the verifier as replay evidence."* Match the existing numbered-list style exactly.
- [ ] In `references/validation.md` (create the section if the file already lists evidence-ref kinds; otherwise add a short new subsection), document: *"`native/<finding_id>/result.json` is a valid `replay`-kind evidence ref: `validate resolve --kind replay --ref native/<finding_id>/result.json` reads its `reproduced` boolean."*
- [ ] Add a doc-parity test if the repo already checks SKILL.md/reference docs against actual CLI verbs (reuse `test_cli_parity.py`'s existing mechanism); otherwise skip (do not invent a new parity test framework here).
- [ ] Run `python -m pytest -q -m "web or not web"` — expect PASS, no regression.
- [ ] Verify: `python -m pytest -q -m "web or not web"`
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/plan.py plugins/flow-review/engine/flow_review/test_plan.py plugins/flow-review/skills/flow-review/SKILL.md plugins/flow-review/skills/flow-review/references/validation.md && git commit -m "feat(plan): zero-token confirm step per tauri surface with open P0/P1; document native replay evidence"`

### Task T10: Docs sync

**Executor:** haiku · **Depends:** T9 · **Wave:** 7
**Files:** `plugins/flow-review/skills/flow-review/references/setup.md`, `plugins/flow-review/skills/flow-review/references/surfaces.md`, `plugins/flow-review/agents/fr-explorer.md`, `README.md`, `plugins/flow-review/skills/flow-review/test_cli_parity.py`
**Interfaces:** Consumes: verbs added by T1/T6/T8 (`run new`, `tauri mocks`, `confirm`). Produces: doc sections; a green `plugins/flow-review/skills/flow-review/test_cli_parity.py` (its real location — not under `engine/flow_review/`).
**Ponytail rung:** 5 (mechanical doc edits, no code).

- [ ] Read `references/setup.md`, `references/surfaces.md`, and `agents/fr-explorer.md` in full so edits match each file's existing structure/voice.
- [ ] In `references/setup.md`, add a "Tauri" section: how to start the dev server, run `flow-review tauri mocks --project P` to generate `.flow-review/tauri-mocks.json` stubs, fill the stubs with plausible responses by hand (one line: "unfilled commands resolve to null and are reported as not-exercised"), and set the `binary` option once `cargo tauri build` has produced it.
- [ ] In `references/surfaces.md`, add a `tauri` driver entry next to the existing `playwright` entry, listing `TAURI_OPTION_KEYS` (`dev_url`, `mocks_file`, `binary`, `native`); grep the file for any stray "cdp" surface-type mention that actually describes what is now the `tauri` driver's native-confirm path, and correct it to point at `confirm`/`native` instead if found.
- [ ] In `agents/fr-explorer.md`, add one line: tauri surfaces are driven with the same verbs as web (`goto`, `click`, `fill`, `press`) — no new verbs to learn.
- [ ] In `README.md`'s install section, add one line: native confirm on Windows requires `cargo tauri build` (or `npm run tauri build`) to have produced the binary named in the surface's `binary` config option.
- [ ] Run `python -m pytest -q plugins/flow-review/skills/flow-review/test_cli_parity.py` — expect PASS if the new verbs (`run new`, `tauri mocks`, `confirm`) are already documented somewhere `test_cli_parity.py` checks (likely `references/` or `SKILL.md`); if it FAILs, add the missing doc line(s) it expects (match the exact format its parity check parses — read the test to know the format) and re-run until PASS.
- [ ] Run `python -m pytest -q -m "web or not web"` — expect PASS, no regression.
- [ ] Verify: `python -m pytest -q -m "web or not web"`
- [ ] Commit: `git add plugins/flow-review/skills/flow-review/references/setup.md plugins/flow-review/skills/flow-review/references/surfaces.md plugins/flow-review/agents/fr-explorer.md README.md plugins/flow-review/skills/flow-review/test_cli_parity.py && git commit -m "docs: tauri setup/surfaces/fr-explorer/README sections; cli parity green"`

### Task T11: Dashboard native confirm pair

**Executor:** sonnet · **Depends:** T8 · **Wave:** 6
**Files:** `plugins/flow-review/engine/flow_review/dashboard/state.py`, `plugins/flow-review/engine/flow_review/dashboard/test_state.py`, `plugins/flow-review/engine/flow_review/dashboard/page/app.js`, `plugins/flow-review/engine/flow_review/dashboard/static/style.css` (or wherever drawer styles live — confirm the filename first)
**Interfaces:** Consumes: `<run_dir>/native/<finding_id>/result.json` (T8). Produces: `confirmed: true|false|null` field in the state fold; a web-shot/native-shot pair in the drawer.
**Ponytail rung:** 5 (one added field + one conditional image pair, reusing existing drawer layout).

Note: this is the only task in this plan that touches the dashboard's visual layout; per the dashboard design rules (no subheadings/descriptions, self-explanatory icons/tooltips, reduced motion, OS theme + toggle) keep the change to a single side-by-side image pair inside the existing drawer, with no new heading text — an implementer working this task should load the `impeccable` design skill for this one change only, per shared.md.

- [ ] Write failing test — append to `plugins/flow-review/engine/flow_review/dashboard/test_state.py`:

```python
def test_fold_exposes_confirmed_from_native_result_json(tmp_path, monkeypatch):
    from flow_review.dashboard.state import fold
    _patch_common(monkeypatch)
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    (run_dir / "native" / "f1").mkdir(parents=True)
    (run_dir / "native" / "f1" / "result.json").write_text(
        '{"finding_id": "f1", "reproduced": true, "findings": []}', encoding="utf-8")
    _write_events(run_dir, [
        {"ts": "2026-09-24T10:00:00.000Z", "id": "e1", "type": "run", "mode": "goal",
         "surfaces": [{"id": "desktop", "kind": "tauri"}]},
        {"ts": "2026-09-24T10:00:01.000Z", "id": "f1", "type": "finding", "sev": "P1",
         "surface_id": "desktop", "flow_id": "flow-1", "text": "console.error in step window",
         "disposition": "engine"},
        {"ts": "2026-09-24T10:00:02.000Z", "id": "f2", "type": "finding", "sev": "P2",
         "surface_id": "desktop", "flow_id": "flow-1", "text": "no native/f2/result.json",
         "disposition": "engine"},
    ])
    state = fold(tmp_path, run_dir, _FakeCfg())
    findings = {f["id"]: f for f in state["findings"]}
    assert findings["f1"]["confirmed"] is True
    assert findings["f2"]["confirmed"] is None
```

  (Use `state.fold(project_root, run_dir, cfg)` — there is no `fold_findings` function; reuse this file's `_patch_common`/`_write_events`/`_FakeCfg` helpers exactly as T3 does.)

- [ ] Run `python -m pytest -q plugins/flow-review/engine/flow_review/dashboard/test_state.py -k confirmed_from_native_result_json` — expect FAIL: `KeyError: 'confirmed'` today.
- [ ] Implement in `dashboard/state.py`, a helper next to `_drop_missing_evidence` (added by T3):

```python
def _confirmed_state(run_dir: Path, finding_id: str) -> bool | None:
    result_path = run_dir / "native" / finding_id / "result.json"
    if not result_path.is_file():
        return None
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return data.get("reproduced")
```

  then, inside `fold()`, right after the `_drop_missing_evidence(findings, run_dir)` call T3 added, add:

```python
    for f in findings:
        f["confirmed"] = _confirmed_state(run_dir, f["id"])
```

- [ ] Run the same command — expect PASS.
- [ ] In `dashboard/page/app.js`'s drawer-rendering code, when a finding's `confirmed` is not `None` and its evidence includes a ref matching `native/<id>/shot.png`, render that image next to the finding's existing web-shot evidence image, side by side, with an `alt`/`title` attribute of `"native confirm"` (used as the accessible name/tooltip per the dashboard rules — no separate heading or description text). When `confirmed` is `null`, render nothing extra (no placeholder, no "not confirmed" label) — absence of the pair is enough per the "no subheadings/descriptions" rule.
- [ ] Confirm the rule-lint check (grep the repo for "rule-lint" or "rule_lint" to find the actual test/script name) still passes; run it explicitly if found: `python -m pytest -q -k rule_lint` (adjust to the real test name).
- [ ] Run `python -m pytest -q -m "web or not web"` — expect PASS, no regression.
- [ ] Verify: `python -m pytest -q -m "web or not web"`
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/dashboard/state.py plugins/flow-review/engine/flow_review/dashboard/test_state.py plugins/flow-review/engine/flow_review/dashboard/page/app.js && git commit -m "feat(dashboard): confirmed field + native/web shot pair in drawer for tauri findings"`

## Checkpoints

### Task CP1: M2 checkpoint

**Executor:** opus · **Depends:** T1-T11 · **Wave:** 8

- [ ] Run `python -m pytest -q -m "web or not web"` from the repo root — expect all green, 0 failed, strictly more than the pre-M2 baseline of 513 passed.
- [ ] Clean-venv install (Windows): `uv venv $env:TEMP\frv`, then `uv pip install --python $env:TEMP\frv\Scripts\python.exe "plugins/flow-review/engine[web]"` — expect a clean install with no errors.
- [ ] From a directory outside the repo, run `& $env:TEMP\frv\Scripts\flow-review.exe --help` — expect exit code 0 and usage text listing `run`, `tauri`, `confirm` among the verbs.
- [ ] Build the fixture's native binary: from `plugins/flow-review/engine/fixtures/tauriapp`, run `cargo tauri build` — expect a binary produced under `src-tauri/target/release/`.
- [ ] Headless real run: copy `plugins/flow-review/engine/fixtures/tauriapp` to a scratch directory (`$env:TEMP\tauriapp-scratch`), start the dev server (`python -m http.server 1421 --directory src`, per `tauri.conf.json`'s `beforeDevCommand` — no `npm install` needed, this fixture's frontend has no build step), then run `claude -p "/flow-review quick save a note" --plugin-dir <repo>/plugins/flow-review` against it from that scratch directory.
- [ ] Assert: the generated project config has a surface with `driver: "tauri"`.
- [ ] Assert: `.flow-review/tauri-mocks.json` exists and has both `load_items` and `save_note` as keys.
- [ ] Assert: the run's ledger contains the planted `console.error` finding at `sev: "P1"` (per M1's rule for a console error occurring inside a step window) plus whatever measurable bugs `fixtures/webapp` already plants (reuse the existing M1 webapp checkpoint's assertion list — read the M1 plan's own checkpoint task for the exact webapp planted-bug list rather than re-deriving it).
- [ ] Run `flow-review confirm --run <run_dir>` — expect it to reproduce the P1 on the native app, writing `<run_dir>/native/<finding_id>/result.json` with `reproduced: true`, exit code 0.
- [ ] Grep the entire run directory and `.flow-review/findings.json` for the fixture's own known secret value (there are no real credentials in this fixture, so use its placeholder password literal, e.g. `grep -r "hunter2-fixture-password" <run_dir> .flow-review/findings.json` — substitute whatever placeholder secret value the M1 webapp fixture actually plants, per its own `.env`/`creds` fixture file; read that file first) and confirm zero matches.
- [ ] If any step fails, file it as a finding in `## QUESTIONS` below rather than silently patching around it; opus reviews before signing off.

## Appendix A: Decisions log

| # | Topic | Decision |
|---|---|---|
| A-35 | M2 native confirm platforms | Windows only: WebView2 over CDP, attached with Playwright `connect_over_cdp` (reuses `WebDriver`, no new driver class). Linux tauri-driver and macOS AX are parked: the config accepts `native: "pending"` and `confirm` reports `not-exercised` with reason `native-pending`; no blind code. |
| A-36 | M2 sample app | Fixture in repo: `plugins/flow-review/engine/fixtures/tauriapp`, a minimal Tauri v2 shell around the existing `fixtures/webapp` with 2 `#[tauri::command]`s and one planted bug (an invoke error swallowed silently: `console.error` and no UI feedback). |
| A-37 | Invoke mocks | Engine stubs, agent fills: `flow-review tauri mocks --project P` scans `src-tauri/**/*.rs` for `#[tauri::command]` fns and writes `.flow-review/tauri-mocks.json` `{command: null}` stubs (never overwriting a filled value); the setup agent fills plausible responses from the Rust signatures; an unfilled command returns `null` at runtime and drive files a `status` event `not-exercised` reason `mock-missing` once per command per flow. |
| A-38 | M3 tooling | User installs Maestro and runs the emulator; the engine only checks: `setup-env` reports `maestro --version` and `adb devices` gaps with the install line; `prove` for a `maestro` surface = one device in `adb devices` + `maestro hierarchy` returns a tree. The engine never boots an emulator. |
| A-39 | M3 sample app | Fixture in repo: `plugins/flow-review/engine/fixtures/mobileapp`, a minimal Expo app (3 screens) run with `npx expo start --android` into Expo Go on the emulator; planted: a tap target under 48dp, two overlapping controls, a dead button. |
| A-40 | M3 scope | Android only; `ios-sim` stays `pending-driver` until a macOS host exists. Measurement from `maestro hierarchy` bounds only: `rect.target-size` (<48dp), `rect.overlap`, `rect.offscreen`; no screenshot-sampled contrast. |
| A-41 | M4 OpenAPI depth | An OpenAPI file (if detected) yields goals (one per operation) and expected status codes. Engine rules: `http.5xx`, `http.status-undeclared`, `http.content-type`, `http.slow` (> 2000 ms). No response-body schema validation, no new dependency. |
| A-42 | M5 `watch` mapping | Surface-level: a change under a surface's `cwd` (mtime polling every 1 s, stdlib, debounced 2 s, `watch.ignore` globs; `.flow-review/`, `node_modules/`, `.git/` always ignored) re-replays every recorded flow of that surface via the M1 `replay` path; exit codes as `replay`; never prompts. No source maps, no coverage. |
| A-43 | M5 benchmark | `flow-review bench [--profile lean|default|max] [--surface ...]` runs the headless `claude -p "/flow-review full"` against the web, api and cli fixtures per profile, compares the ledger to each fixture's `planted.json`, and writes recall + tokens per true finding to `docs/benchmarks/<date>.json`. Tauri/mobile fixtures are opt-in via `--surface`. A manual release step, never CI. |
| A-44 | M1 debt | All of it lands in M2's first phase: the 6 named deferrals (crop links resolve against the dashboard's own run dir; `fnmatch` vs Playwright URL glob; slow fault `time.sleep`; skill `python -c` calls; flow-begin always writing a fault-clear event; `run_id` `:` vs `-`), the route-template fingerprint (final-review Important #5, A-6), and all 20 minors in `.superpowers/sdd/final-review.md`'s "Logged minors triage" table. |
| A-45 | Driver names and options | `config.VALID_DRIVERS` gains `tauri` (M2) and `maestro` (M3); `http` and `shell` already exist and become runnable in M4. Per-driver option keys: `TAURI_OPTION_KEYS = ("dev_url", "mocks_file", "binary", "native")`, `MAESTRO_OPTION_KEYS = ("app_id", "device", "start_cmd")`, `HTTP_OPTION_KEYS = ("base_url", "openapi", "auth_header", "auth_env", "auth_prefix", "timeout_s")`, `SHELL_OPTION_KEYS = ("command", "cwd", "timeout_s", "json_output")`. `_validate_options` dispatches on `surface.driver`. `drift.runnable_surfaces` includes a surface whose driver is in `RUNNABLE_DRIVERS = ("playwright", "tauri", "maestro", "http", "shell")`. Detection (A9) promotes `src-tauri/` to driver `tauri` (M2) and Expo `app.json` to `maestro` (M3). |
| A-46 | Drive verb set per driver | Shared verbs on every driver: `start`, `stop`, `flow-begin`, `flow-end`, `look`, `fault`. Action verbs: web/tauri/maestro `goto`, `click`, `fill`, `press`; http `request`; shell `run`. Every verb returns the M1 compact JSON `{url, title, snapshot, shot, new_findings, console_errors}` (http: `url` = request URL, `title` = `"<status> <content-type>"`, `snapshot` = first 4k chars of the body; shell: `url` = null, `title` = `"exit <code>"`, `snapshot` = stdout+stderr tail). The engine writes the action log, redacts, stamps step windows and runs the driver's measure rules after each action. One `DriveSession` class; `drive.py` builds the driver from `surface.driver` through a dict `DRIVER_FACTORIES = {"playwright": ..., "tauri": ..., "maestro": ..., "http": ..., "shell": ...}` that grows one entry per milestone. |
| A-47 | Driver protocol timing | M2 adds no protocol: a tauri surface uses `WebDriver` (launched against `dev_url` with an init script that installs the mocks; `connect_over_cdp` for native confirm). M3 introduces `flow_review/driver.py::Driver` (typing.Protocol) with exactly the methods `DriveSession` calls: `launch(base_url)`, `close()`, `goto(path)`, `click(locator)`, `fill(locator, value, secret)`, `press(key)`, `screenshot(path)`, `snapshot()`, `is_password(locator)`, `begin_step(i)`, `end_step()`, `console_errors_since_check()`, `network_log_since_check()`. M4's http and shell drivers implement the same protocol with `goto`/`click`/`fill`/`press` raising `NotImplementedError("use request")` / `("use run")` and add `request(...)` / `run(...)`. |
| A-48 | `DRIVER_FACTORIES` signature (superseded by M3's A-53) | Every factory in the dict takes `(headless, viewport, options=None)` even though `playwright` ignores `options` today — this keeps the dict uniform so `drive.py`'s call site never special-cases which driver needs options. M3 formalizes the actual `Driver` protocol (A-47); its own plan is where the calling convention becomes load-bearing across three drivers instead of two, so any adjustment happens there as A-53, not here. |
| A-49 | Mock-missing detection mechanism (resolved) | The init script tracks missing-mock invocations in a JS-side array (`window.__flowReviewMissingMocks`) the Python side can poll via `page.evaluate`, rather than a round-trip callback, to avoid adding a second Tauri IPC surface just for instrumentation. `_note_mock_invocation` itself (the state transition and the status event) is unit-tested directly in T7; the JS-polling wiring into `_result()` is exercised end-to-end by CP1. |
| A-50 | `confirm` port selection (resolved) | A fixed default port, 9333, overridable via `--port` on `confirm`, since only one native confirm run happens at a time locally. Implemented in T8's `confirm.py::DEFAULT_PORT` and the CLI's `--port` flag. |
| A-51 | Run-id minting (resolved) | `flow-review run new --project P` is the only minting point: SKILL.md calls it before `serve`; `replay.py` calls `events.new_run_id()` directly; `drive start` never creates a run dir (it receives `--run DIR`). T1 covers all of it; no follow-up needed in M2. |
| A-52 | Fixture frontend (resolved) | `fixtures/tauriapp` ships its own plain-static frontend (`src/index.html`, `src/app.js`, no build step) rather than reusing `fixtures/webapp`'s build output; `tauri.conf.json` sets `frontendDist` to `../src` and `build.devUrl`/`beforeDevCommand` to a stdlib `python -m http.server` on the same port. Implemented in T5. |
| A-85 | Secret min length (implemented deviation) | Registered secrets shorter than 4 chars are silently skipped by redaction (`events.MIN_SECRET_LEN = 4`), not 8. |
| A-86 | `?` in `url_matches` (implemented deviation) | `?` is a literal character in fault URL patterns (`web/faults.py`), not a one-char wildcard, since URLs use it for query strings. |
| A-87 | `$reject` mock sentinel (implemented deviation) | A tauri mock value shaped exactly `{"$reject": msg}` makes `invoke` reject with msg (`tauri/mocks.py`), to exercise the Err path. |
| A-88 | Confirm skips findings with no repro log (implemented deviation) | `confirm` files a not-exercised/no-repro-log status event and does not count the finding against the exit code. |
| A-89 | Confirm scope = this run (implemented deviation) | `confirm` only takes entries whose `last_run` equals the run dir's name; `--finding` names one explicitly and skips the check. |
| A-90 | Confirm exit-3 preflight (implemented deviation) | Missing/unbuilt binary, unlaunchable binary, taken CDP port or no attach in the retry window returns exit 3 before any replay; no ledger write. |
| A-91 | Confirm runs after the verifier (implemented deviation) | SKILL.md order is Validation (`fr-verifier`), then `ledger reconcile`, then `confirm`; the verifier never consumes confirm's result. |

## QUESTIONS

- This revision confirmed the "Logged minors triage" table's real 20 OK-FOR-LATER rows (numbered 1-23 with 3 MUST-FIX rows already closed) and remapped every task's minor references to those exact row numbers (see "A-44 coverage" above); no open mismatch remains.
- Rows 5 and 8 (A4, A8) are documentation-only per the table's own "OK-FOR-LATER" call — T2 adds a code comment, not a behavior change. Flag at review if a behavior change was actually wanted for either.
- Row 7 (A6, `manifest.py` unused `recorded_hash`): T2's step says "wire it into an actual comparison, or remove it — pick whichever the function's docstring/intent implies" without pre-deciding which; the implementer must read `manifest.py` and choose, then note the choice in the commit message.
- T8's `measure.check_page` call signature is written to match a plausible shape (`driver, surface_id, flow_id, route, step_index`) inferred from `web/replay.py::replay_one`'s own call to a `measure` hook; if the real `web/measure.py::check_page` signature differs (e.g. an extra `tokens`/`project_root` parameter), the implementer adjusts the one call site in `confirm.py` accordingly — flagged here rather than guessed silently.
- A-48 is marked superseded by an M3 decision (A-53) that does not exist yet in this document; the M3 plan drafter must actually add A-53 addressing the `DRIVER_FACTORIES` calling convention across three drivers, or renumber this reference if M3 resolves it differently.
