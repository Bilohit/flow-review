"""Native confirm (A-35, M2): replay each P0/P1 finding's repro log on the native app over CDP.

`flow-review confirm --run DIR [--surface ID] [--finding ID] [--port 9333]` walks the ledger for
open P0/P1 findings on tauri-driver surfaces. A `native: "pending"` surface (A-35: Linux
tauri-driver / macOS AX are parked) never reaches WebDriver.attach -- it only files a
not-exercised/native-pending status event per finding and writes no result.json. Otherwise the
native binary is launched once per surface (A-50: a fixed default CDP port, 9333, overridable
with --port, since only one native confirm run happens at a time locally), attached to with a
bounded retry poll, and each finding's flat repro log `<run_dir>/repro/<flow_slug>.json` is
replayed against it.

Exit 0 = every attempted finding reproduced (native-pending findings do not count against this);
1 = some did not (a missing repro log counts as not reproduced); 3 = the native app could not be
attached within the retry window -- no ledger write happens on that path.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from flow_review import config as configmod
from flow_review import envsetup, events
from flow_review import ledger as ledger_mod
from flow_review.tauri import launch as tauri_launch
from flow_review.web import actionlog, measure
from flow_review.web.driver import WebDriver

DEFAULT_PORT = 9333
ATTACH_RETRIES = 20
ATTACH_POLL_S = 0.5


def _attach_with_retry(cdp_url: str) -> WebDriver | None:
    for _ in range(ATTACH_RETRIES):
        try:
            return WebDriver.attach(cdp_url)
        except Exception:
            time.sleep(ATTACH_POLL_S)
    return None


def _replay_steps(driver, log: dict, project_root: Path) -> str:
    """Runs the repro log's steps; returns the route of the last goto."""
    last_route = "/"
    for step in log["steps"]:
        action = step["action"]
        if action == "goto":
            last_route = step["url"]
            driver.goto(step["url"])
        elif action == "click":
            driver.click(step["locator"])
        elif action == "fill":
            value = step.get("value") or ""
            if step.get("from_env"):
                value = envsetup.resolve_env(step["from_env"], project_root,
                                             envsetup.project_secret_names(project_root))
                if value is None:
                    raise RuntimeError(f"env var {step['from_env']!r} is not set")
            driver.fill(step["locator"], value, secret=bool(step.get("from_env")))
        elif action == "press":
            driver.press(step.get("value") or "")
    return ledger_mod.route_template(last_route)


def _stop(session: dict) -> None:
    driver, proc = session["driver"], session["proc"]
    session["driver"] = session["proc"] = None
    try:
        if driver is not None:
            driver.close()
    except Exception:
        pass  # the app may already be gone; the process kill below still has to run
    finally:
        if proc is not None:
            tauri_launch.stop_native(proc)


def confirm(project_root: Path, run_dir: Path, surface_id: str | None = None,
            finding_id: str | None = None, port: int = DEFAULT_PORT) -> int:
    project_root = Path(project_root)
    run_dir = Path(run_dir)
    cfg = configmod.load(project_root / ".flow-review" / "config.json")
    surfaces_by_id = {s.id: s for s in cfg.surfaces if s.driver == "tauri"}
    ledger_path = project_root / ".flow-review" / "findings.json"
    lgr = ledger_mod.load(ledger_path)

    candidates = [
        entry for entry in lgr.findings.values()
        if entry.state == "open" and entry.sev in ("P0", "P1")
        and entry.surface_id in surfaces_by_id
    ]
    if surface_id is not None:
        candidates = [e for e in candidates if e.surface_id == surface_id]
    if finding_id is not None:
        candidates = [e for e in candidates if e.id == finding_id]

    # one app at a time: every surface shares the one CDP port, so the previous surface's app
    # is stopped before the next one launches
    candidates.sort(key=lambda e: e.surface_id)
    all_reproduced = True
    session: dict = {"surface_id": None, "driver": None, "proc": None}
    try:
        for entry in candidates:
            surface = surfaces_by_id[entry.surface_id]

            if surface.options.get("native") == "pending":
                events.append(run_dir, {
                    "type": "status", "state": "not-exercised",
                    "surface_id": entry.surface_id, "flow_id": entry.flow_id,
                    "step": "confirm", "reason": "native-pending",
                })
                continue

            # ponytail: reaches into actionlog._slug so the path matches what actionlog.save wrote;
            # upgrade: make it public if a third caller appears
            repro_path = run_dir / "repro" / f"{actionlog._slug(entry.flow_id)}.json"
            if not repro_path.exists():
                all_reproduced = False
                continue

            if session["surface_id"] != entry.surface_id:
                _stop(session)
                session["surface_id"] = entry.surface_id
                # a relative binary path in config is relative to the project, not the cwd
                binary = project_root / surface.options["binary"]
                # held in session before attach so _stop kills it on every exit path
                session["proc"] = tauri_launch.launch_native(binary, port)
                session["driver"] = _attach_with_retry(f"http://127.0.0.1:{port}")
                if session["driver"] is None:
                    return 3
            driver = session["driver"]

            out_dir = run_dir / "native" / entry.id
            out_dir.mkdir(parents=True, exist_ok=True)
            result: dict = {"finding_id": entry.id, "reproduced": False, "findings": []}
            try:
                # inside the try: a corrupt log is "did not reproduce", same as a diverged replay
                log = json.loads(repro_path.read_text(encoding="utf-8"))
                route = _replay_steps(driver, log, project_root)
                findings = measure.check_page(driver, entry.surface_id, entry.flow_id, route,
                                               None, None)
                driver.screenshot(out_dir / "shot.png")
                ref = f"native/{entry.id}/shot.png"
                if ref not in entry.evidence:
                    entry.evidence.append(ref)
                result["findings"] = findings
                result["reproduced"] = any(f["rule"] == entry.rule for f in findings)
            except Exception as exc:
                # a diverged/crashed replay is "did not reproduce", not an engine crash
                result["error"] = f"{type(exc).__name__}: {exc}"
            if not result["reproduced"]:
                all_reproduced = False
            # console text / exception strings can carry a registered secret (mirrors ledger.save)
            (out_dir / "result.json").write_text(json.dumps(events.redact(result), indent=2),
                                                 encoding="utf-8")

        ledger_mod.save(lgr, ledger_path)
    finally:
        _stop(session)

    return 0 if all_reproduced else 1
