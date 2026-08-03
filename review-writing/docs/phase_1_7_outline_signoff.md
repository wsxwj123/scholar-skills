# Phase 1.7: Outline from Research + Structure Sign-off + Collection Tree

> **执行顺序：Phase 0 → 1.5（研究空白）→ 1.6（对标框架）→ 本阶段 1.7 → Phase 2。** 提纲是读透调研后的产物，所以先做完 1.5/1.6 才轮到这一步。**进入条件：`phase ≥ 1.6`（`data/research_gap.json` 已有 `selected` 主线 + `data/framing_guide.md` 就位）；若 `phase < 1.6` → HALT，回去先做 Phase 1.5 / 1.6。**

**Start: Read `outline.md` + `state.json` + `data/research_gap.json`（取 `selected` gap/选题方向）+ `data/framing_guide.md`（对标框架）+ `data/benchmark_reviews.json`. If state.json shows phase≥2, skip.**
**Polish Mode: if `state.json` contains `"mode": "polish"`, skip Phase 1.5/1.6/1.7 entirely and go to Phase 3.**

1. **据调研建提纲（不是凭空设计）：** RQ/PICO 已在 Phase 1.5 定义。以 **Phase 1.5 选定的 gap/主线** 为骨架、参照 **Phase 1.6 framing_guide 的可复用章节框架**，提出提纲结构："Funnel" Introduction + "Thematic" Body（≤2 层级）。每个主体节次应能对应到某个 gap / 争议 / 主线分支，避免与既有对标综述结构简单雷同（呼应 novelty_risk）。
   - Scoping review：研究问题用 PCC（Population / Concept / Context）。
2. **对齐对标框架：** 显式说明本提纲如何借鉴/区别于 framing_guide 提炼的结构（由 Phase 3 “Framing hook” 强制落实）。
3. **Confirm outline with user.** Update `outline.md`.

   > **⚠️ 迭代闸（Iteration Gate）：提纲在此可回修。**
   > Phase 2 检索完成后，若揭示出提纲遗漏了重大分支或主要争议（例如：某类方法在文献中被大量讨论但提纲无对应节次），允许回到此步修改提纲，并记录修改理由：
   > ```
   > [Outline revision after Phase 2 search]
   > Reason: Phase 2 revealed that X is a major branch in literature (~N papers) but
   >         was not covered in the original outline. Added Section X.X.
   > Impact: Related sections [list] may need additional citation targets.
   > ```
   > 修改后须更新 `outline.md`，重新确认 Zotero 集合树（`--init` 是幂等的），并用 Git Checkpoint 记录版本。**不得因回修提纲而删除已完成节次的已有文献入库记录。**

   > **[结构签字·强制门禁落锁]** 用户在对话里明确确认提纲后（且**仅在此之后**），运行 Phase 0.5 `init_project.py` 打印的那条 `SIGNOFF_CMD`（已含解析好的绝对路径与项目根）落盘签字，即 `python "<review-writing>/scripts/structure_signoff_gate.py" confirm --root <项目根> --note "<用户确认原话摘录>"`。这一步解锁正文写作：**未落签字，PreToolUse hook 会在工具层拦下（deny）任何对 `drafts/section_*.md` 的写入**（这是防跳步的硬门，不是提示词纪律：写文件类工具一律 deny，经 shell 的写入另有一条 Bash 钩子拦，任何绕行都会记进项目根的 `.academic_gate_audit.jsonl` 供用户复核）。该 hook 由 Phase 0 `init_project.py` 开工时经本技能 vendored 的 `install_gate_hook.py`（在 `scripts/` 下）自动安装并校验，它先把门禁四件套部署到 `~/.claude/academic-gate/`（稳定位置，不随技能目录增删而动），再让 `settings.json` 的 hook 指向那里，单独分发的技能也能自装（备份原 settings / 只追加不覆写 / 校验失败即回滚），init 回显 `门禁保护[active]` 即在岗生效；若回显 `[installed]`，表示首次安装成功、settings.json 已写入，但 hook 需【重启一次本会话】后才加载生效（无法热生效）；若回显 `[degraded]` 或 `[error]`（安装/校验未通过，如缺 `_shared`），拦截层不在岗、降级为提示词纪律，签字仅留痕、无强制，需人工守住「未签字不写 `drafts/section_*.md`」。若后续回修提纲（上方迭代闸允许），改完让用户重新确认并重跑本命令覆盖签字。**签字与它签的那份大纲绑定**：节号/标题/层级/顺序任一变化（含只增不删的细化扩展），下次写正文会被门禁拦下并逐条列出哪几节变了，须由用户重新确认后重跑本命令；进度、统计、时间戳这类变动不触发重签。⚠️ 严禁在用户未确认时自行运行 confirm，那等于伪造用户签字。

4. **规划贯穿全文的概念框架图（提纲确认后，Phase 1.7 内完成）：**
   在 `figures/figure_index.md` 中注册一条 `Figure 0`（概念框架图），要求：
   - 覆盖全文逻辑主线（背景→机制/方法→应用/挑战→展望），体现各节之间的内在逻辑联系
   - 包含 Key Message（一句话）、草稿 Caption（出版级精确度）、节次映射关系
   - 写作时（Phase 3）各节需在文中引用该图，"如 Figure 1 所示"
   ```
   ## Figure 0: [Conceptual Framework — Title of Review]
   - Type: Conceptual overview
   - Section: ALL (全文贯穿)
   - Key Message: [one sentence summarizing the review's core argument/framework]
   - Caption: [draft — publication-ready, ≤150 words]
   - Node mapping: [e.g., "Section 1.1→Background box; Section 2.X→Mechanism module; Section 3.X→Application module"]
   ```

6. **Initialize Zotero collections (Zotero mode):**
   ```bash
   # First check if collection tree already exists (idempotent, safe on re-entry):
   ROOT_KEY=$(python3 scripts/zotero_manager.py --status --find-root-title "[TITLE]" \
     2>/dev/null) && echo "Root exists: $ROOT_KEY" \
     || python3 scripts/zotero_manager.py --init --title "[TITLE]" --outline outline.md
   ```
   - `--find-root-title` exit 0 → root already exists (stdout = key, reuse it); exit 3 → no match, the `||` branch runs `--init`; exit 4 → ambiguous (multiple same-named roots), stdout lists candidate keys. **Stop and ask user to pick** rather than letting `--init` create a duplicate.
   - Creates root collection + subcollections matching outline hierarchy.
7. **Initialize index files (None/EndNote mode):**
   ```bash
   python3 scripts/state_manager.py init-index
   # Creates empty data/literature_index.json + data/synthesis_matrix.json + figures/figure_index.md (idempotent).
   ```
8. **Update state.json** (writes phase=1.7 + zotero_root_key, preserving other keys):
   ```bash
   python3 scripts/state_manager.py set-phase --phase 1.7
   python3 scripts/state_manager.py set-root-key --key "[key from step 6]"   # Zotero mode only; skip in None/EndNote
   ```
9. **Git Checkpoint** (见复用块, msg: `[review] Phase 1.7: outline confirmed (post-research)`)

**HALT. Wait for user to confirm outline before Phase 2.**
