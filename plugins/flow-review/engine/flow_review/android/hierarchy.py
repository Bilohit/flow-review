import re
import xml.etree.ElementTree as ET

from flow_review.locators import LocatorNotFound
from flow_review.web.measure import Finding

_BOUNDS = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")
_IGNORED_RID = re.compile(r"dev-menu|dev_launcher|devmenu")
MIN_DP = 48
_ROLE_CLASS = {"textbox": "EditText", "checkbox": "CheckBox", "switch": "Switch"}


def parse(xml: str) -> list[dict]:
    start = min((i for i in (xml.find("<hierarchy"), xml.find("<?xml")) if i >= 0), default=0)
    end = xml.rfind("</hierarchy>")
    root = ET.fromstring(xml[start:end + len("</hierarchy>")] if end >= 0 else xml[start:])
    nodes: list[dict] = []

    def walk(el, depth):
        for child in el:
            if child.tag != "node":
                continue
            a = child.attrib
            m = _BOUNDS.fullmatch(a.get("bounds", ""))
            nodes.append({
                "cls": a.get("class", ""), "text": a.get("text", ""),
                "desc": a.get("content-desc", ""), "rid": a.get("resource-id", ""),
                "pkg": a.get("package", ""),
                "bounds": tuple(int(g) for g in m.groups()) if m else (0, 0, 0, 0),
                "clickable": a.get("clickable") == "true", "focusable": a.get("focusable") == "true",
                "scrollable": a.get("scrollable") == "true", "password": a.get("password") == "true",
                "enabled": a.get("enabled") != "false", "depth": depth,
                "index": int(a.get("index", 0) or 0),
            })
            walk(child, depth + 1)

    walk(root, 0)
    return nodes


def interactive(node: dict) -> bool:
    return node["clickable"] or (node["focusable"] and bool(node["desc"]) and not node["scrollable"])


def _area(node: dict) -> int:
    x1, y1, x2, y2 = node["bounds"]
    return max(0, x2 - x1) * max(0, y2 - y1)


def _label(node: dict) -> str:
    return "" if node["password"] else (node["text"] or node["desc"])


def _app_nodes(nodes: list[dict], app_id: str | None) -> list[dict]:
    return [n for n in nodes
            if (app_id is None or n["pkg"] == app_id) and not _IGNORED_RID.search(n["rid"])
            and _area(n) > 0]


def _role_ok(node: dict, role: str) -> bool:
    if role == "button":
        return "Button" in node["cls"] or node["clickable"]
    cls = _ROLE_CLASS.get(role)
    return cls is None or cls in node["cls"]


def _by_name(cands: list[dict], name: str) -> dict | None:
    for fold in (False, True):
        for f in ("text", "desc"):
            for n in cands:
                v = n[f]
                if v and (v.casefold() == name.casefold() if fold else v == name):
                    return n
    return None


def resolve(nodes: list[dict], locator: dict) -> dict:
    nodes = [n for n in nodes if _area(n) > 0]
    found = None
    if "testid" in locator:
        t = locator["testid"]
        found = next((n for n in nodes if n["rid"] and (n["rid"] == t or n["rid"].endswith(f":id/{t}"))), None)
    elif "name" in locator and "role" in locator:
        found = _by_name([n for n in nodes if interactive(n) and _role_ok(n, locator["role"])],
                         locator["name"])
    elif "text" in locator:
        found = _by_name([n for n in nodes if n["text"] or n["desc"]], locator["text"])
    if found is None:
        raise _not_found(nodes, locator)
    return found


def _not_found(nodes: list[dict], locator: dict) -> LocatorNotFound:
    vis = [n for n in nodes if _area(n) > 0]
    pkgs = list(dict.fromkeys(n["pkg"] for n in vis if n["pkg"]))
    labels = [lb for lb in dict.fromkeys(_label(n) for n in vis) if lb][:10]
    err = LocatorNotFound(locator)
    err.args = (f"could not resolve locator: {locator!r}; foreground package(s): "
                f"{', '.join(pkgs) or 'none'}; visible: {labels!r}",)
    return err


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def screen_route(nodes: list[dict], app_id: str, screen_h: int) -> str:
    top = sorted((n for n in _app_nodes(nodes, app_id)
                  if _slug(_label(n)) and n["bounds"][1] < screen_h * 0.2),
                 # a title is text; icon buttons in the same bar carry only a content-desc
                 key=lambda n: (not n["text"], n["bounds"][1], n["bounds"][0]))
    return _slug(_label(top[0])) if top else "app"


def _role(node: dict) -> str:
    for role, cls in _ROLE_CLASS.items():
        if cls in node["cls"]:
            return role
    return "button" if interactive(node) else "text"


def outline(nodes: list[dict], app_id: str) -> str:
    lines, controls = [], []
    for n in _app_nodes(nodes, app_id):
        label = _label(n)
        role = _role(n)
        if role == "text":
            # a control's own caption repeats its name: drop it, the outline is a token budget
            if not n["text"] or any(name == n["text"] and _contains(b, n["bounds"])
                                    for name, b in controls):
                continue
        elif not label and not n["password"]:
            continue
        else:
            controls.append((label, n["bounds"]))
        lines.append(f'- {role} "{label or n["desc"]}"' + (" [password]" if n["password"] else ""))
    return "\n".join(lines)


def _locator(n: dict) -> dict | None:
    if n["rid"]:
        return {"testid": n["rid"].rsplit(":id/", 1)[-1]}
    name = n["desc"] or n["text"]
    return {"role": "button", "name": name} if name else None


def _name(n: dict) -> str:
    return n["rid"].rsplit(":id/", 1)[-1] or n["desc"] or n["text"] or n["cls"]


def _contains(a: tuple, b: tuple) -> bool:
    return a[0] <= b[0] and a[1] <= b[1] and a[2] >= b[2] and a[3] >= b[3]


def _intersects(a: tuple, b: tuple) -> bool:
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def check(nodes: list[dict], route: str, density: float, app_id: str,
          screen_wh: tuple[int, int]) -> list[Finding]:
    scale = density / 160.0
    items = [n for n in _app_nodes(nodes, app_id) if interactive(n)]
    findings: list[Finding] = []
    for n in items:
        x1, y1, x2, y2 = n["bounds"]
        w, hh = (x2 - x1) / scale, (y2 - y1) / scale
        if w < MIN_DP or hh < MIN_DP:
            findings.append(Finding(
                rule="rect.target-size", sev="P2", locator=_locator(n), route=route,
                text=f"{_name(n)} is {w:.0f}x{hh:.0f}dp, below the {MIN_DP}x{MIN_DP}dp minimum",
                evidence=[f"w={w:.0f}dp", f"h={hh:.0f}dp"], disposition="engine"))
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            ba, bb = a["bounds"], b["bounds"]
            if _intersects(ba, bb) and not _contains(ba, bb) and not _contains(bb, ba):
                findings.append(Finding(
                    rule="rect.overlap", sev="P1", locator=_locator(a), route=route,
                    text=f"{_name(a)} overlaps {_name(b)}",
                    evidence=[f"{_name(a)}={list(ba)}", f"{_name(b)}={list(bb)}"],
                    disposition="engine"))
    sw, sh = screen_wh
    screen = (0, 0, sw, sh)
    for n in items:
        b = n["bounds"]
        if _intersects(b, screen) and not _contains(screen, b):
            findings.append(Finding(
                rule="rect.offscreen", sev="P2", locator=_locator(n), route=route,
                text=f"{_name(n)} extends outside the {sw}x{sh} screen",
                evidence=[f"bounds={list(b)}", f"screen={sw}x{sh}"], disposition="engine"))
    return findings
