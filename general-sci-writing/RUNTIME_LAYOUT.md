# Runtime Layout

## Why this file exists
分清楚**哪些文件是脚本自己生成的**（可以随手删、别手改、别提交）、
哪些是你的稿子（丢了就没了）。
下面这份清单是 2026-08-04 在一个真项目上从 `/init` 跑到 `/check` 实测出来的，
不是凭印象列的。

## Runtime Artifacts（脚本生成，可删可重建）

**门禁与缓存（`.state/` 下，`.gitignore` 已排除整个目录）**
- `.state/write_gate.json` —— prewrite/complete 硬门禁状态
- `.state/load_cache.json` —— 增量加载缓存，压 payload 体积
- `.state/lit_sync_preview.json` —— 最近一次 dry-run 的预览
- `.state/reports/lit_sync_*.json` —— dry-run / apply / error 报告留存
- `.state/transactions/*.json` —— 写操作事务日志
- `.state/locks/` —— 文件锁
- `.state/check/` —— Phase 10 步骤 9–11 的临时工作目录
  （`_numeric_fulltext.md` / `numeric_candidates.json` / `outline.json` /
  `methods_terms.json` / 各 `*_verify_checklist.json`），跑完可整个删

**备份（`backups/` 下，`.gitignore` 已排除）**
- `backups/snapshot_<时间戳>/` —— `snapshot` 与"整文件覆盖前拍回退点"产生
- `backups/literature_sync/lit_sync_*/` —— 引用同步 apply 前的备份

**项目根下的报告与缓存**
- `env_status.json` —— `env_preflight.py` 的环境预检结果
- `active_field_config.json` —— `set-field` 落的当前研究方向配置
- `style_check_report.json` / `proofread_report.json` —— 去 AI 与校对报告
- `citation_guard_report.json` / `verification_run_log.json` /
  `manual_review_queue.json` / `mcp_literature_cache.json` —— 文献核验四件
- `references.bib` —— `export_bibtex.py` 导出
- `.review_pass/<节>.json` / `.review_return_*.json` —— 盲检门的任务包与回执
- `structure_signoff.json` —— 结构签字锁（**别手删**，删了正文写作会重新被锁住）
- `decisions_log.md` —— `session_journal.py` 的决策流水

> 报告类文件（`style_check_report.json` / `citation_guard_report.json` /
> `verification_run_log.json`）在技能自己的 `.gitignore` 里；你的项目仓库要不要
> 提交它们自己定，但它们随时可由脚本重跑重建。

## Manuscript / State Files（你的东西，丢了没有）
项目根下：
- `project_config.json`、`storyline.json`、`writing_progress.json`、`context_memory.md`
- `literature_index.json`、`literature_matrix.json`、`figures_database.json`、`si_database.json`
- `abbreviations.json`、`reviewer_concerns.json`、`version_history.json`
- `manuscripts/*.md`（正文原子文件）、`figure_analysis/*.md`、`section_memory/*.md`
- `reviews/revision_plan.json`、`reviews/mentor_plan.json`、`submission/submission_state.json`

## Skill Source Files（技能本体，别在项目里改）
- `SKILL.md`、`README.md`、`QUICK_REFERENCE.md`、`CHANGELOG.md`、本文件
- `scripts/*.py`、`references/*.md`、`configs/*.json`、`templates/*`

`/init` 会把 `scripts/` `configs/` `references/` 拷进项目一份（项目自包含）；
技能升级后用 `/upgrade-scripts` 同步，别手工对拷。
