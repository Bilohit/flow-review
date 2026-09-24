# plugins/flow-review/engine/flow_review/dashboard/test_serve.py
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

from flow_review.dashboard.serve import make_server


class _FakeCfg:
    budget = {"cap_tokens": 200000}


def _start(tmp_path):
    project_root = tmp_path / "proj"
    (project_root / ".flow-review").mkdir(parents=True)
    (project_root / ".flow-review" / "findings.json").write_text("{}", encoding="utf-8")
    run_dir = project_root / ".flow-review" / "runs" / "r1"
    run_dir.mkdir(parents=True)
    (run_dir / "events.jsonl").write_text("", encoding="utf-8")
    server = make_server(project_root, run_dir, _FakeCfg(), port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    return server, port


def test_state_endpoint_returns_json_with_required_keys(tmp_path):
    server, port = _start(tmp_path)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/state", timeout=5) as resp:
            assert resp.status == 200
            assert resp.headers["Content-Type"] == "application/json"
            body = json.loads(resp.read())
        for key in ("run", "budget", "badge", "lanes", "header", "report", "findings"):
            assert key in body
        assert body["budget"]["cap_tokens"] == 200000
    finally:
        server.shutdown()
        server.server_close()


def test_triage_post_invokes_apply_and_returns_ok(tmp_path, monkeypatch):
    server, port = _start(tmp_path)

    class _FakeEntry:
        def __init__(self):
            self.id, self.state, self.reason = "f1", "false-positive", None

    calls = []

    def fake_apply(ledger_path, finding_id, state, reason=None):
        calls.append((ledger_path, finding_id, state, reason))
        return _FakeEntry()

    import flow_review.dashboard.serve as serve_mod
    monkeypatch.setattr(serve_mod.triage, "apply", fake_apply)

    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/triage",
            data=json.dumps({"finding_id": "f1", "state": "false-positive"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
            assert json.loads(resp.read())["ok"] is True
        assert len(calls) == 1
        assert calls[0][1:] == ("f1", "false-positive", None)
    finally:
        server.shutdown()
        server.server_close()


def test_triage_post_missing_fields_is_400(tmp_path):
    server, port = _start(tmp_path)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/triage",
            data=json.dumps({"finding_id": "f1"}).encode(),
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            assert False, "expected HTTPError"
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
    finally:
        server.shutdown()
        server.server_close()


def test_server_binds_localhost_only(tmp_path):
    server, port = _start(tmp_path)
    try:
        assert server.server_address[0] == "127.0.0.1"
    finally:
        server.shutdown()
        server.server_close()


def test_get_root_returns_404_when_page_dir_missing(tmp_path, monkeypatch):
    import flow_review.dashboard.serve as serve_mod
    monkeypatch.setattr(serve_mod, "PAGE_DIR", tmp_path / "does-not-exist-page")
    server, port = _start(tmp_path)
    try:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5)
            assert False, "expected HTTPError"
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        server.shutdown()
        server.server_close()


def test_get_unknown_static_path_is_404(tmp_path):
    server, port = _start(tmp_path)
    try:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/nope.css", timeout=5)
            assert False, "expected HTTPError"
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        server.shutdown()
        server.server_close()


def test_triage_post_returns_400_on_apply_exception(tmp_path, monkeypatch):
    server, port = _start(tmp_path)

    def fake_apply(ledger_path, finding_id, state, reason=None):
        raise ValueError("unknown triage state")

    import flow_review.dashboard.serve as serve_mod
    monkeypatch.setattr(serve_mod.triage, "apply", fake_apply)

    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/triage",
            data=json.dumps({"finding_id": "f1", "state": "bogus"}).encode(),
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            assert False, "expected HTTPError"
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
            body = json.loads(exc.read())
            assert "error" in body
    finally:
        server.shutdown()
        server.server_close()


def _get(port, path):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
            return r.status, r.headers.get("Content-Type")
    except urllib.error.HTTPError as exc:
        return exc.code, None


def test_run_route_serves_images_from_the_run_folder_only(tmp_path):
    from PIL import Image
    server, port = _start(tmp_path)
    run_dir = server.RequestHandlerClass.run_dir
    try:
        (run_dir / "shots").mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (8, 8)).save(run_dir / "shots" / "a.png")
        (run_dir / "events.jsonl").write_text("", encoding="utf-8")
        assert _get(port, "/run/shots/a.png") == (200, "image/png")
        assert _get(port, "/run/events.jsonl")[0] == 404            # not an image
        assert _get(port, "/run/../findings.json")[0] == 404        # traversal
        assert _get(port, "/run/%2e%2e/%2e%2e/secret.png")[0] == 404
    finally:
        server.shutdown()
        server.server_close()


def test_triage_post_from_a_foreign_origin_is_403(tmp_path):
    server, port = _start(tmp_path)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/triage",
            data=json.dumps({"finding_id": "f1", "state": "false-positive"}).encode(),
            headers={"Content-Type": "application/json", "Origin": "https://evil.example"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            assert False, "expected HTTPError"
        except urllib.error.HTTPError as exc:
            assert exc.code == 403
    finally:
        server.shutdown()
        server.server_close()
