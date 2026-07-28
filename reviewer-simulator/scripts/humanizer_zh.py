#!/usr/bin/env python3
"""Anti-AI Chinese style checks for nsfc-proposal."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

BANNED_PATTERNS = [
    # 禁用句式（AI模板句）
    (r"不是[^。]{1,30}?而是", "pattern_not_but", "改为直接陈述句，避免对比模板"),
    (r"不仅[^。，]{1,30}?[，,][^。]{1,30}?而且", "pattern_not_only_but_also", "拆成两句事实陈述"),
    (r"值得注意的是", "filler_phrase", "删除该提示语，直接给结论"),
    (r"需要指出的是", "filler_phrase", "删除该提示语，直接给证据"),
    # 空洞修饰词
    (r"至关重要|举足轻重|不可或缺", "overstatement", "用具体数据替代形容词"),
    (r"具有重要的[^。]{0,20}意义和[^。]{0,20}价值", "generic_significance", "删除或改写为具体贡献陈述"),
    # 新闻体/套话
    (r"日益增长|蓬勃发展|方兴未艾", "news_style", "替换为具体数据或趋势描述"),
    # 空洞动词
    (r"深入探讨|系统研究|全面分析", "hollow_verb", "改为具体研究行为描述，如'比较X与Y的差异'"),
    # 机械过渡
    (r"综上所述|总而言之", "template_transition", "用事实句结束段落"),
    (r"在此基础上|鉴于此", "ai_transition", "直接写因果关系"),
    # 禁用修辞：比喻
    (r"的桥梁|的基石|的钥匙|的引擎", "metaphor_rhetoric", "直接陈述其功能或作用"),
    # 禁用修辞：夸张
    (r"革命性的|颠覆性的|突破性的", "hyperbole_rhetoric", "用数据/事实说明程度"),
    # 禁用修辞：排比（"...是A，是B，更是C"）
    (r"是[^，。]{1,20}，是[^，。]{1,20}，更是", "parallelism_rhetoric", "用一个精准表述替代排比"),
    # 禁用修辞：反问
    (r"难道不是[^？]{0,30}？", "rhetorical_question", "改为陈述句"),
    # 禁用修辞：设问
    (r"那么，[^？]{1,30}？", "leading_question", "直接阐述，删除设问"),
]

VAGUE_PATTERNS = [
    (r"近年来", "replace_with_exact_year_range", "改为具体年份范围，如2020年以来"),
    (r"大量研究表明", "replace_with_named_citations", "改为明确作者+文献编号"),
    (r"取得了显著进展", "replace_with_specific_progress", "改为具体进展内容"),
    (r"广泛应用", "replace_with_specific_scenarios", "列出应用场景"),
    (r"越来越多的证据", "replace_with_specific_evidence", "具体引用几项关键证据"),
    (r"已有研究发现", "replace_with_named_researcher", "指明具体研究者和发现"),
]

BULLET_PATTERNS = [
    (r"^\s*[\-\*•]\s", "bullet_list", "改为段落叙述"),
    (r"^\s*\d+[\.)]\s", "numbered_list", "改为段落叙述"),
    (r"^\s*[（\(][一二三四五六七八九十\d]+[）\)]", "cn_numbered_list", "改为段落叙述"),
]

# ── 新增三项检查 ──────────────────────────────────────────────────────────

# B1：装饰性破折号（——用于停顿/补充/强调，而非化学名称连字符）
# 匹配中文"——"前后有文字内容（即不是列表/标题边界），排除行首破折号（标题装饰）。
# 检测策略：——前面有中文字符，视为装饰性停顿
DASH_PATTERN = (
    r"[一-鿿\w][^。！？\n]{0,40}——[^。！？\n]{1,}",
    "decorative_dash",
    "删除——，改写为完整句子或分号连接",
)

# B2：scare quotes（引号包裹非术语短语暗示新概念/反讽）
# 策略：检测"X"或'X'中X为2-8个字、全为中文（非英文字母缩写/固化术语的典型长度），
# 且引号前无"即"/"称为"/"叫做"（术语首次定义标记），排除数字/年份。
# 注意：启发式，存在误报可能，仅检测最明显的情形。
SCARE_QUOTE_PATTERN = (
    r'(?<!即)(?<!称为)(?<!叫做)["""][一-鿿]{2,8}["""]',
    "scare_quotes",
    "直接使用术语，或用'X（英文Y）'格式首次定义；引号暗示反讽时改用直陈句",
)

# B3：解释性冒号（"概念：解释"装饰句式）
# 合法冒号：比例（3:1）、列表引导（以下几点：）、标题后（结论：）、时间（08:00）
# 检测：冒号前有2-10个中文字（非数字），冒号后紧跟中文正文（非换行/列表）
# 排除：行尾冒号（列表引导）、数字前（时间/比例）
EXPLANATORY_COLON_PATTERN = (
    r"[一-鿿]{2,10}：[一-鿿][^：\n]{5,}",
    "explanatory_colon",
    "将'概念：解释'改为'概念是指X'或融入句子，冒号仅用于列表引导/标题/比例",
)


def scan_text(text: str, allow_lists: bool = False) -> dict:
    issues = []

    for pattern, code, suggestion in BANNED_PATTERNS:
        for m in re.finditer(pattern, text):
            issues.append(
                {
                    "severity": "ERROR",
                    "code": code,
                    "span": [m.start(), m.end()],
                    "text": m.group(0),
                    "suggestion": suggestion,
                }
            )

    for pattern, code, suggestion in VAGUE_PATTERNS:
        for m in re.finditer(pattern, text):
            issues.append(
                {
                    "severity": "WARNING",
                    "code": code,
                    "span": [m.start(), m.end()],
                    "text": m.group(0),
                    "suggestion": suggestion,
                }
            )

    if not allow_lists:
        for i, line in enumerate(text.splitlines(), 1):
            for pattern, code, suggestion in BULLET_PATTERNS:
                if re.search(pattern, line):
                    issues.append(
                        {
                            "severity": "WARNING",
                            "code": code,
                            "line": i,
                            "text": line.strip(),
                            "suggestion": suggestion,
                        }
                    )

    # B1：装饰性破折号（硬门禁，禁止使用：severity=ERROR，命中即阻断）
    for m in re.finditer(DASH_PATTERN[0], text):
        issues.append(
            {
                "severity": "ERROR",
                "code": DASH_PATTERN[1],
                "span": [m.start(), m.end()],
                "text": m.group(0),
                "suggestion": DASH_PATTERN[2],
            }
        )

    # B2：scare quotes（硬门禁，禁止使用：severity=ERROR，命中即阻断；启发式，可能有少量误报）
    for m in re.finditer(SCARE_QUOTE_PATTERN[0], text):
        issues.append(
            {
                "severity": "ERROR",
                "code": SCARE_QUOTE_PATTERN[1],
                "span": [m.start(), m.end()],
                "text": m.group(0),
                "suggestion": SCARE_QUOTE_PATTERN[2],
            }
        )

    # B3：解释性冒号（跳过行首，避免误杀标题）
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        # 排除：标题行（以#开头）、纯列表/表格行、行尾冒号（列表引导）
        if stripped.startswith("#") or stripped.endswith("：") or stripped.endswith(":"):
            continue
        for m in re.finditer(EXPLANATORY_COLON_PATTERN[0], stripped):
            # 排除数字比例（如 3：1）和时间格式
            before_colon = stripped[: m.start() + m.group(0).index("：")]
            if re.search(r"\d$", before_colon):
                continue
            issues.append(
                {
                    "severity": "ERROR",
                    "code": EXPLANATORY_COLON_PATTERN[1],
                    "line": i,
                    "span": [m.start(), m.end()],
                    "text": m.group(0),
                    "suggestion": EXPLANATORY_COLON_PATTERN[2],
                }
            )

    return {"count": len(issues), "issues": issues}


def _count_cn_chars(s: str) -> int:
    """计算字符串中中文字符数（用于句长硬上限判断）。"""
    return sum(1 for c in s if "一" <= c <= "鿿")


def rhythm_check(text: str) -> dict:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    issues = []
    openers = []

    for idx, para in enumerate(paragraphs, 1):
        sents = [s for s in re.split(r"[。！？!?]", para) if s.strip()]
        lens = [len(s.strip()) for s in sents]

        # ── 中文句长硬上限（≤50 中文字符）────────────────────────────────
        for sent_idx, sent in enumerate(sents, 1):
            cn_len = _count_cn_chars(sent)
            if cn_len > 50:
                issues.append(
                    {
                        "paragraph": idx,
                        "sentence": sent_idx,
                        "type": "cn_sentence_too_long",
                        "cn_chars": cn_len,
                        "text": sent.strip()[:60] + ("…" if len(sent.strip()) > 60 else ""),
                        "suggestion": "中文单句超50字，拆分为两句或精简从句（目标≤50中文字符）",
                    }
                )

        # ── 连续3句长度差异 <5字（节奏单调）────────────────────────────
        for j in range(len(lens) - 2):
            window = lens[j : j + 3]
            if max(window) - min(window) < 5:
                issues.append({"paragraph": idx, "type": "flat_rhythm", "window": [j + 1, j + 3]})
        openers.append(para[:12])

    for i in range(len(openers) - 1):
        if openers[i] and openers[i] == openers[i + 1]:
            issues.append({"paragraph": i + 1, "type": "repeated_opener", "next_paragraph": i + 2, "text": openers[i]})

    return {"count": len(issues), "issues": issues}


def fix_suggest(text: str, allow_lists: bool = False) -> dict:
    scan = scan_text(text, allow_lists=allow_lists)
    suggestions = []
    for i in scan["issues"]:
        suggestions.append(
            {
                "code": i["code"],
                "original": i.get("text", ""),
                "suggestion": i.get("suggestion", ""),
            }
        )
    return {"count": len(suggestions), "suggestions": suggestions}


def scan_file(path: Path, allow_lists: bool = False) -> dict:
    text = path.read_text(encoding="utf-8")
    return {
        "path": str(path),
        "scan": scan_text(text, allow_lists=allow_lists),
        "rhythm": rhythm_check(text),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan")
    p_scan.add_argument("path")
    p_scan.add_argument("--allow-lists", action="store_true")

    p_scan_all = sub.add_parser("scan-all")
    p_scan_all.add_argument("sections_dir", nargs="?", default="sections")
    p_scan_all.add_argument("--allow-lists", action="store_true")

    p_fix = sub.add_parser("fix-suggest")
    p_fix.add_argument("path")
    p_fix.add_argument("--allow-lists", action="store_true")

    p_rhythm = sub.add_parser("rhythm-check")
    p_rhythm.add_argument("path")

    args = parser.parse_args()

    if args.cmd == "scan":
        print(json.dumps(scan_file(Path(args.path), allow_lists=args.allow_lists), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "scan-all":
        out = []
        for p in sorted(Path(args.sections_dir).glob("*.md")):
            allow = args.allow_lists or p.name.startswith("P3_3") or p.name.startswith("P3_4") or p.name.startswith("P4_")
            out.append(scan_file(p, allow_lists=allow))
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "fix-suggest":
        text = Path(args.path).read_text(encoding="utf-8")
        print(json.dumps(fix_suggest(text, allow_lists=args.allow_lists), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "rhythm-check":
        text = Path(args.path).read_text(encoding="utf-8")
        print(json.dumps(rhythm_check(text), ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
