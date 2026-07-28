# 综述投稿包清单 (submission_checklist) — 综述版

> 被 SKILL.md **Phase 5（投稿包）** 引用。执行该阶段时 `Read` 本文件。
> 对齐 general-sci-writing 的 `references/submission-guide.md` 与 `references/compliance-gate.md`
> 的逐项标准（**只读 gsw，不改 gsw**）。综述（review）与原始研究的差异已在此文件内吸收：
> 综述通常无原始数据/伦理批号/试验注册号/报告规范（PRISMA 除外），故相关项默认 N/A 或仅 systematic 适用。

---

## 1. 强制 / 询问分级（对齐 gsw，不静默留白）

| 件 | 级别 | 说明 |
|----|------|------|
| Cover Letter | **强制** | 目标期刊编辑、开场卖点句、3 条框架级贡献、**按目标刊 Aims & Scope 原文写的契合段（非通用套话）**、通讯作者信息。写法见 `references/cover-letter-guide.md` |
| Title Page | **强制** | 题名 / 作者列表 / 单位 / 通讯作者(含邮箱) / ORCID |
| Author Contributions (CRediT) | **强制** | 综述常用 role：Conceptualization / Writing–original draft / Writing–review & editing / Visualization / Supervision / Funding acquisition |
| COI | **强制** | 无则写 "The authors declare no competing interests." 不留空 |
| Funding | **强制** | 无则写 "This work received no specific external funding." 不留空 |
| Data Availability (DAS) | **强制** | 综述通常无原始数据 → "Data sharing not applicable — no new datasets were generated or analysed."；systematic 有提取数据则给出获取方式 |
| Keywords (3–6) | **强制** | 3–6 个；不照抄标题词；覆盖主题/方法/应用维度 |
| ORCID | **询问** | 向用户索取各作者 ORCID；未提供 → 标 "ORCID: not provided" |
| Acknowledgements 致谢对象 | **询问** | 非作者贡献者 / 资助以外的技术支持 / 讨论反馈；无则各类写 N/A，不留空 |
| Highlights | **按目标刊** | Cell 系等要求时给（3–5 条 ≤85 字符，写完 `wc -L` 确认）；否则跳过 |
| Suggested / Opposed Reviewers | **按目标刊 + 询问** | 要求时向用户索取；逐一核 COI 回避（见第 4 节）；严禁伪造邮箱 |

> 强制件缺任一 = DoD `submission-pack-dod` fail-closed。询问级未拿到信息时，**显式标注 N/A 或 "not provided"**，绝不静默留空，也绝不编造。

---

## 2. 各件要点（综述适配）

- **Cover Letter**（详细写法见 `references/cover-letter-guide.md`）：综述的卖点是 *synthesis / framing / gap→展望*，而非新数据。一句话卖点应突出"本综述提出的新框架/视角"。引用 Phase 1.5 的 gap 与 Phase 1.6 的 framing 作为"为什么现在需要这篇综述"的论据。**scope 契合段强制**：基于目标刊 Aims & Scope 原文（向用户索取）写具体契合，禁 "broad readership" 类通用套话，换成别的刊仍成立即须重写。
- **Title Page**：题名禁缩写（DNA/RNA/PCR 等公知除外）；共同一作 `†`，通讯 `*`，共同通讯双 `*`。
- **CRediT**：综述无 Investigation/Formal analysis（无实验）时，对应作者写覆盖到的 role 即可，未覆盖的 11 类标 N/A 并说明（综述常缺 Resources / Methodology-wet-lab）。通讯作者通常 ≥3 个 role（含 Supervision/Funding）。分配细则见 gsw `submission-guide.md` 第 5 节。
- **Keywords**：从 outline.md 的 RQ/PICO 与各节主题提炼；MeSH 术语优先（医学刊）。
- **Highlights（按需）**：每条聚焦综述的一个核心论点或框架贡献，非罗列章节。

---

## 3. 合规门禁（综述相关项，对齐 gsw compliance-gate）

综述多数合规项 N/A，仅保留与综述相关的：

| 项 | 综述适用性 |
|----|-----------|
| 伦理批号 / 试验注册号 | **N/A**（综述不涉及）→ 标 "Not applicable (review article)" |
| 报告规范 | 仅 **systematic / scoping** 适用 PRISMA 2020（流程图 + checklist）；narrative/critical/why-how-what → N/A |
| 统计报告完整性 | 仅 **systematic 含 meta 分析** 时适用（效应量 + 95% CI + I² + 异质性）；否则 N/A |
| 署名合规（ICMJE 四准则） | **适用**：每位作者须满足实质贡献 + 修订 + 批准 + 问责；仅 1–2 条者列入 Acknowledgements |
| Reviewer COI 回避 | 提供 suggested reviewers 时**适用**（见第 4 节） |

---

## 4. Reviewer 推荐 COI 回避（提供时逐一核）

每位 suggested reviewer 须同时满足：近 3 年无共同发表、近 3 年无同一基金、非同单位（同机构不同系也回避）、非直接导师/学生/博士后关系。不符须替换。**阻断**：存在明显 COI 而未回避。严禁伪造邮箱。

---

## 5. 红线

① 严禁 `{{VAR}}` / TODO 残留 ② 严禁伪造 reviewer 邮箱或编造单位 ③ COI 已有须主动声明，严禁瞒报 ④ Funding 无则写 "received no specific external funding"，**不留空** ⑤ DAS / COI / Funding 三段一律非空（无则按上文标准句声明无）⑥ Keywords 3–6 且不与标题雷同 ⑦ 通讯作者在 Title Page 与 Cover Letter 必须一致。

---

## 6. 产出物路径（Phase 5 生成）

```
exports/cover_letter.md
exports/title_page.md
exports/author_contributions.md   # CRediT
exports/coi_statement.md
exports/keywords.md
exports/highlights.md              # 按目标刊，按需
exports/acknowledgements.md
exports/data_availability.md
exports/suggested_reviewers.md     # 按需
exports/submission_pack.md         # 汇总索引（可选）
```

> DoD gate `submission-pack-dod` 的脚本核验路径以本节为准。强制件（cover_letter / title_page /
> author_contributions / coi_statement / keywords）必须存在；其余按分级生成或标 N/A。
