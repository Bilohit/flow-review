"""`flow-review drive`: localhost session server + thin client so agents drive the browser
through the engine (A-24). The engine records, redacts and measures every action."""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

from flow_review import envsetup, events
from flow_review.web import actionlog, faults, measure

MAX_BODY = 64 * 1024  # an action POST is a few hundred bytes to a few KiB (a fill value)


class DriveSession:
    def __init__(self, driver, surface_id: str, run_dir, project_root, record_enabled: bool,
                 tokens: dict | None = None):
        self.driver = driver
        self.surface_id = surface_id
        self.run_dir = Path(run_dir)
        self.project_root = Path(project_root)
        self.record_enabled = record_enabled
        self.tokens = tokens
        self.log = None
        self.flow_id = None
        self.step_index = 0
        self._offline_active = False
        self._active_5xx_patterns: list[str] = []

    def flow_begin(self, flow_id: str) -> dict:
        self.flow_id = flow_id
        self.log = actionlog.new_log(self.surface_id, flow_id)
        self.step_index = 0
        events.append(self.run_dir, {
            "type": "step", "surface_id": self.surface_id, "flow_id": flow_id,
            "step": "flow-begin",
        })
        return {"flow_id": flow_id}

    def flow_end(self, flow_id: str, status: str) -> dict:
        log_path = None
        if self.log is not None:
            log_path = actionlog.save(self.log, self.run_dir, self.project_root,
                                       self.record_enabled)
        events.append(self.run_dir, {
            "type": "step", "surface_id": self.surface_id, "flow_id": flow_id,
            "step": "flow-end", "status": status,
        })
        self.log = None
        self.flow_id = None
        return {"flow_id": flow_id, "status": status,
                "log_path": str(log_path) if log_path else None}

    def goto(self, path: str) -> dict:
        return self._act("goto", lambda: self.driver.goto(path), url_hint=path)

    def click(self, locator: dict) -> dict:
        return self._act("click", lambda: self.driver.click(locator), locator=locator)

    def fill(self, locator: dict, text: str | None = None, from_env: str | None = None) -> dict:
        is_secret = bool(self.driver.is_password(locator))
        if from_env is not None:
            value = envsetup.resolve_env(from_env, self.project_root,
                                         envsetup.project_secret_names(self.project_root))
            if value is None:
                raise ValueError(f"env var {from_env!r} is not set in the environment or "
                                 f".flow-review/.env")
            is_secret = True
        else:
            value = text or ""
            if is_secret:
                events.register_secret(value)
        return self._act("fill", lambda: self.driver.fill(locator, value, secret=is_secret),
                          locator=locator, value=value, secret=is_secret, from_env=from_env)

    def press(self, key: str) -> dict:
        return self._act("press", lambda: self.driver.press(key), value=key)

    def look(self, shot: bool = False) -> dict:
        result = self._after("look", step_index=None, record=False)
        if shot:
            self.step_index += 1
            path = self.run_dir / "drive" / self.surface_id / f"shot-{self.step_index:04d}.png"
            self.driver.screenshot(path)
            events.append(self.run_dir, {
                "type": "shot", "surface_id": self.surface_id, "step": self.step_index,
                "path": str(path),
            })
            result["shot"] = str(path)
        return result

    def fault(self, kind: str, pattern: str | None = None, delay_ms: int | None = None) -> dict:
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

    def clear_faults(self) -> dict:
        faults.clear_faults(self.driver.page)
        self._offline_active = False
        self._active_5xx_patterns = []
        spec = {"kind": "clear"}
        events.append(self.run_dir, {
            "type": "fault", "surface_id": self.surface_id, "flow_id": self.flow_id,
            "fault": spec,
        })
        return {"ok": True, "fault": spec}

    def _act(self, action, op, *, locator=None, value=None, secret=False, url_hint=None,
             from_env=None):
        step = self.step_index
        self.step_index += 1
        self.driver.begin_step(step)
        try:
            op()
        finally:
            self.driver.end_step()
        return self._after(action, step_index=step, locator=locator, value=value,
                            secret=secret, url_hint=url_hint, from_env=from_env)

    def _after(self, action, *, step_index, locator=None, value=None, secret=False,
               url_hint=None, record=True, from_env=None):
        if record and self.log is not None:
            log_locator = dict(locator) if locator else None
            if log_locator is not None and secret:
                log_locator["secret"] = True
            actionlog.record_step(
                self.log, action, locator=log_locator,
                value=value,  # record_step redacts (and registers) when locator["secret"]
                url=url_hint or self._current_url(), from_env=from_env,
            )
        new_ids = self._run_checks(step_index)
        return self._result(new_ids)

    def _run_checks(self, step_index) -> list:
        # A-6: the route is the URL path only, so fingerprints match replay's and survive a
        # port change between runs.
        route = urlparse(self._current_url() or "").path or "/"
        findings = measure.check_page(
            self.driver, self.surface_id, self.flow_id, route, self.tokens, step_index,
        )
        new_ids = []
        for finding in findings:
            if self._is_self_inflicted(finding):
                continue
            event = events.append(self.run_dir, {
                "type": "finding", "surface_id": self.surface_id, "flow_id": self.flow_id,
                **finding,
            })
            new_ids.append(event["id"])
        return new_ids

    def _is_self_inflicted(self, finding: dict) -> bool:
        # A fault we injected ourselves must not surface as a product finding (it would be a
        # false P0 against the app for an error the tool made up): the point of `drive fault` is
        # to see how the app handles the failure, not to report the failure we caused.
        rule = finding.get("rule")
        if rule == "console.error" and (self._offline_active or self._active_5xx_patterns):
            # Only the browser's own notice for the request we failed; an app error (an uncaught
            # exception while offline) is exactly what the fault is there to expose, so it files.
            return (finding.get("text") or "").startswith("Failed to load resource")
        if rule == "http.5xx" and self._active_5xx_patterns:
            url = self._finding_url(finding)
            if url is not None:
                return any(fnmatch.fnmatch(url, pattern)
                           for pattern in self._active_5xx_patterns)
        return False

    def _finding_url(self, finding: dict) -> str | None:
        # http.5xx findings carry no direct "url" field (measure.check_http_status's payload has
        # rule/route/locator/sev/text/evidence/disposition only); the url is inside evidence[0],
        # which check_http_status builds as json.dumps(network-log entry).
        evidence = finding.get("evidence") or []
        if not evidence:
            return None
        try:
            entry = json.loads(evidence[0])
        except (TypeError, ValueError):
            return None
        return entry.get("url") if isinstance(entry, dict) else None

    def _current_url(self) -> str | None:
        page = getattr(self.driver, "page", None)
        return getattr(page, "url", None) if page is not None else None

    def _result(self, new_ids: list) -> dict:
        page = getattr(self.driver, "page", None)
        title = None
        if page is not None:
            title_fn = getattr(page, "title", None)
            title = title_fn() if callable(title_fn) else None
        snap = self.driver.snapshot()
        text = snap.get("aria") if isinstance(snap, dict) else None
        if not isinstance(text, str):
            text = json.dumps(snap, ensure_ascii=False)
        snapshot = events.redact(text)[:4000]
        return {
            "url": self._current_url(),
            "title": title,
            "snapshot": snapshot,
            "shot": None,
            "new_findings": new_ids,
            "console_errors": len(self.driver.console_errors()),
        }


def _default_driver_factory(headless: bool, viewport: dict | None):
    from flow_review.web.driver import WebDriver
    return WebDriver(headless=headless, viewport=viewport)


class _ActionHandler(BaseHTTPRequestHandler):
    session: "DriveSession" = None
    server_ref: HTTPServer = None

    def log_message(self, fmt, *args) -> None:
        pass  # request bodies may carry secrets; never let BaseHTTPRequestHandler log them

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length > MAX_BODY:
            self.close_connection = True
            self._respond(413, {"error": "body too large"})
            return
        body = self.rfile.read(length) if length else b"{}"  # drain first: replying mid-upload
                                                               # aborts the socket on Windows
        # CSRF: reject any request carrying an Origin header. Browser pages (including
        # third-party script inside the app under test in the Playwright browser) always send
        # one; the thin CLI client (urllib) never does, so this never blocks a legitimate call.
        if self.headers.get("Origin") is not None:
            self._respond(403, {"error": "forbidden origin"})
            return
        try:
            payload = json.loads(body.decode("utf-8"))
        except ValueError:
            self._respond(400, {"error": "invalid JSON"})
            return
        verb = payload.get("verb")
        args = payload.get("args", {})
        try:
            result = self._dispatch(verb, args)
        except Exception as exc:
            self._respond(500, {"error": str(exc)})
            return
        self._respond(200, result)
        if verb == "stop":
            threading.Thread(target=type(self).server_ref.shutdown, daemon=True).start()

    def _dispatch(self, verb: str, args: dict) -> dict:
        session = type(self).session
        if verb == "goto":
            return session.goto(args["path"])
        if verb == "click":
            return session.click(args["locator"])
        if verb == "fill":
            return session.fill(args["locator"], text=args.get("text"),
                                 from_env=args.get("from_env"))
        if verb == "press":
            return session.press(args["key"])
        if verb == "look":
            return session.look(shot=args.get("shot", False))
        if verb == "fault":
            if args.get("clear"):
                return session.clear_faults()
            return session.fault(args["kind"], pattern=args.get("pattern"),
                                  delay_ms=args.get("delay_ms"))
        if verb == "flow-begin":
            return session.flow_begin(args["flow"])
        if verb == "flow-end":
            return session.flow_end(args["flow"], args.get("status", "ok"))
        if verb == "stop":
            try:
                session.driver.close()
            except Exception:
                pass
            return {"stopped": True}
        raise ValueError(f"unknown verb {verb!r}")

    def _respond(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def make_server(host: str, port: int, session: DriveSession) -> HTTPServer:
    handler = type("_BoundActionHandler", (_ActionHandler,), {"session": session})
    httpd = HTTPServer((host, port), handler)
    handler.server_ref = httpd
    return httpd


def serve(surface_id: str, run_dir, project_root, base_url: str, *,
          record_enabled: bool = False, headless: bool = True, viewport: dict | None = None,
          tokens: dict | None = None, driver_factory=_default_driver_factory) -> None:
    run_dir = Path(run_dir)
    driver = driver_factory(headless, viewport)
    driver.launch(base_url)
    session = DriveSession(driver, surface_id, run_dir, Path(project_root), record_enabled,
                            tokens=tokens)

    httpd = make_server("127.0.0.1", 0, session)
    port = httpd.server_address[1]

    state_dir = run_dir / "drive"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / f"{surface_id}.json"
    state_path.write_text(json.dumps({"port": port, "pid": os.getpid()}))

    try:
        httpd.serve_forever(poll_interval=0.1)
    finally:
        try:
            driver.close()
        except Exception:
            pass
        state_path.unlink(missing_ok=True)


def _state_path(run_dir, surface_id: str) -> Path:
    return Path(run_dir) / "drive" / f"{surface_id}.json"


def _read_state(run_dir, surface_id: str) -> dict | None:
    path = _state_path(run_dir, surface_id)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        # os.kill(pid, 0) on Windows is TerminateProcess(pid, 0) -- it would KILL the process.
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _post(port: int, verb: str, args: dict) -> dict:
    body = json.dumps({"verb": verb, "args": args}).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/action", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            message = json.loads(exc.read().decode("utf-8")).get("error") or str(exc)
        except ValueError:
            message = str(exc)
        raise RuntimeError(message) from None


def _client_call(args: argparse.Namespace, verb: str, payload: dict) -> dict:
    state = _read_state(args.run_dir, args.surface)
    if state is None:
        raise RuntimeError(
            f"no drive session for {args.surface!r}; run 'flow-review drive start' first"
        )
    return _post(state["port"], verb, payload)


def _locator_from_args(args: argparse.Namespace) -> dict:
    if getattr(args, "role", None):
        return {"role": args.role, "name": args.name}
    if getattr(args, "testid", None):
        return {"testid": args.testid}
    if getattr(args, "css", None):
        return {"css": args.css}
    raise ValueError("one of --role/--name, --testid or --css is required")


def cmd_start(args: argparse.Namespace) -> dict:
    from flow_review import config as configmod

    run_dir = Path(args.run_dir)
    project_root = Path(args.project_root)

    state = _read_state(run_dir, args.surface)
    if state is not None and _pid_alive(state["pid"]):
        return {"surface_id": args.surface, "port": state["port"]}

    cfg = configmod.load(project_root / ".flow-review" / "config.json")
    surface = next((s for s in cfg.surfaces if s.id == args.surface), None)
    if surface is None:
        raise ValueError(f"no surface {args.surface!r} in config")
    base_url = surface.options.get("base_url")
    if not base_url:
        raise ValueError(f"surface {args.surface!r} has no options.base_url")
    record_enabled = bool(args.record or surface.record)
    viewport_list = surface.options.get("viewport") or []
    viewport = viewport_list[0] if viewport_list else None
    tokens_file = surface.options.get("tokens_file")
    tokens_path = (project_root / tokens_file) if tokens_file else None

    (run_dir / "drive").mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "flow_review.web.drive", "serve",
        "--surface", args.surface, "--run", str(run_dir), "--project", str(project_root),
        "--base-url", base_url,
    ]
    if record_enabled:
        cmd.append("--record")
    if viewport is not None:
        cmd += ["--viewport-width", str(viewport["width"]),
                 "--viewport-height", str(viewport["height"])]
    if tokens_path is not None:
        cmd += ["--tokens-file", str(tokens_path)]

    popen_kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.DETACHED_PROCESS
    else:
        popen_kwargs["start_new_session"] = True
    subprocess.Popen(cmd, **popen_kwargs)

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        state = _read_state(run_dir, args.surface)
        if state is not None:
            return {"surface_id": args.surface, "port": state["port"]}
        time.sleep(0.1)
    raise TimeoutError(f"drive server for {args.surface!r} did not start in time")


def cmd_stop(args: argparse.Namespace) -> dict:
    state = _read_state(args.run_dir, args.surface)
    if state is None:
        return {"stopped": True, "already_stopped": True}
    try:
        _post(state["port"], "stop", {})
    except OSError:
        pass
    _state_path(args.run_dir, args.surface).unlink(missing_ok=True)
    return {"stopped": True}


def cmd_goto(args: argparse.Namespace) -> dict:
    return _client_call(args, "goto", {"path": args.path})


def cmd_click(args: argparse.Namespace) -> dict:
    return _client_call(args, "click", {"locator": _locator_from_args(args)})


def cmd_fill(args: argparse.Namespace) -> dict:
    payload = {"locator": _locator_from_args(args)}
    if args.from_env:
        payload["from_env"] = args.from_env
    else:
        payload["text"] = args.text
    return _client_call(args, "fill", payload)


def cmd_press(args: argparse.Namespace) -> dict:
    return _client_call(args, "press", {"key": args.key})


def cmd_look(args: argparse.Namespace) -> dict:
    return _client_call(args, "look", {"shot": args.shot})


def cmd_fault(args: argparse.Namespace) -> dict:
    if args.clear:
        if args.kind or args.pattern or args.delay_ms is not None:
            raise ValueError("--clear cannot be combined with --kind/--pattern/--delay-ms")
        return _client_call(args, "fault", {"clear": True})
    if not args.kind:
        raise ValueError("--kind is required unless --clear is given")
    if args.kind in ("5xx", "slow") and not args.pattern:
        raise ValueError(f"--pattern is required for --kind {args.kind}")
    if args.kind == "slow" and args.delay_ms is None:
        raise ValueError("--delay-ms is required for --kind slow")
    return _client_call(args, "fault", {
        "kind": args.kind, "pattern": args.pattern, "delay_ms": args.delay_ms,
    })


def cmd_flow_begin(args: argparse.Namespace) -> dict:
    return _client_call(args, "flow-begin", {"flow": args.flow})


def cmd_flow_end(args: argparse.Namespace) -> dict:
    return _client_call(args, "flow-end", {"flow": args.flow, "status": args.status})


def cmd_serve(args: argparse.Namespace) -> None:
    viewport = None
    if args.viewport_width and args.viewport_height:
        viewport = {"width": args.viewport_width, "height": args.viewport_height}
    tokens = None
    if args.tokens_file:
        tokens = measure.load_tokens(Path(args.tokens_file))  # B4, A-25
    serve(args.surface, Path(args.run_dir), Path(args.project_root), args.base_url,
          record_enabled=args.record, headless=args.headless, viewport=viewport, tokens=tokens)


def build_drive_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="flow-review drive")
    sub = parser.add_subparsers(dest="drive_verb", required=True)

    def _common(p):
        p.add_argument("--surface", required=True)
        p.add_argument("--run", required=True, dest="run_dir")

    def _locator_args(p):
        p.add_argument("--role")
        p.add_argument("--name")
        p.add_argument("--testid")
        p.add_argument("--css")

    p = sub.add_parser("start")
    _common(p)
    p.add_argument("--record", action="store_true")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("stop")
    _common(p)
    p.set_defaults(func=cmd_stop)

    p = sub.add_parser("goto")
    _common(p)
    p.add_argument("path")
    p.set_defaults(func=cmd_goto)

    p = sub.add_parser("click")
    _common(p)
    _locator_args(p)
    p.set_defaults(func=cmd_click)

    p = sub.add_parser("fill")
    _common(p)
    _locator_args(p)
    p.add_argument("--text")
    p.add_argument("--from-env")
    p.set_defaults(func=cmd_fill)

    p = sub.add_parser("press")
    _common(p)
    p.add_argument("key")
    p.set_defaults(func=cmd_press)

    p = sub.add_parser("look")
    _common(p)
    p.add_argument("--shot", action="store_true")
    p.set_defaults(func=cmd_look)

    p = sub.add_parser("fault")
    _common(p)
    p.add_argument("--kind", choices=("offline", "5xx", "slow"))
    p.add_argument("--pattern")
    p.add_argument("--delay-ms", type=int, dest="delay_ms")
    p.add_argument("--clear", action="store_true")
    p.set_defaults(func=cmd_fault)

    p = sub.add_parser("flow-begin")
    _common(p)
    p.add_argument("--flow", required=True)
    p.set_defaults(func=cmd_flow_begin)

    p = sub.add_parser("flow-end")
    _common(p)
    p.add_argument("--flow", required=True)
    p.add_argument("--status", choices=("ok", "blocked"), default="ok")
    p.set_defaults(func=cmd_flow_end)

    p = sub.add_parser("serve")
    p.add_argument("--surface", required=True)
    p.add_argument("--run", required=True, dest="run_dir")
    p.add_argument("--project", required=True, dest="project_root")
    p.add_argument("--base-url", required=True)
    p.add_argument("--record", action="store_true")
    p.add_argument("--headless", dest="headless", action="store_true", default=True)
    p.add_argument("--no-headless", dest="headless", action="store_false")
    p.add_argument("--viewport-width", type=int, default=None)
    p.add_argument("--viewport-height", type=int, default=None)
    p.add_argument("--tokens-file", default=None)
    p.set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None, project_root: Path | None = None) -> int:
    parser = build_drive_parser()
    args = parser.parse_args(argv)
    if args.func is cmd_start:
        args.project_root = project_root
    try:
        result = args.func(args)
    except Exception as exc:  # compact JSON error for the agent; never a traceback
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    if result is not None:
        print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
