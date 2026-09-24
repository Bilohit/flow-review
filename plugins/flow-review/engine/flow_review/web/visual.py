from pathlib import Path
from typing import TypedDict

from PIL import Image, ImageChops

DEFAULT_THRESHOLD = 0.02
DEFAULT_PIXEL_DELTA = 24
DEFAULT_MAX_EDGE = 768
_GRID = 32


class DiffResult(TypedDict):
    changed: bool
    diff_ratio: float
    regions: list[dict]


def diff(baseline_path: Path, current_path: Path,
          threshold: float = DEFAULT_THRESHOLD,
          pixel_delta: int = DEFAULT_PIXEL_DELTA) -> DiffResult:
    with Image.open(baseline_path) as base_img, Image.open(current_path) as cur_img:
        base_img = base_img.convert("RGB")
        cur_img = cur_img.convert("RGB")
        if cur_img.size != base_img.size:
            cur_img = cur_img.resize(base_img.size)
        width, height = base_img.size
        raw_diff = ImageChops.difference(base_img, cur_img)
        r, g, b = raw_diff.split()
        combined = ImageChops.lighter(ImageChops.lighter(r, g), b)
        mask = combined.point(lambda p: 255 if p > pixel_delta else 0)
        histogram = mask.histogram()
        changed_count = histogram[255]
        total = width * height
        diff_ratio = changed_count / total if total else 0.0
        regions = _find_regions(mask, width, height)
    return {
        "changed": diff_ratio > threshold,
        "diff_ratio": diff_ratio,
        "regions": regions,
    }


def _find_regions(mask: Image.Image, width: int, height: int) -> list[dict]:
    dirty_cells = set()
    for cy in range(0, height, _GRID):
        for cx in range(0, width, _GRID):
            box = (cx, cy, min(cx + _GRID, width), min(cy + _GRID, height))
            if mask.crop(box).getbbox() is not None:
                dirty_cells.add((cx // _GRID, cy // _GRID))
    if not dirty_cells:
        return []
    visited: set = set()
    regions: list[dict] = []
    for cell in sorted(dirty_cells):
        if cell in visited:
            continue
        component = _flood_fill(cell, dirty_cells, visited)
        min_cx = min(c[0] for c in component) * _GRID
        min_cy = min(c[1] for c in component) * _GRID
        max_cx = min((max(c[0] for c in component) + 1) * _GRID, width)
        max_cy = min((max(c[1] for c in component) + 1) * _GRID, height)
        block = mask.crop((min_cx, min_cy, max_cx, max_cy))
        bbox = block.getbbox()
        if bbox is None:
            continue
        bx0, by0, bx1, by1 = bbox
        regions.append({
            "x": min_cx + bx0,
            "y": min_cy + by0,
            "w": bx1 - bx0,
            "h": by1 - by0,
        })
    return regions


def _flood_fill(start, dirty_cells, visited):
    stack = [start]
    component = []
    while stack:
        cell = stack.pop()
        if cell in visited or cell not in dirty_cells:
            continue
        visited.add(cell)
        component.append(cell)
        cx, cy = cell
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            neighbor = (cx + dx, cy + dy)
            if neighbor in dirty_cells and neighbor not in visited:
                stack.append(neighbor)
    return component


def crop_regions(image_path: Path, regions: list[dict], out_dir: Path,
                  max_edge: int = DEFAULT_MAX_EDGE) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        width, height = img.size
        for i, region in enumerate(regions):
            pad = 8
            x0 = max(region["x"] - pad, 0)
            y0 = max(region["y"] - pad, 0)
            x1 = min(region["x"] + region["w"] + pad, width)
            y1 = min(region["y"] + region["h"] + pad, height)
            crop = img.crop((x0, y0, x1, y1))
            crop.thumbnail((max_edge, max_edge))
            out_path = out_dir / f"region_{i}.png"
            crop.save(out_path)
            paths.append(out_path)
    return paths
