from __future__ import annotations

import re
from pathlib import Path

import pytest

from flow_review.config import PROFILES, ROLES

ROOT = Path(__file__).resolve().parent
AGENTS = ROOT / "agents"

VALID_MODELS = {"haiku", "sonnet", "opus"}
ROLE_TO_FILE = {role: f"fr-{role}.md" for role in ROLES}


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} has no frontmatter"
    front = text.split("---", 2)[1]
    out: dict[str, str] = {}
    for line in front.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip()
    return out


def _profile_table(text: str) -> dict[str, str]:
    body = text.split("## Model profile", 1)[1]
    table: dict[str, str] = {}
    for line in body.splitlines():
        m = re.match(r"\|\s*(lean|default|max)\s*\|\s*(haiku|sonnet|opus)\s*\|", line.strip(), re.I)
        if m:
            table[m.group(1).lower()] = m.group(2).lower()
    return table


@pytest.mark.parametrize("role", ROLES)
def test_agent_file_exists(role):
    assert (AGENTS / ROLE_TO_FILE[role]).is_file(), f"missing agents/{ROLE_TO_FILE[role]}"


@pytest.mark.parametrize("role", ROLES)
def test_agent_has_required_frontmatter(role):
    front = _frontmatter(AGENTS / ROLE_TO_FILE[role])
    for key in ("name", "description", "model", "tools"):
        assert key in front, f"{ROLE_TO_FILE[role]} frontmatter missing {key!r}"
    assert front["model"] in VALID_MODELS
    assert front["model"] != "inherit"


@pytest.mark.parametrize("role", ROLES)
def test_agent_frontmatter_model_mirrors_default_profile(role):
    front = _frontmatter(AGENTS / ROLE_TO_FILE[role])
    assert front["model"] == PROFILES["default"][role]


@pytest.mark.parametrize("role", ROLES)
def test_agent_profile_table_mirrors_config_profiles_exactly(role):
    text = (AGENTS / ROLE_TO_FILE[role]).read_text(encoding="utf-8")
    assert "## Model profile" in text
    table = _profile_table(text)
    for profile in ("lean", "default", "max"):
        assert table.get(profile) == PROFILES[profile][role], (
            f"{ROLE_TO_FILE[role]} {profile!r} row is {table.get(profile)!r}, "
            f"config.PROFILES says {PROFILES[profile][role]!r}"
        )


def test_verifier_never_drops_below_sonnet_in_any_profile():
    text = (AGENTS / "fr-verifier.md").read_text(encoding="utf-8")
    table = _profile_table(text)
    assert table["lean"] in {"sonnet", "opus"}


def test_no_agent_uses_inherit_anywhere():
    for role in ROLES:
        text = (AGENTS / ROLE_TO_FILE[role]).read_text(encoding="utf-8")
        assert re.search(r"model:\s*inherit", text, re.I) is None


# --- A-24: the drive CLI is the only browser interface -----------------------------------

BANNED_BROWSER_TOOLS = (
    "playwright", "puppeteer", "mcp__playwright", "mcp__puppeteer", "mcp__browser",
    "browser_navigate", "browser_click", "browser_screenshot",
)


@pytest.mark.parametrize("role", ["explorer", "cold-eyes"])
def test_explorer_and_cold_eyes_name_the_drive_cli_as_their_browser_interface(role):
    text = (AGENTS / ROLE_TO_FILE[role]).read_text(encoding="utf-8")
    assert "flow-review drive" in text


@pytest.mark.parametrize("role", ["explorer", "cold-eyes"])
def test_explorer_and_cold_eyes_tools_frontmatter_includes_bash(role):
    front = _frontmatter(AGENTS / ROLE_TO_FILE[role])
    tools = [t.strip() for t in front["tools"].split(",")]
    assert "Bash" in tools


@pytest.mark.parametrize("role", ["explorer", "cold-eyes"])
def test_explorer_and_cold_eyes_never_name_an_mcp_or_direct_browser_tool(role):
    front = _frontmatter(AGENTS / ROLE_TO_FILE[role])
    tools_lower = front["tools"].lower()
    body_lower = (AGENTS / ROLE_TO_FILE[role]).read_text(encoding="utf-8").lower()
    for banned in BANNED_BROWSER_TOOLS:
        assert banned not in tools_lower, f"{ROLE_TO_FILE[role]} tools frontmatter names {banned!r}"
        # the body may only ever mention a banned tool to say it is forbidden -- "never" or
        # "must not" must appear on the same line as the mention, or the mention itself must not
        # exist at all; the simplest correct check is that the banned name never appears at all,
        # since this draft's fr-explorer/fr-cold-eyes text never needs to name a competing
        # browser tool even to prohibit it (it says "an MCP browser tool" generically instead).
        assert banned not in body_lower, f"{ROLE_TO_FILE[role]} body names {banned!r}"
