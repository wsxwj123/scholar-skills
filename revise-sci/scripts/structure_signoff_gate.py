#!/usr/bin/env python3
"""结构签字门禁（共享，粗粒度）——"大纲/故事线没经用户确认，不许写正文"。

为什么是它：跳步的 AI（尤其弱模型）最常见的失误就是没等用户确认大纲/storyline
就开写正文。本门禁把"用户确认"理化成一个签字文件，hook 在每次写正文产物前
check 它——签字不存在就物理拦截写入。逐节时序仍由各技能自己的 prewrite_gate
+ token 链负责；本门禁只管这个从文件状态就能可靠判定的粗粒度不变量。

用法：
  confirm: python structure_signoff_gate.py confirm --root <project_root> [--note "用户确认要点"]
    仅当用户在对话中明确确认了大纲/storyline 后才能运行——AI 不得代替用户确认。
    写 <root>/structure_signoff.json（含 UTC 时间戳与 note），解锁正文写作。
  check:   python structure_signoff_gate.py check --root <project_root>
    签字存在且合法 → exit 0；否则 exit 2 并打印人话原因（hook 会转给 AI/用户）。

签字后大纲又大改了怎么办：重跑 confirm 覆盖即可（append 历史到 history 字段）。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

SIGNOFF_NAME = "structure_signoff.json"


def cmd_confirm(root: Path, note: str) -> int:
    path = root / SIGNOFF_NAME
    history = []
    if path.is_file():
        try:
            prev = json.loads(path.read_text(encoding="utf-8"))
            history = prev.get("history", [])
            history.append({k: prev[k] for k in ("confirmed_epoch", "note") if k in prev})
        except Exception:
            pass
    payload = {
        "confirmed": True,
        "confirmed_epoch": int(time.time()),
        "note": note or "",
        "history": history[-10:],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "signoff": str(path)}, ensure_ascii=False))
    return 0


def cmd_check(root: Path) -> int:
    path = root / SIGNOFF_NAME
    if not path.is_file():
        print(
            "结构签字缺失：大纲/故事线还没有经过用户确认。\n"
            "正确流程：① 把完整大纲/storyline 展示给用户 → ② 用户在对话里明确说'确认'"
            " → ③ 运行 python <本脚本> confirm --root <项目根> 落盘签字 → ④ 才能写正文。\n"
            "AI 不得在用户未确认时自行运行 confirm。"
        )
        return 2
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        print("structure_signoff.json 损坏（非合法 JSON），请让用户重新确认大纲后重跑 confirm。")
        return 2
    if not data.get("confirmed"):
        print("structure_signoff.json 存在但 confirmed≠true，请让用户确认大纲后重跑 confirm。")
        return 2
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="结构签字门禁：用户确认大纲前不许写正文")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_confirm = sub.add_parser("confirm", help="用户已在对话中确认大纲后落盘签字")
    p_confirm.add_argument("--root", required=True)
    p_confirm.add_argument("--note", default="", help="用户确认时的要点/原话摘录")
    p_check = sub.add_parser("check", help="校验签字是否存在(hook 调用)")
    p_check.add_argument("--root", required=True)
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"项目根不存在: {root}")
        return 2
    if args.cmd == "confirm":
        return cmd_confirm(root, args.note)
    return cmd_check(root)


if __name__ == "__main__":
    sys.exit(main())
