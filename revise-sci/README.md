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

If a reviewer asks for new references, only `paper-search` is allowed as the external provider family. Unknown material must be marked as `Not provided by user` or `需作者确认`.
