> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

# Polish Mode · 六步执行清单（设计层完整流程见 06_Polish_Mode流程.md）

0. **导入整稿 → 机械原子化拆分（脚本流水线，取代旧"肉眼认标题手工切"；完整流程见 `references/06_Polish_Mode流程.md` Step 0）：**
   - **抽取**：`python3 scripts/extract_headings.py --source '<整稿>' --text-out tmp/draft_import.md --out tmp/heading_manifest.json`（一趟同产 draft_import.md + 标题真值；`.md/.txt` 认 `#`，`.docx` 走 styles.xml 反查 Word 标题样式，`.pdf`/无样式 → `headings:[]`）。抽后 sanity check：`<200 字`硬 HALT（疑扫描件/漏页），先与用户解决再往下。
   - **路径判定**（读 `tmp/heading_manifest.json`）：`trusted = headings 非空 且 无 low-confidence`。
     - **有标题路（trusted）**：机械字节切 `python3 scripts/split_headings.py --text tmp/draft_import.md --headings tmp/heading_manifest.json --atoms-dir sections --naming 'section_{major}_{标题简称}.md' --split-to-level <草稿最小标题层级> --manifest-out tmp/split_manifest.json`（落 `sections/`，原子名反映实节标题，主会话 Bash 零上下文；不套国自然固定 P1-P4，基金语义名留模板驱动第1期）。
     - **无标题路（headless：.pdf / 无 Word 标题样式的 .docx / 纯 .txt）**：**HALT 兜底**——不派拆分、不写任何 atom，提示用户"未检出可靠标题层级，请转成带 `#`/Word 标题样式的 .md/.docx 或补标题后重传"。**绝不静默乱拆。**
   - **Layer 1（确定性）**：`python3 scripts/split_audit.py --text tmp/draft_import.md --headings tmp/heading_manifest.json --manifest tmp/split_manifest.json --atoms-glob 'sections/*.md' --split-to-level <N> --root . --report tmp/split_audit_report.json`。**exit 0** 才进 Layer 2；exit 1（漏/造/串/漂移，fail-closed）→ 回退重拆，**禁手改文件蒙混**。
   - **Layer 2（LLM 反向核验，恒跑）**：split_audit exit 0 后跑 `split_boundary` gate——`delegate_review.py` pack `tmp/split_verify_ctx.md`（标题树 + 各 atom 锚定行，不含全文正文）→ 独立子代理 → verify。verdict：`[OK]`→pass 前进 / `[WRONG]`→回退重切（先修 extract_headings 真值）/ `[UNCERTAIN]`→**交用户裁决**（不自动动）。
   - **用户确认拆分表**（两层皆绿后）：展示 split map + audit 结果，等用户明确 "yes"/adjust。
   - **signoff 解锁**：用户确认后跑 `python3 scripts/structure_signoff_gate.py confirm --root . --note "<用户确认要点>"` 落签字，解锁 Step 3 逐节 Write/Edit（否则 hook 拦每次改节写入）。**铁律：confirm 只能在两层绿 + 用户对拆分表说 yes 之后跑，AI 不得代用户自行 confirm。** 拆分脚本经 Bash 写 `sections/*.md` 不经 Write/Edit，故未签也能落盘拆分产物，真正被 signoff 门控的是 Step 3 逐节改写。
2. Generate strict review report first (`polish_review_report`).
   - Fallback: if `diagnosis_engine.py` fails, output a manual checklist covering: consistency / citation / writing style / format/length dimensions.
3. Agree priority with user (rewrite vs polish vs keep).
   - **Hard block:** do not proceed to step 4 until user explicitly confirms priority order per section or sets a global default. Accept responses like "rewrite P1, polish P2, keep P3".
4. Revise section by section following issue order:
   - academic design/hypothesis
   - consistency
   - writing style
   - format/length
5. Run global consistency repair and full review.
6. Merge final output.
