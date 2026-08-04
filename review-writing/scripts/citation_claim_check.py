#!/usr/bin/env python3
"""引文核证（共享，8 技能通用）——判"引用是否真支持它挂的论点"，而非只验真实性。

定位：矩阵驱动写作的一环。写某节前建"观点↔引文"矩阵时，对每个观点↔引用，拿该引文
**检索到的真实 abstract**（不看可编的 key_finding）判支撑度。承重论点句 contradict/无法判定
→ fail-closed，逼人工处理；承重句还须逐条人工确认(user_confirmed)。背景陈述句只在表里
批量呈现、不逐条阻断。**不含 MCP、不碰 hook**——取 abstract 那半走各技能工作流子代理。

CLI:
  python citation_claim_check.py --root <project_root> [--evidence claim_evidence.json]
  python citation_claim_check.py --evidence <path>            # 直接指定

输入 claim_evidence.json：list，每条
  {section, claim_sentence, is_load_bearing(bool), ref_id,
   retrieved_abstract, verdict∈support/weak/contradict/unknown,
   evidence_quote, user_confirmed(bool)}

行为：
  - 渲染面向用户的矩阵表（stdout 上半）。
  - fail-closed(exit 2) 若任一**承重句**：verdict∈{contradict,unknown} / 缺 retrieved_abstract
    / verdict∈{support,weak} 但 user_confirmed!=true（承重句必须人工逐条确认）。
  - 背景句的 contradict/weak：表里标红提示，不阻断（走批量确认）。
  - stdout 末行输出机器可读 JSON 摘要 {ok, blockers:[...], counts:{...}}。
"""
from __future__ import annotations

import sys as _sys
try:  # Windows GBK 控制台/管道捕获下 emoji print 防 UnicodeEncodeError
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# 「哪些键是文献条目」只有一份实现（citation_guard 的读取与写回也用它）。
# ponytail: 硬 import，缺 vendored 副本就当场炸——这是 MANIFEST/L4/CI 三道守卫
# 都盯着的同目录文件，静默降级只会让纪律再哑火一次。
from citation_guard_core import _dict_entry_keys  # noqa: E402

VALID_VERDICTS = {"support", "weak", "contradict", "unknown"}
REVIEW_TYPES = {"review", "systematic_review"}
EFFICACY_OK_TYPES = {"meta_analysis", "clinical_trial"}
# 机制断言的禁挂集合 = 全部二次文献。Meta 分析对**疗效**是合法上位证据
# （汇总同类试验的效应量），但它同样不含一手机制实验，拿它撑"A 通过 B 调控 C"
# 是错的——这条此前漏在 REVIEW_TYPES 之外，机制挂 Meta 一直放行。
MECHANISM_FORBIDDEN_TYPES = REVIEW_TYPES | {"meta_analysis"}


def _norm(s) -> str:
    """折叠空白做子串比对的归一化。"""
    return " ".join(str(s or "").split())


def _load_evidence(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("rows"), list):
        return data["rows"]
    if isinstance(data, list):
        return data
    raise ValueError("claim_evidence 必须是 list 或 {rows:[...]}")


# 索引路径与条目主键各家不统一（依据各家自己的写入脚本/config 实测，2026-08-04）：
#   路径：gsw/sci2doc=<root>/literature_index.json；nsfc/rw/revise-sci=<root>/data/literature_index.json
#   主键：sci2doc/nsfc=id；rw/revise-sci=global_id；gsw=citation_number
#        （与 delegate_write_core._index_id_field 的口径一一对应；rr 家无索引概念）
# 本脚本是家无关共享件，拿不到也不该拿家名 config → 按数据形状探测：路径取第一个
# 存在的候选；主键把条目上所有候选字段的值都注册（setdefault 先到先得）。
# 新增布局时只改这两个元组，禁止写家名 if/elif 散弹分支。
_INDEX_PATH_CANDIDATES = ("literature_index.json", "data/literature_index.json")
_INDEX_ID_FIELDS = ("id", "global_id", "citation_number")


def _load_ledger(root_dir: Path) -> tuple[dict, int, str | None]:
    """从 literature_index.json（+ ref_evidence_cache.json abstract 兜底）建
    ref_id → {abstract, article_type} 索引。缺失/损坏一律当空（fail-safe，不炸）。
    返回 (索引, 索引本体条目数, 实际选中的索引路径或 None)——条目数为 0 时调用方
    必须把"这次没有索引可依据"打出来，不许和"检查过且通过"混同。"""
    out: dict[str, dict] = {}
    index_entries = 0
    index_path: str | None = None
    if not root_dir:
        return out, index_entries, index_path
    data = None
    for rel in _INDEX_PATH_CANDIDATES:
        p = root_dir / rel
        if not p.is_file():
            continue
        index_path = str(p)
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            data = None
        break  # 第一个存在的候选定胜负：坏了也当空，不再向下读另一处可能陈旧的副本
    entries: list = []
    dict_keys: list[str] = []   # dict_values 形状下条目的原键，与 entries 一一对应
    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        for k in ("entries", "papers", "items", "references", "data"):
            if isinstance(data.get(k), list):
                entries = data[k]
                break
        else:
            # 「按编号做键」的索引（{"1": {...}, "2": {...}}）。判据与
            # citation_guard 的读取/写回共用同一份（metadata 等账本头排除），
            # 两边挑法一旦分叉就会串行。
            dict_keys = _dict_entry_keys(data)
            entries = [data[k] for k in dict_keys]
    for pos, e in enumerate(entries):
        if not isinstance(e, dict):
            continue
        keys = [str(e[f]) for f in _INDEX_ID_FIELDS if e.get(f) not in (None, "")]
        if not keys and dict_keys:
            keys = [dict_keys[pos]]  # 这种形状下原键就是 ref_id，条目内不一定再存一份
        if not keys:
            continue
        index_entries += 1
        rec = {
            "abstract": str(e.get("abstract") or ""),
            "article_type": str(e.get("article_type") or "unknown"),  # 缺字段 → unknown
        }
        for k in keys:
            out.setdefault(k, rec)
    # ref_evidence_cache abstract 作子串比对的兜底来源（不覆盖已有条目；不计入索引条目数）
    cache = _load_cache(root_dir / "ref_evidence_cache.json")
    for ref, rec in (cache.get("abstracts") or {}).items():
        if isinstance(rec, dict) and str(ref) not in out:
            out[str(ref)] = {"abstract": str(rec.get("retrieved_abstract") or ""),
                             "article_type": "unknown"}
    return out, index_entries, index_path


# section 来自 claim_evidence（主会话写、非子代理可控），含 `/`、`..`、glob 通配符
# 时会让下面的 glob 跳出 atomic_md 或误配全部节。仅做防路径穿越/glob 逃逸校验：
# 合法 section 形态各家不同（2.1 / results_3.1 / P1_立项依据），故用黑名单而非
# 字符白名单（后者会误伤 CJK section）。命中 → 当"无正文"处理（返回 None）。
_SECTION_UNSAFE = re.compile(r"[/\\*?\[\]]|\.\.")


def _section_body(root_dir: Path, section) -> str | None:
    """取本节 atomic_md 正文（供 preprint 标注检查）。找不到/非法 section → None。"""
    if not root_dir or not section:
        return None
    if _SECTION_UNSAFE.search(str(section)):
        return None
    for p in glob.glob(os.path.join(str(root_dir), "atomic_md", "*", f"{section}.md")):
        try:
            return Path(p).read_text(encoding="utf-8")
        except OSError:
            continue
    return None


# ── 跨批 ref 级证据缓存（ref_evidence_cache.json）──────────────────────────
# 目的：同一篇文献在第一批已核证后，脚本强制把结果落盘；第二批脚本自动读回、
# 免掉重复反向验证与重复人工确认——不依赖 AI 记得写字段（这是本次修复的核心）。
# 红线：abstract 是文献全局事实、可跨节复用；verdict/确认是「论点特定」的，只有
# 完全同一 (ref_id, 归一化 claim) 才复用，同篇拿去支持另一句话仍须独立判定+确认。
# fail-safe：缓存缺失/损坏一律当空处理，回落全量核验，绝不放行、绝不崩。

def _claim_key(claim_sentence) -> str:
    """归一化论点句作为复用键：仅小写 + 折叠空白，**不做语义归一**。
    只在大小写/空白上等价的才是同一论点（此时合并正确）；真正不同的论点
    不会撞同一 key，故不会误复用确认。"""
    return " ".join(str(claim_sentence or "").lower().split())


def _load_cache(path: Path) -> dict:
    """读 ref_evidence_cache.json。缺失/损坏 → 返回空缓存（fail-safe，回落全量核验）。"""
    empty = {"abstracts": {}, "verdicts": {}}
    try:
        if not path or not path.is_file():
            return empty
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, ValueError):
        return empty
    if not isinstance(data, dict):
        return empty
    ab = data.get("abstracts")
    vd = data.get("verdicts")
    return {"abstracts": ab if isinstance(ab, dict) else {},
            "verdicts": vd if isinstance(vd, dict) else {}}


def _save_cache(path: Path, cache: dict) -> None:
    """尽力回写；写失败绝不中断门禁。"""
    try:
        if path:
            path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _backfill_rows(rows: list, cache: dict, now_iso: str) -> dict:
    """用缓存**只补缺失字段**（原地修改），返回复用计数。绝不覆盖行已有的字段。
    - retrieved_abstract：文献全局事实 → 任一节/论点命中同 ref 即复用。
    - verdict + user_confirmed：论点特定 → 仅 (ref_id, 同一归一化 claim) 精确命中才补；
      同篇不同论点的行不补 → 仍走一次独立判定+确认（门禁强度不变、红线不破）。
    """
    abstracts = cache.get("abstracts", {})
    verdicts = cache.get("verdicts", {})
    reuse = {"abstract": 0, "verdict": 0}
    for row in rows:
        if not isinstance(row, dict):
            continue
        ref = str(row.get("ref_id") or "").strip()
        if not ref:
            continue
        if not str(row.get("retrieved_abstract") or "").strip():
            cached_ab = abstracts.get(ref)
            if isinstance(cached_ab, dict) and str(cached_ab.get("retrieved_abstract") or "").strip():
                row["retrieved_abstract"] = cached_ab["retrieved_abstract"]
                reuse["abstract"] += 1
        cached_vd = verdicts.get(f"{ref}||{_claim_key(row.get('claim_sentence'))}")
        if isinstance(cached_vd, dict) and cached_vd.get("user_confirmed") is True \
                and cached_vd.get("verdict") in {"support", "weak"}:
            filled = False
            if not row.get("verdict"):
                row["verdict"] = cached_vd["verdict"]
                filled = True
            if row.get("user_confirmed") is not True:
                row["user_confirmed"] = True
                filled = True
            if filled:
                reuse["verdict"] += 1
    return reuse


def _persist_rows(rows: list, cache: dict, now_iso: str) -> None:
    """脚本强制回写（不靠 AI 记得）：落盘文献全局 abstract + 已确认承重 verdict，
    供下一批复用。只存**已确立且已确认**的结论，绝不为新论点伪造 verdict。"""
    abstracts = cache.setdefault("abstracts", {})
    verdicts = cache.setdefault("verdicts", {})
    for row in rows:
        if not isinstance(row, dict):
            continue
        ref = str(row.get("ref_id") or "").strip()
        if not ref:
            continue
        ab = str(row.get("retrieved_abstract") or "").strip()
        if ab and ref not in abstracts:
            abstracts[ref] = {"retrieved_abstract": ab,
                              "source": row.get("abstract_source") or "",
                              "fetched_at": now_iso}
        if row.get("is_load_bearing") and row.get("user_confirmed") is True \
                and row.get("verdict") in {"support", "weak"}:
            verdicts[f"{ref}||{_claim_key(row.get('claim_sentence'))}"] = {
                "verdict": row["verdict"], "user_confirmed": True,
                "claim_sentence": row.get("claim_sentence") or "", "confirmed_at": now_iso}


def _row_blockers(row: dict) -> list[str]:
    """返回该行的阻断原因（空=不阻断）。只有承重句会产生阻断。"""
    if not row.get("is_load_bearing"):
        return []
    problems: list[str] = []
    ref = row.get("ref_id") or "?"
    verdict = row.get("verdict")
    if not (row.get("retrieved_abstract") or "").strip():
        problems.append(f"[{ref}] 承重句但未取到被引文献摘要，无法核证（需人工或重取摘要）")
        return problems  # 没摘要就没法谈 verdict
    if verdict not in VALID_VERDICTS:
        problems.append(f"[{ref}] verdict 非法/缺失：{verdict!r}")
    elif verdict in {"contradict", "unknown"}:
        problems.append(f"[{ref}] 承重论点被判 {verdict}——引文不支持/无法判定该论点，禁止照此下笔")
    if verdict in {"support", "weak"} and row.get("user_confirmed") is not True:
        problems.append(f"[{ref}] 承重句须逐条人工确认（user_confirmed 尚未为 true）")
    return problems


VERDICT_CN = {"support": "✅支持", "weak": "🟡弱相关", "contradict": "❌不支持", "unknown": "❔无法判定"}

# 200+ 条文献时 warnings/skipped_refs 逐条呈现会刷屏、淹没真正要处理的 blocker。
# 只压缩呈现（stdout 与 summary JSON 都截断到此上限并给出总数），检查覆盖面一条不少：
# 退出码与判定结论（ok/blockers/counts）与截断完全无关；全量明细加 --full-warnings 取。
WARN_DISPLAY_LIMIT = 10


def _render_table(rows: list[dict]) -> str:
    lines = ["## 引文核证矩阵（观点 ↔ 引文 ↔ 是否真支持）", "",
             "| 承重 | 章节 | 论点句 | 引文 | 判定 | 摘要证据句 | 已确认 |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        lb = "🔴承重" if r.get("is_load_bearing") else "背景"
        claim = (r.get("claim_sentence") or "").replace("|", "\\|")[:60]
        ref = str(r.get("ref_id") or "?")
        verdict = VERDICT_CN.get(r.get("verdict"), str(r.get("verdict")))
        ev = (r.get("evidence_quote") or "").replace("|", "\\|")[:60]
        conf = "是" if r.get("user_confirmed") is True else "—"
        sec = str(r.get("section") or "").replace("|", "\\|")[:16]
        lines.append(f"| {lb} | {sec} | {claim} | {ref} | {verdict} | {ev} | {conf} |")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="引文核证：判引文是否真支持论点")
    ap.add_argument("--root", default=None)
    ap.add_argument("--evidence", default=None)
    ap.add_argument("--cache", default=None,
                    help="ref 级证据缓存路径（默认 <root>/ref_evidence_cache.json）；跨批复用已验 abstract / 已确认 verdict")
    ap.add_argument("--no-cache", action="store_true",
                    help="禁用缓存 backfill/回写（仅校验当前 claim_evidence，不跨批复用）")
    ap.add_argument("--check-quote-substring", action="store_true",
                    help="防伪：承重行 evidence_quote 必须是账本 abstract 子串，否则 fail-closed(exit2)")
    ap.add_argument("--full-warnings", action="store_true",
                    help="不截断警告/跳过明细的呈现（默认超过 %d 条截断；退出码与判定结论不受截断影响）"
                         % WARN_DISPLAY_LIMIT)
    args = ap.parse_args()

    if args.evidence:
        ev_path = Path(args.evidence)
    elif args.root:
        ev_path = Path(args.root) / "claim_evidence.json"
    else:
        print("需 --root 或 --evidence")
        return 2

    if not ev_path.is_file():
        print(json.dumps({"ok": False, "error": "claim_evidence_missing",
                          "message": f"未找到 {ev_path}——先建本节观点↔引文矩阵并取真摘要核证"},
                         ensure_ascii=False))
        return 2

    try:
        rows = _load_evidence(ev_path)
    except Exception as e:
        print(json.dumps({"ok": False, "error": "bad_evidence", "message": str(e)}, ensure_ascii=False))
        return 2

    now_iso = datetime.now(timezone.utc).isoformat()
    cache_path = Path(args.cache) if args.cache else (
        (Path(args.root) if args.root else ev_path.parent) / "ref_evidence_cache.json")
    cache = None
    reuse = {"abstract": 0, "verdict": 0}
    if not args.no_cache:
        cache = _load_cache(cache_path)
        reuse = _backfill_rows(rows, cache, now_iso)  # 只补缺失字段，门禁强度不变

    print(_render_table(rows))
    print("")

    # 账本索引（article_type + abstract）：缺 → 空，机械纪律只 warning 不炸
    root_dir = Path(args.root) if args.root else ev_path.parent
    ledger, ledger_entries, ledger_path = _load_ledger(root_dir)

    blockers: list[str] = []       # exit 2（沿用原承重核证 + G0b 防伪/纪律硬拦）
    soft_blockers: list[str] = []  # exit 1（preprint 未标注）
    warnings: list[str] = []       # exit 0，仅提示
    # 机械纪律的执行台账：article_type 只有 PMID 路径才填得上，只有 DOI 的条目一律
    # unknown，纪律因此会大面积静默哑火。不硬拦（拿不到 PMID 是常态），但"没查"
    # 必须可统计、看得见，否则用户会以为全查过了。
    discipline_checked = 0
    discipline_skipped = 0
    discipline_skipped_refs: list[str] = []
    for r in rows:
        blockers.extend(_row_blockers(r))
        if not r.get("is_load_bearing"):
            continue
        ref = str(r.get("ref_id") or "?").strip() or "?"
        led = ledger.get(ref, {})
        atype = (str(led.get("article_type") or "unknown").strip().lower() or "unknown")
        ckind = (str(r.get("claim_kind") or "unknown").strip().lower() or "unknown")

        # G0b 防伪：evidence_quote 必须是账本 abstract 子串（仅 --check-quote-substring）
        if args.check_quote_substring:
            quote = str(r.get("evidence_quote") or "").strip()
            if quote:
                ledger_ab = led.get("abstract") or r.get("retrieved_abstract") or ""
                if _norm(quote) not in _norm(ledger_ab):
                    blockers.append(f"evidence_quote 非账本 abstract 子串: {ref}")

        # G0b 机械纪律（claim_kind × article_type，任一字段未就绪 → 只 warning + 记账）
        if ckind in ("", "unknown") or atype in ("", "unknown"):
            warnings.append(f"claim_kind/article_type 未就绪, 跳过机械纪律: {ref}")
            discipline_skipped += 1
            if ref not in discipline_skipped_refs:
                discipline_skipped_refs.append(ref)
        else:
            # 两个字段都就绪才算"真查过一条"（含判定为合法而放行的那些）
            discipline_checked += 1
            if ckind in ("mechanism", "efficacy") and atype in REVIEW_TYPES:
                blockers.append(f"承重机制/疗效声明不得挂综述: {ref}")
            elif ckind == "mechanism" and atype in MECHANISM_FORBIDDEN_TYPES:
                blockers.append(f"承重机制声明不得挂二次文献（{atype}）: {ref}")
            # efficacy 挂 meta_analysis/clinical_trial → 合法上位证据，放行（no-op）

        # preprint 标注：正文引了该 ref 但缺 [Preprint] 标记 → soft fail(exit1)
        if atype == "preprint":
            body = _section_body(root_dir, r.get("section"))
            if body is not None and f"[@{ref}]" in body and "[Preprint]" not in body:
                soft_blockers.append(f"preprint 未标注: {ref}")

    # 脚本强制回写（不靠 AI 记得）：即使本批仍有 blocker，也把已确立/已确认部分落盘
    if cache is not None:
        _persist_rows(rows, cache, now_iso)
        _save_cache(cache_path, cache)

    load_bearing = sum(1 for r in rows if r.get("is_load_bearing"))
    contradict = sum(1 for r in rows if r.get("verdict") == "contradict")
    # 呈现层截断（B 段防刷屏）：只截 warnings / skipped_refs 明细，blocker 是要处理的
    # 问题本身、逐条保留。判定（ok/blockers/counts/退出码）全部按全量算，与截断无关。
    limit = None if args.full_warnings else WARN_DISPLAY_LIMIT
    shown_warnings = warnings if limit is None else warnings[:limit]
    shown_skipped_refs = discipline_skipped_refs if limit is None else discipline_skipped_refs[:limit]
    summary = {
        "ok": not blockers and not soft_blockers,
        "blockers": blockers,
        "soft_blockers": soft_blockers,
        "warnings": shown_warnings,
        "warnings_total": len(warnings),
        "counts": {"total": len(rows), "load_bearing": load_bearing, "contradict": contradict,
                   "discipline_checked": discipline_checked,
                   "discipline_skipped": discipline_skipped,
                   "ledger_entries": ledger_entries},
        # 实际读到的文献索引路径（None=候选路径都不存在）；配合 ledger_entries 区分
        # "没索引可依据" 和 "索引在、个别条目字段缺"
        "ledger_path": ledger_path,
        # 哪些 ref 因 claim_kind/article_type 未就绪而没走机械纪律（去重、保序；
        # 呈现截断到 WARN_DISPLAY_LIMIT，全量总数看 counts.discipline_skipped）
        "discipline_skipped_refs": shown_skipped_refs,
        "cache_reuse": reuse,
    }
    if blockers:
        print("🔴 引文核证未过——承重论点存在下列问题，禁止照此下笔（改引文/改论点/补人工确认后重跑）：")
        for b in blockers:
            print(f"  - {b}")
        print("")
    else:
        print("✅ 引文核证通过：承重论点均有真摘要支撑且已人工确认（背景句请在上表批量核对）。")
    if ledger_entries == 0:
        # 判据："读到 0 条"必须和"检查过且通过"看得出区别——说清是索引不存在还是
        # 文件在但没有可识别条目，机械纪律与账本比对这次没有索引可依据。
        if ledger_path:
            where = f"读了 {ledger_path} 但没有可识别条目（主键候选 {'/'.join(_INDEX_ID_FIELDS)}）"
        else:
            tried = "、".join(str(root_dir / rel) for rel in _INDEX_PATH_CANDIDATES)
            where = f"候选路径均不存在：{tried}"
        print(f"🟡 文献索引 0 条——{where}。本次 article_type 全按 unknown 处理，"
              f"「机制/疗效声明不得挂综述」纪律与账本 abstract 比对没有索引可依据。")
    if discipline_skipped:
        # 一句话说清"这次有多少没查"，别让人以为全查过了。逐条 ⚠️ 在下面，
        # 200 条时那堆 warning 就是噪音，这一行才是用户真正要看见的。
        total_disc = discipline_checked + discipline_skipped
        head = "、".join(discipline_skipped_refs[:5])
        more = f" 等 {len(discipline_skipped_refs)} 篇" if len(discipline_skipped_refs) > 5 else ""
        print(f"🟡 机械纪律未执行 {discipline_skipped}/{total_disc} 条承重引用："
              f"claim_kind 或 article_type 未就绪（article_type 只有走 PMID 的文献才填得上，"
              f"只有 DOI 的条目一律 unknown）。这些引用的「机制/疗效声明不得挂综述」未被检查："
              f"{head}{more}")
    if soft_blockers:
        print("🟠 预印本标注缺失（需在正文引用处补 [Preprint] 标记）：")
        for s in soft_blockers:
            print(f"  - {s}")
    for w in shown_warnings:
        print(f"⚠️ {w}")
    hidden = len(warnings) - len(shown_warnings)
    if hidden > 0:
        print(f"⚠️ ……同类警告另有 {hidden} 条未展示（加 --full-warnings 看全部；退出码与判定结论不受截断影响）")
    print(json.dumps(summary, ensure_ascii=False))
    if blockers:
        return 2
    if soft_blockers:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
