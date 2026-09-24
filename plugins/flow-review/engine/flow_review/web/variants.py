from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, TypedDict

from flow_review.web import actionlog
from flow_review.web.replay import ReplayResult, replay_one

_FOCUSABLE_JS = """
() => {
  const sel = 'a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])';
  return Array.from(document.querySelectorAll(sel)).filter(
    el => !el.disabled && el.offsetParent !== null
  ).length;
}
"""

_ACTIVE_ELEMENT_JS = """
() => {
  const el = document.activeElement;
  if (!el) return null;
  return el.outerHTML.slice(0, 200);
}
"""


class Variant(TypedDict):
    kind: str
    params: dict


def _variant_flow_id(flow_id: str, variant: Variant) -> str:
    """Tags a finding's flow id with the variant it was measured under, so sibling variants
    (light vs dark, two widths, new vs returning) and the base flow's own findings never
    collide on `ledger.fingerprint`'s `flow_id|rule|route|locator` key."""
    kind = variant["kind"]
    params = variant["params"]
    if kind == "viewport":
        tag = f"{params['width']}x{params['height']}"
    elif kind == "color-scheme":
        tag = params["scheme"]
    elif kind == "storage-state":
        tag = params["state"]
    else:
        tag = None
    return f"{flow_id}@{kind}:{tag}" if tag else f"{flow_id}@{kind}"


def plan_variants(surface: Any, mode: str) -> list[Variant]:
    if mode == "quick":
        return []
    variants_out: list[Variant] = []
    options = getattr(surface, "options", None) or {}
    for vp in options.get("viewport", []):
        variants_out.append({
            "kind": "viewport",
            "params": {"width": vp["width"], "height": vp["height"]},
        })
    for scheme in ("light", "dark"):
        variants_out.append({"kind": "color-scheme", "params": {"scheme": scheme}})
    variants_out.append({"kind": "keyboard-only", "params": {}})
    variants_out.append({"kind": "reduced-motion", "params": {}})
    variants_out.append({"kind": "storage-state", "params": {"state": "new"}})
    variants_out.append({"kind": "storage-state", "params": {"state": "returning"}})
    return variants_out


def run_variant(driver_factory: Callable[..., Any], base_url: str, log: dict,
                 variant: Variant, storage_state_path: Path | None = None,
                 measure: Callable[..., list[dict]] | None = None) -> ReplayResult:
    kind = variant["kind"]
    tagged_log = dict(log, flow_id=_variant_flow_id(log.get("flow_id", ""), variant))
    kwargs: dict = {}
    if kind == "viewport":
        kwargs["viewport"] = {
            "width": variant["params"]["width"],
            "height": variant["params"]["height"],
        }
    elif kind == "color-scheme":
        kwargs["color_scheme"] = variant["params"]["scheme"]
    elif kind == "reduced-motion":
        kwargs["reduced_motion"] = "reduce"
    elif kind == "storage-state":
        if (variant["params"]["state"] == "returning"
                and storage_state_path is not None and storage_state_path.exists()):
            kwargs["storage_state"] = str(storage_state_path)

    driver = driver_factory(**kwargs)
    driver.launch(base_url)
    try:
        if kind == "keyboard-only":
            driver.goto("/")
            return _replay_keyboard_only(driver, tagged_log)
        return replay_one(driver, tagged_log, measure=measure)
    finally:
        if (kind == "storage-state" and variant["params"]["state"] == "new"
                and storage_state_path is not None):
            storage_state_path.parent.mkdir(parents=True, exist_ok=True)
            storage_state_path.write_text(driver.storage_state())
        driver.close()


def _replay_keyboard_only(driver: Any, log: dict) -> ReplayResult:
    page = driver.page
    focusable_count = page.evaluate(_FOCUSABLE_JS)
    tab_cap = max(20, 2 * focusable_count)
    unreachable: list[dict] = []
    for step in log.get("steps", []):
        if step.get("action") != "click":
            continue
        target = step.get("locator", {}) or {}
        found = False
        first_html = None
        for _ in range(tab_cap):
            page.keyboard.press("Tab")
            html = page.evaluate(_ACTIVE_ELEMENT_JS)
            if first_html is None:
                first_html = html
            elif html == first_html:
                break
            if target.get("testid") and target["testid"] in (html or ""):
                found = True
                break
            if target.get("name") and target["name"] in (html or ""):
                found = True
                break
        if found:
            page.keyboard.press("Enter")
        else:
            # WCAG 2.1.1 (Level A): an engine finding, filed directly (A-23, spec §7.1).
            unreachable.append({
                "surface_id": log.get("surface_id", ""), "flow_id": log.get("flow_id", ""),
                "rule": "a11y.keyboard-unreachable", "route": step.get("url") or "",
                "locator": actionlog.locator_key(target), "sev": "P1",
                "text": f"not reachable by Tab within {tab_cap} presses",
                "evidence": [], "disposition": "engine",
            })
    return ReplayResult(
        flow_id=log.get("flow_id", ""),
        status="regression" if unreachable else "clean",
        steps_run=len(log.get("steps", [])),
        divergence=None,
        findings=unreachable,
    )


def run_all(driver_factory: Callable[..., Any], base_url: str, log: dict, surface: Any,
            storage_state_dir: Path, mode: str = "full",
            measure: Callable[..., list[dict]] | None = None,
            base_viewport: dict | None = None) -> list[tuple[Variant, ReplayResult]]:
    results = []
    for variant in plan_variants(surface, mode):
        if (variant["kind"] == "viewport" and base_viewport is not None
                and variant["params"]["width"] == base_viewport.get("width")
                and variant["params"]["height"] == base_viewport.get("height")):
            continue  # the base flow already ran at this viewport; a variant run would be a dupe
        storage_state_path = (
            storage_state_dir / "storage_state.json"
            if variant["kind"] == "storage-state" else None
        )
        result = run_variant(driver_factory, base_url, log, variant,
                              storage_state_path=storage_state_path, measure=measure)
        results.append((variant, result))
    return results
