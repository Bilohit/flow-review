"""AndroidDriver: duck-typed twin of WebDriver for a running Android app over adb (A-74..A-83).
No playwright import; the hierarchy dump is the only view of the screen."""
from __future__ import annotations

import re
from pathlib import Path

from flow_review.android import hierarchy
from flow_review.android.adb import Adb
from flow_review.locators import LocatorNotFound

_DEL = 67  # KEYCODE_DEL; Adb's key map keeps names only for Enter/Back/Del/MoveEnd
_SECRET_NAME = re.compile(r"password|passcode|pin|secret", re.I)
# ponytail: fixed wait for the screen to settle after an action; upgrade path is polling dumps
# until two match, at ~2s per dump that costs more than it saves on most screens
_SETTLE_S = 1.0


class AndroidDriver:
    kind = "adb"
    page = None
    init_script = None

    def __init__(self, app_id: str, device: str | None = None, options: dict | None = None,
                 adb: Adb | None = None):
        self.app_id = app_id
        self.options = options or {}
        self.adb = adb or Adb(device or self.options.get("device"))
        self.density = 160
        self.screen_wh = (0, 0)
        self._nodes: list[dict] | None = None

    def launch(self, base_url=None) -> None:
        if self.options.get("metro_url"):
            self.adb.reverse(8081)
        if not self.adb.pidof(self.app_id):
            self.adb.start(self.app_id)
        self.adb.wait_foreground(self.app_id)
        self.density = self.adb.density()
        self.screen_wh = self.adb.screen_size()

    def nodes(self) -> list[dict]:
        if self._nodes is None:
            self._nodes = hierarchy.parse(self.adb.dump())
        return self._nodes

    def begin_step(self, step_index) -> None:
        pass  # the last step's post-action dump is still the screen; _resolve re-dumps on a miss

    def end_step(self) -> None:
        self._nodes = None
        self.adb.sleep(_SETTLE_S)

    @property
    def route(self) -> str:
        return hierarchy.screen_route(self.nodes(), self.app_id, self.screen_wh[1])

    @property
    def current_url(self) -> str:
        return f"android://{self.app_id}/{self.route}"

    def goto(self, path: str) -> None:
        scheme = self.options.get("scheme")
        if scheme and path not in ("/", ""):
            self.adb.open_link(f"{scheme}://{path.lstrip('/')}", self.app_id)
        else:
            self.adb.start(self.app_id)

    def _tap(self, node: dict) -> None:
        x1, y1, x2, y2 = node["bounds"]
        self.adb.tap((x1 + x2) // 2, (y1 + y2) // 2)

    def _resolve(self, locator: dict) -> dict:
        try:
            return hierarchy.resolve(self.nodes(), locator)
        except LocatorNotFound:
            self._nodes = None  # the screen may have moved on since the cached dump
            return hierarchy.resolve(self.nodes(), locator)

    def click(self, locator: dict) -> None:
        self._tap(self._resolve(locator))

    def fill(self, locator: dict, value: str, secret: bool = False) -> None:
        node = self._resolve(locator)
        self._tap(node)
        self.adb.key("MoveEnd")
        if node["text"]:
            self.adb.keys(_DEL, len(node["text"]))
        if value:
            self.adb.text(value)
        if self.adb.ime_shown():
            self.adb.key("Back")  # a blind Back would navigate away (A-83)

    def press(self, key: str) -> None:
        self.adb.key(key)

    def screenshot(self, path) -> Path:
        return self.adb.screencap(path)

    def snapshot(self) -> dict:
        return {"aria": hierarchy.outline(self.nodes(), self.app_id)}

    def is_password(self, locator: dict) -> bool:
        try:
            return hierarchy.resolve(self.nodes(), locator)["password"]
        except LocatorNotFound:
            name = locator.get("testid") or locator.get("name") or locator.get("text") or ""
            return bool(_SECRET_NAME.search(name))

    def console_errors(self) -> list:
        return []

    def console_errors_since_check(self) -> list:
        return []

    def network_log_since_check(self) -> list:
        return []

    def close(self) -> None:
        pass  # the app stays running; the engine never force-stops it
