# Scripts Reference

All scripts are in `[project]/scripts/` (copied from skill directory during Phase 0 init).

## Script Overview

| Script | Purpose | Mode |
|--------|---------|------|
| `zotero_manager.py` | Zotero Web API: init, add, dedup, get-section, export BibTeX | Zotero |
| `state_manager.py` | Workflow state.json (`set-phase`/`complete-section`/`set-root-key`), None-mode index ops (`init-index`/`append-literature`), canonical dedup + reindex | All / None |
| `citation_utils.py` | **Import-only library, no CLI.** Shared citation-token parser (`extract_citation_ids`, `parse_citation_group`) imported by `citation_guard.py`, `validate_citations.py`, `check_global_citation_sequence.py`, `export_bibtex.py`. Never invoke directly — `python3 scripts/citation_utils.py` will run and exit silently. | All |
| `export_bibtex.py` | BibTeX export from literature_index.json | None/EndNote |
| `matrix_manager.py` | Section-claim evidence matrix: bootstrap + focus | None |
| `word_counter.py` | Count words/chars in draft files | All |
| `style_checker.py` | Anti-AI style gate (DoD R5): forbidden words, >30-word sentences, passive >30%, em-dash, scare quotes, explanatory colon, trailing -ing. `--passive-max` configurable (review default 0.30) | All |
| `validate_citations.py` | DOI/PMID online validation | All |
| `citation_guard.py` | Anti-hallucination guard | All |
| `check_global_citation_sequence.py` | Verify global [1..N] citation continuity | All |

## `state_manager.py` commands

```bash
# reindex (None Mode — Phase 2.5): canonical dedup + reindex literature by section order + remap draft citations:
python3 scripts/state_manager.py reindex \
  --storyline outline.md --index data/literature_index.json \
  --matrix data/synthesis_matrix.json

# set-phase (all modes — Phase 2.5/3/4): set workflow phase in state.json, preserving every other key.
python3 scripts/state_manager.py set-phase --phase 4 --completed true   # --completed optional (Phase 4 final)

# complete-section (all modes — Phase 2/3): add a section to completed_sections AND drop it from any
# pending_sections bucket (Polish Mode), preserving other keys. Idempotent.
python3 scripts/state_manager.py complete-section --section 2.1

# set-root-key (Zotero mode — Phase 1 Step 6): set zotero_root_key in state.json, preserving other keys.
python3 scripts/state_manager.py set-root-key --key ROOT_KEY

# init-index (None/EndNote mode — Phase 1 Step 5): create empty literature_index.json +
# synthesis_matrix.json + figures/figure_index.md. Idempotent (existing files untouched).
python3 scripts/state_manager.py init-index

# append-literature (None/EndNote mode — Phase 2 Step 5): append a section's papers to
# literature_index.json with gid auto-increment + DOI dedup (case-insensitive). On a duplicate DOI,
# only the section is appended to that record's related_sections.
python3 scripts/state_manager.py append-literature --section 2.1 --papers tmp/papers_2_1.json
```

### Related-Sections 字段规则（append-literature / --add-batch 共用）

每条记录必须用 `related_sections`（array），不用 `section`（string）。一篇论文可同时属于多个节次：

```json
"related_sections": ["2.1", "3.1", "4.1"]
```

`--add-batch` 对重复 DOI 自动 append 到 `related_sections`（不覆盖）；Zotero 侧同一 item 链接到多个集合。**不要强制单节归属。**

### Phase 2 入库前相关性筛选（不得"搜到即入库"）

每篇论文入库前按标题/摘要判断：

| 排除条件 | 标记 |
|---------|------|
| 语言（非英文/中文） | `excluded: language` |
| 话题偏离本节 RQ/PICO | `excluded: off_topic` |
| 无同行评审且非顶级 preprint | `excluded: quality` |
| 发表年份过早且无奠基价值 | `excluded: outdated` |

最终保留的才进入 `tmp/papers_X_X.json`。

```bash
# check-pending (Phase 4 entry gate): exit 1 if Polish Mode pending sections remain.
# Write Mode: always passes (no pending_sections field → empty dict → pass).
python3 scripts/state_manager.py check-pending

# count-citations (Phase 4 Step 2, 引用总量校验): count unique [N] IDs across drafts/, non-blocking warning.
python3 scripts/state_manager.py count-citations --drafts-dir drafts --threshold 150

# append-search-log (Phase 2 per-section, 改动B 检索可复现): record search provenance to data/search_log.json.
python3 scripts/state_manager.py append-search-log \
  --section 2.1 --query "QUERY STRING" --database pubmed \
  --n-hits 342 --n-screened 18
```

> `set-phase` / `complete-section` / `set-root-key` operate on the workflow `state.json` (the `{phase,
> completed_sections, mode, pending_sections, zotero_root_key, citations_imported}` record), which is
> **disjoint** from the `STATE_FILES` map (`progress.json`/`storyline.md`/`literature_index.json`/…) that
> `load`/`update`/`reindex` touch — so these commands cannot affect dedup/reindex. They replace the repeated
> inline "load json → set key → write" Python that previously lived in Phase 1/2/2.5/3/4. Default path is
> `state.json` in CWD; override with `--state PATH`. Phase 0.5 init and Phase 0-P Step 6 still build state.json
> inline (they create the file / write multiple keys at once, not a single-field update).
> `init-index` / `append-literature` operate on the None/EndNote `data/literature_index.json` (+ matrix/figure
> registry) and replace the large inline Python that previously lived in Phase 1 Step 5 and Phase 2 Step 5.

## `matrix_manager.py` commands (None Mode)

```bash
# Phase 2 Step 5b — bootstrap matrix after adding papers for a section:
python3 scripts/matrix_manager.py bootstrap \
  --index data/literature_index.json \
  --matrix data/synthesis_matrix.json \
  --section X.X --round 1

# Phase 3 Step 1 — load evidence context before writing a section:
python3 scripts/matrix_manager.py focus \
  --matrix data/synthesis_matrix.json \
  --section X.X
```

## `citation_guard.py` command

```bash
# Phase 2 (per-section, lightweight):
python3 scripts/citation_guard.py \
  --index data/literature_index.json \
  --log data/citation_guard_report.json

# Phase 4 (final delivery, full validation):
python3 scripts/citation_guard.py \
  --index data/literature_index.json \
  --log data/citation_guard_report.json \
  --write-back \
  --manual-review data/manual_review_queue.json
# --write-back   : persists verified:true/false back into literature_index.json
# --manual-review: dumps unverifiable entries to a JSON queue for human review
# --require-mcp  : hard-gate — blocks if any entry lacks MCP evidence (use only for top-tier journals)
# --offline      : skip online checks (fast mode, local index only)
```

## `word_counter.py` command

```bash
python3 scripts/word_counter.py --file drafts/section_01_01.md --language en
# --language cn: counts Chinese characters (CJK), goal 15,000–20,000 chars
# --language en: counts English words (whitespace split), goal 7,000–10,000 words
# Read language setting from outline.md and pass accordingly.
```

## `validate_citations.py` command (Phase 4 — pre-export consistency check)

```bash
python3 scripts/validate_citations.py \
  --drafts-dir drafts \
  --index-path data/literature_index.json \
  --live --live-used-only \
  --fail-on-orphan --retries 2
# --drafts-dir       : directory to scan for [N] citations (default: drafts)
# --index-path       : literature_index.json path (default: data/literature_index.json)
# --live             : enable online DOI/PMID verification (skip in offline mode)
# --live-used-only   : with --live, only validate gids actually cited in drafts
#                       (saves API calls — skip orphan entries)
# --timeout 8        : HTTP timeout per live check (default: 8s)
# --retries 2        : transient-error retry count (default: 2)
# --retry-backoff 0.6: base backoff seconds between retries (default: 0.6)
# --fail-on-orphan   : exit non-zero if any [N] in drafts has no matching index entry
# --fail-on-live     : exit non-zero if any live DOI/PMID check fails
# --fail-on-trace    : exit non-zero if source traceability gaps exist
# Difference from citation_guard.py: validate_citations cross-checks drafts ⟷ index;
# citation_guard validates the index itself (independent of drafts).
```

## `zotero_manager.py` command reference

| Command | Function |
|---------|---------|
| `--status --lib-id X --api-key Y` | Test connection, list libraries and existing collections |
| `--status --find-root-title "T" --lib-id X --api-key Y` | Idempotent root-collection probe (used in Phase 1 / Phase 0-P Step 5 before `--init`). Exact-match lookup by top-level collection name. **Exit codes:** `0` → exactly one match, prints its key to stdout (capture as ROOT_KEY); `3` → no match (caller should run `--init`); `4` → ambiguous, prints all candidate keys (ask user to pick). Optional `--json` applies to `--status` only, not this probe. |
| `--init --title "T" --outline outline.md --lib-id X --api-key Y` | Create root + subcollection tree from outline |
| `--add-batch --section "2.1" --papers tmp/papers_2_1.json --root-key ROOT_KEY --index data/literature_index.json --lib-id X --api-key Y` | Safe upsert (3 branches): ① paper already in Zotero (has zotero_key) → link to section collection only, gid unchanged; ② paper in local index but NOT yet in Zotero (no zotero_key, e.g. Polish Mode import) → create Zotero item using existing gid, back-fill zotero_key; ③ paper not in index at all → create Zotero item + new gid, append to local index. `--root-key` scopes all collection lookups to the current project's root collection, preventing cross-project contamination when multiple reviews share the same Zotero library. |
| `--dedup --scope ROOT_KEY --lib-id X --api-key Y` | **Repair only** — deduplicate within root collection scope; assigns gid:N; do NOT use in normal workflow (--add-batch already deduplicates at write time) |
| `--get-section "2.1" --lib-id X --api-key Y` | Return section paper list (gid, title, authors, year, abstract) |
| `--export-bibtex --output refs.bib --root-key ROOT_KEY --lib-id X --api-key Y` | Generate .bib with citation keys ref_N; `--root-key` scopes export to current project (without it, exports entire library) |
