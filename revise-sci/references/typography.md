> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

## Character-level typography contract（字符级排版契约）

Applies to all newly written or rewritten content (revised fragments, new sentences, response-letter prose). These inline markers are rendered into real Word character formatting by `scripts/export_docx.py` (bold/italic/superscript/subscript runs). This contract governs the markers you emit when authoring new text. **Reading the original docx now preserves run-level formatting too**: `read_docx_paragraphs(..., inline_format=True)`（仅 `atomize_manuscript.py` 开启）把原稿 run 的 italic/bold/sup/sub 序列化成同一套行内标记进 section text/current_text，所以未改片段的原格式经 revise→export 往返不丢；被改片段也按同一套标记在 in-place 写出时重建 run。默认读取器仍为纯文本（`inline_format=False`），数值/引用/AI 风格红线比对不受标记污染。

- **Italic** via `*...*` for: species Latin names (`*E. coli*`, `*Staphylococcus aureus*`), gene names (`*TP53*`, `*BRCA1*`), single-letter statistical symbols (`*p*`, `*t*`, `*n*`, `*F*`, `*r*`), and Latin abbreviations (`*in vitro*`, `*in vivo*`, `*et al.*`, `*e.g.*`, `*i.e.*`).
- **Superscript** via `<sup>...</sup>`: exponents and powers (`10<sup>6</sup>`, `cm<sup>2</sup>`, `mg·kg<sup>-1</sup>`). **Subscript** via `<sub>...</sub>`: chemical subscripts and indexed terms (`H<sub>2</sub>O`, `CO<sub>2</sub>`, `IC<sub>50</sub>`, `T<sub>max</sub>`). **Never** emit bare `H2O` / `CO2` / `IC50`.
- **Bold** via `**...**` only for headings and inline labels (e.g. `**Limitations.**`), never for emphasis inside running scientific prose.
- 中文回复部分：句内标点全角（，。：；），英文与数字保持半角，中英文之间不强制空格但须一致。

These inline markers are load-bearing and carry the same status as citation markers `[n]`: when rewriting a locked fragment, **do not add, drop, or mis-pair** them. Adding `*`/`<sup>`/`<sub>` where the source had none, or stripping existing ones, is a meaning/format drift and is subject to the same fragment-only and scope-lock rules as `[n]`.
