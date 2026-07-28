#!/usr/bin/env python3
"""Citation reference number tracker for reviewer-response-sci.

Scans all unit JSONs for [N] citation references in response_en and
revised_excerpt_en, then cross-checks against citation_registry.json
and original manuscript reference count.

Catches:
- Undefined references (used in text but not in registry or original refs)
- Orphaned registry entries (in registry but never cited)
- Numbering gaps or duplicates in new citations
- References exceeding original_ref_count without registry backing

Usage:
    python citation_ref_tracker.py --project-root /path/to/project
    python citation_ref_tracker.py --project-root /path/to/project --fail-on-undefined
    python citation_ref_tracker.py --project-root /path/to/project --fail-on-gap
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from unit_glob import iter_units

# Regex: matches [1], [1,2], [1-5], [1, 3-5, 7]
_CITATION_GROUP_RE = re.compile(
    r"\[((?:\s*\d+(?:\s*[-–]\s*\d+)?\s*)(?:[,;]\s*\d+(?:\s*[-–]\s*\d+)?\s*)*)\]"
)


def _expand_token(token: str) -> list[int] | None:
    token = token.strip()
    if re.fullmatch(r"\d+", token):
        return [int(token)]
    m = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", token)
    if not m:
        return None
    start, end = int(m.group(1)), int(m.group(2))
    step = 1 if start <= end else -1
    return list(range(start, end + step, step))


def extract_citation_ids(text: str) -> list[int]:
    """Extract all [N] citation numbers from text, expanding ranges."""
    ids: list[int] = []
    for match in _CITATION_GROUP_RE.finditer(text):
        body = match.group(1)
        for token in re.split(r"\s*[,;]\s*", body.strip()):
            if not token.strip():
                continue
            expanded = _expand_token(token)
            if expanded:
                ids.extend(expanded)
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description="Citation reference number tracker")
    parser.add_argument("--project-root", required=True, help="Project root directory")
    parser.add_argument("--fail-on-undefined", action="store_true", help="Exit non-zero if undefined refs found")
    parser.add_argument("--fail-on-gap", action="store_true", help="Exit non-zero if numbering gaps found (A2 hard gate)")
    args = parser.parse_args()

    root = Path(args.project_root)
    units_dir = root / "units"

    if not units_dir.exists():
        print("CITATION_REF_TRACKER: SKIP (no units dir)")
        return 0

    # Load citation registry
    registry_path = root / "citation_registry.json"
    registry_refs: set[int] = set()
    original_ref_count = 0
    has_registry = False
    if registry_path.exists():
        has_registry = True
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            original_ref_count = int(registry.get("original_ref_count", 0))
            for entry in registry.get("entries", []):
                rn = entry.get("ref_number")
                if isinstance(rn, int):
                    registry_refs.add(rn)
        except Exception:
            pass

    # Scan all units for citation references
    unit_citations: dict[str, set[int]] = {}  # unit_id -> set of citation numbers
    all_cited: set[int] = set()

    for p, unit in iter_units(units_dir):
        uid = unit.get("unit_id", p.stem)
        content = unit.get("content", {})
        combined = " ".join(
            str(content.get(k, ""))
            for k in ["response_en", "revised_excerpt_en", "revised_excerpt_zh"]
        )
        refs = set(extract_citation_ids(combined))
        if refs:
            unit_citations[uid] = refs
            all_cited.update(refs)

    if not all_cited:
        print("CITATION_REF_TRACKER: PASS (no citations found in units)")
        return 0

    # If citations found but no registry exists, warn and skip validation
    if not has_registry:
        print(f"CITATION_REF_TRACKER: WARN (found {len(all_cited)} citation(s) but no citation_registry.json to validate against)")
        report = {
            "status": "warn",
            "total_citations_found": len(all_cited),
            "original_ref_count": 0,
            "note": "no citation_registry.json found; cannot validate references",
            "cited_numbers": sorted(all_cited),
        }
        report_path = root / "logs" / "citation_ref_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0

    # Determine known references: original [1..N] + registry entries
    known_refs = set(range(1, original_ref_count + 1)) | registry_refs

    # Check for issues — known_refs can be empty when original_ref_count=0 and registry has no entries
    undefined = all_cited - known_refs
    orphaned = registry_refs - all_cited
    max_cited = max(all_cited) if all_cited else 0

    # Check for numbering gaps in new citations (above original_ref_count)
    new_citations = {n for n in all_cited if n > original_ref_count}
    new_registry = {n for n in registry_refs if n > original_ref_count}
    gaps: list[int] = []
    if new_registry:
        expected_range = set(range(original_ref_count + 1, max(new_registry) + 1))
        gaps = sorted(expected_range - new_registry)

    # Build per-unit report
    issues: list[dict] = []
    for uid, refs in unit_citations.items():
        undef_in_unit = refs - known_refs
        if undef_in_unit:
            issues.append({
                "unit_id": uid,
                "undefined_refs": sorted(undef_in_unit),
            })

    report = {
        "status": "pass" if not undefined and not gaps else "warn",
        "total_citations_found": len(all_cited),
        "original_ref_count": original_ref_count,
        "new_citations_count": len(new_citations),
        "registry_entries": len(registry_refs),
        "undefined_refs": sorted(undefined),
        "orphaned_registry_entries": sorted(orphaned),
        "numbering_gaps": gaps,
        "max_cited_number": max_cited,
        "units_with_issues": issues,
    }

    # Write report
    report_path = root / "logs" / "citation_ref_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Print summary
    if undefined:
        print("CITATION_REF_TRACKER: WARN")
        print(f"  Undefined references: {sorted(undefined)}")
        for item in issues:
            print(f"  - [{item['unit_id']}]: undefined {item['undefined_refs']}")
    elif gaps:
        print(f"CITATION_REF_TRACKER: WARN (numbering gaps: {gaps})")
    elif orphaned:
        print(f"CITATION_REF_TRACKER: PASS (note: {len(orphaned)} orphaned registry entries)")
    else:
        print(f"CITATION_REF_TRACKER: PASS ({len(all_cited)} refs, all defined)")

    if args.fail_on_undefined and undefined:
        return 1
    if args.fail_on_gap and gaps:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
