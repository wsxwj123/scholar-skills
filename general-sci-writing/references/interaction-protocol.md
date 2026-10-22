> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

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
     - `--finalize` 的 `--status` 默认 `done`（= 本节收口），下一节 `prewrite_gate` 的"上一节完成"才会放行。本节其实**没写完**时才显式传 `--status draft`，那样下一节会被正确拦住。
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
2. 从 skill 源拷贝最新版：`cp ~/.claude/skills/general-sci-writing/scripts/*.py ./scripts/` 与 `cp ~/.claude/skills/general-sci-writing/references/* ./references/`（`references/` 同样会漂：`dod_checklist.json` 的核查项会随 skill 增补；`mkdir -p references` 后再拷，老项目本来没有这个目录。路径按用户实际 skill 安装位置调整）
3. 验证：`python scripts/state_manager.py --help` 看是否含 `add-figure` / `add-abbreviation` / `add-stat-method` / `rename-figure` 等新子命令；`ls scripts/` 看是否含 `proofread.py`；`ls references/` 看是否含 `dod_checklist.json`。
4. 若有不兼容的 STATE_FILES 字段（如旧项目缺新 key），新版脚本会自动按 `get(..., default)` 兼容，无需手动迁移。

---

# 原 SKILL.md「核心交互协议」存档（2026-10-19 拆分保留；§4/§7/§9/§12/§13 概括版已去重，其余逐字保留）

> 历史存档。保留原 SKILL.md 中无细则版对应的 §1/§2/§3/§5/§6/§8/§10/§11 原文；§4/§7/§9/§12/§13 已由上半段细则完整覆盖，概括版已删除（2026-10-19 有意去重）。

## 🧠 核心交互协议 (Core Interactive Protocol)

### 1. 跨平台路径协商与自包含初始化 (Cross-Platform & Self-Contained Init)
**项目必须自包含，严禁依赖 Skill 安装路径**（便于 Windows/Mac 迁移）。
- **路径询问（Mandatory）**：`/init` 前必须先问用户保存路径。建议 Mac `~/Desktop/Manuscripts`，Windows `C:\Users\[User]\Desktop\Manuscripts`。
- **Command Logic**（便携部署：把运行所需文件拷进项目根，换机也能用）：
  1. `mkdir -p [Target_Path]/scripts [Target_Path]/configs [Target_Path]/references [Target_Path]/manuscripts [Target_Path]/section_memory [Target_Path]/figures [Target_Path]/figure_analysis [Target_Path]/reviews [Target_Path]/submission`
  2. `cp [Skill_Path]/scripts/*.py [Skill_Path]/scripts/*.json [Target_Path]/scripts/`（同时拷入 gate_registry.json 等 json；测试文件 test_*.py 属技能自测、不进项目,拷完即删:`rm -f [Target_Path]/scripts/test_*.py`,保证项目 scripts/ 有 gate_registry.json、无 test_*.py；技能仓 scripts/ 里可能躺着维护者本机的运行时残留 env_status.json（gitignore 的运行时产物、不是技能文件），同样不许进项目，拷完即删:`rm -f [Target_Path]/scripts/env_status*.json`）
  3. `cp [Skill_Path]/templates/*.json [Skill_Path]/templates/reference.docx [Target_Path]/`（`reference.docx` 是 `/merge` 导 docx 的字体锁定模板，与 json 一样扁平落到项目根，merge 按候选位置自动认出；漏拷 = 首次导 docx 必撞 `reference_doc_missing` 硬失败）
  4. `cp [Skill_Path]/configs/*.json [Target_Path]/configs/`
  5. `cp [Skill_Path]/references/* [Target_Path]/references/`（**不能省**：`dod_checklist.json` 是盲检门 `delegate_review.py` 的运行时输入，不拷则盲检 pack/verify 在项目根 exit 2 → `.review_pass/` 落不下 → 下一节被 `prewrite_gate` 硬拦；其余 `references/*.md` 是写作时按需 `Read` 的口径真源，拷进来才符合"项目自包含"）

  > **Windows (PowerShell)**：以上 5 步是 POSIX 写法。`mkdir -p` 用 `New-Item -ItemType Directory -Force -Path ...`；`cp ...*.py` 用 `Copy-Item ...\scripts\*.py -Destination ...\scripts\`。或让 AI 按"把 scripts/templates/configs/references 拷进项目根、项目自包含不依赖 Skill 安装路径"的语义,用等价 PowerShell/Python 命令完成。

### 2. 数据依赖熔断机制 (Data Dependency Hard Stop)
**Scope**: 此机制仅适用于 **Phase 8 (/write)** 的 Results/Discussion 章节。**严禁**在 Phase 1 (/preview) 或 Phase 2 (/storyline) 阶段因缺失具体实验数据而阻断流程。
**在执行 `/write` 撰写 Results/Discussion 章节前，必须执行以下检查**：
1. **Check Data Status**: 检查 `figures_database.json` 中该章节涉及的 Figure 的 `data_status`。
2. **按缺失粒度判定（Core vs Auxiliary）**：
   - **核心定量缺失**（支撑组间结论的数值 / 统计检验 / 显著性，如 P 值、关键 n、效应量数值）→ `data_status=pending`：**立即停止**撰写，**输出数据收集表**（缺失的 Figure ID + 数据项），告知用户："我无法在没有核心数据的情况下撰写。请提供上述数据，我将立即开始。"
   - **辅助元数据缺失**（误差棒类型 SD/SEM、非关键 n、量纲细节等不改变结论方向的项）→ **不阻断**写作，但必须在正文/图注以 `<!-- [DATA_PENDING: 项目] -->` 标注待补，交付前清零。
   - **禁止**：无论哪种，严禁编造数据或使用占位符（如 "XX%"）填充缺失值。

### 3. 原子化文件管理 (Atomic File Policy)
- **原则**：一个 Sub-section = 一个独立 Markdown 文件。
- **禁止**：严禁将整个 Results 或 Introduction 写入同一个文件。
- **命名规范**：`{ChapterID}_{SectionID}_{Keyword}.md`
  - ✅ `04_Results_3.1_Characterization.md`
  - ✅ `04_Results_3.2_Uptake.md`
  - ❌ `04_Results.md`
- **🔴 修改/润色的唯一合法目标（铁律）**：任何对正文的修改、润色、改写、重组，**只能改 `manuscripts/*.md` 原子化文件**。**严禁修改**以下派生/合并产物（它们由脚本自动生成，下次 `/merge` 会覆盖你的修改、工作丢失）：
  - `manuscripts/Full_Manuscript.md`（`/merge` 合并稿）
  - `*.docx`（pandoc 转出物）
  - `figure_analysis/figure_*.md` 之外的拼接稿
- **润色 workflow（强制）**：用户给你一段需修改的文本 → ① 先 `grep -rn "<原文片段前 8-15 字>" manuscripts/` 定位它在**哪个原子化文件**；② 命中 `Full_Manuscript.md` 等派生物 → **不要改它**，回到对应的原子化源文件改；③ 同一片段在多个原子化文件命中 → 停下问用户改哪个，不要猜；④ **grep 0 命中（项目未初始化或文本不在项目中）→ 进入独立润色模式**：明确告知用户"该文本未在当前项目找到，将做无状态润色（不写文件、不打快照），结果直接贴回；如需持久化请先 `/init` 后将文本写入对应 `manuscripts/0X_*.md`"，绝不静默写入新文件、绝不猜测归属；⑤ 改完提醒用户重跑 `/merge` 才能在合并稿/docx 中看到更新。
- **自检（写入前必答）**：在 `Edit`/`Write` 任何 `.md` 前，自问"这是 `manuscripts/` 下的原子化源文件吗？还是合并稿/派生物？"。后者一律拒绝写入。

### 5. 上下文显式验证 (Mandatory Context Check)
为解决"健忘"，每次写作前必须执行上下文加载校验（命令、白名单、隔离/展示策略、审计日志示例见 §13）。

### 6. 引用格式强制 (Strict Citation Format)
- **索引绑定**：在 Phase 3 (/literature) 阶段，必须将检索到的文献写入 `literature_index.json`。文中的 `[n]` 必须对应 `literature_index.json` 中的列表索引（n = Index + 1）。
- **正文标记**: 严禁使用 `[Ref 1]`, `[Author, 2023]`, `(1)` 等格式。
  - **必须使用**: **`[n]`** 格式。
  - *Examples*: `[1]`, `[1,2]`, `[5-7]`, `[1,3,5]`.
- **小节末尾列表**: 在撰写每个小节（Markdown文件）的末尾，**必须**附上该小节所引用的参考文献列表（Vancouver格式）。
  - *格式*: `1. Author AA, et al. Title. Journal. Year;Vol:Page.`

### 8. 弹性写作深度 (Elastic Depth)
- **核心论点 (Key Claims)**：必须展开讨论。包含：数据描述 + 统计意义 + 机制解释 + 文献对比 + 意义阐述。
- **辅助数据 (Supporting Data)**：仅描述结果和直接结论。

### 10. SI 主动建议与整合 (SI Proactive Loop)
**在完成每一小节的正文初稿后，必须执行以下步骤**：
1. **Analyze (分析)**：读取当前小节的 Storyline 和 Hypothesis，并**检查 `si_database.json`**。思考：
   - "为了从数据A跳跃到结论B，中间缺失了什么逻辑链？"
   - "是否有排除混杂因素的对照实验在Main Text中为了简洁被省略了？"
   - "方法学上是否有需要验证的细节（如纯度、特异性）？"
   - "当前SI数据库中是否已存在相关证据？如果不存在，必须主动询问。"
2. **Propose & Ask (建议与询问)**：
   - 如果发现逻辑缺环且 `si_database.json` 中无对应数据，**必须主动询问 (Proactively Ask)** 用户。
   - *Example*: "为了证明疗效并非源于载体毒性，建议在SI中补充空白载体的细胞毒性数据 (Figure S2)。您手头有这个数据吗？"
3. **Persist (持久化)**：
   - 获得用户确认的SI内容后，**立即**将其写入 `si_database.json` 保存。
4. **Integrate (整合)**：
   - 将SI引用（如 `(Figure S1, Table S2)`）作为完整证据链的一部分自然插入正文。

### 11. 强制交互结构 (Mandatory Response Architecture)
每次回复（除极简确认外）必须含 3 部分：
- **Part 1 执行内容**（用户可见）：对话 / 执行 / 写入结果。**若用户给了数据**：必加 `🧪 实验逻辑批判`，逐项核查 ① Design Check（对照组合理？如有无空白载体对照）② Reliability（n 够？统计明确？）③ Consistency（Fig 间结论矛盾？）④ Verdict（明确 "Reliable" 或 "Flaw Detected"）。
- **Part 2 状态仪表盘**（默认内部维护，仅用户要审计日志/加载明细时输出）：Word Count（节/总，Key Section 参考 ~500 词，仅提示不硬卡）、Data Logic（Pass/Flaw）、SI Loop（Pending 数）、Snapshot（Created/Skipped）+ State Persistence Log（仅列本轮更新的状态文件）。
- **Part 3 深度交互**（用户可见）：反向拷问（<100 字犀利挑战）+ 你可能想知道（预测性建议/背景知识）。

---

## 启动前置：Python 解释器探测（原 SKILL.md 21–26，2026-10-19 拆分保留，逐字未改）

**【Python 解释器探测：启动前置，一次探测全程沿用】** 本文档中的 `python3` / `python` 仅为 macOS/Linux 默认写法，非硬性指定。启动前执行一次 `python3 --version`：
- 正常返回版本号 → 本次会话所有命令统一使用 `python3`。
- 返回 command not found、无输出或弹出应用商店 → 改为执行 `python --version`，若返回版本号则将后续所有命令的解释器统一替换为 `python`。Windows 系统自带一个 0 字节的 `python3` 占位程序，`python3 --version` 弹出商店或无输出即为命中该占位程序，**视为不可用**，按无 python3 处理（用户亦可在「设置 → 应用 → 应用执行别名」中关闭 `python3.exe`）。
- 若 `python` 亦无法返回版本号则回退至 `python3`（macOS 12.3 起系统不再内置 `python`）。
- 二者均无法返回版本号，表明当前环境未安装 Python，应停止流程并提示用户安装，不得强行执行。
- 探测仅执行一次，后续所有命令沿用同一解释器名称，无需逐条重试。
