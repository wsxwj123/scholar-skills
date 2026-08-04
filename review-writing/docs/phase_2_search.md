# Phase 2: 系统主检索（Systematic Main Search）+ Real-Time Write

> （探索性检索已在 Phase 1.5 完成，本阶段是系统化主检索。）

**Start: Read `outline.md` + `state.json`. Skip sections already in `searched_sections`（检索完成标记；`completed_sections` 是 Phase 3 的写作完成标记，两者独立）.**
> **主线依据（防丢主线）：** 开写前 Read `data/research_gap.json`，取 `selected` 的 gap/选题方向作为本轮检索与写作的综述主线，确保不偏离 Phase 1.5 选定的核心 gap。
> **Phase gate:** if `state.json` does not exist or `phase < 1.7`（提纲未据调研建立/未落结构签字）→ HALT; tell user "先完成 Phase 1.5（研究空白）→ 1.6（对标框架）→ 1.7（据调研建提纲 + 结构签字），系统主检索按提纲逐节进行"; do not proceed.

### Search Priority by Discipline

> Use the **Search Tool Priority (Universal)** table above (§ Search Tool Priority). Primary = PubMed CLI for Medical/Bio/Interdisciplinary, paper-search MCP for CS/AI; fallback is the other; `websearch`/`tavily` are forbidden in all disciplines.

### Per-Section Search Loop
```
for each section in outline.md (e.g., section ID = "2.1"):
  SECTION_FILE="tmp/papers_2_1.json"   # replace dots with underscores in section ID

  1. Check state.json → if section in searched_sections, SKIP (存量项目无该键 = 空列表，全部照常检索)
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
     同一次还会落 `article_type`（批量取 PubMed pubtype，100 条/请求）。stderr 若出现 `ARTICLE_TYPE: N/M 条没取到文献类型` → 那 N 条的「机制/疗效结论不得只挂综述」纪律这次没执行（按 unknown 跳过）；老项目一次性补齐用 `--backfill-article-type`（只改这一个字段）。
     🔴 **这一步是 DoD R2b 的唯一证据来源**：绝不能图快加 `--offline`（离线判不出编造文献），也不能省 `--write-back`（逐条 checked_at 落不下）。少任一个，Phase 3 每节盲检的 R2b 都会 fail。
  7. Confirm write success → update state.json (add section to searched_sections):
     python3 scripts/state_manager.py complete-search --section X.X
     # Adds X.X to searched_sections (idempotent), preserves all other keys.
     # 🔴 检索完成 ≠ 写作完成：completed_sections 只归 Phase 3 写完的节（complete-section），
     #    这里绝不能用 complete-section，否则 Phase 3 会把全部节当已写完跳过。
  8. Git Checkpoint (见复用块, msg: [review] Phase 2: section X.X search complete)
  9. Continue to next section
```

**Global target:** ≥100 papers total (before dedup). If a section yields <10 papers, warn and prompt user to broaden keywords.

**Per-subsection density（按标题层级，prewrite_gate check3 硬拦）:** level = section_id 段数+1（`2.1`=三级、`2.1.1`=四级）。硬地板：三级叶子节 ≥6 条、四级叶子节 ≥3 条，其余层级 ≥1；低于地板 prewrite_gate exit 1 禁止开写。容器父节（大纲里还有更深子节的节，如 `2.1` 下有 `2.1.1`）本身不承载文献，放宽到 ≥1。软目标：三级 ≥10、四级 ≥5，未达只进 warnings 提示补足、不阻断。

**数量与"做没做"是两根轴，不重复**：条数够不够由 check3（上面这段）管；本节的系统主检索**跑没跑过**由 prewrite_gate 的 `section_search_done` 管——它只看本节有没有 `tmp/papers_X_X.json`（非空数组）或 `data/search_log.json` 里归属本节的条目，**不设任何数量阈值**。所以领域本来就小、这节只搜到两篇，只要检索跑过就照常放行；反过来，把 Phase 1.5 探索检索那批文献挨个打上节号凑够条数，`section_search_done` 照样拦。

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
# Sets phase=2 only; completed_sections / searched_sections / zotero_root_key / mode / pending_sections preserved.
```

**Git Checkpoint** (见复用块, msg: `[review] Phase 2.5: dedup + global ID assigned`)
