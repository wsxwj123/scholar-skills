# Citation Style Guide

## In-Text Citations
- **Format:** Numerical, superscript or bracketed depending on specific journal, but for drafting use bracketed numbers: `[1]`, `[2,3]`, `[4-6]`.
- **Placement:** Immediately after the fact, idea, or data being cited, usually before punctuation.
  - Correct: "AI models have shown promise in pathology [1]."
  - Correct: "This method, however, lacks generalizability [2,3]."

## Bibliography Format (Nature Style)
Standard format for the reference list at the end of the document.

**Generic Format:**
`[No.] Authors (LastName Initials). Title of article. Abbreviated Journal Name **Volume**, Page range (Year).`

**Examples:**

**Journal Article:**
`[1] Wang, J., Xu, W., & Xinyan, H. AI in Pathology. *Nat. Med.* **30**, 100-110 (2024).`

**Review:**
`[2] LeCun, Y., Bengio, Y. & Hinton, G. Deep learning. *Nature* **521**, 436–444 (2015).`

**Preprint:**
`[3] Author, A. Title of preprint. *Preprint at* https://arxiv.org/abs/xxxx.xxxxx (2023).`

## Important Rules
1. **Accuracy:** Never fabricate citations. Every DOI must be real.
2. **Diversity:** Ensure a mix of classic foundations and cutting-edge (last 3 years) research.
3. **Primary Sources:** Prefer citing the original research paper over a review that mentions it, unless discussing the review's perspective itself.

---

## Reference Manager Modes

### Zotero Mode (Recommended)
- Real-time write during Phase 2 — one batch per section immediately after search.
- Collection tree mirrors review outline hierarchy (root = title, subcollections = sections).
- Each paper tagged `gid:N`; abstract stored as child note.
- PDF: auto-download OA papers via Unpaywall API (free); non-OA papers tagged `pdf:missing`.
- `lib_id` stored in `outline.md`; `api_key` asked each session, never persisted.

### None Mode
- Uses inherited scripts: `export_bibtex.py`, `matrix_manager.py`, `state_manager.py` (reindex only).
- `data/literature_index.json`: paper metadata + gid + section assignments.
- `data/synthesis_matrix.json`: structured claims per paper per section.
- BibTeX export: `python3 scripts/export_bibtex.py --input data/literature_index.json --output exports/references.bib --clean`

### EndNote Mode
- Same as None Mode during writing phase.
- Final step: user manually imports `exports/references.bib` into EndNote.
- No automatic write-back.

---

## CNKI / 万方中文文献导入

仅适用于 **Chinese writing** 模式。英文模式不需要此流程。

建议在初稿完成后统一补充中文文献，避免 gid 编号冲突。

**知网（CNKI）：**
1. 在检索页勾选目标文献 → 导出 → 选择"EndNote"格式 → 下载 .txt 文件
2. 在 Zotero 中：文件 → 导入 → 选择下载的 .txt 文件 → 导入到对应章节集合
3. 手动为导入条目添加 `gid:N` tag（N 从当前最大 gid+1 开始递增）
4. 在 `drafts/section_XX_XX.md` 中用 `[N]` 引用

**万方：**
导出 → 选择"RIS"格式 → 同上步骤 2–4 导入 Zotero。

> ⚠️ CNKI/Wanfang 条目不走 `append-literature` 脚本（绕过 citation_guard 在线校验）。导入后须人工核对 DOI/PMID 字段是否完整，并在 Phase 4 前手动补全 `data/literature_index.json` 对应记录。
