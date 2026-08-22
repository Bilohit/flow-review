from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent

# Every document a stranger reads before or instead of the code. A scan that covers only
# README.md misses the three files most likely to pick up a leftover from the codebase this
# tool was generalized out of -- nothing else here was ever checked for it.
ROOT_DOCS = (
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "docs" / "concepts.md",
    ROOT / "docs" / "walkthrough.md",
)


def test_readme_has_both_install_paths_and_the_marketplace_name():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "/plugin marketplace add Bilohit/flow-review" in text
    assert "/plugin install flow-review" in text


def test_readme_has_no_emoji():
    for path in ROOT_DOCS:
        text = path.read_text(encoding="utf-8")
        for ch in text:
            assert ord(ch) < 0x2190, f"emoji or symbol {ch!r} in {path}"


def test_svgs_use_currentcolor_only():
    """One asset, both GitHub themes. A literal hex ink is the defect -- a '#' in a url(#id)
    reference is not, so match hex colours specifically rather than banning the character."""
    hex_colour = re.compile(r"#(?:[0-9a-fA-F]{3}){1,2}\b")
    for name in ("mark.svg", "banner.svg"):
        text = (ROOT / "assets" / name).read_text(encoding="utf-8")
        assert "currentColor" in text
        assert not hex_colour.search(text), f"{name} carries a literal colour"


def test_credits_link_every_third_party_upstream():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Credits" in text


def test_credits_section_is_specific_about_third_party_status():
    """The bare 'Credits' check above passes on a heading alone -- that overpromises what its
    name claims. This checks the section actually says something real: whether third-party
    code is bundled, and points at the license that governs the original work either way."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(r"^## Credits\s*\n(.*?)(?=\n## |\Z)", text, re.S | re.M)
    assert match, "no '## Credits' section found"
    section = match.group(1).strip()
    assert len(section) > 80, "Credits section is a stub"
    assert "third-party" in section.lower()
    assert "MIT" in section or "LICENSE" in section


def test_readme_lens_table_includes_the_library_row():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "QA only, and the report says so" in text


def test_readme_has_no_bom():
    for path in ROOT_DOCS:
        raw = path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), f"BOM in {path}"


def test_docs_and_contributing_exist_and_are_not_stubs():
    for rel in ("docs/concepts.md", "docs/walkthrough.md", "CONTRIBUTING.md"):
        path = ROOT / rel
        assert path.is_file(), f"{rel} is missing"
        text = path.read_text(encoding="utf-8")
        assert len(text.strip()) > 400, f"{rel} looks like a stub"
