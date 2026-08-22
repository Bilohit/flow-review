from __future__ import annotations

from fr import findings


def _f(sev="P1", location="web / settings / f01", claim="The save button is 8px from the edge.", ts="t1"):
    return {"ts": ts, "sev": sev, "location": location, "text": claim}


def test_fingerprint_ignores_timestamp_and_whitespace():
    a = _f(ts="t1", claim="The  save button   is off.")
    b = _f(ts="t9", claim="the save button is off.")
    assert findings.fingerprint(a) == findings.fingerprint(b)


def test_fingerprint_separates_different_locations():
    assert findings.fingerprint(_f(location="web / a / f01")) != findings.fingerprint(_f(location="web / b / f01"))


def test_fingerprint_strips_only_one_trailing_period_not_an_ellipsis():
    with_ellipsis = _f(claim="The dialog never closes...")
    without_period = _f(claim="The dialog never closes")
    assert findings.fingerprint(with_ellipsis) != findings.fingerprint(without_period)


def test_an_unchanged_repeat_is_demoted():
    previous = [_f(ts="old")]
    current = [_f(ts="new")]
    headline, repeats = findings.demote_repeats(current, previous)
    assert headline == []
    assert len(repeats) == 1
    assert repeats[0]["repeat_of"] == "old"
    assert repeats[0]["runs_seen"] == 2


def test_a_severity_change_keeps_it_in_the_headline():
    previous = [_f(sev="P2", ts="old")]
    current = [_f(sev="P0", ts="new")]
    headline, repeats = findings.demote_repeats(current, previous)
    assert len(headline) == 1
    assert repeats == []


def test_a_new_finding_stays_in_the_headline():
    headline, repeats = findings.demote_repeats([_f(claim="Something else entirely.")], [_f()])
    assert len(headline) == 1
    assert repeats == []


def test_runs_seen_accumulates_across_runs():
    previous = [dict(_f(ts="old"), runs_seen=4)]
    headline, repeats = findings.demote_repeats([_f(ts="new")], previous)
    assert repeats[0]["runs_seen"] == 5


def test_no_previous_run_means_everything_is_headline():
    headline, repeats = findings.demote_repeats([_f(), _f(claim="Another.")], [])
    assert len(headline) == 2
    assert repeats == []
