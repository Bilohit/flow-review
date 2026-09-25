"""Drawer native confirm pair (M2 I6): real browser against a served run with tauri findings."""
from __future__ import annotations

import json
import threading

import pytest

pytest.importorskip("playwright")

from PIL import Image
from playwright.sync_api import sync_playwright

from flow_review.dashboard.serve import make_server


class _Cfg:
    budget = {"cap_tokens": 200000}


def _finding(fid, rule, text, evidence):
    return {"ts": "2026-09-25T10:00:01.000Z", "id": fid, "type": "finding", "sev": "P1",
            "surface_id": "desktop", "flow_id": "flow-1", "rule": rule, "route": "/",
            "locator": "", "text": text, "evidence": evidence, "disposition": "engine"}


@pytest.fixture
def page(tmp_path):
    project_root = tmp_path / "proj"
    (project_root / ".flow-review").mkdir(parents=True)
    (project_root / ".flow-review" / "findings.json").write_text("{}", encoding="utf-8")
    run_dir = project_root / ".flow-review" / "runs" / "r1"
    for fid, reproduced in (("fyes", True), ("fno", False)):
        (run_dir / "native" / fid).mkdir(parents=True)
        Image.new("RGB", (64, 40), (200, 210, 225)).save(run_dir / "native" / fid / "shot.png")
        (run_dir / "native" / fid / "result.json").write_text(
            json.dumps({"finding_id": fid, "reproduced": reproduced, "findings": []}),
            encoding="utf-8")
    (run_dir / "shots").mkdir()
    Image.new("RGB", (64, 40), (120, 130, 140)).save(run_dir / "shots" / "web.png")
    lines = [
        {"ts": "2026-09-25T10:00:00.000Z", "id": "e1", "type": "run", "mode": "goal",
         "surfaces": [{"id": "desktop", "kind": "tauri"}]},
        # text-only engine evidence (console.error) -- no web image, native shot still pairs
        _finding("fyes", "console.error", "save swallowed",
                 [json.dumps({"level": "error", "text": "disk full"}), "native/fyes/shot.png"]),
        _finding("fno", "visual.changed", "banner moved",
                 ["shots/web.png", "native/fno/shot.png"]),
    ]
    (run_dir / "events.jsonl").write_text(
        "".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    server = make_server(project_root, run_dir, _Cfg(), port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page()
        pg.goto(f"http://127.0.0.1:{server.server_address[1]}/")
        pg.wait_for_selector('[data-role="lanes"]')
        yield pg
        browser.close()
    server.shutdown()
    server.server_close()


def _open(page, text):
    page.locator('[data-role="badge"]').click()
    page.locator('[data-role="findings-list"] .finding-row', has_text=text).first.click()
    return page.locator('[data-role="drawer"] .drawer-evidence')


@pytest.mark.web
def test_native_shot_renders_for_text_evidence_finding_and_marks_reproduced(page):
    ev = _open(page, "save swallowed")
    assert "disk full" in ev.locator("pre").inner_text()
    native = ev.locator('img[src*="native/fyes/shot.png"]')
    assert native.count() == 1
    marker = ev.locator(".native-shot.confirmed-yes [role=img]")
    assert marker.get_attribute("aria-label") == "reproduced natively"


@pytest.mark.web
def test_native_pair_sits_beside_web_shot_and_marks_not_reproduced(page):
    ev = _open(page, "banner moved")
    pair = ev.locator(".before-after")
    assert pair.locator('img[src*="shots/web.png"]').count() == 1
    assert pair.locator('img[src*="native/fno/shot.png"]').count() == 1
    marker = ev.locator(".native-shot.confirmed-no [role=img]")
    assert marker.get_attribute("aria-label") == "not reproduced natively"
    assert ev.locator(".confirmed-yes").count() == 0
