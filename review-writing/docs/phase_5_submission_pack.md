# Phase 5: Submission Pack

**触发时机：** Phase 4 导出完成后（`phase=4, completed=true`）。Write 与 Polish 两模式都执行。
**Entry: Read `outline.md` + `state.json`. If `phase=5, completed=true` → already done, skip.**
> **Phase gate:** `phase < 4` 或 Phase 4 未 completed → HALT，提示先完成 Phase 4 导出。

**📖 进入本阶段必读：**
1. `references/submission_checklist.md`（综述版投稿清单 + 强制/询问分级 + 红线 + 产出路径）
1b. **`references/cover-letter-guide.md`（综述版 cover letter 写法必读）**：四段结构 / Innovation≠Contribution（综述落在框架层）/ **期刊 scope 契合强制**。写 `exports/cover_letter.md` 前必读。
2. `references/presubmission_checklist.md`（投稿前作者自检清单，**soft 提醒不阻断**）：终稿交付前对照逐项自查，重点是机器无法可靠裁决、需作者掌握原始数据/图像/外部工具的项（图像不当处理、Source Data、查重、注册号、报告规范附件、投稿材料齐全等）。已被本技能 hard 门禁覆盖的维度不重复，仅提醒，不阻断交付。

### 强制 / 询问分级（不静默留白）

| 件 | 级别 | 无内容时的处理 |
|----|------|---------------|
| Cover Letter / Title Page / CRediT / COI / Funding / DAS / Keywords(3–6) | **强制** | COI/Funding/DAS 无则按 submission_checklist 标准句声明"无"，不留空 |
| ORCID / Acknowledgements 致谢对象 | **询问** | 向用户索取；未提供 → 显式标 "not provided" / 各类 N/A |
| Highlights / Suggested·Opposed Reviewers | **按目标刊** | Cell 系等要求时给；Reviewers 须逐一核 COI 回避，严禁伪造邮箱 |

### 步骤

1. **逐项询问**（不要静默用空白）：通讯作者信息 + ORCID、各作者 CRediT role、COI、Funding（funder + grant number）、致谢对象、目标刊是否要 Highlights / Suggested Reviewers。明细见 submission_checklist.md 第 1 节。

2. **生成投稿包**（写入 `exports/`，路径以 submission_checklist.md 第 6 节为准）：
   - `exports/cover_letter.md` — 写法见 `references/cover-letter-guide.md`。综述卖点是 synthesis/framing/gap→展望；引用 Phase 1.5 gap + Phase 1.6 framing 作为"为何此刻需要这篇综述"。**🔴 scope 契合段强制**：向用户索取目标刊 **Aims & Scope 原文**（技能不自动抓取），据此写具体契合论证，禁 "will interest the broad readership" 类通用套话；用户未给 scope 原文则停下索取，不编造。
   - `exports/title_page.md` — 题名（禁缩写）/ 作者 / 单位 / 通讯(含邮箱) / ORCID。
   - `exports/author_contributions.md` — CRediT（完整 14 类逐条认领，未覆盖的标 N/A 并说明；角色清单与综述适用性见 `references/submission_checklist.md` 第 2 节）。
   - `exports/coi_statement.md` — 无则 "The authors declare no competing interests."
   - `exports/funding.md`（可并入 title page）— 无则 "This work received no specific external funding."
   - `exports/data_availability.md` — 综述无原始数据 → "Data sharing not applicable — no new datasets were generated or analysed."（systematic 有提取数据则给获取方式）。
   - `exports/keywords.md` — 3–6 个，不照抄标题词。
   - `exports/acknowledgements.md` — 各类别（非作者贡献者/技术平台/讨论反馈），无则 N/A。
   - `exports/highlights.md`（按目标刊）/ `exports/suggested_reviewers.md`（按需，逐一核 COI 回避）。

3. **合规核对**（综述相关项）：署名 ICMJE 四准则、Reviewer COI 回避；伦理/注册号/统计报告对 narrative 综述标 N/A，仅 systematic/scoping 走 PRISMA。细则见 submission_checklist.md 第 3–4 节。

4. **DoD 自检（gate `submission-pack-dod`，委托独立subagent盲检）：**
   ```bash
   python3 scripts/delegate_review.py pack --checklist "[DOD_CHECKLIST]" \
     --gate submission-pack-dod \
     --files exports/cover_letter.md exports/title_page.md exports/author_contributions.md \
             exports/coi_statement.md exports/keywords.md --workdir .
   python3 scripts/delegate_review.py verify --checklist "[DOD_CHECKLIST]" \
     --gate submission-pack-dod --return .review_return_submission-pack-dod.json
   # 退出码非 0 = fail-closed，据subagent证据修复后重跑，未过不得声明完成
   ```
   gate 5 项：S1 强制件齐全（Cover Letter+Title Page+CRediT+COI+Keywords）/ S2 COI·Funding·DAS 非空（无则声明无）/ S3 Keywords 3–6 且不与标题雷同 / S4 通讯作者一致 / S5 无占位符·无伪造。真源见 `references/dod_checklist.json`。

5. **更新 state + Git Checkpoint：**
   ```bash
   python3 scripts/state_manager.py set-phase --phase 5 --completed true
   git add -A && git commit -m "[review] Phase 5: submission pack" --allow-empty-message 2>/dev/null || true
   ```

**完成。向用户交付投稿包，列出已生成文件与询问级标 N/A 的项。**
