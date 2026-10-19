import json

from flow_review.android.maestro_export import to_maestro
from flow_review.web import actionlog

FORBIDDEN = ("clearState", "clearKeychain", "stopApp: true", "killApp", "pm clear", "uninstall")


def _log(*steps):
    log = actionlog.new_log("app", "f")
    for s in steps:
        actionlog.record_step(log, s.pop("action"), **s)
    return log


def test_header_and_basic_steps():
    out = to_maestro(_log(
        dict(action="click", locator={"testid": "login"}),
        dict(action="click", locator={"role": "button", "name": "Sign in"}),
        dict(action="press", value="Enter"),
        dict(action="assert_url", url="/home", checkpoint="c"),
    ), "com.x")
    assert out.startswith('appId: "com.x"\n---\n- launchApp:\n    stopApp: false\n')
    assert '- tapOn:\n    id: "login"' in out
    assert '- tapOn:\n    text: "Sign in"' in out
    assert '- pressKey: "Enter"' in out
    assert "home" not in out


def test_value_with_colon_is_quoted():
    out = to_maestro(_log(dict(action="fill", locator={"testid": "q"}, value="a: b")), "com.x")
    assert '- inputText: "a: b"' in out


def test_secret_and_from_env_never_emit_value():
    out = to_maestro(_log(
        dict(action="fill", locator={"testid": "pw", "secret": True}, value="hunter2"),
        dict(action="fill", locator={"testid": "tok"}, from_env="API_TOKEN"),
    ), "com.x")
    assert "hunter2" not in out
    assert '- inputText: "${FLOW_REVIEW_SECRET_' in out
    assert '- inputText: "${API_TOKEN}"' in out


def test_goto_deep_link_and_root_and_css_skipped():
    log = _log(dict(action="goto", url="/"), dict(action="goto", url="/notes/1"),
               dict(action="click", locator={"css": ".x"}))
    out = to_maestro(log, "com.x", scheme="notes")
    assert '- openLink: "notes://notes/1"' in out
    assert out.count("- launchApp:\n    stopApp: false\n") == 2
    assert "# unsupported locator" in out
    assert "# unsupported goto" in to_maestro(log, "com.x")


def test_no_wipe_invariant():
    log = _log(
        dict(action="goto", url="/"), dict(action="goto", url="/a"),
        dict(action="click", locator={"testid": "x"}),
        dict(action="fill", locator={"testid": "y", "secret": True}, value="s"),
        dict(action="fill", locator={"name": "z"}, from_env="E"),
        dict(action="press", value="Back"), dict(action="assert_url", url="/a"),
    )
    for out in (to_maestro(log, "com.x", scheme="s"), to_maestro(log, "com.x")):
        assert not any(f in out for f in FORBIDDEN)
    assert json.dumps("com.x") in out


def test_launch_never_force_stops_and_bare_stop_is_forbidden():
    out = to_maestro(_log(dict(action="goto", url="/")), "com.x")
    assert "stopApp: true" not in out and out.count("stopApp: false") == 2


def test_tapon_values_are_regex_escaped():
    out = to_maestro(_log(
        dict(action="click", locator={"role": "button", "name": "Add (new) item?"}),
        dict(action="click", locator={"testid": "a.b[0]"}),
    ), "com.x")
    assert r'text: "Add \\(new\\) item\\?"' in out
    assert r'id: "a\\.b\\[0\\]"' in out
