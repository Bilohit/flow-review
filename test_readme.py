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
    # The skill calls the `flow-review` CLI from its first step, so the engine and the browser
    # must be installed before the first /flow-review (found by the R12 end-to-end run).
    assert ('pip install "flow-review[web] @ git+https://github.com/Bilohit/flow-review'
            '#subdirectory=plugins/flow-review/engine"') in text
    assert "python -m playwright install chromium" in text


def test_readme_has_no_emoji():
    for path in ROOT_DOCS:
        text = path.read_text(encoding="utf-8")
        for ch in text:
            assert ord(ch) < 0x2190, f"emoji or symbol {ch!r} in {path}"


def test_svgs_are_dark_ink_on_an_explicit_white_plate():
    """These marks ship on a white plate, so the ink is a fixed near-black rather than
    currentColor: an inherited ink on a white ground goes invisible the moment the host
    page is dark. Both halves are asserted, because either one alone is the bug."""
    for name in ("mark.svg", "banner.svg"):
        text = (ROOT / "assets" / name).read_text(encoding="utf-8")
        assert "currentColor" not in text, f"{name} inherits its ink onto a white plate"
        assert 'fill="#FFFFFF"' in text, f"{name} has no white plate"
        assert "#141414" in text, f"{name} does not use the fixed ink"


def test_dark_banner_is_light_ink_on_an_explicit_dark_plate():
    """The dark variant is served by the README's <picture> element on dark GitHub
    themes; the same fixed-ink rule applies with the roles reversed."""
    text = (ROOT / "assets" / "banner-dark.svg").read_text(encoding="utf-8")
    assert "currentColor" not in text, "banner-dark.svg inherits its ink"
    assert 'fill="#0D0D0D"' in text, "banner-dark.svg has no dark plate"
    assert "#F2F2F2" in text, "banner-dark.svg does not use the light ink"


def test_readme_opens_with_the_theme_aware_banner():
    """The banner is the first thing rendered on the repository page, and the <picture>
    element is what serves the dark variant. If either reference goes, the image simply
    vanishes on one theme without failing anywhere else."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert text.lstrip().startswith("<picture>"), "README does not open with <picture>"
    head = text[:400]
    assert "assets/banner-dark.svg" in head
    assert "assets/banner.svg" in head


def test_credits_section_exists_and_is_not_a_stub():
    """A bare '## Credits' heading with nothing under it is as good as no section -- this
    guards the section against shrinking back to a stub."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(r"^## Credits\s*\n(.*?)(?=\n## |\Z)", text, re.S | re.M)
    assert match, "no '## Credits' section found"
    section = match.group(1).strip()
    assert len(section) > 80, "Credits section is a stub"


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


def test_readme_no_longer_claims_stdlib_only():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Standard library only" not in text
    assert "no third-party packages" not in text.lower()


def test_readme_states_the_managed_venv_and_github_only_install():
    # A-27: no PyPI package; the engine installs from the plugin's own folder (sourced from GitHub).
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "flow-review setup-env" in text
    assert "plugins/flow-review/engine" in text
    assert not re.search(r"\bpypi\b", text, re.I)


def test_contributing_no_longer_claims_stdlib_only():
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "no dependencies to install" not in text.lower()


def test_docs_no_longer_reference_the_v1_findings_module():
    text = (ROOT / "docs" / "concepts.md").read_text(encoding="utf-8")
    assert "fr/findings.py" not in text
