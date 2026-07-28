# 逐节质量自检 Checklist（本技能内部）

本技能内部的轻量质量 checklist，不是 reviewer-simulator 技能。禁止据此调用或进入 reviewer-simulator 技能，禁止生成任何 HTML 审稿报告。
For each dimension, answer every checklist item (Y/N). Dimension passes when ALL items = Y.

## 执行方式（本文件 = Phase 3 Step 6 主 agent 自查参照）

**独立盲检不在 Step 6 做。** 为避免每节两次评分轴高度重叠的委派，本 D1-D5 的独立盲检已并入 Phase 3 **Step 10** 的单次 `manuscript-dod` 盲检（D1 新颖→R23、D2 仲裁→R8、D3 证据→R7+R9、D4 连贯→R18、D5 去 AI→R5），fail-closed 门禁、`.review_pass` 落盘与修复子代理循环全在 Step 10。

- **Step 6（本文件用途）：** 主 agent 落笔后对照下列 D1-D5 做一遍**轻量自查**（配合 `style_checker.py`），把明显问题就地改掉，为 Step 10 兜底。此步不派 subagent、不落盘、不阻断。
- **决策边界：** Step 10 盲检的评审执行（打分/找问题）可委托 subagent；修订方案与是否 HALT 由主 agent 决定，不可委托。

## D1 — Novelty & Contribution

- [ ] Proposes at least one new framework, hypothesis, taxonomy, or perspective not in prior reviews
- [ ] Clearly states how this section advances beyond existing reviews (explicit "gap → contribution" sentence)
- [ ] Does NOT merely summarize existing work without synthesis

## D2 — Arbitration & Critical Analysis

- [ ] Identifies ≥1 contradiction or debate between cited studies
- [ ] Provides *why* analysis for each contradiction (not just "results conflict")
- [ ] Takes a position or proposes a reconciling explanation (does not sit on the fence)

## D3 — Evidence Density & Traceability

- [ ] Every factual claim has ≥1 citation; key claims have ≥2 independent sources
- [ ] No citation-free paragraphs (except transition/framing sentences)
- [ ] Evidence types match claim types (original article for mechanism, clinical trial for efficacy, review for background context)

## D4 — Flow & Coherence

- [ ] Opening sentence of each paragraph connects to the previous paragraph's conclusion (causal/contrastive link, not bolted-on transition)
- [ ] Section has a clear internal arc: setup → evidence → synthesis → implication
- [ ] No orphan paragraphs (paragraphs that could be moved elsewhere without breaking logic)

## D5 — Anti-AI Compliance

- [ ] Zero banned words/phrases from Anti-AI Writing Style lists
- [ ] Sentence length rhythm: no 3+ consecutive sentences within ±5 words of each other
- [ ] Passive voice ≤30% of sentences per paragraph (EN mode)
- [ ] No templated transitions ("Furthermore", "In addition", "Moreover" as sentence openers)

## Gate Rule（在 Phase 3 Step 10 的 manuscript-dod 盲检上执行，非 Step 6）

Step 6 自查发现的问题就地改掉即可、不阻断。真正的 gate 在 Step 10：任一 `manuscript-dod` 项失败 → 派修复子代理针对性修改（max 2 rounds）。After 2 rounds, if any item still fails → **HALT**, output the specific failed items as structured feedback:

```
【问题】(failed item description)
证据锚点: (paragraph/sentence where the failure occurs)
根源分析: (why it fails — e.g., "Paragraph 3 lists 4 studies without comparing their findings")
修复方向: (specific action — e.g., "Add a synthesis sentence after the 4th citation contrasting dosage findings")
```
