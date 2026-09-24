from PIL import Image
from flow_review.web import visual


def _save(path, color, size=(100, 100)):
    Image.new("RGB", size, color).save(path)


def test_diff_identical_images_not_changed(tmp_path):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    _save(a, (255, 255, 255))
    _save(b, (255, 255, 255))
    result = visual.diff(a, b)
    assert result["changed"] is False
    assert result["diff_ratio"] == 0.0
    assert result["regions"] == []


def test_diff_flags_changed_region(tmp_path):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    img_a = Image.new("RGB", (100, 100), (255, 255, 255))
    img_a.save(a)
    img_b = img_a.copy()
    for x in range(10, 30):
        for y in range(10, 30):
            img_b.putpixel((x, y), (255, 0, 0))
    img_b.save(b)
    result = visual.diff(a, b)
    assert result["changed"] is True
    assert result["regions"], "expected at least one bounding box"
    r = result["regions"][0]
    assert r["x"] <= 10 and r["y"] <= 10
    assert r["x"] + r["w"] >= 30 and r["y"] + r["h"] >= 30


def test_crop_regions_downscales_to_max_edge(tmp_path):
    img = Image.new("RGB", (1000, 1000), (0, 0, 0))
    src = tmp_path / "src.png"
    img.save(src)
    out_dir = tmp_path / "crops"
    paths = visual.crop_regions(src, [{"x": 0, "y": 0, "w": 800, "h": 800}], out_dir, max_edge=200)
    assert len(paths) == 1
    with Image.open(paths[0]) as cropped:
        assert max(cropped.size) <= 200
