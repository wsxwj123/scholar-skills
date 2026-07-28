import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Default pandoc reference template bundled with this skill: locks body to
# Times New Roman 12pt and headings to TNR bold (see make_reference_docx.py).
# Resolved relative to this script's skill directory so it works regardless of cwd.
DEFAULT_REFERENCE_DOC = Path(__file__).resolve().parent.parent / "templates" / "reference.docx"

DEFAULT_PATTERNS = [
    "01_Abstract*.md",
    "02_Introduction*.md",
    "03_Methods*.md",
    "04_Results*.md",
    "05_Discussion*.md",
    "06_Conclusion*.md",
    "07_References*.md",
    "*.md",
]


def expand_citation_numbers(raw):
    out = []
    for part in re.split(r"[;,]", str(raw)):
        item = part.strip()
        if not item:
            continue
        m = re.match(r"^(\d+)\s*-\s*(\d+)$", item)
        if m:
            a = int(m.group(1))
            b = int(m.group(2))
            if a <= b:
                out.extend(range(a, b + 1))
            else:
                out.extend(range(b, a + 1))
            continue
        if item.isdigit():
            out.append(int(item))
    # stable unique
    seen = set()
    uniq = []
    for n in out:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq


def collect_citation_numbers(text):
    numbers = []
    pattern = re.compile(r"\[(\d+(?:\s*[-,;]\s*\d+)*)\]")
    for m in pattern.finditer(text or ""):
        numbers.extend(expand_citation_numbers(m.group(1)))
    seen = set()
    uniq = []
    for n in numbers:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq


def natural_key(text):
    return [int(tok) if tok.isdigit() else tok.lower() for tok in re.split(r"(\d+)", text)]


def leading_index(path):
    name = os.path.basename(path)
    m = re.match(r"^\s*(\d+)", name)
    return int(m.group(1)) if m else 9999


def discover_markdown_files(manuscript_dir, patterns):
    included = []
    seen = set()
    for pattern in patterns:
        for path in sorted(glob.glob(os.path.join(manuscript_dir, pattern)), key=natural_key):
            name = os.path.basename(path)
            if name.lower() in {"full_manuscript.md"}:
                continue
            if path in seen:
                continue
            seen.add(path)
            included.append(path)
    included.sort(key=lambda p: (leading_index(p), natural_key(os.path.basename(p))))
    return included


def load_references(index_file):
    if not os.path.exists(index_file):
        return []
    with open(index_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("references", "items", "entries", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def format_reference_entry(entry, number, style="vancouver"):
    if not isinstance(entry, dict):
        return f"{number}. {str(entry).strip()}"
    citation = str(entry.get("citation") or "").strip()
    if citation:
        return f"{number}. {citation}"
    if style == "nature":
        authors = entry.get("authors") or entry.get("author") or "Unknown Author"
        title = entry.get("title") or "Untitled"
        journal = entry.get("journal") or "Unknown Journal"
        year = entry.get("year") or "n.d."
        volume = entry.get("volume") or ""
        pages = entry.get("pages") or ""
        vol_pages = f"{volume}, {pages}".strip(", ").strip()
        if vol_pages:
            return f"{number}. {authors}. {title}. {journal} {vol_pages} ({year})."
        return f"{number}. {authors}. {title}. {journal} ({year})."
    authors = entry.get("authors") or entry.get("author") or "Unknown Author"
    title = entry.get("title") or "Untitled"
    journal = entry.get("journal") or "Unknown Journal"
    year = entry.get("year") or "n.d."
    volume = entry.get("volume") or ""
    pages = entry.get("pages") or ""
    tail = f"{year};{volume}:{pages}".strip(":").strip(";")
    doi = entry.get("doi") or ""
    doi_part = f" doi:{doi}" if doi else ""
    if tail:
        return f"{number}. {authors}. {title}. {journal}. {tail}.{doi_part}".rstrip()
    return f"{number}. {authors}. {title}. {journal}.{doi_part}".rstrip()


def split_out_references_section(content):
    """Remove markdown References/参考文献 block and return body + extracted entries."""
    lines = content.splitlines()
    out = []
    refs = []
    in_refs = False
    current = None
    ref_heading = re.compile(r"^\s{0,3}#{1,6}\s*(references|参考文献)\s*$", re.IGNORECASE)
    next_heading = re.compile(r"^\s{0,3}#{1,6}\s+")
    numbered = re.compile(r"^\s*(\d+)\.\s+(.*)\s*$")
    for line in lines:
        if not in_refs and ref_heading.match(line):
            in_refs = True
            current = None
            continue
        if in_refs:
            if next_heading.match(line):
                in_refs = False
                current = None
                out.append(line)
                continue
            m = numbered.match(line)
            if m:
                refs.append(m.group(2).strip())
                current = len(refs) - 1
                continue
            if current is not None and line.strip():
                refs[current] = (refs[current] + " " + line.strip()).strip()
            continue
        out.append(line)
    body = "\n".join(out).strip()
    return body, refs


def merge_markdown_files(files, relocate_references=False):
    parts = []
    local_refs = []
    for file_path in files:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if relocate_references:
            content, refs = split_out_references_section(content)
            local_refs.extend(refs)
        if content:
            parts.append(content)
    merged = "\n\n---\n\n".join(parts).strip() + ("\n" if parts else "")
    return merged, local_refs


def validate_merge_precheck(files, index_file):
    report = {
        "ok": True,
        "index_file": index_file,
        "references_count": 0,
        "citations_used": [],
        "out_of_range": [],
        "warnings": [],
        "errors": [],
    }
    refs = load_references(index_file) if index_file else []
    report["references_count"] = len(refs)
    if len(refs) == 0:
        report["warnings"].append("literature_index is missing or empty; citation range check skipped")
        return report

    used = []
    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            used.extend(collect_citation_numbers(text))
        except Exception as e:
            report["warnings"].append(f"failed reading {path}: {e}")
    seen = set()
    uniq = []
    for n in used:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    uniq.sort()
    report["citations_used"] = uniq
    report["out_of_range"] = [n for n in uniq if n < 1 or n > len(refs)]
    if report["out_of_range"]:
        report["ok"] = False
        report["errors"].append(
            f"citation numbers out of range: {report['out_of_range'][:20]}, references_count={len(refs)}"
        )
    return report


def convert_docx(output_md, output_docx, reference_doc=None):
    pandoc_bin = shutil.which("pandoc")
    if not pandoc_bin:
        return {
            "attempted": False,
            "ok": False,
            "reason": "pandoc_not_found",
            "message": "Pandoc not found in PATH. Docx generation skipped."
        }
    cmd = [pandoc_bin, "-f", "markdown+superscript+subscript", output_md, "-o", output_docx]
    if reference_doc:
        cmd.extend(["--reference-doc", reference_doc])
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
        return {"attempted": True, "ok": True, "output_docx": output_docx}
    except subprocess.CalledProcessError as e:
        return {
            "attempted": True,
            "ok": False,
            "reason": "pandoc_failed",
            "stderr": (e.stderr or "").strip()
        }


def run_merge(
    manuscript_dir,
    output_md,
    output_docx,
    patterns,
    generate_docx,
    reference_doc=None,
    allow_empty=False,
    skip_precheck=False,
):
    if not os.path.isdir(manuscript_dir):
        return {"ok": False, "error": f"manuscript_dir not found: {manuscript_dir}"}

    files = discover_markdown_files(manuscript_dir, patterns)
    if not files and not allow_empty:
        return {"ok": False, "error": "no manuscript markdown files matched patterns", "patterns": patterns}

    index_file = os.path.join(os.path.dirname(output_md) or ".", "literature_index.json")
    if not os.path.exists(index_file):
        index_file = "literature_index.json"

    precheck = validate_merge_precheck(files, index_file=index_file) if not skip_precheck else {
        "ok": True,
        "skipped": True,
        "reason": "skip_precheck",
    }
    if not precheck.get("ok", False):
        return {
            "ok": False,
            "error": "merge_precheck_failed",
            "precheck": precheck,
            "files_merged_count": len(files),
            "files_merged": files,
        }

    merged, local_refs = merge_markdown_files(files, relocate_references=True)
    global_refs = load_references(index_file)
    if not global_refs:
        global_refs = load_references("literature_index.json")

    reference_lines = []
    if global_refs:
        reference_lines = [format_reference_entry(ref, i + 1, style="vancouver") for i, ref in enumerate(global_refs)]
    elif local_refs:
        # fallback: de-duplicate local references while keeping order
        seen = set()
        for r in local_refs:
            key = r.strip().lower()
            if key and key not in seen:
                seen.add(key)
                reference_lines.append(f"{len(reference_lines) + 1}. {r.strip()}")

    if reference_lines:
        merged = merged.rstrip() + "\n\n# References\n\n" + "\n".join(reference_lines) + "\n"
    os.makedirs(os.path.dirname(output_md) or ".", exist_ok=True)
    banner = "<!-- AUTO-GENERATED by merge_manuscript.py — DO NOT EDIT MANUALLY; run /merge to regenerate -->\n\n"
    with open(output_md, "w", encoding="utf-8") as f:
        f.write(banner + merged)

    result = {
        "ok": True,
        "manuscript_dir": manuscript_dir,
        "output_md": output_md,
        "files_merged_count": len(files),
        "files_merged": files,
        "precheck": precheck,
        "references_relocated": True,
        "references_count": len(reference_lines),
        "docx": {"attempted": False, "ok": False},
    }

    if generate_docx:
        # 模板是已提交的样式资产，缺失=安装损坏。硬失败让用户重生成，
        # 不要 silently 产出字体不受控的 docx。仅 docx 步骤失败，md 已落盘不受影响。
        if not DEFAULT_REFERENCE_DOC.exists() and (
            reference_doc is None or not os.path.exists(reference_doc)
        ):
            missing = reference_doc if reference_doc else str(DEFAULT_REFERENCE_DOC)
            result["ok"] = False
            result["docx"] = {
                "attempted": False,
                "ok": False,
                "reason": "reference_doc_missing",
                "message": (
                    f"reference.docx 模板缺失: {missing}。"
                    "请先运行 `python scripts/make_reference_docx.py` 重新生成后再导出 docx。"
                    "（md 已生成，未产出 docx）"
                ),
            }
            return result
        docx_report = convert_docx(output_md=output_md, output_docx=output_docx, reference_doc=reference_doc)
        result["docx"] = docx_report
    return result


def parse_args():
    parser = argparse.ArgumentParser(description="Merge manuscript markdown files and optionally generate docx")
    parser.add_argument("--manuscript-dir", default="manuscripts", help="Directory containing section markdown files")
    parser.add_argument("--output-md", default=None, help="Output merged markdown path")
    parser.add_argument("--output-docx", default=None, help="Output docx path")
    parser.add_argument("--patterns", default=",".join(DEFAULT_PATTERNS), help="Comma-separated glob patterns")
    parser.add_argument("--skip-docx", action="store_true", help="Skip docx conversion")
    parser.add_argument("--skip-precheck", action="store_true", help="Skip merge consistency precheck")
    parser.add_argument(
        "--reference-doc",
        default=None,
        help="Pandoc reference docx template (defaults to bundled templates/reference.docx if present)",
    )
    parser.add_argument("--allow-empty", action="store_true", help="Allow producing an empty merged file")
    return parser.parse_args()


def main():
    args = parse_args()
    output_md = args.output_md or os.path.join(args.manuscript_dir, "Full_Manuscript.md")
    output_docx = args.output_docx or os.path.join(args.manuscript_dir, "Full_Manuscript.docx")
    patterns = [p.strip() for p in args.patterns.split(",") if p.strip()]

    # Default to the bundled TNR-12pt reference template. If it (or an explicit
    # --reference-doc) is missing when producing docx, run_merge hard-fails so we
    # never emit an uncontrolled-font docx — see the docx branch in run_merge.
    reference_doc = args.reference_doc
    if reference_doc is None and DEFAULT_REFERENCE_DOC.exists():
        reference_doc = str(DEFAULT_REFERENCE_DOC)
    report = run_merge(
        manuscript_dir=args.manuscript_dir,
        output_md=output_md,
        output_docx=output_docx,
        patterns=patterns,
        generate_docx=(not args.skip_docx),
        reference_doc=reference_doc,
        allow_empty=args.allow_empty,
        skip_precheck=args.skip_precheck,
    )
    print(json.dumps(report, ensure_ascii=False))
    if not report.get("ok", False):
        sys.exit(2)


if __name__ == "__main__":
    main()
