#!/usr/bin/env python3
"""结构目录抽取（reviewer-simulator 第 1 层交叉引用确定性锚）。

从成稿（docx/md）客观抽取"真实存在的结构目录"——小标题 / 图 / 表 / 条目编号，
写 <project-root>/outline.json + stdout 末行摘要 JSON。**只列稿子里有啥结构，
不判任何交叉引用对不对**（存在性/语义判断在第 2 层 LLM）。

复用同目录 manuscript_index.py 已验证的读稿与图抽取能力，只新增小标题 / 表 / 条目
三类薄抽取。护栏方向＝**宁抽勿拒**（漏抽真小节 → 第 2 层假 missing_target 假批评，
危害远大于误抽一个没人引的孤儿条目），仅拦"确定性数值信号"。

CLI:
  python structure_outline.py --manuscript <docx|md> --project-root <root>

退出码：0=正常（含空稿）；2=用法/输入错（缺参 / 文件不存在 / 不支持类型）。
契约见 .devflow/INTERFACE-xref-existence.md。
"""
import sys as _sys
try:  # Windows GBK 控制台/管道捕获下防 UnicodeEncodeError
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

# 同目录 manuscript_index.py 是 8 家逐字节共享文件，绝不改，只 import 复用其读稿/图抽取。
from manuscript_index import (
    normalize_ws,
    write_json,
    read_manuscript_paragraphs,
    reference_section_spans,
    body_row_indices,
    build_figure_index,
    looks_like_reference_entry,
    FIG_CAPTION_RE,
    FIG_BARE_RE,
)

SUPPORTED_SUFFIXES = {".docx", ".md", ".markdown", ".txt"}

# 表：与 manuscript_index 的 FIG_* 平行的薄抽取（manuscript_index 不含表，故本地新增）。
TABLE_CAPTION_RE = re.compile(
    r"^(?:Table|Tab\.?)\s*(\d+)\s*[.:]\s*(\S.*)$|^表\s*(\d+)\s*[.:：]\s*(\S.*)$",
    re.IGNORECASE,
)
TABLE_BARE_RE = re.compile(r"^(?:Table|Tab\.?)\s*(\d+)\s*$|^表\s*(\d+)\s*$", re.IGNORECASE)
TABLE_INTEXT_RE = re.compile(r"\b(?:Table|Tab\.?)\s*(\d+)|表\s*(\d+)", re.IGNORECASE)

# 小标题裸编号：与 manuscript_index.is_heading 同款 `^\d+(?:\.\d+)*\.?\s+\S`。
_NUM_TITLE_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(\S.*)$")

# 编号紧跟计量单位（唯一的单位拦截，宁抽勿拒）：编号后第一个 token 即计量单位 → 判数值，拒。
# 仅拦"紧跟"，不检查标题任意位置含单位词（否则 3.4 24h内存活率、3.6 高倍镜观察 被误杀）。
# 时间单位 h/min/s、"倍" 等**不入表**——它们出现在真标题里（24h内存活率），入表会误杀。
_UNITS = {
    "mg", "kg", "g", "l", "ml", "μl", "µl", "ul", "μm", "µm", "um", "mm", "cm", "nm",
    "μg", "µg", "ug", "ng", "pg", "mol", "mmol", "nmol", "μmol", "µmol", "umol",
    "kda", "da", "bp", "kb", "%", "℃", "°c",
}
# 编号后紧邻的 ASCII/单位符号串（遇空格/数字/CJK 即止），用于取"第一个 token"判单位。
_LEAD_UNIT_RE = re.compile(r"^([A-Za-zμµ%℃°/·]+)")

# 作者单位地址行拦截（护栏 4）：机构关键词 + 逗号地址串同现＝确定性伪 section 信号。
# 真小节标题(Introduction/材料与方法)不含机构词；含机构词的真标题(如 "University 数据集")
# 极少带逗号分隔地址串。两条件同时命中才拒，避免误杀。
_AFFIL_RE = re.compile(
    r"\b(?:Department|Hospital|University|Universit[ée]|Laborator|Institute|College|"
    r"School|Centre|Center|Faculty|Division|Clinic|Academy)\b"
    r"|(?:系|学院|医院|大学|研究所|研究院|实验室|中心)",
    re.IGNORECASE,
)

# 条目：段内列表编号 (N)/（N）/①..⑳，须紧跟实质内容字符（区分定义 `(2)确诊` 与引用 `见(2)`）。
_ITEM_RE = re.compile(r"([(（]\s*\d+\s*[)）])|([①-⑳])")
_CONTENT_CHAR_RE = re.compile(r"[A-Za-z一-鿿]")


def _split_number_title(text: str) -> tuple[Optional[str], str]:
    """`3.1 材料与方法` → ('3.1', '材料与方法')；无裸编号 → (None, 原文)。"""
    m = _NUM_TITLE_RE.match(text)
    if m:
        return m.group(1), normalize_ws(m.group(2))
    return None, normalize_ws(text)


def _passes_section_guardrails(text: str) -> bool:
    """裸编号行（非标题样式）是否为真小标题。仅拦确定性数值信号，其余一律放行。"""
    m = _NUM_TITLE_RE.match(text)
    if not m:
        return False
    remainder = m.group(2)
    if looks_like_reference_entry(text):
        return False  # 参考条目 `1. Zhang Y, 2021.` 走参考区，不算小标题
    # 护栏 1：编号紧跟计量单位（3.2 mg/kg、5 mL、10 μM）。
    lead = _LEAD_UNIT_RE.match(remainder)
    if lead:
        tokens = [t for t in lead.group(1).split("/") if t]
        if tokens and all(t.lower() in _UNITS for t in tokens):
            return False
    # 护栏 3：编号后无实质标题文本（纯数字/符号，如 `3.2 5.0`）。
    if not _CONTENT_CHAR_RE.search(remainder):
        return False
    # 护栏 4：作者单位地址行（`1 Department of X, University of Y, 410011, China`）——
    # 机构关键词 + 逗号地址串同现才拒；只命中其一（无逗号的机构词标题 / 有逗号的普通标题）放行。
    if ("," in remainder or "，" in remainder) and _AFFIL_RE.search(remainder):
        return False
    return True


def read_md_lines(path: Path) -> list[dict[str, Any]]:
    """md/txt 逐行成行（一非空行=一 row），不按空行粗切块。

    manuscript_index.read_md_paragraphs 按空行把多行粘成一个 block —— 多个裸编号
    小标题之间无空行时(Word 导出的 .txt 常无空行)会被粘成一段，extract_sections
    每行只认一个标题 → 只抽到首个、其余 number 全丢，且 title 会吞进后续正文。
    这里逐行发 row(与 docx 每段独立同粒度)，让小标题/条目抽取按行正确拆分；
    section 与 item 共用同一 paragraph_index 编号，归属linkage一致。
    `#`/`##` 前缀标题去号并标 Heading 样式(供 is_heading 认章节/终止参考区)。
    参考条目本就一行一条，逐行发天然一条一 row，无需 read_md_paragraphs 的特判。
    """
    raw = path.read_text(encoding="utf-8", errors="ignore")
    rows: list[dict[str, Any]] = []
    para_index = 0
    for line in raw.splitlines():
        if not line.strip():
            continue
        is_md_heading = line.lstrip().startswith("#")
        cleaned = normalize_ws(re.sub(r"^#{1,6}\s*", "", line))
        if not cleaned:
            continue
        rows.append({
            "paragraph_index": para_index,
            "text": cleaned,
            "style_name": "Heading" if is_md_heading else "Normal",
        })
        para_index += 1
    return rows


def extract_sections(rows: list[dict[str, Any]], body_indices: list[int]) -> list[dict[str, Any]]:
    """正文区小标题：docx/md 标题样式直接认；裸编号过护栏。图表题注不进 section。"""
    sections: list[dict[str, Any]] = []
    for i in body_indices:
        row = rows[i]
        text = normalize_ws(row.get("text", ""))
        if not text:
            continue
        # 图/表题注、裸图表标题走各自类别，不算 section。
        if (FIG_CAPTION_RE.match(text) or TABLE_CAPTION_RE.match(text)
                or FIG_BARE_RE.match(text) or TABLE_BARE_RE.match(text)):
            continue
        style = (row.get("style_name", "") or "").lower()
        number, title = _split_number_title(text)
        if style.startswith("heading"):
            is_section = True
        elif number is not None:
            is_section = _passes_section_guardrails(text)
        else:
            is_section = False
        if not is_section:
            continue
        level = len(number.split(".")) if number else None
        sections.append({
            "type": "section",
            "number": number,
            "level": level,
            "title": title,
            "para_index": row.get("paragraph_index"),
        })
    return sections


def build_table_index(rows: list[dict[str, Any]], ref_spans) -> list[dict[str, Any]]:
    """与 build_figure_index 平行的薄表抽取：题注 + 正文引用取并集，number 统一 `Table N`。"""
    body_indices = body_row_indices(rows, ref_spans)
    captions: dict[int, str] = {}
    caption_rows: set[int] = set()
    for i in range(len(rows)):
        text = normalize_ws(rows[i].get("text", ""))
        m = TABLE_CAPTION_RE.match(text)
        if m:
            no = int(m.group(1) or m.group(3))
            captions.setdefault(no, text)
            caption_rows.add(i)
    cited: set[int] = set()
    for i in body_indices:
        text = normalize_ws(rows[i].get("text", ""))
        if not text or i in caption_rows or TABLE_BARE_RE.match(text):
            continue
        for m in TABLE_INTEXT_RE.finditer(text):
            cited.add(int(m.group(1) or m.group(2)))
    out: list[dict[str, Any]] = []
    for no in sorted(set(captions) | cited):
        out.append({
            "type": "table",
            "number": f"Table {no}",
            "title": captions.get(no, ""),
            "caption_found": no in captions,
        })
    return out


def extract_items(rows: list[dict[str, Any]], body_indices: list[int],
                  sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """段内定义式列表编号 (N)/①，挂当前所在小节；引用式 `见(2)`（后无内容）不抽。"""
    section_at_para = {s["para_index"]: s["number"] for s in sections}
    items: list[dict[str, Any]] = []
    current_section: Optional[str] = None
    for i in body_indices:
        row = rows[i]
        para = row.get("paragraph_index")
        if para in section_at_para:
            current_section = section_at_para[para]
        text = normalize_ws(row.get("text", ""))
        if not text:
            continue
        for m in _ITEM_RE.finditer(text):
            after = text[m.end():m.end() + 1]
            if not after or not _CONTENT_CHAR_RE.match(after):
                continue  # 编号后无实质内容 → 引用式（见(2)），非定义条目
            if m.group(1):  # (N) / （N）
                digits = re.search(r"\d+", m.group(1)).group(0)
                number = f"({digits})"
            else:  # 圆圈数字 ①..⑳，原样保留
                number = m.group(2)
            items.append({
                "type": "item",
                "number": number,
                "parent_section": current_section,
                "para_index": para,
            })
    return items


def build_outline(manuscript_path: Path) -> dict[str, Any]:
    # docx 每段独立、本就正确；md/txt 走逐行读，避免 read_md_paragraphs 空行粗切块
    # 把无空行的多个小标题粘成一段丢 number（见 read_md_lines）。
    if manuscript_path.suffix.lower() in {".md", ".markdown", ".txt"}:
        rows = read_md_lines(manuscript_path)
    else:
        rows = read_manuscript_paragraphs(manuscript_path)
    ref_spans = reference_section_spans(rows)
    body_indices = body_row_indices(rows, ref_spans)

    sections = extract_sections(rows, body_indices)
    figures = [
        {
            "type": "figure",
            "number": f["figure_id"],
            "title": f["caption"],
            "caption_found": f["caption_found"],
        }
        for f in build_figure_index(rows, ref_spans, None)
    ]
    tables = build_table_index(rows, ref_spans)
    items = extract_items(rows, body_indices, sections)

    return {
        "sections": sections,
        "figures": figures,
        "tables": tables,
        "items": items,
        "summary": {
            "sections": len(sections),
            "figures": len(figures),
            "tables": len(tables),
            "items": len(items),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="从成稿抽取结构目录（小标题/图/表/条目）当交叉引用确定性锚。"
    )
    parser.add_argument("--manuscript", required=True, help="成稿路径（docx / md / markdown / txt）。")
    parser.add_argument("--project-root", required=True, help="输出根目录，outline.json 写这里。")
    args = parser.parse_args()

    manuscript_path = Path(args.manuscript).expanduser().resolve()
    project_root = Path(args.project_root).expanduser().resolve()

    # 用法/输入错：显式 sys.exit(2)（不用 raise SystemExit(字符串)，那会变 exit 1）。
    if not manuscript_path.exists():
        print(f"manuscript not found: {manuscript_path}", file=sys.stderr)
        sys.exit(2)
    if manuscript_path.suffix.lower() not in SUPPORTED_SUFFIXES:
        print(f"unsupported manuscript type: {manuscript_path.suffix}", file=sys.stderr)
        sys.exit(2)

    outline = build_outline(manuscript_path)
    write_json(project_root / "outline.json", outline)

    print(json.dumps({"ok": True, **outline["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
