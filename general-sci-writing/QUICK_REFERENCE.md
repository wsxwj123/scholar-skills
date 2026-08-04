# General SCI Writing Skill - 快速参考卡片

> 完整流程见 `SKILL.md`（Phase 0–16）；本卡片只列高频命令。
> 版本号只写在 `SKILL.md` frontmatter 的 `version:` 一处，本文件不再另写。
> 下面所有命令都在**项目根目录**下跑，且项目已走完 Phase 0 `/init`。

## 核心定位
- 面向多学科 SCI Article 写作。
- 共享统一的 `write-cycle` / `citation_guard` / `set-field` 基础设施。
- 默认严格门禁：先核验文献，再写正文，再做引用同步。

## 快速开始
```bash
# 1) 选择研究方向（默认可跳过，使用 default）
python scripts/state_manager.py set-field --field default

# 2) 写作前加载当前章节上下文
python scripts/state_manager.py write-cycle --section results_3.1 --token-budget 6000 --tail-lines 80

# 3) 最终落盘并同步引用
python scripts/state_manager.py write-cycle --section results_3.1 --finalize --refs-confirmed --sync-literature --sync-apply --strict-references --summary "..."
```

## 文献核验硬门禁
```bash
python scripts/citation_guard.py \
  --index literature_index.json \
  --mcp-cache mcp_literature_cache.json \
  --mcp-ttl-days 30 \
  --manual-review manual_review_queue.json \
  --log verification_run_log.json \
  --report citation_guard_report.json
```

- 只允许 `pubmed-cli` 与 `paper-search` provider family。
- `tavily` 仅用于文献真实性的反向核验，不得作为检索/入库来源。
- 任何 `source_provider=tavily` 的条目一律失败（带 DOI/PMID 也不例外）。
- `title_mismatch`、`doi_invalid_or_unresolved`、`pmid_invalid_or_unresolved`、`id_mismatch` 都会强制 `verified=false` 并进入 `manual_review_queue.json`。
- `manual_review_queue.json` 非空、`ok=false` 或命令非零，正文写作必须中断。
- 🔴 **绝不加 `--offline`**：离线跳过联网核验，编造的 DOI+PMID 只要字段齐全照样过。

## 研究方向配置
🔴 `config_manager.py` 的子命令后面必须用 `--field`，直接跟名字会 exit 2。

```bash
python scripts/config_manager.py list
python scripts/config_manager.py load --field computer_science
python scripts/config_manager.py validate --field drug_delivery
python scripts/state_manager.py set-field --field quantitative_pharmacology
```

内置字段以 `config_manager.py list` 实际输出为准，当前为：
`default` / `drug_delivery` / `clinical_pharmacy_llm` / `computer_science` /
`quantitative_pharmacology` / `biomedical_pharma`

## 回复协议
- Part 1 `执行内容`：始终对用户可见。
- Part 2 `状态仪表盘`：默认内部维护；只有用户明确要求"显示审计日志/加载明细"时才显式输出。
- Part 3 `深度交互`：始终对用户可见。
- `Context Check`、进度读取日志、加载细节禁止写入正文原子文件。

## 常用命令
```bash
python scripts/state_manager.py word-count
python scripts/state_manager.py stats
python scripts/state_manager.py rollback --target snapshot
python scripts/merge_manuscript.py --manuscript-dir manuscripts --skip-docx
python scripts/export_bibtex.py --index-file literature_index.json --output-file references.bib
```

## Phase 10 `/check` 门禁一览（详细阻断条件见 SKILL.md）
```bash
python scripts/state_manager.py stats                                   # 1 字数
python scripts/state_manager.py sync-literature --dry-run --strict-references   # 2 引用号
python scripts/citation_guard.py --index literature_index.json --report citation_guard_report.json  # 3 文献
python scripts/style_checker.py --manuscript-dir manuscripts --report style_check_report.json --threshold 70 --journal <target_journal>  # 4 去 AI
python scripts/proofread.py --manuscript-dir manuscripts --report proofread_report.json --threshold 70   # 4c 校对
python scripts/abbreviation_consistency.py --root .                     # 7 缩略词
python scripts/cross_section_consistency.py --root . --reconcile-sections  # 8 section 对账
```
`--journal` 取 `project_config.json` 的 `target_journal`（storyline.json 里没这个字段）。
步骤 9–11（数值 / 交叉引用 / 方法学三层核查）是多子代理流程，只能照 SKILL.md 走，
临时产物统一落项目根下的 `.state/check/`。

## 自动化回归
```bash
python3 -m py_compile scripts/citation_guard.py scripts/state_manager.py
```
`scripts/test_*.py` 是本机开发自测，不随包分发（见 README「Tests」）。
