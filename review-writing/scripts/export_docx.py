#!/usr/bin/env python3
"""Phase 4 docx export: Final_Review.md -> Final_Review.docx via pandoc.

Wraps pandoc with the baked house-style template
(templates/reference.docx) and the markdown extensions the review's
character-level contract relies on:

  - superscript  (^...^)   e.g. 10^6^
  - subscript    (~...~)   e.g. H~2~O

Citations are optional: pass --bib (and optionally --csl) to run --citeproc.

Usage:
  python scripts/export_docx.py --md exports/Final_Review.md \
                                --out exports/Final_Review.docx \
                                [--bib exports/references.bib] [--csl style.csl]
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REFERENCE_DOCX = Path(__file__).resolve().parent.parent / "templates" / "reference.docx"


def build_pandoc_cmd(md, out, bib=None, csl=None):
    cmd = [
        "pandoc",
        "-f", "markdown+superscript+subscript",
        "--reference-doc", str(REFERENCE_DOCX),
    ]
    if bib:
        cmd += ["--citeproc", "--bibliography", str(bib)]
        if csl:
            cmd += ["--csl", str(csl)]
    cmd += [str(md), "-o", str(out)]
    return cmd


def main():
    ap = argparse.ArgumentParser(description="Export Final_Review.md to docx via pandoc.")
    ap.add_argument("--md", required=True, help="Input markdown (e.g. exports/Final_Review.md)")
    ap.add_argument("--out", required=True, help="Output docx (e.g. exports/Final_Review.docx)")
    ap.add_argument("--bib", help="BibTeX bibliography; enables --citeproc")
    ap.add_argument("--csl", help="CSL style file (only used with --bib)")
    args = ap.parse_args()

    if shutil.which("pandoc") is None:
        sys.exit(
            "ERROR: pandoc not found on PATH. Install it (e.g. `brew install pandoc`) "
            "and retry. docx export requires pandoc."
        )

    md = Path(args.md)
    if not md.exists():
        sys.exit(f"ERROR: input markdown not found: {md}")

    if not REFERENCE_DOCX.exists():
        sys.exit(
            f"ERROR: reference.docx 模板缺失: {REFERENCE_DOCX}\n"
            "请先运行 `python scripts/make_reference_docx.py` 重新生成后再导出 docx。"
        )

    if args.csl and not args.bib:
        sys.exit("ERROR: --csl requires --bib (citeproc is only enabled when a bibliography is given).")

    cmd = build_pandoc_cmd(md, args.out, args.bib, args.csl)
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(f"ERROR: pandoc failed (exit {e.returncode}). Command:\n  {' '.join(cmd)}")

    print(f"Exported {args.out}")


if __name__ == "__main__":
    main()
