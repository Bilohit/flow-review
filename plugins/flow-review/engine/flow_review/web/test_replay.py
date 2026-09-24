import json
from types import SimpleNamespace

import pytest
pytest.importorskip("playwright")
from PIL import Image

from flow_review import config
from flow_review.web import actionlog, replay as replay_mod
from flow_review.web.driver import LocatorNotFound


def _surface(base_url: str, surface_id: str = "webapp", **options) -> "config.Surface":
    opts = {"base_url": base_url, "viewport": [{"width": 1280, "height": 800}]}
    opts.update(options)
    return config.Surface(
        id=surface_id, name="Fixture App", kind="ui", driver="playwright", launch="",
        options=opts,
    )


# ---------- replay_one: fake driver, no browser ----------

class _FakeDriver:
    """Simulates just enough of WebDriver for replay_one: goto/click/fill and .page.url."""

    def __init__(self, fail_locators: set[str] | None = None,
                 click_target: str = "/dashboard"):
        self._fail_locators = fail_locators or set()
        self._click_target = click_target
        self.page = SimpleNamespace(url="http://x/")

    def _key(self, locator: dict) -> str:
        return locator.get("testid") or locator.get("css") or locator.get("role", "")

    def goto(self, path: str) -> None:
        self.page.url = "http://x" + path

    def click(self, locator: dict) -> None:
        if self._key(locator) in self._fail_locators:
            raise LocatorNotFound(locator)
        self.page.url = "http://x" + self._click_target

    def fill(self, locator: dict, value: str) -> None:
        pass

    def begin_step(self, index: int) -> None:
        pass

    def end_step(self) -> None:
        pass

    def screenshot(self, path) -> None:
        Image.new("RGB", (10, 10), (255, 255, 255)).save(path)


def test_replay_one_clean_flow_calls_measure_after_goto_and_click():
    log = actionlog.new_log("webapp", "load-and-click")
    actionlog.record_step(log, "goto", url="/")
    actionlog.record_step(log, "click", locator={"testid": "load-button"}, url="/")

    calls = []

    def spy_measure(driver, surface_id, flow_id, route, step_index):
        calls.append((surface_id, flow_id, route, step_index))
        return []

    result = replay_mod.replay_one(_FakeDriver(click_target="/"), log, measure=spy_measure)

    assert result["status"] == "clean"
    assert result["divergence"] is None
    assert result["findings"] == []
    assert calls == [("webapp", "load-and-click", "/", 0), ("webapp", "load-and-click", "/", 1)]


def test_replay_one_without_measure_hook_still_runs():
    log = actionlog.new_log("webapp", "no-hook")
    actionlog.record_step(log, "goto", url="/")
    result = replay_mod.replay_one(_FakeDriver(), log, measure=None)
    assert result["status"] == "clean"
    assert result["steps_run"] == 1


def test_replay_one_divergence_on_missing_locator():
    log = actionlog.new_log("webapp", "ghost-flow")
    actionlog.record_step(log, "goto", url="/")
    actionlog.record_step(log, "click", locator={"testid": "does-not-exist"}, url="/")

    result = replay_mod.replay_one(
        _FakeDriver(fail_locators={"does-not-exist"}), log, measure=lambda *a: [],
    )
    assert result["status"] == "divergence"
    assert result["divergence"]["step_index"] == 1
    assert result["divergence"]["reason"] == "locator_not_found"
    assert result["findings"] == []


def test_replay_one_checkpoint_mismatch_files_objective_p1_and_marks_regression():
    log = actionlog.new_log("webapp", "wrong-redirect")
    actionlog.record_step(log, "goto", url="/")
    actionlog.record_step(log, "click", locator={"testid": "signin-button"}, url="/")
    actionlog.record_step(log, "assert_url", url="/settings", checkpoint="post-login")

    result = replay_mod.replay_one(
        _FakeDriver(click_target="/dashboard"), log, measure=lambda *a: [],
    )
    assert result["status"] == "regression"
    assert len(result["findings"]) == 1
    f = result["findings"][0]
    assert f["rule"] == "replay.checkpoint"
    assert f["sev"] == "P1"
    assert f["disposition"] == "objective"
    assert "/settings" in f["text"] and "/dashboard" in f["text"]


def test_replay_one_checkpoint_match_stays_clean():
    log = actionlog.new_log("webapp", "right-redirect")
    actionlog.record_step(log, "goto", url="/")
    actionlog.record_step(log, "click", locator={"testid": "signin-button"}, url="/")
    actionlog.record_step(log, "assert_url", url="/dashboard", checkpoint="post-login")

    result = replay_mod.replay_one(
        _FakeDriver(click_target="/dashboard"), log, measure=lambda *a: [],
    )
    assert result["status"] == "clean"
    assert result["findings"] == []


def test_replay_one_unexpected_exception_files_objective_regression():
    log = actionlog.new_log("webapp", "boom-flow")
    actionlog.record_step(log, "goto", url="/")

    class _ExplodingDriver(_FakeDriver):
        def goto(self, path):
            raise RuntimeError("navigation timed out")

    result = replay_mod.replay_one(_ExplodingDriver(), log, measure=lambda *a: [])
    assert result["status"] == "regression"
    assert result["findings"][0]["rule"] == "replay.step_failed"
    assert result["findings"][0]["disposition"] == "objective"


# ---------- replay(): pure paths (no browser) ----------

def test_replay_no_recordings_prints_howto_and_exits_zero(tmp_path, capsys):
    cfg = config.Config(schema_version=2, generator_version="test",
                         surfaces=[_surface("http://127.0.0.1:1")])
    code = replay_mod.replay(cfg, tmp_path)
    assert code == 0
    assert "record" in capsys.readouterr().out.lower()


def test_replay_unknown_surface_exits_three(tmp_path, capsys):
    cfg = config.Config(schema_version=2, generator_version="test",
                         surfaces=[_surface("http://127.0.0.1:1")])
    code = replay_mod.replay(cfg, tmp_path, surface_id="does-not-exist")
    assert code == 3


def test_replay_ignores_non_playwright_surfaces(tmp_path):
    # driver="shell" (a cli surface) with a same-named recordings dir must never be replayed.
    recordings = tmp_path / ".flow-review" / "recordings" / "cli-tool"
    recordings.mkdir(parents=True)
    (recordings / "flow.json").write_text(json.dumps(actionlog.new_log("cli-tool", "flow")))
    cfg = config.Config(
        schema_version=2, generator_version="test",
        surfaces=[config.Surface(id="cli-tool", name="CLI", kind="cli", driver="shell",
                                  launch="")],
    )
    code = replay_mod.replay(cfg, tmp_path)
    assert code == 0  # treated as "no recordings" for any playwright surface


# ---------- e2e against the B0 fixture (real browser) ----------

@pytest.mark.web
def test_replay_e2e_http_5xx_reconciles_new_open_p0_and_exits_one(tmp_path, webapp_server):
    base_url, _ = webapp_server
    project_root = tmp_path / "project"
    run_dir = tmp_path / "runs" / "run1"
    run_dir.mkdir(parents=True)

    log = actionlog.new_log("webapp", "trigger-500")
    actionlog.record_step(log, "goto", url="/")
    actionlog.record_step(log, "click", locator={"testid": "load-button"}, url="/")
    actionlog.save(log, run_dir, project_root, record_enabled=True)

    cfg = config.Config(schema_version=2, generator_version="test",
                         surfaces=[_surface(base_url)])
    code = replay_mod.replay(cfg, project_root)
    assert code == 1

    from flow_review import ledger
    ledger_ = ledger.load(project_root / ".flow-review" / "findings.json")
    assert any(e.rule == "http.5xx" and e.state == "open" and e.sev == "P0"
               for e in ledger_.findings.values())


@pytest.mark.web
def test_replay_e2e_missing_locator_writes_divergences_and_exits_two(tmp_path, webapp_server):
    base_url, _ = webapp_server
    project_root = tmp_path / "project"
    run_dir = tmp_path / "runs" / "run1"
    run_dir.mkdir(parents=True)

    # docs.html has no seeded defects: "/" carries deliberate P1s (contrast, overlap) that would
    # make exit 1 win over divergence's exit 2.
    log = actionlog.new_log("webapp", "ghost-flow")
    actionlog.record_step(log, "goto", url="/docs.html")
    actionlog.record_step(log, "click", locator={"testid": "does-not-exist"}, url="/docs.html")
    actionlog.save(log, run_dir, project_root, record_enabled=True)

    cfg = config.Config(schema_version=2, generator_version="test",
                         surfaces=[_surface(base_url)])
    code = replay_mod.replay(cfg, project_root)
    assert code == 2
    div_path = project_root / ".flow-review" / "divergences.json"
    assert div_path.exists()
    data = json.loads(div_path.read_text())
    assert data["divergences"][0]["flow_id"] == "ghost-flow"
    assert data["divergences"][0]["reason"] == "locator_not_found"


@pytest.mark.web
def test_replay_log_mode_writes_result_json_and_never_touches_ledger(tmp_path, webapp_server):
    base_url, _ = webapp_server
    project_root = tmp_path / "project"
    run_dir = tmp_path / "runs" / "run1"
    run_dir.mkdir(parents=True)

    log = actionlog.new_log("webapp", "trigger-500")
    actionlog.record_step(log, "goto", url="/")
    actionlog.record_step(log, "click", locator={"testid": "load-button"}, url="/")
    log_path = actionlog.save(log, run_dir, project_root, record_enabled=False)

    cfg = config.Config(schema_version=2, generator_version="test",
                         surfaces=[_surface(base_url)])
    code = replay_mod.replay_log(cfg, project_root, log_path, run_dir)
    assert code == 1

    # C1: the result lands under the run dir, never next to the recorded log -- a
    # `<log>.result.json` sitting in recordings/ would be picked up by the next `replay()`
    # glob (which matches `*.json`) and crash it with a KeyError trying to parse it as a log.
    result_path = run_dir / "replay" / f"{log_path.stem}.result.json"
    assert result_path.exists()
    assert not log_path.with_name(log_path.name + ".result.json").exists()
    data = json.loads(result_path.read_text())
    assert any(f["rule"] == "http.5xx" for f in data["findings"])
    assert not (project_root / ".flow-review" / "findings.json").exists()
    assert not (project_root / ".flow-review" / "divergences.json").exists()



def test_replay_log_recording_result_then_replay_does_not_crash(tmp_path, monkeypatch):
    # C1: a previous bug wrote `<log>.result.json` next to the recorded log itself. Since the
    # log lives under recordings/ as `f.json`, the next `replay()` glob (`*.json`) would pick
    # the result file back up as if it were a recording and crash trying to parse it as one.
    project_root = tmp_path / "project"
    rec = project_root / ".flow-review" / "recordings" / "webapp"
    rec.mkdir(parents=True)
    log = actionlog.new_log("webapp", "f")
    actionlog.record_step(log, "goto", url="/")
    (rec / "f.json").write_text(json.dumps(log), encoding="utf-8")

    drv = _FakeDriver(click_target="/")
    drv.close = lambda: None
    monkeypatch.setattr(replay_mod, "_health_ok", lambda s: True)
    monkeypatch.setattr(replay_mod, "_launch_driver", lambda s: drv)
    monkeypatch.setattr(replay_mod, "_measure_hook", lambda t: (lambda *a: []))
    cfg = config.Config(schema_version=2, generator_version="test",
                         surfaces=[_surface("http://x")])

    run_dir = project_root / ".flow-review" / "runs" / "r1"
    run_dir.mkdir(parents=True)
    replay_mod.replay_log(cfg, project_root, rec / "f.json", run_dir,
                          variants=True, mode="quick")

    assert sorted(p.name for p in rec.iterdir()) == ["f.json"]
    code = replay_mod.replay(cfg, project_root)  # must not raise KeyError
    assert code == 0


def test_replay_variants_storage_state_dir_is_under_run_dir(tmp_path, monkeypatch):
    # I3: `.flow-review/variants/` is not gitignored, and a storage state can carry
    # cookies/tokens -- it must live under the (gitignored) run dir instead, like replay_log's
    # variants already do.
    project_root = tmp_path / "project"
    recordings = project_root / ".flow-review" / "recordings" / "webapp"
    recordings.mkdir(parents=True)
    log = actionlog.new_log("webapp", "f")
    actionlog.record_step(log, "goto", url="/")
    (recordings / "f.json").write_text(json.dumps(log), encoding="utf-8")

    drv = _FakeDriver(click_target="/")
    drv.close = lambda: None
    monkeypatch.setattr(replay_mod, "_health_ok", lambda s: True)
    monkeypatch.setattr(replay_mod, "_launch_driver", lambda s: drv)
    monkeypatch.setattr(replay_mod, "_measure_hook", lambda t: (lambda *a: []))

    captured = {}

    def spy(surface, base_url, log_, mode, storage_state_dir, **kw):
        captured["dir"] = storage_state_dir
        return [], []

    monkeypatch.setattr(replay_mod, "_run_variants", spy)
    cfg = config.Config(schema_version=2, generator_version="test",
                         surfaces=[_surface("http://x")])
    replay_mod.replay(cfg, project_root, variants=True, mode="goal")

    old_path = project_root / ".flow-review" / "variants" / "webapp"
    assert captured["dir"] != old_path
    assert (project_root / ".flow-review" / "runs") in captured["dir"].parents


def test_replay_log_variants_clean_emits_flow_begin_for_reconcile(tmp_path, monkeypatch):
    # I4: on the --log path (the path SKILL.md uses), a variant flow id that ran must be
    # recorded the same way `drive`'s own flow-begin is, or `ledger reconcile`'s flows_run
    # builder never learns the variant flow ran, and a variant finding can never turn fixed.
    project_root = tmp_path / "project"
    run_dir = tmp_path / "runs" / "run1"
    run_dir.mkdir(parents=True)
    log = actionlog.new_log("webapp", "f")
    actionlog.record_step(log, "goto", url="/")
    log_path = actionlog.save(log, run_dir, project_root, record_enabled=False)

    drv = _FakeDriver(click_target="/")
    drv.close = lambda: None
    monkeypatch.setattr(replay_mod, "_health_ok", lambda s: True)
    monkeypatch.setattr(replay_mod, "_launch_driver", lambda s: drv)
    monkeypatch.setattr(replay_mod, "_measure_hook", lambda t: (lambda *a: []))

    variant = {"kind": "color-scheme", "params": {"scheme": "dark"}}
    clean = replay_mod.ReplayResult(flow_id="f@color-scheme:dark", status="clean", steps_run=1,
                                    divergence=None, findings=[])
    monkeypatch.setattr("flow_review.web.variants.run_all", lambda *a, **kw: [(variant, clean)])

    cfg = config.Config(schema_version=2, generator_version="test",
                         surfaces=[_surface("http://x")])
    code = replay_mod.replay_log(cfg, project_root, log_path, run_dir,
                                 variants=True, mode="goal")
    assert code == 0

    events_path = run_dir / "events.jsonl"
    lines = [json.loads(line) for line in events_path.read_text().splitlines()]
    flow_begins = [e for e in lines if e["type"] == "step" and e.get("step") == "flow-begin"]
    assert any(e["flow_id"] == "f@color-scheme:dark" for e in flow_begins)


def test__run_variants_drops_findings_that_match_the_base_flow(monkeypatch):
    # I6: a variant replay re-measures the whole page and re-files every base-flow finding
    # under its own tagged flow id -- drop whatever exactly matches (rule, route, locator) on
    # the base flow's own result, keep whatever is genuinely new under the variant.
    surface = _surface("http://x")
    log = {"flow_id": "f", "steps": []}
    variant = {"kind": "color-scheme", "params": {"scheme": "dark"}}
    dup = {"surface_id": "webapp", "flow_id": "f@color-scheme:dark", "rule": "contrast.aa",
           "route": "/", "locator": "", "sev": "P2", "text": "low contrast", "evidence": [],
           "disposition": "engine"}
    fresh = {"surface_id": "webapp", "flow_id": "f@color-scheme:dark", "rule": "contrast.aa",
             "route": "/other", "locator": "", "sev": "P2", "text": "low contrast",
             "evidence": [], "disposition": "engine"}
    clean_with_findings = replay_mod.ReplayResult(
        flow_id="f@color-scheme:dark", status="clean", steps_run=1, divergence=None,
        findings=[dup, fresh],
    )
    monkeypatch.setattr("flow_review.web.variants.run_all",
                        lambda *a, **kw: [(variant, clean_with_findings)])
    base_findings = [{"rule": "contrast.aa", "route": "/", "locator": ""}]
    findings, flow_ids = replay_mod._run_variants(surface, "http://x", log, "goal", None,
                                                   base_findings=base_findings)
    assert findings == [fresh]


def test_replay_one_resolves_from_env_fill_and_registers_secret(monkeypatch):
    from flow_review import events
    monkeypatch.setattr(replay_mod.envsetup, "project_secret_names", lambda root: {"RP_PW"})
    monkeypatch.setenv("RP_PW", "Rp9secretvalue")
    log = actionlog.new_log("webapp", "login")
    actionlog.record_step(log, "fill", locator={"css": "#pw", "secret": True}, from_env="RP_PW")
    filled = []
    drv = _FakeDriver()
    drv.fill = lambda loc, v, secret=False: filled.append((v, secret))
    result = replay_mod.replay_one(drv, log)
    assert result["status"] == "clean"
    # I2: a from_env fill must reach driver.fill with secret=True so a baseline screenshot
    # masks it, even though this locator's own "secret" flag is also True here.
    assert filled == [("Rp9secretvalue", True)]
    assert "Rp9secretvalue" not in events.redact("Rp9secretvalue")


def test_replay_one_missing_env_raises_missing_env(monkeypatch):
    monkeypatch.delenv("RP_MISSING", raising=False)
    log = actionlog.new_log("webapp", "login")
    actionlog.record_step(log, "fill", locator={"css": "#pw", "secret": True}, from_env="RP_MISSING")
    with pytest.raises(replay_mod.MissingEnv):
        replay_mod.replay_one(_FakeDriver(), log)


def _dead_port() -> int:
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_replay_app_unreachable_exits_three_without_touching_ledger(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    log = actionlog.new_log("webapp", "f")
    actionlog.record_step(log, "goto", url="/")
    actionlog.save(log, tmp_path, project_root, record_enabled=True)
    launched = []
    monkeypatch.setattr(replay_mod, "_launch_driver", lambda s: launched.append(s))
    cfg = config.Config(schema_version=2, generator_version="test",
                         surfaces=[_surface(f"http://127.0.0.1:{_dead_port()}",
                                            health_path="/healthz")])
    assert replay_mod.replay(cfg, project_root) == 3
    assert launched == []
    assert not (project_root / ".flow-review" / "findings.json").exists()


def test_replay_log_app_unreachable_exits_three(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    log = actionlog.new_log("webapp", "f")
    actionlog.record_step(log, "goto", url="/")
    log_path = actionlog.save(log, tmp_path, project_root, record_enabled=False)
    monkeypatch.setattr(replay_mod, "_launch_driver", lambda s: pytest.fail("launched"))
    cfg = config.Config(schema_version=2, generator_version="test",
                         surfaces=[_surface(f"http://127.0.0.1:{_dead_port()}")])
    assert replay_mod.replay_log(cfg, project_root, log_path, tmp_path) == 3


def test_diverged_flow_does_not_mark_unseen_findings_fixed(tmp_path, monkeypatch):
    from flow_review import ledger
    project_root = tmp_path / "project"
    ledger_path = project_root / ".flow-review" / "findings.json"
    ledger_path.parent.mkdir(parents=True)
    seeded = {"surface_id": "webapp", "flow_id": "f", "rule": "contrast.aa", "route": "/after",
              "locator": "", "sev": "P2", "text": "late step", "evidence": [],
              "disposition": "engine"}
    ledger.save(ledger.reconcile(ledger.load(ledger_path), [seeded], {"f"}, "r0"), ledger_path)

    log = actionlog.new_log("webapp", "f")
    actionlog.record_step(log, "goto", url="/")
    actionlog.record_step(log, "click", locator={"testid": "gone"}, url="/")
    actionlog.save(log, tmp_path, project_root, record_enabled=True)

    drv = _FakeDriver(fail_locators={"gone"})
    drv.close = lambda: None
    monkeypatch.setattr(replay_mod, "_health_ok", lambda s: True)
    monkeypatch.setattr(replay_mod, "_launch_driver", lambda s: drv)
    monkeypatch.setattr(replay_mod, "_measure_hook", lambda t: (lambda *a: []))
    cfg = config.Config(schema_version=2, generator_version="test",
                         surfaces=[_surface("http://x")])
    assert replay_mod.replay(cfg, project_root) == 2
    states = {e.state for e in ledger.load(ledger_path).findings.values()}
    assert states == {"open"}


# ---------- --variants wiring (fake driver, no browser) ----------

def test__run_variants_files_p1_summary_for_a_bare_divergence(monkeypatch):
    # No underlying finding to carry its own sev (LocatorNotFound never reaches measure/
    # checkpoint code), so this is the one case that still gets a synthetic P1 `variant.<kind>`.
    surface = _surface("http://x")
    log = {"flow_id": "f", "steps": []}
    variant = {"kind": "viewport", "params": {"width": 375, "height": 812}}
    diverged = replay_mod.ReplayResult(
        flow_id="f@viewport:375x812", status="divergence", steps_run=1,
        divergence={"step_index": 0, "locator": None, "reason": "locator_not_found",
                    "url": "/x"},
        findings=[],
    )
    monkeypatch.setattr("flow_review.web.variants.run_all",
                        lambda *a, **kw: [(variant, diverged)])
    findings, flow_ids = replay_mod._run_variants(surface, "http://x", log, "goal", None)

    assert len(findings) == 1
    finding = findings[0]
    assert finding["surface_id"] == "webapp" and finding["flow_id"] == "f@viewport:375x812"
    assert finding["rule"] == "variant.viewport"
    assert finding["sev"] == "P1"
    assert finding["disposition"] == "engine"
    assert finding["route"] == "/x"
    assert any("375" in item for item in finding["evidence"])
    # I5: a diverged variant never reached its later steps, so its flow id must NOT be folded
    # into flows_run -- otherwise an unrelated, unseen finding under that flow id would be
    # marked "fixed" simply because the variant never got far enough to see it again.
    assert flow_ids == []


def test__run_variants_passes_through_measured_findings_with_their_own_severity(monkeypatch):
    # CRITICAL fix: a contrast/overlap finding measured under a variant keeps its own rule id
    # and sev, it is never collapsed into a generic P1 `variant.<kind>` summary.
    surface = _surface("http://x")
    log = {"flow_id": "f", "steps": []}
    variant = {"kind": "color-scheme", "params": {"scheme": "dark"}}
    measured = {"surface_id": "webapp", "flow_id": "f@color-scheme:dark", "rule": "contrast.aa",
                "route": "/", "locator": "", "sev": "P2", "text": "low contrast", "evidence": [],
                "disposition": "engine"}
    clean_with_finding = replay_mod.ReplayResult(
        flow_id="f@color-scheme:dark", status="clean", steps_run=1, divergence=None,
        findings=[measured],
    )
    monkeypatch.setattr("flow_review.web.variants.run_all",
                        lambda *a, **kw: [(variant, clean_with_finding)])
    findings, flow_ids = replay_mod._run_variants(surface, "http://x", log, "goal", None)

    assert findings == [measured]
    assert findings[0]["sev"] == "P2"
    assert findings[0]["rule"] == "contrast.aa"
    assert flow_ids == ["f@color-scheme:dark"]


def test__run_variants_skips_clean_variants_but_still_reports_their_flow_id(monkeypatch):
    # IMPORTANT fix: a clean variant files nothing, but its tagged flow id must still be
    # reported so the caller can add it to `flows_run` -- otherwise a previously-filed variant
    # finding can never be marked fixed once the underlying bug is fixed.
    surface = _surface("http://x")
    log = {"flow_id": "f", "steps": []}
    variant = {"kind": "reduced-motion", "params": {}}
    clean = replay_mod.ReplayResult(flow_id="f@reduced-motion", status="clean", steps_run=1,
                                    divergence=None, findings=[])
    monkeypatch.setattr("flow_review.web.variants.run_all", lambda *a, **kw: [(variant, clean)])
    findings, flow_ids = replay_mod._run_variants(surface, "http://x", log, "goal", None)

    assert findings == []
    assert flow_ids == ["f@reduced-motion"]


def test__run_variants_threads_the_measure_hook_into_run_all(monkeypatch):
    surface = _surface("http://x")
    log = {"flow_id": "f", "steps": []}
    captured = {}

    def fake_run_all(driver_factory, base_url, log_, surface_, storage_state_dir, mode, measure,
                     base_viewport=None):
        captured["measure"] = measure
        return []

    monkeypatch.setattr("flow_review.web.variants.run_all", fake_run_all)
    sentinel = object()
    replay_mod._run_variants(surface, "http://x", log, "goal", None, measure=sentinel)

    assert captured["measure"] is sentinel


def test_replay_log_variants_quick_mode_runs_none(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    run_dir = tmp_path / "runs" / "run1"
    run_dir.mkdir(parents=True)
    log = actionlog.new_log("webapp", "f")
    actionlog.record_step(log, "goto", url="/")
    log_path = actionlog.save(log, run_dir, project_root, record_enabled=False)

    drv = _FakeDriver(click_target="/")
    drv.close = lambda: None
    monkeypatch.setattr(replay_mod, "_health_ok", lambda s: True)
    monkeypatch.setattr(replay_mod, "_launch_driver", lambda s: drv)
    monkeypatch.setattr(replay_mod, "_measure_hook", lambda t: (lambda *a: []))
    cfg = config.Config(schema_version=2, generator_version="test",
                         surfaces=[_surface("http://x")])

    code = replay_mod.replay_log(cfg, project_root, log_path, run_dir,
                                 variants=True, mode="quick")
    assert code == 0
    assert not (run_dir / "events.jsonl").exists()


def test_replay_log_variants_off_leaves_events_untouched(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    run_dir = tmp_path / "runs" / "run1"
    run_dir.mkdir(parents=True)
    log = actionlog.new_log("webapp", "f")
    actionlog.record_step(log, "goto", url="/")
    log_path = actionlog.save(log, run_dir, project_root, record_enabled=False)

    drv = _FakeDriver(click_target="/")
    drv.close = lambda: None
    monkeypatch.setattr(replay_mod, "_health_ok", lambda s: True)
    monkeypatch.setattr(replay_mod, "_launch_driver", lambda s: drv)
    monkeypatch.setattr(replay_mod, "_measure_hook", lambda t: (lambda *a: []))
    cfg = config.Config(schema_version=2, generator_version="test",
                         surfaces=[_surface("http://x")])

    code = replay_mod.replay_log(cfg, project_root, log_path, run_dir)
    assert code == 0
    assert not (run_dir / "events.jsonl").exists()


def test_replay_log_variants_files_finding_and_exits_one(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    run_dir = tmp_path / "runs" / "run1"
    run_dir.mkdir(parents=True)
    log = actionlog.new_log("webapp", "f")
    actionlog.record_step(log, "goto", url="/")
    log_path = actionlog.save(log, run_dir, project_root, record_enabled=False)

    drv = _FakeDriver(click_target="/")
    drv.close = lambda: None
    monkeypatch.setattr(replay_mod, "_health_ok", lambda s: True)
    monkeypatch.setattr(replay_mod, "_launch_driver", lambda s: drv)
    monkeypatch.setattr(replay_mod, "_measure_hook", lambda t: (lambda *a: []))

    variant = {"kind": "viewport", "params": {"width": 375, "height": 812}}
    diverged = replay_mod.ReplayResult(
        flow_id="f", status="divergence", steps_run=1,
        divergence={"step_index": 0, "locator": None, "reason": "locator_not_found",
                    "url": "/x"},
        findings=[],
    )
    monkeypatch.setattr("flow_review.web.variants.run_all", lambda *a, **kw: [(variant, diverged)])

    cfg = config.Config(schema_version=2, generator_version="test",
                         surfaces=[_surface("http://x")])
    code = replay_mod.replay_log(cfg, project_root, log_path, run_dir,
                                 variants=True, mode="goal")
    assert code == 1

    events_path = run_dir / "events.jsonl"
    lines = [json.loads(line) for line in events_path.read_text().splitlines()]
    findings = [e for e in lines if e["type"] == "finding"]
    assert len(findings) == 1
    assert findings[0]["rule"] == "variant.viewport"
    assert findings[0]["sev"] == "P1"
    assert findings[0]["disposition"] == "engine"


def test_replay_variants_files_finding_and_flows_into_ledger(tmp_path, monkeypatch):
    from flow_review import ledger
    project_root = tmp_path / "project"
    recordings = project_root / ".flow-review" / "recordings" / "webapp"
    recordings.mkdir(parents=True)
    log = actionlog.new_log("webapp", "f")
    actionlog.record_step(log, "goto", url="/")
    (recordings / "f.json").write_text(json.dumps(log), encoding="utf-8")

    drv = _FakeDriver(click_target="/")
    drv.close = lambda: None
    monkeypatch.setattr(replay_mod, "_health_ok", lambda s: True)
    monkeypatch.setattr(replay_mod, "_launch_driver", lambda s: drv)
    monkeypatch.setattr(replay_mod, "_measure_hook", lambda t: (lambda *a: []))

    variant = {"kind": "color-scheme", "params": {"scheme": "dark"}}
    regressed = replay_mod.ReplayResult(flow_id="f", status="regression", steps_run=1,
                                        divergence=None, findings=[])
    monkeypatch.setattr("flow_review.web.variants.run_all",
                        lambda *a, **kw: [(variant, regressed)])

    cfg = config.Config(schema_version=2, generator_version="test",
                         surfaces=[_surface("http://x")])
    code = replay_mod.replay(cfg, project_root, variants=True, mode="goal")
    assert code == 1

    ledger_ = ledger.load(project_root / ".flow-review" / "findings.json")
    assert any(e.rule == "variant.color-scheme" and e.sev == "P1"
               for e in ledger_.findings.values())


def test_replay_variants_off_by_default_does_not_touch_ledger_variants(tmp_path, monkeypatch):
    from flow_review import ledger
    project_root = tmp_path / "project"
    recordings = project_root / ".flow-review" / "recordings" / "webapp"
    recordings.mkdir(parents=True)
    log = actionlog.new_log("webapp", "f")
    actionlog.record_step(log, "goto", url="/")
    (recordings / "f.json").write_text(json.dumps(log), encoding="utf-8")

    drv = _FakeDriver(click_target="/")
    drv.close = lambda: None
    monkeypatch.setattr(replay_mod, "_health_ok", lambda s: True)
    monkeypatch.setattr(replay_mod, "_launch_driver", lambda s: drv)
    monkeypatch.setattr(replay_mod, "_measure_hook", lambda t: (lambda *a: []))

    cfg = config.Config(schema_version=2, generator_version="test",
                         surfaces=[_surface("http://x")])
    code = replay_mod.replay(cfg, project_root)
    assert code == 0
    ledger_ = ledger.load(project_root / ".flow-review" / "findings.json")
    assert not any(e.rule.startswith("variant.") for e in ledger_.findings.values())


def test_replay_variant_finding_marked_fixed_once_its_variant_flow_replays_clean(
    tmp_path, monkeypatch,
):
    # IMPORTANT fix: the variant's tagged flow id must be added to `flows_run` so
    # ledger.reconcile can mark a stale variant finding fixed once it stops reproducing.
    from flow_review import ledger
    project_root = tmp_path / "project"
    recordings = project_root / ".flow-review" / "recordings" / "webapp"
    recordings.mkdir(parents=True)
    log = actionlog.new_log("webapp", "f")
    actionlog.record_step(log, "goto", url="/")
    (recordings / "f.json").write_text(json.dumps(log), encoding="utf-8")

    drv = _FakeDriver(click_target="/")
    drv.close = lambda: None
    monkeypatch.setattr(replay_mod, "_health_ok", lambda s: True)
    monkeypatch.setattr(replay_mod, "_launch_driver", lambda s: drv)
    monkeypatch.setattr(replay_mod, "_measure_hook", lambda t: (lambda *a: []))

    variant = {"kind": "viewport", "params": {"width": 375, "height": 812}}
    diverged = replay_mod.ReplayResult(
        flow_id="f@viewport:375x812", status="divergence", steps_run=1,
        divergence={"step_index": 0, "locator": None, "reason": "locator_not_found",
                    "url": "/x"},
        findings=[],
    )
    monkeypatch.setattr("flow_review.web.variants.run_all",
                        lambda *a, **kw: [(variant, diverged)])
    cfg = config.Config(schema_version=2, generator_version="test",
                         surfaces=[_surface("http://x")])
    code = replay_mod.replay(cfg, project_root, variants=True, mode="goal")
    assert code == 1

    ledger_path = project_root / ".flow-review" / "findings.json"
    entry = next(e for e in ledger.load(ledger_path).findings.values()
                 if e.rule == "variant.viewport")
    assert entry.state == "open"

    # Second run: the same variant now replays clean.
    clean = replay_mod.ReplayResult(flow_id="f@viewport:375x812", status="clean", steps_run=1,
                                    divergence=None, findings=[])
    monkeypatch.setattr("flow_review.web.variants.run_all", lambda *a, **kw: [(variant, clean)])
    code2 = replay_mod.replay(cfg, project_root, variants=True, mode="goal")
    assert code2 == 0

    entry2 = ledger.load(ledger_path).findings[entry.id]
    assert entry2.state == "fixed"


def test_replay_any_divergence_exits_two_even_with_findings_in_the_same_run(
    tmp_path, monkeypatch,
):
    # MINOR fix: documented precedence is "any divergence -> exit 2", even when another flow in
    # the same run produced findings that would otherwise win exit 1.
    project_root = tmp_path / "project"
    recordings = project_root / ".flow-review" / "recordings" / "webapp"
    recordings.mkdir(parents=True)

    checkpoint_log = actionlog.new_log("webapp", "checkpoint-mismatch")
    actionlog.record_step(checkpoint_log, "goto", url="/")
    actionlog.record_step(checkpoint_log, "click", locator={"testid": "signin-button"}, url="/")
    actionlog.record_step(checkpoint_log, "assert_url", url="/settings",
                          checkpoint="post-login")
    (recordings / "checkpoint-mismatch.json").write_text(json.dumps(checkpoint_log),
                                                          encoding="utf-8")

    ghost_log = actionlog.new_log("webapp", "ghost")
    actionlog.record_step(ghost_log, "goto", url="/")
    actionlog.record_step(ghost_log, "click", locator={"testid": "does-not-exist"}, url="/")
    (recordings / "ghost.json").write_text(json.dumps(ghost_log), encoding="utf-8")

    drv = _FakeDriver(fail_locators={"does-not-exist"}, click_target="/dashboard")
    drv.close = lambda: None
    monkeypatch.setattr(replay_mod, "_health_ok", lambda s: True)
    monkeypatch.setattr(replay_mod, "_launch_driver", lambda s: drv)
    monkeypatch.setattr(replay_mod, "_measure_hook", lambda t: (lambda *a: []))

    cfg = config.Config(schema_version=2, generator_version="test",
                         surfaces=[_surface("http://x")])
    code = replay_mod.replay(cfg, project_root)
    assert code == 2


def test_replay_one_opens_a_step_window_per_step():
    log = actionlog.new_log("webapp", "f")
    actionlog.record_step(log, "goto", url="/")
    actionlog.record_step(log, "click", locator={"testid": "b"}, url="/")
    drv = _FakeDriver(click_target="/")
    seen = []
    drv.begin_step = lambda i: seen.append(("begin", i))
    drv.end_step = lambda: seen.append(("end",))
    replay_mod.replay_one(drv, log, measure=lambda *a: seen.append(("measure",)) or [])
    assert seen == [("begin", 0), ("end",), ("measure",), ("begin", 1), ("end",), ("measure",)]


# ---------- visual baselines (A-28/A-32): fake driver, no browser ----------

class _FakeScreenshotDriver:
    """Writes a solid-color PNG of a given size on each screenshot() call, in the order given,
    simulating the masked screenshot WebDriver.screenshot() would take."""

    def __init__(self, images: list[tuple[tuple[int, int, int], tuple[int, int]]]):
        self._images = list(images)
        self.calls = 0

    def screenshot(self, path):
        color, size = self._images[self.calls]
        self.calls += 1
        Image.new("RGB", size, color).save(path)
        return path


def test_visual_baseline_first_replay_saves_baseline_and_files_nothing(tmp_path):
    surface_dir, run_dir = tmp_path / "surface", tmp_path / "run"
    surface_dir.mkdir()
    drv = _FakeScreenshotDriver([((255, 255, 255), (100, 100))])
    finding = replay_mod._visual_baseline_check(
        drv, surface_dir, run_dir, "home", "webapp", "home", "/", update_baselines=False,
    )
    assert finding is None
    baseline = surface_dir / "home.baseline.png"
    assert baseline.exists()
    with Image.open(baseline) as img:
        assert img.size == (100, 100)
    # crops only ever appear inside the run dir, never next to the (persistent) baseline
    assert not run_dir.exists() or not any(run_dir.rglob("*.png"))


def test_visual_baseline_unchanged_app_files_nothing(tmp_path):
    surface_dir, run_dir = tmp_path / "surface", tmp_path / "run"
    surface_dir.mkdir()
    drv = _FakeScreenshotDriver([
        ((255, 255, 255), (100, 100)),
        ((255, 255, 255), (100, 100)),
    ])
    replay_mod._visual_baseline_check(drv, surface_dir, run_dir, "home", "webapp", "home", "/",
                                      update_baselines=False)
    finding = replay_mod._visual_baseline_check(drv, surface_dir, run_dir, "home", "webapp",
                                                "home", "/", update_baselines=False)
    assert finding is None
    # the "current" screenshot must not linger next to the baseline
    assert not (surface_dir / "home.current.png").exists()


def test_visual_baseline_changed_app_files_p2_with_run_relative_crop_evidence(tmp_path):
    surface_dir, run_dir = tmp_path / "surface", tmp_path / "run"
    surface_dir.mkdir()
    drv = _FakeScreenshotDriver([
        ((255, 255, 255), (100, 100)),
    ])
    replay_mod._visual_baseline_check(drv, surface_dir, run_dir, "home", "webapp", "home", "/",
                                      update_baselines=False)

    changed_img = Image.new("RGB", (100, 100), (255, 255, 255))
    for x in range(10, 60):
        for y in range(10, 60):
            changed_img.putpixel((x, y), (255, 0, 0))
    drv2 = SimpleNamespace(screenshot=lambda path: changed_img.save(path))

    finding = replay_mod._visual_baseline_check(drv2, surface_dir, run_dir, "home", "webapp",
                                                "home", "/dash", update_baselines=False)
    assert finding is not None
    assert finding["rule"] == "visual.changed"
    assert finding["sev"] == "P2"
    assert finding["disposition"] == "engine"
    assert finding["surface_id"] == "webapp"
    assert finding["flow_id"] == "home"
    assert finding["route"] == "/dash"
    assert finding["locator"] == ""
    assert finding["evidence"], "expected at least one crop path as evidence"
    for crop in finding["evidence"]:
        # run-relative, forward-slashed, and it must actually resolve under run_dir --
        # the same form dashboard/serve.py's /run/<relpath> route and validate.py expect.
        assert not crop.startswith("/") and ".." not in crop.split("/")
        assert (run_dir / crop).exists()
    # crops never land next to the (persistent) baseline
    assert not any(surface_dir.glob("*.diff")) and not any(surface_dir.rglob("region_*.png"))
    # the baseline itself is untouched by a plain (non-update) diff
    with Image.open(surface_dir / "home.baseline.png") as img:
        assert img.getpixel((0, 0)) == (255, 255, 255)


def test_visual_baseline_update_baselines_overwrites_and_files_nothing(tmp_path):
    surface_dir, run_dir = tmp_path / "surface", tmp_path / "run"
    surface_dir.mkdir()
    drv = _FakeScreenshotDriver([
        ((255, 255, 255), (100, 100)),
    ])
    replay_mod._visual_baseline_check(drv, surface_dir, run_dir, "home", "webapp", "home", "/",
                                      update_baselines=False)

    changed_img = Image.new("RGB", (100, 100), (0, 0, 0))
    drv2 = SimpleNamespace(screenshot=lambda path: changed_img.save(path))
    finding = replay_mod._visual_baseline_check(drv2, surface_dir, run_dir, "home", "webapp",
                                                "home", "/", update_baselines=True)
    assert finding is None
    with Image.open(surface_dir / "home.baseline.png") as img:
        assert img.getpixel((0, 0)) == (0, 0, 0)


def test_visual_baseline_size_mismatch_treated_as_changed_without_crashing(tmp_path):
    surface_dir, run_dir = tmp_path / "surface", tmp_path / "run"
    surface_dir.mkdir()
    drv = _FakeScreenshotDriver([
        ((255, 255, 255), (100, 100)),
    ])
    replay_mod._visual_baseline_check(drv, surface_dir, run_dir, "home", "webapp", "home", "/",
                                      update_baselines=False)

    # same solid color, different size: an implicit resize-then-diff would see no change at all,
    # so this only passes if the size mismatch is treated as "changed" explicitly.
    small_img = Image.new("RGB", (50, 50), (255, 255, 255))
    drv2 = SimpleNamespace(screenshot=lambda path: small_img.save(path))
    finding = replay_mod._visual_baseline_check(drv2, surface_dir, run_dir, "home", "webapp",
                                                "home", "/", update_baselines=False)
    assert finding is not None
    assert finding["rule"] == "visual.changed"
    assert finding["evidence"]
    assert (run_dir / finding["evidence"][0]).exists()


# ---------- baseline gate: only a cleanly-completed base flow (A-32) ----------

def test_replay_crashed_flow_never_writes_or_updates_baseline(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    recordings = project_root / ".flow-review" / "recordings" / "webapp"
    recordings.mkdir(parents=True)
    log = actionlog.new_log("webapp", "f")
    actionlog.record_step(log, "goto", url="/")
    actionlog.record_step(log, "click", locator={"testid": "boom"}, url="/")
    (recordings / "f.json").write_text(json.dumps(log), encoding="utf-8")

    class _CrashingDriver(_FakeDriver):
        def click(self, locator):
            raise RuntimeError("kaboom")

        def screenshot(self, path):
            pytest.fail("a crashed (incomplete) flow must never take a baseline screenshot")

    drv = _CrashingDriver()
    drv.close = lambda: None
    monkeypatch.setattr(replay_mod, "_health_ok", lambda s: True)
    monkeypatch.setattr(replay_mod, "_launch_driver", lambda s: drv)
    monkeypatch.setattr(replay_mod, "_measure_hook", lambda t: (lambda *a: []))

    cfg = config.Config(schema_version=2, generator_version="test",
                         surfaces=[_surface("http://x")])
    code = replay_mod.replay(cfg, project_root)

    assert code == 1  # a real regression, just not one that should ever touch a baseline
    assert not (recordings / "f.baseline.png").exists()


def test_replay_checkpoint_mismatch_never_writes_or_updates_baseline(tmp_path, monkeypatch):
    # A checkpoint mismatch runs the flow to completion (status="regression", not
    # "divergence"), so this is a separate case from the crash above: "clean" is still the
    # only status baselines are gated on.
    project_root = tmp_path / "project"
    recordings = project_root / ".flow-review" / "recordings" / "webapp"
    recordings.mkdir(parents=True)
    log = actionlog.new_log("webapp", "f")
    actionlog.record_step(log, "goto", url="/")
    actionlog.record_step(log, "click", locator={"testid": "signin-button"}, url="/")
    actionlog.record_step(log, "assert_url", url="/settings", checkpoint="post-login")
    (recordings / "f.json").write_text(json.dumps(log), encoding="utf-8")

    drv = _FakeDriver(click_target="/dashboard")
    drv.close = lambda: None
    drv.screenshot = lambda path: pytest.fail(
        "a checkpoint-mismatch flow must never take a baseline screenshot either"
    )
    monkeypatch.setattr(replay_mod, "_health_ok", lambda s: True)
    monkeypatch.setattr(replay_mod, "_launch_driver", lambda s: drv)
    monkeypatch.setattr(replay_mod, "_measure_hook", lambda t: (lambda *a: []))

    cfg = config.Config(schema_version=2, generator_version="test",
                         surfaces=[_surface("http://x")])
    replay_mod.replay(cfg, project_root)

    assert not (recordings / "f.baseline.png").exists()


def test_replay_update_baselines_still_gated_on_clean_status(tmp_path, monkeypatch):
    # --update-baselines must not bypass the clean-status gate: a crashed flow still must not
    # write a baseline even when the caller asked to accept whatever the screenshot shows.
    project_root = tmp_path / "project"
    recordings = project_root / ".flow-review" / "recordings" / "webapp"
    recordings.mkdir(parents=True)
    log = actionlog.new_log("webapp", "f")
    actionlog.record_step(log, "goto", url="/")
    actionlog.record_step(log, "click", locator={"testid": "boom"}, url="/")
    (recordings / "f.json").write_text(json.dumps(log), encoding="utf-8")

    class _CrashingDriver(_FakeDriver):
        def click(self, locator):
            raise RuntimeError("kaboom")

        def screenshot(self, path):
            pytest.fail("a crashed flow must never take a baseline screenshot, "
                        "even under --update-baselines")

    drv = _CrashingDriver()
    drv.close = lambda: None
    monkeypatch.setattr(replay_mod, "_health_ok", lambda s: True)
    monkeypatch.setattr(replay_mod, "_launch_driver", lambda s: drv)
    monkeypatch.setattr(replay_mod, "_measure_hook", lambda t: (lambda *a: []))

    cfg = config.Config(schema_version=2, generator_version="test",
                         surfaces=[_surface("http://x")])
    replay_mod.replay(cfg, project_root, update_baselines=True)

    assert not (recordings / "f.baseline.png").exists()


# ---------- --log replays never write baselines (A-3) ----------

def test_replay_log_never_writes_a_baseline(tmp_path, monkeypatch):
    project_root = tmp_path / "project"
    run_dir = tmp_path / "runs" / "run1"
    run_dir.mkdir(parents=True)
    log = actionlog.new_log("webapp", "f")
    actionlog.record_step(log, "goto", url="/")
    log_path = actionlog.save(log, run_dir, project_root, record_enabled=False)

    drv = _FakeDriver(click_target="/")
    drv.close = lambda: None
    drv.screenshot = lambda path: pytest.fail("--log replay must never take a baseline screenshot")
    monkeypatch.setattr(replay_mod, "_health_ok", lambda s: True)
    monkeypatch.setattr(replay_mod, "_launch_driver", lambda s: drv)
    monkeypatch.setattr(replay_mod, "_measure_hook", lambda t: (lambda *a: []))
    cfg = config.Config(schema_version=2, generator_version="test",
                         surfaces=[_surface("http://x")])

    code = replay_mod.replay_log(cfg, project_root, log_path, run_dir)
    assert code == 0
    assert not any(
        p.name.endswith(".baseline.png")
        for p in (project_root / ".flow-review").rglob("*.png") if (project_root / ".flow-review").exists()
    )


# ---------- e2e against a throwaway copy of the B0 fixture (real browser) ----------

@pytest.mark.web
def test_replay_e2e_visual_baseline_saved_then_diffed_after_css_change(tmp_path,
                                                                        webapp_dir_and_url):
    from flow_review import ledger

    base_url, webapp_dir = webapp_dir_and_url
    project_root = tmp_path / "project"
    run_dir = tmp_path / "runs" / "run1"
    run_dir.mkdir(parents=True)

    log = actionlog.new_log("webapp", "home")
    actionlog.record_step(log, "goto", url="/")
    actionlog.save(log, run_dir, project_root, record_enabled=True)

    cfg = config.Config(schema_version=2, generator_version="test", surfaces=[_surface(base_url)])
    ledger_path = project_root / ".flow-review" / "findings.json"
    baseline_path = project_root / ".flow-review" / "recordings" / "webapp" / "home.baseline.png"

    # first replay: saves the baseline, files nothing
    replay_mod.replay(cfg, project_root)
    assert baseline_path.exists()
    assert not any(e.rule == "visual.changed" for e in ledger.load(ledger_path).findings.values())
    first_mtime = baseline_path.stat().st_mtime_ns

    # second replay: unchanged app, files nothing, baseline untouched
    replay_mod.replay(cfg, project_root)
    assert not any(e.rule == "visual.changed" for e in ledger.load(ledger_path).findings.values())
    assert baseline_path.stat().st_mtime_ns == first_mtime

    # plant a CSS change in the throwaway copy, never the real fixture
    css_path = webapp_dir / "app.css"
    css_path.write_text(
        css_path.read_text(encoding="utf-8").replace(
            "background: #ffffff; color: #1a1a1a;",
            "background: #ff0000; color: #1a1a1a;",
        ),
        encoding="utf-8",
    )

    replay_mod.replay(cfg, project_root)
    ledger_ = ledger.load(ledger_path)
    entry = next(e for e in ledger_.findings.values() if e.rule == "visual.changed")
    assert entry.sev == "P2"
    assert entry.state == "open"
    assert entry.evidence

    # evidence is run-relative (like every other finding's evidence path), and lands inside a
    # fresh `.flow-review/runs/<run_id>/` folder this replay minted -- never next to the
    # baseline under recordings/, which stays persistent (A-32).
    runs_root = project_root / ".flow-review" / "runs"
    run_dirs = [d for d in runs_root.iterdir() if d.is_dir()] if runs_root.is_dir() else []
    assert len(run_dirs) == 1, "the first two (no-diff) replays must never create a run folder"
    this_run_dir = run_dirs[0]
    for crop in entry.evidence:
        assert not crop.startswith("/") and ".." not in crop.split("/")
        assert (this_run_dir / crop).exists()
    assert not (project_root / ".flow-review" / "recordings" / "webapp" / "home.diff").exists()

    # --update-baselines accepts the change and files nothing more
    replay_mod.replay(cfg, project_root, update_baselines=True)
    ledger_ = ledger.load(ledger_path)
    entry2 = ledger_.findings[entry.id]
    assert entry2.state == "fixed"
