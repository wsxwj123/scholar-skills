> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

## Patch 修订协议（可选的确定性修订路径）
This is an **optional, additive** deterministic path for applying scope-locked edits. It does not replace the `atomize -> issue-matrix -> revise_units -> strict_gate` flow. Use it when you need a hard guarantee that only the touched blocks can change and every other block stays byte-for-byte identical, rather than having the model regenerate whole sections (the main source of scope creep and drift).

Protocol (four phases):
1. **anchorize**: split the target draft into blank-line blocks, assign each a stable anchor id (`block-NNNN-<hash8>`), and write a block manifest (anchor -> exact original bytes + sha256 + byte offsets):
   ```bash
   python scripts/anchorize_draft.py --draft <draft.md> --manifest <project_root>/block_manifest.json
   ```
2. **patch**: for each reviewer comment that needs a block changed, author a patch entry `{anchor_id, expected_hash, new_content}` where `expected_hash` is the block's `sha256` from the manifest. Patch only the blocks that must change; never touch other anchors. The patch file is a JSON array of such entries.
3. **apply (deterministic, fail-closed)**: locate each block by anchor id, verify its current sha256 equals the patch's `expected_hash`, then splice only the patched byte-spans:
   ```bash
   python scripts/apply_revision_patch.py --manifest <block_manifest.json> --patch <patch.json> --output <revised.md>
   ```
   If **any** entry's hash does not match (the block already changed) or the source draft drifted since anchorize, the whole patch set is **rejected**, nothing is written, and the script exits non-zero. There is no silent partial apply.
4. **finalizer**: `apply_revision_patch.py` reassembles the full draft from the original source, copying every unpatched byte verbatim (blocks, separators, and trailing-newline state preserved). Feed `<revised.md>` back into the normal `polish -> literature/reference checks -> strict_gate` flow before delivery.

Rules:
- The patch path is **fail-closed**: a hash mismatch or source drift must abort and write nothing; never coerce or auto-relocate a patch onto a changed block.
- The patch path is an increment on top of the existing pipeline, not a replacement: `atomize_comments.py`, `build_issue_matrix.py`, the state-window protocol, and `strict_gate.py` all still apply to the resulting draft.
