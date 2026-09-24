import json
import math
import re
from pathlib import Path
from typing import TypedDict


class Finding(TypedDict):
    rule: str
    sev: str
    locator: dict | None
    route: str | None
    text: str
    evidence: list[str]
    disposition: str


# ---------- CIEDE2000 (Sharma, Wu, Dalal 2005) ----------

def ciede2000(lab1: tuple[float, float, float], lab2: tuple[float, float, float]) -> float:
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2

    C1 = math.hypot(a1, b1)
    C2 = math.hypot(a2, b2)
    Cbar = (C1 + C2) / 2.0

    G = 0.5 * (1 - math.sqrt(Cbar ** 7 / (Cbar ** 7 + 25.0 ** 7)))
    a1p = (1 + G) * a1
    a2p = (1 + G) * a2

    C1p = math.hypot(a1p, b1)
    C2p = math.hypot(a2p, b2)

    def _hue(ap: float, b: float) -> float:
        if ap == 0 and b == 0:
            return 0.0
        h = math.degrees(math.atan2(b, ap))
        return h + 360.0 if h < 0 else h

    h1p = _hue(a1p, b1)
    h2p = _hue(a2p, b2)

    dLp = L2 - L1
    dCp = C2p - C1p

    if C1p * C2p == 0:
        dhp = 0.0
    else:
        dh = h2p - h1p
        if dh > 180.0:
            dh -= 360.0
        elif dh < -180.0:
            dh += 360.0
        dhp = dh
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp) / 2.0)

    Lbarp = (L1 + L2) / 2.0
    Cbarp = (C1p + C2p) / 2.0

    if C1p * C2p == 0:
        hbarp = h1p + h2p
    elif abs(h1p - h2p) > 180.0:
        hbarp = (h1p + h2p + 360.0) / 2.0 if h1p + h2p < 360.0 else (h1p + h2p - 360.0) / 2.0
    else:
        hbarp = (h1p + h2p) / 2.0

    T = (
        1
        - 0.17 * math.cos(math.radians(hbarp - 30))
        + 0.24 * math.cos(math.radians(2 * hbarp))
        + 0.32 * math.cos(math.radians(3 * hbarp + 6))
        - 0.20 * math.cos(math.radians(4 * hbarp - 63))
    )

    d_theta = 30 * math.exp(-(((hbarp - 275) / 25) ** 2))
    Rc = 2 * math.sqrt(Cbarp ** 7 / (Cbarp ** 7 + 25.0 ** 7))
    Sl = 1 + (0.015 * (Lbarp - 50) ** 2) / math.sqrt(20 + (Lbarp - 50) ** 2)
    Sc = 1 + 0.045 * Cbarp
    Sh = 1 + 0.015 * Cbarp * T
    Rt = -math.sin(math.radians(2 * d_theta)) * Rc

    term_L = dLp / Sl
    term_C = dCp / Sc
    term_H = dHp / Sh
    return math.sqrt(term_L ** 2 + term_C ** 2 + term_H ** 2 + Rt * term_C * term_H)


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def normalize_hex(hex_color: str) -> str:
    h = hex_color.lstrip("#").lower()
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return "#" + h


def hex_to_lab(hex_color: str) -> tuple[float, float, float]:
    h = normalize_hex(hex_color).lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    r, g, b = _srgb_to_linear(r), _srgb_to_linear(g), _srgb_to_linear(b)
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041
    xn, yn, zn = 0.95047, 1.0, 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > (6 / 29) ** 3 else t / (3 * (6 / 29) ** 2) + 4 / 29

    fx, fy, fz = f(x / xn), f(y / yn), f(z / zn)
    L = 116 * fy - 16
    a = 500 * (fx - fy)
    b_ = 200 * (fy - fz)
    return (L, a, b_)


# ---------- contrast.aa ----------

def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    def chan(c: int) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def contrast_ratio(fg_rgb: tuple[int, int, int], bg_rgb: tuple[int, int, int]) -> float:
    l1 = _relative_luminance(fg_rgb)
    l2 = _relative_luminance(bg_rgb)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def check_contrast_pair(fg: tuple[int, int, int], bg: tuple[int, int, int], large_text: bool,
                         locator: dict, route: str) -> list[Finding]:
    ratio = contrast_ratio(fg, bg)
    threshold = 3.0 if large_text else 4.5
    if ratio >= threshold:
        return []
    return [Finding(
        rule="contrast.aa", sev="P1", locator=locator, route=route,
        text=f"text contrast {ratio:.2f}:1 is below WCAG AA {threshold}:1",
        evidence=[f"ratio={ratio:.2f}", f"required={threshold}"],
        disposition="engine",
    )]


_RGB_RE = re.compile(r"rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)")


def _css_color_to_rgb(css: str) -> tuple[int, int, int] | None:
    m = _RGB_RE.match(css or "")
    if not m:
        return None
    r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
    a = float(m.group(4)) if m.group(4) is not None else 1.0
    return None if a == 0 else (r, g, b)


# ---------- token.color ----------

def check_tokens(computed: dict[str, str], tokens: dict[str, str],
                  locator: dict, route: str) -> list[Finding]:
    findings: list[Finding] = []
    token_hexes = {name: normalize_hex(v) for name, v in tokens.items()}
    for prop, raw in computed.items():
        norm = normalize_hex(raw)
        if norm in token_hexes.values():
            continue
        lab_c = hex_to_lab(norm)
        best_name, best_de = None, float("inf")
        for name, thex in token_hexes.items():
            de = ciede2000(lab_c, hex_to_lab(thex))
            if de < best_de:
                best_de, best_name = de, name
        if best_de < 3:
            findings.append(Finding(
                rule="token.color", sev="P2", locator=locator, route=route,
                text=f"{prop} {norm} is close to token {best_name} ({token_hexes[best_name]}) "
                     f"but not exact (ΔE={best_de:.2f})",
                evidence=[f"computed={norm}", f"nearest_token={best_name}"],
                disposition="engine",
            ))
        else:
            findings.append(Finding(
                rule="token.color", sev="P2", locator=locator, route=route,
                text=f"{prop} {norm} does not match any design token (off-palette)",
                evidence=[f"computed={norm}"],
                disposition="engine",
            ))
    return findings


# ---------- rect.overlap / rect.target-size ----------

def _overlaps(a: dict, b: dict) -> bool:
    ax2, ay2 = a["x"] + a["w"], a["y"] + a["h"]
    bx2, by2 = b["x"] + b["w"], b["y"] + b["h"]
    return a["x"] < bx2 and ax2 > b["x"] and a["y"] < by2 and ay2 > b["y"]


def _locator_str(locator: dict) -> str:
    return locator.get("css") or locator.get("testid") or locator.get("role", "?")


def check_rects(rects: list[dict], route: str) -> list[Finding]:
    findings: list[Finding] = []
    for r in rects:
        if r["w"] < 24 or r["h"] < 24:
            findings.append(Finding(
                rule="rect.target-size", sev="P2", locator=r["locator"], route=route,
                text=f"{_locator_str(r['locator'])} is {r['w']}x{r['h']}px, below the 24x24 minimum",
                evidence=[f"w={r['w']}", f"h={r['h']}"], disposition="engine",
            ))
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            a, b = rects[i], rects[j]
            if _overlaps(a, b):
                findings.append(Finding(
                    rule="rect.overlap", sev="P1", locator=a["locator"], route=route,
                    text=f"{_locator_str(a['locator'])} overlaps {_locator_str(b['locator'])}",
                    evidence=[json.dumps(a), json.dumps(b)], disposition="engine",
                ))
    return findings


# ---------- http.5xx ----------

def check_http_status(network_log: list[dict], route: str) -> list[Finding]:
    findings: list[Finding] = []
    for entry in network_log:
        if entry["status"] >= 500:
            findings.append(Finding(
                rule="http.5xx", sev="P0", locator=None, route=route,
                text=f"{entry['method']} {entry['url']} returned {entry['status']}",
                evidence=[json.dumps(entry)], disposition="engine",
            ))
    return findings


# ---------- console.error ----------

def check_console(console_errors: list[dict], route: str) -> list[Finding]:
    findings: list[Finding] = []
    for entry in console_errors:
        in_step = entry.get("step_index") is not None
        findings.append(Finding(
            rule="console.error", sev="P1" if in_step else "P2", locator=None, route=route,
            text=entry["text"], evidence=[json.dumps(entry)], disposition="engine",
        ))
    return findings


# ---------- check_page: the one aggregate ----------

_PAGE_SCAN_JS = """
() => {
  function locatorFor(el, index) {
    if (el.dataset && el.dataset.testid) {
      return {testid: el.dataset.testid};
    }
    if (el.id) {
      return {css: '#' + el.id};
    }
    return {css: el.tagName.toLowerCase() + ':nth-of-type(' + (index + 1) + ')'};
  }

  function isVisible(el) {
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return false;
    const style = getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none') return false;
    if (parseFloat(style.opacity) === 0) return false;
    return true;
  }

  const INTERACTIVE_TAGS = new Set(['BUTTON', 'A', 'INPUT', 'SELECT', 'TEXTAREA']);
  const text = [];
  const interactive = [];
  let textIndex = 0;
  let interactiveIndex = 0;

  document.querySelectorAll('body *').forEach((el) => {
    if (!isVisible(el)) return;
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);

    const hasOwnText = Array.from(el.childNodes).some(
      (n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim().length > 0
    );
    if (hasOwnText) {
      text.push({
        locator: locatorFor(el, textIndex++),
        color: style.color,
        backgroundColor: style.backgroundColor,
        fontSize: parseFloat(style.fontSize),
        fontWeight: style.fontWeight,
      });
    }

    const isInteractive = INTERACTIVE_TAGS.has(el.tagName)
      || el.hasAttribute('role')
      || el.hasAttribute('tabindex');
    if (isInteractive) {
      interactive.push({
        locator: locatorFor(el, interactiveIndex++),
        rect: {x: rect.x, y: rect.y, w: rect.width, h: rect.height},
        color: style.color,
        backgroundColor: style.backgroundColor,
      });
    }
  });

  return {text: text, interactive: interactive};
}
"""


def _rgb_to_hex(css: str | None) -> str | None:
    rgb = _css_color_to_rgb(css)
    if rgb is None:
        return None
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def check_page(driver, surface_id: str, flow_id: str, route: str,
                tokens: dict[str, str] | None, step_index: int | None) -> list[dict]:
    from flow_review.web import actionlog

    scan = driver.page.evaluate(_PAGE_SCAN_JS)
    findings: list[Finding] = []

    for item in scan["text"]:
        fg = _css_color_to_rgb(item["color"])
        bg = _css_color_to_rgb(item["backgroundColor"])
        if fg is None or bg is None:
            continue
        large = item["fontSize"] >= 24 or (
            item["fontSize"] >= 18.66 and item["fontWeight"] in ("bold", "700", "800", "900")
        )
        findings.extend(check_contrast_pair(fg, bg, large, item["locator"], route))

    rects = [
        {"locator": item["locator"], "x": item["rect"]["x"], "y": item["rect"]["y"],
         "w": item["rect"]["w"], "h": item["rect"]["h"]}
        for item in scan["interactive"]
    ]
    findings.extend(check_rects(rects, route))

    if tokens is not None:
        for item in scan["text"] + scan["interactive"]:
            computed: dict[str, str] = {}
            fg_hex = _rgb_to_hex(item.get("color"))
            if fg_hex:
                computed["color"] = fg_hex
            bg_hex = _rgb_to_hex(item.get("backgroundColor"))
            if bg_hex:
                computed["background-color"] = bg_hex
            if computed:
                findings.extend(check_tokens(computed, tokens, item["locator"], route))

    findings.extend(check_http_status(driver.network_log_since_check(), route))
    findings.extend(check_console(driver.console_errors_since_check(), route))

    payloads: list[dict] = []
    for f in findings:
        loc = f["locator"]
        payloads.append({
            "surface_id": surface_id,
            "flow_id": flow_id,
            "rule": f["rule"],
            "route": route,
            "locator": actionlog.locator_key(loc) if loc else "",
            "sev": f["sev"],
            "text": f["text"],
            "evidence": f["evidence"],
            "disposition": "engine",
        })
    return payloads


# ---------- load_tokens (A-25) ----------

_CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_CSS_VAR = re.compile(r"(--[\w-]+)\s*:\s*([^;{}]+)")
_COLORISH = re.compile(r"^(#[0-9a-fA-F]{3,8}$|rgba?\(|hsla?\()")


def load_tokens(path: Path) -> dict[str, str]:
    """Color design tokens as {name: css color}.

    .css/.scss: color custom properties (`--brand: #1a56db`). .json: a flat map or W3C design
    tokens (`$value`), nested keys joined with dots. Non-color values are dropped, never guessed.
    """
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".css", ".scss"):
        pairs = ((name, value.strip()) for name, value in _CSS_VAR.findall(_CSS_COMMENT.sub("", text)))
    elif path.suffix == ".json":
        pairs = _walk_json_tokens(json.loads(text), "")
    else:
        raise ValueError(f"tokens_file must be .css, .scss or .json, got {path.name!r}")
    return {name: value for name, value in pairs if _COLORISH.match(value)}


def _walk_json_tokens(node, prefix: str):
    if isinstance(node, dict):
        if isinstance(node.get("$value"), str):
            yield prefix, node["$value"].strip()
            return
        for key, value in node.items():
            if not key.startswith("$"):
                yield from _walk_json_tokens(value, f"{prefix}.{key}" if prefix else key)
    elif isinstance(node, str):
        yield prefix, node.strip()
