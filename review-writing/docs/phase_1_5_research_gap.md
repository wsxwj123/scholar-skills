# Phase 1.5: Research Gap Identification（Write Mode only）

> **⭐ 执行顺序（调研先于提纲）：这是 Phase 0 之后的第一个实质阶段。** 提纲不在这里建，先调研（1.5 空白 + 1.6 对标框架），到 **Phase 1.7** 才据调研结果建提纲并落结构签字。

**触发时机：** Phase 0 初始化后立即进入（提纲尚未建立，先摸清领域再据此建提纲）。Polish Mode 跳过（已有成稿）。
**Entry: Read `outline.md`（此时仅有模板骨架）+ `state.json`. If `phase ≥ 1.6`（对标框架已完成）→ already done, skip.**
> **Phase gate:** `state.json` 不存在 → HALT，提示先完成 Phase 0 初始化（Phase 0.5 生成 outline.md/state.json）。

**目的：** 建提纲、搭框架之前，先用**已检索到的真实文献**把这个领域摸清楚：有哪些热点、哪些争议、哪些机制线索、哪些没人填的空白，再让用户挑选题方向。综述的新意不是靠多引文献堆出来的，而是找到一个**有证据支撑、又还没被人好好综述过**的空白。提纲要等这一步读透了才动手。

### 步骤

0. **先定 RQ/PICO（提纲的语义锚点）：** 与用户确认研究问题 RQ/PICO（scoping review 用 PCC：Population/Concept/Context），写入 `outline.md` 的 `## Research Question` 区。RQ/PICO 明确后，探索性检索与后续提纲各节才有检验标准。（完整提纲结构在 Phase 1.7 据调研结果建立，此处只锚定研究问题。）

1. **初始化 index 并取证文献：** 先建空索引 `python3 scripts/state_manager.py init-index`（幂等，创建 `data/literature_index.json` + `data/synthesis_matrix.json`）。围绕 RQ/PICO 做一轮**探索性检索**（串行，≥1s 间隔，工具优先级同 Phase 2）。**探索阶段只写 `data/literature_index.json`（不依赖 Zotero 集合树，集合树在 Phase 1.7 建提纲后才创建）**，每篇跑 `citation_guard.py`，**gap 只能由 verified 文献推出**。本步入库可与 Phase 2 共享 index（不重复入库）。
   > ⚠️ 红线：gap 必须从真实文献证据推出，**禁止脑补**。每个 gap 关联 ≥1 篇支撑文献 `[n]`，且该 `[n]` 已 citation_guard verified。

2. **识别四类信号**，写入 `data/research_gap.json`：
   - `candidate_topics[]`：候选选题方向（每个含一句话 framing + 支撑 refs）
   - `hotspots`：近年高频/高被引主题（含 support_refs）
   - `controversies`：文献中的矛盾发现/未决争论（含对立双方 refs）
   - `gaps`：研究空白（每个含 `id` / `description` / `support_refs[]` / 为何是空白）
   - `novelty_risk`：候选选题与**既有综述/已发表工作**的重叠度比较，标 high/medium/low + 理由（防止"重复造轮子"）

   ```json
   {
     "candidate_topics": [{"topic": "...", "framing": "...", "support_refs": [3, 7]}],
     "hotspots": [{"theme": "...", "support_refs": [3, 12]}],
     "controversies": [{"issue": "...", "side_a_refs": [5], "side_b_refs": [9], "note": "..."}],
     "gaps": [{"id": "gap-1", "description": "...", "support_refs": [7, 12], "why_gap": "..."}],
     "novelty_risk": [{"topic": "...", "overlapping_reviews": [...], "risk": "low", "reason": "..."}]
   }
   ```

3. **DoD 自检（gate `research-gap-dod`，委托独立subagent盲检）：**
   ```bash
   python3 scripts/delegate_review.py pack --checklist "[DOD_CHECKLIST]" \
     --gate research-gap-dod --files data/research_gap.json --workdir .
   # → 派独立subagent（Claude Code 用 academic-blind-reviewer），不给写作上下文，按任务包返回 JSON
   python3 scripts/delegate_review.py verify --checklist "[DOD_CHECKLIST]" \
     --gate research-gap-dod --return .review_return_research-gap-dod.json
   # 退出码非 0 = fail-closed，据subagent证据修复后重跑，未过不得声明完成
   ```
   gate 5 项：G1 每 gap ≥1 verified 文献支撑 / G2 与 literature_index 一致（无孤儿）/ G3 从真实证据推出（禁脑补）/ G4 含 novelty_risk 比较 / G5 占位符清零。逐项内容以 `references/dod_checklist.json` 为唯一真源。

4. **更新 state + Git Checkpoint：**
   ```bash
   python3 scripts/state_manager.py set-phase --phase 1.5
   git add -A && git commit -m "[review] Phase 1.5: research gap identified" --allow-empty-message 2>/dev/null || true
   ```

**HALT. 向用户展示 candidate_topics / gaps / novelty_risk，等用户确认选题方向后再进 Phase 1.6。**

5. **🔴 选定主线落盘衔接（防长会话丢主线，HALT 确认后必做）：** 用户确认选题方向后，立即把"选定的综述主线（选题方向 + 核心 gap）"显式固化，作为 Phase 2/3 的主线依据，不靠隐式记忆：
   - 在 `research_gap.json` 被选中的 gap/candidate_topic 上加 `"selected": true` 标记；
   - 同时把"选定主线 = 选题方向 + 核心 gap 一句话"写入 `outline.md` 顶部的主线锚点区（无则在文件首行新增 `## 综述主线（锚点）` 区块）。
   - 落盘后再补一次 Git Checkpoint。
