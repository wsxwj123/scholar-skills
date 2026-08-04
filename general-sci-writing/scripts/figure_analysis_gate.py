#!/usr/bin/env python3
"""figure_analysis_gate.py — Phase 8 写 Results 小节前的硬门禁。

逻辑：
1. 读 figures_database.json。**读不出来（文件不在／不可读／顶层形状不认识）→ exit 1**：
   那是"说不清本节有没有图"，不是"没有图"。本节确实无图时用
   `--allow-no-figures "<理由>"` 显式声明（留痕到 figure_waivers.json）。
2. 挑出 section == --section 的所有 figure
3. 对每张 figure，按 figure_id 推断 N（副图 "Figure S5" → "S5"，不与正图 "Figure 5" 撞记录），
   检查 figure_analysis/figure_{N}.md 是否：
   - 存在
   - 非空（去除空白后 >0）
   - 不含未确认占位 "❓待确认"
4. 任一不满足 → stdout 打印 FIGURE_ANALYSIS_NOT_READY:... 并 exit 1
5. 全部就绪或库读得出且该 section 无对应 figure → exit 0

被 SKILL.md Phase 8 / DoD G14 引用。
"""

from __future__ import annotations

import sys as _sys
try:  # Windows GBK 控制台/管道捕获下防 UnicodeEncodeError（与其余门禁脚本同一写法）。
    # 本脚本的**失败原因**里带 ❓待确认（U+2753，GBK 编不出）：崩了就只剩一段
    # Traceback，用户被拦住却看不到"figure_N 里还有 ❓待确认"这个真正原因。
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone


# 先剥掉 fig/figure 前缀，再看紧挨编号的 S/SI 副图标记——两步是为了让 "FigS5"
# （无分隔符）也能被认出来：单条正则里 `s?` 会把那个 S 当成 "Figs" 的复数尾巴吃掉。
_FIG_TOKEN_RE = re.compile(r"^\s*(?:supplementary\s*|supp\.?\s*)?fig(?:ure)?\.?[\s._-]*", re.I)
_FIG_N_RE = re.compile(r"^(SI|S)?[\s._-]*(\d+)", re.I)


def extract_n(figure_id: str) -> str | None:
    """从 figure_id 抽出编号字符串（副图带 S 前缀，正图不带）。

    支持："Figure 2" / "Figure 2A" / "Fig2" / "Fig. 2" / "figure_2" / "2"
         / "Figure S5" / "Fig. S5" / "FigS5" / "S5" → "S5"。
    返回编号字符串（不含 panel 字母后缀）或 None。

    ponytail: 复数写法 "Figures 5" 会把 s 读成副图标记 → "S5" → 找不到文件而被拦。
    figure_id 按 figure-protocol 是单数，这种输入本就畸形，宁可 fail-closed 也不能
    让 "Figure S5" 和 "Figure 5" 共用同一份识图记录（后者是静默串档）。
    """
    if not figure_id:
        return None
    rest = _FIG_TOKEN_RE.sub("", str(figure_id))
    match = _FIG_N_RE.match(rest) or _FIG_N_RE.search(rest)
    if not match:
        return None
    marker, digits = match.group(1), match.group(2)
    return f"S{digits}" if marker else digits


def load_figures(root: str) -> list[dict] | None:
    """读 figures_database.json。

    返回图条目列表（**空列表 = 库里确实没有图**，是 Phase 0 初始化后的合法状态），
    或 None = **读不出来**（文件不在／不可读／顶层形状不认识）。两者必须分开：
    过去三种"读不出来"都当成空列表，于是路径打错、忘跑 Phase 0、模板建错，
    每一节都自动过——这道"素材就位硬门"等于没跑。
    """
    path = os.path.join(root, "figures_database.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None
    except OSError as exc:
        print(f"FIGURE_ANALYSIS_NOT_READY: figures_database.json unreadable ({exc})")
        sys.exit(1)
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
            return None  # dict 但找不到图条目数组 = 形状不认识，不是"没有图"
    if not isinstance(data, list):
        return None
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


WAIVER_REL = "figure_waivers.json"


def record_figure_waiver(root: str, section: str, reason: str) -> str:
    """--allow-no-figures 的留痕：往 <root>/figure_waivers.json 追一条记录。

    写不进去就抛异常（调用方据此拒绝放行）——放行必留痕，痕留不下就不放行。
    台账损坏时宁可失败也不覆盖重建，避免抹掉此前的声明记录。
    与 review-writing prewrite_gate.record_search_waiver 同一套纪律。
    """
    path = os.path.join(root, WAIVER_REL)
    rows: list = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        if text.strip():
            rows = json.loads(text)              # 坏 JSON → 抛 JSONDecodeError，不覆盖
            if not isinstance(rows, list):
                raise ValueError(f"{WAIVER_REL} 顶层不是数组，拒绝覆盖重建")
    rows.append({
        "section": str(section),
        "waived": True,
        "waive_reason": reason,
        "waived_at": datetime.now(timezone.utc).isoformat(),
    })
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    return path


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
    parser.add_argument("--allow-no-figures", default=None, metavar="REASON",
                        help="逃生口：figures_database.json 读不出来、但本节确实无图时，"
                             "附非空理由显式声明（会追一条留痕到 figure_waivers.json）。"
                             "只豁免「读不出库」，不豁免「库里有图但识图文件没就绪」。")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"FIGURE_ANALYSIS_NOT_READY: root not a directory: {root}")
        return 1

    figures = load_figures(root)
    if figures is None:
        # 读不出库 = 说不清本节有没有图，不是"没有图"。默认拦住（原先默认放行，
        # 忘跑 Phase 0 / --root 打错 / 模板建错都会让每一节自动过）。
        reason = (args.allow_no_figures or "").strip()
        if args.allow_no_figures is None:
            print(f"FIGURE_ANALYSIS_NOT_READY: figures_database.json 读不出来"
                  f"（不存在或顶层形状不认识）: {os.path.join(root, 'figures_database.json')}")
            print("  → 正常项目 Phase 0 会把它初始化成 []；先确认 --root 指对、Phase 0 已跑。")
            print("  → 本节确实无图且不打算建库，加 --allow-no-figures \"<理由>\" 显式声明。")
            return 1
        if not reason:
            print("FIGURE_ANALYSIS_NOT_READY: --allow-no-figures 需附非空理由"
                  "（说明本节为何确实无图）")
            return 1
        try:
            waiver_path = record_figure_waiver(root, args.section, reason)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            # 留痕失败 → 拒绝放行。声明留不下来就等于没声明过。
            print(f"FIGURE_ANALYSIS_NOT_READY: --allow-no-figures 的留痕写不进 "
                  f"{os.path.join(root, WAIVER_REL)}（{exc}）——放行必留痕，不予放行")
            return 1
        print(f"FIGURE_ANALYSIS_OK: section={args.section} no figures (waived)")
        print(f"  note: 放行仅因调用方显式声明本节无图，已留痕于 {waiver_path}；"
              f"图库本身仍读不出来，声明属实与否由作者负责。", file=sys.stderr)
        return 0

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
