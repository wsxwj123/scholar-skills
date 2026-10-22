---
name: sci2doc
version: 2.32.1
description: 用于将已成稿的 SCI 论文材料转化为中文博士或硕士学位论文草稿。技能采用原子化 Markdown 工作流，逐节撰写后合并导出 Word，执行严格的章节结构校验、逐阶段门禁检查与版本快照回滚。正文字数按学位类型设定软目标（博士不低于五万字，硕士不低于三万字），材料不足时宁可少写，不以编造数据充抵字数。格式支持内置模板与自定义院校模板两种模式，自定义模板信息不完整时仅允许整理 Markdown，不予导出 docx。触发词：博士论文、硕士论文、学位论文、毕业论文、SCI转论文、doctoral thesis、master thesis、dissertation。本技能要求用户提供可访问的 SCI 论文材料，不适用于本科毕业论文。
---

# Sci2Doc

## Overview

本技能适用于博士或硕士学位论文，需用户提供已成稿的 SCI 论文材料作为转化来源。若用户没有可访问的 SCI 论文材料，或场景是本科毕业论文，主动退出本技能，不要套用本流程。

This skill converts SCI paper materials (PDF/Word plus user context) into a Chinese doctoral thesis draft.

This skill is process-first, not one-shot generation.

The workflow is built around:
- `state_manager.py` for anti-forgetfulness, token budgeting, gate checks, snapshot/rollback
- `atomic_md_workflow.py` for atomic subsection markdown files, numbering validation, merge, self-check, section-level snapshot

**【Python 解释器探测：启动前置，一次探测全程沿用】** 本文档中的 `python3` / `python` 仅为 macOS/Linux 的习惯写法，并非硬性要求。启动前执行一次 `python3 --version`：
- 输出正常版本号 → 本次会话所有命令统一使用 `python3`。
- 报 command not found、无任何输出、或弹出应用商店 → 改为执行 `python --version`，能输出版本号则将后续所有命令中的解释器统一替换为 `python`。注意 Windows 自带一个 0 字节的 `python3` 占位程序，`python3 --version` 弹出商店或无输出即表示命中该占位程序，**不视为已安装 python3**，按"未安装"处理（用户也可在 设置 → 应用 → 应用执行别名 中关闭 `python3.exe`）。
- 反之 `python` 无法输出版本号则改用 `python3`（macOS 12.3 起系统不再预装 `python`）。
- 两者均无法输出版本号，表明该机器未安装 Python，须停止并告知用户先行安装，不得强行执行。
- 探测仅执行一次，后续所有命令沿用同一解释器名称，无需每条命令重复探测。

## 接续与决定日志（每次启动本技能前置）

学位论文往往跨多次会话才写完，用户中途还常插新要求。连续性靠外部状态文件维持，不靠模型记忆：

1. **开局须先执行接续报告并完成确认**：`env_preflight.py` 会输出 `RESUME_CMD`（绝对路径）。按其执行
   `python <..>/session_journal.py resume --root <project_root>`，将输出呈现给用户并确认「从此处继续」后方可动笔。
2. **用户每插一条新要求/新决定，立即 log**：`python <..>/session_journal.py log --root <project_root> --note "用户要求：<原话>"`。
   决定写入 `decisions_log.md`（append-only），后续会话必读并遵守。
3. **引文核证命令**：`env_preflight.py` 同时打印 `CITATION_CHECK_CMD`，见 `## Citation Claim Check (承重论点↔引文)`。

## 快速流程索引 (Quick Workflow Index)

全流程 7 步顺序如下，详细说明见各节。

| 步骤 | 操作 | 阻断条件 | 详见 |
|------|------|----------|------|
| **0. 材料确认** | 确认源材料可访问、用户提供论文题目/章数/院校 | 材料缺失 → 停止 | `### 0) Material Input Gate` |
| **0.5. 研究主线设计** | 产出科学问题→贡献→章节映射表；协商章节字数目标；写入 `outline` | `outline` 为空 → 不得进入 Step 1 | `### 0.5) Research Storyline Design` |
| **1. 样式选择** | 询问 内置默认模板 or 自定义；写入 `thesis_profile.json` | 自定义信息不完整 → `pending_template` | `## Style Selection Gate` |
| **2. 初始化项目** | `state_manager.py init`；验证 profile；章节字数已在 Step 0.5 协商 | profile 缺字段 → 不允许生成 docx | `### 1) Initialize Project` |
| **3. 文献检索** | 学科路由（生命科学→PubMed CLI / CS/AI→paper-search MCP）；运行 citation_guard | guard `ok=false` → 停止写作 | `## Citation Zero-Hallucination Gate` |
| **4. 预写门禁** | `write-cycle --chapter N` 加载跨章记忆 | 每章每节必做，不可跳过 | `### 2) Prewrite Gate` |
| **5. 原子化写作** | 每节一个 `.md`；写完验证编号+实验映射；更新 `chapter_index.json`；原始图不可用时生成 Figure Prompt | 编号断裂 → 修复后才能继续 | `### 3) Atomic Subsection Writing` |
| **6. 快照与质量门** | 节后快照；章后 self-check；humanizer 去 AI 化 | self-check 失败 → 修复 | `### 4) / ### 5) / ### 6)` |
| **7. 合并导出** | merge → gate-check → generate Word | format acceptance 未通过 → 不交付 | `### 7) / ### 8) / ### 9)` |

---

## Style Selection Gate (Mandatory)

> **执行顺序：** 本 Gate 在 `### 0) Material Input Gate` 完成后执行（先确认材料，再选样式）。如无源材料，停在 Step 0，不进入 Style Selection。

初始化或起草前，AI **必须** 让用户在两种样式中二选一：

1. `默认设置`：内置默认学位论文模板（通用格式，可自定义为任意院校）。机构字段为占位符（`示例大学`/`[学校代码]`），用户应替换为本校信息。
2. `自定义样式`：用户须提供目标院校 + 详细 Word 格式要求和/或模板证据文件。

🔴 **CHECKPOINT（阻断 init）：** 未与用户明确确认样式前，**不得运行 `state_manager.py init`**。即使用户可能想用内置默认模板，也必须先得到用户对"就用内置默认模板"的明确确认，再带样式参数运行 init。**禁止** 因看到 QUICK_START 的 init 示例就直接套用默认 `--format-mode default_generic` 跑 init（该默认会静默落成内置模板格式且立即放行 docx 导出）。

**硬门禁：** 自定义信息不完整的项目标记为 `pending_template`，可继续整理 markdown，但 **不得生成 `.docx`、不得运行格式验收**。`custom` 仅在写入结构化布局字段后才能转为 `ready`，否则保持 `pending_template`。

**custom→ready 最小必填字段**（缺一即保持 `pending_template`）：`page_margins_cm.top/bottom/left/right`（四个边距）、`header_distance_cm`、`footer_distance_cm`、`university_name`、`degree_type`。

字段完整定义、需求→字段映射、managed front matter 文件清单、managed marker 覆盖规则等细则见 `references/format_profile_schema.md § Style Selection Gate (full rules)`。

## Non-Negotiable Requirements

1. Body text target depends on degree type: **≥50,000 characters for doctoral**, **≥30,000 for master's** (defaults; confirmed with user at project start and written to profile as `body_target_chars`). 这是**软目标**而非硬门（`check_quality.py` 字数不足为 warning）：可经用户同意上调；不达标只提示、不阻断导出。**真实材料撑不到目标时宁可少写，绝不编数据/灌水凑字**（A③ 已把综述/绪论并入正文计数以减压）。
2. Chapter-level target allocation is **not hardcoded** and must be negotiated with the user for each project.
3. Chinese abstract must be **1500-2500 characters**.
4. Main structure is fixed:
   - independent Introduction chapter
   - multiple research chapters
   - independent final Conclusion/Outlook chapter
   - total chapters >= 5
5. References are unified at the end of the full thesis.
6. Body word count scope: abstract through end of body text (before full-thesis references). **综述/绪论章计入正文字数**，把凑字数压力从研究章分摊出去，缓解逼 AI 靠编数据/扩实验凑字（`check_quality.py` / `count_words.py` 已将 review 章并入 body 计数，另单列 `review_words` 供展示）。仅全文末尾统一参考文献、目录、致谢、附录、成果、声明、缩略语表排除在外；若确有整章须排除，用 `format_profile.exclude_from_body_count`（章标题字符串列表）逐章显式声明。
7. For research chapters, Results & Discussion must map to Methods experiment-by-experiment.
8. One experiment must map to at least one standalone figure or table.
9. Atomic markdown is mandatory: one subsection per `.md`, continuous numbering, merge before Word conversion.
10. Chapter completion requires immediate self-check.
11. Each subsection summary completion requires immediate snapshot.
12. Humanization is required before finalizing chapter text；细则见 `## Humanization Contract`。
13. Do not invent experimental data.
13.1 Do not invent references; citation hallucination is forbidden.
14. Literature retrieval follows topic-dependent routing (MANDATORY)：细则见 `## Citation Zero-Hallucination Gate`。
15. 缩写一致性强制执行：首次展开格式 `中文全称（English Full Name, ABBR）`，后续裸缩写；用 `abbreviation_registry.py` 管理；需生成前置缩略语表。细则见 `## Abbreviation Contract`。
16. 三线表格式强制：所有数据表使用 Markdown 管道语法，`markdown_to_docx.py` 自动转换；边框参数与题注字体字号见 `references/word-format-spec.md § Three-Line Table Borders`。细则见 `## Table Contract`。
17. 文风约束：见 `## Humanization Contract`（清单集中在那里）；`check_quality.py check_writing_style()` 自动检测。**硬禁清零项**：破折号（——）/scare quotes/解释性冒号三项标点 + AI 禁词，finalize 前必须归零。**软提示项**（不阻断 finalize）：句长/句式节奏（C 降软）。
18. 格式对齐规则：正文两端对齐、三线表单元格居中、图占位符居中无首行缩进。完整参数见 `references/word-format-spec.md`。
19. Bold marker 处理：`**text**` / `__text__` 在 Word 转换时由 `md_runs.inline_md_to_runs()` 解析为真正的粗体 run；单 `*` 统计显著性标记（如 `*p<0.05`）由其内置保护规则保留原样。
20. 已发表 SCI 内容复用合规底线：
    - 正文复用必须**改写**为中文学术表述，不得直接翻译粘贴。
    - 每章首次复用处必须标注来源文献（正文引用 [N] + 声明"本章部分内容已发表于 [N]"）。
    - 复用成果须同时体现在"攻读学位期间取得的成果"清单与"独创性声明"中。
    - 缺标注的已发表内容复用等同未注明引用，触发学位办自我抄袭/重复发表红线。
    - **本技能不做查重，改写 ≠ 降重**：技能只把英文材料改写成中文学术表述并做文风/翻译腔软检测，不计算重复率、不对接知网/万方/Turnitin。是否达标须用户自行送第三方查重系统核验。
    - **逐段"原文-改写"对照表（人工产出）**：凡复用已发表 SCI 内容的段落，须在 `docx/reuse_map.md`（或交付附件）中逐段列出对照表，列：所在章节 / 原文出处 [N] / SCI 原文片段 / 中文改写文本 / 改写状态(confirmed/pending)，供用户自查重复率与送查重。

## Citation Zero-Hallucination Gate (Mandatory)

Before writing any chapter section and before final full-thesis merge, run:

`python3 scripts/citation_guard.py --index "${save_path}/literature_index.json" --mcp-cache "${save_path}/mcp_literature_cache.json" --mcp-ttl-days 30 --write-back --manual-review "${save_path}/manual_review_queue.json" --log "${save_path}/verification_run_log.json" --report "${save_path}/citation_guard_report.json"`

规则要点：每批检索/导入更新 `literature_index.json` 后立即跑一次 guard；guard 非零或 `ok=false` → 停写先清队列；双向校验失败的条目置 `verified=false` 进 `manual_review_queue`；未核验文献不得入正文；学科路由 PubMed CLI（生命科学）/ paper-search MCP（CS/AI）二选一且串行；禁 `websearch` / `openalex-cli` / `tavily`；无 DOI/PMID 不放行；引用类型按语境（综述/原始研究/临床试验/预印本）。**Step 3 检索前与每次跑 guard 前，先 Read `references/citation-gate.md`**（完整规则、`--write-back` 短路语义、路由命令、来源策略、`--require-mcp` 严格模式）。


## Citation Claim Check (承重论点↔引文)

`citation_guard.py` 只验引文**真实性**（DOI/PMID/标题对得上）；它不判「这篇引文到底**支不支持**它挂着的那句论点」。写研究章时，对**承重论点句**（机制/因果/关键定量结论）↔ 其引文，必须再过一道**引文核证**：

1. `literature_index.json` 每条可选带 `key_finding`（该文献真实结论一句话）与 `claim`（本文用它支撑的论点）两字段，最小承载核证语义（schema 见 `references/format_profile_schema.md § literature_index.json schema`）。
2. 写某研究章前，对每个「承重论点句 ↔ 引文」建一行证据，落 `claim_evidence.json`（list），字段 `{section, claim_sentence, is_load_bearing, ref_id, retrieved_abstract, verdict∈support/weak/contradict/unknown, evidence_quote, user_confirmed}`。`retrieved_abstract` 用**检索到的真实 abstract**（不看可编的 `key_finding`），取 abstract 走本技能既有文献检索subagent。**已建过证据的可留空以省事**：脚本读写 `ref_evidence_cache.json`，对某条 `ref_id` 已缓存过 abstract 的行自动回填 abstract、AI 不必重新检索；同一 `(ref_id, claim_sentence)` 已判定过的行自动复用上次结论，AI 只需对**新的 (文献, 论点) 组合**做反向验证。
3. 跑共享核证脚本（`env_preflight.py` 打印的 `CITATION_CHECK_CMD`），命令 `python <sci2doc>/scripts/citation_claim_check.py --root <project_root> --evidence <project_root>/claim_evidence.json`。脚本自动读写 `ref_evidence_cache.json`（回填 abstract + 复用同 (文献,论点) 已确认结论），门禁强度不变。
   - 承重句 `verdict∈{contradict,unknown}` 或缺 abstract 或未 `user_confirmed` → **fail-closed（exit 2），硬拦 + 人工逐条确认**后方可下笔。
   - 背景陈述句只在表里批量呈现、不逐条阻断。
4. 纳入节/章 DoD（见 dod_checklist `section-dod`/`chapter-dod` 的 citation_claim_check 项）。

## Single Source of Truth

论文目标配置存于 `thesis_profile.json`；样式选择与格式门禁存于其 `format_profile`；运行时状态镜像在 `project_state.json`。自定义要求不完整时 `progress.status` 必须为 `pending_template`（导出硬门禁见 `## Style Selection Gate`）。

`format_profile` 完整字段清单、结构化更新入口（`--format-profile-json` / `--project-info-json`）、页码格式枚举、需求→字段映射规则、`project_info` 字段，均见 `references/format_profile_schema.md § Single Source of Truth`。

## Project Directory Structure

After `init`, the project root contains exactly these directories and files. **Do NOT create any directories outside this list.**

完整目录树（`atomic_md/`、`02_分章节文档/`、`03_合并文档/`、`04_图表文件/`、`scripts/`、`materials/`、`.state/`、`backups/` 与根级各 JSON/MD 文件）见 `references/project-layout.md`：**`init` 前与首次向任何目录写文件前，先 Read 它**。


### Anti-Drift Rule (Mandatory)

AI **must only** create or write files into the directories listed above. Any artifact that does not fit an existing directory is a workflow violation. Do not create directories outside this list.

## Prewrite Memory Loading (Critical)

`write-cycle` 的 `load_state` 自动加载：`project_state.json`（含 outline 主线）、`chapter_index.json` / `literature_index.json` / `figures_index.json`（按当前章过滤；绪论/结论章按 A① 跨章全量加载）、`context_memory.md`、`history_log.json`、以及从 `atomic_md/` 抽取的轻量 `chapter_section_digests`（只取标题/表题/关键事实/字数，不加载全文）。写完每节后 AI **必须**把该节关键事实更新进 `chapter_index.json`。**每章首次 write-cycle 前，先 Read `references/prewrite-memory.md`**（七项加载内容、A① 例外细则、digest 机制、chapter_index 条目示例）。

**Rule**: Never skip `write-cycle` before writing a new subsection. It is the only mechanism that loads cross-section memory.

## Required Workflow

每一步的完整命令、门禁条件与细则已外置：Step 0–8、10 与节级/章级 DoD 在 `references/workflow-steps.md`，Step 9 全文总检在 `references/full-thesis-checks.md`。**执行任一步前，先 Read 对应文件的该步小节；完整可复制 CLI 见 `QUICK_START.md`。** 骨架如下：

- **0) Material Input Gate**：先问学位类型与正文字数目标并写入 profile；确认材料可访问、题目/章数/院校已给；[可选] `material_ingest.py` 落盘原始材料；提取 SCI 论文文本（pdf/docx）；`extract_docx_images.py` 抠内嵌图；把 SCI 自身参考文献导出为 `sci-source-seed` 种子。材料缺失 → 停。
- **开场监工卡**（原样输出给用户，见下节）。
- **0.5) Research Storyline Design**：与用户共同产出"科学问题 → 贡献映射表"写入 `project_state.json.outline`；协商各章字数写入 `chapter_targets`；用户确认结构后运行 `SIGNOFF_CMD` 落签字。`outline` 为空 → 不得进入 Style Selection Gate 与 Step 1。
- **1) Initialize Project**：`env_preflight.py`（软门禁）→ `git_checkpoint.py init` → 先二选一样式再 `state_manager.py init` → `profile --show` 验证并写入已协商字数。自定义字段不全 → 保持 `pending_template`。
- **2) Prewrite Gate**：`state_manager.py write-cycle --chapter N`，每章每节必跑。
- **3) Atomic Subsection Writing**：`prewrite_gate.py --section X.Y` 硬拦（exit≠0 禁写）→ `delegate_write.py pack-write` → 派撰写子代理按 `references/section_writer_prompt.md` 盲写（引用只写 `[@key]`）→ `verify-write` → `new_refs` 先过 `citation_guard.py --require-mcp` 再 `citation_renumber.py merge-refs` → 落盘 `atomic_md/第N章/` → `data_trace_gate.py`（无 `[数据来源]` 的数值不得保留）→ `abbreviation_registry.py process` → 更新 `chapter_index.json`。章末合并前 `citation_renumber.py renumber --check` 后再 `--in-place`。
- **4) Subsection Snapshot**：`section-snapshot` + `git_checkpoint.py commit`；随后**节级 DoD 盲检**（`delegate_review.py pack/verify --gate section-dod`，exit 0 才算过）→ **①DoD 停**：把逐项结论摆给用户、HALT 等用户说"过"才写下一节。修复 3 次仍不过 → 回滚兜底。
- **5) Merge Chapter**：`merge --chapter N --to-docx`（`pending_template` 时转换器拒绝，不得绕过）→ **6) Chapter Self-Check**：`self-check`；随后**章级 DoD 盲检**（`--gate chapter-dod`）+ 用户抽验"数值→原文图/表"对照表 → ①DoD 停 → **7) Finalize**：`write-cycle --finalize --snapshot` + 章末 git commit。
- **8) Merge Full**：`merge-full --to-docx`（先纳入根级前置页）→ **9) Full Thesis Checks**：字数 / `check_quality.py --enforce-full-structure --md-checks xref` / 交叉引用断链 HALT / 参考文献硬门（≥80）+ 按章软门 / 数值一致性三层核查 HALT / 方法学漏写三层核查（章级 scoping）HALT → **10) Rollback if Needed**：`state_manager.py rollback --target snapshot`。

## 开场监工卡（每次启动本技能须原样输出给用户）

> 学位类型与源材料确认之后、生成章节结构之前，AI **必须** 将下方监工卡原样输出给用户。此卡列出 sci2doc 最易出错的环节，供用户全程监控。

```
【sci2doc 监工卡 · 以下事项须用户全程把控】
1. 数据禁止杜撰：为达字数目标（博士≥5万字/硕士≥3万字），AI 易将实验数值杜撰补齐。
   每完成一章，须要求 AI 提供"数值→原文图/表"对照表，随机抽取 2-3 个数值回原文核对。
2. 须逐章交付，不得一次性生成全文：一次性生成整篇将跳过所有逐节质检与盲检，
   外观完整但实际未通过任何门禁。发现 AI 批量输出全文应立即中断。
3. 本技能不执行查重，改写不等于降重：复用已发表 SCI 段落时，须要求 AI 提供"逐段原文-改写对照表"
   （章节/原文出处/SCI原文/中文改写/状态），由用户自行提交知网/维普查重，不应仅凭"已改写"判定。
4. 引文抽验 DOI：从参考文献中随机选取 3-5 篇，要求 AI 报出 DOI/PMID，自行前往 doi.org 验证真伪。
5. 章节结构须用户亲自签字确认：下方"研究主线/章节结构"须经用户确认后方可落签字解锁正文，
   AI 不会代替用户确认。未签字时，正文写入将被门禁强制拦截。
```

> 若开工前置的 `env_preflight.py` 报门禁状态为 `degraded`（当前环境不透传 hook）→ 明确告诉用户"本环境无法强制拦截，上面 5 条全靠你人工盯"。

---

## 写作契约（按需 Read，主文件只留索引）

- 写任何章的第一节前，先 Read `references/contracts-chapter.md`（研究章五段固定顺序、绪论/结论章跨章写法、方法-结果逐实验耦合、`[实验]`/`[对应实验]`/`[图]`/`[表]` 标记约定）。
- Step 0.5 设计主线与 Step 1 init 前，先 Read `references/contracts-outline.md`（大纲必含项：封面/声明/中英摘要/目录/缩略语表/符号表/各章/参考文献/致谢/成果）。
- 每节写前查 registry、写后跑 `abbreviation_registry.py process` 前，先 Read `references/contracts-abbreviation.md`（首展格式、希腊字母、动词不入全称、CLI 子命令）。
- 每章 finalize 前，先 Read `references/contracts-humanization.md`（humanizer-zh 流程与中文正文/英文摘要去 AI 清单，硬禁三项标点 + 禁词清零）。
- 写含试剂/仪器/分组/统计等结构化数据的小节前，先 Read `references/contracts-table.md`（三线表 Markdown 语法、必用场景、3 项以上同属性必成表）。
- 写正文或表格前，先 Read `references/word-format-spec.md` 的「字符级排版契约」节（斜体/上标/下标/加粗标记与全半角规则）。
- 写含图的小节、运行 `figure_registry.py register` 前，先 Read `references/contracts-figures.md`（`图{chapter}-{seq}` 编号规则、SCI 子图映射、标记约定、注册/校验流程）。
- 原图不可用需重绘或用户明确要配图代码时，先 Read `references/figure_prompt_template.md`（Figure Prompt 块模板与配图代码生成 opt-in 规则）。
- 每节/每章收口前，先 Read `references/anti-patterns.md`（Common Mistakes 5 条 + 反例黑名单 16 条，命中任一即返工）。

## Word Format Specification (Built-in Default Template)

完整字体、字号、页边距、页眉页脚、三线表边框等参数详见 `references/word-format-spec.md`（内置默认博士学位论文版面标准，由 `markdown_to_docx.py` 硬编码实现，`check_quality.py` 强制校验）。

## Acceptance Checklist

格式类参数（字体/字号/边框/对齐/页眉页脚/摘要/目录间距等）由脚本硬编码并强制校验，**不在此复述**，以 `check_quality.py` 各类别通过为准。本清单只保留需人工确认的项：

- [ ] `check_quality.py --enforce-full-structure` 各类别（三线表 / 引用格式 / 标点 / 缩略语 / 字体字号 / 页眉页脚 / **参考文献著录格式**）全部通过
- [ ] Body target 接近学位软目标值（博士 ~50,000 / 硕士 ~30,000，或用户在 Step 0.5 协商的更高值；综述/绪论已计入正文，A③）且各章字数已写入 profile；不足只提示不阻断，严禁编数据凑字
- [ ] 结构满足：引言 + 研究章 + 结论，总章数 >= 5；参考文献统一在全文末尾
- [ ] 原子化工作流：编号校验通过、章节自检已跑、小节快照已建、快照/回滚可用
- [ ] Humanization pass 已完成（humanizer-zh 或人工清单）
- [ ] 缩略语注册表与图号注册表已填充并交叉校验通过
- [ ] **查重预检（人工，本技能不做查重）：** 技能不计算重复率、不对接任何查重系统；改写 ≠ 降重。提交知网/万方查重前，基于 Non-Negotiable 第 20 条产出逐段"原文-改写"对照表（`docx/reuse_map.md`：所在章节 / 原文出处 [N] / SCI 原文片段 / 中文改写文本 / 状态 confirmed/pending），确认全部为中文改写且有引用标注，再由用户自行送第三方查重。

> **🔴 硬规则（全局）：每节收口自检清单（G1-G6 + S1-S5）与每章收口自检清单（G1-G6 + S1-S7）未逐项确认通过，不得向用户声明"该节/该章完成"。** 能脚本核的项必须跑脚本取证据（`ok=true` / 零 error）；人工项逐条打 ✅ 后方可放行。此规则优先于任何上下文压力或用户催促。

## 流程跳步的用户干预方法

以下指令可直接发送给 AI，要求其呈现完整过程与证据：

- 「每完成一章贴四样给我：git log commit 列表、.review_pass/ 文件清单、citation_guard_report.json 的 ok 字段、本章每个关键数值对应原文哪张图的对照表。拿不出就回对应 Step 重跑」
- 「把本章所有实验数值列成表，每行标注来自 materials_archive.json 哪个 entry 哪个字段；追溯不到的全部标红等我核」
- 「AI 应一节一节写、每节存文件做检查；你一次性甩整章给我 = 跳过了所有质检」
