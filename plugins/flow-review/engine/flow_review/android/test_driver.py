import re
from pathlib import Path

import pytest

from flow_review.android.driver import AndroidDriver
from flow_review.locators import LocatorNotFound

FIX = Path(__file__).parent / "fixtures"
APP = "com.example.notes"


class FakeAdb:
    def __init__(self, xml_name="login.xml", pid=True, ime=False):
        self.calls = []
        self.xml = (FIX / xml_name).read_text(encoding="utf-8")
        self.pid, self.ime = pid, ime

    def _rec(self, *c):
        self.calls.append(c)

    def sleep(self, s):
        self._rec("sleep", s)

    def reverse(self, port): self._rec("reverse", port)
    def pidof(self, app): self._rec("pidof"); return self.pid
    def start(self, app): self._rec("start", app)
    def wait_foreground(self, app): self._rec("wait_foreground", app)
    def density(self): return 480
    def screen_size(self): return (1080, 2400)
    def dump(self): self._rec("dump"); return self.xml
    def tap(self, x, y): self._rec("tap", x, y)
    def text(self, v): self._rec("text", v)
    def key(self, k): self._rec("key", k)
    def keys(self, code, n): self._rec("keys", code, n)
    def ime_shown(self): return self.ime
    def open_link(self, url, app): self._rec("open_link", url, app)
    def screencap(self, path): self._rec("screencap", str(path)); return path


def _driver(adb=None, **opts):
    return AndroidDriver(APP, options=opts, adb=adb or FakeAdb())


def _names(adb):
    return [c[0] for c in adb.calls]


def test_attributes():
    d = _driver()
    assert (d.kind, d.page, d.init_script) == ("adb", None, None)


def test_launch_always_starts_and_reads_screen_once():
    adb = FakeAdb(pid=True)
    d = _driver(adb)
    d.launch()
    assert "start" in _names(adb) and "reverse" not in _names(adb) and "pidof" not in _names(adb)
    assert ("wait_foreground", APP) in adb.calls
    assert d.density == 480 and d.screen_wh == (1080, 2400)


def test_launch_reverses_metro_then_starts():
    adb = FakeAdb(pid=False)
    _driver(adb, metro_url="http://127.0.0.1:8081").launch()
    assert _names(adb)[:2] == ["reverse", "start"]


def test_launch_reverses_metro_url_port():
    adb = FakeAdb()
    _driver(adb, metro_url="http://10.0.2.2:19000").launch()
    assert ("reverse", 19000) in adb.calls
    adb = FakeAdb()
    _driver(adb, metro_url="http://localhost").launch()
    assert ("reverse", 8081) in adb.calls


def test_goto_scheme_and_fallback():
    adb = FakeAdb()
    d = _driver(adb, scheme="notes")
    d.goto("/note/1")
    d.goto("/")
    assert adb.calls == [("open_link", "notes://note/1", APP), ("start", APP)]
    adb2 = FakeAdb()
    _driver(adb2).goto("/note/1")
    assert adb2.calls == [("start", APP)]


def test_click_taps_center_of_node():
    adb = FakeAdb()
    _driver(adb).click({"role": "textbox", "name": "Email"})
    assert ("tap", 540, 370) in adb.calls


def test_click_miss_passes_locator_not_found():
    with pytest.raises(LocatorNotFound):
        _driver().click({"testid": "nope"})


def test_fill_empty_field_taps_moves_end_types_no_ime():
    adb = FakeAdb()
    _driver(adb).fill({"role": "textbox", "name": "Email"}, "a b", secret=False)
    assert ("text", "a b") in adb.calls
    assert ("key", "MoveEnd") in adb.calls
    assert not any(c[0] == "keys" for c in adb.calls)  # nothing to delete
    assert ("key", "Back") not in adb.calls


def test_fill_clears_existing_text_and_dismisses_ime():
    adb = FakeAdb(ime=True)
    d = _driver(adb)
    d.nodes()  # prime cache, then give the node text
    for n in d.nodes():
        if n["desc"] == "Email":
            n["text"] = "old!"
    d.fill({"role": "textbox", "name": "Email"}, "x")
    assert ("keys", 67, 4) in adb.calls
    assert adb.calls[-1] == ("key", "Back")


def test_fill_empty_value_skips_text():
    adb = FakeAdb()
    _driver(adb).fill({"role": "textbox", "name": "Email"}, "")
    assert "text" not in _names(adb)


def test_nodes_cached_across_begin_step_and_dropped_after_action():
    adb = FakeAdb()
    d = _driver(adb)
    d.nodes(); d.nodes()
    assert _names(adb).count("dump") == 1
    d.begin_step(0)  # the screen has not changed since the last dump
    d.nodes()
    assert _names(adb).count("dump") == 1
    d.end_step()  # the action may have changed it
    d.nodes()
    assert _names(adb).count("dump") == 2


def test_click_redumps_once_when_cached_screen_misses_locator():
    adb = FakeAdb()
    d = _driver(adb)
    d.nodes()
    with pytest.raises(LocatorNotFound):
        d.click({"role": "button", "name": "No such control"})
    assert _names(adb).count("dump") == 2


def test_snapshot_route_url():
    d = _driver()
    d.screen_wh = (1080, 2400)
    assert "aria" in d.snapshot()
    assert d.route == "sign-in"
    assert d.current_url == f"android://{APP}/sign-in"


def test_is_password_node_and_fallback():
    d = _driver()
    nodes = d.nodes()
    pw = next(n for n in nodes if n["password"])
    assert d.is_password({"role": "textbox", "name": pw["desc"] or pw["text"]}) is True
    assert d.is_password({"testid": "missing-password-field"}) is True
    assert d.is_password({"testid": "missing-email"}) is False


def test_secret_fill_blocks_screenshot_until_route_changes():
    adb = FakeAdb()
    d = _driver(adb)
    d.launch()
    d.fill({"role": "textbox", "name": "Password"}, "pw", secret=True)
    assert d.screenshot("a.png") is None
    assert ("screencap", "a.png") not in adb.calls
    d._nodes = None
    assert d.screenshot("a.png") is None  # same route after refresh
    adb.xml = (FIX / "home.xml").read_text(encoding="utf-8")
    d._nodes = None
    d.nodes()
    assert d.screenshot("b.png") == "b.png" and ("screencap", "b.png") in adb.calls


def test_is_password_name_fallback_whole_words():
    d = _driver()
    for n in ("PIN", "pin-code", "Enter PIN", "confirm_password", "secret"):
        assert d.is_password({"testid": n}) is True, n
    for n in ("shipping", "mapping", "spinner", "email"):
        assert d.is_password({"testid": n}) is False, n


def test_delete_uses_adb_key_table():
    from flow_review.android import adb as adbmod
    assert not hasattr(__import__("flow_review.android.driver", fromlist=["x"]), "_DEL")
    assert adbmod._KEYS["Del"] == 67


def test_screenshot_press_and_noops():
    adb = FakeAdb()
    d = _driver(adb)
    d.screenshot("x.png")
    d.press("Enter")
    assert ("screencap", "x.png") in adb.calls and ("key", "Enter") in adb.calls
    assert d.console_errors() == d.console_errors_since_check() == d.network_log_since_check() == []
    assert d.close() is None


def test_driver_has_every_method_the_session_and_replay_call():
    root = Path(__file__).parent.parent / "web"
    names = set()
    for f, pat in (("drive.py", r"self\.driver\.(\w+)"), ("replay.py", r"\bdriver\.(\w+)")):
        names |= set(re.findall(pat, (root / f).read_text(encoding="utf-8")))
    names -= {"page"}  # attribute: None on adb, guarded by getattr
    missing = [n for n in sorted(names) if not hasattr(AndroidDriver, n)]
    assert not missing, missing


def test_return_to_presses_back_until_start_route_and_never_stops_app():
    adb = FakeAdb()
    adb.foreground_package = lambda: APP
    routes = iter(["settings", "settings", "home"])

    class _Driver(AndroidDriver):
        route = property(lambda self: next(routes))

    d = _Driver(APP, adb=adb)
    assert d.return_to("home") is True
    assert [c for c in adb.calls if c[0] == "key"] == [("key", "Back"), ("key", "Back")]
    assert "start" not in _names(adb)


def test_return_to_gives_up_after_tries():
    adb = FakeAdb()
    adb.foreground_package = lambda: APP

    class _Driver(AndroidDriver):
        route = property(lambda self: "settings")

    assert _Driver(APP, adb=adb).return_to("home", tries=2) is False
