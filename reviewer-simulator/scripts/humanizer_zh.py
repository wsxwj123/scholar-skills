#!/usr/bin/env python3
"""Anti-AI Chinese style checks for nsfc-proposal."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# round25 起共用正则条目收编进共享真源 scripts/ai_cliche_terms.py（vendored，开发
# 真源 _shared/，契约 .devflow/INTERFACE-round25.md）。rsim 不消费 EFFECTIVE_* 词表
# （本家没有套话字符串表），只取具名正则条目与 VAGUE_TABLE。
from ai_cliche_terms import (VAGUE_TABLE,  # noqa: E402
                             P_NOT_BUT, P_NOT_ONLY_BUT_ALSO, P_FILLER_NOTE, P_FILLER_POINT,
                             P_OVERSTATEMENT, P_GENERIC_SIGNIFICANCE, P_NEWS_STYLE,
                             P_HOLLOW_VERB, P_HYPERBOLE, P_PARALLELISM,
                             P_RHETORICAL_Q, P_LEADING_Q,
                             RSIM_TEMPLATE_TRANSITION, RSIM_AI_TRANSITION,
                             RSIM_METAPHOR_NOUN4)

# 条目改由共享真源具名常量拼装（内容逐字节同前）。🔴 排列顺序是本家口径：
# issues 数组顺序可观测，与 nsfc-proposal 的排列**不同是有意的**，不许对齐。
# 机械过渡两条在本家 1 次即 ERROR；nsfc 同正则走 OVERUSE ≥3 阈值（PLAN D10 有意差异）。
BANNED_PATTERNS = [
    # 禁用句式（AI模板句）
    P_NOT_BUT, P_NOT_ONLY_BUT_ALSO, P_FILLER_NOTE, P_FILLER_POINT,
    # 空洞修饰词
    P_OVERSTATEMENT, P_GENERIC_SIGNIFICANCE,
    # 新闻体/套话；空洞动词
    P_NEWS_STYLE, P_HOLLOW_VERB,
    # 机械过渡（本家 1 次即 ERROR）
    RSIM_TEMPLATE_TRANSITION, RSIM_AI_TRANSITION,
    # 禁用修辞：比喻（本家只 4 词名词式；nsfc 是动词式 8 词 + 名词式 12 词，D11 未裁决）
    RSIM_METAPHOR_NOUN4,
    # 禁用修辞：夸张；排比（"...是A，是B，更是C"）
    P_HYPERBOLE, P_PARALLELISM,
    # 禁用修辞：反问；设问
    P_RHETORICAL_Q, P_LEADING_Q,
]

# 6 条与 nsfc-proposal 逐字节共用，改由共享真源 VAGUE_TABLE 取。
VAGUE_PATTERNS = list(VAGUE_TABLE)

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
