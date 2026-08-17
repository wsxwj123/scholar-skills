# revise-sci

`revise-sci` turns reviewer comments, a manuscript `.docx`, optional SI, and attachments into:

- a revised manuscript in Markdown and Word
- a structured `Response to Reviewers` in Markdown and Word

The skill is script-gated and uses this fixed order:

1. `preflight`
2. `atomize_comments`
3. `atomize_manuscript`
4. `build_issue_matrix`
5. `revise_units`
6. `merge_manuscript`
7. `export_docx`
8. `final_consistency_report`
9. `strict_gate`

Run the full pipeline with:

```bash
python scripts/run_pipeline.py \
  --comments /abs/path/comments.docx \
  --manuscript /abs/path/manuscript.docx \
  --project-root /abs/path/output_dir \
  --output-md /abs/path/output_dir/revised_manuscript.md \
  --output-docx /abs/path/output_dir/revised_manuscript.docx
```

Since round22 the one-shot pipeline is a resumable state machine (`pipeline_gate`
in `project_state.json`): it pauses (exit 3, `PIPELINE_PAUSED phase=...`) at the
comment-inventory confirmation, the four-way `revision_strategy` gate, the
three-layer independent audit (detection → reverse verification → user
adjudication) and the independent DoD review; each human gate is confirmed with
a content digest (`--resume --confirm-comment-inventory / --confirm-audit-adjudication /
--confirm-dod-closure <sha256>`). Only after the user's DoD closure does the
pipeline run the final bare `strict_gate.py` and exit 0. Upstream content
changes bump `epoch` and logically invalidate old confirmations/receipts.
Pre-round22 projects: plain `--resume` pauses non-destructively and points to
`--resume --migrate-round22`.

If a reviewer asks for new references, only `paper-search` is allowed as the external provider family. Unknown material must be marked as `Not provided by user` or `需作者确认`.
