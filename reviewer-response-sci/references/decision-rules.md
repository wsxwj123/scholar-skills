# Decision Rules

## A. 选择回复基调
- 审稿意见正确且有证据支持：`Accept and revise`
- 意见部分成立：`Partially accept with bounded revision`
- 意见与研究边界冲突：`Respectfully disagree with evidence`
- 审稿建议超出当前工作范围但有价值：`Alternative improvement`

## B. 英文高频句式
> **与去 AI 禁词表的口径（务必一致）**：下列致谢/缓冲句是**允许**的外交缓冲，不属于被禁的"空致谢"。禁的是副词叠加的浮夸致谢（"we greatly/sincerely/deeply appreciate"）、"this is an excellent suggestion"、以及 ≥3 条回复用同一句开头。缓冲句只用**一句**，其后必须紧跟实质回应；Push back / Partial 基调尤其可用一句缓冲软化否定。`risk_check.py` 的 `ai_appreciation` 正则已按此放行无副词的单句致谢。

- Appreciation（每条至多一句，其后紧跟实质回应）:
  - "We thank the reviewer for this valuable comment."
  - "We appreciate this suggestion and have revised the manuscript accordingly."

- Accept and revise:
  - "We agree with the reviewer and have clarified this point in the revised manuscript."
  - "To address this concern, we have added ... in Section X."

- Partial acceptance:
  - "We agree in principle; however, within the scope of the current study, ..."
  - "Accordingly, we have revised the text to better delimit this boundary."

- Respectful disagreement:
  - "We respectfully note that ..."
  - "Based on the current data, this interpretation is supported by ..."

- Scope limitation without overpromise:
  - "This is an important point. While additional experiments are beyond the scope of the present study, we have ..."

## C. 外交措辞 craft（说服的分寸，尤其 Push back / Partial）

> 反驳最忌硬顶。审稿人手握生杀权，正面否定容易激怒他。三条 craft 让否定读起来像"我们认真想过你的顾虑"，而非"你错了"：

**① 反驳前先承认对方顾虑的合理性**（先给台阶，再讲为什么这次不适用）：
- "The reviewer is right that X could bias the result; in our setting, however, ..."（先认 X 重要，再限定它在本研究不成立）
- "This is a fair concern. We had the same worry during design, which is why we ..."（把顾虑说成"我们也想过"，拉到同一战线）
- "We agree that Y would strengthen the claim in general. For the specific question here, ..."（泛泛承认 → 收窄到本文范围）
- 反例（禁）：一上来 "We disagree." / "This is not correct." —— 没给台阶就否定。

**② 用部分让步软化整体拒绝**（拒绝主诉求，但接一个小的，让审稿人拿到东西）：
- "While a full replication is beyond the present scope, we have added a sensitivity analysis that speaks to the same concern."（拒大让小）
- "We cannot add the requested cohort, but we now discuss this limitation explicitly in Section 4 and cite [N]."（不做实验，但补讨论+引文）
- "We retain the original analysis for the reasons below; we have, however, added the alternative as a supplementary check."（主结论不动，副线让步）
- 要义：整体 Push back 的 unit 里最好有**一个具体、真做得到的让步动作**落在 modification_actions，别只讲道理不给东西。

**③ 把审稿人自己的话引回来 reframe**（用他的措辞，导向你的结论）：
- 审稿人说 "the mechanism is unclear" → "We agree the mechanism deserves clarity. To make it explicit, we have added ... "（认领"unclear"，用"make it explicit"回应）
- 审稿人说 "the sample looks small" → "The reviewer notes the sample size. We now report a power analysis showing ... is sufficient for the primary endpoint."（把"small"转成"我们已用 power analysis 证明够用"）
- 引用审稿人原话时用引号短引一句（属"逐字引用审稿人"豁免，不算 scare quote），紧接给证据，别复述一整段。

**尺度**：以上缓冲/让步/reframe **每条至多一句**，其后必须紧跟实质回应或证据；连续 ≥3 条用同一句开头即触发去 AI 结构重复告警。缓冲不是目的，是让实质回应被听进去的润滑。

## D. 跨审稿人呼应去重（同一问题只答一次）
两个及以上审稿人问同一件事时，**不要各写一遍**（措辞难免不一致，还显得敷衍）。做法：
1. 选一条作 **canonical**（通常是提得最完整/最早的那条，如 Reviewer 2 Comment 3），在它里面把该问题**完整作答 + 落点写全**。
2. 其余同问的 unit：`content.cross_ref` 填 canonical 目标（如 `"Reviewer 2, Comment 3"`），`response_en` 用交叉指引句，答案不重复展开：
   - "As we detail in our response to Reviewer 2 (Comment 3), we have added ... . In brief, ..."（指过去 + 一句摘要）
   - "This point overlaps with Reviewer 1's Comment 2; please see our full response there. Here we note that ..."（承认重叠 + 指向 + 本条补一句差异）
3. 交叉指引的 unit **不必自带落点**——`consistency_check.py` 见 `cross_ref` 非空即免除本 unit 的落点重复要求（落点由 canonical unit 承载）。canonical unit 仍须落点齐全。
4. 若两条虽相关但诉求有细微差别，canonical 答主体，呼应 unit 补那一句差别，别硬合并成"完全一样"。

## E. 风险红线
- 禁止虚构：新增实验、未报告统计结果、不存在的图表与引用。
- 禁止攻击性表达：avoid "the reviewer is wrong" 等对抗句式（见 C① 用"先认后限定"替代）。
- 禁止空泛承诺：avoid "we will definitely prove" without evidence.
