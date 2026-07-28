# Git Rollback 指南

## Git Checkpoint 消息表

每次 `state.json` 更新后执行（`git_available: true` 时）：

```bash
git add -A && git commit -m "[review] <MESSAGE>" --allow-empty-message 2>/dev/null || true
```

| Checkpoint 位置 | commit message |
|-----------------|----------------|
| Phase 0.5 (init script 内) | `[review] Phase 0: project initialized` |
| Phase 1.5 (research gap 后) | `[review] Phase 1.5: research gap identified` |
| Phase 1.6 (benchmark 后) | `[review] Phase 1.6: benchmark reviews + framing guide` |
| Phase 1.7 Step 9 (据调研建提纲后) | `[review] Phase 1.7: outline confirmed (post-research)` |
| Phase 2 每节 Step 8 | `[review] Phase 2: section X.X search complete` |
| Phase 2.5 (dedup 后) | `[review] Phase 2.5: dedup + global ID assigned` |
| Phase 3 每节 Step 9 | `[review] Phase 3: section X.X draft complete` |
| Phase 4 Step 7 | `[review] Phase 4: export finalized` |
| Phase 0-P Step 5 (substep 3 后) | `[review] Phase 0-P: citations imported` |
| Phase 0-P Step 6 (state init 后) | `[review] Phase 0-P: polish mode initialized` |

Because `init_project.py` runs `git init` + commits at Phase 0, every checkpoint is a full project snapshot — drafts (`drafts/section_*.md`), `state.json`, and `data/` indices all roll back together (atomic-draft rollback, no orphaned state). Run from inside the project root (`git_available: true` only):

```bash
git log --oneline                          # list checkpoints; find the [review] commit to return to
git checkout <sha> -- drafts/section_03_02.md   # restore ONE file (e.g. a bad section draft) from that checkpoint
git revert <sha>                            # undo a specific checkpoint's changes as a new commit (history-safe)
git checkout <sha> -- .                     # restore the ENTIRE project tree to that checkpoint (does not move HEAD)
```

Prefer `git checkout <sha> -- <file>` for a single bad section and `git revert` to back out a whole checkpoint. After any file restore, re-run `state_manager.py reindex` (None/EndNote) if gid alignment may have shifted. Do NOT use `git reset --hard` (destroys uncommitted work without confirmation).

## Edge Cases

| Issue | Handling |
|-------|---------|
| 需要回滚到之前某个阶段 | `git log --oneline` 查看检查点 → `git checkout <hash> -- .` 恢复文件 → `git add -A && git commit -m "[review] rollback to <phase>"` |
| 需要推倒重来（reset） | `git log --oneline` 找到 `[review] Phase 0` 的 commit → `git checkout <hash> -- .` → `git add -A && git commit -m "[review] rollback to Phase 0"` → 或直接删除项目目录重新 Phase 0 |
| Git 不可用 | 所有 checkpoint 静默跳过，不影响写作流程；建议安装 git 以获得回滚能力 |
