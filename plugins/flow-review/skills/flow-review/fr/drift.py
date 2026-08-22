"""Compare the config against the repository's current shape.

This is not a new subsystem. The preconditions gate already walks every surface before a run;
this adds one structural comparison to that same walk and reports it as one line at the GO gate.

The comparison stays DUMB and STRUCTURAL -- surface set and launch command, never semantics.
A drift check that flags a harmless rename every run trains the user to click through the gate,
which loses the gate entirely.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fr import audit
from fr.config import Config

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# provenance keys/values are bare strings at the point of use otherwise -- a typo in one spot
# and a check silently stops firing. Values are constrained to config.VALID_PROVENANCE.
DECLINED_PROVENANCE_KEY = "declined"
DECLINED_PROVENANCE_VALUE = "user"

# Marks a surface as PROPOSED BY fr.audit rather than hand-added through the setup interview
# (an adb device, a `custom` driver, anything a user typed in themselves). audit.detect only
# recognizes package.json/pyproject.toml/openapi -- it has no way to see a hand-added surface
# in the repo at all, so treating that surface's absence from `detected` as drift would report
# it as "removed" on every single run. Only a surface carrying this exact marker is eligible to
# be reported missing; a surface without it is treated as hand-added and never reported missing.
# When in doubt, do not report: a missed removal is a quiet gap, a false one destroys the gate.
DETECTED_PROVENANCE_KEY = "origin"
DETECTED_PROVENANCE_VALUE = "audited"


def detect_drift(cfg: Config, root: Path) -> list[str]:
    detected = audit.detect(Path(root))
    # ponytail: keyed by name alone, ignoring kind, so a pyproject script named "web" could
    # collide with a UI surface also named "web" and report drift against the wrong surface.
    # Not observed, not worth building for; upgrade path is keying by (kind, name) instead.
    by_name = {s.name: s for s in cfg.surfaces}
    messages: list[str] = []

    for candidate in detected:
        surface = by_name.get(candidate.name)
        if surface is None:
            messages.append(
                f"drift: surface {candidate.name!r} detected in the repo but not in config "
                f"({candidate.evidence}) -- run /flow-review --reconfigure to add it"
            )
            continue
        if surface.provenance.get(DECLINED_PROVENANCE_KEY) == DECLINED_PROVENANCE_VALUE:
            continue
        if candidate.launch and surface.launch and candidate.launch != surface.launch:
            messages.append(
                f"drift: surface {surface.name!r} launch command changed "
                f"({surface.launch!r} -> {candidate.launch!r}) -- run /flow-review --reconfigure"
            )

    detected_names = {c.name for c in detected}
    for surface in cfg.surfaces:
        if surface.provenance.get(DETECTED_PROVENANCE_KEY) != DETECTED_PROVENANCE_VALUE:
            # Hand-added surface -- audit.detect never could have seen it, so its absence here
            # proves nothing about the repo. Never report it missing.
            continue
        if surface.name not in detected_names:
            messages.append(
                f"drift: surface {surface.name!r} is configured but its evidence is gone from "
                f"the repo -- run /flow-review --reconfigure to remove or update it"
            )

    return messages
