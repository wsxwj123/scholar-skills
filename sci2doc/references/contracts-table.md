> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

## Table Contract

All data tables in the thesis must use three-line (三线表) format.

### Markdown Syntax in Atomic `.md` Files

Write tables using standard Markdown pipe syntax:

```markdown
表 2-1：主要实验试剂

| 试剂名称 | 规格 | 生产厂家 |
|---|---|---|
| 胎牛血清 | 500 mL | Gibco |
| DMEM培养基 | 高糖型 | HyClone |
```

Rules:
- Caption line (`表 X-X：标题`) must appear directly above the table.
- Separator row (`|---|---|---|`) is required between header and data rows.
- No empty rows between caption and table header.
- `markdown_to_docx.py` automatically converts this to a Word three-line table with correct borders.

### Applicable Sections

Three-line tables are mandatory in (but not limited to):
- 实验试剂与耗材，columns: 试剂名称, 规格/货号, 生产厂家
- 实验仪器与设备，columns: 仪器名称, 型号, 生产厂家
- 实验分组设计，columns: 组别, 处理方式, 样本数
- 数据统计结果，columns vary by experiment
- Any section presenting structured data

**Writing rule**: If a subsection contains 3+ items sharing the same attributes (name+spec+source, group+treatment+n, etc.), it MUST be written as a Markdown pipe table, never as a prose list or paragraph.

边框参数（pt 值）与题注字体字号见 `references/word-format-spec.md § Three-Line Table Borders`；格式由 `check_quality.py` 强制校验（无竖线，顶/底线 1.5pt，表头线 0.5pt）。

