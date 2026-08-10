---
name: revise-sci
version: 2.29.6
description: 退稿/返修全管道，同时出逐条回复信+修改后正文docx+Patch修订。触发词：改稿、修改稿子、修订正文、退稿改进、返修、revise manuscript、major revision、minor revision、revise and resubmit、point-by-point response、revised manuscript。路由说明：与reviewer-response-sci区分，本技能同时改主稿+出回复包，后者只出回复不改稿；与gsw区分，gsw写新稿，本技能专处理已有稿子的审稿意见驱动修改。
---

# Revise-Sci

## Overview
Use this skill to turn reviewer comments, the original manuscript, SI, and attachments into two deliverables: a revised manuscript and a structured `Response to Reviewers`. Both come out in Markdown and Word.

The workflow is script-gated. Do not skip steps. Do not fabricate experiments, data, statistics, or references.
The comment parser accepts both atomic `comment-unit` HTML and reviewer-simulator style report HTML with critique lists.
The manuscript atomizer recognizes numbered section headings such as `1`, `1.1`, and `2.3.4` even when the source Word paragraph style is not a formal heading style.

## 开场监工卡（每次启动必打印，逐字给用户）

> 返修改稿最容易在这几处翻车，AI 会做但**只有你能核对是不是真做到了**。启动本技能时必须原样打印这张卡：
>
> 1. **拆意见别信 AI 说全了**：拆完 AI 应给你一份意见清单，你拿原始审稿信**数条数**：有没有被合并成一条、有没有整条漏掉。数目对不上就是漏了。
> 2. **改原意要逐处盯**：每一处改动，AI 应贴「原句 → 改后句」，你确认意思没变、没夹带你没同意的新结论。看不到对照就别放行。
> 3. **覆盖看对照表**：交付前 AI 应给「意见 × 是否回复 × 是否改稿 × 结局」对照表。「改稿」列为空**但结局标 `push_back`（有意驳回不改）**的是正常的，不是漏；真正的漏是：某条既没回复、结局又不是 `completed`/`push_back`/`需作者确认`。分清「有意不改」和「漏改」。
> 4. **缺证据写"需作者确认"是正常的**：AI 没有你的数据/实验时应写「需作者确认」等你补，这不是 bug，请你补齐，别当故障报错。
> 5. **门禁 PASS 只保形式**：门禁只查格式/覆盖/红线这类机械项，**改得对不对、说理通不通，得你自己核**，别把 PASS 当"改对了"。

**【Python 解释器探测·开工第一件事，一次探测全程沿用】** 本文命令里写的 `python3` / `python` 只是 macOS/Linux 的习惯写法，不是硬性要求。动手前先跑一次 `python3 --version`：
- 打印出正常版本号 → 本次会话所有命令照抄用 `python3`。
- 报 command not found、没有任何输出、或弹出应用商店 → 改跑 `python --version`，能出版本号就把后续所有命令里的解释器统一换成 `python`。注意 Windows 自带一个 0 字节的 `python3` 占位程序，`python3 --version` 弹商店或无输出就是撞上了它，**不算有 python3**，按"没有"处理（用户也可在 设置 → 应用 → 应用执行别名 里关掉 `python3.exe`）。
- 反过来 `python` 出不了版本号就换 `python3`（macOS 12.3 起系统不再自带 `python`）。
- 两个都出不了版本号 = 这台机器没装 Python，停下来告诉用户先安装，不要硬跑。
- 探测只做这一次，之后所有命令沿用同一个名字，不要每条命令都再试。

## 跨会话接续（每次开局先跑，与监工卡是两件事）

监工卡是「启动提醒」，接续报告是「续上上一会话的进度」。**每次进入本技能、且 `project_root` 已存在时，先跑接续命令再动手**：

```bash
python "<技能>/scripts/session_journal.py" resume --root <project_root>
```

`env_preflight.py` 会把这条打印为 `RESUME_CMD`（连同 `LOG_CMD` / `CITATION_CHECK_CMD`，均为解析好的绝对路径）。读完接续报告后，**据它跟用户打接续握手**：复述当前 phase、已处理的 comment、以及 `decisions_log.md` 里用户历次要求，问「我接着做 <下一步>，对吗？还是先插新要求？」**等用户确认再继续**。

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
- `docx-review-comments`: ordinary reviewer comments exported from email or web into a `.docx`. The parser expects reviewer / major-minor / numbered-comment structure and keeps multiline comments inside one unit.
- `docx-review-letter`: ordinary decision-letter style `.docx` files where the structure is usually `editor email -> Reviewer #N overall statement -> numbered comments`. The parser now distinguishes editor statements, reviewer overall statements, and actionable numbered comments instead of collapsing them into a single comment stream.
- `reviewer-simulator-html`: HTML generated by `reviewer-simulator`. The parser reads `critique-section / critique-list` blocks and preserves `comment_title`, `problem_description`, `evidence_anchor`, `root_cause`, and `author_strategy`.
- `reviewer-response-sci-html`: HTML generated by `reviewer-response-sci`. The parser extracts the original reviewer comment plus seeded `response_en/zh`, `original_excerpt`, `revised_excerpt`, and `revision_location`, then feeds those seeds back into localization and response drafting.
- `atomic-comment-html`: already-atomic HTML with `comment-unit` nodes. Existing `comment_id` values are preserved.
- `no-comments-manuscript-only`: manuscript exists but reviewer comments are not provided yet. This is not a revise branch by itself; it is an intake state that must first ask whether to bootstrap comments via `reviewer-simulator`.

For `docx-review-letter`, the workflow must:
1. distinguish top-of-letter editor statements from numbered editor action items;
2. capture reviewer-level `Overall statement / General assessment / Reviewer statement` text as reviewer-summary seeds, not as the first numbered comment;
3. preserve those statement seeds into downstream response rendering so the exported response package can still show editor/reviewer context explicitly.

For `reviewer-response-sci-html`, do not trust the incoming response package at face value:
1. treat seeded response/revision content as structured hints rather than auto-approved final output;
2. prioritize seeded location/original-excerpt hints when localizing the target paragraph;
3. still rerun `revise -> polish -> literature/reference checks -> strict_gate` before delivery.

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
Always produce:
- `response_to_reviewers.md`
- `response_to_reviewers.docx`
- revised manuscript markdown at `output_md_path`
- revised manuscript Word at `output_docx_path`
  - **默认 in-place 保原稿格式**：当原稿是 `.docx` 时，改后稿基于原始 manuscript docx 编辑，未被改的段落、表格、图片、样式、对齐**原样保留**，只替换被点名改写的段落的文字，并按行内标记（`*斜体*`/`**粗**`/`<sup>`/`<sub>`）重建 run、继承原段落基础字体（font.name/size/eastAsia）。定位/身份对不上时 **fail-closed 硬停**：`export_docx.py` 退出码 3，把拒绝原因和两个选项（① 重跑加 `--allow-rebuild-fallback` 接受重排版本；② 修锚点后用未改动原稿重跑）显式打给用户，**不再默认静默降级为 md 全量重建**（那会丢原稿表格/图位/对齐并按期刊模板重排，用户却不知情）。只有显式传 `--allow-rebuild-fallback`（run_pipeline 同名 flag 透传）才回退 md 全量重建。原稿非 docx 或无原稿时正常走 md 全量重建（legacy fallback，非降级）。导出模式记录在 `project_state.json` 的 `outputs.manuscript_export_mode`（`in-place` / `in-place-tracked` / `md-rebuild`）。`response_to_reviewers.docx` 不受影响，维持现有固定样式脚本（含 eastAsia）。
  - **可选 `--track-changes` 词级修订痕迹**（默认关闭，仅 in-place 生效）：改动段落按 original vs current 的词级 diff 写成带 Word 红蓝增删痕迹的 docx（`<w:ins>`/`<w:del>`，仅包住真正变化的词，行内斜体/上下标/粗体在痕迹两侧保留），导出模式记为 `in-place-tracked`。关闭时行为与原 clean in-place 完全一致。详见 Pipeline 段 `export_docx.py` 的 `--track-changes` 说明。
- `precheck_report.md`
- `issue_matrix.md`
- `manuscript_edit_plan.md`
- `final_consistency_report.md`
- `data/literature_index.json`
- `data/revision_claims.json`
- `data/synthesis_matrix.json`
- `data/synthesis_matrix_audit.json`
- `data/reference_registry.json`
- `data/reference_coverage_audit.json`
- `figure_index.json` / `reference_index.json`,反向抽取的图、参考交叉索引(每项含 cited_by 与 orphan_type)
- `abbreviation_index.json`,反向抽取的缩略语交叉索引(每项含 defined_count / used_count / orphan_type:undefined_use / duplicate_definition / title_abbreviation 为硬错,defined_unused 为软警告)
- `manuscript_index.md`,人读版图/参考/缩略语索引与孤儿汇总。启发式抽取,作审查辅助而非红线核验
- `figures/figure_NN.<ext>` + `figures/image_manifest.json`,从源 docx `word/media/` 解出的内嵌图(按 zip 出现顺序命名),供最终返修 docx 嵌回。仅二进制搬运,不做 OCR/图像识别;非 docx 输入则目录可能为空
- `manuscript_section_index.json` 每个 section 条目含 `figures` 字段:该节图注/裸图标题锚定的图清单(`figure_id` / `caption` / `image_file` / `source`)。图注文本落在哪节该图即归哪节(definitive);图号→图片文件走 manifest idx 启发式(zip 顺序 ≈ 阅读顺序),故图片绑定标 `image_binding: ordinal_heuristic`

## Pipeline
Run the scripts in this exact order:

```bash
python scripts/intake_router.py ...
python scripts/preflight.py ...
python scripts/atomize_comments.py ...
python scripts/atomize_manuscript.py ...   # 除切 section md 外,为每节写 figures 锚点(figure_id/caption/image_file/source);manifest 此时通常尚未生成,image_file 多为空,由 merge 阶段以 manifest 为准再解析
python scripts/manuscript_index.py --manuscript <manuscript_docx_path> --project-root <project_root> --units-dir units   # 反向抽取图/参考/缩略语交叉索引,辅助图文一致性、引用完整性与缩略语首展核查(产 abbreviation_index.json)。改稿合并后应对最终 output_md 重跑一次,使索引反映改后稿
python scripts/extract_docx_images.py --manuscript <manuscript_path> --project-root <project_root>   # 支持 docx 与 pdf,抠出内嵌图到 figures/,供最终返修 docx 嵌回(best-effort;pdf 需 PyMuPDF,缺失则优雅跳过;其他非 docx/pdf 输入自动 no-op)
python scripts/build_issue_matrix.py ...
python scripts/state_manager.py --project-root <project_root> refresh
python scripts/citation_guard.py ...   # if paper_search_results_path is provided
# 🔴 [意见清单核对·必停] atomize_comments 之后、revise_units 之前的强制关卡：见下方「## [意见清单核对·必停]（拆意见后、改写前的强制关卡）」。未经用户确认"条数对、无合并、无遗漏"，不得进入 revise_units。
python scripts/revise_units.py --project-root <project_root> [--paper-search-results <paper_search_validated.json>] [--comment-id <comment_id>]   # --comment-id 仅处理单条评论,用于迭代调试;默认全量
python scripts/build_literature_index.py --project-root <project_root> [--seed-index <writing_project_literature_index.json>]   # 不传 --seed-index：行为不变，从 global_id=1 重建库。传 --seed-index：复用撰写项目(gsw/review-writing)已有引文库作种子，**保留种子每条的既有 global_id**，本次返修新查到的文献按去重键(归一DOI>PMID>归一标题)与种子比对，命中种子的复用其编号不新增、真正新的从"种子最大 global_id + 1"续号追加，合并结果写 revise 自己的 data/literature_index.json。**只读种子、不写回撰写项目**(种子扩展语义)。种子读取兼容 gsw 松 schema(global_id/citation_number/id/number/ref_number 任一取号，都缺按数组顺序补号)与根级/data 下任意路径。
python scripts/matrix_manager.py bootstrap ...
python scripts/matrix_manager.py audit ...
python scripts/merge_manuscript.py --project-root <project_root> --output-md <output_md>   # md 全量重建(回退路径)时按各节 figures 锚点把图片 markdown 回填到对应节;fail-closed 防幻影删除:manifest 里有但未归到任何一节的图片全部回填到文末 "# Unplaced figures" 区并 stderr/JSON warn,绝不静默丢图。旧工程无 figures 字段则保持原纯文本拼接不变。注:in-place 导出路径不经此重建,图片在原稿内原样保留。图号→图片文件绑定走 ordinal_heuristic(zip 顺序≈阅读顺序,常不一致),故每次都输出一份「图号→图片文件」对照(stderr 醒目 banner + JSON `figure_map`,含 binding=atomize-prefilled/ordinal_heuristic/unresolved),一旦触发 md 重建回退,图按此绑定嵌入,必须人工核对是否错号错位
python scripts/reference_sync.py --project-root <project_root> --output-md <output_md>
python scripts/build_reference_registry.py --project-root <project_root> --output-md <output_md> [--references-source <ref_source>] [--reference-search-decision ask|approved|declined]
python scripts/export_docx.py --project-root <project_root> --output-md <output_md> --output-docx <output_docx> [--reference-docx <ref_docx>] [--manuscript-docx <original_manuscript_docx>] [--no-inplace] [--allow-rebuild-fallback] [--track-changes] [--author revise-sci] [--date <ISO8601>] [--journal-style journal-manuscript|nature-review|cell-press|lancet-review]
# 传 --manuscript-docx <原始稿.docx> 时改后稿默认 in-place 保原稿格式（仅替换被改段落）。定位/身份失败时**硬停退出码 3 并打印两个选项**，不再默认静默降级；显式加 --allow-rebuild-fallback 才回退 md 全量重建。--no-inplace 强制走 legacy 全量重建。run_pipeline 会在原稿为 .docx 时自动传入 --manuscript-docx（并透传 --allow-rebuild-fallback）。
# --track-changes（默认关闭）：in-place 导出时，改动段落不再整段重建成 clean 文本，而是对 original vs current 做**词级 diff**（英文按空白/标点切词、中文按单字切），生成带 Word 修订痕迹的 docx，删除词用 <w:del><w:delText>、新增词用 <w:ins><w:t>、替换=先删旧后插新；未变的词保持普通 run 不进痕迹。每处 ins/del 带唯一递增 w:id + w:author（--author，默认 revise-sci）+ w:date（--date，默认 datetime.now().isoformat()）。行内格式（*斜体*/**粗**/<sup>/<sub>）随词级 diff 完整保留在痕迹两侧。含内嵌图片的段落仍跳过（保图）。开关关闭时 clean in-place 行为**完全不变**。Word 里“接受全部修订”后正文==current，“拒绝全部修订”后==original。注意：python-docx 的 `.text` 不读 w:ins/w:del 内文，属正常现象（能正常打开），校验请用接受/拒绝后的文本或 docx 技能的 accept_changes.py。
python scripts/final_consistency_report.py ...
python scripts/numeric_candidates.py --manuscript <output_docx 或 output_md> --project-root <project_root>   # 数值一致性核查第1层确定性锚；三层(独立检测子代理+delegate_review反向验证+HALT)见下方"数值一致性核查"节。挂在 final_consistency 与 strict_gate 之间
python scripts/structure_outline.py --manuscript <output_docx 或 output_md> --project-root <project_root>   # 交叉引用核查(xref)第1层确定性锚(sections/figures/tables/items)；三层见下方"交叉引用核查"节。与 numeric 同源、numeric 之后
python scripts/methods_terms.py --manuscript <output_docx 或 output_md> --project-root <project_root>   # 方法学漏写核查(M)第1层弱锚(authority:weak_focus_map)；三层+实验稿门见下方"方法学漏写核查"节。综述稿(journal_style∈{nature-review,lancet-review})跳过 M
python scripts/strict_gate.py ...
```

**数值一致性核查（三层·final_consistency 与 strict_gate 之间·HALT 交用户裁决）**：数值矛盾天然跨摘要/结果/表，必须返修后全文成形后跑。读**返修后的 `output_docx`**（in-place 保格式，docx 表格 walk 头号用例，`numeric_candidates.py` 已额外遍历 `doc.tables` 抽单元格值 `location.source=="table"`）或 `output_md`。

- **① 第 1 层确定性锚**：上面 `numeric_candidates.py` 已产 `<project_root>/numeric_candidates.json`。
- **② 第 2 层独立检测子代理（非作者自检·I2）**：派一个 fresh context、**没参与返修**的独立检测子代理（`TaskCreate`/spawn_task），**只喂** `numeric_candidates.json` + 返修全文，**不给返修过程上下文/作者意图**（防继承确认偏误，否则漏看的真矛盾第 3 层永远看不到→系统性假阴）。子代理产出**零容差二元 schema** `[{"metric","same_measurement":bool,"values":[{"id","raw","location":{"region","para_index"}}],"conflict":bool,"evidence_quote","finding"}]`（**无 `tolerance_state`、无 `severity`**）：先判是否**同一指标/对象/分组/时间点/单位**（跨措辞语义归一、跨单位如 μM vs nM 由 LLM 换算判），仅对同一测量判是否**完全相等**，`same_measurement==true && 非完全相等 → conflict=true`；不同剂量组/时间点/亚组/单位的正常差异不报。**样本量 n 跨位置核对**：核对同一实验/同一组的样本重复数 n（`metric_clue=="样本量"`）是否跨**方法学 / 图注 / 结果与讨论**三处一致；**防假阳**：不同图/不同实验的 n 本可合理不同，**只有多处 n 明确指向同一实验、同一组样本时**其不一致才报 conflict，无法确认的按 `same_measurement=false` 不报（拿不准交人工）。**降级**：派不出真正独立子代理时不得自问自答冒充，标注"数值一致性未经独立检测"交用户人肉核。
- **③ 第 3 层反向验证**：每条 `conflict==true` 过 `delegate_review.py`（**不改它，只 pack/verify**，gate=`numeric-verify`，checklist 内自由 key，不查 gate_registry）。⚠️ **revise 的 `delegate_review.py` 是 fork（md5 ≠ base）——pack/verify 与 fail-closed 行为须对 fork 实测，不假设 base 行为。** 动态合成 `<project_root>/numeric_verify_checklist.json`：item 只放两处 `raw`/location/`metric` + 核验所需原文切片（**绝不放子代理 finding/reasoning**），默认硬项（不标 `"severity":"soft"`）；**≥3 值的组拆成两两配对的多个 item**（id `num-<组>-<配对序>`，任一配对 pass → 该组整体保留、全部 fail → 剔除）。**🔴 check 逐字用零容差极性模板（禁占位符、禁自由发挥）**：
  > "到给你的原稿全文里独立核实：`{locA}` 处的值『{valA}』与 `{locB}` 处的值『{valB}』，两者据称都是指标『{metric}』的测量结果。请逐字回源确认两点——**(1) 两处是否确指同一指标、同一测量对象、同一分组、同一时间点、同一单位**（即本就应当相等；跨单位如 μM vs nM，请换算到同一单位后再判是否本应相等）？请到原文找出各自邻近的分组/剂量/时间点/亚组/单位线索比对。**(2) 若确为同一测量，两值是否非完全相等**（**零容差：只要不是完全相同的数值即算不等，含末位舍入差异如 58% vs 58.3%**）？**只有『同一测量且非完全相等』才判 pass（矛盾属实，保留交人工裁决）；只要发现两者其实是不同分组/不同时间点/不同亚组/不同单位（正常差异），或换算后完全相等，一律判 fail（非矛盾，剔除）。** evidence 必填：逐字引出 A、B 两处原文句及各自的分组/时间点/单位线索。"

  `--files` 给返修全文；`pack` → 独立空白子代理逐条裁 `pass|fail|na` 附逐字证据 → `verify`。**verdict 映射**：`pass`→confirmed（矛盾属实）；`fail`/`na`→refuted（剔除）；verify 的 `problems`（空证据/未裁决/verdict 非法）照 fail-closed 视为未核验、不进清单（宁漏报）。极性写反 = 假批评全放行，务必对准 pass=矛盾属实。 ⚠️ **退出码陷阱（务必理解）**：本 numeric-verify 复用通用门禁 `delegate_review`，任一 item fail 会让 verify 报 `ok=false` / **exit 1** / stderr『盲检未通过』——但在数值反向验证里 **fail = 成功剔除假矛盾 = 正常好结果**。主 agent 必须**忽略退出码**，只读返回 JSON 的逐条 verdict + problems：verdict=pass→confirmed 保留、fail/na→refuted 剔除、problems 内→fail-closed 不进报告。切勿把 exit 1 误读成核查失败 / 报告不能完成。
- **④ HALT**：命中 confirmed conflict → **HALT 交用户裁决**（列 `metric` + 两处 `raw`/location + evidence_quote），暂停 pipeline、用户逐条裁决是否需统一，处置后重跑本步至无 confirmed conflict 再进 `strict_gate.py`。**不 auto-block 硬拦、不静默判等放过**（零容差 + 灰区交人工）。

**交叉引用核查（xref，三层·numeric 之后·strict_gate 之前·HALT 交用户裁决）**：改稿最爱动图/节/表编号（删段、并段、重排），"见图5/见3.3节"指向对不对是返修高发坑；必须返修后全文成形、编号冻结后跑（与 numeric 同挂点、同源）。读**返修后的 `output_docx`**（in-place 保格式）或 `output_md`。revise 对交叉引用一致性零覆盖，纯新增能力。

- **① 第 1 层确定性锚**：上面 `structure_outline.py --manuscript <output_docx 或 output_md> --project-root <project_root>` 已产 `<project_root>/outline.json`（稿中真实存在的全部 `sections`/`figures`/`tables`/`items`）。**脚本零改造、docx 读取现役已具备**（走 `manuscript_index.read_manuscript_paragraphs` 抽 docx 段落，含 Heading 样式认小节）。JSON 落 `<project_root>` 根，不进托管 glob。
- **② 第 2 层独立检测子代理（非作者自检·I2）**：派一个 fresh context、**没参与返修**的独立检测子代理（`TaskCreate`/spawn_task），**只喂** `outline.json` + 返修全文，**不给返修过程上下文/作者意图**（防继承确认偏误→系统性假阴）。逐条指向型表述（`见 3.1`/`如前文 4.1.2 所述`/`见图3`/`见表2`/`见(2)`）对着 `outline.json`（**唯一权威真值**，不凭记忆假设稿子有某小节，拿不准标 `uncertain`）判**存在性**（`missing_target`）与**语义对应**（`semantic_mismatch`）。产出 schema `[{"ref_id","citing_location","cited_target","issue_type":"missing_target|semantic_mismatch|uncertain","evidence_quote","outline_says","finding","severity"}]`（`severity` 仅信息字段，HALT 不按它路由）。**🔴 补充材料护栏**：`S` 前缀编号（`Figure S1`/`Table S3`/`见图 S22`/`Supplementary Fig. 5`）**一律强制 skip 丢弃**（不产 finding、绝不标 `uncertain`、绝不报 `missing_target`、绝不送第 3 层——否则补充材料图注天然不在正文稿，第 3 层"连定义处都找不到→pass=confirmed"会把整份补充材料 S1–Sn 批量假报为悬空引用、假阳 HALT）。**降级**：派不出真正独立子代理时不得自问自答冒充，标注"交叉引用未经独立检测"交用户人肉核。
- **③ 第 3 层反向验证**：每条发现过 `delegate_review.py`（**不改它，只 pack/verify**，gate=`xref-verify`，checklist 内自由 key，不查 gate_registry）。⚠️ **revise 的 `delegate_review.py` 是 fork（md5 ≠ base）——但 D1 numeric-verify 已在这份 fork 上实测 pack/verify + 退出码陷阱 + fail-closed 全通；xref 复用同一 fork、同一 gate 机制，pack/verify 一律不传 `--comments`（那是 RR 专用可选 arg，不传则 pack 行为等同 base）。** 动态合成 `<project_root>/xref_verify_checklist.json`（`{"skill":"revise-sci","gates":{"xref-verify":{"title":"交叉引用一致性·反向验证","items":[{"id","name","check"}]}}}`）：item 只放 `cited_target`+`evidence_quote`+`issue_type`+核验所需原文切片（**绝不放子代理 finding/理由、也不放 outline**），默认硬项。**按 issue_type 分流喂料**：`missing_target`/`uncertain` 的 item `--files` 给**返修全文**（让核验人独立回源检索该编号定义存否，反查第 1 层漏抽真小节造成的假 missing_target）；`semantic_mismatch` 的 item 给引用处上下文切片 + outline 里该编号标题/caption。**🔴 check 逐字用极性模板（禁占位符、禁自由发挥），两类分写**：
  > `missing_target`/`uncertain`："到给你的原稿全文里，找得到编号「{编号}」的**定义处**吗？定义处专指：图/表的图注行（以『Figure {N}』『图{N}』『Table {N}』『表{N}』开头、后接说明文字的 caption 行），或该编号的小节标题行（如独占一行的『3.2 方法』）；**把它当引用来提及的句子不算定义处**（如『见 Figure 3』『as shown in Figure 3』『详见 3.2 节』这类指向句，即便含该编号也一律不算）。只有连定义处都找不到（该编号只被引用、从未被定义）才判 pass；只要找到定义处就判 fail，并逐字引出该定义/caption 行。"
  > `semantic_mismatch`："正文该引用处的具体断言，与目标「{编号}」的标题/caption 是否明确无关？只有'正文明确断言见 X 讨论了 Y、而 X 根本不涉及 Y'这种明确错位才判 pass；若只是笼统指向或目标标题能合理概括该引用，一律判 fail。"

  `pack` → 独立空白子代理逐条裁 `pass|fail|na` 附逐字证据（写回 `.review_return_xref-verify.json`）→ `verify`。**verdict 映射**：`missing_target`/`uncertain` 连定义处都找不到（悬空）→ `pass`=confirmed 保留、找到定义处（caption/小节标题行，非引用句自身）→ `fail`=refuted 剔除；`semantic_mismatch` 明确无关→ `pass`=confirmed、笼统指向/合理概括→ `fail`=refuted；verify 的 `problems`（空证据/未裁决/verdict 非法）照 fail-closed 视为未核验、不进清单（宁漏报）。⚠️ **极性关键**：核验人**必须区分"定义处"与"引用处"**（引用句自身含该编号不构成"找得到"），写反 = 假批评全放行。⚠️ **退出码陷阱**：任一 item fail 会让 verify 报 `ok=false`/**exit 1**/stderr『盲检未通过』——但在 xref-verify 里 **fail = 成功剔除假问题 = 正常好结果**。主 agent 必须**忽略退出码**，只读返回 JSON 的逐条 verdict + problems。
- **④ HALT**：命中 confirmed → **HALT 交用户裁决**（列 `cited_target` + 引用处切片 + evidence），暂停 pipeline、用户逐条裁决，处置后重跑本步至无 confirmed 再进下一步。**不 auto-block、不静默放过**（灰区交人工）。

**方法学漏写核查（M，三层·实验稿门·xref 之后·strict_gate 之前·HALT 交用户裁决）**："结果做了某实验、方法学没交代"是审稿高频硬伤；revise 是改已有稿、不像 gsw 那样系统重建 Methods，M 在 revise 补的是一整块空白。读**返修后的 `output_docx`**（in-place 保格式，methods_terms 已自带 `_read_docx_table_cells` 遍历 docx 表格单元格）或 `output_md`。

- **🔴 实验稿门（M 节开头必判，判据可读可测）**：读 `<project_root>/project_state.json` 的 `inputs.journal_style`（由 `preflight.py`/`export_docx.py` 写入、`strict_gate.py` 已校验合法，本挂点在 export 之后 → 字段必就绪）。
  - `journal_style ∈ {"nature-review","lancet-review"}` → **整个 M 节 skip**，向用户打印"综述稿跳过方法学漏写核查"，直接进 `strict_gate.py`（xref 照跑、不受此门影响）。
  - `journal_style ∈ {"journal-manuscript","cell-press"}` → **跑 M**（原始研究/Cell 系一次研究，有实验方法学）。
  - 字段缺失/非法（理论上 strict_gate 已挡）→ **保守跑 M**（宁多跑不漏，第 3 层兜假阳）。
- **① 第 1 层弱锚**：上面 `methods_terms.py --manuscript <output_docx 或 output_md> --project-root <project_root>` 已产 `<project_root>/methods_terms.json`（`authority:"weak_focus_map"`，`method_hits`/`methods_sections`）。**弱锚缺失/损坏降级**：`methods_terms.py` 若 exit 2 或 JSON 缺失/损坏，第 2 层**降级为纯全文语义跑**（它本就不依赖弱锚），不得静默失效。JSON 落 `<project_root>` 根。
- **② 第 2 层独立检测子代理（非作者自检·I2）**：派 fresh context、**没参与返修**的独立检测子代理，**只喂** `methods_terms.json` + 返修全文，**不给返修过程上下文**。读结果/讨论 + 方法学 + 弱锚，判**每个本研究用到的实验方法方法学章节有没有交代**，报 `methods_missing`。关键约束（逐条写进 prompt）：① 弱锚非穷尽、须自行语义补词典外方法（含隐含如"散点图门控"→流式）；② **只判本研究做的（头号假阳防线）**——引用他人研究（`previous studies used…`）/未来工作计划（`plan to/would/future work`）/背景泛提**一律不报**，判据=人称时态 + 区段 + `has_figure_adjacent` + 语义；③ "交代了"从宽三选一（方法学出现方法名 / 主文指向补充材料 / 方法学引用文献描述该方法，任一即 `methods_section_covers=true`）。产出 schema `[{"method","used_in_study":bool,"methods_section_covers":bool,"methods_missing":bool,"evidence_quote","finding"}]`，判据 `used_in_study==true && methods_section_covers==false → methods_missing=true`。**下游路由**：`methods_missing==true` → 第 3 层；`used_in_study==false` 或 `methods_section_covers==true` → 丢弃。**已知局限（明写交代用户）**：仅核主文、不读补充材料文件——方法完全下沉补充材料且主文连"见补充材料"都没提的漏报核不出。**降级**：派不出真正独立子代理时不得自问自答冒充，标注"方法学一致性未经独立检测"交用户人肉核。
- **③ 第 3 层反向验证**：每条 `methods_missing==true` 过 `delegate_review.py`（**不改它，只 pack/verify**，gate=`methods-verify`，checklist 内自由 key，不查 gate_registry，不传 `--comments`，fork 行为等同 base、见 xref ③）。动态合成 `<project_root>/methods_verify_checklist.json`（`skill:"revise-sci"`，gate=`methods-verify`）：item 只放 `{method}` + 结果处命中句（弱锚 `sentence` 或第 2 层 evidence）+ 核验所需切片（**绝不放 finding/reasoning**），默认硬项，`--files` 给**返修全文**。**🔴 check 逐字用两条件极性模板（禁占位符、禁自由发挥）**：
  > "到给你的原稿全文里独立核实两点——**(1) 结果/讨论是否确实报告了本研究做的『{method}』**（有对应实验数据/图/门控/条带等本研究结果，而非仅在背景/引言/讨论里引用他人研究提及该方法，也非讨论/局限里"将来/拟/计划/would/planned to/future work"等表述里打算做但本研究并未做的未来工作/计划实验）？请回源找邻近的数据/图引用与人称/时态/引文线索比对。**(2) 方法学章节是否确实【完全没有】交代『{method}』**——须同时满足三个『没有』才算完全没交代：**(2a)** 既无该方法的小节标题、也无任何描述其如何做的句子；**(2b)** 也没有任何指向补充材料/附录的表述（如『见补充材料』『详见附录』『see Supplementary Methods』『described in the Supplementary/Supporting Information』）；**(2c)** 也没有【引用文献描述该方法】的表述（如『方法参照文献[X]』『按照[X]的方法进行』『as previously described [12]』这类带文献引用标记的方法指向）。只要出现 (2b) 指向补充材料 或 (2c) 引用文献描述该方法，即算已交代、不算漏写。**只有『结果确实用了本研究的该方法』且『方法学确实没写、没指向补充材料、也没引用文献描述该方法』两条同时成立才判 pass（漏写属实，保留交人工裁决）；只要发现方法学其实写了该方法（哪怕只一句）、或主文有指向补充材料的交代、或方法学有引用文献描述该方法（带引文标记）、或结果里的该方法其实是引用他人研究/背景讨论（非本研究做的），一律判 fail（非漏写，剔除）。** evidence 必填：逐字引出结果处用到该方法的句 + 方法学处（有则引出该句证明写了/引出指向补充材料或引用文献的句，无则说明通读方法学未见）。"

  `pack` → 独立空白子代理逐条裁 `pass|fail|na` 附逐字证据（写回 `.review_return_methods-verify.json`）→ `verify`。**verdict 映射**：本研究确用 AND 方法学确未写/未指向补充材料/未引用文献描述 → `pass`=confirmed 保留；方法学其实写了 / 主文指向补充材料 / 方法学引用文献描述 / 结果只是引用他人 → `fail`=refuted 剔除；verify 的 `problems` 照 fail-closed 视为未核验、不进清单（宁漏报）。⚠️ **极性关键**：核验人**必须独立确认两件事**——条件 (1) 本研究做的 vs 引用他人（M 头号假阳源）、条件 (2) 两类从宽交代（(2b) 指向补充材料、(2c) 方法学引用文献描述该方法），不能只问"方法学有没有直接写"，写反 = 假批评全放行。⚠️ **退出码陷阱**：任一 item fail 会让 verify 报 `ok=false`/**exit 1**/『盲检未通过』——但在 methods-verify 里 **fail = 成功剔除假漏写 = 正常好结果**。主 agent 必须**忽略退出码**，只读返回 JSON 的逐条 verdict + problems。
- **④ HALT**：命中 confirmed → **HALT 交用户裁决**（列 `method` + 结果处切片 + evidence），暂停 pipeline、用户逐条裁决，处置后重跑本步至无 confirmed 再进 `strict_gate.py`。**不 auto-block、不静默放过**（灰区交人工）。

Or use the single entrypoint:

```bash
python scripts/run_pipeline.py --comments <comments_path> --manuscript <manuscript_docx_path> --project-root <project_root> --output-md <output_md_path> --output-docx <output_docx_path> [--journal-style journal-manuscript|nature-review|cell-press|lancet-review] [--expected-comments-mode <comments_input_mode>] [--context-token-budget 4200] [--context-tail-lines 80] [--paper-search-results <paper_search_results_path>] [--resume] [--resume-from <step>] [--resume-keep-unaffected] [--force-rebuild] [--allow-rebuild-fallback]
```

`--expected-comments-mode` is strongly recommended after the user confirms the branch chosen by `intake_router.py`. `preflight.py` will block execution if the confirmed mode and the detected mode do not match.

## [意见清单核对·必停]（拆意见后、改写前的强制关卡）

**位置**：`atomize_comments.py` 拆完审稿意见之后、`revise_units.py` 开始改写之前。这是流程内部的硬关卡，与开场监工卡不同：监工卡是启动时提醒，这一步是拆完意见后的当场核对。

拆完审稿意见后，**立即停下**，把**每条 comment_id + 该条前 30 字**列成清单打给用户，并原样问：

> 「请拿**原始审稿信**对照数一遍，条数对不对？有没有哪条被合并成一条、或整段漏掉？（尤其审稿人用连续散文、`(i)(ii)`、罗马数字、或一段里塞多个要求时最容易漏）」

**用户确认"都在、没漏"后才继续改写**。用户指出漏掉或被合并的，回去把它补成独立 comment（补进 `units/`、重新原子化）后再继续，不得跳过这一步直接跑 `revise_units.py`。

## [通读定策略·前置阶段]（清单核对通过后、逐条改写前）

真人返修的第一件事不是逐条动手，而是**先把所有意见通读一遍、定下每条的应对策略**。这里也一样：意见清单核对通过后、`revise_units.py` 开始逐条改写之前，**先做一轮 triage**，不要从 atomize 直接跳到逐条改。

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
`revise-sci` does **not** load the entire manuscript and all comments into one context window. It uses the same approach as `article-writing`, `review-writing`, and `sci2doc`, adapted for revise work:

1. **Intake-first routing**: route the comment source first, then lock the branch before loading anything large.
2. **Section-paragraph atomicization**: only the target section and target paragraph are used for rewrite scope.
3. **Comment-scoped state windows**: every processed `comment_id` gets its own context package under `state/comment_windows/<comment_id>.json`.
4. **Section digests, not full reloads**: cross-section consistency uses `state/section_digests.json`, which stores only headings, paragraph counts, and key sentences, rather than full section text.
5. **Token budget compaction**: `state_manager.py write-cycle` estimates token load and compacts related digests / reviewer context / neighboring paragraphs if the bundle exceeds the configured budget.
6. **Cycle log persistence**: every revise action appends to `state/comment_cycle_log.json` and `state/comment_memory/<comment_id>.md`, so a future agent does not need to reconstruct local history from scratch.
7. **Snapshot safety**: `state_manager.py snapshot` writes state snapshots so runs can be resumed with smaller context and lower drift risk.

Recommended per-comment loading command:

```bash
python scripts/state_manager.py --project-root <project_root> write-cycle --comment-id <comment_id> --token-budget 4200 --tail-lines 80 --json-summary
```

This command is the revise-sci equivalent of the section-scoped state loading in `article-writing`, `review-writing`, and `sci2doc`. It is the preferred context entry before any manual or AI-assisted change to a specific comment-linked paragraph.

## Patch 修订协议（可选的确定性修订路径）
This is an **optional, additive** deterministic path for applying scope-locked edits. It does not replace the `atomize -> issue-matrix -> revise_units -> strict_gate` flow. Use it when you need a hard guarantee that only the touched blocks can change and every other block stays byte-for-byte identical, rather than having the model regenerate whole sections (the main source of scope creep and drift).

Protocol (four phases):
1. **anchorize**: split the target draft into blank-line blocks, assign each a stable anchor id (`block-NNNN-<hash8>`), and write a block manifest (anchor -> exact original bytes + sha256 + byte offsets):
   ```bash
   python scripts/anchorize_draft.py --draft <draft.md> --manifest <project_root>/block_manifest.json
   ```
2. **patch**: for each reviewer comment that needs a block changed, author a patch entry `{anchor_id, expected_hash, new_content}` where `expected_hash` is the block's `sha256` from the manifest. Patch only the blocks that must change; never touch other anchors. The patch file is a JSON array of such entries.
3. **apply (deterministic, fail-closed)**: locate each block by anchor id, verify its current sha256 equals the patch's `expected_hash`, then splice only the patched byte-spans:
   ```bash
   python scripts/apply_revision_patch.py --manifest <block_manifest.json> --patch <patch.json> --output <revised.md>
   ```
   If **any** entry's hash does not match (the block already changed) or the source draft drifted since anchorize, the whole patch set is **rejected**, nothing is written, and the script exits non-zero. There is no silent partial apply.
4. **finalizer**: `apply_revision_patch.py` reassembles the full draft from the original source, copying every unpatched byte verbatim (blocks, separators, and trailing-newline state preserved). Feed `<revised.md>` back into the normal `polish -> literature/reference checks -> strict_gate` flow before delivery.

Rules:
- The patch path is **fail-closed**: a hash mismatch or source drift must abort and write nothing; never coerce or auto-relocate a patch onto a changed block.
- The patch path is an increment on top of the existing pipeline, not a replacement: `atomize_comments.py`, `build_issue_matrix.py`, the state-window protocol, and `strict_gate.py` all still apply to the resulting draft.

## 缩略语首展一致性(Abbreviation Consistency)
改稿最易破坏缩略语一致性:改某句时删掉了首展、在首展之前的位置裸用 ABBR、或新增术语未首展。规则:
- **首展格式**:英文 `Full Name (ABBR)`;中文正文 `中文全称（English Full Name, ABBR）`。同一缩写全文只首展一次,之后裸用 ABBR,不重复展开。
- **Title 禁缩写**(DNA/RNA/PCR 等通用词除外);Abstract 独立,即使正文已定义,Abstract 内首次出现仍应重新展开。
- **改稿守则**:替换/删除句子时若该句承载某缩写的唯一首展,须把首展移到改后稿中该缩写的新首现处;新引入的术语必须在首现处首展。
- **核查**:`manuscript_index.py` 对改后稿产 `abbreviation_index.json`。`undefined_use`(裸用未定义)/`duplicate_definition`(重复首展)/`title_abbreviation`(Title 含缩写)为硬错须修;`defined_unused`(定义后未再用)为软警告,人工取舍。通用缩写见脚本 `UNIVERSAL_ABBREVIATIONS` 白名单,自动跳过。索引为启发式辅助,可疑项人工复核。

## Response Format
`response_to_reviewers` must use this hierarchy:
- `# 回复审稿人的邮件`
- optional `## Editor Statement` when the decision letter contains editor-only overall instructions but no numbered editor comments
- optional `# Editor` when there are numbered editorial action items
- `# Reviewer #N`
- `## Major / Minor`
- `### Comment k`

Each comment must contain:
1. `审稿意见与中文理解`
2. `Response to Reviewer（中英对照）`
3. `可能需要修改的正文/附件内容（中英对照）`
4. `修改说明（中文）`
5. `Evidence Attachments`

## Rules
- Missing information must be written as `Not provided by user` or `需作者确认`.
- If a reviewer asks for new literature, only `paper-search` is allowed as the external provider family.
- `paper_search_results_path` may be used to ingest confirmed paper-search results into citation-oriented comment handling.
- `paper_search_results_path` is not trusted directly. It must first pass `citation_guard.py`, which performs dual verification using provider trace and identifier/title consistency evidence before citations can auto-complete a comment.
- **新增文献真实性双验（B②，不许 --offline 交付）**：审稿要求补新文献时，全部新引文献必须过 `citation_guard.py` 的 **在线**真实性双验（DOI/PMID 解析、撤稿检测、逐源标题一致性）。有已 `completed` 的 citation 类意见时，`strict_gate.py` 会读 `paper_search_guard_report.json`：`summary.online_check` 非 `true`（即用 `--offline` 或没加 `--live` 跑的）或 `all_rows_guard_verified` 非 `true`，一律 fail-close。交付前必须 `python scripts/citation_guard.py --live ...` 重跑，不许 `--offline` 跳过。
  - **已知限制（诊断提示在本技能里看不到，但请求照打）**：`--live` 跑时，对每条没验过、带 DOI/PMID、标题≥3 个词的文献，底层核验会额外拿标题上网回查一次，本可给出「这条的 DOI/PMID 可能填错了，线上同名文章是这个」之类的提示；但本技能的 `verification_details` 只保留固定字段，这些提示会被直接丢掉——**请求照打、结果照扔**，白花一次网络往返和限流额度。**判定结果完全不受影响**（guard_verified / 撤稿 / fail-close 一条都不会变），只是新引文献多时 `--live` 那一趟会慢些。所以验不过的条目直接看 `verification_details.failure_reasons` 排查，别等诊断提示。注意这条省不掉：交付必须 `--live`，不能为了少打请求改用 `--offline`。
- **新引文献↔它支撑的回复论点，须过引文核证（B④）**：真实性通过只说明该文献存在，不说明它真支撑你借它下的结论。对每条「新引文献 → 它在回复信/正文里支撑的论点句」，用该文献**检索到的真实 abstract** 判支撑度，落 `claim_evidence.json`（每条含 `claim_sentence` / `is_load_bearing` / `ref_id` / `retrieved_abstract` / `verdict∈support/weak/contradict/unknown` / `user_confirmed`），再跑共享 `citation_claim_check.py`（`CITATION_CHECK_CMD`）。跨批复用由脚本自动完成，AI 不必手动记账。脚本在核证前从项目根 `ref_evidence_cache.json` 自动回填缺失字段，核证后强制落盘。已在别处验过 abstract 的文献，本批该行 `retrieved_abstract` 可留空，脚本按 `ref_id` 回填。同一篇文献且完全同一论点句此前已人工确认过的，脚本自动复用其 `verdict` 与 `user_confirmed`，不再重复反向验证与逐条确认。只有新的 (文献, 论点) 组合才需要你补 abstract、判支撑度并逐条人工确认。门禁强度不变，承重句被判 `contradict`/`unknown`、缺 abstract、或 support/weak 但未确认一律硬拦，新 (文献, 论点) 无 verdict 仍 fail-close。同一篇文献换去支撑另一句论点，不复用旧确认，须独立判定。有 `completed` citation 意见时，`strict_gate.py` 复用共享 `citation_claim_check._row_blockers` 核验 `claim_evidence.json`，文件缺失或任一承重句阻断即 fail-close。abstract 的检索走工作流subagent（本脚本不含 MCP）。
- `build_literature_index.py` must convert validated citation support into review-writing style canonical artifacts: `data/literature_index.json` and `data/revision_claims.json`.
- `build_literature_index.py` accepts an optional `--seed-index <path>` to reuse the writing project's existing `literature_index.json` (produced by `gsw`/`review-writing`) as a seed. Seed entries keep their original `global_id`; revision-found references that match a seed entry (dedup key: normalized DOI > PMID > normalized title) reuse the seed number instead of getting a new one, and truly new references continue numbering from `max(seed global_id) + 1`. The seed is read-only; the merged result is written only to revise-sci's own `data/literature_index.json`, never back to the writing project (seed-extension semantics). The seed reader tolerates the looser gsw schema (global id under any of `global_id`/`citation_number`/`id`/`number`/`ref_number`, back-filled by array order when absent) and a seed located either at the project root or under `data/`. Omitting `--seed-index` keeps the original rebuild-from-1 behavior unchanged.
- `matrix_manager.py` must derive `data/synthesis_matrix.json` from the canonical literature index and emit `data/synthesis_matrix_audit.json` before delivery.
- `build_reference_registry.py` must extract the final manuscript reference list into canonical `data/reference_registry.json` and audit body-to-reference coverage into `data/reference_coverage_audit.json`.
- `build_reference_registry.py` may import a fallback reference seed from `references_source_path` when the manuscript reference list is empty or absent.
- If a manuscript already has a partial numeric `References` section, `build_reference_registry.py` should try to merge missing numbered entries from the detected legacy reference source instead of failing immediately.
- If unresolved reference gaps still remain after registry rebuild, `build_reference_registry.py` must emit `reference_recovery_request.md` so the author knows exactly which source formats to provide next.
- If no original or legacy reference source is available, ask the user whether to start a new literature-search-and-fill cycle; default state is `reference_search_decision=ask`, not silent auto-search.
- If the user approves new reference search, the search-and-fill path must follow the `review-writing` discipline: `paper-search` retrieval only, immediate `citation_guard.py` after each import batch, update canonical `data/literature_index.json`, then refresh `data/synthesis_matrix.json` / `data/synthesis_matrix_audit.json` before any new references can enter the manuscript.
- If `reference_search_decision=approved` and reference gaps still exist, the skill must generate `reference_search_manifest.json` and `reference_search_task.md` so the approved search cycle is executable and auditable rather than implicit.
- The approved search cycle should also emit `reference_search_strategy.json` and `reference_search_status.json` so search scope, provider policy, round model, and step status remain explicit and machine-checkable.
- The approved search cycle should also emit `reference_search_rounds.json`, containing concrete query batches for Round 1 / Round 2 / Round 3 under `review-writing` governance.
- The approved search cycle must explicitly declare `workflow=review-writing`, `allowed_provider_families=["paper-search"]`, `forbidden_provider_families` containing `websearch`, and `verification_policy.dual_verification_required=true`.
- The approved search cycle must keep a three-round structure in both `reference_search_manifest.json` and `reference_search_strategy.json`, and must record `citation_guard.py` as the mandatory verification command.
- `build_reference_registry.py` should audit both numeric citations and author-year citations; unresolved gaps in either style must block delivery.
- Confirmed citation support must include an explicit anchor such as `target_section_heading`, `target_paragraph_index`, or `target_text`; otherwise the item stays in `needs_author_confirmation`.
- If current materials are insufficient, keep the item in `needs_author_confirmation` instead of inventing a resolution.
- Treat `completed` as a narrow state: only conservative text-only clarification or limitation edits with reliable paragraph localization may be auto-completed.
- If paragraph localization is ambiguous and multiple candidates score similarly, fall back to `needs_author_confirmation` rather than selecting a paragraph aggressively.
- If a comment contains an explicit structured section hint such as `Section 4.2` or `4.2 节` but that hint cannot be matched to an existing section, do not fall back to lexical matching; keep the item in `needs_author_confirmation`.
- For Chinese-source reviewer comments, keep the original Chinese comment as the authoritative source block and render a separate English working summary instead of mislabeled bilingual fields.
- `preflight.py` must record `comments_input_mode` so downstream steps and audit reports know whether the current run came from raw reviewer comments, reviewer-simulator HTML, reviewer-response-sci HTML, or already-atomic HTML.
- `preflight.py` must also record `expected_comments_mode`, `context_token_budget`, and `context_tail_lines`; these values become part of the resume fingerprint.
- `preflight.py` must fail fast when the user runs the full pipeline on an unsupported or unclassified comments source, rather than silently guessing a branch.
- `reviewer-response-sci` HTML inputs must be treated as response-rich seeds: `atomize_comments.py` should preserve the seeded response/revision fields, and `revise_units.py` should reuse them conservatively for localization and draft response blocks without bypassing manuscript rewrite constraints or hard gates.
- Citation-only comments may be auto-completed only when confirmed `paper-search` results and formatted citation text are explicitly provided.
- Citation-only comments may be auto-completed only when the row is `confirmed`, the citation guard marks it `guard_verified=true`, and the target anchor is explicit.
- After manuscript merge, `reference_sync.py` must append or update the `References/参考文献` section using canonical `data/literature_index.json` and emit `reference_sync_report.json`.
- When `author_confirmation_reason` is rendered into English, the translated reason must remain fully English with no leftover Chinese fragments.
- For substantive requests such as new mechanism explanations, new evidence, new figures, or unresolved section matches, stop at `needs_author_confirmation` and do not auto-complete.
- `strict_gate.py` must verify comment coverage, response/manuscript/edit-plan consistency, atomic location completeness, provider-family policy, and per-comment evidence blocks before delivery.
- 📢 **交付前半成品提醒（非阻断）**：`strict_gate.py` 每次运行都统计最终 response 正文里 `需作者确认` 的出现次数、以及非默认的 `Not provided`（排除每个 unit 的 Image/Table 默认模板行 `Not provided by user`，避免狼来了）；命中就打印醒目 banner「还有 N 处待你处理」。这**不判 FAIL**（`需作者确认` 是合法输出），只响亮提醒，防止半成品被当成成品直接投稿。
- 🧭 **PASS 诚实化**：`STRICT_GATE: PASS` 后追加一行真话：PASS 仅覆盖形式层（引文编号/去 AI/结构/占位符/文件完整性），改写是否改变原意、科学结论是否正确、数据是否一致均**未自动核验**，须作者逐条核对。
- `strict_gate.py` must verify that every auto-completed citation comment is covered by `reference_sync_report.json`; otherwise delivery fails.
- `strict_gate.py` must verify that every auto-completed citation comment is present in both `data/literature_index.json` and `data/synthesis_matrix.json`, and that `data/synthesis_matrix_audit.json` reports no unresolved matrix gaps.
- `strict_gate.py` must fail delivery when `data/reference_coverage_audit.json` reports unresolved numeric citation gaps, even if the comment-level workflow itself completed.
- `strict_gate.py` must parse `response_to_reviewers.docx` and verify that comment headings, response-section headings, and evidence-section headings are present for every comment block.
- `strict_gate.py` must verify that `reference_search_manifest.json`, `reference_search_strategy.json`, and `reference_search_status.json` are internally consistent with actual approved-search artifacts such as `paper_search_validated.json`, `paper_search_guard_report.json`, `data/literature_index.json`, `data/synthesis_matrix_audit.json`, and `reference_sync_report.json`.
- `references_source_path` is optional. If not provided explicitly, the pipeline may auto-detect likely sources such as a same-title sibling manuscript docx with a populated `References` block, `<comments_dir>/data/literature_index.json`, attachment files named like `reference*`/`bibliography*`, or project-local seed files.
- `references_source_path` auto-discovery should also inspect nearby versioned manuscript docx files inside shallow subdirectories of the manuscript folder when they share the same title and contain a usable `References` block.
- `references_source_path` may also be a `.ris` file exported from a reference manager.
- Keep `Evidence Attachments` in every comment block, even when no image or table is available.
- `--resume` skips already-materialized upstream artifacts so a rerun does not silently overwrite previously curated units.
- `--resume` also checks stored input fingerprints; if comments/manuscript/SI/attachments/reference/paper-search inputs changed, the rerun fails fast instead of trusting stale artifacts. 失败提示里会引导用户改用 `--resume-keep-unaffected`。
- `--resume-keep-unaffected`：返修一作常天天改稿，一处改动即触发上面的全量重建、丢弃已 curated units。加此 flag 后，若本次改动仅涉及内容输入（comments/manuscript/SI）且**未触及任何已定位的 comment unit**（重新原子化到临时目录后比对：无 comment 文本增删改、且没有 unit 锚定的 section 正文变化），则保留全部 curated units、更新输入指纹后续跑；若有 unit 受影响则**列出受影响的 comment_id 并 fail**（curation 与原子化耦合，无法只重生成受影响 units 而不清空其它 curation，须重新 curation 后 `--force-rebuild`）；若改动涉及非内容输入（journal_style/runner/文献/预算等全局项）也 fail（无法按 unit 局部化）。注：即便保留续跑，若原稿段落发生插入/删除导致全局段落索引漂移，最终 in-place 导出仍会在身份校验处硬停（见 export_docx P1），属预期 fail-safe。
- `--resume` must also fail fast when the stored skill signature differs from the current script tree signature.
- `--resume-from <step>` must clear the selected step and all downstream generated artifacts, then rebuild only from that step onward under the same verified input fingerprint.
- `--force-rebuild` clears generated project artifacts, including `data/` and citation intermediate files, and reruns the pipeline from scratch inside the same `project_root`.
- `state_manager.py refresh` must materialize `state/section_digests.json` and `state/comment_registry.json` before `revise_units.py` starts.
- `revise_units.py` must write `state/comment_windows/<comment_id>.json` and `state/write_cycle_reports/<comment_id>.json` for every comment unit, then append `state/comment_cycle_log.json`.
- `--live-citation-verify` enables online title/identifier verification when `paper-search` results are provided; pipeline mode should be recorded in preflight output.
- `final_consistency_report.md` should list each `needs_author_confirmation` item with a blocker type and the exact stored reason.
- `final_consistency_report.md` should also summarize reference coverage status, including detected numeric citations, reference entry count, and missing reference numbers when present.
- `final_consistency_report.md` should also report whether `reference_search_required=true` and the current `reference_search_decision`.
- `final_consistency_report.md` should also summarize intake mode, expected mode, state-window budget, section digest counts, and comment-window counts.
- Word export should render common markdown emphasis and list markers as real Word formatting instead of leaving raw `**...**` and list prefixes in the document body.
- `response_to_reviewers.docx` should include a visible heading hierarchy plus a TOC field, centered header text, and footer page-number field so the exported package is review-ready rather than plain-text only.
- `export_docx.py` should support profile-based manuscript export via `--journal-style`, with distinct body/title/heading/reference/table styles for at least `journal-manuscript`, `nature-review`, `cell-press`, and `lancet-review`.
- Markdown pipe tables in manuscript or response markdown should be rendered as actual Word tables rather than plain paragraphs.
- Response block labels such as `Text / Image / Table` should be rendered with a dedicated Word paragraph style so exported reviewer-response documents keep a consistent block structure.
- If `reference_search_decision=approved` and `--auto-run-reference-search` is enabled, the pipeline should invoke a local runner hook via `execute_reference_search.py`; this runner must still obey `review-writing` governance and may only emit `paper-search` rows.
- If approved auto-run is requested but no local runner is configured, the pipeline must fail explicitly and write `reference_search_execution_request.md` instead of pretending that search has already been executed.
- The local runner contract must remain machine-checkable: `--rounds-json <path> --output <path> --project-root <path>`, with output saved to `project_root/paper_search_results.json`.
- Approved search auto-execution must rerun `citation_guard.py`, `revise_units.py`, literature-index/matrix steps, `reference_sync.py`, and `build_reference_registry.py` before export and gate.
- If no explicit local runner is provided but `opencode` is available, the workflow may fall back to an internal `opencode run` driver that still writes the same `paper_search_results.json` schema under `review-writing` governance.
- The `opencode` fallback must write a preserved prompt file (`reference_search_opencode_prompt.md`) and an execution report (`reference_search_execution.json`) so the retrieval path remains auditable.
- `strict_gate.py` and `final_consistency_report.md` should surface `reference_search_execution.json` state instead of hiding the actual execution mode.
- Query hints for approved search should come not only from missing reference coverage but also from pending citation-oriented review comments that still point to `paper-search` as a required evidence source.
- Lexical paragraph localization should use structured fields with low-signal-token filtering and heading-weighted scoring; if the best lexical candidate is still low-confidence, keep the item in `needs_author_confirmation`.
- Reviewer-response Word export should use dedicated body, reviewer-heading, label, and comment-heading styles, with improved spacing and Word-native table header shading, rather than leaving all blocks as generic paragraphs.
- Automatic manuscript rewriting must stay at the changed-fragment level. `revise_units.py` should replace only the targeted sentence, or append only the new limitation sentence, rather than rewriting the entire paragraph.
- A dedicated `polish` stage must run after `revise` and before literature/reference merge. This stage consumes only `revision_plan.raw_fragment`, never untouched original sentences.
- The polishing stage must follow `article-writing`, `review-writing`, and `humanizer-zh` constraints together: direct evidence-bounded wording, no invented claims, no new citations, no banned AI phrases, no decorative transitions, and no paragraph-wide rewrite unless the new content is itself a new paragraph.
- The polishing stage must emit `revision_polish_manifest.json`, `revision_polish_prompt.md`, and `revision_polish_execution.json` so the anti-AI prompt, driver mode, and candidate coverage remain auditable.
- `strict_gate.py` must verify that completed revised fragments with a non-empty `revision_plan.scope` have polish state, a valid `polish_driver_mode`, and no residual banned AI-style markers.
- The polishing prompt must be layered, not flat. It must include: role definition, non-negotiable edit/evidence/citation/length constraints, deep anti-AI rewriting protocol, and a JSON-only output contract.
- **Polish anti-AI 去AI五项（适用于中英文改稿正文）。硬/软分层：写作时五项都要守；门禁对「主干」硬失败，套话禁词、scare quotes、解释性冒号、-ing 假分析从句、**装饰性破折号**这类真正的 AI 味硬拦（fail-close）；只把「句长 >30 词」降为软提示（`strict_gate.py` 响亮上报、不 fail-close）。装饰性破折号禁止使用，命中即 FAIL。**
  1. **禁装饰性破折号（🔴 硬门禁，禁止使用，命中即 FAIL）**：禁用 —/——/em-dash 充当停顿、补充或强调（如"该结果——尽管样本量小——表明…"）；改用逗号、句号或拆为两句。连字符（"dose-response"）与数值范围不受限。中英文均适用。`strict_gate.py`/`polish_guard` 对破折号 fail-close，不放行。
  2. **禁 scare quotes**：禁用双引号包裹自造词或普通短语以暗示"新概念/反讽"；保留：术语首次定义、原始审稿人评论直接引用、已固化的术语隐喻。**HTML/代码结构引号豁免**：本条只管正文散文；HTML 标签、属性、内联样式与代码里的结构性双引号（如 `id="sec-1"`、`class="panel"`、`<a href="...">`）是代码语法、不是 scare quotes，**一律不得删除、改写、转全角或转弯引号**——动了会破坏 HTML 渲染，去 scare quotes 绝不触碰 markup 与代码。
  3. **禁解释性冒号**：禁用"概念: 解释"或"Concept: explanation"格式的装饰句式；合法冒号包括比例、时间、列表引导、标题、图表标签。
  4. **英文单句 ≤30 词（🟡 软提示，不阻断）**：polished 片段中任何独立英文句子（以 `.!/? ` 分界）词数应 ≤30 词；超限建议拆句、不要用分号逃避拆句。**句长超限只在 `strict_gate.py` 软提示 banner 上报，不 fail-close**（`sentence >30 words` 已归入 `SOFT_STYLE_MARKERS`）。**禁止 -ing 分词从句作假分析**：形如 `, reflecting …` / `, ensuring …` / `, highlighting …` / `, suggesting …` 的尾置 -ing 从句禁止用于添加未经数据支撑的推断；已有明确证据锚点的 participial phrase 不受此限。`find_ai_style_markers` 中 "trailing -ing clause" 检测已覆盖以 `,\s*(thus|thereby|therefore)\s+[a-z-]+ing` 模式；追加覆盖 `, (reflecting|ensuring|highlighting|suggesting|demonstrating|indicating|revealing)\b` 模式。
  5. **中文单句 ≤50 字、从句 ≤2 层**（如正文含中文）：任何中文句子（句号/问号/感叹号分界）字数不得超过 50 字；嵌套从句层数不超过 2 层（如"A（B（C））"为第 3 层，须拆分）。连续 3 句字数差异 <5 字时应主动变换句长。
  6. **禁比喻与连续同式排比（比喻软/新写禁，排比硬）**：原稿作者已有的比喻（"如同/犹如/像…一样"及"…的桥梁/基石"类、like…/as if…/serves as a bridge/cornerstone）标为软提示交作者定夺、不自动删改；但改写时**模型自己新写的句子禁止新增比喻**。**禁连续≥3句相同起始词或句式框架的排比**（parallel structure repeated across 3+ consecutive sentences）——合并或改写变换句式。
  - **硬/软实现**：`common.hard_ai_style_markers()` 返回会 fail-close 的主干标志（套话/scare quotes/解释性冒号/-ing 假分析/not only…but also/反问/**em dash 破折号**等）；`common.soft_ai_style_markers()` 只返回软项（`sentence >30 words`，即 `SOFT_STYLE_MARKERS`）。`polish_revisions.py` 的 `polish_guard_ok` 与 `strict_gate.py` 的 polished-fragment 校验都对 hard 子集 fail（破折号在内）；soft 项由 `strict_gate.py` 汇总为「去AI软提示」banner 逐条列出、并写入 unit 的 `polish_soft_style_flags`，不阻断。中文句长/从句层数为软警告，记录于 `notes`。
- `revision_plan` should carry `locked_prefix`, `locked_suffix`, `evidence_boundary_note`, and `citation_strings` so the polishing step can preserve untouched context explicitly rather than infer it.
- The polishing output schema should include `edit_decision`, `meaning_changed`, `scope_respected`, `ai_style_flags_removed`, and `notes`.
- `strict_gate.py` must fail if a polished revision reports `meaning_changed=true`, `scope_respected=false`, or if reconstructed paragraph text no longer preserves the locked prefix/suffix context.
- **Polish 片段级守卫（A/B/C/MID，仅比对锁定的 `raw_fragment` 与 `polished_fragment` 两个字符串，不破坏 scope-lock）：**
  - **A 数值守卫**：`common.numeric_tokens_preserved(raw, polished)` 抽取数字 token（整数/小数/百分比/p 值如 `p=0.03`/`CI`/`n=N`）并比对集合。polished 引入原片段没有的新数值，或丢失原有数值，视为 numeric drift。`polish_revisions.py` 写入 `polish_numbers_ok`，`strict_gate.py` 不通过则 fail。
  - **B 不确定性动词校准**：`common.detect_certainty_upgrade(raw, polished)` 只拦截证据强度被升高的方向。谨慎动词（may/might/could/suggests/indicates/is associated with/appears/is consistent with）被升级为强断言（demonstrates/proves/establishes/confirms/shows definitively）即判越权加强，符合保守哲学。写入 `polish_certainty_ok`，`strict_gate.py` 不通过则 fail。
  - **C Risk Flags**：上述拦截在 fail 之外额外输出结构化清单 `polish_risk_flags: [{type: numeric_drift|certainty_upgrade|overstatement|invented_claim, fragment_id, detail}]`，写入每个 unit、`revision_polish_execution.json` 与对应 `comment_records/<id>.md`。**fail 行为保留，不放行。**
  - **MID 禁词表**：`common.AI_CLICHE_TERMS_EN`（本家 `scripts/common.py` 自带，口径与其他撰写类技能的禁词表一致：moreover/delve into/it is worth noting 等）+ `AI_CLICHE_TERMS_ZH`（值得注意的是/综上所述等），由 `find_ai_style_markers` 在 polished 片段上检测套话词，命中归入 overstatement 风险并阻断门禁。
- `strict_gate.py` must also fail if `comments_input_mode` is unsupported, `expected_comments_mode` and detected mode diverge, or the required state-window artifacts are missing.

## Character-level typography contract（字符级排版契约）

Applies to all newly written or rewritten content (revised fragments, new sentences, response-letter prose). These inline markers are rendered into real Word character formatting by `scripts/export_docx.py` (bold/italic/superscript/subscript runs). This contract governs the markers you emit when authoring new text. **Reading the original docx now preserves run-level formatting too**: `read_docx_paragraphs(..., inline_format=True)`（仅 `atomize_manuscript.py` 开启）把原稿 run 的 italic/bold/sup/sub 序列化成同一套行内标记进 section text/current_text，所以未改片段的原格式经 revise→export 往返不丢；被改片段也按同一套标记在 in-place 写出时重建 run。默认读取器仍为纯文本（`inline_format=False`），数值/引用/AI 风格红线比对不受标记污染。

- **Italic** via `*...*` for: species Latin names (`*E. coli*`, `*Staphylococcus aureus*`), gene names (`*TP53*`, `*BRCA1*`), single-letter statistical symbols (`*p*`, `*t*`, `*n*`, `*F*`, `*r*`), and Latin abbreviations (`*in vitro*`, `*in vivo*`, `*et al.*`, `*e.g.*`, `*i.e.*`).
- **Superscript** via `<sup>...</sup>`: exponents and powers (`10<sup>6</sup>`, `cm<sup>2</sup>`, `mg·kg<sup>-1</sup>`). **Subscript** via `<sub>...</sub>`: chemical subscripts and indexed terms (`H<sub>2</sub>O`, `CO<sub>2</sub>`, `IC<sub>50</sub>`, `T<sub>max</sub>`). **Never** emit bare `H2O` / `CO2` / `IC50`.
- **Bold** via `**...**` only for headings and inline labels (e.g. `**Limitations.**`), never for emphasis inside running scientific prose.
- 中文回复部分：句内标点全角（，。：；），英文与数字保持半角，中英文之间不强制空格但须一致。

These inline markers are load-bearing and carry the same status as citation markers `[n]`: when rewriting a locked fragment, **do not add, drop, or mis-pair** them. Adding `*`/`<sup>`/`<sub>` where the source had none, or stripping existing ones, is a meaning/format drift and is subject to the same fragment-only and scope-lock rules as `[n]`.

## ❌ 反例黑名单（Anti-Patterns）

- ❌ 跳过 `intake_router.py` 直接跑 `run_pipeline.py`，或输入源未分类／不支持仍硬跑（preflight 须 fail-fast，不得猜分支）。
- ❌ 重写整段而非只改目标句或只追加新句（fragment-only，`revise_units.py` 只动 `revision_plan` 锁定的片段）。
- ❌ 把全文加全部意见塞进一个上下文窗，违反防遗忘 token 预算，须用 comment-scoped state window 逐条加载。
- ❌ 虚构实验、数据、统计或引用来回应意见；缺信息须写 `Not provided by user` 或 `需作者确认`。
- ❌ 用 websearch／tavily／openalex 补文献；只允许 paper-search，且新引用须过 `citation_guard` 双向核验。
- ❌ 段落定位模糊却硬选一个段落；多候选评分相近时须落 `needs_author_confirmation`，不得激进选段。
- ❌ 把实质性请求（新机制／新证据／新图／未匹配章节）当 `completed` 自动收口；只有保守的纯文本澄清或限制句可 auto-complete。
- ❌ Patch 修订哈希不符仍强行套用或自动重定位（fail-closed，整批拒绝、写空、退非零，不静默部分应用）。
- ❌ 去 AI 主干未过（硬）：scare quotes、解释性冒号、套话禁词、-ing 假分析从句、**装饰性破折号（🔴 硬门禁，禁止使用，命中即 FAIL）**。（仅英文 >30 词为软提示：上报不阻断，但仍应改。）
- ❌ 主 agent 自评 DoD 当通过；`strict_gate.py` 前须委托独立subagent盲检，verify 未 exit 0 不得声明改稿完成；盲检过后仍须摆逐项结论 + HALT 等用户确认才收口。
- ❌ 把「有意驳回不改（`push_back`）」误判成「漏改」，或反过来把真漏改的意见混进 push_back 蒙混；驳回必须在回复信据理反驳，正文不动但回应不能缺。
- ❌ 退稿信漏回某条意见，或某 `completed` comment_id 在 `manuscript_edit_plan.md` 中无 revised_excerpt 落点（`push_back`/`需作者确认` 不要求 revised_excerpt）。
- ❌ 补新文献只验真实性（DOI/PMID）就下笔，跳过「引文↔论点」核证；或用 `--offline` 跑 citation_guard 就交付（承重句须过 `citation_claim_check.py`，guard 须 `--live`）。
- ❌ 引文 `[n]` 与参考列表不对应、缺号或编号不连续就交付（`reference_coverage_audit.json` 须 ok=true）。
- ❌ `--resume` 时输入指纹或脚本签名已变仍信任旧产物，而非 fail-fast 重建。
- ❌ 改稿删/换句子时丢失某缩写的唯一首展、在首展前裸用 ABBR、新增术语不首展，或 Title 出现缩写（`abbreviation_index.json` 的 `undefined_use` / `duplicate_definition` / `title_abbreviation` 硬错须清零）。
- ❌ 改写锁定片段时增删或错配行内排版标记（`*italic*` / `<sup>` / `<sub>` / `**bold**`），等同于篡改引文标记 `[n]`；裸写 `H2O`/`CO2`/`IC50` 或漏给物种名、基因名、统计符号加斜体。

## Definition-of-Done (DoD) 自检清单（改稿收口）

**位置**：polish 完成后、`strict_gate.py` 运行前。**硬规则：清单未逐项确认通过，不得向用户声明"改稿完成"。**

**🔴 委托盲检（不得主 agent 自评）**：改稿完成后自评容易默认通过且漏项。`strict_gate.py` 运行前必须把 DoD 清单**委托给独立上下文的subagent盲检**，不得自己直接打勾：

1. 生成任务包：`python scripts/delegate_review.py pack --checklist references/dod_checklist.json --gate revision-dod --files <改稿相关文件> --comments <comments_path>`（`--comments` 传本次审稿信原文，盲检子代理据原信逐条点名核对漏回/答非所问；同一 `comments_path` 与 `run_pipeline.py --comments` 一致）
2. **派一个独立subagent**（Claude Code 用 `academic-blind-reviewer`；其他平台派通用subagent），把任务包原样给它、**不要给它本次改稿的写作上下文**，要求按任务包返回 JSON 数组。
3. 校验返回：`python scripts/delegate_review.py verify --checklist references/dod_checklist.json --gate revision-dod --return <subagent返回.json>`；退出码非 0（任一缺项/fail/无证据）= **fail-closed**，据subagent证据修复后重跑，**未过不得声明改稿完成**。

> ⚠️ **盲检降级告警**：若当前环境派不出真正独立的subagent（非 Claude Code 客户端、provider 不支持 Task/子会话），**绝不能用同一个 AI 自问自答冒充盲检**（那就是自证）。此时明确告诉用户：「本环境盲检不可靠，请你亲自复核这几点：__（列出该盲检本应查的关键点，如 RV-G1 引文↔参考一一对应、RV-G3 改动是否跑题、RV-G5 去AI五项、RV-G7 缩略语首展、RV-G8 常识/事实错误等）__」，把判断权交回用户，不得伪造一份"通过"的盲检返回。

下列清单与 `references/dod_checklist.json` 逐项对应（**改清单先改 JSON，再同步此处散文**）；能脚本核的项subagent会先跑脚本：

### 通用 8 项（id: RV-G1 ~ RV-G8）

| id | 项目 | 核验方式 |
|---|------|---------|
| RV-G1 | 引文 `[n]` ↔ 参考列表一一对应，无孤儿引用、无缺号，编号连续 | `python scripts/build_reference_registry.py` → `data/reference_coverage_audit.json` ok=true |
| RV-G2 | 本轮新增引用已过 citation_guard 双重核验 | `python scripts/citation_guard.py` → ok=true，无 manual_review 条目 |
| RV-G3 | 改动符合原文 storyline / 主线（不跑题，不与原文主线矛盾） | 人工对照 `issue_matrix.md` 逐段核查（无脚本可自动核验） |
| RV-G4 | 占位符清零：无 `CITE_PENDING` / `DATA_PENDING` / `【待AI】` / `{{` 残留 | `grep -r "CITE_PENDING\|DATA_PENDING\|待AI\|{{" <project_root>/` 零命中 |
| RV-G5 | 去 AI 五项（破折号/scare quotes/解释性冒号/英文≤30词/-ing从句/中文≤50字≤2层从句）通过 | `python scripts/strict_gate.py --project-root <project_root>` → `ai_style_flags_removed` 无残留；句长警告记录于 notes |
| RV-G6 | 字数达标（改动前后正文字数在期刊要求范围内） | 人工或期刊要求核对 |
| RV-G7 | 缩略语首展一致：`abbreviation_index.json` 无 `undefined_use` / `duplicate_definition` / `title_abbreviation` 硬错；改稿未破坏既有首展，Title 不含缩写（`defined_unused` 为软警告可人工豁免） | `python scripts/manuscript_index.py --manuscript <output_md> --project-root <project_root>` 后读 `abbreviation_index.json`，硬错 orphan 零命中（启发式索引，可疑项人工复核） |
| RV-G8 | **Commonsense sanity (🟡 soft report, non-blocking)**: the blind-review subagent also scans rewritten fragments for obvious commonsense/factual errors (absurd unit magnitudes, physiology/mechanism mistakes, internal numeric contradictions) introduced by the rewrite. Report only, never block delivery, never auto-edit content. Distinct from the citation/reference verification gates (RV-G1/RV-G2) and from reviewer-simulator's full scientific audit. | 盲检subagent LLM 判断（复用现有 `delegate_review` 盲检机制，无新脚本）；命中只在subagent返回 `notes` 报告，软项不进 `strict_gate.py` 硬失败、不计入 `delegate_review verify` 的阻断退出码（与 `references/dod_checklist.json` 硬门禁互不冲突） |

🔴 收口前置闸口：`delegate_review verify` 必须 exit 0（含 RV-R8 结构完整性），否则不得声明改稿完成。任一项 fail 均为阻断。

🛑 **DoD 停·摆结论等确认（strict_gate 前的最后一道人工闸）**：盲检 `delegate_review verify` exit 0 之后、`strict_gate.py` 之前，**不得直接收口**。先把逐项结论摆给用户，每条 DoD（RV-G1~G8 / RV-R1~R12）是 pass / na / 🟡soft-report，软项（RV-G8 常识、RV-R12 拉丁斜体、去AI软提示、句长）列出但标明不阻断；同时给「意见 × 是否回复 × 是否改稿 × 结局（completed/push_back/需作者确认）」对照表。**打印后 HALT，等用户明确说「可以收口」再跑 `strict_gate.py` 并交付**。用户没确认就继续 = 违规。这与开场监工卡、清单核对是三道不同的人工闸：开场提醒 → 拆完核对 → 收口前摆结论。

### Revise-Sci 特有项（id: RV-R1 ~ RV-R12）

| id | 项目 | 核验方式 |
|---|------|---------|
| RV-R1 | `strict_gate.py` 通过（exit code 0） | `python scripts/strict_gate.py --project-root <project_root>` → `STRICT_GATE: PASS` |
| RV-R2 | Reference coverage 无缺口：`data/reference_coverage_audit.json` `ok=true`，无 unresolved numeric/author-year gap | `python scripts/build_reference_registry.py` → coverage_audit 直接读；或 RV-R1 覆盖 |
| RV-R3 | Patch 修订哈希一致（如使用 Patch 修订协议）：`apply_revision_patch.py` 未报告任何 hash mismatch，所有未触及 block 字节不变（fail-closed，哈希不符则整批拒绝，不得静默部分应用）；未使用则标 na 并注明 | `python scripts/apply_revision_patch.py --manifest <block_manifest.json> --patch <patch.json> --output <revised.md>` exit code 0 |
| RV-R4 | 退稿信每条意见有落点：`issue_matrix.md` 每个 `comment_id` 在 `manuscript_edit_plan.md` 中有 revised_excerpt | `python scripts/strict_gate.py --project-root <project_root>`（strict_gate 内含此检查，RV-R1 通过则本项通过） |
| RV-R5 | 审稿意见已原子化：`atomize_comments.py` 在 pipeline 中已运行，每条意见有 severity 字段，comment_id 唯一，无混合意见跨意见合并改动 | 人工确认 `state/comment_registry.json` 已生成且 comment_id 唯一（`atomize_comments.py` 无 --dry-run flag，须通过 pipeline 正式运行核验） |
| RV-R6 | polish 状态完整：所有含非空 revision_plan.scope 的片段已有 polish state，无 meaning_changed=true 或 scope_respected=false | `python scripts/strict_gate.py --project-root <project_root>`（strict_gate 内含此检查，RV-R1 通过则本项通过） |
| RV-R9 | polish 片段级守卫通过：每个 polished 片段 `polish_numbers_ok=true`（无数值漂移/丢失）、`polish_certainty_ok=true`（谨慎动词未被升级为强断言）、无套话禁词残留；`polish_risk_flags` 已落盘到 unit / `revision_polish_execution.json` / `comment_records/<id>.md` | `python scripts/strict_gate.py --project-root <project_root>`（strict_gate 内含 A/B/MID 三项检查，RV-R1 通过则本项通过） |
| RV-R7 | response_to_reviewers.docx 结构完整：每个 comment block 都有 comment heading / response-section heading / evidence-section heading | `python scripts/strict_gate.py --project-root <project_root>`（strict_gate 解析 docx 核验结构，RV-R1 通过则本项通过） |
| RV-R8 | 结构完整性：改后稿件结构完整（原结构无破坏、参考文献编号连续、response 各 unit 三要素齐全）；退稿信每条意见在 edit_plan 中有落点无遗漏 | `python scripts/strict_gate.py --project-root <project_root>`（RV-R1 通过则本项通过）；或人工逐段核查 |
| RV-R10 | 跨节一致性盲检（全局层，超出片段级 RV-R9）：改稿后关键数值/样本量/效应量/主要结论在摘要-正文-图表-结论间仍一一对应、无新引入矛盾；改动未把原谨慎表述升级为新过度声称（因果化/普适化/夸大疗效）。跨节不一致或新增过度声称=fail，列冲突两处原文为证 | `python scripts/cross_section_consistency.py --project-root .`（客观信号）+ 盲检subagent据此判定 |
| RV-R11 | 语法拼写与字符级格式：对原子化正文 `manuscript_sections/` 跑字符级体检。高置信类别 **misspelling**（英文常见错拼）/ **chinese_punct**（中文标点漏入英文句）/ **subsup_bare**（H2O、IC50、cm² 等应上下标却裸写，含 CJK 安全边界）**零容忍**：命中任一即 `fail_on_hits` 非空、`ok=false`、退出码非 0；其余类别（学术错拼/中文错字/单位/英美混用/数字格式/术语不一致/Methods 时态/断链）**仅报告不阻断**。**只报告供用户决断，绝不自动改正文**（fragment-only 保真），命中后由用户决定是否回片段修订 | `python scripts/proofread.py --manuscript-dir manuscript_sections --report proofread_report.json --fail-on misspelling,chinese_punct,subsup_bare` → `ok=true` 且 `fail_on_hits` 为空 |
| RV-R12 | 拉丁短语斜体软提醒（🟡软/人工确认，不阻断）：`proofread.py` 的 `latin_italic_missing` 类别，正文里 `in vitro`/`in vivo`/`ex vivo`/`in situ`/`de novo`/`post hoc`/`per se` 等公认须斜体的拉丁短语若裸写（未被 `*...*` 斜体标记包裹）则报告。**仅提示，不阻断、不进 `--fail-on`、不扣分**，由人工确认是否补斜体（`et al.`/`e.g.`/`vs.` 等正体惯例不在词表内） | 同 RV-R11 脚本，读 `proofread_report.json` 中 `latin_italic_missing` 计数供人工决断，不影响 `ok`/退出码 |

> RV-R3 仅在使用 Patch 修订协议时适用，跳过需在 notes 中注明原因。RV-R4/R6/R7/R8/R9 已由 strict_gate 覆盖，RV-R1 通过即视为通过；RV-R5 须确认 pipeline 正式运行产出 comment_registry.json。RV-R10 为跨节一致性全局盲检（独立脚本 `cross_section_consistency.py` + subagent判定），**不由 strict_gate 覆盖**，须单独核。

### 投稿前作者自检（🟡 soft 提醒，不阻断交付）

终稿交付前，对照 `references/presubmission_checklist.md` 过一遍（数字一致性、英美拼写统一、图像无不当处理、Source Data、查重、临床注册号、报告规范附件、投稿材料齐全等）。这些项多需作者掌握原始数据/图像/外部工具，机器无法可靠裁决，故**只提醒、不阻断**；与本技能既有 hard 门禁（引用一一对应、去AI、跨节一致、字符级体检 RV-R11 等）不重复。

## 发现 AI 跳步/漏做了怎么办（用户自救）

如果你怀疑 AI 拆意见拆漏了、改稿改跑了、或直接把半成品当成品交付，下面几句话可直接复制发给它，逼它回到正轨：

- 「审稿信里 Reviewer X 第 N 点你没拆出来，回去把它作为独立 comment 加进 `units/`，重新原子化再重跑 `revise_units.py`。」
- 「把第 X 条对应的**原句**和你**改后的句子**并排贴给我，我要确认意思没变、没夹带我没同意的新结论。」
- 「给我一张表：每条审稿意见 × 有没有回复 × 正文改了哪句（引用 `manuscript_edit_plan.md` 的 revised_excerpt）。哪条空着就是漏了，当场补。」
- 「先别跑完整 pipeline，先只跑到 `atomize_comments.py` 把意见清单给我看，我对照原始审稿信确认条数无误了再往下。」
- 「你这环境派不出独立subagent就别假装盲检通过了。把这轮该盲检的关键点列给我，我自己核。」
