# Phase 1.6: Benchmark Review Library + Framing Guide（Write Mode only）

**触发时机：** Phase 1.5 选题确认后、**Phase 1.7 建提纲前**（对标框架既指导 Phase 1.7 的提纲结构，也在 Phase 3 搭正文框架时复用）。Polish Mode 跳过。
**Entry: Read `outline.md` + `state.json`. If `phase ≥ 1.7`（提纲已定）→ already done, skip.**
> 🔴 **断线重连保护（同 Phase 1.5，只看 phase 会白跑一轮对标检索）：** `set-phase 1.7` 在**进入 Phase 1.7 时**才执行，"用户已确认对标框架、但会话在进 1.7 之前断了"这个窗口里 `phase` 仍是 1.6。
> **判据用产物、不用 phase：** 若 `data/benchmark_reviews.json` 与 `data/framing_guide.md` **都已存在且非空** → 本阶段已完成，补跑 `set-phase --phase 1.7` 后直接进 Phase 1.7，不要重跑对标综述检索。
> **Phase gate:** `phase < 1.5` → HALT，提示先完成 Phase 1.5。

**目的：** 好综述的框架不是拍脑袋想出来的。找近年 5–10 篇**对标综述**（同领域顶刊 review），看它们怎么分章节、怎么讲道理、图和正文怎么配合、引言-主体-展望怎么组织，把这些可复用的套路提炼出来，Phase 3 搭正文框架时直接照着用。

### 步骤

1. **检索对标综述：** 工具优先级同 Phase 2（串行，≥1s）。目标 5–10 篇近年同领域高水平综述（Nature Reviews / Cell / Lancet 系等）。每篇**必须真实存在并走 citation_guard 验证**，禁编造。
   > ⚠️ 红线：对标综述真实存在、走 `citation_guard.py` 验证，不编造标题/期刊/年份。

2. **建对标库 `data/benchmark_reviews.json`：** 每篇含
   ```json
   [{
     "title": "...", "journal": "Nature Reviews ...", "year": 2023,
     "framework_outline": "该综述的章节框架（背景→机制→应用→挑战→展望 ... 具体到节）",
     "highlights": "亮点：如何 framing、如何仲裁矛盾、图怎么用",
     "verified": true
   }]
   ```

3. **提炼 `data/framing_guide.md`：** 从对标库归纳**可操作**的写作思路，至少覆盖：
   - 可复用的章节框架骨架（漏斗引言 → 主题主体 → 展望）
   - 论证思路（如何从 setup → evidence → synthesis → implication）
   - 图表与正文的关系（概念框架图放哪、每节图承担什么角色）
   - 引言-主体-展望的组织套路
   - 对**本综述**的具体建议（结合 Phase 1.5 的 gap，而非泛泛而谈）

4. **DoD 自检（gate `benchmark-reviews-dod`，委托独立subagent盲检）：**
   ```bash
   python3 scripts/delegate_review.py pack --checklist "[DOD_CHECKLIST]" \
     --gate benchmark-reviews-dod --files data/benchmark_reviews.json data/framing_guide.md --workdir .
   python3 scripts/delegate_review.py verify --checklist "[DOD_CHECKLIST]" \
     --gate benchmark-reviews-dod --return .review_return_benchmark-reviews-dod.json
   ```
   gate 4 项：B1 ≥5 篇 verified / B2 每篇含框架大纲 / B3 framing_guide 含可操作建议 / B4 占位符清零。真源见 `references/dod_checklist.json`。（framing_guide 是否真被用于搭框架，是 Phase 3 才发生的动作，不在此 Phase 1.6 gate 里核，改由 Phase 3 framing hook 强制落实、见 SKILL.md Phase 3 “Framing hook”。）

5. **更新 state + Git Checkpoint：**
   ```bash
   python3 scripts/state_manager.py set-phase --phase 1.6
   git add -A && git commit -m "[review] Phase 1.6: benchmark reviews + framing guide" --allow-empty-message 2>/dev/null || true
   ```

**HALT. 向用户展示对标库与 framing_guide 要点，确认后进 Phase 1.7（据调研建提纲）。**

> **🔗 Phase 1.7 + Phase 3 挂接（强制）：** Phase 1.7 建提纲结构、Phase 3 各节搭正文框架前，都必须 `Read data/framing_guide.md`，并使结构与其提炼的可复用框架对齐（由 Phase 3 “Framing hook” 强制落实）。这是 Phase 1.6 产出的落地点，不得跳过。
