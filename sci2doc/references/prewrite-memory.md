> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

# Prewrite Memory Loading：write-cycle 自动加载的内容与 chapter_index.json 更新示例

When `write-cycle` runs, `load_state` automatically loads:

1. `project_state.json`：project metadata, progress, and **outline**（含研究主线 `scientific_question` + 各章 `core_argument`，是写作一致性的锚点）
2. `chapter_index.json`：chapter structure with section titles (filtered to current chapter)
3. `literature_index.json`：references (filtered to current chapter)
4. `figures_index.json`：figures/tables (filtered to current chapter)

> **A① 跨章综合例外：** 当前章为**绪论（绪论/引言）或结论（结论/总结/小结/展望）**时，`load_state` 不按当前章过滤，而是**全量加载 chapter_index / literature_index / figures_index + 全部研究章的 section digest/key_facts**（`bundle.synthesis_role` = `intro`/`conclusion`，`scope=cross-chapter-synthesis`）。这样绪论能综述全部研究、结论能跨章综合各研究章的真实数据，避免缝线全露。章类型由 `project_state.json.outline` 里该章标题判定。**引文核证不整批重验**：绪论/结论引用的文献若已在某研究章验过（承重论点↔引文那道核证），`citation_claim_check.py` 经 `ref_evidence_cache.json` 自动复用该 (文献, 论点) 的既有 abstract 与确认结论，AI 不必对全量引文手动重记证据；只有**新出现的 (文献, 论点) 组合**才需反向验证，fail-closed 不放松。
5. `context_memory.md`：timestamped operation summaries
6. `history_log.json`：recent operation events
7. **`chapter_section_digests`**：lightweight digests extracted from existing `atomic_md/第N章/*.md` files

Item 7 is the cross-section consistency mechanism. It does NOT load full markdown content (that would blow the token budget). Instead, it extracts only:
- Headings (section structure)
- Table captions (表 X-X：...)
- Key experimental facts (grouping, reagents, concentrations, methods, max 10 per section, 80 chars each)
- Character count (progress tracking)

This gives the AI enough context to avoid contradicting earlier subsections (e.g. wrong experimental design, wrong reagent lists) without consuming significant tokens.

### AI Responsibility: Update chapter_index.json

After writing each subsection, the AI **must** update `chapter_index.json` with key facts from that section. This is the primary structured memory that persists across sessions. The digest mechanism is a safety net, not a replacement.

Example entry:
```json
{
  "chapter": "2",
  "section": "2.1",
  "title": "实验材料与试剂",
  "key_facts": ["PMG浓度梯度: 0, 5, 10, 20 μg/mL", "细胞系: HepG2, LO2", "Western blot检测蛋白表达"],
  "tables": ["表 2-1：主要试剂及来源", "表 2-2：主要仪器设备"]
}
```

