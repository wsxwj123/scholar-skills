#!/usr/bin/env python3
"""为 pandoc 生成国自然中文标书的 reference.docx 样式模板。

锁定字体规范（国自然中文标书惯例）：
  - 正文：中文宋体、西文 Times New Roman、小四（12pt）
  - 各级标题：中文黑体、西文 Times New Roman，三号/小三/四号
  - 中文必须显式设置 w:eastAsia，否则 Word 会用默认字体回退（中文不走宋体/黑体）

幂等：对 templates/reference.docx 原地改样式后存回，重复运行结果一致。
字体/字号改这里的常量即可。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import docx
from docx.oxml.ns import qn
from docx.shared import Pt

# ── 字体常量 ───────────────────────────────────────────────
WESTERN_FONT = "Times New Roman"   # 全文西文字体
BODY_EAST_ASIA = "宋体"             # 正文中文字体（SimSun）
HEADING_EAST_ASIA = "黑体"          # 标题中文字体（SimHei）

# ── 字号常量（国自然习惯）────────────────────────────────
BODY_PT = 12   # 小四 = 12pt（正文）
H1_PT = 16     # 三号 ≈ 16pt
H2_PT = 15     # 小三 ≈ 15pt
H3_PT = 14     # 四号 ≈ 14pt
TITLE_PT = H1_PT

# 正文类样式（西文 TNR + eastAsia 宋体 + 小四）
BODY_STYLES = ["Normal", "Body Text", "First Paragraph", "Compact"]

# 段前段后清零的正文样式（国自然正文不留段间距）。
# Compact 已自带 1.8pt 小间距（紧凑列表用）保持不动；
# Bibliography basedOn Normal，Normal 清零后会被继承带零，故须显式补回小间距，
# 保证参考文献条目之间仍有间隔。
ZERO_SPACING_STYLES = ["Normal", "Body Text", "First Paragraph"]
BIBLIOGRAPHY_AFTER_PT = 6

# 标题类样式：(样式名, 字号, 是否加粗)
# 黑体本身够区分层级，国自然标题习惯不强制加粗，统一 bold=False
HEADING_STYLES = [
    ("Heading 1", H1_PT, False),
    ("Heading 2", H2_PT, False),
    ("Heading 3", H3_PT, False),
    ("Title", TITLE_PT, False),
]

# 图注/表注/摘要：比正文小一号（10pt），中文仍走宋体防回退。
CAPTION_PT = 10
CAPTION_STYLES = ["Image Caption", "Table Caption", "Abstract"]

REFERENCE_DOCX = Path(__file__).resolve().parent.parent / "templates" / "reference.docx"


def _set_east_asia(style, font_name: str) -> None:
    """显式写入 w:eastAsia，控制中文字体不回退。"""
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    rfonts.set(qn("w:eastAsia"), font_name)


def _apply_western_and_size(style, size_pt: int) -> None:
    style.font.name = WESTERN_FONT  # 写 w:ascii / w:hAnsi
    style.font.size = Pt(size_pt)


def _set_para_spacing(style, before_pt: float, after_pt: float) -> None:
    pf = style.paragraph_format
    pf.space_before = Pt(before_pt)
    pf.space_after = Pt(after_pt)


def apply_styles(doc) -> None:
    for name in BODY_STYLES:
        style = doc.styles[name]
        _apply_western_and_size(style, BODY_PT)
        _set_east_asia(style, BODY_EAST_ASIA)

    # 正文段前段后清零（字体不动）。
    for name in ZERO_SPACING_STYLES:
        _set_para_spacing(doc.styles[name], 0, 0)
    # Bibliography 显式补回小间距（否则继承已清零的 Normal）。
    try:
        _set_para_spacing(doc.styles["Bibliography"], 0, BIBLIOGRAPHY_AFTER_PT)
    except KeyError:
        pass

    for name, size_pt, bold in HEADING_STYLES:
        style = doc.styles[name]
        _apply_western_and_size(style, size_pt)
        _set_east_asia(style, HEADING_EAST_ASIA)
        style.font.bold = bold

    # 图注/表注/摘要小一号 + 中文宋体（防个别精简模板缺样式，加存在性判断）。
    existing = {s.name for s in doc.styles}
    for name in CAPTION_STYLES:
        if name in existing:
            style = doc.styles[name]
            _apply_western_and_size(style, CAPTION_PT)
            _set_east_asia(style, BODY_EAST_ASIA)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="为 pandoc 生成国自然中文标书的 reference.docx 样式模板。"
    )
    parser.add_argument(
        "--template", default=str(REFERENCE_DOCX),
        help="基线 reference.docx（默认：技能 templates/reference.docx）")
    parser.add_argument(
        "--output", default=str(Path.cwd() / "reference.docx"),
        help="输出路径（默认：当前工作目录 ./reference.docx）")
    args = parser.parse_args()

    template_path = Path(args.template).resolve()
    output_path = Path(args.output).resolve()

    if not template_path.exists():
        raise SystemExit(
            f"未找到 {template_path}\n"
            "请先运行：pandoc --print-default-data-file reference.docx > "
            f"{template_path}"
        )
    doc = docx.Document(str(template_path))
    apply_styles(doc)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    print(f"已写入字体样式：{output_path}")
    print(f"  正文 {BODY_STYLES}: 西文={WESTERN_FONT} 中文={BODY_EAST_ASIA} {BODY_PT}pt")
    print(f"  标题 H1/H2/H3/Title: 西文={WESTERN_FONT} 中文={HEADING_EAST_ASIA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
