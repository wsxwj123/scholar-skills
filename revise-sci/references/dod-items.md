> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

# DoD 逐项清单（与 dod_checklist.json 逐项对应；改清单先改 JSON，再同步此处散文）

### 通用 8 项（id: RV-G1 ~ RV-G8）

| id | 项目 | 核验方式 |
|---|------|---------|
| RV-G1 | 引文 `[n]` ↔ 参考列表一一对应，无孤儿引用、无缺号，编号连续 | `python scripts/build_reference_registry.py` → `data/reference_coverage_audit.json` ok=true |
| RV-G2 | 本轮新增引用已过 citation_guard 双重核验 | `python scripts/citation_guard.py` → ok=true，无 manual_review 条目 |
| RV-G3 | 改动符合原文 storyline / 主线（不跑题，不与原文主线矛盾） | 人工对照 `issue_matrix.md` 逐段核查（无脚本可自动核验） |
| RV-G4 | 占位符清零：无 `CITE_PENDING` / `DATA_PENDING` / `【待AI】` / `{{` 残留 | `grep -r "CITE_PENDING\|DATA_PENDING\|待AI\|{{" <project_root>/` 零命中 |
| RV-G5 | 去 AI 五项（破折号/scare quotes/解释性冒号/英文≤30词/-ing从句/中文≤50字≤2层从句）通过 | `python scripts/strict_gate.py --project-root <project_root>` → `ai_style_flags_removed` 无残留；句长警告记录于 notes |
| RV-G6 | 字数达标（改动前后正文字数在期刊要求范围内） | 人工或期刊要求核对 |
| RV-G7 | 缩略语首展一致：`abbreviation_index.json` 无 `undefined_use` / `duplicate_definition` / `title_abbreviation` 硬错；改稿未破坏既有首展，Title 不含缩写（`defined_unused` 为软警告可人工豁免） | `python scripts/manuscript_index.py --manuscript <output_md> --project-root <project_root>` 后读 `abbreviation_index.json`，硬错 orphan 零命中（启发式索引，可疑项人工复核） |
| RV-G8 | **Commonsense sanity (🟡 soft report, non-blocking)**: the blind-review subagent also scans rewritten fragments for obvious commonsense/factual errors (absurd unit magnitudes, physiology/mechanism mistakes, internal numeric contradictions) introduced by the rewrite. Report only, never block delivery, never auto-edit content. Distinct from the citation/reference verification gates (RV-G1/RV-G2) and from reviewer-simulator's full scientific audit. | 盲检subagent LLM 判断（复用现有 `delegate_review` 盲检机制，无新脚本）；命中只在subagent返回 `notes` 报告，软项不进 `strict_gate.py` 硬失败、不计入 `delegate_review verify` 的阻断退出码（与 `references/dod_checklist.json` 硬门禁互不冲突） |


### Revise-Sci 特有项（id: RV-R1 ~ RV-R12）

| id | 项目 | 核验方式 |
|---|------|---------|
| RV-R1 | `strict_gate.py` 通过（exit code 0） | `python scripts/strict_gate.py --project-root <project_root>` → `STRICT_GATE: PASS` |
| RV-R2 | Reference coverage 无缺口：`data/reference_coverage_audit.json` `ok=true`，无 unresolved numeric/author-year gap | `python scripts/build_reference_registry.py` → coverage_audit 直接读；或 RV-R1 覆盖 |
| RV-R3 | Patch 修订哈希一致（如使用 Patch 修订协议）：`apply_revision_patch.py` 未报告任何 hash mismatch，所有未触及 block 字节不变（fail-closed，哈希不符则整批拒绝，不得静默部分应用）；未使用则标 na 并注明 | `python scripts/apply_revision_patch.py --manifest <block_manifest.json> --patch <patch.json> --output <revised.md>` exit code 0 |
| RV-R4 | 退稿信每条意见有落点：`issue_matrix.md` 每个 `comment_id` 在 `manuscript_edit_plan.md` 中有 revised_excerpt | `python scripts/strict_gate.py --project-root <project_root>`（strict_gate 内含此检查，RV-R1 通过则本项通过） |
| RV-R5 | 审稿意见已原子化：`atomize_comments.py` 在 pipeline 中已运行，每条意见有 severity 字段，comment_id 唯一，无混合意见跨意见合并改动 | 人工确认 `state/comment_registry.json` 已生成且 comment_id 唯一（`atomize_comments.py` 无 --dry-run flag，须通过 pipeline 正式运行核验） |
| RV-R6 | polish 状态完整：所有含非空 revision_plan.scope 的片段已有 polish state，无 meaning_changed=true 或 scope_respected=false | `python scripts/strict_gate.py --project-root <project_root>`（strict_gate 内含此检查，RV-R1 通过则本项通过） |
| RV-R9 | polish 片段级守卫通过：每个 polished 片段 `polish_numbers_ok=true`（无数值漂移/丢失）、`polish_certainty_ok=true`（谨慎动词未被升级为强断言）、无套话禁词残留；`polish_risk_flags` 已落盘到 unit / `revision_polish_execution.json` / `comment_records/<id>.md` | `python scripts/strict_gate.py --project-root <project_root>`（strict_gate 内含 A/B/MID 三项检查，RV-R1 通过则本项通过） |
| RV-R7 | response_to_reviewers.docx 结构完整：每个 comment block 都有 comment heading / response-section heading / evidence-section heading | `python scripts/strict_gate.py --project-root <project_root>`（strict_gate 解析 docx 核验结构，RV-R1 通过则本项通过） |
| RV-R8 | 结构完整性：改后稿件结构完整（原结构无破坏、参考文献编号连续、response 各 unit 三要素齐全）；退稿信每条意见在 edit_plan 中有落点无遗漏 | `python scripts/strict_gate.py --project-root <project_root>`（RV-R1 通过则本项通过）；或人工逐段核查 |
| RV-R10 | 跨节一致性盲检（全局层，超出片段级 RV-R9）：改稿后关键数值/样本量/效应量/主要结论在摘要-正文-图表-结论间仍一一对应、无新引入矛盾；改动未把原谨慎表述升级为新过度声称（因果化/普适化/夸大疗效）。跨节不一致或新增过度声称=fail，列冲突两处原文为证 | `python scripts/cross_section_consistency.py --project-root .`（客观信号）+ 盲检subagent据此判定 |
| RV-R11 | 语法拼写与字符级格式：对原子化正文 `manuscript_sections/` 跑字符级体检。高置信类别 **misspelling**（英文常见错拼）/ **chinese_punct**（中文标点漏入英文句）/ **subsup_bare**（H2O、IC50、cm² 等应上下标却裸写，含 CJK 安全边界）**零容忍**：命中任一即 `fail_on_hits` 非空、`ok=false`、退出码非 0；其余类别（学术错拼/中文错字/单位/英美混用/数字格式/术语不一致/Methods 时态/断链）**仅报告不阻断**。**只报告供用户决断，绝不自动改正文**（fragment-only 保真），命中后由用户决定是否回片段修订 | `python scripts/proofread.py --manuscript-dir manuscript_sections --report proofread_report.json --fail-on misspelling,chinese_punct,subsup_bare` → `ok=true` 且 `fail_on_hits` 为空 |
| RV-R12 | 拉丁短语斜体软提醒（🟡软/人工确认，不阻断）：`proofread.py` 的 `latin_italic_missing` 类别，正文里 `in vitro`/`in vivo`/`ex vivo`/`in situ`/`de novo`/`post hoc`/`per se` 等公认须斜体的拉丁短语若裸写（未被 `*...*` 斜体标记包裹）则报告。**仅提示，不阻断、不进 `--fail-on`、不扣分**，由人工确认是否补斜体（`et al.`/`e.g.`/`vs.` 等正体惯例不在词表内） | 同 RV-R11 脚本，读 `proofread_report.json` 中 `latin_italic_missing` 计数供人工决断，不影响 `ok`/退出码 |

> RV-R3 仅在使用 Patch 修订协议时适用，跳过需在 notes 中注明原因。RV-R4/R6/R7/R8/R9 已由 strict_gate 覆盖，RV-R1 通过即视为通过；RV-R5 须确认 pipeline 正式运行产出 comment_registry.json。RV-R10 为跨节一致性全局盲检（独立脚本 `cross_section_consistency.py` + subagent判定），**不由 strict_gate 覆盖**，须单独核。

### 投稿前作者自检（🟡 soft 提醒，不阻断交付）

终稿交付前，对照 `references/presubmission_checklist.md` 过一遍（数字一致性、英美拼写统一、图像无不当处理、Source Data、查重、临床注册号、报告规范附件、投稿材料齐全等）。这些项多需作者掌握原始数据/图像/外部工具，机器无法可靠裁决，故**只提醒、不阻断**；与本技能既有 hard 门禁（引用一一对应、去AI、跨节一致、字符级体检 RV-R11 等）不重复。
