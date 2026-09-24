from __future__ import annotations

import re
from pathlib import Path

PAGE = Path(__file__).parent / "page"


def _js() -> str:
    return (PAGE / "app.js").read_text(encoding="utf-8")


def _html() -> str:
    return (PAGE / "index.html").read_text(encoding="utf-8")


def _css() -> str:
    return (PAGE / "app.css").read_text(encoding="utf-8")


# ---- Step 1: bootstrap & state load --------------------------------------

def test_bootstraps_from_embedded_state_or_fetches_and_streams():
    js = _js()
    assert "getElementById('state-data')" in js or 'getElementById("state-data")' in js
    assert "fetch('/state')" in js or 'fetch("/state")' in js
    assert "new EventSource('/events')" in js or 'new EventSource("/events")' in js
    assert re.search(r"function patch\s*\(", js)


# ---- Step 2: no subheadings / descriptions in the static shell -----------

def test_index_has_no_h2_to_h6_or_description_markup():
    html = _html()
    assert not re.search(r"<h[2-6][\s>]", html, re.IGNORECASE), "no subheadings anywhere (spec §11)"
    assert "<p " not in html and "<p>" not in html, "no description paragraphs in the shell"


# ---- Step 2: live patch preserving scroll + open drawer -------------------

def test_patch_preserves_lane_scroll_and_open_drawer():
    js = _js()
    assert "scrollTop" in js, "scroll position must be saved/restored across a patch"
    assert "openDrawerId" in js
    # the lane container is diffed by key (surface_id), never wiped wholesale
    assert "innerHTML = ''" not in js and 'innerHTML = ""' not in js


# ---- Step 3: lane grid render (auto-fit, keyed, text-safe) ---------------

def test_lanes_grid_uses_auto_fit_minmax_not_fixed_columns():
    css = _css()
    lanes_block = re.search(r"\.lanes\s*\{([^}]*)\}", css, re.DOTALL)
    assert lanes_block, "app.css must define a .lanes grid"
    body = lanes_block.group(1)
    assert "auto-fit" in body or "auto-fill" in body, "fixes M7: must not be a hardcoded 3-col grid"
    assert re.search(r"minmax\(", body), "auto-grid needs minmax() to size lanes"
    assert not re.search(r"repeat\(\s*\d+\s*,", body), "no hardcoded lane count"


def test_render_lanes_is_keyed_and_uses_textcontent_for_user_text():
    js = _js()
    assert re.search(r"function renderLanes\s*\(", js)
    assert "dataset.surfaceId" in js
    assert ".textContent =" in js
    assert ".innerHTML =" not in js, "user text (step labels, API/CLI output) must never use innerHTML (M8)"


# ---- Step 4: badge (tint, hover split, click list, one eased P0 flash) ---

def test_badge_tint_hover_click_and_p0_flash():
    js = _js()
    assert re.search(r"function renderBadge\s*\(", js)
    assert re.search(r"`sev-\$\{.*worst_sev", js), "badge class must tint by worst_sev"
    assert "el.title =" in js, "hover split (P0/P1/P2) is the accessible title, not a tooltip lib"
    assert "badge-flash" in js
    assert "animationend" in js, "the P0 highlight is one eased animation, removed after it plays"
    assert "addEventListener('click'" in js or 'addEventListener("click"' in js


# ---- Step 5: drawer (evidence per type) + triage + keyboard shortcuts ----

def test_drawer_evidence_dispatch_and_triage_and_keyboard_shortcuts():
    js = _js()
    assert re.search(r"function openDrawer\s*\(", js)
    assert re.search(r"function renderEvidence\s*\(", js)
    assert "before/after" in js or "beforeAfter" in js or "before_after" in js
    assert re.search(r"function triage\s*\(", js)
    assert "'/triage'" in js or '"/triage"' in js
    assert "finding_id" in js and "state" in js
    assert "addEventListener('keydown'" in js or 'addEventListener("keydown"' in js
    assert "if (!openDrawerId) return" in js, "triage keys must be scoped to an open drawer, never lane rows"
    assert "'Escape'" in js or '"Escape"' in js


# ---- Step 6: theme toggle (OS + explicit, persisted) ----------------------

def test_theme_toggle_sets_data_theme_and_persists():
    js = _js()
    assert "data-role=\"theme-toggle\"" in _html() or "data-role='theme-toggle'" in _html()
    assert "documentElement.dataset.theme" in js or "documentElement.setAttribute('data-theme'" in js
    assert "localStorage" in js
    assert "try {" in js and "catch" in js, "storage access must be wrapped -- private windows can throw"
