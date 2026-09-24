import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, TypedDict
from urllib.parse import urlparse

from flow_review import drift, envsetup, events, ledger
from flow_review.web import actionlog
from flow_review.web import measure as measure_mod
from flow_review.web.driver import LocatorNotFound, WebDriver

MeasureHook = Callable[..., list[dict]]


class ReplayResult(TypedDict):
    flow_id: str
    status: str
    steps_run: int
    divergence: dict | None
    findings: list[dict]


class MissingEnv(Exception):
    """A recorded `from_env` fill whose variable is set neither in the environment nor in
    .flow-review/.env: an environment error (exit 3), not a finding."""


def _url_path(url: str | None) -> str:
    if not url:
        return "/"
    return urlparse(url).path or "/"


def _current_path(driver) -> str:
    return _url_path(getattr(driver.page, "url", None))


@contextmanager
def _step_window(driver, index: int):
    """A-17: console errors raised while the step's action runs are stamped with its index."""
    driver.begin_step(index)
    try:
        yield
    finally:
        driver.end_step()


def replay_one(driver, log: dict, measure: MeasureHook | None = None,
               project_root: Path | None = None) -> ReplayResult:
    steps_run = 0
    findings: list[dict] = []
    surface_id, flow_id = log["surface_id"], log["flow_id"]

    for index, step in enumerate(log["steps"]):
        action = step["action"]
        try:
            if action == "goto":
                with _step_window(driver, index):
                    driver.goto(step["url"])
                if measure is not None:
                    route = _current_path(driver) or _url_path(step["url"])
                    findings.extend(measure(driver, surface_id, flow_id, route, index))
            elif action == "click":
                with _step_window(driver, index):
                    driver.click(step["locator"])
                if measure is not None:
                    findings.extend(
                        measure(driver, surface_id, flow_id, _current_path(driver), index)
                    )
            elif action == "fill":
                if step.get("from_env"):
                    value = envsetup.resolve_env(step["from_env"], project_root,
                                                 envsetup.project_secret_names(project_root))
                    if value is None:
                        raise MissingEnv(f"env var {step['from_env']!r} is not set in the "
                                         f"environment or .flow-review/.env")
                else:
                    value = step["value"] or ""
                with _step_window(driver, index):
                    driver.fill(step["locator"], value)
            elif action == "assert_url":
                expected = _url_path(step["url"])
                actual = _current_path(driver)
                if actual != expected:
                    findings.append({
                        "surface_id": surface_id, "flow_id": flow_id,
                        "rule": "replay.checkpoint", "route": expected, "locator": "",
                        "sev": "P1",
                        "text": f"checkpoint {step.get('checkpoint')!r}: expected url path "
                                f"{expected!r}, got {actual!r}",
                        "evidence": [f"expected={expected}", f"actual={actual}"],
                        "disposition": "objective",
                    })
            steps_run += 1
        except MissingEnv:
            raise
        except LocatorNotFound:
            return ReplayResult(
                flow_id=flow_id, status="divergence", steps_run=steps_run,
                divergence={
                    "step_index": index, "locator": step.get("locator"),
                    "reason": "locator_not_found", "url": step.get("url"),
                },
                findings=findings,
            )
        except Exception as exc:
            findings.append({
                "surface_id": surface_id, "flow_id": flow_id,
                "rule": "replay.step_failed", "route": _url_path(step.get("url")), "locator": "",
                "sev": "P1", "text": f"step {index} ({action}) raised: {exc}",
                "evidence": [], "disposition": "objective",
            })
            return ReplayResult(flow_id=flow_id, status="regression", steps_run=steps_run,
                                 divergence=None, findings=findings)

    status = "regression" if any(f["rule"] == "replay.checkpoint" for f in findings) else "clean"
    return ReplayResult(flow_id=flow_id, status=status, steps_run=steps_run,
                         divergence=None, findings=findings)


def _load_tokens(surface, project_root: Path) -> dict[str, str] | None:
    tokens_file = surface.options.get("tokens_file")
    if not tokens_file:
        return None
    path = Path(tokens_file)
    if not path.is_absolute():
        path = project_root / tokens_file
    if not path.is_file():
        return None
    return measure_mod.load_tokens(path)  # .css/.scss custom properties or .json (A-25)


def _measure_hook(tokens: dict[str, str] | None) -> MeasureHook:
    def hook(driver, surface_id, flow_id, route, step_index):
        return measure_mod.check_page(driver, surface_id, flow_id, route, tokens, step_index)
    return hook


def _health_ok(surface) -> bool:
    """GET base_url+health_path. Any HTTP answer means the app is up; a refused/timed-out
    connection means it is not -- an environment error (exit 3), never a finding."""
    import urllib.error
    import urllib.request

    url = surface.options["base_url"].rstrip("/") + (surface.options.get("health_path") or "/")
    timeout = surface.options.get("ready_timeout_s") or 5
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except urllib.error.HTTPError:
        return True
    except (urllib.error.URLError, OSError):
        return False


def _launch_driver(surface) -> WebDriver:
    viewport = (surface.options.get("viewport") or [None])[0]
    driver = WebDriver(headless=True, viewport=viewport)
    driver.launch(surface.options["base_url"])
    return driver


def _playwright_surfaces(cfg, surface_id: str | None):
    surfaces = [s for s in drift.runnable_surfaces(cfg) if s.driver == "playwright"]
    if surface_id is not None:
        surfaces = [s for s in surfaces if s.id == surface_id]
    return surfaces


def replay(cfg, project_root: Path, surface_id: str | None = None,
           flow_id: str | None = None) -> int:
    surfaces = _playwright_surfaces(cfg, surface_id)
    if surface_id is not None and not surfaces:
        print(f"no playwright surface named {surface_id!r} in config", file=sys.stderr)
        return 3

    recordings_root = project_root / ".flow-review" / "recordings"
    all_findings: list[dict] = []
    divergences: list[dict] = []
    flows_run: set[str] = set()
    found_any_recording = False

    for surface in surfaces:
        surface_dir = recordings_root / surface.id
        if not surface_dir.is_dir():
            continue
        flow_files = sorted(surface_dir.glob("*.json"))
        if flow_id is not None:
            flow_files = [p for p in flow_files if p.stem == flow_id]
        if not flow_files:
            continue

        if not _health_ok(surface):
            print(f"app for surface {surface.id!r} is unreachable at "
                  f"{surface.options['base_url']}; start it and re-run", file=sys.stderr)
            return 3
        try:
            driver = _launch_driver(surface)
        except Exception as exc:
            print(f"could not launch driver for surface {surface.id!r}: {exc}", file=sys.stderr)
            return 3

        hook = _measure_hook(_load_tokens(surface, project_root))
        try:
            for flow_path in flow_files:
                found_any_recording = True
                log = actionlog.load(flow_path)
                try:
                    result = replay_one(driver, log, measure=hook, project_root=project_root)
                except MissingEnv as exc:
                    print(str(exc), file=sys.stderr)
                    return 3
                all_findings.extend(result["findings"])
                if result["status"] != "divergence":
                    # a diverged flow never reached its later steps: its unseen findings are
                    # unknown, not fixed (CP2 I6)
                    flows_run.add(log["flow_id"])
                if result["status"] == "divergence":
                    d = result["divergence"]
                    divergences.append({
                        "flow_id": result["flow_id"], "step_index": d["step_index"],
                        "locator": d["locator"], "reason": d["reason"], "url": d["url"],
                    })
        finally:
            driver.close()

    if not found_any_recording:
        print(
            "no recordings found under .flow-review/recordings/. Enable recording with "
            "`record: true` on the surface in config, or `/flow-review record <surface> "
            "<flow>` from the Claude Code plugin, then re-run `flow-review replay`."
        )
        return 0

    ledger_path = project_root / ".flow-review" / "findings.json"
    ledger_ = ledger.load(ledger_path)
    run_id = events.now_iso()
    ledger_ = ledger.reconcile(ledger_, all_findings, flows_run, run_id)
    ledger.save(ledger_, ledger_path)

    if divergences:
        out = {
            "schema_version": 1,
            "generated_at": events.now_iso(),
            "divergences": divergences,
        }
        div_path = project_root / ".flow-review" / "divergences.json"
        div_path.parent.mkdir(parents=True, exist_ok=True)
        div_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # Only entries that reproduced in THIS replay count; a stale regression from an earlier
    # run stays visible in the ledger but does not fail today's exit code.
    has_regression = any(e.state == "regressed" and e.last_run == run_id
                         for e in ledger_.findings.values())
    has_new_open_critical = any(
        e.state == "open" and e.sev in ("P0", "P1") and e.first_run == run_id
        for e in ledger_.findings.values()
    )
    if has_regression or has_new_open_critical:
        return 1
    if divergences:
        return 2
    return 0


def replay_log(cfg, project_root: Path, log_path: Path, run_dir: Path) -> int:
    log = actionlog.load(log_path)
    surfaces = [
        s for s in _playwright_surfaces(cfg, None) if s.id == log["surface_id"]
    ]
    if not surfaces:
        print(f"no playwright surface named {log['surface_id']!r} in config", file=sys.stderr)
        return 3

    if not _health_ok(surfaces[0]):
        print(f"app for surface {surfaces[0].id!r} is unreachable at "
              f"{surfaces[0].options['base_url']}; start it and re-run", file=sys.stderr)
        return 3
    try:
        driver = _launch_driver(surfaces[0])
    except Exception as exc:
        print(f"could not launch driver for surface {surfaces[0].id!r}: {exc}", file=sys.stderr)
        return 3

    hook = _measure_hook(_load_tokens(surfaces[0], project_root))
    try:
        result = replay_one(driver, log, measure=hook, project_root=project_root)
    except MissingEnv as exc:
        print(str(exc), file=sys.stderr)
        return 3
    finally:
        driver.close()

    result_path = log_path.with_name(log_path.name + ".result.json")
    result_path.write_text(json.dumps(dict(result), ensure_ascii=False, indent=2),
                           encoding="utf-8")

    if result["status"] == "divergence":
        return 2
    if result["findings"]:
        return 1
    return 0

