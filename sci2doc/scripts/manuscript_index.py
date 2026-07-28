#!/usr/bin/env python3
"""Manuscript cross-reference index extractor (canonical, polish-sci).

Reverse-extracts figure and reference cross-indexes from a finished manuscript
(docx or md) for review and completeness checking. Output is an assistive hint,
not a red-line verifier: heuristic parsing is good but not 100 percent reliable.

Produces figure_index.json, reference_index.json, abbreviation_index.json and a
human-readable manuscript_index.md under the project root.

CLI:
  python manuscript_index.py --manuscript <docx|md> --project-root <root> [--units-dir units]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

# Self-contained: this script intentionally does NOT import from common.py.
# read_docx_paragraphs / normalize_ws / write_json / write_text are inlined
# verbatim from polish-sci/scripts/common.py so docx reading behaviour is
# identical across host skills. is_heading / looks_like_reference_entry use the
# local implementations below so index results are independent of each host
# skill's (forked) common.py and the file can be byte-shared across skills.
from docx import Document


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_docx_paragraphs(path: Path) -> list[dict[str, Any]]:
    doc = Document(str(path))
    rows: list[dict[str, Any]] = []
    for i, paragraph in enumerate(doc.paragraphs):
        text = normalize_ws(paragraph.text)
        if not text:
            continue
        style_name = normalize_ws(getattr(getattr(paragraph, "style", None), "name", "") or "")
        rows.append({"paragraph_index": i, "text": text, "style_name": style_name})
    return rows


# Markdown list-item prefix ("- ", "* ", "+ ", "• ") that wraps a reference
# entry in a review's per-chapter "## References" block. Stripped before any
# numbering/entry pattern is applied so "- [1] Author..." parses like "[1] ...".
LIST_PREFIX_RE = re.compile(r"^[-*+•]\s+")


def strip_list_prefix(text: str) -> str:
    return LIST_PREFIX_RE.sub("", text, count=1)


def looks_like_reference_entry(text: str) -> bool:
    candidate = strip_list_prefix(normalize_ws(text))
    lowered = candidate.lower()
    if re.search(r"\bdoi:\s*10\.", lowered) or re.search(r"\bpmid:\s*\d+", lowered):
        return True
    if re.match(r"^\[?\d+\]?[.)]?\s+", candidate):
        has_year = re.search(r"\b(19|20)\d{2}\b", candidate) is not None
        author_like = re.search(r"^\[?\d+\]?[.)]?\s+[A-Z][A-Za-z-]+(?:\s+[A-Z]\.)?", candidate) is not None
        if has_year and author_like:
            return True
    return False


def is_heading(row: dict[str, Any]) -> bool:
    style_name = row.get("style_name", "").lower()
    text = row.get("text", "")
    if style_name.startswith("heading"):
        return True
    if re.match(r"^\d+(?:\.\d+)*\.?\s+\S+", text) and not re.match(r"^(fig|figure|table)\b", text, flags=re.IGNORECASE) and not looks_like_reference_entry(text):
        return True
    if len(text.split()) <= 8 and text.lower() in {
        "abstract",
        "introduction",
        "background",
        "methods",
        "materials and methods",
        "results",
        "discussion",
        "conclusion",
        "supplementary methods",
        "supplementary results",
        "references",
        "reference",
        "acknowledgement",
        "acknowledgment",
        "data availability",
        "declaration of competing interest",
        "credit authorship contribution statement",
        "author contributions",
        "funding",
    }:
        return True
    return False


REFERENCE_HEADINGS = {"references", "reference", "参考文献", "bibliography", "literature cited"}


def _strip_heading_number(text: str) -> str:
    """Strip a leading section number from a heading, e.g. '9. References' ->
    'References', '6 参考文献' -> '参考文献'. Leaves un-numbered headings intact."""
    return re.sub(r"^\d+(?:\.\d+)*[.、]?\s*", "", text).strip()

# In-text figure reference, capturing the figure number. Matches "Figure 1",
# "Fig. 2", "Fig 3", "图 4". A trailing panel letter (1A) is allowed but the
# number alone is captured for keying.
FIG_INTEXT_RE = re.compile(r"\b(?:Figure|Fig\.?)\s*(\d+)|图\s*(\d+)", re.IGNORECASE)
# Caption paragraph starts with "Figure N." or "Figure N:" (or 图 N.).
FIG_CAPTION_RE = re.compile(r"^(?:Figure|Fig\.?)\s*(\d+)\s*[.:]\s*(\S.*)$|^图\s*(\d+)\s*[.:：]\s*(\S.*)$", re.IGNORECASE)
# Bare figure title paragraph holds only "Figure N" with nothing meaningful after.
FIG_BARE_RE = re.compile(r"^(?:Figure|Fig\.?)\s*(\d+)\s*$|^图\s*(\d+)\s*$", re.IGNORECASE)

# Bracketed in-text citation group: [11], [2,3], [20-22], [1, 2; 4-6].
CITATION_GROUP_RE = re.compile(r"\[((?:\d+\s*[-–—,;]?\s*)+\d*)\]")
# Numbered reference entry prefix: "[1] ...", "1. ...", "1) ...", "1 ...".
REF_NUMBER_PREFIX_RE = re.compile(r"^\[?(\d+)\]?[.)]?\s+(\S.*)$")

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)", re.IGNORECASE)
PMID_RE = re.compile(r"\bPMID:\s*(\d+)", re.IGNORECASE)

# Abbreviations exempt from first-use definition (kept in sync with
# general-sci-writing/scripts/state_manager.py UNIVERSAL_ABBREVIATIONS; update
# both when the whitelist changes).
UNIVERSAL_ABBREVIATIONS = {
    "DNA", "RNA", "PCR", "HIV", "WHO", "FDA", "NIH", "USA", "UK", "EU",
    "AI", "ML", "API", "URL", "PDF", "HTML", "JSON", "XML", "CSV",
    "ATP", "ADP", "GTP", "NADH", "NADPH", "CO2", "H2O", "NaCl",
    "PH", "RNA-SEQ", "DNA-SEQ", "CHIP-SEQ", "RT-PCR", "QPCR", "ELISA",
    "FACS", "FISH", "GFP", "RFP", "BSA", "PBS", "DMSO", "EDTA",
    "SD", "SEM", "CI", "OD", "MW", "KDA", "BP", "KB",
}

# First-use definition pattern, both "Full Name (ABBR)" and the Chinese form
# "中文全称（English Full Name, ABBR）". Half-width and full-width parens are both
# accepted; the parenthetical may carry an English full name and a comma before
# the abbreviation. ABBR is upper-led, 2-10 chars (uppercase / digit / hyphen).
ABBR_DEF_RE = re.compile(
    r"([A-Za-z一-鿿][\w一-鿿\-/]*"
    r"(?:[ ,][A-Za-z一-鿿][\w一-鿿\-/]*){0,6})"
    r"\s*[(（]\s*(?:[^)）]*?,\s*)?([A-Z][A-Z0-9\-]{1,9})\s*[)）]"
)
# Bare abbreviation token: upper-led, 2-10 chars, not bounded by alphanumerics
# (so it also fires when adjacent to CJK characters, where \b would not).
BARE_ABBR_RE = re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Z0-9\-]{1,9})(?![A-Za-z0-9])")

# Orphan types that should block delivery vs. soft warnings only.
ABBR_HARD_ORPHANS = {"undefined_use", "duplicate_definition", "title_abbreviation"}

# Leading function words trimmed from a heuristic full-name capture so the
# displayed name does not bleed sentence remnants from before the term.
_FULLNAME_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "we", "this", "that", "these",
    "those", "in", "on", "for", "with", "to", "by", "is", "was", "were",
    "are", "as", "at", "from", "using", "used", "via", "here",
}


def trim_full_name(name: str) -> str:
    """Heuristically tidy a captured full name: keep the last few tokens (the
    ones adjacent to the abbreviation) and drop leading function words. CJK
    names without spaces are returned unchanged."""
    parts = name.split()
    if len(parts) <= 1:
        return name
    parts = parts[-5:]
    while parts and parts[0].lower() in _FULLNAME_STOPWORDS:
        parts = parts[1:]
    return " ".join(parts) if parts else name


def read_manuscript_paragraphs(path: Path) -> list[dict[str, Any]]:
    """Return paragraph rows with text/style_name. docx reuses common reader;
    md is split on blank lines into blocks."""
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return read_docx_paragraphs(path)
    if suffix in {".md", ".markdown", ".txt"}:
        return read_md_paragraphs(path)
    raise ValueError(f"unsupported manuscript type: {suffix}")


def read_md_paragraphs(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    rows: list[dict[str, Any]] = []
    block_lines: list[str] = []
    para_index = 0

    def flush() -> None:
        nonlocal para_index, block_lines
        joined = normalize_ws(" ".join(block_lines))
        if joined:
            heading_level = block_lines and block_lines[0].lstrip().startswith("#")
            style = "Heading" if heading_level else "Normal"
            rows.append({"paragraph_index": para_index, "text": joined, "style_name": style})
            para_index += 1
        block_lines = []

    # Reference lists are conventionally one entry per line with no blank line
    # between entries. Blank-line blocking would glue the whole list into one
    # paragraph, so once the References heading is seen each non-blank line
    # becomes its own paragraph.
    def emit_heading(text: str) -> None:
        # Markdown heading -> its own Heading-styled paragraph. Emitted directly
        # (not via flush, which sniffs a leading '#') so the stored text is clean
        # while style stays "Heading", letting is_heading() terminate a reference
        # span even for non-whitelisted chapter titles (e.g. CJK headings).
        nonlocal para_index
        flush()
        cleaned = normalize_ws(text)
        if cleaned:
            rows.append({"paragraph_index": para_index, "text": cleaned, "style_name": "Heading"})
            para_index += 1

    in_references = False
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        is_md_heading = stripped.startswith("#")
        clean = re.sub(r"^#{1,6}\s*", "", line)
        if is_md_heading:
            # A new heading ends any preceding chapter's reference list.
            in_references = _strip_heading_number(normalize_ws(clean).lower()) in REFERENCE_HEADINGS
            emit_heading(clean)
            continue
        if in_references:
            flush()
            block_lines.append(clean)
            flush()
        else:
            block_lines.append(clean)
    flush()
    return rows


def unit_label_for(row_idx: int, units_map: dict[int, str] | None, seq_no: int) -> str:
    """cited_by label: unit idx when a units dir maps this paragraph, else the
    sequential body paragraph number."""
    if units_map is not None and row_idx in units_map:
        return units_map[row_idx]
    return f"p{seq_no}"


def load_units_map(units_dir: Path | None) -> dict[int, str] | None:
    """Map manuscript paragraph_index -> unit idx, if a polish-sci units dir is
    present. Each units/<idx>.json is expected to carry a paragraph_index (or
    source_paragraph_index) field linking it back to the manuscript paragraph."""
    if units_dir is None or not units_dir.exists():
        return None
    mapping: dict[int, str] = {}
    for unit_file in sorted(units_dir.glob("*.json")):
        try:
            data = json.loads(unit_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        idx = data.get("idx")
        if idx is None:
            idx = unit_file.stem
        for key in ("paragraph_index", "source_paragraph_index", "para_index"):
            if isinstance(data.get(key), int):
                mapping[data[key]] = str(idx)
                break
    return mapping or None


def expand_citation_group(group_text: str) -> list[int]:
    """Expand a bracket group like '1, 2; 4-6' into [1,2,4,5,6]."""
    numbers: list[int] = []
    for part in re.split(r"[,;]", group_text):
        part = part.strip()
        if not part:
            continue
        rng = re.match(r"^(\d+)\s*[-–—]\s*(\d+)$", part)
        if rng:
            lo, hi = int(rng.group(1)), int(rng.group(2))
            if lo <= hi and hi - lo < 500:
                numbers.extend(range(lo, hi + 1))
        elif part.isdigit():
            numbers.append(int(part))
    return numbers


def find_reference_section_starts(rows: list[dict[str, Any]]) -> list[int]:
    """All References-heading row indices. A review keeps one '## References'
    per chapter, so there can be many; legacy single-section manuscripts return
    a one-element list."""
    return [
        i
        for i, row in enumerate(rows)
        if _strip_heading_number(normalize_ws(row.get("text", "")).lower())
        in REFERENCE_HEADINGS
    ]


def reference_section_spans(rows: list[dict[str, Any]]) -> list[tuple[int, int]]:
    """For each References heading, the [start, end) row span covering its
    entries: from the heading row up to the next non-reference heading (or EOF).
    Used to carve reference blocks out of the body for figure/abbr scanning."""
    starts = find_reference_section_starts(rows)
    spans: list[tuple[int, int]] = []
    for start in starts:
        end = len(rows)
        for j in range(start + 1, len(rows)):
            text = normalize_ws(rows[j].get("text", ""))
            if not text:
                continue
            if is_heading(rows[j]) and _strip_heading_number(text.lower()) not in REFERENCE_HEADINGS:
                end = j
                break
        spans.append((start, end))
    return spans


def body_row_indices(rows: list[dict[str, Any]], ref_spans: list[tuple[int, int]]) -> list[int]:
    """Body row indices = all rows not inside any reference span. Body between
    two chapters' reference blocks is still body, so figures/abbreviations after
    the first '## References' are not dropped."""
    in_ref = [False] * len(rows)
    for start, end in ref_spans:
        for i in range(start, end):
            in_ref[i] = True
    return [i for i in range(len(rows)) if not in_ref[i]]


def _reference_entry_rows(rows: list[dict[str, Any]], ref_spans: list[tuple[int, int]]) -> list[str]:
    """Collect candidate entry texts (list prefix stripped) from every reference
    span, in document order."""
    texts: list[str] = []
    for start, end in ref_spans:
        for i in range(start + 1, end):
            text = normalize_ws(rows[i].get("text", ""))
            if not text or text.lower() in REFERENCE_HEADINGS:
                continue
            texts.append(strip_list_prefix(text))
    return texts


def parse_references(rows: list[dict[str, Any]], ref_spans: list[tuple[int, int]]) -> list[dict[str, Any]]:
    """Parse reference entries across ALL References sections (a review has one
    per chapter). Supports explicit numbering ([n]/n./n, optionally wrapped in a
    markdown list prefix) and, when entries carry no number prefix, falls back to
    list position as the reference number (1-based). Numbers are deduplicated by
    value: chapter blocks that each restart at [1] collapse onto one entry."""
    entry_texts = _reference_entry_rows(rows, ref_spans)

    explicit_numbered = sum(1 for text in entry_texts if REF_NUMBER_PREFIX_RE.match(text))
    use_position = explicit_numbered < 3  # fall back to positional numbering

    entries: list[dict[str, Any]] = []
    seen_numbers: set[int] = set()
    position = 0
    for text in entry_texts:
        if use_position:
            if not looks_like_reference_entry(text) and not _looks_like_unnumbered_entry(text):
                continue
            position += 1
            ref_number = position
            raw_entry = text
        else:
            m = REF_NUMBER_PREFIX_RE.match(text)
            if not m:
                continue
            ref_number = int(m.group(1))
            raw_entry = m.group(2)
            if ref_number in seen_numbers:
                continue
            seen_numbers.add(ref_number)
        entries.append(
            {
                "ref_number": ref_number,
                "raw_entry": raw_entry,
                "doi": (DOI_RE.search(text).group(1) if DOI_RE.search(text) else None),
                "pmid": (PMID_RE.search(text).group(1) if PMID_RE.search(text) else None),
                "cited_by": [],
                "orphan_type": None,
            }
        )
    return entries


def _looks_like_unnumbered_entry(text: str) -> bool:
    """Heuristic for an unnumbered reference line (author-led, journal-marked or
    year-bearing). Used only in positional mode."""
    text = strip_list_prefix(text)
    if re.search(r"\bdoi:|\b10\.\d{4,9}/|\[J\]|\[C\]|\[M\]", text, re.IGNORECASE):
        return True
    has_year = re.search(r"\b(18|19|20)\d{2}\b", text) is not None
    author_led = re.match(r"^[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]*)*[,\s]", text) is not None
    return has_year and author_led


def build_figure_index(
    rows: list[dict[str, Any]],
    ref_spans: list[tuple[int, int]],
    units_map: dict[int, str] | None,
) -> list[dict[str, Any]]:
    body_indices = body_row_indices(rows, ref_spans)

    captions: dict[int, str] = {}
    caption_rows: set[int] = set()
    for i in range(len(rows)):
        text = normalize_ws(rows[i].get("text", ""))
        m = FIG_CAPTION_RE.match(text)
        if m:
            fig_no = int(m.group(1) or m.group(3))
            caption_body = (m.group(2) or m.group(4) or "").strip()
            # keep the full caption paragraph text as caption
            captions.setdefault(fig_no, normalize_ws(f"{text}"))
            caption_rows.add(i)

    cited_by: dict[int, list[str]] = {}
    seq_no = 0
    for i in body_indices:
        text = normalize_ws(rows[i].get("text", ""))
        if not text:
            continue
        seq_no += 1
        if i in caption_rows or FIG_BARE_RE.match(text):
            continue  # caption / bare title paragraph is not an in-text citation
        seen_in_para: set[int] = set()
        for m in FIG_INTEXT_RE.finditer(text):
            fig_no = int(m.group(1) or m.group(2))
            if fig_no in seen_in_para:
                continue
            seen_in_para.add(fig_no)
            label = unit_label_for(i, units_map, seq_no)
            cited_by.setdefault(fig_no, [])
            if label not in cited_by[fig_no]:
                cited_by[fig_no].append(label)

    all_figs = sorted(set(captions) | set(cited_by))
    index: list[dict[str, Any]] = []
    for fig_no in all_figs:
        has_caption = fig_no in captions
        cites = cited_by.get(fig_no, [])
        if cites and not has_caption:
            orphan = "cited_no_caption"
        elif has_caption and not cites:
            orphan = "caption_not_cited"
        else:
            orphan = None
        index.append(
            {
                "figure_id": f"Figure {fig_no}",
                "caption": captions.get(fig_no, ""),
                "cited_by": cites,
                "caption_found": has_caption,
                "orphan_type": orphan,
            }
        )
    return index


def build_reference_index(
    rows: list[dict[str, Any]],
    ref_spans: list[tuple[int, int]],
    units_map: dict[int, str] | None,
) -> dict[str, Any]:
    if not ref_spans:
        return {
            "entries": [],
            "summary": {"total_refs": 0, "total_intext_citations": 0, "orphans": 0},
        }

    entries = parse_references(rows, ref_spans)
    entry_by_number = {e["ref_number"]: e for e in entries}

    cited_numbers: set[int] = set()
    total_intext = 0
    seq_no = 0
    for i in body_row_indices(rows, ref_spans):
        text = normalize_ws(rows[i].get("text", ""))
        if not text:
            continue
        seq_no += 1
        label = unit_label_for(i, units_map, seq_no)
        for m in CITATION_GROUP_RE.finditer(text):
            for num in expand_citation_group(m.group(1)):
                total_intext += 1
                cited_numbers.add(num)
                target = entry_by_number.get(num)
                if target is not None and label not in target["cited_by"]:
                    target["cited_by"].append(label)

    orphan_count = 0
    for entry in entries:
        if not entry["cited_by"]:
            entry["orphan_type"] = "entry_not_cited"
            orphan_count += 1

    cited_no_entry = sorted(n for n in cited_numbers if n not in entry_by_number)
    for num in cited_no_entry:
        entries.append(
            {
                "ref_number": num,
                "raw_entry": "",
                "doi": None,
                "pmid": None,
                "cited_by": [],
                "orphan_type": "cited_no_entry",
            }
        )
        orphan_count += 1

    entries.sort(key=lambda e: e["ref_number"])
    return {
        "entries": entries,
        "summary": {
            "total_refs": len(entry_by_number),
            "total_intext_citations": total_intext,
            "orphans": orphan_count,
        },
    }


def build_abbreviation_index(
    rows: list[dict[str, Any]],
    ref_spans: list[tuple[int, int]],
) -> list[dict[str, Any]]:
    """Reverse-extract an abbreviation cross-index from the manuscript body.

    Heuristic, not a red-line verifier. Detects first-use definitions
    (Full Name (ABBR) / 中文全称（English Full Name, ABBR）) and bare ABBR uses,
    then flags orphans:
      - undefined_use: bare ABBR used, never defined, not whitelisted
      - duplicate_definition: defined more than once (re-expanded)
      - title_abbreviation: a non-whitelisted ABBR appears in the title
      - defined_unused: defined but never used again (soft warning)
    """
    body_indices = body_row_indices(rows, ref_spans)

    # Title = first non-empty paragraph. A finished manuscript's first paragraph
    # is the title. (md parsing strips '#' markers, so a Heading style is not
    # reliably present; the first paragraph is the robust anchor.)
    title_text = normalize_ws(rows[0].get("text", "")) if rows else ""

    title_abbrs: set[str] = set()
    for m in BARE_ABBR_RE.finditer(title_text):
        abbr = m.group(1).upper()
        if abbr not in UNIVERSAL_ABBREVIATIONS:
            title_abbrs.add(abbr)

    defs: dict[str, list[tuple[str, str]]] = {}  # abbr -> [(label, full_name)]
    uses: dict[str, int] = {}
    first_use: dict[str, str] = {}
    seq_no = 0
    for i in body_indices:
        text = normalize_ws(rows[i].get("text", ""))
        if not text:
            continue
        seq_no += 1
        label = f"p{seq_no}"
        for m in ABBR_DEF_RE.finditer(text):
            full_name = trim_full_name(m.group(1).strip())
            abbr = m.group(2).strip().upper()
            defs.setdefault(abbr, []).append((label, full_name))
        # Strip definitions before counting bare uses so the defining
        # occurrence is not double-counted as a bare use.
        stripped = ABBR_DEF_RE.sub(" ", text)
        for m in BARE_ABBR_RE.finditer(stripped):
            abbr = m.group(1).upper()
            uses[abbr] = uses.get(abbr, 0) + 1
            first_use.setdefault(abbr, label)

    index: list[dict[str, Any]] = []
    for abbr in sorted(set(defs) | set(uses)):
        def_list = defs.get(abbr, [])
        def_count = len(def_list)
        use_count = uses.get(abbr, 0)
        is_universal = abbr in UNIVERSAL_ABBREVIATIONS
        if abbr in title_abbrs:
            orphan = "title_abbreviation"
        elif def_count >= 2:
            orphan = "duplicate_definition"
        elif use_count > 0 and def_count == 0 and not is_universal:
            orphan = "undefined_use"
        elif def_count >= 1 and use_count == 0:
            orphan = "defined_unused"
        else:
            orphan = None
        index.append(
            {
                "abbr": abbr,
                "full_name": def_list[0][1] if def_list else "",
                "defined_count": def_count,
                "used_count": use_count,
                "first_defined": def_list[0][0] if def_list else None,
                "first_used": first_use.get(abbr),
                "universal": is_universal,
                "orphan_type": orphan,
            }
        )
    return index


def render_markdown(
    figure_index: list[dict[str, Any]],
    reference_index: dict[str, Any],
    abbreviation_index: list[dict[str, Any]],
    manuscript_path: Path,
) -> str:
    lines: list[str] = []
    lines.append("# Manuscript Index")
    lines.append("")
    lines.append(f"Source: `{manuscript_path.name}`")
    lines.append("")
    lines.append(
        "Heuristic cross-reference extraction. Use as a review aid, not a "
        "substitute for manual red-line verification."
    )
    lines.append("")

    lines.append("## Figure Index")
    lines.append("")
    lines.append("| Figure | Caption found | Cited by | Orphan |")
    lines.append("|---|---|---|---|")
    for fig in figure_index:
        cap_excerpt = fig["caption"][:80].replace("|", "\\|")
        cited = ", ".join(fig["cited_by"]) if fig["cited_by"] else "-"
        cited = cited.replace("|", "\\|")
        orphan = fig["orphan_type"] or "-"
        found = "yes" if fig["caption_found"] else "NO"
        lines.append(f"| {fig['figure_id']} | {found} | {cited} | {orphan} |")
        if cap_excerpt:
            lines.append(f"| | _{cap_excerpt}_ | | |")
    lines.append("")

    lines.append("## Reference Index")
    lines.append("")
    summary = reference_index["summary"]
    lines.append(
        f"Total refs: {summary['total_refs']} | In-text citations: "
        f"{summary['total_intext_citations']} | Orphans: {summary['orphans']}"
    )
    lines.append("")
    lines.append("| # | Entry | Cited by | Orphan |")
    lines.append("|---|---|---|---|")
    for entry in reference_index["entries"]:
        raw = (entry["raw_entry"] or "(no list entry)")[:90].replace("|", "\\|")
        cited = ", ".join(entry["cited_by"]) if entry["cited_by"] else "-"
        cited = cited.replace("|", "\\|")
        orphan = entry["orphan_type"] or "-"
        lines.append(f"| {entry['ref_number']} | {raw} | {cited} | {orphan} |")
    lines.append("")

    lines.append("## Abbreviation Index")
    lines.append("")
    abbr_hard = sum(1 for a in abbreviation_index if a["orphan_type"] in ABBR_HARD_ORPHANS)
    abbr_soft = sum(1 for a in abbreviation_index if a["orphan_type"] == "defined_unused")
    lines.append(
        f"Total abbreviations: {len(abbreviation_index)} | Hard issues: "
        f"{abbr_hard} | Soft (defined_unused): {abbr_soft}"
    )
    lines.append("")
    lines.append("| Abbr | Full name | Def | Use | Orphan |")
    lines.append("|---|---|---|---|---|")
    for ab in abbreviation_index:
        full = (ab["full_name"] or "-")[:60].replace("|", "\\|")
        orphan = ab["orphan_type"] or "-"
        lines.append(
            f"| {ab['abbr']} | {full} | {ab['defined_count']} | "
            f"{ab['used_count']} | {orphan} |"
        )
    lines.append("")

    lines.append("## Orphan Summary")
    lines.append("")
    fig_orphans = [f for f in figure_index if f["orphan_type"]]
    ref_orphans = [e for e in reference_index["entries"] if e["orphan_type"]]
    abbr_orphans = [a for a in abbreviation_index if a["orphan_type"]]
    if not fig_orphans and not ref_orphans and not abbr_orphans:
        lines.append("No orphans detected.")
    else:
        if fig_orphans:
            lines.append("Figures:")
            for f in fig_orphans:
                lines.append(f"- {f['figure_id']}: {f['orphan_type']}")
        if ref_orphans:
            lines.append("")
            lines.append("References:")
            for e in ref_orphans:
                lines.append(f"- [{e['ref_number']}]: {e['orphan_type']}")
        if abbr_orphans:
            lines.append("")
            lines.append("Abbreviations:")
            for a in abbr_orphans:
                lines.append(f"- {a['abbr']}: {a['orphan_type']}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract figure/reference cross-index from a finished manuscript.")
    parser.add_argument("--manuscript", required=True, help="Path to the finished manuscript (docx or md).")
    parser.add_argument("--project-root", required=True, help="Output root for the index files.")
    parser.add_argument("--units-dir", default=None, help="Optional polish-sci units dir; when present cited_by uses unit idx.")
    args = parser.parse_args()

    manuscript_path = Path(args.manuscript).expanduser().resolve()
    project_root = Path(args.project_root).expanduser().resolve()
    units_dir = None
    if args.units_dir:
        candidate = Path(args.units_dir)
        if not candidate.is_absolute():
            candidate = project_root / candidate
        units_dir = candidate.expanduser().resolve()

    if not manuscript_path.exists():
        raise SystemExit(f"manuscript not found: {manuscript_path}")

    rows = read_manuscript_paragraphs(manuscript_path)
    units_map = load_units_map(units_dir)
    ref_spans = reference_section_spans(rows)

    figure_index = build_figure_index(rows, ref_spans, units_map)
    reference_index = build_reference_index(rows, ref_spans, units_map)
    abbreviation_index = build_abbreviation_index(rows, ref_spans)
    markdown = render_markdown(figure_index, reference_index, abbreviation_index, manuscript_path)

    write_json(project_root / "figure_index.json", figure_index)
    write_json(project_root / "reference_index.json", reference_index)
    write_json(project_root / "abbreviation_index.json", abbreviation_index)
    write_text(project_root / "manuscript_index.md", markdown)

    fig_orphans = sum(1 for f in figure_index if f["orphan_type"])
    ref_orphans = reference_index["summary"]["orphans"]
    abbr_hard = sum(1 for a in abbreviation_index if a["orphan_type"] in ABBR_HARD_ORPHANS)
    abbr_soft = sum(1 for a in abbreviation_index if a["orphan_type"] == "defined_unused")
    print(
        json.dumps(
            {
                "ok": True,
                "figures": len(figure_index),
                "references": reference_index["summary"]["total_refs"],
                "figure_orphans": fig_orphans,
                "reference_orphans": ref_orphans,
                "abbreviations": len(abbreviation_index),
                "abbreviation_hard_orphans": abbr_hard,
                "abbreviation_soft_orphans": abbr_soft,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
