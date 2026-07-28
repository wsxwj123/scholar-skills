#!/usr/bin/env python3
"""Consolidate per-section `## References` blocks into a single global list.

During writing (Phase 3), every section draft carries its own self-contained
`## References` block for verification. When sections are concatenated into
`exports/Final_Review.md` (Phase 4), those per-section blocks must be merged
into ONE global reference list at the end of the document (journal convention).

This script:
  1. Strips every `## References` block from the body.
  2. Collects the global citation numbers [n] actually used in the cleaned body
     (supports [n], [n,m], [n-m] via citation_utils).
  3. Renders Vancouver entries from literature_index.json for the used numbers,
     ordered by ascending global number.
  4. Appends exactly ONE `## References` block with that ordered list.

Idempotent: re-running yields the same result. Citations missing from the index
are warned about on stderr but do not abort the export (exit 0).
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from citation_utils import extract_citation_ids


# A `## References` (or `# References`) heading, case-insensitive.
_REFERENCES_HEADING_RE = re.compile(r"^#{1,6}\s+references\s*$", re.IGNORECASE)
# Any markdown heading line.
_HEADING_RE = re.compile(r"^#{1,6}\s+\S")
# A reference list entry line: `- [12] ...`, `[12] ...`, or `12. ...`.
_REF_ENTRY_RE = re.compile(r"^\s*(?:[-*]\s*)?(?:\[\d+\]|\d+\.)\s")


def strip_reference_blocks(text):
    """Remove every `## References` block from the body.

    A block runs from a `References` heading until the next markdown heading
    (any level) or end of file. Only blank lines and reference-entry lines are
    expected inside; if a non-entry, non-blank, non-heading line is hit, the
    block is closed there to avoid eating real body text.
    """
    # 保留 split('\n')：输出用 "\n".join(out) 重组，splitlines() 会丢弃末尾空元素导致
    # 尾随换行被吃掉（行为变化）。text 来自 open('r') universal newline，本就无 \r 残留。
    lines = text.split("\n")
    out = []
    i = 0
    n = len(lines)
    while i < n:
        if _REFERENCES_HEADING_RE.match(lines[i]):
            # Skip the heading itself.
            i += 1
            # Consume the block body.
            while i < n:
                line = lines[i]
                if _HEADING_RE.match(line):
                    break  # next section starts; stop, do not consume heading
                if line.strip() == "" or _REF_ENTRY_RE.match(line):
                    i += 1
                    continue
                # Unexpected content -> stop stripping here, keep it as body.
                break
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def render_vancouver(entry, number):
    """Render a single Vancouver reference line: `- [n] Authors. Title. Journal. Year. doi:...`"""
    authors = entry.get("authors", [])
    if isinstance(authors, list):
        author_str = ", ".join(a for a in authors if a)
    else:
        author_str = str(authors)

    parts = []
    if author_str:
        parts.append(author_str.rstrip(".") + ".")
    title = entry.get("title")
    if title:
        parts.append(str(title).rstrip(".") + ".")
    journal = entry.get("journal")
    if journal:
        parts.append(str(journal).rstrip(".") + ".")
    year = entry.get("year")
    if year:
        parts.append(f"{year}.")
    doi = entry.get("doi")
    if doi:
        parts.append(f"doi:{doi}")

    return f"- [{number}] " + " ".join(parts)


def build_index_map(index_path):
    """Map global_id (int) -> entry dict from literature_index.json."""
    with open(index_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = data.get("papers", list(data.values()))
    mapping = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        gid = item.get("global_id")
        if gid is None:
            continue
        try:
            mapping[int(gid)] = item
        except (TypeError, ValueError):
            continue
    return mapping


def consolidate(md_path, index_path, output_path=None):
    with open(md_path, "r", encoding="utf-8") as f:
        original = f.read()

    body = strip_reference_blocks(original).rstrip("\n")

    used_numbers = sorted(set(extract_citation_ids(body)))
    index_map = build_index_map(index_path)

    missing = []
    ref_lines = []
    for num in used_numbers:
        entry = index_map.get(num)
        if entry is None:
            missing.append(num)
            ref_lines.append(f"- [{num}] [MISSING FROM INDEX]")
        else:
            ref_lines.append(render_vancouver(entry, num))

    result = body + "\n\n## References\n\n" + "\n".join(ref_lines) + "\n"

    out_path = output_path or md_path
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result)

    print(
        f"Consolidated references: {len(used_numbers)} cited "
        f"({len(missing)} missing from index) -> {out_path}"
    )
    if missing:
        print(
            "Warning: cited [n] not found in literature_index.json: "
            + ", ".join(str(m) for m in missing),
            file=sys.stderr,
        )
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Merge per-section References into a single global list at document end."
    )
    parser.add_argument("--md", required=True, help="Compiled Final_Review.md (edited in place by default).")
    parser.add_argument("--index", required=True, help="data/literature_index.json")
    parser.add_argument("--output", help="Write to this path instead of overwriting --md.")
    args = parser.parse_args()

    sys.exit(consolidate(args.md, args.index, args.output))


if __name__ == "__main__":
    main()
