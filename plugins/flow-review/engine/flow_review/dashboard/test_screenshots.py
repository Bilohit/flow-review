"""Not a correctness gate -- captures reference screenshots for a manual look.
Requires `playwright install chromium` and a running fixture-backed `flow-review serve`.
Run explicitly: pytest test_screenshots.py -q -m manual
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.manual

SCENARIOS = [
    ("light", 1), ("dark", 1), ("light", 4), ("dark", 4),
    ("light", 8), ("dark", 8),
]


@pytest.mark.parametrize("theme,lane_count", SCENARIOS)
def test_capture_theme_and_lane_variants(theme, lane_count, dashboard_server, tmp_path):
    # `dashboard_server` fixture (conftest.py, owned by this task): starts `flow-review serve`
    # against a fixture run folder seeded with `lane_count` surfaces via events.append, and
    # tears it down after the test.
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(color_scheme=theme)
        page.goto(dashboard_server.url)
        page.wait_for_selector('[data-role="lanes"]')
        import os
        out_dir = Path(os.environ.get("FR_SHOTS_DIR", str(tmp_path)))
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{theme}-{lane_count}lane.png"
        page.screenshot(path=str(out), full_page=True)
        browser.close()
    assert out.exists() and out.stat().st_size > 0
    # No pixel assertions here -- the exit criterion is a human (or the impeccable-finish-reviewer
    # agent) looking at these four PNGs and confirming: no subheadings/descriptions, badge tint
    # correct, auto-grid looks right at 1 and 4 lanes, both themes legible.
