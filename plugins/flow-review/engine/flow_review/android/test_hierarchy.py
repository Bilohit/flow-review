from pathlib import Path

import pytest

from flow_review.android import hierarchy as h
from flow_review.locators import LocatorNotFound

FIX = Path(__file__).parent / "fixtures"
APP = "com.example.notes"


def load(name):
    return h.parse((FIX / f"{name}.xml").read_text(encoding="utf-8"))


def node(**kw):
    base = dict(cls="android.view.ViewGroup", text="", desc="", rid="", pkg=APP,
                bounds=(0, 0, 100, 100), clickable=False, focusable=False, scrollable=False,
                password=False, enabled=True, depth=0, index=0)
    base.update(kw)
    return base


def test_parse_keys_and_depth():
    nodes = load("home")
    cal = next(n for n in nodes if n["desc"] == "Calendar")
    assert cal["bounds"] == (828, 79, 944, 194)
    assert cal["clickable"] is True and cal["focusable"] is True and cal["scrollable"] is False
    assert cal["cls"] == "android.widget.Button" and cal["pkg"] == APP
    assert cal["depth"] == 2 and cal["index"] == 1
    assert set(cal) == {"cls", "text", "desc", "rid", "pkg", "bounds", "clickable", "focusable",
                        "scrollable", "password", "enabled", "depth", "index"}
    assert next(n for n in load("login") if n["desc"] == "Password")["password"] is True


def test_parse_unescapes_and_tolerates_prefix_noise():
    nodes = h.parse("junk\n" + (FIX / "dialog.xml").read_text(encoding="utf-8"))
    assert any(n["text"] == "Don't allow" for n in nodes)


def test_interactive():
    assert h.interactive(node(clickable=True))
    assert h.interactive(node(focusable=True, desc="Rename"))
    assert not h.interactive(node(focusable=True))
    assert not h.interactive(node(focusable=True, desc="List", scrollable=True))
    assert not h.interactive(node(text="hello"))


def test_resolve_testid_exact_and_suffix():
    nodes = load("home")
    assert h.resolve(nodes, {"testid": "notes-list"})["cls"] == "android.widget.ScrollView"
    assert h.resolve(load("login"), {"testid": "submit-btn"})["text"] == "Log in"
    assert h.resolve(load("dialog"), {"testid": "permission_allow_button"})["text"] == "Allow"


def test_resolve_role_name_desc_text_and_case():
    nodes = load("home")
    assert h.resolve(nodes, {"role": "button", "name": "Calendar"})["bounds"][0] == 828
    assert h.resolve(nodes, {"role": "button", "name": "calendar"})["desc"] == "Calendar"
    assert h.resolve(load("login"), {"role": "button", "name": "Log in"})["rid"] == "submit-btn"
    assert h.resolve(load("login"), {"role": "button", "name": "log IN"})["rid"] == "submit-btn"


def test_resolve_exact_beats_case_insensitive_and_text_beats_desc():
    a = node(desc="ok", clickable=True)
    b = node(desc="OK", clickable=True, bounds=(0, 0, 5, 5))
    assert h.resolve([a, b], {"role": "button", "name": "OK"}) is b
    c = node(desc="Go", clickable=True)
    d = node(text="Go", clickable=True)
    assert h.resolve([c, d], {"role": "button", "name": "Go"}) is d


def test_resolve_role_narrows():
    et = node(cls="android.widget.EditText", desc="Password", focusable=True, clickable=True)
    btn = node(cls="android.widget.Button", desc="Password", clickable=True)
    assert h.resolve([btn, et], {"role": "textbox", "name": "Password"}) is et
    cb = node(cls="android.widget.CheckBox", text="Agree", clickable=True)
    sw = node(cls="android.widget.Switch", text="Agree", clickable=True)
    assert h.resolve([cb, sw], {"role": "switch", "name": "Agree"}) is sw
    assert h.resolve([sw, cb], {"role": "checkbox", "name": "Agree"}) is cb
    with pytest.raises(LocatorNotFound):
        h.resolve([cb], {"role": "textbox", "name": "Agree"})


def test_resolve_text_locator_no_role():
    assert h.resolve(load("home"), {"text": "Notes"})["cls"] == "android.widget.TextView"


def test_resolve_role_ignores_noninteractive():
    with pytest.raises(LocatorNotFound):
        h.resolve(load("login"), {"role": "button", "name": "Sign in"})


def test_resolve_css_raises():
    with pytest.raises(LocatorNotFound):
        h.resolve(load("home"), {"css": "#x"})


def test_resolve_miss_names_foreground_and_labels():
    nodes = load("dialog")
    with pytest.raises(LocatorNotFound) as ei:
        h.resolve(nodes, {"role": "button", "name": "Nope"})
    msg = str(ei.value)
    assert "com.google.android.permissioncontroller" in msg
    assert "Allow" in msg and "Don't allow" in msg
    assert ei.value.locator == {"role": "button", "name": "Nope"}


def test_resolve_miss_limits_to_ten_labels():
    nodes = [node(text=f"label{i}", bounds=(0, i, 10, i + 5)) for i in range(15)]
    with pytest.raises(LocatorNotFound) as ei:
        h.resolve(nodes, {"text": "zzz"})
    assert "label9" in str(ei.value) and "label10" not in str(ei.value)


def test_screen_route():
    assert h.screen_route(load("home"), APP, 2400) == "notes"
    assert h.screen_route(load("login"), APP, 2400) == "sign-in"
    assert h.screen_route([], APP, 2400) == "app"
    assert h.screen_route([node(text="Low", bounds=(0, 1000, 10, 1100))], APP, 2400) == "app"
    sysui = [n for n in load("home") if n["pkg"] == "com.android.systemui"]
    assert h.screen_route(sysui, APP, 2400) == "app"


def test_screen_route_orders_by_y_then_x():
    ns = [node(text="Second", bounds=(500, 100, 600, 150)), node(text="First", bounds=(10, 100, 60, 150)),
          node(text="Above", bounds=(900, 50, 950, 90))]
    assert h.screen_route(ns, APP, 2400) == "above"
    assert h.screen_route(ns[:2], APP, 2400) == "first"


def test_outline():
    out = h.outline(load("login"), APP)
    assert '- text "Sign in"' in out
    assert '- textbox "Password" [password]' in out
    assert '- textbox "Email"' in out and '- button "Log in"' in out
    assert "12:00" not in out
    assert '- button "Calendar"' in h.outline(load("home"), APP)


def test_check_flags_small_badge_not_full_width_row():
    fs = h.check(load("home"), "notes", 420, APP, (1080, 2400))
    ts = [f for f in fs if f["rule"] == "rect.target-size"]
    names = {f["locator"].get("name") for f in ts}
    assert "Rename" in names and "Groceries" not in names and "Notes" not in names
    badge = next(f for f in ts if f["locator"].get("name") == "Rename")
    assert badge["sev"] == "P2" and badge["route"] == "notes" and badge["disposition"] == "engine"
    assert badge["locator"] == {"role": "button", "name": "Rename"}
    assert badge["evidence"] and "15" in badge["text"]
    assert set(badge) == {"rule", "sev", "locator", "route", "text", "evidence", "disposition"}


def test_check_testid_locator_and_dev_menu_ignored():
    small = node(rid="com.example.notes:id/tiny", clickable=True, bounds=(0, 0, 50, 50))
    f = h.check([small], "r", 420, APP, (1080, 2400))[0]
    assert f["locator"] == {"testid": "tiny"}
    dev = node(rid="dev_launcher_menu", clickable=True, bounds=(0, 0, 50, 50))
    assert h.check([dev], "r", 420, APP, (1080, 2400)) == []


def test_check_ignores_other_package_and_zero_area():
    other = node(pkg="com.android.systemui", clickable=True, bounds=(0, 0, 10, 10))
    zero = node(clickable=True, bounds=(5, 5, 5, 50))
    assert h.check([other, zero], "r", 420, APP, (1080, 2400)) == []


def test_check_overlap_and_containment_skip():
    a = node(desc="A", clickable=True, bounds=(0, 0, 400, 400))
    b = node(desc="B", clickable=True, bounds=(300, 300, 700, 700))
    inner = node(desc="In", clickable=True, bounds=(10, 10, 300, 300))
    fs = [f for f in h.check([a, b, inner], "r", 420, APP, (1080, 2400)) if f["rule"] == "rect.overlap"]
    assert [f["text"] for f in fs] == ["A overlaps B"]  # a contains inner: skipped; inner/b only touch
    assert fs[0]["sev"] == "P1"


def test_check_touching_edges_ok_and_home_fixture_clean():
    a = node(desc="A", clickable=True, bounds=(0, 0, 400, 400))
    b = node(desc="B", clickable=True, bounds=(400, 0, 800, 400))
    assert h.check([a, b], "r", 420, APP, (1080, 2400)) == []
    fs = h.check(load("home"), "notes", 420, APP, (1080, 2400))
    assert not [f for f in fs if f["rule"] in ("rect.overlap", "rect.offscreen")]


def test_check_offscreen():
    part = node(desc="Edge", clickable=True, bounds=(900, 500, 1200, 700))
    gone = node(desc="Gone", clickable=True, bounds=(1100, 500, 1400, 700))
    fs = [f for f in h.check([part, gone], "r", 420, APP, (1080, 2400)) if f["rule"] == "rect.offscreen"]
    assert [f["locator"]["name"] for f in fs] == ["Edge"]
    assert fs[0]["sev"] == "P2"


_BAR = ('<?xml version="1.0"?><hierarchy rotation="0">'
        '<node index="0" text="" resource-id="" class="android.widget.Button" package="com.example"'
        ' content-desc="Calendar" clickable="true" focusable="true" scrollable="false"'
        ' password="false" enabled="true" bounds="[828,79][944,194]">'
        '</node>'
        '<node index="1" text="Notes" resource-id="" class="android.widget.TextView" package="com.example"'
        ' content-desc="" clickable="false" focusable="false" scrollable="false"'
        ' password="false" enabled="true" bounds="[40,100][300,160]"/>'
        '<node index="2" text="" resource-id="" class="android.widget.Button" package="com.example"'
        ' content-desc="Ask your notes" clickable="true" focusable="true" scrollable="false"'
        ' password="false" enabled="true" bounds="[0,900][1080,1100]">'
        '<node index="0" text="Ask your notes" resource-id="" class="android.widget.TextView"'
        ' package="com.example" content-desc="" clickable="false" focusable="false"'
        ' scrollable="false" password="false" enabled="true" bounds="[40,920][600,980]"/>'
        '<node index="1" text="1h" resource-id="" class="android.widget.TextView"'
        ' package="com.example" content-desc="" clickable="false" focusable="false"'
        ' scrollable="false" password="false" enabled="true" bounds="[900,920][1040,980]"/>'
        '</node></hierarchy>')


def test_screen_route_prefers_title_text_over_higher_icon_button():
    nodes = h.parse(_BAR)
    assert h.screen_route(nodes, "com.example", 1920) == "notes"


def test_outline_drops_caption_that_repeats_its_controls_name():
    out = h.outline(h.parse(_BAR), "com.example")
    assert out.count("Ask your notes") == 1
    assert '- text "1h"' in out
