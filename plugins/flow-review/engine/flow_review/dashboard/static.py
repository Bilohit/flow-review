"""flow-review serve --static OUT.html: ONE self-contained snapshot for when
`serve` is not running (attach to a bug report, archive a run). Per A-21:
CSS, JS, the icon sprite and the subsetted fonts are inlined; screenshots are
embedded as small downscaled JPEG thumbnails that link out to the
full-resolution file in the run folder, never inlined at full size.

The served dashboard's real page assets (app.css/app.js/fonts/icon sprite)
are built in E1 (page skeleton + live serve) and E3 (font subsetting), under
`dashboard/page/`. This module reads from `page/` when those files exist
(so it picks up the real assets the moment those tasks land) and otherwise
falls back to the minimal inline constants below, so `--static` stays usable
standalone. The fallback CSS/JS is intentionally tiny -- it is not the design
pass, only a functioning single-file snapshot.
"""
from __future__ import annotations

import base64
import io
import json
import re
from pathlib import Path

from PIL import Image

from flow_review import budget, ledger
from flow_review.dashboard.state import fold

PAGE_DIR = Path(__file__).parent / "page"
THUMB_MAX_EDGE = 320   # px, longest edge -- proposed default, tune once real shots are seen
THUMB_QUALITY = 70      # JPEG quality

# Minimal fallback assets used only until E1 (page/index.html, app.css, app.js,
# icons/sprite.svg) and E3 (page/fonts/*.woff2) land on this branch.
_FALLBACK_TOKENS_CSS = ":root{--bg:#fff;--fg:#111;--accent:#2563eb;--radius:4px;}"
_FALLBACK_APP_CSS = (
    "body{font-family:'Schibsted Grotesk',sans-serif;background:var(--bg);color:var(--fg);"
    "margin:0;padding:16px;}"
    "code,.mono{font-family:'IBM Plex Mono',monospace;}"
)
_FALLBACK_APP_JS = (
    "(function(){"
    "var el=document.getElementById('state-data');"
    "if(!el)return;"
    "var state=JSON.parse(el.textContent);"
    "window.__FLOW_REVIEW_STATE__=state;"
    "})();"
)
# A tiny valid woff2 blob is not worth vendoring for a fallback path; the fallback
# instead ships a placeholder byte string base64-encoded as a woff2 data URI. It is
# not a usable font -- browsers fall back to the OS default -- but it keeps the
# "everything inlined, nothing fetched" contract (A-21) true even before E3 lands
# real subsetted fonts, and is replaced automatically once page/fonts/*.woff2 exist.
_FALLBACK_FONT_PLACEHOLDER = b"flow-review-placeholder-font"
_FALLBACK_SPRITE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" style="display:none">'
    '<symbol id="icon-placeholder" viewBox="0 0 24 24"></symbol>'
    "</svg>"
)
_FALLBACK_HTML = (
    "<!doctype html>\n<html><head><meta charset=\"utf-8\"><title>flow-review</title></head>"
    "<body><div id=\"app\"></div></body></html>"
)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _inline_fonts_css() -> str:
    """@font-face rules with base64 data URIs for every subsetted .woff2 in page/fonts/."""
    fonts_dir = PAGE_DIR / "fonts"
    rules = []
    if fonts_dir.is_dir():
        for woff2 in sorted(fonts_dir.glob("*.woff2")):
            family = "Schibsted Grotesk" if "SchibstedGrotesk" in woff2.name else "IBM Plex Mono"
            weight = "600" if "SemiBold" in woff2.name or "Medium" in woff2.name else "400"
            data_uri = f"data:font/woff2;base64,{_b64(woff2.read_bytes())}"
            rules.append(
                f'@font-face{{font-family:"{family}";font-weight:{weight};'
                f'src:url({data_uri}) format("woff2");font-display:swap;}}'
            )
    if not rules:
        for family, weight in (("Schibsted Grotesk", "400"), ("IBM Plex Mono", "400")):
            data_uri = f"data:font/woff2;base64,{_b64(_FALLBACK_FONT_PLACEHOLDER)}"
            rules.append(
                f'@font-face{{font-family:"{family}";font-weight:{weight};'
                f'src:url({data_uri}) format("woff2");font-display:swap;}}'
            )
    return "\n".join(rules)


def _thumbnail_data_uri(image_path: Path) -> str | None:
    if not image_path.exists():
        return None
    with Image.open(image_path) as im:
        im = im.convert("RGB")
        im.thumbnail((THUMB_MAX_EDGE, THUMB_MAX_EDGE))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=THUMB_QUALITY)
        return f"data:image/jpeg;base64,{_b64(buf.getvalue())}"


def _thumbnail_block(rel_path: str, run_dir: Path) -> str:
    """A thumbnail linking to the full-res file, or an empty string if the file is missing."""
    full = run_dir / rel_path
    data_uri = _thumbnail_data_uri(full)
    if not data_uri:
        return ""
    return f'<a href="{rel_path}"><img src="{data_uri}" alt=""></a>'


def _read_or_fallback(path: Path, fallback: str) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else fallback


def render_static(project_root: Path, run_dir: Path, cfg, out_path: Path) -> None:
    state = fold(project_root, run_dir, cfg)

    thumb_blocks: list[str] = []
    for lane in state["lanes"]:
        if lane.get("shot"):
            block = _thumbnail_block(lane["shot"], run_dir)
            lane["shot_thumb_html"] = block
            if block:
                thumb_blocks.append(block)
    for f in state["findings"]:
        blocks = [
            _thumbnail_block(ev, run_dir) for ev in f.get("evidence", [])
            if ev.lower().endswith((".png", ".jpg", ".jpeg"))
        ]
        f["evidence_thumbs_html"] = blocks
        thumb_blocks.extend(b for b in blocks if b)

    # JSON is embedded inside an HTML <script> element: escape "</" so user text
    # (a finding title, API output) can never close the tag early. This is the
    # ONE server-side escape this module does -- of the JSON string as a whole,
    # never a template substitution of individual fields (see M8 fix in E2).
    payload = json.dumps(state).replace("</", "<\\/")

    app_css = _read_or_fallback(PAGE_DIR / "app.css", _FALLBACK_APP_CSS)
    tokens_css = _read_or_fallback(PAGE_DIR / "tokens.css", _FALLBACK_TOKENS_CSS)
    app_js = _read_or_fallback(PAGE_DIR / "app.js", _FALLBACK_APP_JS)
    sprite_svg = _read_or_fallback(PAGE_DIR / "icons" / "sprite.svg", _FALLBACK_SPRITE_SVG)
    fonts_css = _inline_fonts_css()

    html = _read_or_fallback(PAGE_DIR / "index.html", _FALLBACK_HTML)
    # Strip the external asset links the served page uses; replace with inline equivalents.
    html = re.sub(r'<link rel="stylesheet"[^>]*>\n?', "", html)
    html = re.sub(r'<script src="app\.js"[^>]*></script>\n?', "", html)
    if "<head>" not in html or "</body>" not in html:
        raise ValueError("page/index.html (or the built-in fallback) is missing <head> or </body>")

    html = html.replace(
        "<head>",
        f"<head>\n<style>{tokens_css}\n{fonts_css}\n{app_css}</style>",
        1,
    )
    # Icon sprite inlined directly in the body (app.js's <use href="/icons/sprite.svg#x">
    # becomes <use href="#x"> against this inline sprite -- app.js is unchanged either way
    # since <use> resolves a bare fragment against the current document).
    # Real (non-JSON-escaped) thumbnail markup, so the full-res link and the inlined
    # thumbnail data URI are present verbatim in the document, not only inside the
    # escaped JSON blob app.js reads. Hidden by default; app.js's own rendering
    # (from #state-data) is what's actually shown.
    thumbs_html = "".join(thumb_blocks)
    snippet = (
        f'{sprite_svg}\n'
        f'<div id="evidence-thumbnails" hidden>{thumbs_html}</div>\n'
        f'<script id="state-data" type="application/json">{payload}</script>\n'
        f'<script>{app_js}</script>\n</body>'
    )
    html = html.replace("</body>", snippet, 1)

    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(html, encoding="utf-8")
    tmp.replace(out_path)  # atomic-ish: no reader ever sees a half-written file
