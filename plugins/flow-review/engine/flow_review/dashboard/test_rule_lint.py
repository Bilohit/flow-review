# plugins/flow-review/engine/flow_review/dashboard/test_rule_lint.py
from __future__ import annotations

import re
from pathlib import Path

PAGE = Path(__file__).parent / "page"


def _all_markup_text() -> str:
    # index.html plus any innerHTML/template strings app.js might build client-side --
    # scanned as text since app.js has no build step to statically render.
    html = (PAGE / "index.html").read_text(encoding="utf-8")
    js = (PAGE / "app.js").read_text(encoding="utf-8")
    return html + "\n" + js


def test_no_subheading_or_description_elements_anywhere():
    text = _all_markup_text()
    assert not re.search(r"<h[2-6][\s>]", text, re.IGNORECASE)
    assert not re.search(r"<p[\s>]", text, re.IGNORECASE)
    assert "class=\"description\"" not in text and "class='description'" not in text


def test_every_icon_only_button_has_aria_label_and_title():
    text = _all_markup_text()
    for m in re.finditer(r"<button[^>]*>(.*?)</button>", text, re.DOTALL):
        attrs, inner = m.group(0), m.group(1)
        if "<svg" in inner and not re.search(r">\s*\S", inner):
            assert 'aria-label="' in attrs
            assert 'title="' in attrs


def test_no_hardcoded_colors_outside_tokens_css():
    for path in PAGE.glob("*.css"):
        if path.name == "tokens.css":
            continue
        css = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
        assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", css), f"hex color in {path.name}"
        assert not re.findall(r"\brgba?\([^)]*\)", css), f"rgb()/rgba() in {path.name}"


def test_reduced_motion_media_query_present():
    css = (PAGE / "app.css").read_text(encoding="utf-8")
    assert "@media (prefers-reduced-motion: reduce)" in css


def test_both_themes_defined_in_tokens():
    css = (PAGE / "tokens.css").read_text(encoding="utf-8")
    assert "@media (prefers-color-scheme: dark)" in css
    assert '[data-theme="dark"]' in css
    assert '[data-theme="light"]' in css or ':root:not([data-theme="dark"])' in css
