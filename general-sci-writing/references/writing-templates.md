# 章节写作模板库 (writing-templates)

> 被 SKILL.md 各写作阶段引用。写对应章节前 `Read` 本文件相关小节。
> 含：Introduction 漏斗 / Methods 规范 / Discussion 段落 / Online Methods vs STAR / Figure Prompt 生成。

## Introduction 漏斗结构（Mandatory）

Introduction 必须遵循"宽→窄→缺口→我们"的经典漏斗结构，每层对应一个独立段落：
1. **Broad Context**（1-2段）：研究领域的宏观背景与临床/社会意义，引用 Reviews/统计报告
2. **Narrow Focus**（1-2段）：聚焦到具体技术/策略，介绍现有代表性工作，引用 Original Articles
3. **Gap Statement**（1段）：明确指出现有方案的关键局限，用"However / Despite / remains unclear"等过渡，引用近期文献证明局限确实存在
4. **Our Approach**（1段）：提出本研究的策略/假设，说明为何能解决上述 Gap
5. **Overview**（1-2句）：概括全文结构 "Herein, we..."，不展开细节

## Methods 写作规范（Mandatory）

Methods 有独立于 Results/Discussion 的写作要求：
- **可重复性优先**：所有试剂必须标注厂商和货号（如 "DPPC (Avanti Polar Lipids, #850355)"）。**抗体必须带 RRID**（Research Resource Identifier，如 `RRID:AB_2298772`，去 antibodyregistry.org 查）——2024 后多数高水平期刊用自动工具校验、缺即 desk reject。
- **细胞系（Mandatory if used）**：① 来源（ATCC #HTB-26 等）② **STR 鉴定**（cell line authentication）+ **支原体检测**（mycoplasma testing）日期；二者缺一审稿必被挑。
- **动物（Mandatory if used）**：株系（含 background，如 C57BL/6J）、性别、年龄区间、采购来源（如 Jackson Labs / 自繁）、housing 条件（光周期、温度、饲料）、**IACUC 批号**。
- **测序/组学数据（Mandatory if used）**：必须有 **GEO/SRA/PRIDE accession number**（如 `GSE123456`、`PRJNA987654`、`PXD012345`），无 accession 不能投稿。
- **临床样本（Mandatory if used）**：**IRB 批号** + 知情同意（informed consent）声明 + 样本采集年份范围。
- **软件**：版本号 + 关键参数 + 随机种子（如 `Seurat v4.3.0, resolution=0.5, random.seed=42; Cytoscape 3.10.0`）。
- **实验参数精确值**：温度、时间、浓度、转速等必须给出精确数值，禁止"适量"/"室温"等模糊表述。
- **统计方法**：在 Methods 末段单独声明统计软件版本、检验方法和显著性阈值。**与 figure 识图联动**：写统计方法前，先汇总 `figures_database.json` 各 panel 的 `stat_test` 字段（识图阶段已录入，如 "one-way ANOVA + Tukey"），确保 Methods 声明覆盖各 figure 实际所用检验，不重不漏。
- **引用**：仅引用方法学原始论文（如 DLS 测定方法原始文献），不限年份。

## Discussion 段落结构（Mandatory，分离式 Discussion 章节专用；融合式则按 Results 各小节内嵌讨论）

1. **Para 1 — 主要发现总结**（≤150 词）：用 2-3 句概括本工作的关键发现。**严禁简单复述 Results 数字** —— 提取的是"我们发现了什么生物学现象"而非"数值是多少"。错误示例："Our results showed a 5-fold increase in apoptosis."；正确："Our work establishes Sb9 as a key suppressor of collagen deposition in lung fibrosis."
2. **Para 2-3（可多段）— 与文献对比 + 机制讨论**：每个核心 finding 一段。结构：① 先重述发现 ② 与已有文献对比（一致/不一致）③ 机制层面的解读（why does this happen）。**必须真引文献**（走 citation_guard，禁脑补）。
3. **倒数第二段 — Limitations（强制）**：⚠️ **缺 limitations 是退稿高频原因**。必须有 3-5 个明确的局限性陈述，包含：① 样本量 / 模型局限 ② 技术局限（如 only in vitro / single cell line）③ 未解决的机制问题 ④ 临床转化障碍。**不要写虚假谦虚的 limitations**（"future studies are needed" 是废话），写具体可验证的。
4. **末段 — Outlook / Significance**（≤100 词）：本研究对领域的推进 + 直接的下一步问题。**不要写"我们这工作有重要意义"，要写"this opens X new line of inquiry"**。

## Online Methods vs Main Methods（Nature 系列必须区分，Cell 系列用 STAR Methods）

- **Nature / Nature 子刊**：正文最末"Methods"是**精简版**（≤2000 词），含核心方法概览；完整 Methods 放 **Online Methods** / **Supplementary Information**（不限词数）。
- **Cell / Cell 子刊**：用 **STAR Methods**（Structured, Transparent, Accessible Reporting），强制分章节：① Key Resources Table（试剂表，含 RRID）② Experimental Model and Subject Details ③ Method Details ④ Quantification and Statistical Analysis ⑤ Data and Code Availability。
- **其他期刊**：Methods 一般放在 Results 后或文末，完整即可。
- **写作策略**：识图阶段 `add-figure` 录入的 `stat_test` / 试剂参数全部进 Methods；按目标期刊在 `/write methods` 时**自动选模板**（在 `/init` 时根据 `target_journal` 提示用户）。

## Figure Prompt 生成规范（为需 AI 绘制的示意图/机制图生成结构化提示词）

> **双轨澄清**：`figures_database.json`（via `/figure` + `add-figure`）存的是**用户已有实验图的识图数据**（WB/HE/统计图等，用于写正文）；本节的 `figures/figure_index.md` + `figure_prompts.md` 是**让 AI 帮画的图**（示意图/机制图的绘图提示词）。二者用途不同、不冲突；若同一 figure 既有实验数据又需重绘，以 `figures_database` 为数据源。

When a figure is registered in `figures/figure_index.md`, generate a Figure Prompt block and append to `figures/figure_prompts.md`:

```
[FIGURE PROMPT — Figure N: <title>]
TYPE: Data plot | Schematic | Mechanistic pathway | Workflow | Statistical | Structural
SUBJECT: <specific scientific content, one sentence>
STYLE: BioRender风格, 科研绘图, 最高分辨率, white background (#FFFFFF), publication-quality for <target journal> [默认BioRender风格；如需其他风格（如Cell-style flat icon / Nature手绘风 / 简约线条风），在启动时告知]
COLOR SCHEME: (inherit from project palette in configs/; default: Primary #2E86AB | Secondary #A23B72 | Accent #F18F01 | Neutral #4A4A4A | colorblind-safe, no pure red-green contrast)
ELEMENTS:
  - <Element 1>: <shape, position, label, connections>
  - <Element 2>: <arrows, symbols — specify solid/dashed, direction, type: stimulatory/inhibitory>
  - <Element N>: ...
LAYOUT: <Single panel | Multi-panel (A, B, C...)> | <aspect ratio> | <panel arrangement: 2×1 row / 1×3 column / etc.>
TYPOGRAPHY: Arial/Helvetica, 8-10pt labels, English only, axis labels bold, panel letters (A, B...) 12pt bold top-left corner
DATA REPRESENTATION (if data plot): <chart type: bar/line/scatter/heatmap> | <X-axis: label + unit> | <Y-axis: label + unit> | <statistical markers: * p<0.05, ** p<0.01, *** p<0.001>
SCALE/LEGEND: <scale bar location and value | color bar range | legend position | N/A>
KEY MESSAGE: <one sentence — what conclusion this figure supports>
AVOID: 3D effects, drop shadows, gradients, clip art, stock textures, decorative borders, excessive inline text
```

Generation rules:
- Generate one prompt per figure at the time the figure is first planned (not after writing)
- Color palette must be locked in Phase 0 init and reused across all figures (write to `configs/figure_palette.json`)
- For multi-panel figures: describe each panel (A, B, C...) with its own ELEMENTS block
- For data plots: specify chart type; do NOT describe actual data values — matplotlib generates the actual plot
- For mechanistic/schematic figures: use standard scientific icons (receptor = Y-shape, nucleus = double-border oval, mitochondria = bean shape with cristae, etc.)
- If figure revision is needed in a later phase, update the corresponding prompt block in `figures/figure_prompts.md`
