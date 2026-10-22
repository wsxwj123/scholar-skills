> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

# Script Entry Points（5 条核心命令）+ Regression Tests

正文仅保留5条最常用核心命令；write-cycle 各节 token 预算、verify-entry / matrix-check / validate-one / polish-review / validate-order / 阶段稿 merge / word_counter 等完整调用与子命令清单见 `references/08_脚本清单与合并规则.md`。

- init: `python scripts/state_manager.py --root . init`
- sync-all (repair): `python scripts/state_manager.py --root . sync-all --auto-fix`
- gate-check (full, requires MCP): `python scripts/state_manager.py --root . gate-check --sections-dir sections --index data/literature_index.json --p1 sections/P1_立项依据.md --ref sections/REF_参考文献.md --mcp-cache data/mcp_literature_cache.json --mcp-ttl-days 30 --require-mcp`
- merge: `python scripts/section_merger.py merge --sections-dir sections --output output/申请书_合并.md`
- full-review: `python scripts/diagnosis_engine.py full-review --sections-dir sections --consistency data/consistency_map.json --index data/literature_index.json --p1 sections/P1_立项依据.md --ref sections/REF_参考文献.md --output data/diagnosis_report.json`

Phase 7 引用的 `consistency_mapper.py validate` 完整形式：`python scripts/consistency_mapper.py --path data/consistency_map.json validate`。
其余脚本（write-cycle 逐节预算、citation_validator verify-all/verify-entry/matrix-check、humanizer_zh scan-all、load 变体、word_counter summary）的完整 flag 见 references/08。


## Regression Tests
测试位于 `scripts/`（test_delegate_review / test_format_contract / test_literature_gate / test_prewrite_gate）与 `_shared/`，统一入口 `python3 _shared/run_all_tests.py --skill nsfc-proposal`（仓库完整克隆下，当前 4/4 通过）。
`test-prompts.json` 仅验证触发与门禁交互，未被上述 suite 覆盖的脚本逻辑需人工抽查。

