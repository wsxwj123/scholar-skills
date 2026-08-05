#!/usr/bin/env python3
"""Shared citation-verification core (single source of truth).

Pure verification primitives only. No argparse, no file IO, no print. Skill
adapters (citation_guard.py) handle loading, MCP index building, CLI flags, and
report writing; they call validate_core for the actual checks.

Verification strength here is the baseline floor: provider allowlist, online
DOI/PMID resolution, by-title existence when no identifier, per-source title
cross-validation, retraction, year reasonableness, and bounded HTTP retry. To
change a threshold globally, edit this file once and re-mirror it.
"""

from __future__ import annotations

import http.client
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

DOI_RE = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE)
PMID_RE = re.compile(r"^\d{4,10}$")
TITLE_TOKEN_RE = re.compile(r"[a-z0-9\u4e00-\u9fff]+")
ALLOWED_PROVIDER_FAMILIES = {"pubmed-cli", "paper-search"}
FORBIDDEN_PROVIDER_FAMILIES = {"websearch", "openalex-cli", "tavily"}
TITLE_VERIFY_THRESHOLD = 0.8

# metadata 是 citation_guard --write-back 自己写的账本头；不排除的话，第一次写回
# 之后它会被当成一条文献参与核验（缺标题 → 必 fail），跑第二次就红。
_INDEX_RESERVED_KEYS = frozenset({"metadata"})


def _dict_entry_keys(raw: dict[str, Any]) -> list[str]:
    """dict_values 形状（{"1": {...}, "2": {...}}）下"哪些键是文献条目"的唯一判据。

    三个消费方共用这一份：citation_guard 的读取（_normalize_index）、它的 --write-back
    （按原键落回原位），以及 citation_claim_check 的账本装载。任何一方另写一份，
    挑出的条目就会按位错开 → 写回串行 / 纪律读空。
    """
    return [k for k, v in raw.items()
            if isinstance(v, dict) and k not in _INDEX_RESERVED_KEYS]


def _http_get_json(
    url: str, timeout_sec: float = 8.0, *, retries: int = 2, backoff_sec: float = 1.5
) -> dict[str, Any] | None:
    """GET JSON with bounded retry/backoff.

    Returns None on any failure (network, HTTP error, bad JSON). Callers MUST
    treat None as "not verified" and never as a pass (fail-closed).
    """
    req = urllib.request.Request(url, headers={"User-Agent": "citation-guard/1.0"})
    attempt = 0
    while True:
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            # Retry only on rate-limit / transient server errors.
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(backoff_sec * (2**attempt))
                attempt += 1
                continue
            return None
        except (urllib.error.URLError, TimeoutError, ConnectionError,
                http.client.IncompleteRead):
            # ConnectionError/IncompleteRead 在 read() 阶段抛出、不被 URLError 包住，
            # 同属瞬时网络故障：按同一 retry 语义处理，耗尽返回 None（fail-closed）。
            if attempt < retries:
                time.sleep(backoff_sec * (2**attempt))
                attempt += 1
                continue
            return None
        except json.JSONDecodeError:
            return None


def _normalize_title(title: str) -> str:
    t = title.lower().strip()
    t = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _title_tokens(title: str) -> set[str]:
    return set(TITLE_TOKEN_RE.findall(_normalize_title(title)))


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
    short = min(len(na), len(nb)) / max(len(na), len(nb))
    contain_bonus = 0.1 if (na in nb or nb in na) else 0.0
    return min(1.0, 0.75 * jacc + 0.25 * short + contain_bonus)


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
    checked_at = _parse_dt(str(record.get("verified_at") or record.get("checked_at") or record.get("retrieved_at") or ""))
    if checked_at is None:
        return False, "mcp_timestamp_missing"
    if checked_at < now_utc - timedelta(days=ttl_days):
        return False, "mcp_stale"
    return True, None


def entry_is_fresh_verified(
    raw_entry: dict[str, Any],
    ttl_days: int,
    now_utc: datetime | None = None,
    *,
    require_mcp: bool = False,
    require_online: bool = False,
) -> bool:
    """True when a RAW index entry is already verified within the freshness window.

    Adapters call this BEFORE re-running validate_core: a fresh-verified entry may
    reuse its persisted verification result instead of re-hitting Crossref/PubMed.
    The timestamp may live at the entry top level (``verified_at``/``checked_at``)
    or inside ``verification_details.checked_at`` (adapter-dependent).

    ``require_mcp`` / ``require_online`` say how strict THIS run is. A cached
    result may only be reused when the run that produced it was at least as
    strict, i.e. ``verification_details.sources.mcp`` / ``.online_check`` are
    True. Without this, one ``--offline`` verification (which happily marks a
    fabricated entry verified) short-circuits every ``--require-mcp`` run for the
    next TTL window — the MCP evidence gate becomes a no-op. Both default to
    False, so a plain run still reuses the cache and does NOT re-hit the network.

    Fail-safe by construction: verified is not True, ttl_days<=0, a
    missing/unparseable timestamp, or a details/sources block that is missing or
    not shaped as expected all return False, so the caller falls through to a
    full re-verification. A stale (out-of-TTL) entry also returns False and is
    re-verified — retraction/freshness safety is preserved.
    """
    if ttl_days <= 0:
        return False
    if raw_entry.get("verified") is not True:
        return False
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    details = raw_entry.get("verification_details")
    if require_mcp or require_online:
        sources = details.get("sources") if isinstance(details, dict) else None
        if not isinstance(sources, dict):
            return False
        # `is not True` (not falsiness): a stringy "true" / 1 is an unknown shape,
        # and an unknown shape must tighten, never pass.
        if require_mcp and sources.get("mcp") is not True:
            return False
        if require_online and sources.get("online_check") is not True:
            return False
    ts_raw = (
        raw_entry.get("verified_at")
        or raw_entry.get("checked_at")
        or (details.get("checked_at") if isinstance(details, dict) else None)
    )
    ts = _parse_dt(str(ts_raw or ""))
    if ts is None:
        return False
    return ts >= now_utc - timedelta(days=ttl_days)


def _fetch_crossref_by_doi(doi: str) -> dict[str, Any] | None:
    encoded = urllib.parse.quote(doi, safe="")
    payload = _http_get_json(f"https://api.crossref.org/works/{encoded}")
    if not payload or "message" not in payload:
        return None
    msg = payload["message"]
    title = (msg.get("title") or [""])[0] if isinstance(msg.get("title"), list) else ""
    relation = msg.get("relation") or {}
    is_retracted = isinstance(relation, dict) and any("retract" in str(k).lower() for k in relation.keys())
    return {"source": "crossref", "title": title or "", "doi": doi, "pmid": None, "retracted": is_retracted}


ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
# esummary id 走 GET，100 个 PMID ≈ 1KB query，远低于任何代理/网关的 URL 上限。
PUBMED_BATCH_SIZE = 100


def _parse_esummary_result(pmid: str, result: Any) -> dict[str, Any] | None:
    """esummary 单条 result → 统一记录。单取与批取共用，保证两条路语义逐字段一致。"""
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
    return {"source": "pubmed", "title": title, "doi": doi, "pmid": str(pmid),
            "retracted": is_retracted, "pubtype": [str(x) for x in pubtypes]}


def _fetch_pubmed_by_pmid(pmid: str) -> dict[str, Any] | None:
    payload = _http_get_json(f"{ESUMMARY_URL}?db=pubmed&id={pmid}&retmode=json")
    if not payload or "result" not in payload:
        return None
    return _parse_esummary_result(str(pmid), payload["result"].get(str(pmid)))


def fetch_pubmed_records(
    pmids, *, batch_size: int = PUBMED_BATCH_SIZE
) -> dict[str, dict[str, Any]]:
    """批量取 PubMed esummary：{pmid: 记录}，记录形状与 _fetch_pubmed_by_pmid 相同。

    N 条文献只发 ceil(N/batch_size) 次请求（此前是逐条 N 次）。取不到的 PMID
    **不进返回表**——调用方据此回落逐条抓取或写 unknown，绝不能把"没取到"当成
    "取到了空值"。无网/超时/坏 JSON → 返回 {}（fail-safe，不抛异常）。
    """
    seen: list[str] = []
    known: set[str] = set()
    for p in pmids or ():
        s = str(p or "").strip()
        if s and s not in known and PMID_RE.match(s):
            known.add(s)
            seen.append(s)
    out: dict[str, dict[str, Any]] = {}
    step = max(1, int(batch_size))
    for i in range(0, len(seen), step):
        chunk = seen[i:i + step]
        payload = _http_get_json(f"{ESUMMARY_URL}?db=pubmed&id={','.join(chunk)}&retmode=json")
        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            continue  # 本批取不到 → 这批 PMID 缺席，调用方回落
        for pmid in chunk:
            rec = _parse_esummary_result(pmid, result.get(pmid))
            if rec is not None:
                out[pmid] = rec
    return out


# ── PubMed pubtype list → single article_type enum (deterministic, G0c) ──────
# INTERFACE §2B R5-3: first matching rule wins. "Journal Article" is the generic
# fallback and must never outrank a more specific type (e.g. Review). Pure
# function (unit-testable); empty/unrecognized -> "unknown".
def classify_article_type(pubtypes, source: str = "") -> str:
    pts = [str(x).lower() for x in (pubtypes or [])]
    src = str(source or "").lower()

    def has(*needles: str) -> bool:
        return any(any(n in pt for n in needles) for pt in pts)

    if has("systematic review"):
        return "systematic_review"
    if has("meta-analysis", "meta analysis"):
        return "meta_analysis"
    if has("review"):
        return "review"
    if has("randomized controlled trial", "controlled clinical trial", "clinical trial"):
        return "clinical_trial"
    if has("practice guideline", "guideline"):
        return "guideline"
    if has("book"):  # "Book" / "Book Chapter"
        return "book_chapter"
    if "biorxiv" in src or "medrxiv" in src or has("preprint"):
        return "preprint"
    if has("journal article"):
        return "original_research"
    return "unknown"


def backfill_article_types(
    entries, *, online: bool = True, records: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    """就地补齐条目的 article_type，**只碰这一个字段**，其它字段原样不动。

    已有真值（非 unknown）不覆盖；缺字段/unknown 且有 PMID 的才去查。取不到一律
    落 "unknown" 并计入 unresolved——绝不为了好看编一个类型出来。

    ``records`` 传入已批取的 PubMed 记录可复用（免二次请求）；未传且 online 时
    自行批取；online=False（离线/无网）则不发任何请求，全部落 unknown。

    返回统计 {total, targets, filled, unresolved, no_pmid, pubmed_records, by_type}，
    调用方必须把 unresolved 显式打给用户看（"这次没填上几条"）。
    """
    rows = [e for e in (entries or ()) if isinstance(e, dict)]
    targets = [e for e in rows
               if str(e.get("article_type") or "unknown").strip().lower() in ("", "unknown")]
    no_pmid = [e for e in targets if not PMID_RE.match(str(e.get("pmid") or "").strip())]

    if records is None:
        records = fetch_pubmed_records(
            [e.get("pmid") for e in targets]) if online else {}

    filled = 0
    by_type: dict[str, int] = {}
    for e in targets:
        pmid = str(e.get("pmid") or "").strip()
        rec = records.get(pmid) if pmid else None
        atype = classify_article_type(
            (rec or {}).get("pubtype"), source=_provider_family(str(e.get("source_provider") or ""))
        )
        e["article_type"] = atype
        if atype != "unknown":
            filled += 1
            by_type[atype] = by_type.get(atype, 0) + 1
    return {
        "total": len(rows),
        "targets": len(targets),
        "filled": filled,
        "unresolved": len(targets) - filled,
        "no_pmid": len(no_pmid),
        "pubmed_records": len(records),
        "by_type": dict(sorted(by_type.items())),
    }


def _crossref_year(item: dict[str, Any]) -> int | None:
    """Crossref issued.date-parts[0][0] -> year int, or None when absent/odd."""
    parts = (item.get("issued") or {}).get("date-parts") if isinstance(item.get("issued"), dict) else None
    if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
        try:
            return int(parts[0][0])
        except (ValueError, TypeError):
            return None
    return None


def _lookup_by_title(title: str) -> tuple[dict[str, Any] | None, bool]:
    """By-title lookup returning (match, reachable).

    ``match`` is the best candidate clearing TITLE_VERIFY_THRESHOLD (record shape
    {source, matched_title, similarity, doi, pmid, journal, year}), else None.
    ``reachable`` is True iff at least one of the two providers returned a
    parseable payload; both None (network / rate-limit / HTTP error / bad JSON)
    -> False. Callers must not read "no match" as "title is fabricated" when
    reachable is False.

    Strategy unchanged: Crossref by-title first, Semantic Scholar as fallback.
    """
    if not title.strip():
        return None, False

    # candidate tuple = (title, doi, pmid, journal, year)
    def _best_match(
        candidates: list[tuple[str, str | None, str | None, str | None, int | None]],
        source: str,
    ) -> dict[str, Any] | None:
        best: dict[str, Any] | None = None
        for cand_title, cand_doi, cand_pmid, cand_journal, cand_year in candidates:
            if not cand_title:
                continue
            sim = _title_similarity(title, cand_title)
            if best is None or sim > best["similarity"]:
                best = {
                    "source": source,
                    "matched_title": cand_title,
                    "similarity": sim,
                    "doi": cand_doi,
                    "pmid": cand_pmid,
                    "journal": cand_journal,
                    "year": cand_year,
                }
        if best and best["similarity"] >= TITLE_VERIFY_THRESHOLD:
            return best
        return None

    # 1) Crossref by-title
    cr_url = (
        "https://api.crossref.org/works?"
        + urllib.parse.urlencode({"query.bibliographic": title, "rows": 5})
    )
    cr = _http_get_json(cr_url)
    if cr and isinstance(cr.get("message"), dict):
        items = cr["message"].get("items") or []
        cands: list[tuple[str, str | None, str | None, str | None, int | None]] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            t = (it.get("title") or [""])[0] if isinstance(it.get("title"), list) else ""
            ct = it.get("container-title")
            journal = str(ct[0]) if isinstance(ct, list) and ct else None
            cands.append((str(t or ""), str(it.get("DOI") or "") or None, None,
                          journal, _crossref_year(it)))
        match = _best_match(cands, "crossref-bytitle")
        if match:
            return match, True

    # 2) Semantic Scholar by-title (fallback; rate-limit prone)
    ss_url = (
        "https://api.semanticscholar.org/graph/v1/paper/search?"
        + urllib.parse.urlencode(
            {"query": title, "limit": 5, "fields": "title,externalIds,venue,year"}
        )
    )
    ss = _http_get_json(ss_url)
    if ss and isinstance(ss.get("data"), list):
        cands = []
        for it in ss["data"]:
            if not isinstance(it, dict):
                continue
            ext = it.get("externalIds") or {}
            doi = str(ext.get("DOI") or "") or None if isinstance(ext, dict) else None
            pmid = str(ext.get("PubMed") or "") or None if isinstance(ext, dict) else None
            year = it.get("year") if isinstance(it.get("year"), int) else None
            cands.append((str(it.get("title") or ""), doi, pmid,
                          str(it.get("venue") or "") or None, year))
        match = _best_match(cands, "semanticscholar-bytitle")
        if match:
            return match, True

    return None, (cr is not None or ss is not None)


def _verify_title_exists(title: str) -> dict[str, Any] | None:
    """Confirm an entry with no DOI/PMID corresponds to a real publication.

    Thin wrapper over _lookup_by_title: drops the reachability bit, so the gray
    zone (no match / unreachable / offline) stays FAIL exactly as before.
    """
    return _lookup_by_title(title)[0]


# ---------------------------------------------------------------------------
# advisories —— 不阻断的诊断通道
#
# 禁令（改这段代码前必读）：
#   advisories 是不阻断的诊断通道。把任何 advisory code 接进 failure_reasons、
#   verified、needs_manual_review 或退出码之前必须另立方案——它们是启发式，
#   假阳会让正确文献在 new_refs 自动丢弃路径上被静默丢掉。
#
# 两档就够（拦 / 不拦），不引入第三档：advisory 元素里不得出现 severity/level。
# ---------------------------------------------------------------------------

# ① 标题变体探测：三桶关键词，表序即优先级（首个命中的桶定 code）。
_VARIANT_BUCKETS: tuple[tuple[str, frozenset[str]], ...] = (
    ("retraction_notice_suspect",
     frozenset({"retraction", "retracted", "withdrawn", "withdrawal"})),
    ("erratum_notice_suspect",
     frozenset({"erratum", "errata", "corrigendum", "corrigenda", "correction",
                "corrected", "addendum", "comment", "reply", "editorial"})),
    ("series_variant_suspect",
     frozenset({"part", "parts", "i", "ii", "iii", "iv", "supplement",
                "supplementary"})),
)
# 已知限制：无标记词的语义差异（ovariectomized/aged、post-/premenopausal、加副标题）
# 落在带内但差集里没有可枚举的词，探测不到。宁漏勿误，不做模糊猜测。
_VARIANT_MIN_SIM = 0.72


def detect_title_variant(entry_title: str, other_title: str, source: str) -> dict[str, Any] | None:
    """① 撤稿/勘误/系列篇探测（纯函数：不联网、不读写文件、不看时钟）。

    只在"像但不完全一样"的带内工作：低于 0.72 的条目已被 title_mismatch 判失败
    （不重复报），归一化后完全相同的两个标题没有差异可报。
    差集里找不到标记词就返回 None。

    "无差异"必须用归一化标题相等判定，不能用 sim >= 1.0：_title_similarity 末尾
    有 min(1.0, ...) 钳位，"RETRACTED: <T>" / "Retraction: <T>" 这类单 token 前缀
    加在正常长度的标题上会算出 >1 被钳到恰好 1.0——而这正是 Hindawi/IEEE/Elsevier
    最常用的撤稿标题形式。真实语料实测：靠分数判定会漏掉 81 条撤稿里的 45 条。
    """
    if _normalize_title(entry_title) == _normalize_title(other_title):
        return None
    sim = _title_similarity(entry_title, other_title)
    if sim < _VARIANT_MIN_SIM:
        return None
    diff = _title_tokens(entry_title) ^ _title_tokens(other_title)
    for code, keywords in _VARIANT_BUCKETS:
        hits = diff & keywords
        if code == "series_variant_suspect":
            hits = hits | {t for t in diff if t.isdigit()}
        if hits:
            tokens = sorted(hits)
            return {
                "code": code,
                "detail": "标题与来源记录高度相似，差异词含 %s，可能引的不是同一篇；对照标题：%s"
                          % ("/".join(tokens), other_title),
                "matched_title": other_title,
                "similarity": round(sim, 4),
                "source": source,
                "diff_tokens": tokens,
            }
    return None


# ② 标识符回查诊断
#
# 只有"发起了查询但没查成"才报 unavailable。离线态不报：--offline 下它会挂在每条
# 失败条目上，是零信息量常量（report 的 online_check: false 已经说明了一切），只会
# 淹没同批次里真正有价值的撤稿探测提醒——后者离线照常工作。
def _identifier_unavailable() -> dict[str, Any]:
    return {
        "code": "identifier_lookup_unavailable",
        "detail": "标题回查未取到可解析响应（网络/限流/服务异常），本次无法判断标识符是否正确",
        "reason": "network",
    }


def classify_identifier_suggestion(
    entry_doi: str,
    entry_pmid: str,
    match: dict[str, Any] | None,
    reachable: bool,
) -> dict[str, Any] | None:
    """② 标识符回查五态（纯函数：不联网、不读写文件、不看时钟）。

    优先级：不可达 > 无命中 > 有命中后的同类型比对。不可达排第一，是为了不把
    限流/网络故障退化成"你的标题可能是编的"。

    同类型是硬前提：Crossref 分支的 pmid 恒为 None，若不看类型，PMID-only 的条目
    会全部掉进 identifier_differs，被告知"你打错了，正确的是（空）"。线上没有与
    条目同类型的标识符时一律落 identifier_type_mismatch，只列参考值、不给建议。
    """
    if not reachable:
        return _identifier_unavailable()
    if match is None:
        return {
            "code": "identifier_not_found",
            "detail": "按标题回查未找到相似度达标的线上记录，无法给出标识符建议",
        }

    e_doi = str(entry_doi or "").strip()
    e_pmid = str(entry_pmid or "").strip()
    m_doi = str(match.get("doi") or "").strip()
    m_pmid = str(match.get("pmid") or "").strip()
    sim = match.get("similarity")
    common = {
        "matched_title": match.get("matched_title") or match.get("title"),
        "similarity": round(sim, 4) if isinstance(sim, (int, float)) else None,
        "source": match.get("source"),
    }
    extra = {"journal": match.get("journal"), "year": match.get("year")}

    # DOI 优先：两侧都带 DOI 时由 DOI 定论；条目没有 DOI 时才轮到 PMID。
    if e_doi and m_doi:
        if e_doi.lower() == m_doi.lower():
            return {"code": "identifier_confirmed",
                    "detail": "按标题回查命中的线上记录，其 DOI 与条目所填一致", **common}
        return {"code": "identifier_differs",
                "detail": "同名线上记录的 DOI 为 %s，与条目所填不同，请人工确认是哪一条"
                          "（仅建议，脚本不会改写标识符）" % m_doi,
                "suggested_doi": m_doi, **common, **extra}
    if e_pmid and m_pmid:
        if e_pmid == m_pmid:
            return {"code": "identifier_confirmed",
                    "detail": "按标题回查命中的线上记录，其 PMID 与条目所填一致", **common}
        return {"code": "identifier_differs",
                "detail": "同名线上记录的 PMID 为 %s，与条目所填不同，请人工确认是哪一条"
                          "（仅建议，脚本不会改写标识符）" % m_pmid,
                "suggested_pmid": m_pmid, **common, **extra}
    return {
        "code": "identifier_type_mismatch",
        "detail": "按标题回查命中了线上记录，但该记录不带与条目同类型的标识符，"
                  "无从比对；下列线上标识符仅供人工参考，不构成"
                  "\"条目填错了\"的判断",
        **common,
        "match_doi": m_doi or None,
        "match_pmid": m_pmid or None,
    }


# ---------------------------------------------------------------------------
# Citation-integrity gates (J4 completeness / J5 self-citation / J7 recency).
# Pure functions, no IO. Added independently of validate_core; its signature and
# return contract are untouched. Adapters (citation_guard.py) wire these to CLI.
# ---------------------------------------------------------------------------

# Fields a complete journal-article entry is *expected* to carry. The hard floor
# (whose absence makes an entry truly unusable) is much smaller — see below.
ARTICLE_EXPECTED_FIELDS = ("authors", "title", "journal", "year", "volume", "pages")
# Raw-citation fallback fields: when structured fields are missing but one of
# these holds the full Vancouver/text citation, rendering falls back to it, so
# the entry is "raw_only", not "incomplete".
RAW_CITATION_FIELDS = ("raw_vancouver", "raw_entry", "raw")


def _entry_has_author(entry: dict[str, Any]) -> bool:
    a = entry.get("authors")
    if isinstance(a, list):
        return any(str(x).strip() for x in a)
    if isinstance(a, str) and a.strip():
        return True
    return bool(str(entry.get("author") or "").strip())


def _has_raw_citation(entry: dict[str, Any]) -> bool:
    return any(str(entry.get(k) or "").strip() for k in RAW_CITATION_FIELDS)


def check_completeness(entry: dict[str, Any]) -> dict[str, Any]:
    """J4 — bibliographic completeness for one entry.

    Hard floor (status="incomplete", caller fails closed):
      - title missing, OR
      - no usable handle at all: no DOI AND no PMID AND no raw citation string.
    An entry with a DOI/PMID or a raw Vancouver string can always be rendered
    and re-fetched, so it never hard-fails on missing sub-fields alone.

    raw_only (status="raw_only"): structured fields (authors/journal/...) are
    absent but a raw citation string is present — rendering falls back to it.
    Not an error; reported so callers can surface it without blocking.

    complete / partial (status="ok"): structured fields present; any expected
    article fields still missing are listed in ``missing_fields`` as advisory
    (never blocking on their own).

    Returns: {status, missing_fields[], has_identifier, raw_only}.
    """
    title = str(entry.get("title") or "").strip()
    doi = str(entry.get("doi") or "").strip()
    pmid = str(entry.get("pmid") or "").strip()
    has_identifier = bool(doi or pmid)
    raw_only_source = _has_raw_citation(entry)

    missing: list[str] = []
    for f in ARTICLE_EXPECTED_FIELDS:
        if f == "authors":
            if not _entry_has_author(entry):
                missing.append("authors")
        elif not str(entry.get(f) or "").strip():
            missing.append(f)

    # Hard floor.
    if not title:
        return {"status": "incomplete", "missing_fields": missing or ["title"],
                "has_identifier": has_identifier, "raw_only": False}
    if not has_identifier and not raw_only_source:
        # No identifier and no raw fallback -> cannot render or verify.
        if "title" not in missing:
            missing = [*missing, "identifier"]
        return {"status": "incomplete", "missing_fields": missing,
                "has_identifier": has_identifier, "raw_only": False}

    # Structured fields all absent but a raw citation exists -> raw_only.
    structured_present = _entry_has_author(entry) or any(
        str(entry.get(f) or "").strip() for f in ("journal", "volume", "pages")
    )
    if not structured_present and raw_only_source:
        return {"status": "raw_only", "missing_fields": missing,
                "has_identifier": has_identifier, "raw_only": True}

    return {"status": "ok", "missing_fields": missing,
            "has_identifier": has_identifier, "raw_only": False}


_NAME_SUFFIXES = frozenset({"jr", "sr", "ii", "iii", "iv", "phd", "md", "msc",
                            "mph", "dphil", "facp", "frcp", "esq", "dds"})


def _is_initials_blob(tok: str) -> bool:
    """True for an initials run ("J", "JA", "DL") — never a surname.

    A lone letter is always initials; a 2-3 letter run counts only when it is
    all-caps, so real short surnames ("Lu", "Xu", "Li") stay surnames.
    ponytail: a wholly upper-cased index ("JANE DOE") defeats the caps signal;
    0 of 4037 real names are all-caps, so no extra code for it.
    """
    return len(tok) == 1 or (len(tok) <= 3 and tok.isupper())


def _name_tokens(text: str) -> list[str]:
    """Word tokens of a name: accents folded, hyphens/apostrophes joined, suffixes dropped.

    A suffix is only dropped when it is not an initials blob: "Carson MD" and
    "Marchesi JR" are initials M.D. / J.R., not a degree — dropping them would
    leave a bare surname key that matches every namesake.
    """
    text = re.sub(r"['‘’‐-―-]", "", text)   # Pan-Pan -> PanPan
    text = "".join(ch for ch in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(ch))            # Chavarría -> Chavarria
    return [t for t in re.findall(r"[^\W_]+", text)
            if t.lower() not in _NAME_SUFFIXES or _is_initials_blob(t)]


def _name_key(name: str) -> tuple[str, frozenset[str]] | None:
    """Reduce a person name to a (surname, given-initials) key for matching.

    Surname position is decided by format, not by token length:
      1. comma present -> the surname sits before it ("Doe, Jane", "van der Pol, E.");
      2. otherwise the surname is the **last non-initials token**. Vancouver puts
         its initials last ("Doe J", "Smith JA", "De Vos M") and natural order puts
         the surname last ("Jane Doe", "Pan-Pan Lu"), so one rule covers both.
    Multi-token surnames key on their last word ("van der Pol" -> "pol") so that
    both orderings agree. Every remaining token contributes its first letter to the
    initials set, so "Doe J" and "Jane Doe" both map to ("doe", {"j"}) -> match.
    CJK names map to (joined, ∅).

    Returns None for empty/unusable names.
    """
    raw = str(name or "")
    low = re.sub(r"[^a-z0-9一-鿿]+", " ", raw.lower()).strip()
    if not low:
        return None
    if re.search(r"[一-鿿]", low):
        return (re.sub(r"\s+", "", low), frozenset())
    toks = _name_tokens(raw)
    if not toks:
        return None
    if len(toks) == 1:
        return (toks[0].lower(), frozenset())
    head = _name_tokens(raw.split(",", 1)[0]) if "," in raw else []
    if head:
        surname, given = head[-1], head[:-1] + _name_tokens(raw.split(",", 1)[1])
    else:
        words = [i for i, t in enumerate(toks) if not _is_initials_blob(t)]
        i = words[-1] if words else len(toks) - 1
        surname, given = toks[i], toks[:i] + toks[i + 1:]
    return (surname.lower(), frozenset(t[0].lower() for t in given))


def _names_match(a: tuple[str, frozenset[str]], b: tuple[str, frozenset[str]]) -> bool:
    if a[0] != b[0]:
        return False
    # Same surname: match if either side has no given initials, or they overlap.
    return (not a[1]) or (not b[1]) or bool(a[1] & b[1])


def _is_name_continuation(seg: str, prev: str) -> bool:
    """True when a comma-part continues ``prev`` instead of starting a new author.

    Commas serve double duty in author strings ("Zhang, W." is one person;
    "Nasim, F., B.F. Sabath" is two), so a bare comma split is wrong. A part
    continues the previous name when it carries no surname of its own.

    Tokenized by _name_tokens so a hyphenated given name stays one token:
    "Wang, Xue-Meng" is one person, not a Wang plus a Xue plus a Meng.
    """
    toks = _name_tokens(seg)
    if not toks:
        return True                       # "Jr." / "PhD" / punctuation only
    if all(_is_initials_blob(t) for t in toks):
        return True                       # "F." / "B.F." / "WX" -> initials of prev surname
    # "Smith, John" / "Silva, Caio C G": one given name (plus its own middle
    # initials) right after a bare single-token surname. Initials *leading* the
    # segment mark a new author in natural order ("B.F. Sabath"), never a
    # continuation.
    # ponytail: this misreads bare-surname lists ("Sabath, Eapen, Nasim") as one
    # person; real bibliographies always carry initials, so not worth more code.
    words = [t for t in toks if not _is_initials_blob(t)]
    return (len(words) == 1 and not _is_initials_blob(toks[0])
            and len(prev.split()) == 1)


def _split_names(text: str) -> list[str]:
    """Split one raw author string into individual person names."""
    names: list[str] = []
    for chunk in re.split(r"\s*(?:;|\band\b|&|\bet\s*al\.?)\s*", text):
        prev: str | None = None           # None = chunk start, always a new name
        for seg in chunk.split(","):
            seg = seg.strip()
            if not seg:
                continue
            if prev is not None and _is_name_continuation(seg, prev):
                names[-1] = f"{names[-1]}, {seg}"
            else:
                names.append(seg)
            prev = names[-1]
    return names


def _split_author_field(value: Any) -> list[str]:
    # Every element is re-split: real indexes often stash a whole author list in
    # a single list slot (['Nasim, F., B.F. Sabath, and G.A. Eapen']), which used
    # to collapse to one name key and silently under-count self-citations.
    if isinstance(value, list):
        return [n for x in value for n in _split_names(str(x))]
    if isinstance(value, str):
        return _split_names(value)
    return []


def _entry_author_keys(entry: dict[str, Any]) -> list[tuple[str, frozenset[str]]]:
    names = _split_author_field(entry.get("authors"))
    if not names and entry.get("author"):
        names = _split_author_field(entry.get("author"))
    keys = [_name_key(n) for n in names]
    return [k for k in keys if k is not None]


def check_self_citation(
    entries: list[dict[str, Any]],
    manuscript_authors: list[str] | None,
    threshold: float = 0.4,
) -> dict[str, Any]:
    """J5 — self-citation overuse (advisory / WARN).

    A reference counts as a self-citation when at least one normalized
    manuscript-author name appears among its authors. self_ratio = self-cited /
    total entries that *have* author data (entries with no authors are excluded
    from the denominator so raw_only/identifier-only refs don't dilute it).

    manuscript_authors empty/None -> {"status": "skipped"} (graceful, never an
    error): existing projects with no authors field keep working untouched.

    Returns when authors known:
      {status: "ok"|"warn", self_ratio, count, total_with_authors, threshold}.
    """
    author_keys = [k for k in (_name_key(a) for a in (manuscript_authors or [])) if k is not None]
    if not author_keys:
        return {"status": "skipped", "reason": "no_manuscript_authors"}

    total_with_authors = 0
    self_count = 0
    for e in entries:
        if not isinstance(e, dict):
            continue
        entry_keys = _entry_author_keys(e)
        if not entry_keys:
            continue
        total_with_authors += 1
        if any(_names_match(ma, ea) for ma in author_keys for ea in entry_keys):
            self_count += 1

    if total_with_authors == 0:
        return {"status": "skipped", "reason": "no_entries_with_authors"}

    self_ratio = self_count / total_with_authors
    status = "warn" if self_ratio > threshold else "ok"
    return {
        "status": status,
        "self_ratio": round(self_ratio, 4),
        "count": self_count,
        "total_with_authors": total_with_authors,
        "threshold": threshold,
    }


def check_recency(
    entries: list[dict[str, Any]],
    current_year: int,
    window: int = 5,
    min_recent_ratio: float = 0.3,
) -> dict[str, Any]:
    """J7 — citation recency (advisory / WARN).

    recent_ratio = entries published within the last ``window`` years (inclusive
    of current_year) over entries that carry a parseable year. ``current_year``
    is supplied by the caller (scripts must not call Date.now()).

    No entries with a usable year -> {"status": "skipped"}.

    Returns: {status: "ok"|"warn", recent_ratio, recent_count, total_with_year,
              window, current_year, min_recent_ratio}.
    """
    cutoff = current_year - window + 1
    total_with_year = 0
    recent_count = 0
    for e in entries:
        if not isinstance(e, dict):
            continue
        raw_year = e.get("year")
        if raw_year is None or str(raw_year).strip() == "":
            continue
        try:
            yr = int(str(raw_year).strip()[:4])
        except (ValueError, TypeError):
            continue
        total_with_year += 1
        if yr >= cutoff:
            recent_count += 1

    if total_with_year == 0:
        return {"status": "skipped", "reason": "no_entries_with_year"}

    recent_ratio = recent_count / total_with_year
    status = "warn" if recent_ratio < min_recent_ratio else "ok"
    return {
        "status": status,
        "recent_ratio": round(recent_ratio, 4),
        "recent_count": recent_count,
        "total_with_year": total_with_year,
        "window": window,
        "current_year": current_year,
        "min_recent_ratio": min_recent_ratio,
    }


def check_bidirectional(
    cited_numbers: set[int] | set[str],
    listed_numbers: set[int] | set[str],
) -> dict[str, Any]:
    """A4 — bidirectional citation/list integrity (fail-closed when broken).

    Both inputs are sets of citation numbers, already extracted by the adapter:
      - cited_numbers: every [n] appearing in the manuscript body.
      - listed_numbers: every entry number present in the reference list.

    orphans  = cited but not listed  (a [n] in text with no list entry).
    zombies  = listed but not cited  (a list entry never referenced in text).

    Returns: {status: "ok"|"fail", orphans[], zombies[]} with sorted numeric
    lists. Caller treats status=="fail" as blocking.
    """
    def _as_int(x: Any) -> int | None:
        try:
            return int(str(x).strip())
        except (ValueError, TypeError):
            return None

    cited = {v for v in (_as_int(x) for x in cited_numbers) if v is not None}
    listed = {v for v in (_as_int(x) for x in listed_numbers) if v is not None}
    orphans = sorted(cited - listed)
    zombies = sorted(listed - cited)
    status = "fail" if (orphans or zombies) else "ok"
    return {"status": status, "orphans": orphans, "zombies": zombies}


def _provider_family(raw: str) -> str:
    """Map a raw provider string to its family.

    Accepts a string (not a dict). Field-name differences across skills stay in
    the adapter layer, which extracts the raw provider value before calling.
    """
    p = str(raw or "").strip().lower()
    if p.startswith("paper-search"):
        return "paper-search"
    if p.startswith("pubmed"):
        return "pubmed-cli"
    if p.startswith("openalex") or p == "pyalex":
        return "openalex-cli"
    if p.startswith("tavily"):
        return "tavily"
    if "websearch" in p or "web-search" in p or "web_search" in p:
        return "websearch"
    return p


def validate_core(
    entry: dict[str, Any],
    *,
    online: bool,
    require_mcp: bool = False,
    mcp_record: dict[str, Any] | None = None,
    require_identifier: bool = False,
    prefetched: dict[str, Any] | None = None,
    mcp_ttl_days: int = 30,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Verify a single normalized citation entry.

    Input entry is the normalized schema produced by the adapter:
        {title, doi, pmid, provider_family, source_id, year}
    plus an optional ``retracted`` flag. ``provider_family`` is already mapped
    via _provider_family by the adapter.

    Switches:
      - require_mcp: when True, unresolved/stale MCP evidence is blocking.
      - require_identifier: when True, an entry with no DOI and no PMID hard-fails
        with ``identifier_missing`` regardless of by-title verification (for nsfc;
        not wired in this phase).
      - prefetched: optional pre-fetched online data to avoid re-hitting APIs.
        Recognized keys: ``crossref`` / ``pubmed`` (records shaped like the
        _fetch_* return values), ``title_verify`` (a _verify_title_exists match).
        When a key is present it is used as-is; when absent the corresponding
        online fetch runs (subject to ``online``).
      - mcp_ttl_days / now_utc: MCP freshness window and clock (adapter supplies).

    Returns a normalized result dict:
        {verified, failure_reasons[], confidence, needs_manual_review, details}
    where ``details`` carries the full per-check breakdown.

    ``verified`` requires ``online``: an offline run performs no external lookup,
    so it can only report "not verified", never "verified". failure_reasons stays
    empty for a well-formed entry (nothing failed — it just was not checked); the
    reason is readable from ``details.sources.online_check``.
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    if prefetched is None:
        prefetched = {}

    title = str(entry.get("title") or "").strip()
    doi = str(entry.get("doi") or "").strip()
    pmid = str(entry.get("pmid") or "").strip()
    provider_family = str(entry.get("provider_family") or "").strip().lower()
    source_id = str(entry.get("source_id") or "").strip()

    doi_fmt_ok = DOI_RE.match(doi) is not None if doi else None
    pmid_fmt_ok = PMID_RE.match(pmid) is not None if pmid else None

    mcp_ok = bool(mcp_record)
    mcp_fresh, mcp_fresh_reason = _is_mcp_fresh(mcp_record or {}, mcp_ttl_days, now_utc) if mcp_ok else (False, None)

    # Online fetches honor prefetched cache first (lazy / re-use), else fetch.
    if "crossref" in prefetched:
        crossref = prefetched["crossref"]
    else:
        crossref = _fetch_crossref_by_doi(doi) if (online and doi and doi_fmt_ok) else None
    if "pubmed" in prefetched:
        pubmed = prefetched["pubmed"]
    else:
        pubmed = _fetch_pubmed_by_pmid(pmid) if (online and pmid and pmid_fmt_ok) else None

    has_identifier = bool(doi or pmid)

    # G0c: derive article_type from the PubMed pubtype list (PMID path only);
    # non-PubMed / no pubtype -> "unknown". Back-compat: purely additive, never
    # affects verification outcome.
    article_type = classify_article_type((pubmed or {}).get("pubtype"), source=provider_family)

    # By-title verification: only when the entry carries NO DOI and NO PMID.
    # Confirms the title corresponds to a real publication (Crossref/Semantic
    # Scholar). Gray zone (no match / unreachable / offline) stays FAIL.
    title_verify: dict[str, Any] | None = None
    if not has_identifier and title:
        if "title_verify" in prefetched:
            title_verify = prefetched["title_verify"]
        elif online:
            title_verify = _verify_title_exists(title)
    title_verified = title_verify is not None

    source_title_pairs = [
        (name, str(rec["title"]))
        for name, rec in (("mcp_record", mcp_record), ("pubmed", pubmed), ("crossref", crossref))
        if rec and rec.get("title")
    ]
    source_titles = [t for _, t in source_title_pairs]

    title_similarity = max((_title_similarity(title, st) for st in source_titles), default=0.0)
    title_match = bool(source_titles) and title_similarity >= 0.72

    # Per-source title cross-validation: detect spliced/fabricated entries
    crossref_title_sim = _title_similarity(title, crossref["title"]) if (crossref and crossref.get("title") and title) else None
    pubmed_title_sim = _title_similarity(title, pubmed["title"]) if (pubmed and pubmed.get("title") and title) else None
    crossref_title_ok = crossref_title_sim is None or crossref_title_sim >= 0.72
    pubmed_title_ok = pubmed_title_sim is None or pubmed_title_sim >= 0.72

    # Year reasonableness check
    entry_year = entry.get("year")
    year_reasonable = True
    if entry_year is not None:
        try:
            yr = int(entry_year)
            year_reasonable = 1900 <= yr <= now_utc.year + 1
        except (ValueError, TypeError):
            year_reasonable = False

    doi_valid: bool | None
    if doi:
        if not doi_fmt_ok:
            doi_valid = False
        else:
            http_ok = crossref is not None if online else True
            mcp_doi = str((mcp_record or {}).get("doi") or "").strip().lower()
            mcp_ok_doi = (mcp_doi == doi.lower()) if mcp_doi else True
            doi_valid = http_ok and mcp_ok_doi
    else:
        doi_valid = None

    pmid_match: bool | None
    if pmid:
        if not pmid_fmt_ok:
            pmid_match = False
        else:
            http_ok = pubmed is not None if online else True
            mcp_pmid = str((mcp_record or {}).get("pmid") or "").strip()
            mcp_ok_pmid = (mcp_pmid == pmid) if mcp_pmid else True
            pmid_match = http_ok and mcp_ok_pmid
    else:
        pmid_match = None

    id_cross_match = True
    if doi and pmid and pubmed and pubmed.get("doi"):
        id_cross_match = str(pubmed["doi"]).lower() == doi.lower()

    retracted = bool(entry.get("retracted", False))
    for rec in (mcp_record, pubmed, crossref):
        if rec and rec.get("retracted"):
            retracted = True

    has_traceability = bool(provider_family and source_id)

    failure_reasons: list[str] = []
    if not title:
        failure_reasons.append("title_missing")
    if provider_family in FORBIDDEN_PROVIDER_FAMILIES:
        failure_reasons.append("source_provider_forbidden")
    elif provider_family and provider_family not in ALLOWED_PROVIDER_FAMILIES:
        failure_reasons.append("source_provider_not_allowed")
    if not has_identifier:
        # No DOI/PMID. require_identifier makes this an unconditional hard fail;
        # otherwise only acceptable if by-title verification found a real,
        # high-similarity match (else blocking + manual review below).
        if require_identifier:
            failure_reasons.append("identifier_missing")
        elif not title_verified:
            failure_reasons.append("identifier_missing")
            if online and title:
                failure_reasons.append("title_not_found_online")
    if title and source_titles and not title_match:
        failure_reasons.append("title_mismatch")
    if not crossref_title_ok:
        failure_reasons.append("crossref_title_mismatch")
    if not pubmed_title_ok:
        failure_reasons.append("pubmed_title_mismatch")
    if not year_reasonable:
        failure_reasons.append("year_unreasonable")
    if doi_valid is False:
        failure_reasons.append("doi_invalid_or_unresolved")
    if pmid_match is False:
        failure_reasons.append("pmid_invalid_or_unresolved")
    if not id_cross_match:
        failure_reasons.append("id_mismatch")
    if retracted:
        failure_reasons.append("retracted")
    if not has_traceability:
        failure_reasons.append("source_trace_missing")
    if require_mcp:
        if not mcp_ok:
            failure_reasons.append("mcp_unresolved")
        elif not mcp_fresh:
            failure_reasons.append(mcp_fresh_reason or "mcp_stale")
    elif mcp_ok and (not mcp_fresh):
        failure_reasons.append("mcp_stale_warning")
    if online and has_identifier and not (crossref or pubmed):
        failure_reasons.append("source_unreachable")

    bidirectional_verification_failed = any(
        r in {"title_mismatch", "crossref_title_mismatch", "pubmed_title_mismatch",
              "doi_invalid_or_unresolved", "pmid_invalid_or_unresolved", "id_mismatch"}
        for r in failure_reasons
    )
    if bidirectional_verification_failed:
        failure_reasons.append("manual_confirmation_required_bidirectional_failure")

    # ── advisories（不阻断）：以下三段只写 advisories，绝不碰 failure_reasons /
    # verified / needs_manual_review / confidence。见本文件 advisories 段的禁令。
    advisories: list[dict[str, Any]] = []
    if title:
        # ① 同一 code 只留相似度最高的一条；元素顺序固定为桶序（§1.3）。
        best_by_code: dict[str, dict[str, Any]] = {}
        for src_name, src_title in source_title_pairs:
            adv = detect_title_variant(title, src_title, src_name)
            if adv and adv["similarity"] > best_by_code.get(adv["code"], {}).get("similarity", -1.0):
                best_by_code[adv["code"]] = adv
        advisories.extend(best_by_code[c] for c, _kw in _VARIANT_BUCKETS if c in best_by_code)

    # ② 只在条目已判失败时回查标识符；token<3 的标题不查（防垃圾 query）；
    # 离线不查也不报（见 _identifier_unavailable 上方注释：离线态是零信息量常量）。
    if online and (bidirectional_verification_failed or "source_unreachable" in failure_reasons) \
            and has_identifier and len(_title_tokens(title)) >= 3:
        ident_adv = classify_identifier_suggestion(doi, pmid, *_lookup_by_title(title))
        if ident_adv:
            advisories.append(ident_adv)

    needs_manual_review = any(
        r in {"title_mismatch", "id_mismatch", "mcp_stale", "mcp_timestamp_missing",
              "source_unreachable", "identifier_missing", "title_not_found_online"}
        for r in failure_reasons
    ) or bidirectional_verification_failed

    score = 0.0
    score += (title_similarity * 35) if source_titles else 15  # neutral when no sources to compare
    if doi_valid is True:
        score += 18
    elif doi_valid is False:
        score -= 8
    if pmid_match is True:
        score += 18
    elif pmid_match is False:
        score -= 8
    score += 10 if id_cross_match else -12
    score += 8 if has_traceability else -15
    if provider_family in ALLOWED_PROVIDER_FAMILIES:
        score += 6
    elif provider_family in FORBIDDEN_PROVIDER_FAMILIES:
        score -= 20
    elif provider_family:
        score -= 10
    score += (8 if mcp_ok else (-10 if require_mcp else 0))
    if mcp_ok:
        score += 6 if mcp_fresh else -8
    score += (8 if (crossref or pubmed) else -8) if online else 4
    if not has_identifier:
        score += 12 if title_verified else -12
    if not crossref_title_ok:
        score -= 15
    if not pubmed_title_ok:
        score -= 15
    if not year_reasonable:
        score -= 10
    if retracted:
        score -= 60
    confidence = int(max(0, min(100, round(score))))

    # 🔴 离线绝不发"已核实"证书。online=False 时上面的 doi_valid / pmid_match 是
    # "没查所以算它对"（http_ok 恒 True），格式完整的编造条目因此能拿满分 —— 这就是
    # 假章的产地。"离线模式"这个状态本不存在：--offline 只可能是①测试 ②源站/代理连不上
    # （=故障），两种都不该产出 verified。
    # 注意不往 failure_reasons 里加码（那是冻结码表）：没有东西"失败"，只是这一轮没验；
    # "为什么没验"从 details.sources.online_check 读得出来。调用方据此把报告状态记为
    # unverified 而非 verified，退出码不变。
    verified = online and (len(failure_reasons) == 0) and (not bidirectional_verification_failed)

    details = {
        "checked_at": now_utc.isoformat(),
        "title_match": title_match,
        "title_similarity": round(title_similarity, 4),
        "title_verified": title_verified,
        "title_verify_source": (title_verify.get("source") if title_verify else None),
        "title_verify_similarity": (round(title_verify["similarity"], 4) if title_verify else None),
        "title_verify_matched_title": (title_verify.get("matched_title") if title_verify else None),
        "crossref_title_similarity": round(crossref_title_sim, 4) if crossref_title_sim is not None else None,
        "pubmed_title_similarity": round(pubmed_title_sim, 4) if pubmed_title_sim is not None else None,
        "crossref_fetched_title": (crossref["title"] if crossref and crossref.get("title") else None),
        "pubmed_fetched_title": (pubmed["title"] if pubmed and pubmed.get("title") else None),
        "year_reasonable": year_reasonable,
        "doi_valid": doi_valid,
        "pmid_match": pmid_match,
        "id_cross_match": id_cross_match,
        "bidirectional_verification_failed": bidirectional_verification_failed,
        "retracted": retracted,
        "has_traceability": has_traceability,
        "failure_reasons": failure_reasons,
        "confidence_score": confidence,
        "needs_manual_review": needs_manual_review,
        "advisories": advisories,
        "sources": {
            "mcp": bool(mcp_record),
            "pubmed": bool(pubmed),
            "crossref": bool(crossref),
            "online_check": online,
            "mcp_ttl_days": mcp_ttl_days,
            "require_mcp": require_mcp,
            "provider_family": provider_family,
        },
    }

    return {
        "verified": verified,
        "failure_reasons": failure_reasons,
        "confidence": confidence,
        "needs_manual_review": needs_manual_review,
        "article_type": article_type,
        "details": details,
    }
