import time
from pathlib import Path
from typing import TypedDict

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from flow_review.events import REDACTED

SETTLE_MS = 3000
QUIET_MS = 300  # after the network looks idle, how long nothing may start before we call it settled
POLL_MS = 50


class Locator(TypedDict, total=False):
    role: str
    name: str
    testid: str
    css: str


class LocatorNotFound(Exception):
    def __init__(self, locator: dict):
        super().__init__(f"could not resolve locator: {locator!r}")
        self.locator = locator


class WebDriver:
    def __init__(self, headless: bool = True, viewport: dict | None = None,
                 color_scheme: str | None = None, reduced_motion: str | None = None,
                 storage_state: str | None = None):
        self.headless = headless
        self.viewport = viewport
        self.color_scheme = color_scheme
        self.reduced_motion = reduced_motion
        self.storage_state_path = storage_state
        self._playwright = None
        self.browser = None
        self.page = None
        self._console_errors: list[dict] = []
        self._network_log: list[dict] = []
        self._current_step: int | None = None
        self._network_cursor = 0
        self._console_cursor = 0
        self._inflight = 0
        self._last_activity = 0.0

    def launch(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._playwright = sync_playwright().start()
        self.browser = self._playwright.chromium.launch(headless=self.headless)
        page_kwargs: dict = {"viewport": self.viewport}
        if self.color_scheme is not None:
            page_kwargs["color_scheme"] = self.color_scheme
        if self.reduced_motion is not None:
            page_kwargs["reduced_motion"] = self.reduced_motion
        if self.storage_state_path is not None:
            page_kwargs["storage_state"] = self.storage_state_path
        self.page = self.browser.new_page(**page_kwargs)
        self.page.on("console", self._on_console)
        self.page.on("response", self._on_response)
        self.page.on("request", self._on_request_start)
        self.page.on("requestfinished", self._on_request_done)
        self.page.on("requestfailed", self._on_request_done)

    def storage_state(self) -> str:
        import json
        return json.dumps(self.page.context.storage_state())

    def close(self) -> None:
        if self.browser is not None:
            self.browser.close()
        if self._playwright is not None:
            self._playwright.stop()

    def goto(self, path: str) -> None:
        self.page.goto(self.base_url + path)

    def resolve(self, locator: dict):
        if locator.get("role"):
            loc = self.page.get_by_role(locator["role"], name=locator.get("name"))
        elif locator.get("testid"):
            loc = self.page.get_by_test_id(locator["testid"])
        elif locator.get("css"):
            loc = self.page.locator(locator["css"])
        else:
            raise LocatorNotFound(locator)
        if loc.count() != 1:
            raise LocatorNotFound(locator)
        return loc

    def click(self, locator: dict) -> None:
        self.resolve(locator).click()
        self._settle()

    def _settle(self) -> None:
        # ponytail: networkidle capped at SETTLE_MS; apps with long-poll/SSE never go idle, so
        # an uncapped wait would stall every click for Playwright's 30s default. Upgrade path:
        # an app-specific ready signal from config.
        # networkidle returns at once when the page was already idle before the action, so we
        # then also wait until no request is in flight and nothing (request or console error)
        # happened for QUIET_MS -- click-triggered requests and their errors land in this step.
        deadline = time.monotonic() + SETTLE_MS / 1000
        try:
            self.page.wait_for_load_state("networkidle", timeout=SETTLE_MS)
        except PlaywrightTimeoutError:
            return
        self._last_activity = max(self._last_activity, time.monotonic())
        while time.monotonic() < deadline:
            quiet = time.monotonic() - self._last_activity >= QUIET_MS / 1000
            if self._inflight <= 0 and quiet:
                return
            self.page.wait_for_timeout(POLL_MS)

    def _on_request_start(self, request) -> None:
        self._inflight += 1
        self._last_activity = time.monotonic()

    def _on_request_done(self, request) -> None:
        self._inflight = max(0, self._inflight - 1)
        self._last_activity = time.monotonic()

    def press(self, key: str) -> None:
        self.page.keyboard.press(key)  # Enter may submit a form: settle like a click
        self._settle()

    def fill(self, locator: dict, value: str) -> None:
        self.resolve(locator).fill(value)

    def screenshot(self, path: Path) -> Path:
        password_inputs = self.page.locator("input[type=password]")
        mask = [password_inputs.nth(i) for i in range(password_inputs.count())]
        self.page.screenshot(path=str(path), mask=mask, mask_color="#000000")
        return path

    def snapshot(self) -> dict:
        # Playwright removed `page.accessibility` (deprecated since ~1.49, gone in
        # 1.63 installed here); `Locator.aria_snapshot()` is the current API and
        # returns a YAML-ish accessibility tree string, wrapped here to keep the
        # documented `-> dict` return type. Unlike the real OS accessibility tree
        # (which never exposes password characters), aria_snapshot() echoes the
        # live value of password inputs as plain text, so we redact those values
        # ourselves to uphold the "secrets never appear in snapshots" rule.
        aria = self.page.locator("html").aria_snapshot()
        for value in self.page.eval_on_selector_all(
            "input[type=password]", "els => els.map(e => e.value)"
        ):
            if value:
                aria = aria.replace(value, REDACTED)
        return {"aria": aria}

    def is_password(self, locator: dict) -> bool:
        try:
            loc = self.resolve(locator)
        except LocatorNotFound:
            return False
        return bool(loc.evaluate("el => el.tagName === 'INPUT' && el.type === 'password'"))

    def console_errors(self) -> list[dict]:
        return list(self._console_errors)

    def network_log(self) -> list[dict]:
        return list(self._network_log)

    def network_log_since_check(self) -> list[dict]:
        """Network entries appended since the last call to this method. Advances the
        cursor; a second call right after returns []."""
        new_entries = self._network_log[self._network_cursor:]
        self._network_cursor = len(self._network_log)
        return new_entries

    def console_errors_since_check(self) -> list[dict]:
        """Console-error entries appended since the last call to this method. Advances
        the cursor; a second call right after returns []."""
        new_entries = self._console_errors[self._console_cursor:]
        self._console_cursor = len(self._console_errors)
        return new_entries

    def begin_step(self, step_index: int) -> None:
        self._current_step = step_index

    def end_step(self) -> None:
        self._current_step = None

    def _on_console(self, msg) -> None:
        if msg.type == "error":
            self._last_activity = time.monotonic()
            self._console_errors.append({
                "text": msg.text,
                "location": str(msg.location),
                "step_index": self._current_step,
            })

    def _on_response(self, response) -> None:
        self._network_log.append({
            "method": response.request.method,
            "url": response.url,
            "status": response.status,
        })
