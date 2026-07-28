# General SCI Writing Skill - Test Checklist (v2.20.0)

## Scope
This checklist validates the current hard-gate + section-local + citation-sync behavior, plus the tightened citation provider and manual-review policy.

## Must-Pass Commands
- `python3 -m py_compile scripts/citation_guard.py`
- `python3 -m py_compile scripts/state_manager.py`
- `python3 -m unittest discover -s tests -p 'test_*.py' -q`

## Functional Checks
- [x] hard-gate rejects manual `preflight + load` path for `prewrite` phase
- [x] `write-cycle` establishes valid prewrite gate
- [x] `write-cycle --finalize` can complete gate when sync apply succeeds
- [x] `sync-literature --dry-run` outputs preview and report file
- [x] `sync-literature --apply` rewrites in-text references and strict rebuilds References
- [x] range citations like `[1-4]` are correctly remapped
- [x] table citations like `| Ref | [3] |` are correctly remapped
- [x] dedup conflict blocks apply by default
- [x] `--allow-conflicts` can explicitly bypass conflict block
- [x] rollback restores previous state on validation failure
- [x] backup retention (`--backup-keep`) works
- [x] cache invalidates when source files change
- [x] reference style `nature` renders expected output form
- [x] `set-field` persists active field config and reviewer concerns
- [x] unknown provider family is rejected by `citation_guard.py`
- [x] Tavily entries are rejected as a source (any `source_provider=tavily`, with or without DOI/PMID)
- [x] Tavily reverse-verification backend (`_extract_tavily_title`, title cross-check) remains functional
- [x] bidirectional verification failure forces `verified=false` and manual confirmation
- [x] `citation_guard_report.json` exposes provider policy

## Non-Functional Checks
- [x] section-local load uses cache and budget trimming
- [x] runtime artifacts are isolated in `.state/`
- [x] report/cache retention prevents unbounded growth

## Current Automated Coverage
Implemented in:
- `tests/test_state_manager.py`
- `tests/test_citation_guard.py`

Covered tests:
- `test_gate_requires_write_cycle_origin`
- `test_strict_rebuild_renumbers_ranges_and_tables`
- `test_rollback_on_validation_failure`
- `test_backup_retention_keep_latest_n`
- `test_nature_reference_style_rebuild`
- `test_conflicts_block_apply_unless_allowed`
- `test_load_cache_invalidation_after_source_change`
- `test_write_cycle_default_is_strict`
- `test_set_field_persists_active_configuration`
- `test_main_report_exposes_provider_policy`
- `test_rejects_non_allowed_provider_family`
- `test_rejects_tavily_entries_with_identifier`
- `test_tavily_without_identifier_requires_manual_review`
- `test_bidirectional_failure_forces_manual_confirmation`

## Result
- Status: PASS (20 tests)
