# Phase 0: Setup（收参数 → 检测环境 → 创建项目 → git init）

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
> **⚠️ `[DOD_CHECKLIST]` 取值规则：** `references/` 不镜像进项目，四道 DoD 盲检门（research-gap / benchmark-reviews / manuscript / submission-pack，含 Polish 的 split_boundary）的 `--checklist` 必须用**技能目录绝对路径**。该值由 `init_project.py` 打印（`DOD_CHECKLIST: <绝对路径>`），全程沿用；后文所有 `--checklist "[DOD_CHECKLIST]"` 都代入这个打印值。
>
> **Note:** Phase 0.5 only creates folder structure + copies scripts + writes state.json/outline.md. Zotero collection tree (`--init`) is NOT run here; it runs in Phase 1.7 (Write Mode, after the outline is built from research) or Phase 0-P Step 5 (Polish Mode). Phase 0.5 完成后进入 **Phase 1.5**（调研先于提纲）。

The script writes `[TITLE]/state.json`:
```json
{"phase": 0, "completed_sections": [], "zotero_root_key": ""}
```

…and the `[TITLE]/outline.md` template (AI fills Parameters/Environment fields after Phase 0.1–0.4). The template is auto-generated by `init_project.py`; do NOT recreate it manually. Key fields: Title / Target Journal / Language / Reference Manager / Review Type / Word Count Target / Citation Requirements / Discipline / os / git_available / pubmed_proxy / zotero_lib_id / search_fallback / subagent_model / RQ-PICO / Outline sections / Current Status.
