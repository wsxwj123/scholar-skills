#!/usr/bin/env python3
"""Apply a scope-locked revision patch against an anchored draft (fail-closed).

Reads a block manifest produced by anchorize_draft.py and a patch file listing
{anchor_id, expected_hash, new_content} entries. For each patch entry it:
  1. locates the target block by anchor_id;
  2. verifies the block's current sha256 equals the patch's expected_hash;
  3. if any check fails, REJECTS the whole patch set and writes nothing
     (fail-closed: a mismatched hash means the block already changed).
Only when every patch entry passes does it replace the targeted blocks and
reassemble the full draft. Reassembly splices patched byte-spans into the original
source text and copies every other byte verbatim, so untouched blocks, blank-line
separators, and the document's trailing-newline state are preserved byte-for-byte.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from common import read_json, write_text


def block_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def validate_patches(manifest: dict, patches: list[dict]) -> tuple[list[str], dict[str, dict]]:
    """Return (errors, anchor->patch map). Empty errors => safe to apply."""
    errors: list[str] = []
    blocks_by_anchor = {b["anchor_id"]: b for b in manifest.get("blocks", [])}

    if not isinstance(patches, list):
        return ["patch file must be a JSON array of patch entries"], {}

    patch_map: dict[str, dict] = {}
    for index, patch in enumerate(patches):
        if not isinstance(patch, dict):
            errors.append(f"patch[{index}] is not an object")
            continue
        anchor_id = patch.get("anchor_id")
        expected_hash = patch.get("expected_hash")
        new_content = patch.get("new_content")
        if not anchor_id:
            errors.append(f"patch[{index}] missing anchor_id")
            continue
        if not expected_hash:
            errors.append(f"patch[{index}] ({anchor_id}) missing expected_hash")
            continue
        if new_content is None:
            errors.append(f"patch[{index}] ({anchor_id}) missing new_content")
            continue
        if anchor_id in patch_map:
            errors.append(f"patch[{index}] duplicate anchor_id {anchor_id}")
            continue
        target = blocks_by_anchor.get(anchor_id)
        if target is None:
            errors.append(f"anchor_id {anchor_id} not found in manifest")
            continue
        current_hash = target.get("sha256")
        if current_hash != expected_hash:
            errors.append(
                f"HASH MISMATCH for {anchor_id}: manifest sha256={current_hash} "
                f"!= patch expected_hash={expected_hash} (block changed; patch rejected)"
            )
            continue
        patch_map[anchor_id] = patch
    return errors, patch_map


def load_source(manifest: dict) -> tuple[str, str | None]:
    """Re-read the original source draft and verify it against the manifest hash."""
    source_path = Path(manifest.get("source_draft", ""))
    if not source_path.exists():
        return "", f"source draft missing: {source_path}"
    text = source_path.read_text(encoding="utf-8")
    if block_hash(text) != manifest.get("source_sha256"):
        return "", (
            "source draft changed since anchorize "
            f"(sha256 {block_hash(text)} != manifest {manifest.get('source_sha256')})"
        )
    return text, None


def reassemble(manifest: dict, source_text: str, patch_map: dict[str, dict]) -> tuple[str, list[str]]:
    """Splice patched spans into source_text; copy all other bytes verbatim."""
    blocks = sorted(manifest.get("blocks", []), key=lambda b: b["char_start"])
    out: list[str] = []
    changed: list[str] = []
    cursor = 0
    for block in blocks:
        start, end = block["char_start"], block["char_end"]
        out.append(source_text[cursor:start])  # verbatim gap (separators)
        if block["anchor_id"] in patch_map:
            out.append(patch_map[block["anchor_id"]]["new_content"])
            changed.append(block["anchor_id"])
        else:
            out.append(source_text[start:end])  # verbatim block bytes
        cursor = end
    out.append(source_text[cursor:])  # verbatim tail (trailing newline state)
    return "".join(out), changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a fail-closed revision patch to an anchored draft")
    parser.add_argument("--manifest", required=True, help="Block manifest from anchorize_draft.py")
    parser.add_argument("--patch", required=True, help="Patch JSON: array of {anchor_id, expected_hash, new_content}")
    parser.add_argument("--output", required=True, help="Output path for the reassembled draft")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    patch_path = Path(args.patch)
    if not manifest_path.exists():
        print(json.dumps({"ok": False, "error": f"manifest not found: {manifest_path}"}, ensure_ascii=False))
        return 1
    if not patch_path.exists():
        print(json.dumps({"ok": False, "error": f"patch not found: {patch_path}"}, ensure_ascii=False))
        return 1

    manifest = read_json(manifest_path, {})
    patches = read_json(patch_path, [])

    errors, patch_map = validate_patches(manifest, patches)
    if errors:
        # fail-closed: write nothing, report every reason.
        print(json.dumps({"ok": False, "rejected": True, "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    if not patch_map:
        print(json.dumps({"ok": False, "error": "no applicable patch entries"}, ensure_ascii=False))
        return 1

    source_text, source_error = load_source(manifest)
    if source_error:
        # fail-closed: the anchored source itself drifted.
        print(json.dumps({"ok": False, "rejected": True, "errors": [source_error]}, ensure_ascii=False, indent=2))
        return 1

    reassembled, changed = reassemble(manifest, source_text, patch_map)
    output_path = Path(args.output)
    write_text(output_path, reassembled)

    untouched = [b["anchor_id"] for b in manifest.get("blocks", []) if b["anchor_id"] not in patch_map]
    print(
        json.dumps(
            {
                "ok": True,
                "output": str(output_path.resolve()),
                "blocks_changed": changed,
                "blocks_unchanged": untouched,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
