> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

## Chapter Structure Contract

For each research chapter (Chapter 2 to Chapter N-1), keep this order:

1. 引言
2. 材料与方法
3. 结果与讨论
4. 实验结论
5. 小结

**绪论章（第 1 章）写法：跨全部研究章的综述**
- 把各子研究框进**统一科学问题**（`project_state.json.outline.scientific_question`），逐一预告每个研究章要解决的子问题与贡献点（研究章标题须在绪论正文出现，`check_quality.py check_cross_chapter_coherence` 软核）。
- 写绪论时 `write-cycle` 会**跨章加载全部研究章 digest**（A①，`synthesis_role=intro`），据此综述全部研究，不得只写第一个研究。

**结论章（末章）写法：逐章综合各研究结果拉回中心问题**
- 逐个研究章回收其核心发现（研究章标题须在结论正文出现），再综合成回答中心科学问题的整体结论，指出跨研究的一致性/递进关系与整体贡献。
- 写结论时 `write-cycle` **跨章加载全部研究章 digest/key_facts**（A①，`synthesis_role=conclusion`），结论数值/结论必须来自各研究章真实结果，不得凭空生成或与研究章矛盾。

研究章（第 2 章至第 N-1 章）Rules:
- Results & Discussion is coupled with each method experiment.
- Do not place all results first and discuss later in a separate bulk section.
- **材料与方法 must contain tables** for at least: 实验试剂与耗材, 实验仪器与设备, 实验分组设计. Use Markdown pipe syntax (`| col | col |`). Never describe these as prose paragraphs.
- **结果与讨论 must contain tables** when presenting quantitative/statistical data (e.g. 各组指标比较). Use Markdown pipe syntax.
- Marker convention in subsection markdown:
- `[实验] EXP-2-1` in methods
- `[对应实验] EXP-2-1` in results/discussion
- `[图] 图2-1` or `[表] 表2-1` linked to current experiment

