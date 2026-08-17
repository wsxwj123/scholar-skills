#!/usr/bin/env python3
"""Word and page counting helpers for nsfc-proposal."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 字数/页数硬上限——全仓唯一定义处（INTERFACE-round24 §1）。
# 键是 sections/ 下的 basename，与 structure_profile.chapters[].filename 同一把尺。
# 消费方一律经 resolve_word_limit / resolve_page_limit 取值，不许另抄数字。
# ---------------------------------------------------------------------------
NSFC_WORD_MAX = {
    "00_摘要_中文.md": 400,
    "00_摘要_英文.md": 300,
    "P3_4_完成基金项目情况.md": 500,
    "P4_其他需要说明的情况.md": 500,
}
NSFC_PAGE_MAX = 30

_WARN_LINE = "WORD_LIMIT: WARN structure_profile 不可用，本次按国自然默认上限"


def resolve_word_limit(root, filename):
    """字数上限解析（INTERFACE-round24 §2 九行判定表）。

    纯函数：绝不抛异常、绝不 sys.exit、绝不写文件。filename 是 sections/ 下的
    basename（传全路径不做归一化，按「表里查不到」处理）。
    返回 (limit, source)，source ∈ {"structure_profile", "nsfc_default", "unset"}。
    """
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.insert(0, here)
        import structure_profile
        prof = structure_profile.load(root)
    except Exception:
        # 行 9：读口不可用 → 按国自然默认全量执行，不静默、不崩（同 r23 WARN 方向）
        print(_WARN_LINE, file=sys.stderr)
        return NSFC_WORD_MAX.get(filename), "nsfc_default"
    chapters = prof.get("chapters") if isinstance(prof, dict) else None
    if not isinstance(chapters, list) or not chapters:
        # 行 1-3：无真源/坏/未确认/无 chapters 键（章节表不受管）→ 国自然默认
        if filename in NSFC_WORD_MAX:
            return NSFC_WORD_MAX[filename], "nsfc_default"
        return None, "unset"      # 行 8：表外文件无默认可用
    for ch in chapters:
        if isinstance(ch, dict) and ch.get("filename") == filename:
            wm = ch.get("word_max")
            if isinstance(wm, int) and not isinstance(wm, bool) and wm >= 0:
                return wm, "structure_profile"   # 行 4：word_max == 0 合法
            return None, "unset"  # 行 5/6：缺或非法 → 不判、交人工，绝不回落默认
    return None, "unset"          # 行 7：受管但没列该章


def resolve_page_limit(root):
    """页数上限解析（INTERFACE-round24 §3）。恒返回 (int, source)，永不为 None。

    考卷口径（优先于 INTERFACE §3 第 1 行字面）：声明值等于 NSFC_PAGE_MAX 时
    报 nsfc_default——DEFAULT_PROFILE 自带 page_limit=30，国自然默认项目不算「声明过」。
    """
    try:
        with open(os.path.join(str(root), "proposal_profile.json"), encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return NSFC_PAGE_MAX, "nsfc_default"
    pl = data.get("page_limit") if isinstance(data, dict) else None
    if isinstance(pl, int) and not isinstance(pl, bool) and pl >= 0:
        if pl == NSFC_PAGE_MAX:
            return NSFC_PAGE_MAX, "nsfc_default"
        return pl, "proposal_profile"   # 0 是合法声明（页数必超反例依赖它），不回落
    return NSFC_PAGE_MAX, "nsfc_default"


HAN_RE = re.compile(r"[\u4e00-\u9fff]")
EN_RE = re.compile(r"[A-Za-z0-9_]+")
# Markdown formatting symbols to strip before counting (not content)
MD_RE = re.compile(r"[*#`\[\]!>|~^{}=\-]")


def count_text(text: str) -> int:
    # Strip markdown formatting characters, then count:
    # - each Chinese character as 1 word (matches Word \u5b57\u6570\u7edf\u8ba1)
    # - each continuous English/digit token as 1 word
    # Punctuation (\uff0c\u3002\uff01\uff1fetc.) is NOT counted, matching Word behaviour
    clean = MD_RE.sub(" ", text)
    han = len(HAN_RE.findall(clean))
    en = len(EN_RE.findall(clean))
    return han + en


def count_file(path: Path) -> int:
    return count_text(path.read_text(encoding="utf-8"))


def count_all(sections_dir: Path, pattern: str = "*.md") -> dict[str, int]:
    result: dict[str, int] = {}
    for p in sorted(sections_dir.glob(pattern)):
        result[p.name] = count_file(p)
    result["__total__"] = sum(v for k, v in result.items() if not k.startswith("__"))
    return result


def estimate_pages(total_words: int, words_per_page: int = 800) -> int:
    return math.ceil(total_words / words_per_page) if total_words > 0 else 0


def summary(sections_dir: Path, pattern: str = "*.md", words_per_page: int = 800) -> dict:
    data = count_all(sections_dir, pattern)
    total = data["__total__"]
    pages = estimate_pages(total, words_per_page)
    items = [{"file": k, "words": v} for k, v in data.items() if not k.startswith("__")]
    items = sorted(items, key=lambda x: x["words"], reverse=True)
    return {
        "word_count": data,
        "page_estimate": pages,
        "top_sections": items[:5],
    }


def _run_check(args) -> int:
    """check 子命令（INTERFACE-round24 §4）：纯读 + 打印，不写任何文件。
    rc 与判定正交：超限/上限不可判都是 rc 0（单行 JSON）；目标读不出才 rc 1。"""
    if args.file is not None:
        target = args.file
        try:
            count = count_file(Path(target))
        except (OSError, ValueError) as e:
            print("WORD_LIMIT: MISSING %s: %s" % (target, str(e) or type(e).__name__),
                  file=sys.stderr)
            return 1
        limit, source = resolve_word_limit(args.root, os.path.basename(target))
        kind = "words"
    else:
        target = args.pages
        if not os.path.isdir(target):
            print("WORD_LIMIT: MISSING %s: FileNotFoundError" % target, file=sys.stderr)
            return 1
        count = estimate_pages(count_all(Path(target))["__total__"])
        limit, source = resolve_page_limit(args.root)
        kind = "pages"
    if source == "unset":
        print("WORD_LIMIT: UNSET %s 结构真源受管但该章未声明 word_max，"
              "本项须人工裁决，不得判 pass" % target, file=sys.stderr)
        print("处置：给 structure_profile.json 里该章补 word_max（须带 word_max_evidence），"
              "或本项人工核定。", file=sys.stderr)
    ok = None if limit is None else count <= limit
    print(json.dumps({"kind": kind, "target": target, "count": count,
                      "limit": limit, "limit_source": source, "ok": ok},
                     ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_count = sub.add_parser("count")
    p_count.add_argument("path")

    p_all = sub.add_parser("count-all")
    p_all.add_argument("sections_dir")
    p_all.add_argument("--pattern", default="*.md")

    p_pages = sub.add_parser("page-estimate")
    p_pages.add_argument("total_words", type=int)
    p_pages.add_argument("--words-per-page", type=int, default=800)

    p_summary = sub.add_parser("summary")
    p_summary.add_argument("sections_dir")
    p_summary.add_argument("--pattern", default="*.md")
    p_summary.add_argument("--words-per-page", type=int, default=800)

    p_check = sub.add_parser("check")
    p_check.add_argument("--root", required=True)
    grp = p_check.add_mutually_exclusive_group(required=True)
    grp.add_argument("--file")
    grp.add_argument("--pages")

    args = parser.parse_args()

    if args.cmd == "check":
        return _run_check(args)

    if args.cmd == "count":
        print(count_file(Path(args.path)))
        return 0

    if args.cmd == "count-all":
        print(json.dumps(count_all(Path(args.sections_dir), args.pattern), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "page-estimate":
        print(estimate_pages(args.total_words, args.words_per_page))
        return 0

    if args.cmd == "summary":
        print(json.dumps(summary(Path(args.sections_dir), args.pattern, args.words_per_page), ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
