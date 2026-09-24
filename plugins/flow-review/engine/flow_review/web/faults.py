import fnmatch
import time


def inject_offline(page) -> None:
    def _handler(route):
        route.abort()
    page.route("**/*", _handler)


def inject_5xx(page, url_pattern: str, status: int = 500) -> None:
    def _handler(route):
        if fnmatch.fnmatch(route.request.url, url_pattern):
            route.fulfill(status=status, content_type="text/plain", body="Internal Server Error")
        else:
            route.continue_()
    page.route(url_pattern, _handler)


def inject_slow(page, url_pattern: str, delay_ms: int) -> None:
    def _handler(route):
        if fnmatch.fnmatch(route.request.url, url_pattern):
            time.sleep(delay_ms / 1000)
        route.continue_()
    page.route(url_pattern, _handler)


def clear_faults(page) -> None:
    page.unroute_all()
