> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

# Write Mode · Phase 3–7 与 DoD 停（执行门禁原文；三步命令模板见 SKILL.md 正文）

5. Phase 3: write P3 研究基础（4 sub-files）.
   - **🔴 开写前置闸门 (Mandatory，脚本硬拦截)**：每个子节开写前先跑 `python3 scripts/prewrite_gate.py --section P3_1 --root .`（其余子节同理 P3_2/P3_3/P3_4），exit≠0 禁止开写（硬检查上一节完成、`consistency_map` 含 M、占位符清零；P3_1 额外要求 `data/experimental_design.json` 非空；盲检按 Phase 粒度：P3_1←P2 跨 Phase，缺 `.review_pass/P2.json` 硬拦 exit 1；P3_2/P3_3/P3_4 同属 P3 一次性盲检，同 Phase N/A 不拦）。
   - 每节先跑 `python scripts/state_manager.py --root . write-cycle --section P3_1`（其余子节同理 P3_2/P3_3/P3_4；逐节预算/上下文注入的预写门控，完整参数见 references/08）；不得跳过直接硬写。
   - Input: P2 confirmed; team CV, platform data, and prior publications from Phase 0 profile.
   - Output:
     - `sections/P3_1_研究基础与可行性分析.md` (prior work + feasibility evidence per M + risk mitigation)
     - `sections/P3_2_工作条件.md` (equipment, facilities, missing conditions and remedies)
     - `sections/P3_3_正在承担的相关项目.md` (ongoing projects; explain overlap/difference from this project)
     - `sections/P3_4_完成基金项目情况.md` (completed grants summary ≤500字 + deliverables list)
   - Each M in consistency_map must have at least one feasibility entry (F) sourced from P3_1 or P3_2.
   - **伦理审查（涉人类受试者/实验动物/生物安全/人类遗传资源时为硬项）：** P3_1 可行性分析须说明已获或计划申请的伦理审查批件（如医学伦理委员会、实验动物福利伦理、生物安全审批、人类遗传资源采集/保藏/利用审批），尚未取得的注明送审计划与时间节点。不涉及上述情形则无需展开。
   - P3_3 and P3_4 may use list format (tables allowed).

   **Phase 3 DoD（收口自检）：未逐项确认通过，不得向用户声明 P3 完成**

   **🔴 委托盲检（遵上方总则的三步命令模板，主 agent 不得自评）**：`<gate>`=`p3-dod`，`<files>`=`sections/P3_1_研究基础与可行性分析.md sections/P3_2_工作条件.md sections/P3_3_正在承担的相关项目.md sections/P3_4_完成基金项目情况.md`，`<section>`=`P3_1`。落盘的 `.review_pass/P3_1.json` 代表 P3 整体盲检；P3_2/P3_3/P3_4 同 Phase 内不单独硬校验。

   **本 Phase 完整 DoD 判据（全部核查项 + 脚本命令）以 `references/dod_checklist.json` gate=`p3-dod` 为默认真源；项目根有 `data/dod_selection.json`（用户协商关项）或 `structure_profile.json`（结构真源，非国自减免/改判）时，实际执行的是三步模板第 0 步经 `dod_project.py` 投影后的清单，被关/被减免的项不进盲检、已进报告「未执行的检查」留痕**：盲检subagent据此逐项核、能脚本核的先跑脚本，退出码非 0 即 fail-closed。该 gate 含四子文件齐全、M 可行性覆盖(V-06)、P3_4 字数上限、伦理审查说明、占位符清零、去AI、一致性未引入新矛盾、代表作匹配(V-11)，及 N54 结构完整性、N64 可行性实质盲检。此处不再内联清单，避免与真源 drift。

6. Phase 4: write P4 其他需要说明的情况（≤500字）.
   - 每节先跑 `python scripts/state_manager.py --root . write-cycle --section P4`（逐节预算/上下文注入的预写门控，完整参数见 references/08）；不得跳过直接硬写。
   - Input: P3 confirmed.
   - Output: `sections/P4_其他需要说明的情况.md`.
   - Cover: concurrent grant applications, senior PI prior grants, postdoc status, AI usage declaration, ethics/biosafety/human-genetic-resource approvals (若涉及，与 P3_1 伦理说明呼应), any other required disclosures.

   **Phase 4 DoD（收口自检）：未逐项确认通过，不得向用户声明 P4 完成**

   **🔴 委托盲检（遵上方总则的三步命令模板，主 agent 不得自评）**：`<gate>`=`p4-dod`，`<files>`=`sections/P4_其他需要说明的情况.md`；本 Phase verify 不带 `--section`/`--root`。

   **本 Phase 完整 DoD 判据（全部核查项 + 脚本命令）以 `references/dod_checklist.json` gate=`p4-dod` 为默认真源；项目根有 `data/dod_selection.json`（用户协商关项）或 `structure_profile.json`（结构真源，非国自减免/改判）时，实际执行的是三步模板第 0 步经 `dod_project.py` 投影后的清单，被关/被减免的项不进盲检、已进报告「未执行的检查」留痕**：盲检subagent据此逐项核、能脚本核的先跑脚本，退出码非 0 即 fail-closed。该 gate 含字数上限、伦理说明呼应、AI 使用声明、占位符清零、去AI，及 N55 结构完整性。此处不再内联清单，避免与真源 drift。

7. Phase 5: write 预算说明书（B1-B3）.
   - Input: P2 confirmed (M entries define budget items); project profile (budget_total, duration).
   - Output:
     - `sections/B1_预算说明_直接费用.md` (equipment; materials; tests; travel/conference; publications; labor; consulting; three-line tables where required)
     - `sections/B2_预算说明_合作外拨.md` (co-institution allocation, or "无")
     - `sections/B3_预算说明_其他来源.md` (other funding sources)
   - Budget total must equal profile `budget_total`; each major budget item traces to an M entry.
   - **🔴 预算求和硬核对（Mandatory，脚本硬拦截）**：B1-B3 写完后，把各分项金额按「元」录进 `data/budget_table.json`（`{"budget_total": <总额>, "items": [{"name": "设备费", "amount": 200000}, ...]}`，金额一律纯数字、不写 "20万元" 这类带单位字符串），然后跑：
     ```bash
     python3 scripts/budget_check.py --root .
     ```
     exit 0 = 分项和与总额相符（容差 1 分钱）；**exit 1 = 对不上，禁止声明预算完成**，按输出的 `diff`（= 分项和 − 总额，带符号）定位是漏填分项还是总额写错，改完重跑；**exit 2 = 预算表缺失/畸形/金额非法**（错误行含 `BUDGET_CHECK_ERROR` 并点名是哪条分项），先补齐再跑。该脚本只读，不会替你改平预算表。V-09 只查条目可追溯，不做求和，两者不重叠。

   **Phase 5 DoD（收口自检）：未逐项确认通过，不得向用户声明 P5/预算完成**

   **🔴 委托盲检（遵上方总则的三步命令模板，主 agent 不得自评）**：`<gate>`=`p5-dod`，`<files>`=`sections/B1_预算说明_直接费用.md sections/B2_预算说明_合作外拨.md sections/B3_预算说明_其他来源.md`；本 Phase verify 不带 `--section`/`--root`。

   **本 Phase 完整 DoD 判据（全部核查项 + 脚本命令）以 `references/dod_checklist.json` gate=`p5-dod` 为默认真源；项目根有 `data/dod_selection.json`（用户协商关项）或 `structure_profile.json`（结构真源，非国自减免/改判）时，实际执行的是三步模板第 0 步经 `dod_project.py` 投影后的清单，被关/被减免的项不进盲检、已进报告「未执行的检查」留痕**：盲检subagent据此逐项核、能脚本核的先跑脚本，退出码非 0 即 fail-closed。该 gate 含三子文件齐全、预算总额核算、预算条目可追溯(V-09)、直接费用类别完整、占位符清零，及 N56 结构完整性。此处不再内联清单，避免与真源 drift。

8. Phase 6: write 中英文摘要（abstract-last, based on full draft）.
   - Input: all sections P1–P4 confirmed; run `python scripts/state_manager.py --root . load --global` for full-text summary.
   - Output: `sections/00_摘要_中文.md` (≤400汉字) + `sections/00_摘要_英文.md` (≤300英文词).
   - Keywords must align with `consistency_map.keywords_trace`.

   **Phase 6 DoD（收口自检）：未逐项确认通过，不得向用户声明摘要完成**

   **🔴 委托盲检（遵上方总则的三步命令模板，主 agent 不得自评）**：`<gate>`=`p6-dod`，`<files>`=`sections/00_摘要_中文.md sections/00_摘要_英文.md`；本 Phase verify 不带 `--section`/`--root`。

   **本 Phase 完整 DoD 判据（全部核查项 + 脚本命令）以 `references/dod_checklist.json` gate=`p6-dod` 为默认真源；项目根有 `data/dod_selection.json`（用户协商关项）或 `structure_profile.json`（结构真源，非国自减免/改判）时，实际执行的是三步模板第 0 步经 `dod_project.py` 投影后的清单，被关/被减免的项不进盲检、已进报告「未执行的检查」留痕**：盲检subagent据此逐项核、能脚本核的先跑脚本，退出码非 0 即 fail-closed。该 gate 含中/英文摘要字数、关键词吻合、摘要 H/O/RC/KSQ 一致、占位符清零、去AI，及 N57 结构完整性。此处不再内联清单，避免与真源 drift。

9. Phase 7: 全文自审与终稿 + merge.
   - Input: all sections (00, B1-B3, P1-P4, REF) confirmed.
   - Run `diagnosis_engine.py full-review` and `consistency_mapper.py validate` (完整参数见 Script Entry Points); fix all ERROR-level issues.
   - Run `python scripts/word_counter.py summary sections` and `python scripts/state_manager.py --root . page-estimate --sections-dir sections`; if >30 pages, trim specific locations.
   - Run `humanizer_zh.py scan-all` before final output.
   - **图表交叉引用核查（第 1 层结构锚 · 报告式软门 · 交用户裁决）**：本子里 `见[图1]` / `如[表2]所示` / `如前文 2.1 所述` 这类指向，此前零覆盖（V 规则查 H/O/RC/KSQ 链路，不查图表编号指没指到东西）。merge 前跑：
     ```bash
     mkdir -p tmp && python3 scripts/section_merger.py merge --sections-dir sections --output tmp/xref_corpus.md --root .
     python3 scripts/structure_outline.py --manuscript tmp/xref_corpus.md --project-root .
     ```
     语料必须用 merge 按正文顺序拼（有结构真源按其 `chapters[].order`，没有按内置国自然顺序），**不许用 `cat sections/*.md`**——shell 的 `*` 是字典序，实测 `section_10_*` 会排在 `section_2_*` 前面，语料顺序一错，"如前文 2.1 所述"这类前后指向的判定就会失真。该 merge 会先跑 validate-order，缺必需章节 exit 2 并列出缺哪些（Phase 7 本就要求章节齐全，缺了先补齐）。
     产项目根 `outline.json`（`sections`/`figures`/`tables`/`items` 四类真实存在的结构锚 + `summary`）。退出码 **0 = 正常（含空稿，四类为空数组是合法结果，照常继续）**、**2 = 用法/输入错**。该脚本与 `_shared/` 逐字节共享（6 家），**一个字节不许改**；`[图1]` 的方括号形态已被现役正则正常捕获，题注认 `图 1. 标题` / `图1：标题`（`表` 同理），`图1 标题` 这种无分隔符写法认不出。产物落 `tmp/` 与项目根，**绝不落 `sections/`**（那是 managed_globs，写进去会被 signoff hook 拦下）。
     - **本步只做第 1 层抽取，不自动判悬空**：把 `caption_found=false` 的图/表编号（正文引了、全稿找不到对应题注行）与 `sections` 候选清单列给用户人工过目，说明「这是候选清单不是定论——题注写法不合规也会落进来」，由用户裁决要不要补题注或改引用。**不阻断 merge**，但必须把清单打出来，不许静默跳过。
   - Output: `output/申请书_合并.md`。**合并顺序来源**：无结构真源时按内置国自然顺序（00摘要 → B1-B3预算 → P1 → P2 → P3_1~P3_4 → P4 → REF）；有结构真源（`structure_profile.json` 声明了章节表）时按其 `chapters[].order` 升序，不在真源里的现场文件按文件名数字键排在末尾照样合入。被排除的文件（`figure_prompts.md`、P2 父子同在时的子文件、空文件）逐一列在 merge 输出 JSON 的 `excluded[]` 里，**不静默丢弃**；`merged_files` 只列真正进了产物的文件（空文件不算在内）。

   **Phase 7 DoD（收口自检）：未逐项确认通过，不得向用户声明全文终稿完成**

   **🔴 委托盲检（遵上方总则的三步命令模板，主 agent 不得自评）**：merge 前必检。`<gate>`=`p7-dod`，`<files>`=`sections/P1_立项依据.md sections/P2_研究内容.md sections/P3_1_研究基础与可行性分析.md sections/P4_其他需要说明的情况.md sections/00_摘要_中文.md`；本 Phase 为终审、无下游 prewrite，verify 不带 `--section`/`--root`。**未过不得声明完成、不得 merge**。

   **本 Phase 完整 DoD 判据（全部核查项 + 脚本命令）以 `references/dod_checklist.json` gate=`p7-dod` 为默认真源；项目根有 `data/dod_selection.json`（用户协商关项）或 `structure_profile.json`（结构真源，非国自减免/改判）时，实际执行的是三步模板第 0 步经 `dod_project.py` 投影后的清单，被关/被减免的项不进盲检、已进报告「未执行的检查」留痕**：盲检subagent据此逐项核、能脚本核的先跑脚本，退出码非 0 即 fail-closed。该 gate 含 diagnosis_engine 无 ERROR、V-01~V-12 全量验证、gate-check --require-mcp、页数上限、去AI scan-all（`halfwidth_punct_in_cn` 中文句内半角标点、`english_misspelling` 英文铁错拼均为 ERROR 级硬阻断，判据见 JSON N47）、全文占位符清零、V-11 代表作、V-12 备选路线、合并顺序，及 N58 结构完整性、N66 上下标裸写软提醒。此处不再内联清单，避免与真源 drift。

At each phase:
- snapshot
- sync required state files
- halt for user confirmation

**🔴 DoD 停（适用所有 Phase，Mandatory）：** 每个 Phase 的 `delegate_review verify` 盲检 exit 0 通过后，**不得径直进入下一 Phase**。必须先把该 Phase 的 DoD 逐项结论（每项 pass/fail + 盲检返回的证据摘录，含软项 soft_flags）摆成清单给用户看，然后 **HALT 明确等用户确认**「本 Phase 通过、可进入下一 Phase」。用户未确认前不开写下一 Phase。若盲检环境派不出独立subagent（见各 Phase【P4·盲检降级告警】），一并如实告知用户由其亲自复核。

