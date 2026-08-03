#!/usr/bin/env python3
"""跨平台替代 Phase 4 的两条 bash 专用命令（PowerShell 下原命令产假数据 / 崩）。

替掉的两处（SKILL.md Phase 4）：
  Step 4  `cat drafts/section_*.md > exports/Final_Review.md`
          → PowerShell 5.1 的 `>` 默认写 UTF-16LE，下游 consolidate_references /
            structure_outline / export_docx 全是 read_text(encoding='utf-8')，
            直接 UnicodeDecodeError，Phase 4 从 4a 起全线崩。
  Step 4d `{ grep -E '^##[[:space:]]*Figure…' figures/figure_index.md; cat … ; } > tmp/xref_corpus.md`
          → PowerShell 无 grep / 无 `[[:space:]]` / 无 `{ …; }` 分组。**不是崩，是静默产假
            数据**：按 SKILL.md 的错误契约「grep 空匹配 exit 1 属正常、不得中断本步」，
            grep 不存在时语料退化成纯正文 → 每张注册图都判悬空 = 100% 系统性假阳。

CLI:
  python3 scripts/compile_manuscript.py merge       [--drafts-dir drafts] [--out exports/Final_Review.md]
  python3 scripts/compile_manuscript.py xref-corpus [--figure-index figures/figure_index.md]
                                                    [--body exports/Final_Review.md]
                                                    [--out tmp/xref_corpus.md]

退出码：0 正常（含 figure_index.md 缺失的退化态）/ 1 输入缺失（Final_Review.md 不在 =
流程错序）/ 2 用法错。stdlib-only、纯 pathlib，输出一律 UTF-8 无 BOM。
"""
from __future__ import annotations

import sys as _sys
try:  # Windows GBK 控制台/管道捕获下 emoji print 防 UnicodeEncodeError
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import argparse
import re
import sys
from pathlib import Path

# 注册标题行：行首 `##` + Figure + 编号 + 分隔符。分隔符类**必须含全角冒号**——
# `## Figure 0：概念框架图` 这类注册行若被筛掉就根本进不了语料，而 Figure 0 是要求
# 每节都引的框架图，一条写歪的注册行会稳定产一条假阳（SKILL.md Step 4d ① 已说明）。
# 与 bash 侧 `grep -E '^##[[:space:]]*Figure[[:space:]]*[0-9]+[[:space:]]*[.:：]'` 同形态。
CAPTION_LINE_RE = re.compile(r"^##[ \t]*Figure[ \t]*[0-9]+[ \t]*[.:：]")
# N 的计数口径（SKILL.md 写死）：所有 `^##` 开头且含 Figure + 数字的注册标题行，
# 不论用什么分隔符（含 `-`、破折号、无分隔符等一切写法）。
REGISTERED_RE = re.compile(r"^##.*Figure.*[0-9]")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # newline="" 防 Windows 上把 \n 翻成 \r\n（成稿字节要能逐字节比对）；UTF-8 无 BOM。
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def _section_sort_key(p: Path):
    """按文件名里的数字段排序，zero-pad 与非 pad 混用时也能排对。

    section_01_01.md → (1, 1)；section_2_10.md → (2, 10)。无数字的排最后（按名）。
    """
    nums = [int(x) for x in re.findall(r"\d+", p.stem)]
    return (0, nums, p.name) if nums else (1, [], p.name)


def cmd_merge(args: argparse.Namespace) -> int:
    drafts = Path(args.drafts_dir)
    if not drafts.is_dir():
        sys.stderr.write(f"[compile_manuscript] drafts 目录不存在: {drafts}\n")
        return 1
    files = sorted(drafts.glob("section_*.md"), key=_section_sort_key)
    if not files:
        sys.stderr.write(f"[compile_manuscript] {drafts} 下没有 section_*.md，无可合并内容\n")
        return 1
    _write(Path(args.out), "".join(_read(f) for f in files))
    print(f"✅ 合并 {len(files)} 节 → {args.out}（UTF-8 无 BOM）")
    for f in files:
        print(f"   {f.name}")
    return 0


def cmd_xref_corpus(args: argparse.Namespace) -> int:
    body = Path(args.body)
    if not body.is_file():
        # 成稿缺失 = Step 4 还没跑，属流程错序：报错并停，绝不产空语料静默通过。
        sys.stderr.write(
            f"[compile_manuscript] 成稿不存在: {body}（Step 4 编译还没跑？先跑 merge）\n")
        return 1

    fig_index = Path(args.figure_index)
    caption_lines: list[str] = []
    registered: list[str] = []
    if fig_index.is_file():
        for raw in _read(fig_index).splitlines():
            if REGISTERED_RE.match(raw):
                registered.append(raw)
            if CAPTION_LINE_RE.match(raw):
                caption_lines.append(raw)
    # figure_index.md 缺失 → 语料退化为纯正文，**不报错**（图类会因锚不可用整类 skip）。

    prefix = "".join(ln + "\n" for ln in caption_lines)
    _write(Path(args.out), prefix + _read(body))

    n, m = len(registered), len(caption_lines)
    print(f"✅ 语料 → {args.out}（注册 {n} 条、进锚 {m} 条）")
    if n > m:
        # 差的那 N−M 条逐条列出原行，让用户看得见哪一行写歪了。
        missed = [ln for ln in registered if ln not in caption_lines]
        print(f"⚠️ advisory: {n - m} 条注册行未进语料，按 `## Figure N: Title` 模板修正：")
        for ln in missed:
            print(f"   {ln}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 4 跨平台编译助手（替 bash 专用的 cat / grep 合并）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_merge = sub.add_parser("merge", help="按节次顺序合并 drafts/section_*.md → 成稿（强制 UTF-8）")
    p_merge.add_argument("--drafts-dir", default="drafts")
    p_merge.add_argument("--out", default="exports/Final_Review.md")
    p_merge.set_defaults(func=cmd_merge)

    p_x = sub.add_parser("xref-corpus", help="图注册标题行 + 成稿 → tmp/xref_corpus.md")
    p_x.add_argument("--figure-index", default="figures/figure_index.md")
    # 参数名刻意不叫 --manuscript：4d 的 structure_outline 也有个 --manuscript，
    # 且它**只准指向 tmp/xref_corpus.md**（指成稿=100% 系统性假阳）。两个同名参数
    # 挨在同一段文档里，抄错一次就是整批假阳，故这里用 --body 与之区分。
    p_x.add_argument("--body", default="exports/Final_Review.md",
                     help="要拼在题注之后的成稿（Step 4 merge 的产物）")
    p_x.add_argument("--out", default="tmp/xref_corpus.md")
    p_x.set_defaults(func=cmd_xref_corpus)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
