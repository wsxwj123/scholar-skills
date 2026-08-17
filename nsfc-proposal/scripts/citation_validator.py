#!/usr/bin/env python3
"""Citation validation and matrix checks for nsfc-proposal.

Dual-track validation:
- Track A: MCP evidence cache (paper-search results)
- Track B: Official HTTP sources (PubMed/Crossref)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import sys as _sys

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in _sys.path:
    _sys.path.insert(0, _SCRIPTS_DIR)
import citation_guard_core as core

# round21 T2：used_in_sections 里「立项依据」这一节的取值统一成裸节标识 "P1"。
P1_SECTION = "P1"
# 2026-08-11 之前登记的旧值，只读兼容（检查链认两值；pack-write 切片链只认新值）。
# 🔴 退役条件（两条同时满足才删本常量与 _in_p1 的两值分支，缺一不删）：
# ① 用户名下所有在途 nsfc 项目跑过一次 normalize-sections（用户确认）；
# ② check-gates 的旧值 WARN 连续两轮验收为 0。
# 提前退役会让没迁移的账本静默丢统计。
P1_SECTION_LEGACY = "P1_立项依据"
P1_SECTION_KEYS = (P1_SECTION, P1_SECTION_LEGACY)


def _in_p1(entry: dict[str, Any]) -> bool:
    """条目是否分给 P1（检查链口径：新旧两值都算）。

    🔴 必须先验类型：字段写成数字时 `"P1" in 123` 抛 TypeError（实测）；写成
    字符串 "P1_立项依据" 时 `"P1" in ...` 会子串命中假阳。非 list 一律当「没有分配」。
    """
    secs = entry.get("used_in_sections")
    if not isinstance(secs, list):
        return False
    return any(k in secs for k in P1_SECTION_KEYS)


DOI_RE = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE)
PMID_RE = re.compile(r"^\d{4,10}$")
CIT_RE = re.compile(r"\[\d+(?:[-,，]\d+)*\]")

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


def _atomic_save_index(path: Path, data: dict[str, Any]) -> None:
    """原子写（同目录 tmp + fsync + os.replace）；任何失败都不留 .tmp、原文件一字节不动。"""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent) or ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except OSError:
            pass
        raise


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


def _is_mcp_fresh(record: dict[str, Any], ttl_days: int, now_utc: datetime) -> tuple[bool, str | None]:
    if ttl_days <= 0:
        return True, None
    # 时间戳解析用共享 core 的那一份（本地曾有逐字节相同的副本，已删，避免两处漂移）。
    # 注意：字段查找顺序仍是 nsfc 自己的（只认 verified_at/checked_at，不认 retrieved_at），
    # 与 core._is_mcp_fresh 有意不同，见 SKILL.md:357。
    checked_at = core._parse_dt(str(record.get("verified_at") or record.get("checked_at") or ""))
    if checked_at is None:
        return False, "mcp_timestamp_missing"
    if checked_at < now_utc - timedelta(days=ttl_days):
        return False, "mcp_stale"
    return True, None


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
    if not _in_p1(entry):
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

    # 🔴 离线绝不发"已核实"证书，口径与共享 core 一致（citation_guard_core.validate_core
    # 尾部同款判据 `verified = online and …`）。离线时 doi_valid/pmid_match 是"没查所以
    # 算它对"（http_ok 恒 True），core 又不往 failure_reasons 加码（那是冻结码表），
    # 只靠本地的 len(failure_reasons)==0 重算，一条纯编造文献只要 MCP 缓存里有同 DOI
    # 记录（缓存是本地 JSON）就能拿 verified + 96 分并写回索引——离线发证的产地。
    # 不发证的理由从 details.sources.online_check 读得出来，退出码语义不变。
    verified = online_check and len(failure_reasons) == 0

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


class IndexCorruptError(ValueError):
    """文献索引 entries 混入非对象元素（字符串/列表/None 等）。

    这是索引读入口唯一的 fail-closed 出口：调用方据此结构化拒绝，绝不让
    `e.get(...)` 在下游各消费点裸崩成 traceback。
    round21 起是三态家族的基类：本类=结构坏（corruption="entries"），
    IndexSyntaxError=语法坏（"syntax"），IndexUnreadableError=读不出（"unreadable"）。
    调用方一个 `except IndexCorruptError` 兜住三态。
    """

    corruption = "entries"
    _MAX_LISTED = 10  # 整份文件都是垃圾时别刷屏，只点名前 10 个

    def __init__(self, path: Any, bad_positions: list[int], bad_kinds: list[str]) -> None:
        self.path = str(path)
        self.bad_positions = bad_positions      # 0 基下标
        self.bad_kinds = bad_kinds              # 与 bad_positions 一一对应的类型名
        shown = [f"entries[{i}] 是 {k}" for i, k in
                 zip(bad_positions[: self._MAX_LISTED], bad_kinds[: self._MAX_LISTED])]
        more = "" if len(bad_positions) <= self._MAX_LISTED else f"（仅列前 {self._MAX_LISTED} 个）"
        super().__init__(
            f"文献索引损坏：{self.path} 的 entries 有 {len(bad_positions)} 个元素不是对象"
            f"（条目下标 0 基）：{'、'.join(shown)}{more}。"
            f"索引文件一字未动，请人工修好这些条目后重跑。"
        )


class IndexSyntaxError(IndexCorruptError):
    """索引文件本身不是合法 JSON（语法层，含 0 字节/纯空白）。round21 T5 新增。"""

    corruption = "syntax"

    def __init__(self, path: Any, exc: json.JSONDecodeError) -> None:
        self.path = str(path)
        self.lineno, self.colno, self.pos = exc.lineno, exc.colno, exc.pos
        self.bad_positions: list[int] = []
        self.bad_kinds: list[str] = []
        ValueError.__init__(
            self,
            f"文献索引损坏：{self.path} 不是合法 JSON —— "
            f"第 {exc.lineno} 行第 {exc.colno} 列：{exc.msg}。"
            f"索引文件一字未动，请人工修好后重跑。")


class IndexUnreadableError(IndexCorruptError):
    """索引文件读不出来：路径是目录、读权限不足、字节编码非法等。round21 T5 新增，
    round22 T5 起非法 UTF-8 也收敛到本态。

    文案里刻意不写 Python 异常类名（IsADirectoryError / UnicodeDecodeError 等
    不许甩给用户）。
    """

    corruption = "unreadable"

    def __init__(self, path: Any, exc: Exception) -> None:
        self.path = str(path)
        self.bad_positions: list[int] = []
        self.bad_kinds: list[str] = []
        ValueError.__init__(
            self,
            f"文献索引损坏：{self.path} 读不出来（路径是目录、没有读权限或字节编码非法）。"
            f"索引文件一字未动，请修好路径/权限/编码后重跑。")


def _index_reject_report(exc: IndexCorruptError) -> dict[str, Any]:
    """三态统一的结构化拒绝报告（四个子命令逐字一致，键集合固定）。"""
    return {
        "ok": False,
        "failed_at": "literature_index",
        "literature_index": {
            "ok": False,
            "path": exc.path,
            "error": str(exc),
            "corruption": exc.corruption,
            # 与 error 文案同口径：只点名前 10 个（_MAX_LISTED），整份垃圾文件不刷屏
            "bad_entry_indexes": list(exc.bad_positions)[:IndexCorruptError._MAX_LISTED],
            "line": getattr(exc, "lineno", None),
            "column": getattr(exc, "colno", None),
            "position": getattr(exc, "pos", None),
        },
    }


def load_index(path: Path, default: Any = None) -> dict[str, Any]:
    """读文献索引的唯一入口。内部顺序写死四步（round21 T5，一步不许调换/省略）：
    ① 读盘 load_json（文件不存在 → default，宽松语义保留）
    ② 语法层：JSONDecodeError → IndexSyntaxError；OSError → IndexUnreadableError
    ③ 宽松归一 _normalize_index（顶层数组/字符串、entries 缺失/非数组 → 不拒，行为不变）
    ④ entries 结构层：非 dict 元素 → IndexCorruptError（第十八轮既有）

    与 `_normalize_index`（宽松归一，容忍任何元素）的分工：凡是要拿 entries 里的
    元素当对象用的调用方（gate-check 链上的每一处），都必须走本函数，元素不是
    对象就抛 `IndexCorruptError`——绝不静默丢弃坏条目（丢了等于替用户删文献），
    也绝不放它进下游让 `.get()` 裸崩。
    """
    try:
        raw = load_json(path, default if default is not None else {"metadata": {}, "entries": []})
    except json.JSONDecodeError as exc:
        raise IndexSyntaxError(path, exc) from None
    except (OSError, UnicodeDecodeError) as exc:
        # round22 T5：非法 UTF-8 与目录/权限同归 unreadable，不新增第四错误态
        raise IndexUnreadableError(path, exc) from None
    idx = _normalize_index(raw)
    bad_positions = [i for i, e in enumerate(idx["entries"]) if not isinstance(e, dict)]
    if bad_positions:
        raise IndexCorruptError(path, bad_positions,
                                [type(idx["entries"][i]).__name__ for i in bad_positions])
    return idx


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
    # below. require_mcp/require_online are handed down so a cache produced by a
    # LOOSER run (offline / no MCP evidence) cannot short-circuit a stricter one —
    # otherwise the require_mcp downgrade further down never gets a chance to fire.
    out: list[dict[str, Any]] = []
    for e in entries:
        if core.entry_is_fresh_verified(e, mcp_ttl_days, now_utc,
                                        require_mcp=require_mcp,
                                        require_online=bool(online_check)):
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
    if not out:
        status = "failed"          # 空索引：维持原语义（没有可采信的东西）
    elif online_check:
        status = "verified" if all_ok else ("partial" if any_ok else "failed")
    else:
        # 离线这一轮一次联网核验都没做 → 状态只能是 unverified，绝不许出现
        # verified/partial 字样（口径同 gsw citation_guard.py 的 offline 分支）。
        # 但"没验"不等于"失败"：条目自己带失败原因才算 failed，退出码语义因此不变。
        blocked = any((e.get("verification_details") or {}).get("failure_reasons") for e in out)
        status = "failed" if blocked else "unverified"

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

    # round21 T2 存量提示：含旧值且不含新值的条目，切片链派不进 P1 —— 点条数、给归一命令。
    # 只 WARN 不改退出码；已同时含新值的条目切片能命中，不催归一。
    legacy_p1_count = sum(
        1 for e in entries
        if isinstance(e.get("used_in_sections"), list)
        and P1_SECTION_LEGACY in e["used_in_sections"]
        and P1_SECTION not in e["used_in_sections"])

    exit_code = 2 if incomplete else 0

    registry: dict[str, Any] = {
        "unassigned": unassigned,
        "unassigned_count": len(unassigned),
        "note": "used_in_sections 为检索登记必填；缺者归未分配、须回填，切片不含它们",
        "strength": "warn",
    }
    if legacy_p1_count:
        registry["legacy_p1_count"] = legacy_p1_count
        registry["legacy_p1_warn"] = (
            'WARN: %d 条文献仍用旧节标识 "P1_立项依据" 登记（新值 "P1"，切片链只认新值、'
            "这些条目不会被派进 P1 撰写）。跑 "
            "python3 scripts/citation_validator.py normalize-sections "
            "--index data/literature_index.json 一次性归一（可先加 --dry-run 预览）"
            % legacy_p1_count)

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
        "used_in_sections_registry": registry,
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
        if e.get("ref_number") is not None and _in_p1(e)
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
        if e.get("ref_number") is not None and _in_p1(e)
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
        # round21 T2：分给 P1 的条目数（检查链口径：新值 "P1" + 旧值只读兼容）
        "P1_entries": sum(1 for e in entries if _in_p1(e)),
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


_OFFLINE_HELP = (
    "跳过联网核验，本轮不发证：本轮实际核验的条目一律 verified=false、"
    "verification_status=unverified、ok=false（无硬失败时退出码仍为 0）；"
    "TTL 内已有可信核验记录的条目短路保持原状、不被刷掉。"
    "只用于测试或网络故障应急，不是交付口径，销账前必须不带它重跑。"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_verify_all = sub.add_parser("verify-all")
    p_verify_all.add_argument("--index", default="data/literature_index.json")
    p_verify_all.add_argument("--p1", default="sections/P1_立项依据.md")
    p_verify_all.add_argument("--offline", action="store_true", help=_OFFLINE_HELP)
    p_verify_all.add_argument("--mcp-cache", default="data/mcp_literature_cache.json")
    p_verify_all.add_argument("--mcp-ttl-days", type=int, default=30)
    p_verify_all.add_argument("--require-mcp", action="store_true")
    p_verify_all.add_argument("--manual-review", default="data/manual_review_queue.json")
    p_verify_all.add_argument("--log", default="data/verification_run_log.json")

    p_verify_entry = sub.add_parser("verify-entry")
    p_verify_entry.add_argument("--index", default="data/literature_index.json")
    p_verify_entry.add_argument("--p1", default="sections/P1_立项依据.md")
    p_verify_entry.add_argument("--ref-number", type=int, required=True)
    p_verify_entry.add_argument("--offline", action="store_true", help=_OFFLINE_HELP)
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

    p_norm = sub.add_parser(
        "normalize-sections",
        help='把账本 used_in_sections 里的旧值 "P1_立项依据" 归一成 "P1"（存量项目迁移，幂等）')
    p_norm.add_argument("--index", required=True, help="literature_index.json 路径")
    p_norm.add_argument("--dry-run", action="store_true", help="只报会改几条，一字节不写盘")

    p_gates = sub.add_parser("check-gates")
    p_gates.add_argument("--index", default="data/literature_index.json")
    p_gates.add_argument("--profile", default="proposal_profile.json",
                         help="proposal_profile.json holding applicant_authors (J5)")
    p_gates.add_argument("--current-year", type=int, default=None,
                         help="Current year for J7 recency (default: system clock)")

    args = parser.parse_args()

    # round21 T5：唯一的顶层捕获——三态索引损坏在一个地方接，四个子命令自动一致。
    try:
        return _dispatch(args)
    except IndexCorruptError as exc:
        print(json.dumps(_index_reject_report(exc), ensure_ascii=False))
        _sys.stderr.write("CITATION_VALIDATOR: FAIL literature_index\n")
        return 2


def _dispatch(args) -> int:
    mcp_index: dict[str, dict[str, Any]] = {}
    mcp_schema_version = CACHE_SCHEMA_VERSION
    if args.cmd in {"verify-all", "verify-entry"}:
        mcp_cache_path = Path(getattr(args, "mcp_cache", "data/mcp_literature_cache.json"))
        try:
            mcp_cache_raw = load_json(mcp_cache_path, {"metadata": {"schema_version": CACHE_SCHEMA_VERSION}, "entries": []})
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            # 缓存文件坏了/读不出来 ≠ 索引坏了：既定语义（SKILL.md:226）是当空处理、
            # 回落全量核验，不硬拦；也绝不 save_json 回写——那会把用户的坏缓存覆盖成
            # 空缓存（= 替用户删数据）。只在 stderr 留一行 WARN（不是 FAIL）。
            _sys.stderr.write(
                "CITATION_VALIDATOR: WARN mcp_cache 损坏或读不出来，按空缓存处理、"
                "回落全量核验（缓存文件一字未动）: %s\n" % mcp_cache_path)
            mcp_cache_raw = None
        if mcp_cache_raw is not None:
            mcp_cache = _normalize_mcp_cache(mcp_cache_raw)
            save_json(mcp_cache_path, mcp_cache)
            mcp_index = _build_mcp_index(mcp_cache)
            mcp_schema_version = str((mcp_cache.get("metadata") or {}).get("schema_version") or CACHE_SCHEMA_VERSION)

    if args.cmd == "verify-all":
        index_path = Path(args.index)
        idx = load_index(index_path)
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
                    # 离线 ok 恒 false：ok = 整体可采信，这一轮没做联网核验就不算采信
                    # （全仓口径，四家适配器同款）。退出码与 ok 解耦：unverified 不阻断。
                    "ok": verification_status != "failed" and not args.offline,
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
        idx = load_index(Path(args.index))
        p1_text = Path(args.p1).read_text(encoding="utf-8") if Path(args.p1).exists() else ""
        ref_text = Path(args.ref).read_text(encoding="utf-8") if Path(args.ref).exists() else ""
        print(json.dumps(matrix_check(p1_text, idx, ref_text), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "find-orphans":
        idx = load_index(Path(args.index))
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
        idx = load_index(Path(args.index))
        print(json.dumps(stats(idx), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "normalize-sections":
        index_path = Path(args.index)
        if not index_path.exists():
            _sys.stderr.write("CITATION_VALIDATOR: index not found: %s\n" % index_path)
            return 2                     # 不存在不迁移、更不许顺手建文件
        idx = load_index(index_path)     # 三态损坏 → 顶层捕获，rc=2 结构化拒绝
        converted = already_new = unchanged = 0
        for e in idx["entries"]:
            secs = e.get("used_in_sections")
            if not isinstance(secs, list):
                # 坏类型（数字/字符串/对象/null）与缺字段同款：一字不动、计入 unchanged。
                # 绝不自作主张改成数组——那是替用户改数据。
                unchanged += 1
                continue
            if P1_SECTION_LEGACY in secs:
                has_new = P1_SECTION in secs
                merged: list[Any] = []
                for s in secs:
                    if s == P1_SECTION_LEGACY:
                        if not has_new and P1_SECTION not in merged:
                            merged.append(P1_SECTION)   # 原位替换，顺序保持
                        continue                        # 已有新值 → 删旧值不追加
                    merged.append(s)                    # 其余取值（含非字符串）原样保留
                e["used_in_sections"] = merged
                converted += 1
            elif P1_SECTION in secs:
                already_new += 1
            else:
                unchanged += 1
        if converted and not args.dry_run:
            try:
                _atomic_save_index(index_path, idx)
            except OSError:
                _sys.stderr.write(
                    "CITATION_VALIDATOR: 写入失败（原文件未被改动、无 .tmp 残留）: %s\n"
                    % index_path)
                return 2
        print(json.dumps({"ok": True, "index": str(index_path),
                          "converted": converted, "already_new": already_new,
                          "unchanged": unchanged, "dry_run": bool(args.dry_run)},
                         ensure_ascii=False))
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
