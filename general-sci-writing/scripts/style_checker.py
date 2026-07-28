#!/usr/bin/env python3
"""Anti-AI style checker for scientific manuscripts.

Measures:
- Sentence length variance (Perplexity/Burstiness)
- Passive voice ratio
- Forbidden word/phrase hits
- Paragraph opening repetition
- Consecutive similar-length sentences

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
    re.compile(r"from\s+\w+\s+to\s+\w+", re.IGNORECASE),  # "from X to Y" pattern
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

# ── Journal house-style: active-voice-preferred families ─────────────────────
# Nature/Science/Cell author guidelines explicitly recommend active voice
# ("We show that…"). For those journals a passive-ratio floor is wrong; the
# passive check is emitted as a non-blocking WARNING for every journal (never
# gates the score) and its target text switches by journal.
ACTIVE_VOICE_JOURNAL_RE = re.compile(
    r"\b(nature|science|cell|nat\.?\s|sci\.?\s)", re.IGNORECASE
)


def _passive_target(journal: str) -> tuple[str, float | None, float | None]:
    """Return (guidance_text, low, high) for the passive-ratio warning.
    active-voice journals: recommend active, no floor; traditional: 50–70%."""
    if journal and ACTIVE_VOICE_JOURNAL_RE.search(journal):
        return (
            "Nature/Science/Cell house style prefers active voice "
            "(\"We show that…\"); no passive-ratio floor. Only flag if passive "
            "dominates (>70%).",
            None,
            0.70,
        )
    return ("traditional SCI house style, target 50–70%", 0.40, 0.70)


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
REF_LINE_RE = re.compile(r"^\d+\.\s+\w+.*?\d{4}", re.MULTILINE)
HEADING_RE = re.compile(r"^#+\s+", re.MULTILINE)
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
            in_ref_block = False
            prose_lines.append("")
            continue
        if HEADING_RE.match(stripped):
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


def check_file(filepath: str, journal: str = "") -> dict[str, Any]:
    """Run all checks on a single manuscript file."""
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
        "warnings": [],  # 软提示：不进 score、不阻断 gate
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

    # ── 3. Passive voice ratio (软提示, 不阻断) ───────────────────────────────
    # 语态偏好按 target_journal 切换：Nature/Science/Cell 官方 author guideline
    # 明确推荐主动语态，把被动锁 50–70% 是反着顶刊风格来。故此项只进 warnings，
    # 不计入 score、不影响 gate 通过与否，仅供作者参考。
    passive_count = sum(1 for s in sentences if PASSIVE_RE.search(s))
    passive_ratio = passive_count / len(sentences) if sentences else 0
    result["passive_ratio"] = round(passive_ratio, 3)

    guidance, low, high = _passive_target(journal)
    if high is not None and passive_ratio > high:
        result["warnings"].append({
            "type": "excessive_passive_voice",
            "detail": f"Passive ratio {passive_ratio:.1%} ({guidance}). Passive dominates — consider more active constructions.",
        })
    elif low is not None and passive_ratio < low:
        result["warnings"].append({
            "type": "insufficient_passive_voice",
            "detail": f"Passive ratio {passive_ratio:.1%} ({guidance}). Reads colloquial for a traditional-style journal; not a blocker.",
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
    # 破折号(—/——)硬门禁、禁止使用：进 issues(计入 score 扣分)并置 hard_fail，
    # 无论总分高低一律 fail-close，不放行。
    em_dash_count = len(EM_DASH_RE.findall(prose))
    if em_dash_count >= 1:
        result["issues"].append({
            "type": "decorative_em_dash",
            "severity": "high",
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
    score = 100
    for issue in result["issues"]:
        if issue["severity"] == "high":
            score -= 15
        elif issue["severity"] == "medium":
            score -= 8
        else:
            score -= 3
    result["score"] = max(0, score)

    return result


def main() -> int:
    p = argparse.ArgumentParser(description="Anti-AI style checker for manuscripts")
    p.add_argument("--manuscript-dir", default="manuscripts", help="Directory with .md files")
    p.add_argument("--file", default="", help="Check a single file instead of directory")
    p.add_argument("--report", default="style_check_report.json", help="Output report path")
    p.add_argument("--threshold", type=int, default=70, help="Minimum passing score")
    p.add_argument("--journal", default="", help="Target journal name; switches passive-voice guidance (Nature/Science/Cell → active-preferred, no floor)")
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

    results = [check_file(f, journal=args.journal) for f in files]
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
    if all_pass:
        print("STYLE_CHECK: PASS 仅覆盖形式层(句长方差/被动比软提示/禁词/em-dash 硬门禁/scare quotes/列点)，"
              "科学创新度、论证是否成立、这稿配不配目标刊均未自动核验，须作者与通讯作者自行判断。",
              file=sys.stderr)
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
