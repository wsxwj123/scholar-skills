import argparse
import json
import os
import re
import sys


def load_references(index_file):
    with open(index_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("references", "items", "entries", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    raise ValueError("unsupported literature_index structure; expected list or dict with references/items/entries/data")


def bibtex_escape(value):
    text = str(value) if value is not None else ""
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def normalize_authors(ref):
    authors = ref.get("authors", ref.get("author", ""))
    if isinstance(authors, list):
        return " and ".join(str(x) for x in authors if x)
    return str(authors) if authors else ""


def normalize_cite_key(raw, fallback_idx):
    key = str(raw or "").strip()
    if not key:
        key = f"ref_{fallback_idx}"
    key = re.sub(r"[^A-Za-z0-9:_-]+", "_", key)
    return key[:80]


def build_entry(ref, idx):
    cite_key = normalize_cite_key(ref.get("ref_id") or ref.get("citation_key"), idx)
    title = ref.get("title") or ref.get("citation") or "Unknown Title"
    journal = ref.get("journal") or "Unknown Journal"
    year = ref.get("year") or "2024"
    doi = ref.get("doi") or ""
    authors = normalize_authors(ref)
    volume = ref.get("volume") or ""
    pages = ref.get("pages") or ""
    number = ref.get("number") or ref.get("issue") or ""

    lines = [
        f"@article{{{cite_key},",
        f"  title = {{{bibtex_escape(title)}}},",
        f"  journal = {{{bibtex_escape(journal)}}},",
        f"  year = {{{bibtex_escape(year)}}},",
    ]
    if authors:
        lines.append(f"  author = {{{bibtex_escape(authors)}}},")
    if volume:
        lines.append(f"  volume = {{{bibtex_escape(volume)}}},")
    if number:
        lines.append(f"  number = {{{bibtex_escape(number)}}},")
    if pages:
        lines.append(f"  pages = {{{bibtex_escape(pages)}}},")
    if doi:
        lines.append(f"  doi = {{{bibtex_escape(doi)}}},")
    lines.append("}")
    return "\n".join(lines)


def convert_to_bibtex(index_file="literature_index.json", output_file="references.bib"):
    if not os.path.exists(index_file):
        return {"ok": False, "error": f"index file not found: {index_file}"}
    try:
        refs = load_references(index_file)
    except Exception as e:
        return {"ok": False, "error": f"failed to parse index: {e}"}

    entries = []
    for i, ref in enumerate(refs, 1):
        if isinstance(ref, dict):
            entries.append(build_entry(ref, i))

    try:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n\n".join(entries) + ("\n" if entries else ""))
    except Exception as e:
        return {"ok": False, "error": f"failed to write bibtex: {e}"}

    return {
        "ok": True,
        "index_file": index_file,
        "output_file": output_file,
        "references_input_count": len(refs),
        "references_exported_count": len(entries),
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Export literature index to BibTeX")
    parser.add_argument("--index-file", default="literature_index.json", help="Path to literature index JSON")
    parser.add_argument("--output-file", default="references.bib", help="Path to output .bib file")
    return parser.parse_args()


def main():
    args = parse_args()
    report = convert_to_bibtex(index_file=args.index_file, output_file=args.output_file)
    print(json.dumps(report, ensure_ascii=False))
    if not report.get("ok", False):
        sys.exit(2)


if __name__ == "__main__":
    main()
