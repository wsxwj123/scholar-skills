# Revise-Sci Changelog

## 第十七轮完成记录（2026-03-09）

1. 已完成语义角色定位增强：`revise_units.py` 新增 `front/introduction/methods/results/discussion/conclusion` 角色映射，并在缺少显式结构锚点时尝试按评论语义将抽象评论路由到最可能 section。
2. 已完成单候选 section 的语义兜底：当评论没有结构化 hint，但语义角色只对应一个 section 时，系统可保守地使用该 section，而不再一律降级。
3. 已完成 `location_strategy` 落盘，便于后续审计具体采用了 `citation-anchor / response-seed / evidence-anchor / structured-heading / semantic-role / lexical-fallback` 中哪一种定位路径。
4. 已完成 profile-based Word 导出：`export_docx.py` 现在支持 `journal-manuscript / nature-review / cell-press / lancet-review` 四套 manuscript profile。
5. 已完成 Word 参考文献编号保留：当 markdown 文末 references 使用显式编号时，导出的 Word 不再丢失编号文本。
6. 已完成 `journal_style` 在 `preflight.py / run_pipeline.py / final_consistency_report.py / strict_gate.py` 中的贯通与审计。
7. 已完成 references 区块清洗回写：`build_reference_registry.py` 会过滤掉章节标题/目录项这类伪参考文献，并把干净的 bibliography 重新写回 markdown。
