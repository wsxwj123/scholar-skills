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
    # 禁用修辞：夸张
    (r"革命性的|颠覆性的|突破性的", "hyperbole_rhetoric", "用数据/事实说明程度"),
    # 禁用修辞：排比（"...是A，是B，更是C"）
    (r"是[^，。]{1,20}，是[^，。]{1,20}，更是", "parallelism_rhetoric", "用一个精准表述替代排比"),
    # 禁用修辞：比喻（2026-07 新政一刀切禁；比喻动词，正则对齐 sci2doc check_quality.py）
    (r"如同|好比|仿佛|犹如|恰似|宛如|宛若|像[^素片][^。，]{0,20}一样", "metaphor_rhetoric", "删除比喻表达，直接陈述事实或功能"),
    # 禁用修辞：比喻性名词（...的桥梁/基石/钥匙）
    (r"的(?:桥梁|基石|钥匙|引擎|灯塔|摇篮|沃土|温床|催化剂|助推器|风向标)", "metaphor_noun", "用准确的功能描述替代比喻性名词"),
    # 禁用修辞：反问
    (r"难道不是[^？]{0,30}？", "rhetorical_question", "改为陈述句"),
    # 禁用修辞：设问
    (r"那么，[^？]{1,30}？", "leading_question", "直接阐述，删除设问"),
]

# 逃生口：机制类过渡词是中标本子常态，一刀切全禁反而制造"被洗过"的均匀质感。
# 这些改为"过量才报"——单篇出现 < 阈值不报，达到阈值才提示（WARNING，不硬拦）。
# 注：比喻已一刀切禁（2026-07 新政，见 BANNED_PATTERNS 的 metaphor_rhetoric/metaphor_noun），不再走过量豁免。
OVERUSE_THRESHOLD = 3
OVERUSE_PATTERNS = [
    (r"综上所述|总而言之", "template_transition_overuse", "机械过渡词过量，保留 1~2 处、其余用事实句收尾"),
    (r"在此基础上|鉴于此", "ai_transition_overuse", "过渡模板过量，部分改为直接写因果关系"),
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


# ── 字符级检查（移植自 general-sci proofread.py）：D1半角标点/F2英文拼写=ERROR硬拦，D2上下标/F1错别字=WARN ──

# D1：中文句内夹半角标点（高误报区，极度保守：仅标半角两侧紧邻汉字的高置信情形）
# 半角 , ; : ( ) → 全角 ， ； ： （ ）；DOI/URL/数字区间天然不触发
HALFWIDTH_IN_CN = [
    (re.compile(r"([一-鿿]),([一-鿿])"), ",", "，", "中文句内半角逗号"),
    (re.compile(r"([一-鿿]);([一-鿿])"), ";", "；", "中文句内半角分号"),
    (re.compile(r"([一-鿿]):([一-鿿])"), ":", "：", "中文句内半角冒号"),
    (re.compile(r"([一-鿿])\(([一-鿿])"), "(", "（", "中文句内半角左括号"),
    (re.compile(r"([一-鿿])\)([一-鿿])"), ")", "）", "中文句内半角右括号"),
]

# D2：应上下标却裸写的化学式/标记（先剥离已正确标注的 ^..^ / ~..~ / sup/sub 再扫）
# 边界用 (?<![A-Za-z0-9])/(?![A-Za-z0-9]) 而非 \b：中文在 Unicode re 下属 \w，
# \b 在“汉字H2O汉字”处不成立，故用显式 ASCII 边界，确保中文紧邻时也能抓到，
# 同时不误吞 XH2OY（前后接字母数字时不报）。带电荷的 Na+/Ca2+ 右边界也用 _SE。
_SS = r"(?<![A-Za-z0-9])"  # 左：前面不是字母数字
_SE = r"(?![A-Za-z0-9])"   # 右：后面不是字母数字
SUBSUP_PATTERNS = [
    (re.compile(_SS + r"H2O2" + _SE), "H2O2 → H~2~O~2~（下标）"),
    (re.compile(_SS + r"H2O" + _SE), "H2O → H~2~O（下标 2）"),
    (re.compile(_SS + r"CO2" + _SE), "CO2 → CO~2~（下标 2）"),
    (re.compile(_SS + r"O2" + _SE), "O2 → O~2~（下标 2）"),
    (re.compile(_SS + r"N2" + _SE), "N2 → N~2~（下标 2）"),
    (re.compile(_SS + r"NH3" + _SE), "NH3 → NH~3~（下标 3）"),
    (re.compile(_SS + r"SO2" + _SE), "SO2 → SO~2~（下标 2）"),
    (re.compile(_SS + r"Na\+" + _SE), "Na+ → Na^+^（上标电荷）"),
    (re.compile(_SS + r"Ca2\+" + _SE), "Ca2+ → Ca^2+^（上标电荷）"),
    (re.compile(_SS + r"IC50" + _SE), "IC50 → IC~50~（下标 50）"),
    (re.compile(_SS + r"EC50" + _SE), "EC50 → EC~50~（下标 50）"),
    (re.compile(_SS + r"LD50" + _SE), "LD50 → LD~50~（下标 50）"),
    (re.compile(_SS + r"(\d+(?:\.\d+)?)\s?(cm|mm|nm|μm|um|m)2" + _SE), "面积单位 如 cm2 → cm^2^（上标指数）"),
    (re.compile(_SS + r"(\d+(?:\.\d+)?)\s?(cm|mm|nm|μm|um|m)3" + _SE), "体积单位 如 cm3 → cm^3^（上标指数）"),
]
_SUBSUP_WRAPPED_RE = re.compile(
    r"\^[^\^\s]+\^|~[^~\s]+~|<sup>.*?</sup>|<sub>.*?</sub>",
    re.IGNORECASE | re.DOTALL,
)

# F2：英文高置信拼写错误（固定错拼表，键=错拼，值=正确）。
# 只收"永不是合法英文词、也不像基因符号/缩写/化学式"的铁错拼，误报率≈0，故定为 ERROR 硬拦。
# 与 F1 中文错别字的关键区别：中文"登陆/做为"在个别语境可能合法（登陆作战），故 F1 维持 WARNING；
# 而 occured/recieve 这类字符串在英文里从不成立，置信度更高，可硬拦。
ENGLISH_MISSPELLINGS = {
    "occured": "occurred", "occuring": "occurring", "occurance": "occurrence",
    "occurence": "occurrence", "recieve": "receive", "recieved": "received",
    "seperate": "separate", "seperately": "separately", "definately": "definitely",
    "neccessary": "necessary", "accomodate": "accommodate", "enviroment": "environment",
    "existance": "existence", "acheive": "achieve", "acheived": "achieved",
    "arguement": "argument", "begining": "beginning", "beleive": "believe",
    "comparision": "comparison", "consistant": "consistent", "goverment": "government",
    "paralell": "parallel", "persistant": "persistent", "prefered": "preferred",
    "refered": "referred", "relevent": "relevant", "succesful": "successful",
    "successfull": "successful", "untill": "until", "writen": "written",
}
# 英文错拼用 ASCII 边界（同 D2）：允许汉字紧邻也能抓（如"细胞occured了"），
# 但不匹配更长英文词的内部（如 reoccured 不误报），且大小写不敏感。
_EN_MISSPELL_RE = re.compile(
    _SS + r"(" + "|".join(re.escape(w) for w in ENGLISH_MISSPELLINGS) + r")" + _SE,
    re.IGNORECASE,
)

# F1：中文高置信错别字/成语误写（保守词表，主观字"的/地/得"不收）。键=错，值=对。
CHINESE_TYPOS = {
    "帐号": "账号", "登陆": "登录", "既使": "即使", "按装": "安装",
    "做为": "作为", "拌随": "伴随", "迫不急待": "迫不及待",
    "再接再励": "再接再厉", "一如继往": "一如既往", "言简意骇": "言简意赅",
    "甘败下风": "甘拜下风", "察颜观色": "察言观色", "脉博": "脉搏",
    "松驰": "松弛", "竭泽而鱼": "竭泽而渔", "金榜提名": "金榜题名",
    "美仑美奂": "美轮美奂", "病入膏盲": "病入膏肓", "穿流不息": "川流不息",
}


def check_halfwidth_in_cn(text: str) -> list[dict]:
    """D1：中文句内夹半角标点（ERROR，硬阻断）。仅标半角两侧紧邻汉字的高置信情形。
    中文标书正文应全角标点；半角两侧紧邻汉字误报率极低，故定为 ERROR 由 scan 门禁拦截。"""
    out = []
    for pat, half, full, desc in HALFWIDTH_IN_CN:
        for m in pat.finditer(text):
            out.append({
                "severity": "ERROR",
                "code": "halfwidth_punct_in_cn",
                "span": [m.start(), m.end()],
                "text": m.group(0),
                "suggestion": f"{desc}：'{half}' → '{full}'",
            })
    return out


def check_subsup(text: str) -> list[dict]:
    """D2：应上下标却裸写（WARN）。先剥离已正确标注的片段再扫，避免误报。"""
    stripped = _SUBSUP_WRAPPED_RE.sub(" ", text)
    out = []
    seen = set()
    for pat, desc in SUBSUP_PATTERNS:
        for m in pat.finditer(stripped):
            key = (m.group(0), m.start())
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "severity": "WARNING",
                "code": "subsup_bare",
                "span": [m.start(), m.end()],
                "text": m.group(0),
                "suggestion": desc,
            })
    return out


def check_chinese_typos(text: str) -> list[dict]:
    """F1：中文高置信错别字（WARN）。保守词表，主观字不收。"""
    out = []
    for wrong, right in CHINESE_TYPOS.items():
        for m in re.finditer(re.escape(wrong), text):
            out.append({
                "severity": "WARNING",
                "code": "chinese_typo",
                "span": [m.start(), m.end()],
                "text": wrong,
                "suggestion": f"错别字：'{wrong}' → '{right}'",
            })
    return out


def check_english_spelling(text: str) -> list[dict]:
    """F2：英文高置信拼写错误（ERROR，硬阻断）。固定错拼表，铁错拼从不合法，误报率≈0。"""
    out = []
    for m in _EN_MISSPELL_RE.finditer(text):
        wrong = m.group(0)
        right = ENGLISH_MISSPELLINGS[wrong.lower()]
        out.append({
            "severity": "ERROR",
            "code": "english_misspelling",
            "span": [m.start(), m.end()],
            "text": wrong,
            "suggestion": f"英文拼写错误：'{wrong}' → '{right}'",
        })
    return out


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

    # 过量才报：机制类过渡词/比喻仅在单篇达到阈值时提示（WARNING，不硬拦）
    for pattern, code, suggestion in OVERUSE_PATTERNS:
        matches = list(re.finditer(pattern, text))
        if len(matches) >= OVERUSE_THRESHOLD:
            for m in matches:
                issues.append(
                    {
                        "severity": "WARNING",
                        "code": code,
                        "span": [m.start(), m.end()],
                        "text": m.group(0),
                        "suggestion": f"{suggestion}（全文出现 {len(matches)} 次，阈值 {OVERUSE_THRESHOLD}）",
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

    # B1：装饰性破折号（硬门禁，禁止使用：severity=ERROR，scan 门禁拦截）
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

    # B2：scare quotes（硬门禁，禁止使用：severity=ERROR，scan 门禁拦截；启发式，可能有少量误报）
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

    # 字符级：D1 中文句内半角=ERROR、F2 英文拼写=ERROR（硬拦）；D2 上下标裸写、F1 中文错别字=WARN
    issues.extend(check_halfwidth_in_cn(text))
    issues.extend(check_english_spelling(text))
    issues.extend(check_subsup(text))
    issues.extend(check_chinese_typos(text))

    return {"count": len(issues), "issues": issues}


def _count_cn_chars(s: str) -> int:
    """计算字符串中中文字符数（用于句长提醒判断）。"""
    return sum(1 for c in s if "一" <= c <= "鿿")


# 逃生口：机制类长句（含因果/条件/递进连接词）在中标本子里是严密表达的常态，予以豁免。
MECHANISM_CONNECTORS = ("通过", "从而", "进而", "使得", "导致", "因而", "借助", "基于", "利用", "由于", "以及", "从而使")


def rhythm_check(text: str) -> dict:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    issues = []          # 计入 count 的节奏问题
    advisories = []      # 软提醒：超长句，不计入 count、不阻断
    openers = []

    for idx, para in enumerate(paragraphs, 1):
        sents = [s for s in re.split(r"[。！？!?]", para) if s.strip()]
        lens = [len(s.strip()) for s in sents]

        # ── 中文句长软提醒（>50 中文字符）：机制类长句豁免；其余仅提示不阻断 ──
        for sent_idx, sent in enumerate(sents, 1):
            cn_len = _count_cn_chars(sent)
            if cn_len > 50 and not any(c in sent for c in MECHANISM_CONNECTORS):
                advisories.append(
                    {
                        "paragraph": idx,
                        "sentence": sent_idx,
                        "type": "cn_sentence_too_long",
                        "severity": "advisory",
                        "cn_chars": cn_len,
                        "text": sent.strip()[:60] + ("…" if len(sent.strip()) > 60 else ""),
                        "suggestion": "中文单句超50字（软提醒，不阻断）；若非机制类严密长句，可考虑拆分",
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

    # count 只含硬节奏问题；超长句作为 advisories 单列，不计入 count（故不推高 D-07 至阻断）
    return {"count": len(issues), "issues": issues + advisories, "advisories": advisories}


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
