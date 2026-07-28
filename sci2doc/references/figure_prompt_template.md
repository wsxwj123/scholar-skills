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
