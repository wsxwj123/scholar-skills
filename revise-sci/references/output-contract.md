> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

# Output Contract

Always produce:
- `response_to_reviewers.md`
- `response_to_reviewers.docx`
- revised manuscript markdown at `output_md_path`
- revised manuscript Word at `output_docx_path`
  - **默认 in-place 保原稿格式**：当原稿是 `.docx` 时，改后稿基于原始 manuscript docx 编辑，未被改的段落、表格、图片、样式、对齐**原样保留**，只替换被点名改写的段落的文字，并按行内标记（`*斜体*`/`**粗**`/`<sup>`/`<sub>`）重建 run、继承原段落基础字体（font.name/size/eastAsia）。定位/身份对不上时 **fail-closed 硬停**：`export_docx.py` 退出码 3，把拒绝原因和两个选项（① 重跑加 `--allow-rebuild-fallback` 接受重排版本；② 修锚点后用未改动原稿重跑）显式打给用户，**不再默认静默降级为 md 全量重建**（那会丢原稿表格/图位/对齐并按期刊模板重排，用户却不知情）。只有显式传 `--allow-rebuild-fallback`（run_pipeline 同名 flag 透传）才回退 md 全量重建。原稿非 docx 或无原稿时正常走 md 全量重建（legacy fallback，非降级）。导出模式记录在 `project_state.json` 的 `outputs.manuscript_export_mode`（`in-place` / `in-place-tracked` / `md-rebuild`）。`response_to_reviewers.docx` 不受影响，维持现有固定样式脚本（含 eastAsia）。
  - **可选 `--track-changes` 词级修订痕迹**（默认关闭，仅 in-place 生效）：改动段落按 original vs current 的词级 diff 写成带 Word 红蓝增删痕迹的 docx（`<w:ins>`/`<w:del>`，仅包住真正变化的词，行内斜体/上下标/粗体在痕迹两侧保留），导出模式记为 `in-place-tracked`。关闭时行为与原 clean in-place 完全一致。详见 Pipeline 段 `export_docx.py` 的 `--track-changes` 说明。
- `precheck_report.md`
- `issue_matrix.md`
- `manuscript_edit_plan.md`
- `final_consistency_report.md`
- `data/literature_index.json`
- `data/revision_claims.json`
- `data/synthesis_matrix.json`
- `data/synthesis_matrix_audit.json`
- `data/reference_registry.json`
- `data/reference_coverage_audit.json`
- `figure_index.json` / `reference_index.json`,反向抽取的图、参考交叉索引(每项含 cited_by 与 orphan_type)
- `abbreviation_index.json`,反向抽取的缩略语交叉索引(每项含 defined_count / used_count / orphan_type:undefined_use / duplicate_definition / title_abbreviation 为硬错,defined_unused 为软警告)
- `manuscript_index.md`,人读版图/参考/缩略语索引与孤儿汇总。启发式抽取,作审查辅助而非红线核验
- `figures/figure_NN.<ext>` + `figures/image_manifest.json`,从源 docx `word/media/` 解出的内嵌图(按 zip 出现顺序命名),供最终返修 docx 嵌回。仅二进制搬运,不做 OCR/图像识别;非 docx 输入则目录可能为空
- `manuscript_section_index.json` 每个 section 条目含 `figures` 字段:该节图注/裸图标题锚定的图清单(`figure_id` / `caption` / `image_file` / `source`)。图注文本落在哪节该图即归哪节(definitive);图号→图片文件走 manifest idx 启发式(zip 顺序 ≈ 阅读顺序),故图片绑定标 `image_binding: ordinal_heuristic`
