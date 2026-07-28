# General SCI Writing Skill - 快速参考卡片 (v2.20.0)

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

## 研究方向配置
```bash
python scripts/config_manager.py list
python scripts/config_manager.py load computer_science
python scripts/config_manager.py validate drug_delivery
python scripts/state_manager.py set-field --field quantitative_pharmacology
```

可用内置字段：
- `default`
- `drug_delivery`
- `clinical_pharmacy_llm`
- `computer_science`
- `quantitative_pharmacology`

## 回复协议
- Part 1 `执行内容`：始终对用户可见。
- Part 2 `状态仪表盘`：默认内部维护；只有用户明确要求“显示审计日志/加载明细”时才显式输出。
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

## 自动化回归
- `python3 -m py_compile scripts/citation_guard.py scripts/state_manager.py`
- `python3 -m unittest discover -s tests -p 'test_*.py' -q`

## 版本
- Current: `2.20.0`
- Last updated: `2026-06-11`
