"""Structural + behavioral tests for the served dashboard page (E5 review fix):
header, report section, findings-list panel, and drawer focus management.
Real browser via Playwright against the dashboard_server fixture (conftest.py).
"""
from __future__ import annotations

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright


@pytest.fixture
def page(dashboard_server):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page()
        pg.goto(dashboard_server.url)
        pg.wait_for_selector('[data-role="lanes"]')
        yield pg
        browser.close()


@pytest.mark.web
def test_header_shows_progress_elapsed_budget_and_badge(page):
    assert page.locator('[data-role="progress"]').count() == 1
    assert page.locator('[data-role="elapsed"]').count() == 1
    assert page.locator('[data-role="budget"]').count() == 1
    badge = page.locator('[data-role="badge"]')
    assert badge.count() == 1
    # header text is self-explanatory + numeric, no subheading/description elements (rule-lint
    # covers the static markup; this covers what app.js builds at runtime).
    assert page.locator("h2, h3, h4, h5, h6").count() == 0
    assert page.locator("p").count() == 0


@pytest.mark.web
def test_report_section_renders_needs_attention_and_collapsed_groups(page):
    report = page.locator('[data-role="report"]')
    assert report.is_visible()
    assert "needs attention" in report.locator("summary").first.inner_text()
    # collapsed groups (opinions/repeats/refuted/not-exercised) exist but stay collapsed --
    # progressive disclosure, not headline.
    summaries = report.locator("details > summary").all_inner_texts()
    assert any("opinions" in s for s in summaries)
    assert any("repeats" in s for s in summaries)
    assert any("refuted" in s for s in summaries)
    assert any("not-exercised" in s for s in summaries)
    for details in report.locator("details").all()[1:]:
        assert details.get_attribute("open") is None


@pytest.mark.web
def test_findings_badge_click_opens_single_findings_list_panel(page):
    badge = page.locator('[data-role="badge"]')
    findings_list = page.locator('[data-role="findings-list"]')
    assert findings_list.is_hidden()
    badge.click()
    assert findings_list.is_visible()
    assert findings_list.locator(".finding-row").count() > 0
    # Escape closes the findings-list panel (E4 review fix).
    page.keyboard.press("Escape")
    assert findings_list.is_hidden()


@pytest.mark.web
def test_open_drawer_moves_focus_in_and_escape_returns_focus_to_trigger(page):
    row = page.locator(".finding-row").first
    row.click()
    drawer = page.locator('[data-role="drawer"]')
    assert drawer.is_visible()
    # focus must land inside the drawer, not stay on the trigger or fall back to <body>.
    focused_in_drawer = page.evaluate(
        "document.querySelector('[data-role=\"drawer\"]').contains(document.activeElement)"
    )
    assert focused_in_drawer
    page.keyboard.press("Escape")
    assert drawer.is_hidden()
    # focus returns to the row that opened the drawer.
    is_row_focused = row.evaluate("el => el === document.activeElement")
    assert is_row_focused
