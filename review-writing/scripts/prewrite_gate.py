#!/usr/bin/env python3
"""prewrite_gate.py — review-writing 统一「开写前置闸门」。

在 Phase 3 撰写某个 section 之前运行（Per-Section Cycle 最前），把机械合规
自检升级为脚本级硬拦截（exit≠0 阻断）。只做机械可判定检查，不替代委托盲检。

CLI：python3 prewrite_gate.py --section <section_id> --root <project_root>

硬检查（FAIL → exit 1）：
1. 上一节完成：outline.md 顺序里本节的上一节 ∈ state.json.completed_sections
2. 大纲就位：outline.md 存在且本 section 有对应标题条目
3. 素材就位：synthesis_matrix.json（本 section 文献矩阵非空）
4. 占位符清零：上一节 drafts 文件无 CITE_PENDING/DATA_PENDING/【待 残留
5. 上一节盲检通过：<root>/.review_pass/<上一节>.json 存在且 passed:true
   （由 delegate_review.py verify --section <上一节> 落盘）；缺失 → 硬拦

逃生口（--allow-manual-review "<理由>"，门禁默认行为不变）：
   盲检子代理不可用（平台无 academic-blind-reviewer / 子代理反复失败）时，才用
   此显式人工放行。仅放行「上一节盲检」这一项，其余硬检查照常。放行必留痕：写
   <root>/.review_pass/<上一节>.json（manual:true+reason+timestamp）并追加
   <root>/.review_pass/MANUAL_REVIEW_AUDIT.log；不是静默跳过。理由为空即拒绝放行。

降级 warning（不阻断）：
- 缩略词一致：review 无独立 abbreviation 脚本 → skip 并注明

输出：stdout 一行 JSON {"ok":bool,"section":...,"checks":[...],"warnings":[...]}
任一硬检查失败额外打印 PREWRITE_GATE: FAIL + 原因 并 exit 1。
通过时打印 PREWRITE_GATE: PASS（附一句：PASS 仅覆盖形式层，语义正确性未自动核验）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

PLACEHOLDER_TOKENS = ("CITE_PENDING", "DATA_PENDING", "【待")

# 撰写子代理认键：[@key]（key=gid 或 new:slug）。翻号（state_manager resolve-keys）后草稿里
# 不应再有任何 [@key]——残留即"忘翻号/忘并表"。§4.1-A 节边界机械兜底。
ATKEY_RE = re.compile(r"\[@([A-Za-z0-9:_\-]+)\]")


def _paper_identity(item):
    """与 state_manager._paper_identity 同口径：doi→pmid→title 归一，供 new_refs 并表核验。"""
    doi = str(item.get("doi", "")).strip().lower()
    pmid = str(item.get("pmid", "")).strip()
    title = str(item.get("title", "")).strip().lower()
    if doi:
        return f"doi:{doi}"
    if pmid:
        return f"pmid:{pmid}"
    if title:
        return f"title:{title}"
    return None


def record_manual_review(root, section, reason):
    """逃生口留痕：盲检子代理不可用时对上一节盲检做显式人工放行。

    写 <root>/.review_pass/<section>.json（manual:true）+ 追加审计日志，
    使后续 prewrite_gate 天然通过且全程可追溯。绝非静默跳过。
    """
    pass_dir = os.path.join(root, ".review_pass")
    os.makedirs(pass_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    marker = {"passed": True, "manual": True, "section": section,
              "reason": reason, "timestamp": ts}
    with open(os.path.join(pass_dir, f"{section}.json"), "w", encoding="utf-8") as f:
        json.dump(marker, f, ensure_ascii=False, indent=2)
    with open(os.path.join(pass_dir, "MANUAL_REVIEW_AUDIT.log"), "a", encoding="utf-8") as f:
        f.write(f"{ts}\tsection={section}\tmanual_review_override\treason={reason}\n")


def _load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def load_outline_order(root):
    """从 outline.md 解析「可写小节」id 顺序。

    只纳入真正可写的小节（带子编号，如 1.1 / 2.3）。其余标题一律不计入顺序链：
    - 章级标题（纯 `1`/`2`，来自 `### 1. Introduction`）——否则第一个小节 1.1
      的「上一节」会被误判成章标题 `1`，而 `1` 永不进 completed_sections → 1.1 卡死；
    - 配置段标题（`## Parameters`/`## Outline (...)` 等模板里的非小节标题）——
      否则它们会混进顺序链，同样污染第一个可写小节的「上一节」判定。
    这样 outline 模板下 order = ['1.1','1.2','2.1',...]，1.1 即第一个、idx==0 放行。
    正则兼容三级 X.Y 与四级 X.Y.Z（`2.1.1` 不被截成 `2.1`）。层级由 section_id 段数
    推得：level = section_id.count('.')+2（`2.1`=三级、`2.1.1`=四级）。
    """
    path = os.path.join(root, "outline.md")
    if not os.path.exists(path):
        return []
    subsection_pattern = re.compile(r"^(\d+(?:\.\d+)+)\b")
    order = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return []
    for line in lines:
        m = re.match(r"^(##+)\s+(.*)$", line)
        if not m:
            continue
        title = m.group(2).strip()
        if not title:
            continue
        sub_match = subsection_pattern.match(title)
        if sub_match:
            order.append(sub_match.group(1))
    return order


def completed_sections(root):
    payload = _load_json(os.path.join(root, "state.json"))
    if isinstance(payload, dict):
        done = payload.get("completed_sections")
        if isinstance(done, list):
            return [str(s) for s in done]
    return []


def _section_matches(section, section_list):
    if not isinstance(section_list, list):
        return False
    target = str(section).strip()
    for s in section_list:
        if str(s).strip() == target:
            return True
    return False


def matrix_rows_for_section(root, section):
    """统计 synthesis_matrix.json 中归属本 section 的条目数。"""
    for rel in ("data/synthesis_matrix.json", "data/literature_matrix.json"):
        payload = _load_json(os.path.join(root, rel))
        rows = payload if isinstance(payload, list) else None
        if rows is None and isinstance(payload, dict):
            for key in ("synthesis_matrix", "literature_matrix", "matrix", "rows"):
                if isinstance(payload.get(key), list):
                    rows = payload[key]
                    break
        if not rows:
            continue
        count = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            if (_section_matches(section, row.get("related_sections"))
                    or _section_matches(section, row.get("sections"))
                    or str(row.get("section_id", "")).strip() == str(section).strip()
                    or str(row.get("section", "")).strip() == str(section).strip()):
                count += 1
        if count > 0:
            return count
    return 0


def draft_files(root):
    d = os.path.join(root, "drafts")
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".md"))


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


def main():
    parser = argparse.ArgumentParser(
        description="review-writing 开写前置闸门：上一节完成/大纲/文献矩阵/占位符硬检查。"
    )
    parser.add_argument("--section", required=True, help="section id，例如 2.1")
    parser.add_argument("--root", required=True, help="project root")
    parser.add_argument(
        "--allow-manual-review", default=None, metavar="REASON",
        help="逃生口：盲检子代理不可用时，对上一节盲检做显式人工放行（附非空理由）。"
             "仅放行盲检项，其余硬检查照常；会写 <root>/.review_pass/<prev>.json(manual) "
             "并追加 MANUAL_REVIEW_AUDIT.log 留痕。不传则门禁默认行为不变（缺盲检标记即硬拦）。")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    section = str(args.section)
    checks = []
    warnings = []
    failures = []

    if not os.path.isdir(root):
        print(f"PREWRITE_GATE: FAIL root not a directory: {root}")
        print(json.dumps({"ok": False, "section": section, "checks": [],
                          "warnings": []}, ensure_ascii=False))
        return 1

    # ---- check 2: 大纲就位 ----
    order = load_outline_order(root)
    if not order:
        failures.append("outline.md missing or has no section headings")
        checks.append({"name": "outline", "ok": False})
    elif section not in order:
        failures.append(f"section {section!r} not found in outline.md")
        checks.append({"name": "outline", "ok": False})
    else:
        checks.append({"name": "outline", "ok": True})

    # ---- check 1: 上一节完成 ----
    if order and section in order:
        idx = order.index(section)
        if idx == 0:
            checks.append({"name": "prev_section_done", "ok": True, "note": "first section, skip"})
        else:
            prev = order[idx - 1]
            done = prev in completed_sections(root)
            if done:
                checks.append({"name": "prev_section_done", "ok": True, "prev": prev})
            else:
                failures.append(f"previous section {prev!r} not in completed_sections")
                checks.append({"name": "prev_section_done", "ok": False, "prev": prev})
    else:
        checks.append({"name": "prev_section_done", "ok": False, "note": "no outline order"})

    # ---- check: 上一节盲检通过并落盘（硬） ----
    if order and section in order and order.index(section) > 0:
        prev = order[order.index(section) - 1]
        pass_path = os.path.join(root, ".review_pass", f"{prev}.json")
        marker = _load_json(pass_path)
        if isinstance(marker, dict) and marker.get("passed") is True:
            chk = {"name": "blind_review", "ok": True, "prev": prev}
            if marker.get("manual"):
                chk["manual"] = True
                warnings.append(
                    f"section {prev!r} 盲检为人工放行(manual override, reason={marker.get('reason', '')!r})；"
                    f"语义正确性未经独立盲检核验")
            checks.append(chk)
        elif args.allow_manual_review is not None:
            reason = (args.allow_manual_review or "").strip()
            if not reason:
                failures.append(
                    "--allow-manual-review 需附非空理由（谁放行、为何盲检子代理不可用）")
                checks.append({"name": "blind_review", "ok": False, "prev": prev})
            else:
                record_manual_review(root, prev, reason)
                warnings.append(
                    f"section {prev!r} 盲检由 --allow-manual-review 人工放行；已留痕 "
                    f".review_pass/{prev}.json + .review_pass/MANUAL_REVIEW_AUDIT.log；"
                    f"语义正确性未经独立盲检核验")
                checks.append({"name": "blind_review", "ok": True, "prev": prev, "manual": True})
        else:
            failures.append(
                f"previous section {prev!r} blind review not passed or marker missing; "
                f"run: delegate_review.py verify --section {prev}"
                f"（盲检子代理不可用时可显式人工放行：加 --allow-manual-review \"<理由>\"）")
            checks.append({"name": "blind_review", "ok": False, "prev": prev})
    else:
        checks.append({"name": "blind_review", "ok": True, "note": "first section, N/A"})

    # ---- check（§4.1-A 新增）：上一节 new_refs 已并表核验 + 全草稿无残留 [@key] ----
    # 忘并表/忘核验/忘翻号 → exit≠0。硬要求10 的节边界机械兜底，独立于其它检查照跑。
    #  A1：上一节 .write_return 的 new_refs 每条身份都能命中 verified 文献条目（0 未并表/未核验）；
    #      文件缺失+草稿无残留 [@ = 合法（白名单节主会话就地写、天然无 return）；坏 JSON=账本损坏一律 FAIL。
    #  A2：任意草稿残留 [@key] = 忘跑 resolve-keys → FAIL。
    if order and section in order and order.index(section) > 0:
        prev = order[order.index(section) - 1]
        lit = _load_json(os.path.join(root, "data", "literature_index.json"))
        verified_idents = ({_paper_identity(e) for e in lit
                            if isinstance(e, dict) and e.get("verified", True)}
                           if isinstance(lit, list) else set())
        verified_idents.discard(None)
        # A2：残留 [@key]（全草稿）
        residual = []
        for fp in draft_files(root):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    residual += [(os.path.basename(fp), k) for k in ATKEY_RE.findall(f.read())]
            except OSError:
                continue
        if residual:
            for fn, k in residual:
                failures.append(f"上一节残留未翻号新键: [@{k}] in {fn}（先跑 state_manager resolve-keys）")
            checks.append({"name": "prev_residual_new_key", "ok": False})
        else:
            checks.append({"name": "prev_residual_new_key", "ok": True})
        # A1：上一节 new_refs 并表核验
        ret_path = os.path.join(root, f".write_return_{prev}.json")
        if os.path.exists(ret_path):
            ret = _load_json(ret_path)
            if ret is None:
                failures.append(
                    f"上一节 new_refs 未并表/未核验: {prev} 的 .write_return 损坏，无法核验并表")
                checks.append({"name": "prev_new_refs_merged", "ok": False, "prev": prev})
            else:
                unmerged = [nr.get("key", "") for nr in (ret.get("new_refs") or [])
                            if _paper_identity(nr) not in verified_idents]
                if unmerged:
                    for k in unmerged:
                        failures.append(f"上一节 new_refs 未并表/未核验: {k}")
                    checks.append({"name": "prev_new_refs_merged", "ok": False, "prev": prev})
                else:
                    checks.append({"name": "prev_new_refs_merged", "ok": True, "prev": prev})
        else:
            # 缺 return + 无残留 [@ → 合法（白名单主会话就地写）；有残留已在 A2 拦。
            checks.append({"name": "prev_new_refs_merged", "ok": True, "prev": prev,
                           "note": "no .write_return (main-session-wrote); N/A"})
    else:
        checks.append({"name": "prev_new_refs_merged", "ok": True, "note": "first section; N/A"})

    # ---- check 3: 素材就位（本 section 文献矩阵按层级硬地板，只卡叶子） ----
    # 层级：level = section_id.count('.')+2（`2.1`=三级=3、`2.1.1`=四级=4）。
    # 硬地板 floor={3:6,4:3}，其余层级=1；容器父节（order 里有更深子节）放宽到 1。
    # 软目标 三级≥10 / 四级≥5，不达只进 warnings 不阻断（仅叶子节）。
    n_rows = matrix_rows_for_section(root, section)
    level = section.count(".") + 2
    is_container = any(s != section and s.startswith(section + ".") for s in order)
    floor = 1 if is_container else {3: 6, 4: 3}.get(level, 1)
    if n_rows >= floor:
        chk = {"name": "literature_matrix", "ok": True, "rows": n_rows,
               "level": level, "floor": floor}
        if is_container:
            chk["container"] = True
        soft_target = {3: 10, 4: 5}.get(level)
        if soft_target and not is_container and n_rows < soft_target:
            warnings.append(
                f"section {section!r}(level {level}) 文献 {n_rows} 条 < 软目标 {soft_target}；"
                f"建议补足以保证综述覆盖度（不阻断）")
        checks.append(chk)
    else:
        failures.append(
            f"section {section!r}(level {level}) 文献矩阵仅 {n_rows} 条 < 硬地板 {floor}")
        checks.append({"name": "literature_matrix", "ok": False, "rows": n_rows,
                       "level": level, "floor": floor})

    # ---- check 4: 占位符清零（drafts） ----
    placeholder_hits = scan_placeholders(draft_files(root))
    if placeholder_hits:
        detail = ", ".join(f"{fn}:{tok}" for fn, tok in placeholder_hits)
        failures.append(f"unresolved placeholders: {detail}")
        checks.append({"name": "placeholders", "ok": False, "detail": detail})
    else:
        checks.append({"name": "placeholders", "ok": True})

    # ---- 缩略词：review 无独立脚本 → skip ----
    checks.append({"name": "abbreviation", "ok": None, "note": "no standalone abbreviation script in review-writing; skip"})

    ok = not failures
    print(json.dumps({"ok": ok, "section": section, "checks": checks,
                      "warnings": warnings}, ensure_ascii=False))
    if not ok:
        for reason in failures:
            print(f"PREWRITE_GATE: FAIL {reason}")
        return 1
    print("PREWRITE_GATE: PASS — 仅覆盖形式层（上一节完成/大纲/文献矩阵/占位符/盲检标记存在），"
          "语义正确性未自动核验")
    return 0


if __name__ == "__main__":
    sys.exit(main())
