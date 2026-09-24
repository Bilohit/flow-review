import pytest
pytest.importorskip("playwright")

from flow_review.web.driver import WebDriver, LocatorNotFound


@pytest.mark.web
def test_resolve_order_and_click(webapp_server):
    base_url, _ = webapp_server
    d = WebDriver(headless=True)
    d.launch(base_url)
    d.goto("/")
    d.click({"testid": "load-button"})
    assert any(n["status"] == 500 for n in d.network_log())
    d.close()


@pytest.mark.web
def test_resolve_missing_raises(webapp_server):
    base_url, _ = webapp_server
    d = WebDriver(headless=True)
    d.launch(base_url)
    d.goto("/")
    with pytest.raises(LocatorNotFound):
        d.resolve({"testid": "does-not-exist"})
    d.close()


@pytest.mark.web
def test_screenshot_masks_password_field(tmp_path, webapp_server):
    base_url, _ = webapp_server
    d = WebDriver(headless=True)
    d.launch(base_url)
    d.goto("/")
    d.fill({"testid": "pw-input"}, "hunter2")
    out = d.screenshot(tmp_path / "shot.png")
    assert out.exists() and out.stat().st_size > 0
    snap = d.snapshot()
    assert "hunter2" not in str(snap)
    d.close()


@pytest.mark.web
def test_console_errors_tagged_with_step_window(webapp_server):
    base_url, _ = webapp_server
    d = WebDriver(headless=True)
    d.launch(base_url)
    d.goto("/")
    d.page.evaluate("console.error('outside step')")
    d.begin_step(3)
    d.page.evaluate("console.error('inside step 3')")
    d.end_step()
    d.page.evaluate("console.error('outside again')")
    errors = d.console_errors()
    d.close()
    tagged = {e["text"]: e["step_index"] for e in errors}
    assert tagged["outside step"] is None
    assert tagged["inside step 3"] == 3
    assert tagged["outside again"] is None


class _RecordingPage:
    def __init__(self):
        self.navigated = None

    def goto(self, url):
        self.navigated = url


def test_goto_accepts_a_leading_slash_path():
    d = WebDriver()
    d.base_url = "http://localhost:3000"
    d.page = _RecordingPage()
    d.goto("/dashboard")
    assert d.page.navigated == "http://localhost:3000/dashboard"


@pytest.mark.parametrize("path", [
    "@evil.example/",       # base_url + this resolves off-origin via userinfo syntax
    "//evil.example",       # protocol-relative: off-origin
    "http://evil.example",  # absolute URL: off-origin
    "evil",                 # no leading slash at all
    "",                     # empty path
])
def test_goto_rejects_paths_that_are_not_a_plain_root_relative_path(path):
    d = WebDriver()
    d.base_url = "http://localhost:3000"
    d.page = _RecordingPage()
    with pytest.raises(ValueError):
        d.goto(path)
    assert d.page.navigated is None


def test_click_settle_is_capped_when_the_network_never_idles():
    from playwright.sync_api import TimeoutError as PWTimeout
    from flow_review.web import driver as drv

    calls = []

    class _Page:
        def wait_for_load_state(self, state, timeout=None):
            calls.append((state, timeout))
            raise PWTimeout("never idle")

    d = drv.WebDriver()
    d.page = _Page()
    d._settle()  # must not raise
    assert calls == [("networkidle", drv.SETTLE_MS)]


@pytest.mark.web
def test_screenshot_masks_a_text_input_filled_as_a_secret(tmp_path, webapp_server):
    # CP3 finding 4: only input[type=password] was masked, so a from_env fill into a text
    # field (an API key, an OTP box) showed up in plain sight in look --shot screenshots.
    pytest.importorskip("PIL")
    from PIL import Image

    base_url, _ = webapp_server
    d = WebDriver(headless=True)
    d.launch(base_url)
    d.goto("/")
    d.fill({"testid": "username-input"}, "s3cret-api-key", secret=True)
    out = tmp_path / "shot.png"
    d.screenshot(out)

    box = d.page.locator("[data-testid=username-input]").bounding_box()
    d.close()

    img = Image.open(out).convert("RGB")
    cx = int(box["x"] + box["width"] / 2)
    cy = int(box["y"] + box["height"] / 2)
    assert img.getpixel((cx, cy)) == (0, 0, 0)


@pytest.mark.web
def test_screenshot_does_not_mask_a_plain_text_input(tmp_path, webapp_server):
    base_url, _ = webapp_server
    d = WebDriver(headless=True)
    d.launch(base_url)
    d.goto("/")
    d.fill({"testid": "username-input"}, "not-a-secret")
    out = tmp_path / "shot.png"
    d.screenshot(out)

    box = d.page.locator("[data-testid=username-input]").bounding_box()
    d.close()

    from PIL import Image
    img = Image.open(out).convert("RGB")
    cx = int(box["x"] + box["width"] / 2)
    cy = int(box["y"] + box["height"] / 2)
    assert img.getpixel((cx, cy)) != (0, 0, 0)


@pytest.mark.web
def test_is_password_detects_password_input_and_false_for_others(webapp_server):
    base_url, _ = webapp_server
    d = WebDriver(headless=True)
    d.launch(base_url)
    d.goto("/")
    assert d.is_password({"testid": "pw-input"}) is True
    assert d.is_password({"testid": "load-button"}) is False
    d.close()


@pytest.mark.web
def test_is_password_false_for_unresolvable_locator(webapp_server):
    base_url, _ = webapp_server
    d = WebDriver(headless=True)
    d.launch(base_url)
    d.goto("/")
    assert d.is_password({"testid": "does-not-exist"}) is False
    d.close()


def _slow_fail_server(delay_s: float):
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from pathlib import Path
    import time as _time

    root = Path(__file__).resolve().parents[2] / "fixtures" / "webapp"

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/api/fail":
                _time.sleep(delay_s)
                self.send_response(500)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            f = root / (path.lstrip("/") or "index.html")
            if not f.is_file():
                self.send_response(404)
                self.end_headers()
                return
            data = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html" if f.suffix == ".html"
                             else "application/javascript" if f.suffix == ".js" else "text/css")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


@pytest.mark.web
def test_click_settle_waits_for_click_triggered_request_and_console_error():
    srv = _slow_fail_server(0.6)
    d = WebDriver(headless=True)
    try:
        d.launch(f"http://127.0.0.1:{srv.server_address[1]}")
        d.goto("/")
        # the app defers its request slightly after the click (debounce, animation, etc.)
        d.page.evaluate("""() => document.getElementById('load-button').addEventListener(
            'click', () => setTimeout(() => fetch('/api/fail').then(r => {
                if (!r.ok) console.error('deferred failed ' + r.status); }), 150))""")
        d.page.wait_for_load_state("networkidle")  # page already idle, as after earlier steps
        d.begin_step(7)
        d.click({"testid": "load-button"})
        d.end_step()
        assert sum(e["status"] == 500 for e in d.network_log()) == 2
        assert {e["text"]: e["step_index"] for e in d.console_errors()}.get(
            "deferred failed 500") == 7
    finally:
        d.close()
        srv.shutdown()
