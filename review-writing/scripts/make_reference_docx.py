#!/usr/bin/env python3
"""Bake the docx style template for Phase 4 export.

Takes the pandoc default reference.docx (generated via
`pandoc --print-default-data-file reference.docx > templates/reference.docx`)
and locks the typography to the English-review house style:

  - Body styles (Normal / Body Text / First Paragraph): Times New Roman 12pt.
  - Heading styles: Times New Roman, bold, with descending sizes.

Both the ASCII font and the eastAsia font are set so an occasional CJK glyph
(e.g. a species author name) cannot trigger a fallback to a different face.

Idempotent: re-running on an already-baked template produces the same result.
Run after regenerating the pandoc default to re-apply the house style.
"""

import argparse
from pathlib import Path

from docx import Document
from docx.shared import Pt
from docx.oxml.ns import qn

# --- House-style constants (single source of truth) -------------------------
BODY_FONT = "Times New Roman"   # ASCII/Latin face for all text
EASTASIA_FONT = "Times New Roman"  # force CJK runs onto the same face (anti-fallback)
BODY_SIZE_PT = 12

# Paragraph styles that carry running body text.
BODY_STYLES = ["Normal", "Body Text", "First Paragraph"]

# Zero the paragraph before/after spacing on body styles so exported prose has
# no inter-paragraph gaps. Compact keeps its own small list spacing (untouched).
# Bibliography is basedOn Normal, so it would inherit the zeroed spacing and glue
# entries together — restore an explicit after-gap so refs stay separated.
BIBLIOGRAPHY_AFTER_PT = 6

# Heading style -> point size. All headings are bold TNR.
HEADING_SIZES = {
    "Title": 18,
    "Heading 1": 16,
    "Heading 2": 14,
    "Heading 3": 12,
}

# 图注/表注/摘要:比正文小一号(10pt),从正文尺寸里独立出来。
CAPTION_SIZES = {"Image Caption": 10, "Table Caption": 10, "Abstract": 10}

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "reference.docx"


def _set_font(style, *, size_pt, bold=None):
    """Apply font face + size (+ optional bold) to a paragraph style.

    Sets the ASCII run font via python-docx, then writes the eastAsia attribute
    directly on the rFonts element so CJK glyphs use the same face instead of
    silently falling back to a default CJK font.
    """
    font = style.font
    font.name = BODY_FONT
    font.size = Pt(size_pt)
    if bold is not None:
        font.bold = bold

    # rPr/rFonts may not exist on a bare style; get_or_add creates them.
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), EASTASIA_FONT)
    rfonts.set(qn("w:ascii"), BODY_FONT)
    rfonts.set(qn("w:hAnsi"), BODY_FONT)


def _set_para_spacing(style, before_pt, after_pt):
    pf = style.paragraph_format
    pf.space_before = Pt(before_pt)
    pf.space_after = Pt(after_pt)


def main():
    parser = argparse.ArgumentParser(
        description="Bake the English-review house style into a pandoc reference.docx."
    )
    parser.add_argument(
        "--template", default=str(TEMPLATE),
        help="baseline reference.docx to read (default: skill templates/reference.docx)")
    parser.add_argument(
        "--output", default=str(Path.cwd() / "reference.docx"),
        help="where to write the styled docx (default: ./reference.docx in CWD)")
    args = parser.parse_args()

    template_path = Path(args.template).resolve()
    output_path = Path(args.output).resolve()

    if not template_path.exists():
        raise SystemExit(
            f"Base template not found: {template_path}\n"
            "Generate it first:\n"
            "  pandoc --print-default-data-file reference.docx > "
            f"{template_path}"
        )

    doc = Document(str(template_path))
    style_names = {s.name for s in doc.styles}

    for name in BODY_STYLES:
        if name in style_names:
            _set_font(doc.styles[name], size_pt=BODY_SIZE_PT)
            _set_para_spacing(doc.styles[name], 0, 0)

    # Bibliography inherits zeroed Normal → restore an explicit after-gap so
    # reference entries don't glue together. Compact keeps its own spacing.
    if "Bibliography" in style_names:
        _set_para_spacing(doc.styles["Bibliography"], 0, BIBLIOGRAPHY_AFTER_PT)

    for name, size in HEADING_SIZES.items():
        if name in style_names:
            _set_font(doc.styles[name], size_pt=size, bold=True)

    for name, size in CAPTION_SIZES.items():
        if name in style_names:
            _set_font(doc.styles[name], size_pt=size)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    print(f"Baked house style into {output_path}")
    print(f"  body styles  {BODY_STYLES} -> {BODY_FONT} {BODY_SIZE_PT}pt")
    for name, size in HEADING_SIZES.items():
        print(f"  {name:<10} -> {BODY_FONT} {size}pt bold")


if __name__ == "__main__":
    main()
