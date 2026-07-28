# Edge Cases

| Issue | Handling |
|-------|---------|
| Zotero API key invalid / 403 error | Re-ask user for api_key; do NOT proceed until --status returns ✅ |
| Preprint / no DOI | Dedup falls back to title fuzzy match |
| Multiple Zotero libraries | `--status` lists all; user selects; write to outline.md |
| Windows, no edirect | Prompt WSL install or fallback to paper-search MCP |
| Proxy port varies | Auto-scan 7890/1080/8080/8888; write result to outline.md |
| API key forgotten (cross-session) | outline.md stores lib_id only; ask api_key at start |
| Zotero Web API rate limit | PyZotero auto-waits; batch add ≤50 items per call |
| Zotero --dedup gid 失同步 | --dedup 只改 Zotero 标签，不更新 literature_index.json。正常流程不需要 --dedup（--add-batch 已去重）。如果手动运行了 --dedup，必须用 --get-section 逐节获取新 gid 并手动同步到 literature_index.json |
| Mid-search crash | state.json `completed_sections` tracks progress; resume skips done |
| Section <10 papers found | Warn, prompt user to broaden keywords, continue |
| NCBI_API_KEY set | Auto-use for 10 req/s rate limit |
| Chinese review | One-time CNKI notice at Phase 0 end; no repeated prompts |
| Round 2 new papers | Append + dedup immediately; gid assignments updated |
| PubMed CLI + paper-search MCP both unavailable | HALT; tell user "literature retrieval tools unavailable"; suggest: (1) install edirect: `sh <(curl https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)` or (2) enable paper-search MCP in client settings; do NOT fallback to websearch/tavily |
| Round 3 / Phase 4 preprint search yields 0 new results | Skip gracefully; record `"round3_papers": 0` in state.json; do not block Phase 4 export |
| 需要回滚到之前某个阶段 | `git log --oneline` 查看检查点 → `git checkout <hash> -- .` 恢复文件 → `git add -A && git commit -m "[review] rollback to <phase>"` |
| 需要推倒重来（reset） | `git log --oneline` 找到 `[review] Phase 0` 的 commit → `git checkout <hash> -- .` → `git add -A && git commit -m "[review] rollback to Phase 0"` → 或直接删除项目目录重新 Phase 0 |
| Git 不可用 | 所有 checkpoint 静默跳过，不影响写作流程；建议安装 git 以获得回滚能力 |
