# Revise-Sci Changelog

## [2.29.5] - 2026-08-09

第十五轮共享件同步（SPEC-round15，盲检判合格）：proofread 参考文献段剥离收敛 ref_section 单一口径（新增 vendored ref_section.py）；citation_claim_check 垃圾摘要按缺失处理 + 大批量警告折叠落报告。

## [2.29.4] - 2026-08-06

第十三轮同款 bug 修复（SPEC-round13）：cross_section_consistency GBK 不崩 + 聚类数值归一（45% 与 45.0% 不再误报漂移）；env_preflight argv 守卫。

## [2.29.3] - 2026-08-06

第十二轮共享件同步（SPEC-round12）：citation_guard_core 的 _http_get_json
补 ssl.SSLError / BadStatusLine 异常覆盖（fail-closed，retry 语义不变）。

## [2.29.2] - 2026-08-06

写保护批次（SPEC-round10-protected）：install_gate_hook settings.json 写盘原子化
+ hooks 非 list 点名报错；structure_signoff_gate 签字凭证写盘原子化；
context_guard_core 的 _gsw_left / _nsfc_left 两条判定修正同步。

## [2.29.1] - 2026-08-05

第十轮共享件修复同步（SPEC-round10）：delegate_review 重复 id 往严处倒 +
--section 路径消毒（#14/#15，fork 同构修）；citation_claim_check 非 str 摘要
防崩（#16）；citation_guard_core 连接重置/IncompleteRead fail-closed（#6）；
proofread 4 位年份不再误报数字格式不一致（#9）。

## 第十七轮完成记录（2026-03-09）

1. 已完成语义角色定位增强：`revise_units.py` 新增 `front/introduction/methods/results/discussion/conclusion` 角色映射，并在缺少显式结构锚点时尝试按评论语义将抽象评论路由到最可能 section。
2. 已完成单候选 section 的语义兜底：当评论没有结构化 hint，但语义角色只对应一个 section 时，系统可保守地使用该 section，而不再一律降级。
3. 已完成 `location_strategy` 落盘，便于后续审计具体采用了 `citation-anchor / response-seed / evidence-anchor / structured-heading / semantic-role / lexical-fallback` 中哪一种定位路径。
4. 已完成 profile-based Word 导出：`export_docx.py` 现在支持 `journal-manuscript / nature-review / cell-press / lancet-review` 四套 manuscript profile。
5. 已完成 Word 参考文献编号保留：当 markdown 文末 references 使用显式编号时，导出的 Word 不再丢失编号文本。
6. 已完成 `journal_style` 在 `preflight.py / run_pipeline.py / final_consistency_report.py / strict_gate.py` 中的贯通与审计。
7. 已完成 references 区块清洗回写：`build_reference_registry.py` 会过滤掉章节标题/目录项这类伪参考文献，并把干净的 bibliography 重新写回 markdown。
