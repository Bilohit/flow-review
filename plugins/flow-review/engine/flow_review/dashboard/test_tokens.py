from __future__ import annotations

import re
from pathlib import Path

TOKENS = Path(__file__).parent / "page" / "tokens.css"

REQUIRED_TOKENS = [
    "--bg", "--panel", "--border", "--text-1", "--text-2", "--accent", "--radius",
    "--sev-p0", "--sev-p1", "--sev-p2", "--font-ui", "--font-mono",
]


def test_tokens_file_exists():
    assert TOKENS.exists(), "page/tokens.css must exist (E3)"


def test_root_defines_all_required_tokens():
    css = TOKENS.read_text(encoding="utf-8")
    root_block = re.search(r":root\s*\{([^}]*)\}", css, re.DOTALL)
    assert root_block, "tokens.css must define a base :root block"
    body = root_block.group(1)
    missing = [t for t in REQUIRED_TOKENS if t not in body]
    assert not missing, f"missing tokens in :root: {missing}"


def test_dark_theme_overrides_are_present_both_ways():
    css = TOKENS.read_text(encoding="utf-8")
    assert "@media (prefers-color-scheme: dark)" in css, "OS-driven dark mode is missing"
    assert '[data-theme="dark"]' in css, "explicit dark-toggle override is missing"


def test_radius_is_4px():
    css = TOKENS.read_text(encoding="utf-8")
    match = re.search(r"--radius:\s*([^;]+);", css)
    assert match and match.group(1).strip() == "4px"


def test_palette_validator_run_is_recorded_in_a_comment():
    css = TOKENS.read_text(encoding="utf-8")
    assert "validate_palette.js" in css, (
        "A-23: the severity palette validator is a one-time MANUAL check -- its command "
        "and PASS result must be recorded in a tokens.css comment, not re-run in CI."
    )
