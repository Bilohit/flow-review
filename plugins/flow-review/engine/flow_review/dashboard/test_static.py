from __future__ import annotations

import base64
import json
from pathlib import Path

from PIL import Image

from flow_review.dashboard.static import render_static


class _FakeLedger:
    def __init__(self, findings):
        # Canonical: Ledger.findings is dict[str, LedgerEntry] keyed by id.
        self.findings = {e.id: e for e in findings}


class _FakeCfg:
    budget = {"cap_tokens": 200000}


def _seed(tmp_path, extra_events=""):
    project_root = tmp_path / "proj"
    (project_root / ".flow-review").mkdir(parents=True)
    (project_root / ".flow-review" / "findings.json").write_text("{}", encoding="utf-8")
    run_dir = project_root / ".flow-review" / "runs" / "r1"
    run_dir.mkdir(parents=True)
    base = json.dumps({"ts": "2026-09-23T10:00:00.000Z", "id": "e1", "type": "run",
                        "mode": "goal", "surfaces": [], "state": "done"})
    (run_dir / "events.jsonl").write_text(base + "\n" + extra_events, encoding="utf-8")
    return project_root, run_dir


def test_static_is_one_file_with_css_js_and_fonts_inlined(tmp_path, monkeypatch):
    project_root, run_dir = _seed(tmp_path)
    monkeypatch.setattr("flow_review.dashboard.static.ledger.load", lambda p: _FakeLedger([]))
    monkeypatch.setattr("flow_review.dashboard.static.budget.used", lambda rd: 0)
    out_path = tmp_path / "dashboard.html"
    render_static(project_root, run_dir, _FakeCfg(), out_path)
    html = out_path.read_text(encoding="utf-8")

    assert '<script id="state-data" type="application/json">' in html
    assert html.index('id="state-data"') < html.rindex("</body>")
    # no <link rel="stylesheet"> / <script src="..."> to an external page/ file --
    # everything is inlined, A-21.
    assert "<link rel=\"stylesheet\"" not in html
    assert "<script src=\"app.js\"" not in html
    assert "font/woff2;base64," in html  # subsetted fonts inlined
    assert "<svg" in html and "<symbol" in html  # icon sprite inlined, not fetched


def test_static_escapes_script_close_in_user_text(tmp_path, monkeypatch):
    finding_ev = json.dumps({"ts": "2026-09-23T10:00:01.000Z", "id": "f1", "type": "finding",
                              "sev": "P2", "surface_id": "s",
                              "text": "</script><script>alert(1)</script>"})
    project_root, run_dir = _seed(tmp_path, extra_events=finding_ev + "\n")
    monkeypatch.setattr("flow_review.dashboard.static.ledger.load", lambda p: _FakeLedger([]))
    monkeypatch.setattr("flow_review.dashboard.static.budget.used", lambda rd: 0)
    out_path = tmp_path / "dashboard.html"
    render_static(project_root, run_dir, _FakeCfg(), out_path)
    html = out_path.read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html


def test_static_thumbnails_are_downscaled_jpeg_data_uris_linking_to_full_res(tmp_path, monkeypatch):
    project_root, run_dir = _seed(tmp_path)
    shots_dir = run_dir / "shots"
    shots_dir.mkdir()
    Image.new("RGB", (1600, 1200), "white").save(shots_dir / "web-app-0042.png")
    shot_ev = json.dumps({"ts": "2026-09-23T10:00:01.000Z", "id": "e2", "type": "shot",
                           "surface_id": "web-app", "shot": "shots/web-app-0042.png"})
    (run_dir / "events.jsonl").open("a", encoding="utf-8").write(shot_ev + "\n")
    monkeypatch.setattr("flow_review.dashboard.static.ledger.load", lambda p: _FakeLedger([]))
    monkeypatch.setattr("flow_review.dashboard.static.budget.used", lambda rd: 0)
    out_path = tmp_path / "dashboard.html"
    render_static(project_root, run_dir, _FakeCfg(), out_path)
    html = out_path.read_text(encoding="utf-8")

    assert 'href="shots/web-app-0042.png"' in html  # links to the full-res file, relative
    assert "data:image/jpeg;base64," in html
    b64 = html.split("data:image/jpeg;base64,")[1].split('"')[0]
    thumb = Image.open(__import__("io").BytesIO(base64.b64decode(b64)))
    assert max(thumb.size) <= 320  # proposed max edge


def test_thumbnail_link_escapes_the_path(tmp_path):
    from PIL import Image
    from flow_review.dashboard import static
    name = "a'b&c.png"
    Image.new("RGB", (4, 4)).save(tmp_path / name)
    block = static._thumbnail_block(name, tmp_path)
    assert 'href="a&#x27;b&amp;c.png"' in block
