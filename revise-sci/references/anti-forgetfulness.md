> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

## Anti-Forgetfulness And Token-Budget Protocol
`revise-sci` does **not** load the entire manuscript and all comments into one context window. It uses the same approach as `article-writing`, `review-writing`, and `sci2doc`, adapted for revise work:

1. **Intake-first routing**: route the comment source first, then lock the branch before loading anything large.
2. **Section-paragraph atomicization**: only the target section and target paragraph are used for rewrite scope.
3. **Comment-scoped state windows**: every processed `comment_id` gets its own context package under `state/comment_windows/<comment_id>.json`.
4. **Section digests, not full reloads**: cross-section consistency uses `state/section_digests.json`, which stores only headings, paragraph counts, and key sentences, rather than full section text.
5. **Token budget compaction**: `state_manager.py write-cycle` estimates token load and compacts related digests / reviewer context / neighboring paragraphs if the bundle exceeds the configured budget.
6. **Cycle log persistence**: every revise action appends to `state/comment_cycle_log.json` and `state/comment_memory/<comment_id>.md`, so a future agent does not need to reconstruct local history from scratch.
7. **Snapshot safety**: `state_manager.py snapshot` writes state snapshots so runs can be resumed with smaller context and lower drift risk.

Recommended per-comment loading command:

```bash
python scripts/state_manager.py --project-root <project_root> write-cycle --comment-id <comment_id> --token-budget 4200 --tail-lines 80 --json-summary
```

This command is the revise-sci equivalent of the section-scoped state loading in `article-writing`, `review-writing`, and `sci2doc`. It is the preferred context entry before any manual or AI-assisted change to a specific comment-linked paragraph.
