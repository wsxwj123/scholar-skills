# Changelog - General SCI Writing Skill

## [2.20.0] - 2026-06-11

### 🔒 写作前"读 references"硬门禁（闭环 progressive disclosure 风险）
- `write-cycle --section` 预加载时按 section 类型列出**必读 references 清单**（anti-ai-protocol 通用；results/discussion 加 figure_analysis + writing-templates + citation-policy；methods/intro 加 writing-templates）。
- `write-cycle --finalize` 新增**强制 `--refs-confirmed` 声明**：缺失则 `exit 2` 阻断落盘（`error: refs_not_confirmed`），把"忘记读 references、凭记忆写作"从软约束变成硬门禁。
- SKILL.md / README / QUICK_REFERENCE 所有 `--finalize` 示例同步加 `--refs-confirmed`；P0#10 补门禁说明。
- 新增 `required_refs_for_section()` + `state_manager.py` write-cycle 的 `confirm_refs` 参数。
- **鲁棒性补洞**：`required_refs_for_section()` 对**非标准 section 命名**（如 `uptake`/`characterization`，不含 results/methods 字样）采用"宁多勿漏"——识别不出类型即给全正文 refs，避免门禁因命名退化成只读 anti-ai 而失效。
- **诚实边界**：脚本强制 AI **显式声明**已读，但无法验证它是否真读了内容——挡得住"忘记"，挡不住"故意绕过"。这是文本指令转代码门禁能到达的上限。

## [2.19.0] - 2026-06-11

### 🧹 SKILL.md 结构重构（提升 AI 遵守率）
- **Progressive disclosure**：将 anti-AI 协议、文献政策、统计决策树、投稿指南、章节写作模板、识图模板 6 块参考资料从 SKILL.md 外移到新建的 `references/` 子目录，SKILL.md 各阶段改为按需 `Read` 指针。再原地精简 §11 强制交互结构（33→6 行）与 §1 路径初始化。常驻上下文从 86.8K 字符（914 行）降至 65.1K（692 行，**-25%**）。
- **Phase 编号线性化**：原混乱编号（3.5/3.55/3.6/3.7/4.5/4.8/4.9/5/6.6）重排为连续整数 `Phase 0–16`，消除"Phase 5 物理排在 Phase 4.8 之前"的错位；所有交叉引用同步更新。
- **P0 红线分层**：开头新增「🔴 P0 红线」区（10 条违反即报废级规则）+「📁 references/ 参考文件地图」索引表，建立指令优先级层次。指令通胀词频下降（必须 108→89，严禁 49→42）。
- **清理开发痕迹**：删除正文中 11 处 `Bug X 修复` 内部标记与版本号区的内联 changelog（变更历史统一归口本文件）。

## [2.16.2] - 2026-03-07

### 📚 Protocol and Document Sync
- Clarified the response protocol: Part 1 and Part 3 remain mandatory in user-visible replies, while the Status Dashboard is maintained internally by default and rendered only on explicit audit/log requests.
- Updated `QUICK_REFERENCE.md`, `README.md`, `USAGE_GUIDE.md`, `TEST_CHECKLIST.md`, and `RUNTIME_LAYOUT.md` so documentation matches the current runtime behavior.
- Normalized source-file references in runtime docs (`SKILL.md`, `scripts/config_manager.py`, `configs/*.json`) to remove stale path/case drift.

## [2.16.1] - 2026-03-07

### 🔒 Citation Verification Hardening
- `scripts/citation_guard.py` now enforces provider family policy: only `paper-search` and restricted `tavily` entries are accepted.
- Tavily entries carrying DOI/PMID are blocked; Tavily no-identifier entries are routed to `manual_review_queue.json` and remain unverified.
- Bidirectional verification failures (`title_mismatch`, DOI/PMID mismatch, `id_mismatch`) now force `verified=false` and append an explicit manual-confirmation reason.
- `citation_guard_report.json` now records provider policy details for auditability.
- Added regression tests covering provider allowlist, Tavily restrictions, manual review routing, and bidirectional verification failure handling.

## [2.15.2] - 2026-02-12

### ✅ Reliability Hardening
- `write-cycle` is now strict-preflight by default; use `--preflight-lenient` only for debugging.
- `sync-literature --apply` now blocks by default when `dedup_conflicts` is detected.
- Added explicit override `--allow-conflicts` for manual, reviewed exceptions.
- Added bounded retention for runtime artifacts:
  - `.state/reports/` report files are capped.
  - `.state/load_cache.json` cache entries are capped.
- Fixed cache invalidation precision by switching file signature to nanosecond mtime.
- Added regression tests for nature reference style, conflict blocking, cache invalidation, and strict-default write-cycle.


## [2.15.1] - 2026-02-11

### 🔧 同步自动化与文献一致性修复

#### 核心变更
- **Postwrite Automation (回复后自动同步)**:
  - `state_manager.py` 新增 `postwrite` 强化参数，支持一条命令同步全局进度与记忆（`writing_progress` + `context_memory`）。
- **Literature Dedup + Renumber Sync (文献去重与编号同步)**:
  - 新增 `sync-literature` 命令，按 DOI → PMID → 元数据键 → 精确标题 → 模糊标题 五层策略自动去重 `literature_index.json`，重复项元数据合并而非丢弃。
  - 去重后自动重写 `manuscripts/*.md` 中的 `[n]` 引用编号，避免正文与索引错位。
- **Global/Section Load De-duplication (加载去重)**:
  - `global_history` 收敛为核心全局状态，避免与 section 级索引重复加载。

## [2.15.0] - 2026-02-11

### 🧠 记忆与Token控制升级

#### 核心变更
- **Section-Local Context Protocol (章节级上下文隔离)**:
  - `/write [section]` 仅允许加载该章节相关上下文，默认拒绝跨章节正文读取。
  - 新增章节白名单载入理念：仅项目配置、章节提纲、章节图数据、章节文献、当前章节草稿、章节记忆。
- **Dual Memory Model (双层记忆模型)**:
  - 引入 `section_memory/<section_id>.md` 作为章节记忆层，与全局 `context_memory.md` 分离。
  - 明确全局记忆仅保存决策与约束，章节细节沉淀到 section 级文件，降低“串章”风险。
- **Token Budget Guard (预算熔断器)**:
  - `state_manager.py` 的加载流程新增 token 预算估算与自动降载机制。
  - 超预算时按优先级自动裁剪：先压缩正文与章节记忆，再压缩文献/图数据，避免上下文爆炸。
- **Scoped Loading CLI (作用域加载命令扩展)**:
  - `load` 命令支持 `--section`、`--token-budget`、`--tail-lines`，用于章节定向加载与预算控制。
  - 输出中新增 `loaded_files` 与 `budget_report`，可用于验证“只读当前章节”是否生效。

## [2.14.0] - 2026-01-30

### 📏 严谨性与完整性升级

#### 核心变更
- **Point-by-Point Response Protocol (逐条致密回复协议)**:
  - 将 "逐条致密回复" 列为最高优先级的系统执行红线 (Final Enforcement #6)。
  - 强制 AI 必须细致回答用户的所有问题，严禁忽略或简略回答，确保学术交流的深度与完整性。
- **Figure Caption Generation (图注生成协议)**:
  - Phase 4 写作流程新增 "Figure Caption Generation" 步骤。
  - 强制在每小节末尾生成 Figure Legends，并包含具体的统计信息 (n=X) 和显微标尺 (scale bar = X μm)。

## [2.13.0] - 2026-01-30

### 🔄 SI 持久化与主动管理

#### 核心变更
- **SI Persistence Protocol**: 引入 `si_database.json` 作为新的核心状态文件，强制记录所有在对话中确认的 Supplementary Information。
- **Auto-Persistence**: `state_manager.py` 脚本升级，支持自动加载和保存 `si_database.json`。
- **Proactive Query Loop**: 在 Phase 4 (Writing) 的 SI 建议环节，增加了对 `si_database.json` 的检查步骤。若发现缺失证据且数据库为空，必须主动询问用户并立即保存反馈。
- **Strict Enforcement**: 将 "SI Must Be Persisted" 列为最高优先级的系统执行红线，严禁仅在 Memory 中提及 SI。

## [2.11.0] - 2026-01-30

### 🛡️ 检索健壮性升级

#### 核心变更
- **Abstract Recovery Protocol (摘要补全协议)**: 针对检索结果中摘要缺失的情况，建立了强制性的三级回退机制。
  - **Mandatory Chain**: Google Scholar (Primary) > Semantic Scholar > Tavily。
  - **Strict Policy**: 严禁因摘要缺失直接丢弃相关性高的文献，必须跑完上述补全流程。仅当所有工具失效时才允许标记为 Missing。

## [2.10.0] - 2026-01-30

### 🤖 自动化与输出净化

#### 核心变更
- **State Manager Automation**: 引入 `scripts/state_manager.py`，实现跨平台、标准化的状态加载与原子化更新，彻底告别手动读写多个状态文件的繁琐。
- **Clean Output Protocol**: 强制 `[Context Check]` 块仅作为内部验证日志，**严禁**出现在用户最终回复中，提供沉浸式的无干扰交互体验。
- **Version Compatibility**: 脚本内置 `context_memory.md` 的版本轮转逻辑 (v-1, v-2)，确保历史回溯功能的稳定性。

## [2.9.0] - 2024-01-30

### 📏 引用规范与上下文强化

#### 核心变更
- **Strict Citation Format**: 强制正文引用使用 `[n]` 格式，严禁其他变体。在每个小节末尾自动附上该节引用的参考文献列表（Vancouver style）。
- **Mandatory Context Read**: 强化了上下文检查协议，明确要求在每次回复前读取所有 5 个核心文件（含 `writing_progress.json`）。
- **Final Enforcement**: 将引用格式规则加入到最高优先级的系统执行指令中。

---

## [2.8.0] - 2024-01-30

### 🔄 全局状态持久化 (Continuity Upgrade)

#### 核心变更
- **Global Context Persistence**: 强制在**每次回复结束前**自动更新 `context_memory.md`。无论是在进行问答、头脑风暴还是写作，当前的对话状态、决策和待办事项都会被实时保存。
- **Auto-Snapshot Logic**: 智能快照现在会监控 `context_memory.md` 的实质性变更，确保在对话中断后能无缝恢复到最新状态。

---

## [2.7.0] - 2024-01-29

### 🚫 去除 AI 味关键升级

#### 核心变更
- **NO BULLET POINTS POLICY (段落式写作强制令)**:
  - 明确禁止在正文（Abstract, Intro, Results, Discussion）中使用列点符号。
  - 强制要求使用逻辑连接词（Furthermore, Consequently）将观点串联成连贯段落，模拟真人科学家的写作习惯。
- **Final System Enforcement**:
  - 在 Skill 末尾增加了最高优先级的执行指令，再次强调"强制交互版块"（反向拷问/你可能想知道）和"禁止列点"规则，防止 LLM 在长上下文中遗忘。

---

## [2.6.0] - 2024-01-29

### 💬 交互深度恢复

#### 核心变更
- **强制交互版块恢复**: 在 v2.x 迭代中遗漏的 "反向拷问" 和 "你可能想知道" 版块已重新实装为强制输出协议。
- **Reverse Interrogation**: 每次回复都必须挑战用户的假设或指出盲点。
- **Proactive Suggestions**: 每次回复都必须预测用户的下一步需求。

---

## [2.5.0] - 2024-01-29

### 🛡️ 逻辑完整性升级 (SI重构)

#### 核心变更
- **SI 认知重构**: 明确定义 SI 为 "Integral Evidence Chain" (完整证据链) 而非单纯的防御工具。Main Text 展示"结果与意义"，SI 展示"确信度与过程细节"。
- **Context-Aware SI 建议**: 废除机械的药剂学套路提问。AI 必须基于当前小节的具体逻辑断点（Logical Gap），主动分析缺失的中间证据（如阴性对照、优化过程、方法验证），并据此提出精准的 SI 建议。

---

## [2.4.0] - 2024-01-29

### 🛡️ 逻辑完整性升级

#### 核心变更
- **SI 主动建议与整合回路 (SI Proactive Loop)**:
  - 在撰写 Results 小节时，AI 不再是一次性输出。
  - **Reflect**: 完成初稿后，AI 必须基于药剂学专业知识，主动反思"需要什么补充证据？"（如处方筛选、稳定性、阴性对照）。
  - **Propose**: 向用户建议具体的 SI 列表。
  - **Integrate**: 获得用户反馈后，自动重写该小节，将 SI 引用（如 `Figure S1`）自然融入论证逻辑，形成最终版。

---

## [2.3.0] - 2024-01-29

### 🛡️ 逻辑熔断与检索优化

#### 核心变更
- **数据依赖熔断 (Hard Stop)**: 在撰写 Results/Discussion 章节前，强制检查 Figure 数据的完整性。若数据状态为 `pending`，AI 必须立即停止并请求数据，严禁编造或使用占位符。
- **文献检索优先级调整**:
  - **Primary**: PubMed (医学/药剂学首选)
  - **Secondary**: Semantic Scholar (速度/广度) + bioRxiv (预印本)
  - **Fallback**: Google Scholar (仅作补充)
  - **Forbidden**: Tavily (禁止用于学术检索)

---

## [2.2.0] - 2024-01-29

### 🛡️ 安全与规范升级

#### 核心变更
- **原子化文件管理**: 强制执行"一小节一文件"策略（如 `04_Results_3.1_Characterization.md`），彻底解决大文件覆盖导致的数据丢失问题。
- **写入安全协议**: 在执行 `write_file` 前必须先读取旧文件比对差异，若存在覆盖风险，自动创建 `.bak` 备份。
- **严格工具纪律**: 明确锁定文献检索工具优先级。
  - **Primary**: `paper-search` (PubMed/Scholar), `arxiv` (Preprints).
  - **Forbidden**: 禁止使用 `tavily` 检索学术引用（仅限宽泛概念查询）。

---

## [2.1.0] - 2024-01-28

### 🎉 核心升级

#### 生态兼容
- **BibTeX 导出**: 新增 `/export_bib` 命令，支持将 `literature_index.json` 导出为 `references.bib`，方便导入 Zotero/EndNote。
- **本地脚本实装**: 提供了 `scripts/export_bibtex.py` 和 `scripts/merge_manuscript.py`，支持脱离对话环境的自动化操作。

#### 写作质量
- **自我修正回路**: 在 `/write` 命令中植入 "Draft -> Critique -> Polish" 隐式思维链。AI 在输出前必须进行自我反思和润色，确保语言简练且逻辑严密。

---

## [2.0.0] - 2024-01-28

### 🔥 重大重构

#### 核心逻辑
- **Results & Discussion 融合**: 废弃独立 Discussion 章节。采用"数据呈现 -> 即时讨论 (机制/对比/意义)"的融合写作模式。
- **智能快照系统**: AI 主动判断快照时机（生成内容/关键决策/新数据），而非僵化触发。
- **上下文显式验证**: 强制检查并汇报历史文件（Storyline, Literature, Figures）的读取状态，杜绝幻觉。
- **弹性写作深度**: 引入 "Key Section" vs "Supporting Section" 概念。核心论点强制深度展开 (>200词)，次要数据简洁陈述。

#### 文件变更
- 更新 `storyline.json` 结构以支持融合章节。
- 重写 `skill.md` 以反映新的交互协议。

---

## [1.0.0] - 2024-01-27

### 🎉 初始发布

#### 核心功能
- ✅ 完整的Nature级SCI论文写作工作流
- ✅ 8个阶段的写作流程
- ✅ 12个全局命令系统
- ✅ 持久化记忆系统（3版本context_memory）
- ✅ 完整备份的版本控制
- ✅ 分阶段文献检索
- ✅ 审稿人视角模拟
- ✅ 质量控制系统
