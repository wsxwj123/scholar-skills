"""Proofread checker for SCI manuscript markdown files.

Catches the 80% of mechanical errors that survive Anti-AI style checks:
  1. Common misspellings (teh, occured, etc.)
  2. Chinese punctuation leaked into English text (，；：（）「」 etc.)
  3. Unit format issues (um → μm, degC → °C, x g → ×g)
  4. Inconsistent term spellings (nano-particles vs nanoparticles)
  5. Tense mixing hints (Methods should be past tense; etc.)
  6. Number format (10000 vs 10,000)

Usage:
    python scripts/proofread.py --manuscript-dir manuscripts --report proofread_report.json
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

# ── Common misspellings (a → b) ──────────────────────────────────────────────
MISSPELLINGS = {
    "teh": "the", "adn": "and", "recieve": "receive",
    "occured": "occurred", "occuring": "occurring", "seperate": "separate",
    "definately": "definitely", "alot": "a lot", "untill": "until",
    "wich": "which", "thier": "their", "wierd": "weird",
    "occurence": "occurrence", "accomodate": "accommodate",
    "neccessary": "necessary", "neccesary": "necessary",
    "succesful": "successful", "succesfully": "successfully",
    "tommorow": "tomorrow", "infered": "inferred",
    "behaviuor": "behavior",
    "experiement": "experiment", "experiments": None,
    "phenotpye": "phenotype", "phenotype": None,
    "morpholgy": "morphology", "morphology": None,
    "stastistical": "statistical", "stastistics": "statistics",
    "stastically": "statistically", "siginificant": "significant",
    "siginificantly": "significantly",
    "compromized": "compromised", "compoared": "compared",
    "compairson": "comparison", "comparsion": "comparison",
    "expermental": "experimental",
    "preformed": "performed (or 'preformed' if 'pre-formed')",
    "becuase": "because", "becasue": "because",
}
# 移除 None 值(占位)
MISSPELLINGS = {k: v for k, v in MISSPELLINGS.items() if v is not None}

# ── BrE/AmE pairs (only flag when MIXED within same file) ────────────────────
# 单用一种不报;两种混用才提示风格不一致
BRE_AME_PAIRS = [
    ("colour", "color"), ("analyse", "analyze"), ("modelling", "modeling"),
    ("labelled", "labeled"), ("centre", "center"), ("behaviour", "behavior"),
    ("organise", "organize"), ("organisation", "organization"),
    ("favour", "favor"), ("optimise", "optimize"), ("characterise", "characterize"),
    ("recognise", "recognize"), ("utilise", "utilize"), ("emphasise", "emphasize"),
    ("hypothesise", "hypothesize"),
]


# ── F3: 学术英文常见错拼(WARN 级). codespell 不可用时用本固定词表补充. ────────
# 注:与既有 MISSPELLINGS(high 级)分开存放,本表统一 warn 级、不扣分不阻断。
# 真稿验证环境已确认无 codespell,故走词表路径。键=错拼,值=建议。
ACADEMIC_MISSPELLINGS = {
    "occassion": "occasion", "occassionally": "occasionally",
    "consistant": "consistent", "consistancy": "consistency",
    "dependant": "dependent", "independant": "independent",
    "signficant": "significant", "signficantly": "significantly",
    "signifcant": "significant", "significatn": "significant",
    "measurment": "measurement", "measuremnt": "measurement",
    "enviroment": "environment", "enviornment": "environment",
    "futher": "further", "furthur": "further",
    "homogenous": "homogeneous (for uniform composition)",
    "heterogenous": "heterogeneous",
    "flourescence": "fluorescence", "flourescent": "fluorescent",
    "concentraion": "concentration", "concetration": "concentration",
    "wavelenght": "wavelength", "througput": "throughput",
    "thoughput": "throughput", "paramter": "parameter",
    "parmeter": "parameter", "absorbtion": "absorption",
    "preceeding": "preceding", "supress": "suppress",
    "supressed": "suppressed", "supression": "suppression",
    "inhibtion": "inhibition", "prolifertion": "proliferation",
    "proliferaton": "proliferation", "cytoplasmatic": "cytoplasmic",
}

# ── D2: 应上下标却裸写的常见化学式/标记(WARN 级,字符级易误报) ───────────────
# 仅当未被 markdown 上下标(^...^ / ~...~)或 HTML(<sup>/<sub>)包裹时才报。
# 模式列表可维护:每项 (正则, 说明)。
# 边界用 (?<![A-Za-z0-9]) / (?![A-Za-z0-9]) 而非 \b：Unicode 下汉字属 \w，
# \b 在 "H2O代谢" 这种中英紧邻处失效会漏报；ASCII 字母数字边界则不受汉字干扰，
# 既能在中文紧邻时命中，又不会把 "the H2O level" 的英文写法退化。
# （方案对齐 sci2doc check_quality.py 的字符级边界处理。）
_NB = r"(?<![A-Za-z0-9])"   # 左边界：前面不是 ASCII 字母/数字
_NA = r"(?![A-Za-z0-9])"    # 右边界：后面不是 ASCII 字母/数字
SUBSUP_PATTERNS = [
    (re.compile(_NB + r"H2O" + _NA), "H2O → H~2~O (water; subscript 2)"),
    (re.compile(_NB + r"CO2" + _NA), "CO2 → CO~2~ (subscript 2)"),
    (re.compile(_NB + r"H2O2" + _NA), "H2O2 → H~2~O~2~ (subscripts)"),
    (re.compile(_NB + r"O2" + _NA), "O2 → O~2~ (subscript 2)"),
    (re.compile(_NB + r"N2" + _NA), "N2 → N~2~ (subscript 2)"),
    (re.compile(_NB + r"NH3" + _NA), "NH3 → NH~3~ (subscript 3)"),
    (re.compile(_NB + r"SO2" + _NA), "SO2 → SO~2~ (subscript 2)"),
    (re.compile(_NB + r"Na\+" + _NA), "Na+ → Na^+^ (superscript charge)"),
    (re.compile(_NB + r"Ca2\+"), "Ca2+ → Ca^2+^ (superscript charge)"),
    (re.compile(_NB + r"IC50" + _NA), "IC50 → IC~50~ (subscript 50)"),
    (re.compile(_NB + r"EC50" + _NA), "EC50 → EC~50~ (subscript 50)"),
    (re.compile(_NB + r"LD50" + _NA), "LD50 → LD~50~ (subscript 50)"),
    (re.compile(_NB + r"Km" + _NA), "Km → K~m~ (subscript m; Michaelis constant)"),
    # cm2/m2/μm2 等面积:数字后紧跟单位再跟 2/3(指数)
    (re.compile(_NB + r"(\d+(?:\.\d+)?)\s?(cm|mm|nm|μm|um|m)2" + _NA), "area unit: e.g. cm2 → cm^2^ (superscript exponent)"),
    (re.compile(_NB + r"(\d+(?:\.\d+)?)\s?(cm|mm|nm|μm|um|m)3" + _NA), "volume unit: e.g. cm3 → cm^3^ (superscript exponent)"),
    # 幂:仅匹配带字面 ^ 的 10^n(作者手写乘方),裸数字 105/100/410011 一律不碰
    (re.compile(_NB + r"10\^(\d+)" + _NA), "power-of-ten: 10^6 → 10^6^ (markdown superscript)"),
]

# ── F1: 中文高置信错别字/混用(WARN 级,保守只收确定性错字) ──────────────────
# 主观字(的/地/得)一律不收;只收书写错字。键=错,值=对。
CHINESE_TYPOS = {
    "帐号": "账号", "登陆": "登录", "即时": None,  # 即时合法,占位排除
    "既使": "即使", "按装": "安装", "؟": None,
    "蜡烛": None, "树立": None,
    "必需品": None,
    "做为": "作为", "另据": None,
    "竟然": None,
    "拌随": "伴随", "渡过难关": None,
    "迫不急待": "迫不及待", "再接再励": "再接再厉",
    "一如继往": "一如既往", "言简意骇": "言简意赅",
    "甘败下风": "甘拜下风", "察颜观色": "察言观色",
    "�absolute": None,
    "脉博": "脉搏", "松驰": "松弛", "辐射": None,
    "震荡": None, "竭泽而鱼": "竭泽而渔",
    "金榜提名": "金榜题名", "美仑美奂": "美轮美奂",
    "病入膏盲": "病入膏肓", "信誓旦旦": None,
    "穿流不息": "川流不息", "源远流长": None,
}
CHINESE_TYPOS = {k: v for k, v in CHINESE_TYPOS.items() if v is not None}

# ── D1: 中文句内夹半角标点(WARN 级,高误报区,极度保守) ─────────────────────
# 只标"半角标点两侧紧邻汉字"这种高置信中文句内夹半角的情形。
# 半角标点:, ; : ( )  → 应为全角 ， ； ： （ ）
# DOI/URL/数字/单位区间不会出现"汉字+半角+汉字",故天然规避。
HALFWIDTH_IN_CN = [
    (re.compile(r"([一-鿿]),([一-鿿])"), ",", "，", "中文句内半角逗号"),
    (re.compile(r"([一-鿿]);([一-鿿])"), ";", "；", "中文句内半角分号"),
    (re.compile(r"([一-鿿]):([一-鿿])"), ":", "：", "中文句内半角冒号"),
    (re.compile(r"([一-鿿])\(([一-鿿])"), "(", "（", "中文句内半角左括号"),
    (re.compile(r"([一-鿿])\)([一-鿿])"), ")", "）", "中文句内半角右括号"),
]


# ── Chinese punctuation that leaked into English text ────────────────────────
CHINESE_PUNCT = {
    "，": ",", "；": ";", "：": ":", "（": "(", "）": ")",
    "！": "!", "？": "?", "《": "<", "》": ">",
    "【": "[", "】": "]", "「": "\"", "」": "\"",
    "…": "...",
    "。": ".",
}
# 只收「全角、中文独有」的标点作硬拦。以下**不**计入 chinese_punct(英文排版合法):
# · em dash (—, U+2014) —— 英文破折号;是否 AI 腔由 style_checker 去AI规则裁决。
# · 弯引号 “ ” ‘ ’ (U+201C/D, U+2018/9) —— 英文智能引号/撇号(don't→don’t)通用,
#   published PDF/Word 普遍如此;当中文标点硬拦会误伤几乎所有真实英文稿。
# 直/弯引号一致性若要管,属风格层(soft),不放这里。

# ── Unit format issues ───────────────────────────────────────────────────────
UNIT_PATTERNS = [
    # (问题模式, 应改为, 描述)
    (re.compile(r"\b(\d+(?:\.\d+)?)\s*um\b"), r"\1 μm", "ASCII 'um' should be 'μm'"),
    (re.compile(r"\b(\d+(?:\.\d+)?)\s*degC\b", re.IGNORECASE), r"\1 °C", "'degC' should be '°C'"),
    (re.compile(r"\b(\d+(?:\.\d+)?)\s*deg\s*C\b", re.IGNORECASE), r"\1 °C", "'deg C' should be '°C'"),
    (re.compile(r"(\d+(?:\.\d+)?)\s*[xX]\s*g\b"), r"\1 ×g", "centrifugation force: use '×g' not 'x g'"),
    (re.compile(r"\b(\d+(?:\.\d+)?)\s*ug\b"), r"\1 μg", "ASCII 'ug' should be 'μg'"),
    (re.compile(r"\b(\d+(?:\.\d+)?)\s*ul\b"), r"\1 μL", "ASCII 'ul' should be 'μL'"),
    (re.compile(r"\b(\d+(?:\.\d+)?)\s*uM\b"), r"\1 μM", "ASCII 'uM' should be 'μM'"),
    (re.compile(r"\b(\d+(?:\.\d+)?)\s*uA\b"), r"\1 μA", "ASCII 'uA' should be 'μA'"),
    (re.compile(r"\b(\d+(?:\.\d+)?)\s*degree(s)?\b"), r"\1°", "'degrees' (when temperature) usually written as '°'"),
]

# ── Number format consistency (10000 vs 10,000) ──────────────────────────────
# 期刊偏好:Nature 用 comma 分隔 ≥1000;Cell 同;BMJ 系列同.
# 检测:同文档内出现大于 4 位数字、有的带逗号、有的不带 = 不一致
NUMBER_RE = re.compile(r"(?<![\d.,])\d{4,}(?![\d.,])")
NUMBER_WITH_COMMA_RE = re.compile(r"\d{1,3}(,\d{3})+")

# ── Term consistency tracking ────────────────────────────────────────────────
# 检测同概念多种写法。每组列「互斥」的表面形态(空格/连字符/连写)，仅当 ≥2 种
# 不同形态共存才报；旧版用 `in.?vivo` 与 `in vivo` 重叠模式，单写 "in vivo" 会被
# 两条同时命中误报"不一致"，故改为互斥精确形态。
TERM_VARIANTS = [
    [r"\bnanoparticles?\b", r"\bnano-particles?\b", r"\bnano particles?\b"],
    [r"\binvitro\b", r"\bin-vitro\b", r"\bin vitro\b"],
    [r"\binvivo\b", r"\bin-vivo\b", r"\bin vivo\b"],
    [r"\bcoculture\b", r"\bco-culture\b", r"\bco culture\b"],
    [r"\bcellline\b", r"\bcell-line\b", r"\bcell line\b"],
]

# ── 拉丁短语斜体软提醒(SOFT 级,只报告不阻断) ────────────────────────────────
# 封闭集:只收公认必须斜体、误报≈0 的拉丁短语。正文里裸写(未被 *...* / **...**
# 斜体标记包裹)时给软提醒。**不收** et al./e.g./i.e./vs./etc.——现代多数期刊
# 这些用正体,收了会误报/引争议。severity=soft,权重 0,不扣分、不进 --fail-on 硬集。
LATIN_ITALIC_PHRASES = [
    "in vitro", "in vivo", "ex vivo", "in situ", "in silico", "in utero",
    "de novo", "a priori", "a posteriori", "post hoc", "ad libitum",
    "per se", "in toto", "in vacuo",
]


def _latin_phrase_pattern(phrase):
    """按 CJK 安全边界(_NB/_NA)构造短语正则,词内空格容忍多空白,大小写不敏感。
    左右 ASCII 字母数字边界避免 'invitrogen' 之类连写误伤,且中文紧邻能抓。"""
    parts = [re.escape(w) for w in phrase.split()]
    return re.compile(_NB + r"\s+".join(parts) + _NA, re.IGNORECASE)


_LATIN_PATTERNS = [(p, _latin_phrase_pattern(p)) for p in LATIN_ITALIC_PHRASES]
# 已被 markdown 斜体/粗体标记包裹的片段:剥离后再扫裸写,避免误报。
# 参照 subsup 先剥离已正确标注片段的思路。[^*\n]+ 防跨多个 * / 换行的贪婪过度匹配。
_ITALIC_WRAPPED_RE = re.compile(r"\*\*[^*\n]+\*\*|\*[^*\n]+\*")

# ── Tense hints for Methods (should be past tense) ───────────────────────────
# 简单启发式:Methods 段内出现现在时第三人称单数 + 动作动词
PRESENT_TENSE_VERBS_RE = re.compile(
    r"\b(uses|performs|measures|treats|incubates|conducts|analyzes|tests|"
    r"applies|adds|washes|stains|isolates|extracts|determines|calculates)\b",
    re.IGNORECASE,
)

# ── Ref/heading/code skip filters ─────────────────────────────────────────────
HEADING_RE = re.compile(r"^#+\s+", re.MULTILINE)
CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
REF_LINE_RE = re.compile(r"^\d+\.\s+\w+", re.MULTILINE)
CITATION_RE = re.compile(r"\[\d+(?:[,\-\s]*\d+)*\]")


def _extract_prose(text):
    """Strip non-prose: code blocks, citations (for word matching)."""
    text = CODE_BLOCK_RE.sub("", text)
    return text


def check_misspellings(text):
    issues = []
    lower = text.lower()
    for wrong, right in MISSPELLINGS.items():
        # 允许后缀(-ed/-ing/-s 等),用 \w* 而非 \b 收尾
        # 但词头必须是 \b 防止 'recieve' 误匹配 'irrecieve' 之类
        pattern = re.compile(rf"\b{re.escape(wrong)}\w*\b", re.IGNORECASE)
        for m in pattern.finditer(text):
            issues.append({
                "type": "misspelling",
                "severity": "high",
                "found": m.group(0),
                "suggest": right,
                "pos": m.start(),
            })
    return issues


def check_chinese_punct(text):
    issues = []
    for ch, en in CHINESE_PUNCT.items():
        for m in re.finditer(re.escape(ch), text):
            # 跳过明确合理出现的中文上下文(如中文文献标题在 caption 里) — 简单启发:这行有 ≥3 个中文汉字则跳过
            line_start = text.rfind("\n", 0, m.start()) + 1
            line_end = text.find("\n", m.end())
            line_end = line_end if line_end != -1 else len(text)
            line = text[line_start:line_end]
            cn_chars = len(re.findall(r"[一-鿿]", line))
            if cn_chars >= 3:
                continue
            issues.append({
                "type": "chinese_punct",
                "severity": "high",
                "found": ch,
                "suggest": en,
                "pos": m.start(),
            })
    return issues


def check_academic_misspellings(text):
    """F3: 学术英文错拼(WARN). codespell 不可用时的词表路径."""
    issues = []
    for wrong, right in ACADEMIC_MISSPELLINGS.items():
        pattern = re.compile(rf"\b{re.escape(wrong)}\b", re.IGNORECASE)
        for m in pattern.finditer(text):
            issues.append({
                "type": "academic_misspelling",
                "severity": "warn",
                "found": m.group(0),
                "suggest": right,
                "pos": m.start(),
            })
    return issues


def check_chinese_typos(text):
    """F1: 中文高置信错别字(WARN). 保守词表,主观字不收."""
    issues = []
    for wrong, right in CHINESE_TYPOS.items():
        for m in re.finditer(re.escape(wrong), text):
            issues.append({
                "type": "chinese_typo",
                "severity": "warn",
                "found": wrong,
                "suggest": right,
                "pos": m.start(),
            })
    return issues


def check_halfwidth_in_cn(text):
    """D1: 中文句内夹半角标点(WARN). 仅标半角两侧紧邻汉字的高置信情形."""
    issues = []
    for pat, half, full, desc in HALFWIDTH_IN_CN:
        for m in pat.finditer(text):
            issues.append({
                "type": "halfwidth_punct_in_cn",
                "severity": "warn",
                "found": f"…{m.group(0)}…",
                "suggest": f"{desc}: '{half}' → '{full}'",
                "pos": m.start(),
            })
    return issues


# 已带 markdown 上下标或 HTML sup/sub 的片段:剥离后再扫裸写,避免误报
_SUBSUP_WRAPPED_RE = re.compile(
    r"\^[^\^\s]+\^|~[^~\s]+~|<sup>.*?</sup>|<sub>.*?</sub>",
    re.IGNORECASE | re.DOTALL,
)


def check_subsup(text):
    """D2: 应上下标却裸写(WARN). 先剥离已正确标注的片段再扫."""
    stripped = _SUBSUP_WRAPPED_RE.sub(" ", text)
    issues = []
    seen = set()
    for pat, desc in SUBSUP_PATTERNS:
        for m in pat.finditer(stripped):
            key = (m.group(0), m.start())
            if key in seen:
                continue
            seen.add(key)
            issues.append({
                "type": "subsup_bare",
                "severity": "warn",
                "found": m.group(0),
                "suggest": desc,
                "pos": m.start(),
            })
    return issues


def check_latin_italic(text):
    """拉丁短语斜体软提醒(SOFT). 未被 *...* / **...** 包裹的拉丁短语 → 提示,不阻断.
    先剥离已斜体/粗体标记的片段(其内命中不报),再在剩余文本扫裸写."""
    stripped = _ITALIC_WRAPPED_RE.sub(" ", text)
    issues = []
    for phrase, pat in _LATIN_PATTERNS:
        for m in pat.finditer(stripped):
            issues.append({
                "type": "latin_italic_missing",
                "severity": "soft",
                "found": m.group(0),
                "suggest": f"Latin phrase conventionally italicized: *{phrase}*",
                "pos": m.start(),
            })
    return issues


def check_units(text):
    issues = []
    for pat, replacement, desc in UNIT_PATTERNS:
        for m in pat.finditer(text):
            issues.append({
                "type": "unit_format",
                "severity": "medium",
                "found": m.group(0),
                "suggest": desc,
                "pos": m.start(),
            })
    return issues


def check_number_consistency(text):
    """Within a single file: if any number ≥1000 has comma AND any doesn't → inconsistent."""
    nums_no_comma = NUMBER_RE.findall(text)
    nums_with_comma = NUMBER_WITH_COMMA_RE.findall(text)
    issues = []
    # 阈值:≥4 位数字
    big_nums = [n for n in nums_no_comma if len(n) >= 4]
    if big_nums and nums_with_comma:
        issues.append({
            "type": "number_format_inconsistent",
            "severity": "low",
            "detail": f"{len(big_nums)} numbers without comma + {len(nums_with_comma)} with comma — pick one style (Nature/Cell prefer comma separators for ≥1000)",
        })
    return issues


def check_bre_ame_mixed(text):
    """BrE 与 AmE 混用才报警;单用一种不报(任由作者选).
    判定:跨所有对统计 BrE 系列总命中数与 AmE 系列总命中数,两者都 > 0 = 混用."""
    bre_total = 0
    ame_total = 0
    bre_examples = []
    ame_examples = []
    for bre, ame in BRE_AME_PAIRS:
        bre_re = re.compile(rf"\b{bre}\w*\b", re.IGNORECASE)
        ame_re = re.compile(rf"\b{ame}\w*\b", re.IGNORECASE)
        # 关键:必须包含 BrE/AmE 词根的字面字符 — 否则 'analyse' 模式会误匹配 'analyzed'(无 's')
        bre_hits = [h for h in bre_re.findall(text) if bre.lower() in h.lower()]
        ame_hits = [h for h in ame_re.findall(text) if ame.lower() in h.lower()]
        if bre_hits:
            bre_total += len(bre_hits)
            bre_examples.append(bre_hits[0])
        if ame_hits:
            ame_total += len(ame_hits)
            ame_examples.append(ame_hits[0])
    if bre_total > 0 and ame_total > 0:
        return [{
            "type": "bre_ame_mixed",
            "severity": "low",
            "detail": f"BrE/AmE mixed: BrE={bre_total} (e.g. {', '.join(bre_examples[:3])}), AmE={ame_total} (e.g. {', '.join(ame_examples[:3])})",
        }]
    return []


def check_term_consistency(text):
    issues = []
    for variants in TERM_VARIANTS:
        hits = []
        for v in variants:
            pat = re.compile(rf"\b{v}\b", re.IGNORECASE)
            matches = pat.findall(text)
            if matches:
                hits.append((v, len(matches)))
        if len(hits) >= 2:
            issues.append({
                "type": "term_variant",
                "severity": "low",
                "detail": f"multiple spellings used: " + ", ".join(f"'{v}' ({n}x)" for v, n in hits),
            })
    return issues


def check_methods_tense(text, filename):
    """Methods sections should be past tense. Heuristic: present-tense action verbs."""
    if not re.search(r"(?i)\bmethods?\b|^0?5[_-]?Methods", filename):
        return []
    issues = []
    for m in PRESENT_TENSE_VERBS_RE.finditer(text):
        issues.append({
            "type": "methods_tense",
            "severity": "low",
            "found": m.group(0),
            "suggest": "Methods is past tense — consider switching to '-ed' form",
            "pos": m.start(),
        })
    return issues[:5]  # 限制条数避免刷屏


# ── A5 内部交叉引用有效性（全稿级，非单文件）─────────────────────────────────
# 提取正文里的内部交叉引用并核对引用目标是否真实存在（章节/图/表/附录有定义）。
# 提取易误判（如散文里偶发的 "Figure 1" 既可能是引用也可能是题注），故只 WARN。
_A5_REF_SECTION = re.compile(r"\bSection\s+(\d+(?:\.\d+)*)", re.IGNORECASE)
_A5_REF_FIGURE = re.compile(r"\bFig(?:ure|\.)?\s+(\d+)", re.IGNORECASE)
_A5_REF_TABLE = re.compile(r"\bTable\s+(\d+)", re.IGNORECASE)
_A5_REF_APPENDIX = re.compile(r"\bAppendix\s+([A-Z])\b")
# 定义点（题注 / 标题）：行首（可含 markdown # 或 **）的 Figure/Table/Appendix/Section。
_A5_DEF_FIGURE = re.compile(r"^[#*\s]*Fig(?:ure|\.)?\s+(\d+)", re.IGNORECASE | re.MULTILINE)
_A5_DEF_TABLE = re.compile(r"^[#*\s]*Table\s+(\d+)", re.IGNORECASE | re.MULTILINE)
_A5_DEF_APPENDIX = re.compile(r"^[#*\s]*Appendix\s+([A-Z])\b", re.MULTILINE)
# 章节定义：markdown 标题里的前导数字号（# 2 / ## 2.1 Title）或显式 Section N。
_A5_DEF_HEAD_NUM = re.compile(r"^#{1,4}\s+(\d+(?:\.\d+)*)\b", re.MULTILINE)
_A5_DEF_HEAD_SECTION = re.compile(r"^#{1,4}.*?\bSection\s+(\d+(?:\.\d+)*)", re.IGNORECASE | re.MULTILINE)


def check_crossref_validity(files):
    """全稿级：核对内部交叉引用（Section/Figure/Table/Appendix N）目标是否存在。
    断链 → 一条 warn issue。返回 issue 列表（type=crossref_dangling）。
    files: 待扫描的 .md 路径列表（已剔除合并衍生物）。
    """
    sec_targets, fig_targets, tbl_targets, app_targets = set(), set(), set(), set()
    file_texts = []
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                raw = f.read()
        except Exception:
            continue
        file_texts.append((fp, raw))
        for m in _A5_DEF_FIGURE.finditer(raw):
            fig_targets.add(m.group(1))
        for m in _A5_DEF_TABLE.finditer(raw):
            tbl_targets.add(m.group(1))
        for m in _A5_DEF_APPENDIX.finditer(raw):
            app_targets.add(m.group(1))
        for m in _A5_DEF_HEAD_NUM.finditer(raw):
            num = m.group(1)
            sec_targets.add(num)
            parts = num.split(".")
            for k in range(1, len(parts)):
                sec_targets.add(".".join(parts[:k]))
        for m in _A5_DEF_HEAD_SECTION.finditer(raw):
            sec_targets.add(m.group(1))

    issues = []
    ref_specs = [
        (_A5_REF_SECTION, sec_targets, "Section"),
        (_A5_REF_FIGURE, fig_targets, "Figure"),
        (_A5_REF_TABLE, tbl_targets, "Table"),
        (_A5_REF_APPENDIX, app_targets, "Appendix"),
    ]
    for fp, raw in file_texts:
        text = _extract_prose(raw)
        for ref_re, targets, label in ref_specs:
            for m in ref_re.finditer(text):
                tgt = m.group(1)
                if tgt not in targets:
                    issues.append({
                        "type": "crossref_dangling",
                        "severity": "warn",
                        "file": os.path.basename(fp),
                        "found": m.group(0),
                        "suggest": f"{label} {tgt} is referenced but never defined in the manuscript",
                        "pos": m.start(),
                    })
    return issues


def check_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()
    except Exception as e:
        return {"file": filepath, "error": str(e), "issues": []}
    text = _extract_prose(raw)
    fn = os.path.basename(filepath)
    all_issues = []
    all_issues.extend(check_misspellings(text))
    all_issues.extend(check_chinese_punct(text))
    all_issues.extend(check_academic_misspellings(text))  # F3 (warn)
    all_issues.extend(check_chinese_typos(text))      # F1 (warn)
    all_issues.extend(check_halfwidth_in_cn(text))     # D1 (warn)
    all_issues.extend(check_subsup(text))              # D2 (warn)
    all_issues.extend(check_latin_italic(text))        # 拉丁斜体 (soft,只报告不阻断)
    all_issues.extend(check_units(text))
    all_issues.extend(check_number_consistency(text))
    all_issues.extend(check_bre_ame_mixed(text))
    all_issues.extend(check_term_consistency(text))
    all_issues.extend(check_methods_tense(text, fn))
    # 计分:high 扣 5/medium 扣 2/low 扣 1,起点 100
    score = 100
    severity_weight = {"high": 5, "medium": 2, "low": 1, "warn": 0, "soft": 0}
    for i in all_issues:
        score -= severity_weight.get(i.get("severity", "low"), 1)
    score = max(0, score)
    return {
        "file": filepath,
        "score": score,
        "issues_total": len(all_issues),
        "issues_by_type": dict(_count_by_type(all_issues)),
        "issues": all_issues[:30],  # 截断细节避免报告过大
    }


def _count_by_type(issues):
    c = defaultdict(int)
    for i in issues:
        c[i.get("type", "unknown")] += 1
    return c


def main():
    p = argparse.ArgumentParser(description="Proofread SCI manuscript markdown")
    p.add_argument("--manuscript-dir", default="manuscripts")
    p.add_argument("--report", default="proofread_report.json")
    p.add_argument("--threshold", type=int, default=70)
    p.add_argument("--verbose", action="store_true")
    # --fail-on: 逗号分隔的高置信 issue 类型，命中任一(count>0)即 ok=false。
    # 不传则行为不变(仅 score 阈值)。门禁用：misspelling,chinese_punct,subsup_bare
    p.add_argument("--fail-on", dest="fail_on", default="",
                   help="comma list of high-confidence issue types that force ok=false if count>0")
    args = p.parse_args()

    md_dir = Path(args.manuscript_dir)
    if not md_dir.exists():
        print(json.dumps({"ok": False, "error": f"dir not found: {md_dir}"}, ensure_ascii=False))
        sys.exit(1)
    files = sorted(md_dir.glob("*.md"))
    # Skip merge-generated derivatives (Full_Manuscript.md / Draft_Round*_Manuscript.md):
    # they carry the AUTO-GENERATED banner and duplicate the atomic sources, so
    # scanning them yields false positives (e.g. banner em-dash flagged as chinese_punct).
    files = [
        f for f in files
        if not (
            f.name.lower() == "full_manuscript.md"
            or (f.name.lower().startswith("draft_round") and f.name.lower().endswith("_manuscript.md"))
        )
    ]
    if not files:
        print(json.dumps({"ok": True, "status": "no_files", "manuscript_dir": str(md_dir)}, ensure_ascii=False))
        return 0

    results = [check_file(str(f)) for f in files]
    avg = round(sum(r["score"] for r in results) / len(results), 1)
    total_issues = sum(r["issues_total"] for r in results)
    all_pass = all(r["score"] >= args.threshold for r in results)
    # --fail-on：高置信类别零容忍。汇总各文件 issues_by_type 计数，命中即拉低 ok。
    fail_on = [t.strip() for t in args.fail_on.split(",") if t.strip()]
    fail_on_hits = {}
    if fail_on:
        agg = defaultdict(int)
        for r in results:
            for t, n in r.get("issues_by_type", {}).items():
                agg[t] += n
        fail_on_hits = {t: agg[t] for t in fail_on if agg.get(t, 0) > 0}
        if fail_on_hits:
            all_pass = False
    # A5 全稿级内部交叉引用有效性（断链 → warn，不影响 score / all_pass，保守）。
    crossref_issues = check_crossref_validity([str(f) for f in files])
    summary = {
        "ok": all_pass,
        "avg_score": avg,
        "total_issues": total_issues,
        "files_checked": len(results),
        "threshold": args.threshold,
        "fail_on": fail_on,
        "fail_on_hits": fail_on_hits,
        "crossref_dangling": len(crossref_issues),
        "crossref_issues": crossref_issues,
        "files": results,
    }
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    # 简短控制台输出（剔除明细列表，只留计数）
    print(json.dumps(
        {k: v for k, v in summary.items() if k not in ("files", "crossref_issues")},
        ensure_ascii=False))
    if args.verbose:
        for r in results:
            if r["issues_total"]:
                print(f"  [{r['file']}] score={r['score']} types={r['issues_by_type']}")
    # 诚实化：PASS 只代表字符级形式层过关，别当成内容/科学层已核验（stderr，不污染 stdout JSON）。
    if all_pass:
        sys.stderr.write(
            "PROOFREAD: PASS — 仅覆盖字符级形式层（拼写/标点/上下标/交叉引用编号）；"
            "论点是否被文献支持、结论科学价值未自动核验。\n")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
