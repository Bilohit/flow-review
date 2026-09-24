from types import SimpleNamespace

from flow_review.web import variants


class _FakeSurface:
    def __init__(self, options):
        self.options = options


class _FakeVariantDriver:
    """Just enough of WebDriver for run_variant/replay_one without a real browser."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.page = SimpleNamespace(url="http://x/")

    def launch(self, base_url):
        self.page.url = base_url

    def goto(self, path):
        self.page.url = "http://x" + path

    def click(self, locator):
        pass

    def fill(self, locator, value):
        pass

    def begin_step(self, index):
        pass

    def end_step(self):
        pass

    def close(self):
        pass

    def storage_state(self):
        return "{}"


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


def test_variant_flow_id_tags_the_base_flow_id_per_kind():
    assert variants._variant_flow_id("sign-in", {"kind": "viewport",
                                                  "params": {"width": 390, "height": 844}}
                                      ) == "sign-in@viewport:390x844"
    assert variants._variant_flow_id("sign-in", {"kind": "color-scheme",
                                                  "params": {"scheme": "dark"}}
                                      ) == "sign-in@color-scheme:dark"
    assert variants._variant_flow_id("sign-in", {"kind": "storage-state",
                                                  "params": {"state": "new"}}
                                      ) == "sign-in@storage-state:new"
    assert variants._variant_flow_id("sign-in", {"kind": "keyboard-only", "params": {}}
                                      ) == "sign-in@keyboard-only"
    assert variants._variant_flow_id("sign-in", {"kind": "reduced-motion", "params": {}}
                                      ) == "sign-in@reduced-motion"


def test_variant_flow_id_differs_for_light_and_dark():
    light = variants._variant_flow_id("sign-in", {"kind": "color-scheme",
                                                   "params": {"scheme": "light"}})
    dark = variants._variant_flow_id("sign-in", {"kind": "color-scheme",
                                                  "params": {"scheme": "dark"}})
    assert light != dark


def test_run_variant_threads_measure_hook_and_tags_the_finding_flow_id():
    log = {"surface_id": "webapp", "flow_id": "sign-in", "steps": [{"action": "goto", "url": "/"}]}
    variant = {"kind": "color-scheme", "params": {"scheme": "dark"}}
    calls = []

    def hook(driver, surface_id, flow_id, route, step_index):
        calls.append((surface_id, flow_id, route))
        return [{"surface_id": surface_id, "flow_id": flow_id, "rule": "contrast.aa",
                  "route": route, "locator": "", "sev": "P2", "text": "low contrast",
                  "evidence": [], "disposition": "engine"}]

    result = variants.run_variant(lambda **kw: _FakeVariantDriver(**kw), "http://x", log,
                                   variant, measure=hook)

    assert result["flow_id"] == "sign-in@color-scheme:dark"
    assert calls and calls[0][1] == "sign-in@color-scheme:dark"
    assert result["findings"][0]["rule"] == "contrast.aa"
    assert result["findings"][0]["sev"] == "P2"
    assert result["findings"][0]["flow_id"] == "sign-in@color-scheme:dark"


def test_run_all_quick_mode_runs_nothing_and_never_launches_a_driver():
    surface = _FakeSurface({"viewport": [{"width": 375, "height": 812}]})

    def boom(**kw):
        raise AssertionError("driver must not be launched when the plan is empty")

    results = variants.run_all(boom, "http://x", {"flow_id": "f", "steps": []}, surface,
                                storage_state_dir=None, mode="quick")
    assert results == []


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
