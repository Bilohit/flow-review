import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

WEBAPP_DIR = Path(__file__).parent / "fixtures" / "webapp"

_CONTENT_TYPES = {
    ".html": "text/html", ".js": "application/javascript",
    ".css": "text/css", ".json": "application/json",
}


def _make_handler(requests_log: list[dict]):
    class FixtureHandler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # silence stdlib access log
            pass

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/api/fail":
                body = json.dumps({"error": "boom"}).encode()
                # Log before responding: the client may read the reply before this thread
                # appends, and a test asserting on the log would race.
                requests_log.append({"method": "GET", "path": path, "status": 500})
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            fs_path = WEBAPP_DIR / (path.lstrip("/") or "index.html")
            if fs_path.is_file():
                data = fs_path.read_bytes()
                ctype = _CONTENT_TYPES.get(fs_path.suffix, "application/octet-stream")
                # Log before responding: the client may read the reply before this thread
                # appends, and a test asserting on the log would race.
                requests_log.append({"method": "GET", "path": path, "status": 200})
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                # Log before responding: the client may read the reply before this thread
                # appends, and a test asserting on the log would race.
                requests_log.append({"method": "GET", "path": path, "status": 404})
                self.send_response(404)
                self.end_headers()

    return FixtureHandler


@pytest.fixture
def webapp_server():
    requests_log: list[dict] = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(requests_log))
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}", requests_log
    finally:
        server.shutdown()
        thread.join(timeout=5)
