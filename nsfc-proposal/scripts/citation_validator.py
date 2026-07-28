#!/usr/bin/env python3
"""Citation validation and matrix checks for nsfc-proposal.

Dual-track validation:
- Track A: MCP evidence cache (paper-search results)
- Track B: Official HTTP sources (PubMed/Crossref)
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import sys as _sys

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in _sys.path:
    _sys.path.insert(0, _SCRIPTS_DIR)
import citation_guard_core as core

DOI_RE = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE)
PMID_RE = re.compile(r"^\d{4,10}$")
CIT_RE = re.compile(r"\[\d+(?:[-,，]\d+)*\]")
TITLE_TOKEN_RE = re.compile(r"[a-z0-9\u4e00-\u9fff]+")

CACHE_SCHEMA_VERSION = "1.0"
ALLOWED_PROVIDER_FAMILIES = {"paper-search", "pubmed-cli"}
FORBIDDEN_PROVIDER_FAMILIES = {"tavily", "websearch", "openalex-cli"}
HARD_FAIL_REASONS = {
    "retracted",
    "id_mismatch",
    "doi_invalid_or_unresolved",
    "pmid_invalid_or_unresolved",
    "identifier_missing",
    "source_provider_forbidden",
    "mcp_unresolved",
    "mcp_stale",
    "mcp_timestamp_missing",
}
SOFT_FAIL_REASONS = {
    "source_unreachable",
    "title_mismatch",
    "context_mismatch",
    "title_missing",
}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_citation_numbers(text: str) -> list[int]:
    numbers: list[int] = []
    for match in CIT_RE.findall(text):
        inner = match[1:-1].replace("，", ",")
        for part in inner.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                lo, hi = part.split("-", 1)
                numbers.extend(range(int(lo), int(hi) + 1))
            else:
                numbers.append(int(part))
    return numbers


def _http_get_json(url: str, timeout_sec: float = 8.0) -> dict[str, Any] | None:
    req = urllib.request.Request(url, headers={"User-Agent": "nsfc-proposal-skill/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            return json.loads(body)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None


def _normalize_title(title: str) -> str:
    t = title.lower().strip()
    t = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _title_tokens(title: str) -> set[str]:
    return set(TITLE_TOKEN_RE.findall(_normalize_title(title)))


def _provider_family(entry: dict[str, Any]) -> str | None:
    """Map an entry's recorded retrieval source to a provider family.

    Reads the existing literature_index field ``search_source`` (e.g. "pubmed"),
    falling back to ``source_provider``/``provider`` if present. Returns None when
    no source is recorded so absent provenance does not silently fail an entry.
    """
    raw = str(
        entry.get("search_source")
        or entry.get("source_provider")
        or entry.get("provider")
        or ""
    ).strip().lower()
    if not raw:
        return None
    if raw.startswith("paper-search"):
        return "paper-search"
    if raw.startswith("pubmed") or raw in ("edirect", "ncbi", "esearch", "crossref"):
        return "pubmed-cli"
    if raw.startswith("tavily"):
        return "tavily"
    if raw in ("openalex", "openalex-cli", "pyalex"):
        return "openalex-cli"
    if "websearch" in raw or "web-search" in raw or "web_search" in raw:
        return "websearch"
    return raw


def _title_similarity(a: str, b: str) -> float:
    na = _normalize_title(a)
    nb = _normalize_title(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0

    ta = _title_tokens(a)
    tb = _title_tokens(b)
    jacc = (len(ta & tb) / len(ta | tb)) if ta and tb else 0.0

    # fallback char overlap ratio for small token sets
    short = min(len(na), len(nb)) / max(len(na), len(nb))
    contain_bonus = 0.1 if (na in nb or nb in na) else 0.0
    return min(1.0, 0.75 * jacc + 0.25 * short + contain_bonus)


def _titles_match(a: str, b: str, threshold: float = 0.72) -> tuple[bool, float]:
    score = _title_similarity(a, b)
    return score >= threshold, score


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    s = value.strip()
    if not s:
        return None
    try:
        if len(s) == 10 and s.count("-") == 2:
            return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _is_mcp_fresh(record: dict[str, Any], ttl_days: int, now_utc: datetime) -> tuple[bool, str | None]:
    if ttl_days <= 0:
        return True, None
    checked_at = _parse_dt(str(record.get("verified_at") or record.get("checked_at") or ""))
    if checked_at is None:
        return False, "mcp_timestamp_missing"
    if checked_at < now_utc - timedelta(days=ttl_days):
        return False, "mcp_stale"
    return True, None


def _fetch_crossref_by_doi(doi: str) -> dict[str, Any] | None:
    encoded = urllib.parse.quote(doi, safe="")
    payload = _http_get_json(f"https://api.crossref.org/works/{encoded}")
    if not payload or "message" not in payload:
        return None

    msg = payload["message"]
    title = (msg.get("title") or [""])[0] if isinstance(msg.get("title"), list) else ""
    relation = msg.get("relation") or {}
    is_retracted = False
    if isinstance(relation, dict):
        for k in relation.keys():
            if "retract" in str(k).lower():
                is_retracted = True
                break

    return {
        "source": "crossref",
        "title": title or "",
        "doi": doi,
        "pmid": None,
        "retracted": is_retracted,
    }


def _fetch_pubmed_by_pmid(pmid: str) -> dict[str, Any] | None:
    payload = _http_get_json(
        f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmid}&retmode=json"
    )
    if not payload or "result" not in payload:
        return None

    result = payload["result"].get(str(pmid))
    if not isinstance(result, dict):
        return None

    title = result.get("title") or ""
    article_ids = result.get("articleids") or []
    doi = None
    for aid in article_ids:
        if isinstance(aid, dict) and str(aid.get("idtype", "")).lower() == "doi":
            doi = aid.get("value")
            break

    pubtypes = result.get("pubtype") or []
    is_retracted = any("retract" in str(x).lower() for x in pubtypes)

    return {
        "source": "pubmed",
        "title": title,
        "doi": doi,
        "pmid": str(pmid),
        "retracted": is_retracted,
    }


def _build_mcp_index(mcp_cache: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not mcp_cache:
        return out

    entries: list[dict[str, Any]] = []
    if isinstance(mcp_cache, dict):
        if isinstance(mcp_cache.get("entries"), list):
            entries.extend(x for x in mcp_cache.get("entries", []) if isinstance(x, dict))
        for k, v in mcp_cache.items():
            if k == "entries":
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


def _context_check(entry: dict[str, Any], p1_text: str | None) -> bool | None:
    if "P1_立项依据" not in (entry.get("used_in_sections") or []):
        return None
    if p1_text is None:
        return None

    ref = entry.get("ref_number")
    if ref is None:
        return False

    cited = f"[{ref}]" in p1_text
    key_finding = (entry.get("key_finding") or "").strip()
    if not key_finding:
        return False

    return cited


def _classify_failure_reasons(reasons: list[str]) -> dict[str, list[str]]:
    hard = [r for r in reasons if r in HARD_FAIL_REASONS]
    soft = [r for r in reasons if r in SOFT_FAIL_REASONS]
    info = [r for r in reasons if r not in HARD_FAIL_REASONS and r not in SOFT_FAIL_REASONS]
    return {"hard": hard, "soft": soft, "info": info}


def _confidence_score(
    *,
    title_similarity: float,
    doi_valid: bool | None,
    pmid_match: bool | None,
    id_cross_match: bool,
    mcp_ok: bool,
    mcp_fresh: bool,
    http_ok: bool,
    online_check: bool,
    retracted: bool,
    context_check: bool | None,
) -> int:
    score = 0.0
    score += max(0.0, min(1.0, title_similarity)) * 35.0

    if doi_valid is True:
        score += 18
    elif doi_valid is False:
        score -= 8

    if pmid_match is True:
        score += 18
    elif pmid_match is False:
        score -= 8

    score += 10 if id_cross_match else -12

    if mcp_ok:
        score += 8
    if mcp_ok and not mcp_fresh:
        score -= 10

    if online_check:
        score += 8 if http_ok else -8
    else:
        score += 4

    if context_check is True:
        score += 3
    elif context_check is False:
        score -= 6

    if retracted:
        score -= 60

    return int(max(0, min(100, round(score))))


def validate_entry(
    entry: dict[str, Any],
    p1_text: str | None = None,
    online_check: bool = True,
    mcp_index: dict[str, dict[str, Any]] | None = None,
    mcp_ttl_days: int = 30,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    now_utc = now_utc or datetime.now(timezone.utc)

    doi = (entry.get("doi") or "").strip()
    pmid = str(entry.get("pmid") or "").strip()
    title = (entry.get("title") or "").strip()

    # Provider family stays in this adapter (reads search_source + back-compat
    # fallback). core only accepts an already-mapped family string.
    provider_family = _provider_family(entry)
    provider_forbidden = provider_family in FORBIDDEN_PROVIDER_FAMILIES

    # MCP resolution / freshness is nsfc-specific (dual-track cache) and kept
    # local; core's require_mcp path is bypassed (require_mcp=False below).
    mcp_record = _resolve_mcp_record(entry, mcp_index or {}) if mcp_index else None
    mcp_ok = bool(mcp_record)
    mcp_fresh, mcp_fresh_reason = _is_mcp_fresh(mcp_record or {}, mcp_ttl_days, now_utc) if mcp_ok else (False, None)

    # P1 citation-context check is nsfc-specific and kept local.
    context_check = _context_check(entry, p1_text)

    # Delegate single-entry verification (title / DOI / PMID / cross-match /
    # retraction / provider) to the shared core. require_identifier=True keeps
    # the nsfc rule that an entry with no DOI/PMID hard-fails.
    entry_normalized = {
        "title": title,
        "doi": doi,
        "pmid": pmid,
        "provider_family": provider_family or "",
        "source_id": doi or pmid or "",
        "year": entry.get("year"),
        "retracted": bool(entry.get("retracted", False))
        or bool((mcp_record or {}).get("retracted", False)),
    }
    core_result = core.validate_core(
        entry_normalized,
        online=online_check,
        require_mcp=False,
        mcp_record=mcp_record,
        require_identifier=True,
        mcp_ttl_days=mcp_ttl_days,
        now_utc=now_utc,
    )
    core_details = core_result.get("details", {})

    # Map core's reason vocabulary back to nsfc's. Only reasons nsfc already
    # classifies (hard/soft) are adopted; core-only reasons (source_trace_missing,
    # year_unreasonable, per-source title splits, etc.) are not surfaced here so
    # the hard/soft/info semantics and pass/fail status are unchanged.
    _adoptable = HARD_FAIL_REASONS | SOFT_FAIL_REASONS
    failure_reasons = [r for r in core_result.get("failure_reasons", []) if r in _adoptable]

    # Pull derived signals from core's details for the nsfc details contract.
    title_match = bool(core_details.get("title_match"))
    title_similarity = float(core_details.get("title_similarity") or 0.0)
    doi_valid = core_details.get("doi_valid")
    pmid_match = core_details.get("pmid_match")
    id_cross_match = bool(core_details.get("id_cross_match", True))
    retracted = bool(core_details.get("retracted", False))
    core_sources = core_details.get("sources", {})
    crossref = bool(core_sources.get("crossref"))
    pubmed = bool(core_sources.get("pubmed"))
    http_ok = (crossref or pubmed) if online_check else True

    sources = {
        "mcp": bool(mcp_record),
        "crossref": crossref,
        "pubmed": pubmed,
        "crossref_attempted": bool(online_check and doi and DOI_RE.match(doi)),
        "pubmed_attempted": bool(online_check and pmid and PMID_RE.match(pmid)),
        "online_check": online_check,
        "mcp_ttl_days": mcp_ttl_days,
    }

    # nsfc-specific failure reasons (MCP track + P1 context) appended locally,
    # preserving the original "no MCP record => hard fail" semantics.
    if context_check is False:
        failure_reasons.append("context_mismatch")
    if not mcp_ok:
        failure_reasons.append("mcp_unresolved")
    elif not mcp_fresh:
        failure_reasons.append(mcp_fresh_reason or "mcp_stale")

    levels = _classify_failure_reasons(failure_reasons)
    needs_manual_review = bool(levels["soft"])

    confidence_score = _confidence_score(
        title_similarity=title_similarity,
        doi_valid=doi_valid,
        pmid_match=pmid_match,
        id_cross_match=id_cross_match,
        mcp_ok=mcp_ok,
        mcp_fresh=mcp_fresh,
        http_ok=http_ok,
        online_check=online_check,
        retracted=retracted,
        context_check=context_check,
    )

    verified = len(failure_reasons) == 0

    details = {
        "provider_family": provider_family,
        "provider_forbidden": provider_forbidden,
        "title_match": title_match,
        "title_similarity": round(title_similarity, 4),
        "doi_valid": doi_valid,
        "pmid_match": pmid_match,
        "id_cross_match": id_cross_match,
        "retracted": retracted,
        "context_check": context_check,
        "checked_at": now_utc.isoformat(),
        "sources": sources,
        "failure_reasons": failure_reasons,
        "hard_fail_reasons": levels["hard"],
        "soft_fail_reasons": levels["soft"],
        "info_fail_reasons": levels["info"],
        "has_hard_fail": bool(levels["hard"]),
        "has_soft_fail": bool(levels["soft"]),
        "needs_manual_review": needs_manual_review,
        "confidence_score": confidence_score,
    }

    entry["verification_details"] = details
    entry["verified"] = verified
    entry["verification_confidence"] = confidence_score
    entry["needs_manual_review"] = needs_manual_review
    return entry


def _normalize_index(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        data = dict(raw)
        entries = data.get("entries")
        if not isinstance(entries, list):
            data["entries"] = []
        data.setdefault("metadata", {})
        return data
    if isinstance(raw, list):
        return {"metadata": {}, "entries": raw}
    return {"metadata": {}, "entries": []}


def _normalize_mcp_cache(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"metadata": {"schema_version": CACHE_SCHEMA_VERSION}, "entries": []}

    data = dict(raw)
    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    metadata.setdefault("schema_version", CACHE_SCHEMA_VERSION)
    data["metadata"] = metadata

    entries: list[dict[str, Any]] = []
    if isinstance(data.get("entries"), list):
        entries.extend(x for x in data.get("entries", []) if isinstance(x, dict))

    for k, v in data.items():
        if k in {"entries", "metadata"}:
            continue
        if isinstance(v, dict):
            entries.append(v)

    data["entries"] = entries
    return data


def verify_all(
    index: dict[str, Any] | list[dict[str, Any]],
    p1_text: str | None = None,
    online_check: bool = True,
    mcp_index: dict[str, dict[str, Any]] | None = None,
    mcp_ttl_days: int = 30,
    require_mcp: bool = False,
    mcp_schema_version: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    idx = _normalize_index(index)
    entries = idx.get("entries", [])

    t0 = time.perf_counter()
    now_utc = datetime.now(timezone.utc)

    # L1 short-circuit: an entry already verified within the freshness window
    # reuses its persisted verified + verification_details instead of re-hitting
    # Crossref/PubMed. entry_is_fresh_verified only returns True when the RAW
    # entry has verified is True, so a downgraded/unverified entry (e.g. one
    # carrying mcp_unresolved) is never short-circuited and still re-verifies
    # below; the require_mcp downgrade further down is therefore not bypassed.
    out: list[dict[str, Any]] = []
    for e in entries:
        if core.entry_is_fresh_verified(e, mcp_ttl_days, now_utc):
            out.append(dict(e))
            continue
        out.append(
            validate_entry(
                dict(e),
                p1_text=p1_text,
                online_check=online_check,
                mcp_index=mcp_index,
                mcp_ttl_days=mcp_ttl_days,
                now_utc=now_utc,
            )
        )

    if require_mcp:
        for e in out:
            details = e.get("verification_details") or {}
            reasons = list(details.get("failure_reasons") or [])
            if "mcp_unresolved" in reasons and e.get("verified"):
                e["verified"] = False
                details["failure_reasons"] = reasons
                e["verification_details"] = details

    all_ok = all(e.get("verified") for e in out) if out else False
    any_ok = any(e.get("verified") for e in out)
    status = "verified" if all_ok else ("partial" if any_ok else "failed")

    failure_counter: Counter[str] = Counter()
    confidence_values = []
    manual_review_queue = []
    hard_fail_entries = 0
    soft_fail_entries = 0
    for e in out:
        vd = e.get("verification_details", {})
        confidence_values.append(int(vd.get("confidence_score", 0)))
        for reason in vd.get("failure_reasons", []):
            failure_counter[str(reason)] += 1
        if vd.get("has_hard_fail"):
            hard_fail_entries += 1
        if vd.get("has_soft_fail"):
            soft_fail_entries += 1
        if e.get("needs_manual_review"):
            manual_review_queue.append(
                {
                    "ref_number": e.get("ref_number"),
                    "title": e.get("title"),
                    "doi": e.get("doi"),
                    "pmid": e.get("pmid"),
                    "failure_reasons": vd.get("failure_reasons", []),
                    "hard_fail_reasons": vd.get("hard_fail_reasons", []),
                    "soft_fail_reasons": vd.get("soft_fail_reasons", []),
                    "confidence_score": vd.get("confidence_score"),
                }
            )

    duration_ms = int((time.perf_counter() - t0) * 1000)

    stats_payload = {
        "checked_entries": len(out),
        "verified_count": sum(1 for e in out if e.get("verified")),
        "manual_review_count": len(manual_review_queue),
        "hard_fail_entries": hard_fail_entries,
        "soft_fail_entries": soft_fail_entries,
        "avg_confidence": round((sum(confidence_values) / len(confidence_values)), 2) if confidence_values else 0.0,
        "failure_type_counts": dict(sorted(failure_counter.items())),
        "duration_ms": duration_ms,
        "online_check": online_check,
        "mcp_ttl_days": mcp_ttl_days,
        "require_mcp": require_mcp,
        "checked_at": now_utc.isoformat(),
    }

    idx["entries"] = out
    idx.setdefault("metadata", {})["verification_status"] = status
    idx["metadata"]["last_updated"] = now_utc.isoformat()
    idx["metadata"]["total_count"] = len(out)
    idx["metadata"]["recent_5yr_count"] = sum(1 for e in out if e.get("is_recent_5yr"))
    idx["metadata"]["cn_journal_count"] = sum(1 for e in out if e.get("is_cn_journal"))
    idx["metadata"]["mcp_entries_count"] = len(mcp_index or {})
    idx["metadata"]["mcp_cache_schema_version"] = mcp_schema_version or CACHE_SCHEMA_VERSION
    idx["metadata"]["verification_stats"] = stats_payload

    return idx, stats_payload, manual_review_queue


def _entry_ref_number(entry: dict[str, Any]) -> int | None:
    v = entry.get("ref_number")
    if v is None:
        return None
    try:
        return int(str(v).strip())
    except (ValueError, TypeError):
        return None


def run_integrity_gates(
    entries: list[dict[str, Any]],
    *,
    applicant_authors: list[str],
    current_year: int,
    self_cite_threshold: float = 0.4,
    recency_window: int = 5,
    recency_min_ratio: float = 0.3,
) -> dict[str, Any]:
    """J4/J5/J7 over the literature index entries.

    J4 (completeness) is fail-closed: any incomplete entry -> exit_code 2.
    J5 (self-citation) / J7 (recency) are advisory (WARN) and never change the
    exit code. A4 (bidirectional) is intentionally NOT here: matrix-check already
    covers the three-way P1/index/REF integrity.
    """
    incomplete: list[dict[str, Any]] = []
    raw_only: list[int] = []
    partial: list[dict[str, Any]] = []
    for i, e in enumerate(entries):
        res = core.check_completeness(e)
        num = _entry_ref_number(e)
        ref_id = num if num is not None else f"idx:{i}"
        if res["status"] == "incomplete":
            incomplete.append({"ref": ref_id, "missing_fields": res["missing_fields"]})
        elif res["status"] == "raw_only":
            raw_only.append(num if num is not None else i)
        elif res["missing_fields"]:
            partial.append({"ref": ref_id, "missing_fields": res["missing_fields"]})

    self_cite = core.check_self_citation(entries, applicant_authors, threshold=self_cite_threshold)
    recency = core.check_recency(entries, current_year, window=recency_window,
                                 min_recent_ratio=recency_min_ratio)

    # used_in_sections 升为检索登记必填（决策14/§2.6）：缺/空 → 归"未分配"、只 WARN 不改退出码，
    # 渐进回填（存量项目兼容）。切片按 used_in_sections 过滤，未分配条目不会被派进任何节。
    unassigned = []
    for i, e in enumerate(entries):
        if not (e.get("used_in_sections") or []):
            num = _entry_ref_number(e)
            unassigned.append(num if num is not None else f"idx:{i}")

    exit_code = 2 if incomplete else 0

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
        "used_in_sections_registry": {
            "unassigned": unassigned,
            "unassigned_count": len(unassigned),
            "note": "used_in_sections 为检索登记必填；缺者归未分配、须回填，切片不含它们",
            "strength": "warn",
        },
    }


def _ordered_unique(values: list[int]) -> list[int]:
    seen = set()
    ordered = []
    for v in values:
        if v in seen:
            continue
        seen.add(v)
        ordered.append(v)
    return ordered


def matrix_check(p1_text: str, index: dict[str, Any], ref_text: str) -> dict[str, Any]:
    p1_refs_all = extract_citation_numbers(p1_text)
    p1_refs = set(p1_refs_all)

    idx_refs = {
        int(e.get("ref_number"))
        for e in index.get("entries", [])
        if e.get("ref_number") is not None and "P1_立项依据" in (e.get("used_in_sections") or [])
    }

    ref_refs_all = extract_citation_numbers(ref_text)
    ref_refs = set(ref_refs_all)

    orphan_citations = sorted(p1_refs - idx_refs)
    orphan_entries = sorted(idx_refs - p1_refs)
    ref_missing = sorted(p1_refs - ref_refs)
    ref_extra = sorted(ref_refs - p1_refs)

    p1_first_order = _ordered_unique(p1_refs_all)
    ref_order = _ordered_unique(ref_refs_all)
    order_match = p1_first_order == ref_order

    three_way_match = p1_refs == idx_refs == ref_refs
    ok = not orphan_citations and not orphan_entries and not ref_missing and not ref_extra and order_match and three_way_match

    return {
        "ok": ok,
        "orphan_citations": orphan_citations,
        "orphan_entries": orphan_entries,
        "ref_missing": ref_missing,
        "ref_extra": ref_extra,
        "order_match": order_match,
        "three_way_match": three_way_match,
        "p1_first_order": p1_first_order,
        "ref_order": ref_order,
        "p1_count": len(p1_refs),
        "index_count": len(idx_refs),
        "ref_count": len(ref_refs),
    }


def find_orphans(p1_text: str, index: dict[str, Any]) -> dict[str, list[int]]:
    p1_refs = set(extract_citation_numbers(p1_text))
    idx_refs = {
        int(e.get("ref_number"))
        for e in index.get("entries", [])
        if e.get("ref_number") is not None and "P1_立项依据" in (e.get("used_in_sections") or [])
    }
    return {
        "orphan_citations": sorted(p1_refs - idx_refs),
        "orphan_entries": sorted(idx_refs - p1_refs),
    }


def reorder_entries_by_p1(index: dict[str, Any], p1_text: str) -> dict[str, Any]:
    order = _ordered_unique(extract_citation_numbers(p1_text))
    by_ref = {int(e["ref_number"]): e for e in index.get("entries", []) if e.get("ref_number") is not None}

    new_entries: list[dict[str, Any]] = []
    for n in order:
        if n in by_ref:
            new_entries.append(by_ref[n])

    for n in sorted(by_ref.keys()):
        if n not in order:
            new_entries.append(by_ref[n])

    for i, e in enumerate(new_entries, 1):
        e["ref_number"] = i

    index["entries"] = new_entries
    index.setdefault("metadata", {})["last_updated"] = datetime.now(timezone.utc).isoformat()
    return index


def stats(index: dict[str, Any]) -> dict[str, Any]:
    entries = index.get("entries", [])
    meta = index.get("metadata", {})
    return {
        "total": len(entries),
        "recent_5yr": sum(1 for e in entries if e.get("is_recent_5yr")),
        "cn_journal": sum(1 for e in entries if e.get("is_cn_journal")),
        "verified": sum(1 for e in entries if e.get("verified")),
        "unverified": sum(1 for e in entries if not e.get("verified")),
        "manual_review": sum(1 for e in entries if e.get("needs_manual_review")),
        "avg_confidence": round(
            (sum(int((e.get("verification_details") or {}).get("confidence_score", 0)) for e in entries) / len(entries)), 2
        )
        if entries
        else 0,
        "last_run_stats": meta.get("verification_stats", {}),
    }


def _save_manual_review_queue(path: Path, queue: list[dict[str, Any]]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(queue),
        "entries": queue,
    }
    save_json(path, payload)


def _append_verification_log(path: Path, record: dict[str, Any]) -> None:
    existing = load_json(path, {"runs": []})
    if not isinstance(existing, dict):
        existing = {"runs": []}
    runs = existing.get("runs")
    if not isinstance(runs, list):
        runs = []
    runs.append(record)
    existing["runs"] = runs[-200:]
    save_json(path, existing)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_verify_all = sub.add_parser("verify-all")
    p_verify_all.add_argument("--index", default="data/literature_index.json")
    p_verify_all.add_argument("--p1", default="sections/P1_立项依据.md")
    p_verify_all.add_argument("--offline", action="store_true")
    p_verify_all.add_argument("--mcp-cache", default="data/mcp_literature_cache.json")
    p_verify_all.add_argument("--mcp-ttl-days", type=int, default=30)
    p_verify_all.add_argument("--require-mcp", action="store_true")
    p_verify_all.add_argument("--manual-review", default="data/manual_review_queue.json")
    p_verify_all.add_argument("--log", default="data/verification_run_log.json")

    p_verify_entry = sub.add_parser("verify-entry")
    p_verify_entry.add_argument("--index", default="data/literature_index.json")
    p_verify_entry.add_argument("--p1", default="sections/P1_立项依据.md")
    p_verify_entry.add_argument("--ref-number", type=int, required=True)
    p_verify_entry.add_argument("--offline", action="store_true")
    p_verify_entry.add_argument("--mcp-cache", default="data/mcp_literature_cache.json")
    p_verify_entry.add_argument("--mcp-ttl-days", type=int, default=30)
    p_verify_entry.add_argument("--require-mcp", action="store_true")

    p_matrix = sub.add_parser("matrix-check")
    p_matrix.add_argument("--p1", default="sections/P1_立项依据.md")
    p_matrix.add_argument("--index", default="data/literature_index.json")
    p_matrix.add_argument("--ref", default="sections/REF_参考文献.md")

    p_orphans = sub.add_parser("find-orphans")
    p_orphans.add_argument("--p1", default="sections/P1_立项依据.md")
    p_orphans.add_argument("--index", default="data/literature_index.json")

    p_reorder = sub.add_parser("reorder")
    p_reorder.add_argument("--p1", default="sections/P1_立项依据.md")
    p_reorder.add_argument("--index", default="data/literature_index.json")

    p_stats = sub.add_parser("stats")
    p_stats.add_argument("--index", default="data/literature_index.json")

    p_gates = sub.add_parser("check-gates")
    p_gates.add_argument("--index", default="data/literature_index.json")
    p_gates.add_argument("--profile", default="proposal_profile.json",
                         help="proposal_profile.json holding applicant_authors (J5)")
    p_gates.add_argument("--current-year", type=int, default=None,
                         help="Current year for J7 recency (default: system clock)")

    args = parser.parse_args()

    mcp_index: dict[str, dict[str, Any]] = {}
    mcp_schema_version = CACHE_SCHEMA_VERSION
    if args.cmd in {"verify-all", "verify-entry"}:
        mcp_cache_path = Path(getattr(args, "mcp_cache", "data/mcp_literature_cache.json"))
        mcp_cache_raw = load_json(mcp_cache_path, {"metadata": {"schema_version": CACHE_SCHEMA_VERSION}, "entries": []})
        mcp_cache = _normalize_mcp_cache(mcp_cache_raw)
        save_json(mcp_cache_path, mcp_cache)
        mcp_index = _build_mcp_index(mcp_cache)
        mcp_schema_version = str((mcp_cache.get("metadata") or {}).get("schema_version") or CACHE_SCHEMA_VERSION)

    if args.cmd == "verify-all":
        index_path = Path(args.index)
        raw = load_json(index_path, {"metadata": {}, "entries": []})
        idx = _normalize_index(raw)
        p1_text = Path(args.p1).read_text(encoding="utf-8") if Path(args.p1).exists() else None

        idx, run_stats, queue = verify_all(
            idx,
            p1_text=p1_text,
            online_check=not args.offline,
            mcp_index=mcp_index,
            mcp_ttl_days=max(0, int(args.mcp_ttl_days)),
            require_mcp=bool(args.require_mcp),
            mcp_schema_version=mcp_schema_version,
        )
        save_json(index_path, idx)
        _save_manual_review_queue(Path(args.manual_review), queue)
        _append_verification_log(Path(args.log), {
            "index": str(index_path),
            "verification_status": idx.get("metadata", {}).get("verification_status"),
            **run_stats,
        })

        verification_status = idx["metadata"].get("verification_status")
        print(
            json.dumps(
                {
                    "ok": verification_status != "failed",
                    "verification_status": verification_status,
                    "manual_review_count": len(queue),
                    "avg_confidence": run_stats.get("avg_confidence"),
                    "duration_ms": run_stats.get("duration_ms"),
                },
                ensure_ascii=False,
            )
        )
        return 1 if verification_status == "failed" else 0

    if args.cmd == "verify-entry":
        index_path = Path(args.index)
        raw = load_json(index_path, {"metadata": {}, "entries": []})
        idx = _normalize_index(raw)
        p1_text = Path(args.p1).read_text(encoding="utf-8") if Path(args.p1).exists() else None
        updated = False
        for i, entry in enumerate(idx.get("entries", [])):
            if int(entry.get("ref_number", -1)) == args.ref_number:
                updated_entry = validate_entry(
                    dict(entry),
                    p1_text=p1_text,
                    online_check=not args.offline,
                    mcp_index=mcp_index,
                    mcp_ttl_days=max(0, int(args.mcp_ttl_days)),
                )
                if args.require_mcp:
                    details = updated_entry.get("verification_details") or {}
                    reasons = list(details.get("failure_reasons") or [])
                    if any(r in {"mcp_unresolved", "mcp_stale", "mcp_timestamp_missing"} for r in reasons):
                        updated_entry["verified"] = False
                idx["entries"][i] = updated_entry
                updated = True
                break
        if not updated:
            print(json.dumps({"ok": False, "error": "ref_number not found"}, ensure_ascii=False))
            return 2
        save_json(index_path, idx)
        print(json.dumps({"ok": True, "ref_number": args.ref_number}, ensure_ascii=False))
        return 0

    if args.cmd == "matrix-check":
        raw = load_json(Path(args.index), {"metadata": {}, "entries": []})
        idx = _normalize_index(raw)
        p1_text = Path(args.p1).read_text(encoding="utf-8") if Path(args.p1).exists() else ""
        ref_text = Path(args.ref).read_text(encoding="utf-8") if Path(args.ref).exists() else ""
        print(json.dumps(matrix_check(p1_text, idx, ref_text), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "find-orphans":
        raw = load_json(Path(args.index), {"metadata": {}, "entries": []})
        idx = _normalize_index(raw)
        p1_text = Path(args.p1).read_text(encoding="utf-8") if Path(args.p1).exists() else ""
        print(json.dumps(find_orphans(p1_text, idx), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "reorder":
        index_path = Path(args.index)
        raw = load_json(index_path, {"metadata": {}, "entries": []})
        idx = _normalize_index(raw)
        p1_text = Path(args.p1).read_text(encoding="utf-8") if Path(args.p1).exists() else ""
        idx = reorder_entries_by_p1(idx, p1_text)
        save_json(index_path, idx)
        print(json.dumps({"ok": True, "count": len(idx.get("entries", []))}, ensure_ascii=False))
        return 0

    if args.cmd == "stats":
        raw = load_json(Path(args.index), {"metadata": {}, "entries": []})
        idx = _normalize_index(raw)
        print(json.dumps(stats(idx), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "check-gates":
        raw = load_json(Path(args.index), {"metadata": {}, "entries": []})
        idx = _normalize_index(raw)
        profile = load_json(Path(args.profile), {})
        raw_authors = profile.get("applicant_authors") if isinstance(profile, dict) else None
        applicant_authors = [str(a) for a in raw_authors] if isinstance(raw_authors, list) else []
        current_year = args.current_year or datetime.now(timezone.utc).year
        gates = run_integrity_gates(
            idx.get("entries", []),
            applicant_authors=applicant_authors,
            current_year=current_year,
        )
        print(json.dumps(gates, ensure_ascii=False, indent=2))
        return gates["exit_code"]

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
