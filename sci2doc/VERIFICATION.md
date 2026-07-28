# VERIFICATION

## Scripts Inventory

| Script | Description | LOC (approx) |
|--------|-------------|---------------|
| `scripts/state_manager.py` | Central orchestrator: init/prewrite/postwrite/snapshot/rollback | 1820+ |
| `scripts/atomic_md_workflow.py` | Subsection management: validate/merge/self-check | 720+ |
| `scripts/check_quality.py` | Quality validation: fonts/spacing/structure/tables/figures | 1200+ |
| `scripts/abbreviation_registry.py` | Abbreviation lifecycle: extract/register/strip/validate | 840+ |
| `scripts/count_words.py` | Markdown word counting: file/chapter/full thesis | 590+ |
| `scripts/markdown_to_docx.py` | MD→Word conversion with built-in default formatting | 420+ |
| `scripts/merge_chapters.py` | Docx merging with TOC/header/footer | 380+ |
| `scripts/merge_documents.py` | Compatibility wrapper for merge | 50+ |
| `scripts/figure_registry.py` | Figure numbering: register/validate/cross-validate/export | 400+ |
| `scripts/thesis_profile.py` | Profile management | 110+ |
| `scripts/shared_utils.py` | Shared utilities | 95+ |

## Tests

测试在开发仓库维护，不随技能分发。本技能目录不包含 `tests/` 或 `scripts/test_*.py`。

## Documentation

- `SKILL.md` — Authoritative spec (16+ non-negotiable requirements, Word format, figure/abbreviation/table contracts)
- `README.md` — Usage guide with CLI examples
- `QUICK_START.md` — Quick reference

## Baseline Targets

- Body target >= 80,000 Chinese chars (configured in `thesis_profile.json`)
- Chinese abstract 1500-2500 chars
- Chapter targets negotiated and stored in profile
- Atomic markdown numbering validation required
- Chapter self-check required
- Subsection summary snapshot required
- Three-line table format enforced
- Abbreviation registry populated and cross-validated
- Figure numbering registry populated and cross-validated
