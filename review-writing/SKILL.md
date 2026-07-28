---
name: review-writing
version: 2.28.1
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
| phase=2 | Phase 2（跳过 completed_sections） |
| phase=3 或 pending_sections 非空 | Phase 3（跳过 completed_sections） |
| phase=4, completed=true | Phase 4 导出完成 → 进 Phase 5（投稿包） |
| phase=5, completed=true | 已完成，告知用户 |

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


**Principle:** Complete ALL checks once before any other work. Prevent mid-task failures.

### 0.1 Collect Parameters

Ask all parameters at once. State defaults; user may accept silently.

| Parameter | Default | Notes |
|-----------|---------|-------|
| Review title/topic | (required) | Used as project folder name |
| Project location | **current working directory** | Path where `[TITLE]/` folder will be created |
| Target journal | (required) | Affects word count and citation density |
| Writing language | **English** | English / Chinese (Chinese: only changes writing language, same search tools) |
| Discipline | **Medical/Biomedical** | Determines search tool priority |
| **Review type** | **narrative** | `narrative`（叙述性）/ `critical`（批判性）/ `scoping`（范围综述）/ `systematic`（系统综述/Meta）/ `why-how-what`（三层轻量对比）。<br>• **scoping**：不需 PROSPERO，检索更宽，研究问题用 PCC（Population/Concept/Context）替代 PICO，Phase 0 末尾提示 scoping 记录要求。<br>• **systematic**：叠加 PRISMA 2020 + PICO/PECO + RoB（RoB 2/ROBINS-I）+ 可选 meta + GRADE。选此档则读取 `references/systematic_review_methodology.md`，并在各 Phase 挂接其触发点（见下「系统综述模式触发点」）。<br>• **why-how-what**：WHY/HOW/WHAT 三层结构化对比，介于快速摘要与完整综述之间，无 PRISMA/RoB/GRADE。选此档则读取 `references/why_how_what_mode.md`。 |
| Word count target | EN: 7,000–10,000 words / CN: 15,000–20,000 chars | |
| Total citations | 软目标(随学科浮动，非硬门禁)：生物医学~120–200 / 工程CS~60–120；仅警告不阻断 | 类型拆分与预印本按需，见 Constraints §2 |
| Reference manager | **Zotero** | Zotero / None / EndNote |
| Subagent model | Same as current session | AI scans available models, user confirms |

**If Chinese writing selected**, notify at end of Phase 0:
> 本技能使用 PubMed/paper-search MCP 检索英文文献。中文数据库（CNKI/万方）补充流程详见 `references/citation_styles.md` § CNKI / 万方中文文献导入。在初稿完成后统一补充，避免 gid 编号冲突。

#### 系统综述模式触发点（仅当 Review type = systematic）

> 📖 全部细则见 `references/systematic_review_methodology.md`（选 systematic 档时必读）。本文件只列挂接点：

| Phase | 触发点 | 动作 |
|-------|--------|------|
| **0** | PICO/PECO 登记 | 检索前把纳排标准（PICO 干预型 / PECO 暴露型）写入 `outline.md`；提示用户可选 PROSPERO 注册（本技能不代注册）。 |
| **2** | PRISMA 计数 | 每轮检索/去重后写入计数：`set-screening-counts`（identified/deduplicated/screened/excluded/included），维护「排除原因」表。 |
| **3** | RoB 逐研究评级 | RCT → RoB 2；观察性 → ROBINS-I；产出逐研究 RoB 表（domain × study）。 |
| **3**（可选） | meta 分析 | 仅当用户要求合并：选效应量（OR/RR/MD/SMD）、报告 I²/Q、产出森林图/漏斗图数据（数值合并交 stats 工具，配图交 matplotlib/seaborn）。 |
| **4** | GRADE + 输出 | 逐结局 GRADE 分级（high/moderate/low/very low + 降/升级因素）；导出 PRISMA 流程图数据块 + RoB 汇总 + SoF/GRADE 表。 |

PRISMA 计数读写命令（systematic 模式专用）：

```bash
python3 scripts/state_manager.py set-screening-counts --identified N --deduplicated N
python3 scripts/state_manager.py set-screening-counts --screened N --excluded N --included N
python3 scripts/state_manager.py get-screening-counts   # 读回校验
```

### 0.2 Full Environment Check

Run the 9-step environment detection (Step 0–8) (📖 full commands in `references/env_check.md`): Step 0 OS+Python, 1 curl, 2 git, 3 Zotero+pyzotero, 4 edirect, 5 proxy+PubMed connectivity, 6 NCBI key, 7 paper-search MCP, 8 required scripts. Display ✅/❌ per step. Record `os` / `git_available` / `pubmed_proxy` / `search_fallback` for Phase 0.5 to write into `outline.md`.

**All 8 must resolve before Phase 0.5.** Failure routing:

| Failed step | Blocking? | Consequence / route |
|-------------|-----------|---------------------|
| 0 Python < 3.7 | **YES** | Abort; guide upgrade (python.org / `brew install python` / `winget install Python.Python.3`). |
| 1 curl missing | **YES** | System-level issue; resolve before continuing (Windows: curl ships with PowerShell 5.1+). |
| 2 git missing | No | Not blocking, but **ASK** user to install (no snapshot fallback → no rollback without git). 装好重跑；拒装则确认知悉后继续，Checkpoints 静默跳过（`git_available: false`）。 |
| 3 Zotero/pyzotero (Zotero mode) | **YES** (Zotero mode) | `pip install pyzotero`; install Zotero desktop. None/EndNote mode → skip Step 3. |
| 4 edirect missing (Medical/Bio) | No | Auto-fallback to paper-search MCP → write `search_fallback: paper-search-mcp`; Windows → WSL or fallback. |
| 5 PubMed unreachable | No | Auto-scan proxy ports; if all fail → fallback to paper-search MCP, notify user. |
| 6 NCBI key unset | No | Optional; default 3 req/s rate limit. |
| 7 paper-search MCP absent | No | PubMed CLI only; inform user MCP is optional. |
| 8 required script missing | **YES** | Abort; verify SKILL_DIR path or re-install the skill. |

> ⚠️ At least one of Step 4/5/7 must yield a working retrieval path (edirect OR paper-search MCP). If **both** PubMed CLI and paper-search MCP are unavailable → HALT (see Edge Cases). Never fall back to websearch/tavily.

### 0.3 Zotero First-Time Setup (Zotero mode only)

> 📖 完整设置步骤（账号注册、API key 生成、权限配置、连接测试、安全规则）详见 `references/zotero_setup.md`。

**凭据持久化：存一次，之后自动复用。** 凭据存于 `~/.config/academic-skills/zotero.json`（用户主目录、chmod 600、不入 git，与技能仓库分离）。

- **已存凭据** → 所有命令自动读取，**无需**再传 `--lib-id/--api-key`。开工时先 `--status` 验证即可（不带凭据参数）。
- **未存凭据** → 引导用户去 https://www.zotero.org/settings/keys 拿 userID + API key（勾选 write 权限），运行一次：

```bash
# 首次：保存凭据（仅需一次）
python3 scripts/zotero_manager.py save-credentials --lib-id [NUMBER] --api-key [KEY]

# 之后：无需再传凭据
python3 scripts/zotero_manager.py --status
# Expected: ✅ Connected to Zotero library ...
```

优先级：命令行参数 > 已存 config > 提示保存。`api_key` 绝不明文回显（日志仅显示后 4 位）。若命令行显式传入 `--lib-id/--api-key` 仍可覆盖 config（不落盘）。

If `--status` lists multiple libraries (personal + group), show the list and ask user which to use, then re-run `save-credentials` with the chosen `lib_id`.

### 0.4 Subagent Model Detection

```
1. List all models available in current AI client
2. Present list to user
3. Ask: which model for subagent tasks? (default: same as current session)
4. Write choice to outline.md: subagent_model: <name>
```

### 0.5 Initialize Project Files

After all checks pass, run `scripts/init_project.py`. It creates the folder structure,
copies the active scripts (REQUIRED_SCRIPTS), writes `state.json` + `outline.md` (templates below), and runs
`git init` + the initial `[review] Phase 0: project initialized` commit (skips git silently if
unavailable). Cross-platform (pure pathlib, no heredoc).

> **⚠️ AI: resolve the three arguments before running:**
> - `--title` = the review title from Phase 0.1.
> - `--base`  = project location from Phase 0.1 (default: current working directory `.`).
> - `--skill-dir` = directory containing this skill. Lookup table:
>
> | Client | `[SKILL_DIR]` (Mac/Linux) | `[SKILL_DIR]` (Windows) |
> |--------|--------------------------|------------------------|
> | Claude Code | `~/.claude/skills/review-writing` | `C:\Users\<name>\.claude\skills\review-writing` |
> | Cursor | `~/.cursor/skills/review-writing` or project `.cursor/skills/review-writing` | `C:\Users\<name>\.cursor\skills\review-writing` |
> | Windsurf | `~/.windsurf/skills/review-writing` | `C:\Users\<name>\.windsurf\skills\review-writing` |
> | Other | Auto-detect: 📖 `references/env_check.md` § SKILL_DIR Auto-Detection | same |

```bash
python3 "[SKILL_DIR]/scripts/init_project.py" \
  --title "[review title]" \
  --base "[PROJECT_BASE]" \
  --skill-dir "[SKILL_DIR]"
# Writes: drafts/ exports/ scripts/ data/ tmp/ figures/ + figures/figure_index.md
#         + state.json {"phase":0,...} + outline.md template + git init & first commit.
```

> **⚠️ Working directory rule:** All commands in Phase 1–4 are run from inside `[PROJECT_BASE]/[TITLE]/`.
> After initialization: `cd "[PROJECT_BASE]/[TITLE]"` (the script prints this path).
>
> **Note:** Phase 0.5 only creates folder structure + copies scripts + writes state.json/outline.md. Zotero collection tree (`--init`) is NOT run here; it runs in Phase 1.7 (Write Mode, after the outline is built from research) or Phase 0-P Step 5 (Polish Mode). Phase 0.5 完成后进入 **Phase 1.5**（调研先于提纲）。

The script writes `[TITLE]/state.json`:
```json
{"phase": 0, "completed_sections": [], "zotero_root_key": ""}
```

…and the `[TITLE]/outline.md` template (AI fills Parameters/Environment fields after Phase 0.1–0.4). The template is auto-generated by `init_project.py`; do NOT recreate it manually. Key fields: Title / Target Journal / Language / Reference Manager / Review Type / Word Count Target / Citation Requirements / Discipline / os / git_available / pubmed_proxy / zotero_lib_id / search_fallback / subagent_model / RQ-PICO / Outline sections / Current Status.

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

> **⭐ 执行顺序（调研先于提纲）：这是 Phase 0 之后的第一个实质阶段。** 提纲不在这里建，先调研（1.5 空白 + 1.6 对标框架），到 **Phase 1.7** 才据调研结果建提纲并落结构签字。

**触发时机：** Phase 0 初始化后立即进入（提纲尚未建立，先摸清领域再据此建提纲）。Polish Mode 跳过（已有成稿）。
**Entry: Read `outline.md`（此时仅有模板骨架）+ `state.json`. If `phase ≥ 1.6`（对标框架已完成）→ already done, skip.**
> **Phase gate:** `state.json` 不存在 → HALT，提示先完成 Phase 0 初始化（Phase 0.5 生成 outline.md/state.json）。

**目的：** 建提纲、搭框架之前，先用**已检索到的真实文献**把这个领域摸清楚：有哪些热点、哪些争议、哪些机制线索、哪些没人填的空白，再让用户挑选题方向。综述的新意不是靠多引文献堆出来的，而是找到一个**有证据支撑、又还没被人好好综述过**的空白。提纲要等这一步读透了才动手。

### 步骤

0. **先定 RQ/PICO（提纲的语义锚点）：** 与用户确认研究问题 RQ/PICO（scoping review 用 PCC：Population/Concept/Context），写入 `outline.md` 的 `## Research Question` 区。RQ/PICO 明确后，探索性检索与后续提纲各节才有检验标准。（完整提纲结构在 Phase 1.7 据调研结果建立，此处只锚定研究问题。）

1. **初始化 index 并取证文献：** 先建空索引 `python3 scripts/state_manager.py init-index`（幂等，创建 `data/literature_index.json` + `data/synthesis_matrix.json`）。围绕 RQ/PICO 做一轮**探索性检索**（串行，≥1s 间隔，工具优先级同 Phase 2）。**探索阶段只写 `data/literature_index.json`（不依赖 Zotero 集合树，集合树在 Phase 1.7 建提纲后才创建）**，每篇跑 `citation_guard.py`，**gap 只能由 verified 文献推出**。本步入库可与 Phase 2 共享 index（不重复入库）。
   > ⚠️ 红线：gap 必须从真实文献证据推出，**禁止脑补**。每个 gap 关联 ≥1 篇支撑文献 `[n]`，且该 `[n]` 已 citation_guard verified。

2. **识别四类信号**，写入 `data/research_gap.json`：
   - `candidate_topics[]`：候选选题方向（每个含一句话 framing + 支撑 refs）
   - `hotspots`：近年高频/高被引主题（含 support_refs）
   - `controversies`：文献中的矛盾发现/未决争论（含对立双方 refs）
   - `gaps`：研究空白（每个含 `id` / `description` / `support_refs[]` / 为何是空白）
   - `novelty_risk`：候选选题与**既有综述/已发表工作**的重叠度比较，标 high/medium/low + 理由（防止"重复造轮子"）

   ```json
   {
     "candidate_topics": [{"topic": "...", "framing": "...", "support_refs": [3, 7]}],
     "hotspots": [{"theme": "...", "support_refs": [3, 12]}],
     "controversies": [{"issue": "...", "side_a_refs": [5], "side_b_refs": [9], "note": "..."}],
     "gaps": [{"id": "gap-1", "description": "...", "support_refs": [7, 12], "why_gap": "..."}],
     "novelty_risk": [{"topic": "...", "overlapping_reviews": [...], "risk": "low", "reason": "..."}]
   }
   ```

3. **DoD 自检（gate `research-gap-dod`，委托独立subagent盲检）：**
   ```bash
   python3 scripts/delegate_review.py pack --checklist references/dod_checklist.json \
     --gate research-gap-dod --files data/research_gap.json --workdir .
   # → 派独立subagent（Claude Code 用 academic-blind-reviewer），不给写作上下文，按任务包返回 JSON
   python3 scripts/delegate_review.py verify --checklist references/dod_checklist.json \
     --gate research-gap-dod --return .review_return_research-gap-dod.json
   # 退出码非 0 = fail-closed，据subagent证据修复后重跑，未过不得声明完成
   ```
   gate 5 项：G1 每 gap ≥1 verified 文献支撑 / G2 与 literature_index 一致（无孤儿）/ G3 从真实证据推出（禁脑补）/ G4 含 novelty_risk 比较 / G5 占位符清零。逐项内容以 `references/dod_checklist.json` 为唯一真源。

4. **更新 state + Git Checkpoint：**
   ```bash
   python3 scripts/state_manager.py set-phase --phase 1.5
   git add -A && git commit -m "[review] Phase 1.5: research gap identified" --allow-empty-message 2>/dev/null || true
   ```

**HALT. 向用户展示 candidate_topics / gaps / novelty_risk，等用户确认选题方向后再进 Phase 1.6。**

5. **🔴 选定主线落盘衔接（防长会话丢主线，HALT 确认后必做）：** 用户确认选题方向后，立即把"选定的综述主线（选题方向 + 核心 gap）"显式固化，作为 Phase 2/3 的主线依据，不靠隐式记忆：
   - 在 `research_gap.json` 被选中的 gap/candidate_topic 上加 `"selected": true` 标记；
   - 同时把"选定主线 = 选题方向 + 核心 gap 一句话"写入 `outline.md` 顶部的主线锚点区（无则在文件首行新增 `## 综述主线（锚点）` 区块）。
   - 落盘后再补一次 Git Checkpoint。

---

## Phase 1.6: Benchmark Review Library + Framing Guide（Write Mode only）

**触发时机：** Phase 1.5 选题确认后、**Phase 1.7 建提纲前**（对标框架既指导 Phase 1.7 的提纲结构，也在 Phase 3 搭正文框架时复用）。Polish Mode 跳过。
**Entry: Read `outline.md` + `state.json`. If `phase ≥ 1.7`（提纲已定）→ already done, skip.**
> **Phase gate:** `phase < 1.5` → HALT，提示先完成 Phase 1.5。

**目的：** 好综述的框架不是拍脑袋想出来的。找近年 5–10 篇**对标综述**（同领域顶刊 review），看它们怎么分章节、怎么讲道理、图和正文怎么配合、引言-主体-展望怎么组织，把这些可复用的套路提炼出来，Phase 3 搭正文框架时直接照着用。

### 步骤

1. **检索对标综述：** 工具优先级同 Phase 2（串行，≥1s）。目标 5–10 篇近年同领域高水平综述（Nature Reviews / Cell / Lancet 系等）。每篇**必须真实存在并走 citation_guard 验证**，禁编造。
   > ⚠️ 红线：对标综述真实存在、走 `citation_guard.py` 验证，不编造标题/期刊/年份。

2. **建对标库 `data/benchmark_reviews.json`：** 每篇含
   ```json
   [{
     "title": "...", "journal": "Nature Reviews ...", "year": 2023,
     "framework_outline": "该综述的章节框架（背景→机制→应用→挑战→展望 ... 具体到节）",
     "highlights": "亮点：如何 framing、如何仲裁矛盾、图怎么用",
     "verified": true
   }]
   ```

3. **提炼 `data/framing_guide.md`：** 从对标库归纳**可操作**的写作思路，至少覆盖：
   - 可复用的章节框架骨架（漏斗引言 → 主题主体 → 展望）
   - 论证思路（如何从 setup → evidence → synthesis → implication）
   - 图表与正文的关系（概念框架图放哪、每节图承担什么角色）
   - 引言-主体-展望的组织套路
   - 对**本综述**的具体建议（结合 Phase 1.5 的 gap，而非泛泛而谈）

4. **DoD 自检（gate `benchmark-reviews-dod`，委托独立subagent盲检）：**
   ```bash
   python3 scripts/delegate_review.py pack --checklist references/dod_checklist.json \
     --gate benchmark-reviews-dod --files data/benchmark_reviews.json data/framing_guide.md --workdir .
   python3 scripts/delegate_review.py verify --checklist references/dod_checklist.json \
     --gate benchmark-reviews-dod --return .review_return_benchmark-reviews-dod.json
   ```
   gate 4 项：B1 ≥5 篇 verified / B2 每篇含框架大纲 / B3 framing_guide 含可操作建议 / B4 占位符清零。真源见 `references/dod_checklist.json`。（framing_guide 是否真被用于搭框架，是 Phase 3 才发生的动作，不在此 Phase 1.6 gate 里核，改由 Phase 3 framing hook 强制落实、见 SKILL.md Phase 3 “Framing hook”。）

5. **更新 state + Git Checkpoint：**
   ```bash
   python3 scripts/state_manager.py set-phase --phase 1.6
   git add -A && git commit -m "[review] Phase 1.6: benchmark reviews + framing guide" --allow-empty-message 2>/dev/null || true
   ```

**HALT. 向用户展示对标库与 framing_guide 要点，确认后进 Phase 1.7（据调研建提纲）。**

> **🔗 Phase 1.7 + Phase 3 挂接（强制）：** Phase 1.7 建提纲结构、Phase 3 各节搭正文框架前，都必须 `Read data/framing_guide.md`，并使结构与其提炼的可复用框架对齐（由 Phase 3 “Framing hook” 强制落实）。这是 Phase 1.6 产出的落地点，不得跳过。

---

## Phase 1.7: Outline from Research + Structure Sign-off + Collection Tree

> **执行顺序：Phase 0 → 1.5（研究空白）→ 1.6（对标框架）→ 本阶段 1.7 → Phase 2。** 提纲是读透调研后的产物，所以先做完 1.5/1.6 才轮到这一步。**进入条件：`phase ≥ 1.6`（`data/research_gap.json` 已有 `selected` 主线 + `data/framing_guide.md` 就位）；若 `phase < 1.6` → HALT，回去先做 Phase 1.5 / 1.6。**

**Start: Read `outline.md` + `state.json` + `data/research_gap.json`（取 `selected` gap/选题方向）+ `data/framing_guide.md`（对标框架）+ `data/benchmark_reviews.json`. If state.json shows phase≥2, skip.**
**Polish Mode: if `state.json` contains `"mode": "polish"`, skip Phase 1.5/1.6/1.7 entirely and go to Phase 3.**

1. **据调研建提纲（不是凭空设计）：** RQ/PICO 已在 Phase 1.5 定义。以 **Phase 1.5 选定的 gap/主线** 为骨架、参照 **Phase 1.6 framing_guide 的可复用章节框架**，提出提纲结构："Funnel" Introduction + "Thematic" Body（≤2 层级）。每个主体节次应能对应到某个 gap / 争议 / 主线分支，避免与既有对标综述结构简单雷同（呼应 novelty_risk）。
   - Scoping review：研究问题用 PCC（Population / Concept / Context）。
2. **对齐对标框架：** 显式说明本提纲如何借鉴/区别于 framing_guide 提炼的结构（由 Phase 3 “Framing hook” 强制落实）。
3. **Confirm outline with user.** Update `outline.md`.

   > **⚠️ 迭代闸（Iteration Gate）：提纲在此可回修。**
   > Phase 2 检索完成后，若揭示出提纲遗漏了重大分支或主要争议（例如：某类方法在文献中被大量讨论但提纲无对应节次），允许回到此步修改提纲，并记录修改理由：
   > ```
   > [Outline revision after Phase 2 search]
   > Reason: Phase 2 revealed that X is a major branch in literature (~N papers) but
   >         was not covered in the original outline. Added Section X.X.
   > Impact: Related sections [list] may need additional citation targets.
   > ```
   > 修改后须更新 `outline.md`，重新确认 Zotero 集合树（`--init` 是幂等的），并用 Git Checkpoint 记录版本。**不得因回修提纲而删除已完成节次的已有文献入库记录。**

   > **[结构签字·强制门禁落锁]** 用户在对话里明确确认提纲后（且**仅在此之后**），运行 Phase 0.5 `init_project.py` 打印的那条 `SIGNOFF_CMD`（已含解析好的绝对路径与项目根）落盘签字，即 `python "<review-writing>/scripts/structure_signoff_gate.py" confirm --root <项目根> --note "<用户确认原话摘录>"`。这一步解锁正文写作：**未落签字，PreToolUse hook 会物理拦截任何对 `drafts/section_*.md` 的写入**（这是防跳步的硬门，不是提示词纪律）。该 hook 由 Phase 0 `init_project.py` 开工时经本技能 vendored 的 `install_gate_hook.py`（在 `scripts/` 下）自动安装并校验，它先把门禁四件套部署到 `~/.claude/academic-gate/`（稳定位置，不随技能目录增删而动），再让 `settings.json` 的 hook 指向那里，单独分发的技能也能自装（备份原 settings / 只追加不覆写 / 校验失败即回滚），init 回显 `门禁保护[active]` 即在岗生效；若回显 `[installed]`，表示首次安装成功、settings.json 已写入，但 hook 需【重启一次本会话】后才加载生效（无法热生效）；若回显 `[degraded]` 或 `[error]`（安装/校验未通过，如缺 `_shared`），物理拦截不可用、降级为提示词纪律，签字仅留痕、无强制，需人工守住「未签字不写 `drafts/section_*.md`」。若后续回修提纲（上方迭代闸允许），改完让用户重新确认并重跑本命令覆盖签字。⚠️ 严禁在用户未确认时自行运行 confirm，那等于伪造用户签字。

4. **规划贯穿全文的概念框架图（提纲确认后，Phase 1.7 内完成）：**
   在 `figures/figure_index.md` 中注册一条 `Figure 0`（概念框架图），要求：
   - 覆盖全文逻辑主线（背景→机制/方法→应用/挑战→展望），体现各节之间的内在逻辑联系
   - 包含 Key Message（一句话）、草稿 Caption（出版级精确度）、节次映射关系
   - 写作时（Phase 3）各节需在文中引用该图，"如 Figure 1 所示"
   ```
   ## Figure 0: [Conceptual Framework — Title of Review]
   - Type: Conceptual overview
   - Section: ALL (全文贯穿)
   - Key Message: [one sentence summarizing the review's core argument/framework]
   - Caption: [draft — publication-ready, ≤150 words]
   - Node mapping: [e.g., "Section 1.1→Background box; Section 2.X→Mechanism module; Section 3.X→Application module"]
   ```

6. **Initialize Zotero collections (Zotero mode):**
   ```bash
   # First check if collection tree already exists (idempotent, safe on re-entry):
   ROOT_KEY=$(python3 scripts/zotero_manager.py --status --find-root-title "[TITLE]" \
     2>/dev/null) && echo "Root exists: $ROOT_KEY" \
     || python3 scripts/zotero_manager.py --init --title "[TITLE]" --outline outline.md
   ```
   - `--find-root-title` exit 0 → root already exists (stdout = key, reuse it); exit 3 → no match, the `||` branch runs `--init`; exit 4 → ambiguous (multiple same-named roots), stdout lists candidate keys. **Stop and ask user to pick** rather than letting `--init` create a duplicate.
   - Creates root collection + subcollections matching outline hierarchy.
7. **Initialize index files (None/EndNote mode):**
   ```bash
   python3 scripts/state_manager.py init-index
   # Creates empty data/literature_index.json + data/synthesis_matrix.json + figures/figure_index.md (idempotent).
   ```
8. **Update state.json** (writes phase=1.7 + zotero_root_key, preserving other keys):
   ```bash
   python3 scripts/state_manager.py set-phase --phase 1.7
   python3 scripts/state_manager.py set-root-key --key "[key from step 6]"   # Zotero mode only; skip in None/EndNote
   ```
9. **Git Checkpoint** (见复用块, msg: `[review] Phase 1.7: outline confirmed (post-research)`)

**HALT. Wait for user to confirm outline before Phase 2.**

---

## Phase 2: 系统主检索（Systematic Main Search）+ Real-Time Write

> （探索性检索已在 Phase 1.5 完成，本阶段是系统化主检索。）

**Start: Read `outline.md` + `state.json`. Skip sections already in `completed_sections`.**
> **主线依据（防丢主线）：** 开写前 Read `data/research_gap.json`，取 `selected` 的 gap/选题方向作为本轮检索与写作的综述主线，确保不偏离 Phase 1.5 选定的核心 gap。
> **Phase gate:** if `state.json` does not exist or `phase < 1.7`（提纲未据调研建立/未落结构签字）→ HALT; tell user "先完成 Phase 1.5（研究空白）→ 1.6（对标框架）→ 1.7（据调研建提纲 + 结构签字），系统主检索按提纲逐节进行"; do not proceed.

### Search Priority by Discipline

> Use the **Search Tool Priority (Universal)** table above (§ Search Tool Priority). Primary = PubMed CLI for Medical/Bio/Interdisciplinary, paper-search MCP for CS/AI; fallback is the other; `websearch`/`tavily` are forbidden in all disciplines.

### Per-Section Search Loop
```
for each section in outline.md (e.g., section ID = "2.1"):
  SECTION_FILE="tmp/papers_2_1.json"   # replace dots with underscores in section ID

  1. Check state.json → if section in completed_sections, SKIP
  2. Search ≥10 papers → collect metadata: title, authors, year, doi, abstract, source
     - Every paper must have abstract; if missing → re-fetch via efetch or paper-search
     - Still no abstract after retry → mark abstract:missing, skip for now
  2a. [可复现性] 记录检索日志：
      python3 scripts/state_manager.py append-search-log \
        --section X.X --query "QUERY" --database pubmed \
        --n-hits N_HITS --n-screened N_SCREENED
      # N_HITS = 搜索工具返回的原始命中数；N_SCREENED = 阅读标题/摘要后判断相关保留的数量
      # 检索日志写入 data/search_log.json（独立文件，不影响 literature_index.json）
  2b. [相关性筛选] 入库前逐篇判断（不得"搜到即入库"），保留条件：标题/摘要与本节 RQ/PICO（或 PCC）直接相关。排除标记（language / off_topic / quality / outdated）— 📖 详见 `references/scripts_reference.md` § Phase 2 入库前相关性筛选。最终保留的才进入 `tmp/papers_X_X.json`。
  3. Save metadata to tmp/papers_X_X.json  (e.g., section 1.1 → tmp/papers_1_1.json)
  4. Write papers (run ONLY the branch matching the project's Reference Manager; they are alternatives, not sequential):
     [Zotero] python3 scripts/zotero_manager.py --add-batch \
       --section "X.X" --papers tmp/papers_X_X.json \
       --root-key ROOT_KEY --index data/literature_index.json
       # ROOT_KEY from state.json; --add-batch deduplicates at write time + auto-writes literature_index.json.

     [None/EndNote] python3 scripts/state_manager.py append-literature \
       --section X.X --papers tmp/papers_X_X.json --index data/literature_index.json \
       --source-provider SP
       # SP: pubmed-cli (default) or paper-search. openalex/tavily/websearch FORBIDDEN (citation_guard blocks).
       # CNKI/Wanfang refs go via manual RIS import — 📖 references/citation_styles.md § CNKI/万方。

     Required fields per entry: `global_id` (int), `title`, `authors`, `year`, `doi` or `pmid`, `abstract`, `related_sections` (array, e.g. `["1.1"]`).
     > ⚠️ Use `related_sections` (array), NOT `section` (string). One paper can belong to multiple sections simultaneously — 📖 详见 `references/scripts_reference.md` § Related-Sections 字段规则。
  5. [None/EndNote] Bootstrap synthesis matrix entry for this section (auto-skips if row exists):
      ```bash
      python3 scripts/matrix_manager.py bootstrap \
        --index data/literature_index.json \
        --matrix data/synthesis_matrix.json \
        --section X.X --round 1
      ```
  6. Run anti-hallucination guard (all modes):
       python3 scripts/citation_guard.py \
         --index data/literature_index.json \
         --log data/citation_guard_report.json \
         --write-back
     If guard exits non-zero → do NOT continue to next section; fix flagged entries first.
     `--write-back` 把每条的 verified 与 per-entry checked_at 落盘到 literature_index.json，下一节复用已验条目、跳过重复联网核验（L1 短路，TTL 30 天）。verified 由脚本写、不靠 AI 记。
  7. Confirm write success → update state.json (add section to completed_sections):
     python3 scripts/state_manager.py complete-section --section X.X
     # Adds X.X to completed_sections (idempotent), preserves all other keys.
  8. Git Checkpoint (见复用块, msg: [review] Phase 2: section X.X search complete)
  9. Continue to next section
```

**Global target:** ≥100 papers total (before dedup). If a section yields <10 papers, warn and prompt user to broaden keywords.

**Per-subsection density（按标题层级，prewrite_gate check3 硬拦）:** level = section_id 段数+1（`2.1`=三级、`2.1.1`=四级）。硬地板：三级叶子节 ≥6 条、四级叶子节 ≥3 条，其余层级 ≥1；低于地板 prewrite_gate exit 1 禁止开写。容器父节（大纲里还有更深子节的节，如 `2.1` 下有 `2.1.1`）本身不承载文献，放宽到 ≥1。软目标：三级 ≥10、四级 ≥5，未达只进 warnings 提示补足、不阻断。

**Chinese writing mode:** Search tools identical to English mode. Read language setting from outline.md.

### Phase 2.5: Dedup + Global ID Assignment

**⚠️ HALT before dedup.** Show user: total papers found, estimated duplicates, sections covered.
Wait for explicit "Continue".

```
[Zotero] ⚠️ --add-batch already deduplicates at write time (DOI exact + title fuzzy ≥0.85).
         Normal workflow does NOT need --dedup here — SKIP this step.
         📖 `--dedup` is repair-only and has a gid-resync caveat — see `references/edge_cases.md`
            ("Zotero --dedup gid 失同步") before ever running it.

[None/EndNote]   python3 scripts/state_manager.py reindex \
           --storyline outline.md --index data/literature_index.json \
           --matrix data/synthesis_matrix.json
```

Dedup rules (None/EndNote mode reindex):
1. Primary key: DOI exact match
2. Fallback: normalized title (lowercase + strip punctuation) → SequenceMatcher ≥0.85
3. On duplicate: keep canonical entry, merge related_sections
4. `global_id` reassigned in canonical section outline order (1.1 → 1.2 → 2.1 → ...)

**Update `state.json`（仅更新 phase 字段，不覆盖 completed_sections / zotero_root_key）：**
```bash
python3 scripts/state_manager.py set-phase --phase 2
# Sets phase=2 only; completed_sections / zotero_root_key / mode / pending_sections preserved.
```

**Git Checkpoint** (见复用块, msg: `[review] Phase 2.5: dedup + global ID assigned`)

---

## Phase 3: Section-by-Section Writing

**Entry: Read `outline.md` + `state.json` first. 并 Read `data/research_gap.json` 取 `selected` 的 gap/选题方向作为综述主线依据，开写各节须围绕该核心 gap，不偏离 Phase 1.5 选定的主线。If `state.json` phase < 3 (Write Mode), update to phase=3:**
```bash
# Only run if current phase < 3 (read state.json first; Polish Mode already enters at phase=3).
# Do NOT regress a phase=4 project back to 3.
python3 scripts/state_manager.py set-phase --phase 3
```
**Skip completed sections (check `completed_sections` list).**

> **🔗 Framing hook (Write Mode, MANDATORY before building any section's framework):** `Read data/framing_guide.md` (produced in Phase 1.6) and use its reusable章节框架/论证思路 as the basis for each section's structure. Do NOT fall back to a generic default template. (Polish Mode: file may not exist, skip if absent.) This IS where framing-guide alignment is actually enforced; the Phase 1.6 benchmark gate no longer checks this Phase 3 action, and the resulting structure is reviewed downstream by manuscript-dod (R15/R16/R18).

**Polish Mode branch (if `state.json` contains `"mode": "polish"`):**
```
Before starting any section, read state.json → pending_sections:
  missing → no draft exists: run systematic main search (same as Phase 2 per-section loop Steps 2-6) INLINE here, then proceed to step 1 below. Do NOT navigate back to Phase 2; all search+write happens within this Phase 3 section loop.
  rewrite → existing draft exists in drafts/section_XX_XX.md: read it as context, then fully rewrite
  polish  → existing draft exists in drafts/section_XX_XX.md: read it; fix ONLY AI-flags + thin citations;
            keep structure and arguments intact; do NOT overwrite with fresh draft
  keep    → skip entirely (already in completed_sections)

If pending_sections is empty → all sections complete; proceed to Phase 4.
```

### Per-Section Cycle

0. **🔴 开写前置闸门 (Mandatory，脚本硬拦截)**：开写本 section 前必须先跑 `python3 scripts/prewrite_gate.py --section X.X --root .`，exit≠0 禁止开写。它统一硬检查：上一节完成（上一节 ∈ `state.json.completed_sections`）、大纲就位（`outline.md` 含本节标题）、素材就位（`data/synthesis_matrix.json` 本节文献矩阵按标题层级达硬地板：三级叶子≥6/四级叶子≥3/容器父节≥1；软目标三级≥10、四级≥5 未达只 warn 不拦）、上一节占位符清零（`drafts/` 无 `CITE_PENDING`/`DATA_PENDING`/`【待`）；上一节盲检结果（`.review_pass/<上一节>.json`）缺失即 prewrite_gate 硬拦 exit 1，禁止开写；必须先跑 delegate_review verify --section <上一节> 落盘通过标记。**盲检subagent确实跑不起来时**，用 `--allow-manual-review "<理由>"` 显式人工放行（仅放行盲检项、留痕审计，见规则 10 的逃生口）；不加则门禁默认硬拦行为不变。PASS 时脚本会注明"仅覆盖形式层，语义正确性未自动核验"。Polish Mode `keep` 节跳过本节循环故无需跑。

1. **Load context:**
   ```
   [Zotero] python3 scripts/zotero_manager.py --get-section "X.X" \
              --root-key ROOT_KEY
   [None/EndNote]   python3 scripts/matrix_manager.py focus --section X.X
            # Shows papers + existing claim bindings for this section from synthesis_matrix.json
            # Also read data/literature_index.json filtered by related_sections containing X.X
   [Polish Mode] Also read existing drafts/section_XX_XX.md (rewrite: as reference; polish: as base to edit)
   ```

2. **Round 2 search** (targeted, ≥5 additional papers for specific claims):
   - **Write Mode:** triggered when Phase 2 found <10 papers for this section, or the writer identifies specific claims that lack supporting evidence during Step 4 drafting
   - **Polish Mode `rewrite`:** RECOMMENDED. Run targeted search if diagnosis flagged citations/500w < 2.
   - **Polish Mode `polish`:** only if Phase 0-P Step 3 diagnosis flagged citations/500w < 2
   - **`keep` sections:** skip
   - If user explicitly requests Round 2 for any section → execute regardless of above criteria
   - Add new papers same way as Phase 2 (batch add + dedup).

3. **Figure (MANDATORY): read then write.**
   a. **Read** `figures/figure_index.md` → find existing entries where `Section: [SectionID]`. If an entry exists, load its Caption and Key Message as writing context for Step 4.
   b. **Write** (append) new figure definition if not yet defined for this section:
   ```
   ## Figure N: [Title]
   - Type: Schematic | Conceptual overview | Workflow | Mechanistic pathway
   - Section: [SectionID]
   - Key Message: [one sentence]
   - Caption: [draft caption — precise, publication-ready]
   ```
   > `figures/figure_index.md` is the canonical figure registry for ALL modes (Write, Polish, None). It is NOT inside `drafts/`.

3.5. **🧭 引文核证脚手架（帮你写对的辅助，不是卡后续的墙）：** 落笔前，为本节**承重论点**（load-bearing：机制断言、疗效/因果结论、关键定量声明等支撑全节论证的句子）逐条把"论点 ↔ 它要引的文献"对齐，判断该引用是否真支撑这句话，落盘项目根 `claim_evidence.json`。

   > **🤝 备料子代理起草（一律派，主会话核证+确认）：** 读一堆 abstract 判 verdict 是吃上下文的重活、跨节累加不释放（综述上下文爆的病根），改由**备料子代理**吸走。**非白名单节一律派**（无阈值分支）：
   >   1. 主会话生成备料包：`python3 scripts/delegate_write.py pack-prep --section X.Y --root .`（产 `.prep_task_X.Y.json`，切片来自 `synthesis_matrix.json` claim↔文献绑定，复用矩阵不重复建库）。
   >   2. **派一个备料子代理**，把 `references/prep_subagent_prompt.md` + 备料包路径贴给它；它产草案 `.claim_evidence_draft_X.Y.json`（`user_confirmed` 全 false、提议 `claim_kind∈{mechanism,efficacy,background,emerging}`、`evidence_quote` 须账本 abstract 子串），**不碰任何账本**。
   >   3. 主会话核证：跑 `citation_claim_check.py --root . --check-quote-substring`（子串防伪）读草案渲染矩阵表 → **AskUserQuestion 逐条确认承重句**（`user_confirmed=true` + 顺带确认 `claim_kind`，同一次交互）→ 确认行**由主会话**并入 `claim_evidence.json`（单写者不破）。空草案 `{"claims":[]}` 合法：跳过核证直接进 Step 4。
   >   4. **白名单节**（front/back-matter、无承重论点、或本节零可引文献）主会话就地建、不派备料。
   > `claim_evidence.json` 每条：`{section, claim_sentence, is_load_bearing, claim_kind, ref_id, retrieved_abstract, verdict∈support/weak/contradict/unknown, evidence_quote, user_confirmed}`。abstract 取自文献**检索时原样落盘的真实 abstract**（`data/literature_index.json` 的 `abstract` 字段，**不是可事后编的 key_finding**）。背景陈述句列入即可（`is_load_bearing:false`），批量过目、不逐条阻断。
   > **跨节复用（脚本自动读写 `ref_evidence_cache.json`，AI 不必手记字段）：** 已在别节验过的文献，本节该行的 `retrieved_abstract` 可留空，脚本按 `ref_id` 从项目根 `ref_evidence_cache.json` 自动回填真实 abstract；完全同一 `(ref_id, 论点句)` 且此前已 `user_confirmed` 的承重句，脚本自动复用其 verdict 与确认，不再反向验证、不再 AskUserQuestion。只有**新的 (文献, 论点) 组合**才需重新判支撑并逐条确认。核证后脚本强制把已验 abstract 与已确认承重 verdict 落盘，已验状态由脚本维护。此复用**不放松门禁**：缺 abstract、承重句 contradict/unknown、未 `user_confirmed`，仍 fail-closed（见下 exit 2）。
   然后跑 Phase 0.5 打印的 `CITATION_CHECK_CMD`（绝对路径指向 `<review-writing>/scripts/citation_claim_check.py --root <项目根>`；读项目根 `claim_evidence.json`，渲染 claim↔引用支撑矩阵表）：
   - **承重句** `contradict` / `unknown` / 缺 `retrieved_abstract` / 未 `user_confirmed` → 脚本 fail-closed（exit 2）。对每个被拦的承重句，用 **AskUserQuestion 逐条**呈现（论点 + 拟引文献 + abstract 摘录 + 机器判定），让用户裁决：换引文 / 改写论点 / 确认支撑（确认后在该条置 `user_confirmed:true` 重跑）。
   - **背景句** 的 weak/contradict 只在矩阵表里标红提示，**批量**过目即可，不逐条打断。
   - **定位**：这是帮你把引用挂对的脚手架，带着"引用确实支撑论点"的把握再落笔。通过后进 Step 4。（复用已建的 synthesis_matrix，不重复建库。）

4. **Draft（主会话调度 + 撰写子代理盲写，立场反转）：** 本节 synthesis 正文改由**撰写子代理**盲写、主会话调度（synthesis writing 已从 NOT Delegatable 移入 Delegatable，见 `references/subagent_guide.md`）。**替换只发生在"主会话亲写正文"↔"派子代理写正文"之间；前后所有门禁（Step 0 prewrite / Step 3.5 核证 / Step 5 spot-check / Step 10 盲检）一个不删、次序不变。** 落盘目标仍 `drafts/section_XX_XX.md`（zero-pad 每段到 2 位，如 1.1 → `drafts/section_01_01.md`、2.10 → `drafts/section_02_10.md`）。

   **粒度 = outline 叶子节**（三级 `2.1` / 四级 `2.1.1`）；**容器父节**（大纲里还有更深子节的节）本身不落笔、不派。

   **调度流水线（主会话按序跑，只看退出码，不亲持整节草稿）：**
   1. **pack-write：** `python3 scripts/delegate_write.py pack-write --section X.Y --root .` → 产 `.write_task_X.Y.json`。任务包**嵌入本节全部原料**（`certified_claims` 已核证对 / `lit_section` 本节文献全条带真实 abstract / `neighbor_digest` 邻节 key_facts / 全量缩写表 / `style_rules`），**全局框架给路径**（大纲/全库文献/矩阵按需 Read）。**framing_guide 进包**：把 `data/framing_guide.md` 提炼的本节章节框架/论证思路写进任务包 `embed.framing_guide`（撰写子代理照此搭结构，落实 Framing hook）。
   2. **派撰写子代理：** 把 `references/section_writer_prompt.md` + 任务包路径贴给一个**全新独立上下文**的撰写子代理（Claude Code：`Task`，`subagent_type` 用通用/写作 agent，不给别节写作上下文）。它盲写本节正文，返回 `.write_return_X.Y.json`：正文引用**只写 `[@key]`**（key=gid 或 `new:slug`，绝不裸数字）、承重句只挂内嵌 `certified_claims`、新配对进 `new_claims`、新文献进 `new_refs`。
   3. **verify-write：** `python3 scripts/delegate_write.py verify-write --section X.Y --root .` 机械校验返回（无裸数字引用 / `[@key]` 可解析 / `new_refs` 带 DOI 或 PMID / section_id 一致）；exit≠0 打回子代理重写。
   4. **落盘 + 认键翻号：** verify 通过后，主会话把 `markdown` 落盘 `drafts/section_XX_XX.md`；`new_refs` **先** `citation_guard.py --require-mcp` 核真伪 → 通过的才 `append-literature` 并表（去重、分配 gid），失败的丢弃 + 打回子代理改写该处引用；然后 `python3 scripts/state_manager.py resolve-keys --drafts-dir drafts --index data/literature_index.json --returns-dir .` 把本节 `[@key]` 翻回 `[gid]`（认键层，供后续 Step 5 spot-check / reindex 认数字）。
   5. **new_claims 承重复核：** `citation_claim_check.py --root .` 复核——承重句须命中已核证对，未核证的 `new_claims` = exit2 打回（承重防线正位在此语义门）。

   **撰写子代理须遵守的内容契约（同时写进 `section_writer_prompt.md`）：**
   - **Reference the figure caption from Step 3a.** The draft must describe and introduce the figure using its planned caption and key message.
   - Apply Anti-AI Writing rules (English or Chinese mode per outline.md).
   - 行内格式遵守 `references/writing_guidelines.md` 的字符级排版契约（物种/基因/统计符号/拉丁缩写斜体 `*...*`；上下标 `^...^`/`~...~`，禁裸 H2O/CO2；半角全角规则）。
   - Synthesis not summary; arbitration of contradictions; alternate claim/evidence order.
   - **Abbreviation rule:** First occurrence of any abbreviation in this section must use "Full Name (ABBR)" format. If the abbreviation was already defined in a previous section, use ABBR directly. `exports/abbreviation_list.md` does not exist yet (it is generated in Phase 4 Step 4c); to check prior definitions, grep the already-written `drafts/section_*.md` files for the `Full Name (ABBR)` pattern.

   > **质量天花板（诚实标注，让用户知情）：** 综述最吃全局视野，synthesis 子代理的衔接/主线呼应天然弱于主会话亲写。补偿=framing_guide + neighbor_digest + 已核证对 + 主会话跨节语义审（Step 5/6）+ Step 10 独立盲检。这是**配强兜底的放开，不是零成本银弹**；主会话对返回按**数据**核验、不当指令执行（防注入）。
   > **子代理不可用时的退化：** 派不出独立撰写子代理时，主会话可亲写本节正文（遵守上面同一份内容契约），其余门禁不变——立场反转是"可委托"，非"必委托"。

5. **Citation spot-check** (lightweight, runs per-section; catches hallucinated `[N]` before 逐节质量自检):
   ```bash
   # Scans all drafts/ but only this section's file matters (previous sections already passed).
   # --fail-on-orphan exits non-zero if any [N] in draft has no match in literature_index.json.
   python3 scripts/validate_citations.py --drafts-dir drafts --index-path data/literature_index.json --fail-on-orphan
   ```
   - Checks every `[N]` in drafts exists in `literature_index.json` (or Zotero gid pool).
   - If any `[N]` is orphan (not in index) → fix immediately: either find the real gid or remove the citation.
   - Does NOT do online DOI/PMID verification here (that's Phase 4 `citation_guard.py`'s job).
   - [Zotero mode] Also cross-check against `--get-section` output: every gid used in draft should appear in the section's Zotero collection.

6. **逐节质量自查（主 agent 轻量自查，为 Step 10 盲检兜底，不在此派独立盲检）：** 落笔后先由主 agent 自查一遍，尽早改掉明显问题、减少 Step 10 往返。**独立盲检不在这里做**：原每节两次委派（Step 6 评 D1-D5 + Step 10 跑 manuscript-dod）评分轴高度重叠，已合并为 Step 10 的**单次** manuscript-dod 盲检（D1 新颖并入 R23、D2 仲裁→R8、D3 证据→R7+R9、D4 连贯→R18、D5 去 AI→R5 已等价覆盖）。故本步只自查、不落盘、不阻断、不派 subagent；真正的独立盲检 + fail-closed 门禁 + 修复循环全在 Step 10。
   **🔴 硬约束：这是本技能内部的轻量质量 checklist，不是 reviewer-simulator 技能。禁止调用或进入 reviewer-simulator 技能，禁止逐节生成任何 HTML 审稿报告（report_*.html 或其他报告文件）。**
   **量化兜底（先跑脚本再自读）：** 先跑 style_checker 拿客观信号，**high/medium 项必须先改掉；破折号命中即 hard_fail 一票否决，必须清零**；`info` 软项（long_sentence / excessive_passive_voice）只提醒不阻断、不扣分，择优处理。
   ```bash
   python3 scripts/style_checker.py --file drafts/section_01_01.md --passive-max 0.30
   # 硬项(计分/hard_fail,可致 exit 1)：forbidden_ai_phrases / scare_quotes / explanatory_colon_in_prose / trailing_ing_clause / bullet_points / decorative_em_dash(破折号,hard_fail 一票否决) ...
   # 软项(severity=info,只报告不扣分不阻断)：long_sentence(>30词) / excessive_passive_voice(>30%)
   # exit 0 = 通过(score≥阈值)；非 0 = 据 issues 里的 high/medium 项修复后重跑（info 项不影响退出码）
   ```
   然后主 agent 自读本节，对照 `references/reviewer_checklist.md` 的 D1-D5（新颖 / 仲裁 / 证据 / 连贯 / 去 AI）过一遍，把一眼能看出的问题就地改掉。这只是自查，是否通过不决定能否进下一步，门禁在 Step 10。

7. **Word count check:**
   ```bash
   python3 scripts/word_counter.py --file drafts/section_01_01.md --language en   # or --language cn for Chinese; read from outline.md
   ```
   Key sections target: >500 words (EN) / >1,500 chars (CN); Supporting: >200 words / >600 chars.
   **If user explicitly requested a shorter length** (e.g., "~800 characters"): defer to user's request; treat the skill's minimums as guidance for quality, not a hard gate. Do not loop-prompt the user to write more if they have already confirmed their target length.

8. **Update state.json (MANDATORY, do not skip):**
   ```bash
   python3 scripts/state_manager.py complete-section --section X.X
   # Adds X.X to completed_sections AND removes it from any pending_sections bucket (Polish Mode),
   # preserving all other keys. Idempotent.
   ```
   A section must never appear in both `completed_sections` and `pending_sections` simultaneously (the command guarantees this).

9. **Git Checkpoint** (见复用块, msg: `[review] Phase 3: section X.X draft complete`)

10. **DoD 自检清单（硬规则）：逐项确认通过后才可声明本节完成，不得跳过任何一项。**

    **🔴 进入下一节前置闸口：上一节 delegate_review verify 必须 exit 0（含 R15 结构完整性），否则不得开始下一节撰写。写完即检，不过不进。**

    **🔴 委托盲检（不得主 agent 自评）**：你刚写完本节，自评会失真地默认通过、且易漏项。落盘前必须把 DoD 清单**委托给独立上下文的subagent盲检**，自己不直接打勾：
    1. 生成任务包：`python3 scripts/delegate_review.py pack --checklist references/dod_checklist.json --gate manuscript-dod --files <本节文件> --workdir .`（会在 stderr 打印 `RETURN_PATH=...`，即subagent返回要写入的约定路径）
    2. **派一个独立subagent**（不给它本节写作上下文），把任务包原样贴给它，要求把 JSON 数组写到 `RETURN_PATH`。**可直接复制执行的派发指令**：
       - Claude Code：用 `Task` 工具，`subagent_type="academic-blind-reviewer"`（无此 agent 时退回 `general-purpose`），prompt = pack 打印出的整段任务包原文（含"你的角色/待检文件/检查清单/返回格式/返回写到这个文件"），**不附加任何本节写作说明**。
       - 其他平台（Codex/OpenCode 等无此 agent）：新开一个干净上下文的subagent/子会话，同样只贴任务包原文。
    3. 校验返回：`python3 scripts/delegate_review.py verify --checklist references/dod_checklist.json --gate manuscript-dod --return <subagent返回.json> --section <当前section_id> --root <项目根>`；退出码非 0（任一缺项 / fail / 无证据）= **fail-closed**。**修复循环（原 Step 6 的修复委派并入此处）：** 任一项失败即派一个**修复子代理**（输入 = 盲检返回的结构化意见 + 本节 `drafts/section_XX_XX.md`，不给写作上下文）做针对性修改，改完重跑 `pack → verify` 复评；修满 2 轮仍失败 → **HALT**，输出结构化反馈（【问题】+ 证据锚点 + 根源分析 + 修复方向）交用户裁决。是否修订 / 是否 HALT 的决策由主会话把关，不可委托。**未过不得声明完成。** verify 通过会落盘 `.review_pass/<当前section_id>.json`，下一节 `prewrite_gate.py` 会**硬校验**它（缺失即拒绝开写）。
       > **诚实边界：** verify 的 `ok:true` 只代表清单每项都被裁决且形式合规，**PASS 仅覆盖形式层，语义正确性由盲检subagent主观判断、未自动核验**。
       > **【P4·盲检降级告警】** ⚠️ 若环境派不出真正独立的subagent（非 Claude Code、无 `academic-blind-reviewer`），**绝不能同一 AI 自问自答冒充盲检**。告诉用户「本环境盲检不可靠，请你亲自复核本节」，别让自证闭环静默跑。
    4. **🚪 逃生口（盲检subagent确实跑不起来时，且仅此时）**：若平台无 `academic-blind-reviewer`、通用subagent也反复失败/取不到返回，导致 `verify` 无法落盘标记、下一节被 `prewrite_gate` 永久锁死，**不要卡死或静默跳过**。改为人工逐项盲检本节 DoD 后，用显式放行开锁并留痕：
       ```bash
       python3 scripts/prewrite_gate.py --section <下一节id> --root . \
         --allow-manual-review "谁放行 + 为何盲检subagent不可用 + 已人工核过哪些项"
       ```
       它只放行"上一节盲检"这一项（其余硬检查照常），并写 `.review_pass/<上一节>.json`(manual:true) + 追加 `.review_pass/MANUAL_REVIEW_AUDIT.log`；理由为空则拒绝放行。此后每次 `prewrite_gate` 都会在 warnings 里点名"人工放行、语义未经独立盲检"。**门禁默认行为不变**：不加此参数时，缺盲检标记照旧硬拦。

    `manuscript-dod` gate 共 **24 项（R1–R24；22 硬门禁 + R20/R22 两软报告）**，覆盖：通用（引文一一对应 / citation_guard / 符合 storyline / 占位清零 / 去 AI / 字数）、review 特有（综合非罗列 / 矛盾仲裁 / 引用类型匹配 / 检索日志 / 框架图一致）、systematic 额外（PRISMA 自洽 / RoB / GRADE）、结构完整性、**覆盖全面性 / 关键文献遗漏与引用偏倚 / 论证 arc 连贯 / 学术合规披露（R16-R19 盲检质量核）/ 新颖性与贡献（R23 盲检质量核）**、字符级机器门禁（R21）。**本次盲检已一并承接原 Step 6 逐节自检的 D1-D5 轴：D1 新颖→R23、D2 仲裁→R8、D3 证据→R7+R9、D4 连贯→R18、D5 去 AI→R5，故每节只在此做一次独立盲检，不再于 Step 6 重复委派。** **逐项内容 / severity / 核验命令以 `references/dod_checklist.json` 为唯一真源**，上面 `pack` 步骤运行时会把该 gate 的每个 item（id / name / check / script）完整打印进盲检任务包，此处不逐条枚举以免与 JSON 漂移。systematic 3 项仅 Review type = systematic 时检查，其余全类型通用。

    - **R21 语法拼写与字符级格式(🔴机器硬门禁,可阻断)**,跑 `python3 scripts/proofread.py --manuscript-dir drafts --report proofread_report.json --fail-on misspelling,chinese_punct,subsup_bare`。stdlib-only、自包含。高置信三类**零容忍**：misspelling(英文常见错拼)、chinese_punct(中文标点漏入英文)、subsup_bare(应上下标却裸写,如 H2O/CO2/IC50,CJK 安全边界),命中任一即 `ok=false`(脚本 exit 1),据 `proofread_report.json` 的 `fail_on_hits` 定位修复后重跑。其余类别(英美拼写混用、单位格式、术语写法不一致、数字千分位、Methods 时态、学术错拼/中文错别字等)仅在报告里提示、不阻断,由作者择一统一。与 R5 去AI(style_checker)互补:R5 管文风,R21 管字符级机器错。

    附带软报告项（不计入硬门禁退出码，由盲检subagent LLM 判断）：

    - **R20 常识合理性(🟡软报告,不阻断)**,盲检subagent顺带扫正文是否有明显常识/事实硬伤(单位量级离谱、生理/机制常识错误、跨文献综合时的事实拼接错误、前后数值逻辑矛盾等)。**仅提示不阻断**,只在发现明显硬伤时记入盲检反馈供用户裁决,绝不自动改内容。与引用/文献核验门禁区分:本项管"综述论述的内容常识上是否成立"。

    - **R22 拉丁短语斜体软提醒(🟡软/人工确认,不阻断)**,`proofread.py` 的 `latin_italic_missing` 类别:正文里 `in vitro`/`in vivo`/`ex vivo`/`in situ`/`de novo`/`post hoc`/`per se` 等公认须斜体的拉丁短语若裸写(未被 `*...*` 斜体标记包裹)则报告。**仅提示,不阻断、不进 `--fail-on`、不扣分**,由人工确认是否补斜体(`et al.`/`e.g.`/`vs.` 等正体惯例不在词表内)。

11. **📋 DoD 结论摆出 + HALT（展示式，不新增硬墙）：** 本节 `delegate_review verify` 盲检通过（exit 0 且 `.review_pass/<section>.json` 已落盘）后，先把**逐项 DoD 结论**摆给用户，从subagent返回的 JSON 里**逐条列出每个 `manuscript-dod` item**（id/name + verdict + 证据锚点摘录，以返回 JSON 的实际条目为准、不手点项号，含 systematic 3 项、结构完整性、R16-R19 覆盖全面性/引用偏倚/论证连贯/合规披露、R23 新颖性与贡献、字符级 R21；R5 里降软的长句/被动如命中只作 info 提示、不影响通过；破折号为 hard_fail 一票否决、命中即不通过）。再附本节 summary（content / logic / citation count / word count）。**然后 HALT 等用户确认，才写下一节。** 这是"展示 + 可继续"：盲检已过即可放行，此处只保证用户看到每项结论、有机会叫停，不新增硬门。Wait for "Continue".

### Figure Prompt Generation

**Trigger:** Run ONCE after ALL sections in Phase 3 are complete (all sections in `completed_sections`).
Generate prompts for every entry in `figures/figure_index.md`. Write output to `figures/figure_prompts.md`.

> 📖 Use the figure-prompt template in `references/writing_guidelines.md` §5 (TYPE / SUBJECT / STYLE / COLOR SCHEME / ELEMENTS / LAYOUT / TYPOGRAPHY / KEY MESSAGE / AVOID).

**配图（opt-in，默认关）：** 默认不生成配图；仅当用户明确要求「生成配图 / 画图代码」（生信/统计图）时启用 → 调用本地 matplotlib / seaborn skill 生成**可运行代码（非图片）**，遵循：按数据选图型（bar / box / line / scatter+回归 / forest / funnel（meta 用）/ volcano · MA（差异表达用）/ heatmap / network / concept map）、APA caption、色盲安全配色（viridis / cividis）、300 DPI、轴标签带单位、禁 3D / 饼图。systematic 模式下可据此生成 PRISMA 流程图 / RoB 红绿灯图 / forest / funnel 代码。

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
   python3 scripts/validate_citations.py --live --live-used-only --fail-on-orphan --retries 2
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
4. **Compile:** Merge all section drafts in correct order:
   ```bash
   # Zero-padded filenames (section_01_01.md, section_01_02.md, ...) sort correctly with glob
   cat drafts/section_*.md > exports/Final_Review.md
   # Verify: ls drafts/section_*.md should list files in outline order
   # If any file uses non-padded name, rename first:
   #   mv drafts/section_1_1.md drafts/section_01_01.md
   ```
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
     mkdir -p tmp
     { grep -E '^##[[:space:]]*Figure[[:space:]]*[0-9]+[[:space:]]*[.:：]' figures/figure_index.md; \
       cat exports/Final_Review.md; } > tmp/xref_corpus.md
     ```
     > **分隔符类 `[.:：]` 必须含全角冒号**：`## Figure 0：概念框架图` 这种全角注册行若被筛掉就**根本进不了语料**，④ 护栏 3 的回查再怎么写也看不到它（对该形态是死代码），而 Figure 0 是要求每节都引的框架图 —— 一条写歪的注册行会稳定产一条假阳。收进语料后第 1 层**仍认不出**它（英文 `Figure N` 题注正则只认半角，中文 `图 N` 才认全角），`caption_found` 仍为 `false`，由护栏 3 逐条回查兜住。
     > **该修正的已知副作用（无害，但别当成 bug 查）**：全角注册行既然不被题注正则识别，就**不会进 `caption_rows`**，于是会被当成一条标题、多抽出一条 `number=null` 的**假 section 锚**（实测 `SEC [(None,'Figure 0：概念框架图'), ('2.1','Results')]`）。这使「喂题注前后 `sections` 逐条相同」这条不变式**只在全部注册行都用半角分隔符时成立**。假 section 无编号，且第 2 层通读时一眼能看出那是图题注不是小节标题 → **不产假阳**，只是 `outline.json` 的候选清单多一条噪声。
     **只取匹配 `^## Figure N:` 的注册标题行、绝不 `cat` 整份登记表**（整份会多出一条假 section「Figure Index」，且 `- Type:`/`- Section:`/`- Key Message:`/`- Caption:`/`- Node mapping:` 五类登记字段行会被当成正文里的图/节引用）。**表题注就写在正文里、不需要合并，别把表也塞进本流程。** 落点固定 `tmp/xref_corpus.md`、`outline.json` 落项目根，**两者绝不落 `drafts/`**（`drafts/section_*.md` 是 managed_globs，写进去会被 signoff hook 物理拦截）；本步只读 `exports/`，**不写 `exports/` 下任何文件**（正文修改只发生在 HALT 后的用户裁决环节）。
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

**触发时机：** Phase 4 导出完成后（`phase=4, completed=true`）。Write 与 Polish 两模式都执行。
**Entry: Read `outline.md` + `state.json`. If `phase=5, completed=true` → already done, skip.**
> **Phase gate:** `phase < 4` 或 Phase 4 未 completed → HALT，提示先完成 Phase 4 导出。

**📖 进入本阶段必读：**
1. `references/submission_checklist.md`（综述版投稿清单 + 强制/询问分级 + 红线 + 产出路径）
1b. **`references/cover-letter-guide.md`（综述版 cover letter 写法必读）**：四段结构 / Innovation≠Contribution（综述落在框架层）/ **期刊 scope 契合强制**。写 `exports/cover_letter.md` 前必读。
2. `references/presubmission_checklist.md`（投稿前作者自检清单，**soft 提醒不阻断**）：终稿交付前对照逐项自查，重点是机器无法可靠裁决、需作者掌握原始数据/图像/外部工具的项（图像不当处理、Source Data、查重、注册号、报告规范附件、投稿材料齐全等）。已被本技能 hard 门禁覆盖的维度不重复，仅提醒，不阻断交付。

### 强制 / 询问分级（不静默留白）

| 件 | 级别 | 无内容时的处理 |
|----|------|---------------|
| Cover Letter / Title Page / CRediT / COI / Funding / DAS / Keywords(3–6) | **强制** | COI/Funding/DAS 无则按 submission_checklist 标准句声明"无"，不留空 |
| ORCID / Acknowledgements 致谢对象 | **询问** | 向用户索取；未提供 → 显式标 "not provided" / 各类 N/A |
| Highlights / Suggested·Opposed Reviewers | **按目标刊** | Cell 系等要求时给；Reviewers 须逐一核 COI 回避，严禁伪造邮箱 |

### 步骤

1. **逐项询问**（不要静默用空白）：通讯作者信息 + ORCID、各作者 CRediT role、COI、Funding（funder + grant number）、致谢对象、目标刊是否要 Highlights / Suggested Reviewers。明细见 submission_checklist.md 第 1 节。

2. **生成投稿包**（写入 `exports/`，路径以 submission_checklist.md 第 6 节为准）：
   - `exports/cover_letter.md` — 写法见 `references/cover-letter-guide.md`。综述卖点是 synthesis/framing/gap→展望；引用 Phase 1.5 gap + Phase 1.6 framing 作为"为何此刻需要这篇综述"。**🔴 scope 契合段强制**：向用户索取目标刊 **Aims & Scope 原文**（技能不自动抓取），据此写具体契合论证，禁 "will interest the broad readership" 类通用套话；用户未给 scope 原文则停下索取，不编造。
   - `exports/title_page.md` — 题名（禁缩写）/ 作者 / 单位 / 通讯(含邮箱) / ORCID。
   - `exports/author_contributions.md` — CRediT（完整 14 类逐条认领，未覆盖的标 N/A 并说明；角色清单与综述适用性见 `references/submission_checklist.md` 第 2 节）。
   - `exports/coi_statement.md` — 无则 "The authors declare no competing interests."
   - `exports/funding.md`（可并入 title page）— 无则 "This work received no specific external funding."
   - `exports/data_availability.md` — 综述无原始数据 → "Data sharing not applicable — no new datasets were generated or analysed."（systematic 有提取数据则给获取方式）。
   - `exports/keywords.md` — 3–6 个，不照抄标题词。
   - `exports/acknowledgements.md` — 各类别（非作者贡献者/技术平台/讨论反馈），无则 N/A。
   - `exports/highlights.md`（按目标刊）/ `exports/suggested_reviewers.md`（按需，逐一核 COI 回避）。

3. **合规核对**（综述相关项）：署名 ICMJE 四准则、Reviewer COI 回避；伦理/注册号/统计报告对 narrative 综述标 N/A，仅 systematic/scoping 走 PRISMA。细则见 submission_checklist.md 第 3–4 节。

4. **DoD 自检（gate `submission-pack-dod`，委托独立subagent盲检）：**
   ```bash
   python3 scripts/delegate_review.py pack --checklist references/dod_checklist.json \
     --gate submission-pack-dod \
     --files exports/cover_letter.md exports/title_page.md exports/author_contributions.md \
             exports/coi_statement.md exports/keywords.md --workdir .
   python3 scripts/delegate_review.py verify --checklist references/dod_checklist.json \
     --gate submission-pack-dod --return .review_return_submission-pack-dod.json
   # 退出码非 0 = fail-closed，据subagent证据修复后重跑，未过不得声明完成
   ```
   gate 5 项：S1 强制件齐全（Cover Letter+Title Page+CRediT+COI+Keywords）/ S2 COI·Funding·DAS 非空（无则声明无）/ S3 Keywords 3–6 且不与标题雷同 / S4 通讯作者一致 / S5 无占位符·无伪造。真源见 `references/dod_checklist.json`。

5. **更新 state + Git Checkpoint：**
   ```bash
   python3 scripts/state_manager.py set-phase --phase 5 --completed true
   git add -A && git commit -m "[review] Phase 5: submission pack" --allow-empty-message 2>/dev/null || true
   ```

**完成。向用户交付投稿包，列出已生成文件与询问级标 N/A 的项。**

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
| Mid-search crash | state.json `completed_sections` tracks progress; resume skips done |
| PubMed CLI + paper-search MCP both unavailable | HALT; suggest install edirect or enable paper-search MCP; do NOT fallback to websearch/tavily |

---

## Scripts Reference

> 📖 完整 CLI 参数和用法详见 `references/scripts_reference.md`

18 个活跃脚本（`[project]/scripts/`，Phase 0 init 时全量镜像 `scripts/*.py`，除 `test_*.py` 与 `init_project.py`）：
`zotero_manager.py` | `state_manager.py` | `matrix_manager.py` | `word_counter.py` | `validate_citations.py` | `citation_guard.py` | `check_global_citation_sequence.py` | `export_bibtex.py` | `prewrite_gate.py` | `delegate_review.py` | `style_checker.py` | `proofread.py` | `abbreviation_consistency.py` | `consolidate_references.py` | `export_docx.py` | `make_reference_docx.py` | `citation_utils.py`（import-only） | `citation_guard_core.py`（import-only）

> `scripts/init_project.py` 是 Phase 0.5 一次性脚手架（从 SKILL_DIR 运行，不复制进项目），负责创建目录/全量镜像上述脚本/写 state.json+outline.md/git init。`state_manager.py` 新增 `set-phase` / `complete-section` 子命令管理 workflow `state.json`。

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
