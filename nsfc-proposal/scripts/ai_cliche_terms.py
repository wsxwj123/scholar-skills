"""去 AI 套话词表单一真源（round25）。

一张表登记「哪条套话、哪几家收」：各家从 EFFECTIVE_EN / EFFECTIVE_ZH 按技能名取表。
加一条套话 = 往主表追加一行；改一家的收录范围 = 改那一行的成员集合。没有第二处可改。
唯一契约：.devflow/INTERFACE-round25.md；方案与裁决清单：.devflow/PLAN-round25.md。

硬约束（INTERFACE §1）：纯数据、零 import（含 re——正则以**字符串**登记，编译由消费
端做）；无函数、无类、无 __main__，唯一可执行逻辑是末尾两行推导式；中文 UTF-8 原样
落盘、不转义（「……」被转义成 \\uXXXX 后没人认得出那是留白）。

消费 6 家：general-sci-writing / review-writing / nsfc-proposal / polish-sci /
revise-sci / reviewer-simulator（rsim 只用 §2.4 正则条目，不查 EFFECTIVE_*）。
sci2doc 与 reviewer-response-sci 的词表是正则+严重度形态，收编会改判定，
本轮有意不进（PLAN-round25 §5）。
"""

# ── 成员层（INTERFACE §2.1：按「为什么这几家收」命名）────────────────────────
_ALL5 = frozenset({
    "general-sci-writing", "review-writing", "nsfc-proposal",
    "polish-sci", "revise-sci",
})
L_ALL5 = _ALL5  # 五家共识（_ALL5 的别名，供主表可读）
# nsfc 缺的条目另由本家 BANNED_PATTERNS/OVERUSE/VAGUE 覆盖，收进来会双报，
# 且把「综上所述/总而言之 ≥3 次才报」的逃生口变成一次即拦（PLAN D8）。
L_NO_NSFC = frozenset({
    "general-sci-writing", "review-writing", "polish-sci", "revise-sci",
})
# polish/revise 侧对应的是「……」留白形态（PLAN D5/D6/D7）。
L_NO_POLISH_REVISE = frozenset({
    "general-sci-writing", "review-writing", "nsfc-proposal",
})
L_GSW_RW_ONLY = frozenset({"general-sci-writing", "review-writing"})  # PLAN D4
# 🔴 故意永不生效的留白条目专用层（PLAN D9，用户明确裁定）：条目字面含「……」，
# polish/revise 消费端 `bare = term.replace("……", "")` 后成「随着的发展」这类
# 不可能出现的串。不许去掉省略号、不许改成正则——那等于把用户否决过的判定偷偷打开。
L_INERT = frozenset({"polish-sci", "revise-sci"})
L_REVISE_ONLY = frozenset({"revise-sci"})  # 英文两条连接词（PLAN D1）

# ── 主表（INTERFACE §2.2：唯一真源，行序 = polish/revise 现役 tuple 顺序）──────
# polish/revise 是 tuple 消费、顺序可观测（marker 输出顺序），新词一律追加到表尾；
# gsw/rw/nsfc 是 set 消费、顺序不敏感。
EN_TABLE = (
    ("delve into", L_ALL5),
    ("comprehensive landscape", L_ALL5),
    ("pivotal role", L_ALL5),
    ("realm", L_ALL5),
    ("tapestry", L_ALL5),
    ("underscore", L_ALL5),
    ("testament", L_ALL5),
    ("it is well known", L_ALL5),
    ("it is worth noting", L_ALL5),
    ("it should be noted", L_ALL5),
    ("importantly", L_ALL5),
    ("interestingly", L_ALL5),
    ("remarkably", L_ALL5),
    ("notably", L_ALL5),
    ("in recent years", L_ALL5),
    ("a growing body of evidence", L_ALL5),
    ("has garnered significant attention", L_ALL5),
    ("plays a crucial role", L_ALL5),
    ("a plethora of", L_ALL5),
    ("myriad of", L_ALL5),
    ("in the context of", L_ALL5),
    ("shed light on", L_ALL5),
    ("pave the way", L_ALL5),
    ("of paramount importance", L_ALL5),
    ("a key player", L_ALL5),
    ("moreover", L_REVISE_ONLY),
    ("furthermore", L_REVISE_ONLY),
)

ZH_TABLE = (
    ("值得注意的是", L_NO_NSFC),
    ("值得一提的是", L_ALL5),
    ("众所周知", L_ALL5),
    ("不言而喻", L_ALL5),
    ("综上所述", L_NO_NSFC),
    ("总而言之", L_NO_NSFC),
    ("总的来说", L_ALL5),
    ("毋庸置疑", L_ALL5),
    ("显而易见", L_ALL5),
    ("至关重要", L_NO_NSFC),
    ("举足轻重", L_NO_NSFC),
    ("深入探讨", L_NO_NSFC),
    ("近年来", L_NO_NSFC),
    ("随着……的发展", L_INERT),
    ("在……的背景下", L_INERT),
    ("为……奠定了基础", L_INERT),
    ("发挥着重要作用", L_ALL5),
    ("扮演着重要角色", L_ALL5),
    ("不仅如此", L_NO_POLISH_REVISE),
    ("在此背景下", L_NO_POLISH_REVISE),
    ("发挥关键作用", L_NO_POLISH_REVISE),
    ("越来越多的证据表明", L_GSW_RW_ONLY),
)

# ── 中文正则条目（INTERFACE §2.4：nsfc ↔ reviewer-simulator 共用）──────────────
# 三元组 (pattern, code, suggestion)，正则以字符串登记（消费端 re.finditer 直接吃
# 字符串）。内容与两家 2026-08-17 现役条目逐字节相同，一字不改。
# 12 条共有项：
P_NOT_BUT = (r"不是[^。]{1,30}?而是", "pattern_not_but", "改为直接陈述句，避免对比模板")
P_NOT_ONLY_BUT_ALSO = (r"不仅[^。，]{1,30}?[，,][^。]{1,30}?而且",
                       "pattern_not_only_but_also", "拆成两句事实陈述")
P_FILLER_NOTE = (r"值得注意的是", "filler_phrase", "删除该提示语，直接给结论")
P_FILLER_POINT = (r"需要指出的是", "filler_phrase", "删除该提示语，直接给证据")
P_OVERSTATEMENT = (r"至关重要|举足轻重|不可或缺", "overstatement", "用具体数据替代形容词")
P_GENERIC_SIGNIFICANCE = (r"具有重要的[^。]{0,20}意义和[^。]{0,20}价值",
                          "generic_significance", "删除或改写为具体贡献陈述")
P_NEWS_STYLE = (r"日益增长|蓬勃发展|方兴未艾", "news_style", "替换为具体数据或趋势描述")
P_HOLLOW_VERB = (r"深入探讨|系统研究|全面分析", "hollow_verb",
                 "改为具体研究行为描述，如'比较X与Y的差异'")
P_HYPERBOLE = (r"革命性的|颠覆性的|突破性的", "hyperbole_rhetoric", "用数据/事实说明程度")
P_PARALLELISM = (r"是[^，。]{1,20}，是[^，。]{1,20}，更是", "parallelism_rhetoric",
                 "用一个精准表述替代排比")
P_RHETORICAL_Q = (r"难道不是[^？]{0,30}？", "rhetorical_question", "改为陈述句")
P_LEADING_Q = (r"那么，[^？]{1,30}？", "leading_question", "直接阐述，删除设问")

# 差异层（命名带家名，杜绝误用）：
# nsfc 比喻两条（2026-07 一刀切禁）。注意 sci2doc check_quality.py 的同名检查与
# 这两条**实测不等**（sci2doc 多 `好像(?!素)`，且 `像…一样` 用 `.*?` 能跨句读点），
# 是有意分叉，别对齐（PLAN D13）。
NSFC_METAPHOR_VERB = (r"如同|好比|仿佛|犹如|恰似|宛如|宛若|像[^素片][^。，]{0,20}一样",
                      "metaphor_rhetoric", "删除比喻表达，直接陈述事实或功能")
NSFC_METAPHOR_NOUN12 = (r"的(?:桥梁|基石|钥匙|引擎|灯塔|摇篮|沃土|温床|催化剂|助推器|风向标)",
                        "metaphor_noun", "用准确的功能描述替代比喻性名词")
# rsim 三条：机械过渡在 rsim 是 1 次即 ERROR；nsfc 同正则走 OVERUSE ≥3 阈值分支、
# code/suggestion 都不同，属 PLAN D10 未裁决项，故 nsfc 那两条**不进**本共享件。
RSIM_TEMPLATE_TRANSITION = (r"综上所述|总而言之", "template_transition", "用事实句结束段落")
RSIM_AI_TRANSITION = (r"在此基础上|鉴于此", "ai_transition", "直接写因果关系")
RSIM_METAPHOR_NOUN4 = (r"的桥梁|的基石|的钥匙|的引擎", "metaphor_rhetoric",
                       "直接陈述其功能或作用")

# 模糊表述 6 条（两家逐字节相同，含 suggestion 文案）；两家直接
# `VAGUE_PATTERNS = list(VAGUE_TABLE)`。
VAGUE_TABLE = (
    (r"近年来", "replace_with_exact_year_range", "改为具体年份范围，如2020年以来"),
    (r"大量研究表明", "replace_with_named_citations", "改为明确作者+文献编号"),
    (r"取得了显著进展", "replace_with_specific_progress", "改为具体进展内容"),
    (r"广泛应用", "replace_with_specific_scenarios", "列出应用场景"),
    (r"越来越多的证据", "replace_with_specific_evidence", "具体引用几项关键证据"),
    (r"已有研究发现", "replace_with_named_researcher", "指明具体研究者和发现"),
)

# ── 解析表（INTERFACE §2.3：模块唯一的可执行逻辑，勿在其后再加任何语句）────────
EFFECTIVE_EN = {s: tuple(t for t, m in EN_TABLE if s in m) for s in _ALL5}
EFFECTIVE_ZH = {s: tuple(t for t, m in ZH_TABLE if s in m) for s in _ALL5}
