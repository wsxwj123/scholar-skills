#!/usr/bin/env python3
"""budget_check.py — nsfc-proposal 预算分项求和 vs 总额比对（只读校验器）。

背景：consistency_mapper 的 V-09 只查「预算条目能不能追到 M」（INFO 级），
全项目此前没有任何脚本把分项金额加一遍跟总额比——填错一位数没人发现。

CLI：python3 budget_check.py --root <project_root>
读 <root>/data/budget_table.json：
  {"budget_total": 500000, "items": [{"name": "设备费", "amount": 200000}, ...]}

金额一律「元」的数字，禁止 "20万元" 这类带单位字符串（不猜换算、不当 0）。
求和走 Decimal（按字面十进制精确相加），避免 0.1+0.2 的二进制浮点尾差误报。

退出码：
  0 = 相符（|diff| <= 0.01 元），stdout 一行 JSON ok:true
  1 = 不符，stdout 一行 JSON ok:false 且带 diff（= items_sum - budget_total，带符号）
  2 = 文件缺失/畸形/金额非法/用法错，stderr 打 BUDGET_CHECK_ERROR，绝不输出 ok:true

只读：不写任何文件，也不「顺手改平」预算表。
"""
from __future__ import annotations

# 🔴 stdout/stderr 强制 UTF-8（照抄 _shared/academic_gate_hook.py 的既有写法）：
# 报错理由含中文，英文语系 Windows（cp1252/cp437）下 print() 会抛
# UnicodeEncodeError，导致退出码被编码问题顶掉、错误契约失真。
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import argparse
import json
import math
import os
import sys
from decimal import Decimal, InvalidOperation

TOLERANCE = Decimal("0.01")  # 容差 1 分钱


def die(msg: str) -> None:
    print("BUDGET_CHECK_ERROR: %s" % msg, file=sys.stderr)
    sys.exit(2)


def to_decimal(value, where: str) -> Decimal:
    """金额转 Decimal。非数字（含带单位字符串、bool、NaN/inf）一律报错点名出处。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        die("%s 的金额不是数字：%r。金额必须是「元」的纯数字，"
            "不接受 \"20万元\" 这类带单位字符串（不猜换算，也不当 0 放过）。" % (where, value))
    if isinstance(value, float) and not math.isfinite(value):
        die("%s 的金额不是有限数字：%r" % (where, value))
    try:
        return Decimal(str(value))
    except InvalidOperation:
        die("%s 的金额无法解析为数值：%r" % (where, value))


def jsonable(d: Decimal):
    """Decimal → JSON 可序列化：整数出 int，其余出 float。"""
    return int(d) if d == d.to_integral_value() else float(d)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="国自然预算分项求和与总额比对（只读校验，不改预算表）")
    ap.add_argument("--root", required=True, help="项目根目录（含 data/budget_table.json）")
    args = ap.parse_args()

    path = os.path.join(args.root, "data", "budget_table.json")
    if not os.path.isfile(path):
        die("找不到预算表 budget_table.json -> %s（绝不静默通过，请先落盘预算分项）" % path)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        die("budget_table.json 不是合法 JSON（%s）-> %s" % (e, path))
    except OSError as e:
        die("budget_table.json 读取失败（%s）-> %s" % (e, path))

    if not isinstance(data, dict):
        die("budget_table.json 顶层应是对象 {\"budget_total\":..,\"items\":[..]}，实得 %s"
            % type(data).__name__)
    if "budget_total" not in data:
        die("budget_table.json 缺 budget_total 字段")
    total = to_decimal(data["budget_total"], "budget_total")

    items = data.get("items")
    if not isinstance(items, list):
        die("budget_table.json 的 items 应是数组，实得 %s" % type(items).__name__)

    items_sum = Decimal("0")
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            die("items[%d] 应是对象 {\"name\":..,\"amount\":..}，实得 %r" % (i, item))
        name = item.get("name")
        where = "分项「%s」" % name if isinstance(name, str) and name else "items[%d]" % i
        if "amount" not in item:
            die("%s 缺 amount 字段" % where)
        items_sum += to_decimal(item["amount"], where)

    diff = items_sum - total
    ok = abs(diff) <= TOLERANCE
    print(json.dumps({
        "ok": ok,
        "items_sum": jsonable(items_sum),
        "budget_total": jsonable(total),
        "diff": jsonable(diff),
        "item_count": len(items),
        "tolerance": float(TOLERANCE),
    }, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
