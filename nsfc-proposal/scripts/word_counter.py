#!/usr/bin/env python3
"""Word and page counting helpers for nsfc-proposal."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

HAN_RE = re.compile(r"[\u4e00-\u9fff]")
EN_RE = re.compile(r"[A-Za-z0-9_]+")


def count_text(text: str) -> int:
    han = len(HAN_RE.findall(text))
    en = len(EN_RE.findall(text))
    punct = len([c for c in text if c.strip() and not HAN_RE.match(c) and not c.isalnum() and c != "_"])
    return han + en + punct


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

    args = parser.parse_args()

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
