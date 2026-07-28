#!/usr/bin/env python3
"""Citation verification guard for reviewer-response-sci.

Thin adapter over the shared citation_guard_core.py (single source of truth for
verification logic). This layer owns: loading citation_registry.json's flat
entries[] table, normalizing each entry to the core schema, calling validate_core,
and writing the top-level report contract this skill's pipeline reads.

The report contract is unchanged from the previous standalone implementation:
run_pipeline.py and SKILL.md判定通过用顶层 status == "pass"，判定撤稿用顶层
retracted > 0（无 report.ok 嵌套层）。CLI flags are unchanged.

Usage:
    python citation_guard.py --project-root /path/to/project
    python citation_guard.py --project-root /path/to/project --offline
    python citation_guard.py --project-root /path/to/project --fail-on-unverified
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from citation_guard_core import _provider_family, validate_core


def _normalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Map a flat registry entry to the core's normalized schema.

    The field-name bridge stays in this adapter. This skill's registry uses
    source_provider, which core expects as provider_family (already a family).
    """
    return {
        "title": entry.get("title"),
        "doi": entry.get("doi"),
        "pmid": entry.get("pmid"),
        "provider_family": _provider_family(str(entry.get("source_provider") or "")),
        "source_id": entry.get("source_id") or entry.get("source_provider"),
        "year": entry.get("year"),
        "retracted": entry.get("retracted", False),
    }


def validate_entry(entry: dict[str, Any], *, online: bool) -> dict[str, Any]:
    """Validate one registry entry via the shared core, then shape the per-entry
    result back into this skill's existing structure.

    Note: source_trace_missing from core is downgraded here. This skill's registry
    does not always carry both provider and source_id, and traceability is not part
    of the historical pass criterion for reviewer-response; the previous standalone
    guard never failed on it. Provider allow/forbid, identifier, title, DOI/PMID,
    and retraction checks remain authoritative.
    """
    normalized = _normalize_entry(entry)
    core = validate_core(normalized, online=online)
    details = core.get("details", {})

    failures = [r for r in core["failure_reasons"] if r != "source_trace_missing"]
    verified = len(failures) == 0
    retracted = bool(details.get("retracted"))

    return {
        "ref_number": entry.get("ref_number"),
        "title": normalized["title"] and str(normalized["title"]).strip() or "",
        "doi": str(entry.get("doi") or "").strip(),
        "pmid": str(entry.get("pmid") or "").strip(),
        "verified": verified,
        "confidence": core["confidence"],
        "title_similarity": details.get("title_similarity", 0.0),
        "title_verified": details.get("title_verified", False),
        "title_verify_source": details.get("title_verify_source"),
        "title_verify_similarity": details.get("title_verify_similarity"),
        "failures": failures,
        "retracted": retracted,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Citation guard for reviewer-response-sci")
    parser.add_argument("--project-root", required=True, help="Project root directory")
    parser.add_argument("--offline", action="store_true", help="Skip online API checks")
    parser.add_argument("--fail-on-unverified", action="store_true", help="Exit non-zero if any entry fails")
    args = parser.parse_args()

    root = Path(args.project_root)
    registry_path = root / "citation_registry.json"

    if not registry_path.exists():
        print("CITATION_GUARD: SKIP (no citation_registry.json)")
        return 0

    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"CITATION_GUARD: ERROR reading registry: {e}")
        return 1

    entries = registry.get("entries", [])
    # Business semantic: an empty registry is a valid PASS. Reviewer responses
    # often add no new references; do not let the core's empty policy turn this
    # into a failure. Explicit branch, handled in the adapter.
    if not entries:
        print("CITATION_GUARD: PASS (empty registry)")
        return 0

    t0 = time.perf_counter()
    now_utc = datetime.now(timezone.utc)
    online = not args.offline

    results = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        result = validate_entry(entry, online=online)
        results.append(result)
        if online:
            time.sleep(0.3)  # rate limit courtesy

    verified_count = sum(1 for r in results if r["verified"])
    failed = [r for r in results if not r["verified"]]
    retracted = [r for r in results if r.get("retracted")]
    duration_ms = int((time.perf_counter() - t0) * 1000)

    report = {
        "status": "pass" if verified_count == len(results) else "warn",
        "total": len(results),
        "verified": verified_count,
        "failed": len(failed),
        "retracted": len(retracted),
        "avg_confidence": round(sum(r["confidence"] for r in results) / len(results), 1) if results else 0,
        "duration_ms": duration_ms,
        "checked_at": now_utc.isoformat(),
        "online": online,
        "failed_entries": [
            {"ref_number": r["ref_number"], "title": r["title"][:60], "failures": r["failures"]}
            for r in failed
        ],
        "retracted_entries": [
            {"ref_number": r["ref_number"], "title": r["title"][:60]}
            for r in retracted
        ],
    }

    # Write report
    report_path = root / "logs" / "citation_guard_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Print summary
    if retracted:
        print("CITATION_GUARD: FAIL (retracted references — must be removed)")
        for r in retracted:
            print(f"  - [ref {r['ref_number']}] {r['title'][:50]}: RETRACTED")
    if failed:
        non_retracted_failed = [r for r in failed if not r.get("retracted")]
        if non_retracted_failed:
            print("CITATION_GUARD: WARN")
            for r in non_retracted_failed:
                print(f"  - [ref {r['ref_number']}] {r['title'][:50]}: {', '.join(r['failures'])}")
    if not failed and not retracted:
        print(f"CITATION_GUARD: PASS ({verified_count}/{len(results)} verified)")

    if retracted:
        return 1
    if args.fail_on_unverified and failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
