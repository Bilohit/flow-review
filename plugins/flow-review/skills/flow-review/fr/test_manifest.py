from __future__ import annotations

import pytest

from fr import manifest


def test_hash_ignores_line_ending_differences():
    assert manifest.manifest_hash("a\nb\n") == manifest.manifest_hash("a\r\nb\r\n")


def test_untouched_file_is_not_human_edited(tmp_path):
    path = tmp_path / "flows.md"
    path.write_text("# flows\n", encoding="utf-8")
    recorded = manifest.manifest_hash(path.read_text(encoding="utf-8"))
    assert manifest.is_human_edited(path, recorded) is False


def test_a_hand_edit_is_detected(tmp_path):
    path = tmp_path / "flows.md"
    path.write_text("# flows\n", encoding="utf-8")
    recorded = manifest.manifest_hash(path.read_text(encoding="utf-8"))
    path.write_text("# flows\n\n- my own note\n", encoding="utf-8")
    assert manifest.is_human_edited(path, recorded) is True


def test_learnings_rewrite_in_place_when_untouched(tmp_path):
    path = tmp_path / "flows.md"
    path.write_text("# flows\n", encoding="utf-8")
    recorded = manifest.manifest_hash(path.read_text(encoding="utf-8"))
    new_hash = manifest.apply_learnings(path, recorded, ["f01 resolved to /settings"])
    text = path.read_text(encoding="utf-8")
    assert "f01 resolved to /settings" in text
    assert manifest.ANNOTATION_HEADER not in text
    assert new_hash == manifest.manifest_hash(text)


def test_learnings_never_overwrite_a_human_edit(tmp_path):
    path = tmp_path / "flows.md"
    path.write_text("# flows\n", encoding="utf-8")
    recorded = manifest.manifest_hash(path.read_text(encoding="utf-8"))
    path.write_text("# flows\n\n- my own note\n", encoding="utf-8")
    manifest.apply_learnings(path, recorded, ["f01 resolved to /settings"])
    text = path.read_text(encoding="utf-8")
    assert "- my own note" in text, "the human's text must survive verbatim"
    assert manifest.ANNOTATION_HEADER in text
    assert "f01 resolved to /settings" in text


def test_no_learnings_leaves_the_file_byte_identical(tmp_path):
    path = tmp_path / "flows.md"
    path.write_text("# flows\n", encoding="utf-8")
    before = path.read_bytes()
    manifest.apply_learnings(path, manifest.manifest_hash("# flows\n"), [])
    assert path.read_bytes() == before


def test_no_learnings_never_transfers_ownership_of_a_human_edited_file(tmp_path):
    # Fix 2: a no-op run must not silently mark a human-owned file tool-owned by returning
    # the hash of text the tool never wrote.
    path = tmp_path / "flows.md"
    path.write_text("# flows\n", encoding="utf-8")
    recorded = manifest.manifest_hash(path.read_text(encoding="utf-8"))
    path.write_text("# flows\n\n- my own note\n", encoding="utf-8")

    result = manifest.apply_learnings(path, recorded, [])

    assert result == recorded
    assert manifest.is_human_edited(path, result) is True


def test_missing_file_is_not_human_edited(tmp_path):
    # Fix 3: a first run with no flows.md yet must not raise -- there is nothing to protect.
    path = tmp_path / "flows.md"
    assert manifest.is_human_edited(path, "") is False


def test_annotation_block_replaced_in_place_when_human_text_follows(tmp_path):
    # Fix 1 (the critical one): a prior annotation block, with the human's own reaction typed
    # in below it -- the natural place to react -- must survive. Only the block itself is
    # replaced; every byte above and below it stays byte-identical.
    path = tmp_path / "flows.md"
    path.write_text("# flows\n", encoding="utf-8")
    recorded = manifest.manifest_hash(path.read_text(encoding="utf-8"))
    path.write_text(
        "# flows\n\n- my own note\n\n"
        f"{manifest.ANNOTATION_HEADER}\n- old learning\n{manifest.ANNOTATION_FOOTER}\n\n"
        "- my reaction below\n",
        encoding="utf-8",
    )

    manifest.apply_learnings(path, recorded, ["f02 resolved to /export"])
    text = path.read_text(encoding="utf-8")

    assert text.startswith("# flows\n\n- my own note\n\n")
    assert text.endswith("- my reaction below\n"), "text below the block must survive"
    assert "old learning" not in text
    assert "f02 resolved to /export" in text
    assert text.count(manifest.ANNOTATION_HEADER) == 1, "the block is replaced, not accumulated"


def test_malformed_block_without_footer_is_treated_as_human_content(tmp_path):
    # Fix 1's guard: a header with no matching footer must not be truncated on a guess of
    # where it ends. It is left alone and a fresh, well-formed block is appended.
    path = tmp_path / "flows.md"
    path.write_text("# flows\n", encoding="utf-8")
    recorded = manifest.manifest_hash(path.read_text(encoding="utf-8"))
    before = f"# flows\n\n{manifest.ANNOTATION_HEADER}\n- half written\n"
    path.write_text(before, encoding="utf-8")

    manifest.apply_learnings(path, recorded, ["f03 resolved to /home"])
    text = path.read_text(encoding="utf-8")

    assert before in text, "the malformed block must not be discarded"
    assert "f03 resolved to /home" in text
    assert text.count(manifest.ANNOTATION_HEADER) == 2


def test_a_second_run_after_a_malformed_block_still_keeps_every_human_byte(tmp_path):
    """The regression that mattered most: three pieces of a human's file were destroyed here.

    A file left holding an orphan header pairs that header with the tool's real footer far
    below it on the NEXT run, and a header-through-footer splice then swallows everything in
    between -- the human's own rows included. Appending is always safe; splicing the wrong
    span is not. A single call could never see this, which is why it shipped.
    """
    path = tmp_path / "flows.md"
    path.write_text(
        "# flows\n\n"
        + manifest.ANNOTATION_HEADER
        + "\n- an old note the human kept\n\n- MY OWN ROW\n",
        encoding="utf-8",
    )

    first = manifest.apply_learnings(path, "a-hash-that-does-not-match", ["learning one"])
    after_first = path.read_text(encoding="utf-8")
    assert "MY OWN ROW" in after_first

    path.write_text(
        after_first.replace(
            "- an old note the human kept",
            "- an old note the human kept\n- HUMAN REACTION",
        ),
        encoding="utf-8",
    )

    manifest.apply_learnings(path, first, ["learning two"])
    final = path.read_text(encoding="utf-8")
    for survivor in ("an old note the human kept", "HUMAN REACTION", "MY OWN ROW"):
        assert survivor in final, f"{survivor!r} was destroyed on the second run"
    assert "learning two" in final
    assert "learning one" not in final, "the tool's own block should be replaced, not stacked"


def test_the_tools_own_block_is_replaced_rather_than_accumulated(tmp_path):
    path = tmp_path / "flows.md"
    path.write_text("# flows\n\n- my row\n", encoding="utf-8")
    first = manifest.apply_learnings(path, "not-the-tools-hash", ["one"])
    manifest.apply_learnings(path, first + "-diverged", ["two"])
    text = path.read_text(encoding="utf-8")
    assert text.count(manifest.ANNOTATION_HEADER) == 1, "the block must not grow every run"
    assert text.count(manifest.ANNOTATION_FOOTER) == 1
    assert "- my row" in text
    assert "two" in text and "one" not in text


def test_a_learning_carrying_a_sentinel_is_refused(tmp_path):
    """A marker inside the block makes the block's own boundary ambiguous on the next run."""
    path = tmp_path / "flows.md"
    path.write_text("# flows\n", encoding="utf-8")
    before = path.read_bytes()
    recorded = manifest.manifest_hash("# flows\n")
    for bad in (manifest.ANNOTATION_HEADER, manifest.ANNOTATION_FOOTER):
        with pytest.raises(ValueError, match="annotation header or footer"):
            manifest.apply_learnings(path, recorded, [f"x {bad} y"])
    assert path.read_bytes() == before, "a refused call must not have written anything"
