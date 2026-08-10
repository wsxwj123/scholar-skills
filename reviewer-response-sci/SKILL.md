---
name: reviewer-response-sci
version: 2.28.6
description: 用于SCI审稿意见逐条回复的全流程技能，适用于期刊大修/小修阶段，只出回复包（HTML），不改主稿。触发词：审稿意见回复、回复审稿人、回复reviewer、response letter、回复信、rebuttal、逐条回复、Response to Reviewer、revise and resubmit、R&R、reviewer comments。路由说明：与revise-sci区分，本技能只出回复包不改主稿，需同时改主稿并出修订稿docx请用revise-sci；与reviewer-simulator区分，本技能针对已收到的意见写回复，后者是模拟生成审稿意见。
---

# Reviewer Response SCI

## 开场监工卡（每次启动必须原样打印给用户）
> 这份技能只出回复信、不改你的主稿，机器帮不了的活得你自己盯。启动时先把下面几条打给用户：
> 1. **一段多诉求最容易漏回**：审稿人一段话里常藏好几个要求。拆完 AI 会给你一份意见清单。你对着审稿原信一条条数，确认每个要求都单独成条、没被合并吞掉。
> 2. **主稿要你自己在 Word 改**：本技能不动主稿。你得照 `manuscript_edit_plan.md` 在 Word 里手动改正文，改完回头核对回复信里的**行号、引文、逐字片段**和你最终的稿子对不对得上。
> 3. **承诺必须兑现**：AI 在回复里每写一句"已添加/已修改/已补充"，改稿清单里就得有对应落点。AI 会给你一张回复 ↔ 改稿的对照表，帮你把"嘴上说了、稿里没做"的揪出来。
> 4. **缺数据只会标记、不会编**：证据不足处 AI 一律写 `Not provided by user`，这是等你补的坑，不是已完成。交付前逐个补齐，或确认可以留空。

**【Python 解释器探测·开工第一件事，一次探测全程沿用】** 本文命令里写的 `python3` / `python` 只是 macOS/Linux 的习惯写法，不是硬性要求。动手前先跑一次 `python3 --version`：
- 打印出正常版本号 → 本次会话所有命令照抄用 `python3`。
- 报 command not found、没有任何输出、或弹出应用商店 → 改跑 `python --version`，能出版本号就把后续所有命令里的解释器统一换成 `python`。注意 Windows 自带一个 0 字节的 `python3` 占位程序，`python3 --version` 弹商店或无输出就是撞上了它，**不算有 python3**，按"没有"处理（用户也可在 设置 → 应用 → 应用执行别名 里关掉 `python3.exe`）。
- 反过来 `python` 出不了版本号就换 `python3`（macOS 12.3 起系统不再自带 `python`）。
- 两个都出不了版本号 = 这台机器没装 Python，停下来告诉用户先安装，不要硬跑。
- 探测只做这一次，之后所有命令沿用同一个名字，不要每条命令都再试。

## 跨会话接续（每次开局先跑）
换会话/隔天接着写时，**先跑接续命令重建上下文，再跟用户打握手确认**，别凭记忆盲接：
```
python "<技能>/scripts/session_journal.py" resume --root <project_root>
```
（`env_preflight` 已把绝对路径打成 `RESUME_CMD`，直接复制。）读完它打印的权威状态 + 决定日志后，按脚本末尾的握手话术对用户说「进度到 X、你之前的要求我都读了、我打算接着做 Y，对吗？有新要求先插进来」，**等用户确认再动手**。
用户中途插新要求/改主意时，**立刻 log 一条**（否则下个会话必丢）：
```
python "<技能>/scripts/session_journal.py" log --root <project_root> --note "<用户原话>"
```
（对应 `LOG_CMD`。）

## Scope
Default mode is **one-shot full package with atomic storage**. Two secondary modes also exist: **Re-Render**（手改 unit JSON 后单独重渲，见 Re-Render Workflow）和 **skeleton/prewrite 预览**（出占位符草稿，命令见 Scripts 段）。

## Required Inputs
| 参数 | 必需 | 说明 |
|------|------|------|
| `comments_docx_path` | ✅ | 审稿意见文件 |
| `manuscript_docx_path` | ✅ | 论文正文 |
| `si_docx_path` | 可选 | 补充材料 |
| `project_root` | ✅ | 输出根目录 |
| `output_html_path` | ✅ | 最终 HTML 路径 |

**Outputs（one-shot 产物）：**
1. Atomic JSON pages — `units/` 目录（每条意见一个 JSON + 邮件 JSON）
2. Atomic manuscript units — `manuscript_units/`
3. Atomic SI units — `si_units/`（有SI时）
4. One final hierarchical HTML（主交付物，见 Output Contract）

## Save Path Confirmation (Mandatory)
Before running the pipeline, first ask the user where output files should be saved.

**环境预检（软门禁，确认 project_root 后、跑 pipeline 前）：** `python3 scripts/env_preflight.py <project_root> --cli esearch --py docx`，写 `env_status.json`，末行 `PRECHECK: OK|ASK|BLOCKED`。`BLOCKED`（Python 过低）→ 停并引导升级；`ASK`（缺 esearch/python-docx 等可选工具）→ 逐项问用户是否安装并给指引，用户答"已装/不装"后才继续；`OK` → 继续。回退靠 `state_manager.py snapshot`（不建 git 检查点）。**preflight 还会打印 `RESUME_CMD` / `LOG_CMD` / `CITATION_CHECK_CMD`（绝对路径）**，分别用于跨会话接续（见「跨会话接续」段）、记录用户临时要求、新引核证（见 Step 2）。

Default behavior if user does not specify a custom location:
1. Use the current project directory.
2. Create a dedicated subfolder for this run (for example: `projects/<task_name_or_date>/`).
3. Write all artifacts into that subfolder (`units/`, `manuscript_units/`, `si_units/`, `logs/`, final HTML).

## Output Contract (One-Shot)
> **主交付 = 回复包**（给编辑的总览邮件 + 各审稿人 point-by-point 回复，最终渲染为单文件分层 HTML）。
> **修改稿 track-changes 需用户手工补**：本技能生成回复文档，不产出 Word track-changes 版本；用户应以 `manuscript_edit_plan.md` 为操作指南，在 Word 中手动启用修订模式完成改稿。若用户要求 track-changes 稿件，解释此限制并推荐使用 `manuscript_edit_plan.md`。
> **收口提醒（交付时必须对用户说）**：回复信里的引文/行号/逐字片段是按 AI 拟稿写的；用户在 Word 里手工落地后，措辞或位置可能变。交付时提醒用户：**改完主稿后回头校准回复信里的引文与定位**（尤其行号、逐字引用的 revised 片段），确保回复信与最终修订稿一致。

**主交付物 = 单文件分层 HTML**（左侧层级 TOC + 右侧内容，单页可见）。TOC 顶层节点为 **Editor（若有）+ Reviewer #1/#2/...**，Editor 排在所有 Reviewer 之前；编辑信里的 editor comment（字数/格式/伦理声明/数据可用性/利益冲突/统计复核等）作为**独立顶层 Editor 节点**呈现，与各 Reviewer 并列，**不得并入任何 Reviewer**。**全部 UI 由 `scripts/build_full_package.py` 的 `render_html()` 生成**，TOC 层级、严重度背景色、折叠/展开、可拖拽分割线、`复制` 按钮、`localStorage` 持久化、各 box 布局均已硬编码，**AI 无需手工实现 HTML**。完整 UI 验收对照细则见 `references/output-template.md`。

AI 真正要产出的是每条 comment unit 的**内容字段**（脚本只写占位符，AI 填真值）：
- 审稿人意图：原始意见(EN) + 中文直译（直译不意译）+ 中文意图理解（摘要，非粘贴英文原文）。直译/中文回应必须由当前模型直接产出，脚本不自动出译文、只留占位符。
- Response：中文回复 + 对应英文（非逐字翻译）。
- 修改候选：revised EN 段落（聚焦匹配句周围片段）+ 中文译文；无修改写 `无`；定位字段（unit_id/路径/段落与句子 index）随 unit 写入。
- 修改说明：动作列表（添加/删除/修改+原因）+ `🔴 Core`/`🟡 Support` 汇总。
- 证据/图片：**Figure Prompt Block**，审稿人明确要求改/新增图片时，按 `references/figure-prompt-template.md` 生成结构化提示词，存入对应 comment unit JSON 的 `content.figure_prompt`。

## Atomic JSON Contract
Project layout:
- `project_root/project_state.json`
- `project_root/index.json` (hierarchical TOC source)
- `project_root/citation_registry.json` (new references added during response; see Step 2)
- `project_root/manuscript_edit_plan.md` (ordered revision plan; see Step 5)
- `project_root/units/000_email.json`
- `project_root/units/*.json` (one file per comment)
- `project_root/manuscript_units/*.json` (one section-level block per unit: heading + corresponding body text + corresponding figure captions when present)
- `project_root/si_units/*.json` (one section-level block per unit: heading + corresponding body text + corresponding figure captions when present)

Each unit follows `references/atomic-unit-schema.json`.
Each comment unit should carry `content.atomic_location` and must be renderable in HTML section 3.
Source atomic units (`manuscript_units` / `si_units`) must include:
- section-level units (`unit_type=section_block`, optionally `preamble_block`)
- section text and corresponding figure captions in the same section-level unit when available
- force split back-matter sections into independent units: `Author Contributions`, `Acknowledgements`, `Conflicts of Interest`, `References` (supports numbered headings like `6. AUTHOR CONTRIBUTIONS` and inline heading patterns)
- if no figure exists, figure-caption units can be absent
- optional image attachment extraction is allowed but not mandatory; section text + corresponding figure caption text is mandatory

## Rules
- Do not fabricate experiments, statistics, or references.
- If evidence is missing, explicitly mark `Not provided by user`.
- Keep tone professional and non-defensive.
- English reviewer responses must be fluent and natural, with low AI-style phrasing.
- Prefer short sentences for clear, natural rhythm; avoid long complex sentences by default, but do not split mechanically.
- If a reviewer comment requires adding references, literature retrieval follows topic-dependent routing: ① determine field — life science/medicine → PubMed CLI first (`esearch`/`efetch`, `~/edirect/`, `< /dev/null`, proxy `http://127.0.0.1:<PROXY_PORT>`); CS/AI/engineering → paper-search MCP first (`mcp__paper-search-mcp__search_arxiv` etc.) ② fallback to the other when primary yields no results. Auto-install PubMed CLI if `~/edirect/esearch` missing: `sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"`. **Windows:** the `sh`/`curl` installer and `< /dev/null` are not available in native cmd/PowerShell — run PubMed CLI under WSL, or skip it and use the paper-search MCP fallback instead.
- **严禁** 使用 `tavily`、`websearch` 或 `openalex`（pyalex）进行文献检索。
- **Serial Search (MANDATORY):** Execute all retrieval calls sequentially (PubMed CLI and paper-search MCP alike). Never parallelize search requests. Enforce ≥1s interval between consecutive calls.
- Do not create ad-hoc fixer scripts (e.g., `fix_gate_errors.py`, temporary patch scripts) during normal runs.
- When gate checks fail, directly edit the failing `project_root/units/*.json` fields and re-run checks.
- Keep one-page-per-comment structure.
- **回复信引文要用稳定锚点，别用硬行号/逐字长引文。** 本技能不改主稿，用户手工落地时措辞与位置会变；`response_en` 里若写死行号（"line 214"）或整段逐字引用 AI 拟的 `revised_excerpt_en`，用户一改就对不上。改用稳定锚点定位：章节名 + 小节 + 一句关键原句（"in the Methods, the paragraph beginning 'Cells were cultured...'"），只引最短必要的关键短语而非整段。`revised_excerpt_en` 仍照常写（供 edit_plan 用），但**正文回复对读者的指路**走锚点。
- All copy buttons in the UI must use Chinese label `复制`.
- Frontend design specifications are hardcoded in `scripts/build_full_package.py`'s `render_html()`; AI does not need to write HTML. Full spec is in `references/output-template.md`.
- Quality gates must fail when:
  - `revised_excerpt_en` is placeholder/empty (unless explicitly running with a relaxed gate mode)
  - `revised_excerpt_en` is identical to `original_excerpt_en`
  - unit status indicates `needs_manual_revision`
- If `comments_docx` fails to parse (corrupt file, encoding error), abort immediately and report the exact error; do not proceed to atomization.
- If a reviewer comment cannot be matched to any manuscript paragraph (location confidence below threshold), set `atomic_location.confidence = "low"` and mark the unit `needs_manual_revision`; do not fabricate a location.
- Gate fix loop must not exceed **3 iterations**; if gate still fails after 3 direct JSON edits, halt and report remaining failures to the user with a list of unresolved unit IDs.
- **AI Style Control:** English responses must avoid AI-typical phrasing patterns.
  - **强度说明（先读）：** 分三类。**AI 套话主干（硬）**，即空致谢/对冲词/填充语/模板化重复，是真的 AI 味，必须清。**去AI必禁三项（硬门禁，禁止使用）**，即破折号（`—/——/em-dash`）/ scare quotes / 解释性冒号，`risk_check.py` 命中即 FAIL（hard risk、pipeline-blocking，exit 1），必须清零。**句式偏好（软提示，别机械削平）**，即单句长度、-ing 分词，是**倾向性提醒不是硬门禁**：真人写的 rebuttal 里长句、分词从句本就是常态，为了压指标把自然句子剁碎反而写出更假的"防 AI 腔"。这几项按语感判断，明显堆砌才改；`risk_check.py` 对它们只报 WARN、不阻断。
  - **HTML/代码结构引号豁免（去 scare quotes 只管正文散文）：** 本回复包以 HTML 输出，其中 HTML 标签、属性、内联样式与代码里的**结构性双引号**（如 `id="sec-1"`、`class="panel"`、`<a href="...">`）是**代码语法，不是 scare quotes**，**一律不得删除、改写、转全角或转弯引号**——动了会破坏 HTML 渲染。"禁 scare quotes / 禁双引号"仅针对散文里包裹词/短语的引号，绝不触碰 markup 与代码。
  - Hedging overuse: "it is important to note that", "it should be noted that", "notably", "importantly"
  - Empty appreciation: "we greatly appreciate your insightful comments", "this is an excellent suggestion"
    - **外交缓冲豁免（仅 Push back / Partial 基调）**：rebuttal 里适度致谢与缓冲是不激怒审稿人的润滑剂，不算"空致谢"。反驳/部分接受的 unit **允许一句**克制的开场缓冲，`decision-rules.md` B 段推荐句式如 "We thank the reviewer for this valuable comment." / "We appreciate this suggestion; however, ..." 是**允许**的。禁的仍是：副词叠加的浮夸致谢（"we greatly/sincerely/deeply appreciate"）、`this is an excellent suggestion`、以及 ≥3 条回复用同一句致谢开头。缓冲句之外仍须紧跟实质回应，不得只致谢不作答。`risk_check.py` 的 `ai_appreciation` 正则已按此放行无副词的单句致谢，两文件口径一致。
  - Filler phrases: "in order to", "we would like to point out that", "as the reviewer rightly noted"
  - Structural repetition: ≥3 responses must not open with the same template sentence
  - **（软）English sentence length — 倾向 ≤30 words/句。** 一句明显冗长（>30 词且塞了多重从句）就拆，但**别为压指标机械剁句**：意思连贯的一个长句好过三个断句。绝不靠删必要内容达标。`risk_check.py` 只 WARN。
  - **（软）-ing participial clause — 少用逗号挂 -ing 分词收尾**（如 ", reflecting our commitment to…", ", ensuring that…"）：这是常见 AI 尾巴，堆多了显假；但真人也用分词从句，**偶尔一句自然的分词不必强拆**，明显成串堆砌才改。
  - **（🔴 硬门禁）Decorative em-dash — 破折号禁止使用**（如 "This result—while preliminary—suggests…"）：`—/——/em-dash` 一律禁用，改用逗号、句号或拆句。`risk_check.py` 命中即 FAIL（hard risk、pipeline-blocking，exit 1），必须清零。复合词连字符（"dose-response"）与数值区间（en-dash）不受影响。
  - **（🔴 硬门禁）Scare-quote — 禁给普通词/自造词加引号暗示新颖或反讽**（如 "robust" findings、"novel" approach）：`risk_check.py` 命中即 FAIL（hard risk、pipeline-blocking，exit 1），必须清零。豁免：首次定义术语、逐字引用审稿人原话、约定俗成的固定表达。
  - **禁比喻与连续排比（写作纪律，硬性遵守；脚本暂不检测）：** 回复正文禁任何比喻（no metaphors/similes；如"如同/像…一样"、like…/as if…/serves as a bridge/cornerstone）；禁连续≥3句相同起始词或句式框架的排比（parallel structure repeated across 3+ consecutive sentences；≥3 responses 同模板开头已另有禁令，此条管句子级）。此为模型写作纪律，`risk_check.py` 暂不检测、不 FAIL。
  - **Explanatory-colon ban:** do not use the pattern "concept: explanation" as a decorative sentence structure (e.g., "Main revision: we added a new control group"). Legitimate colons include ratios (2:1), clock times, list lead-ins, section headings, and figure labels ("Figure 3A:").
  - `risk_check.py` scans for these patterns automatically (including sentence length and -ing clause detection); WARN-level issues should be fixed before delivery
- **Chinese response style (中文回复规则，软提示同上)：**
  - **（软）单句倾向 ≤50 字。** 明显冗长的句子拆开更好读，但别为压字数把顺畅的句子机械剁碎，也不得为凑长度补冗余。
  - **（软）从句嵌套倾向 ≤2 层。** 尽量别三重嵌套（"因为…由于…鉴于…"类），读起来绕就拆。
  - `risk_check.py` 对 `response_zh` 执行中文句长检测（WARN 级、不阻断，>50 字告警）
### Domain Edge Cases
- **Reviewer recommends acceptance without comments** ("I have no major/minor concerns"): create a single email-only response acknowledging the reviewer; do not generate an empty Major/Minor section.
- **Two reviewers give contradictory suggestions** (e.g., R1 says "remove Section 3" vs R2 says "expand Section 3"): flag the conflict explicitly in both units' `notes_core_zh`; in the English response, acknowledge the divergence and state which direction is adopted with evidence-based justification. Add a `[CONFLICTING ADVICE]` marker in `manuscript_edit_plan.md`.
- **Reviewer writes comments in a non-English language**: translate the original comment into English first (store in `reviewer_comment_en`), then produce the Chinese translation from the original language (not from the English translation). Note the original language in a `source_language` annotation in the unit JSON.
- **Manuscript lacks standard section headings** (e.g., Letter/Communication format): atomize by paragraph breaks instead of headings; set `unit_type=paragraph_block` for manuscript units; use paragraph index as the primary location anchor.
- **Same paragraph targeted by 5+ comments**: in `manuscript_edit_plan.md`, merge all into one block sorted by reviewer priority (Editor > R1 > R2 > R3). If modifications conflict within the same paragraph, flag `[INTRA-PARAGRAPH CONFLICT]` and present alternative revision options for user decision.

## One-Shot Workflow

**执行模型（先读这段）：** 本流程是**两段式自动化 + AI 填空**，不是线性手工 13 步。
- `scripts/build_full_package.py`（pipeline 内部自动调用）一次性完成 Step 3/4/5/6/8 的机械部分：atomize 论文/SI 段落、在 `units/*.json` 写好**占位符**骨架（`【待AI...】` / `[AI_FILL_REQUIRED]`）、生成 `index.json`、并由 `render_html()` 渲出完整 HTML。**不要手工 atomize，也不要手写 index.json。**
- AI 的核心工作只有两件：①**Step 7** 把 `units/*.json` 里的占位符字段填成真实内容；②gate 失败时按报告**直接改对应 `units/*.json` 再重跑**。
- 两种调用时机，二选一：
  1. **分步**：先 `build_full_package.py` 出骨架（无条件写占位符、不跑 gate）→ AI 填 `units/*.json` → 再 `run_pipeline.py` 跑全部 gate；
  2. **串起**：一条 `run_pipeline.py` 走完 build→gate（首轮占位符会被门禁拦下，按报告填 units 后重跑）。
- 下列编号步骤是**逻辑顺序说明**，多数由脚本代劳；User Checkpoint 之间 AI 需停下确认。
- **跨平台命令说明（一次性）：** 本节及后续所有 `python3 scripts/...` 命令在 Windows 上请用 `python` 或 `py` 代替 `python3`（macOS/Linux 保持 `python3`）。

1. Parse all reviewer comments from `comments_docx_path`. The parser (`split_reviewer_blocks`) recognizes both `Reviewer #N` blocks and **Editor blocks** (`Editor:`, `Editor Comments`, `Comments from the Editor`, `Editorial Comments`, `编辑意见`, `编辑要求` 等) as **top-level nodes**. Editor comments become an independent `reviewer="Editor"` group, never merged into a reviewer.
1.5. **[User Checkpoint]** Print parsed comment summary table:
   - Top-level node count (Editor + Reviewers)
   - Per-node breakdown: Major / Minor / General comment counts (Editor comments usually fall under General)
   - Full list: reviewer × section × comment index × first 20 words of each comment
   Ask the user: "Comment parsing complete. Does this match the reviewer letter? (yes / abort / correct:N)"
   Do not continue to step 1.7 until user confirms.
   - **[对照原信数诉求]** 展示解析清单时，必须提示用户：「请拿**原始审稿信**逐段对照，我把某段拆成了 N 条，如果你觉得这段其实含多个要求(常见于连续散文/`(i)(ii)`/一段多问)，告诉我。」把"对照原文数诉求"从用户脑补变成 AI 主动摆出来。用户确认没漏才继续。

1.7. **[Strategy Planning]** Build a rebuttal strategy table before writing any responses:
   | Reviewer | # | Section | Strategy | Rationale | Data Needed |
   |----------|---|---------|----------|-----------|-------------|
   | R1 | 1 | Major | Accept | Valid concern, easy fix | None |
   | R1 | 2 | Major | Partial | Agree on X, push back on Y | New ref for Y |
   | R2 | 1 | Minor | Push back | Misunderstanding, cite existing evidence | None |

   Strategy options:
   - **Accept**: fully agree, will revise as requested
   - **Partial**: agree on some points, provide evidence/rationale for others
   - **Push back**: respectfully disagree with evidence-based justification
   - **Acknowledge**: thank reviewer for the suggestion, explain why not adopted (e.g., scope, data limitation)

   Rules:
   - Every comment must have a strategy assignment before proceeding
   - `Push back` requires at least one concrete evidence item (existing data, published precedent, or methodological rationale)
   - If strategy requires new literature, flag in `Data Needed` column for Step 2
   - **跨审稿人重复意见**：多个审稿人问同一件事时，在策略表标出这一组（如"R2.3 ≡ R5.1"），选一条作 canonical 完整作答，其余 Step 7 用 `cross_ref` 交叉指过去、答一次即可（见 `decision-rules.md` D 段），避免各写一遍导致口径不一致
   - Print the strategy table and ask user: "Strategy plan ready. Approve? (yes / adjust:R1.2 → Accept / abort)"
   - Do not proceed to Step 2 until user confirms
   - **用户确认后，将每条 comment 的 strategy 写入对应 `units/*.json` 的 `content.strategy` 字段**（脚本建骨架时留空字符串，由 AI 在此步骤填入）

2. If any comment needs additional citations (identified in Step 1.7 `Data Needed`), run retrieval per the Rules section's topic-dependent routing spec.
   - After retrieval, build `citation_registry.json` in `project_root/`:
     ```json
     {
       "original_ref_count": 42,
       "entries": [
         {
           "ref_number": 43,
           "title": "...",
           "doi": "10.xxxx/...",
           "pmid": "12345678",
           "authors": "First A, Second B",
           "year": 2023,
           "journal": "...",
           "source_provider": "pubmed-cli",
           "source_id": "esearch:query_string",
           "added_for_units": ["003_R1_major_01"],
           "retrieved_at": "2024-..."
         }
       ]
     }
     ```
   - `original_ref_count`: total references in the original manuscript (count from References section)
   - New reference numbers must start from `original_ref_count + 1`, sequential, no gaps
   - Each entry must record `source_provider` (e.g., `pubmed-cli`, `paper-search-mcp`) for traceability

   **2b. 新文献验真（只要本次新增了引用就必须做，两道关）：**
   > 反驳时甩一篇新文献最容易翻车，引了不存在、被撤、或根本不支持你论点的文章，审稿人一查就崩。所以新引比原稿引用把关更严，从 WARN 升到 fail-closed。
   1. **真实性硬核验**：`python3 scripts/citation_guard.py --project-root <root> --fail-on-unverified`（DOI/PMID 核对 + 撤稿检测；撤稿一律 FAIL，任一新引验不过即非零退出）。不带 `--fail-on-unverified` 的 pipeline 内 WARN 级不够，新引这里必须带上，验不过就删/换，别硬留。
   2. **支撑度核证**（引文是否真支持它挂的那句回复论点，而非只验真实）。对每条"新引 ↔ 它在 response_en 里支撑的论点句"，用**检索到的真实 abstract**（不看可编的 key_finding）判支撑度，写 `project_root/claim_evidence.json`（每行 `{section, claim_sentence, is_load_bearing, ref_id, retrieved_abstract, verdict∈support/weak/contradict/unknown, evidence_quote, user_confirmed}`），再跑：
      ```
      python3 "<技能>/scripts/citation_claim_check.py" --root <project_root>
      ```
      （对应 preflight 打印的 `CITATION_CHECK_CMD`。）

      **跨批复用（脚本自动做，AI 不必手动记字段）**。脚本核证前自动从项目根 `ref_evidence_cache.json` 回填缺失字段、核证后强制落盘，所以：
      - 已在别处验过的文献，这一行可留 `retrieved_abstract` 空，脚本按 abstract 是文献全局事实自动回填；不必为每行重抄一遍摘要。
      - 完全同一篇文献支撑完全同一句论点、且此前已确认过的，脚本自动复用已有 verdict 与确认，免掉重复反向验证。
      - 只有**新的（文献，论点）组合**才要重新反向验证并逐条人工确认；同一篇文献拿去支撑另一句论点仍算新组合，须独立判定，不复用旧确认。
      - 这条修的是"AI 漏写 `retrieved_abstract`/`verdict` 字段导致同一文献被反复核证"；缓存缺失或损坏时脚本回落全量核验，绝不放行。

      **承重论点句**（用来支撑 Push back / 关键主张的）若 verdict∈{contradict,unknown} 或取不到摘要 → **fail-closed（exit 2）硬拦**，禁止照此下笔；承重句还须逐条人工确认（`user_confirmed=true`）。回填复用不改门禁强度，凑不齐真摘要与确认照样 exit 2。背景陈述句只在表里批量呈现、不逐条阻断。取 abstract 走 Step 2 的检索工作流（PubMed CLI / paper-search MCP），不并行、间隔 ≥1s。
3. Atomize manuscript and SI into section-level units (heading + body + corresponding figure captions).
3.5. **[User Checkpoint]** Print a summary table:
   - Total section-level units extracted (manuscript count / SI count)
   - Any sections that failed to split or produced empty units
   Ask the user: "Atomization complete. Proceed to build comment units? (yes / abort)"
   Do not continue to step 4 until user confirms.
4. Build comment atomic units in `project_root/units/` and attach anchor-based links to manuscript/SI units.
   Also build email page JSON at `project_root/units/000_email.json` with the following content:
   - `subject`: `Response to Reviewers — [Manuscript Title]`
   - `opening`: thank the editor; state that a point-by-point response and revised manuscript are attached
   - `change_summary`: one bullet per reviewer, ≤2 sentences per bullet, summarizing major revisions made
   - `closing`: restate willingness to provide further revisions if needed
   - Tone: professional, concise, non-defensive; English only; no Chinese in email body
5. Build `manuscript_edit_plan.md` **skeleton** in `project_root/` (Step 5 = 建骨架；Step 7 后回填真值，见下).
   - The plan must be sorted by manuscript original order (ascending `manuscript_paragraph_index`).
   - Each row must include:
     - `comment_unit_id` / reviewer and major-minor info
     - target document (`manuscript` / `SI` / both)
     - section heading
     - paragraph index
     - one Word-search key sentence (`Word Find key sentence`)
     - exact to-be-replaced snippet (if available)
     - `revised text to insert` (EN, and ZH if provided)：**此列 Step 5 时留占位符 `[PENDING Step 7]`；Step 7 完成后运行 `python3 scripts/state_manager.py aggregate-edit-plan --project-root <root>` 自动聚合回填**。
     - action type (`添加` / `删除` / `修改`)
   - When multiple comments map to the same paragraph, merge into one ordered block with sub-items.
   - If a comment is global (language polishing, full-figure consistency), put it in a separate `Global edits` section and explicitly mark as non-localized.
6. Build hierarchical index in `project_root/index.json`.
7. Fill all AI-required fields in each comment unit JSON. Execute in sub-steps:

   **改坏可回滚：** 每次大改 `units/*.json` 前先 `python3 scripts/state_manager.py snapshot --project-root <root>` 建还原点；改坏用 `python3 scripts/state_manager.py rollback --project-root <root>`（默认还原最近一次快照）。快照存于 `logs/snapshots/units_<时间戳>/`。


   **7a. 排序与分批：**
   - 按 reviewer 分组，每组内先 major 后 minor 后 general
   - 如 comment 总数 ≤15，一次性处理；>15 条时分批（每批 ≤10 条），每批完成后写盘再继续下一批
   - 每条 comment unit 需填写以下 8 组字段（参照 `references/atomic-unit-schema.json`）：

   **7b. 逐条填写（每条 comment unit）：**
   0. 读取 `content.strategy` 字段（Step 1.7 已写入），据此选定回复基调：Accept→直接致谢+落实；Partial→分点肯定+部分推回；Push back→证据先行+礼貌否定；Acknowledge→解释为何未采纳。**Push back / Partial 必须动用外交措辞 craft**（`decision-rules.md` C 段）：反驳前先承认对方顾虑的合理性、用部分让步软化整体拒绝、把审稿人自己的话引回来 reframe。硬顶最招审稿人反感，先给台阶再讲道理。
   1. `content.reviewer_comment_zh`：直译审稿意见（中文，不改写不概括）
   2. `content.reviewer_intent_zh`：理解审稿人真实意图（中文摘要，≤3 句）
   3. `content.response_en`：英文回复（遵循 `references/decision-rules.md` 的基调选择、外交措辞 craft（C 段）与句式规范；短句优先见 Rules）。**跨审稿人呼应去重**：本条若与另一条已完整作答的意见问同一件事，填 `content.cross_ref`（如 `"Reviewer 2, Comment 3"`），response_en 用 "As noted in our response to Reviewer 2, Comment 3, ..." 交叉指过去、不重复展开答案（详见 `decision-rules.md` D 段）；canonical 那条把答案与落点写全。
   4. `content.response_zh`：中文回复（与英文回复对应，非逐字翻译，需自然通顺）
   5. `content.revised_excerpt_en`：修改后的英文正文段落（如无需修改写 `无`）
   6. `content.revised_excerpt_zh`：修改后的中文翻译（如无需修改写 `无`）
   7. `content.modification_actions`：修改动作列表（每条含 `action_type` + `target` + `reason`）
   8. `content.notes_core_zh` + `content.notes_support_zh`：核心🔴和辅助🟡修改说明

   **7c. 质量标准：**
   - 英文回复：≥3 句、≤300 词；必须包含致谢 + 具体行动描述
   - 中文回复：与英文回复信息等价，但措辞独立，不是机械翻译
   - revised_excerpt：必须与 original_excerpt_en 有实质差异（不能只改标点）
   - 禁止虚构实验、统计、引用（遵循 Rules 中的红线）

   **Step 7 Mini-Gate（填写完成后，进入 Step 8 前执行）：**
   - 抽取前 3 个 comment unit，检查以下字段是否已填（非占位符）：
     - `content.reviewer_comment_zh`（非 `待AI` / `AI_FILL_REQUIRED`）
     - `content.response_zh`（非空、非占位符）
     - `content.revised_excerpt_en`（非空、非与 `original_excerpt_en` 相同）
   - 如发现任何占位符或空值，**停止并列出未填字段**，等待修复后再继续
   - 抽查通过后方可进入 Step 7.5

   7.5. **[User Checkpoint — Quality Review]** 展示回复质量摘要供用户审查：
   - 逐条打印：每条 comment 的 unit_id | reviewer | section，紧跟**该条审稿意见摘要 + 完整 `response_en` 全文**（不截断，前 50 字看不出是否答非所问/避重就轻/只承诺不落实，这是唯一人肉关口，必须给用户看全）| revised_excerpt 状态（有修改/无/needs_manual）
   - 标记需人工关注的条目：`needs_manual_revision` 的 unit、`confidence=low` 的定位、revised_excerpt_en 为 `无` 但 comment 明确要求改文的
   - **兑现"承诺↔落点对照表"承诺（监工卡第 3 条）**：生成并摆给用户：
     ```
     python3 scripts/consistency_check.py --project-root <root> --emit-table <root>/commitment_landing_table.md
     ```
     脚本把 `response_en` 里每一句承诺动作逐句列成表（承诺句 ｜ 类型[🔴实质新增/措辞] ｜ 落点[有/无] ｜ 位置[modification_actions/revised_excerpt_en/中文字段/交叉引用/无]）。**把该表原样贴给用户**，让用户一眼看清哪些是"嘴上说了、稿里没做"。落点为"无"且类型为🔴实质新增的行 = 硬伤，必须在本步补落点或改回复（该项也会让 consistency_check 非零退出）。`cross_ref` 交叉指引的条目落点记为"见交叉引用"，由 canonical unit 承载、不算漏。
   - 问用户："Response content ready for rendering. Review OK? (yes / fix:unit_id / abort)"
   - 用户可指定修改特定 unit，修改后重新展示该 unit 摘要
   - 确认后方可进入 Step 8

   **Step 7 后 → edit_plan 回填（在进入 Step 8 前执行）：**
   ```
   python3 scripts/state_manager.py aggregate-edit-plan --project-root <root>
   ```
   脚本遍历 `units/*.json`，把每个 unit 的 `revised_excerpt_en`（以及 `revised_excerpt_zh`，若有则以 ` ／ ` 拼接）写入 `manuscript_edit_plan.md` 对应行的 `revised text to insert` 列，替换 `[PENDING Step 7]`。`revised_excerpt_en == "无"` 的 unit 写入 `无改动`，不计为 PENDING。输出含两行关键信息：`filled: N`（已回填数）和 `still PENDING: N`（未填数）；若有 PENDING，脚本列出具体 unit_id 并以退出码 2 提示，需补填后重跑。回填完成后 edit_plan 即为可直接用于手工 track-changes 的完整操作清单。

8. Render single HTML with left hierarchical TOC + right content pane from updated atomic JSON.
9. Run hard gate checks, citation checks, and HTML checks before delivery.
   - **判读：** `scripts/run_pipeline.py` 串行自动执行全部 gate（顺序与职责详见 Scripts 段）；退出码 `0` = 全部通过；非零时 stdout 打印 `PIPELINE: FAIL (step=..., code=...)` 及失败 unit。按失败信息直接改对应 `units/*.json`（≤3 次上限，见 Rules）后重跑。Do not run gates manually one-by-one; do not generate extra fixer scripts.
   - **注：** `citation_ref_tracker` / `citation_guard` 在 pipeline 内为 WARN 级（未带 `--fail-on-undefined` / `--fail-on-unverified`，仅撤稿引用会直接 FAIL），`PIPELINE: PASS` 不代表引文零缺陷，RR1/RR2 须在 DoD 委托盲检阶段单独确认。
10. Run final consistency report.
11. Write checkpoint + transaction logs to `project_root/logs/`.
12. Sync unit state map to `project_root/logs/unit_state.json`.
13. Write reproducibility snapshot to `project_root/logs/version_snapshot.json` (hashes for key scripts + outputs).

## ❌ 反例黑名单（Anti-Patterns）

- ❌ 越界改主稿或生成 Word track-changes 稿，本技能只出回复包（HTML），改稿一律落到 `manuscript_edit_plan.md` 由用户手工执行。
- ❌ 虚构实验、统计或引用来回应意见；证据缺失时不写 `Not provided by user` 而是编造数据。
- ❌ response_en 里承诺的动作（we added／clarified／revised）在 `modification_actions` 或 `revised_excerpt_en` 找不到落点（承诺↔落点不一致，consistency_check WARN 必须消除）。
- ❌ 主 agent 自评承诺↔落点一致性与 DoD 清单，必须委托独立上下文subagent盲检，delegate_review verify 未 exit 0 就出具回复信。
- ❌ 漏回任何一条意见，尤其把 Editor 意见并入某个 Reviewer，而非作为独立顶层节点。
- ❌ 用 tavily、websearch 或 openalex（pyalex）查文献；生命医学不走 PubMed CLI、CS/AI 不走 paper-search MCP。
- ❌ 并行发起检索请求，必须串行且相邻调用间隔 ≥1s。
- ❌ 把 `revised_excerpt_en` 留作占位符、留空、或与 `original_excerpt_en` 完全相同（仅改标点也算未改），strict_gate 必拦。
- ❌ 交付时残留 `待AI` / `AI_FILL_REQUIRED` / `[PENDING Step 7]` 占位符，或 Step 7 后漏跑 `aggregate-edit-plan` 回填 edit_plan。
- ❌ 英文回复堆套话（硬）：空致谢（we greatly appreciate your insightful comments）、对冲词（it is important to note that）、填充语、≥3 条回复用同一模板开头；解释性冒号（"Main revision: we added..."）。
- 🔴 破折号（—/——）硬门禁、禁止使用：`risk_check.py` 命中即 FAIL（hard risk、pipeline-blocking，exit 1），必须清零。
- ⚠️ 句式软项（WARN 非 FAIL，别机械削平）：英文单句明显 >30 词、成串 -ing 分词挂句、中文单句明显 >50 字或三重嵌套，明显堆砌才改，真人常态句子不必强拆（见 AI Style Control 强度说明）。scare quotes 不在软项，属去AI必禁三项硬门禁。
- ❌ 意见无法匹配到任何段落时硬编一个 location，而非置 `confidence=low` 并标 `needs_manual_revision`。
- ❌ gate 失败时新建临时修复脚本（fix_gate_errors.py 之类）或逐个手跑 gate，应直接改 `units/*.json` 重跑且修复循环 ≤3 次。
- ❌ Push back 策略的 unit 没有任何具体证据（引文／数据／方法学依据）就硬顶审稿人。

## Definition-of-Done: 回复包收口自检清单

> **硬规则：清单未逐项确认通过，不得向用户声明"回复包完成"。** 能脚本核的项直接跑对应 gate；人工项逐条确认。

**🔴 委托盲检（不得主 agent 自评）**：你刚写完回复包，自评容易失真，会想当然地判自己通过、还容易漏项。**承诺↔落点一致性尤其如此**，主 agent 写了回复再自核"承诺有没有落地"几乎必然失真。`run_pipeline.py` 退出码 0 后、声明完成前，必须把 DoD 清单**委托给独立上下文的subagent盲检**，自己不直接打勾：

🔴 出具前置闸口：delegate_review verify 必须 exit 0（含 RR14 结构完整性），否则不得向用户出具 response letter。

1. 生成任务包：`python scripts/delegate_review.py pack --checklist references/dod_checklist.json --gate response-dod --files <project_root>/units/*.json --comments <comments_docx_path>`（Windows PowerShell/cmd 不展开 `*.json`，需把 `units/` 下的 json 显式逐个列在 `--files` 后，或在 WSL/bash 里运行）
   - **必须带 `--comments`**：把**原始审稿信全文**嵌进任务包，盲检subagent才能对照原信逐条点名核对，被 fallback 塌成一条 general unit 的多诉求意见(连续散文/`(i)(ii)`/罗马数字/项目符号/一段多诉求)只有对照原文才查得出漏回。不带 `--comments` 时盲检只能看已生成的 units，被吞掉的意见永远发现不了(RR7/RR14/RR15 形同虚设)。
2. **派一个独立subagent**（Claude Code 用 `academic-blind-reviewer`；其他平台派通用subagent），把任务包原样给它、**不要给它回复包的写作上下文**，要求按任务包返回 JSON 数组。
3. 校验返回：`python scripts/delegate_review.py verify --checklist references/dod_checklist.json --gate response-dod --return <subagent返回.json>`；退出码非 0（任一缺项/fail/无证据）= **fail-closed**，据subagent证据修复后重跑，**未过不得声明完成**。
4. **盲检通过后 HALT，先摆结论再出信（不得静默直接出回复信）**：verify exit 0 后，把 DoD 逐项结论摆给用户，每项 RR 的通过/告警状态 + subagent给的关键证据一句话（尤其逐条覆盖、承诺↔落点、反驳有据、新引验真几项），并附 Step 7.5 的承诺↔落点对照表。然后停下问用户：「盲检已过，上面是逐项结论，确认出具回复信吗？(yes / 看某项证据 / 改某条)」**等用户明确确认后才生成/交付回复信**。

⚠️ **盲检降级告警**：若环境派不出真正独立的subagent，**绝不能同一 AI 自问自答冒充盲检**。明确告诉用户「本环境盲检不可靠，请你亲自复核：每条审稿意见是否都正面回应了、有没有漏回、承诺的修改是否都有落点」，交回用户。

**本节完整 DoD 判据（全部核查项 + 脚本命令）以 `references/dod_checklist.json` gate=`response-dod` 为唯一真源（16 项 RR1-RR16）**：盲检subagent据此逐项核、能脚本核的先跑脚本，退出码非 0 即 fail-closed。含 RR1-RR6 通用（引文对应/新增引用验真+支撑度核证/主线对齐/占位清零/去AI 硬禁三项标点/字数）、RR7-RR14 特有（逐条覆盖无遗漏 / Editor 层独立 / Strategy 基调 / **承诺↔落点一致（`consistency_check.py`，独立subagent核、主 agent 不得自评）** / edit_plan 回填 / 反驳有据 / 各 gate 全通 / RR14 结构完整性），及 **RR15 逐条实质回应盲检（每条意见含各子问点是否被实质回应，而非答非所问/避重就轻/只承诺不落实）**、RR16 字符级硬门禁（仅扫作者写的 Response 正文、不扫审稿人原话，misspelling/chinese_punct/subsup_bare 零容忍，`proofread_response.py`）。此处不再内联清单，避免与真源 drift。

## Re-Render Workflow
After manual editing of any unit JSON:
1. Keep `index.json` unchanged unless hierarchy changes.
2. Rebuild HTML only using `scripts/render_from_atomic_json.py`.
   - If render fails (JSON parse error / missing required field): fix the offending `units/*.json` directly, then re-run. Do not regenerate from scratch.
   - If render fails (script not found / import error): check `scripts/` directory exists and dependencies are installed; fall back to `scripts/run_pipeline.py --allow-placeholder` as last resort.
3. Sync state using `scripts/state_manager.py sync --project-root .`.
   - If sync fails: run `scripts/state_manager.py show --project-root .` to identify out-of-sync units; fix manually, then retry sync.
4. Run `scripts/final_content_gate.py` and `scripts/html_format_check.py` on the newly rendered HTML.
   - Gate checks are mandatory even for single-unit edits.
   - If gate fails, fix the offending `units/*.json` directly and re-run from step 2. Do not skip.

## Scripts
**入口：** `scripts/run_pipeline.py`，一条命令串行执行 preflight → build → 全部 gate → consistency report → html gate。5 个必需参数：`--comments` / `--manuscript` / `--si`（可选）/ `--project-root` / `--output-html`。

最小可执行示例（占位符首轮预览，加 `--allow-placeholder` 放宽内容门禁出骨架；正式交付去掉该 flag）：
```bash
python3 scripts/run_pipeline.py \
  --comments /path/to/reviewer_comments.docx \
  --manuscript /path/to/manuscript.docx \
  --si /path/to/supplementary.docx \
  --project-root /path/to/project_root \
  --output-html /path/to/project_root/reviewer_response.html \
  --allow-placeholder
```
无 SI 时省略 `--si`。AI 填完 `units/*.json` 后，去掉 `--allow-placeholder` 重跑同一命令即为正式交付。

各 gate 由 `run_pipeline.py` 串行自动调用，正常运行无需手动单独跑。按执行顺序：
- `strict_gate.py`：硬门禁，检查 `revised_excerpt_en` 非空/非占位符/与原文有实质差异、`needs_manual_revision` 状态
- `final_content_gate.py`：内容完整性，检查所有 `待AI` / `AI_FILL_REQUIRED` 占位符是否已填（`--allow-placeholder` 仅骨架预览阶段）
- `consistency_check.py`：① 禁用词/冲突术语检查；② **承诺↔落点一致性**：`response_en` 中承诺的动作动词（含 `we (have/now) added/performed/conducted/provide/cited/discussed...` 及被动 `changes were made`）须能在同 unit 的 `modification_actions` 或 `revised_excerpt_en` 找到对应落点。**承诺新增实质内容（新实验/分析/图表/数据/对照）却无落点 = FAIL（脚本非零退出，阻断 pipeline）**；措辞类承诺无落点 = WARN（非阻断）。③ **跨审稿人呼应豁免**：unit 的 `content.cross_ref` **能解析到一个真实存在、且不是自己的 unit** 时（支持 `"u-1"` 式 unit_id 与 `"Reviewer 2, Comment 3"` 式描述，后者按 reviewer+comment_number 匹配），其承诺落点由被指向的 canonical unit 承载，本 unit 免落点检查（避免"As noted in our response to Reviewer 2..."被误判漏落点）；**指不到任何 unit（幽灵目标）或指向自己 = 不豁免**，照常按无落点判定。④ **`--emit-table <path>`**：把逐句承诺列成面向用户的 markdown 对照表（承诺句｜类型｜落点有/无｜位置），Step 7.5 摆给用户
- `final_consistency_report.py`：生成统计报告（units 数量、链接率、缺失 excerpt 计数）
- `html_format_check.py`：HTML 结构完整性
- `risk_check.py`：检测虚构实验/统计、过度承诺、AI 式套话、跨 unit 结构重复
- `citation_guard.py`：验证 `citation_registry.json` 新增引用真实性（DOI/PMID/撤稿检测）；`--offline` 跳过联网核验，**此时所有条目一律记为未核验**（每条 `verified` 恒 false、报告 `status` 为 `unverified`），既证明不了文献真实存在也查不出撤稿，只能用于测试或网络故障应急，不是交付口径。报告写入 `logs/citation_guard_report.json`，顶层结构为 `{"status": "pass"|"warn"|"unverified", "verified": N, "failed": N, "retracted": N, ...}`（注意：无 `report.ok` 嵌套层；判断通过用 `status == "pass"`，判断撤稿用 `retracted > 0`；`unverified` 表示这一轮压根没验，不得当通过）
  - **已知限制（诊断提示在本技能里看不到，但请求照打）**：在线跑（不加 `--offline`，即默认）时，对每条没验过、带 DOI/PMID、标题≥3 个词的文献，底层核验会额外拿标题上网回查一次，本可给出「这条的 DOI/PMID 可能填错了，线上同名文章是这个」之类的提示；但本技能的报告只保留固定字段，这些提示会被直接丢掉——**请求照打、结果照扔**，白花一次网络往返和限流额度。**判定结果完全不受影响**（验过/没验过/撤稿一条都不会变），只是慢一点。所以遇到验不过的条目，直接看报告里每条的 `failures` 排查，别指望有诊断提示；只想快速过一遍时可以加 `--offline`（离线不打这些请求）。
- `citation_ref_tracker.py`：交叉验证 `[N]` 引用编号一致性（未定义引用、编号间隙）

字符级硬门禁（DoD RR16 单独跑，不在 pipeline 内自动调用）：
- `proofread_response.py`：抽取每个 `units/*.json` 的**作者 Response 正文**（仅 `content.response_en` / `response_zh`，绝不扫 `reviewer_comment_*` 审稿人原话），dump 到临时目录后调 `proofread.py --fail-on misspelling,chinese_punct,subsup_bare`，纯读不写回。`ok=false` 即命中拼写错/中文标点漏入英文/上下标裸写，须修复后重跑。em dash 与智能引号不计入 chinese_punct（`proofread.py` 已排除），故引用审稿人英文原话不会误伤。

Re-Render 单独脚本：`render_from_atomic_json.py`（重渲）、`state_manager.py`（状态同步 `sync`/`show`/`set`/`init`；改 units 前后用 `snapshot`/`rollback` 建还原点与回滚）。

## References
按需加载，不要全部预加载：
- Atomic schema: `references/atomic-unit-schema.json`，单元 JSON 结构定义（原子化构建时参考）
- Atomic workflow: `references/atomic-workflow.md`，原子化流程详细说明（首次使用或遇到异常时）
- HTML structural skeleton: `references/html-template-full.html`，主交付物布局骨架（grid + sidebar + content 结构）；实际渲染由 `scripts/build_full_package.py` 的 `render_html()` 生成完整 UI（含折叠/展开、拖拽分割线、复制按钮、severity 背景色、localStorage 持久化）
- Single-comment fill template: `references/html-template.html`，单条 comment 的占位符填充骨架，仅配合 `html-fill-guide.md` 手工填单页时使用；与上面的整包骨架 `html-template-full.html` 不同
- Output contract: `references/output-template.md`，输出规范（核对交付物结构时）
- Decision rules and sentence patterns: `references/decision-rules.md`，回复措辞决策规则（撰写英文回复时）
- HTML filling notes: `references/html-fill-guide.md`，`html-template.html` 占位符填写注意事项（手工填单页或渲染异常时）
- Figure prompt template: `references/figure-prompt-template.md`，图片修改/新增时的结构化提示词模板（Output Contract 第3块图片需求时）

## 发现 AI 跳步/漏做了怎么办（用户自救）
当你怀疑 AI 把审稿意见拆漏了、承诺没落地、或用摘要糊弄你时，直接复制下面的话逼它返工：
- 「Reviewer X 那段我看像有 3 个问题，你只拆了 1 条，重新拆」
- 「把你在回复里承诺的所有动作列出来，逐个告诉我在改稿清单哪一行落地了」
- 「这条回复我只想看它到底答没答审稿人的问题，把 response 全文贴我，别给摘要」
- Consistency rules: `references/consistency-rules.json`，`consistency_check.py` 默认加载的一致性规则集（无需手动引用，gate 自动读取）
