> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

### Phase 1.9: 体裁前置确认（Mandatory，提示级闸门）
构建 storyline 前须先向用户确认稿件体裁，体裁误判将导致后续全部流程失效（本闸口脚本无法自动判定体裁，依赖提示级把关）：
- **研究论文（Article / IMRaD，有原始数据与结果）** → 留在本技能，进入 Phase 2。
- **综述 / 文献综述（无原始实验，梳理与综合已有文献）** → 停下，转 **review-writing** 技能。
- **学位论文 / 毕业论文（博士 / 硕士，中文，SCI 转学位论文）** → 停下，转 **sci2doc** 技能。

无法判定时应直接询问用户"本稿件为投期刊的研究论文、综述还是学位论文？"，获得明确答复后方可继续；**严禁默认按研究论文处理并直接构建 storyline**。

### Phase 2: 故事脉络构建 (`/storyline`)
构建融合Results与Discussion的提纲。

**目标期刊适配（Mandatory）**：先读 `project_config.json` 的 `target_journal`，按下表硬约束 storyline：

| 期刊家族 | Abstract | Article 正文（不含 Methods/Refs/Legends） | 主图上限 | Methods 位置 |
|---|---|---|---|---|
| Nature / Nature 子刊 | ≤200 词，**unstructured** | 4500-5000 词 | 4-6 主图 + SI 不限 | 文末（Online Methods） |
| Cell / Cell 子刊 | ~150 词，可 structured | 5000-7500 词 | 7 主图（含 GA） | **STAR Methods 结构化**（Key Resources Table + Method Details） |
| Science | ≤125 词 | 2500 词 + 30 refs（Research Article 不限）| 4 主图 | 文末 |
| NEJM / Lancet / JAMA | 250 词 **structured**（Background/Methods/Results/Conclusions）| 3000-3500 词 | 5 主图 + 5 表 | 文中（Methods 在 Results 前） |
| BMC / PLOS ONE / Scientific Reports | 350 词 structured | 不限 | 不限 | 文中 |

未列入上表的期刊，须查阅该刊官网 Author Guidelines 获取相应限制后告知用户，并写入 `project_config.word_limits`。Storyline 必须在期刊上限内编排，**严禁先写超 30% 再砍**。

**`/change-journal` 中途转投流程**：五步流程（查新刊限制→改 config→/check 字数→重跑 submission-pack→重组 Methods）见 `references/interaction-protocol.md`（`/change-journal` 节）。

**引用密度预估（Mandatory）**：storyline 确认前，必须为每个小节标注预估引用数量：
- Introduction 各段：背景段 1-2 篇，Gap 段 3-5 篇，创新点段 2-3 篇
- Results+Discussion 融合段：Key Section 3-5 篇，Supporting Section 1-2 篇
- Methods：0-5 篇（仅方法学原始文献）
- 预估总数写入 storyline 输出表格，作为 Phase 3 检索目标

**Title 写法规范（Mandatory，两阶段）**：storyline 阶段先出 **3 个工作 title 候选**（working titles，基于 storyline 主线，**允许后续调整**）；Phase 3 文献检索完成、知道领域 gap 后，在 Phase 8 写完 Discussion 时**回头精修 title**，此时才能体现真正的创新点定位。
- **结构选**：① **Declarative**（"X improves Y in Z"，Nature 系偏好，最高接收率）② **Mechanism-flavored**（"X regulates Y via Z pathway"，Cell 系偏好）③ **Question form**（"Does X drive Y?"，较少用，仅 Perspective/Opinion 类）
- **硬约束**：≤ 期刊 title word limit（Nature ≤15 词；Cell ≤17 词；多数 ≤25 词）；**严禁**缩写（除 DNA/RNA/PCR 等极通用词）；**严禁** 'A study of / An investigation into / Studies on' 等老式开头（信号弱、明显学生气）；**严禁** 'Novel / First / Comprehensive' 等 self-promoting 词（编辑反感）。
- **强制包含**：核心实体（具体到化合物/分子/疾病模型）+ 核心动作（improves/inhibits/activates/links）+ 必要语境（细胞类型 / 物种 / 临床场景）。
- **核对**：选定后必须 cross-check storyline 主线（创新点），title 必须能从一句话浓缩主线得到，不能有 title 没体现的 Results，也不能有 Results 没支撑的 title 承诺。

> **[用户确认检查点 Mandatory]** 展示 storyline 草稿（章节标题、核心论点、关键图序、**各节预估引用数**、**3 个 title 候选**），等待用户明确确认后才进入 Phase 2.5。禁止在故事线未确认的情况下启动图集规划。
>
> **[结构签字·强制门禁落锁]** 用户在对话里明确确认 storyline 后（且**仅在此之后**），运行 Phase 0 env_preflight 打印的那条 `SIGNOFF_CMD`（已含解析好的绝对路径）落盘签字，即 `python "<项目内 scripts 绝对路径>/structure_signoff_gate.py" confirm --root <project_root> --note "<用户确认原话摘录>"`。这一步解锁正文写作：**未落签字，PreToolUse hook 会在工具层拦下（deny）任何对 `manuscripts/*.md` 的写入**（这是防跳步的硬门，不是提示词纪律：写文件类工具一律 deny，经 shell 的写入另有一条 Bash 钩子拦，任何绕行都会记进项目根的 `.academic_gate_audit.jsonl` 供用户复核）。该 hook 由 Phase 0 `env_preflight.py` 开工时经本技能 `scripts/install_gate_hook.py`（vendored）自动安装并校验，安装器按环境分两轨：机器上已装 academic-gate 插件（`~/.claude/skills/academic-gate/`）时，hook 由插件在 Claude Code 启动时自动加载，安装器不再部署 `~/.claude/academic-gate/`，只负责摘掉它曾写进 `settings.json` 的旧条目以免重复拦截；插件不在场时（如单独分发的技能），安装器走 legacy 自装，把门禁四件套部署到 `~/.claude/academic-gate/`（稳定位置，不随技能目录增删而动），再让 `settings.json` 的 hook 指向那里（改 `settings.json` 前先备份、只追加不覆盖、校验失败即回滚）。两轨下 preflight 返回 `active` 都表示 hook 已在岗、拦截真实生效；若返回 `degraded`/`error`，preflight 会输出告警，此时硬门已降级为提示词纪律，需人工留意并手动守住未签字不写正文。若后续回修 storyline（Phase 2.5 允许），改完让用户重新确认并重跑本命令覆盖签字。**签字与它签的那份大纲绑定**：节号/标题/层级/顺序任一变化（含只增不删的细化扩展），下次写正文会被门禁拦下并逐条列出哪几节变了，须由用户重新确认后重跑本命令；进度、统计、时间戳这类变动不触发重签。⚠️ 严禁在用户未确认时自行运行 confirm，那等于伪造用户签字。

### Phase 2.5: 主图集规划 (`/figure-plan`)

**定位**：在故事线骨架确定后、文献检索前，先规划图集结构。Nature/Cell 流程中图集即论文骨架，先规划再写字，避免识图后频繁调整字数与结构。

**输入**：用户已有的实验数据概要（不需要图文件，只需知道有哪些数据/实验）+ 已确认的 storyline。

**输出**：Figure 1–N 规划表（含每张图的信息载荷、main/SI 分配建议）。

**执行步骤**：

1. **信息载荷映射**：对 storyline 每个核心论点，列出支撑它的实验数据类型，决定哪些是 Main Figure 必须展示的、哪些可移入 SI。
2. **Figure 编号规划**（草版）：
   - 按"Figure 1 = 模型/机制/全景图；Figure 2–N-1 = 核心数据图；Figure N = 转化/机理/功能验证图"的 Nature/Cell 惯例排布。
   - 每张 Figure 对应 storyline 中的哪个小节（section_id），信息载荷一句话描述。
   - main/SI 分配：结论直接的数据→main；重复验证/对照/方法学细节→SI。
   - 输出格式（表格）：Figure ID | 对应 section_id | 信息载荷（一句话）| Main/SI | 需要的数据类型（用户确认是否已有）
3. **与 storyline 双向对齐**：检查图序与 storyline 小节顺序是否一一对应；若规划图集后发现 storyline 有逻辑缺口或冗余节，**允许此时回修 storyline**（storyline 是草版，图集规划是第一次真实检验）。用户确认回修内容后更新 `storyline.json`。
4. **写入 figures_database.json（草版条目）**：用 `add-figure` 为每张 Main Figure 写入占位条目（`data_status="pending"` 表示用户尚未提供图文件），SI Figure 记录到 `si_database.json`。

**迭代规则（允许但须显式触发）**：
- Phase 6（`/figure` 识图）后若发现某张图承载的信息需拆分或合并，可回到此步更新图集规划，同步修改 `storyline.json` 对应节。
- 每次回修必须告知用户"图集规划已迭代：Figure X 信息载荷调整为…，storyline [section_id] 对应更新"，不得静默改动。
- 字数预算跟随：图集变动后必须重新评估各 section 字数是否仍在期刊上限内。

> **[用户确认检查点 Mandatory]** 展示 Figure 1–N 规划表 + main/SI 分配 + 与 storyline 对齐确认（含是否需要回修 storyline），等待用户明确确认后才进入 Phase 3 文献检索。

### Phase 3: 文献检索 (`/literature`)
分阶段检索（Phase 1核心，Phase 2写作时实时补充）。**执行前必须 `Read references/citation-policy.md`**，检索路由（生命科学 PubMed CLI / CS·AI paper-search）、Zero-Fabrication 9 条硬约束、引用类型按语境的完整细则都在那。

**检索命令**：路由、命令模板（PubMed CLI / paper-search MCP）、Provider 白名单见 `references/citation-policy.md`（文献检索工具节），Phase 3 执行前必须 `Read` 该文件。

**中文文献支线**：AI发现→用户取证（路径A/B/C）→合规入库的完整流程见 `references/citation-policy.md`（中文文献支线节）。

**执行红线**：本阶段必须遵守“文献真实性硬约束”，任何未通过同源核验的条目不得进入 `literature_index.json`，也不得在正文中引用。
**新增硬门禁**：完成本阶段后必须运行 `python scripts/citation_guard.py --index literature_index.json --mcp-cache mcp_literature_cache.json --require-mcp --report citation_guard_report.json --manual-review manual_review_queue.json`，仅当 `citation_guard_report.json` 为 `ok=true` 才能进入 `/write`。`--require-mcp` 在 Phase 3 结束时为强制参数，确保所有文献有 MCP 证据轨。
**阻断条件**：只要 `manual_review_queue.json` 非空，或报告存在 provider policy / bidirectional verification failure 相关失败项，都必须先处理后再写作。
**退出条件（Escalation Protocol）**：若人工处理后条目仍无法核验（无法获取 DOI/PMID/S2 ID），则将该条目标记为 `status=dropped`，从 `literature_index.json` 中移除，并在写作时写入占位注释 `<!-- [REF_DROPPED: 原标题] -->`，待用户手动补充替代文献后再重新分配编号。最多处理 2 轮；若问题未解决，必须告知用户并给出可操作的替代文献检索建议，不得无限等待。

**`REF_DROPPED` 占位的最终处置**：含 `REF_DROPPED` 占位的句子在 Phase 10 `/check` 阶段必须**单独列出**让用户决定 → ① 用户补替代文献 → 删占位 + 改正常 `[n]`；② 用户决定删该句 → 整句删除并检查上下文逻辑连贯；③ 用户决定弱化论点 → 删占位 + 改写为不依赖文献的描述性表述。**严禁带 `REF_DROPPED` 占位 `/merge`**，已纳入 Phase 10 占位扫描门禁（grep CITE_PENDING|DATA_PENDING|REF_DROPPED）。
**文献编号触发点（Mandatory）**：首轮检索完成、以及后续每一轮增量检索后，都必须执行"分配到小节 → 写入文献矩阵 → 全局重编号为连续 `1..N` → 同步落盘"，严禁未分配或仅追加到索引末尾就写正文；写某小节时只能引用该小节矩阵内文献。**完整分节重编号规则（首轮强制分配 + 后续增量同流程的逐条约束）见 `references/citation-policy.md`**。
**脚本硬门禁**：`sync-literature --apply` 与 `write-cycle --finalize --refs-confirmed --sync-literature --sync-apply` 默认强制执行"矩阵重编号校验"；缺失矩阵或分配不完整将直接阻断落盘（仅调试可用 `--no-require-matrix-reindex` 临时放行）。

> **[用户确认检查点 Mandatory]** 展示文献矩阵（小节-文献映射，含各节文献数和 citation_guard 通过状态），等待用户确认后才进入 Phase 8 写作。矩阵未确认禁止启动 `/write`。

> **[P4·文献抽验·用户必做]** 文献进正文前，用户应随机抽 2-3 篇让 AI 报 PMID/DOI，自己上 PubMed 搜标题核对真伪。⚠️ Windows 下 edirect 检索工具常静默失效，此时 AI 可能凭知识库"回忆"出看似真实实则编造的文献或 DOI。**检索工具不可用时 AI 必须明确告知用户，绝不许假装查过或就地编 DOI**。

### Phase 4: 章节专用写作模板

写各章节前 `Read references/writing-templates.md` 取对应模板：
- **Introduction**：宽→窄→缺口→我们 五层漏斗结构。
- **Methods**：可重复性硬要求（试剂货号 / 抗体 RRID / 细胞系 STR+支原体 / 动物 IACUC / 组学 accession / 临床 IRB / 软件版本+种子 / 精确参数 / 统计独立声明）。
- **Discussion**：主要发现→文献对比+机制→Limitations（强制）→Outlook 四段式。
- **Online Methods vs STAR Methods**：按 target_journal 选模板。
- **Figure Prompt**：为需 AI 绘制的示意图生成结构化提示词。

