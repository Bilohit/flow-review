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
