---
name: general-sci-writing
description: >
This Skill is a structured manuscript collaboration system specifically engineered for researchers. Far more than a simple text generator, it functions as a comprehensive academic writing engine built on atomic file management, rigorous citation verification, and logical consistency maintenance. It is designed to assist users in crafting high-impact Articles that meet the stringent publication standards of top-tier journals.
---


# General SCI Writing Skill (v2.20.0)

## Purpose
This skill is for long-form academic manuscript writing with strict state consistency.
Primary goals:
- no memory loss across turns
- no token explosion during context loading
- stable citation/index consistency after each writing turn
- multi-disciplinary research field support

## Research Field Configuration System (v2.16.2)

This version introduces a configurable research field system that supports multiple academic disciplines.

### Available Fields

| Field ID | Name | Description |
|----------|------|-------------|
| `default` | General Academic |适用于大多数学科 |
| `drug_delivery` | Drug Delivery System | 纳米药物、基因治疗等 |
| `clinical_pharmacy_llm` | Clinical Pharmacy & LLM | 临床药学、AI交叉 |
| `computer_science` | Computer Science | 机器学习、系统等 |
| `quantitative_pharmacology` | Quantitative Pharmacology | PK/PD建模等 |

### Using Configuration Manager

```bash
# List all available fields
python scripts/config_manager.py list

# Load a specific configuration
python scripts/config_manager.py load drug_delivery

# Validate a configuration
python scripts/config_manager.py validate drug_delivery

# Create a custom configuration
python scripts/config_manager.py create my_field "My Research Field"
```

### Custom Configuration

Users can add custom configurations in:
1. Project directory's `configs/` subdirectory
2. User directory `~/.general-sci-writing/configs/`

Custom configurations have higher priority than built-in ones.

## Canonical Workflow (Required)
Use `write-cycle` as the only entry point.

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
python scripts/merge_manuscript.py --manuscript-dir manuscripts
python scripts/merge_manuscript.py --manuscript-dir manuscripts --skip-docx
python scripts/export_bibtex.py --index-file literature_index.json --output-file references.bib
```

## Safety Defaults
- `write-cycle` uses strict preflight by default.
- literature apply is blocked if `dedup_conflicts` exists.
- apply only proceeds if you explicitly pass `--allow-conflicts`.
- md rewrite is default; docx rewrite is opt-in with `--rewrite-docx`.

## Citation Integrity Defaults
- `citation_guard.py` now enforces provider family allowlist: only `pubmed-cli` and `paper-search` are accepted.
- `tavily` is only for reverse verification of literature authenticity, never a retrieval/ingestion source; any entry with `source_provider=tavily` is rejected.
- Any bidirectional verification failure (`title_mismatch`, DOI/PMID mismatch, id mismatch) forces `verified=false` and routes the entry to `manual_review_queue.json`.
- Entries without `source_provider` / `source_id`, or with `needs_manual_review=true`, must not be cited in manuscript text or emitted into the final references list.
- If `citation_guard.py` exits non-zero or report `ok=false`, writing must stop until `manual_review_queue.json` is resolved.

## Runtime Files and Why They Exist
- `.state/write_gate.json`: hard-gate state (prewrite/complete guard)
- `.state/lit_sync_preview.json`: latest dry-run preview payload
- `.state/reports/lit_sync_*.json`: persisted dry-run/apply/error reports
- `.state/load_cache.json`: incremental load cache to reduce repeated payload size

These are runtime artifacts, not manuscript content.

## Tests
Regression tests live in:
- `tests/test_state_manager.py`
- `tests/test_citation_guard.py`

Run:
```bash
python3 -m py_compile scripts/citation_guard.py scripts/state_manager.py
python3 -m unittest discover -s tests -p 'test_*.py' -q
```

## Directory Intent
- `scripts/`: executable workflow logic
- `references/`: on-demand reference docs loaded by SKILL.md phases (anti-AI protocol, stat tree, submission guide, writing templates, figure protocol)
- `templates/`: initialization/reference templates
- `configs/`: research field configurations
- `tests/`: regression coverage for state manager
- `manuscripts/` (in project workspace, not skill root): actual section drafts

## Version
- Current: `2.20.0`
