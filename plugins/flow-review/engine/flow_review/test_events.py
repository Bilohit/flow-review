from __future__ import annotations

import json
import re
import uuid

import pytest

from flow_review import events


@pytest.fixture(autouse=True)
def _clean_registry():
    events.clear_secrets()
    yield
    events.clear_secrets()


def test_now_iso_has_millisecond_precision_and_z_suffix():
    ts = events.now_iso()
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$", ts), ts


def test_append_writes_one_json_line_built_with_json_dumps(tmp_path):
    written = events.append(tmp_path, {"type": "step", "surface": "web", "state": "ok"})
    text = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert text.count("\n") == 1
    line = json.loads(text.strip())
    assert line == written
    assert line["type"] == "step"
    assert "ts" in line


def test_append_fills_ts_only_when_absent(tmp_path):
    written = events.append(tmp_path, {"type": "step", "ts": "2020-01-01T00:00:00.000Z"})
    assert written["ts"] == "2020-01-01T00:00:00.000Z"


def test_append_never_mutates_the_caller_dict(tmp_path):
    original = {"type": "step"}
    events.append(tmp_path, original)
    assert original == {"type": "step"}


def test_finding_event_gets_a_uuid_id_when_none_supplied(tmp_path):
    written = events.append(tmp_path, {"type": "finding", "sev": "P1", "text": "x"})
    assert "id" in written
    assert uuid.UUID(written["id"])  # a valid uuid4 hex round-trips


def test_finding_event_keeps_a_supplied_id(tmp_path):
    written = events.append(tmp_path, {"type": "finding", "id": "ledger-fp-123", "text": "x"})
    assert written["id"] == "ledger-fp-123"


def test_non_finding_events_get_no_id(tmp_path):
    written = events.append(tmp_path, {"type": "step"})
    assert "id" not in written


def test_registered_secret_is_redacted_in_event_values(tmp_path):
    events.register_secret("hunter2")
    written = events.append(tmp_path, {"type": "step", "text": "logged in with hunter2 ok"})
    assert "hunter2" not in written["text"]
    assert events.REDACTED in written["text"]
    on_disk = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert "hunter2" not in on_disk


def test_redaction_applies_to_nested_values(tmp_path):
    events.register_secret("s3cr3t")
    written = events.append(tmp_path, {"type": "step", "detail": {"body": ["contains s3cr3t here"]}})
    assert "s3cr3t" not in json.dumps(written)


def test_longer_secret_redacted_before_a_shorter_substring_of_it(tmp_path):
    events.register_secret("ab")
    events.register_secret("abcdef")
    written = events.append(tmp_path, {"type": "step", "text": "value is abcdef exactly"})
    assert written["text"] == f"value is {events.REDACTED} exactly"


def test_clear_secrets_empties_the_registry(tmp_path):
    events.register_secret("topsecret")
    events.clear_secrets()
    written = events.append(tmp_path, {"type": "step", "text": "topsecret shown"})
    assert written["text"] == "topsecret shown"


def test_multiple_appends_are_all_present_and_line_delimited(tmp_path):
    events.append(tmp_path, {"type": "step", "n": 1})
    events.append(tmp_path, {"type": "step", "n": 2})
    lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(l)["n"] for l in lines] == [1, 2]
