#!/usr/bin/env python3
"""prewrite_gate.py — general-sci-writing 统一「开写前置闸门」。

在 Phase 8 撰写某个 section 之前运行，把原本散落在提示词里的机械合规自检
升级为脚本级硬拦截（exit≠0 阻断开写）。本脚本只做"机械可判定"的检查，
不替代委托盲检（语义判断仍由 academic-blind-reviewer 负责）。

CLI：python3 prewrite_gate.py --section <section_id> --root <project_root>

硬检查（FAIL → exit 1）：
1. 上一节完成：storyline 顺序里本节的上一节，其 writing_progress 最新状态为 done/completed
2. 故事线就位：storyline.json 存在且本 section 有对应条目
3. 占位符清零：上一节 manuscript 文件无 CITE_PENDING/DATA_PENDING/【待 残留
4. 缩略词一致：subprocess 调 abbreviation_consistency.py（复用，不重写）
5. 上一节盲检通过：<root>/.review_pass/<上一节>.json 存在且 passed:true
   （由 delegate_review.py verify --section <上一节> 落盘）；缺失 → 硬拦

仅信息（不阻断）：
- 素材就位：subprocess 探查 figure_analysis_gate.py 并记录，硬判定统一交给 step0b
  的 figure_analysis_gate.py --section（exit1 阻断），避免同一 gate 双跑。

输出：stdout 一行 JSON {"ok":bool,"section":...,"checks":[...],"warnings":[...]}
任一硬检查失败额外打印 PREWRITE_GATE: FAIL + 原因 并 exit 1。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

PLACEHOLDER_TOKENS = ("CITE_PENDING", "DATA_PENDING", "【待")
# 残留未映射新引用键：[@new:slug]（主会话并表后进 .newref_map.json；未在其中 = 未映射）
NEW_KEY_RE = re.compile(r"\[@(new:[A-Za-z0-9:_\-]+)\]")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 按 section 角色的软文献门：只有 Intro / Discussion 设低地板，其余（Methods /
# Results / 其它）一律不设篇数门（研究论文引用数学科差异大，硬门只在 Intro /
# Discussion 兜底）。(hard_floor, soft_target)：hard 不达→failures 硬拦；
# soft 不达→warnings 提醒。
ROLE_LIT_FLOORS = {
    "introduction": (6, 10),
    "discussion": (8, 12),
}

# 复用 state_manager 的矩阵解析（同技能目录，非受保护文件）；导入失败则降级跳过。
sys.path.insert(0, SCRIPT_DIR)
try:
    from state_manager import load_literature_matrix, sanitize_section_id
except Exception:  # pragma: no cover - 降级路径
    load_literature_matrix = None
    sanitize_section_id = None


def infer_section_role(section_dict, section_id):
    """判定 section 角色：优先读显式 role 字段，否则从 id 关键词推断。

    gsw storyline 无强制 role 字段（模板只有 id/type），故 id 兜底：含 intro→
    introduction、含 discuss→discussion，其余（含 results/methods/conclusion）→
    other（不设文献门）。gsw 融合 Results+Discussion，results_* 归 results 无门。
    """
    raw = ""
    if isinstance(section_dict, dict):
        raw = str(section_dict.get("role") or "").strip().lower()
    if not raw:
        raw = str(section_id or "").lower()
    # results_/methods_ 前置判定：gsw 融合 Results+Discussion，results_* 一律归 other 无门，
    # 即使 id 含 intro/discuss 子串（如 results_reintroduction / results_discussion），
    # 避免结果节被误套 Intro/Discussion 硬地板而 false block（与本函数 docstring 一致）。
    if raw.startswith(("results", "result_", "method", "conclusion")):
        return "other"
    if "intro" in raw:
        return "introduction"
    if "discuss" in raw:
        return "discussion"
    return "other"


def load_storyline_sections(root):
    """返回 storyline.json 的 sections 列表（dict 元素），无则 []。"""
    payload = _load_json(os.path.join(root, "storyline.json"))
    if not isinstance(payload, dict):
        return []
    sections = payload.get("sections")
    return [s for s in sections if isinstance(s, dict)] if isinstance(sections, list) else []


def count_section_literature(root, section):
    """统计矩阵里归属该 section 的文献条数（合并 literature_matrix.json + storyline 内嵌）。"""
    if load_literature_matrix is None:
        return None
    try:
        matrix, _ = load_literature_matrix(
            matrix_file=os.path.join(root, "literature_matrix.json"),
            storyline_file=os.path.join(root, "storyline.json"),
        )
    except Exception:
        return None
    key = sanitize_section_id(str(section)) if sanitize_section_id else str(section)
    refs = matrix.get(key)
    return len(refs) if isinstance(refs, list) else 0


def _load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def load_storyline_order(root):
    """返回 storyline.json 的 section id 顺序列表，无则 []。"""
    payload = _load_json(os.path.join(root, "storyline.json"))
    if not isinstance(payload, dict):
        return []
    sections = payload.get("sections")
    order = []
    if isinstance(sections, list):
        for item in sections:
            if isinstance(item, dict):
                sid = item.get("id") or item.get("section_id")
                if sid:
                    order.append(str(sid))
    return order


def section_status_from_progress(root, section):
    """从 writing_progress.json 的 update_history 取该 section 最新 status。"""
    payload = _load_json(os.path.join(root, "writing_progress.json"))
    if not isinstance(payload, dict):
        return None
    history = payload.get("update_history")
    last = None
    if isinstance(history, list):
        for entry in history:
            if isinstance(entry, dict) and str(entry.get("section")) == str(section):
                last = entry.get("status")
    # 兜底：last_section 直读
    if last is None and str(payload.get("last_section")) == str(section):
        last = payload.get("status")
    return last


def manuscript_files_for_section(root, section):
    """猜测本 section 对应的 manuscript 文件（用于占位符扫描）。

    gsw manuscript 文件名不强绑 section_id，故扫所有 manuscripts/*.md 中
    内容含该 section_id 的文件；找不到则返回全部（保守扫描）。
    """
    md_dir = os.path.join(root, "manuscripts")
    if not os.path.isdir(md_dir):
        return []
    files = [os.path.join(md_dir, f) for f in os.listdir(md_dir)
             if f.endswith(".md") and f != "Full_Manuscript.md"
             and not f.startswith("Draft_Round")]
    return sorted(files)


def _load_newref_map(root):
    m = _load_json(os.path.join(root, ".newref_map.json"))
    return m if isinstance(m, dict) else {}


def scan_placeholders(files):
    hits = []
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            continue
        for token in PLACEHOLDER_TOKENS:
            if token in content:
                hits.append((os.path.basename(fp), token))
    return hits


def run_subprocess_gate(script_name, extra_args, root):
    """复用既有 gate 脚本（subprocess），返回 (ok, output)。"""
    script_path = os.path.join(SCRIPT_DIR, script_name)
    if not os.path.exists(script_path):
        return None, f"{script_name} not found (skip)"
    cmd = [sys.executable, script_path] + extra_args + ["--root", root]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    except (subprocess.SubprocessError, OSError) as exc:
        return False, f"{script_name} run error: {exc}"
    out = (proc.stdout or "").strip() + (("\n" + proc.stderr.strip()) if proc.stderr.strip() else "")
    return proc.returncode == 0, out


def main():
    parser = argparse.ArgumentParser(
        description="general-sci-writing 开写前置闸门：上一节完成/故事线/素材/占位符/缩略词硬检查。"
    )
    parser.add_argument("--section", required=True, help="storyline section_id，例如 results_3.2")
    parser.add_argument("--root", required=True, help="project root")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    section = args.section
    checks = []
    warnings = []
    failures = []

    if not os.path.isdir(root):
        print(f"PREWRITE_GATE: FAIL root not a directory: {root}")
        print(json.dumps({"ok": False, "section": section, "checks": [],
                          "warnings": []}, ensure_ascii=False))
        return 1

    # ---- check 2 (先判故事线，因 check1 依赖其顺序) ----
    order = load_storyline_order(root)
    if not order:
        failures.append("storyline.json missing or has no sections")
        checks.append({"name": "storyline", "ok": False})
    elif section not in order:
        failures.append(f"section {section!r} not found in storyline.json")
        checks.append({"name": "storyline", "ok": False})
    else:
        checks.append({"name": "storyline", "ok": True})

    # ---- check 1: 上一节完成 ----
    if order and section in order:
        idx = order.index(section)
        if idx == 0:
            checks.append({"name": "prev_section_done", "ok": True, "note": "first section, skip"})
        else:
            prev = order[idx - 1]
            status = section_status_from_progress(root, prev)
            done = str(status).lower() in ("done", "completed", "finalized")
            if done:
                checks.append({"name": "prev_section_done", "ok": True, "prev": prev})
            else:
                failures.append(f"previous section {prev!r} status={status!r} (need done/completed)")
                checks.append({"name": "prev_section_done", "ok": False, "prev": prev})
    else:
        checks.append({"name": "prev_section_done", "ok": False, "note": "no storyline order"})

    # ---- check (硬): 上一节盲检通过并落盘 ----
    if order and section in order and order.index(section) > 0:
        prev = order[order.index(section) - 1]
        pass_path = os.path.join(root, ".review_pass", f"{prev}.json")
        marker = _load_json(pass_path)
        if isinstance(marker, dict) and marker.get("passed") is True:
            checks.append({"name": "blind_review", "ok": True, "prev": prev})
        else:
            failures.append(
                f"previous section {prev!r} blind review not passed or marker missing; "
                f"run: delegate_review.py verify --section {prev}")
            checks.append({"name": "blind_review", "ok": False, "prev": prev})
    else:
        checks.append({"name": "blind_review", "ok": True, "note": "first section, N/A"})

    # ---- check 3: 素材就位（figure_analysis，仅信息，硬判定交给 step0b figure_analysis_gate.py） ----
    # 只跑一次探查并记录，绝不阻断——避免与 step0b 的硬门 figure_analysis_gate 双跑同一 gate。
    fig_ok, fig_out = run_subprocess_gate("figure_analysis_gate.py", ["--section", section], root)
    if fig_ok is None:
        warnings.append(f"figure_analysis_gate.py unavailable: {fig_out}")
        checks.append({"name": "figure_analysis", "ok": None, "note": fig_out})
    elif fig_ok:
        checks.append({"name": "figure_analysis", "ok": True})
    else:
        warnings.append(f"figure_analysis not ready (info only, enforced by step0b): {fig_out}")
        checks.append({"name": "figure_analysis", "ok": False, "info_only": True, "detail": fig_out})

    # ---- check 4: 占位符清零（上一节文件） ----
    placeholder_hits = scan_placeholders(manuscript_files_for_section(root, section))
    if placeholder_hits:
        detail = ", ".join(f"{fn}:{tok}" for fn, tok in placeholder_hits)
        failures.append(f"unresolved placeholders: {detail}")
        checks.append({"name": "placeholders", "ok": False, "detail": detail})
    else:
        checks.append({"name": "placeholders", "ok": True})

    # ---- check 5: 缩略词一致（subprocess abbreviation_consistency.py，复用） ----
    abbr_ok, abbr_out = run_subprocess_gate("abbreviation_consistency.py", [], root)
    if abbr_ok is None:
        warnings.append(f"abbreviation_consistency.py unavailable: {abbr_out}")
        checks.append({"name": "abbreviation", "ok": None, "note": abbr_out})
    elif abbr_ok:
        checks.append({"name": "abbreviation", "ok": True})
    else:
        failures.append(f"abbreviation_consistency failed: {abbr_out}")
        checks.append({"name": "abbreviation", "ok": False, "detail": abbr_out})

    # ---- check 6: 按 section 角色的软文献门（Intro/Discussion 低地板，余不设门） ----
    if order and section in order:
        sections = load_storyline_sections(root)
        sec_dict = next((s for s in sections
                         if str(s.get("id") or s.get("section_id") or "") == str(section)), None)
        role = infer_section_role(sec_dict, section)
        floor = ROLE_LIT_FLOORS.get(role)
        n = count_section_literature(root, section)
        if n is None:
            warnings.append("literature matrix unreadable (state_manager unavailable), skip literature floor")
            checks.append({"name": "literature_role", "ok": None, "role": role})
        elif floor is None:
            checks.append({"name": "literature_role", "ok": True, "role": role, "count": n, "note": "no floor"})
        else:
            hard, soft = floor
            if n < hard:
                failures.append(f"{role} literature count {n} < hard floor {hard}")
                checks.append({"name": "literature_role", "ok": False, "role": role, "count": n, "hard": hard})
            else:
                checks.append({"name": "literature_role", "ok": True, "role": role, "count": n, "hard": hard})
                if n < soft:
                    warnings.append(f"{role} literature count {n} < soft target {soft} (info only)")

    # ---- check（§4.1-A 新增）：上一节 new_refs 已并表核验 + 全稿无残留未映射新键 ----
    # 撰写子代理写 [@new:slug]，主会话并表后把 slug→已并表 id 落 .newref_map.json。忘并表/
    # 忘核验 → exit≠0（硬要求10 节边界机械兜底）。prev 按 storyline 顺序取（gsw 无 chapter.sub
    # 算术）；gsw manuscript 文件名不绑 section_id，故 A2 残留扫描对全部 manuscripts/*.md 做
    # （"任何残留未映射新键 = 有节忘并表"，保守 fail-closed，不漏）。
    if order and section in order and order.index(section) > 0:
        prev = order[order.index(section) - 1]
        keymap = _load_newref_map(root)
        lit = _load_json(os.path.join(root, "literature_index.json"))
        verified_ids = ({str(e.get("id")) for e in lit
                         if isinstance(e, dict) and e.get("id") and e.get("verified", True)}
                        if isinstance(lit, list) else set())
        all_md = manuscript_files_for_section(root, section)
        # A2 先扫全稿残留未映射 [@new: 键（用于判定 A1 缺失是否致命）。
        residual = []
        for fp in all_md:
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    residual += [k for k in NEW_KEY_RE.findall(f.read()) if k not in keymap]
            except OSError:
                continue
        # A1：上一节 .write_return 的 new_refs 每条都并表到 verified 文献。
        #  - 坏 JSON → 账本损坏，一律 FAIL。
        #  - 文件缺失 + 全稿确有未映射新键 → 无从审计 → FAIL；否则（白名单节主会话就地写、
        #    天然无 return）合法缺失，放行。
        ret_path = os.path.join(root, f".write_return_{prev}.json")
        unmerged, ret_broken = [], False
        if os.path.exists(ret_path):
            ret = _load_json(ret_path)
            if ret is None:
                ret_broken = True
            elif isinstance(ret, dict):
                for nr in (ret.get("new_refs") or []):
                    key = nr.get("key", "")
                    resolved = keymap.get(key)
                    if not resolved or str(resolved) not in verified_ids:
                        unmerged.append(key)
        elif residual:
            ret_broken = True
        if ret_broken:
            failures.append(
                f"上一节 new_refs 未并表/未核验: {prev} 的 .write_return 缺失或损坏，无法核验并表")
            checks.append({"name": "prev_new_refs_merged", "ok": False, "prev": prev})
        elif unmerged:
            for k in unmerged:
                failures.append(f"上一节 new_refs 未并表/未核验: {k}")
            checks.append({"name": "prev_new_refs_merged", "ok": False, "prev": prev})
        else:
            checks.append({"name": "prev_new_refs_merged", "ok": True, "prev": prev})
        if residual:
            for k in sorted(set(residual)):
                failures.append(f"上一节残留未并表新键: {k}")
            checks.append({"name": "prev_residual_new_key", "ok": False})
        else:
            checks.append({"name": "prev_residual_new_key", "ok": True})
    else:
        checks.append({"name": "prev_new_refs_merged", "ok": True, "note": "first section; N/A"})

    ok = not failures
    print(json.dumps({"ok": ok, "section": section, "checks": checks,
                      "warnings": warnings}, ensure_ascii=False))
    if not ok:
        for reason in failures:
            print(f"PREWRITE_GATE: FAIL {reason}")
        return 1
    print("PREWRITE_GATE: PASS 仅覆盖流程前置(上一节完成/盲检标记/故事线/素材就位/"
          "占位清零/缩略词一致)，不代表本节内容有科学价值或够顶刊——那靠盲检与作者判断。",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
