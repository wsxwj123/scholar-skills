#!/usr/bin/env python3
"""跨会话接续 + 决定日志（共享，8 技能通用）——解决"关会话换会话接着写 + 中途插很多要求"。

不靠 hook：把连续性做成"外置状态 + 决定日志"，让任何新会话开局读它就能重建上下文。

CLI:
  # 记录用户临时要求（每次用户插要求就 append，后续会话必读）
  python session_journal.py log --root <R> --note "用户要求：把第3节改成先讲机制"

  # 新会话/续写开局：打印接续报告，供 AI 贴给用户 + 打接续握手
  python session_journal.py resume --root <R>

约定文件（项目根）：
  decisions_log.md   —— 决定日志，一条一行，带 UTC 时间戳，append-only
  以及各技能自己的权威 state（state.json / project_state.json / writing_progress.json /
  project_config.json 之一）、outline.md / project_state.json.outline 等——resume 尽力读、缺则跳过。

纯 stdlib、跨平台、不含 MCP、不碰 hook。resume 只读只展示、绝不阻断。
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

DECISIONS = "decisions_log.md"
STATE_CANDIDATES = ["writing_progress.json", "project_state.json", "project_config.json", "state.json"]
OUTLINE_CANDIDATES = ["outline.md", "outline.json"]


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def cmd_log(root: Path, note: str) -> int:
    note = (note or "").strip()
    if not note:
        print("拒绝：--note 不能为空")
        return 2
    line = f"- [{_utc()}] {note}\n"
    p = root / DECISIONS
    if not p.exists():
        p.write_text("# 决定日志（用户历次要求/决定，后续会话必读并遵守）\n\n", encoding="utf-8")
    with p.open("a", encoding="utf-8") as f:
        f.write(line)
    print(json.dumps({"ok": True, "logged": note, "file": str(p)}, ensure_ascii=False))
    return 0


def _read_state(root: Path) -> tuple[str, dict] | None:
    for name in STATE_CANDIDATES:
        p = root / name
        if p.is_file():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return name, data
            except Exception:
                pass
    return None


def _read_decisions(root: Path) -> list[str]:
    p = root / DECISIONS
    if not p.is_file():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln.startswith("- ["):
            out.append(ln)
    return out


def cmd_resume(root: Path) -> int:
    if not root.is_dir():
        print(f"项目根不存在：{root}")
        return 2
    lines = ["# 接续报告（新会话开局先读，再跟用户打接续握手）", ""]

    st = _read_state(root)
    if st:
        name, data = st
        phase = data.get("phase", data.get("current_phase", "?"))
        done = data.get("completed_sections") or data.get("completed") or data.get("done_sections") or []
        lines += [f"**权威状态**（{name}）：phase = `{phase}`",
                  f"- 已完成：{', '.join(map(str, done)) if done else '（无记录）'}"]
        for k in ("last_section", "next_section", "skill", "title"):
            if data.get(k):
                lines.append(f"- {k}: {data[k]}")
    else:
        lines.append("**权威状态**：未找到 state 文件——可能是新项目或未初始化。")
    lines.append("")

    for name in OUTLINE_CANDIDATES:
        p = root / name
        if p.is_file():
            lines.append(f"**大纲/提纲**：见 `{name}`（存在，写作前请读取）")
            break

    decisions = _read_decisions(root)
    lines.append("")
    if decisions:
        lines.append(f"**用户历次要求/决定（{len(decisions)} 条，必须遵守）：**")
        lines += decisions
    else:
        lines.append("**用户历次要求/决定**：暂无（`decisions_log.md` 为空或不存在）。")

    lines += ["", "---",
              "AI 接续握手（据上表对用户说，并等确认再动手）：",
              "「我们在写这个项目，进度到上面的 phase；你之前的要求我都读了（见决定日志）；",
              "我打算接着做 <下一步>，对吗？还是你有新的要求先插进来？」"]
    print("\n".join(lines))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="跨会话接续 + 决定日志")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("log", help="记录用户临时要求")
    pl.add_argument("--root", required=True)
    pl.add_argument("--note", required=True)
    pr = sub.add_parser("resume", help="开局打印接续报告")
    pr.add_argument("--root", required=True)
    args = ap.parse_args()
    root = Path(args.root).expanduser().resolve()
    if args.cmd == "log":
        return cmd_log(root, args.note)
    return cmd_resume(root)


if __name__ == "__main__":
    raise SystemExit(main())
