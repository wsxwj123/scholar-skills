#!/usr/bin/env python3
"""Unified citation hallucination guard for multiple writing skills.

Goals:
- Prevent fabricated references
- Prevent citation-index mismatch
- Enforce DOI/PMID/title/source traceability checks
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from citation_guard_core import (  # noqa: E402
    ALLOWED_PROVIDER_FAMILIES,
    FORBIDDEN_PROVIDER_FAMILIES,
    TITLE_VERIFY_THRESHOLD,
    _provider_family,
    check_bidirectional,
    check_completeness,
    check_recency,
    check_self_citation,
    entry_is_fresh_verified,
    validate_core,
)

# Citation-group matcher: [12], [1,4-7], [3; 5–9]. Expands ranges and lists.
_CITATION_GROUP_RE = re.compile(
    r"\[((?:\s*\d+(?:\s*[-–]\s*\d+)?\s*)(?:[,;]\s*\d+(?:\s*[-–]\s*\d+)?\s*)*)\]"
)


def _extract_cited_numbers(text: str) -> set[int]:
    """Every citation number appearing as [n] / [a,b-c] in manuscript text."""
    out: set[int] = set()
    for m in _CITATION_GROUP_RE.finditer(text):
        for token in re.split(r"\s*[,;]\s*", m.group(1).strip()):
            token = token.strip()
            if token.isdigit():
                out.add(int(token))
                continue
            rng = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", token)
            if rng:
                a, b = int(rng.group(1)), int(rng.group(2))
                out.update(range(min(a, b), max(a, b) + 1))
    return out


def _scan_cited_numbers(drafts_dir: Path) -> set[int]:
    out: set[int] = set()
    if not drafts_dir.exists():
        return out
    for md in drafts_dir.rglob("*.md"):
        try:
            out |= _extract_cited_numbers(md.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
    return out


def _entry_citation_number(entry: dict[str, Any]) -> int | None:
    for k in ("citation_number", "global_id", "id", "number", "ref_number"):
        v = entry.get(k)
        if v is None:
            continue
        try:
            return int(str(v).strip())
        except (ValueError, TypeError):
            continue
    return None


def run_integrity_gates(
    entries: list[dict[str, Any]],
    *,
    drafts_dir: Path | None,
    manuscript_authors: list[str],
    current_year: int,
    self_cite_threshold: float = 0.4,
    recency_window: int = 5,
    recency_min_ratio: float = 0.3,
) -> dict[str, Any]:
    """Run J4/J5/J7/A4 over a normalized entry list.

    Returns a report dict plus an ``exit_code``: non-zero when a fail-closed gate
    (J4 incomplete, or A4 broken) trips. J5/J7 are advisory (WARN) and never
    change the exit code.
    """
    # J4 — per-entry completeness.
    incomplete: list[dict[str, Any]] = []
    raw_only: list[int] = []
    partial: list[dict[str, Any]] = []
    for i, e in enumerate(entries):
        res = check_completeness(e)
        num = _entry_citation_number(e)
        if res["status"] == "incomplete":
            incomplete.append({"ref": num if num is not None else f"idx:{i}",
                               "missing_fields": res["missing_fields"]})
        elif res["status"] == "raw_only":
            raw_only.append(num if num is not None else i)
        elif res["missing_fields"]:
            partial.append({"ref": num if num is not None else f"idx:{i}",
                            "missing_fields": res["missing_fields"]})

    # J5 / J7 — corpus-level advisory.
    self_cite = check_self_citation(entries, manuscript_authors, threshold=self_cite_threshold)
    recency = check_recency(entries, current_year, window=recency_window,
                            min_recent_ratio=recency_min_ratio)

    # A4 — bidirectional (only when drafts are available to scan).
    bidirectional: dict[str, Any] | None = None
    if drafts_dir is not None:
        cited = _scan_cited_numbers(drafts_dir)
        listed = {n for n in (_entry_citation_number(e) for e in entries) if n is not None}
        bidirectional = check_bidirectional(cited, listed)

    j4_failed = bool(incomplete)
    a4_failed = bool(bidirectional and bidirectional["status"] == "fail")
    exit_code = 2 if (j4_failed or a4_failed) else 0

    return {
        "ok": exit_code == 0,
        "exit_code": exit_code,
        "j4_completeness": {
            "incomplete": incomplete,
            "raw_only_count": len(raw_only),
            "partial": partial,
            "strength": "fail-closed",
        },
        "j5_self_citation": {**self_cite, "strength": "warn"},
        "j7_recency": {**recency, "strength": "warn"},
        "a4_bidirectional": (
            {**bidirectional, "strength": "fail-closed"} if bidirectional is not None
            else {"status": "skipped", "reason": "no_drafts_dir", "strength": "fail-closed"}
        ),
    }


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")



def _normalize_index(raw: Any) -> tuple[list[dict[str, Any]], str]:
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)], "list"
    if isinstance(raw, dict):
        for key in ("entries", "papers", "items", "references", "data"):
            val = raw.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)], key
        vals = [v for v in raw.values() if isinstance(v, dict)]
        if vals:
            return vals, "dict_values"
    return [], "empty"


def _build_mcp_index(mcp_cache: Any) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not mcp_cache:
        return out

    entries: list[dict[str, Any]] = []
    if isinstance(mcp_cache, list):
        entries.extend(x for x in mcp_cache if isinstance(x, dict))
    elif isinstance(mcp_cache, dict):
        for key in ("entries", "papers", "items", "references", "data"):
            val = mcp_cache.get(key)
            if isinstance(val, list):
                entries.extend(x for x in val if isinstance(x, dict))
        for k, v in mcp_cache.items():
            if k in {"entries", "papers", "items", "references", "data"}:
                continue
            if isinstance(v, dict):
                entries.append(v)

    for e in entries:
        doi = str(e.get("doi") or "").strip().lower()
        pmid = str(e.get("pmid") or "").strip()
        if doi:
            out[f"doi:{doi}"] = e
        if pmid:
            out[f"pmid:{pmid}"] = e
    return out


def _resolve_mcp_record(entry: dict[str, Any], mcp_index: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    doi = str(entry.get("doi") or "").strip().lower()
    pmid = str(entry.get("pmid") or "").strip()
    if doi and f"doi:{doi}" in mcp_index:
        return mcp_index[f"doi:{doi}"]
    if pmid and f"pmid:{pmid}" in mcp_index:
        return mcp_index[f"pmid:{pmid}"]
    return None


def _entry_ref_id(entry: dict[str, Any], fallback_idx: int) -> str:
    for k in ("ref_number", "global_id", "id"):
        v = entry.get(k)
        if v is not None:
            return str(v)
    return f"idx:{fallback_idx}"


def validate_entry(
    entry: dict[str, Any],
    *,
    online_check: bool,
    mcp_index: dict[str, dict[str, Any]],
    require_mcp: bool,
    mcp_ttl_days: int,
    now_utc: datetime,
) -> dict[str, Any]:
    """Adapter: normalize a raw index entry, resolve its MCP record, delegate the
    verification to validate_core, then restore the skill's output contract.

    The output shape (verified / needs_manual_review / verification_confidence /
    verification_details with source_provider) is preserved byte-for-byte versus
    the pre-refactor baseline; only the check logic moved into the shared core.
    """
    source_provider = str(entry.get("source_provider") or "").strip()
    core_entry = {
        "title": entry.get("title"),
        "doi": entry.get("doi"),
        "pmid": entry.get("pmid"),
        "provider_family": _provider_family(source_provider),
        "source_id": entry.get("source_id"),
        "year": entry.get("year"),
        "retracted": entry.get("retracted", False),
    }
    mcp_record = _resolve_mcp_record(entry, mcp_index)
    result = validate_core(
        core_entry,
        online=online_check,
        require_mcp=require_mcp,
        mcp_record=mcp_record,
        mcp_ttl_days=mcp_ttl_days,
        now_utc=now_utc,
    )
    details = dict(result["details"])
    # Restore the raw source_provider field the baseline exposed under sources.
    sources = dict(details.get("sources", {}))
    sources["source_provider"] = source_provider
    details["sources"] = sources
    return {
        **entry,
        "verified": result["verified"],
        "needs_manual_review": result["needs_manual_review"],
        "verification_confidence": result["confidence"],
        "verification_details": details,
        # G0c: PMID pubtype 分类落库；无分类保留条目原值（缺 → unknown），不 clobber
        "article_type": (result.get("article_type") if result.get("article_type", "unknown") != "unknown"
                         else str(entry.get("article_type") or "unknown")),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Unified anti-hallucination citation guard")
    p.add_argument("--index", required=True, help="Path to literature index JSON")
    p.add_argument("--mcp-cache", default="", help="Path to MCP cache JSON")
    p.add_argument("--offline", action="store_true", help="Disable online check")
    p.add_argument("--mcp-ttl-days", type=int, default=30)
    p.add_argument("--require-mcp", action="store_true", help="Require MCP evidence; unresolved/stale MCP is blocking")
    p.add_argument("--manual-review", default="data/manual_review_queue.json")
    p.add_argument("--log", default="data/verification_run_log.json")
    p.add_argument("--report", default="data/citation_guard_report.json")
    p.add_argument("--write-back", action="store_true", help="Write verification fields back to index")
    # Integrity-gate mode (J4/J5/J7/A4). Independent of the online verifier above.
    p.add_argument("--gates", action="store_true",
                   help="Run citation-integrity gates (J4 completeness, J5 self-citation, "
                        "J7 recency, A4 bidirectional) instead of the online verifier")
    p.add_argument("--drafts-dir", default="manuscripts",
                   help="Manuscript directory scanned for [n] citations (A4)")
    p.add_argument("--project-config", default="project_config.json",
                   help="project_config.json holding manuscript authors (J5)")
    p.add_argument("--current-year", type=int, default=None,
                   help="Current year for J7 recency (default: system clock)")
    p.add_argument("--gates-report", default="data/citation_integrity_report.json")
    args = p.parse_args()

    index_path = Path(args.index)
    raw = load_json(index_path, {})
    entries, shape = _normalize_index(raw)

    if args.gates:
        cfg = load_json(Path(args.project_config), {})
        authors = None
        if isinstance(cfg, dict):
            # 兼容两种布局：根级 {"authors": [...]} 或嵌套 {"project_config": {"authors": [...]}}
            authors = cfg.get("authors")
            if authors is None and isinstance(cfg.get("project_config"), dict):
                authors = cfg["project_config"].get("authors")
        manuscript_authors = [str(a) for a in authors] if isinstance(authors, list) else []
        drafts_dir = Path(args.drafts_dir)
        current_year = args.current_year or datetime.now(timezone.utc).year
        gates = run_integrity_gates(
            entries,
            drafts_dir=drafts_dir if drafts_dir.exists() else None,
            manuscript_authors=manuscript_authors,
            current_year=current_year,
        )
        save_json(Path(args.gates_report), gates)
        print(json.dumps(gates, ensure_ascii=False, indent=2))
        return gates["exit_code"]

    mcp_cache = load_json(Path(args.mcp_cache), {}) if args.mcp_cache else {}
    mcp_index = _build_mcp_index(mcp_cache)

    t0 = time.perf_counter()
    now_utc = datetime.now(timezone.utc)
    ttl_days = max(0, int(args.mcp_ttl_days))
    checked: list[dict[str, Any]] = []
    reused_count = 0
    for e in entries:
        ent = dict(e)
        # L1 per-entry short-circuit. An entry already verified=True and still
        # within the TTL reuses its persisted verification_details (checked_at
        # comes from validate_core on the prior --write-back run) instead of
        # re-hitting Crossref/PubMed. Seeds (verified=false), stale, and
        # unverified entries all return False here and fall through to a full
        # online re-check, so retraction/freshness safety is unchanged.
        if entry_is_fresh_verified(ent, ttl_days, now_utc):
            reused_count += 1
            checked.append(ent)
            continue
        checked.append(
            validate_entry(
                ent,
                online_check=not args.offline,
                mcp_index=mcp_index,
                require_mcp=args.require_mcp,
                mcp_ttl_days=ttl_days,
                now_utc=now_utc,
            )
        )

    failure_counter: Counter[str] = Counter()
    advisory_counter: Counter[str] = Counter()
    advisory_ref_ids: dict[str, list[str]] = {}
    manual = []
    for i, e in enumerate(checked, 1):
        vd = e.get("verification_details", {})
        for r in vd.get("failure_reasons", []):
            failure_counter[str(r)] += 1
        # advisories 是不阻断的诊断通道：只做计数与定位（逐条 details 不带
        # --write-back 就会被丢掉），绝不参与 ok/status/退出码。
        for a in vd.get("advisories", []):
            code = str(a.get("code"))
            advisory_counter[code] += 1
            refs = advisory_ref_ids.setdefault(code, [])
            if len(refs) < 50:
                refs.append(_entry_ref_id(e, i))
        if e.get("needs_manual_review"):
            manual.append(
                {
                    "ref_id": _entry_ref_id(e, i),
                    "title": e.get("title"),
                    "doi": e.get("doi"),
                    "pmid": e.get("pmid"),
                    "failure_reasons": vd.get("failure_reasons", []),
                    "confidence_score": vd.get("confidence_score"),
                }
            )

    verified_count = sum(1 for e in checked if e.get("verified"))
    duration_ms = int((time.perf_counter() - t0) * 1000)
    status = "verified" if (checked and verified_count == len(checked)) else ("failed" if checked else "empty")

    report = {
        "ok": status == "verified",
        "status": status,
        "shape": shape,
        "checked_entries": len(checked),
        "verified_count": verified_count,
        "reused_fresh_verified_count": reused_count,
        "manual_review_count": len(manual),
        "avg_confidence": round(sum(int(e.get("verification_confidence", 0)) for e in checked) / len(checked), 2)
        if checked
        else 0.0,
        "failure_type_counts": dict(sorted(failure_counter.items())),
        "advisory_counts": dict(sorted(advisory_counter.items())),
        "advisory_refs": dict(sorted(advisory_ref_ids.items())),
        "duration_ms": duration_ms,
        "checked_at": now_utc.isoformat(),
        "online_check": not args.offline,
        "require_mcp": bool(args.require_mcp),
        "mcp_ttl_days": ttl_days,
        "provider_policy": {
            "allowed_provider_families": sorted(ALLOWED_PROVIDER_FAMILIES),
            "forbidden_provider_families": sorted(FORBIDDEN_PROVIDER_FAMILIES),
            "no_identifier_policy": "crossref/semanticscholar_by_title_verify_else_manual_review_queue",
            "title_verify_threshold": TITLE_VERIFY_THRESHOLD,
        },
    }

    save_json(Path(args.report), {"report": report, "manual_review_queue": manual})
    save_json(Path(args.manual_review), {"generated_at": now_utc.isoformat(), "count": len(manual), "entries": manual})

    run_log_path = Path(args.log)
    logs = load_json(run_log_path, {"runs": []})
    if not isinstance(logs, dict):
        logs = {"runs": []}
    runs = logs.get("runs") if isinstance(logs.get("runs"), list) else []
    runs.append(report)
    logs["runs"] = runs[-200:]
    save_json(run_log_path, logs)

    if args.write_back:
        if isinstance(raw, list):
            save_json(index_path, checked)
        elif isinstance(raw, dict):
            out = dict(raw)
            if shape in {"entries", "papers", "items", "references", "data"}:
                out[shape] = checked
            else:
                out["entries"] = checked
            md = out.get("metadata") if isinstance(out.get("metadata"), dict) else {}
            md.update({"verification_status": status, "last_updated": now_utc.isoformat(), "verification_stats": report})
            out["metadata"] = md
            save_json(index_path, out)

    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
