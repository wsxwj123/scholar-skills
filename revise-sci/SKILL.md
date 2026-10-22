---
name: revise-sci
version: 2.31.1
description: 用于退稿或返修阶段的完整改稿管道，由审稿意见驱动修改既有稿件。技能将审稿信拆解为逐条意见，据此修改主稿并同步产出三项交付物：逐条回复信、修改后的正文 docx，以及基于内容哈希校验的 Patch 修订记录。可选启用词级修订痕迹，在 Word 中以增删痕迹形式呈现改动。禁止杜撰实验、数据、统计结果与参考文献，证据不足处标记为需作者确认。触发词：改稿、修改稿子、修订正文、退稿改进、返修、revise manuscript、major revision、minor revision、revise and resubmit、point-by-point response、revised manuscript。路由说明：本技能同时修改主稿并产出回复包，若仅需回复而不修改主稿，应使用 reviewer-response-sci；撰写新稿应使用 general-sci-writing，本技能仅处理审稿意见驱动的既有稿件修改。
---

# Revise-Sci

## Overview
Use this skill to turn reviewer comments, the original manuscript, SI, and attachments into two deliverables: a revised manuscript and a structured `Response to Reviewers`. Both come out in Markdown and Word.

The workflow is script-gated. Do not skip steps. Do not fabricate experiments, data, statistics, or references.
The comment parser accepts both atomic `comment-unit` HTML and reviewer-simulator style report HTML with critique lists.
The manuscript atomizer recognizes numbered section headings such as `1`, `1.1`, and `2.3.4` even when the source Word paragraph style is not a formal heading style.

## 开场监工卡（每次启动须原样输出给用户）

> 返修改稿最易在以下环节出错，AI 可执行但**结果是否正确只有用户能核对**。启动本技能时须原样输出此卡：
>
> 1. **意见拆解须用户核对完整性**：拆解完成后 AI 会输出意见清单，须对照原始审稿信**逐条核对**：是否存在被合并或整条遗漏的情况。条数不一致即存在遗漏。
> 2. **改动须逐处核对**：每处改动 AI 应提供「原句 → 改后句」对照，用户须确认语义未变、未夹带未经同意的新结论。未见对照不应放行。
> 3. **覆盖须查对照表**：交付前 AI 应提供「意见 × 是否回复 × 是否改稿 × 结局」对照表。「改稿」列为空**但结局标 `push_back`（有意驳回不改）**的属于正常，非遗漏；真正的遗漏是：某条既无回复、结局又不属于 `completed`/`push_back`/`需作者确认`。须区分「有意不改」与「遗漏」。
> 4. **标注"需作者确认"属于正常行为**：AI 无法获取用户的数据/实验时应标注「需作者确认」等待补充，此为设计行为而非故障，须由用户逐项补齐。
> 5. **门禁通过仅保证形式合规**：门禁仅检查格式、覆盖率与红线等机械项，**改动是否正确、说理是否通顺须用户自行核对**，不应将门禁通过等同于"改对了"。

**【Python 解释器探测：启动前置，一次探测全程沿用】** 本文档中的 `python3` / `python` 仅为 macOS/Linux 的习惯写法，并非硬性要求。启动前执行一次 `python3 --version`：
- 输出正常版本号 → 本次会话所有命令统一使用 `python3`。
- 报 command not found、无任何输出、或弹出应用商店 → 改为执行 `python --version`，能输出版本号则将后续所有命令中的解释器统一替换为 `python`。注意 Windows 自带一个 0 字节的 `python3` 占位程序，`python3 --version` 弹出商店或无输出即表示命中该占位程序，**不视为已安装 python3**，按"未安装"处理（用户也可在 设置 → 应用 → 应用执行别名 中关闭 `python3.exe`）。
- 反之 `python` 无法输出版本号则改用 `python3`（macOS 12.3 起系统不再预装 `python`）。
- 两者均无法输出版本号，表明该机器未安装 Python，须停止并告知用户先行安装，不得强行执行。
- 探测仅执行一次，后续所有命令沿用同一解释器名称，无需每条命令重复探测。

## 跨会话接续（每次开局前置，与监工卡是两件事）

监工卡是「启动提醒」，接续报告是「恢复上一会话的进度」。**每次进入本技能、且 `project_root` 已存在时，须先执行接续命令后方可继续**：

```bash
python "<技能>/scripts/session_journal.py" resume --root <project_root>
```

`env_preflight.py` 会将此命令输出为 `RESUME_CMD`（连同 `LOG_CMD` / `CITATION_CHECK_CMD`，均为解析好的绝对路径）。读取接续报告后，**据其与用户进行接续确认**：复述当前 phase、已处理的 comment、以及 `decisions_log.md` 中用户历次要求，询问「继续执行 <下一步>，是否正确？如有新要求请先提出」**等待用户确认后方可继续**。

用户在会话中途**插入任何临时要求**（改哪节、换策略、加/撤某条意见的处理方式）时，**当场 log**，后续会话必读必守：

```bash
python "<技能>/scripts/session_journal.py" log --root <project_root> --note "<用户要求原话>"
```

## Mandatory Intake Before Any Full Pipeline Run
When the user provides a `comments_path`, a `manuscript_docx_path`, or both, do **not** jump straight into `run_pipeline.py`.

First, env precheck (soft gate, before any pipeline run): `python scripts/env_preflight.py <project_root> --cli esearch --py docx`; it writes `env_status.json`, and the last line prints `PRECHECK: OK|ASK|BLOCKED`. BLOCKED (Python too old) → stop and guide upgrade; ASK (missing optional tools like esearch/python-docx) → ask the user per tool whether to install, give guidance, continue only after the user answers installed/skip; OK → continue. Rollback uses `state_manager.py snapshot` + Patch-hash (no git checkpoints).

Always run:

```bash
python scripts/intake_router.py --comments <comments_path> --manuscript <manuscript_docx_path>
```

Before any substantive revise work, report to the user:
- which `comments_input_mode` was detected;
- which branch-specific workflow will be used next;
- that the workflow preserves the same atomicization, fragment-only rewrite, anti-AI polish, state-window, anti-forgetfulness, and hard-gate rules;
- then ask the user to confirm that routing decision **together with** the desired `project_root` / output path.

If the input does **not** match any supported branch:
- do not proceed silently;
- ask the user whether to map the input to an existing branch or create a new branch;
- any new branch must still preserve the same atomicization, fragment-only rewrite, anti-AI polish, state-window, anti-forgetfulness, and hard-gate rules.

If the user has **no reviewer comments** and only provides the manuscript:
1. run `python scripts/intake_router.py --manuscript <manuscript_docx_path>`;
2. ask whether to use `reviewer-simulator` first to generate reviewer comments;
3. check global availability using `python scripts/ensure_global_skill.py --skill-name reviewer-simulator`;
4. if the skill is missing and the user confirms installation, install it from your own skills backup repository (reviewer-simulator subdirectory) before invoking that branch.

## Comment Input Modes
六种模式：`docx-review-comments` / `docx-review-letter` / `reviewer-simulator-html` / `reviewer-response-sci-html` / `atomic-comment-html` / `no-comments-manuscript-only`。`intake_router.py` 报出 `comments_input_mode` 后、向用户汇报分支前，先 Read `references/comment-input-modes.md`（各模式的解析器行为，以及 `docx-review-letter` 与 `reviewer-response-sci-html` 两个分支的专属要求）。

## Required Inputs
- `comments_path`
- `manuscript_docx_path`
- `project_root`
- `output_md_path`
- `output_docx_path`

Optional but supported:
- `si_docx_path`
- `attachments_dir_path`
- `reference_docx_path`
- `journal_style`
- `paper_search_results_path`
- `references_source_path`
- `expected_comments_mode`
- `context_token_budget`
- `context_tail_lines`

## Output Contract
固定交付：`response_to_reviewers.md` / `response_to_reviewers.docx`、改后稿 `output_md_path` / `output_docx_path`（原稿为 `.docx` 时默认 in-place 保原稿格式，定位失败硬停退出码 3；可选 `--track-changes` 词级修订痕迹）、各类报告与 `data/` 索引。向用户说明交付物前、以及运行 `export_docx.py` 前，先 Read `references/output-contract.md`（完整产物清单、in-place / `--allow-rebuild-fallback` / `--track-changes` 的语义）。

## Pipeline
执行 Pipeline 任何一步前，先 Read `references/pipeline.md`（逐脚本顺序与参数说明、`export_docx.py` in-place / `--track-changes` 细则、三层核查的四步细则与逐字极性模板、round22 一键 pipeline 状态机与退出码）。骨架顺序如下，脚本名与参数以该文件为准：

1. 原子化与索引：`intake_router.py` → `preflight.py` → `atomize_comments.py` → `atomize_manuscript.py` → `manuscript_index.py` → `extract_docx_images.py` → `build_issue_matrix.py` → `state_manager.py refresh` → `citation_guard.py`（有 paper-search 结果时）。
2. 🔴 [意见清单核对·必停]（见下节）→ [通读定策略] 给每条 unit 填 `revision_strategy`（见下节）→ `revise_units.py` → `build_literature_index.py` → `matrix_manager.py bootstrap` / `audit` → `merge_manuscript.py` → `reference_sync.py` → `build_reference_registry.py` → `export_docx.py`。
3. 收口核查：`final_consistency_report.py` → 三层核查（`numeric_candidates.py` 数值一致性 → `structure_outline.py` 交叉引用 → `methods_terms.py` 方法学漏写，综述稿跳过方法学；每层 = 第 1 层确定性锚 + 第 2 层独立检测子代理 + 第 3 层 `delegate_review.py` 反向验证，命中 confirmed 即 HALT 交用户裁决；主 agent 忽略 verify 退出码、只读逐条 verdict）→ DoD 盲检（见下文）→ `strict_gate.py`。

单入口（`run_pipeline.py` 内置 round22 状态机：退出码 `3` 为预期人工暂停并打印 `PIPELINE_PAUSED phase=<phase>`，用 `--resume --confirm-*` 续跑）：

```bash
python scripts/run_pipeline.py --comments <comments_path> --manuscript <manuscript_docx_path> --project-root <project_root> --output-md <output_md_path> --output-docx <output_docx_path> [--journal-style journal-manuscript|nature-review|cell-press|lancet-review] [--expected-comments-mode <comments_input_mode>] [--context-token-budget 4200] [--context-tail-lines 80] [--paper-search-results <paper_search_results_path>] [--resume] [--resume-from <step>] [--resume-keep-unaffected] [--force-rebuild] [--allow-rebuild-fallback]
```

## [意见清单核对·必停]（拆意见后、改写前的强制关卡）

**位置**：`atomize_comments.py` 拆完审稿意见之后、`revise_units.py` 开始改写之前。这是流程内部的硬关卡，与开场监工卡不同：监工卡是启动时提醒，这一步是拆完意见后的当场核对。

拆完审稿意见后，**立即停下**，把**每条 comment_id + 该条前 30 字**列成清单打给用户，并原样问：

> 「请拿**原始审稿信**对照数一遍，条数对不对？有没有哪条被合并成一条、或整段漏掉？（尤其审稿人用连续散文、`(i)(ii)`、罗马数字、或一段里塞多个要求时最容易漏）」

**用户确认"都在、没漏"后才继续改写**。用户指出漏掉或被合并的，回去把它补成独立 comment（补进 `units/`、重新原子化）后再继续，不得跳过这一步直接跑 `revise_units.py`。

## [通读定策略·前置阶段]（清单核对通过后、逐条改写前）

实际返修的第一步不是逐条修改，而是**先将所有意见通读一遍、确定每条的应对策略**。本流程同理：意见清单核对通过后、`revise_units.py` 开始逐条改写之前，**须先做一轮 triage**，不得从 atomize 直接跳至逐条改写。

对每条 comment 定四选一的策略，并**写进该 unit 的 `revision_strategy` 字段**（`units/*.json`）：

| 策略 | `revision_strategy` 值 | 含义 | 结局 |
|---|---|---|---|
| 照做 | `comply` | 认可意见，按要求改正文 | 走正常改写 → `completed` / `needs_author_confirmation` |
| 部分让 | `partial` | 部分采纳，改一部分并说明取舍 | 正常改写 + 回复信说明界限 |
| 驳回 | `push_back`（或 `驳回`/`reject`） | 不采纳、正文不动，在回复信据理反驳 | 一等结局 `push_back`（见下节） |
| 补数据 | `needs_data` | 需新增实验/数据/图，当前材料不足 | 落 `needs_author_confirmation`，等作者补 |

**硬规则**：`revise_units.py` 逐条改写前，每条 unit 的 `revision_strategy` 必须先填（该字段已存在也要强制先确认/覆盖，不能留空跳过）。通读定策略是本阶段的产出，把结论落到字段里再进逐条改写。

## [驳回/不改] 是一等合法结局（不是漏改）

除 `completed` / `needs_author_confirmation` 外，新增第三个合法结局 **`push_back`**：**认定某条意见不应采纳，正文一个字不动，只在回复信里据理反驳**。这是真实返修的常态（审稿人误解、超范围要求、与本文定位冲突等），不是缺陷。

- **怎么触发**：该 unit 的 `revision_strategy` 设为 `push_back`（或 `驳回`/`reject` 等，见上表）。`revise_units.py` 即把该条 `status` 置为 `push_back`：正文不改、`revised_excerpt` 记为「N/A — manuscript unchanged」、回复信生成据理反驳的中英回应。反驳理由填 unit 的 `push_back_rationale_zh` / `push_back_rationale_en`（不填则回复信留占位提示作者补）。
- **覆盖判定别误报**：`issue_matrix.md` 的「修改动作」列会显示「不改（驳回）」、状态列显示 `push_back`；**监工卡第 3 条的对照表里，某条「改稿」列为空但结局是 `push_back` 的，是「有意不改」，不得判成「漏改」**。判漏改的唯一标准是：`status` 既非 `completed`、又非 `push_back`、又非 `needs_author_confirmation`，或该 comment_id 在回复信里根本没有回应。
- **不阻断交付**：`push_back` 是已决结局，`delivery_status` 只被 `needs_author_confirmation` 卡；`push_back` 计入 `project_state.json` 的 `counts.push_back`，不进待办。
- **红线仍在**：驳回≠可以不回应。回复信里该条必须有据理反驳的 response（中英），否则仍算漏回。

## [合并意见] 允许多条相关意见协调回应

原子架构默认每条意见一个密封 state window，但相关意见（同一处、同一诉求的不同侧面）应允许**合并成一处协调回应 + 交叉引用**，而不是各写各的、自相矛盾。

- **最小用法**：给相关的几条 unit 设同一个 `merge_group`（任意稳定 id，如 `MG-limitations`），并指定其中一条为 `merge_lead`（主回应所在的 comment_id）。主条写完整协调回应；其余成员条的 response 里**交叉引用**主条（如「详见 R2.3 的统一回应」/ "see our unified response to R2.3"），不重复长篇。
- **窗口不封死**：`state/comment_windows/<id>.json` 会带上 `merge_group` / `merge_lead`，据此从 `comment_registry.json` 找到同组兄弟条一起看，避免协同时上下文被切断。
- **不拆原子架构**：合并只是「分组 + 交叉引用」，每条仍是独立 unit、独立 comment_id、独立覆盖核验，绝不把多条塞进一条。

## Anti-Forgetfulness And Token-Budget Protocol
本技能不把全稿和全部意见塞进一个上下文窗，而是按 comment 逐条加载 state window。处理任何一条 comment 前，先 Read `references/anti-forgetfulness.md`（七条防遗忘原则：intake 先路由、节/段原子化、comment 级 state window、section digest、token 预算压缩、cycle log、snapshot）。每条 comment 的推荐加载命令：

```bash
python scripts/state_manager.py --project-root <project_root> write-cycle --comment-id <comment_id> --token-budget 4200 --tail-lines 80 --json-summary
```

## 外置契约（按需 Read，主文件只留索引）

- 需要锁定块级字节不变的确定性修订（anchorize → patch → apply）时，动手前先 Read `references/patch-protocol.md`。
- 改写任何句子、删句或新引术语前，先 Read `references/abbreviations.md`（缩略语首展一致性规则与 `abbreviation_index.json` 的硬错/软警告口径）。
- 生成 `response_to_reviewers.md` 前，先 Read `references/response-format.md`（标题层级与每条 comment 的 5 个固定小节）。
- 进入 `revise_units.py` 改写、文献补充、`--resume`、polish 或 `strict_gate.py` 任一环节前，先 Read `references/rules.md`（全部 Rules：引文双验与引文核证、reference 搜索治理、定位保守规则、resume 规则、polish 去 AI 五项与片段级守卫）。
- 撰写或改写任何正文片段、回复信英文前，先 Read `references/typography.md`（斜体/上标/下标/加粗行内标记与全半角规则；标记与 `[n]` 同等承重）。
- 每轮改写前与收口前，先 Read `references/anti-patterns.md`（反例黑名单，命中任一即停）。

## Definition-of-Done (DoD) 自检清单（改稿收口）

**位置**：polish 完成后、`strict_gate.py` 运行前。**硬规则：清单未逐项确认通过，不得向用户声明"改稿完成"。**

**🔴 委托盲检（不得主 agent 自评）**：改稿完成后自评容易默认通过且漏项。`strict_gate.py` 运行前必须把 DoD 清单**委托给独立上下文的subagent盲检**，不得自己直接打勾：

1. 生成任务包：`python scripts/delegate_review.py pack --checklist references/dod_checklist.json --gate revision-dod --files <改稿相关文件> --comments <comments_path>`（`--comments` 传本次审稿信原文，盲检子代理据原信逐条点名核对漏回/答非所问；同一 `comments_path` 与 `run_pipeline.py --comments` 一致）
2. **派一个独立subagent**（Claude Code 用 `academic-blind-reviewer`；其他平台派通用subagent），把任务包原样给它、**不要给它本次改稿的写作上下文**，要求按任务包返回 JSON 数组。
3. 校验返回：`python scripts/delegate_review.py verify --checklist references/dod_checklist.json --gate revision-dod --return <subagent返回.json>`；退出码非 0（任一缺项/fail/无证据）= **fail-closed**，据subagent证据修复后重跑，**未过不得声明改稿完成**。

> ⚠️ **盲检降级告警**：若当前环境派不出真正独立的subagent（非 Claude Code 客户端、provider 不支持 Task/子会话），**绝不能用同一个 AI 自问自答冒充盲检**（那就是自证）。此时明确告诉用户：「本环境盲检不可靠，请你亲自复核这几点：__（列出该盲检本应查的关键点，如 RV-G1 引文↔参考一一对应、RV-G3 改动是否跑题、RV-G5 去AI五项、RV-G7 缩略语首展、RV-G8 常识/事实错误等）__」，把判断权交回用户，不得伪造一份"通过"的盲检返回。

下列清单与 `references/dod_checklist.json` 逐项对应（**改清单先改 JSON，再同步此处散文**）；能脚本核的项subagent会先跑脚本：

逐项清单（通用 RV-G1~G8 / 特有 RV-R1~R12 / 投稿前作者自检）见 `references/dod-items.md`：**生成盲检任务包前、向用户摆逐项结论前，必须先 Read 它**。

🔴 收口前置闸口：`delegate_review verify` 必须 exit 0（含 RV-R8 结构完整性），否则不得声明改稿完成。任一项 fail 均为阻断。

🛑 **DoD 停·摆结论等确认（strict_gate 前的最后一道人工闸）**：盲检 `delegate_review verify` exit 0 之后、`strict_gate.py` 之前，**不得直接收口**。先把逐项结论摆给用户，每条 DoD（RV-G1~G8 / RV-R1~R12）是 pass / na / 🟡soft-report，软项（RV-G8 常识、RV-R12 拉丁斜体、去AI软提示、句长）列出但标明不阻断；同时给「意见 × 是否回复 × 是否改稿 × 结局（completed/push_back/需作者确认）」对照表。**打印后 HALT，等用户明确说「可以收口」再跑 `strict_gate.py` 并交付**。用户没确认就继续 = 违规。这与开场监工卡、清单核对是三道不同的人工闸：开场提醒 → 拆完核对 → 收口前摆结论。

## 流程跳步的用户干预方法

发现 AI 遗漏意见、改稿偏离原意或将半成品作为成品交付时，可将以下指令直接发送给 AI：

- 「审稿信里 Reviewer X 第 N 点你没拆出来，回去把它作为独立 comment 加进 `units/`，重新原子化再重跑 `revise_units.py`。」
- 「把第 X 条对应的**原句**和你**改后的句子**并排贴给我，我要确认意思没变、没夹带我没同意的新结论。」
- 「给我一张表：每条审稿意见 × 有没有回复 × 正文改了哪句（引用 `manuscript_edit_plan.md` 的 revised_excerpt）。哪条空着就是漏了，当场补。」
- 「先别跑完整 pipeline，先只跑到 `atomize_comments.py` 把意见清单给我看，我对照原始审稿信确认条数无误了再往下。」
- 「你这环境派不出独立subagent就别假装盲检通过了。把这轮该盲检的关键点列给我，我自己核。」
