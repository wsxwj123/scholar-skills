#!/usr/bin/env python3
"""dod_project.py — DoD 自检项协商投影（INTERFACE-nsfc-template §7）。

把 references/dod_checklist.json 减去 <root>/data/dod_selection.json 的
disabled[]，写成临时 checklist，供 delegate_review.py pack --checklist 消费。
过滤发生在 nsfc 侧，绝不改共享脚本 delegate_review.py。

CLI:
    python3 dod_project.py project --root <root> --gate <g> --out tmp/dod_active_<g>.json

退出码: 0 成功；1 checklist 或 selection 损坏；2 用法错（未知 gate 等）。
成功时 stdout 单行 JSON（§9 裁决 9）:
    {"ok": true, "gate": "<g>", "out": "<路径>", "total": N, "active": N, "disabled": N}

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

    disabled_entries, selection_broken = _load_selection(root, set(gates))
    off_ids = {e["id"] for e in disabled_entries if e.get("gate") == args.gate}

    total = len(items)
    active_items = [it for it in items if not (isinstance(it, dict) and it.get("id") in off_ids)]
    active = len(active_items)

    # 就地替换该 gate 的 items；其余 gate 原样保留（pack 只读指定 gate）
    gate_obj["items"] = active_items

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

    if selection_broken:
        # 回落「全项都跑」的产物已写出可用；退出码 1 提示 selection 需要修
        return 1

    print(json.dumps({"ok": True, "gate": args.gate, "out": out_path,
                      "total": total, "active": active, "disabled": total - active},
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
