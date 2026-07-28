# Figure Prompt Template

When a reviewer requires figure revision or addition, generate a structured Figure Prompt immediately after the image placeholder block.

```
[FIGURE PROMPT — Response to Reviewer #N, Comment K]
REVISION TYPE: New figure | Replace existing Figure X | Add panel to Figure X | Revise color/style only
REVIEWER REQUEST SUMMARY: <one sentence distilling what the reviewer asked for>
TYPE: Data plot | Schematic | Mechanistic pathway | Statistical | Workflow
SUBJECT: <specific scientific content required by reviewer>
STYLE: BioRender风格, 科研绘图, 最高分辨率, white background (#FFFFFF), publication-quality, consistent with manuscript's existing figure style [默认BioRender风格；如需其他风格（如Cell-style flat icon / Nature手绘风），在启动时告知]
COLOR SCHEME: (match manuscript's existing palette; default: Primary #2E86AB | Secondary #A23B72 | Accent #F18F01 | colorblind-safe)
ELEMENTS:
  - <Element 1>: <exact requirement from reviewer comment>
  - <Element 2>: <additional components needed>
LAYOUT: <Single panel | Multi-panel, specifying new panel position relative to existing figure>
TYPOGRAPHY: Match existing manuscript figures (Arial/Helvetica, 8-10pt, English labels)
STATISTICAL REQUIREMENTS: <if new statistical analysis required: chart type, error bars: SEM/SD, significance markers>
KEY MESSAGE: <what this revised figure must now demonstrate to satisfy the reviewer>
AVOID: Changes that contradict existing data; adding elements not supported by the underlying experiment
```

Rules:
- Generate Figure Prompt ONLY when reviewer explicitly requests a figure change (not for text-only responses)
- If reviewer requests a new experiment's figure: mark as `[NEW EXPERIMENT REQUIRED]` and note `Not provided by user` in evidence area
- If revision is cosmetic only (color, font, layout): mark as `[STYLE REVISION ONLY]` and skip ELEMENTS block
- Store all figure prompts in the corresponding comment unit JSON under `content.figure_prompt`
