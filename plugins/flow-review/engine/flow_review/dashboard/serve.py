"""flow-review serve: local HTTP server for the live dashboard.

ThreadingHTTPServer bound to 127.0.0.1 only (never exposed on the network).
Endpoints: GET / (page), GET /state (JSON), GET /events (SSE), POST /triage,
GET /<path> (static assets under page/).
"""
from __future__ import annotations

import dataclasses
import json
import mimetypes
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from flow_review import triage
from flow_review.dashboard.state import fold

PAGE_DIR = Path(__file__).parent / "page"
HEARTBEAT_S = 15
POLL_S = 0.5
MAX_BODY = 64 * 1024  # a triage POST is a few hundred bytes


def _ledger_path(project_root: Path) -> Path:
    return project_root / ".flow-review" / "findings.json"


class Handler(BaseHTTPRequestHandler):
    project_root: Path
    run_dir: Path
    cfg: object

    def log_message(self, fmt, *args):  # noqa: A002 -- silence default stderr access log
        pass

    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str):
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_404(self):
        self.send_response(404)
        self.end_headers()

    def do_GET(self):  # noqa: N802 -- stdlib handler name
        parsed = urlparse(self.path)
        if parsed.path == "/":
            index = PAGE_DIR / "index.html"
            if not index.is_file():
                self._send_404()
                return
            self._send_file(index, "text/html; charset=utf-8")
            return
        if parsed.path == "/state":
            self._send_json(fold(self.project_root, self.run_dir, self.cfg))
            return
        if parsed.path == "/events":
            self._stream_events()
            return
        if parsed.path.startswith("/run/"):
            run_root = Path(self.run_dir).resolve()
            candidate = (run_root / unquote(parsed.path[len("/run/"):])).resolve()
            ctype = mimetypes.guess_type(str(candidate))[0] or ""
            if run_root in candidate.parents and candidate.is_file() and ctype.startswith("image/"):
                self._send_file(candidate, ctype)
            else:
                self._send_404()
            return
        rel = parsed.path.lstrip("/")
        page_root = PAGE_DIR.resolve()
        candidate = (page_root / rel).resolve()
        if page_root in candidate.parents and candidate.is_file():
            ctype = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
            self._send_file(candidate, ctype)
            return
        self._send_404()

    def _stream_events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        events_path = self.run_dir / "events.jsonl"
        last_size = -1
        last_beat = time.monotonic()
        try:
            while True:
                size = events_path.stat().st_size if events_path.exists() else 0
                if size != last_size:
                    last_size = size
                    payload = json.dumps(fold(self.project_root, self.run_dir, self.cfg))
                    self.wfile.write(f"event: state\ndata: {payload}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    last_beat = time.monotonic()
                elif time.monotonic() - last_beat > HEARTBEAT_S:
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
                    last_beat = time.monotonic()
                time.sleep(POLL_S)
        except (BrokenPipeError, ConnectionResetError):
            return

    def do_POST(self):  # noqa: N802
        if urlparse(self.path).path != "/triage":
            self._send_404()
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length > MAX_BODY:
            self.close_connection = True
            self._send_json({"error": "body too large"}, status=413)
            return
        raw = self.rfile.read(length)  # drain first: replying mid-upload aborts the socket on Windows
        # Block cross-site writes: a browser tab on another site can POST to localhost.
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).hostname not in ("127.0.0.1", "localhost"):
            self._send_json({"error": "forbidden origin"}, status=403)
            return
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            self._send_json({"error": "invalid json"}, status=400)
            return
        finding_id = body.get("finding_id")
        state = body.get("state")
        reason = body.get("reason")
        if not finding_id or not state:
            self._send_json({"error": "finding_id and state are required"}, status=400)
            return
        try:
            entry = triage.apply(_ledger_path(self.project_root), finding_id, state, reason=reason)
        except Exception as exc:  # triage.apply's own errors are user-facing (bad state name etc.)
            self._send_json({"error": str(exc)}, status=400)
            return
        finding = dataclasses.asdict(entry) if dataclasses.is_dataclass(entry) else vars(entry)
        self._send_json({"ok": True, "finding": finding})


def make_server(project_root: Path, run_dir: Path, cfg, port: int = 0) -> ThreadingHTTPServer:
    bound = type("BoundHandler", (Handler,), {
        "project_root": project_root, "run_dir": run_dir, "cfg": cfg,
    })
    return ThreadingHTTPServer(("127.0.0.1", port), bound)


def serve(project_root: Path, run_dir: Path, cfg, port: int = 0) -> None:
    server = make_server(project_root, run_dir, cfg, port)
    _, bound_port = server.server_address
    print(f"flow-review dashboard: http://127.0.0.1:{bound_port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
