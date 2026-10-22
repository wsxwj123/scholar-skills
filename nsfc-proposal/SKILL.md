---
name: nsfc-proposal
version: 2.39.0
description: 用于国家自然科学基金申请书（2026 版模板）的撰写、结构重组与润色。提供两种工作模式：写作模式从零分阶段构建，润色模式导入既有稿件后先行诊断再逐节修订。技能执行逐节签字门禁，强制维持科学假说、研究目标、研究内容与关键科学问题四者的一致性，通过 paper-search MCP 核验文献真实性，并施加反 AI 腔的中文学术写作约束。字数与页数上限以脚本核算结果为准。触发词：国自然、国家自然科学基金、基金申请书、科研申请、NSFC、标书、本子、面上项目、青年基金。
---

# NSFC Proposal Skill

## Overview
This skill covers NSFC proposal writing and polishing from start to finish under the 2026 template. It gates each section, keeps the sections consistent with one another, verifies the literature, and keeps the academic Chinese restrained.

Use two modes:
- Write Mode: build from zero in phased gates.
- Polish Mode: import an existing draft, diagnose first, then revise section by section.

**【Python 解释器探测：启动前置，一次探测全程沿用】** 本文档中的 `python3` / `python` 仅为 macOS/Linux 的习惯写法，并非硬性要求。启动前执行一次 `python3 --version`：
- 输出正常版本号 → 本次会话所有命令统一使用 `python3`。
- 报 command not found、无任何输出、或弹出应用商店 → 改为执行 `python --version`，能输出版本号则将后续所有命令中的解释器统一替换为 `python`。注意 Windows 自带一个 0 字节的 `python3` 占位程序，`python3 --version` 弹出商店或无输出即表示命中该占位程序，**不视为已安装 python3**，按"未安装"处理（用户也可在 设置 → 应用 → 应用执行别名 中关闭 `python3.exe`）。
- 反之 `python` 无法输出版本号则改用 `python3`（macOS 12.3 起系统不再预装 `python`）。
- 两者均无法输出版本号，表明该机器未安装 Python，须停止并告知用户先行安装，不得强行执行。
- 探测仅执行一次，后续所有命令沿用同一解释器名称，无需每条命令重复探测。

## 跨会话接续（每次进入/续写必做，Mandatory）
每次进入本技能或续写已有项目时，**须先执行 Phase 0 env_preflight 输出的 `RESUME_CMD`**（`python "<本技能>/scripts/session_journal.py" resume --root <project_root>`），将接续报告完整呈现给用户，按报告末尾的确认话术与用户对齐进度，等待确认后方可继续。用户**中途提出任何临时要求，须立即通过 `JOURNAL_LOG_CMD`**（`<本技能>/scripts/session_journal.py log --root <R> --note "<原话>"`）追加至 `decisions_log.md`，后续会话开局的 resume 会重新读出、必须遵守。新项目（无 state）resume 会提示未初始化，照常走 Phase 0。

## Mode Handshake Gate (Mandatory)
Before any drafting/revision action, the assistant must ask exactly one mode-selection question and wait for the user answer:
- `Write Mode` (from scratch)
- `Polish Mode` (revise existing draft)

Hard rules:
- If mode is not explicitly confirmed, do not run section writing, diagnosis, citation verification, or merge commands.
- First actionable response in this skill must be the mode-selection question when mode is missing.
- If the user already explicitly states `Write Mode` or `Polish Mode` in the opening message, do not ask again; proceed directly with the specified mode.
- After user confirms mode, record it in project state/profile and continue with that mode workflow only.

## 开场监工卡（每次启动必打印，Mandatory；国自然 / 其他基金通用）
确认 Mode 后、生成章节结构前，须将下方监工卡原样输出给用户（此为面向非专家的 AI 风险提示清单，每次启动均须输出，不得省略）：

> **【开场监工卡 · 国自然标书 / 其他基金】以下各项为 AI 最易出错的环节：**
> 1. **立意、创新与可行性是中标核心，也是 AI 最易空泛填充的部分**。脚本仅核查字数与条目数，无法判断内容是否有实质。这三部分的每一句均须用户亲自审阅，发现空泛内容应退回修改，不应仅凭"看上去专业"而通过。
> 2. **诊断引擎报告的字数、条目数与通过项仅代表"格式合规"，不代表"内容过关"**。门禁通过不等于能中标，不应将指标达标等同于写作质量。
> 3. **引用须用户亲自抽验**：随机选取数条文献，要求 AI 报出 PMID / DOI，自行前往 PubMed / 期刊官网核对（防止杜撰文献或引用已撤稿论文）。
> 4. **每写完一章须暂停等待用户确认**后再继续；若 AI 未停顿而连续撰写多章，应立即中断，此属流程跳步。
> 5. **"研究假说 → 研究目标 → 研究内容 → 关键科学问题"链条须保持对齐**，AI 会以表格形式逐条呈现，用户须检查是否存在脱节或断链。
> 6. **科学问题与章节结构须经用户确认后方可开写正文**，此项有硬门禁强制执行（见"结构签字落锁"），非依赖 AI 自律。
> 7. **默认按国自然 2026 模板执行**。若需撰写省基金、校基金、企业课题或其他基金/自定义模板，**请在此时说明**。AI 会先读取模板进行结构提取，将章节结构逐条呈现供核对，后续的章节顺序与字数上限均按用户模板执行。未说明则按国自然结构及「科学问题属性四选一」要求执行。

## 基金归属确认（Mandatory，仅全新项目问一次）
打完上面那张卡后，先做基金归属判定。两个条件**同时**成立才问，缺一不问：项目根**不存在** `project_state.json`，且项目根**不存在** `structure_profile.json`（文件在但内容坏了也算"有"，交由结构真源三态处理去报，不许退化成重新问一遍）。满足则问一次，二选一：
- **A. 国自然 2026（默认）** → **不建任何文件**。契约不变：「无 `structure_profile.json` = 国自然默认，行为一个字不变」。
- **B. 其他基金 / 自定义模板** → 请用户给模板文件路径，走下方 Phase 0「模板结构提取」的五步链，最后由 `structure_profile.py confirm` 落盘 `funding_scheme: "other"`。

不问的三种情况：任一判据文件已存在（老项目续写，按已有真源走）；用户在开场消息里已明说基金类型（如「我写省自然」「国自然面上」——口径同上方 Mode 已明说就不再问）；同一会话内已经问过。
⚠️ 已知天花板（如实登记）：答 A 故意不落任何文件，所以只承诺**同一会话内**问过不再问；用户答完 A 就中断、没走到 `state_manager init` 的，下次新会话两个判据文件仍都不存在，会再问一次——这是接受的代价，不为它新造"AI 自己写结构真源"的落点。

## Core Terminology
SQ is the upstream root; H/O/RC/KSQ form the 1:1 consistency backbone derived from it.

| Symbol | Chinese | Role | Example |
|--------|---------|------|---------|
| SQ | 科学问题 (Scientific Question) | Field-level open problem distilled in P1; root for H and KSQ (not part of the 1:1 chain). SQ 不持有下行映射字段，关联由 H/KSQ 的 `mapped_from_sq` 反向建立 | "XXX的分子机制尚不清楚" |
| H | 假说 (Hypothesis) | Causal claim derived from SQ | "A蛋白通过B通路调控C过程" |
| O | 目标 (Objective) | What you **do** (action-oriented) | "阐明XXX的机制" |
| RC | 研究内容 (Research Content) | Specific investigation; links to methods | "通过ChIP-seq分析A蛋白的结合位点" |
| KSQ | 关键科学问题 (Key Scientific Question) | What you **answer** (question-oriented), distilled from SQ | "XXX如何调控YYY？" |

Mapping constraint: H-n ↔ O-n ↔ RC-n ↔ KSQ-n (strict one-to-one, no cross-linking allowed).
SQ vs KSQ: SQ is the broad open problem stated in P1; KSQ is the focused, answerable question distilled from SQ and bound 1:1 to its H/O/RC. One SQ may seed one or more KSQ; each SQ must trace to ≥1 H and ≥1 KSQ (rule V-01).

**If user asks a conceptual question about any of H/O/RC/KSQ/SQ/mapping:** load `references/02_核心机制.md` and answer from it before continuing with workflow phases.

## Inputs Required
Collect before execution:
- Project basics: title, discipline code, project type, research attribute, duration, budget.
- 🔴 **科学问题属性（四选一，仅国自然项目强制）**：与"研究属性"是两个独立必填字段。研究属性=分类评审的「自由探索类/目标导向类」；科学问题属性=申请书独立必填项，四类官方标准措辞如下，Phase 0 必须选定其一并写入 profile 的 `science_problem_attribute`。**适用范围**：没有结构真源（项目根无 `structure_profile.json`）或真源未声明非国自然时，本项必填；真源声明 `"funding_scheme": "other"`（非国自然）后本项不再必填——gate-check 不再因它阻断（SPA-REQUIRED 关闭），并记入报告的「未执行的检查」（见 references/07）：
  - 鼓励探索、突出原创
  - 聚焦前沿、独辟蹊径
  - 需求牵引、突破瓶颈
  - 共性导向、交叉融通
- Existing materials: draft files, prior work, platform/conditions, related projects.
- User constraints: word targets per section, preferred P2 sub-structure, H/O/RC/KSQ mapping count.

### 2026模板硬约束速查表
| 项目 | 硬限 |
|------|------|
| 正文总页数 | ≤30页（约18000-25000字），页数估算替代字数硬门控 |
| 中文摘要 | ≤400汉字 |
| 英文摘要 | ≤300英文词 |
| P4 其他需要说明的情况 | ≤500字 |
| P3_4 完成基金项目情况总结 | ≤500字 |
| 研究属性（分类评审） | 必选「自由探索类」或「目标导向类」二选一 |
| 科学问题属性（独立必填，≠研究属性；**仅国自然**） | 四选一：鼓励探索·突出原创 / 聚焦前沿·独辟蹊径 / 需求牵引·突破瓶颈 / 共性导向·交叉融通；Phase 0 未选定则 gate-check 阻断（`failed_at=profile`）。结构真源声明 `funding_scheme: "other"` 后不再必填、不再阻断（进「未执行的检查」） |
| 伦理审查（涉人类受试者/实验动物/生物安全/人类遗传资源时） | 须在可行性分析中说明伦理审查批件或送审计划 |

> 字数/页数硬限以 `python scripts/word_counter.py check` 输出为准（单一真源：`scripts/word_counter.py` 顶部 `NSFC_WORD_MAX` / `NSFC_PAGE_MAX`）；非国自然模板按 `structure_profile.chapters[].word_max` 与 `proposal_profile.json` 的 `page_limit` 声明取值。

## Tooling Rules
Academic literature retrieval follows topic-dependent routing (Mandatory):

1. **Determine field type first:**
   - Life science / Medicine / Clinical / Biochemistry / Pharmacology → **PubMed CLI first**
   - CS / AI / Engineering / Physics / Interdisciplinary → **paper-search MCP first** (arXiv/Google Scholar)

2. **PubMed CLI** (life science primary): Use `esearch`/`efetch`/`einfo` (path `~/edirect/`). Must append `< /dev/null`, use proxy `http_proxy=http://127.0.0.1:<PROXY_PORT>`.
   Example: `export http_proxy=http://127.0.0.1:<PROXY_PORT> && esearch -db pubmed -query "xxx" < /dev/null | efetch -format abstract`
   Auto-install if `~/edirect/esearch` missing: `sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"`
   **Windows:** edirect does not run in PowerShell/CMD. Use WSL bash, or fall back to paper-search MCP.

3. **paper-search MCP** (CS/AI primary / preprints / fallback when PubMed yields no results):
   Tool names: `mcp__paper-search-mcp__search_pubmed`, `mcp__paper-search-mcp__search_arxiv`, `mcp__paper-search-mcp__search_biorxiv`, `mcp__paper-search-mcp__search_medrxiv`

Do not use generic web search/fetch tools for citation evidence in proposal claims.
**严禁** 使用 `tavily`、`websearch` 或 `openalex`（pyalex），无论有无 DOI/PMID. 该禁令已脚本级强制：literature_index 条目的 `search_source` 字段若属上述被禁家族，`citation_validator.py` 触发 `source_provider_forbidden` 硬失败，与 DOI/PMID/标题核验同级阻断门禁。
**Serial Search (MANDATORY):** Execute all retrieval calls sequentially (including both PubMed CLI and paper-search MCP). Never parallelize search requests. Enforce ≥1s interval between consecutive calls.

> **Windows note:** all `python3 scripts/...` commands below use `python` or `py` instead of `python3` on Windows.

## Non-Conflict Canon (Conflict Resolution Rules)
> These rules resolve specific contradictions discovered during operation. When any instruction in SKILL.md or its references conflicts with a rule here, this section takes precedence.

Apply these resolutions when references conflict:
1. No-bullet narrative applies to proposal body sections only; diagnostics/review reports may use structured lists.
2. Interaction extras (reverse questioning, suggested follow-up questions, extended thinking) are optional by context, not mandatory on every response.
3. Merge order is fixed: references at the end of final merged manuscript.
4. P2 should not include numbered literature markers; citation numbering is restricted to P1.

(V-01 validation implementation note: SQ nodes carry no `mapped_to_h` field. Moved to `references/02_核心机制.md` §2.3.)

*Source: accumulated from operation feedback; last reviewed 2026-05.*

## Execution Workflow

### Write Mode
完整的分阶段门禁文本已外置：Phase 0 / 0.5 / 1 / 2 在 `references/workflow-p0-p2.md`，Phase 3–7 与 DoD 停在 `references/workflow-p3-p7.md`（`references/05_Write_Mode流程.md` 是设计层流程总览，两者并存、不互相替代）。**进入任一 Phase 前，先 Read 对应文件的该 Phase 小节。** 骨架如下：

1. **Phase 0**：`env_preflight.py`（软门禁，`PRECHECK: OK|ASK|BLOCKED`）→ `git_checkpoint.py init`（此后每个 Phase verify 通过即 commit）→ 选定「科学问题属性」四选一写入 profile（仅国自然）→ 非国自然模板走 `structure_profile.py` 五步链（`extract-text` → AI 读投影写 `tmp/structure_draft.json` → `verify` 逐字节核验 → 用户逐条确认 → 落盘 `structure_profile.json`），国自然项目不建任何文件；AI 不得在用户确认前替用户落盘。
2. **Phase 0.5**：逐 RC 五字段问询（methods / preliminary_data / feasibility / alternative_plan / ethics）落 `data/experimental_design.json`，信息已充足也不得静默跳过、须回放 ✓ 列表让用户确认；Phase 0.5 DoD 五项过后，用户明确确认结构，再由用户授意运行 `SIGNOFF_CMD`（`structure_signoff_gate.py confirm`）落结构签字解锁正文。

**🔴 委托盲检总则（适用下列 Phase 1–7 每一个 DoD 闸口，Mandatory）：** 以下每个闸口一律遵守同一条铁律。每个 Phase 落盘前，DoD 清单必须委托一个独立上下文的 subagent 盲检（Claude Code 用 `academic-blind-reviewer`，其他平台派通用 subagent），不给它本稿的写作上下文；主 agent 不得自评打勾。各闸口只列本 Phase 专属的 `<gate>`/`<files>`/`<section>` 参数，套用下方三步命令模板执行；盲检的角色与纪律统一遵此总则，不再逐处复述。**降级告警**：若判到科学意义/创新/可行性等决定成败的维度，而环境派不出真正独立的 subagent，绝不能同一 AI 编一份全 pass 的盲检 JSON 冒充（那几个维度就裸奔了）。此时须告诉用户「本环境盲检不可靠，请你亲自复核」，把判断交回用户，绝不自问自答冒充盲检。

**三步命令模板（各 Phase 只改 `<gate>`/`<files>`/`<section>`，其余照抄；DoD 判据默认以 `dod_checklist.json` gate=`<gate>` 为真源，项目协商关过自检项时以第 0 步投影后的清单为准）：**
0. 选清单（条件分支，每个 Phase 盲检前先做这一步）：项目根**存在** `data/dod_selection.json`（用户在 DoD 协商中关过自检项，见 references/05 Step 0.4b）**或** `structure_profile.json`（结构真源；合法已确认 `funding_scheme: "other"` 时投影会按清单声明键减免国自绑定项、把结构完整性类判据换成按结构真源查齐，见 references/08 §2.9）任一时，先跑 `python3 scripts/dod_project.py project --root . --gate <gate> --out tmp/dod_active_<gate>.json` 产出投影清单，且第 1、3 步的 checklist 参数一律改用投影产物 `--checklist tmp/dod_active_<gate>.json`——pack 与 verify 必须同用这一份：pack 用投影、verify 仍用全量，会把被减免/被关掉的项判成「缺漏未裁决」硬卡盲检（实测 exit 1）。两份文件都不存在时跳过本步，第 1、3 步照抄下方原样命令、用全量 `references/dod_checklist.json`（国自然默认，与协商前行为一字不变）。
1. pack：`python scripts/delegate_review.py pack --checklist references/dod_checklist.json --gate <gate> --files <files>`
2. 派一个独立 subagent（Claude Code 用 `academic-blind-reviewer`，其他平台派通用 subagent），任务包原样给它、不给写作上下文，要求按任务包返回 JSON 数组。
3. verify：`python scripts/delegate_review.py verify --checklist references/dod_checklist.json --gate <gate> --return <subagent返回.json> --section <section> --root <项目根>`；退出码非 0（任一缺项/fail/无证据）= fail-closed，据证据修复后重跑，未过不得声明完成、不得进入下一 Phase/merge。verify 通过落盘 `.review_pass/<section>.json`，下一 Phase 的 `prewrite_gate.py` 跨 Phase 时硬校验它（缺失即拒绝开写）。
   - `<section>`/`--root` 仅对门控下游 prewrite 的 Phase（P1/P2/P3/P7）给出；P4/P5/P6 不 gate 下游，verify 只带 `--return`，省略 `--section`/`--root`。

3. **Phase 1（P1 立项依据）**：文献检索 → 段落级大纲 `tmp/outline_draft.json` → 用户授意运行 `outline_manager.py confirm` 落唯一真源 `data/outline.json`（AI 不得代跑、不得手写 `confirmed`/`content_hash`）→ **落盘之后**派独立子代理 `pack-prep` 做大纲级论点核证（有出入改草稿重跑 confirm）→ `prewrite_gate.py --section P1`（exit≠0 禁写）→ `write-cycle --section P1` → 备料子代理起草「观点↔证据」草案 → 主会话 `CITATION_CHECK_CMD` 核证 + 逐条 AskUserQuestion 确认 → `pack-write` → 撰写子代理盲写（引用只写 `[@key]`）→ `verify-write` → `new_refs` 先核真伪再 `merge-refs` → 落盘 `sections/P1_立项依据.md` 并 `citation_renumber.py renumber --check` 后 `--in-place`。承重论点引文核证写项目根 `claim_evidence.json`，顶层形如 `{"outline_claim_set_hash": "<抄自 .prep_task_P1.json>", "rows": [{"section": "P1", "claim_sentence": ..., "is_load_bearing": true, "ref_id": ..., "verdict": ..., "user_confirmed": true}]}`——键只能叫 `rows`、行内 `section` 只能是 `"P1"`，承重句 `contradict/unknown`/未确认即 fail-closed。收口：`<gate>`=`p1-dod`。
4. **Phase 2（P2 研究内容）**：`prewrite_gate.py --section P2`（缺 `.review_pass/P1.json` 硬拦）→ 非国自然项目先出段落级计划并经用户确认 → `write-cycle --section P2` → 主会话就地写（P2–P7 走白名单、不派备料）→ 撰写 M 前必须 Read `data/experimental_design.json` → `consistency_mapper.py validate --phase 2` → 生成 `sections/figure_prompts.md` → `<gate>`=`p2-dod`。
5. **Phase 3（P3_1–P3_4）**：各子节 `prewrite_gate.py` + `write-cycle`；每个 M 至少一条来自 P3_1/P3_2 的可行性 F；伦理审查涉及时为硬项 → `<gate>`=`p3-dod`、`<section>`=`P3_1`。
6. **Phase 4**：P4 ≤500 字 → `p4-dod`。**Phase 5**：B1–B3 + `data/budget_table.json` + `python3 scripts/budget_check.py --root .` 求和硬核对（exit 1 禁止声明完成）→ `p5-dod`。**Phase 6**：中文摘要 ≤400 汉字、英文 ≤300 词，关键词对齐 `keywords_trace` → `p6-dod`。
7. **Phase 7（全文自审与终稿）**：`diagnosis_engine.py full-review` + `consistency_mapper.py validate` + `word_counter.py summary` + `page-estimate`（>30 页裁）+ `humanizer_zh.py scan-all` → 图表交叉引用核查（第 1 层结构锚，报告式软门、交用户裁决，不许 `cat sections/*.md` 拼语料）：
     ```bash
     mkdir -p tmp && python3 scripts/section_merger.py merge --sections-dir sections --output tmp/xref_corpus.md --root .
     python3 scripts/structure_outline.py --manuscript tmp/xref_corpus.md --project-root .
     ```
   → merge 到 `output/申请书_合并.md`（顺序按内置国自然或结构真源 `chapters[].order`）→ `<gate>`=`p7-dod`，merge 前必检。

每个 Phase：snapshot → sync 状态文件 → **🔴 DoD 停**：盲检 `delegate_review verify` exit 0 后不得径直进下一 Phase，先把逐项结论（含 soft_flags）摆给用户、HALT 等用户确认；修复 3 次仍不过提示回滚到上一检查点。

### Polish Mode
六步执行清单与各命令见 `references/workflow-polish.md`，设计层完整流程见 `references/06_Polish_Mode流程.md`：**导入整稿前先 Read 前者**。骨架：0) 导入 → `extract_headings.py` 抽标题真值 → 有标题路 `split_headings.py` 机械切 / 无标题路 HALT 兜底 → Layer 1 `split_audit.py`（exit 0 才进下一层）→ Layer 2 `split_boundary` 盲检 → 用户确认拆分表 → 用户授意跑 `structure_signoff_gate.py confirm` 解锁逐节改写；2) 先出严格评审报告；3) 与用户议定逐节优先级（硬阻断，未确认不进第 4 步）；4) 按问题顺序逐节修改；5) 全局一致性修复与全文复审；6) merge。

## State and Artifacts
Maintain and sync after each section edit:
- `data/consistency_map.json`
- `data/literature_index.json`
- `data/mcp_literature_cache.json`
- `data/manual_review_queue.json`
- `context_memory.md`
- `project_state.json`
- `history_log.json`

Any missing sync blocks phase progression.

**State Corruption Fallback:** If any required state file is missing or unparseable (JSON decode error), run `python scripts/state_manager.py --root . sync-all --auto-fix` to restore defaults. (`init --repair` does not exist; `sync-all --auto-fix` is the correct repair command.) Do not proceed without valid state files.

脚本静默必填字段（`mcp_literature_cache.json` 的 `verified_at`/`checked_at`、`literature_index.json` 的 `key_finding` 与 `search_source`）及最小合规样例：**写入或修复 `data/*.json`、跑 `citation_validator.py` 前，先 Read `references/field-contracts.md`**。

## Quality Gates
阻断条件、`gate-check` 完整命令、反例黑名单（17 条）、`failed_at=*` 失败处置手册与已知限制均在 `references/quality-gates.md`：**跑 `gate-check` 前、任一 Phase 收口前、以及 gate-check 报 `failed_at` 时，先 Read 它**。

## References
Load only what is needed:
- `references/00_设计方案_总览.md`
- `references/01_目录结构与配置.md`
- `references/02_核心机制.md`
- `references/03_写作规范与反AI.md`
- `references/04_文献管理.md`
- `references/05_Write_Mode流程.md`
- `references/06_Polish_Mode流程.md`
- `references/07_自审与评审模块.md`
- `references/08_脚本清单与合并规则.md`
- `references/09_交互规范与回复模板.md`
- `references/10_Figure_Prompt规范.md`
- `references/section_writer_prompt.md`（P1 撰写子代理角色 prompt + 数据/指令隔离声明）
- `references/prep_subagent_prompt.md`（P1 承重核证备料子代理角色 prompt）

- `references/workflow-p0-p2.md` / `references/workflow-p3-p7.md` / `references/workflow-polish.md`（SKILL.md 拆出的执行门禁原文，进入对应 Phase 前 Read）
- `references/field-contracts.md`（脚本静默必填字段与样例）
- `references/quality-gates.md`（阻断条件 / 反例 / 失败处置手册）
- `references/scripts.md`（5 条核心命令 + 回归测试入口）

## Output Contract
Deliverables should include:
- section files under `sections/` (canonical filenames):
  `P1_立项依据.md`, `P2_研究内容.md`（含独立预期成果小节：论文/专利/人才培养目标），
  `P3_1_研究基础与可行性分析.md`, `P3_2_工作条件.md`, `P3_3_正在承担的相关项目.md`, `P3_4_完成基金项目情况.md`,
  `P4_其他需要说明的情况.md`,
  `B1_预算说明_直接费用.md`, `B2_预算说明_合作外拨.md`, `B3_预算说明_其他来源.md`,
  `00_摘要_中文.md`, `00_摘要_英文.md`, `REF_参考文献.md`
- updated state and data files
- review reports in `data/`
- merged manuscript in `output/` (md/docx if requested)

When reporting to user, state:
- what was changed
- which gate passed/failed
- what is blocked and exact unblock action

## Script Entry Points
5 条核心命令（init / sync-all / gate-check / merge / full-review）与回归测试入口见 `references/scripts.md`：**首次运行任一脚本前先 Read 它**；write-cycle 预算、verify-entry / matrix-check / validate-one 等完整子命令见 `references/08_脚本清单与合并规则.md`。

---

## Figure Prompt 触发规则
技术路线图 / 研究框架图的触发时机、统一色板与 RC 映射规则已并入 `references/10_Figure_Prompt规范.md` 末节：**Phase 1/2 生成任何 Figure Prompt 前先 Read 它**。

---

## 流程跳步的用户干预方法

发现 AI 跳过门禁、杜撰文献或盲检失真时，可将以下指令直接发送给 AI 以要求呈现证据：

- 「把刚才那章的 DoD 盲检重跑：真正派一个独立subagent、不给它写作上下文，跑 delegate_review verify，把返回的 JSON 原文和退出码贴我，不许你自己扮演盲检」
- 「Phase 1 所有文献逐条跑 citation_validator verify-all，把每条 verified 值和反查证据贴我，我挑 3 条去 PubMed 核」
- 「用表格把'假设-目标-研究内容-科学问题'的对齐关系摆给我」
