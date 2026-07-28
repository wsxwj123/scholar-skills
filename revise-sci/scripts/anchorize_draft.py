#!/usr/bin/env python3
"""Anchorize a manuscript draft into stable, content-hashed blocks.

Splits a draft (markdown or plain text) into blocks on blank-line boundaries,
assigns each block a stable anchor id (ordinal + content-hash prefix), and emits
a block manifest mapping anchor -> exact original bytes + sha256. The manifest is
the precondition store for deterministic, scope-locked patch application later via
apply_revision_patch.py.

Block bytes are preserved verbatim (no normalization) so downstream byte-level
diffing can prove that untouched blocks are unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from common import write_json


BLOCK_SEPARATOR_RE = re.compile(r"\n[ \t]*\n")


def block_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def split_blocks(text: str) -> list[tuple[int, int]]:
    """Return (start, end) byte-offset spans of non-blank blocks in the source.

    Splitting on offsets (not strings) lets apply_revision_patch.py splice patched
    spans while copying every other byte verbatim, so separators and the document's
    trailing-newline state are preserved exactly.
    """
    spans: list[tuple[int, int]] = []
    cursor = 0
    for match in BLOCK_SEPARATOR_RE.finditer(text):
        spans.append((cursor, match.start()))
        cursor = match.end()
    spans.append((cursor, len(text)))
    return [(start, end) for start, end in spans if text[start:end].strip()]


def anchorize(text: str) -> list[dict]:
    blocks: list[dict] = []
    for ordinal, (start, end) in enumerate(split_blocks(text), start=1):
        content = text[start:end]
        digest = block_hash(content)
        blocks.append(
            {
                "anchor_id": f"block-{ordinal:04d}-{digest[:8]}",
                "ordinal": ordinal,
                "sha256": digest,
                "char_start": start,
                "char_end": end,
                "original_text": content,
            }
        )
    return blocks


def main() -> int:
    parser = argparse.ArgumentParser(description="Anchorize a draft into content-hashed blocks")
    parser.add_argument("--draft", required=True, help="Path to the draft markdown/text file to anchorize")
    parser.add_argument("--manifest", required=True, help="Output path for the block manifest JSON")
    args = parser.parse_args()

    draft_path = Path(args.draft)
    if not draft_path.exists():
        print(json.dumps({"ok": False, "error": f"draft not found: {draft_path}"}, ensure_ascii=False))
        return 1

    text = draft_path.read_text(encoding="utf-8")
    blocks = anchorize(text)
    if not blocks:
        print(json.dumps({"ok": False, "error": "no non-empty blocks found in draft"}, ensure_ascii=False))
        return 1

    manifest = {
        "source_draft": str(draft_path.resolve()),
        "source_sha256": block_hash(text),
        "block_count": len(blocks),
        "blocks": blocks,
    }
    manifest_path = Path(args.manifest)
    write_json(manifest_path, manifest)

    print(
        json.dumps(
            {"ok": True, "manifest": str(manifest_path.resolve()), "block_count": len(blocks)},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
