---
name: polish-sci
version: 2.25.2
description: 纯论文润色全管道。输入一份已写完的稿子(无审稿意见),逐段提升语言表达,绝不改内容/数据/结论。触发词：润色、polish、语言润色、润色论文、polish paper、language polish、proofread manuscript、母语化、润色稿子。路由说明：与revise-sci区分,revise-sci由审稿意见驱动、只改被点名片段;polish-sci无意见、全文逐段润色覆盖每一段。与general-sci-writing区分,gsw从零写新稿,polish-sci只润色现成稿。
---

# Polish-Sci

**【Python 解释器探测·开工第一件事，一次探测全程沿用】** 本文命令里写的 `python3` / `python` 只是 macOS/Linux 的习惯写法，不是硬性要求。动手前先跑一次 `python3 --version`：
- 打印出正常版本号 → 本次会话所有命令照抄用 `python3`。
- 报 command not found、没有任何输出、或弹出应用商店 → 改跑 `python --version`，能出版本号就把后续所有命令里的解释器统一换成 `python`。注意 Windows 自带一个 0 字节的 `python3` 占位程序，`python3 --version` 弹商店或无输出就是撞上了它，**不算有 python3**，按"没有"处理（用户也可在 设置 → 应用 → 应用执行别名 里关掉 `python3.exe`）。
- 反过来 `python` 出不了版本号就换 `python3`（macOS 12.3 起系统不再自带 `python`）。
- 两个都出不了版本号 = 这台机器没装 Python，停下来告诉用户先安装，不要硬跑。
- 探测只做这一次，之后所有命令沿用同一个名字，不要每条命令都再试。

> 🔁 **每次进入/续写先接续**:开工或换会话续写前,先跑 `env_preflight` 打印的 **RESUME_CMD**(`python <polish-sci>/scripts/session_journal.py resume --root <project_root>`),把接续报告贴给用户并打一次接续握手(确认进度到哪、之前的要求都读了、下一步做什么),等用户确认再动手。用户中途插入任何临时要求,立刻用 **LOG_CMD**(`session_journal.py log --root <project_root> --note "<原话>"`)记进 `decisions_log.md`,后续会话必读必守。

## Overview
本技能只做一件事,纯语言润色一份已写完的稿子。输入是完整稿(md 或 docx),没有审稿意见。输出是逐段润色后的稿子,加一份逐段改动报告。**默认走交互式逐段润色**(每段先贴原文/润色/逐处改动给你看、你确认或要求调整后才写回,见"交互式逐段润色协议"专节),方便你边润边对照改自己的原稿。

核心约束,只提升语言表达,绝不改内容、数据、结论。润色覆盖全文每一段,不是只改被点名的片段。

not_for(以下情况不要用本技能):
- 从零写新稿,用 general-sci-writing。
- 审稿意见驱动改稿(收到 reviewer comments / 退稿信),用 revise-sci。
- 写综述,用 review-writing。

工作流是脚本闸门式的。脚本只负责拆分、生成润色任务包、校验红线,真正的语言改写由主 agent 按本文 prompt 逐段执行。不要跳步,不要让脚本假装自己会改写。

## 📁 references/ 参考文件地图(按需 Read,不要靠记忆复述其内容)

| 必须 Read 的时机 | 文件 |
|---|---|
| 每段改写前 | `references/anti-ai-protocol.md` |
| 第 3 步逐段润色前 | `references/interaction-protocol.md` |
| 第 5 步委托盲检前 | `references/dod-protocol.md` |
| 第 7 步 merge/导出前 | `references/output-contract.md` |
| 用户问"AI 改坏了怎么办"时 | `references/user-selfhelp.md` |

## 🔴 Intake Gate(开工前必须确认)
🛑 STOP：拿到稿子后,先与用户确认四件事,再动工:

1. **输入稿路径**,md 还是 docx。docx 需要本机已装 python-docx。
2. **语言**,中文还是英文。决定句长上限(英文≤30词 / 中文≤50字)与去AI规则分支。
3. **目标期刊 + 美式/英式拼写(US / UK English)**。目标期刊决定语域与用词习惯(可留白,建议给出);英文稿必须定 US 还是 UK,它决定拼写(color/colour、analyze/analyse)、标点(引号与句号位置)、以及被动语态偏好,全稿一把尺子,不得混用。中文稿此项记"N/A"。
4. **润色强度**,light / standard / deep。
   - light,只去AI套话、修语法、拆超长句,保留原措辞骨架。
   - standard,默认,在 light 基础上做母语化、术语统一、被动语态向目标区间靠拢。
   - deep,在 standard 基础上做段内句序与衔接优化,但仍不改任何论点与数据。
5. **是否要 docx 导出**,默认只出 md。

确认这四项 + 目标 project_root 后,先跑**环境预检（软门禁）**:`python scripts/env_preflight.py <project_root> --py docx`,写 `env_status.json`,末行 `PRECHECK: OK|ASK|BLOCKED`。`BLOCKED`(Python 过低)→停并引导升级;`ASK`(缺 git/python-docx 等可选工具)→逐项问用户是否安装并给指引,用户答"已装/不装"后才继续;`OK`→继续。再进 Pipeline。

### 📋 开场监工卡(每次启动必须原样打印给用户)
确认完上述四项、跑完预检后,**每次开工都要把下面这张卡贴给用户**,让用户知道该盯什么:

> **这次润色你要盯的几件事:**
> 1. 我**只动语言**,绝不改你的数据、结论、引用标记、专名/单位。你若看到某处数值、结论或引用被改了,**立刻喊停**,那是越界。
> 2. 我默认**逐段停**:每段给你看「原文 → 润色后 → 改了哪几处」,请你每段核对**意思没被改**再放行。
> 3. 你可以让我"连续润完不停",但那样就**失去逐段核对**,润坏了只能等最后的合并稿兜底才发现,**慎选**。
> 4. 红线由脚本做集合比对(引用/数值/专名),但脚本只拦得住"能从文本判定"的越界;**语义有没有被悄悄改,最终要靠你逐段看**。

## Red Lines(一字不改)
以下内容润色时绝对不动,脚本会做集合比对拦截:
- 引用标记 `[n]`、DOI 字符串。
- 数值、统计量、p 值、置信区间、`n=N`、百分比、单位。
- 基因、蛋白、试剂、细胞系、物种名。
- 任何改动会改变科学论断的 token。

每段 `meaning_changed` 必须为 false,但**改写方自填的 false 不作数**(标 false 即蒙混)。语义等价的唯一权威是独立 PL-G11 盲检subagent的裁决:strict_gate 交付前会读 `<root>/.review_return_polish-dod.json`,要求 PL-G11 verdict==pass 且证据非空;缺独立裁决即视为"未核",fail-closed 拦下(见下方 ⑥/PL-G11)。脚本的数值/引用集合比对只补语义盲区的一部分,不替代盲检。

## 字符级排版契约(等同红线)
行内格式标记与上方红线**同级**,润色时逐字保留其位置与配对,不得增删、不得错配:
- **斜体** `*…*`,标注物种(`*E. coli*`)、基因(`*TP53*`)、统计符号(`*p*` 值、`*t*`、`*F*`、`*r*`、`*n*` 作变量时)。原文已斜体的,润色后仍斜体且范围不变。
- **上标** `<sup>…</sup>`,如 `10<sup>6</sup>`、`cm<sup>2</sup>`、`O<sub>2</sub>` 的对应上标场景。
- **下标** `<sub>…</sub>`,如 `H<sub>2</sub>O`、`CO<sub>2</sub>`、`Ca<sup>2+</sup>` 的对应下标。
- **加粗** `**…**`,保留原稿强调位置,不新增、不删除。

硬约束:
- 标记成对出现,改写后开闭标签数量与配对必须守恒(每个 `<sup>` 对一个 `</sup>`,每个 `*` 成对)。
- 禁止裸写需要排版的字符,如 `H2O` 必须写 `H<sub>2</sub>O`、`10^6` 必须写 `10<sup>6</sup>`、基因斜体不可退化为正体。
- 标记内的字符属红线,不可改动其中的数值/专名;只可改标记**外**的散文。

## Anti-AI 规则(检测见 common.py,分级见 strict_gate.py)
去AI检测由 `find_ai_style_markers`(scripts/common.py)统一执行,润色后残留即记 flag。**但阻断与否分两级**(分级在 `strict_gate.is_soft_ai_marker`),学术散文里长句、-ing 分词、修辞铺陈本是正当修辞手段,一刀切硬禁会把作者文风削平,故这些降为软提示;但 AI 套话主干与**破折号**硬拦。

**硬拦项(strict_gate 阻断交付,exit 1)**:
- AI 套话禁词表(delve into、pivotal role、underscore、testament、It is worth noting that、值得注意的是、综上所述、至关重要 等,中英双语,见 common.py 的 `AI_STYLE_BANNED_PATTERNS` 与 `AI_CLICHE_TERMS_EN/ZH`)。这些是 AI 腔的硬指纹,润色后一律清零。
- **去AI必禁三项——修辞性破折号(`—` / `——` / em-dash)、scare quotes(普通短语裹双引号)、解释性冒号(概念冒号后接句子片段)——三者禁止使用,硬拦阻断交付**。strict_gate 对这三项 fail-close,命中即 exit 1,不放行、不交作者取舍。

📖 软提示分级与非散文豁免 → 每段改写前先 Read [references/anti-ai-protocol.md](references/anti-ai-protocol.md)。

本 SKILL.md 文本自身也遵守上述去AI规则。

## ❌ 禁止动作清单(润色时绝不做)
对现有规则的集中索引,逐条对应正文已有约束,违反任一即 strict_gate 或盲检拦截:
- ❌ 改动数值/统计量/p值/n=N/百分比/单位/引用标记[n]/DOI/专名(基因蛋白细胞系物种),见 Red Lines
- ❌ 升级不确定性动词(may/suggest/可能 改成 prove/demonstrate/证实),见 Polish Prompt #5
- ❌ 凭空增加原文没有的程度词(significantly/extensively/显著 等),等同升级语气,meaning_changed 必为 false
- ❌ 为求变化做同义替换、破坏全文术语一致,见 Polish Prompt #4
- ❌ 裸写需排版字符(H2O 不写成 H<sub>2</sub>O、10^6 不写成 10<sup>6</sup>、基因斜体退化为正体),见 字符级排版契约
- ❌ 润色后残留 AI 套话禁词(delve into / 值得注意的是 等)或**去AI必禁三项(装饰性破折号 —/—— 、scare quotes、解释性冒号)**,均 Anti-AI **硬拦**、命中即 exit 1;长句/-ing 拖尾为软提示(记报告不阻断),别硬删削平文风
- ❌ 只改被点名片段而非全文逐段覆盖,本技能是纯润色,覆盖每一段
- ❌ 未经用户确认就把该段写回 polished/,见 交互式逐段润色协议
- ❌ 主 agent 自评 DoD 不委托独立盲检subagent,见 DoD 委托盲检(强制)

## DoD 自检清单(润色收口)
机器可读真源,`references/dod_checklist.json` 的 `polish-dod` gate。strict_gate 运行前,必须委托独立subagent盲检。

📖 **主 agent 不得自评 DoD**;PL-G1~PL-G14 判据、委托四步细则、【P4·降级告警】(派不出独立subagent时绝不自评自过) → **第 5 步盲检前先 Read [references/dod-protocol.md](references/dod-protocol.md)**。

**PL-G11 科学内容零改动 = 语义等价的唯一权威**:改写方在 polished/<idx>.json 里自填 `meaning_changed=false` 只是自证、不足信;strict_gate 交付前会读独立subagent写回的 `<root>/.review_return_polish-dod.json`,要求 PL-G11 verdict==pass 且证据非空,缺独立裁决/非 pass/空证据一律 fail-closed。即"没有独立盲检 = meaning 未核 = 拦",自填 false 不能替代。

**① DoD 停**:盲检(尤其 PL-G11 语义等价)通过后,**不要直接 merge 交付**。先把每一项(PL-G1~PL-G14)的裁决结论逐条摆给用户看(通过/软提示/需人工确认的都列清),然后 **🛑 HALT 等用户确认**,用户点头才进 strict_gate + merge + report。这是交付前最后一道人肉闸,用户此刻仍可喊停或补要求(补要求即 LOG_CMD 记入决定日志)。

🔴 **结构完整性闸口(前置)**,合并后立即核对段落数与原稿一致、无错位、引用编号连续,再进交付。

通过条件,delegate_review verify 通过 + strict_gate.py exit 0 输出 `STRICT_GATE: PASS`。

## Pipeline(脚本顺序)
**第 0 步(拆段前必做,无脚本):通读全稿一遍。** atomize 一拆段,你就只能逐段看局部,靠临场记忆润色,极易术语前后不一、指代判错。所以拆段前先把整稿从头读一遍,建立三样全局依据,写进 `decisions_log.md`(用 LOG_CMD)供逐段润色时对照:
- **术语一致表**:同一概念/缩写/基因蛋白名在全文的既定写法(哪个词、什么大小写、缩写首展在哪),逐段润色时照此表统一,不临场另起同义词。
- **作者语感基线**:摸清作者的句式偏好、语气强弱、正式度,润色是向目标期刊语域靠拢而非抹平成千篇一律的 AI 腔。
- **目标期刊语境**:结合 Intake 的目标期刊与 US/UK 拼写,定全稿统一的拼写/标点/语域基准。

通读只读不改,是逐段润色的全局基准;跳过它,就只能靠局部记忆硬润,必然出术语漂移。

```bash
# 1. 原子化:把稿子按段落拆成 units/<idx>.json
python scripts/atomize_manuscript.py --manuscript <input.md|docx> --project-root <root>

# 1.5 反向抽取图/参考/缩略语交叉索引(图文一致性、引用完整性与缩略语首展的审查辅助;产 abbreviation_index.json)
python scripts/manuscript_index.py --manuscript <input> --project-root <root> --units-dir units

# 1.6 抠图落盘(支持 docx 与 pdf,把内嵌图片解到 figures/,供最终 docx 嵌回;pdf 需 PyMuPDF,缺失则优雅跳过;其他非 docx/pdf 输入会自动 no-op)
python scripts/extract_docx_images.py --manuscript <input> --project-root <root>

# 2. 生成逐段润色任务包(含 section_type 的被动目标区间 + 句长上限 + 红线)
python scripts/polish_units.py pack --project-root <root> --intensity standard

# 3. 主 agent 逐段润色:读 polish_manifest.json 的每个 task,按下方 Polish Prompt 改写。
#    📖 动手前必须 Read references/interaction-protocol.md + references/anti-ai-protocol.md,
#       不许凭记忆跑。自查:我这轮真的读过这两个文件吗?没有就先读。

# 4. 校验红线(逐段写回 polish_risk_flags)
python scripts/polish_units.py verify --project-root <root>

# 5. 委托独立subagent盲检 DoD(见上方 DoD 自检清单)
#    📖 动手前必须 Read references/dod-protocol.md(含 Windows 通配符注意事项),不许凭记忆跑。
python scripts/delegate_review.py pack --checklist references/dod_checklist.json \
    --gate polish-dod --files <polished/*.json polished_manuscript.md> --workdir <root>
# subagent返回后:
python scripts/delegate_review.py verify --checklist references/dod_checklist.json \
    --gate polish-dod --workdir <root>

# 5b. 语法拼写与字符级自检(PL-G13,只报告不改稿;命中高置信类别 misspelling/chinese_punct/subsup_bare -> exit 1)
python scripts/proofread_polished.py --project-root <root>

# 6. 交付前 fail-closed 闸门(任一红线破 -> exit 1;
#    另⑥:还会读 .review_return_polish-dod.json,要求独立 PL-G11 语义等价盲检 verdict==pass+证据,
#    否则即便每段自填 meaning_changed=false 也判 FAIL,故本步须在第 5 步盲检 verify 之后跑)
python scripts/strict_gate.py --project-root <root>

# 7. 合并 + 报告
#    📖 动手前必须 Read references/output-contract.md(选哪条 docx 导出路径),不许凭记忆跑。
python scripts/merge_manuscript.py --project-root <root> [--docx out.docx] [--in-place-src <原始docx>]
python scripts/polish_report.py --project-root <root>
```

## Polish Prompt(主 agent 逐段改写时遵守)
对 `polish_manifest.json` 里的每个 task,产出 `polished_text`:
1. **去AI**,清除 AI 套话与五项装饰(见 Anti-AI 规则),改写后自检不得残留。
2. **句长**,英文单句≤30词、中文单句≤50字,长短句交替,避免连续长句。
3. **被动语态**,向该段 `passive_target` 区间靠拢。methods/results 可较高,intro/discussion 偏低。区间是软目标,不硬卡。
4. **术语一致**,同一概念全文用同一词,不要为求变化做同义替换。
5. **不确定性动词不升级**,hedge 不可改成 strong(may/suggest 不可变成 prove/demonstrate)。只可平移或下调。
6. **红线**,task 里 `red_lines.preserve_citations` 列出的引用标记、所有数值、专名一字不动。
7. **保留行内格式标记**,见"字符级排版契约"。`*斜体*`(物种/基因/统计符号)、`<sup>`/`<sub>`、`**加粗**`逐字保留位置与配对,不增删、不错配,标记内字符按红线处理。
8. 改完写回该 unit,`polished_by` 填非 PLACEHOLDER 值,`meaning_changed` 必须为 false,`polish_note` 简述改了什么或为何不改。

## 交互式逐段润色协议(默认开启)
📖 **散文段一段一停,未经用户确认绝不写回 `polished/<idx>.json`**;五步协议/对照格式/跨段编辑两条硬约束/非散文段/节奏开关 → 第 3 步动手前先 Read [references/interaction-protocol.md](references/interaction-protocol.md)。
