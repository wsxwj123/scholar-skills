# Figure Prompt Generation（图注之外，同步生成AI绘图提示词）

For each figure referenced in the converted document where the original figure is unavailable or needs redrawing, generate a Figure Prompt block:

```
[FIGURE PROMPT — Figure N: <caption title>]
TYPE: Data plot | Schematic | Mechanistic pathway | Workflow | Statistical | Structural | Microscopy description
SUBJECT: <exact scientific content from the original paper, one sentence>
STYLE: BioRender风格, 科研示意图, 最高分辨率, white background (#FFFFFF), publication-quality [默认BioRender风格；如需其他风格（如Cell-style flat icon / Nature手绘风 / 简约线条风），在启动时告知]
COLOR SCHEME: Primary #2E86AB | Secondary #A23B72 | Accent #F18F01 | Neutral #4A4A4A | colorblind-safe
ELEMENTS:
  - <Element 1>: <derived from figure caption or manuscript description>
  - <Element 2>: <arrows, labels, key components>
LAYOUT: <inferred from caption: single/multi-panel> | <aspect ratio: 4:3 default>
TYPOGRAPHY: Arial/Helvetica, 8-10pt, English labels, panel letters bold top-left
DATA REPRESENTATION (if applicable): <chart type | axes labels from caption>
SCALE/LEGEND: <from original caption if stated | N/A>
KEY MESSAGE: <derived from the Results section paragraph that references this figure>
AVOID: 3D effects, gradients, clip art, decorative elements, photo-realistic rendering
SOURCE NOTE: Reconstructed from: <original paper DOI or figure caption text>
```

Generation rules:
- Only generate a Figure Prompt if the original figure is not available in the source PDF or needs reconstruction
- Derive all element descriptions from the figure caption + surrounding Results text — do NOT fabricate experimental data
- If microscopy/imaging data: describe as "Representative [modality] image showing [structure], [magnification] if stated, scale bar [X]μm if stated" — do NOT attempt to recreate actual experimental images
- Store all generated prompts in `${save_path}/figure_prompts.md`
- Mark each prompt with `[RECONSTRUCTED]` tag to distinguish from original figures


> 以下一节由 SKILL.md 拆分而来（原 `## Figure Prompt Generation` 节，含配图代码生成 opt-in 规则），仅在主文件指示时读取。

## Figure Prompt Generation（图注之外，同步生成AI绘图提示词）

原图在源 PDF 中不可用或需重绘时，按 `references/figure_prompt_template.md` 为每张图生成 Figure Prompt 块，存入 `${save_path}/figure_prompts.md` 并标 `[RECONSTRUCTED]`。所有元素描述须来自图注与 Results 文本，**不得编造实验数据**。

**配图代码生成（opt-in，默认关）**：与上述 Figure Prompt 并列的另一可选项，默认不生成配图（基础实验用户自行作图）。仅当用户**明确要求**"生成配图/画图代码"（如生信、统计图场景）时启用。启用后：① 调用本地 matplotlib/seaborn skill 生成**可运行代码**（产出代码非图片）；② 遵循学术规范：按数据选图型（bar/boxplot/line/scatter+回归/**forest plot**/**funnel plot**（meta 分析用）/heatmap/network/concept map），APA 7.0 caption，色盲安全配色（viridis/cividis/Tol），300 DPI，轴标签带单位，**禁 3D 图与饼图**；③ 生成后由用户运行得图。

