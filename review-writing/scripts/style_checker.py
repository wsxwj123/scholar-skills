#!/usr/bin/env python3
"""Anti-AI style checker for literature reviews (review-writing variant).

Adapted from general-sci-writing/scripts/style_checker.py. Differences:
- Default input dir is `drafts` (review-writing drafts/section_XX_XX.md), not `manuscripts`.
- Passive voice target is the REVIEW threshold (<=30%), not the research-paper 50-70%.
  Reviews are written in a more active, synthesis-driven voice; >30% passive flags stiffness.
  Configurable via --passive-max (default 0.30).
- Adds a long-sentence check (single sentence >30 words) to back DoD item R5.

Measures:
- Sentence length variance (Perplexity/Burstiness)
- Passive voice ratio (review target <=30%)
- Long sentences (>30 words)
- Forbidden word/phrase hits
- Paragraph opening repetition
- Consecutive similar-length sentences
- Decorative em-dash / scare quotes / explanatory colon / trailing -ing clause

Outputs a JSON report with per-file and aggregate scores.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any


def is_merged_derivative(path: str) -> bool:
    """True for merge_manuscript.py outputs (Full_Manuscript.md / Draft_Round*_Manuscript.md).
    These carry the AUTO-GENERATED banner and duplicate the atomic sources, so
    scanning them produces false positives (e.g. banner em-dash)."""
    name = os.path.basename(path).lower()
    return name == "full_manuscript.md" or (name.startswith("draft_round") and name.endswith("_manuscript.md"))


# ── Forbidden words/phrases (AI-typical) ──────────────────────────────────────
FORBIDDEN_EXACT = {
    "delve into", "comprehensive landscape", "pivotal role", "realm",
    "tapestry", "underscore", "testament", "it is well known",
    "it is worth noting", "it should be noted", "importantly",
    "interestingly", "remarkably", "notably", "in recent years",
    "a growing body of evidence", "has garnered significant attention",
    "plays a crucial role", "a plethora of", "myriad of",
    "in the context of", "shed light on", "pave the way",
    "of paramount importance", "a key player",
}
FORBIDDEN_PATTERNS = [
    re.compile(r"not only\b.*?\bbut also\b", re.IGNORECASE),
    re.compile(r"seamless[,\s]+intuitive[,\s]+and\s+powerful", re.IGNORECASE),
    # NOTE: removed `from\s+\w+\s+to\s+\w+` ("from X to Y"). In scientific reviews
    # this construction is high-frequency and legitimate ("from gut to joint",
    # "from adipogenic to osteogenic differentiation"); the false-positive rate
    # made the signal-to-noise ratio too poor to keep as an AI-rhetoric flag.
]

# ── Anti-AI: em-dash, scare quotes, explanatory colon ────────────────────────
# Em-dash (U+2014 —) used decoratively in prose (not in code/URLs/math).
EM_DASH_RE = re.compile(r"(?<!\d)—(?!\d)")
# Scare quotes: double-quoted phrase of 1-4 words not preceded by numeric citation
# context, to catch "synergistic", "perfect storm", etc.
SCARE_QUOTE_RE = re.compile(r'(?<!\[)(?<!\d)"([A-Za-z][^"]{1,40})"(?!\s*:)')
# Explanatory colon: "NounPhrase: Explanation" pattern in prose.
# Matches: Title-case phrase (1-4 words) followed by ": " then another capital+lower word.
# Excludes: digit before colon (ratio/time), all-caps acronym before colon.
EXPLANATORY_COLON_RE = re.compile(
    r"(?<!\d)([A-Z][a-z]{2,}(?:\s[A-Za-z][a-z]{1,}){0,3})\s*:\s+[A-Za-z][a-z]"
)

# ── Trailing participial clause (禁 -ing 分词悬垂从句) ──────────────────────
# Matches: ", <verb>ing" at end of sentence where verb is a common AI-typical
# commentary participle. Only triggers on sentence-final position.
TRAILING_ING_VERBS = (
    r"reflecting|ensuring|highlighting|demonstrating|symbolizing|underscoring"
    r"|suggesting|indicating|revealing|confirming|emphasizing|illustrating"
    r"|showing|proving|signifying|supporting|implying"
)
TRAILING_ING_RE = re.compile(
    rf",\s+(?:{TRAILING_ING_VERBS})\s+[a-z]",
    re.IGNORECASE,
)

# ── Passive voice detection (simplified) ──────────────────────────────────────
_BE_FORMS = r"(?:is|are|was|were|been|being|be)"
_PAST_PARTICIPLE = r"(?:[a-z]+ed|[a-z]+en|[a-z]+t)\b"
PASSIVE_RE = re.compile(
    rf"\b{_BE_FORMS}\s+(?:\w+\s+)?{_PAST_PARTICIPLE}",
    re.IGNORECASE,
)

# ── Sentence splitting ────────────────────────────────────────────────────────
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[])")

# ── Reference/figure/heading filters ─────────────────────────────────────────
# Reference list lines. Matches both the Vancouver numbered format
# ("1. Author A, ... 2020") and the bullet format used in review drafts
# ("- [168] Author A, ... 2020" / "* [12] ...").
REF_LINE_RE = re.compile(
    r"^(?:\d+\.\s+\w+.*?\d{4}"          # 1. Author...2020
    r"|[-*]\s+\[\d+\].*?\d{4})",        # - [168] Author...2020
    re.MULTILINE,
)
HEADING_RE = re.compile(r"^#+\s+", re.MULTILINE)
# Heading text (after stripping leading #/space) that marks a reference section.
REF_HEADING_RE = re.compile(r"^(?:References|参考文献|Bibliography)", re.IGNORECASE)
FIGURE_LEGEND_RE = re.compile(r"^(?:Figure|Fig\.?|Table)\s+\d", re.IGNORECASE | re.MULTILINE)
CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
CITATION_RE = re.compile(r"\[\d+(?:[,\-\s]*\d+)*\]")


def _extract_prose(text: str) -> str:
    """Strip non-prose elements from manuscript markdown."""
    text = CODE_BLOCK_RE.sub("", text)
    lines = text.splitlines()  # 跨平台：兼容 \r\n/\r 换行
    prose_lines = []
    in_ref_block = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            # Keep in_ref_block as-is: a reference section commonly has blank
            # lines between entries. The block is closed only by a non-ref
            # heading (see HEADING branch), not by an empty line.
            prose_lines.append("")
            continue
        if HEADING_RE.match(stripped):
            # A "## References"/"参考文献"/"Bibliography" heading opens the ref
            # block; any other heading closes it. Without this, the heading
            # branch swallowed "## References" first and the dedicated
            # `^(References|参考文献)` check below never fired.
            heading_text = HEADING_RE.sub("", stripped, count=1).strip()
            if REF_HEADING_RE.match(heading_text):
                in_ref_block = True
            else:
                in_ref_block = False
            continue
        if stripped.startswith("---"):
            continue
        if FIGURE_LEGEND_RE.match(stripped):
            continue
        if re.match(r"^(References|参考文献)", stripped, re.IGNORECASE):
            in_ref_block = True
            continue
        if in_ref_block and REF_LINE_RE.match(stripped):
            continue
        if in_ref_block and not stripped:
            in_ref_block = False
            continue
        prose_lines.append(line)
    return "\n".join(prose_lines)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    text = CITATION_RE.sub("", text)  # remove [n] before splitting
    raw = SENTENCE_RE.split(text)
    return [s.strip() for s in raw if s.strip() and len(s.split()) >= 3]


def _word_count(sentence: str) -> int:
    return len(sentence.split())


def check_file(filepath: str, passive_max: float = 0.30) -> dict[str, Any]:
    """Run all checks on a single review draft file.

    passive_max: maximum acceptable passive-voice ratio (review default 0.30).
    """
    with open(filepath, "r", encoding="utf-8") as f:
        raw_text = f.read()

    prose = _extract_prose(raw_text)
    sentences = _split_sentences(prose)
    paragraphs = [p.strip() for p in prose.split("\n\n") if p.strip() and len(p.split()) >= 10]

    total_words = sum(_word_count(s) for s in sentences)
    result: dict[str, Any] = {
        "file": os.path.basename(filepath),
        "total_sentences": len(sentences),
        "total_words": total_words,
        "issues": [],
        "hard_fail": False,  # 硬门禁命中（如破折号）：无论分数一律 fail-close
    }

    if not sentences:
        result["score"] = 100
        return result

    # ── 1. Sentence length variance (P/B check) ──────────────────────────────
    lengths = [_word_count(s) for s in sentences]
    mean_len = sum(lengths) / len(lengths)
    variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
    std_dev = math.sqrt(variance)
    cv = std_dev / mean_len if mean_len > 0 else 0  # coefficient of variation

    result["sentence_stats"] = {
        "mean_length": round(mean_len, 1),
        "std_dev": round(std_dev, 1),
        "cv": round(cv, 3),
        "min": min(lengths),
        "max": max(lengths),
    }

    if cv < 0.25 and len(sentences) >= 5:
        result["issues"].append({
            "type": "low_sentence_variance",
            "severity": "high",
            "detail": f"CV={cv:.3f} (target: ≥0.35). Sentences too uniform — typical AI pattern.",
        })

    # ── 2. Consecutive similar-length sentences ──────────────────────────────
    consec_similar = 0
    max_consec = 0
    for i in range(1, len(lengths)):
        if abs(lengths[i] - lengths[i - 1]) < 5:
            consec_similar += 1
            max_consec = max(max_consec, consec_similar)
        else:
            consec_similar = 0

    if max_consec >= 3:
        result["issues"].append({
            "type": "consecutive_similar_length",
            "severity": "medium",
            "detail": f"{max_consec + 1} consecutive sentences with <5 word difference.",
        })

    # ── 3. Passive voice ratio ────────────────────────────────────────────────
    # Review style (DoD R5): passive <= passive_max (default 30%). Reviews favor
    # an active, synthesis-driven voice; excess passive reads stiff. No lower bound.
    passive_count = sum(1 for s in sentences if PASSIVE_RE.search(s))
    passive_ratio = passive_count / len(sentences) if sentences else 0
    result["passive_ratio"] = round(passive_ratio, 3)

    if passive_ratio > passive_max:
        result["issues"].append({
            "type": "excessive_passive_voice",
            "severity": "info",  # 软提示：报告但不阻断、不扣分（见 SOFT_ISSUE_TYPES）
            "detail": f"Passive ratio {passive_ratio:.1%} (soft guide: <={passive_max:.0%}). Consider trimming passive constructions.",
        })

    # ── 3b. Long sentences (>30 words) ────────────────────────────────────────
    # 软提示：单句 >30 词只提醒不阻断（节奏建议，非硬门）。
    long_sentences = [(i, l) for i, l in enumerate(lengths) if l > 30]
    if long_sentences:
        result["issues"].append({
            "type": "long_sentence",
            "severity": "info",
            "detail": (
                f"{len(long_sentences)} sentence(s) exceed 30 words "
                f"(max={max(l for _, l in long_sentences)}). Consider splitting for rhythm."
            ),
        })

    # ── 4. Forbidden words/phrases ────────────────────────────────────────────
    forbidden_hits: list[dict[str, str]] = []
    lower_prose = prose.lower()
    for phrase in FORBIDDEN_EXACT:
        if phrase in lower_prose:
            forbidden_hits.append({"phrase": phrase, "type": "forbidden_word"})
    for pat in FORBIDDEN_PATTERNS:
        if pat.search(prose):
            forbidden_hits.append({"phrase": pat.pattern[:50], "type": "forbidden_pattern"})

    result["forbidden_hits"] = forbidden_hits
    if forbidden_hits:
        result["issues"].append({
            "type": "forbidden_ai_phrases",
            "severity": "high",
            "detail": f"{len(forbidden_hits)} AI-typical phrases detected: {', '.join(h['phrase'] for h in forbidden_hits[:5])}",
        })

    # ── 5. Paragraph opening repetition ───────────────────────────────────────
    openers = []
    for para in paragraphs:
        first_sentence = SENTENCE_RE.split(para)[0].strip() if para else ""
        # Extract first 3 words as structural pattern
        words = first_sentence.split()[:3]
        if len(words) >= 2:
            openers.append(" ".join(words).lower())

    repeated_openers: list[str] = []
    for i in range(1, len(openers)):
        if openers[i] == openers[i - 1]:
            if openers[i] not in repeated_openers:
                repeated_openers.append(openers[i])

    if repeated_openers:
        result["issues"].append({
            "type": "repeated_paragraph_openers",
            "severity": "medium",
            "detail": f"Consecutive paragraphs start the same way: {', '.join(repeated_openers[:3])}",
        })

    # ── 6. Bullet point check (正文禁用) ─────────────────────────────────────
    # Exclude Vancouver-style reference lines (number. AuthorText YYYY) from
    # the numbered-list count — _extract_prose strips the References section
    # only when headed by a markdown heading; fallback: skip lines that look
    # like bibliography entries (contain a 4-digit year).
    bullet_lines = re.findall(r"^[\s]*[-*]\s+\w", prose, re.MULTILINE)
    _all_numbered = re.findall(r"^[\s]*\d+\.\s+.+", prose, re.MULTILINE)
    _ref_like = re.compile(r"\b(19|20)\d{2}\b")
    numbered_lines = [ln for ln in _all_numbered if not _ref_like.search(ln)]
    bullet_count = len(bullet_lines) + len(numbered_lines)
    if bullet_count > 0:
        result["issues"].append({
            "type": "bullet_points_in_prose",
            "severity": "high",
            "detail": f"{bullet_count} bullet/numbered list lines detected in prose body.",
        })

    # ── 7. Decorative em-dash (硬门禁, 禁止使用) ─────────────────────────────
    em_dash_count = len(EM_DASH_RE.findall(prose))
    if em_dash_count >= 1:
        result["issues"].append({
            "type": "decorative_em_dash",
            "severity": "high",  # 硬门禁：破折号禁止使用，计入 score 并置 hard_fail
            "detail": f"{em_dash_count} em-dash(es) (—/——) detected. 禁止使用破折号(硬门禁)，用逗号/句号/重构替代。",
        })
        result["hard_fail"] = True

    # ── 8. Scare quotes (硬门禁, 禁止使用: 引号暗示新概念) ─────────────────────
    # 去AI必禁三项之一。与破折号同级：命中即 hard_fail 一票否决，不放行。
    scare_hits = SCARE_QUOTE_RE.findall(prose)
    # Filter obvious false positives: ALL CAPS acronyms, or phrases ≥5 words
    scare_hits = [h for h in scare_hits if len(h.split()) <= 4 and not h.isupper()]
    if len(scare_hits) >= 1:
        result["issues"].append({
            "type": "scare_quotes",
            "severity": "high",
            "detail": f"{len(scare_hits)} likely scare-quote phrase(s): {', '.join(repr(h) for h in scare_hits[:3])}. 禁止使用 scare quotes(硬门禁)，除非直接引用或已固化术语。",
        })
        result["hard_fail"] = True

    # ── 9. Explanatory colon in prose (硬门禁, 禁止使用: 解释性冒号) ────────────
    # 去AI必禁三项之一。与破折号同级：命中即 hard_fail 一票否决，不放行。
    expl_colon_hits = EXPLANATORY_COLON_RE.findall(prose)
    if len(expl_colon_hits) >= 1:
        result["issues"].append({
            "type": "explanatory_colon_in_prose",
            "severity": "high",
            "detail": f"{len(expl_colon_hits)} possible explanatory colon(s): {', '.join(repr(h) for h in expl_colon_hits[:3])}. 禁止使用解释性冒号(硬门禁)，改写为从句。",
        })
        result["hard_fail"] = True

    # ── 10. Trailing -ing participial clause (禁 -ing 分词悬垂从句) ──────────
    # Sentence-final ", reflecting/demonstrating/suggesting/..." is a hallmark
    # AI pattern. We scan each sentence for the pattern.
    trailing_ing_hits: list[str] = []
    for sent in sentences:
        m = TRAILING_ING_RE.search(sent)
        if m:
            trailing_ing_hits.append(sent[:80])
    if trailing_ing_hits:
        result["issues"].append({
            "type": "trailing_ing_clause",
            "severity": "medium",
            "detail": (
                f"{len(trailing_ing_hits)} trailing participial clause(s) detected "
                f"(e.g. ', reflecting/demonstrating/suggesting …'). "
                f"Rewrite as a new sentence. First hit: {repr(trailing_ing_hits[0])}"
            ),
        })

    # ── Score calculation ─────────────────────────────────────────────────────
    # severity == "info" 为软提示（长句 / 被动比例等），只报告不扣分、不影响 gate 通过。
    # 破折号是硬门禁（severity=high 计分 + hard_fail 一票否决）。high/medium/low 仍计分。
    score = 100
    for issue in result["issues"]:
        sev = issue["severity"]
        if sev == "info":
            continue
        if sev == "high":
            score -= 15
        elif sev == "medium":
            score -= 8
        else:
            score -= 3
    result["score"] = max(0, score)

    return result


def main() -> int:
    p = argparse.ArgumentParser(description="Anti-AI style checker for review drafts")
    p.add_argument("--manuscript-dir", "--drafts-dir", dest="manuscript_dir",
                   default="drafts", help="Directory with review draft .md files")
    p.add_argument("--file", default="", help="Check a single file instead of directory")
    p.add_argument("--report", default="data/style_check_report.json", help="Output report path")
    p.add_argument("--threshold", type=int, default=70, help="Minimum passing score")
    p.add_argument("--passive-max", type=float, default=0.30,
                   help="Max acceptable passive-voice ratio (review default 0.30)")
    args = p.parse_args()

    files: list[str] = []
    if args.file:
        files = [args.file]
    elif os.path.isdir(args.manuscript_dir):
        files = sorted(glob.glob(os.path.join(args.manuscript_dir, "*.md")))
        # Skip merge-generated derivatives (carry the AUTO-GENERATED banner;
        # double-scanning them and the banner em-dash cause false positives).
        files = [f for f in files if not is_merged_derivative(f)]

    if not files:
        print(json.dumps({"ok": True, "message": "No manuscript files found", "files": []}))
        return 0

    results = [check_file(f, passive_max=args.passive_max) for f in files]
    scores = [r["score"] for r in results]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 100
    any_hard_fail = any(r.get("hard_fail") for r in results)  # 破折号等硬门禁：一票否决
    all_pass = all(s >= args.threshold for s in scores) and not any_hard_fail
    total_issues = sum(len(r["issues"]) for r in results)

    report = {
        "ok": all_pass,
        "avg_score": avg_score,
        "threshold": args.threshold,
        "files_checked": len(results),
        "total_issues": total_issues,
        "files": results,
    }

    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": all_pass, "avg_score": avg_score, "total_issues": total_issues, "files_checked": len(results)}))
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
