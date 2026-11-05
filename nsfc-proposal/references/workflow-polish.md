> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

# Polish Mode · 六步执行清单（设计层完整流程见 06_Polish_Mode流程.md）

0. **导入整稿 → 机械原子化拆分（脚本流水线，取代旧"肉眼认标题手工切"；完整流程见 `references/06_Polish_Mode流程.md` Step 0）：**
   - **抽取**：`python3 scripts/extract_headings.py --source '<整稿>' --text-out tmp/draft_import.md --out tmp/heading_manifest.json`（一趟同产 draft_import.md + 标题真值；`.md/.txt` 认 `#`，`.docx` 走 styles.xml 反查 Word 标题样式，`.pdf`/无样式 → `headings:[]`）。抽后 sanity check：`<200 字`硬 HALT（疑扫描件/漏页），先与用户解决再往下。
   - **路径判定**（读 `tmp/heading_manifest.json`）：`trusted = headings 非空 且 无 low-confidence`。
     - **有标题路（trusted）**：机械字节切 `python3 scripts/split_headings.py --text tmp/draft_import.md --headings tmp/heading_manifest.json --atoms-dir sections --naming 'section_{major}_{标题简称}.md' --split-to-level <草稿最小标题层级> --manifest-out tmp/split_manifest.json`（落 `sections/`，原子名反映实节标题，主会话 Bash 零上下文；不套国自然固定 P1-P4，基金语义名留模板驱动第1期）。
     - **无标题路（headless：.pdf / 无 Word 标题样式的 .docx / 纯 .txt）**：子代理只认标题、不抄正文。先 `python3 scripts/heading_locate.py lines --text tmp/draft_import.md --out tmp/draft_lines.txt` 给整稿编行号；派认标题子代理（角色 prompt `references/headless_heading_prompt.md`）写 `tmp/llm_headings.json`；再 `python3 scripts/heading_locate.py locate --text tmp/draft_import.md --headings-in tmp/llm_headings.json --out tmp/heading_manifest.json` 按行号定位并核对原句（退出码 1 把 errors 交回子代理重做，最多 2 次）；然后用 `split_headings.py` 切，命名改为 `'section_{n:02d}_{标题简称}.md'`，`--split-to-level` 填 locate 输出的 `split_to_level`。小文件名的数字是文档顺序，不需要研究目标改名。完整步骤与已知限制见 06 的 0.3.3。
   - **Layer 1（确定性）**：`python3 scripts/split_audit.py --text tmp/draft_import.md --headings tmp/heading_manifest.json --manifest tmp/split_manifest.json --atoms-glob 'sections/*.md' --split-to-level <N> --root . --report tmp/split_audit_report.json`。**exit 0** 才进拼接核对；exit 1（漏/造/串/漂移，fail-closed）→ 回退重拆，**禁手改文件蒙混**。
   - **拼接核对（两路都跑）**：`python3 scripts/split_concat_check.py --text tmp/draft_import.md --manifest tmp/split_manifest.json --root .`。按清单顺序把小文件原始字节拼起来与整稿逐字节比较，另查 `sections/` 里清单外的 `.md`；split_audit 归一空白查不出的换行改空格由它兜住。exit 0 才进 Layer 2；exit 1 停下说明，不重试、不手改。
   - **Layer 2（LLM 反向核验，恒跑）**：split_audit exit 0 后跑 `split_boundary` gate——`delegate_review.py` pack `tmp/split_verify_ctx.md`（标题树 + 各 atom 锚定行，不含全文正文）→ 独立子代理 → verify。verdict：`[OK]`→pass 前进 / `[WRONG]`→回退重切（先修 extract_headings 真值）/ `[UNCERTAIN]`→**交用户裁决**（不自动动）。
   - **无编号研究目标原子的重命名**（国自然 P2 新结构专用）：原稿里研究目标段没有编号时，机械拆分出的原子名不带数字，合并排序会把它排到 2.7 之后。处置是把该原子改名为带 `2.0` 的名字（如 `section_2_2.0研究目标.md`），同时把 `tmp/split_manifest.json` 里对应条目的 `file` 与 `id` 改成新名，再重跑一次 Layer 1 的 `split_audit.py`，仍须 exit 0（实测改名加改 manifest 后 audit 仍 exit 0）。这是允许的手工改名，目的是调整合并顺序，不算上面 Layer 1 禁止的蒙混。
   - **P2 结构参照**：国自然 P2 的子结构与三套固定格式，见 `references/workflow-p0-p2.md` 的 Phase 2 P2 子结构真源一节。旧结构的在写项目不强制迁移，迁不迁由用户定，选保留的按真源里的过渡口径关掉 N17、N52、N53。
   - **用户确认拆分表与归属**（两层皆绿后）：主会话按 06 的 0.3.6 对应表写 `tmp/parts_draft.json`（小文件名到 P1、P2、P3、P4、其他），跑 `python3 scripts/section_parts.py table --manifest tmp/split_manifest.json --draft tmp/parts_draft.json --out tmp/split_table.md --root .` 出拆分表（按连续同归属分组，带容器、前后同属他组等提示），展示给用户；再把技能脚本与项目根的绝对路径填进 `section_parts.py confirm` 命令交给用户，由用户在自己的终端（Mac 终端或 App 终端面板，Windows PowerShell）粘贴运行、逐组回车、输入 确认，写出 `<项目根>/section_parts.json`。AI 不得代跑，非终端时它退出码 3。研究目标改名要在 confirm 之前做；重拆或回滚后要重新确认归属。
   - **signoff 解锁**：用户确认归属后跑 `python3 scripts/structure_signoff_gate.py confirm --root . --note "<用户确认要点>"` 落签字，解锁 Step 3 逐节 Write/Edit（否则 hook 拦每次改节写入）。**铁律：confirm 只能在两层绿 + 用户对拆分表说 yes 之后跑，AI 不得代用户自行 confirm。** 拆分脚本经 Bash 写 `sections/*.md` 不经 Write/Edit，故未签也能落盘拆分产物，真正被 signoff 门控的是 Step 3 逐节改写。
2. Generate strict review report first (`polish_review_report`).
   - Fallback: if `diagnosis_engine.py` fails, output a manual checklist covering: consistency / citation / writing style / format/length dimensions.
   - **已知限制**：写作风格评级对两类文件放行中文括号编号，以及分项行与年度计划行的第一个冒号，一类是文件名以 `P2` 开头的节，另一类是 `section_parts.json` 里经用户确认归属为 P2 或 P3 的小文件；两类取并集，只加放行不撤销。没有经 confirm 确认归属的 `section_` 开头的原子仍不放行，其中分项行与年度计划行的冒号会报 ERROR 级 `explanatory_colon`，计入终检的写作风格评级，要通过终检先让用户确认归属，或把这些冒号改成逗号或句号。项目符号与数字点的提示在任何文件里都要改。
3. Agree priority with user (rewrite vs polish vs keep).
   - **Hard block:** do not proceed to step 4 until user explicitly confirms priority order per section or sets a global default. Accept responses like "rewrite P1, polish P2, keep P3".
4. Revise section by section following issue order:
   - academic design/hypothesis
   - consistency
   - writing style
   - format/length
5. Run global consistency repair and full review.
6. Merge final output.
