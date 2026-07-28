# Word Format Specification — Built-in Default Doctoral Thesis Standard

`markdown_to_docx.py` applies the built-in default doctoral thesis formatting. All values below are authoritative — they are hardcoded in the converter and enforced by `check_quality.py`.

## Page Layout

| Property | Value |
|----------|-------|
| Paper size | A4 |
| Top margin | 2.54 cm |
| Bottom margin | 2.54 cm |
| Left margin | 3.17 cm |
| Right margin | 3.17 cm |

## Font & Paragraph Styles

| Element | Chinese Font | Latin Font | Size | Weight | Alignment | Line Spacing | Indent | Spacing |
|---------|-------------|------------|------|--------|-----------|-------------|--------|---------|
| 一级标题 (Heading 1) | 黑体 (SimHei) | Times New Roman | 三号 (16pt) | 加粗 | 居中 | 固定值 20pt | 无 | 段前 18pt，段后 12pt |
| 二级标题 (Heading 2) | 宋体 (SimSun) | Times New Roman | 四号 (14pt) | 常规 | 左对齐 | 固定值 20pt | 无 | 段前 10pt，段后 8pt |
| 三级标题 (Heading 3) | 宋体 (SimSun) | Times New Roman | 小四 (12pt) | 常规 | 左对齐 | 固定值 20pt | 无 | 段前 10pt，段后 8pt |
| 正文 (Normal) | 宋体 (SimSun) | Times New Roman | 小四 (12pt) | 常规 | 两端对齐 | 固定值 20pt | 首行缩进 0.74cm (2字符) | 段前 0，段后 0 |
| 图题注 (Figure Caption) | 楷体 (KaiTi) | Times New Roman | 五号 (10.5pt) | 常规 | 居中 | 单倍行距 | 无 | 段前 0，段后 12pt |
| 表题注 (Table Caption) | 楷体 (KaiTi) | Times New Roman | 五号 (10.5pt) | 常规 | 居中 | 单倍行距 | 无 | 段前 12pt，段后 0 |
| 表格单元格 | 宋体 (SimSun) | Times New Roman | 五号 (10.5pt) | 表头加粗 | 居中 | — | — | — |

## Three-Line Table Borders

| Border | Weight | Note |
|--------|--------|------|
| 顶部边框 (top) | 1.5pt (sz=12) | 第一行顶部 |
| 表头分隔线 (header-body) | 0.5pt (sz=4) | 表头行底部 |
| 底部边框 (bottom) | 1.5pt (sz=12) | 最后一行底部 |
| 竖线 & 其他横线 | 无 | 全部清除 |

## Font Pairing Rule

Every run must set both `w:name` (Latin) and `w:eastAsia` (CJK) via `set_run_font()`. This prevents Word from falling back to Calibri or other unexpected fonts when mixing Chinese and English text.

## Page Header & Footer

| Element | Content | Font | Size | Position |
|---------|---------|------|------|----------|
| 页眉左侧 | "<大学名>博士学位论文"（默认模板示例 "示例大学博士学位论文"） | 宋体 + TNR | 五号 (10.5pt) | 距顶端 1.5cm |
| 页眉右侧 | "第X章 章名" | 宋体 + TNR | 五号 (10.5pt) | 右对齐 Tab |
| 页脚 | PAGE 域页码 | Times New Roman | 小五 (9pt) | 居中，距底端 1.75cm |

- `setup_header()` and `setup_footer()` in `markdown_to_docx.py` implement this.
- `merge_chapters.py` `add_header_footer()` applies the same spec during docx merge.
- CLI args: `--header-right`, `--page-num-fmt` (decimal/roman), `--page-num-start`.

## Front Matter Formatting

| Section | Title Font | Title Size | Body Font | Body Size | Notes |
|---------|-----------|------------|-----------|-----------|-------|
| 中文摘要 | 黑体 (SimHei) | 三号 (16pt) 居中 | 宋体 (SimSun) | 四号 (14pt) | "摘要："黑体四号加粗，关键词全角分号分隔 |
| 英文摘要 | Times New Roman | 三号 (16pt) 居中 | Times New Roman | 四号 (14pt) | "Abstract:" TNR 四号加粗，keywords 半角分号分隔 |
| 目录 | 黑体 (SimHei) | 三号 (16pt) 居中 | 章：黑体 / 节：宋体 | 小四 (12pt) | 1.5 倍行距 |

- `add_abstract_section()`, `add_english_abstract_section()`, `add_toc_section()` in `markdown_to_docx.py`.
