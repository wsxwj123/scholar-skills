---
name: general-sci-writing
description: >
This Skill is a structured manuscript collaboration system specifically engineered for researchers. Far more than a simple text generator, it functions as a comprehensive academic writing engine built on atomic file management, rigorous citation verification, and logical consistency maintenance. It is designed to assist users in crafting high-impact Articles that meet the stringent publication standards of top-tier journals.
---


# General SCI Writing Skill

> **真正的入口是 `SKILL.md`**（完整流程 Phase 0–16、门禁与阻断条件全在那里）。
> 本 README 只讲"这技能是干什么的 + 命令怎么敲"。
> **版本号只写在 `SKILL.md` frontmatter 的 `version:` 一处**，本文件不再另写一个数；
> 变更历史见 `CHANGELOG.md`。

## Purpose
This skill is for long-form academic manuscript writing with strict state consistency.
Primary goals:
- no memory loss across turns
- no token explosion during context loading
- stable citation/index consistency after each writing turn
- multi-disciplinary research field support

## Research Field Configuration System

### Built-in Fields

| Field ID | Name | Description |
|----------|------|-------------|
| `default` | General Academic | 适用于大多数学科 |
| `drug_delivery` | Drug Delivery System | 纳米药物、基因治疗等 |
| `clinical_pharmacy_llm` | Clinical Pharmacy & LLM | 临床药学、AI 交叉 |
| `computer_science` | Computer Science | 机器学习、系统等 |
| `quantitative_pharmacology` | Quantitative Pharmacology | PK/PD 建模等 |
| `biomedical_pharma` | Biomedical / Pharma | 医药领域研究 |

以 `python scripts/config_manager.py list` 的实际输出为准（含你自建的配置）。

### Using Configuration Manager

🔴 **子命令后面一律用 `--field`，不能直接跟名字**（argparse 只有 `--field` / `--name`
两个选项，写成位置参数会 `error: unrecognized arguments` 并 exit 2）。

```bash
# List all available fields
python scripts/config_manager.py list

# Load a specific configuration
python scripts/config_manager.py load --field drug_delivery

# Validate a configuration
python scripts/config_manager.py validate --field drug_delivery

# Create a custom configuration
python scripts/config_manager.py create --field my_field --name "My Research Field"
```

### Custom Configuration

Users can add custom configurations in:
1. Project directory's `configs/` subdirectory
2. User directory `~/.general-sci-writing/configs/`

Custom configurations have higher priority than built-in ones.

## Canonical Workflow (Required)

**前置**：下面所有命令都在**项目根目录**下跑（不是技能安装目录），且项目必须先走完
`SKILL.md` 的 Phase 0 `/init`——`storyline.json` 等状态文件不在时，`write-cycle`
严格预检会 exit 2 并提示 `Run /init to create them.`。

`write-cycle` 是写作期唯一入口。

1. Pre-write load (strict by default):
```bash
python scripts/state_manager.py write-cycle --section results_3.1 --token-budget 6000 --tail-lines 80
```

2. If continuing an existing section draft:
```bash
python scripts/state_manager.py write-cycle --section results_3.1 --include-draft --token-budget 6000 --tail-lines 80
```

3. Finalize this turn:
```bash
python scripts/state_manager.py write-cycle --section results_3.1 --finalize --refs-confirmed --sync-literature --sync-apply --strict-references --summary "..."
```

4. Word count (default excludes References):
```bash
python scripts/state_manager.py word-count
python scripts/state_manager.py word-count --section results_3.1
```

5. Stats and rollback:
```bash
python scripts/state_manager.py stats
python scripts/state_manager.py rollback --target snapshot
python scripts/state_manager.py rollback --target literature_sync
```

6. Merge and export references:
```bash
python scripts/merge_manuscript.py --manuscript-dir manuscripts --skip-docx
python scripts/merge_manuscript.py --manuscript-dir manuscripts
python scripts/export_bibtex.py --index-file literature_index.json --output-file references.bib
```
不带 `--skip-docx` 时会顺带导 docx；导 docx 依赖 pandoc 与 `templates/reference.docx`，
缺件时 md 照常生成、返回 JSON 的 `docx` 字段会写明原因。

## Safety Defaults
- `write-cycle` uses strict preflight by default.
- literature apply is blocked if `dedup_conflicts` exists.
- apply only proceeds if you explicitly pass `--allow-conflicts`.
- md rewrite is default; docx rewrite is opt-in with `--rewrite-docx`.

## Citation Integrity Defaults
- `citation_guard.py` enforces a provider family allowlist: only `pubmed-cli` and `paper-search` are accepted.
- `tavily` is only for reverse verification of literature authenticity, never a retrieval/ingestion source; any entry with `source_provider=tavily` is rejected.
- Any bidirectional verification failure (`title_mismatch`, DOI/PMID mismatch, id mismatch) forces `verified=false` and routes the entry to `manual_review_queue.json`.
- Entries without `source_provider` / `source_id`, or with `needs_manual_review=true`, must not be cited in manuscript text or emitted into the final references list.
- If `citation_guard.py` exits non-zero or report `ok=false`, writing must stop until `manual_review_queue.json` is resolved.

## Runtime Files
运行时产物清单（哪些是脚本生成的、哪些是你的稿子）见 `RUNTIME_LAYOUT.md`。

## Tests
技能**不随包分发测试**——`scripts/test_*.py` 是本机开发用的自测，被 `.gitignore`
排除，装到用户机上不存在，因此没有可对外承诺的 `unittest discover` 入口。
装完能自查的只有语法编译：

```bash
python3 -m py_compile scripts/citation_guard.py scripts/state_manager.py
```

本机开发时跑自测（文件在才有）：

```bash
cd scripts && for f in test_*.py; do python3 "$f" >/dev/null 2>&1 && echo "PASS $f" || echo "FAIL $f"; done
```

## Directory Intent
- `scripts/`: executable workflow logic
- `references/`: on-demand reference docs loaded by SKILL.md phases (anti-AI protocol, stat tree, submission guide, writing templates, figure protocol)
- `templates/`: initialization/reference templates
- `configs/`: research field configurations
- `manuscripts/` (in project workspace, not skill root): actual section drafts
