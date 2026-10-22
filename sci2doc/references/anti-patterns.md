> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

## Common Mistakes

1. Mistake: Hardcoding chapter targets without user negotiation.
   - Fix: update `thesis_profile.json` via `state_manager.py profile`.

2. Mistake: Keeping conflicting old thresholds in docs/scripts.
   - Fix: profile-driven targets only.

3. Mistake: Writing one chapter in a single large markdown file.
   - Fix: atomic subsection files + validate numbering.

4. Mistake: Skipping self-check and snapshot.
   - Fix: run `self-check` and `section-snapshot` as hard gates.

5. Mistake: Overly mechanical AI text in final chapter.
   - Fix: run humanizer pass before finalize.

## ❌ 反例黑名单（Anti-Patterns）

- ❌ 把全文末尾的统一参考文献计入正文字数，正文范围只到正文结束、参考文献之前。（注：综述/绪论章按 A③ **计入**正文字数，不再排除。）
- ❌ 把博士/硕士字数目标当硬门逼 AI 编数据/灌水凑字：地板是**软目标**（`check_quality.py` 已降为 warning），真实内容不够宁可少写也不得造数据。
- ❌ 看到 QUICK_START 的 init 示例就直接套 `--format-mode default_generic` 跑 init，未经用户确认样式即静默落成内置模板格式并放行 docx 导出。
- ❌ 在自定义信息不完整、状态仍为 `pending_template` 时生成 `.docx` 或跑格式验收，或手动绕过 `markdown_to_docx.py` 的拒绝。
- ❌ `outline` 数组为空就进入 Style Selection Gate 与 Step 1，缺 `scientific_question` 或研究章 `core_argument`。
- ❌ 把章节字数目标硬编码或在 init 后才定，应在 Step 0.5 与用户协商后写入 `chapter_targets`。
- ❌ 引用 `citation_guard` 未核验的文献，或在 guard 报 `ok=false`、双向校验失败时继续写作而不入人工核验队列。
- ❌ 用 `websearch` / `openalex-cli` / `tavily` 作为文献来源，或把 `sci-source-seed` 种子条目当可直接引用来源（须以 DOI／PMID 经 PubMed CLI 或 paper-search 正式核验）。
- ❌ 并行发起文献检索调用，必须串行且相邻调用间隔 ≥1s。
- ❌ 对图片材料做 OCR 或从文件名猜内容，图片一律 `pending_confirm`，须用户口述补充后才能引用。
- ❌ 编造实验数据或参考文献，引用数值／结论必须可追溯到 `materials/` 对应 entry。
- ❌ 跳过 `write-cycle` 预写门禁就写新小节，它是唯一加载跨章记忆的机制。
- ❌ 把材料与方法、分组、统计等结构化数据写成散文段落，3 项以上同属性数据必须用 Markdown 管道三线表。
- ❌ 主 agent 自评 DoD 清单代替独立subagent盲检，或上一节／上一章 `delegate_review verify` 未 exit 0 就开始下一节／下一章。
- ❌ 把结果全部前置、后面集中讨论，研究章结果与讨论必须按实验逐一耦合，且每个实验至少配一张图或表。

