> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

# Quality Gates：阻断条件、gate-check 命令、反例黑名单、失败处置手册、已知限制

Block progression when any of the following fails:
- ERROR-level consistency rules.
- Unverified references in P1 citation set.
- Citation-index-reference matrix mismatch.
- Any D-grade in global review dimensions.
- More than 3 C-grade dimensions in global review.
- Page estimate beyond configured hard limit.

Use atomic gate command for final checks:
- `python scripts/state_manager.py --root . gate-check --sections-dir sections --index data/literature_index.json --p1 sections/P1_立项依据.md --ref sections/REF_参考文献.md --mcp-cache data/mcp_literature_cache.json --mcp-ttl-days 30 --require-mcp`

### ❌ 反例黑名单（Anti-Patterns，门控人读版总览）

- ❌ 把「科学问题属性」当成「研究属性」填，或四类官方措辞（鼓励探索·突出原创／聚焦前沿·独辟蹊径／需求牵引·突破瓶颈／共性导向·交叉融通）未在 Phase 0 选定写入 profile，会触发 gate-check `failed_at=profile` 阻断。
- ❌ 跳过 Mode Handshake，未确认 Write Mode 或 Polish Mode 就直接开写、做诊断或跑文献核验。
- ❌ H/O/RC/KSQ 不做严格 1:1 对应，出现交叉映射、数量不等或某个 SQ 没有对应的 H 与 KSQ（违反 V-01／V-02）。
- ❌ 把研究目标写成问题、把关键科学问题写成动作，混淆“做什么”（O）与“回答什么”（KSQ）。
- ❌ 创新点写成空话（“首次系统研究”“开创性”“革命性”），不追溯到具体 RC 和 M，无技术／方法／理论突破的实证（违反 V-05／FC-05）。
- ❌ 给每个 M 留空 alternative_plan，或备选方案只写“调整参数”而无触发条件／替代方案／切换代价（违反 V-12，阻断 Phase 3）。
- ❌ 可行性靠自夸撑场，每个方法 M 找不到来自 P3_1／P3_2 的可行性证据 F，预实验或代表作与 H/RC 方向对不上（违反 V-06／V-11）。
- ❌ 虚构或不核验引用，PMID／DOI／标题不反查、跳过撤稿检查，或带着 `verified=false` 的文献进入 Phase 2。
- ❌ 用 tavily、websearch、openalex／pyalex、webfetch 等通用工具检索文献证据，而非 PubMed CLI 或 paper-search MCP。
- ❌ 并行发起检索请求，未串行执行、未保证连续调用间隔 ≥1 秒。
- ❌ 在 P2 研究内容里使用文献编号引用 [n]，或把编号引用用在 P1 之外的部分。
- ❌ 正文用项目符号或编号列表展开论述，而非段落式叙事（年度计划、P2 的 2.1／2.2／2.4／2.5／2.7 分项、P3_3／P3_4 清单、预算三线表是仅有的例外）。
- ❌ 关键科学问题、2.6 年度研究计划、2.7 预期成果不按 `references/workflow-p0-p2.md` 的 Phase 2 P2 子结构真源一节的写法与格式写。
- ❌ 国自然项目的研究假说没写在 P1 末段，或 P2 里仍单设研究假说节（选保留旧结构的项目除外）。
- ❌ 使用禁用句式与修辞：“不是…而是…”“不仅…而且…”“值得注意的是”“至关重要”“综上所述”、排比、比喻、反问、夸张。
- ❌ 留下装饰性破折号、scare quotes、解释性冒号，或定语从句嵌套超 2 层（humanizer_zh 报 ERROR）。中文单句超 50 字为 `rhythm-check` 软提醒（机制类严密长句已豁免、不阻断），非机制类单句超 50 字须拆分。
- ❌ 超篇幅：正文 >30 页、中文摘要 >400 字、英文摘要 >300 词、P4 或 P3_4 >500 字（上限以 `word_counter.py check` 输出为准；非国自然模板按结构真源 `word_max` / `page_limit` 声明）。
- ❌ 在任一 Phase 不跑委托盲检（或降级独立重核），主 agent 写完就自评打勾、verify 未 exit 0 就声明完成或执行 merge。

Failure handling playbook:
- `failed_at=profile`: 科学问题属性未选定或取值非四类官方措辞之一。回到 Phase 0 与用户确认四选一，写入 profile `science_problem_attribute`（`python scripts/state_manager.py --root . profile --json '{"science_problem_attribute":"聚焦前沿、独辟蹊径"}'`），再 re-run `gate-check`。
- `failed_at=sync`: run `sync-all --auto-fix`, then re-run `gate-check`.
- `failed_at=citation`: repair index/cache, re-run `verify-all --require-mcp`, then `gate-check`.
- `failed_at=literature_total`: 文献总量硬门未过（`literature_index.metadata.total_count` < `citation_targets.min_total`，默认30）。补充检索录入到 ≥30 篇，再 re-run `gate-check`。近5年≥20、中文≥5、P1段引用≥20为软 warn，见报告 `literature.warnings`，不阻断但建议补足。
- `failed_at=matrix`: run `matrix-check` and `reorder`, then `gate-check`.
- `failed_at=review`: fix D/C dimensions from review report, then `gate-check`.
- `failed_at=literature_index`: 文献索引损坏——`entries` 里混入了非对象元素（字符串/列表/null 等），报告的 `literature_index.error` 会点名是第几条（0 基下标）、什么类型。**按点名的下标人工修好 `data/literature_index.json` 里那些条目**（补成完整对象或整条删掉），索引文件门禁没有动过、也不要指望 `sync-all --auto-fix`（它只修容器类型不清洗元素，不会替你删文献）。修完 re-run `gate-check`。

**Dual-Track Citation Verification:** Provide MCP retrieval cache in `data/mcp_literature_cache.json` and run online validation without `--offline` whenever network is available. Final gate must enforce `--require-mcp`.

**已知限制（非国自然项目的结构指纹保护是空白，本轮不补）**：结构签字门禁（`structure_signoff_gate`）的"大纲变了要重签"保护，靠 `data/consistency_map.json` 与 `data/experimental_design.json` 里的实体表建指纹。非国自然项目（`funding_scheme: "other"`）通常不建这两份文件——两份都不是 dict 时指纹为 None，签字落成 `outline_bound: false`，此后**改结构不会触发重签要求**。这不是旧保护的丢失：改造前非国自然项目根本走不到签字（被科学问题属性卡死在 Phase 7 之前），这是新场景带来的空白。不补的原因：补它要把 `structure_profile.json` 纳入指纹投影，会让已签字的国自然项目被要求重签（红线禁止），且 `structure_signoff_gate.py` 在门禁写保护清单里。将来要补需单独授权的第 3 期工作（投影加"仅当签字时该文件已存在才计入"的条件迁移 + 用户亲手开门禁豁免），建议等真有人拿省基金本子跑完一轮再说。

**已知限制（诊断提示在本技能里看不到，但请求照打）**：在线核验（不加 `--offline`，即默认）时，对每条没验过、带 DOI/PMID、标题≥3 个词的文献，底层核验会额外拿标题上网回查一次，本可给出「这条的 DOI/PMID 可能填错了，线上同名文章是这个」之类的提示；但 `citation_validator.py` 的 `verification_details` 只保留固定字段，这些提示会被直接丢掉——**请求照打、结果照扔**，白花一次网络往返和限流额度。**判定结果完全不受影响**（verified / 撤稿 / 硬失败一条都不会变），只是文献多时 `verify-all` 会慢一些。所以验不过的条目直接看 `verification_details.failure_reasons` 排查，别等诊断提示；网络紧张时可先 `--offline` 跑一遍粗筛（但终审 gate 仍须在线 + `--require-mcp`）。

