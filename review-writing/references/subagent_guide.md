# Subagent Delegation Guide

Delegate mechanical tasks to subagent; main agent focuses on synthesis and writing.

**Model:** Read `subagent_model` from `outline.md`. If unspecified, use same model as current session.

## Delegatable Tasks

| Task | Input → Output |
|------|---------------|
| Batch literature search | Search strategy → `tmp/papers_X_X.json` (section-specific) |
| Metadata extraction + Zotero write | papers.json → Zotero entries |
| Anti-AI compliance scan | Draft text → violation report |
| BibTeX formatting | literature data → refs.bib |
| Word count + citation validation | Draft → stats report |
| **Section synthesis writing**（叶子节正文，主会话调度）| `.write_task_<section>.json` → `.write_return_<section>.json` |

### Section synthesis writing 的约束（立场反转，见 SKILL.md Phase 3 Step 4）

synthesis writing 从"不可委托"改为"可委托"，但**只有满足全部约束才派**：
- 盲写：撰写子代理是全新一次性上下文，看不到别节写作过程，只按任务包写本节；
- 只用已核证对：承重句只准挂任务包内嵌 `certified_claims` 里的 ref_key，不得自配文献/自证；
- 只写 `[@key]`：正文引用一律 `[@key]`（key=gid 或 `new:<slug>`），绝不写裸数字 `[N]`（编号权焊死主会话）；
- `framing_guide` 进任务包：章节框架/论证思路由主会话从 `data/framing_guide.md` 提炼后嵌入，子代理照此搭结构。

**质量天花板（诚实标注）**：综述最吃全局视野，synthesis 子代理的衔接/主线呼应天然弱于主会话亲写。补偿手段=framing_guide + 邻节 digest + 已核证对 + 主会话跨节语义审 + Step 10 盲检；这是配强兜底的放开，不是零成本银弹。

## NOT Delegatable

Outline design, 逐节质量自检的修订/HALT decisions, user interaction, HALT decisions。（synthesis writing 已移入 Delegatable，见上；大纲设计/HALT/用户交互仍必须主会话亲为。）
