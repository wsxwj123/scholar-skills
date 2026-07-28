# Cover Letter 撰写指南

> 被 SKILL.md **Phase 11（`/submission-pack`）** 引用。生成 `submission/cover_letter.md` 前必须先 `Read` 本文件。
> 模板骨架在 `templates/submission_package.json` 的 `cover_letter` 字段；本文件讲**怎么填才有效**。

## 0. 一句话认知

Cover letter 是稿件送外审前唯一的"面试机会"。编辑每天扫几十篇稿，不会逐字读你的摘要，只扫几句话就决定送审还是桌拒。所以每一句都要有信息量，套话等于没写。

## 1. 首投信结构（四段 + 结尾声明）

### 段 1｜开场 + 一句创新点强调句
- 常规提交句（"We are pleased to submit our manuscript ... for consideration in {{JOURNAL}}"）本身没错，但等于什么都没说。
- **真正起作用的是紧跟其后的一句创新点强调句**，把这篇最尖锐的贡献一句话砸出来。编辑就扫这一句。
- 示例句式（照录）："This study introduces an innovative strategy to ..." / "Here we report the first ... that ..."。

### 段 2｜核心内容总结（红线：禁止照抄摘要）
- 背景一句带过，核心篇幅留给**创新点**和**解决的问题**。
- **大忌：把摘要原样搬进来**。Cover letter 要比摘要更尖锐、更有针对性，突出"这不是增量改进，是突破"。
- 写完自检：这段有没有一句是从 abstract 复制的？有就重写。

### 段 3｜3 条 Key Innovations + 3 条 Major Contributions（编号列表）
- 用编号列表呈现，便于编辑扫读。这是编辑判断"是否送审"的核心区。
- **Innovation 与 Contribution 不能混**（区分见第 2 节）。
- 各 3 条，不堆砌；每条一行，动词开头，可量化就量化。

### 段 X｜期刊 scope 契合段（**强制，本技能重点，见第 3 节**）
- 单列一段，论证"为什么这篇适合投这本刊"。
- 位置可放段 2 之后或段 3 之后，紧扣该刊 Aims & Scope。

### 结尾｜三项标准声明
- 无一稿多投（not under consideration elsewhere）、全体作者同意投稿、无利益冲突（或见附 COI）。
- 格式化内容，照标准句写即可，不必花心思。

## 2. Innovation ≠ Contribution（学生最常混淆）

| | Key Innovation | Major Contribution |
|---|---|---|
| 回答 | 你**做了什么新东西** | 这东西**对领域有什么用** |
| 内容 | 新方法 / 新发现 / 新机制 / 新材料 | 解决什么争议、填补什么空白、提供什么工具、改变什么认识 |
| 反例（写错） | "我们的方法很重要" ← 这是没内容 | "我们提出了一个新算法" ← 这是 Innovation 不是 Contribution |
| 正例 | "首次用单细胞测序在 X 中鉴定出 Y 亚群" | "为 Z 领域长期争论的 A 与 B 之争提供了直接证据" |

编辑扫这 3+3 就判断稿子够不够格。两栏各自成立、不重复，才算写清楚。

## 3. 期刊 scope 契合（本技能强制要求，原文模板缺此项）

投稿像相亲，编辑第一反应是"这稿子是不是投错门了"。scope 不匹配是桌拒的高频原因，且与稿件质量无关。

### 3.1 硬要求
- **必须基于目标刊的 Aims & Scope 原文来写**，不能凭刊名想象。
- 技能**不自动抓取**期刊页面（安全考虑）。执行 Phase 11 时**主动向用户索取目标刊的 Aims & Scope 原文**（用户从期刊官网 About/Scope 页复制）。用户没给就停下来要，不要编。
- 契合段要具体呼应该刊**关注的主题 / 方法取向 / 读者群**，用该刊 scope 里的实际字眼去勾连本文贡献。

### 3.2 禁止（通用套话，直接删）
- ✗ "which we believe will interest the broad readership of {{JOURNAL}}"
- ✗ "this work is highly relevant to the scope of your esteemed journal"
- ✗ 任何把刊名换成别的刊也照样成立的句子 —— 这种句子等于没写。

### 3.3 正例（具体、可迁移的写法）
> The journal's stated emphasis on [scope 原文关键词，如 "mechanistic studies of host-microbe interactions"] aligns directly with our central finding that [本文贡献]. Our work extends this focus by [具体如何呼应/推进该刊长期关注的方向], and speaks to the [该刊读者群，如 "microbiology and immunology"] community the journal serves.

自检一句话：把句子里的刊名换成另一本刊，还成立吗？成立就是套话，重写。

## 4. 长度 / 语气 / 格式

- **长度**：四段核心 + 简短结尾声明，一页以内。不铺陈、不复制摘要。
- **语气**：精炼、直给、句句有信息量，反对空话套话。
- **格式**：Innovations / Contributions 用编号列表；scope 契合单独成段；结尾声明可合并为一小段。
- **去 AI 三禁**（沿用本技能红线）：英文正文禁破折号（—）、禁 scare quotes（给普通词强行加引号）、禁解释性冒号（用冒号硬拽出解释）。

## 5. 红线

① scope 契合段必须存在且非通用套话，用户未提供 scope 原文则停下索取，不编造。
② 段 2 禁照抄 abstract。
③ Innovation 与 Contribution 分栏写清，不混不重复。
④ key findings 必须取自已 `/check` 通过的校对版稿（Phase 11 前置门禁已保证）。
⑤ `{{VAR}}` 占位符零残留。
⑥ 三项结尾声明齐全，COI 已有须主动声明。

## 6. 返修信（resubmission，本技能不产出，仅备查）

改投/返修时的 cover letter 核心是"帮编辑省时间"：开头致谢 → 修改总览表（审稿意见共几条 / 改了多少处 / 新增哪些数据 / 改动哪些章节）→ 逐条详细回复放附件 → 格式严的刊（如 ACS）补一句格式合规声明。本技能只做首投信；返修回复由 revise-sci / reviewer-response-sci 技能负责。
