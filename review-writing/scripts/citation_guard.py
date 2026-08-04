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
import os
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
    backfill_article_types,
    entry_is_fresh_verified,
    fetch_pubmed_records,
    validate_core,
)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: serialize to a sibling .tmp first, then os.replace() onto the
    # target so an interrupted/failed run cannot truncate an existing report.
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)



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
    pubmed_record: dict[str, Any] | None = None,
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
        # 批量 esummary 已取到本条 → 直接复用，省掉逐条请求；没取到就不传，
        # 核心自行逐条抓取（行为与批量上线前完全一致）。
        prefetched={"pubmed": pubmed_record} if pubmed_record else None,
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
    p.add_argument(
        "--backfill-article-type",
        action="store_true",
        help="只回填 article_type（批量取 PubMed pubtype），不做核验、不动任何其它字段",
    )
    args = p.parse_args()

    index_path = Path(args.index)
    raw = load_json(index_path, {})
    entries, shape = _normalize_index(raw)

    if args.backfill_article_type:
        # 存量项目补类型的那"一条命令"。就地改 entries（与 raw 是同一批 dict 对象），
        # 回写 raw 本身 → 除 article_type 外逐字段原样，连未识别的条目都不丢。
        stats = backfill_article_types(entries, online=not args.offline)
        if entries:
            save_json(index_path, raw)
        print(json.dumps({"backfill_article_type": stats}, ensure_ascii=False))
        if stats["unresolved"]:
            sys.stderr.write(
                f"ARTICLE_TYPE: 本次有 {stats['unresolved']}/{stats['targets']} 条没填上"
                f"（其中 {stats['no_pmid']} 条无 PMID），已按 unknown 落库——"
                "这些文献的「机制/疗效结论不得只挂综述」纪律仍然不会执行。\n")
        return 0

    mcp_cache = load_json(Path(args.mcp_cache), {}) if args.mcp_cache else {}
    mcp_index = _build_mcp_index(mcp_cache)

    t0 = time.perf_counter()
    now_utc = datetime.now(timezone.utc)
    mcp_ttl_days = max(0, int(args.mcp_ttl_days))
    # 本轮的核验强度：缓存只有在"当初至少这么严"时才准短路（否则一条 --offline
    # 验过的编造文献能一路顶掉 --require-mcp / 联网核验，硬门禁形同虚设）。
    strictness = {"require_mcp": bool(args.require_mcp), "require_online": not args.offline}
    # 批量取 PubMed 记录（100 条/请求）：核验用 + article_type 用共一份，避免 N 条发 N 次。
    # 需要取的两类：① 本轮要真核验的；② 短路复用但 article_type 还空着的。
    need_pmids = [
        e.get("pmid")
        for e in entries
        if not entry_is_fresh_verified(e, mcp_ttl_days, now_utc, **strictness)
        or str(e.get("article_type") or "unknown").strip().lower() in ("", "unknown")
    ]
    pubmed_batch = {} if args.offline else fetch_pubmed_records(need_pmids)
    checked = []
    for e in entries:
        # L1 短路：本条已在 TTL 内被脚本核验过（verified:true + 新鲜 checked_at）→
        # 复用已存 verified/verification_details，跳过在线 DOI/PMID 核验，避免重复联网。
        # entry_is_fresh_verified 是 fail-safe：未验/过期/无时间戳/当初比本轮松，一律回落全量核验。
        if entry_is_fresh_verified(e, mcp_ttl_days, now_utc, **strictness):
            checked.append(dict(e))
            continue
        res = validate_entry(
            dict(e),
            online_check=not args.offline,
            mcp_index=mcp_index,
            require_mcp=args.require_mcp,
            mcp_ttl_days=mcp_ttl_days,
            now_utc=now_utc,
            pubmed_record=pubmed_batch.get(str(e.get("pmid") or "").strip()),
        )
        # 给本次真正核验过的条目盖 per-entry 时间戳（写进 verification_details.checked_at），
        # --write-back 时落盘，下次可命中短路；短路复用的条目保留其原 checked_at，
        # TTL 到期仍会重新核验，撤稿/时效安全不被削弱。
        vd = res.get("verification_details")
        if isinstance(vd, dict):
            res["verification_details"] = {**vd, "checked_at": now_utc.isoformat()}
        checked.append(res)

    # 短路复用的条目不过 validate_core，类型靠这一步补齐（已有真值不覆盖）。
    # 取不到就留 unknown 并明说，绝不编一个类型——unknown 会让下游纪律跳过，
    # 这时候骗人比不填更糟。
    atype_stats = backfill_article_types(checked, records=pubmed_batch, online=False)
    if atype_stats["unresolved"]:
        sys.stderr.write(
            f"ARTICLE_TYPE: {atype_stats['unresolved']}/{atype_stats['targets']} 条没取到文献类型"
            f"（其中 {atype_stats['no_pmid']} 条无 PMID），按 unknown 落库；"
            "这些引用不会走「机制/疗效结论不得只挂综述」检查。\n")

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
        # ok 是"本次没查出问题"（=退出码 0），不是"文献已核实"；后者只看 status。
        "ok": status in ("verified", "unverified"),
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
        "mcp_ttl_days": max(0, int(args.mcp_ttl_days)),
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
            elif shape == "dict_values":
                # 按原键写回原位。绝不另起一份 out["entries"]：那会让同一批文献
                # 在同一个文件里存两份，而所有读取侧（本脚本 _normalize_index、
                # citation_claim_check._load_ledger）都优先读 entries ——
                # 用户之后手工改原键的内容将永远不被任何检查看见。
                for k, e in zip(_dict_entry_keys(raw), checked):
                    out[k] = e
            else:
                out["entries"] = checked
            md = out.get("metadata") if isinstance(out.get("metadata"), dict) else {}
            md.update({"verification_status": status, "last_updated": now_utc.isoformat(), "verification_stats": report})
            out["metadata"] = md
            save_json(index_path, out)

    print(json.dumps(report, ensure_ascii=False))
    # 诚实化：PASS 只代表引文来源合规层过关，不代表论点被文献支持（stderr，不污染 stdout JSON）。
    if report["ok"]:
        sys.stderr.write(
            "CITATION_GUARD: PASS — 仅核验引文来源合规层（标识符/provider 白名单/标题比对）；"
            "论点是否被所引文献支持、结论科学价值未核验。\n")
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
