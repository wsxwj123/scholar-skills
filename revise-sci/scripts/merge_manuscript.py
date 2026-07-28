#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from atomize_manuscript import load_figure_image_map
from common import read_json, write_text

_FIG_NO_RE = re.compile(r"(\d+)")


def _fig_no(figure_id: str) -> int | None:
    m = _FIG_NO_RE.search(figure_id or "")
    return int(m.group(1)) if m else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge revised manuscript sections into a single markdown file")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()

    project_root = Path(args.project_root)
    output_md = Path(args.output_md)
    index = read_json(project_root / "manuscript_section_index.json", {"sections": []})
    sections = index.get("sections", [])

    # 旧工程/未跑新版 atomize 时无 figures 字段 -> 保持原纯文本拼接行为不变,不做图片处理。
    has_figures_field = any("figures" in section for section in sections)
    image_map = load_figure_image_map(project_root) if has_figures_field else {}

    parts: list[str] = []
    placed_files: set[str] = set()
    figure_map: list[dict[str, str]] = []  # 图号→图片文件对照(供人工核对启发式绑定)
    for section in sections:
        body = (project_root / section["file"]).read_text(encoding="utf-8").strip()
        if body:
            parts.append(body)
        if not has_figures_field:
            continue
        # 把本节归属的图片按 markdown 图引用回填到该节末尾(图注文本已在 section md 里)。
        # image_file 以 atomize 预填为先,为空则用 merge 期(manifest 已存在)的启发式再解析。
        for fig in section.get("figures", []):
            fig_id = fig.get("figure_id", "")
            img = fig.get("image_file") or image_map.get(_fig_no(fig_id))
            binding = "atomize-prefilled" if fig.get("image_file") else "ordinal_heuristic"
            figure_map.append({
                "figure_id": fig_id,
                "image_file": img or "",
                "section": section.get("heading", ""),
                "binding": binding if img else "unresolved",
            })
            if img and img not in placed_files:
                placed_files.add(img)
                parts.append(f"![{fig_id}](figures/{img})")

    # 🔴 fail-closed 防幻影删除:manifest 里存在但没归到任何一节的图片,全部回填到文末
    # "未定位图片"区,并 warn。绝不静默丢图。zip 顺序 ≠ 阅读顺序,归属只能启发式。
    all_files = [f for f in image_map.values()]
    unplaced = [f for f in dict.fromkeys(all_files) if f not in placed_files]
    if unplaced:
        block = [
            "# Unplaced figures",
            "",
            "以下图片在原稿中存在,但启发式未能定位到具体章节(zip 顺序 ≠ 阅读顺序),请人工归位:",
            "",
        ]
        block.extend(f"![{f}](figures/{f})" for f in unplaced)
        parts.append("\n".join(block))
        print(
            f"[merge_manuscript] WARNING: {len(unplaced)} image(s) could not be anchored to a section "
            f"and were appended under 'Unplaced figures': {', '.join(unplaced)}",
            file=sys.stderr,
        )

    write_text(output_md, "\n\n".join(part for part in parts if part).strip() + "\n")

    # 🔴 图号→图片文件对照:zip 顺序 ≠ 阅读顺序,ordinal_heuristic 可能错号错位。
    # 一旦 in-place 保格式导出失败、回退到本 md 重建稿,图片就按此绑定嵌入,必须人工核对。
    if figure_map:
        print("=" * 60, file=sys.stderr)
        print("[merge_manuscript] 图号→图片文件对照(启发式绑定,请人工核对是否错号/错位):", file=sys.stderr)
        for row in figure_map:
            print(
                f"  · {row['figure_id']} -> {row['image_file'] or '(未解析)'} "
                f"[{row['binding']}]  节:{row['section'] or '?'}",
                file=sys.stderr,
            )
        print("=" * 60, file=sys.stderr)

    print(
        json.dumps(
            {
                "ok": True,
                "output_md": str(output_md.resolve()),
                "sections_merged": len(sections),
                "image_binding": "ordinal_heuristic",
                "images_total": len(dict.fromkeys(all_files)),
                "images_placed": len(placed_files),
                "images_unplaced": unplaced,
                "figure_map": figure_map,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
