from pathlib import Path
from typing import TypedDict

from playwright.sync_api import sync_playwright


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
    def __init__(self, headless: bool = True, viewport: dict | None = None):
        self.headless = headless
        self.viewport = viewport
        self._playwright = None
        self.browser = None
        self.page = None
        self._console_errors: list[dict] = []
        self._network_log: list[dict] = []
        self._current_step: int | None = None

    def launch(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._playwright = sync_playwright().start()
        self.browser = self._playwright.chromium.launch(headless=self.headless)
        self.page = self.browser.new_page(viewport=self.viewport)
        self.page.on("console", self._on_console)
        self.page.on("response", self._on_response)

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
        self.page.wait_for_load_state("networkidle")

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
                aria = aria.replace(value, "[redacted]")
        return {"aria": aria}

    def console_errors(self) -> list[dict]:
        return list(self._console_errors)

    def network_log(self) -> list[dict]:
        return list(self._network_log)

    def begin_step(self, step_index: int) -> None:
        self._current_step = step_index

    def end_step(self) -> None:
        self._current_step = None

    def _on_console(self, msg) -> None:
        if msg.type == "error":
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
