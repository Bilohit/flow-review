"""dashboard_server fixture (E5): an in-process flow-review dashboard, seeded with a
fixture run so the screenshot harness (and any test that wants a real live page) has
real data to render -- not an empty shell. Starts flow_review.dashboard.serve's own
ThreadingHTTPServer, the same one `flow-review serve` runs, so no subprocess is needed.
"""
from __future__ import annotations

import dataclasses
import threading
from pathlib import Path

import pytest
from PIL import Image

from flow_review import events, ledger
from flow_review.dashboard.serve import make_server

SEVS = ["P0", "P1", "P2"]


class _FakeCfg:
    budget = {"cap_tokens": 200000}


@dataclasses.dataclass
class DashboardServer:
    url: str
    project_root: Path
    run_dir: Path
    _server: object
    _thread: threading.Thread

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


def _seed_run(project_root: Path, run_dir: Path, lane_count: int) -> None:
    surface_ids = [f"surface-{i + 1}" for i in range(lane_count)]
    events.append(run_dir, {
        "type": "run", "mode": "goal", "flows_total": lane_count, "state": "running",
        "surfaces": [{"id": sid, "kind": "web"} for sid in surface_ids],
    })
    for i, sid in enumerate(surface_ids):
        events.append(run_dir, {
            "type": "step", "surface_id": sid, "flow_id": "checkout",
            "step": "fill the cart", "state": "running",
        })
        events.append(run_dir, {
            "type": "output", "surface_id": sid,
            "text": f"GET /api/cart 200\nPOST /api/checkout 200 ({sid})",
        })
        shots = run_dir / "shots"
        shots.mkdir(exist_ok=True)
        Image.new("RGB", (640, 400), (200 - 30 * (i % 4), 210, 225)).save(shots / f"{sid}.png")
        events.append(run_dir, {"type": "shot", "surface_id": sid, "shot": f"shots/{sid}.png"})
        sev = SEVS[i % len(SEVS)]
        events.append(run_dir, {
            "type": "finding", "surface_id": sid, "flow_id": "checkout",
            "rule": "contrast.aa" if sev == "P2" else "a11y.keyboard-unreachable",
            "route": "/checkout", "locator": "role:button[name=Pay]",
            "sev": sev, "text": f"{sid}: low contrast on the pay button",
            "evidence": [], "disposition": "engine",
        })
    events.append(run_dir, {
        "type": "goal", "flow_id": "checkout", "text": "reach checkout",
        "reached": True, "actions": 3, "shortest": 2, "from_docs": True,
    })
    events.append(run_dir, {"type": "status", "state": "done"})
    events.append(run_dir, {"type": "run", "mode": "goal", "state": "done", "surfaces": []})

    # A triaged (false-positive) entry, already reconciled into this run -- must show in the
    # report's own "triaged" collapsed group (A-15), not vanish.
    triaged = ledger.LedgerEntry(
        id="f_triaged1", fingerprint="fp1", surface_id=surface_ids[0], flow_id="checkout",
        rule="contrast.aa", route="/checkout", locator="role:button[name=Pay]", sev="P2",
        text="triaged: flagged as a false positive", state="false-positive", runs_seen=2,
        last_run=run_dir.name,
    )
    ledger.save(ledger.Ledger(findings={triaged.id: triaged}), project_root / ".flow-review" / "findings.json")


@pytest.fixture
def dashboard_server(tmp_path, request):
    lane_count = 1
    if hasattr(request, "param"):
        lane_count = request.param
    else:
        # test_capture_theme_and_lane_variants parametrizes (theme, lane_count) positionally;
        # pull lane_count from the test's own params when present.
        params = getattr(request.node, "callspec", None)
        if params is not None and "lane_count" in params.params:
            lane_count = params.params["lane_count"]

    project_root = tmp_path / "proj"
    (project_root / ".flow-review").mkdir(parents=True)
    (project_root / ".flow-review" / "findings.json").write_text("{}", encoding="utf-8")
    run_dir = project_root / ".flow-review" / "runs" / "r1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text("", encoding="utf-8")
    _seed_run(project_root, run_dir, lane_count)

    server = make_server(project_root, run_dir, _FakeCfg(), port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    dash = DashboardServer(
        url=f"http://127.0.0.1:{port}/", project_root=project_root, run_dir=run_dir,
        _server=server, _thread=thread,
    )
    yield dash
    dash.stop()
