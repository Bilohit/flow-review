"""flow-review serve --static OUT.html: ONE self-contained snapshot for when
`serve` is not running (attach to a bug report, archive a run). Per A-21:
CSS, JS, the icon sprite and the subsetted fonts are inlined; screenshots are
embedded as small downscaled JPEG thumbnails that link out to the
full-resolution file in the run folder, never inlined at full size.

The served dashboard's real page assets (app.css/app.js/fonts/icon sprite)
live under `dashboard/page/` (E1 page skeleton + live serve, E3 font
subsetting, E4 the built page) and are always present alongside this module
in the repo, so this reads them directly -- no placeholder fallback.
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


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _inline_fonts_css() -> str:
    """@font-face rules with base64 data URIs for every subsetted .woff2 in page/fonts/."""
    fonts_dir = PAGE_DIR / "fonts"
    rules = []
    for woff2 in sorted(fonts_dir.glob("*.woff2")):
        family = "Schibsted Grotesk" if "SchibstedGrotesk" in woff2.name else "IBM Plex Mono"
        weight = "600" if "SemiBold" in woff2.name or "Medium" in woff2.name else "400"
        data_uri = f"data:font/woff2;base64,{_b64(woff2.read_bytes())}"
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

    app_css = (PAGE_DIR / "app.css").read_text(encoding="utf-8")
    tokens_css = (PAGE_DIR / "tokens.css").read_text(encoding="utf-8")
    app_js = (PAGE_DIR / "app.js").read_text(encoding="utf-8")
    sprite_svg = (PAGE_DIR / "icons" / "sprite.svg").read_text(encoding="utf-8")
    fonts_css = _inline_fonts_css()

    html = (PAGE_DIR / "index.html").read_text(encoding="utf-8")
    # Strip the external asset links the served page uses; replace with inline equivalents.
    html = re.sub(r'<link rel="stylesheet"[^>]*>\n?', "", html)
    html = re.sub(r'<script src="app\.js"[^>]*></script>\n?', "", html)
    if "<head>" not in html or "</body>" not in html:
        raise ValueError("page/index.html is missing <head> or </body>")

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
