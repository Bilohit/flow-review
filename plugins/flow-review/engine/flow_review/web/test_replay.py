import json
from types import SimpleNamespace

import pytest
pytest.importorskip("playwright")

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

    result_path = log_path.with_name(log_path.name + ".result.json")
    assert result_path.exists()
    data = json.loads(result_path.read_text())
    assert any(f["rule"] == "http.5xx" for f in data["findings"])
    assert not (project_root / ".flow-review" / "findings.json").exists()
    assert not (project_root / ".flow-review" / "divergences.json").exists()



def test_replay_one_resolves_from_env_fill_and_registers_secret(monkeypatch):
    from flow_review import events
    monkeypatch.setenv("RP_PW", "Rp9secretvalue")
    log = actionlog.new_log("webapp", "login")
    actionlog.record_step(log, "fill", locator={"css": "#pw", "secret": True}, from_env="RP_PW")
    filled = []
    drv = _FakeDriver()
    drv.fill = lambda loc, v: filled.append(v)
    result = replay_mod.replay_one(drv, log)
    assert result["status"] == "clean"
    assert filled == ["Rp9secretvalue"]
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
