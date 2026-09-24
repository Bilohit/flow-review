from flow_review.web import faults


def test_match_pattern_glob():
    assert faults.match_pattern("http://x/api/broken", "**/api/*")
    assert not faults.match_pattern("http://x/other", "**/api/*")


class FakeRequest:
    def __init__(self, url):
        self.url = url


class FakeRoute:
    def __init__(self, url):
        self.request = FakeRequest(url)
        self.aborted = False
        self.fulfilled = None
        self.continued = False

    def abort(self):
        self.aborted = True

    def fulfill(self, **kwargs):
        self.fulfilled = kwargs

    def continue_(self):
        self.continued = True


class FakePage:
    def __init__(self):
        self.handlers = {}
        self.unrouted = False

    def route(self, pattern, handler):
        self.handlers[pattern] = handler

    def unroute_all(self):
        self.unrouted = True


def test_inject_5xx_fulfills_matching_and_continues_others():
    page = FakePage()
    faults.inject_5xx(page, "**/api/broken")
    handler = page.handlers["**/api/broken"]

    matching = FakeRoute("http://x/api/broken")
    handler(matching)
    assert matching.fulfilled["status"] == 500

    other = FakeRoute("http://x/other")
    handler(other)
    assert other.continued is True
    assert other.fulfilled is None


def test_inject_offline_aborts_every_request():
    page = FakePage()
    faults.inject_offline(page)
    handler = page.handlers["**/*"]
    route = FakeRoute("http://x/anything")
    handler(route)
    assert route.aborted is True


def test_inject_slow_delays_then_continues(monkeypatch):
    page = FakePage()
    slept = {}
    monkeypatch.setattr(faults.time, "sleep", lambda s: slept.setdefault("seconds", s))
    faults.inject_slow(page, "**/api/broken", delay_ms=250)
    handler = page.handlers["**/api/broken"]
    route = FakeRoute("http://x/api/broken")
    handler(route)
    assert slept["seconds"] == 0.25
    assert route.continued is True


def test_clear_faults_calls_unroute_all():
    page = FakePage()
    faults.clear_faults(page)
    assert page.unrouted is True


import pytest

pytest.importorskip("playwright")


@pytest.mark.web
def test_inject_5xx_overrides_route_live(webapp_server):
    from flow_review.web.driver import WebDriver
    base_url, _ = webapp_server
    d = WebDriver(headless=True)
    d.launch(base_url)
    faults.inject_5xx(d.page, "**/api/broken")
    d.goto("/")
    d.click({"testid": "load-button"})
    assert any(n["status"] == 500 for n in d.network_log())
    d.close()
