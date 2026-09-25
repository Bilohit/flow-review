# flow-review M4 (API and CLI) Implementation Plan
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. Each task names its executor model; dispatch it pinned to that model, never `inherit`. Opus reviews every checkpoint.

**Goal:** Give flow-review a first-class HTTP API driver and a first-class shell/CLI driver, both
built on stdlib only, so a project whose runnable surfaces are an OpenAPI-described service and/or
a command-line tool gets the same drive/measure/replay/lens pipeline the web driver already has.
**Architecture:** two new driver modules (`flow_review/api/`, `flow_review/shell/`) implementing the
M3 `Driver` protocol with `request`/`run` in place of pointer actions; `DriveSession` (A-46)
generalizes to dispatch the right measure rules and evidence shape per driver kind; `replay.py`
generalizes to replay a recorded `request`/`run` step. **Tech Stack:** Python 3.14 stdlib
(`urllib.request`, `subprocess`, `http.server`), no new dependency (A-41). **Spec:**
`docs/superpowers/specs/2026-09-23-flow-review-v2-design.md` §6, §9, §10, §12.

Assumes M2 and M3 have already landed: `flow_review/driver.py::Driver` (Protocol), `config.py`
already carries `TAURI_OPTION_KEYS`, `MAESTRO_OPTION_KEYS`; `drift.py` already carries
`RUNNABLE_DRIVERS = ("playwright", "tauri", "maestro", "http", "shell")` in full (M2 T4 already
added `"http"`/`"shell"` to it, ahead of this plan actually shipping those two drivers); M3's
`build_driver(driver_name, headless, viewport, options)` (A-53) and `web/drive.py`'s
`DRIVER_FACTORIES` dict already carry `"playwright"`, `"tauri"`, `"maestro"` entries in the
`factory(headless, viewport, options=None) -> Driver` shape. This plan's diffs are written
against that state; where the exact surrounding code cannot be verified today (M2/M3 not yet
merged into this checkout), the task gives the complete resulting function/file so the executor
pastes it in whole rather than patching a diff that might not apply verbatim -- flagged inline as
"(full replacement)".

## Global Constraints
- The engine never calls an LLM API. flow-review never edits product code.
- Windows 11, Python 3.14. Stdlib only in the engine core: no `requests`, no `httpx`, no `yaml`
  dependency. `urllib.request` for HTTP, `subprocess` for shell, `http.server` for fixtures.
- Every new driver implements the M3 `flow_review/driver.py::Driver` Protocol methods that
  `DriveSession` calls; `goto`/`click`/`fill`/`press` on a non-pointer driver raise
  `NotImplementedError("use request")` / `NotImplementedError("use run")`.
- Every task that adds code states its ponytail rung (1 skip / 2 stdlib / 3 native platform /
  4 installed dep / 5 one line / 6 minimum code). A deliberate shortcut carries a
  `# ponytail:` comment naming the ceiling.
- Executor tags: haiku = mechanical, sonnet = standard TDD, opus = cross-cutting/high judgment.
  Opus reviews the checkpoint.
- Run the full suite from the repo root: `python -m pytest -q -m "web or not web"`.
- Banned names (never write them): `Ledger.load`, `.upsert(`, `runs_for`, `"severity"`,
  `viewports`, `refuted_reason`, `lens_or_rule`, `resolve_project_root(`, `envsetup.redact`,
  `add_suppression`, `_recordings_root`.

## File Structure (target)
```
plugins/flow-review/engine/
  fixtures/
    apiapp/           # NEW: server.py, openapi.json, planted.json, README.md, test_apiapp.py
    cliapp/           # NEW: notes.py, planted.json, README.md, test_cliapp.py
  flow_review/
    api/              # NEW package
      __init__.py
      driver.py       # HttpDriver
      measure.py      # check_response
      openapi.py      # load, goals
      test_driver.py
      test_measure.py
      test_openapi.py
    shell/            # NEW package (the M4 shell driver; flow_review/cli.py stays the engine CLI)
      __init__.py
      driver.py       # ShellDriver
      measure.py      # check_run, check_json_shape, check_help
      test_driver.py
      test_measure.py
    audit.py           # MODIFIED: Candidate gains `options`, _from_openapi fills it
    config.py           # MODIFIED: HTTP_OPTION_KEYS, SHELL_OPTION_KEYS, _validate_options
    envsetup.py          # MODIFIED: secret_names() picks up options.auth_env
    web/
      drive.py           # MODIFIED: DriveSession.kind, .request(), .run(), fault dispatch,
                          #           DRIVER_FACTORIES gains http/shell, cmd_request/cmd_run
      actionlog.py        # MODIFIED: record_request_step, record_run_step
      replay.py            # MODIFIED: replay_one handles request/run steps; replay() runs
                            #           non-playwright surfaces too
plugins/flow-review/skills/flow-review/
  references/
    lenses/api.md      # RESTORED from git history
    lenses/cli.md       # RESTORED from git history
    surfaces.md          # MODIFIED: http, shell sections filled in
    testing.md            # MODIFIED: shell / http per-driver notes filled in
  test_references.py       # MODIFIED: REQUIRED gains the two lens files; kind tuples gain api/cli
plugins/flow-review/agents/
  fr-lens.md            # MODIFIED: drop the "(API and CLI lenses return with M4)" parenthetical
  fr-explorer.md          # MODIFIED: api/cli probing paragraph
  fr-cold-eyes.md          # MODIFIED: api/cli probing paragraph
plugins/flow-review/skills/flow-review/SKILL.md  # MODIFIED: same parenthetical dropped
```

## Task Skeleton

| id | goal (one line) | deps | wave | owner | exec |
|---|---|---|---|---|---|
| T1 | Config: `HTTP_OPTION_KEYS`, `SHELL_OPTION_KEYS`, `_validate_options` for http/shell, a test asserting `drift.RUNNABLE_DRIVERS` already carries both, `auth_env` registered as a secret name | — | 1 | D1 | sonnet |
| T2 | API fixture `fixtures/apiapp` + `planted.json` + README + boot-and-hit pytest | — | 1 | D1 | haiku |
| T3 | CLI fixture `fixtures/cliapp` + `planted.json` + README + per-planted-behaviour pytest | — | 1 | D2 | haiku |
| T9 | Lenses back: restore `lenses/api.md`/`lenses/cli.md`, wire `test_references.py`, drop the M4-pending parenthetical in `fr-lens.md`/SKILL.md | — | 1 | D3 | haiku |
| T4 | `api/driver.py::HttpDriver` + `api/measure.py::check_response`, tests against `fixtures/apiapp` | T1, T2 | 2 | D1 | sonnet |
| T5 | `shell/driver.py::ShellDriver` + `shell/measure.py::check_run/check_json_shape/check_help`, tests against `fixtures/cliapp` | T1, T3 | 2 | D2 | sonnet |
| T6 | `api/openapi.py` (`load`, `goals`), `_from_openapi` fills `options.openapi` (M2 owns `Candidate.options`), `flow-review api goals` verb | T4 | 3 | D1 | sonnet |
| T7 | Drive verbs `request` (http) and `run` (shell) in `DriveSession` + parser + `DRIVER_FACTORIES`, action-log steps, evidence, fault limits for http | T4, T5 | 3 | D2 | opus |
| T8 | Replay for http/shell recordings: `replay_one` handles `request`/`run`, `replay()` runs non-playwright surfaces | T7 | 4 | D1 | opus |
| T10 | Docs: `surfaces.md`/`testing.md` http+shell sections, `fr-explorer.md`/`fr-cold-eyes.md` probing paragraphs; `test_cli_parity` green | T7, T9 | 4 | D3 | haiku |
| T11 | Budget: kind-keyed explorer/cold-eyes/lens priors for api/cli at 60% of web's; `plan.py` puts `surface.kind` into each plan unit | T6 | 4 | D2 | sonnet |
| T12 | Dashboard: lock in existing `output`-lane support with a regression test (no code change needed -- `state.py`/`app.js` already carry it) | T7 | 4 | D4 | haiku |
| CP1 | M4 checkpoint | T1-T12 | 5 | — | opus |

## Lanes
Phase 1 (wave 1): lane A = T1; lane B = T2; lane C = T3 ‖ T9 (T9 touches only skill-tree files,
disjoint from T3's fixture files -- run it alongside T3's lane). **Lanes merge here:** T1, T2, T3,
T9 all land before wave 2 starts.

Phase 2 (wave 2): lane A = T4; lane B = T5. Disjoint files (`api/` vs `shell/`). **Lanes merge
here:** T4, T5 land before wave 3.

Phase 3 (wave 3): lane A = T6; lane B = T7. T6 touches `audit.py`/`api/openapi.py`; T7 touches
`web/drive.py`/`web/actionlog.py` -- disjoint. **Lanes merge here:** T6, T7 land before wave 4.

Phase 4 (wave 4): lane A = T8; lane B = T10; lane C = T11 then T12 in the same lane (T11 touches
`budget.py`/`plan.py`, T12 adds one dashboard test file -- disjoint from T8's `web/replay.py` and
T10's docs, sequential in one lane keeps the phase at 3 lanes). **Lanes merge here:** T8, T10,
T11, T12 all land before CP1.

## Canonical Interfaces
Reused verbatim from the shared cross-milestone contract (shared.md, binding):

- **HTTP** (M4): `api/driver.py::HttpDriver(base_url, auth: dict | None, timeout_s)` with
  `request(method, path, headers: dict | None, body: str | None) -> HttpResponse` (TypedDict:
  `status, content_type, body, elapsed_ms, url`); `api/measure.py::check_response(resp, expected:
  list[int] | None, route) -> list[Finding]`; `api/openapi.py::load(path) -> dict`,
  `goals(spec) -> list[dict]` (`op_id, method, path, expected: list[int], summary`). Action-log
  step for http: `{"action": "request", "method", "path", "headers" (secret values redacted),
  "body", "status"}`.
- **Shell** (M4): `shell/driver.py::ShellDriver(command, cwd, timeout_s, json_output: bool)` with
  `run(args: list[str], stdin: str | None) -> RunResult` (TypedDict: `exit_code, stdout, stderr,
  elapsed_ms`); `shell/measure.py::check_run(res, route: str) -> list[Finding]` with rules
  `cli.exit-code` (non-zero without stderr), `cli.stderr-on-success`, `cli.json-shape` (when
  `json_output`), `cli.help` (`--help` must exit 0). Action-log step: `{"action": "run", "args",
  "stdin", "exit_code"}`.
- **Driver names and options** (A-45): `HTTP_OPTION_KEYS = ("base_url", "openapi", "auth_header",
  "auth_env", "auth_prefix", "timeout_s")`, `SHELL_OPTION_KEYS = ("command", "cwd", "timeout_s",
  "json_output")`. `drift.RUNNABLE_DRIVERS` is already the full `("playwright", "tauri",
  "maestro", "http", "shell")` as of M2 T4 -- this plan never edits that tuple, only tests it.
  `web/drive.py::DRIVER_FACTORIES` (already carrying `"playwright", "tauri", "maestro"` entries
  in the M2 A-48 `factory(headless, viewport, options=None) -> Driver` shape) gains `"http",
  "shell"` entries in that same shape.
- **Drive verb set** (A-46): shared verbs on every driver: `start`, `stop`, `flow-begin`,
  `flow-end`, `look`, `fault`. Action verbs: http `request`; shell `run`. Every verb returns
  the compact JSON `{url, title, snapshot, shot, new_findings, console_errors}` (http: `url` =
  request URL, `title` = `"<status> <content-type>"`, `snapshot` = first 4k chars of the body;
  shell: `url` = null, `title` = `"exit <code>"`, `snapshot` = stdout+stderr tail).
- **Fingerprint route template** (M2 debt, already landed): `ledger.route_template(path: str) ->
  str`. `web/drive.py` and `web/replay.py` call it before `ledger.fingerprint`.
- **Evidence refs**: `http/<flow>/<step>.json` (request + response, redacted), `shell/<flow>/
  <step>.txt` (args + exit + stdout + stderr tail). Served at `/run/<relpath>`.

### New in this plan (drafter proposal, confirm at review)
- `flow_review.web.drive.DriveSession.__init__` gains a `kind: str = "web"` parameter selecting
  which measure rules `_run_checks`-equivalent code runs (`"web" | "http" | "shell"`). Existing
  `DriveSession(driver, surface_id, run_dir, project_root, record_enabled, tokens=None)` calls
  (tests, `serve()`) keep working unchanged because `kind` defaults to `"web"`.
- `flow_review.web.actionlog.record_request_step(log, method, path, headers, body, status)` and
  `record_run_step(log, args, stdin, exit_code)` append the A-46 step shapes directly (distinct
  from the generic `record_step` used by goto/click/fill/press, whose flat
  action/url/locator/value/checkpoint shape does not fit a request or a shell invocation).
- `flow_review.web.replay._runnable_recording_surfaces(cfg, surface_id)` replaces
  `_playwright_surfaces` -- same shape, widened to `driver in ("playwright", "http", "shell")`.

## Tasks

### Task T1: Config plumbing for http/shell surfaces
**Executor:** sonnet · **Depends:** — · **Wave:** 1
**Files:** `plugins/flow-review/engine/flow_review/config.py`,
`plugins/flow-review/engine/flow_review/envsetup.py`,
`plugins/flow-review/engine/flow_review/test_config.py`
**Interfaces:** Produces `config.HTTP_OPTION_KEYS`, `config.SHELL_OPTION_KEYS`,
`envsetup.secret_names` (extended). Consumes `drift.RUNNABLE_DRIVERS`, already complete
(M2 T4) -- this task asserts it, never edits it.
**Ponytail rung:** 2 (stdlib set/tuple manipulation, no new abstraction).

- [ ] Write the failing test in `test_config.py` (append):
  ```python
  def test_http_and_shell_option_keys_validate():
      surface = Surface(id="api", name="api", kind="api", driver="http", launch="",
                         options={"base_url": "http://localhost:9000", "openapi": "openapi.json",
                                  "auth_header": "Authorization", "auth_env": "API_TOKEN",
                                  "auth_prefix": "Bearer ", "timeout_s": 5})
      _validate_surface(surface)  # must not raise

      shell_surface = Surface(id="cli", name="cli", kind="cli", driver="shell", launch="",
                               options={"command": "notes.py", "cwd": ".", "timeout_s": 5,
                                        "json_output": True})
      _validate_surface(shell_surface)  # must not raise

      bad = Surface(id="api", name="api", kind="api", driver="http", launch="",
                    options={"bogus_key": 1})
      with pytest.raises(ConfigKeyError):
          _validate_surface(bad)


  def test_drift_runnable_drivers_already_includes_http_and_shell():
      # M2 T4 already set drift.RUNNABLE_DRIVERS to its final form; this test only guards
      # against a regression, this task never edits the tuple itself.
      from flow_review.drift import RUNNABLE_DRIVERS

      assert "http" in RUNNABLE_DRIVERS
      assert "shell" in RUNNABLE_DRIVERS
  ```
  Add the needed imports at the top of `test_config.py` if not already present:
  `from flow_review.config import (Surface, ConfigKeyError, _validate_surface)`.
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/test_config.py -q` from the
  repo root. Expected FAIL: the http/shell options currently fail `_validate_options`'s
  catch-all branch with `ConfigKeyError` (the `RUNNABLE_DRIVERS` assertion already passes --
  M2 T4 shipped it -- so only the first test fails).
- [ ] Implement in `config.py`. Add below `WEB_OPTION_KEYS`:
  ```python
  HTTP_OPTION_KEYS = (
      "base_url", "openapi", "auth_header", "auth_env", "auth_prefix", "timeout_s",
  )
  SHELL_OPTION_KEYS = ("command", "cwd", "timeout_s", "json_output")
  ```
  Do not touch `drift.RUNNABLE_DRIVERS` -- it already reads `("playwright", "tauri", "maestro",
  "http", "shell")` from M2 T4.
  M2/M3 already generalized `_validate_options` to dispatch through a single
  `_OPTION_KEYS_BY_DRIVER` dict (`{"playwright": WEB_OPTION_KEYS, "tauri": TAURI_OPTION_KEYS,
  "maestro": MAESTRO_OPTION_KEYS}`) rather than an if/elif ladder. This task only adds two
  entries to that existing dict -- it never re-touches `_validate_options` itself:
  ```python
  _OPTION_KEYS_BY_DRIVER["http"] = HTTP_OPTION_KEYS
  _OPTION_KEYS_BY_DRIVER["shell"] = SHELL_OPTION_KEYS
  ```
  If `_OPTION_KEYS_BY_DRIVER` is not yet present in the checkout this task actually runs against
  (M2/M3 not yet merged), define it and `_validate_options` together instead, in the shape M2/M3
  already commit to:
  ```python
  _OPTION_KEYS_BY_DRIVER = {
      "playwright": WEB_OPTION_KEYS, "http": HTTP_OPTION_KEYS, "shell": SHELL_OPTION_KEYS,
  }


  def _validate_options(surface: Surface) -> None:
      where = f"surfaces[{surface.id!r}].options"
      allowed = _OPTION_KEYS_BY_DRIVER.get(surface.driver)
      if allowed is not None:
          _check_keys(surface.options, set(allowed), where)
      elif surface.options:
          _check_keys(surface.options, set(), where)
  ```
  and flag the gap rather than silently inventing `TAURI_OPTION_KEYS`/`MAESTRO_OPTION_KEYS`
  placeholders -- those two belong to M2/M3, not to this task.
- [ ] In `envsetup.py`, replace `secret_names` (full replacement):
  ```python
  def secret_names(cfg) -> set[str]:
      """A-26: the env-var names some surface's `creds` points at, plus (M4) an http surface's
      `options.auth_env` -- the only .env values that are secrets. Registering every value
      (DEBUG=1, PORT=3000) blanked those substrings in every event, timestamps included."""
      names = {name for surface in cfg.surfaces for name in (surface.creds or {}).values()}
      for surface in cfg.surfaces:
          if surface.driver == "http":
              auth_env = (surface.options or {}).get("auth_env")
              if auth_env:
                  names.add(auth_env)
      return names
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/test_config.py plugins/flow-review/engine/flow_review/test_envsetup.py -q`. Expected PASS.
- [ ] Verify: `python -m pytest -q -m "web or not web"` from the repo root, all green.
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/config.py plugins/flow-review/engine/flow_review/envsetup.py plugins/flow-review/engine/flow_review/test_config.py && git commit -m "feat(config): http/shell option keys, auth_env as secret name"`

### Task T2: API fixture `fixtures/apiapp`
**Executor:** haiku · **Depends:** — · **Wave:** 1
**Files:** `plugins/flow-review/engine/fixtures/apiapp/server.py`,
`plugins/flow-review/engine/fixtures/apiapp/openapi.json`,
`plugins/flow-review/engine/fixtures/apiapp/planted.json`,
`plugins/flow-review/engine/fixtures/apiapp/README.md`,
`plugins/flow-review/engine/fixtures/apiapp/test_apiapp.py`
**Interfaces:** none (a fixture, not engine code).
**Ponytail rung:** 2 (stdlib `http.server`, no framework).

- [ ] Create `plugins/flow-review/engine/fixtures/apiapp/server.py`:
  ```python
  """Stdlib-only fixture API server for flow-review M4 (A-41). Serves four documented
  operations plus one undocumented slow one. Run: python server.py [port] (0 = OS-assigned)."""
  from __future__ import annotations

  import json
  import sys
  import time
  from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

  ITEMS = {"1": {"id": 1, "name": "widget"}, "13": {"id": 13, "name": "cursed"}}


  class Handler(BaseHTTPRequestHandler):
      def log_message(self, fmt, *args) -> None:
          pass

      def _send(self, status: int, body: bytes, content_type: str = "application/json") -> None:
          self.send_response(status)
          self.send_header("Content-Type", content_type)
          self.send_header("Content-Length", str(len(body)))
          self.end_headers()
          self.wfile.write(body)

      def do_GET(self) -> None:
          if self.path == "/items":
              self._send(200, json.dumps(list(ITEMS.values())).encode("utf-8"))
          elif self.path.startswith("/items/"):
              item_id = self.path.rsplit("/", 1)[-1]
              if item_id == "13":
                  # planted: http.5xx
                  self._send(500, json.dumps({"error": "cursed item"}).encode("utf-8"))
              elif item_id in ITEMS:
                  self._send(200, json.dumps(ITEMS[item_id]).encode("utf-8"))
              else:
                  self._send(404, json.dumps({"error": "not found"}).encode("utf-8"))
          elif self.path == "/slow":
              time.sleep(2.5)  # planted: http.slow
              self._send(200, json.dumps({"ok": True}).encode("utf-8"))
          elif self.path == "/export":
              # planted: http.content-type -- header claims JSON, body is HTML
              self._send(200, b"<html><body>export</body></html>", content_type="application/json")
          else:
              self._send(404, json.dumps({"error": "not found"}).encode("utf-8"))

      def do_POST(self) -> None:
          if self.path == "/items":
              length = int(self.headers.get("Content-Length", 0) or 0)
              self.rfile.read(length)
              # planted: http.status-undeclared -- openapi.json declares 200 for this operation
              self._send(201, json.dumps({"id": 2, "name": "new"}).encode("utf-8"))
          else:
              self._send(404, json.dumps({"error": "not found"}).encode("utf-8"))


  def main(argv: list[str] | None = None) -> None:
      argv = argv if argv is not None else sys.argv[1:]
      port = int(argv[0]) if argv else 8000
      server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
      print(f"listening on {server.server_address[1]}")
      sys.stdout.flush()
      server.serve_forever()


  if __name__ == "__main__":
      main()
  ```
- [ ] Create `plugins/flow-review/engine/fixtures/apiapp/openapi.json`:
  ```json
  {
    "openapi": "3.0.0",
    "info": {"title": "fixtures/apiapp", "version": "1.0.0"},
    "paths": {
      "/items": {
        "get": {"operationId": "listItems", "responses": {"200": {"description": "ok"}}},
        "post": {"operationId": "createItem", "responses": {"200": {"description": "ok"}}}
      },
      "/items/{id}": {
        "get": {
          "operationId": "getItem",
          "responses": {"200": {"description": "ok"}, "404": {"description": "not found"}}
        }
      },
      "/export": {
        "get": {
          "operationId": "exportItems",
          "responses": {"200": {"description": "ok", "content": {"application/json": {}}}}
        }
      }
    }
  }
  ```
- [ ] Create `plugins/flow-review/engine/fixtures/apiapp/planted.json`:
  ```json
  [
    {"rule": "http.5xx", "route": "/items/:id", "locator": ""},
    {"rule": "http.status-undeclared", "route": "/items", "locator": ""},
    {"rule": "http.content-type", "route": "/export", "locator": ""},
    {"rule": "http.slow", "route": "/slow", "locator": ""}
  ]
  ```
- [ ] Create `plugins/flow-review/engine/fixtures/apiapp/README.md`:
  ```markdown
  # fixtures/apiapp

  A stdlib-only `http.server` fixture used by M4's api driver tests and by the M4 checkpoint's
  headless run. Start it with `python server.py [port]` (omit the port to use 8000; the port
  argument lets tests bind a free one). `openapi.json` documents three operations
  (`GET /items`, `POST /items`, `GET /items/{id}`, `GET /export`); `/slow` is intentionally
  undocumented. See `planted.json` for the four defects this fixture exists to exercise.
  ```
- [ ] Write the failing test `plugins/flow-review/engine/fixtures/apiapp/test_apiapp.py`:
  ```python
  import json
  import socket
  import subprocess
  import sys
  import time
  import urllib.error
  import urllib.request
  from pathlib import Path

  FIXTURE_DIR = Path(__file__).parent


  def _free_port() -> int:
      with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
          s.bind(("127.0.0.1", 0))
          return s.getsockname()[1]


  def _get(port, path):
      try:
          with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as resp:
              return resp.status, resp.read(), resp.headers.get("Content-Type", "")
      except urllib.error.HTTPError as exc:
          return exc.code, exc.read(), exc.headers.get("Content-Type", "")


  def test_every_planted_route_behaves_as_documented():
      port = _free_port()
      proc = subprocess.Popen([sys.executable, str(FIXTURE_DIR / "server.py"), str(port)],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
      try:
          deadline = time.monotonic() + 5
          while time.monotonic() < deadline:
              try:
                  urllib.request.urlopen(f"http://127.0.0.1:{port}/items", timeout=1)
                  break
              except OSError:
                  time.sleep(0.1)

          status, body, _ = _get(port, "/items/13")
          assert status == 500  # http.5xx

          req = urllib.request.Request(f"http://127.0.0.1:{port}/items", data=b"{}",
                                        method="POST")
          try:
              resp = urllib.request.urlopen(req, timeout=5)
              status = resp.status
          except urllib.error.HTTPError as exc:
              status = exc.code
          assert status == 201  # http.status-undeclared vs the openapi.json 200

          status, body, content_type = _get(port, "/export")
          assert content_type.startswith("application/json")
          assert body.startswith(b"<html")  # http.content-type

          started = time.monotonic()
          status, _, _ = _get(port, "/slow")
          assert status == 200
          assert time.monotonic() - started > 2.0  # http.slow

          planted = json.loads((FIXTURE_DIR / "planted.json").read_text())
          assert {p["rule"] for p in planted} == {
              "http.5xx", "http.status-undeclared", "http.content-type", "http.slow",
          }
      finally:
          proc.terminate()
          proc.wait(timeout=5)
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/fixtures/apiapp/test_apiapp.py -q`.
  Expected FAIL before `server.py` exists: `ModuleNotFoundError`/`FileNotFoundError`. Once
  `server.py` above is in place, expected PASS.
- [ ] Run `python -m pytest plugins/flow-review/engine/fixtures/apiapp/test_apiapp.py -q` again
  for confirmation. Expected PASS.
- [ ] Verify: `python -m pytest -q -m "web or not web"` from the repo root, all green.
- [ ] Commit: `git add plugins/flow-review/engine/fixtures/apiapp && git commit -m "test(fixtures): add apiapp fixture with four planted API defects"`

### Task T3: CLI fixture `fixtures/cliapp`
**Executor:** haiku · **Depends:** — · **Wave:** 1
**Files:** `plugins/flow-review/engine/fixtures/cliapp/notes.py`,
`plugins/flow-review/engine/fixtures/cliapp/planted.json`,
`plugins/flow-review/engine/fixtures/cliapp/README.md`,
`plugins/flow-review/engine/fixtures/cliapp/test_cliapp.py`
**Interfaces:** none.
**Ponytail rung:** 2 (stdlib `argparse`/`json`).

- [ ] Create `plugins/flow-review/engine/fixtures/cliapp/notes.py`:
  ```python
  """Stdlib-only fixture CLI for flow-review M4 (A-41): a tiny notes store."""
  from __future__ import annotations

  import argparse
  import json
  import sys
  from pathlib import Path

  STORE = Path(__file__).parent / "notes.json"


  def _load() -> list[str]:
      if STORE.exists():
          return json.loads(STORE.read_text(encoding="utf-8"))
      return []


  def _save(notes: list[str]) -> None:
      STORE.write_text(json.dumps(notes), encoding="utf-8")


  def cmd_add(args: argparse.Namespace) -> int:
      notes = _load()
      notes.append(args.text)
      _save(notes)
      # planted: cli.stderr-on-success -- a warning on the success path
      print("warning: notes.json is unencrypted", file=sys.stderr)
      print(f"added note {len(notes)}")
      return 0


  def cmd_list(args: argparse.Namespace) -> int:
      notes = _load()
      if not notes:
          # planted: cli.exit-code -- non-zero exit with no stderr message at all
          return 2
      for i, text in enumerate(notes, 1):
          print(f"{i}. {text}")
      return 0


  def cmd_export(args: argparse.Namespace) -> int:
      notes = _load()
      if args.json:
          print(json.dumps(notes))
          # planted: cli.json-shape -- trailing text after the JSON payload
          print("(export complete)")
      else:
          for text in notes:
              print(text)
      return 0


  def build_parser() -> argparse.ArgumentParser:
      parser = argparse.ArgumentParser(prog="notes", add_help=False)
      parser.add_argument("-h", "--help", action="store_true", dest="help")
      sub = parser.add_subparsers(dest="command")

      add_p = sub.add_parser("add")
      add_p.add_argument("text")
      add_p.set_defaults(func=cmd_add)

      list_p = sub.add_parser("list")
      list_p.set_defaults(func=cmd_list)

      export_p = sub.add_parser("export")
      export_p.add_argument("--json", action="store_true")
      export_p.set_defaults(func=cmd_export)

      return parser


  def main(argv: list[str] | None = None) -> int:
      argv = argv if argv is not None else sys.argv[1:]
      parser = build_parser()
      args = parser.parse_args(argv)
      if args.help or args.command is None:
          parser.print_help()
          # planted: cli.help -- --help exits 1 instead of 0
          return 1
      return args.func(args)


  if __name__ == "__main__":
      raise SystemExit(main())
  ```
- [ ] Create `plugins/flow-review/engine/fixtures/cliapp/planted.json`:
  ```json
  [
    {"rule": "cli.exit-code", "route": "list", "locator": ""},
    {"rule": "cli.stderr-on-success", "route": "add", "locator": ""},
    {"rule": "cli.json-shape", "route": "export", "locator": ""},
    {"rule": "cli.help", "route": "--help", "locator": ""}
  ]
  ```
- [ ] Create `plugins/flow-review/engine/fixtures/cliapp/README.md`:
  ```markdown
  # fixtures/cliapp

  A stdlib-only argparse CLI (`notes.py`) used by M4's shell driver tests and by the M4
  checkpoint's headless run: `add TEXT`, `list`, `export [--json]`. `notes.json` (created next
  to the script on first `add`) is the store; delete it to reset. See `planted.json` for the
  four defects this fixture exists to exercise.
  ```
- [ ] Write the failing test `plugins/flow-review/engine/fixtures/cliapp/test_cliapp.py`:
  ```python
  import json
  import subprocess
  import sys
  from pathlib import Path

  FIXTURE_DIR = Path(__file__).parent
  NOTES_PY = FIXTURE_DIR / "notes.py"


  def _run(tmp_path, *args):
      store = tmp_path / "notes.json"
      env_script = tmp_path / "notes.py"
      env_script.write_text(NOTES_PY.read_text().replace(
          'STORE = Path(__file__).parent / "notes.json"', f'STORE = Path(r"{store}")'
      ), encoding="utf-8")
      return subprocess.run([sys.executable, str(env_script), *args],
                             capture_output=True, text=True)


  def test_list_on_empty_store_exits_2_with_no_stderr(tmp_path):
      res = _run(tmp_path, "list")
      assert res.returncode == 2
      assert res.stderr == ""


  def test_add_warns_on_stderr_despite_succeeding(tmp_path):
      res = _run(tmp_path, "add", "buy milk")
      assert res.returncode == 0
      assert "unencrypted" in res.stderr


  def test_export_json_has_trailing_text_after_the_payload(tmp_path):
      _run(tmp_path, "add", "buy milk")
      res = _run(tmp_path, "export", "--json")
      decoder = json.JSONDecoder()
      _, end = decoder.raw_decode(res.stdout.strip())
      assert res.stdout.strip()[end:].strip() != ""


  def test_help_exits_1_not_0(tmp_path):
      res = _run(tmp_path, "--help")
      assert res.returncode == 1


  def test_planted_json_matches_the_four_behaviours_above():
      planted = json.loads((FIXTURE_DIR / "planted.json").read_text())
      assert {p["rule"] for p in planted} == {
          "cli.exit-code", "cli.stderr-on-success", "cli.json-shape", "cli.help",
      }
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/fixtures/cliapp/test_cliapp.py -q`.
  Expected FAIL before `notes.py` exists. Once created, expected PASS.
- [ ] Re-run for confirmation. Expected PASS.
- [ ] Verify: `python -m pytest -q -m "web or not web"` from the repo root, all green.
- [ ] Commit: `git add plugins/flow-review/engine/fixtures/cliapp && git commit -m "test(fixtures): add cliapp fixture with four planted CLI defects"`

### Task T9: Restore `lenses/api.md` and `lenses/cli.md`
**Executor:** haiku · **Depends:** — · **Wave:** 1
**Files:** `plugins/flow-review/skills/flow-review/references/lenses/api.md`,
`plugins/flow-review/skills/flow-review/references/lenses/cli.md`,
`plugins/flow-review/skills/flow-review/test_references.py`,
`plugins/flow-review/agents/fr-lens.md`,
`plugins/flow-review/skills/flow-review/SKILL.md`
**Interfaces:** none (docs only).
**Ponytail rung:** 1 (skip -- the content already exists in git history and already matches the
canonical finding shape; nothing to write from scratch).

- [ ] Confirm the deletion commit (already known): `git log --diff-filter=D --oneline -- plugins/flow-review/skills/flow-review/references/lenses/` names `0fa2ac5` ("docs(skill): ship M1-only lens + driver content") as the commit that removed
  `references/lenses/api.md` and `references/lenses/cli.md`.
- [ ] Write the failing test first. Add to `test_references.py`:
  ```python
  def test_lenses_api_and_cli_are_restored_and_required():
      assert (REFS / "lenses" / "api.md") in REQUIRED
      assert (REFS / "lenses" / "cli.md") in REQUIRED
      for kind in ("api", "cli"):
          path = REFS / "lenses" / f"{kind}.md"
          assert path.is_file(), f"missing {path}"
          assert len(path.read_text(encoding="utf-8")) > 400
  ```
  Then change `REQUIRED` (near the top of `test_references.py`) from:
  ```python
  REQUIRED = [
      REFS / "surfaces.md", REFS / "testing.md", REFS / "evidence.md", REFS / "stuck.md",
      REFS / "goals.md", REFS / "validation.md",
      REFS / "lenses" / "ui.md",
      ROOT / "templates" / "flows.md",
  ]
  ```
  to:
  ```python
  REQUIRED = [
      REFS / "surfaces.md", REFS / "testing.md", REFS / "evidence.md", REFS / "stuck.md",
      REFS / "goals.md", REFS / "validation.md",
      REFS / "lenses" / "ui.md", REFS / "lenses" / "api.md", REFS / "lenses" / "cli.md",
      ROOT / "templates" / "flows.md",
  ]
  ```
  and every `for kind in ("ui",):` loop in the file (four occurrences:
  `test_no_lens_file_claims_it_runs_alone_or_never_drives_the_flow`,
  `test_no_lens_file_requires_two_lenses_to_agree`,
  `test_every_lens_file_uses_the_canonical_finding_field_names`,
  `test_every_lens_file_points_at_validation_not_arbitration`) to `for kind in ("ui", "api", "cli"):`.
- [ ] Run `python -m pytest plugins/flow-review/skills/flow-review/test_references.py -q`.
  Expected FAIL: `assert (REFS / "lenses" / "api.md") in REQUIRED` -- the file does not exist yet.
- [ ] Restore the two files verbatim from git history:
  ```bash
  git show 0fa2ac5^:plugins/flow-review/skills/flow-review/references/lenses/api.md > plugins/flow-review/skills/flow-review/references/lenses/api.md
  git show 0fa2ac5^:plugins/flow-review/skills/flow-review/references/lenses/cli.md > plugins/flow-review/skills/flow-review/references/lenses/cli.md
  ```
  Both files already use the canonical finding field names (`surface_id`, `flow_id`, `rule`,
  `route`, `locator`, `sev`, `text`, `evidence`, `disposition`), already point at
  `references/validation.md`, and already carry the same "never dispatched once per lens" /
  "no agreement rule" contract as `lenses/ui.md` -- no trimming is needed beyond the restore
  itself.
- [ ] In `plugins/flow-review/agents/fr-lens.md`, change:
  ```
  against every lens `references/lenses/ui.md` defines for that surface's `kind`, in this
  single call -- never dispatched once per lens. (API and CLI lenses return with M4.)
  ```
  to:
  ```
  against every lens `references/lenses/<kind>.md` defines for that surface's `kind` (`ui`,
  `api`, or `cli`), in this single call -- never dispatched once per lens.
  ```
- [ ] In `plugins/flow-review/skills/flow-review/SKILL.md`, change:
  ```
  entirely in `quick` mode), `fr-lens` runs once per screen against every lens that surface
  kind defines -- never once per lens. `references/lenses/ui.md` is the rubric (API and CLI
  lenses return with M4); suppressions from `flow-review ledger suppressions --rule RULE`
  ```
  to:
  ```
  entirely in `quick` mode), `fr-lens` runs once per screen against every lens that surface
  kind defines -- never once per lens. `references/lenses/<kind>.md` (`ui`, `api`, `cli`) is
  the rubric; suppressions from `flow-review ledger suppressions --rule RULE`
  ```
- [ ] Run `python -m pytest plugins/flow-review/skills/flow-review/ -q`. Expected PASS.
- [ ] Verify: `python -m pytest -q -m "web or not web"` from the repo root, all green.
- [ ] Commit: `git add plugins/flow-review/skills/flow-review/references/lenses/api.md plugins/flow-review/skills/flow-review/references/lenses/cli.md plugins/flow-review/skills/flow-review/test_references.py plugins/flow-review/agents/fr-lens.md plugins/flow-review/skills/flow-review/SKILL.md && git commit -m "docs(skill): restore api/cli lens rubrics (A-29)"`

### Task T4: `api/driver.py::HttpDriver` and `api/measure.py::check_response`
**Executor:** sonnet · **Depends:** T1, T2 · **Wave:** 2
**Files:** `plugins/flow-review/engine/flow_review/api/__init__.py`,
`plugins/flow-review/engine/flow_review/api/driver.py`,
`plugins/flow-review/engine/flow_review/api/measure.py`,
`plugins/flow-review/engine/flow_review/api/test_driver.py`,
`plugins/flow-review/engine/flow_review/api/test_measure.py`
(a new package directory counts as one file per shared.md's fixture-directory convention; this
task is scoped to the package as a unit)
**Interfaces:** Produces `api.driver.HttpDriver`, `api.driver.HttpResponse`,
`api.driver.resolve_auth`, `api.measure.check_response`. Consumes `flow_review.web.measure.Finding`.
**Ponytail rung:** 2 (stdlib `urllib.request` only, no HTTP client dependency).

- [ ] Create `plugins/flow-review/engine/flow_review/api/__init__.py` (empty).
- [ ] Write the failing test `plugins/flow-review/engine/flow_review/api/test_driver.py`:
  ```python
  import socket
  import subprocess
  import sys
  import time
  from pathlib import Path

  import pytest

  from flow_review.api.driver import HttpDriver

  FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "apiapp" / "server.py"


  def _free_port() -> int:
      with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
          s.bind(("127.0.0.1", 0))
          return s.getsockname()[1]


  @pytest.fixture
  def api_server():
      port = _free_port()
      proc = subprocess.Popen([sys.executable, str(FIXTURE), str(port)],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
      deadline = time.monotonic() + 5
      while time.monotonic() < deadline:
          try:
              HttpDriver(f"http://127.0.0.1:{port}").request("GET", "/items")
              break
          except OSError:
              time.sleep(0.1)
      yield f"http://127.0.0.1:{port}"
      proc.terminate()
      proc.wait(timeout=5)


  def test_request_returns_the_typed_response_shape(api_server):
      driver = HttpDriver(api_server)
      resp = driver.request("GET", "/items")
      assert resp["status"] == 200
      assert resp["content_type"].startswith("application/json")
      assert resp["url"] == api_server + "/items"
      assert isinstance(resp["elapsed_ms"], int)


  def test_pointer_methods_raise_not_implemented(api_server):
      driver = HttpDriver(api_server)
      with pytest.raises(NotImplementedError):
          driver.goto("/")
      with pytest.raises(NotImplementedError):
          driver.click({})


  def test_auth_header_is_sent(api_server):
      driver = HttpDriver(api_server, auth={"header": "Authorization", "value": "Bearer x"})
      # the fixture ignores auth, but a request must not raise when auth is configured
      resp = driver.request("GET", "/items")
      assert resp["status"] == 200


  def test_request_rejects_a_relative_or_scheme_relative_path(api_server):
      driver = HttpDriver(api_server)
      with pytest.raises(ValueError):
          driver.request("GET", "items")  # no leading slash
      with pytest.raises(ValueError):
          driver.request("GET", "//evil.example/items")  # scheme-relative, changes host


  def test_resolve_auth_resolves_the_named_env_var(monkeypatch):
      from flow_review.api.driver import resolve_auth

      monkeypatch.setenv("API_TOKEN", "s3cr3t")
      headers = resolve_auth({"header": "Authorization", "env": "API_TOKEN", "prefix": "Bearer "},
                              None, {"API_TOKEN"})
      assert headers == {"Authorization": "Bearer s3cr3t"}


  def test_resolve_auth_returns_empty_when_auth_is_none():
      from flow_review.api.driver import resolve_auth

      assert resolve_auth(None, None, set()) == {}
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/api/test_driver.py -q`.
  Expected FAIL: `ModuleNotFoundError: No module named 'flow_review.api'`.
- [ ] Create `plugins/flow-review/engine/flow_review/api/driver.py`:
  ```python
  """HttpDriver: the M4 api surface driver (A-41/A-46/A-47). Stdlib `urllib.request` only --
  no `requests`/`httpx` dependency. Implements the M3 Driver protocol's non-pointer surface:
  goto/click/fill/press raise NotImplementedError so a mis-scripted flow fails loudly instead
  of silently doing nothing."""
  from __future__ import annotations

  import time
  import urllib.error
  import urllib.request
  from typing import TypedDict
  from urllib.parse import urlparse

  MAX_BODY = 64 * 1024


  class HttpResponse(TypedDict):
      status: int
      content_type: str
      body: str
      elapsed_ms: int
      url: str


  class _NoRedirect(urllib.request.HTTPRedirectHandler):
      def redirect_request(self, req, fp, code, msg, headers, newurl):
          return None  # never follow a redirect across origins (A-41 bind)


  class HttpDriver:
      def __init__(self, base_url: str, auth: dict | None = None, timeout_s: float = 10):
          self.base_url = base_url.rstrip("/")
          self.auth = auth or {}
          self.timeout_s = timeout_s
          self._opener = urllib.request.build_opener(_NoRedirect)
          self._offline = False
          self._delay_ms = 0

      def launch(self, base_url: str | None = None) -> None:
          if base_url:
              self.base_url = base_url.rstrip("/")

      def close(self) -> None:
          pass

      def goto(self, path: str):
          raise NotImplementedError("use request")

      def click(self, locator):
          raise NotImplementedError("use request")

      def fill(self, locator, value, secret: bool = False):
          raise NotImplementedError("use request")

      def press(self, key: str):
          raise NotImplementedError("use request")

      def screenshot(self, path) -> None:
          raise NotImplementedError("an api surface has no screen to capture")

      def snapshot(self) -> dict:
          return {"aria": ""}

      def is_password(self, locator) -> bool:
          return False

      def begin_step(self, index: int) -> None:
          pass

      def end_step(self) -> None:
          pass

      def console_errors_since_check(self) -> list:
          return []

      def network_log_since_check(self) -> list:
          return []

      def simulate_offline(self, active: bool) -> None:
          self._offline = active

      def simulate_delay(self, delay_ms: int) -> None:
          self._delay_ms = delay_ms

      def clear_faults(self) -> None:
          self._offline = False
          self._delay_ms = 0

      def request(self, method: str, path: str, headers: dict | None = None,
                  body: str | None = None) -> HttpResponse:
          if not (path.startswith("/") and not path.startswith("//")):
              raise ValueError(
                  f"path must be an absolute in-origin path starting with a single '/', "
                  f"got {path!r}"
              )
          intended_url = self.base_url + path
          assert urlparse(intended_url).netloc == urlparse(self.base_url).netloc, (
              f"request path {path!r} escaped the surface's own origin {self.base_url!r}"
          )
          base = "http://127.0.0.1:1" if self._offline else self.base_url  # closed port
          url = base + path
          req_headers = dict(headers or {})
          if self.auth.get("header") and self.auth.get("value"):
              req_headers[self.auth["header"]] = self.auth["value"]
          data = body.encode("utf-8") if body is not None else None
          req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
          if self._delay_ms:
              time.sleep(self._delay_ms / 1000)
          started = time.monotonic()
          try:
              with self._opener.open(req, timeout=self.timeout_s) as resp:
                  raw = resp.read(MAX_BODY + 1)
                  status = resp.status
                  content_type = resp.headers.get("Content-Type", "")
          except urllib.error.HTTPError as exc:
              raw = exc.read(MAX_BODY + 1)
              status = exc.code
              content_type = exc.headers.get("Content-Type", "") if exc.headers else ""
          except (urllib.error.URLError, OSError) as exc:
              elapsed_ms = int((time.monotonic() - started) * 1000)
              return HttpResponse(status=0, content_type="", body=str(exc),
                                   elapsed_ms=elapsed_ms, url=url)
          elapsed_ms = int((time.monotonic() - started) * 1000)
          return HttpResponse(
              status=status, content_type=content_type,
              body=raw[:MAX_BODY].decode("utf-8", errors="replace"),
              elapsed_ms=elapsed_ms, url=url,
          )


  def resolve_auth(auth: dict | None, project_root, secret_names) -> dict:
      """Resolve an `_auth_from`-shaped spec (`{"header", "env", "prefix"}`, from
      `web/drive.py::_auth_from`) into the header(s) to merge into one request, via
      `envsetup.resolve_env` -- the same path `fill --from-env` already uses, so the value is
      registered as a secret (and therefore redacted downstream) at the point it is actually
      read. Called per call, both from `DriveSession.request` (live, T7) and `replay_one`'s
      `request` branch (recorded, T8) -- never from inside `HttpDriver` itself and never once
      at construction, so a resolved credential is never baked into a driver object or a
      recorded action-log step."""
      from flow_review import envsetup

      if not auth or not (auth.get("header") and auth.get("env")):
          return {}
      value = envsetup.resolve_env(auth["env"], project_root, secret_names)
      if value is None:
          return {}
      return {auth["header"]: auth.get("prefix", "") + value}
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/api/test_driver.py -q`.
  Expected PASS.
- [ ] Write the failing test `plugins/flow-review/engine/flow_review/api/test_measure.py`:
  ```python
  from flow_review.api.measure import check_response


  def _resp(status=200, content_type="application/json", body="{}", elapsed_ms=10,
            url="http://x/items"):
      return {"status": status, "content_type": content_type, "body": body,
              "elapsed_ms": elapsed_ms, "url": url}


  def test_5xx_is_p0():
      findings = check_response(_resp(status=500), [200], "GET /items/:id")
      assert any(f["rule"] == "http.5xx" and f["sev"] == "P0" for f in findings)


  def test_undeclared_status_is_p1():
      findings = check_response(_resp(status=201), [200], "POST /items")
      assert any(f["rule"] == "http.status-undeclared" and f["sev"] == "P1" for f in findings)


  def test_no_expected_list_never_flags_undeclared_status():
      findings = check_response(_resp(status=201), None, "POST /items")
      assert not any(f["rule"] == "http.status-undeclared" for f in findings)


  def test_json_content_type_with_non_json_body_flags_content_type():
      findings = check_response(_resp(body="<html></html>"), [200], "GET /export")
      assert any(f["rule"] == "http.content-type" for f in findings)


  def test_slow_response_over_2000ms_flags_slow():
      findings = check_response(_resp(elapsed_ms=2500), [200], "GET /slow")
      assert any(f["rule"] == "http.slow" and f["sev"] == "P2" for f in findings)


  def test_fast_clean_response_has_no_findings():
      assert check_response(_resp(), [200], "GET /items") == []
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/api/test_measure.py -q`.
  Expected FAIL: `ModuleNotFoundError: No module named 'flow_review.api.measure'`.
- [ ] Create `plugins/flow-review/engine/flow_review/api/measure.py`:
  ```python
  """A-41 rules for an http surface response. Every rule fires from the response alone -- no
  response-body schema validation (no yaml/jsonschema dependency)."""
  from __future__ import annotations

  import json

  from flow_review.web.measure import Finding

  SLOW_THRESHOLD_MS = 2000


  def check_response(resp: dict, expected: list[int] | None, route: str) -> list[Finding]:
      findings: list[Finding] = []
      status = resp["status"]

      if status >= 500:
          findings.append(Finding(
              rule="http.5xx", sev="P0", locator=None, route=route,
              text=f"{route} returned {status}",
              evidence=[json.dumps(resp)], disposition="engine",
          ))
      elif expected is not None and status not in expected and status != 0:
          findings.append(Finding(
              rule="http.status-undeclared", sev="P1", locator=None, route=route,
              text=f"{route} returned {status}, not one of the declared {expected}",
              evidence=[json.dumps(resp)], disposition="engine",
          ))

      content_type = (resp.get("content_type") or "").split(";")[0].strip()
      if content_type == "application/json":
          try:
              json.loads(resp["body"])
          except ValueError:
              findings.append(Finding(
                  rule="http.content-type", sev="P1", locator=None, route=route,
                  text=f"{route} declares Content-Type application/json but the body is not "
                       f"valid JSON",
                  evidence=[resp["body"][:200]], disposition="engine",
              ))

      if resp.get("elapsed_ms", 0) > SLOW_THRESHOLD_MS:
          findings.append(Finding(
              rule="http.slow", sev="P2", locator=None, route=route,
              text=f"{route} took {resp['elapsed_ms']}ms (over the {SLOW_THRESHOLD_MS}ms budget)",
              evidence=[f"elapsed_ms={resp['elapsed_ms']}"], disposition="engine",
          ))

      return findings
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/api/ -q`. Expected PASS.
- [ ] Verify: `python -m pytest -q -m "web or not web"` from the repo root, all green.
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/api && git commit -m "feat(api): HttpDriver and check_response measure rules (A-41)"`

### Task T5: `shell/driver.py::ShellDriver` and `shell/measure.py`
**Executor:** sonnet · **Depends:** T1, T3 · **Wave:** 2
**Files:** `plugins/flow-review/engine/flow_review/shell/` package (`__init__.py`, `driver.py`,
`measure.py`, `test_driver.py`, `test_measure.py`)
**Interfaces:** Produces `shell.driver.ShellDriver`, `shell.driver.RunResult`,
`shell.measure.check_run`, `shell.measure.check_json_shape`, `shell.measure.check_help`.
**Ponytail rung:** 2 (stdlib `subprocess` only).

- [ ] Create `plugins/flow-review/engine/flow_review/shell/__init__.py` (empty).
- [ ] Write the failing test `plugins/flow-review/engine/flow_review/shell/test_driver.py`:
  ```python
  from pathlib import Path

  from flow_review.shell.driver import ShellDriver

  FIXTURE = Path(__file__).resolve().parents[3] / "fixtures" / "cliapp" / "notes.py"
  import sys


  def test_run_returns_the_typed_result_shape(tmp_path):
      store = tmp_path / "notes.json"
      script = tmp_path / "notes.py"
      script.write_text(FIXTURE.read_text().replace(
          'STORE = Path(__file__).parent / "notes.json"', f'STORE = Path(r"{store}")'
      ), encoding="utf-8")
      driver = ShellDriver(sys.executable, cwd=str(tmp_path), timeout_s=5)
      res = driver.run([str(script), "add", "hello"])
      assert res["exit_code"] == 0
      assert "unencrypted" in res["stderr"]
      assert isinstance(res["elapsed_ms"], int)


  def test_pointer_methods_raise_not_implemented(tmp_path):
      driver = ShellDriver(sys.executable, cwd=str(tmp_path), timeout_s=5)
      import pytest
      with pytest.raises(NotImplementedError):
          driver.goto("/")
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/shell/test_driver.py -q`.
  Expected FAIL: `ModuleNotFoundError`.
- [ ] Create `plugins/flow-review/engine/flow_review/shell/driver.py`:
  ```python
  """ShellDriver: the M4 cli surface driver (A-41/A-46/A-47). Stdlib `subprocess` only."""
  from __future__ import annotations

  import subprocess
  import time
  from typing import TypedDict


  class RunResult(TypedDict):
      exit_code: int
      stdout: str
      stderr: str
      elapsed_ms: int


  class ShellDriver:
      def __init__(self, command: str, cwd: str | None = None, timeout_s: float = 10,
                   json_output: bool = False):
          self.command = command
          self.cwd = cwd
          self.timeout_s = timeout_s
          self.json_output = json_output

      def launch(self, base_url=None) -> None:
          pass

      def close(self) -> None:
          pass

      def goto(self, path):
          raise NotImplementedError("use run")

      def click(self, locator):
          raise NotImplementedError("use run")

      def fill(self, locator, value, secret: bool = False):
          raise NotImplementedError("use run")

      def press(self, key):
          raise NotImplementedError("use run")

      def screenshot(self, path) -> None:
          raise NotImplementedError("a cli surface has no screen to capture")

      def snapshot(self) -> dict:
          return {"aria": ""}

      def is_password(self, locator) -> bool:
          return False

      def begin_step(self, index: int) -> None:
          pass

      def end_step(self) -> None:
          pass

      def console_errors_since_check(self) -> list:
          return []

      def network_log_since_check(self) -> list:
          return []

      def run(self, args: list[str], stdin: str | None = None) -> RunResult:
          started = time.monotonic()
          proc = subprocess.run(
              [self.command, *args], input=stdin, capture_output=True,
              timeout=self.timeout_s, cwd=self.cwd, text=True, encoding="utf-8",
              errors="replace",
          )
          elapsed_ms = int((time.monotonic() - started) * 1000)
          return RunResult(exit_code=proc.returncode, stdout=proc.stdout,
                            stderr=proc.stderr, elapsed_ms=elapsed_ms)
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/shell/test_driver.py -q`.
  Expected PASS.
- [ ] Write the failing test `plugins/flow-review/engine/flow_review/shell/test_measure.py`:
  ```python
  from flow_review.shell.measure import check_help, check_json_shape, check_run


  def _res(exit_code=0, stdout="", stderr="", elapsed_ms=10):
      return {"exit_code": exit_code, "stdout": stdout, "stderr": stderr,
              "elapsed_ms": elapsed_ms}


  def test_nonzero_exit_with_no_stderr_is_flagged():
      findings = check_run(_res(exit_code=2, stderr=""), "list")
      assert any(f["rule"] == "cli.exit-code" for f in findings)


  def test_nonzero_exit_with_stderr_is_not_flagged_by_exit_code_rule():
      findings = check_run(_res(exit_code=2, stderr="empty store"), "list")
      assert not any(f["rule"] == "cli.exit-code" for f in findings)


  def test_success_with_stderr_is_flagged():
      findings = check_run(_res(exit_code=0, stderr="warning: x"), "add")
      assert any(f["rule"] == "cli.stderr-on-success" for f in findings)


  def test_json_with_trailing_text_is_flagged():
      findings = check_json_shape(_res(stdout='["a"]\n(export complete)\n'), "export")
      assert any(f["rule"] == "cli.json-shape" for f in findings)


  def test_clean_json_is_not_flagged():
      findings = check_json_shape(_res(stdout='["a"]\n'), "export")
      assert findings == []


  def test_help_nonzero_exit_is_flagged():
      findings = check_help(_res(exit_code=1), "--help")
      assert any(f["rule"] == "cli.help" for f in findings)


  def test_help_zero_exit_is_not_flagged():
      assert check_help(_res(exit_code=0), "--help") == []
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/shell/test_measure.py -q`.
  Expected FAIL: `ModuleNotFoundError: No module named 'flow_review.shell.measure'`.
- [ ] Create `plugins/flow-review/engine/flow_review/shell/measure.py`:
  ```python
  """A-41 rules for a shell surface invocation."""
  from __future__ import annotations

  import json

  from flow_review.web.measure import Finding


  def check_run(res: dict, route: str) -> list[Finding]:
      findings: list[Finding] = []
      if res["exit_code"] != 0 and not res["stderr"].strip():
          findings.append(Finding(
              rule="cli.exit-code", sev="P1", locator=None, route=route,
              text=f"{route} exited {res['exit_code']} with no stderr message",
              evidence=[json.dumps(res)], disposition="engine",
          ))
      if res["exit_code"] == 0 and res["stderr"].strip():
          findings.append(Finding(
              rule="cli.stderr-on-success", sev="P2", locator=None, route=route,
              text=f"{route} succeeded but wrote to stderr",
              evidence=[res["stderr"][:200]], disposition="engine",
          ))
      return findings


  def check_json_shape(res: dict, route: str) -> list[Finding]:
      stdout = res["stdout"].strip()
      decoder = json.JSONDecoder()
      try:
          _, end = decoder.raw_decode(stdout)
      except ValueError:
          return []  # not JSON at all is not this rule's concern -- check_run covers failure
      trailing = stdout[end:].strip()
      if not trailing:
          return []
      return [Finding(
          rule="cli.json-shape", sev="P1", locator=None, route=route,
          text=f"{route} --json prints trailing text after the JSON payload",
          evidence=[res["stdout"][-200:]], disposition="engine",
      )]


  def check_help(res: dict, route: str) -> list[Finding]:
      if res["exit_code"] == 0:
          return []
      return [Finding(
          rule="cli.help", sev="P1", locator=None, route=route,
          text=f"{route} exited {res['exit_code']} instead of 0",
          evidence=[json.dumps(res)], disposition="engine",
      )]
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/shell/ -q`. Expected PASS.
- [ ] Verify: `python -m pytest -q -m "web or not web"` from the repo root, all green.
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/shell && git commit -m "feat(cli): ShellDriver and check_run/check_json_shape/check_help measure rules (A-41)"`

### Task T6: OpenAPI loader + goals, `_from_openapi` records the spec path, `flow-review api goals`
**Executor:** sonnet · **Depends:** T4 · **Wave:** 3
**Files:** `plugins/flow-review/engine/flow_review/api/openapi.py`,
`plugins/flow-review/engine/flow_review/api/test_openapi.py`,
`plugins/flow-review/engine/flow_review/audit.py`,
`plugins/flow-review/engine/flow_review/test_audit.py`,
`plugins/flow-review/engine/flow_review/cli.py`,
`plugins/flow-review/engine/flow_review/test_cli.py`
**Interfaces:** Consumes `audit.Candidate.options` (added by the M2 plan's T4). Produces `api.openapi.load`, `api.openapi.goals`, and the CLI verb `flow-review api goals --surface ID [--project P]` (prints the `goals(...)` list as JSON; this is how the explorer's docs pass reads OpenAPI, since agents never import Python).
**Ponytail rung:** 2 (stdlib `json` only; no `yaml` dependency -- a `.yaml`-only OpenAPI file
is a friendly error, never a silent guess).

- [ ] Write the failing test `plugins/flow-review/engine/flow_review/api/test_openapi.py`:
  ```python
  import json

  import pytest

  from flow_review.api.openapi import goals, load

  SPEC = {
      "openapi": "3.0.0",
      "paths": {
          "/items": {
              "get": {"operationId": "listItems", "responses": {"200": {}}},
              "post": {"operationId": "createItem", "responses": {"200": {}}},
          },
          "/items/{id}": {
              "get": {"operationId": "getItem", "responses": {"200": {}, "404": {}}},
          },
      },
  }


  def test_load_reads_json(tmp_path):
      path = tmp_path / "openapi.json"
      path.write_text(json.dumps(SPEC))
      assert load(path) == SPEC


  def test_load_rejects_yaml_only_file_with_a_friendly_error(tmp_path):
      path = tmp_path / "openapi.yaml"
      path.write_text("openapi: 3.0.0")
      with pytest.raises(ValueError, match="JSON only"):
          load(path)


  def test_goals_one_per_operation():
      out = goals(SPEC)
      assert len(out) == 3
      by_id = {g["op_id"]: g for g in out}
      assert by_id["listItems"]["method"] == "GET"
      assert by_id["listItems"]["path"] == "/items"
      assert set(by_id["getItem"]["expected"]) == {200, 404}
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/api/test_openapi.py -q`.
  Expected FAIL: `ModuleNotFoundError: No module named 'flow_review.api.openapi'`.
- [ ] Create `plugins/flow-review/engine/flow_review/api/openapi.py`:
  ```python
  """A-41: OpenAPI is read for goals and expected status codes only -- no response-body schema
  validation, no yaml dependency (a .yaml-only file is a named limitation, not a silent skip)."""
  from __future__ import annotations

  import json
  from pathlib import Path

  _METHODS = ("get", "post", "put", "patch", "delete")


  def load(path: Path) -> dict:
      path = Path(path)
      if path.suffix in (".yaml", ".yml"):
          raise ValueError(
              f"{path.name} is a YAML OpenAPI file; flow-review reads JSON only (no yaml "
              f"dependency, A-41) -- add a openapi.json twin or convert this file to JSON"
          )
      return json.loads(path.read_text(encoding="utf-8"))


  def goals(spec: dict) -> list[dict]:
      out: list[dict] = []
      for path, methods in (spec.get("paths") or {}).items():
          for method, op in methods.items():
              if method.lower() not in _METHODS:
                  continue
              expected = [int(code) for code in (op.get("responses") or {}) if code.isdigit()]
              out.append({
                  "op_id": op.get("operationId") or f"{method}_{path}",
                  "method": method.upper(),
                  "path": path,
                  "expected": expected,
                  "summary": op.get("summary", ""),
              })
      return out
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/api/test_openapi.py -q`.
  Expected PASS.
- [ ] Write the failing test in `test_audit.py` (append):
  ```python
  def test_from_openapi_records_the_spec_path_in_options(tmp_path):
      (tmp_path / "openapi.json").write_text('{"openapi": "3.0.0", "paths": {}}')
      candidates = detect(tmp_path)
      api = next(c for c in candidates if c.kind == "api")
      assert api.options == {"openapi": "openapi.json"}
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/test_audit.py -q`. Expected
  FAIL: `AttributeError: 'Candidate' object has no attribute 'options'`.
- [ ] `audit.Candidate` already has `options: dict = field(default_factory=dict)` from the M2 plan's T4. If this branch lacks it, add exactly that field (and `field` to the dataclasses import) before continuing. Then replace `_from_openapi`:
  ```python
  def _from_openapi(root: Path) -> list[Candidate]:
      for name in _OPENAPI_NAMES:
          path = root / name
          if not path.is_file():
              continue
          return [Candidate(
              name="api", kind="api", driver="http", launch="",
              evidence=_evidence(path, root, None, ""),
              options={"openapi": path.relative_to(root).as_posix()},
          )]
      return []
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/test_audit.py -q`. Expected
  PASS.
- [ ] Write the failing test in `test_cli.py` (append):
  ```python
  def test_api_goals_prints_openapi_goals_as_json(tmp_path, capsys):
      import json
      from flow_review import cli
      (tmp_path / ".flow-review").mkdir()
      (tmp_path / "openapi.json").write_text(json.dumps({
          "openapi": "3.0.0",
          "paths": {"/items": {"get": {"operationId": "listItems", "responses": {"200": {}}}}},
      }))
      (tmp_path / ".flow-review" / "config.json").write_text(json.dumps({
          "schema_version": 2, "generator_version": "2.0.0", "surfaces": [{
              "id": "api", "name": "api", "kind": "api", "driver": "http", "launch": "",
              "options": {"base_url": "http://127.0.0.1:1", "openapi": "openapi.json"},
          }],
      }))
      rc = cli.main(["api", "goals", "--surface", "api", "--project", str(tmp_path)])
      assert rc == 0
      out = json.loads(capsys.readouterr().out)
      assert out == [{"op_id": "listItems", "method": "GET", "path": "/items",
                      "expected": [200], "summary": ""}]


  def test_api_goals_without_openapi_option_prints_empty_list(tmp_path, capsys):
      import json
      from flow_review import cli
      (tmp_path / ".flow-review").mkdir()
      (tmp_path / ".flow-review" / "config.json").write_text(json.dumps({
          "schema_version": 2, "generator_version": "2.0.0", "surfaces": [{
              "id": "api", "name": "api", "kind": "api", "driver": "http", "launch": "",
              "options": {"base_url": "http://127.0.0.1:1"},
          }],
      }))
      assert cli.main(["api", "goals", "--surface", "api", "--project", str(tmp_path)]) == 0
      assert json.loads(capsys.readouterr().out) == []
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/test_cli.py -q -k api_goals`.
  Expected FAIL: `argparse` error `invalid choice: 'api'` (exit 2 raised as SystemExit).
- [ ] In `cli.py`, add the verb next to the other subparsers, following the file's existing
  `sub.add_parser(...)` + `_run_<verb>` pattern exactly. `_project_and_cfg(args)` below stands
  for whatever helper `cli.py` already uses to resolve `--project` and load the config: read the
  file and call that helper by its real name.
  ```python
  def _run_api(args) -> int:
      import json
      from flow_review.api import openapi
      project_root, cfg = _project_and_cfg(args)
      surface = next((s for s in cfg.surfaces if s.id == args.surface), None)
      if surface is None:
          print(json.dumps({"error": f"unknown surface {args.surface!r}"}))
          return 3
      rel = surface.options.get("openapi")
      if not rel:
          print("[]")
          return 0
      path = Path(rel) if Path(rel).is_absolute() else project_root / rel
      print(json.dumps(openapi.goals(openapi.load(path))))
      return 0
  ```
  Parser wiring (inside `build_parser()`):
  ```python
  p_api = sub.add_parser("api", help="API surface helpers")
  api_sub = p_api.add_subparsers(dest="api_verb", required=True)
  p_goals = api_sub.add_parser("goals", help="print OpenAPI-derived goals as JSON")
  p_goals.add_argument("--surface", required=True)
  p_goals.add_argument("--project")
  ```
  and the dispatch entry `"api": _run_api`.
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/test_cli.py -q -k api_goals`.
  Expected PASS.
- [ ] Verify: `python -m pytest -q -m "web or not web"` from the repo root, all green.
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/api/openapi.py plugins/flow-review/engine/flow_review/api/test_openapi.py plugins/flow-review/engine/flow_review/audit.py plugins/flow-review/engine/flow_review/test_audit.py plugins/flow-review/engine/flow_review/cli.py plugins/flow-review/engine/flow_review/test_cli.py && git commit -m "feat(api): OpenAPI load/goals, audit records options.openapi"`

### Task T7: Drive verbs `request` and `run`
**Executor:** opus · **Depends:** T4, T5 · **Wave:** 3
**Files:** `plugins/flow-review/engine/flow_review/web/drive.py`,
`plugins/flow-review/engine/flow_review/web/actionlog.py`,
`plugins/flow-review/engine/flow_review/web/test_drive.py`,
`plugins/flow-review/engine/flow_review/web/test_actionlog.py`
**Interfaces:** Consumes `api.driver.HttpDriver`, `api.driver.resolve_auth`,
`api.openapi.load`/`goals`, `shell.driver.ShellDriver`, `api.measure.check_response`,
`shell.measure.check_run/check_json_shape/check_help`, `actionlog._slug`. Produces
`DriveSession.request`, `DriveSession.run`, `actionlog.record_request_step`,
`actionlog.record_run_step`, `DRIVER_FACTORIES["http"]`, `DRIVER_FACTORIES["shell"]`.
**Ponytail rung:** 3 (one class generalized by a `kind` discriminator, no new plugin
framework -- A-46 is explicit that there is one `DriveSession` class, not one per driver).

- [ ] Write the failing tests. Append to `web/test_actionlog.py`:
  ```python
  def test_record_request_step_redacts_header_values():
      from flow_review import events
      from flow_review.web.actionlog import new_log, record_request_step

      events.register_secret("s3cr3t")
      log = new_log("api", "f1")
      record_request_step(log, "GET", "/items", {"Authorization": "Bearer s3cr3t"}, None, 200)
      step = log["steps"][-1]
      assert step["action"] == "request"
      assert "s3cr3t" not in step["headers"]["Authorization"]
      events.clear_secrets()


  def test_record_run_step_shape():
      from flow_review.web.actionlog import new_log, record_run_step

      log = new_log("cli", "f1")
      record_run_step(log, ["list"], None, 2)
      step = log["steps"][-1]
      assert step == {"action": "run", "args": ["list"], "stdin": None, "exit_code": 2}
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/web/test_actionlog.py -q`.
  Expected FAIL: `ImportError: cannot import name 'record_request_step'`.
- [ ] In `web/actionlog.py`, append (after `record_step`):
  ```python
  def record_request_step(log: dict, method: str, path: str, headers: dict | None,
                           body: str | None, status: int) -> dict:
      from flow_review import events

      safe_headers = events.redact(dict(headers or {}))
      safe_body = events.redact(body) if body else body
      log["steps"].append({
          "action": "request", "method": method, "path": path,
          "headers": safe_headers, "body": safe_body, "status": status,
      })
      return log


  def record_run_step(log: dict, args: list[str], stdin: str | None, exit_code: int) -> dict:
      from flow_review import events

      log["steps"].append({
          "action": "run", "args": [events.redact(a) for a in args],
          "stdin": events.redact(stdin) if stdin else stdin, "exit_code": exit_code,
      })
      return log
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/web/test_actionlog.py -q`.
  Expected PASS.
- [ ] Write the failing tests. Append to `web/test_drive.py`:
  ```python
  def test_drive_session_request_files_a_finding_and_writes_output_event(tmp_path):
      from flow_review.api.measure import check_response
      from flow_review.web.drive import DriveSession

      class FakeHttpDriver:
          def request(self, method, path, headers=None, body=None):
              return {"status": 500, "content_type": "application/json", "body": "{}",
                      "elapsed_ms": 5, "url": "http://x" + path}

      session = DriveSession(FakeHttpDriver(), "api", tmp_path, tmp_path, False, kind="api")
      session.flow_begin("f1")
      result = session.request("GET", "/items/13")
      assert result["title"] == "500 application/json"
      assert len(result["new_findings"]) == 1

      events_text = (tmp_path / "events.jsonl").read_text()
      assert '"type": "output"' in events_text or '"type":"output"' in events_text


  def test_drive_session_request_looks_up_expected_codes_from_openapi(tmp_path):
      import json as jsonmod
      from flow_review.web.drive import DriveSession

      (tmp_path / "openapi.json").write_text(jsonmod.dumps({
          "openapi": "3.0.0",
          "paths": {"/items": {"post": {"operationId": "createItem",
                                        "responses": {"200": {}}}}},
      }))

      class FakeHttpDriver:
          def request(self, method, path, headers=None, body=None):
              return {"status": 201, "content_type": "application/json", "body": "{}",
                      "elapsed_ms": 5, "url": "http://x" + path}

      session = DriveSession(FakeHttpDriver(), "api", tmp_path, tmp_path, False, kind="api",
                              options={"openapi": str(tmp_path / "openapi.json")})
      session.flow_begin("f1")
      result = session.request("POST", "/items")
      # 201 is not among the declared {200} -- http.status-undeclared must fire
      assert len(result["new_findings"]) == 1


  def test_drive_session_run_files_a_finding(tmp_path):
      from flow_review.web.drive import DriveSession

      class FakeShellDriver:
          def run(self, args, stdin=None):
              return {"exit_code": 2, "stdout": "", "stderr": "", "elapsed_ms": 5}

      session = DriveSession(FakeShellDriver(), "cli", tmp_path, tmp_path, False, kind="cli")
      session.flow_begin("f1")
      result = session.run(["list"])
      assert result["title"] == "exit 2"
      assert len(result["new_findings"]) == 1


  def test_drive_session_run_dispatches_help_step_to_check_help(tmp_path):
      from flow_review.web.drive import DriveSession

      class FakeShellDriver:
          def run(self, args, stdin=None):
              return {"exit_code": 1, "stdout": "usage: notes ...", "stderr": "",
                      "elapsed_ms": 5}

      session = DriveSession(FakeShellDriver(), "cli", tmp_path, tmp_path, False, kind="cli")
      session.flow_begin("f1")
      result = session.run(["--help"])
      # cli.help fires (exit 1 instead of 0), never cli.exit-code (stderr is empty but this
      # step is --help, not a generic invocation)
      assert len(result["new_findings"]) == 1


  def test_http_fault_rejects_5xx_kind(tmp_path):
      from flow_review.web.drive import DriveSession

      class FakeHttpDriver:
          def request(self, *a, **k):
              return {"status": 200, "content_type": "application/json", "body": "{}",
                      "elapsed_ms": 5, "url": "http://x/"}

          def simulate_offline(self, active):
              pass

          def simulate_delay(self, ms):
              pass

      session = DriveSession(FakeHttpDriver(), "api", tmp_path, tmp_path, False, kind="api")
      import pytest
      with pytest.raises(ValueError):
          session.fault("5xx", pattern="*")


  def test_cli_fault_is_rejected_outright(tmp_path):
      from flow_review.web.drive import DriveSession

      class FakeShellDriver:
          def run(self, args, stdin=None):
              return {"exit_code": 0, "stdout": "", "stderr": "", "elapsed_ms": 5}

      session = DriveSession(FakeShellDriver(), "cli", tmp_path, tmp_path, False, kind="cli")
      import pytest
      with pytest.raises(ValueError):
          session.fault("slow", delay_ms=100)
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/web/test_drive.py -q`.
  Expected FAIL: `TypeError: DriveSession.__init__() got an unexpected keyword argument 'kind'`.
- [ ] Implement in `web/drive.py`. Add `import ledger` is already imported; add
  `from flow_review.api import measure as api_measure` and
  `from flow_review.shell import measure as cli_measure` to the existing import block
  (lazily inside the methods that need them, matching this module's existing lazy-import style
  for `WebDriver`/`configmod`, so a project with neither an api nor a shell surface never pays
  the import cost). Change `DriveSession.__init__` **additively**: add `kind: str = "web"` and
  `options: dict | None = None` keyword parameters, and two new lines assigning `self.kind` and
  `self._expected_by_route`. Every other parameter, field, and M2 addition already in `__init__`
  (including M2's `self._warned_missing_mocks` and `self._active_fault`) stays exactly as it is
  today -- do not paste a full replacement over it. The two new lines go at the end of the
  existing body:
  ```python
  def __init__(self, driver, surface_id: str, run_dir, project_root, record_enabled: bool,
               tokens: dict | None = None, kind: str = "web", options: dict | None = None):
      self.driver = driver
      self.surface_id = surface_id
      self.run_dir = Path(run_dir)
      self.project_root = Path(project_root)
      self.record_enabled = record_enabled
      self.tokens = tokens
      # ... every existing line here (including M2's self._warned_missing_mocks,
      # self._active_fault, and everything else M2/M3 already added) is unchanged ...
      self.kind = kind  # "web" | "api" | "cli" -- selects the measure rules and evidence shape
      self._expected_by_route: dict[tuple[str, str], list[int]] = {}
      if options and options.get("openapi"):
          from flow_review.api import openapi as openapi_mod

          spec = openapi_mod.load(Path(options["openapi"]))
          for goal in openapi_mod.goals(spec):
              key = (goal["method"], ledger.route_template(goal["path"]))
              self._expected_by_route[key] = goal["expected"]
  ```
  `options["openapi"]` is already an absolute path by the time it reaches here -- `cmd_start`
  absolutises `surface.options["openapi"]` against `project_root` before passing it through
  `--driver-options` (see the `serve()`/`cmd_start` note further down in this task).
  Extract the finding-filing loop already in `_run_checks` into a shared helper (add this new
  method; then change `_run_checks`'s body from its `for finding in findings: ...` loop onward
  to call it -- `_run_checks` keeps computing `route`/`findings` via `measure.check_page` exactly
  as it does today, then ends with `return self._file_findings(findings)`):
  ```python
  def _file_findings(self, findings: list[dict]) -> list[str]:
      new_ids = []
      for finding in findings:
          if self._is_self_inflicted(finding):
              continue
          fp = ledger.fingerprint(self.flow_id or "", finding.get("rule") or "",
                                   finding.get("route") or "", finding.get("locator") or "")
          seen_key = (fp, finding.get("sev"), finding.get("text"))
          if seen_key in self._seen_fingerprints:
              continue
          self._seen_fingerprints.add(seen_key)
          event = events.append(self.run_dir, {
              "type": "finding", "surface_id": self.surface_id, "flow_id": self.flow_id,
              **finding,
          })
          new_ids.append(event["id"])
      return new_ids
  ```
  Add `request` and `run` methods (near `fault`):
  ```python
  def request(self, method: str, path: str, headers: dict | None = None,
              body: str | None = None) -> dict:
      from flow_review import envsetup
      from flow_review.api import measure as api_measure
      from flow_review.api.driver import resolve_auth

      headers = dict(headers or {})
      auth = getattr(self.driver, "auth", None)  # {"header", "env", "prefix"} -- see A-64
      # Resolved here, per call, via the same helper (and the same envsetup.resolve_env path
      # `fill --from-env` uses) that `replay_one`'s request branch (T8) also calls -- never in
      # the DRIVER_FACTORIES factory and never inside HttpDriver itself -- so the value is
      # registered as a secret (and therefore redacted below) at the point it is actually read,
      # and a recorded flow log never carries it.
      secret_names = envsetup.project_secret_names(self.project_root)
      headers.update(resolve_auth(auth, self.project_root, secret_names))
      resp = self.driver.request(method, path, headers, body)
      if self.log is not None:
          actionlog.record_request_step(self.log, method, path, headers, body, resp["status"])
      route = ledger.route_template(path)
      expected = self._expected_by_route.get((method.upper(), route))
      raw_findings = api_measure.check_response(resp, expected, route)
      ref = self._write_evidence("http", f"{self.step_index:04d}.json", json.dumps(
          {"method": method, "path": path, "headers": events.redact(dict(headers or {})),
           "body": events.redact(body) if body else body, "response": resp},
          ensure_ascii=False, indent=2,
      ))
      payloads = [
          {"surface_id": self.surface_id, "flow_id": self.flow_id, **f,
           "evidence": list(f.get("evidence", [])) + [ref]}
          for f in raw_findings
      ]
      new_ids = self._file_findings(payloads)
      self.step_index += 1
      events.append(self.run_dir, {
          "type": "output", "surface_id": self.surface_id,
          "text": f"{method} {path} -> {resp['status']}",
      })
      return {
          "url": resp["url"], "title": f"{resp['status']} {resp['content_type']}",
          "snapshot": resp["body"][:4000], "shot": None,
          "new_findings": new_ids, "console_errors": 0,
      }

  def run(self, args: list[str], stdin: str | None = None) -> dict:
      from flow_review.shell import measure as cli_measure

      res = self.driver.run(args, stdin)
      if self.log is not None:
          actionlog.record_run_step(self.log, args, stdin, res["exit_code"])
      route = args[0] if args else "-"
      if args == ["--help"]:
          # The explorer runs `--help` as an ordinary step whenever it chooses to (never once
          # automatically at `drive start`) -- this step alone is judged against cli.help;
          # every other invocation is judged against cli.exit-code/cli.stderr-on-success.
          raw_findings = cli_measure.check_help(res, route)
      else:
          raw_findings = cli_measure.check_run(res, route)
          if getattr(self.driver, "json_output", False):
              raw_findings += cli_measure.check_json_shape(res, route)
      tail = (res["stdout"] + res["stderr"])[-4000:]
      ref = self._write_evidence("shell", f"{self.step_index:04d}.txt",
                                  f"args={args}\nexit={res['exit_code']}\n{tail}")
      payloads = [
          {"surface_id": self.surface_id, "flow_id": self.flow_id, **f,
           "evidence": list(f.get("evidence", [])) + [ref]}
          for f in raw_findings
      ]
      new_ids = self._file_findings(payloads)
      self.step_index += 1
      events.append(self.run_dir, {
          "type": "output", "surface_id": self.surface_id,
          "text": f"exit {res['exit_code']}\n{tail[-500:]}",
      })
      return {
          "url": None, "title": f"exit {res['exit_code']}",
          "snapshot": tail, "shot": None,
          "new_findings": new_ids, "console_errors": 0,
      }

  def _write_evidence(self, subdir: str, filename: str, text: str) -> str:
      """Returns the run-relative ref (`http/<flow-slug>/<file>` or `shell/<flow-slug>/<file>`)
      so the caller can append it to every finding filed on this step (A-46 evidence refs)."""
      flow_slug = actionlog._slug(self.flow_id or "_")
      safe_text = events.redact(text)[:65536]  # 64 KiB cap, same as HttpDriver's MAX_BODY
      path = self.run_dir / subdir / flow_slug / filename
      path.parent.mkdir(parents=True, exist_ok=True)
      path.write_text(safe_text, encoding="utf-8")
      return path.relative_to(self.run_dir).as_posix()
  ```
  Change `fault` (full replacement) to dispatch by `self.kind`, and never reach `self.driver.page`
  for a non-web kind:
  ```python
  def fault(self, kind: str, pattern: str | None = None, delay_ms: int | None = None) -> dict:
      if self.kind == "api":
          if kind == "offline":
              self.driver.simulate_offline(True)
          elif kind == "slow":
              self.driver.simulate_delay(delay_ms or 0)
          else:
              raise ValueError(
                  f"api surfaces support only fault kind offline/slow, got {kind!r}"
              )
          spec = {"kind": kind, "pattern": pattern, "delay_ms": delay_ms}
          events.append(self.run_dir, {
              "type": "fault", "surface_id": self.surface_id, "flow_id": self.flow_id,
              "fault": spec,
          })
          return {"ok": True, "fault": spec}

      if self.kind == "cli":
          # No `drive fault` is defined for a shell surface (A-41's unhappy-path bind covers
          # api only) -- reject outright rather than silently touching a driver that has no
          # `.page` at all.
          raise ValueError(f"cli surfaces do not support drive fault, got {kind!r}")

      page = self.driver.page
      if kind == "offline":
          faults.inject_offline(page)
          self._offline_active = True
      elif kind == "5xx":
          faults.inject_5xx(page, pattern, status=503)
          self._active_5xx_patterns.append(pattern)
      elif kind == "slow":
          faults.inject_slow(page, pattern, delay_ms)
      else:
          raise ValueError(f"unknown fault kind {kind!r}")
      spec = {"kind": kind, "pattern": pattern, "delay_ms": delay_ms}
      events.append(self.run_dir, {
          "type": "fault", "surface_id": self.surface_id, "flow_id": self.flow_id,
          "fault": spec,
      })
      return {"ok": True, "fault": spec}
  ```
  Add two entries to the existing `DRIVER_FACTORIES` dict (M2 already defines the dict with
  `"playwright"`, `"tauri"`, `"maestro"` keys, each in the A-48 shape `factory(headless: bool,
  viewport: dict | None, options: dict | None = None) -> Driver`; this task only merges in
  `"http"` and `"shell"`, never touches the other three entries):
  ```python
  def _auth_from(options: dict | None) -> dict | None:
      """{"header", "env", "prefix"} naming which env var to resolve -- never the resolved
      value itself. `DriveSession.request` resolves it per call, the same way `fill --from-env`
      resolves a credential, so the value is registered as a secret (and redacted) at the point
      it is actually read, not baked into a long-lived driver object."""
      options = options or {}
      if not (options.get("auth_header") and options.get("auth_env")):
          return None
      return {"header": options["auth_header"], "env": options["auth_env"],
              "prefix": options.get("auth_prefix", "")}


  DRIVER_FACTORIES["http"] = lambda headless, viewport, options=None: HttpDriver(
      base_url=(options or {})["base_url"], auth=_auth_from(options),
      timeout_s=(options or {}).get("timeout_s", 30),
  )
  DRIVER_FACTORIES["shell"] = lambda headless, viewport, options=None: ShellDriver(
      command=(options or {})["command"], cwd=(options or {}).get("cwd", "."),
      timeout_s=(options or {}).get("timeout_s", 30),
      json_output=(options or {}).get("json_output", False),
  )
  ```
  Add the two imports these lambdas need to the top of `web/drive.py`'s import block:
  `from flow_review.api.driver import HttpDriver` and
  `from flow_review.shell.driver import ShellDriver`.

  `serve()`'s signature and its call into `build_driver` need no change in this task: M3 T5
  (A-53) already gave `serve()` the signature `serve(surface_id, run_dir, project_root, *,
  driver_name: str = "playwright", options: dict | None = None, record_enabled=False,
  headless=True, viewport=None, tokens=None)`, which calls `build_driver(driver_name,
  headless=headless, viewport=viewport, options=options or {})` (M3's dispatcher over
  `DRIVER_FACTORIES`) and never loads `.flow-review/config.json` itself; and `cmd_start` already
  spawns the serve subprocess with `--driver surface.driver --driver-options
  json.dumps(surface.options)`. What this task DOES add to `serve()` is the two lines that pass
  the new `kind`/`options` parameters through to the `DriveSession(...)` constructor call
  already inside `serve()`'s body -- find that call and add the two keyword arguments:
  ```python
  kind = "api" if driver_name == "http" else "cli" if driver_name == "shell" else "web"
  session = DriveSession(driver, surface_id, run_dir, project_root, record_enabled,
                          tokens=tokens, kind=kind, options=options)
  ```
  (every other argument on that existing call stays as M2/M3 left it). Also add one line to
  `cmd_start`, right before it builds `--driver-options`: if `surface.driver == "http"` and
  `surface.options.get("openapi")`, absolutise it against `project_root` before serializing --
  `DriveSession.__init__` (above) expects `options["openapi"]` to already be a usable path, not
  one relative to a working directory the spawned subprocess may not share:
  ```python
  driver_options = dict(surface.options)
  if surface.driver == "http" and driver_options.get("openapi"):
      openapi_path = Path(driver_options["openapi"])
      if not openapi_path.is_absolute():
          openapi_path = project_root / openapi_path
      driver_options["openapi"] = str(openapi_path)
  cmd += ["--driver", surface.driver, "--driver-options", json.dumps(driver_options)]
  ```
  (replace whatever line currently serializes `surface.options` directly into `--driver-options`
  with the block above -- every surface whose driver is not `"http"` or has no `openapi` option
  passes through `dict(surface.options)` unchanged). Confirm this by running
  `python -m pytest plugins/flow-review/engine/flow_review/web/test_drive.py -k serve -q`
  after the `DRIVER_FACTORIES`/`serve()`/`cmd_start` edits above; if `serve()`/`cmd_start` do not
  yet match the M3 T5 shape described here in the checkout this task actually runs against (M3
  not yet merged), stop and flag it rather than re-deriving a second, possibly divergent version
  of M3's own function.
  Add `request` and `run` verbs to `build_drive_parser` (after the `"fault"` subparser):
  ```python
  p = sub.add_parser("request")
  _common(p)
  p.add_argument("--method", required=True)
  p.add_argument("path")
  p.add_argument("--header", action="append", default=[], dest="headers_raw")
  p.add_argument("--body")
  p.set_defaults(func=cmd_request)

  p = sub.add_parser("run")
  _common(p)
  p.add_argument("cmd_args", nargs="*")
  p.add_argument("--stdin")
  p.set_defaults(func=cmd_run)
  ```
  Add the two command functions (near `cmd_fault`):
  ```python
  def cmd_request(args: argparse.Namespace) -> dict:
      headers = {}
      for raw in args.headers_raw:
          name, _, value = raw.partition(":")
          headers[name.strip()] = value.strip()
      return _client_call(args, "request", {
          "method": args.method, "path": args.path, "headers": headers, "body": args.body,
      })


  def cmd_run(args: argparse.Namespace) -> dict:
      return _client_call(args, "run", {"args": args.cmd_args, "stdin": args.stdin})
  ```
  Add the two verbs to `_ActionHandler._dispatch` (after the `"fault"` branch):
  ```python
  if verb == "request":
      return session.request(args["method"], args["path"], headers=args.get("headers"),
                              body=args.get("body"))
  if verb == "run":
      return session.run(args["args"], stdin=args.get("stdin"))
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/web/test_drive.py -q`.
  Expected PASS.
- [ ] Verify: `python -m pytest -q -m "web or not web"` from the repo root, all green.
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/web/drive.py plugins/flow-review/engine/flow_review/web/actionlog.py plugins/flow-review/engine/flow_review/web/test_drive.py plugins/flow-review/engine/flow_review/web/test_actionlog.py && git commit -m "feat(drive): request/run verbs for http/shell surfaces (A-46)"`

### Task T8: Replay for http/shell recordings
**Executor:** opus · **Depends:** T7 · **Wave:** 4
**Files:** `plugins/flow-review/engine/flow_review/web/replay.py`,
`plugins/flow-review/engine/flow_review/web/test_replay.py`
**Interfaces:** Consumes `flow_review.driver.build_driver`, `drift.RUNNABLE_DRIVERS` (via
`drift.runnable_surfaces`), `api.driver.resolve_auth`. Produces
`replay._runnable_recording_surfaces` (replaces `_playwright_surfaces`, both call sites).
**Ponytail rung:** 3 (dispatch by driver name, no new abstraction layer beyond what `replay_one`
already has for goto/click/fill).

- [ ] Write the failing tests. Append to `web/test_replay.py`:
  ```python
  def test_replay_one_request_step_clean_when_status_matches():
      from flow_review.web.replay import replay_one

      class FakeHttpDriver:
          def begin_step(self, i):
              pass

          def end_step(self):
              pass

          def request(self, method, path, headers=None, body=None):
              return {"status": 200, "content_type": "application/json", "body": "{}",
                      "elapsed_ms": 5, "url": "http://x" + path}

      log = {"surface_id": "api", "flow_id": "f1", "steps": [
          {"action": "request", "method": "GET", "path": "/items", "headers": {},
           "body": None, "status": 200},
      ]}
      result = replay_one(FakeHttpDriver(), log)
      assert result["status"] == "clean"
      assert result["steps_run"] == 1


  def test_replay_one_request_step_diverges_on_status_mismatch():
      from flow_review.web.replay import replay_one

      class FakeHttpDriver:
          def begin_step(self, i):
              pass

          def end_step(self):
              pass

          def request(self, method, path, headers=None, body=None):
              return {"status": 500, "content_type": "application/json", "body": "{}",
                      "elapsed_ms": 5, "url": "http://x" + path}

      log = {"surface_id": "api", "flow_id": "f1", "steps": [
          {"action": "request", "method": "GET", "path": "/items", "headers": {},
           "body": None, "status": 200},
      ]}
      result = replay_one(FakeHttpDriver(), log)
      assert result["status"] == "divergence"
      assert result["divergence"]["reason"] == "status_mismatch"


  def test_replay_one_run_step_diverges_on_exit_code_mismatch():
      from flow_review.web.replay import replay_one

      class FakeShellDriver:
          def begin_step(self, i):
              pass

          def end_step(self):
              pass

          def run(self, args, stdin=None):
              return {"exit_code": 1, "stdout": "", "stderr": "", "elapsed_ms": 5}

      log = {"surface_id": "cli", "flow_id": "f1", "steps": [
          {"action": "run", "args": ["list"], "stdin": None, "exit_code": 0},
      ]}
      result = replay_one(FakeShellDriver(), log)
      assert result["status"] == "divergence"
      assert result["divergence"]["reason"] == "exit_code_mismatch"
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/web/test_replay.py -q`.
  Expected FAIL: the `"request"`/`"run"` actions fall through `replay_one`'s if/elif ladder
  unhandled, so `steps_run` stays 0 and `status` ends "clean" with no divergence recorded --
  the assertions on `divergence`/`steps_run` fail.
- [ ] In `web/replay.py`, add two new `elif` branches to `replay_one`'s action ladder (insert
  after the existing `elif action == "assert_url":` block, before `steps_run += 1`):
  ```python
              elif action == "request":
                  from flow_review import envsetup
                  from flow_review import ledger as ledger_mod
                  from flow_review.api import measure as api_measure
                  from flow_review.api.driver import resolve_auth

                  # Resolved here, per replayed call, through the exact same helper
                  # `DriveSession.request` uses (A-64) -- a recorded flow log never stores the
                  # resolved credential, only the env var name (inside the surface's own
                  # `options`, read fresh from `project_root` on every replay).
                  auth = getattr(driver, "auth", None)
                  secret_names = envsetup.project_secret_names(project_root)
                  resolved_headers = dict(step.get("headers") or {})
                  resolved_headers.update(resolve_auth(auth, project_root, secret_names))
                  with _step_window(driver, index):
                      resp = driver.request(step["method"], step["path"],
                                            headers=resolved_headers, body=step.get("body"))
                  if resp["status"] != step.get("status"):
                      return ReplayResult(
                          flow_id=flow_id, status="divergence", steps_run=steps_run,
                          divergence={"step_index": index, "locator": "",
                                      "reason": "status_mismatch", "url": step["path"]},
                          findings=findings,
                      )
                  route = ledger_mod.route_template(step["path"])
                  for f in api_measure.check_response(resp, None, route):
                      findings.append({"surface_id": surface_id, "flow_id": flow_id, **f})
              elif action == "run":
                  from flow_review.shell import measure as cli_measure

                  with _step_window(driver, index):
                      res = driver.run(step["args"], stdin=step.get("stdin"))
                  if res["exit_code"] != step.get("exit_code"):
                      return ReplayResult(
                          flow_id=flow_id, status="divergence", steps_run=steps_run,
                          divergence={"step_index": index, "locator": "",
                                      "reason": "exit_code_mismatch",
                                      "url": step["args"][0] if step["args"] else "-"},
                          findings=findings,
                      )
                  route = step["args"][0] if step["args"] else "-"
                  for f in cli_measure.check_run(res, route):
                      findings.append({"surface_id": surface_id, "flow_id": flow_id, **f})
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/web/test_replay.py -q`.
  Expected PASS.
- [ ] Write the failing test for the surface-selection widening:
  ```python
  def test_runnable_recording_surfaces_includes_http_and_shell():
      from flow_review.config import Config, Surface
      from flow_review.web.replay import _runnable_recording_surfaces

      cfg = Config(schema_version=2, generator_version="x", surfaces=[
          Surface(id="web", name="web", kind="ui", driver="playwright", launch=""),
          Surface(id="api", name="api", kind="api", driver="http", launch=""),
          Surface(id="cli", name="cli", kind="cli", driver="shell", launch=""),
          Surface(id="mob", name="mob", kind="ui", driver="pending", launch=""),
      ])
      ids = {s.id for s in _runnable_recording_surfaces(cfg, None)}
      assert ids == {"web", "api", "cli"}
  ```
- [ ] Run it. Expected FAIL: `ImportError: cannot import name '_runnable_recording_surfaces'`.
- [ ] Replace `_launch_driver` and `_playwright_surfaces` (full replacement of both functions):
  ```python
  def _launch_driver(surface, project_root: Path):
      from flow_review.driver import build_driver  # M3 A-53 dispatcher over DRIVER_FACTORIES

      driver = build_driver(surface.driver, headless=True, viewport=None,
                             options=surface.options)
      driver.launch(surface.options.get("base_url"))
      return driver


  def _runnable_recording_surfaces(cfg, surface_id: str | None):
      # Every driver already in drift.RUNNABLE_DRIVERS -- playwright, tauri, maestro, http,
      # shell -- not just the two this milestone adds; a tauri/maestro recording replays the
      # same way a playwright one always has (goto/click/fill/press), just without the
      # playwright-only baseline/variants steps guarded below.
      surfaces = drift.runnable_surfaces(cfg)
      if surface_id is not None:
          surfaces = [s for s in surfaces if s.id == surface_id]
      return surfaces
  ```
  Update every call site inside `replay()`:
  - `surfaces = _playwright_surfaces(cfg, surface_id)` -> `surfaces =
    _runnable_recording_surfaces(cfg, surface_id)`, and its error message from
    `f"no playwright surface named {surface_id!r} in config"` to
    `f"no runnable surface named {surface_id!r} in config"`.
  - `driver = _launch_driver(surface)` -> `driver = _launch_driver(surface, project_root)`.
  - Guard the playwright-only steps (`_health_ok`, the visual-baseline check, and the
    `variants` block) with `if surface.driver == "playwright":` so any non-playwright surface
    (http, shell, and also tauri/maestro) skips straight to `replay_one` and
    `flows_run.add(...)` without a health probe, a screenshot baseline, or device/persona
    variants -- none of which apply beyond a Playwright-driven web surface. The existing
    `for flow_path in flow_files:` loop body's structure (call `replay_one`, extend
    `all_findings`, add to `flows_run` when not a divergence, append to `divergences` on
    divergence) is unchanged for every driver; only the `if result["status"] == "clean":`
    inner block (baseline + variants) becomes `if surface.driver == "playwright" and
    result["status"] == "clean":`.
  - `replay.py` has a second, separate call site for the old `_playwright_surfaces` helper
    inside `replay_log` (the `--log` ephemeral-replay path), around the existing line
    `surfaces = [s for s in _playwright_surfaces(cfg, None) if s.id == log["surface_id"]]`.
    Update that line to `surfaces = [s for s in _runnable_recording_surfaces(cfg, None)
    if s.id == log["surface_id"]]` too, and its error message from `f"no playwright surface
    named {log['surface_id']!r} in config"` to `f"no runnable surface named
    {log['surface_id']!r} in config"`. `replay_log` stays playwright-oriented otherwise (its
    own `_health_ok`/`_launch_driver` calls are unchanged by this task) -- this is purely the
    lookup-by-name fix so an http/shell surface's `--log` replay does not fail with "no
    playwright surface" before it even gets that far.
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/web/test_replay.py -q`.
  Expected PASS.
- [ ] Verify: `python -m pytest -q -m "web or not web"` from the repo root, all green.
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/web/replay.py plugins/flow-review/engine/flow_review/web/test_replay.py && git commit -m "feat(replay): replay recorded http/shell flows (A-46)"`

### Task T10: Docs -- surfaces/testing references, explorer/cold-eyes probing paragraphs
**Executor:** haiku · **Depends:** T7, T9 · **Wave:** 4
**Files:** `plugins/flow-review/skills/flow-review/references/surfaces.md`,
`plugins/flow-review/skills/flow-review/references/testing.md`,
`plugins/flow-review/agents/fr-explorer.md`,
`plugins/flow-review/agents/fr-cold-eyes.md`
**Interfaces:** none (docs only). Must keep `test_cli_parity.py` green -- every
`` `flow-review ...` `` span added below uses only real argparse flags from T7.
**Ponytail rung:** 1 (skip -- fills in stub sections the M1 docs already reserved for this).

- [ ] In `references/surfaces.md`, replace:
  ```
  ## Driver: shell

  pending-driver until M2/M3/M4 (A-14).

  ## Driver: http

  pending-driver until M2/M3/M4 (A-14).
  ```
  with:
  ```
  ## Driver: shell

  Drives a command-line tool as a subprocess (A-41/A-46).

  **Launch.** Nothing is launched ahead of time -- each drive verb runs `<options.command>
  <args...>` fresh via `subprocess.run`, with `options.cwd` as the working directory.

  **Proven attached when.** `flow-review drive run --surface ID -- --help` starts the process
  and produces output; there is no persistent process to attach to.

  **Evidence it can produce.** exit code, stdout, stderr (tail), elapsed time. No screenshots --
  `drive look --shot` is never issued against a shell surface.

  ## Driver: http

  Drives an HTTP API surface with `urllib.request` (A-41/A-46) -- no client library dependency.

  **Launch.** Nothing is launched by flow-review itself; `options.base_url` must already be
  reachable (start the service the same way you would to hit it with curl).

  **Proven attached when.** `flow-review drive request --surface ID --method GET /` (or the
  first OpenAPI operation's path) returns any HTTP status, including a 4xx/5xx -- reachability
  is the bar, not a 200.

  **Evidence it can produce.** status code, response headers/body (redacted, capped at 64 KiB),
  elapsed time. No screenshots.
  ```
- [ ] In `references/testing.md`, replace:
  ```
  ### shell / http

  pending-driver until M2/M3/M4 (A-14).
  ```
  with:
  ```
  ### shell

  - There is no persistent process between actions: `drive run` spawns a fresh subprocess every
    call. A state change (a note added, a file written) must be verified by a *second* `drive
    run` that reads the state back -- never assumed from the first call's exit code alone.
  - `--help` is judged against `cli.help` exactly when the explorer chooses to run it
    (`flow-review drive run --surface ID -- --help`), like any other invocation -- there is no
    separate setup-time or once-per-`drive start` check; run it as a step whenever the flow
    calls for it.
  - stdin is passed once per invocation (`--stdin`); an interactive prompt with no way to answer
    it non-interactively is a product-stuck finding (`testing.md` section 3), not a harness bug.

  ### http

  - A non-2xx status is not automatically a finding -- read `references/lenses/api.md`'s
    `error shapes`/`status codes` lenses before deciding a 4xx is wrong; only a 5xx or an
    undeclared status against the surface's own OpenAPI file is engine-checked
    (`http.5xx`/`http.status-undeclared`).
  - `drive fault --kind offline` and `--kind slow` are the only supported fault kinds for an
    http surface (`--kind 5xx` raises an error) -- a 5xx from the real service is exercised by
    finding a route that actually returns one, never simulated.
  - The action log's captured body is truncated at 64 KiB; a claim about content past that point
    is not evidence you actually captured.
  ```
- [ ] In `plugins/flow-review/agents/fr-explorer.md`, add a paragraph (after the existing web
  `drive` interface paragraph) covering api/cli probing:
  ```
  **Driving an api or cli surface uses the same `drive` CLI**, with `request`/`run` in place of
  `goto`/`click`/`fill`/`press`: `flow-review drive request --surface ID --method GET /items`
  and `flow-review drive run --surface ID -- list`. Cold-eyes pass 2 (docs) for an api surface
  reads `.flow-review/config.json`'s `options.openapi` and calls `api/openapi.py::goals` for the
  operation list; there is no equivalent docs pass for a cli surface beyond its own `--help`.
  ```
- [ ] In `plugins/flow-review/agents/fr-cold-eyes.md`, add a paragraph (after its existing web
  `drive` paragraph):
  ```
  **For an api surface**, pass 2 (docs) runs every operation `api/openapi.py::goals` returns
  against the live surface via `flow-review drive request`, in addition to the cold-eyes probe
  set (`/`, `/health`, `/docs`, `/openapi.json`). **For a cli surface**, the only docs pass is
  `flow-review drive run --surface ID -- --help` followed by trying each subcommand it lists.
  ```
- [ ] Run `python -m pytest plugins/flow-review/skills/flow-review/test_cli_parity.py plugins/flow-review/skills/flow-review/test_references.py -q`. Expected PASS (every span above uses
  `--method`, `--stdin` and the bare `path`/`cmd_args` positional exactly as T7's parser defines
  them).
- [ ] Verify: `python -m pytest -q -m "web or not web"` from the repo root, all green.
- [ ] Commit: `git add plugins/flow-review/skills/flow-review/references/surfaces.md plugins/flow-review/skills/flow-review/references/testing.md plugins/flow-review/agents/fr-explorer.md plugins/flow-review/agents/fr-cold-eyes.md && git commit -m "docs: fill in shell/http driver reference and explorer/cold-eyes probing"`

### Task T11: Budget priors for api/cli roles
**Executor:** sonnet · **Depends:** T6 · **Wave:** 4
**Files:** `plugins/flow-review/engine/flow_review/budget.py`,
`plugins/flow-review/engine/flow_review/test_budget.py`,
`plugins/flow-review/engine/flow_review/plan.py`,
`plugins/flow-review/engine/flow_review/test_plan.py`
**Interfaces:** Extends `budget._prior` to accept a surface kind; extends `budget.estimate`'s
`PlanUnit` with an optional `kind` key; `plan.py::plan` now puts each surface's own `kind` into
every `PlanUnit` it builds.
**Ponytail rung:** 5 (one lookup table keyed by kind, one extra dict key threaded through, no
new module).

- [ ] Write the failing test. Append to `test_budget.py`:
  ```python
  def test_api_and_cli_explorer_priors_are_60pct_of_web():
      from flow_review.budget import PRIORS_TOKENS_PER_UNIT, _prior

      web_explorer = PRIORS_TOKENS_PER_UNIT["explorer"]
      assert _prior("explorer", kind="api") == round(web_explorer * 0.6)
      assert _prior("explorer", kind="cli") == round(web_explorer * 0.6)
      assert _prior("explorer", kind="ui") == web_explorer
      assert _prior("cold-eyes", kind="api") == round(PRIORS_TOKENS_PER_UNIT["cold-eyes"] * 0.6)
      assert _prior("lens", kind="cli") == round(PRIORS_TOKENS_PER_UNIT["lens"] * 0.6)
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/test_budget.py -q`. Expected
  FAIL: `TypeError: _prior() got an unexpected keyword argument 'kind'`.
- [ ] In `budget.py`, add below `PRIORS_TOKENS_PER_UNIT`:
  ```python
  # text-only explorer/cold-eyes/lens priors for api/cli surfaces run at 60% of the web ones --
  # no screenshots, no DOM scan, a smaller evidence bundle per call.
  # ponytail: one ratio, revisited by the M5 benchmark once real usage_history exists.
  _TEXT_ONLY_ROLE_RATIO = {"api": 0.6, "cli": 0.6}
  _KIND_SCALED_ROLES = ("explorer", "cold-eyes", "lens")
  ```
  Replace `_prior`:
  ```python
  def _prior(role: str, kind: str = "ui") -> int:
      base = PRIORS_TOKENS_PER_UNIT.get(role, 0)
      if role in _KIND_SCALED_ROLES and kind in _TEXT_ONLY_ROLE_RATIO:
          return round(base * _TEXT_ONLY_ROLE_RATIO[kind])
      return base
  ```
  Update the two callers so a surface's `kind` reaches `_prior`: `_per_unit_estimate` gains a
  `kind: str = "ui"` parameter, threading it to `_prior(role, kind=kind)`; `check`'s call to
  `_prior(next_role)` stays unchanged (budget-cap gating has no surface context, so it keeps the
  `"ui"` default -- a slight over-estimate for an api/cli surface's cap check, never an
  under-estimate, which is the safe direction). `estimate`'s call to `_per_unit_estimate(
  surface_id, role, project_root)` needs a kind; since `estimate`'s `PlanUnit` carries no kind
  today, add `kind: str = "ui"` to `PlanUnit` (TypedDict, all keys required by convention here
  stay required except this one being additive is safe since TypedDict without
  `total=False` still allows callers who already build `{"surface_id":..., "role":...,
  "count":...}` dicts to pass type-checking loosely at runtime -- Python does not enforce
  TypedDict at runtime), and change `estimate`'s loop to `kind = unit.get("kind", "ui")` then
  `per_unit = _per_unit_estimate(surface_id, role, project_root, kind=kind)`.
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/test_budget.py -q`. Expected
  PASS.
- [ ] Write the failing test. Append to `test_plan.py`:
  ```python
  def test_plan_units_carry_the_surfaces_own_kind(tmp_path, monkeypatch):
      from flow_review import config as configmod
      from flow_review.plan import plan

      cfg_dir = tmp_path / ".flow-review"
      cfg_dir.mkdir()
      cfg = configmod.Config(schema_version=2, generator_version="x", surfaces=[
          configmod.Surface(id="api", name="api", kind="api", driver="http", launch="",
                             options={"base_url": "http://localhost:9000"}),
      ])
      configmod.save(cfg, cfg_dir / "config.json")

      captured = {}
      import flow_review.budget as budget_mod
      real_estimate = budget_mod.estimate

      def spy_estimate(plan_units, project_root):
          captured["units"] = plan_units
          return real_estimate(plan_units, project_root)

      monkeypatch.setattr(budget_mod, "estimate", spy_estimate)
      plan(tmp_path, "quick", goal="list items")
      assert all(u["kind"] == "api" for u in captured["units"])
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/test_plan.py -q`. Expected
  FAIL: `KeyError: 'kind'` (the current `plan_units` dict has no `kind` key).
- [ ] In `plan.py`, inside `plan()`'s per-surface loop, change:
  ```python
          plan_units = [
              {"surface_id": surface.id, "role": u["role"], "count": u["count"]}
              for u in units
          ]
  ```
  to:
  ```python
          plan_units = [
              {"surface_id": surface.id, "role": u["role"], "count": u["count"],
               "kind": surface.kind}
              for u in units
          ]
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/test_plan.py plugins/flow-review/engine/flow_review/test_budget.py -q`.
  Expected PASS.
- [ ] Verify: `python -m pytest -q -m "web or not web"` from the repo root, all green.
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/budget.py plugins/flow-review/engine/flow_review/test_budget.py plugins/flow-review/engine/flow_review/plan.py plugins/flow-review/engine/flow_review/test_plan.py && git commit -m "feat(budget): api/cli text-only priors at 60% of web, plan units carry surface kind"`

### Task T12: Lock in the dashboard's existing output-lane support
**Executor:** haiku · **Depends:** T7 · **Wave:** 4
**Files:** `plugins/flow-review/engine/flow_review/dashboard/test_state.py`
**Interfaces:** none -- `dashboard/state.py`'s `_Lane.output` field and the `"output"` event
type it already folds, and `app.js`'s `lane.output` rendering, already exist; this task only
adds the regression test that would have caught either regressing once http/shell surfaces
start emitting `type: output` events for real.
**Ponytail rung:** 1 (skip -- no code change; `state.py` already carries `output: str | None =
None` on `_Lane` and already folds a `type: "output"` event into it at the line `elif kind ==
"output": ln.output = ev.get("text") or ln.output`, and the JSON it returns already includes
`"output": l.output` per lane).

- [ ] Write the test. Append to `dashboard/test_state.py`:
  ```python
  def test_fold_exposes_output_for_a_non_web_lane(tmp_path):
      from flow_review.config import Config, Surface
      from flow_review.dashboard.state import fold

      run_dir = tmp_path / "run"
      run_dir.mkdir()
      (tmp_path / ".flow-review").mkdir()
      (run_dir / "events.jsonl").write_text(
          '{"type": "run", "ts": "2026-01-01T00:00:00.000Z", "mode": "auto", '
          '"surfaces": [{"id": "api", "kind": "api"}]}\n'
          '{"type": "output", "ts": "2026-01-01T00:00:01.000Z", "surface_id": "api", '
          '"text": "GET /items -> 200"}\n'
      )
      cfg = Config(schema_version=2, generator_version="x", surfaces=[
          Surface(id="api", name="api", kind="api", driver="http", launch=""),
      ])
      state = fold(tmp_path, run_dir, cfg)
      lane = next(l for l in state["lanes"] if l["surface_id"] == "api")
      assert lane["output"] == "GET /items -> 200"
      assert lane["shot"] is None
  ```
- [ ] Run `python -m pytest plugins/flow-review/engine/flow_review/dashboard/test_state.py -q`.
  Expected PASS immediately (no production code change) -- if it fails, `state.py`'s existing
  `output` support has regressed and must be restored to the shape described above before this
  task can close.
- [ ] Verify: `python -m pytest -q -m "web or not web"` from the repo root, all green.
- [ ] Commit: `git add plugins/flow-review/engine/flow_review/dashboard/test_state.py && git commit -m "test(dashboard): lock in output-lane folding for http/shell surfaces"`

## Checkpoints

### Task CP1: M4 checkpoint
**Executor:** opus · **Depends:** T1-T12 · **Wave:** 5

- [ ] Run the full suite from the repo root: `python -m pytest -q -m "web or not web"`. Every
  test must pass; note the total count against the 513 baseline in shared.md (expect ~560+ with
  this milestone's new tests).
- [ ] Clean-venv install (PowerShell): `uv venv $env:TEMP\frv-m4 ; uv pip install --python
  $env:TEMP\frv-m4\Scripts\python.exe "plugins/flow-review/engine[web]"`, then from a directory
  outside the repo: `$env:TEMP\frv-m4\Scripts\flow-review.exe --help` exits 0.
- [ ] Copy the fixture out of the repo before running or editing anything in it: `Copy-Item
  plugins/flow-review/engine/fixtures/apiapp $env:TEMP\frv-m4-apiapp -Recurse` and `Copy-Item
  plugins/flow-review/engine/fixtures/cliapp $env:TEMP\frv-m4-cliapp -Recurse`. Every step below
  runs against these copies, never against the tracked repo fixture -- so a checkpoint run's
  `notes.json` scratch file or a deliberately-broken planted status never dirties `git status`.
- [ ] Headless run against the copied `apiapp`: start `python $env:TEMP\frv-m4-apiapp\server.py
  8099` in the background, then from `$env:TEMP\frv-m4-apiapp` run `claude -p "/flow-review
  quick list items and export them" --plugin-dir <repo>/plugins/flow-review`. Confirm the
  resulting run's `findings.json`/`events.jsonl` contains `http.5xx`, `http.status-undeclared`,
  `http.content-type`, and `http.slow`. Confirm the dashboard lane for the api surface shows
  text output, never a screenshot placeholder. Confirm no `.env`/secret value appears anywhere
  under the run directory (`grep -r` for any registered secret value returns nothing).
- [ ] Headless run against the copied `cliapp`: from `$env:TEMP\frv-m4-cliapp`, run `claude -p
  "/flow-review quick add a note and list it" --plugin-dir <repo>/plugins/flow-review`. Confirm
  the ledger contains `cli.help`, `cli.exit-code`, `cli.stderr-on-success`, `cli.json-shape`.
- [ ] `flow-review replay` on a recorded api flow, against the copied `apiapp`: with `record:
  true` on the apiapp surface, run one flow to record it, then run `flow-review replay --surface
  api` and confirm exit 0; edit `$env:TEMP\frv-m4-apiapp\server.py`'s planted `/items/{id}`
  status for a recorded id (the copy, never `plugins/flow-review/engine/fixtures/apiapp/server.py`
  itself), restart the copied server, re-run `flow-review replay --surface api`, and confirm
  exit 1 (a new finding) or exit 2 (a status-mismatch divergence, if the recorded flow's
  `expected` status was hardcoded to the old value).
- [ ] File any gap found as a new task appended to this plan (do not silently patch during the
  checkpoint) and re-run the affected task's verify step before closing CP1.

## Appendix A: Decisions log
Extends the M2 plan's Appendix A (A-35..A-47) and the M3 plan's (A-53..A-58).

| # | Topic | Decision |
|---|---|---|
| A-59 | Shell driver package name (resolved by the orchestrator) | `flow_review/cli.py` is the engine entry point and stays; the shell driver lives in the package `flow_review/shell/` (`shell/driver.py::ShellDriver`, `shell/measure.py::check_run`), matching the driver name `shell` and the evidence prefix `shell/<flow>/<step>.txt`. The shared Canonical Interfaces' `cli/driver.py` and `cli/measure.py` read as `shell/...`. |
| A-60 | `DriveSession` generalization (bound by orchestrator, restated) | One `DriveSession` class (A-46) gains additive `kind: str = "web"` and an optional `options` (a dict, default `None`) constructor parameter, plus a shared `_file_findings` helper factored out of the existing web-only `_run_checks`, rather than a `DriveSession` subclass per driver kind -- matches A-46's "one class" instruction. `kind` takes surface-kind values `"web"`/`"api"`/`"cli"` (never the driver names `"http"`/`"shell"`), set by `serve()` from `driver_name`. `fault`'s per-kind validation (api supports only offline/slow; cli supports none) lives in the same method via `if self.kind == "api"` then `elif self.kind == "cli": raise` then the existing page-based web logic -- the web branch's `self.driver.page` access is never reached for a non-web kind. |
| A-61 | `serve()`/`cmd_start` driver selection (restated from M3 T5, A-53) | `web/drive.py::serve()` already takes `driver_name: str = "playwright"` and an optional `options` dict (default `None`) and calls M3's `build_driver(driver_name, headless=headless, viewport=viewport, options=options or {})` -- `serve()` never loads `.flow-review/config.json` itself. `cmd_start` already spawns the serve subprocess with `--driver surface.driver --driver-options json.dumps(surface.options)` (M3 T5 design, now A-53). T7 adds `"http"`/`"shell"` entries to `DRIVER_FACTORIES` (which `build_driver` already dispatches into by name), threads `kind`/`options` through to the existing `DriveSession(...)` call inside `serve()`, and has `cmd_start` absolutise `surface.options["openapi"]` against `project_root` before serializing `--driver-options`, so `DriveSession.__init__`'s one-time `openapi.load(...)` call always receives a path that resolves regardless of the spawned subprocess's own working directory. |
| A-62 | Http fault surface (bound by m4 brief, restated) | `drive fault` on an http surface accepts only `--kind offline` (points requests at a closed local port) and `--kind slow` (a client-side `time.sleep` before sending); `--kind 5xx` raises `ValueError` -- a real 5xx is exercised by finding a route that actually returns one, per the m4 brief's explorer-side-unhappy-paths bind. A cli surface accepts no fault kind at all -- `drive fault` on one always raises `ValueError` before touching the driver. |
| A-63 | Evidence write path for http/shell (bound by orchestrator, restated) | `DriveSession._write_evidence` writes the evidence file (`self.run_dir / "http" / <flow-slug> / <step>.json` or `.../ "shell" / <flow-slug> / <step>.txt`, `flow_id` slugged via `actionlog._slug` and the text passed through `events.redact` and capped at 64 KiB) from inside `DriveSession.request`/`.run` themselves, rather than through a generic "evidence writer" abstraction -- there are exactly two shapes (A-46), and a third would only ever be added alongside a third driver. It returns the run-relative ref, which the caller appends to every finding filed on that step (`finding["evidence"].append(ref)`) so a finding's evidence always points back at the exact request/invocation that produced it. |
| A-64 | Http auth resolution timing (bound by orchestrator, restated) | `DRIVER_FACTORIES["http"]` builds `HttpDriver` with `auth = _auth_from(options)` = `{"header", "env", "prefix"}` or `None` -- the env var NAME only, never its value. Both `DriveSession.request` (live, T7) and `replay_one`'s `request` branch (recorded, T8) resolve the value every call through the same shared helper, `api/driver.py::resolve_auth(auth, project_root, secret_names)`, which itself calls `envsetup.resolve_env` -- the same path `fill --from-env` already uses -- and merges the header into that one call before invoking `driver.request(...)`. `HttpDriver.request`'s own auth block (T4, `{"header", "value"}`, pre-resolved) is untouched and simply never fires for a factory-built driver, since that shape has no `"value"` key -- it stays live only for direct construction (tests, or a caller outside `DriveSession`/`replay_one`). A recorded flow log never stores the resolved value, only the env var name (inside the surface's `options`, not the log). |

## QUESTIONS

- none (the package name, the `options.openapi` resolution and the `_playwright_surfaces` rename were resolved by the orchestrator: see A-59 and T6).
