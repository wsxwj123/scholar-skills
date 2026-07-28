#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from common import normalize_ws, read_json, write_json


def normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", str(text).lower()).strip()


def normalize_doi(doi: str) -> str:
    return re.sub(r"\s+", "", str(doi or "").strip().lower())


def normalize_pmid(pmid: str) -> str:
    return str(pmid or "").strip()


def canonical_key(citation: dict[str, Any]) -> tuple[str, str]:
    doi = normalize_doi(citation.get("doi"))
    pmid = normalize_pmid(citation.get("pmid"))
    title = normalize_text(citation.get("title"))
    if doi:
        return ("doi", doi)
    if pmid:
        return ("pmid", pmid)
    return ("title", title)


# Seed entries may come from gsw/review-writing indexes whose schema is looser
# than revise-sci's canonical. The global id can live under any of these keys.
SEED_GLOBAL_ID_KEYS = ("global_id", "citation_number", "id", "number", "ref_number")


def _coerce_global_id(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def load_seed_entries(seed_path: Path) -> list[tuple[int, dict[str, Any]]]:
    """Read a seed literature index (gsw root-level or review-writing data/ style),
    tolerating a bare list or a wrapper dict. Each returned entry keeps its ORIGINAL
    global id (resolved from any of SEED_GLOBAL_ID_KEYS); entries missing a numeric
    id are back-filled by array order without colliding with explicit ids.

    Read-only: the seed file itself is never modified by this function."""
    raw = read_json(seed_path, None)
    if isinstance(raw, dict):
        for key in ("entries", "literature_index", "results", "items"):
            if isinstance(raw.get(key), list):
                raw = raw[key]
                break
        else:
            raw = []
    if not isinstance(raw, list):
        return []

    parsed: list[tuple[int | None, dict[str, Any]]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        gid: int | None = None
        for key in SEED_GLOBAL_ID_KEYS:
            if key in item:
                gid = _coerce_global_id(item.get(key))
                if gid is not None:
                    break
        parsed.append((gid, item))

    used = {gid for gid, _ in parsed if gid is not None}
    next_fallback = 1
    resolved: list[tuple[int, dict[str, Any]]] = []
    for gid, item in parsed:
        if gid is None:
            while next_fallback in used:
                next_fallback += 1
            gid = next_fallback
            used.add(gid)
        resolved.append((gid, item))
    return resolved


def merge_unique_str_list(existing: list[str], new_values: list[str]) -> list[str]:
    seen = {normalize_ws(x) for x in existing if normalize_ws(x)}
    out = [x for x in existing if normalize_ws(x)]
    for value in new_values:
        normalized = normalize_ws(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def explicit_missing_note(value: Any, default_note: str) -> str:
    text = normalize_ws(str(value or ""))
    return text or default_note


def main() -> int:
    parser = argparse.ArgumentParser(description="Build review-writing style literature_index.json for revise-sci")
    parser.add_argument("--project-root", required=True)
    parser.add_argument(
        "--seed-index",
        default=None,
        help=(
            "Optional path to an existing literature_index.json (e.g. from the writing "
            "project run by gsw/review-writing) to reuse as a seed. Seed entries keep "
            "their original global ids; revision-found references matching a seed reuse "
            "its number, truly new references continue from max(seed id)+1. Read-only: "
            "the seed file is never modified. Omit to rebuild from global_id=1 (unchanged)."
        ),
    )
    args = parser.parse_args()

    project_root = Path(args.project_root)
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    validated = read_json(project_root / "paper_search_validated.json", {"results": []})
    units = [read_json(path, {}) for path in sorted((project_root / "units").glob("*.json"))]
    unit_map = {unit.get("comment_id"): unit for unit in units}

    canonical: list[dict[str, Any]] = []
    key_to_index: dict[tuple[str, str], int] = {}
    index_to_comment_ids: dict[int, list[str]] = {}
    next_global_id = 1

    if args.seed_index:
        for gid, seed_item in load_seed_entries(Path(args.seed_index)):
            entry = dict(seed_item)  # copy so the seed file's data is never mutated
            entry["global_id"] = gid
            canonical.append(entry)
            key = canonical_key(entry)
            if key[1]:
                key_to_index.setdefault(key, len(canonical) - 1)
            next_global_id = max(next_global_id, gid + 1)

    for row in validated.get("results", []):
        if not row.get("guard_verified"):
            continue
        comment_id = normalize_ws(str(row.get("comment_id", "")))
        unit = unit_map.get(comment_id, {})
        atomic = unit.get("atomic_location") or {}
        related_section = normalize_ws(
            atomic.get("manuscript_section_id")
            or atomic.get("si_section_id")
            or atomic.get("section_heading")
            or row.get("target_section_heading")
            or "unassigned"
        )
        claim_text = normalize_ws(unit.get("reviewer_comment_original") or unit.get("reviewer_comment_en") or "")
        for citation in row.get("citations", []) or []:
            if not citation.get("guard_verified"):
                continue
            key = canonical_key(citation)
            if not key[1]:
                continue
            if key in key_to_index:
                idx = key_to_index[key]
                entry = canonical[idx]
                entry["related_sections"] = merge_unique_str_list(entry.get("related_sections", []), [related_section])
                entry["comment_ids"] = merge_unique_str_list(entry.get("comment_ids", []), [comment_id])
                entry["claim_ids"] = merge_unique_str_list(entry.get("claim_ids", []), [comment_id])
                entry["formatted_citation_texts"] = merge_unique_str_list(
                    entry.get("formatted_citation_texts", []),
                    [normalize_ws(str(row.get("formatted_citation_text") or ""))],
                )
                if citation.get("reference_entry"):
                    entry["reference_entry"] = citation["reference_entry"]
                fallback_map = {
                    "abstract": citation.get("abstract"),
                    "key_finding": citation.get("key_finding") or citation.get("summary"),
                    "limitation": citation.get("limitation"),
                    "study_type": citation.get("study_type"),
                }
                for field, default_note in (
                    ("abstract", ""),
                    ("key_finding", "Not provided by paper-search result / 需作者确认"),
                    ("limitation", "Not provided by paper-search result / 需作者确认"),
                    ("study_type", "unknown"),
                ):
                    new_value = explicit_missing_note(fallback_map.get(field), default_note)
                    current_value = normalize_ws(str(entry.get(field) or ""))
                    if not current_value or current_value == default_note:
                        entry[field] = new_value
                index_to_comment_ids[idx] = merge_unique_str_list(index_to_comment_ids.get(idx, []), [comment_id])
                continue

            entry = {
                "global_id": next_global_id,
                "title": normalize_ws(str(citation.get("title") or "")),
                "authors": citation.get("authors") or [],
                "journal": normalize_ws(str(citation.get("journal") or citation.get("venue") or "")),
                "year": citation.get("year") or "",
                "doi": normalize_doi(citation.get("doi")),
                "pmid": normalize_pmid(citation.get("pmid")),
                "source_provider": "paper-search",
                "source_id": normalize_ws(str(citation.get("source_id") or citation.get("source") or "")),
                "verified": True,
                "guard_verified": True,
                "related_sections": [related_section],
                "comment_ids": [comment_id] if comment_id else [],
                "claim_ids": [comment_id] if comment_id else [],
                "claim_text": claim_text,
                "target_document": unit.get("target_document", "manuscript"),
                "target_section_heading": normalize_ws(str(row.get("target_section_heading") or atomic.get("section_heading") or "")),
                "target_paragraph_index": row.get("target_paragraph_index", atomic.get("paragraph_index")),
                "formatted_citation_texts": [normalize_ws(str(row.get("formatted_citation_text") or ""))] if normalize_ws(str(row.get("formatted_citation_text") or "")) else [],
                "reference_entry": normalize_ws(str(citation.get("reference_entry") or "")),
                "abstract": normalize_ws(str(citation.get("abstract") or "")),
                "key_finding": explicit_missing_note(
                    citation.get("key_finding") or citation.get("summary"),
                    "Not provided by paper-search result / 需作者确认",
                ),
                "limitation": explicit_missing_note(
                    citation.get("limitation"),
                    "Not provided by paper-search result / 需作者确认",
                ),
                "source_tier": "revision-citation",
                "study_type": normalize_ws(str(citation.get("study_type") or "unknown")),
                "evidence_round": 2,
            }
            key_to_index[key] = len(canonical)
            canonical.append(entry)
            index_to_comment_ids[len(canonical) - 1] = [comment_id] if comment_id else []
            next_global_id += 1

    write_json(data_dir / "literature_index.json", canonical)
    claims = []
    for entry in canonical:
        for claim_id in entry.get("claim_ids", []):
            claims.append(
                {
                    "claim_id": claim_id,
                    "text": entry.get("claim_text", ""),
                    "related_sections": entry.get("related_sections", []),
                    "global_id": entry.get("global_id"),
                }
            )
    write_json(data_dir / "revision_claims.json", claims)
    summary = {
        "entries": len(canonical),
        "claims": len(claims),
        "output": str((data_dir / "literature_index.json").resolve()),
    }
    write_json(project_root / "literature_index_report.json", summary)
    print(json.dumps({"ok": True, "entries": len(canonical), "claims": len(claims)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
