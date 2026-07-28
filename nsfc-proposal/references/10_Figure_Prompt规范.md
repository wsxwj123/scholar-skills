# 10 Figure Prompt 规范

为申请书中需要的图（技术路线图、研究框架图、预期结果示意图等）生成绘图提示词，存入 `sections/figure_prompts.md`。

## 提示词模板

```
[FIGURE PROMPT — <figure role, e.g., Technical Roadmap / Research Framework / Preliminary Data>]
TYPE: Workflow | Conceptual framework | Mechanistic schematic | Data plot | Experimental design
SUBJECT: <specific content, e.g., "Three-phase technical roadmap for investigating X mechanism in Y disease model">
STYLE: BioRender风格, 科研示意图, 最高分辨率, white background (#FFFFFF), suitable for NSFC proposal submission [默认BioRender风格；如需其他风格（如简约线条风 / PowerPoint扁平风 / 手绘概念图），在启动时告知]
COLOR SCHEME: Primary #1A5276 (dark blue, main flow) | Secondary #148F77 (green, key innovations) | Accent #D35400 (orange, expected outputs) | Neutral #566573 | Background #FFFFFF
ELEMENTS:
  - Phase/Stage boxes: <label, sequential left→right or top→bottom>
  - Connecting arrows: solid arrows for sequential flow, dashed for feedback loops
  - Key innovation markers: highlighted box or star symbol at innovation points
  - Input/Output labels: brief text labels at start and end nodes
  - <Additional element if needed>
LAYOUT: <Horizontal flow 3-phase | Vertical hierarchy | Mixed: top-level + branching sub-tasks> | aspect ratio 16:9 preferred for roadmap
TYPOGRAPHY: Chinese labels allowed for NSFC figures, Arial/SimHei 9-10pt, phase headers bold, sub-labels regular
HIERARCHY LEVELS: <e.g., Level 1: 3 main phases | Level 2: 2-3 tasks per phase | Level 3: key outputs>
KEY MESSAGE: <one sentence summarizing what this diagram communicates to reviewers>
AVOID: 3D effects, excessive colors (>4 colors), clip art, stock icons, overly complex branching that obscures the main logic
```

## 生成规则

- 技术路线图（技术路线 / 研究方案）：Phase 2 必须生成（技术路线属于 P2_研究内容的 M 子节）
- 研究框架图（总体框架）：Phase 1 推荐生成（研究逻辑适合可视化时）
- 预期结果示意图：用占位符 `[Preliminary Data Fig N]` 标注
- 所有图使用统一色板（深蓝=主线索，绿色=创新点，橙色=预期产出）
- 每张图必须能在 consistency_map.json 中映射到至少一个 RC（研究内容）
