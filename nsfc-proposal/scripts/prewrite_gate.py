#!/usr/bin/env python3
"""prewrite_gate.py — nsfc-proposal 统一「开写前置闸门」。

在各 Phase 的 write-cycle 处、撰写某个 section 之前运行，把机械合规自检
升级为脚本级硬拦截（exit≠0 阻断）。只做机械可判定检查，不替代委托盲检。

CLI：python3 prewrite_gate.py --section <section_id> --root <project_root>

section_id ∈ {P1, P2, P3_1, P3_2, P3_3, P3_4}（固定写作顺序）。

硬检查（FAIL → exit 1）：
1. 上一节完成：固定顺序里本节的上一节，其 sections/<file>.md 存在且非空
2. 大纲/故事线就位：data/consistency_map.json 存在且非空（H/O/RC/KSQ 链路已登记）
3. 素材就位（适配）：
   - P2/P3_1：必须有 data/experimental_design.json（entries 非空）
   - P2 起：consistency_map 须含 M（methodologies）条目
4. 占位符清零：上一节 sections 文件无 CITE_PENDING/DATA_PENDING/【待 残留
5. 上一节盲检通过：<root>/.review_pass/<上一节>.json 存在且 passed:true
   （由 delegate_review.py verify --section <上一节> 落盘）；缺失 → 硬拦

降级 warning（不阻断）：
- 缩略词一致：nsfc 无独立 abbreviation 脚本 → skip 并注明

输出：stdout 一行 JSON {"ok":bool,"section":...,"checks":[...],"warnings":[...]}
任一硬检查失败额外打印 PREWRITE_GATE: FAIL + 原因 并 exit 1。
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

PLACEHOLDER_TOKENS = ("CITE_PENDING", "DATA_PENDING", "【待")

# 固定写作顺序
SECTION_ORDER = ["P1", "P2", "P3_1", "P3_2", "P3_3", "P3_4"]

# section_id -> sections/ 文件名前缀（用 glob 匹配真实文件名后缀）
SECTION_FILE_PREFIX = {
    "P1": "P1_",
    "P2": "P2_",
    "P3_1": "P3_1_",
    "P3_2": "P3_2_",
    "P3_3": "P3_3_",
    "P3_4": "P3_4_",
}


def _load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def section_file(root, section_id):
    """返回 sections/<prefix>*.md 第一个匹配文件路径，无则 None。"""
    prefix = SECTION_FILE_PREFIX.get(section_id)
    if not prefix:
        return None
    matches = sorted(glob.glob(os.path.join(root, "sections", f"{prefix}*.md")))
    return matches[0] if matches else None


def file_nonempty(path):
    if not path:
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            return bool(f.read().strip())
    except OSError:
        return False


def consistency_map_nonempty(root):
    cm = _load_json(os.path.join(root, "data/consistency_map.json"))
    if not isinstance(cm, dict):
        return False, False
    # 非空：任一实体列表非空
    nonempty = any(isinstance(v, list) and v for v in cm.values())
    # 含 M（methodologies）
    has_m = isinstance(cm.get("M"), list) and bool(cm.get("M"))
    if not has_m and isinstance(cm.get("methodologies"), list):
        has_m = bool(cm.get("methodologies"))
    return nonempty, has_m


def experimental_design_nonempty(root):
    ed = _load_json(os.path.join(root, "data/experimental_design.json"))
    if not isinstance(ed, dict):
        # 也容忍直接是 list
        if isinstance(ed, list):
            return bool(ed)
        return False
    entries = ed.get("entries")
    return isinstance(entries, list) and bool(entries)


NEWKEY_RE = __import__("re").compile(r"\[@new:")


def _load_verified_ids(root):
    """data/literature_index.json 的 verified 条目 id 集合（缺/畸形→空集，不炸）。"""
    idx = _load_json(os.path.join(root, "data", "literature_index.json"))
    if not isinstance(idx, dict):
        return set()
    return {e.get("id") for e in idx.get("entries", [])
            if isinstance(e, dict) and e.get("verified", True)}


def check_new_refs_merged(root, prev_section, prev_fp):
    """节边界并表核验（INTERFACE §4.1，硬要求4-A）。返回 failures 列表（空=通过）。

    只在上一节走过撰写编排（存在 .write_return_<prev>.json）时校验：
      1. 上一节 new_refs 每条都经 merge-refs 并表且解析到 verified 文献条目（忘并表/忘核验→FAIL）
      2. 上一节正文无残留未映射的 [@new: 键（已并表成真 id 后不应残留）
    未走编排（无 .write_return）→ 两项均 vacuously pass（不是每节都派子代理）。
    """
    failures = []
    ret_path = os.path.join(root, f".write_return_{prev_section}.json")
    ret = _load_json(ret_path)
    if isinstance(ret, dict):
        new_refs = ret.get("new_refs") or []
        keymap = _load_json(os.path.join(root, ".newref_map.json"))
        keymap = keymap if isinstance(keymap, dict) else {}
        verified_ids = _load_verified_ids(root)
        for nr in new_refs if isinstance(new_refs, list) else []:
            key = nr.get("key") if isinstance(nr, dict) else None
            rid = keymap.get(key)
            if not rid or rid not in verified_ids:
                failures.append(
                    f"上一节 new_refs 未并表/未核验: {key} "
                    f"(run: citation_renumber.py merge-refs)")
    # 残留 [@new: 扫描（编排与否都查；真源正文里不该有未翻号的新键）
    if prev_fp and os.path.isfile(prev_fp):
        try:
            with open(prev_fp, "r", encoding="utf-8") as f:
                if NEWKEY_RE.search(f.read()):
                    failures.append(f"上一节残留未并表新键 [@new: in {os.path.basename(prev_fp)}")
        except OSError:
            pass
    return failures


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
        description="nsfc-proposal 开写前置闸门：上一节完成/consistency_map/素材就位/占位符硬检查。"
    )
    parser.add_argument("--section", required=True, help="section id ∈ {P1,P2,P3_1,P3_2,P3_3,P3_4}")
    parser.add_argument("--root", required=True, help="project root")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    section = str(args.section).strip()
    checks = []
    warnings = []
    failures = []

    if not os.path.isdir(root):
        print(f"PREWRITE_GATE: FAIL root not a directory: {root}")
        print(json.dumps({"ok": False, "section": section, "checks": [],
                          "warnings": []}, ensure_ascii=False))
        return 1

    known_section = section in SECTION_ORDER
    if not known_section:
        warnings.append(f"section {section!r} not in fixed order {SECTION_ORDER}; prev/gate checks degraded")

    # ---- check 1: 上一节完成 ----
    if known_section:
        idx = SECTION_ORDER.index(section)
        if idx == 0:
            checks.append({"name": "prev_section_done", "ok": True, "note": "first section, skip"})
        else:
            prev = SECTION_ORDER[idx - 1]
            prev_fp = section_file(root, prev)
            if file_nonempty(prev_fp):
                checks.append({"name": "prev_section_done", "ok": True, "prev": prev})
            else:
                failures.append(f"previous section {prev} file missing or empty under sections/")
                checks.append({"name": "prev_section_done", "ok": False, "prev": prev})
    else:
        checks.append({"name": "prev_section_done", "ok": None, "note": "unknown section, skip"})

    # ---- check 2: consistency_map 就位（链路已登记） ----
    cm_nonempty, has_m = consistency_map_nonempty(root)
    if cm_nonempty:
        checks.append({"name": "consistency_map", "ok": True})
    else:
        failures.append("data/consistency_map.json missing or empty (H/O/RC/KSQ not registered)")
        checks.append({"name": "consistency_map", "ok": False})

    # ---- check 3: 素材就位（适配 section） ----
    # P2 / P3_1 需要 experimental_design.json
    if section in ("P2", "P3_1"):
        if experimental_design_nonempty(root):
            checks.append({"name": "experimental_design", "ok": True})
        else:
            failures.append("data/experimental_design.json missing or has no entries (required for M / feasibility)")
            checks.append({"name": "experimental_design", "ok": False})
    # P2 起 consistency_map 须含 M
    if section in ("P2", "P3_1", "P3_2", "P3_3", "P3_4"):
        if has_m:
            checks.append({"name": "methodologies_M", "ok": True})
        elif section == "P2":
            # P2 正是产出 M 的阶段，开写前 M 可能尚空 → 降级 warning
            warnings.append("consistency_map has no M entries yet; P2 is where M is authored, ensure M is registered before locking section")
            checks.append({"name": "methodologies_M", "ok": None, "note": "P2 authors M; warning only"})
        else:
            failures.append("consistency_map has no M (methodologies) entries; P3 must build on P2's M")
            checks.append({"name": "methodologies_M", "ok": False})

    # ---- check: 上一节盲检通过并落盘（硬，仅跨 Phase 边界生效） ----
    # nsfc 盲检按 Phase(p1/p2/p3/...)粒度，P3_1..P3_4 同属 P3 Phase 一次性盲检，
    # 内部子节间无独立盲检契约 → 同 Phase 内 prev 不硬校验。仅 P2→需 P1、
    # P3_1→需 P2 这类跨 Phase 边界硬校验上一 Phase 的盲检通过标记。
    if known_section and SECTION_ORDER.index(section) > 0:
        prev = SECTION_ORDER[SECTION_ORDER.index(section) - 1]
        same_phase = prev.split("_")[0] == section.split("_")[0]
        if same_phase:
            checks.append({"name": "blind_review", "ok": True,
                          "note": f"prev {prev} in same Phase, single blind review, N/A"})
        else:
            pass_path = os.path.join(root, ".review_pass", f"{prev}.json")
            marker = _load_json(pass_path)
            if isinstance(marker, dict) and marker.get("passed") is True:
                checks.append({"name": "blind_review", "ok": True, "prev": prev})
            else:
                failures.append(
                    f"previous section {prev!r} blind review not passed or marker missing; "
                    f"run: delegate_review.py verify --section {prev}")
                checks.append({"name": "blind_review", "ok": False, "prev": prev})
    elif known_section:
        checks.append({"name": "blind_review", "ok": True, "note": "first section, N/A"})

    # ---- check 4: 占位符清零（上一节文件；P1 无上一节则扫已写的 sections/*.md） ----
    files_to_scan = []
    if known_section:
        idx = SECTION_ORDER.index(section)
        if idx > 0:
            prev_fp = section_file(root, SECTION_ORDER[idx - 1])
            if prev_fp:
                files_to_scan = [prev_fp]
    if not files_to_scan:
        files_to_scan = sorted(glob.glob(os.path.join(root, "sections", "P*.md")))
    placeholder_hits = scan_placeholders(files_to_scan)
    if placeholder_hits:
        detail = ", ".join(f"{fn}:{tok}" for fn, tok in placeholder_hits)
        failures.append(f"unresolved placeholders: {detail}")
        checks.append({"name": "placeholders", "ok": False, "detail": detail})
    else:
        checks.append({"name": "placeholders", "ok": True})

    # ---- check: new_refs 并表核验 + 残留新键（节边界，硬要求4-A，INTERFACE §4.1） ----
    if known_section and SECTION_ORDER.index(section) > 0:
        prev = SECTION_ORDER[SECTION_ORDER.index(section) - 1]
        prev_fp = section_file(root, prev)
        nr_failures = check_new_refs_merged(root, prev, prev_fp)
        if nr_failures:
            failures.extend(nr_failures)
            checks.append({"name": "new_refs_merged", "ok": False, "detail": nr_failures})
        else:
            checks.append({"name": "new_refs_merged", "ok": True})
    else:
        checks.append({"name": "new_refs_merged", "ok": True, "note": "first section, N/A"})

    # ---- 缩略词：nsfc 无独立 abbreviation 脚本 → skip ----
    checks.append({"name": "abbreviation", "ok": None, "note": "no standalone abbreviation script in nsfc-proposal; skip"})

    ok = not failures
    print(json.dumps({"ok": ok, "section": section, "checks": checks,
                      "warnings": warnings}, ensure_ascii=False))
    if not ok:
        for reason in failures:
            print(f"PREWRITE_GATE: FAIL {reason}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
