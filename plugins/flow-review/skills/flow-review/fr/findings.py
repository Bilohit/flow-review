"""Demote findings that repeat unchanged from the previous run.

    BINDING -- Never headline a finding identical to the previous run's.
    Applies even when the finding is severe; a severity CHANGE re-promotes it, a repeat does not.
    A report that opens with the same three findings every run teaches its reader to skip it,
    and a QA tool nobody reads has failed regardless of what it found.
    why: council ruling 2026-08-22, spec section 8.7

Fingerprinting is deliberately coarse -- severity is excluded so that a P2 becoming a P0 is a
CHANGE rather than a new finding, and whitespace is normalized so a reworded space does not
manufacture novelty.
"""
from __future__ import annotations

import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_WS = re.compile(r"\s+")


def fingerprint(finding: dict) -> str:
    location = _WS.sub(" ", str(finding.get("location", ""))).strip().lower()
    # removesuffix strips exactly one trailing period, never a whole run of them -- rstrip(".")
    # would also eat an ellipsis, collapsing "...the button did nothing..." and "...did nothing"
    # into the same fingerprint. That is over-normalisation the docstring above does not license:
    # the coarse axes are severity and whitespace, not punctuation.
    text = _WS.sub(" ", str(finding.get("text", ""))).strip().lower().removesuffix(".")
    return f"{location}|{text}"


def demote_repeats(
    current: list[dict], previous: list[dict]
) -> tuple[list[dict], list[dict]]:
    # ponytail: a dict comprehension collapses duplicate fingerprints in `previous`, keeping
    # whichever entry comes last in list order -- if the previous run somehow filed the same
    # coarse claim twice, one of them silently loses its accumulated runs_seen. That double
    # filing is arguably a bug upstream (the same claim about the same location, filed twice),
    # not a case this module owes faithful handling. Not observed; upgrade path is matching by
    # consuming from a multiset (e.g. a dict of lists, popped as each current finding matches)
    # instead of a plain last-write-wins dict.
    prior = {fingerprint(f): f for f in previous}
    headline: list[dict] = []
    repeats: list[dict] = []

    for finding in current:
        match = prior.get(fingerprint(finding))
        if match is None or match.get("sev") != finding.get("sev"):
            headline.append(finding)
            continue
        demoted = dict(finding)
        # ponytail: repeat_of stores the immediate predecessor's ts, so across three or more
        # runs it chains one hop back per run rather than pointing at the first sighting.
        # Not observed, and runs_seen already answers "how long has this lingered" directly --
        # upgrade path, if ever needed, is carrying a first_seen field forward instead of ts.
        demoted["repeat_of"] = match.get("ts")
        demoted["runs_seen"] = int(match.get("runs_seen", 1)) + 1
        repeats.append(demoted)

    return headline, repeats
