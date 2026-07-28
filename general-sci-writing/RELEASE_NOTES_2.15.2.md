# Release Notes 2.15.2

## Scope
This release focuses on reliability for long-running manuscript writing:
- no memory loss across turns
- no token explosion during context loading
- citation/index consistency after every writing turn

## Final Canonical Workflow
Use `write-cycle` as the mandatory entry.

1. Pre-write context load (strict by default):
```bash
python scripts/state_manager.py write-cycle --section results_3.1 --token-budget 6000 --tail-lines 80
```

2. Continue an existing draft (optional):
```bash
python scripts/state_manager.py write-cycle --section results_3.1 --include-draft --token-budget 6000 --tail-lines 80
```

3. Review citation sync changes before apply:
```bash
python scripts/state_manager.py sync-literature --dry-run --strict-references
```

4. Finalize this writing turn:
```bash
python scripts/state_manager.py write-cycle --section results_3.1 --finalize --sync-literature --sync-apply --strict-references --summary "..."
```

## Safety Defaults
- `write-cycle` uses strict preflight by default.
- Dedup conflicts block apply by default.
- Use `--allow-conflicts` only after manual review of dry-run report.
- Markdown rewrite is default; docx rewrite is opt-in via `--rewrite-docx`.

## New Reliability Hardening
- hard-gate enforcement for prewrite/complete phases
- strict references rebuild to continuous `1..N`
- dedup strategy: DOI -> PMID -> metadata key -> exact title -> fuzzy title (duplicates merged, not discarded)
- runtime artifact retention (reports/cache/backups bounded)
- cache invalidation uses nanosecond mtime signature

## Runtime Artifacts
Generated under skill runtime area:
- `.state/write_gate.json`
- `.state/lit_sync_preview.json`
- `.state/load_cache.json`
- `.state/reports/lit_sync_*.json`
- `backups/literature_sync/lit_sync_*/`

## Verification Snapshot
- `python3 -m py_compile scripts/state_manager.py` passed
- `python3 -m unittest discover -s tests -p 'test_*.py' -q` passed (`8` tests)

## Notes
This release does not require changes to other skills. `article-writing` remains isolated.
