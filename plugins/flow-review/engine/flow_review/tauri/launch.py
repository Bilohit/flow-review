"""Native launch/attach for Windows WebView2 over CDP (A-35). Linux tauri-driver and macOS AX
are parked -- confirm.py checks surface.options['native'] and never reaches this module for a
'pending' surface."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def launch_native(binary: Path, port: int) -> subprocess.Popen:
    env = dict(os.environ)
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={port}"
    return subprocess.Popen([str(binary)], env=env)


def stop_native(proc: subprocess.Popen) -> None:
    """Kill the app AND its msedgewebview2.exe children: killing only the host can leave the
    WebView2 browser process holding the CDP port for the next run. Never raises: it runs in
    cleanup (finally), where an exception would replace the caller's real exit code."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        proc.kill()
        proc.wait(timeout=10)
    except (subprocess.TimeoutExpired, OSError):
        # ponytail: last-resort kill with no further wait; a truly stuck process is left to the
        # OS rather than hanging or crashing cleanup. Upgrade: report it if leaks show up.
        try:
            proc.kill()
        except OSError:
            pass
