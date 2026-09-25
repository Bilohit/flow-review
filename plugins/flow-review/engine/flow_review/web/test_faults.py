from flow_review.web import faults


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


def test_url_matches_star_does_not_cross_slash():
    # A single '*' excludes '/', so it can only stand in for one path segment -- it can never
    # span the scheme's own '//' the way T1-brief's literal "*/api/*" example assumed (that
    # pattern can't match ANY absolute URL, since every one has '//' after the scheme; deviation
    # noted in the report). The literal scheme+host here isolates the behavior under test.
    assert faults.url_matches("http://h/api/x", "http://h/api/*")
    assert not faults.url_matches("http://h/api/x/y", "http://h/api/*")


def test_url_matches_double_star_crosses_slash():
    assert faults.url_matches("http://h/api/x", "**/api/**")
    assert faults.url_matches("http://h/api/x/y", "**/api/**")


def test_url_matches_question_mark_is_literal_not_a_wildcard():
    # Real Playwright escapes '?' -- URLs use it for query strings, so a one-char wildcard
    # would make every query-string URL an accidental match. '?' must be a literal character.
    assert faults.url_matches("http://h/api/x?a=1", "http://h/api/x?a=1")
    assert not faults.url_matches("http://h/api/xA", "http://h/api/x?")


def test_inject_slow_uses_wait_for_timeout_not_sleep(monkeypatch):
    import time
    called = {"sleep": False}
    monkeypatch.setattr(time, "sleep", lambda *_: called.__setitem__("sleep", True))

    class FakeRequest:
        url = "http://h/api/x"

    class FakeRouteForSlow:
        def __init__(self):
            self.continued = False

        @property
        def request(self):
            return FakeRequest()

        def continue_(self):
            self.continued = True

    class FakePageForSlow:
        def __init__(self):
            self.waited = None
            self.handler = None

        def route(self, pattern, handler):
            self.handler = handler

        def wait_for_timeout(self, ms):
            self.waited = ms

    page = FakePageForSlow()
    faults.inject_slow(page, "http://h/api/*", 500)
    route = FakeRouteForSlow()
    page.handler(route)
    assert page.waited == 500
    assert route.continued is True
    assert called["sleep"] is False


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
