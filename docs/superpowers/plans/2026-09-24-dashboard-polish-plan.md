# Dashboard Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Each task names its executor model; dispatch it pinned to that model, never `inherit`.

**Goal:** Fix the six visual defects found in the E5 screenshots of the flow-review M1 dashboard, within the existing (unsigned-off) direction.

**Architecture:** All changes live in `plugins/flow-review/engine/flow_review/dashboard/`: static page assets (`page/`), the live server (`serve.py`) and the screenshot fixture (`conftest.py`). The page is vanilla JS that builds DOM from the `/state` JSON; `static.py` embeds the same assets into one offline HTML file.

**Tech Stack:** Python 3.14 stdlib `http.server`, vanilla JS/CSS, pytest 9.1 + Playwright 1.63 (chromium).

**Council verdict (2026-09-24):** fix all six. #2 (grey band) and #5 (no thumbnails) share a cause. #5 needs no engine work: `state.py` already folds `shot` events into `lane.shot`, and `app.js` already renders it. What's missing is a server route for run-folder files, plus seeded fixture data.

## Global Constraints

- No subheadings (`h2`–`h6`) and no descriptions (`p`) anywhere in the UI; icons and titles are self-explanatory; hover/focus tooltips double as accessible names.
- Progressive disclosure; one findings badge.
- Schibsted Grotesk (`var(--font-ui)`) for UI text; IBM Plex Mono (`var(--font-mono)`) for numbers and logs only.
- Cool neutrals, hairline borders, `var(--radius)` = 4px, one blue accent (`var(--accent)`). Every colour is a `var(--token)` from `tokens.css`; no new hex values.
- Light/dark follow the OS, with a toggle. Motion uses `var(--motion-*)` tokens, which zero under `prefers-reduced-motion`.
- Never use `innerHTML`: build the DOM with `createElement`/`textContent`/`setAttribute`.
- No external network requests.
- The server binds `127.0.0.1` only. It never serves a file outside its root; resolve the path, then check containment.
- Secrets never reach the page (events are already redacted by `events.append`).
- TDD: write the failing test, run it and see it fail for the stated reason, implement, run it and see it pass, commit.
- Test command, from the repo root: `rtk proxy python -m pytest -q -m "web or not web" plugins/flow-review/engine/flow_review/dashboard`. Baseline: dashboard suite green.
- The full suite has 2 known environment failures in `test_prove.py` (the A8 1s snapshot window vs a slow PowerShell CIM call). They're logged for the final review; ignore them.

## File Structure

```text
plugins/flow-review/engine/flow_review/dashboard/
  page/app.css          layout, fonts and header styles (T1, T2)
  page/index.html       header markup: budget = text + bar (T2)
  page/app.js           renderHeader (T2); _assetUrl for shots/evidence (T3)
  page/icons/sprite.svg severity-dot becomes a filled circle (T1)
  serve.py              GET /run/<rel>: images from run_dir only (T3)
  conftest.py           seeds a real PNG shot per lane; supports 8 lanes (T3)
  test_polish.py        NEW: browser tests for T1-T3
  test_serve.py         /run route tests (T3)
  test_screenshots.py   adds 8-lane scenarios + FR_SHOTS_DIR output (T3)
```

## Task Skeleton

| id | goal | deps | exec | review |
|---|---|---|---|---|
| T1 | #2 lanes stop stretching, #3 UI font on report text, #4 filled severity dot | — | haiku | controller |
| T2 | #1 budget shows `used/cap` text + a solid bar, #6 header dots get status tooltips | T1 | haiku | controller |
| T3 | #5 thumbnails: `/run/` route, `_assetUrl`, seeded shots, 8-lane screenshots | T2 | sonnet | Sonnet reviewer (serve security) |
| T4 | Controller: capture light/dark × 1/4/8 lanes + the static report; show the user | T3 | controller | user |

T1 and T2 touch the same files, and T3 depends on the header markup being settled, so the tasks run in order. Running them in parallel would only produce merge conflicts.

---

### Task T1: Lanes size to content, UI font on report text, filled severity dot

**Executor:** haiku

**Files:**
- Modify: `plugins/flow-review/engine/flow_review/dashboard/page/app.css`
- Modify: `plugins/flow-review/engine/flow_review/dashboard/page/icons/sprite.svg` (symbol `severity-dot`)
- Create: `plugins/flow-review/engine/flow_review/dashboard/test_polish.py`

**Interfaces:**
- Consumes: the `dashboard_server` fixture (`conftest.py`), which yields an object with `.url`; the seeded run is finished, so the report is visible.
- Produces: `test_polish.py` with a module-level `page` fixture that T2 and T3 append tests to.

- [ ] **Step 1: Write the failing tests.** Create `test_polish.py`:

```python
"""Dashboard polish (2026-09-24 plan): browser checks for the six screenshot defects."""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright

PAGE = Path(__file__).parent / "page"


@pytest.fixture
def page(dashboard_server):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page()
        pg.goto(dashboard_server.url)
        pg.wait_for_selector('[data-role="lanes"] .lane')
        yield pg
        browser.close()


@pytest.mark.web
def test_lanes_region_ends_at_its_last_lane(page):
    gap = page.evaluate("""() => {
        const lanes = document.querySelector('[data-role="lanes"]');
        const last = lanes.querySelector('.lane:last-child');
        return lanes.getBoundingClientRect().bottom - last.getBoundingClientRect().bottom;
    }""")
    assert gap <= 2, f"lanes region stretches {gap}px past its content (grey band)"


@pytest.mark.web
def test_report_group_labels_use_the_ui_font(page):
    family = page.evaluate(
        "() => getComputedStyle(document.querySelector('[data-role=\"report\"] summary')).fontFamily")
    assert "Schibsted" in family, family


def test_severity_dot_symbol_is_a_filled_circle():
    svg = (PAGE / "icons" / "sprite.svg").read_text(encoding="utf-8")
    start = svg.index('<symbol id="severity-dot"')
    symbol = svg[start:svg.index("</symbol>", start)]
    assert "<circle" in symbol and 'fill="currentColor"' in symbol
    assert "<path" not in symbol, "the Phosphor ring path renders hollow"
```

- [ ] **Step 2: Run; expected FAIL.** Run `rtk proxy python -m pytest -q -m "web or not web" plugins/flow-review/engine/flow_review/dashboard/test_polish.py`. Expected: 3 failed, with `grey band`, a font-family without `Schibsted`, and `<circle` missing.

- [ ] **Step 3: Implement.**

In `app.css`, replace the `.lanes{ ... }` block:

```css
.lanes{
  flex:0 1 auto;          /* size to content; shrink and scroll only when the lanes overflow */
  min-height:0;
  overflow-y:auto;
  display:grid;
  grid-template-columns:repeat(auto-fit, minmax(280px, 1fr));
  gap:1px;
  background:var(--border);
  align-content:start;
}
```

In `app.css`, replace these two lines:

```css
.report summary{ cursor:pointer; color:var(--text-2); }
.not-exercised-row{ color:var(--text-2); padding:var(--space-1) 0; }
```

In `app.css`, replace the `.finding-row svg` line:

```css
.finding-row svg{ width:12px; height:12px; flex:none; }
```

In `page/icons/sprite.svg`, replace the whole `severity-dot` symbol:

```xml
  <symbol id="severity-dot" viewBox="0 0 256 256">
    <circle cx="128" cy="128" r="104" fill="currentColor"/>
  </symbol>
```

- [ ] **Step 4: Run; expected PASS.** Run the Step 2 command: 3 passed. Then run the dashboard suite command from Global Constraints. It must be all green; the existing E4 scroll-preservation test still passes because `.lanes` still scrolls when it overflows.

- [ ] **Step 5: Commit.**

```bash
git add plugins/flow-review/engine/flow_review/dashboard/page/app.css plugins/flow-review/engine/flow_review/dashboard/page/icons/sprite.svg plugins/flow-review/engine/flow_review/dashboard/test_polish.py
git commit -m "fix(dashboard): lanes size to content, UI font on report labels, filled severity dot"
```

---

### Task T2: Readable budget, self-explanatory header dots

**Executor:** haiku · **Depends:** T1

**Files:**
- Modify: `plugins/flow-review/engine/flow_review/dashboard/page/index.html` (the budget element)
- Modify: `plugins/flow-review/engine/flow_review/dashboard/page/app.js` (`renderHeader`)
- Modify: `plugins/flow-review/engine/flow_review/dashboard/page/app.css` (add `.budget`)
- Modify: `plugins/flow-review/engine/flow_review/dashboard/test_polish.py` (append)

**Interfaces:**
- Consumes: the `page` fixture from T1. The seeded state has `budget.cap_tokens = 200000` and `header.surface_dots = [{surface_id, status}, ...]`.
- Produces: header markup `[data-role="budget"]` (wrapper, carries the tooltip) > `[data-role="budget-text"]` + `[data-role="budget-meter"]`. The existing test that `[data-role="budget"]` exists once still holds.

- [ ] **Step 1: Write the failing tests.** Append to `test_polish.py`:

```python
@pytest.mark.web
def test_budget_shows_used_over_cap_as_text_beside_a_bar(page):
    text = page.locator('[data-role="budget-text"]').inner_text()
    assert text.replace(",", "").count("/") == 1 and text.split("/")[1].strip() == "200000", text
    meter = page.locator('[data-role="budget-meter"]')
    assert meter.inner_text() == ""
    assert page.locator('[data-role="budget"]').get_attribute("title").endswith("tokens used")


@pytest.mark.web
def test_header_dots_name_their_surface_and_status(page):
    dots = page.locator('[data-role="surface-dots"] .dot')
    assert dots.count() >= 1
    for i in range(dots.count()):
        d = dots.nth(i)
        title = d.get_attribute("title")
        assert title.startswith("surface-") and ": " in title, title
        assert d.get_attribute("aria-label") == title
        assert d.get_attribute("role") == "img"
```

- [ ] **Step 2: Run; expected FAIL.** Run `rtk proxy python -m pytest -q -m "web or not web" plugins/flow-review/engine/flow_review/dashboard/test_polish.py -k "budget or header_dots"`. Expected: 2 failed. The first times out on the missing `budget-text`; the second fails on the title having no `": "`.

- [ ] **Step 3: Implement.**

In `index.html`, replace `<div class="meter" data-role="budget"></div>` with:

```html
    <div class="budget" data-role="budget"><span class="stat" data-role="budget-text"></span><span class="meter" data-role="budget-meter"></span></div>
```

In `app.js` `renderHeader`, replace the block from `const budgetEl = ...` through the `--pct` line with:

```js
  const budgetEl = document.querySelector('[data-role="budget"]');
  const cap = s.budget.cap_tokens;
  const used = s.budget.used_tokens;
  document.querySelector('[data-role="budget-text"]').textContent = cap ? `${used}/${cap}` : String(used);
  budgetEl.title = cap ? `${used} of ${cap} tokens used` : `${used} tokens used`;
  document.querySelector('[data-role="budget-meter"]').style.setProperty(
    '--pct', cap ? String(Math.min(1, used / cap) * 100) : '0');
```

In `app.js` `renderHeader`, replace `dot.title = d.surface_id;` with:

```js
    const label = `${d.surface_id}: ${d.status}`;
    dot.title = label;
    dot.setAttribute('role', 'img');
    dot.setAttribute('aria-label', label);
```

In `app.css`, add this line directly above the `.meter{` line:

```css
.budget{ display:flex; align-items:center; gap:var(--space-2); }
```

- [ ] **Step 4: Run; expected PASS.** Run the Step 2 command: 2 passed. Then run the dashboard suite command: all green. If `test_page_structure.py`/`test_rule_lint.py` assumed the old markup, update only the selector they use (never remove an assertion) and say so in the report.

- [ ] **Step 5: Commit.**

```bash
git add plugins/flow-review/engine/flow_review/dashboard/page/index.html plugins/flow-review/engine/flow_review/dashboard/page/app.js plugins/flow-review/engine/flow_review/dashboard/page/app.css plugins/flow-review/engine/flow_review/dashboard/test_polish.py
git commit -m "fix(dashboard): budget text beside a solid bar, header dots name surface and status"
```

---

### Task T3: Lane thumbnails load in the live dashboard

**Executor:** sonnet · **Depends:** T2

**Files:**
- Modify: `plugins/flow-review/engine/flow_review/dashboard/serve.py` (`do_GET`)
- Modify: `plugins/flow-review/engine/flow_review/dashboard/page/app.js` (add `_assetUrl`; use it for `lane.shot` and every `finding.evidence` image `src`)
- Modify: `plugins/flow-review/engine/flow_review/dashboard/conftest.py` (seed shots; 8 lanes)
- Modify: `plugins/flow-review/engine/flow_review/dashboard/test_serve.py`, `test_polish.py`, `test_screenshots.py`

**Interfaces:**
- Consumes: `shot` events `{"type": "shot", "surface_id", "shot": "<run_dir-relative path>"}`, already folded by `state.py` into `lane.shot`. `finding.evidence` holds paths relative to the run folder (the same contract `static.py` uses: `run_dir / rel_path`).
- Produces: `GET /run/<rel>` serves `run_dir/<rel>` only when it resolves inside `run_dir` and its guessed MIME type starts with `image/`; everything else returns 404. `_assetUrl(p)` in app.js returns `p` unchanged in static mode (`#state-data` present) and `'run/' + p.split('/').map(encodeURIComponent).join('/')` in live mode.

- [ ] **Step 1: Write the failing tests.**

Append to `test_serve.py` (reuse its existing `_start(tmp_path)` helper, which returns `(server, port)`):

```python
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
```

(`make_server` builds the handler class with `run_dir` as a class attribute, so `server.RequestHandlerClass.run_dir` is the run folder `_start` created.)

Append to `test_polish.py`:

```python
@pytest.mark.web
def test_lane_thumbnail_loads(page):
    img = page.locator('[data-role="lanes"] .lane .shot img').first
    img.wait_for()
    assert page.evaluate("(el) => el.complete && el.naturalWidth > 0", img.element_handle())
```

- [ ] **Step 2: Run; expected FAIL.** Run `rtk proxy python -m pytest -q -m "web or not web" plugins/flow-review/engine/flow_review/dashboard/test_serve.py plugins/flow-review/engine/flow_review/dashboard/test_polish.py -k "run_route or thumbnail"`. Expected: the route test fails with 404 != 200. The thumbnail test fails or times out because no shot is seeded.

- [ ] **Step 3: Implement.**

In `serve.py` `do_GET`, insert before the `rel = parsed.path.lstrip("/")` line (`unquote` comes from `urllib.parse`; add it to the existing import):

```python
        if parsed.path.startswith("/run/"):
            run_root = Path(self.run_dir).resolve()
            candidate = (run_root / unquote(parsed.path[len("/run/"):])).resolve()
            ctype = mimetypes.guess_type(str(candidate))[0] or ""
            if run_root in candidate.parents and candidate.is_file() and ctype.startswith("image/"):
                self._send_file(candidate, ctype)
            else:
                self._send_404()
            return
```

In `app.js`, add near the top, after the first helper functions:

```js
// Live mode serves run-folder files under /run/; the static report inlines them, so paths pass through.
function _assetUrl(p) {
  if (!p || document.getElementById('state-data')) return p || '';
  return 'run/' + p.split('/').map(encodeURIComponent).join('/');
}
```

In `app.js`, replace `img.src = lane.shot;` with `img.src = _assetUrl(lane.shot);`. Replace every `img.src = <evidence path>` in `renderEvidence` the same way, e.g. `img.src = _assetUrl(finding.evidence[0]);` and `img.src = _assetUrl(src);` in the before/after loop. Do not touch the `pre.textContent` line.

In `conftest.py` `_seed_run`, inside the per-surface loop after the `output` event, add:

```python
        shots = run_dir / "shots"
        shots.mkdir(exist_ok=True)
        Image.new("RGB", (640, 400), (200 - 30 * (i % 4), 210, 225)).save(shots / f"{sid}.png")
        events.append(run_dir, {"type": "shot", "surface_id": sid, "shot": f"shots/{sid}.png"})
```

and add `from PIL import Image` to its imports.

In `test_screenshots.py`, set `SCENARIOS = [("light", 1), ("dark", 1), ("light", 4), ("dark", 4), ("light", 8), ("dark", 8)]`. Replace `out = tmp_path / f"{theme}-{lane_count}lane.png"` with:

```python
        import os
        out_dir = Path(os.environ.get("FR_SHOTS_DIR", str(tmp_path)))
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{theme}-{lane_count}lane.png"
```

and add `from pathlib import Path` to its imports.

- [ ] **Step 4: Run; expected PASS.** Run the Step 2 command: all pass. Then run the dashboard suite command: all green. Then run `rtk proxy python -m pytest -q plugins/flow-review/engine/flow_review/dashboard/test_static.py`: the static report still builds, with thumbnails inlined as data URIs.

- [ ] **Step 5: Commit.**

```bash
git add plugins/flow-review/engine/flow_review/dashboard/serve.py plugins/flow-review/engine/flow_review/dashboard/page/app.js plugins/flow-review/engine/flow_review/dashboard/conftest.py plugins/flow-review/engine/flow_review/dashboard/test_serve.py plugins/flow-review/engine/flow_review/dashboard/test_polish.py plugins/flow-review/engine/flow_review/dashboard/test_screenshots.py
git commit -m "feat(dashboard): serve run-folder images under /run/ so lane thumbnails load"
```

---

### Task T4: Screenshots for sign-off (controller)

**Executor:** controller (Opus) · **Depends:** T3

- [ ] **Step 1: Capture.** Run `FR_SHOTS_DIR=.superpowers/sdd/polish-shots rtk proxy python -m pytest -q -m manual plugins/flow-review/engine/flow_review/dashboard/test_screenshots.py`. Expected: 6 passed, and 6 PNGs in `.superpowers/sdd/polish-shots/`.
- [ ] **Step 2: Static report.** Render the static report for a seeded run (reuse `conftest._seed_run` in a scratch script), open it in chromium with the network blocked, and screenshot it. Expected: thumbnails visible and fonts rendered.
- [ ] **Step 3: Check against the six issues.** In each PNG:
  - (1) `used/cap` is readable beside a solid bar
  - (2) no grey band under the lanes
  - (3) report labels are in the UI font
  - (4) severity dots are filled
  - (5) the lanes show thumbnails
  - (6) the header dots have tooltips (verified by the test)
- [ ] **Step 4: Ask the user** (AskUserQuestion) to approve the look or request changes, attaching the PNG paths. Record the answer in the plan's decisions log and the progress ledger.

---

### Task T5: Offline static report shows thumbnails, icons and fonts

**Executor:** sonnet · **Depends:** T3 · Found during T4: `flow-review serve --static` output rendered in chromium with all non-`file:` requests blocked shows thumbnail `naturalWidth == 0` and missing sprite icons.

**Root causes:**
1. `static.py` puts thumbnails in a hidden `#evidence-thumbnails` block and `lane.shot_thumb_html`, but `app.js` renders `lane.shot`/`finding.evidence` paths, which don't exist beside the report file.
2. `app.js` builds `<use href="icons/sprite.svg#id">`, and `index.html` has the same for the theme icons. Offline, the sprite is inlined, so only `#id` resolves.

**Files:**
- Modify: `plugins/flow-review/engine/flow_review/dashboard/static.py`, `page/app.js`, `test_static.py`

**Required behaviour:**
- In `render_static`, replace `lane["shot"]` with its thumbnail data URI (`_thumbnail_data_uri(run_dir / rel)`; set `None` when the file is missing). Replace each image path in `finding["evidence"]` (`.png/.jpg/.jpeg`) with its data URI, and keep non-image evidence as is. Delete `shot_thumb_html`, `evidence_thumbs_html` and the hidden `#evidence-thumbnails` block if no test needs them; if an existing test asserts the full-res `<a href>` link, keep that block and say so. Keep `_thumbnail_block` escaping.
- In `app.js`, add `function _iconHref(id) { return document.getElementById('state-data') ? '#' + id : 'icons/sprite.svg#' + id; }` and use it for every `use.setAttribute('href', ...)`. `_assetUrl` already passes data URIs through in static mode (`!p || static` returns `p`).
- In `static.py`, rewrite `href="icons/sprite.svg#` to `href="#` in the inlined `index.html` markup (plain `str.replace`).
- Fonts: verify with `await document.fonts.ready` before `document.fonts.check`. Fix `_inline_fonts_css` only if the check is still false after `ready`.

**Test (write first, `@pytest.mark.web`, in `test_static.py`):**
- Seed a 4-lane run via `conftest._seed_run`.
- Render with `render_static`.
- Open the file in chromium with `page.route("**/*", lambda r: r.continue_() if r.request.url.startswith("file:") else r.abort())`.
- Wait for `[data-role="lanes"] .lane`.
- Assert every `.lane .shot img` has `naturalWidth > 0`.
- Assert every `.finding-row svg use` has an `href` starting with `#` and that the target symbol exists: `document.querySelector(href)` is not null.
- Assert `await document.fonts.ready; document.fonts.check('16px "Schibsted Grotesk"')` is true.
- Close the browser in `finally`.
- Watch the test fail first.

**Verify:** the dashboard suite command from Global Constraints is all green. Commit: `fix(dashboard): static report inlines thumbnails and resolves icons offline`.
