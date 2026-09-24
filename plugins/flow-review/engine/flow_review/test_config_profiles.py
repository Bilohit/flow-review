from __future__ import annotations

import pytest

from flow_review.config import PROFILES, ROLES, Config, resolve_model

EXPECTED_ROLES = {"explorer", "cold-eyes", "lens", "replay-repair", "triage", "verifier"}


def _cfg(profile="default", overrides=None):
    return Config(schema_version=2, generator_version="0", surfaces=[],
                  model_profile=profile, role_overrides=overrides or {})


def test_profiles_has_exactly_lean_default_max():
    assert set(PROFILES) == {"lean", "default", "max"}


def test_every_profile_covers_every_role():
    for profile, mapping in PROFILES.items():
        assert set(mapping) == EXPECTED_ROLES, f"profile {profile!r} covers {set(mapping)}"


def test_roles_constant_matches_the_role_set():
    assert set(ROLES) == EXPECTED_ROLES


def test_every_model_is_a_real_tier():
    for mapping in PROFILES.values():
        for model in mapping.values():
            assert model in {"haiku", "sonnet", "opus"}


def test_verifier_is_never_below_sonnet_in_any_profile():
    for profile, mapping in PROFILES.items():
        assert mapping["verifier"] in {"sonnet", "opus"}, (
            f"{profile} drops verifier to {mapping['verifier']!r}"
        )


def test_resolve_model_reads_the_configured_profile():
    cfg = _cfg(profile="lean")
    assert resolve_model(cfg, "explorer") == PROFILES["lean"]["explorer"]


def test_resolve_model_role_override_wins_over_profile():
    cfg = _cfg(profile="default", overrides={"lens": "opus"})
    assert resolve_model(cfg, "lens") == "opus"


def test_resolve_model_rejects_an_unknown_role():
    cfg = _cfg()
    with pytest.raises(ValueError):
        resolve_model(cfg, "fr-lens")  # the fr- prefix is a file-naming convention, not a role


def test_resolve_model_never_returns_inherit():
    for profile in PROFILES:
        cfg = _cfg(profile=profile)
        for role in ROLES:
            assert resolve_model(cfg, role) != "inherit"
