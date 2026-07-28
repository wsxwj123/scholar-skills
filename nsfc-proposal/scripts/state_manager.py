#!/usr/bin/env python3
"""Project state manager for nsfc-proposal skill."""

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
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import consistency_mapper
import diagnosis_engine
import citation_validator
import word_counter


DEFAULT_PROFILE = {
    "project_type": "面上项目",
    "research_attribute": "自由探索类",
    "science_problem_attribute": None,
    "duration_years": 4,
    "budget_total": 500000,
    "page_limit": 30,
    "word_targets": {
        "p1_rationale": {"recommended_max": 8000, "user_agreed": None},
        "p2_content": {"recommended_max": 8000, "user_agreed": None},
        "p3_foundation": {"recommended_max": 6000, "user_agreed": None},
        "p4_other": {"recommended_max": 500, "user_agreed": None},
        "total_body": {"min": 18000, "max": 25000},
    },
    "citation_targets": {"min_total": 30, "min_recent_5yr": 20, "min_cn_journals": 5},
    "applicant_authors": [],
    "mode": "write",
}

# 国自然申请书"科学问题属性"四选一官方标准措辞（与"研究属性"为两个独立字段）
SCIENCE_PROBLEM_ATTRIBUTES = (
    "鼓励探索、突出原创",
    "聚焦前沿、独辟蹊径",
    "需求牵引、突破瓶颈",
    "共性导向、交叉融通",
)

SECTION_ALIASES = {
    "P1": "P1_立项依据.md",
    "P2": "P2_研究内容.md",
    "P3_1": "P3_1_研究基础与可行性分析.md",
    "P3_2": "P3_2_工作条件.md",
    "P3_3": "P3_3_正在承担的相关项目.md",
    "P3_4": "P3_4_完成基金项目情况.md",
    "P4": "P4_其他需要说明的情况.md",
    "REF": "REF_参考文献.md",
}


AUTO_FIX_STUBS = {
    "sections/P1_立项依据.md": "# P1_立项依据\n\n待补充。\n",
    "sections/REF_参考文献.md": "# REF_参考文献\n\n待补充。\n",
}


def ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_history(root: Path, event: str, payload: dict[str, Any] | None = None) -> None:
    history = load_json(root / "history_log.json", {"events": []})
    history.setdefault("events", []).append({"at": utc_now(), "event": event, "payload": payload or {}})
    save_json(root / "history_log.json", history)


def append_context(root: Path, content: str) -> None:
    path = root / "context_memory.md"
    if not path.exists():
        path.write_text("# Context Memory\n\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as f:
        f.write(f"## {utc_now()}\n")
        f.write(content.strip() + "\n\n")


def init_project(root: Path, force_shared: bool = False) -> None:
    # PROJECT_ROOT 归属冲突检测(fail-closed)：写任何东西之前，若该目录 project_state.json
    # 已被别的技能占用(skill 非空且≠nsfc-proposal)，拒绝，避免两技能同目录互相覆盖 state。
    if not force_shared:
        existing_state = load_json(root / "project_state.json", {})
        prior_skill = (existing_state.get("skill") or "").strip()
        if prior_skill and prior_skill != "nsfc-proposal":
            _sys.exit(
                f"PROJECT_ROOT 冲突：此目录已被 {prior_skill} 使用(project_state.json 的 skill={prior_skill})。"
                f"nsfc-proposal 与它同目录会互相覆盖 state；请另指空 --root，或确知安全时加 --force-shared 跳过。"
            )

    for d in ["sections", "output", "data", ".state", "snapshots"]:
        (root / d).mkdir(parents=True, exist_ok=True)

    # 自包含：把技能 scripts/*.py 全量拷进项目 scripts/，使 SKILL 命令
    # `python3 scripts/xxx.py` 在项目目录可直接运行（state_manager 还 import 同目录
    # consistency_mapper/diagnosis_engine/citation_validator/word_counter，必须全量拷）。
    src_dir = Path(__file__).resolve().parent
    dst_dir = root / "scripts"
    if src_dir.resolve() != dst_dir.resolve():
        dst_dir.mkdir(parents=True, exist_ok=True)
        # 拷 *.py 与 *.json（gate_registry.json 等必须进项目），跳过 test_*.py（测试不进产物）
        for src in glob.glob(str(src_dir / "*.py")) + glob.glob(str(src_dir / "*.json")):
            name = os.path.basename(src)
            if name.startswith("test_"):
                continue
            shutil.copy2(src, dst_dir / name)

    save_json(root / "proposal_profile.json", DEFAULT_PROFILE)
    save_json(root / "data/literature_index.json", {"metadata": {"verification_status": "pending"}, "entries": []})
    save_json(root / "data/consistency_map.json", consistency_mapper.load_map(Path("__missing__")))
    save_json(root / "project_state.json", {"skill": "nsfc-proposal", "phase": "phase0", "gate": "init", "updated_at": utc_now()})
    save_json(root / "history_log.json", {"events": []})

    (root / "context_memory.md").write_text("# Context Memory\n\n", encoding="utf-8")
    append_history(root, "init")
    append_context(root, "Project initialized.")


def deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def do_snapshot(root: Path, name: str) -> Path:
    # ts() 只到秒，同秒内多次快照(如连续 rollback 各写一个 pre_rollback)会撞名致 copytree 崩，
    # 撞名则加数字后缀保唯一。
    base = root / "snapshots" / f"{ts()}_{name}"
    snap = base
    i = 1
    while snap.exists():
        snap = Path(f"{base}_{i}")
        i += 1
    snap.mkdir(parents=True, exist_ok=True)

    for d in ["sections", "data", "output", ".state"]:
        src = root / d
        if src.exists():
            shutil.copytree(src, snap / d)

    for f in ["project_state.json", "proposal_profile.json", "history_log.json", "context_memory.md"]:
        src = root / f
        if src.exists():
            shutil.copy2(src, snap / f)

    append_history(root, "snapshot", {"name": name, "path": str(snap)})
    return snap


def _resolve_snapshot(root: Path, snapshot_dir: Path) -> Path:
    """裸快照名(如 20260714_x_good)解析到 root/snapshots/<名>；已是有效路径则原样返回。"""
    if not snapshot_dir.exists():
        candidate = root / "snapshots" / snapshot_dir.name
        if candidate.exists():
            return candidate
    return snapshot_dir


def _snapshot_has_content(snapshot_dir: Path) -> bool:
    """快照至少含 sections/data/output/.state 之一或 project_state.json 才算有内容。"""
    if not snapshot_dir.is_dir():
        return False
    for name in ["sections", "data", "output", ".state", "project_state.json"]:
        if (snapshot_dir / name).exists():
            return True
    return False


def rollback(root: Path, snapshot_dir: Path) -> bool:
    """回滚到指定快照。丢稿守卫：先解析裸名+校验快照非空，任何 rmtree 之前拒绝并返回 False。"""
    resolved = _resolve_snapshot(root, snapshot_dir)
    if not _snapshot_has_content(resolved):
        print(
            f"❌ rollback 拒绝：快照 '{snapshot_dir}' 解析为 '{resolved}'，"
            f"不存在或为空(未含 sections/data/output/.state/project_state.json 任一)。"
            f"工作区未改动。请核对快照名(可用裸名如 20260714_x)或路径。",
            file=_sys.stderr,
        )
        return False

    snapshot_dir = resolved
    do_snapshot(root, "pre_rollback")

    for d in ["sections", "data", "output", ".state"]:
        target = root / d
        if target.exists():
            shutil.rmtree(target)
        src = snapshot_dir / d
        if src.exists():
            shutil.copytree(src, target)

    for f in ["project_state.json", "proposal_profile.json", "history_log.json", "context_memory.md"]:
        src = snapshot_dir / f
        if src.exists():
            shutil.copy2(src, root / f)

    append_history(root, "rollback", {"snapshot": str(snapshot_dir)})
    append_context(root, f"Rolled back to snapshot: {snapshot_dir}")
    return True


def _phase_number(state: dict[str, Any]) -> int:
    phase = str(state.get("phase", ""))
    m = re.match(r"phase(\d+)", phase)
    return int(m.group(1)) if m else -1


def _semantic_sync_checks(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    cm = consistency_mapper.load_map(root / "data/consistency_map.json")
    cm_validation = consistency_mapper.validate(cm)
    cm_error = any((not x["pass"] and x["severity"] == "ERROR") for x in cm_validation.values())

    lit = load_json(root / "data/literature_index.json", {"metadata": {}, "entries": []})
    p1_entries = [e for e in lit.get("entries", []) if "P1_立项依据" in (e.get("used_in_sections") or [])]
    p1_verified = all(bool(e.get("verified")) for e in p1_entries) if p1_entries else False

    context_text = (root / "context_memory.md").read_text(encoding="utf-8") if (root / "context_memory.md").exists() else ""
    has_context_blocks = "## " in context_text

    history = load_json(root / "history_log.json", {"events": []})
    has_history = bool(history.get("events"))

    phase_no = _phase_number(state)
    require_strict = phase_no >= 1

    return {
        "cm_has_error": cm_error,
        "cm_validation": cm_validation,
        "p1_entries_count": len(p1_entries),
        "p1_verified": p1_verified,
        "has_context_blocks": has_context_blocks,
        "has_history": has_history,
        "strict_mode": require_strict,
    }


def sync_all(root: Path) -> dict[str, Any]:
    required = [
        root / "data/consistency_map.json",
        root / "data/literature_index.json",
        root / "context_memory.md",
        root / "project_state.json",
        root / "history_log.json",
    ]
    exists = {str(p.relative_to(root)): p.exists() for p in required}

    state = load_json(root / "project_state.json", {})
    phase = state.get("phase", "")
    gate = state.get("gate", "")
    if phase == "phase0" and gate == "init":
        fresh = {str(p.relative_to(root)): True for p in required if p.name != "project_state.json"}
    else:
        state_mtime = (root / "project_state.json").stat().st_mtime if (root / "project_state.json").exists() else 0.0
        grace_seconds = 2.0
        fresh = {
            str(p.relative_to(root)): (p.exists() and (p.stat().st_mtime + grace_seconds) >= state_mtime)
            for p in required
            if p.name != "project_state.json"
        }

    semantic = _semantic_sync_checks(root, state)

    return {
        "exists": exists,
        "fresh": fresh,
        "semantic": semantic,
    }



def _sync_semantic_ok(semantic: dict[str, Any]) -> bool:
    if semantic.get("strict_mode"):
        return (
            (not semantic.get("cm_has_error"))
            and bool(semantic.get("has_context_blocks"))
            and bool(semantic.get("has_history"))
            and bool(semantic.get("p1_verified"))
        )
    return bool(semantic.get("has_context_blocks")) and bool(semantic.get("has_history"))


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


def gate_check(
    root: Path,
    sections_dir: str = "sections",
    index_path: str = "data/literature_index.json",
    p1_path: str = "sections/P1_立项依据.md",
    ref_path: str = "sections/REF_参考文献.md",
    mcp_cache_path: str = "data/mcp_literature_cache.json",
    mcp_ttl_days: int = 30,
    offline: bool = False,
    require_mcp: bool = True,
) -> dict[str, Any]:
    sync_status = sync_all(root)
    exists_ok = all(sync_status["exists"].values())
    fresh_ok = all(sync_status["fresh"].values()) if sync_status["fresh"] else True
    semantic_ok = _sync_semantic_ok(sync_status["semantic"])
    sync_ok = exists_ok and fresh_ok and semantic_ok

    idx_file = root / index_path
    p1_file = root / p1_path
    ref_file = root / ref_path
    mcp_file = root / mcp_cache_path

    idx = citation_validator._normalize_index(load_json(idx_file, {"metadata": {}, "entries": []}))
    mcp_cache = citation_validator._normalize_mcp_cache(
        load_json(mcp_file, {"metadata": {"schema_version": citation_validator.CACHE_SCHEMA_VERSION}, "entries": []})
    )
    save_json(mcp_file, mcp_cache)
    mcp_schema_version = str((mcp_cache.get("metadata") or {}).get("schema_version") or citation_validator.CACHE_SCHEMA_VERSION)
    mcp_index = citation_validator._build_mcp_index(mcp_cache)

    p1_text = p1_file.read_text(encoding="utf-8") if p1_file.exists() else ""
    ref_text = ref_file.read_text(encoding="utf-8") if ref_file.exists() else ""

    idx, run_stats, manual_queue = citation_validator.verify_all(
        idx,
        p1_text=p1_text,
        online_check=not offline,
        mcp_index=mcp_index,
        mcp_ttl_days=max(0, int(mcp_ttl_days)),
        require_mcp=require_mcp,
        mcp_schema_version=mcp_schema_version,
    )
    save_json(idx_file, idx)
    save_json(
        root / "data/manual_review_queue.json",
        {
            "generated_at": utc_now(),
            "count": len(manual_queue),
            "entries": manual_queue,
        },
    )
    _append_verification_log(
        root / "data/verification_run_log.json",
        {
            "index": str(idx_file),
            "verification_status": idx.get("metadata", {}).get("verification_status"),
            **run_stats,
        },
    )

    citation_ok = idx.get("metadata", {}).get("verification_status") == "verified"
    matrix = citation_validator.matrix_check(p1_text, idx, ref_text)
    matrix_ok = bool(matrix.get("ok"))

    profile = load_json(root / "proposal_profile.json", DEFAULT_PROFILE)

    # 总量文献门：min_total 为硬门（<min_total 阻断交付），近5年/中文/P1段为软 warn。
    # ponytail: 直接读 verify_all 写入 metadata 的计数，无需重新统计。
    citation_targets = profile.get("citation_targets") or DEFAULT_PROFILE["citation_targets"]
    min_total = int(citation_targets.get("min_total", 30))
    min_recent = int(citation_targets.get("min_recent_5yr", 20))
    min_cn = int(citation_targets.get("min_cn_journals", 5))
    lit_meta = idx.get("metadata", {})
    total_count = int(lit_meta.get("total_count", len(idx.get("entries", []))))
    recent_count = int(lit_meta.get("recent_5yr_count", 0))
    cn_count = int(lit_meta.get("cn_journal_count", 0))
    p1_cite_count = int(matrix.get("p1_count", 0))
    literature_ok = total_count >= min_total  # 硬门
    literature_warnings: list[str] = []
    if recent_count < min_recent:
        literature_warnings.append(f"[LIT-WARN] 近5年文献 {recent_count} 篇 < 软目标 {min_recent} 篇")
    if cn_count < min_cn:
        literature_warnings.append(f"[LIT-WARN] 中文期刊文献 {cn_count} 篇 < 软目标 {min_cn} 篇")
    if p1_cite_count < 20:  # ponytail: 立项依据 P1 段软目标固定 20，nsfc 文献集中在立项依据
        literature_warnings.append(f"[LIT-WARN] 立项依据(P1)引用 {p1_cite_count} 处 < 软目标 20 处")
    spa = profile.get("science_problem_attribute")
    profile_ok = isinstance(spa, str) and spa.strip() in SCIENCE_PROBLEM_ATTRIBUTES

    review = diagnosis_engine.full_review(
        sections_dir=root / sections_dir,
        consistency_path=root / "data/consistency_map.json",
        index_path=idx_file,
        p1_path=p1_file,
        ref_path=ref_file,
        page_limit=int(profile.get("page_limit", 30)),
    )
    review_ok = review.get("pass_status") == "pass" and int(review.get("d_count", 0)) == 0 and int(review.get("c_count", 0)) <= 3

    overall_ok = profile_ok and sync_ok and citation_ok and literature_ok and matrix_ok and review_ok
    if not profile_ok:
        failed_at = "profile"
    elif not sync_ok:
        failed_at = "sync"
    elif not citation_ok:
        failed_at = "citation"
    elif not literature_ok:
        failed_at = "literature_total"
    elif not matrix_ok:
        failed_at = "matrix"
    elif not review_ok:
        failed_at = "review"
    else:
        failed_at = "none"

    return {
        "ok": overall_ok,
        "failed_at": failed_at,
        "profile": {
            "ok": profile_ok,
            "science_problem_attribute": spa,
        },
        "sync": {
            "ok": sync_ok,
            "exists_ok": exists_ok,
            "fresh_ok": fresh_ok,
            "semantic_ok": semantic_ok,
            **sync_status,
        },
        "citation": {
            "ok": citation_ok,
            "verification_status": idx.get("metadata", {}).get("verification_status"),
            "stats": run_stats,
            "manual_review_count": len(manual_queue),
        },
        "literature": {
            "ok": literature_ok,
            "total_count": total_count,
            "min_total": min_total,
            "recent_5yr_count": recent_count,
            "cn_journal_count": cn_count,
            "p1_citation_count": p1_cite_count,
            "warnings": literature_warnings,
        },
        "matrix": matrix,
        "review": {
            "ok": review_ok,
            "overall_grade": review.get("overall_grade"),
            "pass_status": review.get("pass_status"),
            "c_count": review.get("c_count"),
            "d_count": review.get("d_count"),
            "page_estimate": review.get("page_estimate"),
            "page_limit": review.get("page_limit"),
        },
    }


def _auto_fix_project(root: Path) -> dict[str, Any]:
    fixed: list[str] = []

    for d in ["sections", "output", "data", ".state", "snapshots"]:
        p = root / d
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            fixed.append(f"mkdir:{d}")

    profile_path = root / "proposal_profile.json"
    profile = load_json(profile_path, DEFAULT_PROFILE)
    if not isinstance(profile, dict):
        profile = DEFAULT_PROFILE
        fixed.append("reset:proposal_profile.json")
    save_json(profile_path, deep_merge(DEFAULT_PROFILE, profile))

    lit_path = root / "data/literature_index.json"
    lit = load_json(lit_path, {"metadata": {"verification_status": "pending"}, "entries": []})
    if isinstance(lit, list):
        lit = {"metadata": {"verification_status": "pending"}, "entries": lit}
        fixed.append("normalize:data/literature_index.json:list->dict")
    elif not isinstance(lit, dict):
        lit = {"metadata": {"verification_status": "pending"}, "entries": []}
        fixed.append("reset:data/literature_index.json")
    lit.setdefault("metadata", {})
    if not isinstance(lit.get("entries"), list):
        lit["entries"] = []
        fixed.append("normalize:data/literature_index.json:entries")
    save_json(lit_path, lit)

    cm_path = root / "data/consistency_map.json"
    cm = consistency_mapper.load_map(cm_path)
    save_json(cm_path, cm)

    ps_path = root / "project_state.json"
    ps = load_json(ps_path, {"phase": "phase0", "gate": "init", "updated_at": utc_now()})
    if not isinstance(ps, dict):
        ps = {"phase": "phase0", "gate": "init", "updated_at": utc_now()}
        fixed.append("reset:project_state.json")
    ps.setdefault("skill", "nsfc-proposal")
    ps.setdefault("phase", "phase0")
    ps.setdefault("gate", "init")
    ps["updated_at"] = utc_now()
    save_json(ps_path, ps)

    hist_path = root / "history_log.json"
    hist = load_json(hist_path, {"events": []})
    if not isinstance(hist, dict):
        hist = {"events": []}
        fixed.append("reset:history_log.json")
    if not isinstance(hist.get("events"), list):
        hist["events"] = []
        fixed.append("normalize:history_log.json:events")
    save_json(hist_path, hist)

    context_path = root / "context_memory.md"
    if not context_path.exists():
        context_path.write_text("# Context Memory\n\n", encoding="utf-8")
        fixed.append("create:context_memory.md")

    for rel, content in AUTO_FIX_STUBS.items():
        target = root / rel
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            fixed.append(f"create:{rel}")

    append_history(root, "auto_fix", {"fixed": fixed})
    append_context(root, "Auto-fix applied.")
    return {"fixed_count": len(fixed), "fixed": fixed}


def _normalize_section_name(section: str) -> str:
    s = section.strip()
    if s in SECTION_ALIASES:
        return SECTION_ALIASES[s]
    if s.endswith(".md"):
        return s
    return s + ".md"


def _section_file(root: Path, section: str) -> Path:
    return root / "sections" / _normalize_section_name(section)


def _section_key_facts(text: str, max_facts: int = 10, max_chars: int = 80) -> list[str]:
    if not text.strip():
        return []
    parts = re.split(r"[\n。！？!?；;]", text)
    facts = []
    for raw in parts:
        x = raw.strip()
        if not x:
            continue
        if len(x) > max_chars:
            x = x[: max_chars - 3] + "..."
        facts.append(x)
        if len(facts) >= max_facts:
            break
    return facts


def _compact_consistency_for_section(cm: dict[str, Any], section_stem: str) -> dict[str, Any]:
    q = consistency_mapper.query_by_section(cm, section_stem)
    out: dict[str, Any] = {}
    for k, items in q.items():
        out[k] = [{"id": i.get("id"), "statement": i.get("statement", "")} for i in items]
    return out


def _section_excerpt(text: str, limit_chars: int = 1200) -> str:
    if len(text) <= limit_chars:
        return text
    half = limit_chars // 2
    return text[:half] + "\n...\n" + text[-half:]


# 科学问题属性 → 论证关键词映射（SPA-WARN 规则，WARN 级不硬卡）
_SPA_KEYWORD_MAP: dict[str, list[str]] = {
    "鼓励探索、突出原创": ["原创", "首次", "新发现", "无先例"],
    "聚焦前沿、独辟蹊径": ["前沿", "空白", "独特视角", "尚无"],
    "需求牵引、突破瓶颈": ["瓶颈", "制约", "急需", "突破"],
    "共性导向、交叉融通": ["共性", "交叉", "融合", "跨学科"],
}


def _check_spa_justification(spa: str | None, p1_text: str) -> dict[str, Any]:
    """检查P1正文是否对所选科学问题属性做了论证（WARN级，不硬卡）。"""
    if not spa or spa not in _SPA_KEYWORD_MAP:
        return {"warn": False, "spa": spa, "found_keywords": []}
    keywords = _SPA_KEYWORD_MAP[spa]
    found = [kw for kw in keywords if kw in p1_text]
    warn = len(found) == 0
    return {
        "warn": warn,
        "spa": spa,
        "keywords_checked": keywords,
        "found_keywords": found,
        "message": (
            f'[SPA-WARN] 科学问题属性"{spa}"未见正文论证，建议在P1科学问题凝练段补充说明原创性/瓶颈/前沿/交叉维度的具体体现。'
            if warn else ""
        ),
    }


def build_write_cycle(root: Path, section: str, token_budget: int | None = None) -> dict[str, Any]:
    profile = load_json(root / "proposal_profile.json", DEFAULT_PROFILE)
    cm = consistency_mapper.load_map(root / "data/consistency_map.json")
    lit = load_json(root / "data/literature_index.json", {"metadata": {}, "entries": []})

    sec_path = _section_file(root, section)
    section_text = sec_path.read_text(encoding="utf-8") if sec_path.exists() else ""

    related_entities = _compact_consistency_for_section(cm, sec_path.stem)
    token_budget = token_budget or 4000

    literature_ctx = []
    if sec_path.stem.startswith("P1"):
        for e in lit.get("entries", [])[:20]:
            literature_ctx.append(
                {
                    "ref_number": e.get("ref_number"),
                    "title": e.get("title"),
                    "year": e.get("year"),
                    "role": e.get("role"),
                    "verified": e.get("verified"),
                }
            )

    return {
        "section": sec_path.name,
        "token_budget": token_budget,
        "token_plan": {
            "section_summary": int(token_budget * 0.4),
            "consistency": int(token_budget * 0.2),
            "literature": int(token_budget * 0.25) if sec_path.stem.startswith("P1") else 0,
            "system": token_budget
            - int(token_budget * 0.4)
            - int(token_budget * 0.2)
            - (int(token_budget * 0.25) if sec_path.stem.startswith("P1") else 0),
        },
        "section_excerpt": _section_excerpt(section_text),
        "section_key_facts": _section_key_facts(section_text),
        "related_consistency": related_entities,
        "literature_context": literature_ctx,
        "profile": {
            "mode": profile.get("mode"),
            "page_limit": profile.get("page_limit"),
            "word_targets": profile.get("word_targets", {}),
        },
        # SPA-WARN：仅在撰写P1时检查科学问题属性论证（WARN级，不硬卡）
        "spa_justification_check": (
            _check_spa_justification(profile.get("science_problem_attribute"), section_text)
            if sec_path.stem.startswith("P1")
            else None
        ),
    }


def load_view(root: Path, section: str | None, minimal: bool, global_load: bool) -> dict[str, Any]:
    state = load_json(root / "project_state.json", {})
    out: dict[str, Any] = {"state": state}

    if section:
        path = _section_file(root, section)
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        out["section_name"] = path.name
        if minimal:
            cm = consistency_mapper.load_map(root / "data/consistency_map.json")
            out["section_key_facts"] = _section_key_facts(text)
            out["related_consistency"] = _compact_consistency_for_section(cm, path.stem)
        else:
            out["section"] = text

    if global_load:
        out["consistency"] = consistency_mapper.load_map(root / "data/consistency_map.json")
        out["literature_meta"] = load_json(root / "data/literature_index.json", {"metadata": {}}).get("metadata", {})
        out["profile"] = load_json(root / "proposal_profile.json", DEFAULT_PROFILE)

    if minimal:
        out["mode"] = "minimal"

    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--force-shared", action="store_true",
                        help="跳过 PROJECT_ROOT 归属冲突检查(该目录已被别的技能占用时的逃生口)")

    p_profile = sub.add_parser("profile")
    p_profile.add_argument("--json", required=True)

    p_load = sub.add_parser("load")
    p_load.add_argument("--section")
    p_load.add_argument("--minimal", action="store_true")
    p_load.add_argument("--global", dest="global_load", action="store_true")

    p_update = sub.add_parser("update")
    p_update.add_argument("--json", required=True)

    p_snap = sub.add_parser("snapshot")
    p_snap.add_argument("--name", required=True)

    p_roll = sub.add_parser("rollback")
    p_roll.add_argument("--snapshot", required=True)

    p_wc = sub.add_parser("word-count")
    p_wc.add_argument("--sections-dir", default="sections")

    p_pe = sub.add_parser("page-estimate")
    p_pe.add_argument("--sections-dir", default="sections")

    p_write = sub.add_parser("write-cycle")
    p_write.add_argument("--section", required=True)
    p_write.add_argument("--token-budget", type=int, default=4000)

    sub.add_parser("sync-all")

    p_review = sub.add_parser("self-review")
    p_review.add_argument("--sections-dir", default="sections")
    p_review.add_argument("--output", default="data/diagnosis_report.json")

    p_gate = sub.add_parser("gate-check")
    p_gate.add_argument("--sections-dir", default="sections")
    p_gate.add_argument("--index", default="data/literature_index.json")
    p_gate.add_argument("--p1", default="sections/P1_立项依据.md")
    p_gate.add_argument("--ref", default="sections/REF_参考文献.md")
    p_gate.add_argument("--mcp-cache", default="data/mcp_literature_cache.json")
    p_gate.add_argument("--mcp-ttl-days", type=int, default=30)
    p_gate.add_argument("--offline", action="store_true")
    p_gate.add_argument("--require-mcp", action="store_true")

    p_sync = sub.choices["sync-all"]
    p_sync.add_argument("--auto-fix", action="store_true")

    args = parser.parse_args()
    root = Path(args.root).resolve()

    if args.cmd == "init":
        init_project(root, force_shared=bool(getattr(args, "force_shared", False)))
        print(json.dumps({"ok": True, "root": str(root)}, ensure_ascii=False))
        return 0

    if args.cmd == "profile":
        patch = json.loads(args.json)
        current = load_json(root / "proposal_profile.json", DEFAULT_PROFILE)
        merged = deep_merge(current, patch)
        save_json(root / "proposal_profile.json", merged)
        append_history(root, "profile_update", patch)
        print(json.dumps({"ok": True}, ensure_ascii=False))
        return 0

    if args.cmd == "load":
        print(json.dumps(load_view(root, args.section, args.minimal, args.global_load), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "update":
        patch = json.loads(args.json)
        state = load_json(root / "project_state.json", {})
        state = deep_merge(state, patch)
        state["updated_at"] = utc_now()
        save_json(root / "project_state.json", state)
        append_history(root, "state_update", patch)
        print(json.dumps({"ok": True}, ensure_ascii=False))
        return 0

    if args.cmd == "snapshot":
        snap = do_snapshot(root, args.name)
        print(json.dumps({"ok": True, "snapshot": str(snap)}, ensure_ascii=False))
        return 0

    if args.cmd == "rollback":
        ok = rollback(root, Path(args.snapshot))
        print(json.dumps({"ok": ok}, ensure_ascii=False))
        return 0 if ok else 2

    if args.cmd == "word-count":
        data = word_counter.count_all(root / args.sections_dir)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "page-estimate":
        data = word_counter.count_all(root / args.sections_dir)
        print(word_counter.estimate_pages(data.get("__total__", 0)))
        return 0

    if args.cmd == "write-cycle":
        payload = build_write_cycle(root, args.section, token_budget=args.token_budget)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "sync-all":
        if getattr(args, "auto_fix", False):
            fix = _auto_fix_project(root)
        else:
            fix = {"fixed_count": 0, "fixed": []}
        status = sync_all(root)
        exists_ok = all(status["exists"].values())
        fresh_ok = all(status["fresh"].values()) if status["fresh"] else True

        semantic = status["semantic"]
        semantic_ok = _sync_semantic_ok(semantic)

        ok = exists_ok and fresh_ok and semantic_ok
        print(json.dumps({"ok": ok, **status, "semantic_ok": semantic_ok, "auto_fix": fix}, ensure_ascii=False, indent=2))
        return 0 if ok else 2

    if args.cmd == "gate-check":
        report = gate_check(
            root=root,
            sections_dir=args.sections_dir,
            index_path=args.index,
            p1_path=args.p1,
            ref_path=args.ref,
            mcp_cache_path=args.mcp_cache,
            mcp_ttl_days=args.mcp_ttl_days,
            offline=bool(args.offline),
            require_mcp=bool(args.require_mcp),
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report.get("ok") else 2

    if args.cmd == "self-review":
        profile = load_json(root / "proposal_profile.json", DEFAULT_PROFILE)
        report = diagnosis_engine.full_review(
            sections_dir=root / args.sections_dir,
            consistency_path=root / "data/consistency_map.json",
            index_path=root / "data/literature_index.json",
            p1_path=root / "sections/P1_立项依据.md",
            ref_path=root / "sections/REF_参考文献.md",
            page_limit=int(profile.get("page_limit", 30)),
        )
        out = root / args.output
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        append_history(root, "self_review", {"overall_grade": report["overall_grade"]})
        print(json.dumps({"ok": True, "output": str(out), "overall": report["overall_grade"]}, ensure_ascii=False))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
