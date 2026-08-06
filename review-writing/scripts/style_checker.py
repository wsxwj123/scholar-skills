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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ref_section import is_reference_heading  # noqa: E402


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
# ── 中文 AI 套话（与上面英文表同级：命中即 high，计入 score）──────────────────
# 真源口径与 polish-sci / revise-sci 的 `AI_CLICHE_TERMS_ZH` 对齐（那份表是用户人工
# curated 的）。本表 = 那份表里**能实际生效的 15 条** ∪ 本家原有 4 条（不仅如此 /
# 在此背景下 / 越来越多的证据表明 / 发挥关键作用），共 19 条。
#
# 🚫 刻意不收 `随着……的发展` / `在……的背景下`(带省略号那条) / `为……奠定了基础`。
#    它们在 polish-sci 里带「……」占位符、字面永远匹配不上，这是用户**有意**留着不
#    生效的——他判定这几种表述不算 AI 感。别把它们改成能命中的形态。
#
# 🔧 要加/删一条套话就改这个 set。同一份口径目前散在四处、互为分叉副本：
#    rw / gsw 各一份 style_checker.py + polish-sci / revise-sci 各一份 common.py。
#    抽成 _shared/ 共享件是结构性改动，合并见 PROJECT.md 待办。
#    用户可见的说明：review-writing/references/writing_guidelines.md §4「Chinese Mode」
#    与 general-sci-writing/references/anti-ai-protocol.md。
FORBIDDEN_CN = {
    # ↓ 与 polish-sci / revise-sci AI_CLICHE_TERMS_ZH 逐条对齐的 15 条
    "值得注意的是", "值得一提的是", "众所周知", "不言而喻", "综上所述",
    "总而言之", "总的来说", "毋庸置疑", "显而易见", "至关重要",
    "举足轻重", "深入探讨", "近年来", "发挥着重要作用", "扮演着重要角色",
    # ↓ 本家原有、polish-sci 没有的 4 条
    "不仅如此", "在此背景下", "越来越多的证据表明", "发挥关键作用",
}
FORBIDDEN_PATTERNS = [
    re.compile(r"not only\b.*?\bbut also\b", re.IGNORECASE),
    re.compile(r"seamless[,\s]+intuitive[,\s]+and\s+powerful", re.IGNORECASE),
    # NOTE: removed `from\s+\w+\s+to\s+\w+` ("from X to Y"). In scientific reviews
    # this construction is high-frequency and legitimate ("from gut to joint",
    # "from adipogenic to osteogenic differentiation"); the false-positive rate
    # made the signal-to-noise ratio too poor to keep as an AI-rhetoric flag.
]

# ── 扣分档位与「套话扣分随证据量升级」 ────────────────────────────────────────
# 每档只扣一次是原口径；问题在于套话这一项**与命中条数无关**：一节里命中 1 条和命中
# 8 条同扣 15 分。中文稿越长命中越多、分数却纹丝不动，而按句子算的检查（句长方差）
# 在句子多了以后反而不触发 → **越长越容易过**。实测 935 字通篇套话的中文稿拿 77 分
# 放行（100-15 套话-8 连续等长），就是这么漏的。
#
# 修法：前 FORBIDDEN_FREE_HITS 条按老口径扣满 high(15)，之后每多一条再加
# FORBIDDEN_EXTRA_PENALTY。**命中 ≤3 条的文件分数与改动前逐分相同**，正常稿不受影响。
#
# ponytail: 3 条免加成 + 每条 5 分是启发式，定这两个数的依据是实测——正常英文学术散文
# 最多命中 2 条（notably + in recent years 那种），正常中文散文 0 条；通篇 AI 腔的稿子
# 命中 5–24 条。已知天花板：只命中 3 条套话、其余检查全过的稿子仍会放行（85 分）。
# 真稿反馈说误报/漏报再调这两个数。
SEVERITY_PENALTY = {"high": 15, "medium": 8, "low": 3}
FORBIDDEN_FREE_HITS = 3
FORBIDDEN_EXTRA_PENALTY = 5


def forbidden_penalty(hit_count: int) -> int:
    """套话项扣分：前 FORBIDDEN_FREE_HITS 条 = high 档 15 分，之后每条 +5。"""
    return SEVERITY_PENALTY["high"] + FORBIDDEN_EXTRA_PENALTY * max(
        0, hit_count - FORBIDDEN_FREE_HITS)

# ── Anti-AI: em-dash, scare quotes, explanatory colon ────────────────────────
# 破折号是**硬禁**：当停顿 / 插入语 / 补充说明用的破折号一个都不许有，命中即
# hard_fail 一票否决。用户已定死这条规矩，别改成配额/密度制。
# 覆盖三种实际会出现的形态，各算**一个**破折号：
#   —    单个 em dash（英文常见）
#   ——   中文双破折号（GB/T 15834 里它是一个标点，`—+` 保证不按两个记）
#   ␣–␣  空格包夹的 en dash（英式排版的停顿破折号）
# en dash **只在两侧有空格、且不是数字区间时**才算：复合词与数字区间里的 en dash
# 根本不是破折号（Michaelis–Menten、structure–activity、1990–2005、5–50 mM），
# 连坐它们就是误伤，化学/生物稿会凭空判死。
# 「不是数字区间」这半条：期刊常见 `5 – 50 mM`、`25 – 45 °C` 这种**带空格**的区间
# （带单位时尤其常见），若只按"有空格"判，一段正常方法学英文的 7 个区间会全被当成
# 装饰性 → 误判不合格。判据是**左右紧邻都得是数字**才算区间；
# 一侧数字一侧文字（`in 2020 – a landmark year – the field shifted`）是同位插入语，
# 仍按装饰性计——那正是 AI 腔要抓的形态。
# ponytail: 单位写在两侧的 `5 mM – 50 mM` 仍会被当成装饰性（Python 定宽 lookbehind
#   看不到"左窗口里有数字"）。真稿撞上再改成"先抹区间再计数"的两步式。
EM_DASH_RE = re.compile(
    r"(?<!\d)—+(?!\d)"            # em dash（—/中文 —— 按一个记）；1990—2005 不算
    r"|(?<!\d\s)(?<=\s)–+(?=\s)"  # ␣–␣ 且左侧紧邻不是数字
    r"|(?<=\s)–+(?=\s(?!\d))"     # ␣–␣ 且右侧紧邻不是数字
)
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

# ── 中文支持：切句与计词 ──────────────────────────────────────────────────────
# 中文句子以「。！？」收尾且**不带空格**，上面那条英文规则一句都切不出来；再叠加
# 「按空格数词」的碎片过滤（中文不分词 → 整段只算 1 词 < 3），整段中文会被整体丢弃，
# 于是所有按句子算的检查（句长方差/连续等长/长句…）在中文稿上全部空转 → 恒满分。
# 下面两条只在文本里真有汉字时才起作用；纯英文输入的行为与旧实现逐字节一致。
CJK_CHAR_RE = re.compile(r"[一-鿿]")           # 汉字：用于计字数
# 汉字 + 中文标点 + 全角符号：剥掉之后再数剩余的英文词，避免把「，」当成一个词。
CJK_TEXT_RE = re.compile(r"[　-〿一-鿿＀-￯]")
# 在中文句末标点之后断句；连续的句末标点（？！）和紧跟的收尾引号/括号留在本句。
CJK_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？])(?![。！？…”’」』）】])")

# ponytail: 2 个汉字折 1 个英文词。选 2 是为了让「单句 >30 词」这条阈值在中文上
# 落到 >60 字，正好对上本技能自己的节奏建议（短句 ≤15 字、长句 30–60 字）。
# 启发式，真稿反馈说长句判早/判晚了就调这一个数。
CJK_CHARS_PER_WORD = 2

# ── Reference/figure/heading filters ─────────────────────────────────────────
# NOTE: there is deliberately no per-line reference format regex any more.
# Real drafts mix at least five entry styles ("1. Author…2020", "- [12] …",
# "1. [99] Author…" with or without a year, bare "[99] …"), and any whitelist
# leaks the ones it does not know — that leak was the single largest false-
# positive source (bullets / explanatory colons / author initials read as
# undefined abbreviations). Once we know we are inside a reference block we
# drop every line until the block is closed; see _extract_prose.
#
# 段标题识别唯一口径在 ref_section.py（模块级 import，函数对象同一性），
# 与 general-sci-writing 同一份共享件（_shared/ref_section.py vendored 副本）。
# 这里曾放着本技能的独立实现（REF_HEADING_RE + _is_reference_label_line，
# 词表只有 References/参考文献/Bibliography 三条），与 ref_section 对同一份稿
# 判定不一致：`## Reference List` / `#References` / `## 7. References` /
# `## 引用文献` / 裸行 `Reference` / `References and Notes` 全认不得（条目泄进
# prose 误报），`####### References` 反而误开块（整段被误剥漏报）。已删除收敛
# （SPEC-round9 E2，与 gsw 第六轮同款修复）。
# 那份实现里的 ReDoS 事故记录与线性消费要求一并由 ref_section.py 继承，
# 识别路径不许回到正则。
HEADING_RE = re.compile(r"^#+\s+", re.MULTILINE)
FIGURE_LEGEND_RE = re.compile(r"^(?:Figure|Fig\.?|Table)\s+\d", re.IGNORECASE | re.MULTILINE)
CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
CITATION_RE = re.compile(r"\[\d+(?:[,\-\s]*\d+)*\]")

# ── CRediT 作者贡献行 / 通讯作者 boilerplate ──────────────────────────────────
# `Wenjie Xu: Conceptualization, Methodology, ...` 与 `Corresponding authors: 邮箱`
# 是期刊模板 boilerplate，不是正文 prose——留着每行稳定命中一条解释性冒号硬门禁
# （gsw 真稿 10 条假阳性，正文真实冒号 0 条）。CRediT 的 14 个角色是封闭标准词表
# （https://credit.niso.org/），按"冒号后整段全部落在词表内"判，不枚举人名。
# 与 general-sci-writing/scripts/style_checker.py 同口径（SPEC-round9 E2c D3 对齐）。
_CREDIT_ROLES = frozenset({
    "conceptualization", "data curation", "formal analysis", "funding acquisition",
    "investigation", "methodology", "project administration", "resources",
    "software", "supervision", "validation", "visualization",
    "writing - original draft", "writing - review and editing",
})
# 通讯作者 boilerplate 的封闭标签集（冒号前的全部头部，词表外不剥）。
_CORRESPONDING_HEADS = frozenset({
    "corresponding author", "corresponding authors", "correspondence", "correspondence to",
})


def _normalize_credit(text: str) -> str:
    """归一 CRediT 角色写法：破折号三态并到连字符、& 并到 and、压空白、小写。"""
    t = text.lower().replace("–", "-").replace("—", "-").replace("&", " and ")
    return " ".join(t.split())


def _is_credit_role_line(stripped: str) -> bool:
    """整行是 CRediT 贡献行（人名: 角色, 角色, ...）时返回 True。

    结构性判据：冒号后整段按逗号/分号切开后**每一项**都是 CRediT 角色词。
    正文解释性冒号（`The mechanism is simple: X inhibits Y.`）的冒号后不是
    角色词表，不剥。已知天花板：`Key contribution: Validation.` 这种整段恰好
    只有一个角色词的电报句也会被剥——它本就撞解释性冒号硬门禁，同方向。
    """
    head, sep, tail = stripped.partition(":")
    if not sep or not head.strip() or not tail.strip():
        return False
    items = [it for it in re.split(r"[,;]", tail) if it.strip(" .")]
    if not items:
        return False
    for it in items:
        norm = _normalize_credit(it.strip(" ."))
        if norm.startswith("and "):
            norm = norm[4:]
        if norm not in _CREDIT_ROLES:
            return False
    return True


def _is_corresponding_line(stripped: str) -> bool:
    """整行是通讯作者 boilerplate（标签: 邮箱/地址）时返回 True。

    判据是冒号前头部**整体**落在封闭标签集内；正文里的
    `Correspondence analysis showed: ...`（对应分析，统计方法）头部不在集内，不剥。
    """
    head, sep, _ = stripped.partition(":")
    if not sep:
        return False
    return _normalize_credit(head).strip("*_ ") in _CORRESPONDING_HEADS


def _extract_prose(text: str) -> str:
    """Strip non-prose elements from manuscript markdown."""
    text = CODE_BLOCK_RE.sub("", text)
    lines = text.splitlines()  # 跨平台：兼容 \r\n/\r 换行
    prose_lines = []
    in_ref_block = False
    # 段落起点标记：图注是独立段落（前面是空行/块边界），pandoc 硬换行的正文续行
    # 在段落中间（上一行非空）——两者行首都可能是 "Figure 5"，只有前者该剥。
    # 此前无条件剥，正文续行被整行吞掉（gsw 真稿 3 处：As shown in ↵ Figure 5E ...），
    # 而 `Figure S4C` 因 S 前缀不匹配正则幸存，同性质句子主图被剥、附图留下。
    para_start = True
    for line in lines:
        stripped = line.strip()
        if not stripped:
            # Keep in_ref_block as-is: a reference section commonly has blank
            # lines between entries, and standard Markdown always puts one
            # between the "References" label and the first entry. Closing on a
            # blank line meant the block never survived past its own label.
            prose_lines.append("")
            para_start = True
            continue
        if is_reference_heading(line):
            # 参考文献段标题开块（markdown 标题与裸标签行两类都由这一个函数认）。
            in_ref_block = True
            para_start = True
            continue
        if HEADING_RE.match(stripped):
            # 任何非参考文献标题关块：`## References` 之后若还有 `## Appendix`
            # 这类带自己标题的正文节，该节正文必须继续被检查，不许一个参考
            # 文献标题截断全文。
            in_ref_block = False
            para_start = True
            continue
        if in_ref_block:
            # Inside a reference block every line is bibliography, whatever its
            # entry format. Only a non-reference heading (branch above) closes
            # the block. Trade-off: prose placed after a reference list without
            # its own heading is dropped, which can only hide style issues
            # (false negatives) — the old format whitelist produced dozens of
            # false positives per draft instead, which is the worse failure.
            continue
        if stripped.startswith("---"):
            para_start = True
            continue
        if _is_credit_role_line(stripped) or _is_corresponding_line(stripped):
            # CRediT 贡献行 / 通讯作者 boilerplate：期刊模板内容，不是正文 prose，
            # 留着每行稳定命中一条解释性冒号假阳性。
            para_start = True
            continue
        if para_start and FIGURE_LEGEND_RE.match(stripped):
            # 段首的 Figure/Table 编号行是图注，剥；段落中间的同形行是硬换行
            # 续行（上一行非空），必须留下被检查。
            continue
        prose_lines.append(line)
        para_start = False
    return "\n".join(prose_lines)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences (English punctuation + Chinese 。！？)."""
    text = CITATION_RE.sub("", text)  # remove [n] before splitting
    raw: list[str] = []
    for chunk in SENTENCE_RE.split(text):
        raw.extend(CJK_SENTENCE_SPLIT_RE.split(chunk))
    return [s.strip() for s in raw if s.strip() and _word_count(s) >= 3]


def _word_count(sentence: str) -> int:
    """词数；中文按「CJK_CHARS_PER_WORD 个汉字 = 1 词」折算。

    没有汉字时直接走旧路径（len(split())），保证纯英文文本结果一字不差。"""
    cjk = len(CJK_CHAR_RE.findall(sentence))
    if not cjk:
        return len(sentence.split())
    return len(CJK_TEXT_RE.sub(" ", sentence).split()) + cjk // CJK_CHARS_PER_WORD


def _opener_key(first_sentence: str) -> str:
    """段首指纹：英文取前 3 词，中文取前 6 字（= 3 个词当量，口径一致）。

    中文没有空格，沿用 split()[:3] 会把整段当成一个 opener，等于不查。"""
    if CJK_CHAR_RE.match(first_sentence[:1]):
        return first_sentence[: 3 * CJK_CHARS_PER_WORD]
    words = first_sentence.split()[:3]
    return " ".join(words).lower() if len(words) >= 2 else ""


def _is_cjk_dominant(text: str, total_words: int) -> bool:
    """半数以上词当量来自汉字 → 当中文稿处理（英文专属检查对它没有意义）。"""
    cjk_equiv = len(CJK_CHAR_RE.findall(text)) // CJK_CHARS_PER_WORD
    return total_words > 0 and cjk_equiv * 2 > total_words


def check_file(filepath: str, passive_max: float = 0.30) -> dict[str, Any]:
    """Run all checks on a single review draft file.

    passive_max: maximum acceptable passive-voice ratio (review default 0.30).
    """
    # errors="replace"：GBK 等非 UTF-8 稿混入时坏字节替换为 U+FFFD 而非抛
    # UnicodeDecodeError 裸崩（SPEC-round13 F3，与 gsw 同款）。
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        raw_text = f.read()

    prose = _extract_prose(raw_text)
    sentences = _split_sentences(prose)
    paragraphs = [p.strip() for p in prose.split("\n\n") if p.strip() and _word_count(p) >= 10]

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

    # PASSIVE_RE 认的是 be + 过去分词，中文稿上恒为 0；不对中文稿发这条提示。
    if passive_ratio > passive_max and not _is_cjk_dominant(prose, total_words):
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
    for phrase in FORBIDDEN_CN:  # 中文无大小写，直接在原文里找
        if phrase in prose:
            forbidden_hits.append({"phrase": phrase, "type": "forbidden_word_cn"})
    for pat in FORBIDDEN_PATTERNS:
        if pat.search(prose):
            forbidden_hits.append({"phrase": pat.pattern[:50], "type": "forbidden_pattern"})

    result["forbidden_hits"] = forbidden_hits
    if forbidden_hits:
        result["issues"].append({
            "type": "forbidden_ai_phrases",
            "severity": "high",
            # 扣分随命中条数升级（长稿不再被稀释），见 forbidden_penalty
            "penalty": forbidden_penalty(len(forbidden_hits)),
            "detail": f"{len(forbidden_hits)} AI-typical phrases detected: {', '.join(h['phrase'] for h in forbidden_hits[:5])}",
        })

    # ── 5. Paragraph opening repetition ───────────────────────────────────────
    openers = []
    for para in paragraphs:
        first_sentence = SENTENCE_RE.split(para)[0].strip() if para else ""
        opener = _opener_key(first_sentence)
        if opener:
            openers.append(opener)

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

    # ── 7. Decorative em-dash (硬门禁, 禁止使用: 一个都不许有) ─────────────────
    # 去AI必禁三项之一。命中即 hard_fail 一票否决，不放行。
    # 计数口径见 EM_DASH_RE：复合词与数字区间里的 en dash 不是破折号，不计。
    em_dash_count = len(EM_DASH_RE.findall(prose))
    if em_dash_count >= 1:
        result["issues"].append({
            "type": "decorative_em_dash",
            "severity": "high",
            "detail": (f"{em_dash_count} decorative dash(es) (—/——/ – ) detected. "
                       f"禁止使用破折号(硬门禁，一个都不许有)：用逗号/句号/重构替代。"),
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
        # 缺省按 severity 档位扣；带 "penalty" 的项自报扣分（套话项按命中条数升级）
        score -= issue.get("penalty", SEVERITY_PENALTY.get(sev, SEVERITY_PENALTY["low"]))
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

    # 输入路径先验证再用：路径打错过去会走到「没扫到文件」分支、以 ok:true exit 0
    # 收场——去 AI 腔这道硬门少打一个字母就等于整道门没跑。区分两件事：
    #   路径不存在/不是目录 = 调用方搞错了 → 非 0 拒绝（同 proofread.py 的 dir not found）
    #   目录在但没有 .md    = 合法的空项目状态 → 维持 ok:true exit 0
    if args.file:
        if not os.path.isfile(args.file):
            print(json.dumps({"ok": False, "error": f"file not found: {args.file}"},
                             ensure_ascii=False))
            return 1
    elif not os.path.isdir(args.manuscript_dir):
        print(json.dumps({"ok": False, "error": f"dir not found: {args.manuscript_dir}"},
                         ensure_ascii=False))
        return 1

    files: list[str] = []
    if args.file:
        files = [args.file]
    else:
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
