"""Critique lenses, keyed by surface kind and shipped as data.

A lens is a critique question plus the evidence it is allowed to answer from. Nothing more.
Making lenses data rather than code is what lets a user add their own without touching the tool.

Lens sets are PER SURFACE KIND and never universal. "No pixels" is not "no interface": a CLI's
flags, help text and errors are its interface, and an API's error shapes and naming are its
contract surface. The genuinely critique-free case is narrower -- a library called only from
code has no human-facing edge, so it gets QA and an explicit statement that there is no
critique, never an empty critique section.

Sprawl guard: a new lens set is added when a real user asks for one, never on a hunch.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


@dataclass(frozen=True)
class Lens:
    name: str
    kind: str
    evidence_required: str
    question: str
    fast: bool = False


_UI = (
    Lens("identity", "ui", "computed style values compared against the project's tokens",
         "Does this surface use the project's own type, colour and radius tokens?", fast=True),
    Lens("first-time-user", "ui", "a screenshot plus the step sequence taken to reach it",
         "Could someone who has never seen this product complete this flow unaided?", fast=True),
    Lens("accessibility", "ui", "contrast ratios, focus order, hit-target rects, roles",
         "Can this be operated without a mouse, and read at low vision?"),
    Lens("hierarchy", "ui", "bounding rects and computed font sizes",
         "Does visual weight match actual importance on this screen?"),
    Lens("craft", "ui", "computed transition durations, rect intersections, alignment deltas",
         "Are alignment, spacing and motion consistent with the rest of the product?"),
    Lens("copy", "ui", "the literal strings rendered on screen",
         "Does every label, error and empty state say something true and useful?"),
)

_CLI = (
    Lens("discoverability", "cli", "the output of --help and of an invalid invocation",
         "Can a new user find the command they need without reading source?", fast=True),
    Lens("error-message quality", "cli", "stderr text from each failure path exercised",
         "Does each error say what went wrong and what to do next?", fast=True),
    Lens("exit-code semantics", "cli", "the numeric exit code of each exercised path",
         "Does the exit code distinguish success, user error and internal failure?"),
    Lens("help usability", "cli", "the full --help text and the terminal width it was rendered at",
         "Is the help readable at 80 columns and ordered by what people need first?"),
)

_API = (
    Lens("contract consistency", "api", "the response bodies captured per endpoint",
         "Do naming, casing and pagination behave the same across every endpoint?", fast=True),
    Lens("error shapes", "api", "the response body of each error path exercised",
         "Does every error return the same shape with an actionable message?", fast=True),
    Lens("status codes", "api", "the HTTP status of each exercised request",
         "Does each status code mean what the specification says it means?"),
    Lens("pagination", "api", "two consecutive pages captured from a list endpoint",
         "Is paging stable, bounded and consistent across list endpoints?"),
    Lens("doc drift", "api", "the served responses compared against the checked-in schema",
         "Does the documented contract match what the service actually returns?"),
)

LENS_SETS: dict[str, tuple[Lens, ...]] = {
    "ui": _UI,
    "cli": _CLI,
    "api": _API,
    "library": (),
}


def for_kind(kind: str) -> tuple[Lens, ...]:
    return LENS_SETS.get(kind, ())


def has_critique(kind: str) -> bool:
    return bool(for_kind(kind))
