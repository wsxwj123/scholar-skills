#!/usr/bin/env python3
"""figure_analysis_gate.py — Phase 8 写 Results 小节前的硬门禁。

逻辑：
1. 读 figures_database.json，挑出 section == --section 的所有 figure
2. 对每张 figure，按 figure_id 推断 N，检查 figure_analysis/figure_{N}.md 是否：
   - 存在
   - 非空（去除空白后 >0）
   - 不含未确认占位 "❓待确认"
3. 任一不满足 → stdout 打印 FIGURE_ANALYSIS_NOT_READY:... 并 exit 1
4. 全部就绪或该 section 无对应 figure → exit 0

被 SKILL.md Phase 8 / DoD G14 引用。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys


def extract_n(figure_id: str) -> str | None:
    """从 figure_id 抽出编号字符串。

    支持："Figure 2" / "Figure 2A" / "Fig2" / "Fig. 2" / "figure_2" / "2"。
    返回纯数字字符串（不含字母 panel 后缀）或 None。
    """
    if not figure_id:
        return None
    match = re.search(r"(\d+)", str(figure_id))
    return match.group(1) if match else None


def load_figures(root: str) -> list[dict]:
    path = os.path.join(root, "figures_database.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"FIGURE_ANALYSIS_NOT_READY: figures_database.json invalid JSON ({exc})")
        sys.exit(1)
    # Tolerate list[dict] or dict-with-list.
    if isinstance(data, dict):
        for key in ("figures", "items", "data"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def figures_for_section(figures: list[dict], section: str) -> list[dict]:
    section_norm = section.strip()
    out = []
    for item in figures:
        # 兼容单数字符串字段与复数数组字段（section_ids）
        sec = str(item.get("section") or item.get("section_id") or "").strip()
        section_list = item.get("section_ids") or []
        if not isinstance(section_list, list):
            section_list = [section_list]
        section_list = [str(s).strip() for s in section_list]
        if sec == section_norm or section_norm in section_list:
            out.append(item)
    return out


def check_one(root: str, figure: dict) -> str | None:
    """返回 None 表示就绪，否则返回失败原因短句。"""
    fid = figure.get("figure_id") or figure.get("fig_id") or figure.get("id") or ""
    n = extract_n(fid)
    if not n:
        return f"figure_id={fid!r} cannot extract numeric N"
    fa_path = os.path.join(root, "figure_analysis", f"figure_{n}.md")
    if not os.path.exists(fa_path):
        return f"figure_{n} missing (expected {fa_path})"
    try:
        with open(fa_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as exc:
        return f"figure_{n} unreadable ({exc})"
    if not content.strip():
        return f"figure_{n} empty"
    if "❓待确认" in content:
        return f"figure_{n} incomplete (contains ❓待确认)"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 8 figure_analysis 加载门禁：在 /write {section} 前确认该节涉及的所有 "
            "figure_analysis/figure_N.md 已就绪。"
        )
    )
    parser.add_argument("--section", required=True,
                        help="storyline section_id，例如 results_3.2")
    parser.add_argument("--root", required=True,
                        help="project root，含 figures_database.json 与 figure_analysis/")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"FIGURE_ANALYSIS_NOT_READY: root not a directory: {root}")
        return 1

    figures = load_figures(root)
    section_figs = figures_for_section(figures, args.section)
    if not section_figs:
        # 该节无关联 figure（如 Introduction/Methods 仅依赖文献）— 直接放行。
        print(f"FIGURE_ANALYSIS_OK: section={args.section} has no associated figures")
        print("  note: 放行仅因本节无关联图，不代表内容科学性已核验——须作者判断。",
              file=sys.stderr)
        return 0

    failures: list[str] = []
    for fig in section_figs:
        reason = check_one(root, fig)
        if reason:
            failures.append(reason)

    if failures:
        for reason in failures:
            print(f"FIGURE_ANALYSIS_NOT_READY: {reason}")
        return 1

    print(
        f"FIGURE_ANALYSIS_OK: section={args.section} "
        f"figures_ready={len(section_figs)}"
    )
    print(
        "  note: OK 仅确认识图文件存在/非空/无❓待确认残留，"
        "不核验图的科学解读是否正确、数据是否支持结论——须作者判断。",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
