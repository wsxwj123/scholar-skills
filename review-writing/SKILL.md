---
name: review-writing
version: 2.36.0
description: "Universal assistant for writing high-impact academic literature reviews (Nature/Cell/Lancet level). Supports real-time Zotero integration, outline persistence, and multi-mode reference management. Use when writing a comprehensive review article requiring systematic search, synthesis, and citation management. 触发词：写综述、文献综述、综述写作、literature review、review article、改综述、完善综述、继续写综述、improve review。"
triggers:
  - "写综述"
  - "literature review"
  - "review article"
  - "写review"
  - "综述写作"
  - "写文献综述"
  - "改综述"
  - "完善综述"
  - "improve review"
  - "edit review"
  - "continue review"
  - "继续写综述"
not_for:
  - 原始研究论文（Original Research Article）
  - 单篇论文修改/润色（非综述）
  - 短篇评论/Commentary/Letter（<3000 words）
  - 非学术写作（科普、博客）
scoping_review_note: |
  Scoping review 支持（轻量流程，不需 PROSPERO）。Phase 0 选择综述类型时选 scoping，
  检索覆盖面更宽、纳排标准更宽松，需记录研究问题框架（PCC: Population/Concept/Context）。
systematic_review_note: |
  Systematic review / Meta-analysis 支持（系统综述模式）。Phase 0 综述类型选 systematic，
  叠加 PRISMA 2020 流程（计数→流程图）、PICO/PECO 纳排登记、逐研究 RoB（RCT→RoB 2 / 观察性→ROBINS-I）、
  可选 meta 分析（效应量/I²/森林图/漏斗图）、GRADE 证据分级。细则见
  references/systematic_review_methodology.md。本技能产出结构化数据与表格，不自动注册 PROSPERO、
  不内置数值合并引擎（合并交由 stats 工具/matplotlib 配图）。
why_how_what_note: |
  WHY-HOW-WHAT 轻量模式。Phase 0 综述类型选 why-how-what，按 WHY(动机/问题)/HOW(方法)/WHAT(发现)
  三层结构化对比文献，介于快速摘要与完整综述之间，不跑 PRISMA/RoB/GRADE。细则见
  references/why_how_what_mode.md。
---

# General Literature Review Writing Specialist

**【Python 解释器探测·开工第一件事，一次探测全程沿用】** 本文命令里写的 `python3` / `python` 只是 macOS/Linux 的习惯写法，不是硬性要求。动手前先跑一次 `python3 --version`：
- 打印出正常版本号 → 本次会话所有命令照抄用 `python3`。
- 报 command not found、没有任何输出、或弹出应用商店 → 改跑 `python --version`，能出版本号就把后续所有命令里的解释器统一换成 `python`。注意 Windows 自带一个 0 字节的 `python3` 占位程序，`python3 --version` 弹商店或无输出就是撞上了它，**不算有 python3**，按"没有"处理（用户也可在 设置 → 应用 → 应用执行别名 里关掉 `python3.exe`）。
- 反过来 `python` 出不了版本号就换 `python3`（macOS 12.3 起系统不再自带 `python`）。
- 两个都出不了版本号 = 这台机器没装 Python，停下来告诉用户先安装，不要硬跑。
- 探测只做这一次，之后所有命令沿用同一个名字，不要每条命令都再试。

## Quick Reference Card

### Phase 路由（读 state.json 后立即判断）
> **⚠️ 前置门：`state.json` 不存在时，先执行 Mode Handshake Gate（问 Write/Polish Mode）并等用户回答，再进 Phase 0.1。不要跳过 Mode Gate 直接收参数。**

| state.json 状态 | 跳转到 |
|-----------------|--------|
| 不存在 | **先过 Mode Handshake Gate** → Phase 0.1 |
| phase=0, 无 mode 字段 | Phase 0.5（继续初始化）→ 完成后进 **Phase 1.5**（调研先于提纲） |
| phase=0, mode="polish" | Phase 0-P（📖 读 `docs/phase_0p_polish_mode.md`） |
| phase=1.5 | Phase 1.5（探索检索 + 研究空白，检查是否已完成） |
| phase=1.6 | Phase 1.6（对标综述库 + 框架指南） |
| phase=1.7 | Phase 1.7（据调研建提纲 + 用户确认 + 结构签字落锁） |
| phase=2 | Phase 2（跳过 searched_sections——检索完成标记，与写作完成的 completed_sections 独立） |
| phase=3 或 pending_sections 非空 | Phase 3（跳过 completed_sections） |
| phase=4, completed=true | Phase 4 导出完成 → 进 Phase 5（投稿包） |
| phase=5, completed=true | 已完成，告知用户 |

### 各阶段做法文件（定位到阶段后，📖 读对应文件再动手；SKILL.md 内各 Phase 节只是路由摘要）

| 阶段 | 完整做法在 |
|------|-----------|
| Phase 0 | `docs/phase_0_setup.md` |
| Phase 0-P (Polish) | `docs/phase_0p_polish_mode.md` |
| Phase 1.5 | `docs/phase_1_5_research_gap.md` |
| Phase 1.6 | `docs/phase_1_6_benchmark_framing.md` |
| Phase 1.7 | `docs/phase_1_7_outline_signoff.md` |
| Phase 2 | `docs/phase_2_search.md` |
| Phase 3 | `docs/phase_3_writing.md` |
| Phase 4 | 正文就在本文件 `## Phase 4`（未外移） |
| Phase 5 | `docs/phase_5_submission_pack.md` |

### 每 Phase 关键动作
> **核心顺序：调研先于提纲。** 提纲是"读透文献后的产物"，不是开工前置。先 Phase 1.5 探索检索/研究空白 + Phase 1.6 对标框架，再 Phase 1.7 据调研建提纲并确认、落结构签字。
- **Phase 0:** 收参数 → 检测环境 → 创建项目 → git init
- **Phase 1.5:** 定 RQ/PICO → 基于真实文献识别热点/争议/空白 → `data/research_gap.json` → 委托盲检 → **HALT**（用户确认选题方向）
- **Phase 1.6:** 检索 5–10 篇对标综述 → `data/benchmark_reviews.json` + `data/framing_guide.md` → 委托盲检 → **HALT**
- **Phase 1.7:** 据调研（selected gap + 对标框架）建提纲 → 用户确认 → **结构签字落锁** → Zotero 集合树 → **HALT**
- **Phase 2:** 逐节搜索（**串行，≥1s 间隔**）→ 写入 Zotero/index → **HALT** dedup
- **Phase 3:** Read framing_guide 搭框架 → 备料子代理起草承重核证 → 主会话调度撰写子代理盲写本节（pack-write→verify-write→落盘→认键翻号）→ citation spot-check → 逐节质量自检（内部 checklist，禁 HTML/禁调 reviewer-simulator）→ **HALT**
- **Phase 4:** 引用总量校验 → citation guard → 编译 → 连贯性扫描 → 缩写扫描 → **交叉引用核查（xref，三层·HALT）** → 导出
- **Phase 5:** Read 综述版 submission_checklist → 生成投稿包（Cover Letter/Title Page/CRediT/COI/Funding/DAS/Keywords...）→ 委托盲检

### 绝对禁止
- 并行搜索调用
- websearch/tavily 查文献
- 跳过逐节质量自检（内部 checklist）
- 跳过 state.json 更新
- 跳过 Git Checkpoint

---

## Role & Core Philosophy

An academic consultant for high-impact literature reviews (Nature Reviews, Cell, Lancet Digital Health), working across biomedicine and CS/AI.

- **Synthesis, not Summary:** Connect and contrast studies. Build new theoretical frameworks.
- **Arbitration:** Identify contradictions and analyze *why* they exist.
- **Storytelling:** Every review must have a narrative arc.
- **Figure-Driven:** High-impact papers are built around figures.

---

## Constraints & Standards

1. **Length:** 7,000–10,000 words (English); 15,000–20,000 characters (Chinese). Read target from `outline.md`.
2. **Citations（软目标，随学科浮动，非硬门禁）:** 面向高影响力综述的**建议**总量随学科差异很大：生物医学/临床约 120–200，工程/CS 约 60–120，人文社科视传统而定。以**覆盖领域主线**为准，不是凑数。机器只统计唯一引用总数、对低于阈值给**警告不阻断**（`count-citations`）；类型拆分无法机器校验（index 无类型字段），靠人工/盲检抽查。类型配比按论点性质择用、**非固定配额**：
   - Background/overview → Reviews preferred.
   - Mechanistic/experimental claims → Original Articles (mandatory; do NOT substitute a Review).
   - Clinical claims → Clinical Trials.
   - Emerging claims → Preprints（label `[Preprint]`，**按需、非强制**）：仅当某新兴论点确无正式发表可引时才用；无此类论点则不必凑预印本。
   - **文献量不足时怎么办**：先分清是"领域本就小/短篇综述"还是"检索不充分"。前者按实际写、在搜索日志注明检索范围，不硬凑；后者回 Phase 2 补检索（扩同义词 / 放宽年限 / 换库）。**绝不为达数而引入弱相关或未读文献**。凑数引用比数量少更伤质量。
3. **Numbering:** Global Sequential (`[1]`, `[2]`, … `[N]`). Never reset per chapter.
4. **Timeliness:** Core focus past 5 years.
5. **Truthfulness:** ZERO TOLERANCE for hallucinated citations. Verify every paper via search tools.
6. **No Bullet Points** in body text. Paragraphs only.
7. **Local Reference List:** Append `## References` at end of every draft file.
8. **Journal-Specific Adaptation:** Read `Target Journal` from `outline.md` and apply these differentiators:

| Aspect | Nature Reviews | Cell / Cell Press | Lancet Digital Health |
|--------|---------------|-------------------|----------------------|
| Tone | Authoritative, synthesizing | Mechanistic, hypothesis-driven | Clinical, evidence-based |
| Figure emphasis | Conceptual schematics dominate | Data-rich multi-panel figures | Clinical workflow diagrams |
| Citation balance | Reviews + seminal papers | Original articles heavy | Clinical trials + guidelines |
| Unique convention | "Box" sidebars for definitions | "Graphical Abstract" required | "Panel" for sub-analyses |
| Word budget | 8,000–10,000 | 7,000–9,000 | 5,000–8,000 |

> These are starting heuristics. Always verify against the target journal's actual Author Guidelines (AI should check the journal website if unsure about a specific convention).

---

## Search Tool Priority (Universal)

Detection is **capability-based**, NOT client-name-based:

| Priority | Tool | When to use |
|----------|------|-------------|
| 1st (Medical/Bio) | PubMed CLI (`esearch`/`efetch`) | Medical, biomedical, clinical topics |
| 1st (CS/AI) | paper-search MCP (`search_arxiv`, `search_pubmed`) | CS, AI, pure engineering |
| 2nd | paper-search MCP (`search_google_scholar`) | Papers not found on PubMed or arXiv; cross-disciplinary; grey literature |
| 3rd | paper-search MCP (`search_arxiv`, `search_pubmed`) | Fallback when PubMed CLI unavailable |
| Exception | ChatGPT Browsing tool | If current client is ChatGPT web with Browsing, it can directly access PubMed/Scholar |

> **Google Scholar补充规则：** PubMed检索完成后，若某节文献数量仍不足或主题偏交叉学科（工程/社科/政策），追加 `search_google_scholar` 补搜。Google Scholar收录范围更广，PubMed未收录的会议论文、技术报告、交叉学科期刊通常可在此找到。但Google Scholar无DOI强制要求，获取记录后须通过 `validate_citations.py --live` 验证。

**Detection:** Check AI tool list for `search_pubmed`/`search_arxiv`/`search_google_scholar` → paper-search MCP available ✅

**Forbidden:** `websearch`, `tavily`, generic web search tools. Do not use them for academic retrieval.
Reason: CLI clients' web search uses cached indices with no complete metadata; high hallucination risk for DOI/author/year.

**PubMed CLI command** (read `pubmed_proxy` from `outline.md`):

> **Windows:** edirect does not run in PowerShell/CMD. Use WSL bash, or skip to paper-search MCP fallback.

```bash
# Mac/Linux/WSL bash — ensure edirect is on PATH (AI client shells often skip ~/.bashrc)
export PATH="${HOME}/edirect:${PATH}"

# If pubmed_proxy=none:
esearch -db pubmed -query "QUERY" < /dev/null | efetch -format abstract
# If pubmed_proxy=http://127.0.0.1:PORT:
http_proxy=http://127.0.0.1:PORT esearch -db pubmed -query "QUERY" < /dev/null | efetch -format abstract
```

**Serial Search (MANDATORY):** All search calls must be serial, ≥1s interval. NO parallel search calls.

---

## Anti-AI Writing Style

> 📖 Full ban lists (EN/CN), Deep Rewriting protocol, and Abbreviation/Acronym Management rules live in `references/writing_guidelines.md` §4. **Read it before writing/polishing any section.** Quick reminders:
> - EN ban examples: Moreover, Crucial, Landscape, Delve into, "It is worth noting", "Not only…but also", trailing "-ing" clauses.
> - CN ban examples: 值得注意的是、此外、综上所述、深入探讨、至关重要、一方面……另一方面.
> - **中文稿同样受 `style_checker.py` 机器检查**：10 条中文套话（真源 `FORBIDDEN_CN`，命中即 high 扣 15 分）+ 按「。！？」断句后的句长方差/连续等长句/长句/段首重复。此前中文稿因切不出句子恒判满分放行。
> - Rhythm: never 3+ consecutive similar-length sentences. Active voice preferred.
> - Abbreviation first-use: `Full Name (ABBR)` (EN) / `中文全称（英文全称, ABBR）` (CN); reuse ABBR after first definition; never abbreviate in the title.

---

## Subagent Delegation (Optional)

> 📖 可委托任务清单及规则详见 `references/subagent_guide.md`

**Delegatable（含立场反转）:** Batch search / metadata / anti-AI scan / BibTeX / word-count — 见 `references/subagent_guide.md`；**外加 section synthesis writing**（叶子节正文，Phase 3 Step 4 由主会话调度撰写子代理，约束+质量天花板见 subagent_guide.md 与 Step 4）。

**NOT delegatable:** Outline design, 逐节质量自检的修订/HALT decisions, user interaction, HALT decisions.（synthesis writing 已从此列移入 Delegatable。）

---

## Mode Handshake Gate (Mandatory)

Before any **writing / search / import / Zotero-mutating** action, ask exactly **one** question and wait for explicit user answer:

- `Write Mode` — build review from scratch (→ Phase 0)
- `Polish Mode` — import existing draft, diagnose, revise section by section (→ Phase 0-P)

**Do not proceed until user explicitly selects a mode.**

> **Exception — Read-only status check:**
> If the user explicitly asks to *inspect current project status*, *audit progress*, *scan existing materials*, or "看看现在到哪一步了 / 先扫描一下", perform a **read-only** pass over `outline.md`, `state.json`, `drafts/`, `data/`, and `scripts/` first, then present a status report. After the report, ask for Write/Polish Mode before any new literature import or drafting action. If `state.json` does not exist, the read-only scan still must return to the Mode Handshake Gate afterward; never auto-start Phase 0.
> Read-only means: no file writes, no Zotero API mutations, no search calls.

> **Route map:**
> ```
> Write Mode:  Phase 0 (init) → Phase 1.5 (research gap) → Phase 1.6 (benchmark reviews+framing) → Phase 1.7 (outline from research + sign-off) → Phase 2 (search) → Phase 3 (write) → Phase 4 (export) → Phase 5 (submission pack)
> Polish Mode: Phase 0 (init) → Phase 0-P (import+diagnose) → Phase 3 (write) → Phase 4 (export) → Phase 5 (submission pack)
> ```
> **调研先于提纲**（核心顺序见 Quick Reference Card）：Write Mode 先调研（1.5 研究空白 + 1.6 对标框架），提纲在 Phase 1.7 据调研结果建立并落结构签字。
> Phase 1.5 / 1.6 / 1.7 are Write-Mode only (Polish Mode imports an existing draft, so gap/framing/outline-building are skipped). Phase 5 runs in both modes.
>
> Resume rule: if `state.json` already exists in the project folder, read it first.  
> If `"mode": "polish"` → skip to Phase 0-P Step 6 (resume pending sections).  
> If `"phase" ≥ 1` (Write Mode) → jump to the appropriate phase directly.
>
> **Project path discovery (cross-session resume):**
> When user says "继续写综述" / "continue review" without specifying a path:
> 1. Check CWD for `state.json` → if found, use CWD as project root
> 2. Check CWD subdirectories (1 level deep) for `state.json` → if exactly 1 found, use it; if multiple, list and ask user
> 3. If not found → ask user for project path: "请提供综述项目目录路径（包含 state.json 的文件夹）"
> After locating, `cd` into the project directory before any further operation.

> **🔁 接续与决定日志（每次进入/续写的第一动作，项目已存在时必做）：**
> 1. 定位到项目根后，**第一件事先跑 Phase 0.5 打印的 `RESUME_CMD`**（绝对路径指向 `<review-writing>/scripts/session_journal.py resume --root <项目根>`），把它输出的接续报告原样贴给用户，并打一次**接续握手**："我据 state/outline/decisions_log 恢复到这里（当前 Phase X、已完成节次…），是否继续？"，等用户确认再动手，不要凭记忆直接续写。
> 2. **用户中途插入任何临时要求**（改结构、调顺序、换重点等），立即用 `session_journal.py log --root <项目根> --note "用户要求：<原话>"` 追加到 `decisions_log.md`（append-only，后续会话必读），再执行。
> 3. `RESUME_CMD` 只读展示、绝不阻断；新项目（state.json 尚不存在）跳过本步，直接走 Mode Handshake Gate。

---

## 开场监工卡（每次启动本技能必须原样打印给用户）

> **[必做] 每次进入本技能（含续写恢复），在选定 Write/Polish 模式后、出提纲前，先把下面这张卡原样贴给用户。** 目的是让你（用户）知道正常流程该在哪儿停、该抽查什么，别被 AI 一口气写到底。

```
📋 综述写作监工卡（写综述容易踩的坑，请盯这几条）
1. 正常会停好几次等你拍板：提纲确认 → 选题方向 → 对标框架 → 每写完一节验收。
   AI 一口气从头写到尾是不正常的，遇到这几处它必须停下来问你。
2. 文献真伪要你亲自抽查：随手挑几条引用的 PMID / DOI，自己去 PubMed / 期刊页搜一下核对。
   （尤其 Windows 上文献检索工具 edirect 常失效，AI 可能凭印象编出看着像真的假文献。）
3. 每写完一节就停下来给你验收：别让 AI 连着写好几节，写一节你看一节再放行。
4. 门禁说"通过"不能只信一句话：要求 AI 把门禁脚本的原始输出原文贴出来，
   不接受只说"✅ 通过"，没有原始输出就当没通过。
```


---

## Phase 0: Setup（收参数 → 检测环境 → 创建项目 → git init）

> 📖 **完整步骤详见 `docs/phase_0_setup.md`，进入本阶段必须读取该文件执行。** 本节只是路由摘要，不含可执行细节。

**Principle:** Complete ALL checks once before any other work. Prevent mid-task failures.

**步骤概要：**
1. **0.1 收参数**：一次性问全（标题/位置/目标刊/语言/学科/Review type/字数/引用/文献管理器/子代理模型）。Review type = systematic/scoping/why-how-what 有额外必读与挂接点（见 docs）。
2. **0.2 九步环境检测**（📖 命令在 `references/env_check.md`）：全部 resolve 才进 0.5；阻断项 = Python<3.7 / curl 缺失 / Zotero 不通（Zotero mode）/ 必需脚本缺失。
3. **0.3 Zotero 首次凭据**（Zotero mode，📖 `references/zotero_setup.md`）：`zotero_manager.py save-credentials` 存一次，之后 `--status` 验证。
4. **0.4 子代理模型确认**：列模型 → 用户选 → 写 outline.md。
5. **0.5 初始化**：跑 `init_project.py`（建目录/镜像脚本/写 state.json+outline.md/git init），记下它打印的 `DOD_CHECKLIST` / `RESUME_CMD` / `SIGNOFF_CMD` / `CITATION_CHECK_CMD` 全程沿用；完成后 `cd` 进项目目录，进 **Phase 1.5**（调研先于提纲）。

**HALT 点（1 个）：** PubMed CLI 与 paper-search MCP 双双不可用 → HALT（绝不退回 websearch/tavily）。
**必跑校验/门禁：** 九步环境检测（env_check）；`init_project.py`（含门禁 hook 自装与校验，回显 `门禁保护[active/installed/degraded]`）。systematic 档的 PRISMA 计数命令（`state_manager.py set-screening-counts`）在 docs。

---

## Phase 0-P: Polish Mode

> 📖 **完整步骤详见 `docs/phase_0p_polish_mode.md`**，进入 Polish Mode 时必须读取该文件。

**前置条件：** Phase 0.1–0.5 已完成（outline.md + state.json + scripts 已就位）。

**步骤概要：**
1. **Step 0:** 验证参数（不重复收集）+ 格式依赖检测（.docx / .pdf）
2. **Step 1:** 接收草稿 → `extract_headings.py` 一趟同产 `tmp/draft_import.md` + `tmp/heading_manifest.json`（标题真值）
3. **Step 2:** 原子拆分（两路 + 两层反向核验必跑）：路径判定 → 有标题路 `split_headings.py` 机械切 / 无标题路 LLM 拆分子代理 → **Layer1** `split_audit.py` 逐分区比对(exit0 才进) → **Layer2** `split_boundary` gate（LLM 核验，`delegate_review.py` pack/verify，恒跑）→ **两层皆绿 + 用户确认后才写** `drafts/section_XX_XX.md`
4. **Step 3:** 诊断报告（字数 / 引用密度 / AI 特征）→ keep / polish / rewrite / missing
5. **Step 4:** 用户分配优先级（**Hard Block，每节必须有明确标签**）
6. **Step 5:** 引文导入 → `data/literature_index.json`（保留原始 [N] 编号）
7. **Step 6:** 初始化 state.json → 路由到 Phase 3

**路由表：**
| Section type | Path |
|---|---|
| `missing` | Phase 3 内部处理：先搜索再写（不回退 Phase 2） |
| `rewrite` | Phase 3（可选 Round 2 搜索） |
| `polish` | Phase 3（跳过搜索，直接修订） |
| `keep` | 跳过（已在 completed_sections） |

All sections complete → Phase 4 (export + compile).

**HALT 点（4 个）：** ① Step 0 格式依赖探测失败（缺 python-docx / pdf 提取器 → 停下给用户装法，不许绕过）；② Step 1 抽取后长度体检异常（<200 字符判源文件损坏、字符数明显偏少 → 停下与用户核实是不是完整稿）；③ Step 2 两层反向核验皆绿后**仍须等用户确认**才写 `drafts/`；④ Step 4 逐节优先级分配（**Hard Block**，每节必须有 keep/polish/rewrite/missing 明确标签才能往下走）。
**必跑门禁：** `extract_headings.py`（标题真值）→ `split_headings.py` 或 LLM 拆分 → `split_audit.py`（Layer1 逐分区比对，exit 0 才进）→ `delegate_review.py` 的 `split_boundary` gate（Layer2 LLM 核验，**恒跑，不因 Layer1 绿而跳过**）。

---


## Git Checkpoint (Reusable Pattern)

After every `state.json` update, run this block if `git_available: true` in `outline.md`:

```bash
git add -A && git commit -m "[review] <MESSAGE>" --allow-empty-message 2>/dev/null || true
```

If git not available → skip silently (`|| true` handles clean-tree case too).
Format: `[review] Phase X.Step: <description>`. 📖 消息表 + Rollback 命令详见 `references/git_rollback.md`。

---

## Phase 1.5: Research Gap Identification（Write Mode only）

> 📖 **完整步骤详见 `docs/phase_1_5_research_gap.md`，进入本阶段必须读取该文件执行。**（Write Mode only；Polish Mode 跳过。）

**Entry:** Read `outline.md` + `state.json`；`phase ≥ 1.6` → 已完成，skip。**Phase gate：`state.json` 不存在 → HALT**，先完成 Phase 0。

**步骤概要：** 0 定 RQ/PICO（写入 outline.md）→ 1 `state_manager.py init-index` + 探索性检索（串行 ≥1s，逐篇 `citation_guard.py`，gap 只能由 verified 文献推出、禁脑补）→ 2 识别四类信号写 `data/research_gap.json`（candidate_topics/hotspots/controversies/gaps + novelty_risk）→ 3 DoD 盲检 → 4 `set-phase 1.5` + Git Checkpoint → HALT → 5 选定主线落盘（`selected` 标记 + outline.md 主线锚点 + 再补 Checkpoint）。

**HALT 点（2 个）：** ① phase gate（state.json 不存在）；② 展示 candidate_topics/gaps/novelty_risk 等用户确认选题方向，确认后必做主线落盘。
**必跑门禁：** `citation_guard.py`（逐篇 verified）；gate `research-gap-dod` 独立subagent盲检（`delegate_review.py pack/verify --checklist "[DOD_CHECKLIST]"`，fail-closed，未过不得声明完成）。

---

## Phase 1.6: Benchmark Review Library + Framing Guide（Write Mode only）

> 📖 **完整步骤详见 `docs/phase_1_6_benchmark_framing.md`，进入本阶段必须读取该文件执行。**（Write Mode only；Polish Mode 跳过。）

**Entry:** Read `outline.md` + `state.json`；`phase ≥ 1.7` → 已完成，skip。**Phase gate：`phase < 1.5` → HALT**，先完成 Phase 1.5。

**步骤概要：** 1 检索 5–10 篇近年同领域对标综述（串行 ≥1s，每篇走 `citation_guard.py` 验证、禁编造）→ 2 建 `data/benchmark_reviews.json` → 3 提炼 `data/framing_guide.md`（可复用章节框架/论证思路/图文关系/对本综述的具体建议）→ 4 DoD 盲检 → 5 `set-phase 1.6` + Git Checkpoint → HALT。产出在 Phase 1.7 建提纲与 Phase 3 搭框架时由 Framing hook 强制复用。

**HALT 点（2 个）：** ① phase gate（phase < 1.5）；② 展示对标库与 framing_guide 要点等用户确认，确认后进 Phase 1.7。
**必跑门禁：** `citation_guard.py`（对标综述真实性）；gate `benchmark-reviews-dod` 独立subagent盲检（`delegate_review.py pack/verify`，fail-closed）。

---

## Phase 1.7: Outline from Research + Structure Sign-off + Collection Tree

> 📖 **完整步骤详见 `docs/phase_1_7_outline_signoff.md`，进入本阶段必须读取该文件执行。**（Write Mode only；Polish Mode 直接去 Phase 3。）

**Entry:** Read `outline.md` + `state.json` + `data/research_gap.json`（selected 主线）+ `data/framing_guide.md` + `data/benchmark_reviews.json`；`phase ≥ 2` → skip。**Phase gate：`phase < 1.6` → HALT**，回去先做 Phase 1.5 / 1.6。

**步骤概要：** 1 据调研建提纲（selected gap 为骨架 + framing_guide 框架，Funnel Introduction + Thematic Body ≤2 层）→ 2 显式对齐对标框架 → 3 用户确认提纲、更新 outline.md（含迭代闸：Phase 2 后可回修）→ **结构签字落锁（用户在对话里明确确认提纲后，跑 Phase 0.5 打印的 `SIGNOFF_CMD`，即 `structure_signoff_gate.py` 的 confirm 子命令；未落签字则 PreToolUse hook deny 一切 `drafts/section_*.md` 写入；⚠️ 严禁在用户未确认时自行 confirm，那等于伪造用户签字）** → 4 注册 Figure 0 概念框架图 → 6 Zotero 集合树 `--init`（幂等；`--find-root-title` exit 4 多根时停下问用户）或 7 `init-index`（None/EndNote 模式）→ 8 `set-phase 1.7` + `set-root-key` → 9 Git Checkpoint → HALT。

**HALT 点（3 个）：** ① phase gate（phase < 1.6）；② 提纲确认（Confirm outline with user，确认后才许落签字）；③ 节末 HALT 等用户确认后进 Phase 2。（Zotero 多同名根集合 exit 4 时另需停下问用户。）
**必跑门禁：** 结构签字落锁（`structure_signoff_gate.py`，签字绑定大纲指纹，节号/标题/层级/顺序变化须用户重新确认后重签）。

---

## Phase 2: 系统主检索（Systematic Main Search）+ Real-Time Write

> 📖 **完整步骤详见 `docs/phase_2_search.md`（含 Per-Section Search Loop 全部命令、密度地板、Phase 2.5 去重），进入本阶段必须读取该文件执行。**（探索性检索已在 Phase 1.5 完成，本阶段是系统化主检索。）

**Entry:** Read `outline.md` + `state.json`，跳过已在 `searched_sections` 的节（检索完成标记，与写作完成的 `completed_sections` 独立）。开写前 Read `data/research_gap.json` 取 `selected` 主线。**Phase gate：`state.json` 不存在或 `phase < 1.7`（未落结构签字）→ HALT**，先完成 1.5→1.6→1.7。

**步骤概要（逐节循环，工具优先级见 § Search Tool Priority，串行 ≥1s）：** 每节 ≥10 篇 → `append-search-log` 记检索日志 → 入库前相关性筛选（不得"搜到即入库"）→ 写库（Zotero `--add-batch` / None `append-literature`，字段含 `related_sections` 数组）→ matrix bootstrap（None/EndNote）→ **`citation_guard.py --write-back`（exit 非 0 不得进下一节；🔴 绝不加 `--offline`、绝不省 `--write-back`，这是 Phase 3 盲检 R2b 的唯一证据来源）** → `complete-search`（🔴 绝不能用 complete-section）→ Git Checkpoint。全局目标 ≥100 篇；密度硬地板（三级叶子 ≥6 / 四级叶子 ≥3 / 容器父节 ≥1）由 Phase 3 prewrite_gate check3 硬拦。**Phase 2.5 去重：⚠️ HALT before dedup**，用户明确 "Continue" 后 [Zotero] 跳过（写入时已去重）/ [None] `reindex`，然后 `set-phase 2` + Checkpoint。

**HALT 点（2 个）：** ① phase gate（无 state.json 或 phase < 1.7）；② Phase 2.5 去重前（展示总数/预估重复/覆盖节次，等明确 "Continue"）。
**必跑门禁：** `citation_guard.py --write-back`（逐节，fail 即停）；`state_manager.py append-search-log`（可复现性台账）。

---

## Phase 3: Section-by-Section Writing

> 📖 **完整步骤详见 `docs/phase_3_writing.md`（Per-Section Cycle 十一步全部命令与契约、Polish 分支、Figure Prompt Generation），进入本阶段必须读取该文件执行。**

**Entry:** Read `outline.md` + `state.json`，并 Read `data/research_gap.json` 取 `selected` 主线（各节不得偏离）；`phase < 3`（Write Mode）才 `set-phase 3`，不得把 phase=4 项目回退；跳过 `completed_sections`。**Framing hook（MANDATORY）：** 各节搭框架前必须 `Read data/framing_guide.md` 并对齐（Polish Mode 文件缺失可跳过）。**Polish Mode 分支：** 按 `pending_sections` 路由 missing（就地补检索再写）/ rewrite / polish / keep（跳过）；空 → Phase 4。

**Per-Section Cycle 步骤概要（每节按序，细节全在 docs）：**
- **Step 0 🔴 prewrite_gate（脚本硬拦）：** `prewrite_gate.py --section X.X --root .`，exit≠0 禁止开写（查上一节完成/大纲就位/矩阵密度地板/占位符清零/本节检索做过 section_search_done/上一节盲检标记 `.review_pass/`）。逃生口 `--allow-no-search` / `--allow-manual-review`（显式理由、留痕）。
- **Step 1-2** 加载本节文献上下文（`--get-section` / matrix focus）；按条件 Round 2 补检索。
- **Step 3** Figure 读+写 `figures/figure_index.md`。
- **Step 3.5 🧭 引文核证：** 备料子代理起草（`delegate_write.py pack-prep` → `.claim_evidence_draft`）→ 主会话跑 `CITATION_CHECK_CMD`（`citation_claim_check.py`，承重句 contradict/unknown/缺 abstract/未 `user_confirmed` → fail-closed exit 2）→ AskUserQuestion 逐条确认承重句。
- **Step 4 撰写子代理盲写：** `delegate_write.py pack-write` → 派子代理（`references/section_writer_prompt.md`）→ `verify-write` 机械校验 → 落盘 `drafts/section_XX_XX.md` + new_refs 走 `citation_guard.py --require-mcp` → `resolve-keys` 认键翻号 → new_claims 复核（`citation_claim_check.py`）。子代理派不出时主会话亲写、门禁不变。
- **Step 5** `validate_citations.py --fail-on-orphan`（孤儿 `[N]` 即修）。
- **Step 6 轻量自查：** 先跑 `style_checker.py`（high/medium 必改；破折号禁止使用，命中一个即 hard_fail）再对照 `references/reviewer_checklist.md` D1-D5 自读。**🔴 硬约束：这是本技能内部的轻量质量 checklist，不是 reviewer-simulator 技能。禁止调用或进入 reviewer-simulator 技能，禁止逐节生成任何 HTML 审稿报告（report_*.html 或其他报告文件）。**
- **Step 7** `word_counter.py` 字数检查（用户自定短篇则尊重用户）。
- **Step 8** `state_manager.py complete-section`（MANDATORY）。
- **Step 9** Git Checkpoint。
- **Step 10 🔴 manuscript-dod 独立盲检（不得主 agent 自评）：** `delegate_review.py pack` → 派独立subagent → `verify --section --root`（fail-closed；通过落 `.review_pass/<节>.json` 供下一节 prewrite_gate 硬校验）。25 项含 R2b 联网核验（`check_online_verified.py`）、R21 `proofread.py` 机器硬门、R20/R22 软报告。修复循环最多 2 轮，仍败 → HALT 交用户。盲检跑不起来 → 逃生口 `--allow-manual-review`（人工核过再放行，禁自问自答冒充）。
- **Step 11 📋 DoD 结论摆出 + HALT：** 逐项列盲检 verdict + 本节 summary，等用户 "Continue" 才写下一节。

**HALT 点（2 个/节 + 1 个兜底）：** ① Step 10 修复 2 轮仍失败 → HALT 交用户裁决；② Step 11 每节完成必 HALT 等 "Continue"；（Step 3.5 承重句被拦时 AskUserQuestion 逐条等用户裁决。）
**必跑门禁（每节）：** `prewrite_gate.py`（Step 0）→ `citation_claim_check.py`（Step 3.5/Step 4 复核）→ `delegate_write.py verify-write`（Step 4）→ `validate_citations.py --fail-on-orphan`（Step 5）→ `style_checker.py`（Step 6）→ `word_counter.py`（Step 7）→ manuscript-dod 盲检 + `proofread.py` R21（Step 10）。
**全节完成后：** Figure Prompt Generation 一次性生成 `figures/figure_prompts.md`（配图 opt-in 默认关，见 docs）。

---

## Phase 4: Export & Finalization

**Start: Read `outline.md` + `state.json`. If state.json shows phase=4 and completed=true, skip.**

**⚠️ MANDATORY entry gate: block Phase 4 when pending sections remain (Polish Mode):**
```bash
python3 scripts/state_manager.py check-pending
```
Write Mode has no `pending_sections` field so this gate is a no-op (no key → empty dict → pass).

> **⚠️ HALT before Round 3 sweep.** Show user:
> - Sections to search: [list from outline.md]
> - Estimated: ~5–10 new preprints per section
>
> Ask: "Proceed with Round 3 preprint sweep? (yes / skip)"
> **Do not proceed until explicit user answer.** If "skip" → record `"round3_papers": 0` in state.json and jump to Step 2.

1. **Round 3 search:** Scan arXiv/preprints (last 6 months) for each section topic → add to relevant sections.
2. **Citation consistency + online validation:**

   **Polish Mode guard** (skip Steps 2a–2b when EITHER condition below holds; on hit, append `Citations not validated — manual review required.` to outline.md Current Status):
   ```bash
   # Empty index — no citations to validate
   python3 -c "import json,pathlib; p=pathlib.Path('data/literature_index.json'); exit(0 if (not p.exists() or len(json.loads(p.read_text(encoding='utf-8') or '[]'))==0) else 1)" && echo "GUARD: empty index → skip 2a-2b"
   # OR state.json marks citations as not imported
   python3 -c "import json,pathlib; s=json.loads(pathlib.Path('state.json').read_text(encoding='utf-8')); exit(0 if s.get('citations_imported') is False else 1)" && echo "GUARD: citations_imported=false → skip 2a-2b"
   ```
   **引用总量校验（警告性，不阻断；尊重用户自定的短篇长度）:**
   ```bash
   python3 scripts/state_manager.py count-citations --drafts-dir drafts --threshold 150
   ```
   > **类型分布（人工核对）：** literature_index.json 未记录 Original/Review/Preprint 类型字段，无法机器统计。AI 对照 Constraints §2 的**软目标**（按学科浮动、类型配比按论点性质、预印本按需）人工抽查 index，明显失衡时提示用户；不按固定配额卡数。

   ```bash
   python3 scripts/check_global_citation_sequence.py
   python3 scripts/validate_citations.py --live --live-used-only --fail-on-orphan --fail-on-live --fail-on-trace --retries 2
   # 🔴 --fail-on-live / --fail-on-trace 必带：不带时联网核验失败（编造 DOI 打 404）
   #    只打 [LIVE-FAIL] 行而退出码仍为 0，会被误读成通过。
   # Final citation guard pass: write verification results back to index
   python3 scripts/citation_guard.py \
     --index data/literature_index.json \
     --log data/citation_guard_report.json \
     --write-back \
     --manual-review data/manual_review_queue.json
   ```
   If non-zero exit → list all gaps; block compilation until resolved.
   `--write-back`: persists `verified:true/false` fields into literature_index.json for traceability.
   `--manual-review`: writes unverifiable entries to `data/manual_review_queue.json` for human check; does NOT block compilation unless `--require-mcp` is also set.

   > **【P4·文献抽验·用户必做】** 综述的命是引文。文献进正文前用户应抽 2-3 篇让 AI 报 PMID/DOI 自己去 PubMed 核对。⚠️ 你在 Windows 上 edirect 联网核验常跑不起来（本 SKILL 已注明 edirect 在 PowerShell/CMD 不可用），**一旦不能真的联网查，AI 必须停下告诉用户，绝不许硬着头皮编 DOI/年份**。`validate_citations.py --live` 跑不起来时明说「联网核验不可用」，不许自判通过。
3. **Export bibliography:**
   ```
   [Zotero] python3 scripts/zotero_manager.py --export-bibtex \
              --output exports/references.bib --root-key ROOT_KEY
   [None/EndNote]   python3 scripts/export_bibtex.py \
              --input data/literature_index.json \
              --output exports/references.bib \
              --clean
   ```
4. **Compile:** Merge all section drafts in correct order（**跑这条，跨平台**）:
   ```bash
   python3 scripts/compile_manuscript.py merge --drafts-dir drafts --out exports/Final_Review.md
   # 按文件名数字段排序合并，强制写 UTF-8 无 BOM；打印实际合并了哪些节，核对是否为大纲顺序。
   # 非 zero-pad 文件名也能排对，但建议统一：mv drafts/section_1_1.md drafts/section_01_01.md
   ```
   > **🔴 别用 shell 重定向合并。** POSIX 下的等价形态是 `cat drafts/section_*.md > exports/Final_Review.md`（仅供理解本步在做什么）；**PowerShell 下绝对不要跑它**——PowerShell 5.1 的 `>` 默认写 UTF-16LE，而下游 `consolidate_references.py` / `structure_outline.py` / `export_docx.py` 全是 `read_text(encoding='utf-8')`，会当场 UnicodeDecodeError，Phase 4 从 4a 起全线崩。上面的脚本没有这个问题。
   > **导出范围注记：** Markdown（`exports/Final_Review.md`）是中间产物；最终 docx 由本技能 Step 5d 的 `scripts/export_docx.py` 产出。字符级排版契约里的上下标 `^...^`/`~...~` 通过 pandoc 的 `+superscript+subscript` 扩展转换，正文/标题字体（Times New Roman、标题加粗）由 `templates/reference.docx` 锁定（该模板由 `scripts/make_reference_docx.py` 烘焙）。图注和表注比正文小一号锁 10pt，摘要走独立样式层同样 10pt。
   4a. **Consolidate references into ONE global list** (run immediately after the `cat` merge):
   ```bash
   python3 scripts/consolidate_references.py \
     --md exports/Final_Review.md \
     --index data/literature_index.json
   ```
   > 写作阶段（Phase 3 规则 7）每节自带 `## References` 是**自包含核验用**，保证每节引用都能当场对账。`cat` 拼接会把这些每节列表全部塞进最终稿，导致 docx 出现多个参考表。本步把正文里散落的所有每节 `## References` 块**剥掉**，按全局编号 `[n]` 升序在**文末重建唯一一个** `## References`（Vancouver 条目来自 `literature_index.json`）。脚本幂等；若某 `[n]` 在 index 查不到，stderr 警告但不阻断导出（退出码仍 0），按需补 index 后重跑。
   4b. **Cross-section coherence scan** (on compiled `exports/Final_Review.md`):
   Read the full compiled text sequentially and check:
   - **Transition continuity:** The opening of each section/subsection must logically connect to the closing of the previous one. Flag abrupt topic jumps with no bridging sentence.
   - **Cross-references:** If Section 3.2 discusses a mechanism introduced in Section 2.1, it should contain an explicit reference ("as discussed in Section 2.1" or equivalent). Flag implicit back-references that assume the reader remembers without a pointer.
   - **Argument arc:** The review's overall narrative should follow the outline's intended logic (e.g., "background → mechanisms → applications → challenges → future"). Flag sections that repeat points already made elsewhere or contradict earlier conclusions without acknowledging the contradiction.
   - **Introduction funnel check:** Introduction must narrow from broad field → specific gap → this review's contribution. Flag introductions that jump directly to specifics without establishing context.
   - **Conclusion echo check:** Conclusion must directly address the Research Question(s) from `outline.md` and reference key findings from body sections. Flag conclusions that introduce new claims not supported in the body.
   - If violations found → AI fixes inline in `exports/Final_Review.md`, adds transition sentences or cross-references, and propagates changes back to source `drafts/section_XX_XX.md`.

   4c. **Abbreviation consistency scan**（先跑脚本硬门，再做脚本盖不住的人工补查）：
   ```bash
   python3 scripts/abbreviation_consistency.py --drafts-dir drafts
   ```
   > **参数别照抄 gsw**：本家这份脚本只认 `--drafts-dir`（`--help` 实测），**不认** gsw 那份的 `--root`，照抄会当场 argparse 报错。扫 `drafts/**/*.md`（重复定义要靠跨文件比对，故喂 drafts 而非编译后的单文件；merge 衍生物已自动排除）。检测 ① **重复定义** 同一缩写在多个 draft 文件首次定义；② **未定义就用** 裸用 ABBR 且全稿无内联定义、又不在通用白名单（DNA/RNA/PCR 等自动跳过）；③ **Title 出现缩写**。**阻断**：exit 非 0 → 逐条按 `ABBR_CHECK_FAIL` 修 `drafts/section_XX_XX.md`，改完重跑至 exit 0，未过不得进 4d/导出。
   - 以下为脚本未覆盖、须人工补查的部分 (on compiled `exports/Final_Review.md`)：
   - Scan for all uppercase sequences ≥2 chars (candidate abbreviations) and parenthetical definitions like `Full Name (ABBR)` or `中文全称（英文全称, ABBR）`.
   - **Check:** Every abbreviation used bare (without parenthetical definition) in the text must have exactly ONE prior definition. Flag: (a) undefined abbreviations, (b) abbreviations re-defined in multiple sections, (c) abbreviations defined but never used again.
   - Generate `exports/abbreviation_list.md` table (see format in `references/writing_guidelines.md` §4 Abbreviation Management).
   - Title and abstract must not contain unexpanded abbreviations (except universally known: DNA, RNA, PCR, HIV, WHO, FDA).
   - If violations found → list them; AI fixes inline in `exports/Final_Review.md` and propagates back to the source `drafts/section_XX_XX.md`.

   4d. **交叉引用核查（xref，三层 · 报告式软门 · HALT 交用户裁决）** (on compiled `exports/Final_Review.md`)：
   查正文里"见图 5 / 见 3.3 节 / 见表 2 / as discussed in Section 2.1 / as shown in Figure 1"这类**显式指向**的目标存不存在、指得对不对。综述是交叉引用密度最高的稿型（Figure 0 要求每节都引，4b 还会**新写**指向句），而现役对此零覆盖：`validate_citations.py` 管文献 `[N]`、4a 管参考表合并、4b 管"隐式回指缺指针"、R11 只问"引没引框架图"——四者与本步零重叠，都不改判据、不合并。**本步必须排在 4b/4c 之后**（4b 新写的指向句正是最该抓的那批）。
   - **① 合成语料（本步开头无条件覆盖重建，幂等）**：综述的图题注登记在 `figures/figure_index.md`、按设计**不在成稿里**（Phase 4 Step 4 的 `cat` 编译一个字不改，题注不塞进成稿），直接把成稿喂第 1 层 = 每张注册过的图都被判悬空 = **100% 系统性假阳**（再被第 3 层"找不到定义处→confirmed"全部坐实）。故先把注册题注行拼到成稿前面：
     ```bash
     python3 scripts/compile_manuscript.py xref-corpus \
       --figure-index figures/figure_index.md --body exports/Final_Review.md --out tmp/xref_corpus.md
     # 🔴 这里是 --body（成稿），不是 --manuscript：下面第 1 层的 --manuscript 只准指
     #    tmp/xref_corpus.md，两者抄混就是 100% 系统性假阳。
     # 幂等覆盖重建；自动按下面的错误契约处理（figure_index 缺失→退化为纯正文且不报错、
     # 成稿缺失→报错退出）并打印「注册 N 条、进锚 M 条」，N>M 时逐条列出写歪的原行。
     ```
     > **🔴 别用 bash 那套。** POSIX 下的等价形态是
     > `mkdir -p tmp` + `{ grep -E '^##[[:space:]]*Figure[[:space:]]*[0-9]+[[:space:]]*[.:：]' figures/figure_index.md; cat exports/Final_Review.md; } > tmp/xref_corpus.md`（仅供理解取法：行首 `##` + Figure + 编号 + 分隔符的注册标题行）；**PowerShell 下不要跑它**——无 `grep`、不认 `[[:space:]]`、不认 `{ …; }` 分组，且 `>` 写 UTF-16LE。**这不是崩、是静默产假数据**：按下面的错误契约「grep 空匹配 exit 1 属正常、不得中断本步」，grep 不存在时语料会退化成纯正文 → 每张注册图都判悬空 → 正是本步开头写的「100% 系统性假阳」。上面的脚本内置同一形态的判据，跨平台一致。
     > **分隔符类 `[.:：]` 必须含全角冒号**：`## Figure 0：概念框架图` 这种全角注册行若被筛掉就**根本进不了语料**，④ 护栏 3 的回查再怎么写也看不到它（对该形态是死代码），而 Figure 0 是要求每节都引的框架图 —— 一条写歪的注册行会稳定产一条假阳。收进语料后第 1 层**仍认不出**它（英文 `Figure N` 题注正则只认半角，中文 `图 N` 才认全角），`caption_found` 仍为 `false`，由护栏 3 逐条回查兜住。
     > **该修正的已知副作用（无害，但别当成 bug 查）**：全角注册行既然不被题注正则识别，就**不会进 `caption_rows`**，于是会被当成一条标题、多抽出一条 `number=null` 的**假 section 锚**（实测 `SEC [(None,'Figure 0：概念框架图'), ('2.1','Results')]`）。这使「喂题注前后 `sections` 逐条相同」这条不变式**只在全部注册行都用半角分隔符时成立**。假 section 无编号，且第 2 层通读时一眼能看出那是图题注不是小节标题 → **不产假阳**，只是 `outline.json` 的候选清单多一条噪声。
     **只取匹配 `^## Figure N:` 的注册标题行、绝不 `cat` 整份登记表**（整份会多出一条假 section「Figure Index」，且 `- Type:`/`- Section:`/`- Key Message:`/`- Caption:`/`- Node mapping:` 五类登记字段行会被当成正文里的图/节引用）。**表题注就写在正文里、不需要合并，别把表也塞进本流程。** 落点固定 `tmp/xref_corpus.md`、`outline.json` 落项目根，**两者绝不落 `drafts/`**（`drafts/section_*.md` 是 managed_globs，写进去会被 signoff hook 拦下）；本步只读 `exports/`，**不写 `exports/` 下任何文件**（正文修改只发生在 HALT 后的用户裁决环节）。
     - **错误契约**：`figures/figure_index.md` 缺失 → `grep` 空匹配 exit 1 属正常，语料退化为纯正文、**不得因这个非零退出码中断本步**（图类会因锚不可用自动整类 skip）；`exports/Final_Review.md` 缺失 → 报错并停（Step 4 还没跑，属流程错序），不得产出空语料静默通过。登记表有 N 条注册项而只有 M 条进锚 → 在本步 advisory 里列出"注册 N 条、进锚 M 条"，提示用户按 `## Figure N: Title` 模板修正。**计数口径（写死，免各跑各的）**：**N = `figures/figure_index.md` 里所有 `^##` 开头且含 `Figure` + 数字的注册标题行数**（不论用什么分隔符，含 `-`、破折号、无分隔符等一切写法）；**M = 上面 `grep` 实际命中的行数**（即真正进语料的题注行数）。`N > M` 就报，差的那 N−M 条逐条列出原行，让用户看得见哪一行写歪了。
   - **② 第 1 层 确定性结构锚**：
     ```bash
     python3 scripts/structure_outline.py --manuscript tmp/xref_corpus.md --project-root .
     ```
     产 `./outline.json`（`sections`/`figures`/`tables`/`items` 四类真实存在的结构锚 + `summary`）。退出码 **0 = 正常（含空稿；四类为空数组是合法结果，不是失败，本步照常继续）**、**2 = 用法/输入错**（文件不存在、后缀不支持）。该脚本与 `_shared/` byte-identical、5 家共享，**一个字节不许改**（中文 `如图 1 所示` 已被现役正则正常捕获，不需要为它改）。
   - **③ 锚可用性门（第 2 层开跑前的确定性前置判定，主 agent 算好写进 prompt）**：
     ```
     figures_anchor_available  = any(f["caption_found"] for f in outline["figures"])
     tables_anchor_available   = any(t["caption_found"] for t in outline["tables"])
     items_anchor_available    = False   # 🔴 写死的常量：条目类整类不做，与第 1 层抽到什么无关
     # 节类没有对应的布尔量：它的可核性是语义判断，由第 2 层通读全文定（见下条）
     ```
     某类 `*_anchor_available == false` → **该类交叉引用一律强制 skip：不产 finding、绝不标 `uncertain`、绝不报 `missing_target`、绝不送第 3 层反向验证**；并在本步末尾产一条 advisory「X 类锚不可用，X 交叉引用未核，需人工过目」（强制 skip 不等于静默放过，用户必须知道哪一类没核）。
     **为什么禁 `uncertain` 而不是"标 uncertain 走人工"**：`uncertain` 与 `missing_target` 共用第 3 层同一条极性模板（"连定义处都找不到 → pass=confirmed"），锚不可用时目标本来就没有定义处 → 每条 uncertain 都会被自动坐实成 confirmed → 假阳 HALT。这与补充材料 S 前缀是同一个形状的坑，处置必须一致。
     - **🔴 节类不设确定性锚门，`outline["sections"]` 降级为"候选清单"**：不作真值、不做门、不据它算任何布尔量。原因是第 1 层根本分不清"章节标题"和"正文编号列举"——实测一份标题全无编号的稿，正文写了 `1. 代谢物通路` / `2. 免疫通路` 就抽成 `SEC [(None,'综述标题'),(None,'背景'),('1','代谢物通路'),('2','免疫通路')]`，任何基于它的门都被翻真。**节类的可核性与逐条判定，全部由 ④ 第 2 层子代理通读全文决定**（它能看到 markdown 结构、代码围栏、上下文）；子代理通读后认为全稿没有编号小节标题 → **节类整类 skip + advisory**。
     - **🔴 判据层级要匹配问题性质（本轮的架构修正，留档）**：**节标题的识别是语义判断，不做机器判据**——历史上用字符规则做过三轮，被**正文编号列表 → 中文顿号 `1、代谢物` → 孤立单条编号 → 多级列举 `2.1/2.2` → 围栏代码块里的 `#` 注释**逐一击穿（形态是开放集合，规则永远追不上），**别再放回来**。图/表能用确定性判据，是因为它们的锚来自**作者亲手声明的实物**（`figures/figure_index.md` 登记表、正文里的 `Table N:` 题注行）→ 回查等于查表；节**没有这种产物**（本技能不要求标题带编号）→ 判定本质是"读懂这份文档的结构"，**必须交给能看懂上下文的那一层**。这与本技能一贯分工一致：脚本抽弱锚（确定性、可回归测试），LLM 做语义判断。
     - **三类的实情**：**图**——题注在成稿外，靠 ① 合并语料才查得了；Polish 模式登记表为空 → 整类 skip。**表**——**一等公民**，题注就写在正文里、直接抽（systematic 档强制四类表：exclusions-with-reasons / RoB / effect / SoF，量大且核心）；作者一张表题注都没写才 skip。**节**——无确定性门，全交第 2 层通读（上两条）。
     - **🔴 条目类恒 skip**：`items_anchor_available = False` 是常量，`outline["items"]` **不读、不喂给第 2 层**。条目编号（`(1)`/`（1）`/`①` 这类）的交叉引用本轮**一律不核**——第 1 层的判据是"编号后是否紧邻实词"，而门要的是"这是定义还是引用"，两者正交（`(1)中枢神经系统`是定义、`(2)中已说明`是引用，同为行首、同一个"中"字），字符级规则区分不了；换判据得改 5 家 byte-identical 的脚本 → 本轮不可通。属**已知限制**，在交付说明里明写告诉用户。
   - **④ 第 2 层 独立检测子代理（fresh context、非作者自评）**：派一个**没参与撰写**的独立子代理（`TaskCreate`/spawn_task），**只喂** `./outline.json`（去掉 `items` 字段）+ `tmp/xref_corpus.md`，**不给撰写过程上下文、不给 `outline.md` 提纲、不给作者意图**（防继承作者确认偏误 → 系统性假阴）。逐条指向型表述判**存在性**（目标编号在不在 → `missing_target`）与**语义对应**（编号在但指错内容 → `semantic_mismatch`），拿不准标 `uncertain` 不硬判。**真值口径分两类，别混**：**图/表**——`outline.json` 的 `figures`/`tables` 是**权威真值**（锚来自作者亲手声明的登记表/题注行），不得凭记忆假设稿里有某张图；**节**——`outline.json` 的 `sections` 只是**候选参考**，以通读全文的结论为准（护栏 1b）。产出 schema `[{"ref_id","citing_location","cited_target","issue_type":"missing_target|semantic_mismatch|uncertain","evidence_quote","outline_says","finding","severity"}]`（`severity` 仅信息字段，**HALT 不按它路由**，所有 confirmed 一律交作者裁决）。三道护栏逐条写进 prompt：
     - **护栏 1 · 锚可用性门（图/表/条目三类）**：③ 算出的布尔量原样写进 prompt，取 `false` 的类别**一条都不许报**（含**绝不标 `uncertain`**）。`items_anchor_available` 恒 `false`，prompt 里同时写死：「条目编号（`(1)`/`（1）`/`①` 这类）的交叉引用本轮一律不核：不产 finding、不标 uncertain、不报 missing_target、不送反向验证。outline.json 的 items 字段不作为真值，忽略它。」
     - **🔴 护栏 1b · 节类判断指引（不是机器判据，逐条写进 prompt）**：
       > 「**通读 `tmp/xref_corpus.md` 全文，自行判断哪些行是真正的小节标题**——你能看到 markdown 结构、代码围栏和上下文，这件事只有你做得了。
       > 下面三类**不是**章节标题，别把它们当小节：**(a) 正文编号列举**（`1、代谢物通路` / `1. 免疫通路` / `2) 临床转化`，中文列举常不加空格）；**(b) 围栏代码块（```…```）内以 `#` 开头的行**——`#` 在 bash/python 里是注释符不是标题，systematic 档登记 PubMed 检索式时很常见；**(c) 行内提及**（句子中间出现的编号）。
       > `outline.json` 的 `sections` **只是候选参考、不是真值**，它由脚本按字符规则抽取，分不清标题和编号列举；**与你的通读结论冲突时，一律以通读为准**。
       > **判不准就交人工**：某条节引用你无法确定目标小节是否存在，**标注出来交用户过目，不要猜**——宁可交人工，不要产假阳。附录编号（`A.1` / `附录 A` / `Appendix B`）同样按通读判断，判不准照样交人工。
       > **🔴 两种情况整类 skip（类级出口，不逐条判）**：**(a)** 通读后认为**全稿根本没有编号小节标题**（作者用的是 `## 背景` 这类无编号标题）；**(b)** 通读后发现**编号体系不完整或不一致**——部分小节有编号、部分没有，或正文引用的编号层级与实际标题体系对不上（4b 会照提纲补写 `Section 2.1` 这类指向，而 drafts 的标题未必对得上，此时"3.4 不存在"看着很像真的，逐条判会自信地判错）。两种情况都：**不产任何 finding、整类 skip**，并产 advisory 告知用户节类未核、需人工过目。」
     - **护栏 2 · 补充材料 S 前缀**：**补充材料引用（`S` 前缀编号，如 `Figure S1`/`Table S3`/`见图 S22`/`Supplementary Fig. 5`）不在 outline 范围内**——正文稿抽不到补充文件的定义，此类**一律强制 skip 丢弃（不产 finding、绝不标 `uncertain`、绝不报 `missing_target`、绝不送第 3 层反向验证）**（否则走 `uncertain` 支会连同 `missing_target` 一起被送第 3 层，而补充材料图注天然不在主文 → 第 3 层"连定义处都找不到→pass=confirmed"把整份补充材料 S1–Sn 批量假报为悬空、假阳 HALT）。⚠️ 实测落实说明：`Figure S1`/`Table S3` 因 `S` 挡住数字捕获，第 1 层天然抽不到、无害；但 **`Supplementary Fig. 5` 里的 `Fig. 5` 会被第 1 层正常捕获成 `Figure 5` 假锚**，只能靠本条款 skip 掉。
     - **🔴 护栏 3 · 定义形态逐条回查（三类通用，防第 1 层漏抽造成的假悬空）**：判**任何** `missing_target` 前——**图、表、节三类一视同仁，不分类别**——必须先到 `tmp/xref_corpus.md` 里回查该编号的**定义形态**，**命中任一即不报**（改判无问题）；只有连一处定义形态都找不到，才允许判该编号悬空。**判据要泛化、不是逐例枚举。**
       - **🔴 节类的适用范围更宽、且判法不同：任何节类 finding（含 `semantic_mismatch`，不只 `missing_target`）都要先回查**，但回查方式是**通读，不是套判据**——「判任何节类问题前，先通读一遍全文确认：这个编号有没有在**某个真正的小节标题**里出现过？（`outline.json` 的节锚会被正文编号列举污染，正文写 `1. 代谢物通路` 就会多出一条 `('1','代谢物通路')` 的假节锚，拿它当真值判'编号在、但指的内容对不上'同样会假阳。）确认出现过 → 不报存在性问题；确认没出现过 → 才可报；**确认不了 → 交人工，不要猜**。」
       - **图/表的定义形态（题注行）**：该行**去掉行首的任意组合修饰**后，以 `Figure N` / `Table N` 开头且后接冒号或句点，即算题注。行首修饰含（但不限于）`#` 标题标记、`>` 引用块、`-`/`*`/`+` 列表符、`**`/`*`/`***` 强调标记、任意空白；分隔符含半角 `:` `.` 与全角 `：` `。`；题注可位于图/表的**上方或下方**（题注扫描逐行、位置无关）。已实测第 1 层认不出、必须靠本护栏兜住的形态：**粗体** `**Table N: …**`、**斜体/粗斜体** `*Table N: …*` / `***Table N: …***`（Word 转 md 常见）、**前缀式** `**Table N.** 说明`（编号后跟句点、强调只包编号，投稿模板高频）、**全角冒号** `Table N：…`。**别把回查写成只匹配这四例**——枚举必漏，按上面的泛化判据实现。advisory 里顺带提示用户"表题注别加粗，写成 `Table N: 说明` 或 `#### Table N: 说明`"。
       - **节没有"定义形态"判据，别去补一个**：节标题的识别是语义判断，交第 2 层通读（护栏 1b）。理由见 ③ 的「判据层级要匹配问题性质」。
     - **降级**：派不出真正独立的子代理 → 照盲评降级告警，**不得自问自答冒充**，标注"交叉引用未经独立检测"交用户人肉核。
   - **⑤ 第 3 层 反向验证（gate=`xref-verify`，fail-closed）**：每条 `missing_target`/`semantic_mismatch`/`uncertain` 过 `delegate_review.py`（**不改它一个字节，只调用其打包/校验两步**；`--gate` 是 checklist 内的自由 key，**不查 gate_registry**）。动态合成 `./xref_verify_checklist.json`：`{"skill":"review-writing","gates":{"xref-verify":{"title":"交叉引用一致性·反向验证","items":[{"id":"xref-001","name":"<cited_target 摘要>","check":"<按下方极性模板逐字填>"}]}}}`；item 只放 `cited_target` + `evidence_quote` + `issue_type` + 核验所需原文切片（**绝不放第 2 层的 finding 措辞/理由、也不放 `outline.json`**，防带节奏），默认硬项。**按 issue_type 分流喂料**：`missing_target`/`uncertain` 的 item 待检文件给**合成语料**（含题注的完整语料，让核验人独立回源检索该编号到底有没有定义处）——给成稿的话每条图引用都会因"成稿里本来就没有题注"被错误确认为悬空、这层等于失效；`semantic_mismatch` 的 item **按类别拆开喂**——**图/表**：引用处上下文切片 + `outline.json` 里该编号的标题/caption（那是权威真值，锚来自作者亲手声明的登记表/题注行）；**🔴 节**：只给引用处上下文切片 + **第 2 层通读认定的那条小节标题行原文**（原样引自 `tmp/xref_corpus.md`），**绝不给 `outline["sections"]`**。
     > **为什么节类要拆（与 ④ 的真值口径一致）**：`outline["sections"]` 是被正文编号列举污染的**候选清单**，不是真值——正文写了 `1. 代谢物通路`，喂过去就等于告诉核验人"第 1 节的标题是代谢物通路"这个**脚本编造的事实**，他据此判"内容明显无关 → pass=confirmed"，第 3 层不但没兜住、还成了假阳共犯。护栏 3 的通读只管第 2 层报不报，管不到报出来之后喂什么，所以这里必须单独拆。
     > **措辞留档（勿"顺手还原"，会致测试红）**：上一段刻意写成"只调用其打包/校验两步"，而不是更顺口的"只 pack/verify"——验收考卷把"同一行里既出现该脚本名、又出现 pack 字样"的行**一律当成打包命令行**来断言（要求该行含 `tmp/xref_corpus.md`），散文里同现会误伤致红。契约本身没被削弱（真正的命令行在下面的代码块里），改这段措辞前先看这条。
     **🔴 `check` 逐字用极性模板（禁占位符、禁自由发挥，`{编号}` 处填 `cited_target`）**：
     > `missing_target`/`uncertain`："到给你的原稿全文里，找得到编号「{编号}」的**定义处**吗？定义处专指：图/表的图注行（以『Figure {N}』『图{N}』『Table {N}』『表{N}』开头、后接说明文字的 caption 行），或该编号的小节标题行（如独占一行的『3.2 方法』）；**把它当引用来提及的句子不算定义处**（如『见 Figure 3』『as shown in Figure 3』『详见 3.2 节』这类指向句，即便含该编号也一律不算）。只有连定义处都找不到（该编号只被引用、从未被定义）才判 pass；只要找到定义处就判 fail，并逐字引出该定义/caption 行。"

     > `semantic_mismatch`："正文该引用处的具体断言，与目标「{编号}」的标题/caption 是否明确无关？只有'正文明确断言见 X 讨论了 Y、而 X 根本不涉及 Y'这种明确错位才判 pass；若只是笼统指向或目标标题能合理概括该引用，一律判 fail。"

     ```bash
     python3 scripts/delegate_review.py pack --checklist xref_verify_checklist.json --gate xref-verify --files tmp/xref_corpus.md --workdir .
     python3 scripts/delegate_review.py verify --checklist xref_verify_checklist.json --gate xref-verify --workdir .
     ```
     **🔴 禁传 `--section` / `--root`（跨阶段污染）**：校验全过且提供了 `--section` 时，会往 `<root>/.review_pass/<section>.json` 落"该节盲检通过"标记，而那正是 Phase 3 `prewrite_gate` 的硬校验依据——等于用 Phase 4 的 xref 核查**伪造 Step 10 `manuscript-dod` 的逐节盲检通过**。跑完本步 `.review_pass/` 必须零新增文件。
     独立空白子代理（无撰写上下文、不给 outline、不给第 2 层 reasoning）逐条只依据原文裁 `pass|fail|na` 并附逐字证据，写回 `./.review_return_xref-verify.json`。**verdict 映射（恒定）**：`missing_target`/`uncertain` **找到定义处（caption/小节标题行，非引用句自身）→ fail = refuted 剔除**、**连定义处都找不到（悬空引用）→ pass = confirmed 保留**；`semantic_mismatch` **明确无关 → pass = confirmed 保留**、**笼统指向/合理概括 → fail = refuted 剔除**；`problems`（空证据/未裁决/verdict 非法）照 fail-closed 视为未核验、**一律不进报告**（宁漏报）。极性写反 = 假批评全放行，务必让核验人区分"定义处 vs 引用处"。⚠️ **退出码陷阱**：任一 item fail 会让校验报 `ok=false` / **exit 1** / stderr『盲检未通过』——但在 xref-verify 里 **fail = 成功剔除假问题 = 正常好结果**。主 agent **必须忽略退出码**，只读返回 JSON 的逐条 verdict + problems，切勿把 exit 1 误读成核查失败。
   - **⑥ HALT 与清理**：命中 confirmed → **HALT 交用户裁决**：打印全部 confirmed（`cited_target` + 引用处原文切片 + evidence），暂停 Phase 4、交用户逐条裁决，就地改 `exports/Final_Review.md` **并反向同步回** `drafts/section_XX_XX.md`（与 4b/4c 同节拍），重跑 4d 至无 confirmed 再进 Step 5。**不 auto-block 硬拦、不静默放过。** 清理两态：**本步无 confirmed、放行下一步时 `rm -f tmp/xref_corpus.md`**（`tmp/` 未进项目 `.gitignore`，不删会被 Step 7 的 git checkpoint 收进去）；**命中 HALT 时保留语料**（用户要照着它核对），处置后重跑本步会重建再删。`outline.json` 保留供诊断。
5. **Final word count:** Verify total ≥ target in `outline.md`.

5b. **结构化"未来方向/开放问题"段（强制，Phase 4 交付前）：**
   若结论节不含独立 Future Directions 段，在此强制补写并插入 `exports/Final_Review.md` + 反向同步到最后一节 `drafts/section_XX_XX.md`。
   规则：≥3 条具体可操作方向，每条含 gap 原因 + 突破路径，不引入正文未建立的概念。
   📖 格式模板详见 `references/writing_guidelines.md` §6。

5c. **元数据块（导出前补全）：** 在 `exports/Final_Review.md` 末尾追加 Manuscript Metadata 块（search cutoff / databases / COI / funding）。
   📖 字段模板详见 `references/writing_guidelines.md` §7。

5d. **导出 docx（最终交付物）：** 所有 md 修复（4b/4c/5/5b/5c）完成后，将 `exports/Final_Review.md` 编译为 `exports/Final_Review.docx`：
   ```bash
   python3 scripts/export_docx.py --md exports/Final_Review.md --out exports/Final_Review.docx
   # 若使用 BibTeX/CSL 渲染参考文献，追加：--bib exports/references.bib [--csl style.csl]
   ```
   样式由 `templates/reference.docx` 锁定（正文 Times New Roman 12pt、标题 TNR 加粗），上下标 `^...^`/`~...~` 经 pandoc `+superscript+subscript` 转为真实上下标。pandoc 缺失时脚本会报清晰错误并退出。

6. **Update state.json (merge, do NOT overwrite):**
   ```bash
   python3 scripts/state_manager.py set-phase --phase 4 --completed true
   ```
   Only `phase` and `completed` are mutated; `completed_sections`, `mode`, `pending_sections`, `zotero_root_key`, `citations_imported` are preserved untouched.
7. **Git Checkpoint** (见复用块, msg: `[review] Phase 4: export finalized`)
8. **Update outline.md** current status section (human-readable summary).

**进入 Phase 5（投稿包）。** Phase 4 导出完成后不直接结束，继续生成投稿材料。

---

## Phase 5: Submission Pack

> 📖 **完整步骤详见 `docs/phase_5_submission_pack.md`（强制/询问分级表、投稿包各件写法与产出路径），进入本阶段必须读取该文件执行。**（Write 与 Polish 两模式都执行。）

**Entry:** Phase 4 导出完成后（`phase=4, completed=true`）。Read `outline.md` + `state.json`；`phase=5, completed=true` → skip。**Phase gate：`phase < 4` 或 Phase 4 未 completed → HALT**，先完成 Phase 4。
**进入本阶段必读：** `references/submission_checklist.md`、`references/cover-letter-guide.md`（写 cover letter 前必读）、`references/presubmission_checklist.md`（soft 提醒不阻断）。

**步骤概要：** 1 逐项询问（通讯作者/ORCID/CRediT/COI/Funding/致谢/是否要 Highlights·Suggested Reviewers，不静默留白）→ 2 生成投稿包写入 `exports/`（cover_letter/title_page/author_contributions/coi_statement/funding/data_availability/keywords/acknowledgements 等；**🔴 cover letter 的 scope 契合段强制：用户未给目标刊 Aims & Scope 原文则停下索取、不编造**；Suggested Reviewers 严禁伪造邮箱）→ 3 合规核对（ICMJE 署名、COI 回避；narrative 综述伦理/注册号标 N/A）→ 4 DoD 盲检 → 5 `set-phase 5 --completed true` + Git Checkpoint → 交付清单。

**HALT 点（2 个）：** ① phase gate（phase < 4 或未 completed）；② scope 原文缺失时停下向用户索取。
**必跑门禁：** gate `submission-pack-dod` 独立subagent盲检（`delegate_review.py pack/verify --checklist "[DOD_CHECKLIST]"`，fail-closed，未过不得声明完成）。

---

## Reference Manager Modes

Three modes: **Zotero**（推荐，实时写入）/ **None**（纯本地 JSON + BibTeX）/ **EndNote**（同 None，最后手动导入）。

> 📖 各模式详细说明见 `references/citation_styles.md` § Reference Manager Modes

---

## Edge Cases

> 📖 完整列表详见 `references/edge_cases.md`

| Issue | Handling |
|-------|---------|
| Zotero API key invalid / 403 error | Re-run `save-credentials` with a fresh key; do NOT proceed until `--status` returns ✅ |
| Mid-search crash | state.json `searched_sections` tracks search progress; resume skips done |
| PubMed CLI + paper-search MCP both unavailable | HALT; suggest install edirect or enable paper-search MCP; do NOT fallback to websearch/tavily |

---

## Scripts Reference

> 📖 完整 CLI 参数和用法详见 `references/scripts_reference.md`

19 个活跃脚本（`[project]/scripts/`，Phase 0 init 时全量镜像 `scripts/*.py`，除 `test_*.py` 与 `init_project.py`）：
`zotero_manager.py` | `state_manager.py` | `matrix_manager.py` | `word_counter.py` | `validate_citations.py` | `citation_guard.py` | `check_global_citation_sequence.py` | `export_bibtex.py` | `prewrite_gate.py` | `delegate_review.py` | `style_checker.py` | `proofread.py` | `abbreviation_consistency.py` | `compile_manuscript.py` | `consolidate_references.py` | `export_docx.py` | `make_reference_docx.py` | `citation_utils.py`（import-only） | `citation_guard_core.py`（import-only）

> `scripts/init_project.py` 是 Phase 0.5 一次性脚手架（从 SKILL_DIR 运行，不复制进项目），负责创建目录/全量镜像上述脚本/写 state.json+outline.md/git init。`state_manager.py` 新增 `set-phase` / `complete-section` / `complete-search` 子命令管理 workflow `state.json`（`complete-search` 写 Phase 2 的 `searched_sections`，与写作完成的 `completed_sections` 分开）。

---

## Interaction Rules

- **Read `outline.md` + `state.json`** at the start of EVERY phase and EVERY section loop.
- **State update is mandatory:** Update `state.json` immediately after every section and phase change.
- **Step-by-step stop:** HALT after each section. Output summary. Wait for "Continue".
- **Anti-Flattery:** Objective only.
- **Reverse Questioning:** Challenge user assumptions when warranted.
- **Point-by-Point Reply:** Address every query, no skipping.

---

## 发现 AI 跳步/漏做了怎么办（用户自救）

怀疑 AI 偷工减料时，直接把下面的话贴给它（可复制）：

- 「查进度：把 `state.json` 当前 Phase、`drafts/` 下已完成的节、`research_gap.json` / `benchmark_reviews.json` 在不在，逐一报我」（不在=跳了 Phase 1.5/1.6）
- 「对每条用到的引用跑 `validate_citations.py --live --live-used-only`，把原始输出贴我；`--live` 跑不起来就直说『联网核验不可用』，不许自判通过」
- 「每写完一节该停下让我验收，别一路写到底」
