> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

# 第四步：技术合规性审计的四个脚本锚（辅助索引 / 结构目录锚 / 数值候选锚 / 方法术语弱锚）

**图表完整性与参考文献审计的辅助索引（执行前先跑）：** 用脚本反向抽取稿件的图、参考交叉索引，为图文一致性与引用完整性核查提供逐项依据（孤儿图、孤儿引用、列而未引）。脚本用安装目录绝对路径，输出锚定 `$WORKROOT`（本技能无原子化步骤，故不带 `--units-dir`，cited_by 退化为正文段号 pN）：
`python "$SKILL_DIR/scripts/manuscript_index.py" --manuscript <稿件 docx 或 md> --project-root "$WORKROOT"`
产出 `$WORKROOT/figure_index.json`、`$WORKROOT/reference_index.json`、`$WORKROOT/manuscript_index.md`。结果为启发式抽取，作审计辅助而非红线核验：图表完整性审计据 `figure_index.json` 核对每图是否有图注、是否被正文引用（`orphan_type`）；参考文献审计据 `reference_index.json` 核对孤儿引用（列而未引 `entry_not_cited`、引而无条目 `cited_no_entry`）。**同时产出 `$WORKROOT/abbreviation_index.json`**（缩写定义/裸使用点/首现位置 + orphan 的交叉索引，bare JSON 数组）——其 `duplicate_definition` orphan 供**确定性直报**（软报告，见第五部分七『术语一致性核查产物的报告归位』小节），其 `defined_count>=1` 缩写清单供**视角⑧术语一致性审稿人**当焦点。**`undefined_use` orphan 本轮不消费**（卡点5 决策：审稿端真价值实测 0——学界惯例裸用 + 末尾缩写表被脚本打穿导致全是假阳，见 PLAN §6）。合法空数组 `[]`（通篇无缩写）是有效结果、不是失败。

**交叉引用一致性的结构目录锚（紧接着再跑一条）：** 抽取稿件里**真实存在的结构目录**（小标题 `3.1`/`4.1.2`、图/表编号、条目 `(1)(2)(3)`），作为第四步半视角⑤"交叉引用一致性审稿人"的**确定性锚**——LLM 只在这份机器真值上判交叉引用对不对，不凭记忆假设稿子有哪些小节。同样用安装目录绝对路径，输出锚定 `$WORKROOT`：
`python "$SKILL_DIR/scripts/structure_outline.py" --manuscript <稿件 docx 或 md> --project-root "$WORKROOT"`
产出 `$WORKROOT/outline.json`（`sections`/`figures`/`tables`/`items` 四类清单 + `summary`）。脚本护栏取向"宁抽勿拒"，只列结构不判引用；图/表编号统一记作 `Figure N`/`Table N`（正文"图3"＝`Figure 3` 的跨语言对应由视角⑤ LLM 兜）。此文件在第四步半仅喂给视角⑤。

**数值一致性的数值候选锚（再紧接着跑一条）：** 抽取稿件里**真实出现的带上下文数值候选**（数字+单位+所在句+指标名线索+分组/时间点线索+位置），作为第四步半视角⑥"数值一致性审稿人"的**确定性锚**——LLM 只在这份机器真值上判数值矛盾，不凭记忆。同样用安装目录绝对路径，输出锚定 `$WORKROOT`：
`python "$SKILL_DIR/scripts/numeric_candidates.py" --manuscript <稿件 docx 或 md> --project-root "$WORKROOT"`
产出 `$WORKROOT/numeric_candidates.json`（`candidates` 清单，每条含 `id`/`raw`/`value`/`value_secondary`/`norm`/`unit`/`form`/`sentence`/`metric_clue`/`group_clue`/`location` + `summary`）。脚本护栏"宁抽勿拒"，**只列数值不判矛盾、不判同一测量、不判容差**（判断全留视角⑥ + 反向验证）；百分比 `norm` 归一为分数、docx 表格单元格值也抽（`location.source=="table"`）。此文件在第四步半仅喂给视角⑥。

**方法学一致性的方法术语弱锚（再紧接着跑一条）：** 拿内置实验方法术语词典**扫全稿命中**，输出稿子里哪些方法术语字面出现在哪些句/哪个 region/是否邻接图，外加方法学章节的小节标题清单，作为第四步半视角⑦"方法学交代完整性审稿人"的**聚焦焦点图**。同样用安装目录绝对路径，输出锚定 `$WORKROOT`：
`python "$SKILL_DIR/scripts/methods_terms.py" --manuscript <稿件 docx 或 md> --project-root "$WORKROOT"`
产出 `$WORKROOT/methods_terms.json`（顶层 `authority:"weak_focus_map"` + `method_hits` 清单，每条含 `id`/`term`/`canonical`/`region`/`sentence`/`location`/`has_figure_adjacent` + `methods_sections` 小节清单 + `summary`）。**⚠️ 与 outline.json / numeric_candidates.json 的根本差异：这是弱锚焦点图、不是权威真值**——结果侧"用了什么方法"一般无字面 token（是语义），脚本**只报字面命中、只标注（region + 是否邻接图），从不判任何方法是否漏写、是否本研究做的、是否穷尽**（判断 100% 留视角⑦ + 反向验证）。此文件在第四步半仅喂给视角⑦。**降级编排：`methods_terms.py` 若 exit 2 或 `methods_terms.json` 缺失/损坏，视角⑦ 照常派出、降级为纯全文语义跑（它本就被要求不依赖弱锚、须自行语义识别），不得静默跳过。**

