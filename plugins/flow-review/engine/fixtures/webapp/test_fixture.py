import json
import urllib.error
import urllib.request


def test_webapp_server_serves_fixture_and_fail_route(webapp_server):
    base_url, requests_log = webapp_server

    body = urllib.request.urlopen(base_url + "/").read().decode()
    assert "muted-note" in body
    assert "cta-button" in body
    assert 'id="pw"' in body and 'data-testid="pw-input"' in body
    assert 'href="docs.html"' not in body  # orphan: docs.html not linked from index

    docs = urllib.request.urlopen(base_url + "/docs.html").read().decode()
    assert "export" in docs.lower()

    tokens = json.loads(urllib.request.urlopen(base_url + "/tokens.json").read())
    assert tokens["color.primary"] == "#1a56db"

    try:
        urllib.request.urlopen(base_url + "/api/fail")
        assert False, "expected HTTPError"
    except urllib.error.HTTPError as exc:
        assert exc.code == 500

    assert any(r["path"] == "/api/fail" and r["status"] == 500 for r in requests_log)
