from __future__ import annotations

from fr.config import VALID_KINDS
from fr import lenses


def test_ui_keeps_the_six_named_lenses():
    names = [lens.name for lens in lenses.for_kind("ui")]
    assert names == ["identity", "first-time-user", "accessibility", "hierarchy", "craft", "copy"]


def test_cli_has_its_own_named_set_not_the_ui_one():
    names = {lens.name for lens in lenses.for_kind("cli")}
    assert "discoverability" in names
    assert "visual hierarchy" not in names
    assert names.isdisjoint({lens.name for lens in lenses.for_kind("ui")})


def test_api_has_its_own_set():
    names = {lens.name for lens in lenses.for_kind("api")}
    assert {"contract consistency", "error shapes"} <= names


def test_a_library_has_no_critique_and_says_so():
    assert lenses.for_kind("library") == ()
    assert lenses.has_critique("library") is False


def test_every_valid_kind_is_covered():
    for kind in VALID_KINDS:
        assert kind in lenses.LENS_SETS


def test_every_lens_demands_evidence():
    for kind in VALID_KINDS:
        for lens in lenses.for_kind(kind):
            assert lens.evidence_required, f"{lens.name} must state what evidence it needs"
            assert lens.question.endswith("?"), f"{lens.name} must ask a question"


def test_fast_mode_is_a_small_subset():
    fast = [lens for lens in lenses.for_kind("ui") if lens.fast]
    assert 0 < len(fast) <= 2
