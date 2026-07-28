# 交互协议细则 (interaction-protocol)

> 被 SKILL.md 的 §4/§7/§9/§12/§13 指针引用。内含写入安全检查、快照判断、自我修正回路、摘要补全、章节上下文与Token预算的完整细则。

---

## §4 写入安全检查 (Anti-Overwrite Check)

在执行 `write_file` 之前，必须进行以下自查：
1. **Check Existence**：目标路径是否存在文件？
2. **Diff Check**：如果存在，读取旧内容。如果新内容是旧内容的**完全覆盖**（而非追加或优化），必须先将旧文件重命名备份为 `.bak`，或者向用户发出**高风险警告**。
3. **Report**：告知用户："已创建新文件 [Filename]" 或 "已更新 [Filename] (原文件已备份)"。

---

## §7 智能快照判断 (Smart Snapshot)

在每次回复结束时，进行内部判断：
- "我刚刚生成了新的正文段落吗？"
- "用户刚刚确认了一个关键决策吗？"
- "我刚刚添加了新的文献到索引吗？"

**如果有任意一个为 Yes** → **主动执行** `/snapshot` 并告知用户。

---

## §9 自我修正回路 (Self-Correction Loop)

在生成任何正文段落时，必须在内部执行以下隐式思维链：
1. **Draft**：生成初稿。
2. **Critique**：
   - "这是否太啰嗦？"
   - "是否用了 'It is well known' 等废话？"
   - "核心论点是否展开了 200 词以上？"
   - "逻辑连接词是否自然？"
3. **Polish**：根据 Critique 修改。

**输出原则**：只输出 Polish 后的最终版本，不要向用户展示修改过程。

---

## §12 摘要补全协议 (Abstract Recovery Protocol)

**针对检索结果中缺失摘要（Abstract）的文献，严禁直接丢弃。必须严格执行以下补全回退链（Mandatory Fallback Chain）**：

1. **Google Scholar (Primary)**：必须优先使用 `mcp__paper-search-mcp__search_google_scholar` 检索论文标题。
2. **PubMed (Secondary)**：若前者失败，使用 `mcp__paper-search-mcp__search_pubmed` 或 PubMed CLI 按标题检索。
3. **Tavily (Final Fallback)**：若前两者均失败，才允许使用 `mcp__tavily__tavily-search` 搜索 "Title abstract"。

**执行边界**：
- Tavily 在此阶段只允许补全 `abstract` 或辅助反向核验，**不得**替换原始文献的 `source_provider` / `source_id`。
- 若该条文献本身没有 DOI/PMID，且 Tavily 仅提供网页级佐证，则必须进入 `manual_review_queue.json`，且不得视为 `verified=true`。

**终止条件**：仅当上述三个步骤均无法获取摘要时，才允许将该文献标记为 "Abstract Missing" 并询问用户手动补充。

---

## §13 章节局部上下文与Token预算协议 (Section-Local + Budget Guard)

**目标**：在保证连续性的同时，严格控制上下文规模，避免失忆与爆 token。

### 默认行为（强制）

每次写作动作开始前，必须执行此上下文加载校验（解决"健忘"）：

1. 执行 `/write [section]` 前，必须优先加载章节局部上下文（统一强制入口，默认含全局历史 + 当前章节索引，不含正文草稿）：
   - **Prewrite（必须先跑）**：`python scripts/state_manager.py write-cycle --section [section_id] --token-budget 6000 --tail-lines 80`
   - 若需续写/改写已存在章节正文，再显式追加 `--include-draft`。
   - **Postwrite 收口（落盘前必须跑，缺 `--refs-confirmed` 则 exit 2 硬阻断）**：`python scripts/state_manager.py write-cycle --section [section_id] --finalize --refs-confirmed --sync-literature --sync-apply --strict-references --summary "[本节一句话摘要]"`
2. 若用户未明确要求，禁止读取其他章节正文文件。
3. 输出中必须包含 `loaded_files`，作为"只读当前章节"的审计证据。
4. **隔离**：校验内容仅用于内部校验与必要的用户审计，**严禁**写入生成的 Markdown 稿件文件中。
5. **展示策略**：默认不在用户回复中展开加载明细；仅在用户要求"显示加载明细/审计日志"时展示。

> **审计日志示例**（仅当用户要求"显示加载明细"时输出，平时不展示）：
> ```
> writing_progress.json: ✅ Loaded
> context_memory.md: ✅ Loaded (Tail)
> （其他文件仅在需要时按需加载）
> ```

### 章节白名单（仅允许）

1. `project_config.json`
2. `storyline.json`（仅当前 section 过滤结果）
3. `figures_database.json`（仅当前 section 过滤结果）
4. `literature_index.json`（仅当前 section 过滤结果）
5. （默认不读）`manuscripts/` 下匹配当前 section 的原子化文件，仅在 `--include-draft` 时加载
6. `section_memory/[section_id].md`
7. `figure_analysis/figure_{N}.md`（撰写对应 Results 小节时，由 `/write` 在 write-cycle 之外**显式 `Read` 加载**；write-cycle 不自动加载它，须手动读取，作为该节结果与讨论的事实依据）

### 预算熔断策略

1. 若估算 token 超出预算，先裁剪当前章节正文到 tail。
2. 再裁剪章节记忆到 tail。
3. 再压缩文献与图数据为 compact 字段。
4. 若仍超预算，输出 `over_budget=true` 并要求进一步压缩输入数据。

---

## `/change-journal` 中途转投流程

写完一半想转投另一家期刊（如 Nature 退稿→投 Nat Commun）触发：
1. 询问新 `target_journal` 名称 → 上面表查或官网查新 `word_limits` / Abstract 结构 / Methods 位置。
2. 用 `update` 命令改 `project_config.json` 的 `target_journal` + `word_limits` 字段。
3. 立即跑 `/check` 1-2 步看正文字数是否需要砍（或新刊允许更长，可保留）。
4. 重跑 `/submission-pack`——它会 Read `submission_state.json`，仅问"哪些字段需要因转投而改"（如 cover letter 编辑名、suggested reviewer 是否变），不重新问全部。
5. 若新刊 Methods 结构不同（如 STAR Methods vs Online Methods），需重新组织 `manuscripts/03_Methods*.md`。

---

## `/upgrade-scripts` 升级脚本（解决版本漂移）

项目 init 后 scripts/ 是该时点 skill 的快照副本；skill 后续更新（如新增 `add-figure` / `add-abbreviation` / `add-stat-method` / `rename-figure` / `proofread` 等命令）后，旧项目用不到新功能。触发：用户说"升级脚本"/"项目脚本是旧的"。流程：
1. 提示用户备份：`cp -r scripts scripts.bak.$(date +%Y%m%d)`
2. 从 skill 源拷贝最新版：`cp ~/.claude/skills/general-sci-writing/scripts/*.py ./scripts/`（路径按用户实际 skill 安装位置调整）
3. 验证：`python scripts/state_manager.py --help` 看是否含 `add-figure` / `add-abbreviation` / `add-stat-method` / `rename-figure` 等新子命令；`ls scripts/` 看是否含 `proofread.py`。
4. 若有不兼容的 STATE_FILES 字段（如旧项目缺新 key），新版脚本会自动按 `get(..., default)` 兼容，无需手动迁移。
