#!/usr/bin/env python3
"""Scan for high-risk phrases suggesting fabricated claims or overpromises."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from unit_glob import iter_units

# ---------------------------------------------------------------------------
# Sentence-length and -ing clause helpers
# ---------------------------------------------------------------------------
EN_SENTENCE_WORD_LIMIT = 30
ZH_SENTENCE_CHAR_LIMIT = 50


def _split_en_sentences(text: str) -> list[str]:
    """Very conservative English sentence splitter (period/!/?).
    Avoids splitting "Fig. 3A", "vs.", "et al.", "e.g.", "i.e." etc.
    """
    # Protect common abbreviations
    text = re.sub(r'\b(Fig|fig|No|no|vs|Vol|vol|et al|e\.g|i\.e|Dr|Prof|Mr|Mrs|Ms|Jr|Sr|etc)\.',
                  r'\1<DOT>', text)
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    return [p.replace('<DOT>', '.').strip() for p in parts if p.strip()]


def _count_words(sentence: str) -> int:
    return len(sentence.split())


def _split_zh_sentences(text: str) -> list[str]:
    """Split Chinese text on sentence-ending punctuation."""
    parts = re.split(r'(?<=[。！？；])', text)
    return [p.strip() for p in parts if p.strip()]


def _count_zh_chars(sentence: str) -> int:
    """Count only CJK + ASCII non-space chars (excludes punctuation-only spans)."""
    return len(re.sub(r'\s', '', sentence))

# Categories prefixed with "ai_" are only applied to comment units, not email units.
RISK_PATTERNS = {
    "fabricated_experiment": [
        r"we (have )?conducted additional experiments",
        r"new experiments? (were|was) performed",
    ],
    "fabricated_statistics": [
        r"p\s*[<=>]\s*0\.0[0-9]",
        r"significant at p\s*[<=>]",
        r"we now report .* confidence interval",
    ],
    "overpromise": [
        r"we will definitely",
        r"this proves that",
        r"without any doubt",
    ],
    "ai_hedging": [
        r"it is important to note that",
        r"it should be noted that",
        r"it is worth (noting|mentioning) that",
        r"importantly,",
        r"notably,",
        r"it is crucial to",
        r"needless to say",
    ],
    "ai_appreciation": [
        r"we (greatly|sincerely|deeply) (appreciate|thank)",
        r"we are (deeply |truly )?(grateful|thankful) for",
        r"thank you for (your )?(insightful|valuable|constructive|thoughtful) (comments?|suggestions?|feedback)",
    ],
    "ai_filler": [
        r"in order to\b",
        r"as a matter of fact",
        r"it is worth noting that",
        r"we would like to (point out|emphasize|highlight|note) that",
        r"as (the reviewer )?(rightly|correctly) (pointed out|noted|observed|suggested)",
        r"we completely agree with the reviewer",
        r"this is (indeed )?an excellent (point|suggestion|observation)",
    ],
    # Comma + -ing participial dangling clause (AI signature pattern).
    # Match ", <word(s)> <verb>ing" where the -ing verb is at the clause start.
    # Excludes legitimate list items and figure labels by requiring lowercase after comma.
    "ai_ing_clause": [
        r",\s+(?:thus|thereby|hence|therefore\s+)?(?:\w+\s+){0,3}\b\w+ing\b(?:\s+(?:that|the|our|its|this|a|an)\b)",
        r",\s+(?:reflecting|ensuring|highlighting|demonstrating|confirming|indicating|suggesting|showing|providing|allowing|enabling|supporting|strengthening|underscoring|emphasizing)\b",
    ],
    # Decorative em-dash ban: —/—— used as pause/parenthetical/emphasis.
    # Excludes: hyphens in compound terms, numeric ranges (e.g. 1–10), citation ranges.
    # Pattern: text—text where surrounded by word chars (not purely numeric ranges).
    "ai_em_dash": [
        r"(?<=[a-zA-Z一-鿿,;])\s*[—―][—―]?\s*(?=[a-zA-Z一-鿿])",
    ],
    # Scare-quote ban: ordinary phrases wrapped in quotation marks to imply novelty/irony.
    # Excludes: first-use term definitions, reviewer verbatim quotes, idiomatic expressions.
    # Covers ASCII double-quotes (") and curly/smart quotes ("").
    # Heuristic: quoted phrase <=30 chars, not preceded by "termed/called/so-called/defined as".
    "ai_scare_quote": [
        r'(?<!termed\s)(?<!called\s)(?<!so-called\s)(?<!defined as\s)"(?![\d])[A-Za-z][^"]{1,30}"(?!\s+(?:et al\.|[A-Z]))',
        r'(?<!termed\s)(?<!called\s)(?<!so-called\s)(?<!defined as\s)"(?![\d])[A-Za-z一-鿿][^"]{1,30}"',
    ],
    # Explanatory-colon ban: "concept: explanation" as decorative sentence structure.
    # Legitimate colons: ratios (2:1), times (10:30), list lead-ins ending sentence, section headings, figure labels.
    # Heuristic: colon within a sentence (not at end), preceded by a noun/phrase (not a digit), followed by lowercase/Chinese.
    "ai_explanatory_colon": [
        r'(?<!\d):\s+(?=[a-z一-鿿])(?!(?:\d|\w+://|//))(?!(?:e\.g\.|i\.e\.|etc\.|vs\.))',
    ],
    # AI cliché phrase blacklist (EN + ZH). Aligned with general-sci-writing
    # style_checker.py FORBIDDEN_EXACT. Only phrases NOT already covered by
    # ai_hedging / ai_filler above are listed here, to avoid double-flagging
    # one sentence under two categories.
    "forbidden_ai_phrase": [
        # ── English (gsw FORBIDDEN_EXACT, minus hedging/filler overlaps) ──
        r"\bmoreover\b",
        r"\bfurthermore\b",
        r"\bdelve into\b",
        r"\bcomprehensive landscape\b",
        r"\bpivotal role\b",
        r"\brealm\b",
        r"\btapestry\b",
        r"\bunderscore[sd]?\b",
        r"\ba testament to\b",
        r"\btestament\b",
        r"\binterestingly\b",
        r"\bremarkably\b",
        r"\bin recent years\b",
        r"\ba growing body of evidence\b",
        r"\bhas garnered significant attention\b",
        r"\bplays? a crucial role\b",
        r"\ba plethora of\b",
        r"\bmyriad of\b",
        r"\bin the context of\b",
        r"\bshed[s]? light on\b",
        r"\bpave[sd]? the way\b",
        r"\bof paramount importance\b",
        r"\ba key player\b",
        # ── Chinese AI cliché ──
        r"值得注意的是",
        r"综上所述",
        r"众所周知",
        r"不言而喻",
        r"显而易见",
        r"毋庸置疑",
        r"总而言之",
        r"总的来说",
        r"在.{0,8}的背景下",
        r"发挥着?(?:至关重要|关键|重要|举足轻重)的作用",
        r"扮演着?(?:重要|关键)的角色",
        r"日益(?:增长|凸显|受到)",
        r"近年来",
    ],
}

AI_STYLE_CATEGORIES = {"ai_hedging", "ai_appreciation", "ai_filler", "ai_ing_clause",
                       "ai_em_dash", "ai_scare_quote", "ai_explanatory_colon",
                       "forbidden_ai_phrase"}
FABRICATION_CATEGORIES = {"fabricated_experiment", "fabricated_statistics"}
# 去AI必禁三项(破折号/scare quotes/解释性冒号)硬门禁、禁止使用：命中即 pipeline-blocking(return 1)。
# 其余 AI 风格项(hedging/appreciation/filler/-ing 从句/句长等)仍为软提示(WARN-only)。
HARD_STYLE_CATEGORIES = {"ai_em_dash", "ai_scare_quote", "ai_explanatory_colon"}


def _check_en_sentence_length(units: list[dict]) -> list[tuple[str, str, str]]:
    """Flag English sentences exceeding EN_SENTENCE_WORD_LIMIT words (WARN)."""
    hits: list[tuple[str, str, str]] = []
    for unit in units:
        uid = unit.get("unit_id", "?")
        content = unit.get("content", {})
        for field in ("response_en", "revised_excerpt_en"):
            text = str(content.get(field, ""))
            if not text or text in ("无", "N/A", ""):
                continue
            for sent in _split_en_sentences(text):
                wc = _count_words(sent)
                if wc > EN_SENTENCE_WORD_LIMIT:
                    preview = sent[:80] + ("…" if len(sent) > 80 else "")
                    hits.append((uid, "en_sentence_too_long",
                                 f"{field}: {wc} words: \"{preview}\""))
    return hits


def _check_zh_sentence_length(units: list[dict]) -> list[tuple[str, str, str]]:
    """Flag Chinese sentences exceeding ZH_SENTENCE_CHAR_LIMIT chars (WARN)."""
    hits: list[tuple[str, str, str]] = []
    for unit in units:
        uid = unit.get("unit_id", "?")
        content = unit.get("content", {})
        for field in ("response_zh", "revised_excerpt_zh"):
            text = str(content.get(field, ""))
            if not text or text in ("无", "N/A", ""):
                continue
            for sent in _split_zh_sentences(text):
                cc = _count_zh_chars(sent)
                if cc > ZH_SENTENCE_CHAR_LIMIT:
                    preview = sent[:60] + ("…" if len(sent) > 60 else "")
                    hits.append((uid, "zh_sentence_too_long",
                                 f"{field}: {cc} chars: \"{preview}\""))
    return hits


def _check_structural_repetition(units: list[dict]) -> list[tuple[str, str]]:
    """Detect cross-unit response opening repetition (>=3 same pattern)."""
    openings: dict[str, list[str]] = {}
    for unit in units:
        uid = unit.get("unit_id", "")
        response = str(unit.get("content", {}).get("response_en", "")).strip()
        if not response:
            continue
        # Extract first sentence, normalize to pattern
        first = response.split(".")[0].strip().lower() if "." in response else response[:80].strip().lower()
        # Remove specific nouns/numbers to get structural template
        pattern = re.sub(r"\b(figure|table|section|page|line|paragraph)\s*\d+\w*", "REF", first)
        pattern = re.sub(r"\b(reviewer|comment)\s*#?\d+", "REVIEWER", pattern)
        pattern = re.sub(r"\d+", "N", pattern)
        openings.setdefault(pattern, []).append(uid)

    hits: list[tuple[str, str]] = []
    for pattern, uids in openings.items():
        if len(uids) >= 3:
            hits.append(("structural_repetition", f"{len(uids)} units share opening pattern: {uids[:5]}"))
    return hits


def scan_text(text: str, *, skip_ai_style: bool = False, cross_check_text: str = "") -> list[tuple[str, str]]:
    """Scan text for risk patterns.

    cross_check_text: when provided, fabricated_statistics hits are suppressed if
    the same matched substring also appears in cross_check_text (revised_excerpt_en),
    meaning the statistic is grounded in the actual revision rather than invented.
    """
    hits: list[tuple[str, str]] = []
    for category, patterns in RISK_PATTERNS.items():
        if skip_ai_style and category in AI_STYLE_CATEGORIES:
            continue
        for pattern in patterns:
            m = re.search(pattern, text, flags=re.IGNORECASE)
            if not m:
                continue
            # Exempt fabricated_statistics when the same matched value also appears
            # in revised_excerpt_en — the statistic is being reported faithfully, not invented.
            if category == "fabricated_statistics" and cross_check_text:
                matched_value = m.group(0)
                if re.search(re.escape(matched_value), cross_check_text, flags=re.IGNORECASE):
                    continue  # Grounded in revised excerpt — not fabricated
            hits.append((category, pattern))
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Risk phrase checker")
    parser.add_argument("file", nargs="?", help="Path to a single text/HTML file (legacy mode)")
    parser.add_argument("--project-root", default="", help="Scan all units/*.json in a project")
    args = parser.parse_args()

    all_hits: list[tuple[str, str, str]] = []  # (source, category, pattern)

    if args.project_root:
        root = Path(args.project_root)
        units_dir = root / "units"
        if not units_dir.exists():
            print(f"RISK_CHECK: SKIP (no units dir: {units_dir})")
            return 0
        loaded_units = []
        comment_units = []
        for p, unit in iter_units(units_dir):
            loaded_units.append(unit)
            is_email = unit.get("section") == "email" or "email" in str(unit.get("unit_id", "")).lower()
            if not is_email:
                comment_units.append(unit)
            content = unit.get("content", {})
            response_en = str(content.get("response_en", ""))
            revised_en = str(content.get("revised_excerpt_en", ""))
            # Fabrication patterns only scan response_en.
            # Pass revised_en as cross_check: if the same statistic appears in the revision,
            # it is being reported faithfully and should not be flagged as fabricated.
            for cat, pat in scan_text(response_en, skip_ai_style=is_email, cross_check_text=revised_en):
                all_hits.append((unit.get("unit_id", p.name), cat, pat))
            # AI style + overpromise also scan revised_excerpt (but NOT fabrication categories)
            for cat, pat in scan_text(revised_en, skip_ai_style=is_email):
                if cat not in FABRICATION_CATEGORIES:
                    all_hits.append((unit.get("unit_id", p.name), cat, pat))
        # Structural repetition check across comment units only
        for cat, msg in _check_structural_repetition(comment_units):
            all_hits.append(("cross-unit", cat, msg))
        # Sentence-length checks (WARN-level, both EN and ZH)
        for uid, cat, msg in _check_en_sentence_length(comment_units):
            all_hits.append((uid, cat, msg))
        for uid, cat, msg in _check_zh_sentence_length(comment_units):
            all_hits.append((uid, cat, msg))
    elif args.file:
        text = Path(args.file).read_text(encoding="utf-8")
        for cat, pat in scan_text(text):
            all_hits.append((args.file, cat, pat))
    else:
        text = sys.stdin.read()
        for cat, pat in scan_text(text):
            all_hits.append(("stdin", cat, pat))

    # Separate hard risks (pipeline-blocking) from soft risks (warn-only)
    _HARD = FABRICATION_CATEGORIES | HARD_STYLE_CATEGORIES
    hard_hits = [(s, c, p) for s, c, p in all_hits if c in _HARD]
    soft_hits = [(s, c, p) for s, c, p in all_hits if c not in _HARD]

    if hard_hits:
        print("RISK_CHECK: FAIL (hard risk detected)")
        for source, category, pattern in hard_hits:
            print(f"- [{source}] {category}: matched /{pattern}/")
        if soft_hits:
            print("Additional warnings:")
            for source, category, pattern in soft_hits:
                print(f"- [{source}] {category}: matched /{pattern}/")
        return 1

    if soft_hits:
        print("RISK_CHECK: WARN (non-blocking)")
        for source, category, pattern in soft_hits:
            print(f"- [{source}] {category}: matched /{pattern}/")
        return 0

    print("RISK_CHECK: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
