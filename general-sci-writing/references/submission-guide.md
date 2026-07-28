# 投稿包详细指南 (submission-guide)

> 被 SKILL.md 的 **Phase 8 (`/submission-pack`)** 引用。执行该阶段时 `Read` 本文件。

## 1. 逐项询问明细（必须主动问，不要静默用空白）

- **Cover letter**（**详细写法必读 `references/cover-letter-guide.md`**）：目标期刊编辑姓名 / 开场创新点强调句 / 3 条 Key Innovation + 3 条 Major Contribution（区分：Innovation=做了什么新东西，Contribution=对领域什么用）/ **目标刊 Aims & Scope 原文（向用户索取，据此写强制的 scope 契合段，禁通用套话）** / 3 位 suggested reviewer 名字与邮箱 / 是否有 opposed reviewer / 通讯作者信息+ORCID
- **Data Availability**：原始数据是否 deposit？哪个 repository？accession number？源数据 Supp Data 编号？
- **Code Availability**：是否有自定义代码？GitHub URL？license？Zenodo DOI？
- **CRediT**：每位作者承担哪些 role（11 类），用作者首字母缩写（分配指南见第 5 节）
- **COI**：所有作者有无 competing interests（专利、咨询、股权）
- **Funding**：每个 funder + grant number + 受资助 PI
- **Highlights**（Cell 系强制）：3-5 条 ≤85 字符，写完后必须 `wc -L` 确认
- **One-sentence summary / eTOC**：Nature 系 ~150 字符，Cell ~125 字符
- **Keywords**：3-6 个投稿关键词（数量遵从目标刊），与 title/abstract 主题一致，生命科学优先 MeSH（详见第 8 节）
- **Graphical abstract**：按 `submission_package.json.graphical_abstract_spec` 出，用户自己画或交付 BioRender，本流程不画

## 2. 目标期刊适配（按需读取）

从 `project_config.json` 读 `target_journal`，挑出该期刊的 `required_by` 项强制：如 Nature 必给 one-sentence summary 与 DAS，Cell 必给 highlights + graphical abstract。

**Cover letter 的 scope 契合（强制）**：投稿包必须让 cover letter 论证本文与目标刊 Aims & Scope 的契合。技能不自动抓期刊页，须主动向用户索取该刊 **Aims & Scope 原文**并据此撰写具体契合段。判定与正反例见 `references/cover-letter-guide.md` 第 3 节。

## 3. 报告规范 checklist（强制）

`Read templates/reporting_checklists.json` → 按 `project_config.json` 的 `research_field` 自动挂对应 checklist（如 `drug_delivery`→ARRIVE，`clinical_pharmacy_llm`→CONSORT/STROBE/TRIPOD，CS→ML reproducibility）。再叠加 `target_journal` 特定要求（Nature Reporting Summary、Cell STAR Methods 等）。逐项核查 Methods 与 Results 是否齐全，缺项必须补到 Methods 后才能 `/merge`。**动物实验 ARRIVE 不全 = 多数期刊编辑桌面拒**。

## 4. Source Data .xlsx 准备（Nature/Cell 强制，其他多数期刊 strongly preferred）

- **格式**：一个 `submission/source_data.xlsx`，**每张主图一个 sheet**（Sheet 命名 `Figure 1A`、`Figure 1B`...）。
- **内容**：每个 sheet 含**该 panel 的全部原始数值**（n 个独立实验、每个数据点的原始值，而非只是 mean ± SD）。
- **行列规范**：第一列为分组/时间点；其后各列为各重复（n=1, n=2, ...）；最末行可放 mean / SEM / P 值汇总。
- **不能藏数据**：审稿人会比对 source data 与图表，**数值对不上 = 学术不端嫌疑**。
- 用户自己准备 .xlsx（脚本生成出错率高），AI 给规范 + 检查 sheet 命名与 figures_database 的 figure_id 是否对应。

## 5. CRediT 角色分配指南（学生常犯困）—— 11 类对应典型角色

- **Conceptualization** → 通常 PI + 提出 idea 的核心学生
- **Methodology** → 设计实验方案的人（学生 + PI）
- **Investigation** → 真正做实验的学生（**博士生主体**）
- **Formal analysis** → 跑统计 / 数据处理的人
- **Resources** → 提供独家试剂 / 样本 / 设备的人
- **Writing – original draft** → 写初稿的人（**博士生主体**）
- **Writing – review & editing** → 改稿的人（PI + 共同作者）
- **Visualization** → 出图的人
- **Supervision** → 直接指导的 PI
- **Project administration** → 协调多 lab 的负责人
- **Funding acquisition** → 拿钱的 PI
- **规则**：① 每个 role 至少一位作者，全员覆盖 11 类（无人对应的写"N/A"并解释）② 一位作者可承担多个 role ③ 通讯作者通常 ≥ 4 个 role（含 Supervision/Funding）。

## 6. Acknowledgments 模板（投稿必备但常忘）—— 必须含以下类别，无则写 N/A

- **非作者贡献者**（提供试剂/样本/技术指导但不达 authorship 标准的人）
- **技术平台**（核心设施、共享仪器、生物信息平台）
- **样本/资源来源**（biobank、动物中心、临床中心）
- **预印本/讨论致谢**（在会议或 bioRxiv 收到的有用反馈）
- **Funding 不放 Acks**（独立 funding 章节）

## 7. 红线

① 严禁 `{{VAR}}` 残留 ② 严禁伪造 reviewer 邮箱 ③ COI 已有需主动声明严禁瞒报 ④ Funding 无则写 "This work received no specific external funding"，**不留空** ⑤ **Source Data 数值必须与图对应** —— 不一致即学术不端嫌疑 ⑥ Acks 不能空，无则各类写 N/A ⑦ **Keywords 必须产出**（`submission/keywords.txt`，3-6 个且数量符合目标刊），缺失或数量不符即阻断投稿包导出。

## 8. Keywords（投稿关键词）—— 强制产出 `submission/keywords.txt`

- **数量规则**：3-6 个，具体遵从目标刊投稿系统要求（多数刊 3-6；部分刊固定 5 个或上限 6）。数量不符即被 Phase 10.5 阻断。
- **选词原则**：
  - 覆盖研究对象 / 方法 / 应用领域三个维度，便于检索命中。
  - 与 title 和 abstract 主题一致；**避免与标题词完全重复**（标题已显著出现的词不再占关键词名额，应补充标题未含但检索价值高的同义/上位/方法学词）。
  - 用领域规范术语，避免生造缩写与过宽泛词（如 "study" / "analysis"）。
- **MeSH 适配（生命科学优先）**：生命科学/医学稿件优先从 MeSH（Medical Subject Headings）受控词表选词，提升 PubMed 检索可发现性；无对应 MeSH 词时用领域公认术语。CS/AI 等无 MeSH 体系的领域用本领域标准关键词（如 ACM CCS、arXiv 分类术语）。
- **格式**：`submission/keywords.txt`，每行一个关键词或单行分号/逗号分隔（按目标刊要求），全小写或首字母大写遵从目标刊范例。
