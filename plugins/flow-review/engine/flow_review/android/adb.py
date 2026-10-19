"""adb transport for the Android driver (A-74, A-83). Every adb call goes through Adb.run; the
runner and sleep are injectable so tests use recorded output and need no device."""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import time
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
from pathlib import Path

_EXE = "adb.exe" if os.name == "nt" else "adb"
_PNG = b"\x89PNG\r\n\x1a\n"
# ponytail: only the keys the driver uses; ints pass through for anything else.
_KEYS = {"Enter": 66, "Back": 4, "Del": 67, "MoveEnd": 123}
_XML = re.compile(r"(<\?xml|<hierarchy).*</hierarchy>|<hierarchy[^>]*/>", re.S)
_PKG = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$")
_LAUNCHER = "android.intent.category.LAUNCHER"


class AdbError(RuntimeError):
    pass


def valid_package(s) -> bool:
    return isinstance(s, str) and bool(_PKG.fullmatch(s))


def _pkg(app_id: str) -> str:
    if not valid_package(app_id):
        raise ValueError(f"invalid app id {app_id!r}")
    return app_id


def metro_port(url: str) -> int:
    """Port of options.metro_url; 8081 (Metro's default) when absent or unparsable."""
    try:
        return urlparse(url).port or 8081
    except ValueError:
        return 8081


def adb_path() -> str | None:
    found = shutil.which("adb")
    if found:
        return found
    roots = [os.environ.get("ANDROID_HOME"),
             os.path.join(os.environ["LOCALAPPDATA"], "Android", "Sdk")
             if os.environ.get("LOCALAPPDATA") else None]
    for root in filter(None, roots):
        p = Path(root) / "platform-tools" / _EXE
        if p.is_file():
            return str(p)
    return None


def devices(runner=subprocess.run) -> list[str]:
    """Serials in `device` state only (not offline/unauthorized)."""
    out = Adb(runner=runner).run("devices")
    rows = (line.split("\t") for line in out.splitlines()[1:])
    return [r[0] for r in rows if len(r) == 2 and r[1].strip() == "device"]


class Adb:
    def __init__(self, device: str | None = None, runner=subprocess.run, sleep=time.sleep):
        self.device, self.runner, self.sleep = device, runner, sleep

    def run(self, *args: str, timeout: int = 20, binary: bool = False):
        exe = adb_path()
        if not exe:
            raise AdbError("adb not found: install platform-tools or set ANDROID_HOME")
        cmd = [exe, *(["-s", self.device] if self.device else []), *args]
        kw = {} if binary else {"text": True, "encoding": "utf-8", "errors": "replace"}
        # `input text` carries typed values (maybe secrets): never put them in an error message
        shown = list(args)
        for i in range(len(shown) - 2):
            if shown[i:i + 2] == ["input", "text"]:
                shown[i + 2:] = ["<redacted>"] * (len(shown) - i - 2)
                break
        label = "adb " + " ".join(shown)
        try:
            p = self.runner(cmd, capture_output=True, timeout=timeout, **kw)
        except FileNotFoundError as e:
            raise AdbError(f"{label}: adb executable not found") from None
        except subprocess.TimeoutExpired:
            raise AdbError(f"{label}: timed out after {timeout}s") from None
        if p.returncode != 0:
            err = p.stderr if isinstance(p.stderr, str) else p.stderr.decode("utf-8", "replace")
            if shown != list(args):
                err = ""  # device stderr may echo the typed value
            raise AdbError(f"{label} exited {p.returncode}: {err.strip()}")
        return p.stdout

    def _wm(self, what: str) -> str | None:
        out = self.run("shell", "wm", what)
        m = (re.search(r"Override %s: (\S+)" % what, out)
             or re.search(r"Physical %s: (\S+)" % what, out))
        return m.group(1) if m else None

    def density(self) -> int:
        v = self._wm("density")
        return int(v) if v and v.isdigit() else 160

    def screen_size(self) -> tuple[int, int]:
        m = re.fullmatch(r"(\d+)x(\d+)", self._wm("size") or "")
        if not m:
            raise AdbError("cannot parse wm size")
        return int(m.group(1)), int(m.group(2))

    def dump(self) -> str:
        """Hierarchy XML in one call. Retries once: uiautomator fails with 'could not get idle
        state' on busy screens. ponytail: no maestro-hierarchy fallback yet (A-74)."""
        last = ""
        for _ in range(2):
            try:
                out = self.run("exec-out", "uiautomator", "dump", "/dev/tty")
                m = _XML.search(out)
                if not m:
                    raise ET.ParseError("no hierarchy in output")
                xml = m.group(0)
                ET.fromstring(xml)
                return xml
            except (AdbError, ET.ParseError) as e:
                last = str(e)
        raise AdbError(f"hierarchy unavailable: {last}")

    def tap(self, x, y) -> None:
        self.run("shell", "input", "tap", str(int(x)), str(int(y)))

    def text(self, value: str) -> None:
        # ponytail: `input text` is ASCII-only and '%' is its own escape; both refused (A-83).
        if "%" in value or not value.isascii():
            raise ValueError("adb input text supports ASCII without '%' only")
        self.run("shell", "input", "text", shlex.quote(value.replace(" ", "%s")))

    def key(self, name_or_code) -> None:
        self.keys(self._code(name_or_code), 1)

    @staticmethod
    def _code(k) -> int:
        if isinstance(k, int):
            return k
        if k not in _KEYS:
            raise ValueError(f"unknown key {k!r}")
        return _KEYS[k]

    def keys(self, code: int, n: int) -> None:
        self.run("shell", "input", "keyevent", *[str(code)] * n)

    def screencap(self, path) -> Path:
        data = self.run("exec-out", "screencap", "-p", binary=True)
        if not data.startswith(_PNG):
            raise AdbError("screencap did not return a PNG")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def start(self, app_id: str) -> None:
        out = self.run("shell", "monkey", "-p", _pkg(app_id), "-c", _LAUNCHER, "1")
        if "No activities found" in out:
            raise AdbError(f"No activities found for {app_id}")

    def open_link(self, url: str, app_id: str) -> None:
        self.run("shell", "am", "start", "-a", "android.intent.action.VIEW",
                 "-d", shlex.quote(url), _pkg(app_id))

    def foreground_package(self) -> str | None:
        out = self.run("shell", "dumpsys", "window")
        for key in ("mCurrentFocus", "mFocusedApp"):
            m = re.search(key + r"=\w+\{\S+ u\d+ ([\w.]+)/", out)
            if m:
                return m.group(1)
        return None

    def wait_foreground(self, app_id: str, timeout: float = 60, poll: float = 0.5) -> None:
        _pkg(app_id)
        for _ in range(int(timeout / poll) + 1):
            if self.foreground_package() == app_id:
                return
            self.sleep(poll)
        raise AdbError(f"{app_id} not in foreground after {timeout}s")

    def pidof(self, app_id: str) -> bool:
        # `|| true`: pidof exits 1 when the app is not running; that is an answer, not an error.
        return bool(self.run("shell", f"pidof {shlex.quote(_pkg(app_id))} || true").strip())

    def is_installed(self, app_id: str) -> bool:
        return f"package:{app_id}" in self.run("shell", "pm", "list", "packages", _pkg(app_id)).split()

    def is_debuggable(self, app_id: str) -> bool:
        # a release build embeds its JS bundle; only a debuggable one loads it from Metro
        m = re.search(r"pkgFlags=\[([^\]]*)\]", self.run("shell", "dumpsys", "package", _pkg(app_id)))
        return bool(m) and "DEBUGGABLE" in m.group(1).split()

    def ime_shown(self) -> bool:
        return "mInputShown=true" in self.run("shell", "dumpsys", "input_method")

    def reverse(self, port: int) -> None:
        self.run("reverse", f"tcp:{port}", f"tcp:{port}")
