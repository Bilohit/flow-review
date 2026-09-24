from __future__ import annotations

import json
import sys

import pytest

from flow_review import envsetup, events


class _FakeCompleted:
    def __init__(self, returncode=0):
        self.returncode = returncode


class _RecordingRunner:
    def __init__(self, returncode=0):
        self.calls: list[list[str]] = []
        self.returncode = returncode

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        return _FakeCompleted(self.returncode)


@pytest.fixture(autouse=True)
def _clean_registry():
    events.clear_secrets()
    yield
    events.clear_secrets()


def test_find_uv_uses_the_injected_which():
    assert envsetup.find_uv(which=lambda name: "/usr/bin/uv" if name == "uv" else None) == "/usr/bin/uv"
    assert envsetup.find_uv(which=lambda name: None) is None


def test_setup_env_uses_uv_when_found(tmp_path):
    runner = _RecordingRunner()
    result = envsetup.setup_env(
        tmp_path, tmp_path / "engine", runner=runner, which=lambda n: "/usr/bin/uv" if n == "uv" else None,
    )
    assert result.created is True
    assert result.used_uv is True
    assert any("uv" in cmd[0] or cmd[0].endswith("uv") for cmd in runner.calls)
    assert (tmp_path / ".flow-review" / ".venv").exists()


def test_setup_env_falls_back_to_stdlib_venv_and_pip_without_uv(tmp_path):
    runner = _RecordingRunner()
    result = envsetup.setup_env(tmp_path, tmp_path / "engine", runner=runner, which=lambda n: None)
    assert result.used_uv is False
    assert any(sys.executable in cmd or "python" in cmd[0].lower() for cmd in runner.calls)


def test_setup_env_never_spawns_a_real_process(tmp_path):
    # The requirement this test locks in: every subprocess interaction goes through `runner`.
    calls = []
    def spy_runner(cmd, **kwargs):
        calls.append(cmd)
        return _FakeCompleted(0)
    envsetup.setup_env(tmp_path, tmp_path / "engine", runner=spy_runner, which=lambda n: None)
    assert calls, "setup_env must have invoked the injected runner, not a real subprocess"


def test_a_failing_command_raises(tmp_path):
    runner = _RecordingRunner(returncode=1)
    with pytest.raises(RuntimeError):
        envsetup.setup_env(tmp_path, tmp_path / "engine", runner=runner, which=lambda n: None)


def test_setup_env_is_idempotent_for_the_same_extras_and_engine_path(tmp_path):
    runner = _RecordingRunner()
    first = envsetup.setup_env(tmp_path, tmp_path / "engine", runner=runner, which=lambda n: None)
    second = envsetup.setup_env(tmp_path, tmp_path / "engine", runner=runner, which=lambda n: None)
    assert first.created is True
    assert second.created is False
    assert len(runner.calls) == 2  # no new calls on the second, no-op run


def test_setup_env_reruns_when_extras_change(tmp_path):
    runner = _RecordingRunner()
    envsetup.setup_env(tmp_path, tmp_path / "engine", extras="web", runner=runner, which=lambda n: None)
    calls_after_first = len(runner.calls)
    result = envsetup.setup_env(tmp_path, tmp_path / "engine", extras="web,mobile", runner=runner, which=lambda n: None)
    assert result.created is True
    assert len(runner.calls) > calls_after_first


def test_gitignore_commits_recordings_by_default(tmp_path):
    envsetup.write_gitignore(tmp_path)
    text = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in text
    assert ".venv/" in text
    assert "runs/" in text
    assert "recordings/" not in text


def test_gitignore_excludes_recordings_when_opted_out(tmp_path):
    envsetup.write_gitignore(tmp_path, commit_recordings=False)
    text = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert "recordings/" in text


def test_load_dotenv_parses_key_value_pairs_skipping_comments_and_blanks(tmp_path):
    path = tmp_path / ".env"
    path.write_text("# a comment\n\nADMIN_PASSWORD=hunter2\nQUOTED=\"has spaces\"\n", encoding="utf-8")
    env = {}
    result = envsetup.load_dotenv(path, environ=env)
    assert result == {"ADMIN_PASSWORD": "hunter2", "QUOTED": "has spaces"}
    assert env == result


def test_load_dotenv_redacts_a_creds_named_value(tmp_path):
    path = tmp_path / ".env"
    path.write_text("ADMIN_PASSWORD=hunter2\n", encoding="utf-8")
    envsetup.load_dotenv(path, environ={}, secret_names={"ADMIN_PASSWORD"})
    written = events.append(tmp_path, {"type": "step", "text": "logged in with hunter2"})
    assert "hunter2" not in written["text"]


def test_load_dotenv_does_not_redact_a_non_creds_value(tmp_path):
    # A-26: DEBUG=1 used to blank every "1" in every event, timestamps included.
    path = tmp_path / ".env"
    path.write_text("DEBUG=1\nADMIN_PASSWORD=hunter2\n", encoding="utf-8")
    env = {}
    envsetup.load_dotenv(path, environ=env, secret_names={"ADMIN_PASSWORD"})
    assert env["DEBUG"] == "1"
    written = events.append(tmp_path, {"type": "step", "text": "step 1 of 10"})
    assert written["text"] == "step 1 of 10"
    assert "[redacted]" not in written["ts"]


def test_load_dotenv_never_registers_a_creds_value_under_four_chars(tmp_path):
    path = tmp_path / ".env"
    path.write_text("PIN=123\n", encoding="utf-8")
    envsetup.load_dotenv(path, environ={}, secret_names={"PIN"})
    written = events.append(tmp_path, {"type": "step", "text": "code 123"})
    assert written["text"] == "code 123"


def test_secret_names_is_the_union_of_every_surface_creds_env_name():
    from flow_review.config import Config, Surface
    cfg = Config(schema_version=2, generator_version="x", surfaces=[
        Surface(id="a", name="A", kind="ui", driver="playwright", launch="x", creds={"user": "A_USER", "pw": "A_PW"}),
        Surface(id="b", name="B", kind="ui", driver="playwright", launch="x", creds={"pw": "B_PW"}),
        Surface(id="c", name="C", kind="cli", driver="shell", launch="x"),
    ])
    assert envsetup.secret_names(cfg) == {"A_USER", "A_PW", "B_PW"}


def test_resolve_env_resolves_a_name_listed_in_secret_names(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "s3cret")
    value = envsetup.resolve_env("ADMIN_PASSWORD", tmp_path, secret_names={"ADMIN_PASSWORD"})
    assert value == "s3cret"


def test_resolve_env_refuses_an_arbitrary_environ_name_outside_secret_names(tmp_path, monkeypatch):
    # A-26 / CP3 finding 1: resolve_env used to read ANY os.environ name, so a `from_env` fill
    # on a CSRF-forged drive request could exfiltrate an unrelated secret (AWS keys, etc).
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "leak-me")
    value = envsetup.resolve_env(
        "AWS_SECRET_ACCESS_KEY", tmp_path, secret_names={"ADMIN_PASSWORD"},
    )
    assert value is None


def test_resolve_env_refuses_when_no_secret_names_given(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "s3cret")
    assert envsetup.resolve_env("ADMIN_PASSWORD", tmp_path) is None


def test_load_dotenv_defaults_to_os_environ_when_none_given(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("SOME_VAR=abc\n", encoding="utf-8")
    monkeypatch.delenv("SOME_VAR", raising=False)
    envsetup.load_dotenv(path)
    import os
    assert os.environ["SOME_VAR"] == "abc"
