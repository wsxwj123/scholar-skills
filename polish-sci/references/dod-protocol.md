# DoD 自检清单 PL-G1~PL-G14 逐项判据与委托盲检细则

> 本文件是 polish-sci SKILL.md 的下沉细则，内容与拆分前逐字一致，未作任何改写。
> 何时读：Pipeline 第 5 步委托独立 subagent 盲检之前；向用户逐条摆裁决结论之前。

通用 14 项(id: PL-G1 ~ PL-G14,其中 PL-G11 为科学内容零改动硬项、PL-G12 为软报告、PL-G13 为字符级自检硬项、PL-G14 为拉丁斜体软提醒):
- **PL-G1 数值保留**,每段数值/统计量集合与原文一字不差。
- **PL-G2 无语气升级**,不确定性动词未被升级。
- **PL-G3 引用保留**,引用标记与 DOI 集合前后一致。
- **PL-G4 去AI**,散文单元 find_ai_style_markers 的**硬拦**项(AI 套话禁词表 + 去AI必禁三项 破折号/scare quotes/解释性冒号)无残留;长句/-ing 拖尾/not only...but also/修辞问句为软提示,记报告不阻断(见 Anti-AI 规则的分级);非散文单元豁免。
- **PL-G5 meaning 未变**,每段 meaning_changed=false,专名未动,语义层人工逐段对照。
- **PL-G6 逐段全覆盖**,无 PLACEHOLDER 残留,无遗漏段落。
- **PL-G7 被动语态合区间(软报告)**,各段被动比例落在 section_type 目标区间附近;区间为软目标,只报告不阻断交付。
- **PL-G8 术语一致**,全文术语用词前后一致(人工核)。
- **PL-G9 结构完整性**,合并稿段落顺序与小节结构与原稿一致,引用编号连续。
- **PL-G10 缩略语首展一致(软报告)**,`abbreviation_index.json` 的 undefined_use / duplicate_definition / title_abbreviation 已列出供人工取舍;润色未破坏既有首展、未新增缩略语问题。纯润色不主动改缩略语定义,原稿固有问题只报告不阻断交付(与 revise-sci 的硬门禁 RV-G7 区分)。
- **PL-G11 科学内容零改动(语义等价的唯一权威)**,盲检补脚本红线之外的语义盲区:润色是否仅改语言、未改科学实质(事实/机制陈述、方法描述、因果方向、限定条件与适用范围、结论确切含义均与原文等价)。任一处科学内容被实质改写或含义偏移即 fail,列出原文与润色后对应句为证。**⑥ 这是判定 meaning 未变的唯一权威**:改写方在 polished/<idx>.json 里自填 `meaning_changed=false` 只是自证、不足信;strict_gate 交付前会读独立subagent写回的 `<root>/.review_return_polish-dod.json`,要求 PL-G11 verdict==pass 且证据非空,缺独立裁决/非 pass/空证据一律 fail-closed。即"没有独立盲检 = meaning 未核 = 拦",自填 false 不能替代。
  - ⚠️ **【P4·盲检降级告警】** 若环境派不出真正独立的subagent来做本项语义等价盲检,**绝不能同一 AI 自评自过**(自己润的自己判"意思没改坏"= 没有盲检)。必须告诉用户「本环境语义盲检不可靠,请你逐段亲自核对:改后有没有改变原意/数据/专名」,把这一核验交回用户,不得伪造盲检通过。好在 polish-sci 逐段一停让你每段都看得到改动点,本就有人肉兜底。
- **PL-G12 常识合理性(🟡软报告,不阻断)**,盲检subagent顺带扫一遍是否有明显常识/事实硬伤(单位量级离谱、生理/机制常识错误、前后数值逻辑矛盾等)被原文带入或润色引入。**仅提示不阻断**,纯润色默认原文内容正确,本项只在发现明显硬伤时记入报告供人工判断,绝不自动改内容(与 PL-G1~G11 的核验/硬拦区分,也与 reviewer-simulator 的完整科学性审查区分)。
- **PL-G13 润色后语法拼写与字符级格式自检(硬项)**,`python scripts/proofread_polished.py --project-root <root>` 对润色输出(polished/<idx>.json 的 polished_text)扫 misspelling / chinese_punct / subsup_bare,命中任一则 ok=false、阻断交付并列出问题供用户处理。**只报告不自动改**,脚本纯读 polished/ 并输出 proofread_report.json,绝不写回任何 json/docx/原稿(改与不改由用户决断,守"科学内容零改动"铁律)。
- **PL-G14 拉丁短语斜体软提醒(🟡软/人工确认,不阻断)**,PL-G13 同一次 `proofread_polished.py` 运行产出的 `proofread_report.json` 里 `latin_italic_missing` 类别:润色输出中 `in vitro`/`in vivo`/`ex vivo`/`in situ`/`de novo`/`post hoc`/`per se` 等公认须斜体的拉丁短语若裸写(未被 `*...*` 斜体标记包裹)则报告。**仅提示,不阻断、不进 `--fail-on`、不扣分**,由人工确认是否补斜体(`et al.`/`e.g.`/`vs.` 等正体惯例不在词表内)。


🔴 **委托盲检(强制)**,主 agent 不得自评 DoD。必须:
1. `python scripts/delegate_review.py pack --checklist references/dod_checklist.json --gate polish-dod --files <...> --workdir <root>`,把打印的任务包交给独立subagent(默认继承主 agent 模型/用户指定)。
2. subagent只依据文件实际内容逐项裁决,返回 JSON 写到约定路径。
3. `python scripts/delegate_review.py verify ... --gate polish-dod --workdir <root>`,fail-closed 校验。任一缺项/fail/证据为空 -> exit 1,不得声明完成。
4. **① DoD 停**:盲检(尤其 PL-G11 语义等价)通过后,**不要直接 merge 交付**。先把每一项(PL-G1~PL-G14)的裁决结论逐条摆给用户看(通过/软提示/需人工确认的都列清),然后 **🛑 HALT 等用户确认**,用户点头才进 strict_gate + merge + report。这是交付前最后一道人肉闸,用户此刻仍可喊停或补要求(补要求即 LOG_CMD 记入决定日志)。

## Windows 注意（原 SKILL.md Pipeline 第 5 步 bash 注释，逐字搬运）

# Windows 注意:PowerShell/cmd 不展开 *.json 通配符,需把 polished/ 下的 json 文件显式逐个列在 --files 后,或在 WSL/bash 里运行
