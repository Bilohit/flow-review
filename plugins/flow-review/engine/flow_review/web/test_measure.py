from flow_review.web import measure


def test_ciede2000_matches_sharma_reference_pair():
    # Sharma, Wu, Dalal (2005) test-data table, row 1.
    de = measure.ciede2000((50.0, 2.6772, -79.7751), (50.0, 0.0, -82.7485))
    assert round(de, 4) == 2.0425


def test_contrast_ratio_matches_known_value():
    ratio = measure.contrast_ratio((0x99, 0x99, 0x99), (0xFF, 0xFF, 0xFF))
    assert 2.8 < ratio < 2.9


def test_check_contrast_pair_flags_low_contrast():
    findings = measure.check_contrast_pair(
        fg=(0x99, 0x99, 0x99), bg=(0xFF, 0xFF, 0xFF), large_text=False,
        locator={"css": "#muted-note"}, route="/",
    )
    assert findings and findings[0]["rule"] == "contrast.aa"
    assert findings[0]["sev"] == "P1"
    assert findings[0]["disposition"] == "engine"


def test_check_contrast_pair_passes_large_text_at_3to1():
    findings = measure.check_contrast_pair(
        fg=(0x76, 0x76, 0x76), bg=(0xFF, 0xFF, 0xFF), large_text=True,
        locator={"css": "h1"}, route="/",
    )
    assert findings == []


def test_check_tokens_flags_near_miss_naming_the_token():
    findings = measure.check_tokens(
        computed={"background-color": "#1a57dc"},
        tokens={"color.primary": "#1a56db"},
        locator={"css": "#cta-button"}, route="/",
    )
    assert findings[0]["rule"] == "token.color"
    assert findings[0]["sev"] == "P2"
    assert "color.primary" in findings[0]["text"]


def test_check_tokens_flags_off_palette_when_far():
    findings = measure.check_tokens(
        computed={"background-color": "#00ff00"},
        tokens={"color.primary": "#1a56db"},
        locator={"css": "#x"}, route="/",
    )
    assert "off-palette" in findings[0]["text"]


def test_check_tokens_passes_exact_match():
    findings = measure.check_tokens(
        computed={"background-color": "#1A56DB"},
        tokens={"color.primary": "#1a56db"},
        locator={"css": "#x"}, route="/",
    )
    assert findings == []


def test_check_rects_flags_overlap_and_target_size():
    rects = [
        {"locator": {"css": "#save-button"}, "x": 20, "y": 40, "w": 80, "h": 30},
        {"locator": {"css": "#cancel-button"}, "x": 20, "y": 40, "w": 80, "h": 30},
        {"locator": {"css": "#tiny-icon"}, "x": 200, "y": 200, "w": 16, "h": 16},
    ]
    findings = measure.check_rects(rects, route="/")
    assert any(f["rule"] == "rect.overlap" and f["sev"] == "P1" for f in findings)
    assert any(f["rule"] == "rect.target-size" and f["sev"] == "P2" for f in findings)


def test_check_http_status_flags_5xx():
    findings = measure.check_http_status(
        [{"method": "GET", "url": "/api/fail", "status": 500}], route="/",
    )
    assert findings[0]["rule"] == "http.5xx" and findings[0]["sev"] == "P0"


def test_check_console_severity_follows_step_window():
    findings = measure.check_console(
        [
            {"text": "outside", "location": "", "step_index": None},
            {"text": "inside", "location": "", "step_index": 2},
        ],
        route="/",
    )
    sev_by_text = {f["text"]: f["sev"] for f in findings}
    assert sev_by_text["outside"] == "P2"
    assert sev_by_text["inside"] == "P1"


# ---------- check_page: fake driver, no browser ----------

class _FakePage:
    def __init__(self, scan):
        self._scan = scan

    def evaluate(self, script):
        return self._scan


class _FakeDriver:
    def __init__(self, scan, network=None, console=None):
        self.page = _FakePage(scan)
        self._network = network or []
        self._console = console or []

    def network_log_since_check(self):
        return self._network

    def console_errors_since_check(self):
        return self._console


def test_check_page_aggregates_every_rule_family():
    scan = {
        "text": [
            {"locator": {"css": "#muted-note"}, "color": "rgb(153, 153, 153)",
             "backgroundColor": "rgb(255, 255, 255)", "fontSize": 16.0, "fontWeight": "400"},
        ],
        "interactive": [
            {"locator": {"css": "#save-button"}, "rect": {"x": 20, "y": 40, "w": 80, "h": 30},
             "color": "rgb(0, 0, 0)", "backgroundColor": "rgb(26, 87, 220)"},
            {"locator": {"css": "#cancel-button"}, "rect": {"x": 20, "y": 40, "w": 80, "h": 30},
             "color": "rgb(0, 0, 0)", "backgroundColor": "rgb(255, 255, 255)"},
        ],
    }
    driver = _FakeDriver(
        scan,
        network=[{"method": "GET", "url": "/api/fail", "status": 500}],
        console=[{"text": "boom", "location": "", "step_index": 4}],
    )
    tokens = {"color.primary": "#1a56db"}

    payloads = measure.check_page(driver, "webapp", "login-happy-path", "/", tokens, 4)

    rules = {p["rule"] for p in payloads}
    assert rules == {"contrast.aa", "rect.overlap", "token.color", "http.5xx", "console.error"}
    for p in payloads:
        assert set(p) == {
            "surface_id", "flow_id", "rule", "route", "locator", "sev", "text",
            "evidence", "disposition",
        }
        assert "id" not in p
        assert p["disposition"] == "engine"
        assert p["surface_id"] == "webapp"
        assert p["flow_id"] == "login-happy-path"
        assert isinstance(p["locator"], str)  # canonical string form, never a dict


def test_check_page_skips_token_checks_when_tokens_none():
    scan = {
        "text": [],
        "interactive": [
            {"locator": {"css": "#cta-button"}, "rect": {"x": 0, "y": 0, "w": 40, "h": 40},
             "color": "rgb(255, 255, 255)", "backgroundColor": "rgb(26, 87, 220)"},
        ],
    }
    payloads = measure.check_page(_FakeDriver(scan), "webapp", "flow", "/", None, None)
    assert not any(p["rule"] == "token.color" for p in payloads)


def test_check_page_locator_is_the_canonical_string_key():
    from flow_review.web import actionlog

    scan = {
        "text": [],
        "interactive": [
            {"locator": {"testid": "save-button"}, "rect": {"x": 0, "y": 0, "w": 10, "h": 10},
             "color": "rgb(0, 0, 0)", "backgroundColor": "rgb(255, 255, 255)"},
        ],
    }
    payloads = measure.check_page(_FakeDriver(scan), "webapp", "flow", "/", None, None)
    rect_findings = [p for p in payloads if p["rule"] == "rect.target-size"]
    assert rect_findings
    assert rect_findings[0]["locator"] == actionlog.locator_key({"testid": "save-button"})


def test_check_page_uses_http_and_console_cursors_not_full_history():
    scan = {"text": [], "interactive": []}
    driver = _FakeDriver(scan, network=[], console=[])
    # network_log_since_check()/console_errors_since_check() are the driver's job to filter;
    # check_page must not re-derive "since last call" itself.
    payloads = measure.check_page(driver, "webapp", "flow", "/", None, None)
    assert payloads == []


# ---------- web-marked: fixture end to end ----------

import pytest
pytest.importorskip("playwright")


@pytest.mark.web
def test_check_contrast_catches_fixture_muted_note(webapp_server):
    from flow_review.web.driver import WebDriver

    base_url, _ = webapp_server
    d = WebDriver(headless=True)
    d.launch(base_url)
    d.goto("/")
    findings = measure.check_contrast(d, selector="#muted-note", route="/")
    d.close()
    assert any(f["rule"] == "contrast.aa" for f in findings)


@pytest.mark.web
def test_check_page_catches_fixture_bugs_end_to_end(webapp_server):
    from flow_review.web.driver import WebDriver

    base_url, _ = webapp_server
    d = WebDriver(headless=True)
    d.launch(base_url)
    d.goto("/")
    tokens = {"color.primary": "#1a56db"}
    findings = measure.check_page(d, "webapp", "smoke", "/", tokens, None)
    d.click({"testid": "load-button"})
    findings += measure.check_page(d, "webapp", "smoke", "/", tokens, None)
    d.close()

    rules = {f["rule"] for f in findings}
    assert "contrast.aa" in rules   # #muted-note
    assert "rect.overlap" in rules  # #save-button / #cancel-button
    assert "token.color" in rules   # #cta-button's off-token background
    assert "http.5xx" in rules      # /api/fail via #load-button
    for f in findings:
        assert isinstance(f["locator"], str)
        assert f["disposition"] == "engine"


# ---------- load_tokens (A-25) ----------

def test_load_tokens_reads_css_custom_properties(tmp_path):
    p = tmp_path / "tokens.css"
    p.write_text(":root {\n  --brand: #1a56db; /* --ghost: #000 */\n  --space-2: 8px;\n"
                 "  --ink: rgb(17, 24, 39);\n}\n", encoding="utf-8")
    assert measure.load_tokens(p) == {"--brand": "#1a56db", "--ink": "rgb(17, 24, 39)"}


def test_load_tokens_reads_flat_and_dtcg_json(tmp_path):
    flat = tmp_path / "flat.json"
    flat.write_text('{"color.primary": "#1a56db", "radius": "4px"}', encoding="utf-8")
    assert measure.load_tokens(flat) == {"color.primary": "#1a56db"}
    dtcg = tmp_path / "dtcg.json"
    dtcg.write_text('{"color": {"primary": {"$value": "#1a56db", "$type": "color"},'
                    ' "$description": "brand"}}', encoding="utf-8")
    assert measure.load_tokens(dtcg) == {"color.primary": "#1a56db"}


def test_load_tokens_rejects_an_unknown_extension(tmp_path):
    p = tmp_path / "tokens.yaml"
    p.write_text("a: b", encoding="utf-8")
    with pytest.raises(ValueError):
        measure.load_tokens(p)
