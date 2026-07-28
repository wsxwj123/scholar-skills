# 投稿前合规门禁细则 (compliance-gate)

> 被 SKILL.md Phase 10.5 (`/compliance-check`) 指针引用。包含六项合规检查的完整判定细则与阻断条件。

---

## 1. 伦理批号

- 动物实验 → IACUC 批准号（格式：`机构名-年份-批次`）+ 实验方案符合 3Rs 原则（Replacement/Reduction/Refinement）。
- 人体研究 → IRB 批准号 + 知情同意声明（"All participants provided written informed consent"）。
- 体外/计算/公开数据集研究 → 无需批号，标注 "This study did not involve human subjects or animal experiments"。
- **阻断**：涉及动物/人体但缺批准号，或 Methods 中无伦理声明段落。

---

## 2. 临床试验注册号

- 前瞻性临床研究（干预性试验、观察性队列、RCT）→ 必须提供 ClinicalTrials.gov NCT 编号或等效注册库（ChiCTR/ISRCTN/UMIN 等）编号及注册日期；注册须在首例入组**前**完成，事后注册须标明。
- 回顾性研究/体外实验/动物实验 → 标注 "Not applicable (retrospective study / in vitro study)"。
- **阻断**：前瞻性临床研究缺注册号（ICMJE 强制要求，缺则桌面拒稿）。

---

## 3. 报告规范（CONSORT/STROBE/ARRIVE/PRISMA）

`Read templates/reporting_checklists.json` → 按 `project_config.research_field` + `target_journal` 自动匹配。

适用匹配规则：

| 研究类型 | 适用规范 |
|---|---|
| RCT | CONSORT 2010 |
| 观察性研究（队列/病例对照/横断面） | STROBE |
| 动物实验 | ARRIVE 2.0 essential 10 |
| 系统综述/Meta分析 | PRISMA 2020 |
| 预测模型 | TRIPOD |
| qPCR | MIQE |
| ML | NeurIPS ML reproducibility |

对 Methods/Results 逐项核对，输出通过率；**缺项必须补写**。
**阻断**：ARRIVE essential 10 任意一项、CONSORT flow diagram、PRISMA flow diagram 缺失。

---

## 4. 统计报告完整性

- **精确 P 值**：必须报告精确 P 值（如 P = 0.032），禁止仅写 P < 0.05（除非 P < 0.0001 无精确值）。
- **效应量 + 置信区间**：每个主要比较必须报告效应量（Cohen's d / OR / HR / η² 等）+ 95% CI。
- **多重比较校正**：多组比较或多个主要终点时，必须说明校正方法（Bonferroni / Benjamini-Hochberg FDR 等）及校正后阈值。
- **检验前提验证**：正态性（Shapiro-Wilk / Q-Q plot）+ 方差齐性（Levene / Brown-Forsythe）须在 Methods 中说明；未验证则补写或改非参检验。
- **阻断**（仅含假设检验/组间推断统计的研究）：主要结果缺 95% CI，或多重比较无校正说明。纯描述性研究不受此阻断，但须报告描述性统计离散度（SD/IQR 等）。

---

## 5. 署名合规性（ICMJE 四准则）

每位作者须同时满足全部四条：
① 对构思/设计/数据采集/分析有**实质性贡献**；
② 参与起草或对重要内容进行**严格修订**；
③ 批准最终提交版本；
④ 对本工作各方面问责。

- **仅满足 1-2 条**的贡献者 → 列入 Acknowledgments，**不能列为作者**。
- **署名顺序**：第一作者 / 共同第一（"†These authors contributed equally"）/ 通讯（最后，"*Corresponding author"）/ 共同通讯（双 *）。
- **阻断**：CRediT 分配中出现不符合 ICMJE 四准则的作者（挂名），须提请用户确认修正。

---

## 6. Reviewer 推荐 COI 回避

每位 suggested reviewer 须同时满足：
- 近 3 年内无共同发表论文
- 近 3 年内无同一基金
- 非同单位（同机构不同系也须回避）
- 非直接导师/学生/博士后关系

若用户提供了 suggested reviewers 列表，逐一核对；不符合须替换。
**阻断**：suggested reviewer 存在明显 COI（同单位/近 3 年合作/导师-学生关系）而未回避。

---

## 7. Keywords（投稿关键词列表）

- 投稿包必须含 `submission/keywords.txt`，内含 3-6 个投稿关键词（具体数量遵从目标刊投稿系统要求）。
- 数量须符合目标刊规则：多数期刊 3-6 个；缺失或数量越界即阻断。
- 关键词与 title/abstract 主题一致，避免与标题词完全重复（标题已含的词不重复占名额）。
- 生命科学优先选 MeSH 受控词。选词原则与 MeSH 适配细则见 `references/submission-guide.md` 第 8 节。
- **阻断**：`submission/keywords.txt` 缺失，或关键词数量不符目标刊规则（一般 <3 或 >6），阻断投稿包导出。

---

## 输出格式

`submission/compliance_report.md`：

```
## 投稿前合规门禁报告
1. 伦理批号：✅/❌ [说明]
2. 试验注册号：✅/❌ [说明]
3. 报告规范（CONSORT/STROBE/ARRIVE/PRISMA）：✅/❌ [缺失条目列表]
4. 统计报告完整性：✅/❌ [缺失项]
5. 署名合规性（ICMJE）：✅/❌ [问题项]
6. Reviewer COI 回避：✅/❌ [问题项]
7. Keywords：✅/❌ [keywords.txt 是否存在 + 关键词数量]
```

全部 ✅ → 进 Phase 11；任一 ❌ → 补充后重跑，不得跳过。
