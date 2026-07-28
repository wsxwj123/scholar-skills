#!/usr/bin/env python3
"""Embedded-image extractor for .docx and .pdf manuscripts (canonical, shared
across polish-sci / revise-sci / sci2doc).

A .docx file is a zip archive; embedded images live under `word/media/`. This
script unzips that directory verbatim, drops the binaries into
`<project-root>/<figures-dir>/` with deterministic, ordered names
(`figure_01.<ext>`, `figure_02.<ext>`, ...), and writes an
`image_manifest.json` next to them.

A .pdf file is handled via PyMuPDF (`import fitz`): embedded raster images are
extracted by xref into the same `figures/` dir with the same naming scheme and
manifest shape. PyMuPDF is an optional dependency; if it is missing the script
degrades gracefully (prints a hint, exit 0, images_extracted=0) rather than
crashing the host pipeline.

No pixel inspection, no OCR, no image-content reasoning. Aligns with the rest
of the atomize/index pipeline: AI consumes text and structural metadata, not
pixels.

CLI:
  python3 extract_docx_images.py --manuscript <docx|pdf> --project-root <root>
                                 [--figures-dir figures]

Exit contract:
  - Always prints a single JSON line to stdout:
      {"ok": true, "images_extracted": N, "figures_dir": "<abs path>"}
  - exit 0 on success (N >= 0), including pymupdf-missing degrade case.
  - exit 1 only on hard errors (manuscript missing / not a zip-or-pdf).
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

# Ordering rule for the manifest. word/media/ entries appear in zip order,
# which for python-docx-produced files matches the rId order — close enough to
# document order for naming purposes. We intentionally preserve zip order
# rather than alpha-sorting because alpha-sort puts image10 before image2.
ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".jpe", ".gif", ".bmp", ".tif", ".tiff", ".emf", ".wmf", ".svg"}


def extract_pdf(manuscript: Path, figures_dir: Path) -> dict[str, Any]:
    """Extract embedded raster images from a PDF via PyMuPDF.

    Graceful degrade: if PyMuPDF is not installed, print a hint and return a
    no-op success so the host pipeline is never blocked.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("PDF extraction requires PyMuPDF (pip install pymupdf); skipping", file=sys.stderr)
        return {
            "ok": True,
            "images_extracted": 0,
            "figures_dir": str(figures_dir),
            "note": "pymupdf-missing",
        }

    manifest: list[dict[str, Any]] = []
    idx = 0
    seen_xrefs: set[int] = set()
    with fitz.open(manuscript) as doc:
        for page_num in range(doc.page_count):
            for img in doc.get_page_images(page_num, full=True):
                xref = img[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                extracted = doc.extract_image(xref)
                data = extracted["image"]
                ext = "." + extracted.get("ext", "png")
                idx += 1
                out_name = f"figure_{idx:02d}{ext}"
                out_path = figures_dir / out_name
                out_path.write_bytes(data)
                manifest.append({
                    "idx": idx,
                    "filename": out_name,
                    "size_kb": round(len(data) / 1024, 2),
                    "original_filename": f"xref_{xref}{ext}",
                    "source_page": page_num + 1,
                    "xref": xref,
                })

    manifest_path = figures_dir / "image_manifest.json"
    manifest_path.write_text(
        json.dumps({"source_pdf": str(manuscript), "count": idx, "images": manifest}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"ok": True, "images_extracted": idx, "figures_dir": str(figures_dir)}


def extract(manuscript: Path, project_root: Path, figures_subdir: str) -> dict[str, Any]:
    figures_dir = (project_root / figures_subdir).resolve()
    figures_dir.mkdir(parents=True, exist_ok=True)

    if manuscript.suffix.lower() == ".pdf":
        return extract_pdf(manuscript, figures_dir)

    if not zipfile.is_zipfile(manuscript):
        # Not a docx (could be a legacy .doc or a .md). Treat as no-op success.
        return {"ok": True, "images_extracted": 0, "figures_dir": str(figures_dir), "note": "manuscript is not a zip/docx"}

    manifest: list[dict[str, Any]] = []
    idx = 0
    with zipfile.ZipFile(manuscript, "r") as zf:
        media_entries = [n for n in zf.namelist() if n.startswith("word/media/") and not n.endswith("/")]
        # Preserve insertion order from the zip directory listing.
        for entry in media_entries:
            ext = Path(entry).suffix.lower()
            if ext not in ALLOWED_EXTS:
                # Unknown extension — keep it, but don't rename to .png.
                pass
            idx += 1
            out_name = f"figure_{idx:02d}{ext}"
            out_path = figures_dir / out_name
            data = zf.read(entry)
            out_path.write_bytes(data)
            manifest.append({
                "idx": idx,
                "filename": out_name,
                "size_kb": round(len(data) / 1024, 2),
                "original_filename": Path(entry).name,
                "zip_path": entry,
            })

    manifest_path = figures_dir / "image_manifest.json"
    manifest_path.write_text(
        json.dumps({"source_docx": str(manuscript), "count": idx, "images": manifest}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"ok": True, "images_extracted": idx, "figures_dir": str(figures_dir)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract embedded images from a .docx manuscript.")
    ap.add_argument("--manuscript", required=True, help="Path to the source .docx (or any path; non-zip is no-op).")
    ap.add_argument("--project-root", required=True, help="Project root; figures land under <root>/<figures-dir>/.")
    ap.add_argument("--figures-dir", default="figures", help="Subdirectory under project-root for image output (default: figures).")
    args = ap.parse_args()

    manuscript = Path(args.manuscript)
    project_root = Path(args.project_root)

    if not manuscript.exists():
        print(json.dumps({"ok": False, "error": f"manuscript not found: {manuscript}"}, ensure_ascii=False))
        return 1
    project_root.mkdir(parents=True, exist_ok=True)

    try:
        result = extract(manuscript, project_root, args.figures_dir)
    except Exception as exc:  # noqa: BLE001 — surface as JSON, never traceback
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 1

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
