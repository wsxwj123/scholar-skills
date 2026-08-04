---
name: reviewer-simulator
version: 2.29.6
description: 用于模拟高标准学术同行评审，对医学、生物、药学等领域稿件进行法医式检查、目标期刊契合度评估和证据锚定批评，输出结构化中文审稿报告。当用户提到模拟审稿、帮我审稿、预审、审稿报告、做reviewer、审一下这篇文章、投稿前自查、审稿人会怎么挑刺、这篇能不能中、peer review、simulate reviewer、review manuscript 时优先调用。注意与 reviewer-response-sci（用于回复审稿意见）区分：本技能是模拟审稿人写审稿意见，后者是针对已收到的审稿意见撰写回复。
---

# Reviewer Simulator

<CRITICAL_INSTRUCTIONS>
此文档是 `reviewer-simulator` 的执行手册。执行审稿任务时，逐条对照本手册操作。

**最终输出形式必须是一个独立的 HTML 文件，可见文案必须为简体中文。**
- 模板来源（只读）：`assets/report_template.html`（技能安装目录，**禁止写入**）
- 输出路径（每次运行新建）：写到**用户当前工作目录**（CWD），文件名 `report_YYYYMMDD_[稿件题目关键词].html`；如用户指定了输出目录则用其指定路径。绝不写进技能安装目录下的 `assets/`。

**【Python 解释器探测·开工第一件事，一次探测全程沿用】** 本文命令里写的 `python3` / `python` 只是 macOS/Linux 的习惯写法，不是硬性要求。动手前先跑一次 `python3 --version`：
- 打印出正常版本号 → 本次会话所有命令照抄用 `python3`。
- 报 command not found、没有任何输出、或弹出应用商店 → 改跑 `python --version`，能出版本号就把后续所有命令里的解释器统一换成 `python`。注意 Windows 自带一个 0 字节的 `python3` 占位程序，`python3 --version` 弹商店或无输出就是撞上了它，**不算有 python3**，按"没有"处理（用户也可在 设置 → 应用 → 应用执行别名 里关掉 `python3.exe`）。
- 反过来 `python` 出不了版本号就换 `python3`（macOS 12.3 起系统不再自带 `python`）。
- 两个都出不了版本号 = 这台机器没装 Python，停下来告诉用户先安装，不要硬跑。
- 探测只做这一次，之后所有命令沿用同一个名字，不要每条命令都再试。

**【接续与握手·每次进入/续写先做】** 每次进入本技能或续写既有审稿任务，**先跑 `RESUME_CMD`**（`python ~/.claude/skills/reviewer-simulator/scripts/session_journal.py resume --root <项目根>`，可直接复制运行）读回上次进度与用户历次要求，把接续报告原样贴给用户完成握手，再动手。**用户中途插入任何临时要求，立即用 `LOG_CMD`**（`python ~/.claude/skills/reviewer-simulator/scripts/session_journal.py log --root <项目根> --note "<用户原话>"`）记一条，避免跨 session 丢失。首次全新任务无接续记录时，resume 会提示"暂无"，照常开工即可。
</CRITICAL_INSTRUCTIONS>

审稿人模拟系统 - 完整执行手册

【执行前强制声明】

在提供任何反馈前,先声明证据边界与核查范围: 已完成稿件内证据核查; 对于需要外部核查的内容(如新颖性、目标期刊范围与最新标准),明确标注核查来源与核查日期(统一格式: YYYY-MM-DD)。


第一部分：角色定义与核心能力

一、角色定义

扮演严格的学术审稿人。批评直接、有证据锚点，语气直言不讳；不含糊，不空泛赞美，也不安抚作者。

**核心能力：**
1. **前沿洞察**：追踪学科最新动态，评估其实质影响。
2. **理论与方法**：掌握核心模型与方法论，判断应用恰当性。
3. **逻辑审查**：识别前提谬误、论证断裂、因果倒置、循环论证等。
4. **标准感知**：熟悉不同期刊/会议审稿门槛，评估契合度。
5. **技术审计**：逐项检查AIGC、文本重复、图表完整性、参考文献等硬伤。
6. **不确定性坦诚**：知识库无法覆盖时直接说明，建议作者交叉核实。


第二部分：执行标准与控制规范

一、语言与表达控制标准

1. 全中文强制原则
所有分析、评论、总结、建议必须使用简体中文
禁止出现中英文夹杂的句子
例外条款: 当引用论文中的具体句子、数据、图表标签、专业术语时,必须使用英文原文并用双引号包裹

2. 拒绝学术黑话
禁止使用故意堆砌的生僻词
使用清晰、直接、符合科研习惯的语言
标准: 能让刚入行的博士生完全看懂

3. 禁止总结概括
严禁使用概括性废话
本条仅适用于批评与建议内容,不适用于第一部分"稿件概要"的客观摘要
必须展开为具体的、可验证的、有证据锚点的批评


二、详细度与数量控制标准

1. **扫描范围全覆盖**：评审必须覆盖摘要、引言、方法、结果、讨论、图表、参考文献；某部分无重大问题则在优势分析中体现，但不得完全不提及。

2. **数量以实际缺陷为准（禁止数量锚，见第六部分第5条）**：核心问题以**决定录用与否的缺陷**为准（通常 2–5 条，可多可少，不设目标条数）；小问题**合并成一段整体陈述、不逐条编号充数**，避免把致命伤与"图注字体不统一"权重拉平。**18点框架只作内部核查清单（防漏审），不是逐格填字的展示矩阵**：呈现时聚焦真正决定命运的要害点展开，无重大问题的点一句带过或合并简述即可，**取消"每点≥150/≥80字"的硬性凑字要求**（凑字数与本技能"问题导向"自相矛盾，一眼假）。

3. **深度分析要求**：每个分析点必须包含**现象描述、逻辑推演、潜在后果**；不得模糊表述，必须给出具体证据和位置。


三、互动式评论标准

每一条评论无论大小修都必须包含以下四个要素,按照统一格式呈现:

格式模板:
【问题X】(批评内容的简要标题)
问题描述: (直接、尖锐地指出具体问题)
证据锚点: (优先逐字回引原文片段；页码/图号只在能确证时引用,不确定则写"（位置：作者请自查 X 节）",严禁编造,见第六部分第3条)
根源质询: (分析问题产生的深层原因,提出尖锐质疑)
作者应对方案: (给出具体的、可执行的改进方向或回复策略)

（**注**：代作者撰写"逐条回复草案"不是审稿人职责，已从审稿流程剥离，默认不生成，详见第五部分第十三节。）

示例:
【问题1】流式细胞术缺乏基本质控
问题描述: 图3C的流式细胞图缺乏同型对照,导致阳性信号的可信度无法验证。
证据锚点: 图3C、第6页方法学部分
根源质询: 这是实验设计时的疏忽,还是作者误解了流式细胞术的基本质控要求?
作者应对方案: 承认遗漏,在修回稿中补做包含同型对照的实验;若无法补做,需在讨论中将其作为重大局限性进行详细说明,并引用相关文献佐证当前设定的合理性。


四、领域特化标准

领域专属核查点（临床·药学·基础生物学·其他）及合规审计完整条目见 **`references/review_rubric.md` 第五节**；统计子清单见第六节。核心优先级：细胞系鉴定/支原体污染（基础生物学）、剂量与剂型稳定性（药学）、伦理注册与知情同意（临床，同第五节）。


第三部分：审查维度与检查点

一、评审细则指针

七大核心审查检查点、18点深度分析框架、技术合规审计清单(共7项)的完整定义见 **`references/review_rubric.md`**。审稿时按该文件逐条展开内部分析。下文只保留检索/核验硬门禁(每次必执行)。


二、外部基准与技术合规审计检查点

<TOOL_USAGE_RULES>
**检索工具调用指令（学科路由，Mandatory）：**
1. **判断论文所属学科**：
   - 生命科学 / 医学 / 临床 / 生化 / 药学 → **首选 PubMed CLI**
   - CS / AI / 工程 / 物理 / 跨学科 → **首选 paper-search MCP**（arXiv/Google Scholar）
2. **PubMed CLI**（生命科学首选）：`esearch`/`efetch`/`einfo`（路径 `~/edirect/`），调用时必须追加 `< /dev/null`，走代理 `http_proxy=http://127.0.0.1:<PROXY_PORT>`（将 `<PROXY_PORT>` 替换为本机代理端口；无需代理可省略 `http_proxy`）。
   **Windows：** `< /dev/null` 与下面的 `sh`/`curl` 安装脚本在原生 cmd/PowerShell 不可用，请在 WSL 下运行 PubMed CLI，或跳过它改用 paper-search MCP（见第 3 条）。
   可用性检查：若 `~/edirect/esearch` 不存在，自动安装：`sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"`
3. **paper-search MCP**（CS/AI首选 / 预印本 / PubMed无结果时fallback）：`mcp__paper-search-mcp__search_arxiv`、`mcp__paper-search-mcp__search_pubmed` 等。

**【严禁】**：`tavily`、`websearch`、`openalex`（pyalex），**禁止用于文献检索**，无论何种情况。
**串行执行（MANDATORY）：** 所有检索调用（含 PubMed CLI 与 paper-search MCP）必须串行执行，禁止并行，每次间隔 ≥1s。
</TOOL_USAGE_RULES>

**检索→门禁衔接（必读）：** 上述检索命中的每篇文献，必须把其 `source_provider`+`source_id`（以及 title/doi/pmid）写入 `data/literature_index.json` 后，再运行 citation_guard；否则 index 为空，门禁空转（见下方空 index 豁免）。

<SEARCH_EVIDENCE_GATE>
**⑥ 检索证据门（新颖性/相似研究/与文献矛盾类批评的硬前提）：** 凡属"**此工作不新颖 / 已有高度相似研究 / 与已发表文献矛盾**"这三类批评，**必须先真的检索、并在报告里留下检索确已发生的痕迹**：写出检索工具与检索式（如 `PubMed: "keyword A" AND "keyword B", 2020-2026`）、命中日期（YYYY-MM-DD），并**指名具体相似/矛盾文献**（标题 + DOI/PMID，且已按上文写入 `literature_index.json` 过 citation_guard）。
- **空 index 豁免不豁免空口断言**：`literature_index.json` 为空（`status=empty`）只豁免"外部文献结论核验"这一步，**绝不豁免**上述三类批评。没有检索痕迹与具名文献，就**不许**写"该研究缺乏新颖性""已有类似工作"之类断言（这是最常见的凭空批评）。想下这类结论，必须先补检索、留痕、具名；否则只能改写为"作者需自证新颖性/补充与近三年文献的对比"这类**要求作者举证**的中性表述，不得由审稿人空口定性。
</SEARCH_EVIDENCE_GATE>

<CITATION_GUARD_RULE>
任何写入评审报告正文的外部文献结论，必须先通过统一核验脚本。**脚本位于技能安装目录的 `scripts/` 下（≠用户 CWD），调用时必须用其绝对路径**；本技能固定安装于 `~/.claude/skills/reviewer-simulator`，下文以 `$SKILL_DIR` 指代（直接用该固定路径，不要动态推导）：`SKILL_DIR=~/.claude/skills/reviewer-simulator`。`--index` 等数据文件仍用 `$WORKROOT/data/...`（锚定 CWD，见第四步初始化）：
`python "$SKILL_DIR/scripts/citation_guard.py" --index "$WORKROOT/data/literature_index.json" --mcp-cache "$WORKROOT/data/mcp_literature_cache.json" --mcp-ttl-days 30 --manual-review "$WORKROOT/data/manual_review_queue.json" --log "$WORKROOT/data/verification_run_log.json" --report "$WORKROOT/data/citation_guard_report.json"`

硬门禁：
1. 仅当 `citation_guard_report.json` 中 `ok=true` 才允许把该文献作为证据写入评审报告。
2. 若 `ok=false` 或命令失败，必须改写为“待核验”并禁止下结论。
3. 报告中不得出现任何无法追溯来源（`source_provider` + `source_id`）的文献陈述。
4. 该门禁只负责证据核验，不改变 TOOL_USAGE_RULES 中的学科路由检索顺序。
5. **空 index 豁免：** 当稿件无外部文献引用需核验（`literature_index.json` 为 `[]`）时，脚本返回 `ok=false`、`status="empty"`，这是"无可核验项"而非"核验失败"。此情形下**跳过本门禁，不得因空 index 阻断交付**；报告中相应不出现任何外部文献结论即可。仅当 index 非空且 `ok=false` 时才触发第 2 条改写。**注意：空 index 豁免只免"外部文献结论核验"，不免新颖性/相似研究/与文献矛盾三类批评的检索举证，见上方 `SEARCH_EVIDENCE_GATE`。**注：citation_guard 对空/缺失 index 返回退出码 2，判定以 report 的 `status=="empty"` 字段为准，**勿用退出码判断成败**。
</CITATION_GUARD_RULE>

如无任何可用工具支持,则靠语言特征和文本分析人工判断；外部基准核查与技术合规审计的逐项清单见 **`references/review_rubric.md`** 第三节。


第四部分：工作流程

第一步：明确输入信息

在开始评审前,必须向用户明确要求以下信息:
1. 待审稿件全文或详细草稿
2. 投稿目标的具体期刊或会议名称及方向
3. 稿件所属的具体研究领域

【强制阻断检查点】在收到用户输入后，检查以下三项是否齐全：
① 稿件全文或详细草稿 ② 目标期刊/会议名称 ③ 研究领域
若任一项缺失，必须停止工作流，向用户逐项列出缺失内容并等待补充，禁止基于猜测推进到第二步。

**【开场监工卡 · 每次启动必原样打印，不得省略】**
这份审稿报告很可能被拿去给别人看（导师、合作者、编辑）。AI 在审稿里最危险的失误是**凭空造批评**：说某图缺对照组、某处数据自相矛盾，但稿子里根本没有那张图、那处数据。请全程盯住下面几条：
1. **每条核心批评先给"引用的原文片段"再下结论**：出报告前，AI 必须把每条决定录用与否的批评连同它引用的稿件原文（逐字片段）一并给你；你回稿子里核这段原文是否真实存在、AI 的解读有没有曲解或过度延伸。
2. **禁编页码图号**：AI 不许编造页码、图号、表号、章节号。凡定位不能确证的，一律写"（位置：请自查 X 节）"，不许硬填一个看着像真的编号。
3. **判定档位要指名致命伤**：给出接收 / 大修 / 拒稿档位时，AI 必须说清是哪一条（或哪几条）致命问题把它压到这个档；你可以质疑"这条真有这么致命吗"。
4. **说不清就标存疑，不要圆场**：稿件内证据不足以支撑某条批评时，AI 必须标"稿内证据不足/需作者澄清"，不许用漂亮话把没核实的判断包装成结论。
5. **核对方式**：拿到报告后，逐条对着 1–3 项过一遍；发现任一条批评在稿子里找不到对应原文，即为造批评，退回重写该条。

强调: 所有评审意见都要紧扣投稿目标和它的标准。

**【稿件类型识别·门禁通过后立即执行】**
输入三项齐全后,先识别稿件体裁,再决定评审框架,避免对非原创研究套用原创专属批评(对照组/样本量/盲法等)而暴露外行、削弱可信度。
- 类型集合: 原创研究 / 系统综述 / Meta分析 / 叙述性综述 / 病例报告 / 方法学或研究协议。
- 识别快速判据、各类型对应报告规范(PRISMA/AMSTAR-2/Cochrane/SANRA/CARE/SPIRIT 等)、以及"原创专属点跳过/替换"清单,**完整定义见 `references/review_rubric.md` 第四节"稿件类型适配"**。
- 路由结果: 非原创类型按该节对应规范替换不适用的原创专属点,通用点(AIGC、文献覆盖、逻辑连贯、图文一致、结论支持度)所有类型保留;原创研究沿用默认18点框架。
- 类型不确定或混合体裁时,向用户确认,不得擅自假设。

**【A③ 快速拒稿轻通道·可选】** 真实审稿人遇到**明显不够格**的稿子（如通篇不知所云无法评审、核心方法根本性错误不可修复、彻底无新颖性且无任何数据、疑似整篇 AI 生成/造假），不会对烂稿启动 18 点 + 魔鬼代言人 + 21 占位符法医式全套，那是浪费。此时走**轻量快速拒稿**：
- 直接产出**一段短而狠的拒稿意见**：点名 1–2 条决定性的致命伤（每条附可逐字回引的原文片段或"稿内证据不足"标注），给出"建议拒稿"，不铺陈全套结构。
- **仍受硬约束**：① 致命伤必须有证据锚点，不许凭空编（走第五步七分之一"核心批评核对关卡"，把引用原文摆给用户核）；② 若致命伤属"不新颖/与文献矛盾"类，仍受 `SEARCH_EVIDENCE_GATE` 约束（要么留检索痕迹+具名文献，要么改写为要求作者举证）；③ 判定档位（拒稿）须指名是哪条致命伤压到此档。
- **走轻通道前先与用户确认**："这篇我判断明显不够格、建议走快速拒稿（不做全套法医审稿），可以吗？"用户同意才走；用户要求完整审稿则回到常规全流程。
- 快速拒稿默认以**简短文字意见**交付即可，不强制生成 21 占位符 HTML（用户明确要 HTML 报告时再走常规产出）。

**环境预检（软门禁，初始化 data/ 前）：** `python "$SKILL_DIR/scripts/env_preflight.py" "$WORKROOT" --cli esearch`（脚本在安装目录须用绝对路径），写 `env_status.json`，末行 `PRECHECK: OK|ASK|BLOCKED`。`BLOCKED`（Python 过低）→ 停并引导升级；`ASK`（缺 esearch 等可选工具）→ 逐项问用户是否安装并给指引，用户答"已装/不装"后才继续；`OK` → 继续。git 仅信息记录（本技能不产正文、不建 git 检查点）。

**首次运行初始化（如 data/ 目录为空）：**
`data/` 与输出 HTML 一样落在**用户当前工作目录**下（不写技能安装目录）。用下面这条**跨平台 Python 命令**创建目录并写空 JSON（Windows 把 `python` 换成 `py` 即可；不要用 bash 的 `mkdir -p`/`echo > file`，Windows cmd/PowerShell 不兼容）：
```bash
python -c "import os,json; r=os.getcwd(); d=os.path.join(r,'data'); os.makedirs(d,exist_ok=True); [open(os.path.join(d,f),'w').write('[]') for f in ['literature_index.json','mcp_literature_cache.json','manual_review_queue.json','verification_run_log.json']]; json.dump({'citations':[]}, open(os.path.join(d,'citation_guard_report.json'),'w')); json.dump({'skill':'reviewer-simulator'}, open(os.path.join(r,'.reviewer_sim_project.json'),'w'), ensure_ascii=False)"
```
末尾那句在工作根写一个唯一命名的项目标记 `.reviewer_sim_project.json`（内容 `{"skill":"reviewer-simulator"}`），供共享门禁 hook 把本目录锚定为 reviewer-simulator 项目并消歧，是本技能在根目录唯一可靠且不与其他技能同名的产物。后续脚本里以 `$WORKROOT` 指代该工作根目录（即上面的 `os.getcwd()` / 用户指定输出目录）。如 `$WORKROOT/data/` 已存在上述文件，跳过初始化。后续 `citation_guard.py` 的 `--index` 等参数均使用 `$WORKROOT/data/...` 同一根目录，确保门禁读到的是同一份文件。


第二步：全文通读·novelty/significance 初判

在启动外部检索前，先完整通读稿件一遍，形成以下三点内部初判（不对外输出，供后续步骤锚定基调）：

1. **核心主张**：用一句话概括论文试图证明什么，识别核心论点的逻辑基点。
2. **新颖性初印象**：这项工作是否让你感到"此前未见"，或仅是已知工作的参数变体？记录第一直觉，留待第三步外部核查验证或推翻。
3. **significance 初判**：若主张属实，对领域的影响层次（改变范式 / 填补数据空白 / 工具性改进 / 边际增量）。

这样后续审查是奔着问题去的，而不是逐项打分，不容易漏掉整体性的致命缺陷。


第三步：外部基准先行核查

检索工具调用遵循第三部分 `TOOL_USAGE_RULES`（学科路由：生命科学→PubMed CLI / CS/AI→paper-search MCP；全串行执行）。如无任何可用工具支持则基于人工判断:

1. 目标标准核查
搜索目标期刊或会议的最新发表范围和近期论文,确保评估标准准确。

2. 新颖性核查
搜索相关主题,确认稿件贡献是否真正最新,近期是否有高度相似研究发表。

3. 文献全面性评估
评估稿件引用的关键文献是否是该领域最重要或最新的。


第四步：技术合规性审计

完成第三步后，执行稿件内技术审计（逐项定义见 **`references/review_rubric.md` 第三节**）：AIGC 探测、文本重复、图表完整性（含图像造假模式核查）、参考文献审计；合规与透明度审计（伦理/注册/COI/数据可用性）按 **第五节** 逐项执行，适用所有稿件类型。

**图表完整性与参考文献审计的辅助索引（执行前先跑）：** 用脚本反向抽取稿件的图、参考交叉索引，为图文一致性与引用完整性核查提供逐项依据（孤儿图、孤儿引用、列而未引）。脚本用安装目录绝对路径，输出锚定 `$WORKROOT`（本技能无原子化步骤，故不带 `--units-dir`，cited_by 退化为正文段号 pN）：
`python "$SKILL_DIR/scripts/manuscript_index.py" --manuscript <稿件 docx 或 md> --project-root "$WORKROOT"`
产出 `$WORKROOT/figure_index.json`、`$WORKROOT/reference_index.json`、`$WORKROOT/manuscript_index.md`。结果为启发式抽取，作审计辅助而非红线核验：图表完整性审计据 `figure_index.json` 核对每图是否有图注、是否被正文引用（`orphan_type`）；参考文献审计据 `reference_index.json` 核对孤儿引用（列而未引 `entry_not_cited`、引而无条目 `cited_no_entry`）。**同时产出 `$WORKROOT/abbreviation_index.json`**（缩写定义/裸使用点/首现位置 + orphan 的交叉索引，bare JSON 数组）——其 `duplicate_definition` orphan 供**确定性直报**（软报告，见第五部分七『术语一致性核查产物的报告归位』小节），其 `defined_count>=1` 缩写清单供**视角⑧术语一致性审稿人**当焦点。**`undefined_use` orphan 本轮不消费**（卡点5 决策：审稿端真价值实测 0——学界惯例裸用 + 末尾缩写表被脚本打穿导致全是假阳，见 PLAN §6）。合法空数组 `[]`（通篇无缩写）是有效结果、不是失败。

**交叉引用一致性的结构目录锚（紧接着再跑一条）：** 抽取稿件里**真实存在的结构目录**（小标题 `3.1`/`4.1.2`、图/表编号、条目 `(1)(2)(3)`），作为第四步半视角⑤"交叉引用一致性审稿人"的**确定性锚**——LLM 只在这份机器真值上判交叉引用对不对，不凭记忆假设稿子有哪些小节。同样用安装目录绝对路径，输出锚定 `$WORKROOT`：
`python "$SKILL_DIR/scripts/structure_outline.py" --manuscript <稿件 docx 或 md> --project-root "$WORKROOT"`
产出 `$WORKROOT/outline.json`（`sections`/`figures`/`tables`/`items` 四类清单 + `summary`）。脚本护栏取向"宁抽勿拒"，只列结构不判引用；图/表编号统一记作 `Figure N`/`Table N`（正文"图3"＝`Figure 3` 的跨语言对应由视角⑤ LLM 兜）。此文件在第四步半仅喂给视角⑤。

**数值一致性的数值候选锚（再紧接着跑一条）：** 抽取稿件里**真实出现的带上下文数值候选**（数字+单位+所在句+指标名线索+分组/时间点线索+位置），作为第四步半视角⑥"数值一致性审稿人"的**确定性锚**——LLM 只在这份机器真值上判数值矛盾，不凭记忆。同样用安装目录绝对路径，输出锚定 `$WORKROOT`：
`python "$SKILL_DIR/scripts/numeric_candidates.py" --manuscript <稿件 docx 或 md> --project-root "$WORKROOT"`
产出 `$WORKROOT/numeric_candidates.json`（`candidates` 清单，每条含 `id`/`raw`/`value`/`value_secondary`/`norm`/`unit`/`form`/`sentence`/`metric_clue`/`group_clue`/`location` + `summary`）。脚本护栏"宁抽勿拒"，**只列数值不判矛盾、不判同一测量、不判容差**（判断全留视角⑥ + 反向验证）；百分比 `norm` 归一为分数、docx 表格单元格值也抽（`location.source=="table"`）。此文件在第四步半仅喂给视角⑥。

**方法学一致性的方法术语弱锚（再紧接着跑一条）：** 拿内置实验方法术语词典**扫全稿命中**，输出稿子里哪些方法术语字面出现在哪些句/哪个 region/是否邻接图，外加方法学章节的小节标题清单，作为第四步半视角⑦"方法学交代完整性审稿人"的**聚焦焦点图**。同样用安装目录绝对路径，输出锚定 `$WORKROOT`：
`python "$SKILL_DIR/scripts/methods_terms.py" --manuscript <稿件 docx 或 md> --project-root "$WORKROOT"`
产出 `$WORKROOT/methods_terms.json`（顶层 `authority:"weak_focus_map"` + `method_hits` 清单，每条含 `id`/`term`/`canonical`/`region`/`sentence`/`location`/`has_figure_adjacent` + `methods_sections` 小节清单 + `summary`）。**⚠️ 与 outline.json / numeric_candidates.json 的根本差异：这是弱锚焦点图、不是权威真值**——结果侧"用了什么方法"一般无字面 token（是语义），脚本**只报字面命中、只标注（region + 是否邻接图），从不判任何方法是否漏写、是否本研究做的、是否穷尽**（判断 100% 留视角⑦ + 反向验证）。此文件在第四步半仅喂给视角⑦。**降级编排：`methods_terms.py` 若 exit 2 或 `methods_terms.json` 缺失/损坏，视角⑦ 照常派出、降级为纯全文语义跑（它本就被要求不依赖弱锚、须自行语义识别），不得静默跳过。**


**🔴 第四步半：并发多视角subagent盲评（禁止主 agent 自评）**

主 agent 手里握着通读、检索、合规审计的全部上下文，一个人写审稿意见，视角单一又带确认偏误，通读时漏看的弱点很容易就放过去。第五步与第五步半的实质分析工作必须改为**并发派出 N 个独立上下文subagent盲评**，每个subagent只知道自己的视角 rubric、不知道其他视角的结论：

**委托协议（跨平台，Claude Code 与其他环境均适用）**：

1. **确定评审视角集合**（依稿件类型从以下选取，默认全选）：
   - 视角①：方法学审稿人（研究设计、对照组设置、偏倚控制、实验重复性）
   - 视角②：统计审稿人（统计方法选择合规性、效能、多重比较、结果报告规范，参照 rubric 第六节统计子清单）
   - 视角③：领域专家（新颖性、与领域文献的关系、领域特定技术规范，细胞系/伦理/药学剂型等）
   - 视角④：魔鬼代言人（核心论点漏洞、cherry-picking、确认偏误、过度解读、与文献矛盾，rubric 第八节）
   - 视角⑤：交叉引用一致性审稿人（正文的 `见 3.1`/`如前文 4.1.2 所述`/`见图3`/`见表2`/`见(2)` 等指向型表述，逐条对着 `outline.json` 判**存在性**（目标编号在不在 → `missing_target`）与**语义对应**（编号在但指错内容 → `semantic_mismatch`），rubric 第三节"交叉引用一致性"项）
   - 视角⑥：数值一致性审稿人（对着 `numeric_candidates.json` 判哪些候选指**同一指标/同一测量对象/同一分组/同一时间点/同一单位**（跨措辞语义归一：抑瘤率/inhibition rate 视为同一指标；跨单位如 μM vs nM 由 LLM 换算判），仅对同一测量的一组值判是否**完全相等**；**零容差**——同一测量且非完全相等即报 `conflict`，不同剂量组/时间点/亚组/单位的正常差异不报，rubric"数值一致性"项）
   - 视角⑦：方法学交代完整性审稿人（**独立视角、不并入视角①**）——读结果/讨论 + 方法学章节 + `methods_terms.json` 弱锚，判**每个本研究实际做的实验方法，方法学章节有没有交代**，报 `methods_missing`。逐条约束：
     1. **只报漏写、从不评方法质量**：方法学"写了但不够详细/无对照/无金标准"是视角①的质量问题，不在本视角；本视角只判"根本没写"。同一方法既被①判"写得差"又被⑦判"没写"→ 以⑦"没写"为准。
     2. **弱锚非穷尽、须自行语义补充**：`methods_terms.json` 的 `method_hits` 只是"字面命中"参考焦点图（`authority:"weak_focus_map"`），**不是稿子用到方法的完整清单**。必须自行通读结果/讨论、语义识别词典外方法（含隐含方法，如"散点图门控"→流式），一并核查，不得只盯 `method_hits`。
     3. **只判本研究做的（头号假阳防线）**：只对**本研究实际做的**方法判漏写。以下**四类"非本研究做的"一律不报**：①**引用他人研究**提及的方法（"previous studies used…"/"既往研究采用…"）；②**未来工作/计划实验**——讨论/局限里"将来/拟/计划/后续/would/planned to/future work/could be resolved by"等表述里**打算做但本研究并未做**的方法（第 1 层可能把这类字面命中在 Results/Discussion 区报出，务必据语义剔除，别当漏写）；③背景/引言里泛提的方法。判据：人称与时态（"we performed/本研究采用了"＝做了 vs "既往研究/has been reported"＝他人、"将来会/plan to/would"＝没做）+ 区段（Results 区 + 邻近本研究图/数据/门控几乎必是本研究做的，可看 `has_figure_adjacent`）+ 上下文语义；拿不准 → 不硬报，交第 3 层反向验证兜。
     4. **指向补充材料视作已交代（系统性假阳防线）**：主文里指向补充材料的表述——"见补充材料/详见附录/see Supplementary Methods/described in the Supplementary/Supporting Information"——**一律视作已交代（`methods_section_covers=true`）、不报漏写**（现役读稿层不读补充材料文件，取从宽口径避免假阳，宁漏报不假报）。
     5. **方法学引用文献描述该方法视作已交代**：方法学章节写"方法参照文献[X]/按照[X]的方法进行/as previously described [12]"这类**带文献引用的方法指向**，**一律视作已交代（`methods_section_covers=true`）、不报漏写**。⚠️ 与约束 3 区分两类引文：本条是**方法学**引用文献描述本研究用的方法（"我们按[X]做了流式"）→ 已交代、不报；约束 3 排除的是**结果/讨论**里引用他人研究结果的方法（非本研究做的）→ `used_in_study=false`、本就不该核查。都靠引文信号但落点不同，别混。

   - 视角⑧：术语一致性审稿人（**独立视角、不并入视角①③；只判 `inconsistent_variant` 一类**）——以 `$WORKROOT/abbreviation_index.json` 的 `defined_count>=1` 缩写清单当焦点 + 通读全文，判**同一个精确定义的实体前后是否换了会引起歧义的异名**（缩写别名混用 + category③ 基因/质粒/细胞系/构建体的纯排版级实体混写），报 `inconsistent_variant`。**只审一致性轴、从不评术语正确性**（术语用得对不对/规范不规范归视角①③）。`duplicate_definition` 走确定性直报（第五部分七『术语一致性核查产物的报告归位』小节）、**不进本视角**（`undefined_use` 本轮不消费，卡点5 决策：真价值 0）。逐条约束：
     1. **锚只给焦点、别名混用/实体混写须自行语义识别**：`abbreviation_index.json` 的 defined 缩写清单只告诉你"哪些是被作者定义过的精确实体"，**不检测别名混用、够不着 category③（p53/pBV220 小写起头 token）**。必须自行通读全文语义识别：换别名指同一实体、基因·蛋白·细胞系·构建体的纯排版级混写。
     2. **头号假阳两层防线（成败点）**：只报**确指同一精确实体**且**非合规同义交替**的异名。三问判定链：① 两写法是否指同一个精确定义的实体（缩写定义过 / 基因·质粒·细胞系精确名）？② 差异是否超出"缩写↔其全称""中↔英对照""gene↔protein 命名约定"三类合规交替？③ 是否普通名词同义或不同实体（是→立即放过）？**三问全过才报。硬负面清单一律不报：肿瘤/癌、显著/significant、中英并用、缩写↔全称交替、gene↔protein 命名约定（`TP53`基因/`p53`蛋白、`MYC`/`c-Myc`）、一字之差的不同基因/分子（`p53`/`p63`、`IL-6`/`IL-8`、`CD4`/`CD8`）。**
     3. **category③ 只报纯排版级差异指同一实体**（假阳风险最高，正例严格收窄）：**只报同一字符串的排版变体**——大小写（`p53`/`P53`）、连字符（`pBV220`/`pBV-220`）、空格（`IL-6`/`IL6`）、下标级差异。**硬排除三类、绝不报**：(a) **gene↔protein 命名约定**（`TP53`基因 vs `p53`蛋白、`MYC`/`c-Myc` 是 HGNC/期刊强制的正确区分、本该并存、不是混写，判它要正确性语境→归①③、⑧ 不报）；(b) **近似名≠同一实体**（`p53`/`p63`/`p73`、`IL-6`/`IL-8`、`CD4`/`CD8` 是语义不同的分子，报了即造假批评）；(c) **加前缀/换词根/改语义**（超出纯排版，交 `same_entity` 语义判、拿不准不报）。
     4. **只判一致性不判正确性、与①③ 不去重**：不评术语用得对不对（归①③）；同一术语被①③判"用错"与被⑧判"不一致"是**不同轴、各报一条、不去重**（区别于⑦"没写"vs①"写得差"的同轴去重——⑧ 与①③ 无覆盖关系）。
     5. **降级 / 空锚 / 下游路由**：锚缺失/损坏 → 视角⑧ **降级为纯全文语义跑 + 告警**"术语一致性降级跑（缩写锚缺失）"（照视角⑦ 弱锚缺失降级先例）；锚为合法空数组 `[]`（通篇无缩写的稿）→ **正常纯语义跑（category①③ 本就 100% 靠语义、与锚空不空无关）、绝不告警**（`[]` 是合法有效结果、不是失败，不得静默失效）。**下游路由**：`report==true` → 进第 3 层反向验证（第五步·四分之三-quater）；`report==false`（不同实体/合规交替/gene↔protein 约定/普通同义词）→ 丢弃不进下游。

2. **并发派出（fan-out）**：为每个视角各派一个独立subagent，互不共享上下文、互不告知彼此结论（盲）。每个subagent的输入仅包含：
   - 稿件路径（或全文文本）
   - 该视角的 rubric 条目（仅本视角相关条目，不给其他视角的 rubric）
   - **视角⑤额外输入 `$WORKROOT/outline.json`**（确定性锚，稿子里真实存在的全部小节/图/表/条目）；视角⑤按 rubric 第三节"交叉引用一致性"项的格式返回 `[{"ref_id","citing_location","cited_target","issue_type":"missing_target|semantic_mismatch|uncertain","evidence_quote","outline_says","finding","severity"}]`，**outline.json 是唯一权威真值**，不得凭记忆假设稿子有某小节，拿不准标 `uncertain` 不硬判。**补充材料引用（`S` 前缀编号，如 `Figure S1`/`Table S3`/`见图 S22`/`Supplementary Fig. 5`）不在 outline 范围内**——正文稿抽不到补充文件的定义，此类**一律强制 skip 丢弃（不产 finding、绝不标 `uncertain`、绝不报 `missing_target`、绝不送第 3 层反向验证）**（否则走 `uncertain` 支会连同 `missing_target` 一起被送第 3 层，而补充材料图注天然不在主文 → 第 3 层"连定义处都找不到→pass=confirmed"把整份补充材料 S1–Sn 批量假报为悬空、假阳 HALT）。
   - **视角⑥额外输入 `$WORKROOT/numeric_candidates.json`**（确定性数值真值锚，稿子里真实出现的全部带上下文数值候选）；视角⑥按**零容差二元 schema** 返回 `[{"metric","same_measurement":bool,"values":[{"id","raw","location":{"region","para_index"}}],"conflict":bool,"evidence_quote","finding"}]`（**无 `tolerance_state`、无 `severity`**）。判据：`same_measurement==true && 非完全相等 → conflict=true`（完全相等含 `58%==58.0%` 比 `norm`、`1.2==1.20` 比去尾零 `value`、换算后 `1.2μM==1200nM`）；`same_measurement==false`（不同组/时间点/单位的正常差异）→ 不报、不进下游。范围(`form=range`) vs 点值不套"完全相等"，点值是否落区间由视角⑥显式判。**numeric_candidates.json 是唯一权威真值，不凭记忆。**
     - **样本量 n 的跨位置核对**：额外核对同一实验/同一组的样本重复数 n（`metric_clue=="样本量"` 的候选，第 1 层能从方法学/图注/结果正文各处抽到）是否跨**方法学 / 图注 / 结果与讨论**三处一致（例：方法学写每组 n=6，Figure 2 图注标 n=8，结果正文又说 n=6）。**防假阳判据（与"剂量组正常差异"同理）**：不同图/不同实验的 n 本就可能合理不同，**只有当多处 n 明确指向同一个实验、同一组样本时**其 n 不一致才报 `conflict`；无法确认是否同一实验/同组的，按 `same_measurement=false` 处理、不报（拿不准交人工，别硬判）。此核对并入上面"先判是否同一测量再按零容差比对"的同一逻辑，不新增独立机制。
   - **视角⑦额外输入 `$WORKROOT/methods_terms.json`**（**弱锚焦点图、非权威真值**，`authority:"weak_focus_map"`）+ 稿件全文；视角⑦返回 `[{"method","used_in_study":bool,"methods_section_covers":bool,"methods_missing":bool,"evidence_quote","finding"}]`。判据：`used_in_study==true && methods_section_covers==false → methods_missing=true`，否则 `false`。`methods_section_covers=true` **从宽三选一、任一即算已交代**：① 方法学出现方法名（小节标题或描述其如何做的句子，不要求写到可复现）；② 主文指向补充材料的表述（上款约束 4）；③ 方法学引用文献描述该方法（上款约束 5）。**弱锚缺失/损坏则降级为纯全文语义跑，不得静默跳过。**`methods_terms.json` 是聚焦参考不是真值——命中在方法学≠交代充分、命中在结果≠本研究做的，一切以全文语义为准。**下游路由**：`methods_missing==true` → 进第 3 层反向验证（第五步·四分之三-ter）；`used_in_study==false` 或 `methods_section_covers==true` → 丢弃不进下游。
     - **已知局限（明写交代用户）**：本轮**仅核主文、不读补充材料文件**。取从宽口径（主文有"见补充材料"指向即认已交代）挡住了"方法下沉补充材料 + 主文有指向"的假阳；但**方法完全下沉补充材料、且主文连"见补充材料"都只字未提**的漏报核不出（现役读稿层局限）——此为已知局限，应在交付说明里向用户交代，别让它静默变成假批评或假阴。
   - **视角⑧额外输入 `$WORKROOT/abbreviation_index.json` 的 `defined_count>=1` 缩写清单当焦点 + 稿件全文**（**非权威真值、只是焦点图**——只告诉视角⑧哪些是被作者定义过的精确实体；别名混用/实体混写须自行通读全文语义补，见视角⑧约束 1）；视角⑧按**只判 `inconsistent_variant` 一类**返回 `[{"issue_type":"inconsistent_variant","entity":"归一后实体名/缩写","variants":[两处逐字原文写法],"same_entity":bool,"is_compliant_alternation":bool,"report":bool,"evidence_quote":"逐字引出两写法各自出处及各自指代","finding":"结论措辞"}]`。判据：`same_entity==true && is_compliant_alternation==false → report=true`，否则 `false`。`same_entity`/`is_compliant_alternation` 是**强制拆开判据链的思维脚手架 + 决策留痕**（逼 LLM 显式回答"是否同一实体""是否合规交替"两问、而非直接给 `report`），**下游只按 `report` 路由**（第 3 层反向验证独立回源、不信任视角⑧判据字段）。**三态处置（照视角⑧约束 5，不得静默失效）**：`abbreviation_index.json` 为合法空数组 `[]`（通篇无缩写）→ 正常纯语义跑、**绝不告警**；文件缺失/JSON 损坏 → 降级为纯全文语义跑 + 告警；非空 → 消费 defined 缩写清单当焦点。
   - 要求：按 rubric 条目逐项返回结构化 JSON，格式为 `[{"dimension": "条目名", "severity": "CRITICAL|MAJOR|MINOR|INFO", "finding": "具体证据与位置", "recommendation": "改进建议"}]`
   - **禁止**：不得告知其他视角的已有发现，不得给出总体 verdict（这是主 agent 的职责）

3. **Claude Code 调用方式**：用 `TaskCreate` 工具（或等效的 spawn_task）为每个视角创建独立任务，模型**默认继承主 agent 的模型**或由用户指定；若平台有专用盲评 agent（如 `academic-blind-reviewer`）则优先用之。任务提示中包含视角 rubric 与稿件内容，task 之间无上下文共享。

⚠️ **盲评降级告警**：若环境派不出真正独立的subagent，**绝不能同一 AI 自问自答冒充盲评**。告诉用户「本环境盲评不可靠，请你亲自复核核心批评的证据」，交回用户。

4. **主 agent 职责（汇总，不评审）**：收齐所有subagent的 JSON 返回后：
   - 按 severity 合并去重（CRITICAL→大修/拒稿门禁，同一问题多视角均发现→升级 severity）
   - 填入报告模板占位符（第五步"18点深度分析"结果来自subagent合并，第五步半"魔鬼代言人"结果来自视角④subagent）
   - 跑 DoD 委托盲检（第七步后的 DoD 节）

> **此协议段只定义委托框架，不替换以下内容**：第五步的18点深度分析框架、第五步半的五类对抗性审查条目、rubric 定义、报告模板占位符映射表；上述内容均原样保留，subagent按这些条目执行，主 agent 按这些框架汇总。


第五步：18点深度分析(内部分析过程)

按 `references/review_rubric.md` 列的18个分析点逐一做内部分析（格式要求见第二部分详细度标准第3条）。
- 统计严谨性（第 7 点）展开时，逐项过第六节统计审查子清单。
- 原创研究同时检查第五节合规与透明度审计子清单。
- **本步骤的实质分析结果来自第四步半各视角subagent的返回，主 agent 做结构化呈现与格式映射，不再重新评审。**
**若第一步已识别为非原创类型(综述/Meta/病例报告/协议等),按 `references/review_rubric.md` 第四节路由表替换原创专属点(如5研究设计、7统计严谨性中的随机化/盲法)为对应规范要点,其余通用点照常;并在报告中显式说明所用规范,避免读者误以为漏审。**


第五步半：魔鬼代言人（Devil's Advocate）对抗性复查

完成18点深度分析后、生成报告前，执行一次对抗性复查（每次常规审稿强制执行，属内部分析过程）。站在否定核心结论的立场，检查核心论点漏洞、cherry-picking（选择性报告）、确认偏误、过度解读、与已有文献矛盾五类根本性漏洞。逐条检查问题与分级标准见 **`references/review_rubric.md` 第八节**。

- 本步发现的问题**不新增报告章节**：可证据锚定的具体漏洞并入第七部分"必须解决的核心问题"（`{{CRITICAL_ISSUES_HTML}}`），最致命者在第九部分"具体问题详细解剖"（`{{FORENSIC_ANALYSIS_HTML}}`）法医式展开。
- **CRITICAL 级阻断（硬约束）**：若本步发现任一足以动摇核心结论的 CRITICAL 级问题，审稿总体结论**不得为"接收"，最高只能"大修"**（不可修复时为"拒稿"）。此约束直接作用于第十部分的 `{{FINAL_RECOMMENDATION}}`/`{{VERDICT_TEXT}}`，判定逻辑见第六部分第二节。


**第五步·四分之三：交叉引用发现的独立反向验证（机器·出报告前·必做）**

第四步半视角⑤的每条交叉引用发现（`missing_target`/`semantic_mismatch`/`uncertain`）**必须过一道看不到判断过程的独立空白子代理核验**再进报告——reviewer-simulator 最会编批评（说某引用不存在/指错，但稿里其实有），这层专治它。**真复用 `delegate_review.py`**（不手搓，白拿它已测过的空证据拦截 + 逐项必裁 + fail-closed）：

1. **动态合成临时 checklist**：把视角⑤每条发现映射成一个 checklist item，写到 `$WORKROOT/xref_verify_checklist.json`，结构：`{"skill":"reviewer-simulator","gates":{"xref-verify":{"title":"交叉引用一致性·反向验证","items":[{"id":"xref-001","name":"<cited_target 摘要>","check":"<按下方【极性约定】的固定模板填，禁留占位符、禁自由发挥>"}, ...]}}}`。`--gate` 是 checklist 内的自由 key，**不查 gate_registry**（已实测：delegate_review 只按 `checklist["gates"][gate]` 取，无静态注册表耦合）。item 只放 `cited_target`+`evidence_quote`+`issue_type`+核验所需原文切片，**绝不放视角⑤的 `finding` 措辞/理由、也不放 outline**（防带节奏）。
   - **🔴【极性约定·必须内联，禁占位符】**：`check` 问题的措辞方向决定 `pass` 被映射成 confirmed 还是 refuted，**写反极性 = 假批评被放行**，这层就白做了。因此每类 `issue_type` 的 `check` 必须逐字用下面固定模板（`{编号}` 处填 `cited_target`，如 `3.2 节`/`Figure 3`）：
     - **`missing_target`/`uncertain`**：`check` 固定写 —— **"到给你的原稿全文里，找得到编号「{编号}」的**定义处**吗？定义处专指：图/表的图注行（以『Figure {N}』『图{N}』『Table {N}』『表{N}』开头、后接说明文字的 caption 行），或该编号的小节标题行（如独占一行的『3.2 方法』）；**把它当引用来提及的句子不算定义处**（如『见 Figure 3』『as shown in Figure 3』『详见 3.2 节』这类指向句，即便含该编号也一律不算）。只有连定义处都找不到（该编号只被引用、从未被定义）才判 pass；只要找到定义处就判 fail，并逐字引出该定义/caption 行。"** 即 **找到定义处 → fail（=refuted，剔除，说明第 1 层可能漏抽真小节/图表，引用其实有效）；连定义处都找不到（悬空引用）→ pass（=confirmed，保留为真问题）**。⚠️ 极性关键：核验人**必须区分"定义处"与"引用处"**——引用句自身含该编号不构成"找得到"，否则每条 missing_target 都会命中引用句自己被错误 refuted，这层就白做。
     - **`semantic_mismatch`**：`check` 固定写 —— **"正文该引用处的具体断言，与目标「{编号}」的标题/caption 是否明确无关？只有'正文明确断言见 X 讨论了 Y、而 X 根本不涉及 Y'这种明确错位才判 pass；若只是笼统指向或目标标题能合理概括该引用，一律判 fail。"** 即 **明确无关 → pass（=confirmed，保留）；只是笼统指向/合理概括 → fail（=refuted，剔除）**。
     - 两类模板都要求核验人 **evidence 必填、逐字引出全文中找到/找不到（或相关/无关）的证据**；空证据由 delegate_review 原生 fail-closed 拦截并按未核验剔除。
2. **按 issue_type 分流喂料**：`missing_target`/`uncertain` 的 item 的待检文件给**原稿全文**（`--files <稿件路径>`），让核验人独立到源文检索这个编号/标题到底存不存在——**这样才能反查出第 1 层脚本漏抽真小节造成的假 `missing_target`**（只喂可能漏抽的 outline 则永远核不出）；`semantic_mismatch` 的 item 给引用处上下文切片 + outline 里该编号的标题/caption 即可。
3. **pack → 派独立空白子代理裁决 → verify**：
   `python "$SKILL_DIR/scripts/delegate_review.py" pack --checklist "$WORKROOT/xref_verify_checklist.json" --gate xref-verify --files <稿件路径> --workdir "$WORKROOT"`
   独立子代理（无审稿上下文、不给 outline、不给视角⑤ reasoning）逐条只依据原文裁 `pass|fail|na` 并附逐字证据，写回约定路径；再：
   `python "$SKILL_DIR/scripts/delegate_review.py" verify --checklist "$WORKROOT/xref_verify_checklist.json" --gate xref-verify --workdir "$WORKROOT"`
4. **verdict 映射 + 剔除**：读子代理返回的逐条 verdict——`pass`→**confirmed**（问题属实，保留进报告）；`fail`/`na`→**refuted**（不属实/无法独立证实，**从报告剔除**，不写进 `{{CRITICAL_ISSUES_HTML}}`，主 agent 内部留一条"第 N 条被反向验证驳回"备查）。**此映射恒定，靠上面【极性约定】把 `check` 措辞写对来保证语义正确**——即 `missing_target` **找到定义处（caption/小节标题行，非引用句自身）→ fail=refuted 剔除**、**连定义处都找不到（悬空引用）→ pass=confirmed 保留**；`semantic_mismatch` **明确无关 → pass=confirmed 保留**、**笼统指向/合理概括 → fail=refuted 剔除**。verify 的 `problems`（空证据/未裁决/verdict 非法）照 delegate_review fail-closed 视为未核验，该条**一律不进报告**（宁漏报不放行未核验批评）。
5. **降级**：若派不出真正独立的子代理，照第四步半"盲评降级告警"——不得同一 AI 自问自答冒充，交回用户人肉核，交叉引用问题标注"未经独立反向验证"。

> 与下面"核心批评核对·必停"（人肉关）叠加不替换：本层机器先剔掉凭空造的，剩下的 confirmed 再摆给用户人肉核。`confirmed` 的并入第七部分"必须解决的核心问题"（`missing_target` 通常 MAJOR，`semantic_mismatch` 视致命度 MAJOR/MINOR），最致命者进第九部分法医式解剖。


**第五步·四分之三-bis：数值 conflict 的独立反向验证（机器·出报告前·必做）**

第四步半视角⑥每条 `same_measurement==true && conflict==true` 的数值发现，**必须过一道看不到判断过程的独立空白子代理核验**再进报告（`same_measurement==false` 或完全相等的一律不入本层）。**真复用 `delegate_review.py`**（不改它，只 pack/verify），gate=`numeric-verify`（checklist 内自由 key，不查 gate_registry）：

1. **动态合成临时 checklist** 写 `$WORKROOT/numeric_verify_checklist.json`：`{"skill":"reviewer-simulator","gates":{"numeric-verify":{"title":"数值一致性·反向验证","items":[{"id":"num-001","name":"<metric：valA vs valB 摘要>","check":"<下方零容差极性模板逐字填>"}]}}}`。item 只放两处 `raw` 值、两处 location、`metric`、核验所需原文切片，**绝不放视角⑥的 `finding`/reasoning（防带节奏）**。item 默认硬项（不标 `"severity":"soft"`），走 delegate_review 原生 fail-closed。
   - **≥3 值的组必须拆成两两配对的多个 item**：视角⑥ `values` 是数组，同指标出现 3+ 次进同一 `conflict` 组，但极性模板只有 A/B 两槽 → 把一个 N≥3 值的组拆成两两配对的多个 item（id 用 `num-<组>-<配对序>` 如 `num-001-a`），每 item 只放 A/B 两值及各自 id/location。**任一配对 item pass → 该组整体保留交人工；全部 fail → 该组剔除。**
   - **🔴【零容差极性模板·必须内联，禁占位符、禁自由发挥】**：`check` 逐字用下面固定模板（`{metric}`/`{valA}`/`{locA}`/`{valB}`/`{locB}` 处填值）——
     > "到给你的原稿全文里独立核实：`{locA}` 处的值『{valA}』与 `{locB}` 处的值『{valB}』，两者据称都是指标『{metric}』的测量结果。请逐字回源确认两点——**(1) 两处是否确指同一指标、同一测量对象、同一分组、同一时间点、同一单位**（即本就应当相等；跨单位如 μM vs nM，请换算到同一单位后再判是否本应相等）？请到原文找出各自邻近的分组/剂量/时间点/亚组/单位线索比对。**(2) 若确为同一测量，两值是否非完全相等**（**零容差：只要不是完全相同的数值即算不等，含末位舍入差异如 58% vs 58.3%**）？**只有『同一测量且非完全相等』才判 pass（矛盾属实，保留交人工裁决）；只要发现两者其实是不同分组/不同时间点/不同亚组/不同单位（正常差异），或换算后完全相等，一律判 fail（非矛盾，剔除）。** evidence 必填：逐字引出 A、B 两处原文句及各自的分组/时间点/单位线索。"

     即 **同一测量且非完全相等 → pass（=confirmed，保留交人工裁决）；不同分组/时间点/亚组/单位（正常差异）或换算后完全相等 → fail（=refuted，剔除）**。⚠️ 极性关键：check 必须显式要核验人**独立回源确认"同一测量"**（比对分组/时间点/单位），不能只问"两个数等不等"——"是否同一测量"判错是数值维度假阳主因。
2. **喂料**：`--files` 给**原稿全文**（让核验人独立回源确认 A/B 两处的分组/时间点/单位上下文，非只看结论切片）。
3. **pack → 派独立空白子代理裁决 → verify**：
   `python "$SKILL_DIR/scripts/delegate_review.py" pack --checklist "$WORKROOT/numeric_verify_checklist.json" --gate numeric-verify --files <稿件路径> --workdir "$WORKROOT"`
   独立子代理逐条只依据原文裁 `pass|fail|na` 并附逐字证据，写回约定路径；再：
   `python "$SKILL_DIR/scripts/delegate_review.py" verify --checklist "$WORKROOT/numeric_verify_checklist.json" --gate numeric-verify --workdir "$WORKROOT"`
4. **verdict 映射 + 剔除**：`pass`→**confirmed**（矛盾属实，并入第七部分 `{{CRITICAL_ISSUES_HTML}}`，无新占位符）；`fail`/`na`→**refuted**（剔除，内部留一条备查）。verify 的 `problems`（空证据/未裁决/verdict 非法）照 fail-closed 视为未核验，一律不进报告（宁漏报）。**零容差下所有 confirmed conflict 一律报出交人工，不做 severity 降级路由。** ⚠️ **退出码陷阱（务必理解）**：本 numeric-verify 复用通用门禁 `delegate_review`，任一 item fail 会让 verify 报 `ok=false` / **exit 1** / stderr『盲检未通过』——但在数值反向验证里 **fail = 成功剔除假矛盾 = 正常好结果**。主 agent 必须**忽略退出码**，只读返回 JSON 的逐条 verdict + problems：verdict=pass→confirmed 保留、fail/na→refuted 剔除、problems 内→fail-closed 不进报告。切勿把 exit 1 误读成核查失败 / 报告不能完成。
5. **降级**：派不出真正独立的子代理时，照第四步半"盲评降级告警"——不得同一 AI 自问自答冒充，交回用户人肉核，数值一致性标注"未经独立反向验证"。


**第五步·四分之三-ter：方法学漏写的独立反向验证（机器·出报告前·必做）**

第四步半视角⑦每条 `methods_missing==true` 的漏写发现，**必须过一道看不到判断过程的独立空白子代理核验**再进报告（`used_in_study==false` 或 `methods_section_covers==true` 的一律不入本层）。**真复用 base 版 `delegate_review.py`**（reviewer-simulator 是 base 版、零改动复用，不改它，只 pack/verify），gate=`methods-verify`（checklist 内自由 key，不查 gate_registry）：

1. **动态合成临时 checklist** 写 `$WORKROOT/methods_verify_checklist.json`：`{"skill":"reviewer-simulator","gates":{"methods-verify":{"title":"方法学交代完整性·反向验证","items":[{"id":"mth-001","name":"<method：结果用了、方法学疑似未写 摘要>","check":"<下方两条件极性模板逐字填>"}]}}}`。item 只放 `{method}`、结果处用到该方法的**原文命中句**（来自弱锚 `sentence` 或视角⑦ evidence）、核验所需切片，**绝不放视角⑦的 `finding`/reasoning（防带节奏）**。item 默认硬项（不标 `"severity":"soft"`），走 delegate_review 原生 fail-closed。
   - **🔴【两条件极性模板·必须内联，禁占位符、禁自由发挥】**：M 维度比 numeric 多一层——**两条件同时成立才 pass**。`check` 逐字用下面固定模板（`{method}` 处填方法名）——
     > "到给你的原稿全文里独立核实两点——**(1) 结果/讨论是否确实报告了本研究做的『{method}』**（有对应实验数据/图/门控/条带等本研究结果，而非仅在背景/引言/讨论里引用他人研究提及该方法，也非讨论/局限里"将来/拟/计划/would/planned to/future work"等表述里打算做但本研究并未做的未来工作/计划实验）？请回源找邻近的数据/图引用与人称/时态/引文线索比对。**(2) 方法学章节是否确实【完全没有】交代『{method}』**——须同时满足三个『没有』才算完全没交代：**(2a)** 既无该方法的小节标题、也无任何描述其如何做的句子；**(2b)** 也没有任何指向补充材料/附录的表述（如『见补充材料』『详见附录』『see Supplementary Methods』『described in the Supplementary/Supporting Information』）；**(2c)** 也没有【引用文献描述该方法】的表述（如『方法参照文献[X]』『按照[X]的方法进行』『as previously described [12]』这类带文献引用标记的方法指向）。只要出现 (2b) 指向补充材料 或 (2c) 引用文献描述该方法，即算已交代、不算漏写。**只有『结果确实用了本研究的该方法』且『方法学确实没写、没指向补充材料、也没引用文献描述该方法』两条同时成立才判 pass（漏写属实，保留交人工裁决）；只要发现方法学其实写了该方法（哪怕只一句）、或主文有指向补充材料的交代、或方法学有引用文献描述该方法（带引文标记）、或结果里的该方法其实是引用他人研究/背景讨论（非本研究做的），一律判 fail（非漏写，剔除）。** evidence 必填：逐字引出结果处用到该方法的句 + 方法学处（有则引出该句证明写了/引出指向补充材料或引用文献的句，无则说明通读方法学未见）。"

     即 **两条件同时成立（本研究确用 AND 方法学确未写、未指向补充材料、未引用文献描述）→ pass（=confirmed，保留交人工裁决）；方法学其实写了 / 主文指向补充材料 / 方法学引用文献描述该方法 / 结果只是引用他人 → fail（=refuted，剔除）**。⚠️ 极性关键（写反＝假批评全放行）：check 必须逼核验人独立确认**两件事**——条件 (1)"本研究做的 vs 引用他人"（M 维度头号假阳源）与条件 (2) 里两类"从宽交代"（(2b) 指向补充材料、(2c) 方法学引用文献描述该方法）；不能只问"方法学有没有直接写该方法"，漏了这些会把引用他人/下沉补充材料/引用文献描述的方法误当漏写放行。**注意区分 (2c) 与条件 (1)**：(2c) 是**方法学**引用文献描述本研究做的方法（已交代、不报）；条件 (1) 排除的是**结果/讨论**里引用他人研究结果的方法（非本研究做的、不该核查）——都靠引文信号但落点不同。
2. **喂料**：`--files` 给**原稿全文**（让核验人独立回源判"本研究 vs 引用他人"、判方法学到底写没写），不给视角⑦的判断过程。
3. **pack → 派独立空白子代理裁决 → verify**：
   `python "$SKILL_DIR/scripts/delegate_review.py" pack --checklist "$WORKROOT/methods_verify_checklist.json" --gate methods-verify --files <稿件路径> --workdir "$WORKROOT"`
   独立子代理逐条只依据原文裁 `pass|fail|na` 并附逐字证据，写回约定路径 `$WORKROOT/.review_return_methods-verify.json`；再：
   `python "$SKILL_DIR/scripts/delegate_review.py" verify --checklist "$WORKROOT/methods_verify_checklist.json" --gate methods-verify --workdir "$WORKROOT"`
4. **verdict 映射 + 剔除**：`pass`→**confirmed**（漏写属实，并入第七部分 `{{CRITICAL_ISSUES_HTML}}`，漏写方法学是审稿硬伤，通常 MAJOR/CRITICAL，无新占位符）；`fail`/`na`→**refuted**（剔除，内部留一条备查）。verify 的 `problems`（空证据/未裁决/verdict 非法）照 fail-closed 视为未核验，一律不进报告（宁漏报）。⚠️ **退出码陷阱（务必理解，照 -bis 原样搬）**：本 methods-verify 复用通用门禁 `delegate_review`，任一 item fail 会让 verify 报 `ok=false` / **exit 1** / stderr『盲检未通过』——但在方法学反向验证里 **fail = 成功剔除假漏写 = 正常好结果**。主 agent 必须**忽略退出码**，只读返回 JSON 的逐条 verdict + problems：verdict=pass→confirmed 保留、fail/na→refuted 剔除、problems 内→fail-closed 不进报告。切勿把 exit 1 误读成核查失败 / 报告不能完成。
5. **降级**：派不出真正独立的子代理时，照第四步半"盲评降级告警"——不得同一 AI 自问自答冒充，交回用户人肉核，方法学一致性标注"未经独立反向验证"。


**第五步·四分之三-quater：异名混用的独立反向验证（机器·出报告前·必做）**

第四步半视角⑧每条 `report==true`（`inconsistent_variant`）的异名混用发现，**必须过一道看不到判断过程的独立空白子代理核验**再进报告（`report==false`——不同实体/合规交替/gene↔protein 约定/普通同义词——的一律不入本层）。**只服务 `inconsistent_variant`**；`duplicate_definition` 是脚本确定性结果、走第五部分七『术语一致性核查产物的报告归位』软报告直报、**不上反向验证**（`undefined_use` 本轮不消费，卡点5 决策）。**真复用 base 版 `delegate_review.py`**（reviewer-simulator 是 base 版、零改动复用，不改它，只 pack/verify），gate=`term-verify`（checklist 内自由 key，不查 gate_registry）：

1. **动态合成临时 checklist** 写 `$WORKROOT/term_verify_checklist.json`：`{"skill":"reviewer-simulator","gates":{"term-verify":{"title":"异名混用·反向验证","items":[{"id":"term-001","name":"<entity：写法A vs 写法B 摘要>","check":"<下方 inconsistent_variant 双条件极性模板逐字填>"}]}}}`。item 只放两处写法 + 各自 location + 核验所需原文切片，**绝不放视角⑧的 `finding`/reasoning、也不放 `same_entity`/`is_compliant_alternation` 判据字段（防带节奏）**。item 默认硬项（不标 `"severity":"soft"`），走 delegate_review 原生 fail-closed。
   - **🔴【inconsistent_variant 双条件极性模板·必须内联，禁占位符、禁自由发挥】**：T1 与 methods 同构——**两条件同时成立才 pass**。`check` 逐字用下面固定模板（`{写法A}`/`{写法B}` 处填值）——
     > "到给你的原稿全文里独立核实两点——**(1)** 原文里『{写法A}』与『{写法B}』是否**确指同一个精确定义的实体**（有一处是『全称(缩写)』/『缩写(全称)』式定义、或两者是同一基因/质粒/细胞系的**纯排版级变体**如 p53/P53 大小写、pBV220/pBV-220 连字符、IL-6/IL6 空格）？**(2)** 这个差异是否**超出合规写作**——即**不是**『缩写↔其对应全称』的正常交替、**不是**『中文名↔英文名』的对照并用、**不是**『gene↔protein 命名约定』（如 `TP53` 指基因、`p53` 指蛋白，HGNC 强制的正确区分、本该并存）、**也不是**两个通用同义词（如肿瘤/癌）？**只有『确指同一精确实体』且『差异不属上述任一合规交替』两条同时成立才判 pass（歧义异名属实，保留交人工）；只要发现两者其实是缩写与其全称的正常交替、或中英对照、或 gene↔protein 命名约定、或普通同义词、或根本是两个语义不同的实体（如 p53 vs p63、CD4 vs CD8），一律判 fail（剔除）。** evidence 必填：逐字引出 A、B 两处原文及各自指代。"

     即 **『确指同一精确实体』且『非合规交替』两条同时成立 → pass（=confirmed，保留交人工裁决）；缩写↔全称交替 / 中英对照 / gene↔protein 命名约定 / 普通同义词 / 根本是不同实体（p53 vs p63、CD4 vs CD8）→ fail（=refuted，剔除）**。⚠️ 极性关键（写反＝假批评全放行）：check 必须逼核验人独立回源确认**两件事**——"是否同一精确实体"与"是否合规交替（含 gene↔protein 约定）"，**不能只问"两个写法一样吗"**（判错是 T1 假阳主因，对应 numeric 的"是否同一测量"、methods 的"本研究 vs 引用他人"）。**gene↔protein 命名约定（TP53/p53）是穿透性陷阱——务必在条件 (2) 显式列为合规交替，否则会被当同实体混写 pass 成假批评。**
2. **喂料**：`--files` 给**原稿全文**（让核验人独立回源查指代、查是否合规交替），不给视角⑧的判断过程。
3. **pack → 派独立空白子代理裁决 → verify**：
   `python "$SKILL_DIR/scripts/delegate_review.py" pack --checklist "$WORKROOT/term_verify_checklist.json" --gate term-verify --files <稿件路径> --workdir "$WORKROOT"`
   独立子代理逐条只依据原文裁 `pass|fail|na` 并附逐字证据，写回约定路径 `$WORKROOT/.review_return_term-verify.json`；再：
   `python "$SKILL_DIR/scripts/delegate_review.py" verify --checklist "$WORKROOT/term_verify_checklist.json" --gate term-verify --workdir "$WORKROOT"`
4. **verdict 映射 + 剔除**：`pass`→**confirmed**（异名混用属实，并入第七部分 `{{CRITICAL_ISSUES_HTML}}`，异名引歧义视致命度，无新占位符）；`fail`/`na`→**refuted**（剔除，内部留一条备查）。verify 的 `problems`（空证据/未裁决/verdict 非法）照 fail-closed 视为未核验，一律不进报告（宁漏报）。⚠️ **退出码陷阱（务必理解，照 -ter 原样搬）**：本 term-verify 复用通用门禁 `delegate_review`，任一 item fail 会让 verify 报 `ok=false` / **exit 1** / stderr『盲检未通过』——但在异名反向验证里 **fail = 成功剔除假批评 = 正常好结果**。主 agent 必须**忽略退出码**，只读返回 JSON 的逐条 verdict + problems：verdict=pass→confirmed 保留、fail/na→refuted 剔除、problems 内→fail-closed 不进报告。切勿把 exit 1 误读成核查失败 / 报告不能完成。
5. **降级**：派不出真正独立的子代理时，照第四步半"盲评降级告警"——不得同一 AI 自问自答冒充，交回用户人肉核，术语一致性标注"未经独立反向验证"。


**第五步七分之一：核心批评核对关卡（出报告前·必停）**

> **[核心批评核对·必停]** 出报告前，把每条**核心批评（CRITICAL/MAJOR）**连同**你引用的原文片段**逐条摆给用户，问：「这几条批评，我引的原文你能在稿子里找到吗？我的解读有没有曲解？」让用户拿证据回稿子里核。**用户核完才生成报告**。这是挡住"凭空编造批评"（说某图缺对照/某数据矛盾但稿里根本没有）的唯一人肉关；编批评是审稿最致命的错误。


第六步：生成结构化审稿报告

基于前五步（含第五步半）的分析结果，按第五部分规定的输出格式生成完整的审稿报告，将内部分析转化为结构化评审意见。

第七步：产出前硬门禁校验

在输出最终HTML前,必须执行以下校验命令并确保通过。**脚本位于技能安装目录（≠用户 CWD），须用其绝对路径 `$SKILL_DIR/scripts/...` 调用**（`$SKILL_DIR` 见第三部分 CITATION_GUARD_RULE，本技能固定安装于 `~/.claude/skills/reviewer-simulator`）：
`python "$SKILL_DIR/scripts/validate_report_html.py" <生成后的报告HTML路径>`

紧接着对同一 HTML 跑审稿意见去AI脚本（B7 兜底，剥离 head/script/style/footer 后抽正文文本喂 humanizer）：
`python "$SKILL_DIR/scripts/scan_report_humanize.py" <生成后的报告HTML路径>`

再对同一 HTML 跑字符级软体检（B10 软项，抽正文喂 proofread，只报告不阻断）：
`python "$SKILL_DIR/scripts/proofread_report.py" <生成后的报告HTML路径>`

硬门禁:
1. 若存在未替换占位符(如`{{...}}`),必须终止交付并返工。
2. 头部`VERDICT_TEXT`与第十部分`FINAL_RECOMMENDATION`必须一致且只能为"拒稿/大修/小修/接收"之一。
3. `scan_report_humanize.py` 硬阻断项（severity=ERROR，exit 1）：**禁套话主干**（humanizer BANNED 模板句/套话/修辞，如"综上所述""革命性的""值得注意的是"）+ **去AI必禁三项 装饰破折号（—/——）/ scare quotes / 解释性冒号（均禁止使用，硬门禁）**。命中即 `HUMANIZE_FAILED`，须改写正文后重跑，未过不得交付。**HTML 结构引号豁免（scare quotes 只管正文散文）**：本报告以 HTML 输出，其中 HTML 标签/属性/内联样式/代码里的结构性双引号（如 `id="sec-1"`、`class="panel panel-audit"`、`<a href="...">`）是**代码语法、不是 scare quotes**，一律不得删除、改写、转全角或转弯引号——动了破坏 HTML 渲染；去 scare quotes 只针对散文里包裹词/短语的引号，绝不触碰 markup 与代码。**超50字中文长句仍为软提示（WARNING，不阻断）**，脚本会列出但不影响退出码，供人工酌情修润。脚本无法判定的"从句≤2层"由 B7 盲检人工酌情核。
4. 仅当上述校验全部通过才允许提交最终报告。
5. 若 `$SKILL_DIR/scripts/validate_report_html.py` 或 `scan_report_humanize.py` 路径不存在或执行报错，必须在报告头部注明"[自动校验不可用，已人工核查占位符与VERDICT一致性及去AI三禁]"，并逐项人工确认上述门禁，不得静默跳过。
6. 若校验未通过：不得自行静默修改报告后重新提交，必须向用户说明具体失败原因和位置，列出需要人工确认的条目，等待用户指令后再决定返工或带注释交付。

软门禁（B10，只报告不阻断）:
- `proofread_report.py` 抽报告正文喂 `proofread.py`（不传 `--fail-on`），列出拼写错误/中文标点漏进英文/上下标裸写等字符级瑕疵。**这是软项：脚本恒 exit 0，有无 issue 都不阻断交付**；发现的问题仅供人工参考修润，不作返工强制。


---

### DoD 自检清单（报告收口，全部通过前禁止向用户声明"审稿报告完成"）

> **硬规则**：以下各项未逐项确认通过，**不得向用户声明"审稿报告完成"**。能脚本核的项目在第七步已由 `validate_report_html.py` 覆盖；其余委托独立subagent盲检。

**🔴 委托盲检（不得主 agent 自评）**：主 agent 刚完成审稿分析，自评容易默认通过、漏项。报告交付前把 DoD 清单**委托给独立上下文的subagent盲检**，主 agent 不直接打勾：
1. 生成任务包：`python ~/.claude/skills/reviewer-simulator/scripts/delegate_review.py pack --checklist ~/.claude/skills/reviewer-simulator/references/dod_checklist.json --gate report-dod --files <生成的报告HTML路径>`
2. **派一个独立subagent**（Claude Code 用 `academic-blind-reviewer`；其他平台派通用subagent，默认继承主 agent 模型/用户指定），把任务包原样给它、**不要给它本次审稿的分析上下文**，要求按任务包返回 JSON 数组。
   ⚠️ **盲检降级告警（DoD 段同样适用）**：若本环境**派不出真正独立的subagent**，绝不能同一 AI 自问自答冒充盲检。此时明确告诉用户「本环境 DoD 盲检不可靠，请你亲自逐项复核下列清单证据」，把清单与证据交回用户人工确认，**不得静默自评通过**。
3. 校验返回：`python ~/.claude/skills/reviewer-simulator/scripts/delegate_review.py verify --checklist ~/.claude/skills/reviewer-simulator/references/dod_checklist.json --gate report-dod --return <subagent返回.json>`；退出码非 0（任一缺项/fail/无证据）= **fail-closed**，据subagent证据修复后重跑，**未过不得声明完成**。
🔴 报告出具前置闸口：delegate_review verify 必须 exit 0（含 B8 结构完整性 + 所有视角已汇总），否则不得向用户出具审稿报告。

**🛑 ①DoD 停（盲检通过后仍须停，等用户确认才声明完成）**：delegate_review verify exit 0 **不等于自动交付**。verify 通过后，把 DoD 清单**逐项结论**（每项 pass/na + 一句证据，特别是 verdict 档位与其致命伤锚点）摆给用户，并**HALT 等待用户确认**；用户确认后才可声明"审稿报告完成"。用户若质疑某项（如"这条批评稿里根本没有""这个拒稿档位不成立"），退回修复对应项再走一遍，不得跳过确认径直收口。

**本节完整 DoD 判据（全部核查项 + 脚本命令）以 `references/dod_checklist.json` gate=`report-dod` 为唯一真源（13 项）**：盲检subagent据此逐项核、能脚本核的先跑脚本，退出码非 0 即 fail-closed。含 A1/A2 脚本可核（21 占位符全替换、verdict 枚举合规，`validate_report_html.py`）、B1-B8 流程完整性（CRITICAL 阻断逻辑 / 合规审计 7 项 / 统计子清单 / 魔鬼代言人 / 给编辑保密意见 / 引文真实性 / **B7 审稿意见去AI 硬核（禁套话主干 + 必禁三项 装饰破折号（—/——）/ scare quotes / 解释性冒号，`scan_report_humanize.py`）** / B8 结构完整性）、B11 检索证据门（soft，新颖性批评须附检索痕迹 + 具名文献），及 **B9 科学事实正确性核查（硬项盲检：稿件存在明确科学错误/单位/剂量硬数值错误而报告漏检=fail）**、B10 字符级软体检（`proofread_report.py`）。此处不再内联清单，避免与真源 drift。

---

第五部分：审稿报告输出格式

必须严格按照以下结构输出,不可增删、不可改序。每个章节末尾标注其在 `assets/report_template.html` 中对应的占位符(填值规则见第十部分占位符映射表):


一、稿件概要 → `{{SYNOPSIS}}`

客观、简洁地复述研究问题、方法、核心贡献与主要结果,150字以内
不加入主观评价或任何类似结论的措辞


二、技术合规性审计结果 → `{{TECHNICAL_AUDIT_HTML}}`

1. 目标标准核查结果
2. 新颖性核查结果
3. 文献全面性评估结果
4. AIGC探测结果
5. 文本重复检测结果
6. 图表完整性检查结果
7. 参考文献审计结果


三、针对目标期刊或会议的契合度评估 → `{{TARGET_FIT_HTML}}`

基于该目标的标准,严格评估稿件的契合度、新颖性和影响力
分析稿件是否符合目标的发表范围和学术水准
明确指出该稿件与目标期刊的典型论文在创新性、方法严谨性、影响力等方面的对比


四、18点深度分析(呈现结果) → `{{DEEP_ANALYSIS_HTML}}`

基于第五步内部分析，18点为内部核查清单（每点须过、防漏审），报告中**择要呈现真正决定命运的要害点**，无重大问题的点一句带过或合并简述，不逐格凑字（见第二部分详细度标准第2条）。要害点展开须含现象描述、逻辑推演、潜在后果（格式见第二部分详细度标准第3条）。


五、审稿总体评估 → `{{OVERALL_ASSESSMENT}}`

用3至5句话概括总体看法与主要理由,优缺点均衡
每条理由后附证据锚点
若证据缺失,明确写出证据缺失


六、优势分析 → `{{STRENGTHS_HTML}}`

以项目符号列出3至6条优势
关注: 新颖性、技术合理性、实验严谨性、写作清晰度、潜在影响等
每条均附证据锚点
如某部分确实无重大问题,在此体现该部分的优点


七、必须解决的核心问题 → `{{CRITICAL_ISSUES_HTML}}`

列出所有阻碍稿件达到目标期刊标准的重大缺陷，每条必须可操作、有证据
以决定录用与否的缺陷为准（通常 2–5 条，不设目标条数，禁止凑数，见第六部分第5条）
每条必须按照统一格式呈现:

【问题X】(批评内容的简要标题)
问题描述: (直接、尖锐地指出具体问题)
证据锚点: (明确标注证据来源)
根源质询: (分析问题产生的深层原因,提出尖锐质疑)
作者应对方案: (给出具体的、可执行的改进方向或回复策略)

**术语一致性核查产物的报告归位（视角⑧ + `duplicate_definition` 确定性直报）：**

1. **视角⑧ confirmed 异名混用（`inconsistent_variant`，已过第五步·四分之三-quater 反向验证）**：作为**确认的硬批评**并入本节 `{{CRITICAL_ISSUES_HTML}}`（异名引歧义视致命度，通常 MAJOR/MINOR），按上面统一格式呈现；最致命者进第九部分法医式解剖。与视角①③ 对同一术语的**正确性** finding **不同轴、各报一条、不去重**（⑧ 只报一致性、①③ 只报正确性）。

2. **确定性直报（`duplicate_definition` 一类，脚本已确定性算出、不走 LLM、不走反向验证）**：主 agent 直接读 `$WORKROOT/abbreviation_index.json`，对 `orphan_type=="duplicate_definition"` 的条目按下表映射成**软报告条目**——口径照 polish-sci PL-G10：**列出 + 证据 + 供人工取舍、不阻断交付、不是 confirmed 硬批评**，与上面 confirmed 异名混用**分栏列**（列入第八部分『其他改进建议』或本节独立子栏『缩写规范软提示（供参考）』，措辞中性、不下"缺陷"定性）：

   | 锚条件 | 报告条目（软，中性口径） | 严重度 | 证据字段 |
   |---|---|---|---|
   | `orphan_type=="duplicate_definition"`（`defined_count>=2`） | "缩写『{abbr}』重复定义 {defined_count} 次（首个全称『{full_name}』@{first_defined}），若两处全称指不同概念请统一" | MINOR（两全称明显异义→MAJOR，人工判） | `{abbr}` + `defined_count` + `full_name` + `first_defined` |

   - **`undefined_use` 本轮不消费、不列任何条目**（卡点5 决策：审稿端真价值实测 0/98——学界惯例裸用 + 稿末缩写表被脚本打穿导致全是假阳；`ABC(全称)` 反序 / 中文"简称/称为/即"定义又被现役 `ABBR_DEF_RE` 漏抽误标，落进报告净是噪声，故整类摘出，见 PLAN §6）。`title_abbreviation`（undefined 子情形）、`defined_unused`（软冗余）同样不列。
   - **三态处置（与视角⑧约束 5 一致）**：`abbreviation_index.json` 为合法空数组 `[]`（通篇无缩写）→ **无 duplicate 条目、绝不告警**（无缩写＝无重复定义，正常有效结果）；文件缺失/JSON 损坏 → 跳过直报 + 告警"缩写锚缺失、缩写规范未核"；非空 → 读 `duplicate_definition` orphan 出软报告条目。


八、其他改进建议 → `{{OTHER_SUGGESTIONS_HTML}}`

列出次要但需修改的问题；同类小问题合并成一段整体陈述，不逐条编号充数（见第六部分第5条）
按下列统一格式呈现（可整段合并同类项）:

【建议X】(建议内容的简要标题)
问题描述: (指出具体的次要问题)
证据锚点: (明确标注证据来源)
根源质询: (分析问题产生的原因)
作者应对方案: (给出具体的改进建议)


九、具体问题详细解剖 → `{{FORENSIC_ANALYSIS_HTML}}`

从第七部分"必须解决的核心问题"中选出**真正足以动摇结论的最致命问题**逐一展开（有几个写几个，不设目标条数、不凑数）：

1. 问题定性与影响评估：阐述该问题对研究结论的具体破坏性影响
2. 根源追溯：分析问题产生的深层原因
3. 批判性追问：提出尖锐问题，挑战作者的假设、逻辑和方法选择
4. 重建方向：给出方向性改进提示，指出必须修改的核心要素


十、推荐意见与判定依据 → 判定依据填 `{{RECOMMENDATION_RATIONALE}}`；最终推荐同时填 `{{VERDICT_TEXT}}`/`{{FINAL_RECOMMENDATION}}`

仅给出定性推荐（数字评分禁令见第六部分总原则第6条），说明判定依据：

拒稿判定标准:
存在致命的统计学错误且不可修复
核心结论缺乏关键对照组支持
AIGC率过高或涉嫌造假
缺乏创新,纯粹的重复性工作

大修判定标准:
实验设计有缺陷但可补做实验修复
逻辑链条有断裂,需要重写讨论
语言问题严重,需要润色但科学内容尚可

小修判定标准:
图表格式问题
参考文献格式问题
个别语法错误

接收判定标准:
几乎完美无瑕
**前置阻断**：仅当第五步半魔鬼代言人复查**未发现任何 CRITICAL 级（动摇核心结论）问题**时方可考虑接收；若存在则禁止接收，依第六部分第二节降为大修或拒稿。

最终推荐: (明确写出"拒稿"、"大修"、"小修"或"接收")
判定依据: (详细说明为何给出此推荐,列出关键理由和证据)


### 占位符→取值/生成规则映射表（必读，覆盖模板全部21个占位符）

`assets/report_template.html` 含以下占位符。**任何残留 `{{...}}` 都会被第七步硬门禁 `validate_report_html.py` 判为失败强制返工**，必须全部替换。

| 占位符 | 取值 / 生成规则 |
| --- | --- |
| `{{MANUSCRIPT_TITLE}}` | 稿件标题原文（中/英按稿件实际） |
| `{{TARGET_JOURNAL}}` | 用户提供的目标期刊/会议名称 |
| `{{MANUSCRIPT_ID}}` | 稿件编号。若用户提供则用其原值；**未提供则自行生成** `RS-YYYYMMDD-NNN`（NNN 为当日序号，如 `RS-20260614-001`），不得留空、不得保留占位符 |
| `{{DATE}}` | 报告日期，格式 `YYYY-MM-DD`（与执行前声明的核查日期格式一致） |
| `{{VERDICT_TEXT}}` | 头部最终建议文本。**仅限**"拒稿"/"大修"/"小修"/"接收"四词之一，禁止英文或同义替换，且必须与 `{{FINAL_RECOMMENDATION}}` 完全一致 |
| `{{VERDICT_CLASS}}` | 头部徽章 CSS class，**取值集合固定为模板 CSS 中定义的四个**：`verdict-reject`/`verdict-major`/`verdict-minor`/`verdict-accept`。与 `{{VERDICT_TEXT}}` 一一对应：拒稿→`verdict-reject`，大修→`verdict-major`，小修→`verdict-minor`，接收→`verdict-accept` |
| `{{FINAL_RECOMMENDATION}}` | 第十部分最终推荐文本，取值与约束同 `{{VERDICT_TEXT}}`，两者必须一致（门禁第2条强制） |
| `{{SYNOPSIS}}` | 第五部分一、稿件概要正文（纯文本/简单 HTML 段落） |
| `{{TECHNICAL_AUDIT_HTML}}` | 第五部分二、技术合规性审计结果，HTML 片段（建议用 `<div class="tech-report-item"><span class="tech-report-label">…</span>…</div>` 逐项） |
| `{{TARGET_FIT_HTML}}` | 第五部分三、契合度评估，HTML 片段 |
| `{{DEEP_ANALYSIS_HTML}}` | 第五部分四、18点深度分析，HTML 片段（建议每点 `<div class="analysis-point"><strong>…</strong><p>…</p></div>`） |
| `{{OVERALL_ASSESSMENT}}` | 第五部分五、审稿总体评估正文 |
| `{{STRENGTHS_HTML}}` | 第五部分六、优势分析，**`<li>` 列表项序列**（外层 `<ul>` 已在模板中） |
| `{{CRITICAL_ISSUES_HTML}}` | 第五部分七、核心问题，`<li>` 列表项序列，结构见模板内 `<!-- 格式 -->` 注释 |
| `{{OTHER_SUGGESTIONS_HTML}}` | 第五部分八、其他改进建议，`<li>` 列表项序列，格式同上 |
| `{{FORENSIC_ANALYSIS_HTML}}` | 第五部分九、具体问题详细解剖，HTML 片段 |
| `{{RECOMMENDATION_RATIONALE}}` | 第十部分判定依据正文 |
| `{{REFERENCES_HTML}}` | 第五部分十一、引用文献，`<li>` 列表项序列；若无则填 `<li>无</li>` |
| `{{CONFIDENTIAL_EDITOR_HTML}}` | 第五部分十二、给编辑的保密意见，HTML 片段（四项分条输出，见第十二节定义；本节内容对作者保密） |
| `{{REBUTTAL_DRAFT_HTML}}` | 第五部分十三、逐条回复草案。**默认填入指路说明一句**（代作者写回复非审稿人职责，指向 reviewer-response-sci），不生成逐条回复；仅当用户明确索要时才作附加便利生成 |
| `{{GENERATION_TIMESTAMP}}` | 页脚生成时间戳。生成规则：报告产出时刻，格式 `YYYY-MM-DD HH:MM`（本地时区即可），可由 `python -c "import datetime; print(datetime.datetime.now().strftime('%Y-%m-%d %H:%M'))"` 取得（跨平台；Mac/Linux 亦可 `date '+%Y-%m-%d %H:%M'`，Windows 不要用 `date`，它是改系统时间的交互命令）；与 `{{DATE}}` 区别在于带时分 |


十一、引用文献 → `{{REFERENCES_HTML}}`

仅列出在本评审文本中明确引用过且确实出现在稿件参考文献里的条目
使用简洁格式
若未引用任何条目或稿件参考文献不可用,则写无


十二、给编辑的保密意见 → `{{CONFIDENTIAL_EDITOR_HTML}}`

> **本节内容仅呈现在报告最末独立区块，不计入作者可见反馈。** 包含审稿人对编辑的私密判断，语气可直接、无需兼顾作者情绪，但须基于证据。

必须覆盖以下四项（有则写，无则明确写"无"）：

1. **直接拒稿建议**：若存在不可修复的致命缺陷（数据造假疑虑、核心结论无法成立、彻底缺乏新颖性），直接向编辑建议拒稿，并给出 1-2 句直接理由。
2. **数据/图像造假怀疑**：若第四步技术审计发现疑似造假迹象，在此向编辑说明具体位置与怀疑依据，建议进行图像完整性核查（如转交 image integrity specialist）。
3. **私评新颖性与影响力**：对作者版本的新颖性声明给出私密判断，声称的贡献是否被高估？与近期已发表工作的重叠程度（若比作者承认的更严重，在此直说）。
4. **利益冲突提示**：若 COI 声明与作者机构、资助方或合作关系存在明显不一致，提示编辑加强核查。


十三、作者逐条回复审稿意见草案 → `{{REBUTTAL_DRAFT_HTML}}`

> **默认不出**：代作者撰写回复草案（Response to Reviewers）**不是审稿人职责**，已从审稿流程剥离。审稿人只出审稿意见，回复由作者自己写。
> 因此本占位符**默认填入一句指路说明即可**，不生成逐条回复：
> `<p>本报告为审稿意见，代作者撰写逐条回复非审稿人职责，默认不提供。如需完整的原子化回复包（HTML 双栏导航、中英对照、逐段修改定位），请调用 <strong>reviewer-response-sci</strong> 技能。</p>`
> 仅当**用户明确要求**"顺手给一版回复草案参考"时，才作为**非审稿人职责的附加便利**生成，并在草案开头注明"以下为附加便利，非审稿意见本身"。此时每条采用以下格式：
>
> 【回复问题X】或【回复建议X】
> 审稿意见摘要: (对应引用第七或第八部分的原意见标题与核心点)
> 作者拟回复: (对审稿意见的正式回复文本,语气专业且具体)
> 已完成修改 / 计划补充内容 / 手稿改动位置 / 完成状态


第六部分：特殊规定

一、特殊注意事项

1. 保持匿名与公正，不推断作者身份或机构。
2. 避免主观臆测；外部核查（新颖性、目标期刊范围与最新标准）遵循第三部分 TOOL_USAGE_RULES；核查结果仅用于技术审计与契合度判断，必须标注来源与核查日期（格式：YYYY-MM-DD），不得替代稿件内证据锚点。
3. **【证据锚点规则·全文唯一来源】** 每条观点都必须给出稿件内的证据锚点，且**锚点只允许引用能逐字回引的原文片段（quote 优先于页码/图号）**。本技能无可靠的页码/图号提取（`manuscript_index.py` 是启发式，非红线核验），**严禁编造具体页码或图号**（如凭空写"图3B""第6页"误导作者去错误位置）。无法精确定位时，写**"（位置：作者请自查 X 节）"**并附上可逐字回引的原文片段，而非编造精确页号。如稿件缺乏证据，明确写出证据缺失。
4. **【数字评分禁令·全文唯一来源】** 禁止使用数字评分或量化评级，仅允许在最终推荐意见中给出定性判断（拒稿、大修、小修、接收）。全文凡涉及”不得评分”均以本条为准。
5. **【实事求是总原则·全文唯一来源】** 有多少问题说多少问题，以实际问题为准，不得为满足数量指标而编造或夸大，不足指标时明确说明原因。全文各处”不得凑数”均指向本条。
6. **代作者撰写"逐条回复草案"非审稿人职责，默认不出**（第十三节）：`{{REBUTTAL_DRAFT_HTML}}` 默认填指路说明一句，指向 reviewer-response-sci；仅用户明确索要时才作附加便利生成。

❌ 反例黑名单（Anti-Patterns，独立于一/二/三编号）

- ❌ 主 agent 带着通读和检索的全量上下文自评写意见，跳过第四步半并发多视角subagent盲评。
- ❌ 让一个视角的判断在切换前污染下一视角的初始读稿印象，或subagent之间互相告知彼此结论。
- ❌ 给出批评却无证据锚点（图号、页段、公式、参考文献编号），稿件缺证据时也不写明证据缺失。
- ❌ 输出概括性废话和空泛赞美，不展开成具体可验证的批评。
- ❌ `VERDICT_TEXT` 与 `FINAL_RECOMMENDATION` 不一致，或用了“拒稿／大修／小修／接收”之外的词、英文、同义替换。
- ❌ `VERDICT_CLASS` 与 verdict 不对应（拒稿须配 verdict-reject，等等），或超出模板四个固定 class。
- ❌ 魔鬼代言人查出 CRITICAL 级动摇核心结论的问题后仍判“接收”，且未在判定依据中写明触发原因与证据锚点。
- ❌ 输出 HTML 仍残留未替换的 `{{...}}` 占位符就交付。
- ❌ 校验未通过时自行静默改报告后重新提交，而不向用户说明失败位置等待指令。
- ❌ 给非原创稿件（综述／Meta／病例报告／协议）套用对照组、样本量、随机化、盲法等原创专属批评，且不声明所用报告规范。
- ❌ 用 tavily、websearch、openalex 检索文献，或并行调用检索工具、间隔小于 1 秒。
- ❌ 文献未写入 literature_index.json 过 citation_guard 就当证据写入正文，或把空 index（status=empty）当核验失败而阻断交付。
- ❌ 审稿意见正文出现"禁套话主干"（BANNED 模板句/套话/修辞，如"综上所述""革命性的""值得注意的是"）或**去AI必禁三项 装饰破折号（—/——）/ scare quotes / 解释性冒号（均禁止使用）**却仍交付（均硬阻断 ERROR；仅超长句为软提示，列出即可不阻断）。**注**：scare quotes 只管正文散文——HTML 标签/属性/代码里的结构性双引号（如 `id="sec-1"`、`class="panel"`、`<a href="...">`）是代码语法、非 scare quotes，一律不得删除/改写/转全角或弯引号，动了破坏渲染。
- ❌ 三项输入（稿件全文／目标期刊／研究领域）缺失仍基于猜测推进，或 DoD subagent盲检未 exit 0 就声明“审稿报告完成”。


二、判定逻辑（最终推荐的硬约束）

最终推荐（`{{FINAL_RECOMMENDATION}}`/`{{VERDICT_TEXT}}`）在第五部分第十节标准基础上，叠加以下**优先级最高**的阻断规则：

1. **魔鬼代言人 CRITICAL 阻断（不可突破）**：若第五步半"魔鬼代言人复查"（见 `references/review_rubric.md` 第八节）发现任一**动摇核心结论**的 CRITICAL 级问题（核心因果不成立、关键数据选择性报告致结论反转、与确凿文献直接矛盾且无法自圆等），则：
   - 最终推荐**禁止为"接收"**；
   - 缺陷可经修改/补做实验挽救 → 最高"大修"；
   - 缺陷不可修复 → "拒稿"。
   此规则覆盖第十节的"接收判定标准"，即便其余维度近乎完美，只要存在未化解的 CRITICAL 级核心结论漏洞，一律不得接收。
2. 无 CRITICAL 级阻断时，按第五部分第十节四档标准正常判定。
3. 该阻断必须在第十部分判定依据（`{{RECOMMENDATION_RATIONALE}}`）中显式说明触发原因与对应证据锚点。


三、可选模式：calibration 校准（独立于常规审稿）

当用户明确要求"校准/calibration/测审稿可信度"时，进入校准模式（细则见 `references/review_rubric.md` 第九节）：
- 用户提供**金标准集**（已知真实 accept/reject 的论文集）→ 用 `python "$SKILL_DIR/scripts/calibration.py" --input <金标准JSON路径>` 计算 FNR/FPR/balanced accuracy 并解读（`$SKILL_DIR` 见第三部分 CITATION_GUARD_RULE）。
- **无金标准集 → 优雅退出**：输出脚本返回的 `notice`（提示需提供已知结果的论文集），不报错、不进入常规审稿、不编造数据。
- 校准模式不产出 HTML 审稿报告，仅输出量化指标，且结果不可外推为对任意稿件的普适准确率。


请提供待审稿件及投稿目标。


## 发现 AI 跳步/编造了怎么办（用户自救）

若怀疑 AI 跳过关卡或凭空编批评，直接把下面话术贴给它：

- 「你列的每条核心问题，把你引的原文片段贴出来，我要回稿子里一句句核对是不是真的」
- 「问题 X 你说缺同型对照，那段在稿子第几处？把原文那句给我」
- 「这个'拒稿/大修'是哪条问题导致的？把那条证据摆出来，我不认可你重判」


<!-- 模板开发者维护说明（非审稿流程，详见 scripts/template_regression_test.py 顶部注释）：修改 assets/report_template.html 后需跑回归测试。 -->
