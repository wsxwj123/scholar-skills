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
    _dict_entry_keys,
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
    for k in ("citation_number", "ref_number", "global_id", "id", "index", "number"):
        v = entry.get(k)
        if v is None:
            continue
        try:
            return int(str(v).strip())
        except (ValueError, TypeError):
            continue
    return None


def _reference_index_signal(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    """A4 reverse-lookup straight off a reference_index that already carries the
    pairing verdict (cited_by / orphan_type), e.g. 肠骨轴 reference_index.json.

    Preferred over a drafts re-scan because the index author already resolved
    which [n] map to which entry. Returns None when no entry carries either
    signal (so the caller falls back to a drafts scan or skips).

    zombie = listed but never cited (cited_by empty OR orphan_type=="entry_not_cited").
    orphan = cited with no list entry (orphan_type=="cited_no_entry").
    """
    has_signal = any(
        ("cited_by" in e) or ("orphan_type" in e)
        for e in entries if isinstance(e, dict)
    )
    if not has_signal:
        return None

    zombies: set[int] = set()
    orphans: set[int] = set()
    for e in entries:
        if not isinstance(e, dict):
            continue
        num = _entry_citation_number(e)
        if num is None:
            continue
        otype = str(e.get("orphan_type") or "").strip()
        cited_by = e.get("cited_by")
        if otype == "cited_no_entry":
            orphans.add(num)
            continue
        if otype == "entry_not_cited":
            zombies.add(num)
            continue
        # No explicit orphan_type verdict: fall back to cited_by emptiness.
        if isinstance(cited_by, (list, tuple, set)) and len(cited_by) == 0:
            zombies.add(num)
    status = "fail" if (orphans or zombies) else "ok"
    return {
        "status": status,
        "orphans": sorted(orphans),
        "zombies": sorted(zombies),
        "source": "reference_index",
    }


def run_review_gates(
    entries: list[dict[str, Any]],
    *,
    drafts_dir: Path | None,
    manuscript_authors: list[str],
    current_year: int,
    self_cite_threshold: float = 0.4,
    recency_window: int = 5,
    recency_min_ratio: float = 0.3,
) -> dict[str, Any]:
    """Review-side J4/J5/J7/A4 reverse-lookup. ALL report-only (never blocks).

    This is the審稿端 counterpart of general-sci-writing's run_integrity_gates:
    same core functions, but the verdict is advisory — every section is tagged
    strength="report", mode is "review_report", and exit_code is pinned to 0 so
    the reviewer simulator can fold findings into its report without aborting.

    A4 source precedence: reference_index reverse-lookup (cited_by/orphan_type) >
    drafts [n] scan > skipped.
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

    # A4 — reference_index signal first, then drafts scan, then skip.
    a4 = _reference_index_signal(entries)
    if a4 is None and drafts_dir is not None:
        cited = _scan_cited_numbers(drafts_dir)
        listed = {n for n in (_entry_citation_number(e) for e in entries) if n is not None}
        a4 = {**check_bidirectional(cited, listed), "source": "drafts_scan"}
    if a4 is None:
        a4 = {"status": "skipped", "reason": "no_signal_no_drafts", "source": "none"}

    return {
        "ok": True,
        "mode": "review_report",
        "exit_code": 0,
        "j4_completeness": {
            "incomplete": incomplete,
            "raw_only_count": len(raw_only),
            "partial": partial,
            "strength": "report",
        },
        "j5_self_citation": {**self_cite, "strength": "report"},
        "j7_recency": {**recency, "strength": "report"},
        "a4_bidirectional": {**a4, "strength": "report"},
    }


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")



# dict_values 形状（{"1": {...}, "2": {...}}）里不算文献条目的保留键。
def _normalize_index(raw: Any) -> tuple[list[dict[str, Any]], str]:
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)], "list"
    if isinstance(raw, dict):
        for key in ("entries", "papers", "items", "references", "data"):
            val = raw.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)], key
        keys = _dict_entry_keys(raw)
        if keys:
            return [raw[k] for k in keys], "dict_values"
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
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Unified anti-hallucination citation guard")
    p.add_argument("--index", required=True, help="Path to literature index JSON")
    p.add_argument("--mcp-cache", default="", help="Path to MCP cache JSON")
    p.add_argument("--offline", action="store_true",
                   help="跳过联网核验，本次结果一律记为未核验（条目 verified 恒 false、"
                        "报告 status=unverified）。只用于测试或网络故障应急，"
                        "不是交付口径，交付前必须不带它重跑")
    p.add_argument("--mcp-ttl-days", type=int, default=30)
    p.add_argument("--require-mcp", action="store_true", help="Require MCP evidence; unresolved/stale MCP is blocking")
    p.add_argument("--manual-review", default="data/manual_review_queue.json")
    p.add_argument("--log", default="data/verification_run_log.json")
    p.add_argument("--report", default="data/citation_guard_report.json")
    p.add_argument("--write-back", action="store_true", help="Write verification fields back to index")
    # Review-side reverse-lookup gates (J4/J5/J7/A4). All report-only (exit 0).
    p.add_argument("--gates", action="store_true",
                   help="Run review-side citation reverse-lookup checks (J4 completeness, "
                        "J5 self-citation, J7 recency, A4 bidirectional). Report-only.")
    p.add_argument("--drafts-dir", default="manuscripts",
                   help="Manuscript directory scanned for [n] citations (A4 fallback)")
    p.add_argument("--project-config", default="project_config.json",
                   help="Config holding manuscript authors (J5); from manuscript metadata under review")
    p.add_argument("--current-year", type=int, default=None,
                   help="Current year for J7 recency (default: system clock)")
    p.add_argument("--gates-report", default="data/citation_review_report.json")
    args = p.parse_args()

    index_path = Path(args.index)
    raw = load_json(index_path, {})
    entries, shape = _normalize_index(raw)

    if args.gates:
        cfg = load_json(Path(args.project_config), {})
        authors = cfg.get("authors") if isinstance(cfg, dict) else None
        manuscript_authors = [str(a) for a in authors] if isinstance(authors, list) else []
        drafts_dir = Path(args.drafts_dir)
        current_year = args.current_year or datetime.now(timezone.utc).year
        gates = run_review_gates(
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
    # 本轮的核验强度：缓存只有在"当初至少这么严"时才准短路（否则一条 --offline
    # 验过的记录能顶掉 --require-mcp / 联网核验，硬门禁形同虚设）。
    # 离线跑绝不短路：离线一轮一次联网都没做，不能拿旧记录冒充本次。
    strictness = {"require_mcp": bool(args.require_mcp), "require_online": not args.offline}
    # L1 per-entry short-circuit: TTL 内已在线核验的条目复用上次 --write-back 落盘的
    # 结果，不重新联网。entry_is_fresh_verified 是 fail-safe（缺/旧时间戳、
    # verified!=True、缓存强度弱于本轮一律返回 False → 全量重验），门禁绝不因此变松。
    checked = []
    for e in entries:
        e = dict(e)
        if not args.offline and entry_is_fresh_verified(e, ttl_days, now_utc, **strictness):
            checked.append(e)  # reuse cached verified result verbatim
        else:
            checked.append(
                validate_entry(
                    e,
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
    if args.offline:
        # 离线这一轮一次联网核验都没做 → 状态只能是 unverified，绝不许出现 verified 字样。
        # 但"没验"不等于"失败"：格式合规的条目照旧不阻断（退出码维持 0，命令做了它被
        # 要求做的事），是否阻断只看条目自己有没有真的硬失败。
        blocked = any((e.get("verification_details") or {}).get("failure_reasons") for e in checked)
        status = ("failed" if blocked else "unverified") if checked else "empty"
    else:
        status = "verified" if (checked and verified_count == len(checked)) else ("failed" if checked else "empty")

    report = {
        # ok 是"整体可采信"：本轮真做了联网核验且全部通过（status=verified）才为 true。
        # 离线轮一次联网核验都没做 → ok 恒 false（哪怕无硬失败、status=unverified）。
        # 但 ok 与退出码在此处解耦：无硬失败的离线跑仍 exit 0，是否阻断只看条目自己
        # 有没有真的硬失败（status=failed 才非 0）。
        "ok": status == "verified",
        "status": status,
        "shape": shape,
        "checked_entries": len(checked),
        "verified_count": verified_count,
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
        to_write = checked
        if args.offline:
            # E3a 数据安全：离线轮一次联网核验都没做，写回时绝不许把索引里此前在线
            # 验过的 verified:true 刷成 false。判据看原始条目的 verified 字段本身：
            # 是 True 就整条保留原值（连同它的时间戳与 sources 证据），其余条目照常
            # 写回本轮离线结果。fail-closed 方向：能证明是 TTL 内在线核验来源的静默
            # 保留；证明不了的（缺时间戳/来源字段）同样保留但留痕 stderr——
            # 宁可不刷也不误刷，绝不静默乱写。
            merged = []
            unproven = []
            for i, (orig, new) in enumerate(zip(entries, checked), 1):
                if orig.get("verified") is True:
                    merged.append(orig)
                    if not entry_is_fresh_verified(orig, ttl_days, now_utc,
                                                   require_online=True):
                        unproven.append(_entry_ref_id(orig, i))
                else:
                    merged.append(new)
            if unproven:
                sys.stderr.write(
                    "WRITE-BACK: %d 条 verified:true 记录缺新鲜时间戳/在线来源证明，"
                    "已按 fail-closed 保留原值（未写入本轮离线结果）：%s\n"
                    % (len(unproven), unproven))
            to_write = merged
        if isinstance(raw, list):
            save_json(index_path, to_write)
        elif isinstance(raw, dict):
            out = dict(raw)
            if shape in {"entries", "papers", "items", "references", "data"}:
                out[shape] = to_write
            elif shape == "dict_values":
                # 按原键写回原位。绝不另起一份 out["entries"]：那会让同一批文献
                # 在同一个文件里存两份，而所有读取侧（本脚本 _normalize_index、
                # citation_claim_check._load_ledger）都优先读 entries ——
                # 用户之后手工改原键的内容将永远不被任何检查看见。
                for k, e in zip(_dict_entry_keys(raw), to_write):
                    out[k] = e
            else:
                out["entries"] = to_write
            md = out.get("metadata") if isinstance(out.get("metadata"), dict) else {}
            md.update({"verification_status": status, "last_updated": now_utc.isoformat(), "verification_stats": report})
            out["metadata"] = md
            save_json(index_path, out)

    print(json.dumps(report, ensure_ascii=False))
    # 退出码与 ok 解耦（ok 离线恒 false 之后不能再用 ok 当退出码）：维持既有映射
    # 一字不变——verified/unverified → 0，failed/empty → 2。
    return 2 if status in ("failed", "empty") else 0


if __name__ == "__main__":
    raise SystemExit(main())
