# 去 AI 化写作协议 (Anti-AI Protocol)

> 被 SKILL.md 的 Role 区与 **Phase 8 (`/write`)、Phase 10 (`/check`)** 引用。
> **每次撰写或润色英文正文段落前必须 `Read` 本文件**；`/check` 跑 `style_checker.py` 作为客观兜底。
> 本协议自包含；`humanizer-zh` skill 若已装可作辅助参考但非强制依赖。

## 目标读者画像

以美国 STEM 博士研究生（PhD candidate）日常阅读、自然书写的水平为基准，朴素、平实、信息密度优先；笔触受 Nature 资深编辑把关（Role 设定不变），但**克制使用编辑级精炼修辞**，避免炫技。

## 禁词表 (The "Stop" List)

完整清单以 `scripts/style_checker.py` 的 `FORBIDDEN_EXACT` 为准（约 30 词，写作前可 `grep FORBIDDEN_EXACT scripts/style_checker.py` 查全），下方为高频代表：
- 严禁词："delve into", "comprehensive landscape", "pivotal role", "realm", "tapestry", "underscore", "testament", "elucidate", "unveil", "pronounced", "substantial"。
- 首句套话："It is well known", "It is worth noting", "Interestingly", "Remarkably", "In recent years"。
- 严禁结构：三段式排比 ("seamless, intuitive, and powerful")、虚假范围 ("from X to Y")、否定式排比 ("not only... but also...")。

## 🔴 禁修辞 (No Rhetorical Devices)

严禁文学性修辞，即隐喻、拟人、明喻、夸张、对偶、设问、引经据典等。例外：领域内已固化的术语隐喻（如 "molecular switch"、"signaling cascade"）保留；新造的、装饰性的修辞一律删。

## 🔴 禁 -ing 分词悬垂从句 (No Trailing Participial Clauses)

严禁在句尾加逗号 + 现在分词（-ing）做补充说明，即"主句, reflecting/ensuring/highlighting/demonstrating/symbolizing/underscoring/suggesting/indicating/revealing …"句型。这是 AI 写作最高频痕迹之一：用悬垂分词从句追加"意义评论"，显得刻意。

**违规示例 → 修正**：
- ✗ "Treatment reduced tumor volume by 60%, demonstrating the therapeutic efficacy of the nanoparticle system."
- ✓ "Treatment reduced tumor volume by 60%. These data demonstrate the therapeutic efficacy of the nanoparticle system."
- ✗ "Expression levels were elevated in all three cohorts, suggesting dysregulation of the pathway."
- ✓ "Expression levels were elevated in all three cohorts, consistent with pathway dysregulation."

**合法保留**：句首或句中位置的 -ing 从句（"Using flow cytometry, we..."）不属于本条限制。

`style_checker.py` 的 `TRAILING_ING_RE` 检测本条，见 `/check`。

## 🔴 系动词回避 (Avoid "Serves as / Features / Offers" Substitutions)

严禁用 "serves as / features / offers / boasts / presents" 替代简单系动词 "is / has"。AI 写作惯用这类"高级感"替换，实为冗余。

**违规示例 → 修正**：
- ✗ "The scaffold serves as a drug reservoir." → ✓ "The scaffold is a drug reservoir."
- ✗ "The model features three key parameters." → ✓ "The model has three key parameters."
- ✗ "The approach offers unprecedented precision." → ✓ "The approach achieves high precision." （同时去掉 "unprecedented"）

## 🔴 同段保持一致称谓 (Consistent Terminology Within Paragraph)

同一科学概念在同一段落内只用一种称谓，不刻意换同义词（如 "nanoparticles → nanocarriers → nanoformulation"）。AI 为"避免重复"而频繁换词，反而造成概念漂移，影响精确性。
- 例外：两个词已在领域中通用互换（如 "exosomes / extracellular vesicles"）且已在首次使用时标注关系，则允许。
- 段间过渡、标题与正文中的术语变换同样须保持一致，除非刻意区分两个不同的概念。

## 🔴 禁生僻词 (No Obscure Vocabulary)

- 通用动词/形容词用平实词：用 `show / find / use / large / small`，不用 `elucidate / unveil / pronounced / substantial`；用 `cause / lead to`，不用 `precipitate / engender`。
- 例外保留：领域专业术语（如 `apoptosis / pharmacokinetics`）不算生僻，必须用准确术语。
- 判定原则：能用一个 GRE 范围内的常见词替代且不丢精度的，就替换。

## 🔴 禁造词 (No Neologisms)

严禁拼接新词或自造缩略。所有词、所有缩写必须能在权威词典 / 领域教科书 / 已发表文献中找到原型。首次出现的缩写必须给全称（如 "extracellular vesicles (EVs)"）。AI 凭语感造的新组合词（"transformomics"、"diseasability" 之类）一律删。

## 🟡 慎用长难句 (Prefer Short Sentences — 软提示，不阻断)

- **软上限：建议单句 ≤ 30 词**（含从句）。超过时优先拆句，但不硬卡、不一票否决——句长只进 `style_checker.py` 的 warnings，不计入 score。
- **从句深度建议 ≤ 2 层**，避免"主句套定语从句套状语从句"三层嵌套。
- 一句话尽量只承担一个核心论点，复合论点优先拆成两句。

## 🟡 语态按目标刊切换 (Voice by Target Journal — 软提示，不阻断)

语态是 house-style 偏好，不是去 AI 硬线。`style_checker.py` 只把语态偏差写进 warnings，不计入 score、不卡门禁。

- **Nature / Science / Cell 系**：官方 author guideline 明确推荐**主动语态**（"We show that…"、"We find…"）。不设被动下限；仅当被动 > 70%（呆板）才软提示。用 `style_checker.py --journal Nature` 触发此策略。
- **传统 SCI 刊**：实验描述仍以被动为主流，参考被动 50–70%。Methods / Results → 优先被动（"Cells were treated with..."）；Discussion 表达推断可主动。< 40% 或 > 70% 仅软提示，不扣分。
- 拿不准目标刊语言风格（被动比例/句式）→ 不在写作阶段前置学习；留到**末尾用 polish-sci 润色时**按目标刊调性对齐（`/journal-study` 已停用，见 SKILL.md Phase 8.6）。写作期照本协议通用规则即可。

## 🔴 禁装饰性破折号 (Ban Decorative Em-dashes，硬门禁，禁止使用)

**禁止**用 em-dash（—、——）做停顿、补充说明或强调，一律改用逗号、句号或拆句处理。破折号是硬门禁：`style_checker.py` 命中即置 hard_fail 一票否决（无论总分高低），不放行。

**合法保留的连字符/横线用途（不属于本条禁止范围）**：
- 连字符（hyphen `-`）：复合词 / 术语（如 dose-response, T-cell, non-significant）。
- 数字范围号（–，en-dash）：数值范围（如 5–10 mg, 2020–2023）。

**违规示例 → 修正**：
- ✗ "The model predicted high efficacy — a finding that requires further validation."
- ✓ "The model predicted high efficacy, though further validation is required."
- ✗ "Three factors were identified — dose, timing, and formulation."
- ✓ "Three factors were identified: dose, timing, and formulation." （列举引导用冒号合法）

## 🔴 禁 Scare Quotes（挂引号暗示新概念）

严禁用双引号包裹自造词、普通短语或非直接引用内容，以暗示"这是一个新概念/反讽"。这是 AI 写作的典型痕迹。

**合法保留**：
- 首次引入领域内已固化的术语隐喻（如首次的 "molecular switch"，之后不再加引号）。
- 直接引用原文（quote）。
- 已固化行业术语（如 "off-label" use，文献中已普遍使用）。

**违规示例 → 修正**：
- ✗ "The results suggest a 'synergistic' interaction between the two pathways."
- ✓ "The results suggest synergy between the two pathways."
- ✗ "This creates a 'perfect storm' for resistance development."
- ✓ "This creates conditions that favor resistance development."

## 🔴 禁解释性冒号（No Explanatory Colons in Prose）

严禁在正文句子中用"概念: 解释"格式插入装饰性冒号，用以暗示"深刻定义"或"特别说明"。这类冒号通常可直接删掉或改为从句。

**合法保留的冒号用途**：
- 比例（1:10）、时间（08:30）、图表标签（Figure 1: ）。
- 真正的列举引导（见后跟三项以上的并列列表）。
- 节标题 / 方法子标题（Methods: Cell culture）。

**违规示例 → 修正**：
- ✗ "The key limitation: sample size was insufficient for subgroup analysis."
- ✓ "The key limitation was that sample size was insufficient for subgroup analysis."
- ✗ "Our approach: integrating pharmacokinetic modeling with in vivo data."
- ✓ "We integrated pharmacokinetic modeling with in vivo data."

## 写作范式

- **数据驱动 (Data-First)**：用数据说话，拒绝 "significant effect" 这种空话，必须写 "5-fold increase (P<0.001)"。
- **No Bullet Points**：正文严禁列点，必须写成连贯段落。

## 句长节奏

- 同段落内混合**短句（≤12 词）**与**中句（15-25 词）**，不要求 25-40 词的长句（与"禁长难句"统一）。
- 严禁连续 3 句以上句长相近（差异 < 5 词），避免 AI 式齐整。
- 同一概念在同段落不重复同表述，用同义替换或结构重组。
- 改写后段落长度控制在原文 ±15% 以内。
- 连续段落首句禁用相同句式（如连续 "This study..."、"The results..."、"We found..."）。

## 深度改写策略 (Anti-Similarity Protocol)

- **词汇层 (Lexical)**：术语不动；术语周围的非术语通用词降到 PhD 平实层（如 `significant → clear/large`，不再升级为 `pronounced/marked/substantial`，那是编辑级修饰，违反目标读者画像）。禁止直接使用原始文献完整短语（≥4 连续词），必须拆解重构。
- **句法层 (Syntactic)**：语态按目标刊（顶刊主动为主 / 传统刊被动为主，见上「语态按目标刊切换」）；将因果从句拆为独立句而非套层从句。禁止模板化过渡（"Furthermore"、"In addition"、"Moreover"），改用逻辑内嵌或自然连接（"Because..."、"This in turn..."）。
- **结构层 (Structural)**：允许调整段内论点顺序（不破逻辑链）；可适度插入作者推断句（"This likely reflects..."、"One plausible explanation is..."）模拟真人推理痕迹。

## 自我审查

输出任何段落前，必须运行自检（句长 / 句长方差 / 段首重复 / 被动占比 / 是否含修辞、生僻词、造词、em-dash、scare quotes、解释性冒号）；`/check` 阶段跑 `style_checker.py` 量化打分作为客观兜底。

## 学科语感适配（可选）

如当前研究方向的 `configs/*.json` 含 `writing_style` 字段（目前 `drug_delivery` / `computer_science` 有），写作时优先读取并遵循其语态偏好、推荐/避免动词、过渡短语和句长范围；**未配置该字段时使用本协议通用规则即可，不报错**，本协议已自给自足。
