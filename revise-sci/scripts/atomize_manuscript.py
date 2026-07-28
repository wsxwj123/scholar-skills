#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from common import build_section_markdown, is_heading, normalize_ws, read_docx_paragraphs, slugify, write_json, write_text
from manuscript_index import FIG_BARE_RE, FIG_CAPTION_RE


# inline_format=True 让图注段落带上 `*italic*`/`<sup>` 等行内标记,会顶掉行首的
# "Figure N" 前缀致正则失配。匹配前先剥掉这些标记(仅用于识别,不改 section md)。
_INLINE_MARK_RE = re.compile(r"\*{1,2}|_{1,2}|</?su[bp]>", re.IGNORECASE)


def _plain(text: str) -> str:
    return normalize_ws(_INLINE_MARK_RE.sub("", text or ""))


def load_figure_image_map(project_root: Path, figures_subdir: str = "figures") -> dict[int, str]:
    """从 extract_docx_images.py 产出的 image_manifest.json 读 figure 编号 -> 图片文件名。

    启发式:zip/media 顺序(manifest idx)≈ 阅读顺序 ≈ 图号,故 idx==N 映射到 Figure N。
    manifest 不存在/损坏时返回空 dict(不报错),留空 image_file 由 merge 阶段再解析。"""
    manifest_path = project_root / figures_subdir / "image_manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {
        img["idx"]: img["filename"]
        for img in data.get("images", [])
        if isinstance(img.get("idx"), int) and img.get("filename")
    }


def extract_section_figures(paragraphs: list[dict], image_map: dict[int, str]) -> list[dict]:
    """本节内以图注/裸图标题段落出现的 figure 清单。图注文本落在哪节,该图就归哪节
    (definitive);正文里的 "见 Figure 3" 引用不算归属。image_file 走 image_map 启发式,
    缺失留 None,source 记录锚定依据供下游标注置信度。"""
    figures: list[dict] = []
    seen: set[int] = set()
    for para in paragraphs:
        plain = _plain(para.get("text", ""))
        source = None
        caption_match = FIG_CAPTION_RE.match(plain)
        if caption_match:
            fig_no = int(caption_match.group(1) or caption_match.group(3))
            source = "caption"
        else:
            bare_match = FIG_BARE_RE.match(plain)
            if not bare_match:
                continue
            fig_no = int(bare_match.group(1) or bare_match.group(2))
            source = "bare_title"
        if fig_no in seen:
            continue
        seen.add(fig_no)
        figures.append(
            {
                "figure_id": f"Figure {fig_no}",
                "caption": plain,
                "image_file": image_map.get(fig_no),
                "source": source,
            }
        )
    return figures


def parse_sections(rows: list[dict], prefix: str, out_dir: Path, image_map: dict[int, str] | None = None) -> dict:
    image_map = image_map or {}
    sections: list[dict] = []
    current = {"heading": "Front matter", "paragraphs": [], "section_id": f"{prefix}-001"}

    def flush() -> None:
        if not current["paragraphs"] and current["heading"] == "Front matter" and sections:
            return
        section_number = len(sections) + 1
        heading_slug = slugify(current["heading"])
        current["section_id"] = f"{prefix}-{section_number:03d}"
        current["file"] = str(out_dir / f"{section_number:02d}-{heading_slug}.md")
        sections.append(dict(current))

    for row in rows:
        if is_heading(row):
            if current["paragraphs"]:
                flush()
            current = {"heading": row["text"], "paragraphs": [], "section_id": ""}
            continue
        current["paragraphs"].append(
            {
                "paragraph_index": row["paragraph_index"],
                "text": normalize_ws(row["text"]),
                "current_text": normalize_ws(row["text"]),
            }
        )
    flush()

    index_sections = []
    for section in sections:
        file_path = Path(section["file"])
        write_text(file_path, build_section_markdown(section))
        index_sections.append(
            {
                "section_id": section["section_id"],
                "heading": section["heading"],
                "file": str(file_path.relative_to(out_dir.parent)),
                "paragraphs": section["paragraphs"],
                "figures": extract_section_figures(section["paragraphs"], image_map),
            }
        )
    return {"sections": index_sections}


def count_tracked_changes(docx_path: Path) -> dict:
    """统计 docx 未接受的修订痕迹。python-docx 不读 <w:ins> 插入文本,带修订痕迹的
    稿件会被静默丢字/串字(抽取残缺),原子化前须拦下。"""
    import zipfile, re
    if docx_path.suffix.lower() != ".docx":
        return {"ins": 0, "del": 0}
    try:
        with zipfile.ZipFile(docx_path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
    except Exception:
        return {"ins": 0, "del": 0}
    return {
        "ins": len(re.findall(r"<w:ins[ >]", xml)),
        "del": len(re.findall(r"<w:del[ >]", xml)) + len(re.findall(r"<w:delText[ >]", xml)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Atomize manuscript and SI into markdown sections")
    parser.add_argument("--manuscript", required=True)
    parser.add_argument("--si", default="")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--allow-tracked-changes", action="store_true",
                        help="跳过修订痕迹拦截(仅在确认可接受丢字风险时使用)")
    args = parser.parse_args()

    # 🔴 修订痕迹拦截:tracked changes 会致 python-docx 静默丢字,fail-closed。
    if not args.allow_tracked_changes:
        for label, p in [("manuscript", args.manuscript), ("si", args.si)]:
            if not p:
                continue
            tc = count_tracked_changes(Path(p))
            if tc["ins"] or tc["del"]:
                print(json.dumps({
                    "ok": False, "error": "tracked_changes_present", "which": label,
                    "ins": tc["ins"], "del": tc["del"],
                    "message": (f"{label} docx 含未接受的修订痕迹: {tc['ins']} 插入 / {tc['del']} 删除。"
                                "python-docx 会静默丢弃插入文本致抽取残缺。请先在 Word 里【接受所有修订】"
                                "并关闭修订跟踪后重导入;或明知风险时加 --allow-tracked-changes。"),
                }, ensure_ascii=False))
                return 1

    project_root = Path(args.project_root)
    manuscript_dir = project_root / "manuscript_sections"
    si_dir = project_root / "si_sections"
    manuscript_dir.mkdir(parents=True, exist_ok=True)
    si_dir.mkdir(parents=True, exist_ok=True)

    # image_manifest.json 通常在 extract_docx_images.py(排在 atomize 之后)才生成,此处多为空;
    # resume/重跑时若已存在则顺带填 image_file。空缺不阻断,merge 阶段以 manifest 为准再解析。
    image_map = load_figure_image_map(project_root)

    # inline_format=True 让原稿段落的 run 级 斜体/上下标/加粗 以行内标记进入 section
    # text/current_text,经 revise -> export 往返保住语义行内格式(与 polish 口径一致)。
    manuscript_index = parse_sections(read_docx_paragraphs(Path(args.manuscript), inline_format=True), "manuscript", manuscript_dir, image_map)
    write_json(project_root / "manuscript_section_index.json", manuscript_index)

    if args.si:
        si_index = parse_sections(read_docx_paragraphs(Path(args.si), inline_format=True), "si", si_dir, image_map)
    else:
        si_index = {"sections": []}
    write_json(project_root / "si_section_index.json", si_index)

    print(json.dumps({"ok": True, "manuscript_sections": len(manuscript_index["sections"]), "si_sections": len(si_index["sections"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
