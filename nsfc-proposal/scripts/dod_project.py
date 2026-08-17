#!/usr/bin/env python3
"""dod_project.py — DoD 自检项协商投影（INTERFACE-nsfc-template §7）。

把 references/dod_checklist.json 先减去「本项目类型不适用的项」（round23：仅当
<root>/structure_profile.json 合法已确认 funding_scheme=other 时，减免清单里声明
nsfc_bound 的项、把声明 check_other 的项判据换文），再减去 <root>/data/
dod_selection.json 的 disabled[]，写成临时 checklist，供 delegate_review.py
pack --checklist 消费。两层减掉的项逐条留痕（stdout 与产物顶层 skipped_checks）。
过滤发生在 nsfc 侧，绝不改共享脚本 delegate_review.py。契约见
.devflow/INTERFACE-round23.md。

CLI:
    python3 dod_project.py project --root <root> --gate <g> --out tmp/dod_active_<g>.json

退出码: 0 成功（含全部 fail-safe 回落路径）；1 checklist 缺失/损坏/声明键非法、
selection 损坏、产物写入失败；2 用法错（未知 gate 等）。
成功时 stdout 单行 JSON:
    {"ok": true, "gate": "<g>", "out": "<路径>", "total": N, "active": N,
     "disabled": N, "waived": N, "repointed": N, "funding_scheme": "nsfc"|"other",
     "skipped_checks": [...], "repointed_ids": [...]}

dod_selection.json 四态（§7，fail-safe 方向是收紧不是放松）:
    不存在        -> 全项都跑，零输出
    坏 JSON       -> stderr 打 DOD_SELECTION: CORRUPT，回落全项都跑，exit 1
    字段非法      -> stderr 打 DOD_SELECTION: INVALID，回落全项都跑，exit 1
                     （schema_version 缺失/≠"1.0" 归此档；disabled[].gate 缺失或不是
                     checklist 里真实存在的 gate 也归此档——缺 gate 的条目在 == 匹配下
                     永不生效、留痕路却会照记，必须两路同拒；与 structure_profile.
                     _dod_disabled 同标签）
    未确认        -> confirmed != true：stderr 打 DOD_SELECTION: UNCONFIRMED，
                     关项不生效、全项都跑，exit 0（降级继续，与"不存在"同档；
                     structure_profile cmd_show 对 unconfirmed 同样归 0）
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def _fail(msg: str) -> None:
    sys.stderr.write(msg + "\n")


def _find_checklist(root: str) -> str | None:
    """checklist 定位：技能目录 references/ 优先；init 拷贝进项目后回落 <root>/references/。"""
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (
        os.path.join(here, os.pardir, "references", "dod_checklist.json"),
        os.path.join(root, "references", "dod_checklist.json"),
    ):
        cand = os.path.abspath(cand)
        if os.path.isfile(cand):
            return cand
    return None


# nsfc_bound 取值域＝07 §7.1 封闭集四项：DoD 层不自造减免理由，每条减免都必须
# 挂在已对用户讲清楚的封闭集上。新增第五种理由 = 先改封闭集，不是改这里。
_NSFC_BOUND_SET = ("SPA-REQUIRED", "HRCK-V-RULES", "HRCK-DIMS", "SPA-JUSTIFY")


def _scheme_is_other(root: str) -> bool:
    """项目类型读口的硬化壳：判据一处定义在 structure_profile.scheme_is_other
    （合法已确认 funding_scheme=other 才 True；坏真源/未确认/非法取值在那边已收敛
    成 False）。这里只兜「读口本身不可用」：导入失败/抛异常一律回 nsfc（从严）。"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import structure_profile
        return bool(structure_profile.scheme_is_other(root))
    except Exception:
        _fail("DOD_SCHEME: WARN structure_profile 不可用，本次按国自然全量执行")
        return False


def _load_selection(root: str, valid_gates: set[str]) -> tuple[list[dict], bool]:
    """读 dod_selection.json，返回 (disabled 条目列表, 是否损坏)。

    损坏/非法一律回落空列表（= 全项都跑），错误行打 stderr（格式同 §3，统一 stderr）。
    confirmed != true 同样回落空列表并打 UNCONFIRMED 行，但不算损坏（exit 0）。

    valid_gates: checklist 里真实存在的 gate 集合。条目 gate 缺失/非字符串/不在
    集合内 = 字段非法（INVALID）——缺 gate 的条目在本路的 == 匹配下永不生效，
    留痕路却会照记「未执行」，必须在入口就拒掉，两路才同口径（2026-08-03 缺陷）。
    """
    path = os.path.join(root, "data", "dod_selection.json")
    if not os.path.isfile(path):
        return [], False  # 缺失 = 正常态，零输出
    abs_path = os.path.abspath(path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        _fail("DOD_SELECTION: CORRUPT %s: line %d column %d" % (abs_path, exc.lineno, exc.colno))
        _fail("处置：修复该文件；或删除它，脚本会回落到「全项都跑」。")
        return [], True
    except OSError as exc:
        _fail("DOD_SELECTION: CORRUPT %s: %s" % (abs_path, exc))
        _fail("处置：修复该文件；或删除它，脚本会回落到「全项都跑」。")
        return [], True

    if not isinstance(data, dict):
        _fail("DOD_SELECTION: INVALID %s: (root) 必须是对象" % abs_path)
        _fail("处置：修正该文件；或删除它，脚本会回落到「全项都跑」。")
        return [], True

    # 与留痕路 structure_profile._dod_disabled 同口径：schema_version 非法 = INVALID，
    # 先于 confirmed 检查（否则两路对同一份文件打不同标签，正是本次修的缺陷）
    if data.get("schema_version") != "1.0":
        _fail('DOD_SELECTION: INVALID %s: schema_version 缺失或不等于 "1.0"' % abs_path)
        _fail("处置：修正该字段；或删除该文件，脚本会回落到「全项都跑」。")
        return [], True

    disabled = data.get("disabled", [])
    if not isinstance(disabled, list):
        _fail("DOD_SELECTION: INVALID %s: disabled 必须是数组" % abs_path)
        _fail("处置：修正该字段；或删除该文件，脚本会回落到「全项都跑」。")
        return [], True

    out: list[dict] = []
    for i, entry in enumerate(disabled):
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or not entry.get("id"):
            _fail("DOD_SELECTION: INVALID %s: disabled[%d] 必须含字符串 id" % (abs_path, i))
            _fail("处置：修正该条目；或删除该文件，脚本会回落到「全项都跑」。")
            return [], True
        gate = entry.get("gate")
        if not isinstance(gate, str) or gate not in valid_gates:
            _fail("DOD_SELECTION: INVALID %s: disabled[%d].gate 缺失或不是已知 gate（可用: %s）"
                  % (abs_path, i, ", ".join(sorted(valid_gates)) or "(空)"))
            _fail("处置：修正该条目；或删除该文件，脚本会回落到「全项都跑」。")
            return [], True
        out.append(entry)

    # 红线：未经用户确认的关项一律不生效（关掉检查=降低标准，必须逐条确认）。
    # 留痕路 structure_profile._dod_disabled 对 confirmed != true 同样回落全项。
    # 这是降级继续而非错误输入，broken=False -> exit 0，与"文件不存在"同档。
    if data.get("confirmed") is not True:
        _fail("DOD_SELECTION: UNCONFIRMED %s" % abs_path)
        _fail("处置：这份自检项选择未经用户确认，本次按全项执行。"
              "请把 disabled 清单摆给用户逐条核对后，将 confirmed 置为 true。")
        return [], False
    return out, False


def cmd_project(args: argparse.Namespace) -> int:
    root = args.root

    checklist_path = _find_checklist(root)
    if checklist_path is None:
        _fail("DOD_CHECKLIST: MISSING references/dod_checklist.json（技能目录与 %s 下均未找到）" % root)
        return 1
    try:
        with open(checklist_path, "r", encoding="utf-8") as f:
            checklist = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        _fail("DOD_CHECKLIST: CORRUPT %s: %s" % (checklist_path, exc))
        return 1

    gates = checklist.get("gates") if isinstance(checklist, dict) else None
    if not isinstance(gates, dict):
        _fail("DOD_CHECKLIST: CORRUPT %s: gates 必须是对象" % checklist_path)
        return 1
    if args.gate not in gates:
        _fail("dod_project: 未知 gate %r。可用: %s" % (args.gate, ", ".join(sorted(gates)) or "(空)"))
        return 2
    gate_obj = gates[args.gate]
    items = gate_obj.get("items") if isinstance(gate_obj, dict) else None
    if not isinstance(items, list):
        _fail("DOD_CHECKLIST: CORRUPT %s: gates[%s].items 必须是数组" % (checklist_path, args.gate))
        return 1

    scheme_other = _scheme_is_other(root)
    disabled_entries, selection_broken = _load_selection(root, set(gates))
    off_ids = {e["id"] for e in disabled_entries if e.get("gate") == args.gate}

    total = len(items)
    decl_invalid = False
    waived_ids: set[str] = set()
    repointed_ids: list[str] = []
    if scheme_other:
        # 声明键校验只在 scheme=other 时做（nsfc 下两键不生效，不校验不报错）
        for i, it in enumerate(items):
            if not isinstance(it, dict):
                continue
            has_bound, has_other = "nsfc_bound" in it, "check_other" in it
            why = None
            if has_bound and has_other:
                why = "nsfc_bound 与 check_other 不得同时出现"
            elif has_bound and it["nsfc_bound"] not in _NSFC_BOUND_SET:
                why = ("nsfc_bound 取值 %s 不在封闭集（SPA-REQUIRED / HRCK-V-RULES"
                       " / HRCK-DIMS / SPA-JUSTIFY）" % (it["nsfc_bound"],))
            elif has_other and (not isinstance(it["check_other"], str)
                                or not it["check_other"].strip()):
                why = "check_other 必须是非空字符串"
            if why:
                decl_invalid = True
                _fail("DOD_CHECKLIST: INVALID %s: gates[%s].items[%d] %s"
                      "（本项按国自然全量执行）" % (checklist_path, args.gate, i, why))
                _fail("处置：修正该条目的声明键；本次已按「不减免、不改判」执行。")
        if not decl_invalid:
            for it in items:
                if not isinstance(it, dict) or not isinstance(it.get("id"), str):
                    continue
                if "nsfc_bound" in it:
                    waived_ids.add(it["id"])
                elif "check_other" in it:
                    it["check"] = it["check_other"]   # 改判：判据换文本，键保留（§3）
                    repointed_ids.append(it["id"])
        # 自检信号：整份 checklist（不是单个 gate）一个 nsfc_bound 都没有 → 提示
        if not any(isinstance(it, dict) and "nsfc_bound" in it
                   for g in gates.values() if isinstance(g, dict)
                   for it in (g.get("items") or [])):
            _fail("DOD_SCHEME: NO_MARKERS %s: funding_scheme=other "
                  "但清单中无任何 nsfc_bound 标记" % checklist_path)
            _fail("处置：多半命中了项目自带的旧 references/dod_checklist.json 副本，"
                  "请更新它或删除后改用技能目录版本。")

    # 两层叠加（INTERFACE §6）：removed = waived ∪ disabled，重叠只算一次归 waived
    item_ids = {it.get("id") for it in items if isinstance(it, dict)}
    disabled_effective = (off_ids & item_ids) - waived_ids
    removed = waived_ids | disabled_effective
    active_items = [it for it in items
                    if not (isinstance(it, dict) and it.get("id") in removed)]
    active = len(active_items)

    # 留痕：先第一层（items 原序），后第二层（items 原序），id 不重复（§2.1）
    skipped_checks = []
    for it in items:
        if isinstance(it, dict) and it.get("id") in waived_ids:
            skipped_checks.append({"id": it["id"], "name": it.get("name", ""),
                                   "reason": "structure_profile.funding_scheme=other",
                                   "status": "未执行", "nsfc_bound": it["nsfc_bound"]})
    for it in items:
        if isinstance(it, dict) and it.get("id") in disabled_effective:
            skipped_checks.append({"id": it["id"], "name": it.get("name", ""),
                                   "reason": "dod_selection.disabled",
                                   "status": "未执行"})

    # 就地替换该 gate 的 items；其余 gate 原样保留（pack 只读指定 gate）。
    # 顶层 skipped_checks：scheme=other 时与 stdout 同一份数组（delegate_review 不读
    # 它，只为留痕落盘）；nsfc 时恒 []——考卷 K5 锁死「国自产物不得出现手关项 id」，
    # 与 INTERFACE §3「同一份数组」在 nsfc+手关场景冲突，按考卷为准（已登记）。
    gate_obj["items"] = active_items
    checklist["skipped_checks"] = skipped_checks if scheme_other else []

    out_path = args.out
    parent = os.path.dirname(out_path)
    try:
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(checklist, f, ensure_ascii=False, indent=2)
    except OSError as exc:
        _fail("dod_project: 临时 checklist 写入失败 %s: %s" % (out_path, exc))
        return 1

    if selection_broken or decl_invalid:
        # 从严回落的产物已写出可用；退出码 1 提示 selection / checklist 声明键需要修
        return 1

    print(json.dumps({"ok": True, "gate": args.gate, "out": out_path,
                      "total": total, "active": active,
                      "disabled": len(disabled_effective),
                      "waived": len(waived_ids), "repointed": len(repointed_ids),
                      "funding_scheme": "other" if scheme_other else "nsfc",
                      "skipped_checks": skipped_checks,
                      "repointed_ids": sorted(repointed_ids)},
                     ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="DoD 清单协商投影：checklist 减 dod_selection.disabled")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("project", help="产出减去 disabled 项的临时 checklist")
    p.add_argument("--root", required=True, help="项目根（读 <root>/data/dod_selection.json）")
    p.add_argument("--gate", required=True, help="checklist 内的 gate id")
    p.add_argument("--out", required=True, help="临时 checklist 输出路径")
    p.set_defaults(func=cmd_project)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
