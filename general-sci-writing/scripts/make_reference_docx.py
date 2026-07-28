"""Generate / refresh the pandoc reference.docx that locks SCI manuscript fonts.

Opens templates/reference.docx (the pandoc baseline produced by
`pandoc --print-default-data-file reference.docx`) and forces key paragraph
styles to Times New Roman with explicit point sizes, so that `/merge`'s pandoc
export yields a docx whose body is TNR 12pt and whose headings are TNR bold.

The script is IDEMPOTENT: re-running it on an already-processed file produces
the same result. Run it after editing the FONT/SIZE constants below.

Usage:
    python scripts/make_reference_docx.py [--template BASE.docx] [--output OUT.docx]
    (default: read skill templates/reference.docx, write ./reference.docx in CWD)

Requires: python-docx. The baseline templates/reference.docx must already exist
(regenerate with: pandoc --print-default-data-file reference.docx > templates/reference.docx).
"""

import argparse
from pathlib import Path

from docx import Document
from docx.shared import Pt
from docx.oxml.ns import qn

# ---------------------------------------------------------------------------
# TUNABLES — edit these to change the locked fonts/sizes, then re-run the script.
# ---------------------------------------------------------------------------
FONT_NAME = "Times New Roman"  # applied to Latin, complex-script AND East-Asian slots

# Body-text styles: name -> point size. Set to TNR 12pt (standard SCI manuscript).
BODY_STYLES = {
    "Normal": 12,           # base style everything inherits from
    "Body Text": 12,        # pandoc wraps most paragraphs in Body Text
    "First Paragraph": 12,  # first paragraph after a heading
    "Compact": 12,          # tight paragraphs / list items
    "Bibliography": 12,     # reference list entries (keep consistent with body)
}

# 正文段前段后清零：这三个样式承载绝大多数正文段落，SCI 正文不留段间距。
# Compact 保留自带小间距（紧凑列表用），不清零。
# Bibliography basedOn Normal，Normal 清零后会被继承带零导致条目粘连，故显式补回
# space_after 保证参考文献条目间仍有间隔。
ZERO_SPACING_STYLES = ("Normal", "Body Text", "First Paragraph")
BIBLIOGRAPHY_AFTER_PT = 6

# Heading / title styles: name -> (point size, bold). TNR bold, descending sizes.
HEADING_STYLES = {
    "Title": (18, True),
    "Heading 1": (16, True),
    "Heading 2": (14, True),
    "Heading 3": (12, True),
}

# 图注/表注/摘要:比正文小一号(10pt),从正文尺寸里独立出来。
# Image/Table Caption 的斜体由 pandoc 的 Caption 基样式继承,无需显式设。
CAPTION_STYLES = {
    "Image Caption": 10,
    "Table Caption": 10,
    "Abstract": 10,
}

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "reference.docx"


def set_style_font(style, size_pt, bold=None):
    """Force a style's font name + size, including the East-Asian font slot.

    Setting font.name only writes the Latin (w:ascii/hAnsi) slot; we also write
    w:eastAsia so an occasional CJK glyph or locale fallback cannot swap the
    body to a different face mid-document.
    """
    font = style.font
    font.name = FONT_NAME
    font.size = Pt(size_pt)
    if bold is not None:
        font.bold = bold

    rfonts = style.element.get_or_add_rPr().get_or_add_rFonts()
    rfonts.set(qn("w:eastAsia"), FONT_NAME)
    # Also pin ascii/hAnsi/cs at the XML level so the eastAsia write can't leave
    # the other slots inconsistent across python-docx versions.
    rfonts.set(qn("w:ascii"), FONT_NAME)
    rfonts.set(qn("w:hAnsi"), FONT_NAME)
    rfonts.set(qn("w:cs"), FONT_NAME)


def set_para_spacing(style, before_pt, after_pt):
    """强制段前段后间距（字体不动）。"""
    pf = style.paragraph_format
    pf.space_before = Pt(before_pt)
    pf.space_after = Pt(after_pt)


def main():
    parser = argparse.ArgumentParser(
        description="Bake SCI manuscript fonts (TNR) into a pandoc reference.docx."
    )
    parser.add_argument(
        "--template", default=str(TEMPLATE_PATH),
        help="baseline reference.docx to read (default: skill templates/reference.docx)")
    parser.add_argument(
        "--output", default=str(Path.cwd() / "reference.docx"),
        help="where to write the styled docx (default: ./reference.docx in CWD)")
    args = parser.parse_args()

    template_path = Path(args.template).resolve()
    output_path = Path(args.output).resolve()

    if not template_path.exists():
        raise SystemExit(
            f"baseline template not found: {template_path}\n"
            "regenerate it first:\n"
            "  pandoc --print-default-data-file reference.docx > templates/reference.docx"
        )

    doc = Document(str(template_path))
    styles = {s.name: s for s in doc.styles}

    applied = []
    for name, size in BODY_STYLES.items():
        if name in styles:
            set_style_font(styles[name], size)
            applied.append(f"{name} -> {FONT_NAME} {size}pt")

    for name, (size, bold) in HEADING_STYLES.items():
        if name in styles:
            set_style_font(styles[name], size, bold=bold)
            applied.append(f"{name} -> {FONT_NAME} {size}pt bold={bold}")

    for name, size in CAPTION_STYLES.items():
        if name in styles:
            set_style_font(styles[name], size)
            applied.append(f"{name} -> {FONT_NAME} {size}pt (caption/abstract layer)")

    # 正文段前段后清零（字体已在上面设好，这里只动间距）。
    for name in ZERO_SPACING_STYLES:
        if name in styles:
            set_para_spacing(styles[name], 0, 0)
            applied.append(f"{name} -> spacing before/after 0pt")
    # Bibliography 显式补回 space_after（否则继承已清零的 Normal 导致条目粘连）。
    if "Bibliography" in styles:
        set_para_spacing(styles["Bibliography"], 0, BIBLIOGRAPHY_AFTER_PT)
        applied.append(f"Bibliography -> spacing after {BIBLIOGRAPHY_AFTER_PT}pt (anti-stick)")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))

    print(f"wrote {output_path}")
    for line in applied:
        print("  " + line)


if __name__ == "__main__":
    main()
