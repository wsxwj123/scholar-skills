#!/usr/bin/env python3
"""Atomize a finished manuscript into per-paragraph polish units.

输入一份已写完的稿子(md 或 docx),按段落原子化成 units/<idx>.json。
每个 unit 记录:raw_text、推断的 section_type、是否含引用/数值。
section_type 由最近的标题文本推断(intro/methods/results/discussion/abstract/other)。
脚本只做拆分与标注,不改任何文字。
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from common import looks_like_reference_entry, normalize_ws, numeric_tokens, read_docx_paragraphs, write_json

CITATION_RE = re.compile(r"\[\d+(?:\s*[-,]\s*\d+)*\]|\bdoi:\s*10\.\d", re.IGNORECASE)

SECTION_KEYWORDS = (
    ("abstract", ("abstract", "摘要")),
    ("intro", ("introduction", "background", "引言", "前言", "背景")),
    ("methods", ("methods", "materials and methods", "methodology", "experimental",
                 "材料与方法", "方法", "实验")),
    ("results", ("results", "findings", "结果")),
    ("discussion", ("discussion", "conclusion", "conclusions", "讨论", "结论")),
)


def infer_section_type(heading: str) -> str:
    h = normalize_ws(heading).lower()
    # strip leading numbering like "2." / "2.1"
    h = re.sub(r"^[\d.]+\s*", "", h)
    for section_type, keys in SECTION_KEYWORDS:
        for key in keys:
            if h == key or h.startswith(key):
                return section_type
    return "other"


# 内容式标题识别:许多 docx/稿子的标题不是 Word Heading 样式,而是普通短段落
# (如 "1. Introduction" / "2.1 Foo" / "Experimental Section")。
_NUMBERED_HEADING_RE = re.compile(r"^\d+(?:\.\d+)*\.?\s+\S")
_SECTION_NAME_RE = re.compile(
    r"^(abstract|introduction|background|results?(?:\s+and\s+discussion)?|discussion|"
    r"conclusions?|summary|methods?|materials\s+and\s+methods|methodology|"
    r"experimental(?:\s+section)?|references|acknowledge?ments|keywords|"
    r"supporting\s+information|author\s+contributions?|conflicts?\s+of\s+interest|"
    r"data\s+availability|"
    r"摘要|引言|前言|背景|方法|材料与方法|实验(?:部分)?|结果(?:与讨论)?|讨论|结论|参考文献|关键词)$",
    re.IGNORECASE,
)
_ABSTRACT_LEADIN_RE = re.compile(r"^(abstract|摘要)\s*[.:：]", re.IGNORECASE)
# 机构/地址行常以编号开头(如 "3 X University / X Key Laboratory of …"),含机构实体词则不算章节标题。
_AFFILIATION_HINT_RE = re.compile(
    r"\b(?:universit|institut|laborator|hospital|college|faculty|academ|ministr)\w*"
    r"|\b(?:department|school|center|centre|division)\s+(?:of|for)\b"
    r"|大学|学院|研究院|研究所|重点实验室|实验室|医院",
    re.IGNORECASE,
)


def looks_like_heading(text: str) -> bool:
    """非样式化的章节标题判定:短段落 + (编号开头 或 整行就是已知章节名)。"""
    t = normalize_ws(text)
    if not t or len(t.split()) > 10:
        return False
    # 数字编号的参考文献条目(如 "1. Smith J, et al. Nature. 2020;...")不是标题
    if looks_like_reference_entry(t):
        return False
    core = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", t).strip().rstrip(".．")
    if (
        _NUMBERED_HEADING_RE.match(t)
        and 1 <= len(core.split()) <= 8
        and not _AFFILIATION_HINT_RE.search(t)  # 编号机构行不算标题
    ):
        return True
    if _SECTION_NAME_RE.match(core) and len(core.split()) <= 6:
        return True
    return False


# 非散文章节:其内容是清单/条目(参考文献、致谢、作者贡献、利益冲突、数据可用性、
# 补充材料、资助),不做语言润色,去AI/句长检测对它们不适用。
_NONPROSE_SECTION_RE = re.compile(
    r"^(references?|bibliography|acknowledge?ments?|author\s+contributions?|"
    r"conflicts?\s+of\s+interest|competing\s+interests?|data\s+availability|"
    r"supporting\s+information|supplementary(?:\s+\w+)?|funding|abbreviations?|"
    r"参考文献|致谢|作者贡献|利益冲突|数据可用性|补充材料|资助|缩略语)$",
    re.IGNORECASE,
)


def is_nonprose_section(heading: str) -> bool:
    core = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", normalize_ws(heading)).strip().rstrip(".．:：")
    return bool(_NONPROSE_SECTION_RE.match(core))


def is_markdown_heading(line: str) -> bool:
    return bool(re.match(r"^#{1,6}\s+\S", line))


def heading_text(line: str) -> str:
    return re.sub(r"^#{1,6}\s+", "", line).strip()


def markdown_heading_level(line: str) -> int:
    """`#` 的个数即层级(1-6);非 md 语法标题返回 0。"""
    m = re.match(r"^(#{1,6})\s+\S", line)
    return len(m.group(1)) if m else 0


def split_md_paragraphs(text: str) -> list[dict]:
    """Return ordered list of {'kind': 'heading'|'para', 'text': str}."""
    blocks: list[dict] = []
    buf: list[str] = []

    def flush() -> None:
        joined = normalize_ws(" ".join(buf))
        if joined:
            blocks.append({"kind": "para", "text": joined})
        buf.clear()

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if is_markdown_heading(line):
            flush()
            blocks.append({"kind": "heading", "text": heading_text(line),
                           "heading_level": markdown_heading_level(line)})
        elif not line.strip():
            flush()
        else:
            buf.append(line.strip())
    flush()
    return blocks


def split_docx_paragraphs(path: Path) -> list[dict]:
    blocks: list[dict] = []
    for row in read_docx_paragraphs(path):
        style = (row.get("style_name") or "").lower()
        text = normalize_ws(row.get("text", ""))
        if not text:
            continue
        # marked_text 带 run 级行内格式标记(斜体/上下标/加粗);para 用它做 raw_text,
        # 使润色直接看到并保留这些语义格式。heading 判定仍用纯 text,避免标记干扰正则。
        marked = normalize_ws(row.get("marked_text", "")) or text
        para_index = row.get("paragraph_index")
        if style.startswith("heading") or style == "title":
            # 从 style name 提取层级:"heading 1"->1, "heading 2"->2;"title" 视为 1。
            m = re.search(r"(\d+)", style)
            level = int(m.group(1)) if m else 1
            blocks.append({"kind": "heading", "text": text, "para_index": para_index,
                           "heading_level": level})
        else:
            blocks.append({"kind": "para", "text": marked, "plain_text": text, "para_index": para_index})
    return blocks


def build_units(blocks: list[dict]) -> list[dict]:
    units: list[dict] = []
    current_heading = ""
    current_type = "other"
    current_prose = True
    current_heading_level = 0
    current_heading_inferred = False
    idx = 0
    for block in blocks:
        # 标题判定用纯文本(plain_text),避免行内格式标记干扰正则;para 默认无 plain_text 时回退 text
        plain = block.get("plain_text", block["text"])
        # 样式化标题,或内容上像未样式化的章节标题,都当作标题处理
        if block["kind"] == "heading" or (
            block["kind"] == "para" and looks_like_heading(plain)
        ):
            current_heading = plain
            current_type = infer_section_type(current_heading)
            current_prose = not is_nonprose_section(current_heading)
            if "heading_level" in block:
                # 显式标题(md `#` 语法 / docx heading 样式):用记录的真实层级
                current_heading_level = block["heading_level"]
                current_heading_inferred = False
            else:
                # 未样式化、靠 looks_like_heading 推断的标题:给默认 level 1 并标 inferred
                current_heading_level = 1
                current_heading_inferred = True
            continue
        raw = block["text"]  # 带行内格式标记(docx)或纯文本(md)
        # Abstract 引导词判定用纯文本
        is_abstract = bool(_ABSTRACT_LEADIN_RE.match(plain))
        unit_type = "abstract" if is_abstract else current_type
        units.append(
            {
                "idx": idx,
                "raw_text": raw,
                "heading": current_heading,
                # heading_level:该 unit 所属标题的层级(1-6)。abstract 引导词段无独立标题,
                # 沿用当前 section 层级。inferred 段(非 # 语法)默认 1。
                "heading_level": current_heading_level,
                "heading_inferred": current_heading_inferred,
                "section_type": unit_type,
                # source_para_index:该 unit 对应源 docx 的段落下标,供 in-place 写回精确定位;
                # md 输入无此概念则为 None。
                "source_para_index": block.get("para_index"),
                # prose=False 的段落(参考文献/致谢等)只保留不润色,去AI/句长检测豁免
                "prose": True if is_abstract else current_prose,
                "has_citation": bool(CITATION_RE.search(raw)),
                "has_numeric": bool(numeric_tokens(raw)),
                "word_count": len(raw.split()),
                "char_count": len(raw),
            }
        )
        idx += 1
    return units


def count_tracked_changes(docx_path: Path) -> dict:
    """统计 docx 未接受的修订痕迹(tracked changes)。
    python-docx 的 paragraph.text 只读普通 run,不读 <w:ins> 插入文本、且会保留
    <w:del> 删除文本,带修订痕迹的稿件会被静默丢字/串字(抽取残缺)。原子化前须拦下。"""
    import zipfile
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
    parser = argparse.ArgumentParser(description="Atomize finished manuscript into per-paragraph polish units")
    parser.add_argument("--manuscript", required=True, help="input md or docx")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--allow-tracked-changes", action="store_true",
                        help="跳过修订痕迹拦截(仅在确认可接受丢字风险时使用)")
    args = parser.parse_args()

    src = Path(args.manuscript)
    project_root = Path(args.project_root)
    units_dir = project_root / "units"
    units_dir.mkdir(parents=True, exist_ok=True)

    if src.suffix.lower() == ".docx":
        # 🔴 修订痕迹拦截:tracked changes 会导致 python-docx 静默丢字,fail-closed。
        if not args.allow_tracked_changes:
            tc = count_tracked_changes(src)
            if tc["ins"] or tc["del"]:
                print(json.dumps({
                    "ok": False, "error": "tracked_changes_present",
                    "ins": tc["ins"], "del": tc["del"],
                    "message": ("docx 含未接受的修订痕迹(tracked changes): "
                                f"{tc['ins']} 处插入 / {tc['del']} 处删除。python-docx 会静默丢弃 "
                                "<w:ins> 插入文本,导致抽取的正文残缺(丢词/掉首字母)。请先在 Word 里 "
                                "【审阅→接受→接受所有修订】并关闭修订跟踪后重新导入;或明知风险时加 "
                                "--allow-tracked-changes 强制继续。"),
                }, ensure_ascii=False))
                return 1
        blocks = split_docx_paragraphs(src)
    else:
        blocks = split_md_paragraphs(src.read_text(encoding="utf-8"))

    units = build_units(blocks)
    for unit in units:
        write_json(units_dir / f"{unit['idx']}.json", unit)

    index = {
        "source": str(src.resolve()),
        "unit_count": len(units),
        "units": [
            {"idx": u["idx"], "section_type": u["section_type"], "heading": u["heading"],
             "heading_level": u["heading_level"],
             "has_citation": u["has_citation"], "has_numeric": u["has_numeric"]}
            for u in units
        ],
    }
    write_json(project_root / "units_index.json", index)
    print(json.dumps({"ok": True, "unit_count": len(units)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
