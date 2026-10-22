> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

## ❌ 反例黑名单（Anti-Patterns）

- ❌ 跳过 `intake_router.py` 直接跑 `run_pipeline.py`，或输入源未分类／不支持仍硬跑（preflight 须 fail-fast，不得猜分支）。
- ❌ 重写整段而非只改目标句或只追加新句（fragment-only，`revise_units.py` 只动 `revision_plan` 锁定的片段）。
- ❌ 把全文加全部意见塞进一个上下文窗，违反防遗忘 token 预算，须用 comment-scoped state window 逐条加载。
- ❌ 虚构实验、数据、统计或引用来回应意见；缺信息须写 `Not provided by user` 或 `需作者确认`。
- ❌ 用 websearch／tavily／openalex 补文献；只允许 paper-search，且新引用须过 `citation_guard` 双向核验。
- ❌ 段落定位模糊却硬选一个段落；多候选评分相近时须落 `needs_author_confirmation`，不得激进选段。
- ❌ 把实质性请求（新机制／新证据／新图／未匹配章节）当 `completed` 自动收口；只有保守的纯文本澄清或限制句可 auto-complete。
- ❌ Patch 修订哈希不符仍强行套用或自动重定位（fail-closed，整批拒绝、写空、退非零，不静默部分应用）。
- ❌ 去 AI 主干未过（硬）：scare quotes、解释性冒号、套话禁词、-ing 假分析从句、**装饰性破折号（🔴 硬门禁，禁止使用，命中即 FAIL）**。（仅英文 >30 词为软提示：上报不阻断，但仍应改。）
- ❌ 主 agent 自评 DoD 当通过；`strict_gate.py` 前须委托独立subagent盲检，verify 未 exit 0 不得声明改稿完成；盲检过后仍须摆逐项结论 + HALT 等用户确认才收口。
- ❌ 把「有意驳回不改（`push_back`）」误判成「漏改」，或反过来把真漏改的意见混进 push_back 蒙混；驳回必须在回复信据理反驳，正文不动但回应不能缺。
- ❌ 退稿信漏回某条意见，或某 `completed` comment_id 在 `manuscript_edit_plan.md` 中无 revised_excerpt 落点（`push_back`/`需作者确认` 不要求 revised_excerpt）。
- ❌ 补新文献只验真实性（DOI/PMID）就下笔，跳过「引文↔论点」核证；或用 `--offline` 跑 citation_guard 就交付（承重句须过 `citation_claim_check.py`，guard 须 `--live`）。
- ❌ 引文 `[n]` 与参考列表不对应、缺号或编号不连续就交付（`reference_coverage_audit.json` 须 ok=true）。
- ❌ `--resume` 时输入指纹或脚本签名已变仍信任旧产物，而非 fail-fast 重建。
- ❌ 改稿删/换句子时丢失某缩写的唯一首展、在首展前裸用 ABBR、新增术语不首展，或 Title 出现缩写（`abbreviation_index.json` 的 `undefined_use` / `duplicate_definition` / `title_abbreviation` 硬错须清零）。
- ❌ 改写锁定片段时增删或错配行内排版标记（`*italic*` / `<sup>` / `<sub>` / `**bold**`），等同于篡改引文标记 `[n]`；裸写 `H2O`/`CO2`/`IC50` 或漏给物种名、基因名、统计符号加斜体。
