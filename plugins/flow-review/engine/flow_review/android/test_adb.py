import subprocess
import xml.etree.ElementTree as ET

import pytest

from flow_review.android import adb as adbmod
from flow_review.android.adb import Adb, AdbError

PNG = b"\x89PNG\r\n\x1a\n" + b"rest"
XML = ('<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
       '<hierarchy rotation="0"><node text="Hi"/></hierarchy>')
DUMP_OUT = XML + "UI hierchary dumped to: /dev/tty\n"
BAD_XML = "<hierarchy><node></hierarchy>"
FOCUS = ("  mCurrentFocus=Window{d1ffe86 u0 com.secondthought.phone/"
         "com.secondthought.phone.MainActivity}\n")
FOCUS_NULL = ("  mCurrentFocus=null\n  mFocusedApp=ActivityRecord{a1b2c3 u0 "
              "com.secondthought.phone/.MainActivity t12}\n")


class Fake:
    """Scripted runner: each reply is (returncode, stdout) or an Exception to raise."""
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append((cmd, kw))
        r = self.replies.pop(0) if self.replies else (0, "")
        if isinstance(r, Exception):
            raise r
        code, out = r
        return subprocess.CompletedProcess(cmd, code, stdout=out, stderr="boom" if code else "")

    @property
    def cmds(self):
        return [c for c, _ in self.calls]


@pytest.fixture(autouse=True)
def _adb_on_path(monkeypatch):
    monkeypatch.setattr(adbmod, "adb_path", lambda: "adb")


def mk(*replies, device="emu"):
    f = Fake(*replies)
    return Adb(device, runner=f, sleep=lambda s: None), f


def test_adb_path_prefers_which(monkeypatch):
    monkeypatch.undo()
    monkeypatch.setattr(adbmod.shutil, "which", lambda n: "/x/adb")
    assert adbmod.adb_path() == "/x/adb"


def test_adb_path_android_home_then_none(monkeypatch, tmp_path):
    monkeypatch.undo()
    monkeypatch.setattr(adbmod.shutil, "which", lambda n: None)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("ANDROID_HOME", str(tmp_path))
    assert adbmod.adb_path() is None
    exe = tmp_path / "platform-tools" / adbmod._EXE
    exe.parent.mkdir()
    exe.write_text("")
    assert adbmod.adb_path() == str(exe)


def test_devices_keeps_device_state_only():
    out = "List of devices attached\nemulator-5554\tdevice\nR58\toffline\nabc\tunauthorized\n\n"
    assert adbmod.devices(Fake((0, out))) == ["emulator-5554"]


def test_run_prefixes_device_and_uses_utf8_text():
    a, f = mk((0, "ok"))
    assert a.run("shell", "echo") == "ok"
    cmd, kw = f.calls[0]
    assert cmd == ["adb", "-s", "emu", "shell", "echo"]
    assert kw["encoding"] == "utf-8" and kw["errors"] == "replace" and kw["timeout"] == 20


def test_run_without_device_has_no_dash_s():
    a, f = mk((0, ""), device=None)
    a.run("devices")
    assert f.cmds[0] == ["adb", "devices"]


def test_run_errors_become_adberror(monkeypatch):
    for reply in [(1, ""), FileNotFoundError("adb"), subprocess.TimeoutExpired("adb", 20)]:
        with pytest.raises(AdbError):
            mk(reply)[0].run("shell", "x")
    monkeypatch.setattr(adbmod, "adb_path", lambda: None)
    with pytest.raises(AdbError, match="adb not found"):
        mk()[0].run("shell", "x")


def test_run_errors_never_leak_input_text_secret():
    secret = "hunter two s3cret"
    for reply in [(1, ""), FileNotFoundError(f"adb input text {secret}"),
                  subprocess.TimeoutExpired(["adb", "input", "text", secret], 20)]:
        with pytest.raises(AdbError) as ei:
            mk(reply)[0].run("shell", "input", "text", secret, "tail")
        msg = str(ei.value)
        assert "hunter" not in msg and "s3cret" not in msg and "<redacted>" in msg
    with pytest.raises(AdbError, match="timed out after 20s"):
        mk(subprocess.TimeoutExpired("adb", 20))[0].run("shell", "x")


def test_valid_package_and_methods_reject_bad_ids():
    from flow_review.android.adb import valid_package
    assert valid_package("com.example.app_1") and not valid_package("com")
    for bad in ["x; rm -rf /", "com.1a.b", "a.b c", "", "a..b"]:
        assert not valid_package(bad)
        a, f = mk()
        for call in (a.start, a.pidof, a.is_installed, a.is_debuggable, a.wait_foreground,
                     lambda i: a.open_link("http://x", i)):
            with pytest.raises(ValueError):
                call(bad)
        assert f.calls == []


def test_density_override_wins_and_falls_back():
    assert mk((0, "Physical density: 420\n"))[0].density() == 420
    assert mk((0, "Physical density: 420\nOverride density: 320\n"))[0].density() == 320
    assert mk((0, "garbage"))[0].density() == 160


def test_screen_size_override_wins():
    assert mk((0, "Physical size: 1080x2400\n"))[0].screen_size() == (1080, 2400)
    assert mk((0, "Physical size: 1080x2400\nOverride size: 720x1600\n"))[0].screen_size() == (720, 1600)
    with pytest.raises(AdbError):
        mk((0, "nope"))[0].screen_size()


def test_dump_slices_xml_in_one_call():
    a, f = mk((0, DUMP_OUT))
    xml = a.dump()
    assert xml == XML and ET.fromstring(xml).tag == "hierarchy"
    assert f.cmds[0][-4:] == ["exec-out", "uiautomator", "dump", "/dev/tty"]


def test_dump_without_xml_declaration():
    body = '<hierarchy rotation="0"/>'
    assert mk((0, "junk" + body + "UI hierchary dumped"))[0].dump() == body


def test_dump_retries_once_then_succeeds():
    a, f = mk((0, "ERROR: could not get idle state."), (0, DUMP_OUT))
    assert a.dump() == XML and len(f.calls) == 2


def test_dump_bad_xml_twice_raises():
    a, f = mk((0, BAD_XML), (0, BAD_XML))
    with pytest.raises(AdbError, match="hierarchy"):
        a.dump()
    assert len(f.calls) == 2


def test_tap():
    a, f = mk()
    a.tap(10.4, 20)
    assert f.cmds[0][-5:] == ["shell", "input", "tap", "10", "20"]


def test_text_encodes_spaces_and_quotes():
    a, f = mk()
    a.text("a b;c")
    assert f.cmds[0][-4:] == ["shell", "input", "text", "'a%sb;c'"]


@pytest.mark.parametrize("bad", ["100%", "café"])
def test_text_rejects_percent_and_non_ascii(bad):
    a, f = mk()
    with pytest.raises(ValueError):
        a.text(bad)
    assert not f.calls


def test_key_names_and_passthrough():
    a, f = mk()
    for k in ("Enter", "Back", "Del", "MoveEnd", 29):
        a.key(k)
    assert [c[-1] for c in f.cmds] == ["66", "4", "67", "123", "29"]
    with pytest.raises(ValueError):
        a.key("Nope")


def test_keys_single_call():
    a, f = mk()
    a.keys(67, 3)
    assert len(f.calls) == 1
    assert f.cmds[0][-5:] == ["input", "keyevent", "67", "67", "67"]


def test_screencap_writes_png_and_makes_parents(tmp_path):
    a, f = mk((0, PNG))
    out = a.screencap(tmp_path / "deep" / "s.png")
    assert out.read_bytes() == PNG
    assert f.cmds[0][-3:] == ["exec-out", "screencap", "-p"]
    assert "encoding" not in f.calls[0][1]


def test_screencap_rejects_non_png(tmp_path):
    a, _ = mk((0, b"\r\nnot a png"))
    with pytest.raises(AdbError, match="PNG"):
        a.screencap(tmp_path / "s.png")


def test_start_uses_monkey_launcher():
    a, f = mk((0, "Events injected: 1"))
    a.start("com.x")
    c = f.cmds[0]
    assert c[c.index("monkey"):] == ["monkey", "-p", "com.x", "-c",
                                     "android.intent.category.LAUNCHER", "1"]


def test_start_no_activities_raises():
    a, _ = mk((0, "** No activities found to run, monkey aborted."))
    with pytest.raises(AdbError, match="No activities"):
        a.start("com.x")


def test_open_link_quotes_url():
    a, f = mk()
    a.open_link("myapp://a?b=1&c=2", "com.x")
    c = f.cmds[0]
    assert c[c.index("am"):] == ["am", "start", "-a", "android.intent.action.VIEW", "-d",
                                 "'myapp://a?b=1&c=2'", "com.x"]


def test_foreground_package_parses_current_focus():
    assert mk((0, FOCUS))[0].foreground_package() == "com.secondthought.phone"


def test_foreground_package_falls_back_to_focused_app_then_none():
    assert mk((0, FOCUS_NULL))[0].foreground_package() == "com.secondthought.phone"
    assert mk((0, "  mCurrentFocus=null\n  mFocusedApp=null\n"))[0].foreground_package() is None


def test_wait_foreground_polls_until_match():
    a, f = mk((0, "mCurrentFocus=null\n"), (0, FOCUS))
    a.wait_foreground("com.secondthought.phone")
    assert len(f.calls) == 2


def test_wait_foreground_times_out():
    a, f = mk(*[(0, "mCurrentFocus=null\n")] * 10)
    with pytest.raises(AdbError, match="foreground"):
        a.wait_foreground("com.x", timeout=2, poll=0.5)
    assert len(f.calls) <= 6


def test_pidof():
    assert mk((0, "1234\n"))[0].pidof("com.x") is True
    assert mk((0, "\n"))[0].pidof("com.x") is False


def test_is_installed_exact_line():
    assert mk((0, "package:com.x.beta\npackage:com.x\n"))[0].is_installed("com.x") is True
    assert mk((0, "package:com.x.beta\n"))[0].is_installed("com.x") is False


def test_ime_shown():
    assert mk((0, "  mInputShown=true\n"))[0].ime_shown() is True
    assert mk((0, "  mInputShown=false\n"))[0].ime_shown() is False


def test_reverse():
    a, f = mk()
    a.reverse(8081)
    assert f.cmds[0][-3:] == ["reverse", "tcp:8081", "tcp:8081"]


@pytest.mark.parametrize("flags,expected", [
    ("pkgFlags=[ DEBUGGABLE HAS_CODE ALLOW_BACKUP ]", True),
    ("pkgFlags=[ HAS_CODE ALLOW_BACKUP ]\n    privatePkgFlags=[ DEBUGGABLE ]", False),
    ("", False)])
def test_is_debuggable_reads_pkg_flags_only(flags, expected):
    adb, _ = mk((0, flags))
    assert adb.is_debuggable("com.x") is expected
