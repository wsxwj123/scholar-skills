# Output Contract（产物清单与 docx 导出细则）

> 本文件是 polish-sci SKILL.md 的下沉细则，内容与拆分前逐字一致，未作任何改写。
> 何时读：Pipeline 第 7 步 merge/导出之前；需要向用户交代产物文件时。

## Output Contract
- `units/<idx>.json`,原子化单元(原文 + section_type + 引用/数值标记)。
- `figure_index.json` / `reference_index.json`,反向抽取的图、参考交叉索引(每项含 cited_by 与 orphan_type)。
- `abbreviation_index.json`,反向抽取的缩略语交叉索引(每项含 defined_count / used_count / orphan_type)。纯润色不改缩略语定义,此索引为**软报告**,列出 undefined_use / duplicate_definition / title_abbreviation 供人工取舍,不阻断交付。
- `manuscript_index.md`,人读版图/参考/缩略语索引与孤儿汇总。启发式抽取,作审查辅助而非红线核验。
- `figures/figure_NN.<ext>` + `figures/image_manifest.json`,从源 docx `word/media/` 解出的内嵌图(按 zip 出现顺序命名)。仅二进制搬运,不做 OCR/图像识别;非 docx 输入则该目录可能为空。供最终 docx 嵌图使用。
- `polish_manifest.json`,逐段润色任务包。
- `polished/<idx>.json`,逐段润色结果 + polish_risk_flags。
- `polished_manuscript.md`,合并后的润色稿。docx 导出有两条路径:
  - **in-place 保格式导出(交付级,docx 输入首选)**:`--in-place-src <原始docx>`(可配 `--docx <输出路径>`,缺省 `polished_inplace.docx`)。直接打开**原始输入 docx**,只把每个 prose 段落的文字换成 polished 文本,按行内标记(`*斜体*`/`**加粗**`/`<sup>`/`<sub>`)重建 run,每个新 run 继承该段落原首个 run 的基础字体(`font.name`/`size`/`w:eastAsia`),再叠加 italic/sup/sub/bold。段落级格式(对齐/样式/缩进 pPr)、表格、图片、页眉页脚、参考文献等非 prose 内容**完全不动**。映射靠 `units/<idx>.json` 的 `source_para_index`;段落数与 unit 对不齐(缺索引/越界/冲突)时 **fail-closed 报错退出**,绝不错位写入。**含内嵌图片(`<w:drawing>`/`<w:object>`)的段落会跳过文字改写以保图**(清 run 重建会删图,且改写后无法确定图在新文字里的位置),改写时跳过该段、保留原 runs 不动、stderr 警告并记入 `paragraphs_skipped_images`,需人工处理该段文字(与 revise-sci 口径一致)。这是 docx 输入的**保格式交付稿**。
    > ⚠️ **已知局限:run 级颜色/下划线**:run 级颜色(`w:color`)与下划线(`w:u`)**不在**行内标记(`marked_text`)范围(只序列化斜体/加粗/上下标),润色全程不携带这两类格式。in-place 导出对此做了**分级保真**:① 某段文字**未被润色改动**时,若段内存在 run 级颜色/下划线,跳过破坏性重建、**保留原 runs 无损**(记入 `paragraphs_skipped_color_underline`);② 该段文字**被润色改动**时,原颜色/下划线锚定的词可能已不在,无可靠位置映射,**重建后丢失**。因此:**用颜色/下划线表达的强调,在被改写的段落里不保证保留**,这类强调请改用 markdown 行内标记(`*斜体*`/`**加粗**`/上下标),它们随 `marked_text` 全程保真。
  - **md 重建导出(无原始 docx 时,如 md 输入)**:`--docx out.docx`(不带 `--in-place-src`)。从 polished md 重建裸 docx,解析行内标记渲染为 run 级格式并对每个 run 设含 `w:eastAsia` 的字体(中文默认宋体)。能渲染显式标注的字符级格式,但**不携带原稿的段落排版/表格/图片**,适合 md 输入或预览。
  > ℹ️ 读取层(`read_docx_paragraphs`)已把原稿 run 级格式(斜体/上下标/加粗)序列化进 `marked_text`,atomize 用它作 prose 段落 `raw_text`,润色全程带标记(见"字符级排版契约"),因此 in-place 写回能还原原稿语义行内格式,纯润色不再把 `H₂O→H2O` 或丢斜体。
- `polish_change_report.md`,逐段改动 + 风险 flag + 未改原因。
