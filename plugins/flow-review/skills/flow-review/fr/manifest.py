"""Ownership discipline for the flows manifest, which is a human's document.

The rule this file enforces:

    BINDING -- Never overwrite the flows manifest when a human has edited it.
    Applies even when the run learned something that corrects a row; append an annotation instead.
    The previous version rewrote the file unconditionally at run end, which destroys hand-written
    flow notes the first time someone edits between runs.
    why: council ruling 2026-08-22, spec section 8.5

The mechanism is a lockfile-style hash: the config records what the tool last wrote. If the file
still hashes to that, the tool wrote it last and may rewrite. If not, the human owns it.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ANNOTATION_HEADER = "<!-- flow-review learnings -->"
ANNOTATION_FOOTER = "<!-- /flow-review learnings -->"

# ponytail: this module assumes the annotation block is the only machine-written region of
# the file -- replacing header-through-footer is safe only because nothing else the tool
# writes lives outside that span. A second machine-writer (a different section, a different
# tool) would need its own header/footer pair rather than sharing this one; add that only
# once a second producer actually exists.


def manifest_hash(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def is_human_edited(path: Path, recorded_hash: str) -> bool:
    path = Path(path)
    if not path.exists():
        # No file yet is not "a human changed it out from under us" -- there is nothing to
        # protect on a first run, and the tool may create it.
        return False
    current = path.read_text(encoding="utf-8")
    return manifest_hash(current) != recorded_hash


def _find_own_block(existing: str) -> tuple[int, int] | None:
    """Locate the tool's own annotation block, searching from the END of the file.

    The invariant this relies on: the tool only ever APPENDS a block, so its own block is the
    last well-formed header/footer pair in the file. Searching forward from the first header
    instead is what made this unsafe -- an orphan header left in human text by an earlier
    malformed state would pair with the tool's real footer far below it, and the splice would
    swallow every byte in between, human text included. That was observed destroying three
    separate pieces of a human's file, which is the exact failure this module exists to prevent.

    A pair with another header between its own header and footer is not a block; nothing is
    matched rather than guessing which header owns the footer.
    """
    footer_index = existing.rfind(ANNOTATION_FOOTER)
    if footer_index == -1:
        return None
    header_index = existing.rfind(ANNOTATION_HEADER, 0, footer_index)
    if header_index == -1:
        return None
    inner = existing.find(ANNOTATION_HEADER, header_index + len(ANNOTATION_HEADER), footer_index)
    if inner != -1:
        return None
    return header_index, footer_index + len(ANNOTATION_FOOTER)


def _replace_annotation_block(existing: str, body: str) -> str:
    """Insert or replace the tool's annotation block in human-owned text.

    The tool's own block is replaced precisely, leaving every byte above and below untouched.
    Anything that is not unambiguously the tool's own block is treated as human content and
    left alone; a fresh block is appended below it rather than guessing where a damaged one
    ended. Appending is always safe. Splicing the wrong span is not, so ambiguity resolves to
    appending, every time.
    """
    block = f"{ANNOTATION_HEADER}\n{body}\n{ANNOTATION_FOOTER}"

    found = _find_own_block(existing)
    if found is not None:
        start, end = found
        return existing[:start] + block + existing[end:]

    return f"{existing.rstrip(chr(10))}\n\n{block}\n"


def apply_learnings(path: Path, recorded_hash: str, learnings: list[str]) -> str:
    if not learnings:
        # A no-op run must never transfer ownership: return the recorded hash unchanged,
        # before reading or writing anything, so a human-owned file stays human-owned.
        return recorded_hash

    for line in learnings:
        if ANNOTATION_HEADER in line or ANNOTATION_FOOTER in line:
            # A learning carrying a sentinel would put a second marker inside the block and
            # make the block's own boundary ambiguous on the next run. Refuse it here, where
            # the caller can see why, rather than write a file that cannot be parsed back.
            raise ValueError(
                "a learning may not contain the annotation header or footer: " f"{line!r}"
            )

    path = Path(path)
    text = path.read_text(encoding="utf-8")
    body = "\n".join(f"- {line}" for line in learnings)

    if is_human_edited(path, recorded_hash):
        # The human owns this file. Their bytes survive; ours arrive as a clearly marked block
        # they can accept, edit or delete.
        new_text = _replace_annotation_block(text, body)
    else:
        new_text = f"{text.rstrip(chr(10))}\n\n{body}\n"

    path.write_text(new_text, encoding="utf-8")
    return manifest_hash(new_text)
