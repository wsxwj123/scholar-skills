> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

# Required Workflow：Step 0 – Step 8、Step 10 与节级/章级 DoD（Step 9 全文总检见 full-thesis-checks.md）

### 0) Material Input Gate (Mandatory)

**Degree & target confirmation (must ask before anything else):**

AI must ask the user two questions before proceeding:

1. **Degree type**: doctoral (博士) or master's (硕士)?
2. **Body word count target**: defaults are doctoral ≥50,000 / master's ≥30,000; confirm or let user specify a different number.

Record answers into `thesis_profile.json > format_profile.degree_type` and `targets.body_target_chars` during `init` / `profile` step. Do not proceed to material extraction until both are confirmed.

Before initializing any project, also verify:
- Source materials (PDF/Word SCI papers + supplementary figures) are accessible at a known local path.
- User has provided: thesis topic, research chapter count estimate, target university (or explicit consent to use the built-in default template).

If source materials are missing or inaccessible, **stop and request them**. Do not proceed to Step 1.

**[可选] 多格式原始材料落盘：** 若用户除 SCI 论文外还提供了其他原始材料（实验数据 Excel/CSV、组会笔记 md、参考 PDF/Word、结果图片等），在提取 SCI 论文文本前先运行材料落盘脚本，把素材分析写进 `materials/` 目录，供后面按章写作时引用取证：

```bash
python3 scripts/material_ingest.py --dir /path/to/raw_materials --save-path "${save_path}"
# 或指定文件列表：--list file1.xlsx file2.md fig1.png
```

落盘完成后，`materials/materials_archive.json` 为素材总索引，每个材料对应一个 `materials/<name>.md`（含可引用要点、表结构/数值范围、图片待确认标记）。后续写作时，引用数值/结论必须能追溯到对应 entry，不得凭空生成。图片类材料标记 `pending_confirm`，须等用户口述或补充图内容后方可引用。详细规则见 `references/material_ingest_guide.md`。

**SCI 论文内容提取（必做）：** 确认材料可访问后，在进入 Step 1 前，必须将 SCI 论文内容提取为可读文本：

- **PDF 格式** → 使用 `/pdf` skill（`pdf-viewer:view-pdf`）逐页阅读，或在用户本地运行：
  ```bash
  # 使用 pdfminer 提取（无需联网）
  python3 -c "import pdfminer.high_level; print(pdfminer.high_level.extract_text('paper.pdf'))" > paper_text.txt
  ```
  若 pdfminer 未安装：`pip3 install pdfminer.six`
- **Word 格式** → 使用 `/docx` skill 或直接 Read 工具读取文件内容
- **网络来源（DOI 可访问）** → 使用 `/fetch-everything` skill 抓取全文

**[docx/pdf 源稿] 内嵌图抠出（必做于 atomic_md_workflow 之前）：** 支持 docx 与 pdf，运行下面这一步把内嵌图按出现顺序解到 `figures/`，供后续按章节嵌图与 `figure_registry.py` 使用（pdf 需 PyMuPDF，缺失则优雅跳过；其他非 docx/pdf 输入自动 no-op，安全可重复运行）：

```bash
python3 scripts/extract_docx_images.py --manuscript /path/to/source.docx --project-root "${save_path}"
```

产出：`figures/figure_NN.<ext>` + `figures/image_manifest.json`。脚本只搬运二进制，不做 OCR / 图像识别；图片对应到章节图号的映射仍走 `figure_registry.py` 注册流程。

提取完成后，AI 应先通读全文摘要（Abstract）、结果（Results）、方法（Methods）三节，大致读懂做过哪些实验，再进入 Step 0.5。

**SCI 自身参考文献导出（初始种子）：** 在通读的同时，同步扫描源 SCI 论文的 References 部分，将其中每条参考文献按 `literature_index.json` schema 格式整理为初始种子条目，`source_provider` 填 `"sci-source-seed"`，`verified` 填 `false`，写入项目的 `literature_index.json`（若文件已存在则 merge 而非覆盖）。这些种子作为 Step 3 文献检索的**待核验候选清单**（已带 DOI/PMID，省去重新构造检索式、确定检索目标的成本），而非可直接引用的来源。注意：`sci-source-seed` 不在 `citation_guard.py` 的合法 provider 白名单（`pubmed-cli` / `paper-search`）内。种子条目必须在 Step 3 以其 DOI/PMID 为目标经 `pubmed-cli` 或 `paper-search` 正式检索核验，核验通过后将 `source_provider` 更新为实际核验来源并置 `verified=true`，方可引用；未核验的种子不得进入正文。

> 以下各步只列命令名 + 关键参数 + 门禁条件。**完整可复制 CLI（含所有 flag、占位符）见 `QUICK_START.md`。**

---

（开场监工卡在 SKILL.md 正文，位于 Step 0 与 Step 0.5 之间，须原样输出给用户。）

### 0.5) Research Storyline Design (Mandatory)

> **执行时机：** Step 0（材料确认 + 内容提取）完成后、Style Selection Gate 前执行。

通读 SCI 论文材料的 Abstract / Introduction / Results / Discussion 后，AI **必须**与用户共同确定"研究主线"并产出下表，写入 `project_state.json` 的 `outline` 字段（每章一条记录）再进入 Step 1。

**强制产出：科学问题 → 贡献映射表**

| 字段 | 说明 |
|------|------|
| `scientific_question` | 全论文核心科学问题（一句话，来自材料，不得自造） |
| `chapters[]` | 每章：章号、章名、对应 SCI 论文/图组、本章核心论点、承载主要内容（300字以内） |
| `contribution_map` | 各 SCI 来源 → 对应章节（避免章节撞题） |

**写入格式（project_state.json `outline` 数组，每条一章）：**
```json
{
  "chapter": 2,
  "title": "XX对XX的影响",
  "sci_source": "Paper A, Figure 1-3",
  "core_argument": "XX通过XX机制发挥XX作用",
  "estimated_content": "材料方法+结果讨论，主实验3个，预计图表各3"
}
```

🔴 **门禁（阻断 Step 1）：** `outline` 数组为空时不得进入 Style Selection Gate。`outline` 必须包含：`scientific_question`（顶层字段）+ 所有研究章条目（含 `sci_source` 和 `core_argument`）。

**章节字数协商在此阶段完成（不在 init 后）：** 基于各章实际承载内容（实验数量/图表数量/方法复杂度），与用户协商每章字数目标，写入 profile 的 `chapter_targets`，再执行 Step 1 init。

> **[章节结构签字·强制门禁落锁]** 用户在对话里明确确认上面的研究主线 / 章节结构映射表后（且**仅在此之后**），运行开局 `env_preflight.py` 打印的那条 `SIGNOFF_CMD`（已含解析好的绝对路径）落盘签字。注意 `env_preflight.py` 在会话开场就运行（即本 Step 0.5 签字之前，见本文件开头第 1 条握手；它文档虽列在 Step 1，实际执行在最前），所以此刻 `SIGNOFF_CMD` 早已拿到，不存在签字时还没拿到命令的次序歧义：即 `python "<sci2doc>/scripts/structure_signoff_gate.py" confirm --root <项目根> --note "<用户确认原话摘录>"`。这一步解锁正文写作：**未落签字，PreToolUse hook 会在工具层拦下（deny）任何对 `atomic_md/*/*.md`（学位论文各章正文）的写入**（这是防跳步的硬门，不是提示词纪律：写文件类工具一律 deny，经 shell 的写入另有一条 Bash 钩子拦，任何绕行都会记进项目根的 `.academic_gate_audit.jsonl` 供用户复核）。这道拦截 hook 由 `env_preflight.py` 开工时经本技能 `scripts/install_gate_hook.py`（vendored）自动安装并校验，它先把门禁四件套部署到 `~/.claude/academic-gate/`（稳定位置，不随技能目录增删而动），再让 `settings.json` 的 hook 指向那里，单独分发的技能也能自装（带备份与回滚），门禁状态 active 即在岗；若报 degraded / error（如缺 `_shared`），拦截层不在岗，签字仅留痕、无强制，需人工守住「未签字不写正文」。若后续章节结构又改，改完让用户重新确认并重跑本命令覆盖签字。**签字与它签的那份大纲绑定**：节号/标题/层级/顺序任一变化（含只增不删的细化扩展），下次写正文会被门禁拦下并逐条列出哪几节变了，须由用户重新确认后重跑本命令；进度、统计、时间戳这类变动不触发重签。⚠️ 严禁在用户未确认时自行运行 confirm，那等于伪造用户签字。
>
> 注意：本签字闸管的是**章节结构确认**，与 `## Style Selection Gate`（样式/格式确认，阻断 init 与 docx 导出）是**两道独立的门**，各管各的，别混淆或相互替代。

### 1) Initialize Project

- **Env Precheck（软门禁，建项目文件前）**：`python3 scripts/env_preflight.py ${save_path} --cli esearch --py docx`，写 `env_status.json`，末行 `PRECHECK: OK|ASK|BLOCKED`。`BLOCKED`（Python 过低）→ 停并引导升级；`ASK`（缺 git/esearch/python-docx 等可选工具）→ **逐项问用户是否安装**并给指引，用户答"已装/不装"后才继续，后续再遇缺工具同此处理；`OK` → 继续。
- **Git Init（叠加在 snapshot 之上）**：`python3 scripts/git_checkpoint.py init ${save_path}`。git 可用且项目根不在他人仓库内时建 git 检查点，否则静默回退 snapshot。
- `state_manager.py init`：先二选一样式。`--format-mode default_generic` 或 `--format-mode custom`（+ `--university-name` / `--degree-type` / `--template-source` / `--missing-requirement`）。
- `state_manager.py profile --show` 验证；`render-front-matter` 手动重渲前置页；`profile --body-target/--abstract-min/--chapter-target ...` 写入已协商好的各章字数目标（应在 Step 0.5 中已与用户确定）。
- 自定义结构化布局字段不全 → 保持 `pending_template`（最小必填字段见 `## Style Selection Gate`）。
- init / profile 必须自动刷新 managed front matter；无 managed marker 的用户改写文件不得覆盖。用户在聊天里给的详细要求应转成 JSON 经 `--format-profile-json` / `--project-info-json` 写入，而非仅留在 prose memory。

### 2) Prewrite Gate (Mandatory)

- `state_manager.py write-cycle --chapter N --token-budget 6000 --tail-lines 80 --json-summary`。每章每节必跑，加载跨章记忆。

### 3) Atomic Subsection Writing

- **🔴 开写前置闸门 (Mandatory，脚本硬拦截)**：每节开写前必须先跑 `python3 scripts/prewrite_gate.py --section X.Y --root .`（X.Y 为章.节，如 2.1），exit≠0 禁止开写。它统一硬检查：上一节完成（同章编号紧邻上一节 `atomic_md/第N章/{X.Y-1}_*.md` 存在非空）、大纲就位（`project_state.json.outline` 含本章 + `chapter_index.json`）、素材就位（`figures_index.json` 本章有图表/实验映射条目，无则降级 warning）、上一节占位符清零（无 `CITE_PENDING`/`DATA_PENDING`/`【待`）；上一节盲检结果（`.review_pass/<上一节>.json`）缺失即 prewrite_gate 硬拦 exit 1，禁止开写；必须先跑 delegate_review verify --section <上一节> 落盘通过标记。**⑥ 数据溯源硬门**：prewrite_gate 还会对上一节跑 `data_trace_gate`：上一节含实验数值却无有效 `[数据来源] materials/<档>#<字段>` 标记（或标记指向不存在的素材档/字段）即硬拦 exit 1（堵编数据）。
- **盲检逃生口（仅盲检子代理不可用时）**：本环境派不出独立盲检子代理（平台无 academic-blind-reviewer 或子代理反复失败）才可加 `--allow-manual-review "<非空理由>"`，对上一节或上一章章级盲检做显式人工放行。它只放行这两处盲检项，上一节文件/大纲/占位符/data_trace 等其余硬门照常拦。放行会写 `.review_pass/<sec>.json`（`manual:true`+理由+时间戳）并追加 `.review_pass/MANUAL_REVIEW_AUDIT.log` 留痕，绝非静默跳过；理由为空即拒绝放行。用了此逃生口等于承认盲检未做，须请用户亲自复核数据溯源与章节逻辑。
- **🟢 本节正文由撰写子代理盲写（主会话调度，堵上下文爆 + 焊死编号权）**：prewrite_gate 通过后，本节正文**不再由主会话直接手写**，改走下面这条流水线（前后所有门禁一个字不改，照跑）：
  1. **组任务包**：`python3 scripts/delegate_write.py pack-write --section X.Y --root .` → 生成 `.write_task_X.Y.json`（本节大纲/承重方向 + 已核证观点-证据对 `certified_claims` + `chapter_matrix` 切给本节的文献全条 + 缩写表 + 风格禁项**嵌入**，全篇大纲/全库文献只给 `refs` 路径）。承重句未完成人工核证 / 本节有承重论点却缺 `claim_evidence` → 脚本 exit 2 拒绝出包（先补核证）。
  2. **派撰写子代理**：把 `references/section_writer_prompt.md`（角色 prompt + 数据/指令隔离声明）+ 任务包路径交给一个**全新一次性上下文**子代理，让它盲写本节。它只写 `.write_return_X.Y.json`，**正文引用只写 `[@key]`（绝不写裸数字 `[5]`）**，承重句只准挂任务包内嵌 `certified_claims` 里的 `ref_key`，禁写任何账本。
  3. **机械校验返回**：`python3 scripts/delegate_write.py verify-write --section X.Y --root .`（V1-V9：无裸数字引用 / `[@key]` 可解析 / `new_refs` 带 DOI 或 PMID / `section_id` 一致）。exit≠0 打回子代理重写，不落盘。
  4. **new_refs 先核验再并表**（账本零污染）：对返回的 `new_refs` **先** `citation_guard.py --require-mcp` 核真伪，**通过的才** `python3 scripts/citation_renumber.py merge-refs --root . --return .write_return_X.Y.json` 去重并表（DOI→PMID→归一标题）+ 分配稳定 id + 同步 upsert `chapter_matrix`。核验失败的直接丢弃、打回子代理改写该处引用。
  5. **落盘正文**（主会话已结构签字，hook 放行）到 `atomic_md/第N章/`，随后照跑机械审（`citation_claim_check` 复核承重句、`data_trace_gate`、缩写、索引更新）。
  - **白名单琐节**（front/back-matter、无承重论点清单的节）：主会话就地写、不派子代理。
  - **试点期说明**：备料子代理与 `article_type` 落库属推广批未上；本期承重核证走主会话就地建 `claim_evidence.json`、引用类型纪律走本 prompt + 盲检兜底。
- **正文 `[@key]` 是长期真源，`[N]` 是章末派生**：原子 md 一直保持 `[@key]`；章末合并前跑 `python3 scripts/citation_renumber.py renumber --root . --chapter N --check`（exit≠0 若有未并表 `new:` 键 / id 冲突 / 未知键）通过后再 `--in-place` 把 `[@key]` 统一翻成连续 `[N]`（按 `reference_renderer.citation_sort_key` 同一排序，保证正文 `[N]` 与参考文献列表逐一对应）。
- 文件存于 `${save_path}/atomic_md/第{chapter}章/`，命名 `{section_number}_{section_title}.md`（如 `2.1_研究对象.md`）。
- **Table reminder**：呈现结构化数据（试剂/仪器/分组/统计）的小节 **必须** 用 Markdown 管道表，见 [Table Contract](#table-contract)，不得用散文描述。
- 校验：`atomic_md_workflow.py validate --chapter N`（加 `--enforce-research-structure`）+ `validate-experiment-map --chapter N`。**门禁：** 编号断裂 → 修复后才能继续。
- **⑥ 数据溯源标注（写作时必做，堵编数据）**：凡写入实验数值（浓度/剂量/比率/统计量等），该处必须紧跟标注 `[数据来源] materials/<素材档>#<字段>`，指向真实 `materials/*.md` 素材档里承载该数值的字段。落盘后自查 `python3 scripts/data_trace_gate.py --section X.Y --root .`，exit≠0 必须补标或删除无源数值，**追溯不到 materials 的数值就是编的，不得留在正文**。
- Post-write 必做：`abbreviation_registry.py process --file ... --in-place`，然后更新 `chapter_index.json` key_facts（AI 责任），再进 Step 4。

### 4) Subsection Summary Snapshot

- `atomic_md_workflow.py section-snapshot --chapter N --section X.Y`。每节小结完成即快照。
- **Git Checkpoint**：`python3 scripts/git_checkpoint.py commit ${save_path} "[sci2doc] section X.Y done"`（git 不可用自动 no-op，snapshot 仍兜底）。

#### 🔴 每节收口自检清单（Definition of Done · 节级）

**硬规则：以下各项未逐一确认通过，不得向用户声明"该节完成"。**

**🔴 进入下一节前置闸口**：上一节 `delegate_review verify` 必须 exit 0（含结构完整性项 S6），否则不得开始下一节。写完即检，不过不进。
**🔴 修复 3 次仍不过 → 回滚兜底**：同一节/章据盲检证据修复重跑 3 次仍 fail，停止盲目重写，提示用户回滚到上一检查点（git 可用 `git checkout <sha> -- <文件>`；否则 `state_manager.py rollback --target snapshot`）后重写。

**🔴 委托盲检（不得主 agent 自评）**：落盘前必须把 DoD 清单**委托给独立上下文的subagent盲检**，自己不直接打勾：
1. 生成任务包：`python scripts/delegate_review.py pack --checklist references/dod_checklist.json --gate section-dod --files <本节文件>`
2. **派一个独立subagent**（Claude Code 用 `academic-blind-reviewer`；其他平台派通用subagent），把任务包原样给它、**不要给它本节的写作上下文**，要求按任务包返回 JSON 数组。
3. 校验返回：`python scripts/delegate_review.py verify --checklist references/dod_checklist.json --gate section-dod --return <subagent返回.json> --section <当前节号如3.2> --root <项目根>`；退出码非 0（任一缺项/fail/无证据）= **fail-closed**，据subagent证据修复后重跑，**未过不得声明完成**。verify 通过会落盘 `.review_pass/<当前节号>.json`，下一节 `prewrite_gate.py` 会**硬校验**它（缺失即拒绝开写）。

> ⚠️ 若环境派不出真正独立的subagent，**绝不能同一 AI 自问自答冒充盲检**。告诉用户「本环境盲检不可靠，请你亲自复核数据溯源与章节逻辑」，交回用户。

**🔴 ①DoD停（盲检通过后必须停一次）**：`section-dod` 盲检 exit 0 后，**不得直接开写下一节**。先把该节 DoD **逐项结论**（每项 pass/证据一行）摆给用户，并**HALT 等用户明确说"过，继续下一节"**才动笔。用户未确认前停在此处。

**本节完整 DoD 判据（全部核查项 + 脚本命令）以 `references/dod_checklist.json` gate=`section-dod` 为唯一真源（20 项）**：盲检subagent据此逐项核、能脚本核的先跑脚本，退出码非 0 即 fail-closed。含 G1-G6 通用（编号连续/citation_guard/主线对齐/占位清零/去AI 硬禁三项标点/字数软目标）、S1-S5 sci2doc 特有（实验-方法映射/一实验≥一图表/三线表/缩略语首展/自我抄袭标注）、S-GIT 检查点，及 **S6 结构完整性、S10 数据溯源硬门（含数值却无 `[数据来源]` 标记=编数据嫌疑，fail-closed）、S11 承重引文核证，与 C1 科学事实正确 / I1 论证逻辑闭环 / O3 工作量与原创性 / O4 中英摘要对应 / M3 伦理合规披露 五项盲检质量核**。此处不再内联清单，避免与真源 drift。

### 5) Merge Chapter Markdown and Convert

- `atomic_md_workflow.py merge --chapter N --to-docx`。
- **硬门禁：** `format_profile.status == pending_template` 时 `markdown_to_docx.py` 拒绝生成 `.docx`，不得手动绕过转换器。

### 6) Chapter Self-Check (Immediate)

- `atomic_md_workflow.py self-check --target ".../02_分章节文档/第N章_自动合并.docx"`。
- 章节自检按 `chapter_targets` 判断，不卡全文参考文献下限（在全文总检卡）。`pending_template` 时 `check_quality.py` 同样拒绝格式验收（同 Style Gate 导出门禁）。

#### 🔴 每章收口自检清单（Definition of Done · 章级）

**硬规则：以下各项未逐一确认通过，不得向用户声明"该章完成"，不得进入 Step 7。**

> **[数据溯源·用户必抽验]** 学位论文里每个实验数值/每张图都必须能在原始 SCI 里找到出处。每写完一章，让 AI 给一张"本章数值/结论 → 源自原文哪张图/哪段"对照表，用户抽查几行（`data_trace_gate.py` 已机械校验 `[数据来源]` 标记，⑥）。⚠️ 字数目标已降为**软目标**（A③/C 降软，综述/绪论并入正文减压），就是为了不再逼 AI 靠编数据/扩实验凑字，追溯不到 materials 的数值就是编的。引文同样抽几篇验 DOI。

**🔴 进入下一章前置闸口**：上一章 `delegate_review verify` 必须 exit 0（含章结构完整性项 S8），否则不得开始下一章。写完即检，不过不进。现在 `prewrite_gate.py` 已对这道闸口硬校验，不再只靠提示词纪律：写下一章首节（如第 N 章的 N.1）前，它会读 `.review_pass/第<N-1>章.json`，缺标记或未 passed 即 exit≠0 硬拦。前提是上一章 chapter-dod 盲检已用 `delegate_review.py verify --section 第<N-1>章` 落盘通过标记。第 1 章首节无上一章，放行。

**🔴 委托盲检（不得主 agent 自评）**：章级闸口同样委托独立subagent盲检，不得主 agent 自评：
1. 生成任务包：`python scripts/delegate_review.py pack --checklist references/dod_checklist.json --gate chapter-dod --files <章节合并文件>`
2. **派一个独立subagent**（Claude Code 用 `academic-blind-reviewer`；其他平台派通用subagent），把任务包原样给它、**不要给它本章的写作上下文**，要求按任务包返回 JSON 数组。
3. 校验返回：`python scripts/delegate_review.py verify --checklist references/dod_checklist.json --gate chapter-dod --return <subagent返回.json>`；退出码非 0（任一缺项/fail/无证据）= **fail-closed**，据subagent证据修复后重跑，**未通过不得进入 Step 7**。

**🔴 ①DoD停（盲检通过后必须停一次）**：`chapter-dod` 盲检 exit 0 后，**不得直接开写下一章**。先把本章 DoD **逐项结论**（每项 pass/证据一行，含数据溯源 S10、承重引文核证 S11）摆给用户，并**HALT 等用户明确说"过，继续下一章"**才动笔。用户未确认前停在此处。

**本章完整 DoD 判据（全部核查项 + 脚本命令）以 `references/dod_checklist.json` gate=`chapter-dod` 为唯一真源（19 项）**：盲检subagent据此逐项核、能脚本核的先跑脚本，退出码非 0 即 fail-closed。含 G1-G7 通用（编号/citation_guard/主线/占位/去AI/字数/G7 常识软报告）、S1-S7 sci2doc 特有（实验-方法映射/一实验≥一图表/三线表/缩略语注册/GB7714 著录/自我抄袭/章后 self-check）、S9 字符级排版（`subsup_bare` + `halfwidth_punct_in_cn` + `english_misspelling` 任一命中即 `check_quality.py` 非零退出 hard 阻断）、S-GIT 检查点，及 **S8 全章结构完整性、S10 全章数据溯源硬门（数值均标 `[数据来源]`，fail-closed）、S11 全章承重引文核证**。此处不再内联清单，避免与真源 drift。

### 7) Finalize Chapter State

- `state_manager.py write-cycle --chapter N --finalize --summary "..." --snapshot`。
- **Git Checkpoint（章末）**：`python3 scripts/git_checkpoint.py commit ${save_path} "[sci2doc] chapter N done"`（git 不可用自动 no-op）。

### 8) Merge Full Markdown and Full Word

- `atomic_md_workflow.py merge-full --to-docx`。**规则：** 必须先纳入 `atomic_md/` 根级前置页 markdown，再合并正文。
- 可选高保真合并：`merge_chapters.py --input-dir .../02_分章节文档 --output .../03_合并文档/完整博士论文.docx --require-high-fidelity`。
- 兼容规则：`merge_documents.py` 优先用 `02_分章节文档/` 中已物化的前置页 docx，默认纳入 `封面`、`题名页`、`独创性声明与授权书`。

### 10) Rollback if Needed

- `state_manager.py rollback --target snapshot`（加 `--strict-mirror` 严格镜像）。

