> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

### Phase 0: 项目初始化 (`/init`) - 跨平台便携模式
1. **Ask Path**: 询问用户保存路径 (默认 Desktop)。
2. **Create Dir**: 创建项目根目录及子目录 `scripts/`、`configs/`、`references/`、`manuscripts/`、`section_memory/`、`figures/`、`figure_analysis/`、`reviews/`、`submission/`。
3. **Copy Resources**: 将 Skill 中的文件拷贝到项目（参见 §1 Command Logic）：
   - `scripts/*.py` → `[Project_Root]/scripts/`
   - `templates/*.json` → `[Project_Root]/`
   - `templates/reference.docx` → `[Project_Root]/reference.docx`（`/merge` 字体模板，漏拷 = 首次导 docx 硬失败）
   - `configs/*.json` → `[Project_Root]/configs/`
   - `references/*` → `[Project_Root]/references/`（`dod_checklist.json` 是盲检门的运行时输入，漏拷 = 下一节开不了写）
4. **Init Config**: 基于 `project_init.json` 中的模板生成独立状态文件：
   - `writing_progress.json` ← `writing_progress_template`
   - `context_memory.md` ← `context_memory_template`（填入当前日期和研究方向）
   - `version_history.json` ← `version_history_template`（`{"snapshots":[],"current_version":"v0_initialized","max_snapshots":10}`）
   - `si_database.json` ← `si_database_template`（空数组 `[]`）
   - `figures_database.json` ← `figures_database_template`（空数组 `[]`）
   - `literature_index.json` ← `literature_index_template`（空数组 `[]`）
   - `literature_matrix.json` ← `literature_matrix_template`（空对象 `{}`）
   - `abbreviations.json` ← `abbreviations_template`（空数组 `[]`）
   - 运行 `python scripts/state_manager.py set-field --field [field_id]` 生成 `project_config.json` 和 `reviewer_concerns.json`
5. **Env Precheck（软门禁）**: `python scripts/env_preflight.py [Project_Root] --cli esearch`，写 `env_status.json`，末行打印 `PRECHECK: OK|ASK|BLOCKED`。`BLOCKED`（Python 过低）→ 停并引导升级，不得继续；`ASK`（缺 git/esearch 等可选工具）→ **逐项问用户是否安装**并给安装指引，用户答"已装/不装"后才继续，后续再遇工具缺失同此处理；`OK` → 继续。随后 `python scripts/state_manager.py load` 验证脚本环境。**它打印的 `DOD_CHECKLIST` / `PREP_PROMPT` / `WRITER_PROMPT` / `SIGNOFF_CMD` / `RESUME_CMD` / `LOG_CMD` / `CITATION_CHECK_CMD` 绝对路径要记下来全程沿用**（项目内**有** `references/`——§1 Command Logic 第 5 步已拷进来，别把那步删了；但 cwd 不一定在项目根，所以一律用这些绝对路径）。
6. **Git Init**（叠加在 snapshot 之上，非替换）：运行 `python scripts/git_checkpoint.py init [Project_Root]`。git 可用且项目根不在他人仓库内时建立 git 检查点；否则静默回退 snapshot。

**`/upgrade-scripts` 升级脚本**：触发场景、备份/拷贝/验证流程见 `references/interaction-protocol.md`（`/upgrade-scripts` 节）。

### Phase 1: 预审模式 (`/preview`)
**输入**：用户提供的摘要/实验描述/数据概述。
**输出**：3000词可行性报告，包含：选题价值、数据充分性评估、拟发表期刊建议、关键风险点。
**决策门**：用户阅读报告后确认继续，或调整研究设计再回到 Phase 0。

### Phase 5: 统计方法选择助手 (`/stat-helper`)

**触发场景**：用户持有原始数据但无法确定适用的统计检验方法（统计方法选择错误将直接导致论文审稿不通过）。

**执行**：`Read references/stat-decision-tree.md`，含完整决策树（按数据类型/分组数/配对/分布）、5 条强制询问（正态性/方差齐性/样本量/配对/outlier）、报告模板与 4 条红线。输出的检验用 `add-stat-method` 落地到 `figures_database` 各 panel 的 `stat_test` 字段。

---

### Phase 6: Figure 识图与讨论 (`/figure`)

**定位**：将用户逐张提供实验图、AI 读图产出结果与讨论草稿、存为写作依据这一流程标准化。产物 `figure_analysis/figure_{N}.md` 是 Phase 8 撰写对应 Results/Discussion 小节的**上游素材**，非正文，不参与 `/merge` 合并。

**前置**：必须在 `/figure-plan`（Phase 2.5）完成图集规划、且文献检索（Phase 3）基本完成后才运行。此时每张图的 section_id 与 main/SI 分配已确定（来自 Phase 2.5 的 `figures_database.json` 草版条目），本阶段用真实图文件填充该条目，不再重新规划图序。结构由 storyline 决定（融合式 / Results 与 Discussion 分离 / 方法学后置均可），本阶段只产素材、不假设结构。**本阶段不检索文献**。**与 Phase 8 逐节交替**：不是先识完所有 figure 再统一写，而是每写一个 Results 小节前先对该节对应 figure 跑 `/figure`，再 `/write` 该节。

**🔴 读图红线 (Zero-Hallucination on Images，最高优先级)**：
1. **只读已符号化/已印出的信息**：分组标签、坐标轴文字与量纲、星号数量(`*/**/***`)、图面或图注印出的 P 值数字、误差棒有无、组间高低**方向**与趋势。
2. **严禁视觉定量与判读**：不得从像素估算条带灰度、荧光/CLSM 强度、阳性率、共定位、转移灶/肿瘤数目等任何**未标注**的定量值；不得对 WB/HE/IHC/荧光/CLSM/拍照图做病理或表型**判读**；不得反推未印出的数值或 P 值。
3. **不数散点**：散点图只读趋势与组间比较结果，**不清点数据点估算 n**。
4. **读不到 = 问，不猜**：误差棒类型(SD/SEM/CI)、各组 n、星号阈值定义、看不清的小字，一律列入"❓待确认"问用户，严禁脑补。
5. **讨论不脑补背景**：讨论草稿只写"基于用户提供的实验设计/假设、以及本图数据本身成立的推理"；需外部文献佐证处（段落首背景句、尾意义句）用占位注释 `<!-- [CITE_PENDING: 关键词] -->` 标记，留待 Phase 8/最终补引时按"文献真实性硬约束"真检索填充，补不到则问用户或转 `REF_DROPPED`。严禁用知识库充当已检索文献。
6. **中文确认 → 英文写入**：每张小图读完，先用**中文**贴出"结果 + 讨论草稿"（含读到的分组 / 比较 / 趋势 + ❓待确认项）给用户核对；经用户确认 / 修正后，再翻译为**英文**写入 `figure_X.md`（文档落盘正文为英文，确认环节用中文）。

**流程 (逐图循环)**：完整 8 步流程（进入→建档→逐张索取→读图中文草稿→确认英文写入→自检→下一张→收口）见 `references/figure-protocol.md`，进入 `/figure` 时 `Read` 取用；本节只留收口的执行命令与不可丢的约束。

**收口命令（执行必需，每完成一个大 Figure 跑一次）**：
- `python scripts/state_manager.py add-figure <one_figure.json>`：传**单个** figure 对象（`figure_id` 必需、`section` = storyline 的 section_id），锁内去重合并进 figures_database 并顺带同步 writing_progress/context_memory/storyline；核心定量读不到的项 `data_status="pending"`，对接 §2 熔断。**字段与条目示例见 figure-protocol.md。**
- 缩略词扫描：对本 figure_{N}.md 新引入且未在 `abbreviations.json` 的 `Full Name (ABBR)`，逐个 `add-abbreviation`（否则 `/write` 写正文会重复展开）。
- `python scripts/state_manager.py snapshot` 备份。**勿用 `postwrite`**，它有 prewrite gate（`state_manager.py` 的 `postwrite_state()`），识图阶段没跑 write-cycle 会 `sys.exit(2)`。

**落盘模板**：`figure_analysis/figure_{N}.md` 模板与 `figures_database.json` 条目示例见 `references/figure-protocol.md`，收口落盘 / `add-figure` 时 `Read` 取用。（`data_status`：核心定量齐全=`ready`，缺核心项=`pending`；`section` 值必须 = storyline 的 section_id。）

**与 Phase 8 衔接（关键）**：write-cycle **不会**自动加载 `figure_analysis/`（其白名单见 §13），故 `/write {section}` 必须在 write-cycle 之后**显式 `Read` 本节对应的 `figure_analysis/figure_{N}.md`**（已列入 §13 白名单第 7 项）作为该小节 Results/Discussion 的事实依据。**写 Results 小节前的 gate（提示词级）**：若该 `figure_analysis/figure_{N}.md` 不存在、或仍有核心定量的 ❓待确认 → 不开写，先回到 `/figure` 补全再 `/write`。正文按 storyline 既定结构组织：融合则结果讨论同段；**分离结构下，写 Discussion 小节前同样必须显式 `Read` 对应 figure_X.md 的讨论块**（与上面 Results 的 gate 同等，否则 Discussion 丢失识图讨论草稿）。`[CITE_PENDING]` 处理时机：**每节 `/write` 收口（postwrite）前应尽量真检索清零本节占位**，Phase 10 `/check` 的占位扫描作为最终兜底。

**红线重申**：本阶段严禁任何"AI 看像素得出的定量或诊断结论"。定量以用户数据 / 图面印出数字 / 图注为准；外部背景以真检索文献为准；二者缺一即停下问用户。

**配图代码生成（opt-in，默认关）**：本阶段默认只做识别用户已有实验图（上述读图红线），**不**生成新图，基础实验用户自行作图。生成新图代码是与识图**并列的另一项可选能力**，二者互不混淆：仅当用户**明确要求**"生成配图/画图代码"（如生信、统计图场景）时启用。启用后：① 调用本地 matplotlib/seaborn skill 生成**可运行代码**（产出代码非图片，不替代识图、不写入 `figure_analysis/`）；② 遵循学术规范：按数据选图型（bar/boxplot/line/scatter+回归/**forest plot**/**funnel plot**（meta 分析用）/**volcano plot**·**MA plot**（差异表达用）/heatmap/network/concept map），APA 7.0 caption，色盲安全配色（viridis/cividis/Tol），300 DPI，轴标签带单位，**禁 3D 图与饼图**；③ 生成后由用户运行得图。

### Phase 7: 缩略词表管理 (`add-abbreviation`)
**定位**：跨小节维护缩略词一致性，避免同一缩写在多个章节重复定义或在后文中使用未经定义的缩写。

**首次出现规则（Mandatory）**：
- **EN**：`Full Name (ABBR)`，例：`reactive oxygen species (ROS)`
- **CN**：`中文全称（英文全称, ABBR）`，例：`光动力疗法（Photodynamic Therapy, PDT）`
- **后续使用**：直接用 ABBR，**严禁重复定义**。
- **Title 严禁缩写**；**Abstract 独立**，即使正文已定义，Abstract 首次出现仍须重新展开（Abstract 通常独立阅读）。
- **通用免定义白名单**（脚本同步）：DNA / RNA / PCR / HIV / WHO / FDA / NIH / ATP / pH / ELISA / qPCR / SD / SEM / CI 等，直接使用不展开。详见 `state_manager.py` 的 `UNIVERSAL_ABBREVIATIONS`。

**写作时实时入库**：每节 `/write` 写完时，对该节首次定义的每个缩写，执行：
```bash
python scripts/state_manager.py add-abbreviation <one.json>
# payload: {"abbr":"ROS","full_name":"reactive oxygen species","first_defined_in":"results_3.2","notes":"optional"}
```
该命令在 `FileLock` 下按 `abbr` 去重合并；**冲突拒绝**：同 abbr 但不同 full_name 直接 `sys.exit(2)` 报错（属科学错误，必须人工解决）。

**写新节前查表**：开始 `/write` 任何小节前，先 `Read abbreviations.json` 拿已定义清单。已存在的缩写**直接用 ABBR，严禁重新展开**。

### Phase 8: 逐节撰写 (融合模式 + 原子化文件 + SI循环)

**核心指令**：`/write [section]`

> **Methods 写作时机（门控）**：Methods 必须在**所有 Results 小节写完后、`/abstract` 前**用 `/write methods` 撰写，此时 `figures_database.json` 的 `stat_test`/`n`/试剂参数已随识图齐全，可一次性联动汇总（见 Phase 4 Methods 规范）。不要在 Results 之前写 Methods（统计方法尚不全）。

**原子化文件策略**：
- **Target Path**: `manuscripts/{Chapter}_{Subsection}_{Keyword}.md`
- **Example**: `/write results_3.1` -> `manuscripts/04_Results_3.1_Characterization.md`

**执行流程**：
0. **Scoped Load (Mandatory)**: 先执行章节局部加载命令，确保只读当前章节。
0a. **🔴 开写前置闸门 (Mandatory，脚本硬拦截)**：开写任何 section 前必须先跑 `python3 scripts/prewrite_gate.py --section [section_id] --root .`，exit≠0 禁止开写。它统一硬检查：上一节完成（`writing_progress.json` 该节最新 status=done）、故事线就位（`storyline.json` 含本节）、素材就位（subprocess 探查 `figure_analysis_gate.py`，**仅信息性记录、绝不阻断**，硬判定在 step 0b）、上一节占位符清零（无 `CITE_PENDING`/`DATA_PENDING`/`【待`）、缩略词一致（subprocess 调 `abbreviation_consistency.py`）；上一节盲检结果（`.review_pass/<上一节>.json`）缺失即 prewrite_gate 硬拦 exit 1，禁止开写；必须先跑 delegate_review verify --section <上一节> 落盘通过标记。还含一条按 section 角色的软文献门（读该 section 的 role、统计矩阵里归属它的文献条数），Intro 硬地板 6 篇软目标 10 篇、Discussion 硬 8 软 12，Methods/Results/其它一律不设篇数门（0 篇也放行）；硬地板不达算 failures 拦截，软目标不达只进 warnings。过此闸门后再走下面 0b。
0b. **🔴 figure_analysis 加载门禁 (Mandatory，脚本兜底)**：跑 `python scripts/figure_analysis_gate.py --section [section_id] --root .`。该 gate 比对 `figures_database.json` 中该节涉及的 figure，确认每张 `figure_analysis/figure_{N}.md` 存在、非空、无 `❓待确认` 残留；任一未就绪 → 脚本 exit 1，**禁止开写**，先回 `/figure` 补齐再回来。Introduction/Methods 等无 figure 的小节脚本自然放行（exit 0）。过 gate 后**必须显式 `Read` 本节对应的 `figure_analysis/figure_{N}.md`**（write-cycle 不自动加载，见 §13 白名单第 7 项），作为 Results/Discussion 的事实依据。
0c. **🟢 引文核证脚手架 (Citation-Claim Matrix，写对的脚手架，非事后墙)**：开写本节前，先把"本节承重论点 ↔ 拟引文献"建成矩阵，用**真 abstract** 判每条引用是否真支撑它挂的论点，再下笔，避免写完才发现引文对不上、又得返工重写。
   - **🟢 备料子代理起草（一律派，把"读摘要判 verdict"的重活从主会话吸走）**：本节（非白名单节）核证矩阵**先派备料子代理起草**——`python3 scripts/delegate_write.py pack-prep --section [section_id] --root .` 生成 `.prep_task_[section_id].json`，把 `[PREP_PROMPT]`（Phase 0 打印的绝对路径；项目内有 `references/`，但子代理 cwd 未必在项目根，故一律传绝对路径）（角色 + 数据/指令隔离）+ 任务包路径交给一个独立子代理，它只产草案 `.claim_evidence_draft_[section_id].json`（`evidence_quote` 必须是账本 abstract 原文子串、`user_confirmed` 一律 false、提议 `claim_kind`），**绝不碰账本**。空草案 `{"claims":[]}` 合法（本节无承重配对）→ 跳过核证直接进撰写打包。白名单琐节不派备料。
   - **哪些算承重论点（is_load_bearing=true）**：支撑本节结论方向的机制句、因果句、定量对比结论句。段首背景句、常识铺垫句算背景（is_load_bearing=false，批量核对即可，不逐条阻断）。
   - **证据只用检索原样落盘的真摘要**：从 `literature_index.json` 里取该 ref 当初 MCP **检索原样落盘的 `abstract`**（不看可编的 key_finding、不脑补），逐条判 `verdict ∈ support/weak/contradict/unknown` 并摘一句 `evidence_quote`。取不到摘要的承重引用先走 §12 摘要补全或换引文，别硬写。
   - **落盘 `claim_evidence.json`**（list，每条）：`{section, claim_sentence, is_load_bearing, claim_kind, ref_id, retrieved_abstract, verdict, evidence_quote, user_confirmed}`。主会话把备料子代理草案核证 + 用户确认后并入本文件（备料草案不是账本，绝不直接当账本用）。
   - **🟢 跨节复用（修"AI 漏写字段导致重复验证"的关键）**：核证脚本会**自动读写项目根 `ref_evidence_cache.json`**，已验状态由脚本落盘，**AI 不必手动记忆或回写任何字段**。因此建矩阵时：① 对**已在别节验过的同一 `ref_id`**，`retrieved_abstract` 可留空，脚本核证前会按 ref_id 从 cache 回填摘要，无需重抓；② 对**同一 `ref_id` + 完全同一论点句**且此前已确认的，脚本自动复用已确认的 verdict/`user_confirmed`，不再 AskUserQuestion 打扰用户；③ **只对新出现的 (ref_id, 论点句) 组合**做反向验证与逐条确认。门禁强度不变：新 (ref, claim) 无 verdict 仍 fail-closed。
   - **跑核证**：运行 Phase 0 `env_preflight.py` 打印的 `CITATION_CHECK_CMD`，即 `python "<项目内 scripts 绝对路径>/citation_claim_check.py" --root <project_root>`（草案来自备料子代理时**加 `--check-quote-substring`**，机械查每条 `evidence_quote` 确是账本 abstract 子串，编证据的 fail-closed 打回）。它渲染"观点↔引文↔是否真支持"矩阵表；**承重句 verdict=contradict/unknown、或缺摘要、或未逐条人工确认 → exit 2 fail-closed 硬拦**；另有 `claim_kind × article_type` 机械纪律（承重机制/疗效声明挂综述 → exit 2），据表改引文/改论点/补确认后重跑。
   - **承重句逐条确认 (AskUserQuestion)**：**只对新出现的承重 (ref_id, 论点句)** 把"论点句 + 判定 + 摘要证据句"用 AskUserQuestion 逐条给用户确认（确认后脚本把该行 `user_confirmed=true` 落盘）；此前已确认过的同一组合由脚本自动复用、不再打扰；背景句在矩阵表里**批量**呈现让用户扫一眼，不逐条阻断。
   - **定位**：这是"帮你写对的脚手架"：先核对引文再落笔，不是卡死后续的墙；核证过了才进 step 1 起草。（承重句 contradict 硬拦是防止照着不支持的引文下笔，属科学正确性底线。）
1. **Pre-Write Check**: 检查数据完整性。
2. **🟢 本节正文由撰写子代理盲写（主会话调度，堵上下文爆 + 焊死编号权）**：本节正文**不再由主会话直接手写**，改走下面这条流水线（前后所有门禁一个字不改，照跑；`resolve-keys` 之后 `[n]` 与现有 sync/DoD 全兼容）：
   1. **组任务包**：`python3 scripts/delegate_write.py pack-write --section [section_id] --root .` → 生成 `.write_task_[section_id].json`（本节故事线/承重方向 + 已核证观点-证据对 `certified_claims` + `literature_matrix` 切给本节的文献全条 + 缩写表 + 风格禁项**嵌入**，全篇故事线/全库文献只给 `refs` 路径）。承重句未完成人工核证 / 本节有承重论点却缺 `claim_evidence` → 脚本 exit 2 拒绝出包（先回 0c 补核证）。
   2. **派撰写子代理**：把 `[WRITER_PROMPT]`（Phase 0 打印的绝对路径；项目内有 `references/`，但子代理 cwd 未必在项目根，故一律传绝对路径）（角色 prompt + 数据/指令隔离声明）+ 任务包路径交给一个**全新一次性上下文**子代理盲写本节。它只写 `.write_return_[section_id].json`，**正文引用只写 `[@key]`（绝不写裸数字 `[5]`）**，承重句只准挂任务包内嵌 `certified_claims` 里的 `ref_key`，禁写任何账本。
   3. **机械校验返回**：`python3 scripts/delegate_write.py verify-write --section [section_id] --root .`（V1-V9：无裸数字引用 / `[@key]` 可解析 / `new_refs` 带 DOI 或 PMID / `section_id` 一致）。exit≠0 打回子代理重写，不落盘。
   4. **new_refs 先核验再并表**（账本零污染）：对返回的 `new_refs` **先** `citation_guard.py --require-mcp` 核真伪，**通过的才**并入 `literature_index.json`（走现有去重 `dedup_literature_index`），并把每条 `new:slug → 已并表条目 id` 写进项目根 `.newref_map.json`（供认键与 prewrite 并表核验读）。核验失败的直接丢弃、打回子代理改写该处引用。
   5. **落盘本节初稿**到 `manuscripts/{Chapter}_{Subsection}_{Keyword}.md`，随后跑**认键**：`python3 scripts/state_manager.py resolve-keys --file <本节文件> --root . --in-place` 把 `[@key]`/`[@new:slug]` 翻成当前 `[n]`（未知键 exit 1，先补并表）。之后本节正文即回到 gsw 标准 `[n]` 形态，进 step 3。
   - **白名单琐节**（front/back-matter、`storyline` 里无承重论点清单的节）：主会话就地写、不派子代理、不派备料，天然无 `.write_return`（prewrite 并表核验对其合法放行）。
   - **Citation Format**：子代理阶段写 `[@key]`；`resolve-keys` 后与全稿统一为 `[n]`。step 8 全局 sync 再做跨节连续重编号。
3. **Reference List Generation**: 在文末生成本节引用的文献列表 (Vancouver style)。
4. **Figure Caption Generation**: 在参考文献列表后，必须生成 "Figure Legends" 版块。
   - **Content**: 包含整体描述和分图说明 (e.g., "Figure 1. Characterization... (A) TEM image...").
   - **Strict Rules**: 统计图必须声明 "n=X"；显微镜图必须声明 "scale bar = X μm"。
4b. **Figure Prompt Generation**：为需 AI 绘制的示意图/机制图生成结构化提示词，`Read references/writing-templates.md` 末节取 `[FIGURE PROMPT]` 模板与生成规则，append 到 `figures/figure_prompts.md`。（注意双轨：`figures_database.json` 是用户已有实验图的识图数据；`figures/figure_prompts.md` 是让 AI 帮画的图，二者不冲突。）
5. **SI Proactive Proposal**: AI 主动思考并建议 SI 数据。
6. **User Feedback**: 用户确认。
7. **Final Integration**: AI 重写该节，插入 SI 标记。
8. **Global Literature Sync**: 写完当前节后，通过脚本执行全局文献去重与编号同步（含正文 `[n]` 自动重写）。
9. **🔴 节末用户确认检查点（Mandatory，先确认再落盘）**：在 Safety Write 之前展示给用户：① 字数 ② 引用条数 ③ 已引用的 figure_id 列表 ④ 本节新增缩略词列表 ⑤ 残留 `CITE_PENDING`/`DATA_PENDING`/`REF_DROPPED` 数；等待用户明确确认（"OK 继续" 或 "需修改 X"）。**OK 才进 step 10 落盘**；用户说改 → 在内存里改后重新展示确认；连续自动写多节禁止。

   **🔴 DoD 自检清单（硬规则：清单未逐项确认通过，不得向用户声明"本节完成"）**

   **🔴 委托盲检（不得主 agent 自评）**：你刚写完本节，自评会失真地默认通过、且易漏项。落盘前必须把 DoD 清单**委托给独立上下文的subagent盲检**，自己不直接打勾：
   1. 生成任务包：`python scripts/delegate_review.py pack --checklist "[DOD_CHECKLIST]" --gate section-dod --files <本节文件>`（`[DOD_CHECKLIST]` = Phase 0 `env_preflight.py` 打印的那个绝对路径。项目内**有** `references/dod_checklist.json`（/init 第 5 步拷入），相对路径只在 cwd 恰好是项目根时才成立，**一律用绝对路径**，找不到文件 pack 会 exit 2）
   2. **派一个 fresh-context 独立通用 subagent**（全新一次性上下文、不依赖任何具名代理类型；本环境没有名为 `academic-blind-reviewer` 的代理，不要按名字找），把任务包原样给它、**不要给它本节的写作上下文**，要求按任务包返回 JSON 数组。
   3. 校验返回:`python scripts/delegate_review.py verify --checklist "[DOD_CHECKLIST]" --gate section-dod --return <subagent返回.json> --section <当前section_id> --root <项目根>`;退出码非 0(任一缺项/fail/无证据)= **fail-closed**,据subagent证据修复后重跑,**未过不得声明完成**。verify 通过会落盘 `.review_pass/<当前section_id>.json`,下一节 `prewrite_gate.py` 会**硬校验**它(缺失即拒绝开写)。

   🔴 **[P4·盲检降级告警]**：若环境派不出真正独立的subagent，**绝不能同一 AI 自问自答冒充盲检**（自证）。告诉用户「本环境盲检不可靠，请你亲自复核：__（列出该盲检本应查的关键点）__」，交回用户。

   🟢 **[①DoD 停·盲检通过后必须展示+握手]**：`delegate_review verify` exit 0（盲检通过）**不等于自动往下写**。通过后 AI 必须把盲检的**逐项结论**（每条 DoD 项 pass/warn + subagent给的证据要点）摆给用户看，并**HALT 等用户确认**"这节可以定稿、继续下一节吗？"；用户明确同意后才开始写下一节。这是**展示+可继续**的握手停顿，不是加硬墙；脚本层前置闸口（下条）照旧。

   🔴 **进入下一节前置闸口**：上一节 `delegate_review verify` 必须 exit 0（含 G13 结构完整性），否则不得开始下一节撰写。写完即检，不过不进。
   🔴 **修复 3 次仍不过 → 回滚兜底**：同一节据盲检证据修复重跑 3 次仍 fail，停止盲目重写，提示用户回滚到上一检查点（git 可用：`git checkout <sha> -- <文件>`；否则 `/rollback` 到上一 snapshot）后重写。

   **本节完整 DoD 判据（全部核查项 + 脚本命令）以 `references/dod_checklist.json` gate=`section-dod` 为唯一真源（26 项）**：盲检subagent据此逐项核、能脚本核的先跑脚本，退出码非 0 即 fail-closed。该 gate 含引文对应/citation_guard/主线对齐/占位清零/去AI(style_checker，含必禁三项 scare_quotes/explanatory_colon/em-dash 硬门)/字数上限/figure data_status 非 pending/无像素定量/实验逻辑批判/节末 Vancouver/只改原子源/figure_analysis 加载/缩略词一致/检查点/字符级排版(proofread subsup_bare 硬门)/拉丁斜体软提醒/承重声明引文类型(G26)等脚本项，及 G13 结构完整性、G23 常识合理性(软)，与 **G17-G22 六项盲检质量核（科学事实正确、统计方法学、论证逻辑闭环、文献完整性与引用偏倚、图表质量与疑似造假、学术合规披露）**。此处不再内联清单，避免与真源 drift。
10. **Safety Write**: 用户 OK 后写入文件 → 智能快照 → **Git Checkpoint**：`python scripts/git_checkpoint.py commit [Project_Root] "[gsw] section <section_id> done"`（git 不可用时自动 no-op，snapshot 仍是回退兜底）。回退手段：若落盘后用户反悔，`/rollback` 到上一个 snapshot、`git checkout <sha> -- <file>` 回退单节，或直接 Edit 改原子化文件（参见 §3 润色 workflow）。

**Discussion 段落结构 / Online Methods vs STAR Methods**：写 Discussion 或 Methods 章节前 `Read references/writing-templates.md` 对应小节。要点：Discussion 走"主要发现总结→文献对比+机制→**Limitations（强制，缺即退稿高频）**→Outlook"四段式；Methods 按 target_journal 选 Online Methods（Nature 精简版+完整版后置）或 STAR Methods（Cell 五段结构）。

**融合写作策略**：
1. **数据呈现 (Results)**：描述Figure结果 + 统计数据。
2. **即时讨论 (Discussion)**：机制解释 + 文献对比 + 意义阐述。
3. **深度控制（软提示，非硬门）**：Key Section 建议 ~500 词展开、Supporting Section ~200 词；字数只作深度参考，不足不阻断落盘（凑字数地板已降软），关键看论点是否讲透。

### Phase 8.6: 目标期刊风格深度学习 (`/journal-study`)：🚫 已停用（DEPRECATED，不在写作流程中执行）

> **🚫 本 Phase 已从写作流程移除，不要在写作中/写作后触发 `/journal-study`。** 期刊**语言风格适配**（被动比例、句式、摘要调性、图序惯例）**已调整至全文完成后的最后一步，由 `polish-sci` 技能执行**。语言风格属于润色阶段的工作，不应在写作阶段提前引入，更不应阻塞摘要撰写流程。
> 
> **结构目标不受影响、仍然保留**：字数上限、主图张数、Abstract 结构/词数、Methods 形式（Online vs STAR）等**结构约束**由 **Phase 2 `/storyline` 的 `target_journal` 早已捕获并写入 `project_config.word_limits`**，全流程沿用，不依赖本 Phase。停用的只是"写完再回头学期刊语言风格"这一步，不动 Phase 2 的早期结构约束。
> 
> 因此 Phase 8 写完所有 Results/Discussion 后**直接进 Phase 9 `/abstract`**；abstract/正文的目标刊语言调性对齐留到末尾 `polish-sci`。原步骤的历史细节查 CHANGELOG.md / 版本库旧版本，**不执行**。

### Phase 9: 摘要撰写 (`/abstract`)
**时机**：全部正文章节完成后、质量控制前。Abstract 是全文的压缩精华，必须最后写。Abstract 的**结构约束**（结构化与否、词数上限）按 Phase 2 `target_journal` 已捕获的规则来（见 Phase 2 表）；**期刊语言调性对齐留到末尾 `polish-sci`**，本阶段不再依赖 `/journal-study`（已停用）。
**结构**（严格遵循目标期刊 word limit，默认 ≤250 词）：
1. **Background**（1-2句）：研究背景与未解决问题
2. **Methods**（1-2句）：核心方法/策略概述
3. **Results**（3-4句）：关键定量结果（必须含具体数值）
4. **Conclusion**（1-2句）：核心结论与意义
**禁止**：不引用文献 `[n]`；**Abstract 独立**，即使正文已在 `abbreviations.json` 定义过，Abstract 首次出现仍须重新展开为 `Full Name (ABBR)`（投稿规范，Abstract 独立阅读）；不出现"significantly"等无定量支撑的空话。
**输出文件**：`manuscripts/01_Abstract.md`

### Phase 10: 质量控制 (`/check`)

**前置理由**：投稿包须基于已通过质检的稿件生成（cover letter 的 key findings 必须取自校对版、Source Data 必须与校对后的图表对应）。流程顺序为 /check 通过后方可执行 /submission-pack。

**执行命令（有序，每步阻断条件明确）**：
1. `python scripts/state_manager.py stats`：字数检查。**字数预算分类**：手动汇总 `01_Abstract*.md + 02_Introduction*.md + 04_Results*.md + 05_Discussion*.md` 为"正文字数"（`03_Methods*.md`/`07_References*.md`/Legends 多数期刊不计入），对比 `project_config.word_limits`。**阻断**：超 10% 必砍；超 5% 警告。
2. `python scripts/state_manager.py sync-literature --dry-run --strict-references`：引用号一致性。**阻断**：dry-run 报冲突 → 跑 `--apply` 后重检。
3. `python scripts/citation_guard.py --index literature_index.json --report citation_guard_report.json`：文献完整性（**联网核验，绝不加 `--offline`**——离线跳过联网核验，编造的 DOI+PMID 只要字段齐全照样过，这道阻断门就成了给假文献发证）。**阻断**：`ok=false` → 处理 `manual_review_queue.json` 后重跑；报 `source_unreachable` 是「网络不通、没验成」，同样按阻断处理，别改回 `--offline` 绕过去。
4. `python scripts/style_checker.py --manuscript-dir manuscripts --report style_check_report.json --threshold 70 --journal <target_journal>`：去 AI 风格检测（`--journal` 取 `project_config.json` 的 `target_journal`——storyline.json 里没有这个字段，切换语态软提示策略）。**阻断**：avg_score<70 → 列具体段落修改后重跑。**注意**：avg_score 不含语态项（被动比只进 `warnings`，不阻断）；PASS 只代表形式层过关，科学创新度/配不配目标刊未自动核验，须作者与通讯作者判断。
4b. `python scripts/style_checker.py --manuscript-dir figure_analysis --report figure_analysis_style.json --threshold 70`：识图阶段写入的英文草稿也检测。**阻断**同 4。
4c. `python scripts/proofread.py --manuscript-dir manuscripts --report proofread_report.json --threshold 70`：机械错误。**阻断**：avg_score<70 → 按 report 中 `issues` 字段逐条修后重跑。
5. `grep -rn "CITE_PENDING\|DATA_PENDING\|REF_DROPPED" manuscripts/ figure_analysis/ 2>/dev/null`：占位扫描。**阻断**：非空 → 必须按 §REF_DROPPED 三种处置补齐。
6. 防误改合并稿门禁：`[ ! -f manuscripts/Full_Manuscript.md ] || grep -q "AUTO-GENERATED" manuscripts/Full_Manuscript.md`：**阻断**：banner 不在 → 合并稿被手改过，需 `/merge` 重生成。

> **Windows**：步骤 5 的 `grep ... 2>/dev/null` 与步骤 6 的 `[ ... ] || grep -q ...` 是 POSIX shell 写法，PowerShell/cmd 不可用。AI 在 Windows 上改用 `Select-String` 或直接用 Python 等价逻辑，完成同样的占位符扫描与 AUTO-GENERATED banner 校验。
7. `python scripts/abbreviation_consistency.py --root .`：缩略词一致性扫描（脚本化，不再纯靠 AI 自评）。检测：① **重复定义** 同一缩写在多个 manuscript 文件首次定义；② **未定义就用** 直接用 ABBR 但 `abbreviations.json` 缺、且不在 `UNIVERSAL_ABBREVIATIONS` 白名单；③ **Title 出现缩写**（Title 严禁缩写）。**阻断**：脚本 exit 非 0 → 必修后重跑。通用缩写（DNA/RNA/PCR 等）自动跳过。脚本未覆盖的"已定义但全文未使用"等冗余项可人工补查。
8. `python scripts/cross_section_consistency.py --root . --reconcile-sections`（section 双向对账，🟡 报告式软门，非硬拦、无签字门禁）。同时报：① **漏建**（storyline 有该 section_id、manuscripts 无对应文件）；② **孤儿**（manuscripts 有文件、不属于任何 storyline section）。exit 1 = 有差异：把 `missing_in_manuscripts` / `orphan_manuscripts` 列给用户，漏建的补写、孤儿的确认是否并入某节或从 storyline 补登，处置后重跑至 exit 0 再合并。exit 0 直接放行。
9. **数值一致性核查（三层·报告式软门·HALT 交用户裁决）**：数值矛盾天然跨摘要/结果/表，必须全文成形后跑。与步骤 8 cross_section（正则 WARN"同标签词跨段数值漂移"，零成本保留）分工——本步是其更强后继（LLM 判同测量 + 反向验证），共存不拆。
   > **步骤 9–11 共用一个临时工作目录 `.state/check/`**（项目根下的写死相对路径；这三步的命令都在项目根 cwd 下原样可跑，`merge_manuscript` 会自动建目录，不必先 mkdir）。它在 `.gitignore` 内、不属于 `managed_globs`（`manuscripts/*.md`），跑完可随手删。**别换成别的路径**：换了三步就读不到同一份临时全文。

   - **① 合并临时全文（不污染源）**：`python scripts/merge_manuscript.py --manuscript-dir manuscripts --output-md ".state/check/_numeric_fulltext.md" --skip-docx` —— 合并到 `.state/check` 临时路径，**绝不落 `manuscripts/Full_Manuscript.md`**（避开步骤 6 AUTO-GENERATED banner 门禁与派生稿红线）。
   - **② 第 1 层确定性锚**：`python scripts/numeric_candidates.py --manuscript ".state/check/_numeric_fulltext.md" --project-root ".state/check"` → 产 `.state/check/numeric_candidates.json`（英文 SCI，markdown pipe 表走普通行读，不触发 docx 表格 walk）。
   - **③ 第 2 层独立检测子代理（非作者自检·I2）**：派一个 fresh context、**没参与撰写**的独立检测子代理（`TaskCreate`/spawn_task），**只喂** `.state/check/numeric_candidates.json` + 临时全文，**不给撰写过程上下文/作者意图**（防继承作者确认偏误——作者自评漏看的真矛盾第 3 层反向验证永远看不到，会系统性假阴）。子代理产出**零容差二元 schema** `[{"metric","same_measurement":bool,"values":[{"id","raw","location":{"region","para_index"}}],"conflict":bool,"evidence_quote","finding"}]`（**无 `tolerance_state`、无 `severity`**）：先判是否**同一指标/对象/分组/时间点/单位**（跨措辞语义归一、跨单位如 μM vs nM 由 LLM 换算判），仅对同一测量判是否**完全相等**，`same_measurement==true && 非完全相等 → conflict=true`；不同剂量组/时间点/亚组/单位的正常差异不报。**样本量 n 跨位置核对**：核对同一实验/同一组的样本重复数 n（`metric_clue=="样本量"` 的候选）是否跨**方法学 / 图注 / 结果与讨论**三处一致（例：方法 n=6、Figure 2 图注 n=8、结果又 n=6）；**防假阳**：不同图/不同实验的 n 本可合理不同，**只有多处 n 明确指向同一实验、同一组样本时**其不一致才报 conflict，无法确认是否同一实验/同组的按 `same_measurement=false` 不报（拿不准交人工）。**降级**：派不出真正独立子代理时不得自问自答冒充，标注"数值一致性未经独立检测"交用户人肉核。
   - **④ 第 3 层反向验证**：每条 `conflict==true` 过 `delegate_review.py`（**不改它，只 pack/verify**，gate=`numeric-verify`，checklist 内自由 key，不查 gate_registry）。动态合成 `.state/check/numeric_verify_checklist.json`：item 只放两处 `raw`/location/`metric` + 核验所需原文切片（**绝不放子代理的 finding/reasoning，防带节奏**），默认硬项（不标 `"severity":"soft"`）；**≥3 值的组拆成两两配对的多个 item**（id `num-<组>-<配对序>`，任一配对 pass → 该组整体保留交人工、全部 fail → 该组剔除）。**🔴 check 逐字用零容差极性模板（禁占位符、禁自由发挥）**：
     > "到给你的原稿全文里独立核实：`{locA}` 处的值『{valA}』与 `{locB}` 处的值『{valB}』，两者据称都是指标『{metric}』的测量结果。请逐字回源确认两点——**(1) 两处是否确指同一指标、同一测量对象、同一分组、同一时间点、同一单位**（即本就应当相等；跨单位如 μM vs nM，请换算到同一单位后再判是否本应相等）？请到原文找出各自邻近的分组/剂量/时间点/亚组/单位线索比对。**(2) 若确为同一测量，两值是否非完全相等**（**零容差：只要不是完全相同的数值即算不等，含末位舍入差异如 58% vs 58.3%**）？**只有『同一测量且非完全相等』才判 pass（矛盾属实，保留交人工裁决）；只要发现两者其实是不同分组/不同时间点/不同亚组/不同单位（正常差异），或换算后完全相等，一律判 fail（非矛盾，剔除）。** evidence 必填：逐字引出 A、B 两处原文句及各自的分组/时间点/单位线索。"

     `--files` 给临时全文；`pack` → 独立空白子代理逐条裁 `pass|fail|na` 附逐字证据 → `verify`。**verdict 映射**：`pass`→confirmed（矛盾属实）；`fail`/`na`→refuted（剔除）；verify 的 `problems`（空证据/未裁决/verdict 非法）照 fail-closed 视为未核验、不进清单（宁漏报）。极性写反 = 假批评全放行，务必对准 pass=矛盾属实。 ⚠️ **退出码陷阱（务必理解）**：本 numeric-verify 复用通用门禁 `delegate_review`，任一 item fail 会让 verify 报 `ok=false` / **exit 1** / stderr『盲检未通过』——但在数值反向验证里 **fail = 成功剔除假矛盾 = 正常好结果**。主 agent 必须**忽略退出码**，只读返回 JSON 的逐条 verdict + problems：verdict=pass→confirmed 保留、fail/na→refuted 剔除、problems 内→fail-closed 不进报告。切勿把 exit 1 误读成核查失败 / 报告不能完成。
   - **⑤ HALT**：命中 confirmed conflict → **HALT 交用户裁决**：打印全部 confirmed（`metric` + 两处 `raw`/location + evidence_quote），暂停 `/check`、要求用户逐条裁决是否需统一，处置后重跑本步至无 confirmed conflict 再进 Phase 10.5。**不 auto-block 硬拦、不静默判等放过**（零容差 + 灰区交人工）。
10. **交叉引用核查（xref，三层·报告式软门·HALT 交用户裁决）**：正文"见图5 / 见3.3节 / 见表2 / 见(2)"指向对不对，天然跨全文，必须成形后跑。gsw 现役对此零覆盖，纯新增能力（与步骤 8 cross_section 无重叠）。
   - **① 复用 step9 临时全文（只读，不重复 merge）**：直接读 step9（步骤 9①）已产出的 `.state/check/_numeric_fulltext.md`——**只读、不改名、不重复 merge、不改 step9 任何字节**（step9 必先于本步跑、文件已在）。
   - **② 第 1 层结构锚**：`python scripts/structure_outline.py --manuscript ".state/check/_numeric_fulltext.md" --project-root ".state/check"` → 产 `.state/check/outline.json`（`sections`/`figures`/`tables`/`items` 四类真实存在结构锚 + `summary`；退出码 0=正常含空稿、2=用法/输入/解析错）。落 `.state/check` 根，**不进任何 managed_globs**（否则触发 signoff）。
   - **③ 第 2 层独立检测子代理（非作者自检·I2）**：派一个 fresh context、**没参与撰写**的独立检测子代理（`TaskCreate`/spawn_task），**只喂** `.state/check/outline.json` + 临时全文，**不给撰写过程上下文/作者意图**（防继承作者确认偏误→系统性假阴）。逐条指向型表述对着 `outline.json`（**唯一权威真值**，不得凭记忆假设稿子有某小节）判**存在性**（目标编号在不在→`missing_target`）与**语义对应**（编号在但指错内容→`semantic_mismatch`），拿不准标 `uncertain`。**🔴 补充材料护栏**：**补充材料引用（`S` 前缀编号，如 `Figure S1`/`Table S3`/`见图 S22`/`Supplementary Fig. 5`）不在 outline 范围内**——正文稿抽不到补充文件的定义，此类**一律强制 skip 丢弃（不产 finding、绝不标 `uncertain`、绝不报 `missing_target`、绝不送第 3 层反向验证）**（否则走 `uncertain` 支会连同 `missing_target` 一起被送第 3 层，而补充材料图注天然不在主文 → 第 3 层"连定义处都找不到→pass=confirmed"把整份补充材料 S1–Sn 批量假报为悬空、假阳 HALT）。产出 schema `[{"ref_id","citing_location","cited_target","issue_type":"missing_target|semantic_mismatch|uncertain","evidence_quote","outline_says","finding","severity"}]`（`severity` 仅信息字段，HALT 不按它路由）。**降级**：派不出真正独立子代理时不得自问自答冒充，标注"交叉引用未经独立检测"交用户人肉核。
   - **④ 第 3 层反向验证**：每条问题过 `delegate_review.py`（**不改它，只 pack/verify**，gate=`xref-verify`，checklist 内自由 key，不查 gate_registry）。动态合成 `.state/check/xref_verify_checklist.json`：item 只放 `cited_target`+`evidence_quote`+`issue_type`+核验所需原文切片（**绝不放子代理的 finding/理由、也不放 outline，防带节奏**），默认硬项。**按 issue_type 分流喂料**：`missing_target`/`uncertain` 的 item `--files` 给**原稿全文**（让核验人独立回源检索该编号到底存不存在，才能反查第 1 层漏抽真小节造成的假 `missing_target`）；`semantic_mismatch` 的 item 给引用处上下文切片 + outline 里该编号标题/caption。**🔴 check 逐字用极性模板（禁占位符、禁自由发挥，`{编号}` 填 `cited_target`）**：
     > `missing_target`/`uncertain`："到给你的原稿全文里，找得到编号「{编号}」的**定义处**吗？定义处专指：图/表的图注行（以『Figure {N}』『图{N}』『Table {N}』『表{N}』开头、后接说明文字的 caption 行），或该编号的小节标题行（如独占一行的『3.2 方法』）；**把它当引用来提及的句子不算定义处**（如『见 Figure 3』『as shown in Figure 3』『详见 3.2 节』这类指向句，即便含该编号也一律不算）。只有连定义处都找不到（该编号只被引用、从未被定义）才判 pass；只要找到定义处就判 fail，并逐字引出该定义/caption 行。"

     > `semantic_mismatch`："正文该引用处的具体断言，与目标「{编号}」的标题/caption 是否明确无关？只有'正文明确断言见 X 讨论了 Y、而 X 根本不涉及 Y'这种明确错位才判 pass；若只是笼统指向或目标标题能合理概括该引用，一律判 fail。"

     `pack` → 独立空白子代理逐条裁 `pass|fail|na` 附逐字证据 → `verify`。**verdict 映射**：`missing_target`/`uncertain` **找到定义处（caption/小节标题行，非引用句自身）→ fail=refuted 剔除**、**连定义处都找不到（悬空引用）→ pass=confirmed 保留**；`semantic_mismatch` **明确无关 → pass=confirmed 保留**、**笼统指向/合理概括 → fail=refuted 剔除**；verify 的 `problems`（空证据/未裁决/verdict 非法）照 fail-closed 视为未核验、不进清单（宁漏报）。极性写反 = 假批评全放行，务必让核验人区分"定义处 vs 引用处"。 ⚠️ **退出码陷阱（同 step9）**：任一 item fail 会让 verify 报 `ok=false`/**exit 1**/stderr『盲检未通过』——但在 xref-verify 里 **fail = 成功剔除假问题 = 正常好结果**。主 agent **忽略退出码**，只读返回 JSON 的 verdict + problems。
   - **⑤ HALT**：命中 confirmed → **HALT 交用户裁决**：打印全部 confirmed（`ref_id` + `cited_target` + 原文切片 + evidence_quote），暂停 `/check`、逐条裁决，处置后重跑本步至无 confirmed 再进下一步。**不 auto-block 硬拦、不静默放过**（灰区交人工）。
11. **方法学漏写核查（M，三层·报告式软门·HALT 交用户裁决）**：结果做了某实验、方法学没交代，是审稿高频硬伤。Phase 8 已把方法↔结果耦合大半（Methods 从 figures_database 系统拉），本步是其更强后继，补"用了某法但没建 figure 条目"的窄缝 + LLM 判"引用他人 vs 本研究"。
   - **① 复用 step9 临时全文（只读）**：同 step10，直接读 `.state/check/_numeric_fulltext.md`（只读、不重复 merge、不改名）。
   - **② 第 1 层弱锚焦点图**：`python scripts/methods_terms.py --manuscript ".state/check/_numeric_fulltext.md" --project-root ".state/check"` → 产 `.state/check/methods_terms.json`（顶层 `authority:"weak_focus_map"` + `method_hits` 命中清单 + `methods_sections` 方法学小节清单 + `summary`；退出码 0=正常含空稿、2=用法/输入/解析错）。落 `.state/check` 根，不进 managed_globs。**弱锚非权威真值**——只帮第 2 层聚焦、给第 3 层回源锚点，从不判"漏写"。**弱锚缺失/损坏降级**：`methods_terms.py` 若 exit 2 或 `methods_terms.json` 缺失/损坏，第 2 层**降级为纯全文语义跑**（它本就被要求不依赖弱锚、须自行语义识别），**不得静默失效**。
   - **③ 第 2 层独立检测子代理（非作者自检·I2）**：派 fresh context、**没参与撰写**的独立检测子代理，**只喂** `.state/check/methods_terms.json` + 临时全文，不给撰写上下文/作者意图。读结果/讨论 + 方法学 + 弱锚焦点图，判**每个本研究用到的实验方法方法学章节有没有交代**，报 `methods_missing`。**关键约束（逐条写进 prompt）**：① **弱锚非穷尽**：`method_hits` 只是字面命中参考，必须自行通读结果/讨论、语义识别词典外方法（含隐含方法，如"散点图门控"→流式），不得只盯 `method_hits`；② **只判本研究做的（头号假阳防线）**：只对**本研究实际做的**方法判漏写，背景/引言/讨论里**引用他人研究**提及的方法（`previous studies used…`/`既往研究采用…`）**一律不报**（判据：人称 we performed/本研究 vs 既往研究/has been reported + 区段 Results 邻近本研究图/数据/门控 + `has_figure_adjacent` + 语义，拿不准交第 3 层兜）；③ **"交代了"从宽三选一**（任一即 `methods_section_covers=true`）：方法学出现方法名（标题或描述怎么做的句，不要求可复现）/ 主文指向补充材料（见补充材料/详见附录/see Supplementary Methods）/ 方法学引用文献描述该方法（方法参照文献[X]/as previously described [12] 带引文标记）。产出 schema `[{"method","used_in_study":bool,"methods_section_covers":bool,"methods_missing":bool,"evidence_quote","finding"}]`（判据 `used_in_study==true && methods_section_covers==false → methods_missing=true`）。**下游路由**：`methods_missing==true` 进第 3 层；`used_in_study==false`（引用他人/背景）或 `methods_section_covers==true` 丢弃。**降级**：派不出真正独立子代理时不得自问自答冒充，标注"方法学一致性未经独立检测"交用户人肉核。
   - **④ 第 3 层反向验证**：每条 `methods_missing==true` 过 `delegate_review.py`（**不改它，只 pack/verify**，gate=`methods-verify`，checklist 内自由 key，不查 gate_registry）。动态合成 `.state/check/methods_verify_checklist.json`：item 只放 `{method}` + 结果处用到该方法的原文命中句（弱锚 `sentence` 或第 2 层 evidence）+ 核验所需切片（**绝不放子代理 finding/reasoning**），默认硬项；`--files` 给**原稿全文**。**🔴 check 逐字用两条件极性模板（禁占位符、禁自由发挥，`{method}` 填方法名）—— 两条件同时成立才 pass**：
     > "到给你的原稿全文里独立核实两点——**(1) 结果/讨论是否确实报告了本研究做的『{method}』**（有对应实验数据/图/门控/条带等本研究结果，而非仅在背景/引言/讨论里引用他人研究提及该方法，也非讨论/局限里"将来/拟/计划/would/planned to/future work"等表述里打算做但本研究并未做的未来工作/计划实验）？请回源找邻近的数据/图引用与人称/时态/引文线索比对。**(2) 方法学章节是否确实【完全没有】交代『{method}』**——须同时满足三个『没有』才算完全没交代：**(2a)** 既无该方法的小节标题、也无任何描述其如何做的句子；**(2b)** 也没有任何指向补充材料/附录的表述（如『见补充材料』『详见附录』『see Supplementary Methods』『described in the Supplementary/Supporting Information』）；**(2c)** 也没有【引用文献描述该方法】的表述（如『方法参照文献[X]』『按照[X]的方法进行』『as previously described [12]』这类带文献引用标记的方法指向）。只要出现 (2b) 指向补充材料 或 (2c) 引用文献描述该方法，即算已交代、不算漏写。**只有『结果确实用了本研究的该方法』且『方法学确实没写、没指向补充材料、也没引用文献描述该方法』两条同时成立才判 pass（漏写属实，保留交人工裁决）；只要发现方法学其实写了该方法（哪怕只一句）、或主文有指向补充材料的交代、或方法学有引用文献描述该方法（带引文标记）、或结果里的该方法其实是引用他人研究/背景讨论（非本研究做的），一律判 fail（非漏写，剔除）。** evidence 必填：逐字引出结果处用到该方法的句 + 方法学处（有则引出该句证明写了/引出指向补充材料或引用文献的句，无则说明通读方法学未见）。"

     `pack` → 独立空白子代理逐条裁 `pass|fail|na` 附逐字证据 → `verify`。**verdict 映射**：**本研究确用 AND 方法学确未写、未指向补充材料、未引用文献描述 → pass=confirmed 保留交人工**；**方法学其实写了 / 主文指向补充材料 / 方法学引用文献描述该方法 / 结果只是引用他人 → fail=refuted 剔除**；verify 的 `problems` 照 fail-closed 不进清单（宁漏报）。极性写反 = 假批评全放行，务必逼核验人独立确认条件 (1)"本研究做的 vs 引用他人" 与条件 (2) 两类从宽交代 (2b)/(2c)。 ⚠️ **退出码陷阱（同 step9）**：任一 item fail 会让 verify 报 `ok=false`/**exit 1**/stderr『盲检未通过』——但在 methods-verify 里 **fail = 成功剔除假漏写 = 正常好结果**。主 agent **忽略退出码**，只读 JSON verdict + problems。
   - **⑤ HALT + 已知局限**：命中 confirmed → **HALT 交用户裁决**：打印全部 confirmed（`method` + 结果处命中句 + evidence_quote），暂停 `/check`、逐条裁决，处置后重跑本步至无 confirmed 再进 Phase 10.5。**不 auto-block 硬拦、不静默放过**。**已知局限（交代用户）**：本轮**仅核主文、不读补充材料文件**——从宽口径挡住了"方法下沉补充材料 + 主文有指向"的假阳；但**方法完全下沉补充材料且主文连"见补充材料"都只字未提**的漏报**核不出**，此为已知局限。

**期刊语言调性对齐（改到末尾 polish-sci）**：本阶段只做 `/check` 的去 AI/校对；**期刊语言风格深度对齐不在此做**，留到全文定稿后用 `polish-sci` 技能统一处理（不改科学内容，仅调语言风格/结构呈现）。`/journal-study` 已停用，不再产 `journal_study/target_journal_study.json`。

**步骤 1–11 全部通过 → 进 Phase 10.5 合规门禁**；任一阻断 → 修复后重跑该步及之后步骤。

### Phase 10.5: 投稿前合规门禁 (`/compliance-check`)

**触发时机**：`/check` 全部通过后、`/submission-pack` 执行前强制触发。用户说"准备投稿"时 AI 自动先跑此 phase。

**执行前必须 `Read references/compliance-gate.md`**：七项判定细则与阻断条件完整定义在那里。

**七项合规检查（缺一阻断，逐项输出 ✅/❌ + 缺失说明）**：

1. **伦理批号**（IACUC/IRB）：涉及动物/人体无批号即阻断
2. **临床试验注册号**（NCT/ChiCTR 等）：前瞻性临床研究无注册号即阻断（ICMJE 强制）
3. **报告规范**（CONSORT/STROBE/ARRIVE/PRISMA）：按研究类型匹配；关键条目缺失即阻断
4. **统计报告完整性**（精确 P 值/效应量+95%CI/多重比较校正）：推断统计研究主要结果缺 CI 即阻断
5. **署名合规性**（ICMJE 四准则）：挂名作者须提请用户确认修正
6. **Reviewer COI 回避**（近 3 年合作/同单位/导师-学生）：明显 COI 未回避即阻断
7. **Keywords**（投稿关键词列表）：`submission/keywords.txt` 缺失，或关键词数量不符目标刊规则（一般 3-6 个）即阻断投稿包导出

**执行**：无专用脚本，逐项交互核查；报告规范部分 `Read templates/reporting_checklists.json` 取 checklist。**输出** `submission/compliance_report.md`。

**全部 ✅ → 进 Phase 11**；任一 ❌ → 补充后重跑，不得跳过。

### Phase 11: 投稿包准备 (`/submission-pack`)
**时机**：`/check` **全部通过**后；投稿包内容必须基于已通过质检的稿件。投稿包不完整将直接导致编辑桌面拒稿（desk reject）。

**结构化持久化**：所有问答结果（cover letter 编辑名 / 建议 reviewer / CRediT 分配 / funding / COI / highlights / one-sentence summary）都写入 `submission/submission_state.json`（已加入 STATE_FILES，snapshot 备份+rollback 恢复）。重跑 `/submission-pack`（如改投另一家期刊）时先 Read 该文件，仅问"变化项"，不重新问全部。写入命令：`python scripts/state_manager.py update <payload.json>` payload 形如 `{"submission_state": {"target_journal":"...", "cover_letter_data":{...}, "credit_data":{...}, ...}}`。

**触发**：用户说"准备投稿"/"提交"/"submission"/"准备投递材料" 即进入。

**流程（细则见 `references/submission-guide.md`，执行本阶段时必须先 `Read` 它）**：
1. **Read 模板**：`Read templates/submission_package.json`（8 类模板 + 投稿 checklist）+ `Read references/submission-guide.md`（逐项询问明细 / CRediT 14 类分配 / Source Data 规范 / Acks 模板 / 报告 checklist 映射）+ **`Read references/cover-letter-guide.md`**（cover letter 四段结构 / Innovation≠Contribution / 期刊 scope 契合，写 cover letter 前必读）。
2. **建目录**：`mkdir -p submission/`；下分 `cover_letter.md`、`statements.md`（DAS+Code+CRediT+COI+Funding 合并）、`highlights.md`、`keywords.txt`、`graphical_abstract/`。
3. **逐项询问 → 填模板**：按 guide 第 1 节主动问全部字段，**不要静默用空白**。**🔴 cover letter 的 scope 契合段强制**：主动向用户索取目标刊 **Aims & Scope 原文**（技能不自动抓取），据此写具体契合论证，禁 "will interest the broad readership" 类通用套话；用户未提供 scope 原文则停下索取，不编造（细则见 `references/cover-letter-guide.md` 第 3 节）。
4. **替换占位符**：所有 `{{VAR}}` 必须替换成实际值；**严禁保留 `{{}}` 占位**就交付。
5. **🔴 Keywords（强制产出）**：产出 `submission/keywords.txt`，3-6 个投稿关键词（符合目标刊数量规则），与 title/abstract 主题一致，避免与标题词完全重复，生命科学优先选 MeSH 词。选词规则见 `references/submission-guide.md` 第 8 节。
6. **跑 checklist**：投稿 checklist（guide 第 2 节期刊适配）+ 报告规范 checklist（guide 第 3 节）+ Source Data（guide 第 4 节）逐项 ✅/❌，缺项补到全 ✅。
7. **输出**：`submission/submission_checklist.md`（含逐项 status + 报告 checklist 状态 + Source Data sheet 命名核对 + Keywords 数量核对）+ 各 markdown 模板 + `submission/keywords.txt`。
8. **DoD 核查**：对照 `references/dod_checklist.json` 的 `submission-pack-dod` gate 逐项核对（SP1 无占位 / SP2 Keywords 3-6 个 / SP3 Source Data 对应 / SP4 Funding·Acks 不空）；其中 Keywords 缺失或数量不符由 Phase 10.5 强制阻断。
9. **终稿前 soft 自查**：终稿前对照 `references/presubmission_checklist.md` 自查（soft，不阻断）：覆盖摘要数字一致性、英美拼写统一、图像无不当处理、Source Data、查重/AIGC 声明、试验注册号、报告规范附件、投稿材料齐全等机器无法可靠裁决、需作者掌握原始数据/外部工具的项；仅提示，不阻断交付。

**红线（详见 guide 第 7 节）**：严禁 `{{VAR}}` 残留 / 伪造 reviewer 邮箱 / 瞒报 COI；Funding 无则写 "no specific external funding" 不留空；**Source Data 数值必须与图对应**（不一致即学术不端嫌疑）；Acks 不能空；**Keywords 必须产出且数量符合目标刊（3-6 个），缺失或数量不符即阻断投稿包导出（见 Phase 10.5）**。

### Phase 12: Presubmission Inquiry（仅 Nature/Cell/Science 系列，可选但强烈建议）

**必要性**：Nature 系列桌面拒稿率达 60%-80%，编辑预审 inquiry 通常于 1-2 周内回复是否有兴趣，若无兴趣可避免 4-6 周的审稿等待周期。Cell 系列同理。

**何时触发**：用户表态"投 Nature/Cell/Science 子刊"且 `/submission-pack` 完成后、正式提交前。

**Inquiry 格式**（≤1 页 / ≤500 词）：
1. **Subject 行**："Presubmission inquiry: [Working title]"
2. **段 1（≤80 词）**：本工作 1-2 句概括 + 为何适合该期刊。
3. **段 2（200-250 词）**：核心发现 + 关键证据（≤4 个 key findings + 关键定量结果）。
4. **段 3（≤80 词）**：与该刊已发表近期论文的 differentiation（"advances over Smith et al, 2024"）。
5. **段 4（≤50 词）**：简短作者承诺（"manuscript draft ready; 5 main figures + SI; ~5000 words"）。
6. **附件**：**仅** title + abstract + 1-2 key figures（不发全文）。

**输出**：`submission/presubmission_inquiry.md` + `submission/presubmission_figures/`（精选 1-2 张主图）。
**红线**：① 不要在 inquiry 里提"submitted elsewhere" ② 不要承诺超出现有结果 ③ 一次只发一家期刊，等回复（≤2 周无回则发下一家）。

### Phase 13: 审稿人模拟 / 退稿改进 (`/reviewer`)

**13A. 内部审稿模拟（投稿前）**：
**Storyline 阶段**：逻辑自检（假设→方法→结论链完整性）。
**Final 阶段**：完整同行评审报告（新颖性/严谨性/影响力），标注需作者回应的 major/minor 问题；与项目根 `reviewer_concerns.json` 内的领域质疑库逐条比对，覆盖率不足则补写。输出 `reviewer_report.md`。

**13B. 退稿/审稿意见改进（收到真实退稿信后）**：
当用户提供真实退稿信 / 审稿人意见时触发：
1. **导入**：将退稿信原文存为 `reviews/decision_letter.md`，每条审稿意见原文逐条编号存为 `reviews/reviewer_X_concerns.md`（X = 审稿人编号）。
2. **逐条 gap 分析**：每条意见映射到 ① 涉及的 section（数据/方法/讨论/逻辑）② 严重度（major/minor）③ 修改类型（补实验 / 重写 / 增引用 / 澄清）。结果存为 `reviews/revision_plan.json`，含字段 `{reviewer, concern_id, severity, action_type, target_section, status}`。
3. **修改执行**：按 plan 逐条改原子化文件（走 §3 润色 workflow，不改合并稿）；每条改完 `status` 设 `addressed` 并写明改动出处（如 "Results 3.2 加入 Figure 2F 增补 n=10 重复实验"）。
4. **Response letter 生成**：`reviews/response_letter.md`，对每条意见用结构化模板回复："Reviewer X comment N: <原文摘要>. **Response:** <说明修改/反驳/承认局限>. **Changes in manuscript:** <文件:行号或段落锚点>"。
5. **重投门禁**：`revision_plan.json` 所有 `status` 必须 `addressed` 或带书面理由的 `not_addressed`（如审稿人提议越界）才允许 `/merge` 重投稿。

### Phase 14: 导师批注循环 (`/mentor-review`)

**触发场景**：对应博士生写作的实际工作流程——逐节撰写、提交导师审阅、接收批注、修改、再审、再改，通常循环 5-10 轮。本阶段将该循环流程结构化管理。

**输入形式**：
- **形式 A**：导师在 Word 上开 track changes 标注 → 用户导出 `.docx` 或截图 → 你需要 `Read` 后转 `reviews/mentor_comments_round{N}.md`
- **形式 B**：导师邮件给批注文本 → 用户粘贴 → 直接存 `reviews/mentor_comments_round{N}.md`
- **形式 C**：用户口述导师意见 → 你记录后让用户校对存盘

**流程**：
1. **录入批注（用 STATE_FILES["mentor_plan"]）**：所有 round 集中在 `reviews/mentor_plan.json`（已加进 STATE_FILES，snapshot 备份+rollback 恢复），通过 `update` 子命令写入；结构：
   ```json
   {"current_round": 1, "rounds": {"1": {"items": [{"id":1, "comment":"原文摘录", "type":"data|logic|wording|reference|figure", "severity":"major|minor", "target_section":"results_3.2", "action":"补图|改写|引文献|拆段", "status":"open|addressed|not_addressed"}]}}}
   ```
   写入命令：`python scripts/state_manager.py update <payload.json>` payload 形如 `{"mentor_plan": {...}}`。
2. **逐条执行**：按严重度（major 先做）+ target_section 顺序处理，每条改完 `status` 设 `addressed` 并写明改动出处。
3. **改动追踪**：每条 `addressed` 后必须主动告知用户"改动 X 在 manuscripts/Y.md 第 Z 段"，方便导师重审定位。
4. **重审准备**：所有 major 处理完 → `/merge --intermediate` 导出当前稿给导师（参见 Phase 16 中间版本约定）；同时生成 `reviews/response_to_mentor_round{N}.md`。
5. **轮次管理**：进入新一轮（round 2/3/…），旧 round 数据保留在 `mentor_plan.json` 的 `rounds` 字段下作修改史；`current_round` 字段同步更新。

**与 Phase 13B（退稿改进）的区分**：Phase 14 是**写作期间**的导师反馈循环（友好、内部）；Phase 13B 是**退稿后**的官方审稿意见回复（正式、对外）。结构化方式相似，但 Phase 14 不出 response letter，Phase 13B 必须出。

### Phase 15: 版本控制 (`/snapshot`, `/rollback`)
智能快照 + 手动备份 + 回滚机制。
- `/snapshot` → `python scripts/state_manager.py snapshot`
- `/rollback`（默认最近快照）→ `python scripts/state_manager.py rollback --target snapshot`
- 回滚到最近一次文献同步备份 → `python scripts/state_manager.py rollback --target literature_sync`

### Phase 16: 最终合并与导出 (`/merge`, `/export_bib`)
> **[用户确认检查点 Mandatory]** 合并前必须展示各章节字数、引用总数和 gate-check 状态，等待用户确认后才执行合并。

**合并前强制核验**：执行 `python scripts/citation_guard.py --index literature_index.json --mcp-cache mcp_literature_cache.json --require-mcp --report citation_guard_report.json --write-back`，仅当 `ok=true` 才允许合并。（`--write-back` 必带：落盘每条 `verified`+`checked_at`，供 L1 逐条短路复用，避免每次全量重验；过期/未验条目仍照常重验。）

生成Word文档和BibTeX引用文件。
- **`/merge` 中间版本 vs 最终版本**：
  - **中间版本（给导师 / 自己核对）**：`python scripts/merge_manuscript.py --manuscript-dir manuscripts --output-md manuscripts/Draft_Round{N}_Manuscript.md --skip-docx`，文件名带 round 编号，不覆盖 Full_Manuscript.md。
  - **最终版本（投稿用）**：`python scripts/merge_manuscript.py --manuscript-dir manuscripts`（默认输出 `manuscripts/Full_Manuscript.md` + .docx）。**只在 `/check` 全过 + `/submission-pack` 已生成后才允许跑最终版**；否则视为中间稿。
  - 可选：`--skip-docx`（仅生成 Markdown）
  - **docx 字体锁定**：`/merge` 自动按候选位置找模板（技能自带 `templates/reference.docx` → 项目 `templates/reference.docx` → 项目根 `reference.docx`，也可用 `--reference-doc` 显式指定），把正文锁为 Times New Roman 12pt、标题 TNR 加粗。图注和表注比正文小一号锁 10pt，摘要走独立样式层同样 10pt。**`/init` 已把模板拷到项目根 `reference.docx`**（§1 Command Logic 第 3 步），正常项目首次导 docx 零人工步骤。模板缺失只出现在老项目（init 时没拷）或模板被删时：docx 步骤硬失败（退出非零、不产出 docx，md 仍正常落盘），不会悄悄产出字体不受控的 docx。自愈只需一条命令：在项目根跑 `python scripts/make_reference_docx.py`（缺基准模板时它会用 pandoc 现产一份，不需要你先有这个文件），生成的 `./reference.docx` 会被 `/merge` 自动认出。要改字体/字号：编辑 `scripts/make_reference_docx.py` 顶部常量后重跑 `python scripts/make_reference_docx.py` 重生成模板（会覆盖项目根 `reference.docx`，这正是改字体的正规路径）。
  - 可选：`--patterns "01_Abstract*.md,02_Introduction*.md,03_Methods*.md,04_Results*.md,05_Discussion*.md,06_Conclusion*.md,07_References*.md,*.md"`（自定义合并顺序与兜底匹配；默认值同此，与 `merge_manuscript.py` DEFAULT_PATTERNS 一致）
- `/export_bib` → `python scripts/export_bibtex.py --index-file literature_index.json --output-file references.bib`
  - 支持 `literature_index.json` 为 list 或 dict（`references/items/entries/data`）

