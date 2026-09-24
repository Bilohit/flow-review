from flow_review.web import variants


class _FakeSurface:
    def __init__(self, options):
        self.options = options


def test_plan_variants_quick_mode_returns_none():
    surface = _FakeSurface({"viewport": [{"width": 375, "height": 812}]})
    assert variants.plan_variants(surface, "quick") == []


def test_plan_variants_expands_viewport_and_modes():
    surface = _FakeSurface({
        "viewport": [{"width": 375, "height": 812}, {"width": 1280, "height": 800}],
    })
    plan = variants.plan_variants(surface, "full")
    kinds = [v["kind"] for v in plan]
    assert kinds.count("viewport") == 2
    assert kinds.count("color-scheme") == 2
    assert kinds.count("keyboard-only") == 1
    assert kinds.count("reduced-motion") == 1
    assert kinds.count("storage-state") == 2


def test_plan_variants_goal_and_auto_and_full_all_expand():
    # 1 viewport + 2 color-scheme + 1 keyboard-only + 1 reduced-motion + 2 storage-state = 7.
    # (Brief's literal test text says "== 6"; that undercounts by one relative to the brief's
    # own reference implementation and to test_plan_variants_expands_viewport_and_modes above,
    # which for 2 viewports asserts counts summing to 8 = N + 6. Fixed here for internal
    # consistency; see task-B7-report.md.)
    surface = _FakeSurface({"viewport": [{"width": 1280, "height": 800}]})
    for mode in ("goal", "auto", "full"):
        assert len(variants.plan_variants(surface, mode)) == 7


import pytest

pytest.importorskip("playwright")


@pytest.mark.web
def test_run_variant_keyboard_only_reaches_load_button(webapp_server, tmp_path):
    from flow_review.web.driver import WebDriver
    base_url, _ = webapp_server
    log = {"steps": [{"action": "click", "locator": {"testid": "load-button"}}]}
    result = variants.run_variant(
        lambda **kw: WebDriver(headless=True, **kw), base_url, log,
        {"kind": "keyboard-only", "params": {}},
    )
    assert result["findings"] == [] and result["status"] == "clean"
