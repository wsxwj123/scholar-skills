"""Generate / refresh the pandoc reference.docx that locks SCI manuscript fonts.

Opens templates/reference.docx (the pandoc baseline produced by
`pandoc --print-default-data-file reference.docx`) and forces key paragraph
styles to Times New Roman with explicit point sizes, so that `/merge`'s pandoc
export yields a docx whose body is TNR 12pt and whose headings are TNR bold.

The script is IDEMPOTENT: re-running it on an already-processed file produces
the same result. Run it after editing the FONT/SIZE constants below.

Usage:
    python scripts/make_reference_docx.py [--template BASE.docx] [--output OUT.docx]
    (default: 按候选位置找基准模板，写 ./reference.docx 到当前目录)

Requires: python-docx。基准模板**不需要事先存在**：一个候选位置都没有时本脚本会用
`pandoc --print-default-data-file reference.docx` 现产一份。此前它硬读
scripts/../templates/reference.docx，而 /init 部署后的项目里根本没有 templates/ 目录
—— merge 报"模板缺失，请跑 make_reference_docx.py"，make_reference_docx.py 又读同一个
缺失文件报错，补救成了死循环。
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from docx import Document
    from docx.shared import Pt
    from docx.oxml.ns import qn
except ImportError as exc:  # 环境问题给可操作提示，不要甩裸 traceback
    raise SystemExit(
        f"缺少 python-docx（{exc}）。装上再跑：\n"
        f"  {sys.executable} -m pip install python-docx\n"
        "（本脚本只在生成 docx 样式模板时需要它；不导出 docx 的流程不受影响）"
    )

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


def baseline_candidates():
    """基准模板可能在的位置，与 merge_manuscript.reference_doc_candidates() 对齐。"""
    seen, out = set(), []
    for p in (TEMPLATE_PATH,
              Path.cwd() / "templates" / "reference.docx",
              Path.cwd() / "reference.docx"):   # 上一次本脚本的产物，重跑幂等
        if str(p) not in seen:
            seen.add(str(p))
            out.append(p)
    return out


def make_pandoc_baseline(dest):
    """没有任何基准模板时，用 pandoc 现产一份 —— 补救路径不能读它自己要产的文件。"""
    pandoc = shutil.which("pandoc")
    if not pandoc:
        raise SystemExit(
            "基准模板在这些位置都找不到：\n  "
            + "\n  ".join(str(p) for p in baseline_candidates())
            + "\n且 PATH 里没有 pandoc，无法现产一份。二选一：\n"
            "  1) 装 pandoc（macOS: brew install pandoc）后重跑本脚本；\n"
            "  2) 从别处拷一份 reference.docx 过来，用 --template 指给本脚本。"
        )
    try:
        proc = subprocess.run([pandoc, "--print-default-data-file", "reference.docx"],
                              check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        raise SystemExit(
            f"pandoc 产基准模板失败（exit {e.returncode}）：\n"
            f"{(e.stderr or b'').decode('utf-8', 'replace').strip()}")
    dest.write_bytes(proc.stdout)
    return dest


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
        "--template", default=None,
        help="baseline reference.docx to read (默认按候选位置找，都没有就用 pandoc 现产)")
    parser.add_argument(
        "--output", default=str(Path.cwd() / "reference.docx"),
        help="where to write the styled docx (default: ./reference.docx in CWD)")
    args = parser.parse_args()

    output_path = Path(args.output).resolve()
    tmp_baseline = None

    if args.template:
        template_path = Path(args.template).resolve()
        if not template_path.exists():
            raise SystemExit(f"--template 指定的基准模板不存在: {template_path}")
    else:
        template_path = next((p.resolve() for p in baseline_candidates() if p.exists()), None)
        if template_path is None:
            # 关键：补救路径不再去读它自己要产的那个文件。
            tmp_baseline = Path(tempfile.mkdtemp(prefix="ref_docx_")) / "baseline.docx"
            template_path = make_pandoc_baseline(tmp_baseline)
            print(f"基准模板缺失，已用 pandoc 现产一份: {template_path}")

    doc = Document(str(template_path))
    if tmp_baseline:  # 现产的基准只是中转，读完即清
        shutil.rmtree(tmp_baseline.parent, ignore_errors=True)
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
