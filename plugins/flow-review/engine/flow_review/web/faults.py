import re


def url_matches(url: str, pattern: str) -> bool:
    """Playwright glob semantics: '*' matches any run of characters except '/', '**' matches
    across '/'. '?' is a literal character (real Playwright escapes it, since URLs use '?' for
    query strings -- a one-char wildcard there would make every query-string URL an accidental
    match). Used by page.route and by drive's self-inflicted check so both sides agree on what a
    fault pattern covers.

    # ponytail: this covers '*', '**', and literals only -- '**' here is a flat '.*', not
    # Playwright's context-sensitive '**/' segment handling. Upgrade path if a pattern ever needs
    # that edge semantics: port playwright's own glob_to_regex (playwright/_impl/_glob.py)
    # instead of extending this by hand.
    """
    out = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if pattern[i:i + 2] == "**":
            out.append(".*")
            i += 2
            continue
        if ch == "*":
            out.append("[^/]*")
            i += 1
            continue
        out.append(re.escape(ch))
        i += 1
    regex = "^" + "".join(out) + "$"
    return re.match(regex, url) is not None


def inject_offline(page) -> None:
    def _handler(route):
        route.abort()
    page.route("**/*", _handler)


def inject_5xx(page, url_pattern: str, status: int = 500) -> None:
    def _handler(route):
        if url_matches(route.request.url, url_pattern):
            route.fulfill(status=status, content_type="text/plain", body="Internal Server Error")
        else:
            route.continue_()
    page.route(url_pattern, _handler)


def inject_slow(page, url_pattern: str, delay_ms: int) -> None:
    # ponytail: rung 3 (native platform feature) -- page.wait_for_timeout yields the Playwright
    # greenlet instead of blocking the process the way time.sleep would (M1 debt A-44).
    def _handler(route):
        if url_matches(route.request.url, url_pattern):
            page.wait_for_timeout(delay_ms)
        route.continue_()
    page.route(url_pattern, _handler)


def clear_faults(page) -> None:
    page.unroute_all()
