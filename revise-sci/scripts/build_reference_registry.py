#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from common import autodiscover_reference_source, docx_title_hint, normalize_ws, read_docx_paragraphs, read_json, write_json, write_text


HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s*(references|reference|参考文献|bibliography|cited literature|literature cited)\s*$", re.IGNORECASE)
# Plain (non-markdown) references heading, e.g. a bare "References" line produced
# from a .docx/.txt source that carries no markdown "#" prefix. Optional leading
# numbering ("4 References", "5. References") is tolerated.
PLAIN_HEADING_RE = re.compile(r"^\s{0,3}(?:\d+(?:\.\d+)*\.?\s+)?(references|reference|参考文献|bibliography|cited literature|literature cited)\s*$", re.IGNORECASE)
NEXT_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+\S+")
NUMBERED_REF_RE = re.compile(r"^\s*(\d+)[\.\)]\s+(.*)$")
INLINE_NUMERIC_CITATION_RE = re.compile(r"\[(\d+(?:\s*[-,–]\s*\d+)*)\]")
AUTHOR_YEAR_PAREN_RE = re.compile(r"\(([A-Z][A-Za-z'`-]+(?:\s+et al\.)?),\s*((?:19|20)\d{2}[a-z]?)\)")
AUTHOR_YEAR_NARRATIVE_RE = re.compile(r"\b([A-Z][A-Za-z'`-]+(?:\s+et al\.)?)\s*\(((?:19|20)\d{2}[a-z]?)\)")
AUTHOR_YEAR_IN_MULTI_PAREN_RE = re.compile(r"([A-Z][A-Za-z'`-]+(?:\s+et al\.)?),\s*((?:19|20)\d{2}[a-z]?)")
REFERENCE_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}[a-z]?\b")
AUTHOR_LIKE_RE = re.compile(r"^[A-Z][A-Za-z'`-]+,\s")
# Author-year reference entry where the surname leads with initials following,
# e.g. "BRAY F, LAVERSANNE M, SUNG H, et al. ..." or "Smith J, Doe A. ...".
# This covers the GB/T author-year style that AUTHOR_LIKE_RE (Surname,\s) misses.
AUTHOR_INITIALS_REF_RE = re.compile(r"^[A-Z][A-Za-z'`-]+\s+[A-Z](?:[\s.,;-]|$)")


def _entries_follow_heading(lines: list[str], start: int, end: int) -> bool:
    """At least one line after the heading must look like a reference entry."""
    for line in lines[start + 1 : end]:
        if normalize_ws(line) and looks_like_reference_entry(line):
            return True
    return False


def split_reference_section(text: str) -> tuple[str, list[str], bool]:
    lines = text.splitlines()
    end = len(lines)
    # Prefer an explicit markdown heading (pipeline-built section md).
    start = None
    for idx, line in enumerate(lines):
        if HEADING_RE.match(line):
            start = idx
            break
    # Fallback: a bare "References"/"参考文献" line with no markdown prefix
    # (e.g. a .docx/.txt reference source that lost its heading style). Only
    # accept it when the following block actually contains reference entries,
    # so a stray "References" mention in body text is not misread as a heading.
    if start is None:
        for idx, line in enumerate(lines):
            if PLAIN_HEADING_RE.match(line) and _entries_follow_heading(lines, idx, len(lines)):
                start = idx
                break
    if start is None:
        return text, [], False
    for idx in range(start + 1, len(lines)):
        if NEXT_HEADING_RE.match(lines[idx]):
            end = idx
            break
    body_lines = lines[:start] + lines[end:]
    reference_lines = [line for line in lines[start + 1 : end] if normalize_ws(line)]
    return "\n".join(body_lines), reference_lines, True


def normalize_reference_key(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"doi:\s*10\.\S+", "", lowered)
    lowered = re.sub(r"pmid:\s*\d+", "", lowered)
    lowered = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def looks_like_reference_entry(text: str) -> bool:
    normalized = normalize_ws(text)
    if not normalized:
        return False
    lowered = normalized.lower()
    if "doi:" in lowered or "pmid:" in lowered:
        return True
    if REFERENCE_YEAR_RE.search(normalized):
        return True
    if AUTHOR_LIKE_RE.search(normalized):
        return True
    if AUTHOR_INITIALS_REF_RE.match(normalized):
        return True
    if " et al." in normalized:
        return True
    return False


def build_registry(reference_lines: list[str]) -> list[dict]:
    registry: list[dict] = []
    next_number = 1
    for line in reference_lines:
        match = NUMBERED_REF_RE.match(line)
        if match:
            number = int(match.group(1))
            raw_text = normalize_ws(match.group(2))
            next_number = max(next_number, number + 1)
        else:
            number = next_number
            raw_text = normalize_ws(line)
            next_number += 1
        if not looks_like_reference_entry(raw_text):
            continue
        registry.append(
            {
                "reference_number": number,
                "raw_text": raw_text,
                "normalized_key": normalize_reference_key(raw_text),
                "provider_family": "user-provided",
                "source_tier": "manuscript-reference",
                "verified": False,
            }
        )
    return registry


def registry_to_reference_lines(registry: list[dict]) -> list[str]:
    lines = []
    for entry in sorted(registry, key=lambda item: item.get("reference_number", 0)):
        number = int(entry.get("reference_number") or 0)
        raw_text = normalize_ws(str(entry.get("raw_text") or ""))
        if not raw_text:
            continue
        lines.append(f"{number}. {raw_text}" if number else raw_text)
    return lines


def build_reference_entry_from_fields(entry: dict, fallback_number: int) -> str:
    raw = normalize_ws(str(entry.get("reference_entry") or entry.get("raw_text") or entry.get("text") or ""))
    if raw:
        return raw
    authors = entry.get("authors") or []
    if isinstance(authors, list):
        authors_text = ", ".join(normalize_ws(str(author)) for author in authors if normalize_ws(str(author)))
    else:
        authors_text = normalize_ws(str(authors))
    title = normalize_ws(str(entry.get("title") or f"Reference {fallback_number}"))
    journal = normalize_ws(str(entry.get("journal") or entry.get("venue") or ""))
    year = normalize_ws(str(entry.get("year") or ""))
    doi = normalize_ws(str(entry.get("doi") or ""))
    pmid = normalize_ws(str(entry.get("pmid") or ""))
    parts = []
    if authors_text:
        parts.append(f"{authors_text}.")
    parts.append(f"{title}.")
    if journal:
        parts.append(f"{journal}.")
    if year:
        parts.append(f"{year}.")
    if doi:
        parts.append(f"DOI: {doi}.")
    if pmid:
        parts.append(f"PMID: {pmid}.")
    return " ".join(part for part in parts if part).strip()


def parse_seed_json(path: Path) -> list[str]:
    payload = read_json(path, {})
    if isinstance(payload, dict):
        entries = payload.get("entries") or payload.get("results") or payload.get("references") or []
    elif isinstance(payload, list):
        entries = payload
    else:
        entries = []
    lines = []
    for idx, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            lines.append(normalize_ws(str(entry)))
            continue
        lines.append(build_reference_entry_from_fields(entry, idx))
    return [line for line in lines if normalize_ws(line)]


def parse_seed_docx(path: Path) -> list[str]:
    rows = read_docx_paragraphs(path)
    texts = [row["text"] for row in rows if normalize_ws(row["text"])]
    _, reference_lines, found = split_reference_section("\n".join(texts))
    if found and reference_lines:
        return reference_lines
    return [text for text in texts if NUMBERED_REF_RE.match(text)]


def parse_seed_bib(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    entries = re.split(r"(?=@\w+\s*\{)", text)
    lines = []
    for idx, block in enumerate(entries, start=1):
        if "title" not in block.lower():
            continue
        def grab(field: str) -> str:
            match = re.search(rf"{field}\s*=\s*[\{{\"](.+?)[\}}\"],?\s*$", block, flags=re.IGNORECASE | re.MULTILINE)
            return normalize_ws(match.group(1)) if match else ""
        entry = {
            "authors": grab("author"),
            "title": grab("title"),
            "journal": grab("journal") or grab("booktitle"),
            "year": grab("year"),
            "doi": grab("doi"),
            "pmid": grab("pmid"),
        }
        lines.append(build_reference_entry_from_fields(entry, idx))
    return [line for line in lines if normalize_ws(line)]


def parse_seed_ris(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    records = re.split(r"(?m)^ER\s*-\s*$", text)
    lines = []
    for idx, block in enumerate(records, start=1):
        tags: dict[str, list[str]] = {}
        for raw_line in block.splitlines():
            match = re.match(r"^([A-Z0-9]{2})\s*-\s*(.*)$", raw_line.strip())
            if not match:
                continue
            tags.setdefault(match.group(1), []).append(normalize_ws(match.group(2)))
        if not tags:
            continue
        year_field = next((key for key in ("PY", "Y1", "DA") if tags.get(key)), "")
        year_text = tags.get(year_field, [""])[0] if year_field else ""
        year_match = re.search(r"(19|20)\d{2}", year_text)
        entry = {
            "authors": tags.get("AU", []) or tags.get("A1", []),
            "title": (tags.get("TI", []) or tags.get("T1", []) or tags.get("CT", [""]))[0],
            "journal": (tags.get("JO", []) or tags.get("JF", []) or tags.get("T2", [""]))[0],
            "year": year_match.group(0) if year_match else "",
            "doi": (tags.get("DO", [""]))[0],
            "pmid": (tags.get("AN", [""]))[0],
        }
        lines.append(build_reference_entry_from_fields(entry, idx))
    return [line for line in lines if normalize_ws(line)]


def load_reference_source_lines(path: Path | None) -> tuple[list[str], str]:
    if path is None or not path.exists():
        return [], ""
    suffix = path.suffix.lower()
    if suffix == ".json":
        return parse_seed_json(path), str(path.resolve())
    if suffix in {".md", ".txt"}:
        text = path.read_text(encoding="utf-8", errors="ignore")
        _, reference_lines, found = split_reference_section(text)
        if found and reference_lines:
            return reference_lines, str(path.resolve())
        return [line for line in text.splitlines() if normalize_ws(line)], str(path.resolve())
    if suffix == ".docx":
        return parse_seed_docx(path), str(path.resolve())
    if suffix == ".bib":
        return parse_seed_bib(path), str(path.resolve())
    if suffix == ".ris":
        return parse_seed_ris(path), str(path.resolve())
    return [], str(path.resolve())


def rewrite_references_section(output_md: Path, body_text: str, reference_lines: list[str], references_found: bool) -> None:
    body = body_text.rstrip()
    lines = body.splitlines() if body else []
    if lines and normalize_ws(lines[-1]):
        lines.append("")
    lines.append("## References")
    lines.append("")
    lines.extend(reference_lines)
    write_text(output_md, "\n".join(lines).rstrip() + "\n")


def expand_citation_numbers(payload: str) -> list[int]:
    numbers: list[int] = []
    for chunk in re.split(r"\s*,\s*", payload.replace("–", "-").strip()):
        if not chunk:
            continue
        if "-" in chunk:
            start_str, end_str = [part.strip() for part in chunk.split("-", 1)]
            if start_str.isdigit() and end_str.isdigit():
                start = int(start_str)
                end = int(end_str)
                if start <= end:
                    numbers.extend(range(start, end + 1))
                else:
                    numbers.extend([start, end])
            continue
        if chunk.isdigit():
            numbers.append(int(chunk))
    return numbers


def detect_cited_numbers(body_text: str) -> list[int]:
    cited = set()
    for match in INLINE_NUMERIC_CITATION_RE.finditer(body_text):
        cited.update(expand_citation_numbers(match.group(1)))
    return sorted(cited)


def normalize_author_year_key(author: str, year: str) -> str:
    surname = normalize_ws(author).lower().replace(" et al.", "")
    surname = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", surname)
    return f"{surname}|{normalize_ws(year)}"


def detect_author_year_citations(body_text: str) -> list[str]:
    citations: set[str] = set()
    for match in AUTHOR_YEAR_PAREN_RE.finditer(body_text):
        citations.add(normalize_author_year_key(match.group(1), match.group(2)))
    for match in AUTHOR_YEAR_NARRATIVE_RE.finditer(body_text):
        citations.add(normalize_author_year_key(match.group(1), match.group(2)))
    for parenthetical in re.findall(r"\(([^)]*;\s*[^)]*)\)", body_text):
        for match in AUTHOR_YEAR_IN_MULTI_PAREN_RE.finditer(parenthetical):
            citations.add(normalize_author_year_key(match.group(1), match.group(2)))
    return sorted(citations)


def reference_author_year_keys(registry: list[dict]) -> list[str]:
    keys: set[str] = set()
    for entry in registry:
        raw_text = normalize_ws(str(entry.get("raw_text") or ""))
        if not raw_text:
            continue
        year_match = re.search(r"\b((?:19|20)\d{2}[a-z]?)\b", raw_text)
        author_match = re.match(r"^[\[\]\d\.\)\s]*([A-Z][A-Za-z'`-]+)", raw_text)
        if year_match and author_match:
            keys.add(normalize_author_year_key(author_match.group(1), year_match.group(1)))
    return sorted(keys)


def merge_missing_numeric_references(current_registry: list[dict], source_registry: list[dict], missing_numbers: list[int]) -> tuple[list[dict], list[int]]:
    if not missing_numbers:
        return current_registry, []
    current_by_number = {int(entry.get("reference_number") or 0): dict(entry) for entry in current_registry}
    source_by_number = {int(entry.get("reference_number") or 0): dict(entry) for entry in source_registry}
    imported_numbers: list[int] = []
    for number in missing_numbers:
        if number in current_by_number or number not in source_by_number:
            continue
        current_by_number[number] = dict(source_by_number[number])
        imported_numbers.append(number)
    merged = [current_by_number[number] for number in sorted(current_by_number)]
    return merged, imported_numbers


def write_reference_recovery_request(project_root: Path, report: dict) -> None:
    request_path = project_root / "reference_recovery_request.md"
    missing_numbers = report.get("missing_reference_numbers", [])
    missing_author_year = report.get("missing_author_year_citations", [])
    if not missing_numbers and not missing_author_year:
        if request_path.exists():
            request_path.unlink()
        return
    decision = report.get("reference_search_decision", "ask")
    source_missing = not normalize_ws(str(report.get("reference_source", "")))
    lines = [
        "# Reference Recovery Request",
        "",
        "当前主稿中的正文引文尚未被现有参考文献源完整覆盖，因此该项目不能被视为可直接投稿版本。",
        "",
        "## 缺失概览",
        "",
        f"- citation_style: {report.get('citation_style', 'unknown')}",
        f"- missing_reference_numbers: {', '.join(str(number) for number in missing_numbers) if missing_numbers else '无'}",
        f"- missing_author_year_citations: {', '.join(missing_author_year) if missing_author_year else '无'}",
        f"- current_reference_source: {report.get('reference_source') or 'Not provided by user'}",
        f"- reference_search_decision: {decision}",
        "",
        "## 需作者补充的材料",
        "",
        "- 请提供同一篇稿件的完整旧版参考文献源，推荐格式：.docx/.bib/.ris/.json/.md/.txt",
        "- 如果当前稿件采用数字引文，请优先提供带完整编号的旧稿或 Bib/RIS 文件。",
        "- 如果当前稿件采用 author-year 引文，请优先提供完整参考文献列表，并确保作者-年份信息可唯一对应。",
        "",
        "## 是否允许按 review-writing 规则启动新文献检索并补全文末参考文献？",
        "",
    ]
    if source_missing:
        if decision == "ask":
            lines.extend(
                [
                    "- 当前没有可追溯的旧版参考文献源。请作者明确回复：是否允许启动新文献检索并补全文末参考文献？",
                    "- 在收到作者明确批准前，系统不会自行检索或补写新文献。",
                    "",
                ]
            )
        elif decision == "approved":
            lines.extend(
                [
                    "- 作者已批准启动新文献检索，但当前项目中尚未导入可用的检索结果批次。",
                    "- 请按下述流程提供新的 paper-search 检索批次，然后重新运行 pipeline。",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "- 作者当前未批准启动新文献检索，因此系统只能等待旧版参考文献源或作者后续改变决定。",
                    "",
                ]
            )
    else:
        lines.extend(
            [
                "- 当前已经存在旧版参考文献源，但其覆盖仍不足；若作者同意，也可以额外启动新文献检索补齐缺口。",
                "",
            ]
        )
    lines.extend(
        [
            "## review-writing 风格检索约束",
            "",
            "- 仅允许使用 paper-search 作为新增文献检索入口；不得接入其他自由网页搜索来直接补引文。",
            "- 每个检索/导入批次更新后，必须立即运行 citation_guard.py 做双重验证，未验证通过的条目不得引用。",
            "- 检索结果必须进入 canonical data/literature_index.json，并继续更新 data/synthesis_matrix.json 与 data/synthesis_matrix_audit.json。",
            "- 只有在 citation_guard、literature index、synthesis matrix 和 reference sync 四处全部闭环后，新增文献才可进入最终 References。",
            "- 引文编号必须继续保持全文全局顺序，不得局部重排或跳号。",
            "",
        "## 处理原则",
        "",
        "- 系统不会凭空生成或猜测缺失的历史参考文献条目。",
        "- 在未获得可追溯的参考文献源之前，相关缺口会持续阻断 strict gate。",
        "",
        ]
    )
    write_text(request_path, "\n".join(lines))


def cleanup_reference_search_artifacts(project_root: Path) -> None:
    for name in ("reference_search_manifest.json", "reference_search_task.md", "reference_search_strategy.json", "reference_search_status.json", "reference_search_rounds.json"):
        path = project_root / name
        if path.exists():
            path.unlink()


def pending_citation_units(project_root: Path) -> list[dict]:
    units_dir = project_root / "units"
    pending: list[dict] = []
    if not units_dir.exists():
        return pending
    for unit_path in sorted(units_dir.glob("*.json")):
        unit = read_json(unit_path, {})
        if normalize_ws(str(unit.get("status", ""))) != "needs_author_confirmation":
            continue
        if normalize_ws(str(unit.get("editorial_intent", ""))) == "citation":
            pending.append(unit)
            continue
        for source in unit.get("evidence_sources", []) or []:
            provider = normalize_ws(str(source.get("provider_family", "")))
            source_name = normalize_ws(str(source.get("source", "")))
            if provider == "paper-search" and source_name == "candidate-search-required":
                pending.append(unit)
                break
    return pending


def reference_search_governance_active(project_root: Path, report: dict) -> bool:
    if report.get("reference_search_decision") != "approved":
        return False
    if report.get("reference_search_required"):
        return True
    if pending_citation_units(project_root):
        return True
    return any(
        (project_root / name).exists()
        for name in ("paper_search_results.json", "paper_search_validated.json", "paper_search_guard_report.json")
    )


def search_query_hints(project_root: Path, state: dict, report: dict) -> list[dict]:
    manuscript_path = Path(state.get("inputs", {}).get("manuscript_docx_path", "")) if state.get("inputs", {}).get("manuscript_docx_path") else None
    title = docx_title_hint(manuscript_path) if manuscript_path and manuscript_path.exists() else ""
    output_md = project_root / "revised_manuscript.md"
    headings: list[str] = []
    if output_md.exists():
        for line in output_md.read_text(encoding="utf-8").splitlines():
            stripped = normalize_ws(line)
            if stripped.startswith("#"):
                heading = normalize_ws(stripped.lstrip("#"))
                if heading and heading.lower() not in {"references", "reference", "参考文献"}:
                    headings.append(heading)
    hints: list[dict] = []
    if title:
        hints.append({"type": "manuscript_title", "query": f"{title} review"})
    for heading in headings[:5]:
        hints.append({"type": "section_heading", "query": heading})
    for key in report.get("missing_author_year_citations", [])[:10]:
        author, _, year = key.partition("|")
        hints.append({"type": "missing_author_year", "query": f"{author} {year}"})
    if report.get("missing_reference_numbers"):
        hints.append({"type": "missing_number_batch", "query": f"Resolve missing references for citation numbers {', '.join(str(x) for x in report.get('missing_reference_numbers', [])[:20])}"})
    for unit in pending_citation_units(project_root):
        for key in ("comment_title", "problem_description", "root_cause", "author_strategy", "reviewer_comment_original", "reviewer_comment_en"):
            value = normalize_ws(str(unit.get(key, "")))
            if value:
                hints.append({"type": "citation_comment", "query": value})
    deduped: list[dict] = []
    seen: set[str] = set()
    for hint in hints:
        query = normalize_ws(hint.get("query", ""))
        if not query or query in seen:
            continue
        seen.add(query)
        deduped.append({"type": hint["type"], "query": query})
    return deduped


def build_search_rounds(query_hints: list[dict], report: dict) -> dict:
    round1_queries: list[str] = []
    round2_queries: list[str] = []
    round3_queries: list[str] = []
    for hint in query_hints:
        hint_type = normalize_ws(str(hint.get("type", "")))
        query = normalize_ws(str(hint.get("query", "")))
        if not query:
            continue
        if hint_type in {"manuscript_title", "missing_number_batch"}:
            round1_queries.append(query)
        elif hint_type in {"section_heading", "missing_author_year"}:
            round2_queries.append(query)
        else:
            round1_queries.append(query)
    if not round1_queries:
        fallback_queries = []
        if report.get("missing_reference_numbers"):
            fallback_queries.append(f"Resolve missing references for citation numbers {', '.join(str(x) for x in report.get('missing_reference_numbers', [])[:20])}")
        for key in report.get("missing_author_year_citations", [])[:10]:
            author, _, year = key.partition("|")
            fallback_queries.append(f"{author} {year}")
        round1_queries.extend(fallback_queries)
    round3_queries.extend(round2_queries[:3] or round1_queries[:3])
    return {
        "workflow": "review-writing",
        "rounds": [
            {
                "round": 1,
                "name": "Candidate retrieval",
                "status": "pending",
                "provider_family": "paper-search",
                "queries": round1_queries,
            },
            {
                "round": 2,
                "name": "Section-deepening retrieval",
                "status": "pending",
                "provider_family": "paper-search",
                "queries": round2_queries,
            },
            {
                "round": 3,
                "name": "Critical refresh",
                "status": "pending",
                "provider_family": "paper-search",
                "queries": round3_queries,
            },
        ],
    }


def write_reference_search_artifacts(project_root: Path, state: dict, report: dict) -> None:
    if not reference_search_governance_active(project_root, report):
        cleanup_reference_search_artifacts(project_root)
        return
    guard_command = "python scripts/citation_guard.py --paper-search-results <project_root/paper_search_results.json> --project-root <project_root> --live"
    manifest = {
        "workflow": "review-writing",
        "reference_search_required": bool(report.get("reference_search_required")),
        "reference_search_decision": "approved",
        "governance_active": True,
        "allowed_provider_families": ["paper-search"],
        "forbidden_provider_families": ["websearch"],
        "verification_policy": {
            "dual_verification_required": True,
            "allow_unverified": False,
            "guard_command": guard_command,
        },
        "canonical_outputs": [
            "data/literature_index.json",
            "data/revision_claims.json",
            "data/synthesis_matrix.json",
            "data/synthesis_matrix_audit.json",
            "reference_sync_report.json",
            "data/reference_registry.json",
            "data/reference_coverage_audit.json",
        ],
        "query_hints": search_query_hints(project_root, state, report),
        "mode": "gap-recovery" if report.get("reference_search_required") else "citation-supplement",
        "workflow_rules": {
            "rounds": [
                {
                    "round": 1,
                    "goal": "Build a candidate pool for missing references under review-writing governance",
                    "required_steps": [
                        "Run paper-search retrieval batches only",
                        "Save imported rows to project_root/paper_search_results.json",
                        "Run citation_guard.py immediately after each retrieval/import batch",
                    ],
                },
                {
                    "round": 2,
                    "goal": "Convert validated rows into canonical literature artifacts",
                    "required_steps": [
                        "Run build_literature_index.py",
                        "Run matrix_manager.py bootstrap and audit",
                        "Keep new references out of the manuscript until citation_guard and matrix audit both pass",
                    ],
                },
                {
                    "round": 3,
                    "goal": "Write validated references back into the manuscript package",
                    "required_steps": [
                        "Rerun revise_units.py if citation comments are affected",
                        "Run reference_sync.py and build_reference_registry.py",
                        "Require strict_gate.py to pass before delivery",
                    ],
                },
            ]
        },
    }
    round_plan = build_search_rounds(manifest["query_hints"], report)
    strategy = {
        "workflow": "review-writing",
        "reference_search_decision": "approved",
        "mode": manifest["mode"],
        "mandatory_guard_command": guard_command,
        "provider_policy": {
            "primary": ["paper-search"],
            "reverse_verification_only": [],
            "forbidden": ["websearch"],
        },
        "scope": {
            "citation_style": report.get("citation_style", "unknown"),
            "missing_reference_numbers": report.get("missing_reference_numbers", []),
            "missing_author_year_citations": report.get("missing_author_year_citations", []),
            "core_time_window": "2021-2026",
            "manuscript_title": docx_title_hint(Path(state.get("inputs", {}).get("manuscript_docx_path", ""))) if state.get("inputs", {}).get("manuscript_docx_path") else "",
        },
        "round_model": [
            {
                "round": 1,
                "name": "Candidate retrieval",
                "requirements": [
                    "paper-search only",
                    "save project_root/paper_search_results.json",
                    "run citation_guard.py immediately after import",
                ],
            },
            {
                "round": 2,
                "name": "Canonicalization and matrix audit",
                "requirements": [
                    "run build_literature_index.py",
                    "run matrix_manager.py bootstrap",
                    "run matrix_manager.py audit",
                ],
            },
            {
                "round": 3,
                "name": "Write-back and final gate",
                "requirements": [
                    "run reference_sync.py",
                    "rerun build_reference_registry.py",
                    "run strict_gate.py before delivery",
                ],
            },
        ],
        "hard_block_conditions": [
            "Do not cite entries that fail citation_guard.py",
            "Do not write references back before literature index and synthesis matrix audit exist",
            "Do not deliver until strict_gate.py passes",
        ],
        "required_outputs": manifest["canonical_outputs"],
        "query_hints": manifest["query_hints"],
    }
    paper_search_results_path = project_root / "paper_search_results.json"
    paper_search_validated_path = project_root / "paper_search_validated.json"
    guard_report = read_json(project_root / "paper_search_guard_report.json", {})
    literature_report = read_json(project_root / "literature_index_report.json", {})
    matrix_audit = read_json(project_root / "data" / "synthesis_matrix_audit.json", {})
    status = {
        "reference_search_required": bool(report.get("reference_search_required")),
        "reference_search_decision": "approved",
        "governance_active": True,
        "mode": manifest["mode"],
        "steps": {
            "search_round_plan_generated": True,
            "paper_search_batch_imported": paper_search_results_path.exists(),
            "validated_batch_present": paper_search_validated_path.exists(),
            "citation_guard_passed": bool(guard_report.get("summary", {}).get("all_rows_guard_verified", False)),
            "literature_index_built": bool(literature_report.get("entries", 0) > 0),
            "synthesis_matrix_audited": bool((project_root / "data" / "synthesis_matrix_audit.json").exists()),
            "reference_sync_completed": bool((project_root / "reference_sync_report.json").exists()),
        },
        "pending_missing_reference_numbers": report.get("missing_reference_numbers", []),
        "pending_missing_author_year_citations": report.get("missing_author_year_citations", []),
        "matrix_audit_missing_claim": matrix_audit.get("missing_claim", 0) if isinstance(matrix_audit, dict) else 0,
        "matrix_audit_missing_key_fields": matrix_audit.get("missing_key_fields", 0) if isinstance(matrix_audit, dict) else 0,
    }
    write_json(project_root / "reference_search_manifest.json", manifest)
    write_json(project_root / "reference_search_strategy.json", strategy)
    write_json(project_root / "reference_search_status.json", status)
    write_json(project_root / "reference_search_rounds.json", round_plan)
    lines = [
        "# Reference Search Task",
        "",
        "作者已批准在缺少原始参考文献源的情况下启动新文献检索，但后续步骤必须严格遵守 review-writing 风格治理。",
        "",
        "## Provider Policy",
        "",
        "- Allowed provider: `paper-search` only",
        "- Forbidden direct fallback: `websearch` and other free-form web retrieval",
        "",
        "## Required Step Order",
        "",
        "1. 使用 `paper-search` 分批检索，并把结果保存到 `project_root/paper_search_results.json`。",
        "2. 每个检索/导入批次后，立即运行 `citation_guard.py`；未通过双重验证的条目不得进入下一步。",
        "3. 运行 `build_literature_index.py`，把验证通过的条目写入 `data/literature_index.json`。",
        "4. 运行 `matrix_manager.py bootstrap` 和 `matrix_manager.py audit`，更新 `data/synthesis_matrix.json` 与审计报告。",
        "5. 如 citation comment 受影响，重新运行 `revise_units.py`，然后运行 `reference_sync.py` 与 `build_reference_registry.py`。",
        "6. 最后重新运行 `strict_gate.py`，只有全部通过后才能交付。",
        "",
        "## Query Hints",
        "",
    ]
    for hint in manifest["query_hints"]:
        lines.append(f"- {hint['type']}: {hint['query']}")
    lines.extend(["", "## Canonical Commands", ""])
    lines.append("- `python scripts/citation_guard.py --paper-search-results <project_root/paper_search_results.json> --project-root <project_root> --live`")
    lines.append("- `python scripts/build_literature_index.py --project-root <project_root>`")
    lines.append("- `python scripts/matrix_manager.py bootstrap --index <project_root/data/literature_index.json> --matrix <project_root/data/synthesis_matrix.json> --round 2`")
    lines.append("- `python scripts/matrix_manager.py audit --matrix <project_root/data/synthesis_matrix.json> --report <project_root/data/synthesis_matrix_audit.json>`")
    lines.append("- `python scripts/reference_sync.py --project-root <project_root> --output-md <output_md>`")
    lines.append("- `python scripts/build_reference_registry.py --project-root <project_root> --output-md <output_md> --reference-search-decision approved`")
    lines.extend(["", "## Search Round Plan", "", f"- `reference_search_rounds.json`: {str((project_root / 'reference_search_rounds.json').resolve())}"])
    write_text(project_root / "reference_search_task.md", "\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build canonical reference registry and coverage audit from merged manuscript markdown")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--references-source", default="")
    parser.add_argument("--reference-search-decision", choices=("ask", "approved", "declined"), default="")
    args = parser.parse_args()

    project_root = Path(args.project_root)
    output_md = Path(args.output_md)
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    state = read_json(project_root / "project_state.json", {})
    inputs = state.get("inputs", {}) if isinstance(state, dict) else {}
    reference_search_decision = args.reference_search_decision or inputs.get("reference_search_decision") or "ask"
    references_source = (
        Path(args.references_source).resolve()
        if args.references_source
        else autodiscover_reference_source(
            Path(inputs["comments_path"]) if inputs.get("comments_path") else None,
            Path(inputs["attachments_dir_path"]) if inputs.get("attachments_dir_path") else None,
            project_root,
            Path(inputs["manuscript_docx_path"]) if inputs.get("manuscript_docx_path") else None,
        )
    )

    if not output_md.exists():
        write_json(data_dir / "reference_registry.json", [])
        resolved_reference_source = str(references_source.resolve()) if references_source else ""
        report = {
            "ok": True,
            "citation_style": "none",
            "references_section_found": False,
            "reference_entries": 0,
            "cited_numbers": [],
            "available_reference_numbers": [],
            "missing_reference_numbers": [],
            "reference_source": resolved_reference_source,
            "reference_source_used": "",
            "reference_search_required": False,
            "reference_search_decision": reference_search_decision,
        }
        write_json(data_dir / "reference_coverage_audit.json", report)
        write_reference_recovery_request(project_root, report)
        print(json.dumps({"ok": True, "reference_entries": 0, "cited_numbers": 0}, ensure_ascii=False))
        return 0

    text = output_md.read_text(encoding="utf-8")
    body_text, reference_lines, references_found = split_reference_section(text)
    imported_lines: list[str] = []
    imported_source = ""
    cited_numbers = detect_cited_numbers(body_text)
    author_year_citations = detect_author_year_citations(body_text)

    if not reference_lines:
        imported_lines, imported_source = load_reference_source_lines(references_source)
        if imported_lines:
            reference_lines = imported_lines
            rewrite_references_section(output_md, body_text, reference_lines, references_found)
            text = output_md.read_text(encoding="utf-8")
            body_text, reference_lines, references_found = split_reference_section(text)

    registry = build_registry(reference_lines)
    sanitized_reference_lines = registry_to_reference_lines(registry)
    if reference_lines != sanitized_reference_lines:
        reference_lines = sanitized_reference_lines
        rewrite_references_section(output_md, body_text, reference_lines, references_found)
        text = output_md.read_text(encoding="utf-8")
        body_text, reference_lines, references_found = split_reference_section(text)
        registry = build_registry(reference_lines)
    missing_numbers: list[int] = []
    imported_reference_numbers: list[int] = []
    if cited_numbers:
        available_numbers = sorted({entry["reference_number"] for entry in registry})
        missing_numbers = [number for number in cited_numbers if number not in set(available_numbers)]
        if missing_numbers and references_source is not None:
            imported_lines, imported_source = load_reference_source_lines(references_source)
            if imported_lines:
                source_registry = build_registry(imported_lines)
                registry, imported_reference_numbers = merge_missing_numeric_references(registry, source_registry, missing_numbers)
                if imported_reference_numbers:
                    reference_lines = registry_to_reference_lines(registry)
                    rewrite_references_section(output_md, body_text, reference_lines, references_found)
                    text = output_md.read_text(encoding="utf-8")
                    body_text, reference_lines, references_found = split_reference_section(text)
                    registry = build_registry(reference_lines)

    write_json(data_dir / "reference_registry.json", registry)

    available_numbers = sorted({entry["reference_number"] for entry in registry})
    missing_numbers = [number for number in cited_numbers if number not in set(available_numbers)]
    available_author_year_keys = reference_author_year_keys(registry)
    missing_author_year_citations = [key for key in author_year_citations if key not in set(available_author_year_keys)]
    if cited_numbers and author_year_citations:
        citation_style = "mixed"
    elif cited_numbers:
        citation_style = "numeric"
    elif author_year_citations:
        citation_style = "author-year"
    else:
        citation_style = "none"
    resolved_reference_source = str(references_source.resolve()) if references_source else ""
    report = {
        "ok": not missing_numbers and not missing_author_year_citations,
        "citation_style": citation_style,
        "references_section_found": references_found,
        "reference_entries": len(registry),
        "cited_numbers": cited_numbers,
        "available_reference_numbers": available_numbers,
        "missing_reference_numbers": missing_numbers,
        "author_year_citations": author_year_citations,
        "available_author_year_keys": available_author_year_keys,
        "missing_author_year_citations": missing_author_year_citations,
        "max_cited_number": max(cited_numbers) if cited_numbers else 0,
        "reference_source": resolved_reference_source,
        "reference_source_used": imported_source,
        "imported_reference_numbers": imported_reference_numbers,
        "reference_search_required": bool((missing_numbers or missing_author_year_citations) and not normalize_ws(resolved_reference_source)),
        "reference_search_decision": reference_search_decision,
    }
    write_json(data_dir / "reference_coverage_audit.json", report)
    write_reference_recovery_request(project_root, report)
    write_reference_search_artifacts(project_root, state if isinstance(state, dict) else {}, report)
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "reference_entries": len(registry),
                "cited_numbers": len(cited_numbers),
                "missing_reference_numbers": missing_numbers,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
