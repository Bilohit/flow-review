"""Compare the config against the repository's current shape (H1, H2).

Matching a detected candidate to a configured surface is done by id, never by display name
(H2): a surface's `name` is free text a user may rename at any time: A2 spun `id` out
specifically so this comparison has something stable to key on. `runnable_surfaces` is the one
place "should this surface be in the run plan at all" is decided (H1): declined and
pending-driver surfaces never reach it.
"""
from __future__ import annotations

from pathlib import Path

from flow_review import audit
from flow_review.config import Config, Surface, slug

DETECTED_PROVENANCE_KEY = "origin"
DETECTED_PROVENANCE_VALUE = "audited"

# The literal "pending" driver value: A9 (same wave, no dependency between the two tasks) is
# what starts writing this value into VALID_DRIVERS/Surface.driver. This module does not import
# a shared constant for it so neither task depends on the other having landed first; the string
# itself is the contract.
_PENDING_DRIVER = "pending"


def detect_drift(cfg: Config, root: Path) -> list[str]:
    detected = audit.detect(Path(root))
    by_id = {s.id: s for s in cfg.surfaces}
    messages: list[str] = []

    for candidate in detected:
        candidate_id = slug(candidate.name)
        surface = by_id.get(candidate_id)
        if surface is None:
            messages.append(
                f"drift: surface {candidate_id!r} detected in the repo but not in config "
                f"({candidate.evidence}) -- run /flow-review --reconfigure to add it"
            )
            continue
        if surface.declined:
            continue
        if candidate.launch and surface.launch and candidate.launch != surface.launch:
            messages.append(
                f"drift: surface {surface.id!r} launch command changed "
                f"({surface.launch!r} -> {candidate.launch!r}) -- run /flow-review --reconfigure"
            )

    detected_ids = {slug(c.name) for c in detected}
    for surface in cfg.surfaces:
        if surface.provenance.get(DETECTED_PROVENANCE_KEY) != DETECTED_PROVENANCE_VALUE:
            continue
        if surface.id not in detected_ids:
            messages.append(
                f"drift: surface {surface.id!r} is configured but its evidence is gone from "
                f"the repo -- run /flow-review --reconfigure to remove or update it"
            )

    return messages


def runnable_surfaces(cfg: Config) -> list[Surface]:
    return [s for s in cfg.surfaces if not s.declined and s.driver != _PENDING_DRIVER]
