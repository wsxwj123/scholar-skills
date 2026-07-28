# 统计方法选择决策树 (stat-decision-tree)

> 被 SKILL.md 的 **`/stat-helper`** 引用。用户有 raw data、不确定用什么检验时 `Read` 本文件。
> 这是博士生最高频的卡点——选错一篇文章基本报废。

## 决策树（按数据类型 + 分组数 + 配对/独立 + 分布逐步问用户）

| 用户场景 | 推荐检验 | 备选 |
|---|---|---|
| 两组连续变量，独立，正态 | unpaired t-test | Mann-Whitney（不正态） |
| 两组连续变量，配对（如治疗前后） | paired t-test | Wilcoxon signed-rank（不正态） |
| 三组及以上连续变量，独立，正态 | one-way ANOVA + Tukey HSD | Kruskal-Wallis + Dunn（不正态） |
| 重复测量（同一动物多时间点） | repeated-measures ANOVA | Friedman（不正态） |
| 两因素（如药物 × 剂量） | two-way ANOVA + Bonferroni / Šídák | scheirer-ray-hare（不正态） |
| 分类变量（是/否） | Chi-square / Fisher's exact（n<5） | McNemar（配对） |
| 生存数据 | Log-rank test + Kaplan-Meier；多变量用 Cox 回归 | — |
| 剂量-反应 | nonlinear regression（4-PL）；EC50/IC50 用 GraphPad 内置模型 | — |
| 相关 | Pearson（连续+正态）/ Spearman（秩） | — |

## 强制询问

1. **正态性检验**做了吗？（Shapiro-Wilk for n<50, Kolmogorov-Smirnov for n≥50）—— 不正态走非参或先变换。
2. **方差齐性**检查了吗？（Levene's test）—— 不齐用 Welch's t-test / Welch ANOVA。
3. **样本量**——n<5 必须用非参；3 组以上必须做事后多重比较校正（Tukey/Bonferroni/FDR），不能简单两两做 t-test。
4. **配对 vs 独立**——同一只动物不同时间点必须配对，独立误用配对反之亦然，是退稿高频原因。
5. **outlier 处理**：是否预先定义 outlier 剔除规则（ROUT Q=1% 等）？事后剔除属于 p-hacking。

## 输出

建议的检验 + 报告模板，如：
> "Mean ± SD; one-way ANOVA followed by Tukey's multiple comparisons test; n=6 biological replicates; P<0.05 considered significant; analyses performed in GraphPad Prism v10.1"

→ 自动建议加入 `figures_database` 各 panel 的 `stat_test` 字段（用 `add-stat-method` 落地，与 `add-figure` 联动）。

## 红线

① 严禁三组以上直接 multiple t-test 不做校正；② 严禁事后看数据再选检验（HARKing）；③ 严禁 n<3 出统计学结论；④ 严禁 P>0.05 写"趋势性显著（trending significance）"。
