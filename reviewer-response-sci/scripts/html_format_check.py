#!/usr/bin/env python3
"""Validate hierarchical HTML output contract for reviewer-response-sci."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REQUIRED_IDS = ["toc-root", "content-root", "layout-root", "resizer"]
REQUIRED_CLASSES = ["toc-level-1", "toc-level-2", "toc-level-3", "page", "toc-btn"]


def read_text(path: str | None) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8")
    return sys.stdin.read()


def normalize_html_text(text: str) -> str:
    match = re.search(r"```html\n([\s\S]*?)```", text)
    if match:
        return match.group(1)
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate reviewer-response hierarchical HTML output")
    parser.add_argument("file", nargs="?", help="Path to output text or HTML file")
    args = parser.parse_args()

    raw = read_text(args.file)
    html = normalize_html_text(raw)

    errors: list[str] = []

    if "<html" not in html.lower() or "</html>" not in html.lower():
        errors.append("Missing complete HTML document wrapper")

    for rid in REQUIRED_IDS:
        if f'id="{rid}"' not in html and f"id='{rid}'" not in html:
            errors.append(f"Missing required id: {rid}")

    for cls in REQUIRED_CLASSES:
        pat = re.compile(
            r'class="[^"]*\b' + re.escape(cls) + r'\b[^"]*"'
            + r"|class='[^']*\b" + re.escape(cls) + r"\b[^']*'",
            re.IGNORECASE,
        )
        if not pat.search(html):
            errors.append(f"Missing required class usage: {cls}")

    # Only require <img> if the HTML contains actual figure prompt blocks or image placeholders.
    # Mere text references to "Figure 4B" in reviewer comments do not require <img> tags.
    has_figure_prompt = any(k in html for k in ["FIGURE PROMPT", "figure_prompt", "image placeholder", "Image Placeholder"])
    if has_figure_prompt and "<img" not in html:
        errors.append("Missing <img> block despite figure prompt/placeholder present")

    if "<table" not in html or "<th" not in html:
        errors.append("Missing table structure (<table>/<th>)")

    if "copy-btn" not in html or "copyText(" not in html:
        errors.append("Missing copy button support for bilingual blocks")

    if "--sidebar-w" not in html or "role=\"separator\"" not in html:
        errors.append("Missing draggable splitter scaffold (--sidebar-w / separator)")

    if "reviewer_sidebar_width_v1" not in html:
        errors.append("Missing persisted splitter width storage key")

    if "Response to Reviewer（中英对照）" not in html:
        errors.append("Missing bilingual response section heading")

    if "可能需要修改的正文/附件内容（中英对照）" not in html:
        errors.append("Missing bilingual revision section heading")

    if "原子化定位（Atomic Location）" not in html:
        errors.append("Missing atomic location block in revision section")

    if "manuscript_unit_id" not in html:
        errors.append("Missing manuscript_unit_id display in HTML")

    if "核心" not in html and "Core" not in html:
        errors.append("Missing core/support note markers")

    if errors:
        print("HTML_FORMAT_CHECK: FAIL")
        for err in errors:
            print(f"- {err}")
        return 1

    print("HTML_FORMAT_CHECK: PASS")
    print("- Hierarchical TOC structure detected")
    print("- Content pane and page switching scaffolding detected")
    print("- Image and table support present")
    print("- Core/support markers found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
