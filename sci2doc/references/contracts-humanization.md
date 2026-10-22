> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

## Humanization Contract

写作前先 Read `references/anti_ai_prose_rules.md`，执行其中全部条目。

Before finalizing each chapter:

1. Run technical self-check（命令见 `QUICK_START.md` § 7）。
2. Invoke the `/humanizer-zh` skill on the chapter's merged markdown. The skill rewrites the text in-place; confirm the output before saving. If `/humanizer-zh` is unavailable, manually apply the following checklist to every paragraph:

   **中文正文规则（博论核心，脚本可检测项见括号）：**
   > C 降软：句长/句式节奏为**软提示**（`cn_sentence_too_long` 为 warning、`cn_sentence_monotone` 为 info，均不阻断 finalize）。这是脚本阈值，不放宽写作要求，句式节奏按 `references/anti_ai_prose_rules.md` 第一节第 2 条执行；**破折号（——）/scare quotes/解释性冒号三项标点与 AI 禁词仍为硬禁清零**（主干保留）。
   - [ ] **中文单句 ≤50 字**（软提示，尽量拆分；`check_quality.py` 检测 `cn_sentence_too_long`，warning）
   - [ ] **从句嵌套 ≤2 层**：禁止"当A使B导致C从而D"类四层套叠结构（软提示）
   - [ ] **短句（≤15字）与长句（30-50字）交替**：连续 3 句字数差异 <5 字必须改写，按 `references/anti_ai_prose_rules.md` 第一节第 2 条执行（`check_quality.py` 检测 `cn_sentence_monotone`，info 级，这是脚本阈值，不放宽写作要求）
   - [ ] **中文 AI 禁词清零**：`check_quality.py` 的 `去AI-禁词` 类别零违规（覆盖：至关重要/深入探讨/蓬勃发展/革命性的/综上所述/值得注意的是/不仅…而且/大量研究表明 等）
   - [ ] **无模板化过渡句**：删除"由此可见"、"在此基础上"等空洞衔接词
   - [ ] **无空洞宏观主张**：每段必须有具体数据或实验结果支撑，不允许纯观点段落
   - [ ] **证据先于结论**：数据/观测在前，解释/结论在后；不允许倒置
   - [ ] **无破折号（——）**：改用逗号、句号或拆句（注意：连字符 `-` 不在此限）
   - [ ] **句法与节奏**：按 `references/anti_ai_prose_rules.md` 第一节第 2 条与第 6 条执行，删除"如同"、"犹如"、"是…的桥梁"等表达。
   - [ ] **无 scare quotes（恐惧引号）**：禁用双引号/引号包裹自造词或普通短语以暗示"新概念"或"特别含义"（保留合法场景：术语首次定义、原文引用、已固化术语）。检测规则：引号内为 2-10 字且非术语首次展开模式
   - [ ] **无解释性冒号（装饰句式）**：禁用"概念：解释"装饰结构（如"本研究的核心：探索..."）。合法冒号场景：比例（1:2）、列表引导（以下三点：）、标题/图表标签（表2-1：...）、数值（10:00）

   **英文摘要规则（Abstract 专用）：**
   - [ ] **英文单句 ≤30 词**：每句不超过 30 个英文单词
   - [ ] **禁 -ing 悬垂从句**：禁用 `, reflecting/ensuring/highlighting/demonstrating/suggesting...` 悬垂分词（改为独立句）

3. Re-run self-check to confirm no regressions（硬禁项 `writing_style`（三项标点）+ `去AI-禁词` 类必须归零；`句长规范` 类为软提示，尽量优化但不阻断）
4. Finalize snapshot + gate completion

