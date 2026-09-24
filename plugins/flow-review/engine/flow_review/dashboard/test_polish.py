"""Dashboard polish (2026-09-24 plan): browser checks for the six screenshot defects."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright

PAGE = Path(__file__).parent / "page"


@pytest.fixture
def page(dashboard_server):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page()
        pg.goto(dashboard_server.url)
        pg.wait_for_selector('[data-role="lanes"] .lane')
        yield pg
        browser.close()


@pytest.mark.web
def test_lanes_region_ends_at_its_last_lane(page):
    gap = page.evaluate("""() => {
        const lanes = document.querySelector('[data-role="lanes"]');
        const last = lanes.querySelector('.lane:last-child');
        return lanes.getBoundingClientRect().bottom - last.getBoundingClientRect().bottom;
    }""")
    assert gap <= 2, f"lanes region stretches {gap}px past its content (grey band)"


@pytest.mark.web
def test_report_group_labels_use_the_ui_font(page):
    family = page.evaluate(
        "() => getComputedStyle(document.querySelector('[data-role=\"report\"] summary')).fontFamily")
    assert "Schibsted" in family, family


def test_severity_dot_symbol_is_a_filled_circle():
    svg = (PAGE / "icons" / "sprite.svg").read_text(encoding="utf-8")
    start = svg.index('<symbol id="severity-dot"')
    symbol = svg[start:svg.index("</symbol>", start)]
    assert "<circle" in symbol and 'fill="currentColor"' in symbol
    assert "<path" not in symbol, "the Phosphor ring path renders hollow"
