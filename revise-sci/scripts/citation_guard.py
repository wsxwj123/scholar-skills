#!/usr/bin/env python3
"""revise-sci citation guard (adapter over shared citation_guard_core).

This file is the skill-specific adapter: it owns CLI flags, the two-level
results[] -> row.citations[] loader, identifier extraction from free-text
``source`` fields, the produced report/exit-code contract, and the report
writing. All actual verification logic lives in citation_guard_core.validate_core
(single source of truth; re-mirror that file to change thresholds globally).

Output contract (3 downstream consumers depend on it, do not drift):
  - paper_search_guard_report.json -> summary.all_rows_guard_verified
    (read by build_reference_registry.py and strict_gate.py)
  - each citation's guard_verified flag (read by revise_units.py)
  - paper_search_validated.json (the --write-back equivalent)
Exit code 2 when not all rows verified and --allow-unverified absent; else 0.
With --fail-on-unverified, exit 2 on any unverified row even if --allow-unverified
is passed (opt-in hard gate; default behaviour is unchanged).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from common import normalize_ws, read_json, write_json
from citation_guard_core import _provider_family, validate_core


def _extract_identifier(citation: dict[str, Any]) -> tuple[str, str]:
    """Pull DOI/PMID from explicit fields, falling back to the free-text source."""
    doi = normalize_ws(str(citation.get("doi") or ""))
    pmid = normalize_ws(str(citation.get("pmid") or ""))
    source = normalize_ws(str(citation.get("source") or citation.get("source_id") or ""))
    if not doi:
        match = re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", source, flags=re.IGNORECASE)
        if match:
            doi = match.group(0)
    if not pmid:
        match = re.search(r"PMID[:\s]*(\d{4,10})", source, flags=re.IGNORECASE)
        if match:
            pmid = match.group(1)
    return doi, pmid


def _raw_provider(citation: dict[str, Any]) -> str:
    """Provider field is one of three; default empty -> core treats as unknown.

    Note: original adapter defaulted absent provider to "paper-search" for
    backwards compat. Preserved here so legacy rows without a provider field are
    not penalized as source_provider_not_allowed.
    """
    raw = normalize_ws(
        str(
            citation.get("source_provider")
            or citation.get("provider_family")
            or citation.get("provider")
            or ""
        )
    )
    return raw or "paper-search"


def build_reference_entry(citation: dict[str, Any], doi: str, pmid: str) -> str:
    authors = citation.get("authors") or []
    if isinstance(authors, list):
        authors_text = ", ".join(str(x).strip() for x in authors if str(x).strip())
    else:
        authors_text = normalize_ws(str(authors))
    title = normalize_ws(str(citation.get("title") or "Untitled"))
    journal = normalize_ws(str(citation.get("journal") or citation.get("venue") or ""))
    year = normalize_ws(str(citation.get("year") or ""))
    parts = []
    if authors_text:
        parts.append(f"{authors_text}.")
    parts.append(f"{title}.")
    if journal:
        parts.append(journal + ".")
    if year:
        parts.append(year + ".")
    if doi:
        parts.append(f"DOI: {doi}.")
    if pmid:
        parts.append(f"PMID: {pmid}.")
    return " ".join(parts).strip()


def _build_prefetched(citation: dict[str, Any], title: str) -> dict[str, Any]:
    """Reuse entry-carried verification data to avoid hammering APIs.

    The original adapter only hit Crossref/PubMed when an entry lacked a
    secondary title. We preserve that laziness by feeding any entry-provided
    verified_title / crossref_title / pubmed_title (and matching ids) into the
    core's ``prefetched`` cache so three-round bulk verification does not trip
    Crossref/PubMed rate limits (429).
    """
    prefetched: dict[str, Any] = {}
    crossref_title = normalize_ws(str(citation.get("crossref_title") or citation.get("verified_title") or ""))
    pubmed_title = normalize_ws(str(citation.get("pubmed_title") or ""))
    verified_doi = normalize_ws(str(citation.get("verified_doi") or citation.get("crossref_doi") or ""))
    verified_pmid = normalize_ws(str(citation.get("verified_pmid") or citation.get("pubmed_pmid") or ""))
    if crossref_title:
        prefetched["crossref"] = {
            "source": "crossref",
            "title": crossref_title,
            "doi": verified_doi or None,
            "pmid": None,
            "retracted": bool(citation.get("retracted", False)),
        }
    if pubmed_title:
        prefetched["pubmed"] = {
            "source": "pubmed",
            "title": pubmed_title,
            "doi": verified_doi or None,
            "pmid": verified_pmid or None,
            "retracted": bool(citation.get("retracted", False)),
        }
    return prefetched


def validate_citation(citation: dict[str, Any], *, online_check: bool) -> dict[str, Any]:
    """Normalize one citation, run validate_core, re-emit in the legacy contract."""
    title = normalize_ws(str(citation.get("title") or ""))
    source_id = normalize_ws(str(citation.get("source_id") or citation.get("source") or ""))
    doi, pmid = _extract_identifier(citation)
    provider_family = _provider_family(_raw_provider(citation))

    entry = {
        "title": title,
        "doi": doi,
        "pmid": pmid,
        "provider_family": provider_family,
        "source_id": source_id,
        "year": citation.get("year"),
        "retracted": bool(citation.get("retracted", False)),
    }
    prefetched = _build_prefetched(citation, title)

    result = validate_core(
        entry,
        online=online_check,
        prefetched=prefetched,
    )

    details = result["details"]
    secondary_titles = [
        t for t in (details.get("crossref_fetched_title"), details.get("pubmed_fetched_title")) if t
    ]
    if details.get("title_verify_matched_title"):
        secondary_titles.append(str(details["title_verify_matched_title"]))

    payload = dict(citation)
    payload["provider_family"] = provider_family
    payload["doi"] = doi
    payload["pmid"] = pmid
    payload["retracted"] = details.get("retracted", False)
    payload["guard_verified"] = result["verified"]
    payload["reference_entry"] = build_reference_entry(payload, doi, pmid)
    payload["verification_details"] = {
        "title_similarity": details.get("title_similarity", 0.0),
        "failure_reasons": result["failure_reasons"],
        "confidence": result["confidence"],
        "needs_manual_review": result["needs_manual_review"],
        "secondary_titles": secondary_titles,
        "title_verified": details.get("title_verified", False),
        "title_verify_source": details.get("title_verify_source"),
        "title_verify_similarity": details.get("title_verify_similarity"),
        "retracted": details.get("retracted", False),
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Double-verify paper-search citation payloads for revise-sci")
    parser.add_argument("--paper-search-results", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--allow-unverified", action="store_true")
    parser.add_argument(
        "--fail-on-unverified",
        action="store_true",
        help="Hard gate: exit 2 if any row is unverified, even with --allow-unverified (fail-closed for DoD).",
    )
    args = parser.parse_args()

    online_check = args.live and not args.offline
    project_root = Path(args.project_root)
    project_root.mkdir(parents=True, exist_ok=True)
    payload = read_json(Path(args.paper_search_results), {"results": []})
    rows = payload.get("results", []) if isinstance(payload, dict) else payload

    validated_rows = []
    # Fail-closed. Empty rows means no citations verified, so treat as unverified.
    all_rows_guard_verified = bool(rows)
    verified_citation_count = 0
    total_citation_count = 0

    for row in rows or []:
        citations = []
        for citation in row.get("citations", []) or []:
            checked = validate_citation(citation, online_check=online_check)
            citations.append(checked)
            total_citation_count += 1
            if checked["guard_verified"]:
                verified_citation_count += 1
        # row_guard_verified ties the business-state row.confirmed flag to the
        # per-citation guard result (adapter-level; not a core concern).
        row_guard_verified = bool(row.get("confirmed")) and bool(citations) and all(c["guard_verified"] for c in citations)
        if not row_guard_verified:
            all_rows_guard_verified = False
        checked_row = dict(row)
        checked_row["citations"] = citations
        checked_row["guard_verified"] = row_guard_verified
        validated_rows.append(checked_row)

    report = {
        "summary": {
            "rows": len(validated_rows),
            "citations": total_citation_count,
            "verified_citations": verified_citation_count,
            "all_rows_guard_verified": all_rows_guard_verified,
            "online_check": online_check,
            "provider_policy": {"paper_search_only": True, "double_verification_required": True},
        },
        "results": validated_rows,
    }
    write_json(project_root / "paper_search_guard_report.json", report)
    write_json(project_root / "paper_search_validated.json", {"results": validated_rows})

    # --fail-on-unverified is the opt-in hard gate: it overrides --allow-unverified
    # so a DoD can turn the default WARN downgrade back into fail-closed (exit 2).
    if not all_rows_guard_verified and (args.fail_on_unverified or not args.allow_unverified):
        print(json.dumps({"ok": False, "summary": report["summary"]}, ensure_ascii=False))
        return 2

    print(json.dumps({"ok": True, "summary": report["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
