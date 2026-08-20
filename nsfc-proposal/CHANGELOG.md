# Changelog - NSFC Proposal Skill

## [2.37.2] - 2026-08-20

第二十六轮（中文 Windows 兼容，两条外部用户实证的上游 bug）：① `install_gate_hook.py` 选解释器由"只判在不在 PATH"改成"先实跑一次再定"——Windows 商店那个 0 字节 `python3.exe` 占位程序在 PATH 里存在、实跑 rc=9009，此前会被选中，导致门禁三个钩子静默失效且不报错；② `git_checkpoint.py` / `env_preflight.py` / `install_gate_hook.py`的 subprocess 文本调用补 `encoding="utf-8", errors="replace"`——`text=True` 缺 `encoding=` 时按 locale 解码，cp936 中文 Windows 下遇 UTF-8 输出即 `UnicodeDecodeError`。🔴 `git_checkpoint.py` 是回滚安全网，技能自己写的中文 commit message 就会触发它崩，中文 Windows 用户开始写稿后第一次调检查点即挂。判定逻辑与输出格式零改动。

## [2.37.1] - 2026-08-17

第二十五轮：去 AI 套话词表与共用正则收编共享真源 `scripts/ai_cliche_terms.py`（vendored，开发真源 `_shared/`）——`humanizer_zh.py` 的 `AI_CLICHE_TERMS_ZH`(11)/`AI_CLICHE_TERMS_EN`(25) 改从 `EFFECTIVE_ZH/EN["nsfc-proposal"]` 取；`BANNED_PATTERNS` 15 条改由具名常量拼装（12 条与 reviewer-simulator 共用 + NSFC_METAPHOR_VERB/NOUN12 差异层 + `_AI_CLICHE_RE` 现算条，排列顺序本家口径不变）；`VAGUE_PATTERNS = list(VAGUE_TABLE)`。判定行为零变化，`OVERUSE_PATTERNS`(≥3 逃生口)/阈值/严重度全不动；顺带修正「比喻正则对齐 sci2doc」错注释（实测不等，PLAN D13）。

## [2.37.0] - 2026-08-17

第二十四轮（字数/页数上限单一真源，minor）：同一组上限（400/300/500/500/30）此前散在 13 处代码 + 6 份文档，收成 `word_counter.py` 顶部唯一真源 `NSFC_WORD_MAX`/`NSFC_PAGE_MAX` + 两个纯函数 `resolve_word_limit(root, filename)`（九行判定表：无真源/坏/未确认/无 chapters 键 → 国自然默认；chapters 受管且该章 `word_max` 合法（含 0）→ 声明值；受管但缺/非法/未列该章 → `unset` 交人工，绝不悄悄按默认判；读口不可用打 `WORD_LIMIT: WARN` 按国自然全量）与 `resolve_page_limit(root)`（读 `proposal_profile.json.page_limit`，合法非负 int（含 0）且异于国自然默认 30 → 声明值，其余回落 30；恒返回 int）。新增 `word_counter.py check --root . --file <章>|--pages <目录>` 子命令：单行 JSON 六键 `kind/target/count/limit/limit_source/ok`，超限与上限不可判都是 rc 0（退出码与判定正交），`unset` 时打 `WORD_LIMIT: UNSET`（含「不得判 pass」）+ 处置行，目标读不出 rc 1 + `WORD_LIMIT: MISSING`，用法错 rc 2；纯读不写任何文件。消费方全部改读真源：`diagnosis_engine._abstract_limits` 签名 `(prof)`→`(root)` 改调 resolver（删自有 chapters 遍历，skipped_checks 条目四字面量不变），`full-review`/`polish-review` 的 `--page-limit` 缺省 30→None（显式传值 > 项目声明 > 国自然默认，报告 `page_limit` 恒 int），markdown 兜底与 `state_manager` 四处 30/500 字面量改引常量（取值不变）。DoD 五条（N21/N27/N37/N38/N46）`check` 去数字改「脚本给出上限与判定」口径、`script` 改指 `word_counter.py check`（r23 §10.1 投影产物逐字节基线按本轮重建，`nsfc_bound`/`check_other` 两张白名单一项不增不减）。国自然默认项目零变化：四个既有子命令、`state_manager` 全部子命令、报告六项基线逐字节不变。

## [2.36.0] - 2026-08-17

第二十三轮（非国自 DoD 按国自结构查，minor）：**DoD 层项目类型感知**。`dod_project.py` 在「全量清单 − 用户手关项」之外再减「本项目类型不适用的项」：仅当 `structure_profile.json` 合法已确认 `funding_scheme: "other"`（判据一处定义——`structure_profile.scheme_is_other()`，由 `_p2_outline_scope_enabled` 提公开、旧名转发行为零变化；用户 DoD 手关 HRCK-V-RULES 不反推项目类型）时，按 `dod_checklist.json` 声明键执行：13 项 `nsfc_bound`（取值锁死 07 §7.1 封闭集四 id，含用户裁决"免5留1"的 N11/N16/N20/N26/N49；N50/N43/N45 明确不标）移出盲检并逐条留痕，6 项 `check_other`（N52/N53/N54/N57/N58 共用逐字节同一段"按结构真源查齐"文案 + N62 专属）改判不减免。stdout 新增 `waived`/`repointed`/`funding_scheme`/`skipped_checks`/`repointed_ids` 五键，计数不变式 `active + waived + disabled == total`（重叠归 waived）；投影产物顶层带 `skipped_checks`（scheme=other 时同 stdout，nsfc 恒 `[]`）。fail-safe 恒收紧：真源缺失/坏 JSON/非法/未确认按 nsfc 全量，读口不可用打 `DOD_SCHEME: WARN`，声明键非法打 `DOD_CHECKLIST: INVALID` + rc 1 + 按「不减免、不改判」从严照写，scheme=other 而整份清单无标记打 `DOD_SCHEME: NO_MARKERS`（旧项目副本提示）；两层 fail-safe 各自独立。接线：三步模板第 0 步触发条件改为「`data/dod_selection.json` **或** `structure_profile.json` 任一存在就跑投影」（05 Step 0.4b、08 §2.9 同步，07 §7.1/§7.2/§7.3 登记 DoD 层投影与四出口）。国自项目零变化：无真源时产物除顶层多出 `skipped_checks: []` 外逐字节不变，既有 stderr/退出码/`resolve_scope` 返回全不动。

同版本随行收口：`word_counter.py` 计数口径对齐 Word（用户实测对照后亲改，主会话审核提交）——剥 markdown 符号后按中文单字 + 英文 token 计数、不再计标点；消费者仅字数/页数门，计数变小方向宽松，非共享件、无测试锁定旧口径。

## [2.35.1] - 2026-08-17

第二十二轮延期项（R4·T3/T5 修正，patch）：**T3** P2 段落级大纲门项目类型判据修正——`is_managed(P2)` 不再笼统由 `v_rules_disabled`（HRCK-V-RULES 在 skipped 即算）反推：skipped 条目按 reason 分流，`dod_selection.disabled`（用户 DoD 关项）只影响 DoD、不改项目类型；`structure_profile.funding_scheme=other` 写入的条目才启用 P2 段落级大纲门。仍走 `safe_resolve_scope` 继承 round21 全部读口 fail-safe（缺失/坏 JSON/未确认/非法 UTF-8/模块坏一律收敛国自然口径、零 traceback），DoD 关项留痕（skipped_checks）不受影响。**T5** `load_index()` 精确增捕 `UnicodeDecodeError`——非法 UTF-8 索引与目录/权限问题同归既有 `IndexUnreadableError`（`corruption=unreadable`、行列位置 null、bad indexes 空，不新增第四态），四个只读子命令与 `state_manager gate-check` 结构化拒绝 rc=2、无 traceback、原文件字节不变；syntax/entries 两态零漂移。

## [2.35.0] - 2026-08-11

第二十一轮欠账清理（T1-T6 里 nsfc 承担的六项落点）：**T1** 开场问基金归属——监工卡通用化+第 7 条常驻提示；全新项目（无 `project_state.json` 且无 `structure_profile.json`）问一次二选一：答国自然不落任何文件，答其他基金走既有五步结构提取链（只承诺同一会话内不再问，跨会话可能重复问，如实登记）。**T2** 文献切片节标识统一裸 `"P1"`——写入端（merge-refs/renumber）只写新值；检查链（matrix-check/find-orphans/stats/gate-check P1 计数）新旧两值都认；切片链只认新值，存量账本用新入口 `citation_validator.py normalize-sections --index <索引> [--dry-run]`（幂等、原子写、坏类型一字不动）一次性归一，check-gates 对「含旧值不含新值」条目发 WARN 附命令。**T3** 非国自然项目（四维表已关）P2 新增前置计划环节——作用域三函数落 `structure_profile.py` 唯一定义（`section_number_of`/`safe_resolve_scope`+`v_rules_disabled`/`is_managed`），`outline_manager` 扩到 P1+P2、闸口分节感知（新 reason `outline_section_not_covered`），P2 段落契约 rc_id 必填、不要求承重；国自然项目 P2 零影响；结构真源读口六种坏形态收敛「空 scope=国自然最严口径」零 traceback。**T4** 英文 AI 套话 25 条自 gsw `FORBIDDEN_EXACT` 平移（WARNING 不硬拦、小写化子串匹配、误报面有意保留）。**T5** 索引 JSON 损坏 fail-closed——语法/结构/不可读三态统一 rc=2 结构化拒绝（`corruption: syntax/entries/unreadable`），四个只读子命令逐字一致、零裸崩；mcp 缓存坏按空缓存回落全量核验（不硬拦、不回写坏文件）；语法坏索引退出码由 1（裸崩默认）收紧为 2。**T6** 重烘出厂 `templates/reference.docx`：图注/表注样式补上 10pt（模板停在 2026-07-14、烘焙脚本 07-16 改的 10pt 从未入模板）。

## [2.34.0] - 2026-08-11

第十九轮（用户实测报告「开新项目、尤其省自然这类非国自然标书时不会自动写立项依据大纲」；小任务轻量档，三轮盲检判合格）：**补上 P1 立项依据的段落级大纲环节**——这是 nsfc 从来没有过的一环（rw 有 Phase 1.7 出大纲＋签字、gsw 有 storyline，nsfc 的结构签字签的是四维表＝"做什么研究"，不是"立项依据怎么讲"；非国自然项目 HRCK-V-RULES 被关掉后连四维表都没有，从检索直接跳到子代理闷头写整节）。

新增 `scripts/outline_manager.py`（`confirm` / `check`）与真源 `data/outline.json`：AI 出草稿落 `tmp/outline_draft.json`（任何脚本都不读它）→ 用户逐条改 → 用户点头后 `confirm` 才落盘真源；段落级要点从严（每段 `gist`/`conclusion` 必填、≥1 承重段且承重段必须挂文献）；承重论点核证复用既有 `pack-prep` → 独立子代理 → `citation_claim_check` 链，不新造第二套。两道开写前闸口（`delegate_write` 的 `pack-write`/`pack-prep` + `prewrite_gate` 的 `outline_fresh`）：未确认 / 被改过 / 核证过期 / 检查器不可用一律 fail-closed；`data/outline.json` 是唯一大纲候选（多一个候选就多一条绕过路径）；存量老项目按节豁免（无真源 + 有实质正文 + `glob.escape`），占位稿不算写过。`confirm --from` 可指真源自身（realpath 判定，剥签名后同一套校验），覆盖前留 `.prev`——用户手改的大纲不会被旧草稿无声覆盖。去AI顺带对齐两条：11 条中文套话进 `BANNED_PATTERNS`（ERROR）、破折号形态逐字节照抄 gsw `EM_DASH_RE`（数字区间仍豁免）。

🔴 **闸口强度如实登记**：拦得住"无意的忘记"，**拦不住"故意的绕过"**——`content_hash` 算法写在被约束方读得到的文件里、没有秘密，`--note` 只校验非空而命令行是 AI 自己敲的。"AI 不得替用户 confirm"是纪律约束，没有任何机制在执行它，且这类绕法走的是正常命令、留痕很淡。任何文档都不许写成"强制""AI 关不掉"。

## [2.33.9] - 2026-08-10

第十八轮（SPEC-round18，第十七轮盲检观察项 O4，小任务轻量档，盲检 M1/M2 变异全红判合格）：畸形文献索引不再裸崩——entries 混入非对象元素时 gate-check 由 AttributeError traceback 改为结构化拒绝（ok=false / failed_at=literature_index / 点名 0 基下标与类型 / rc=2 / 索引文件一字不动）；读索引收敛 citation_validator.load_index 单入口 fail-closed，四个消费点（语义门/gate 链/写作循环/评审矩阵）零散弹补丁；离线与联网同形（校验在分叉前，拒绝时不触网）；合法四态与基线逐字对照仅差时间戳。SKILL.md 排障表补 failed_at=literature_index 处置行。

## [2.33.8] - 2026-08-10

第十七轮（SPEC-round17 P4-rev，用户两次拍板收敛，盲检判合格）：离线 gate 未核验改为阻断——判定挪到条目级，全部条目都持 TTL 内可信联网核验记录（短路保真）才放行，任何一条没验过/过期/中毒（T8 判别式打回）即 ok=false、failed_at=citation、rc=2；发证与放行分开：聚合 verification_status 照旧永不写 verified（T9-c 一字未动），放行凭旧证时 citation note + 顶层 warnings 明示"本轮未做新核验"；阻断明细写清销账路径。联网路径逐字不变。第十六轮"离线接受 unverified 不阻断"（T9-d）作废，test_gate_offline_unverified 首条断言随规则翻转。04_文献管理.md 离线段同步改准。

## [2.33.7] - 2026-08-10

第十六轮技术债清理（SPEC-round16，盲检判合格）：离线发证路径堵死——MCP 缓存命中不再产出 verified:true（缓存是本地 JSON 不算核验证据；编造文献离线曾拿 96 分置信度，实证修掉）；--offline 补 help 且措辞与短路行为逐条对应；04_文献管理.md"允许 --offline 临时通过"矛盾口径改准；gate 链适配：离线模式 citation 维接受 unverified 不阻断（联网仍必须 verified）。共享件同步：折叠报告回退、delegate_review 畸形 exit 2、元素级校验、中毒缓存结构性判别。

## [2.33.6] - 2026-08-09

第十五轮共享件同步（SPEC-round15，盲检判合格）：citation_claim_check 垃圾摘要（非 str）按缺失处理不放行 + 大批量警告折叠落报告；delegate_write_core 键类型归一（矩阵主键与账本主键类型不同不再静默拿空）+ 缺条目报出 + lit_section 畸形按契约 exit 2。

## [2.33.5] - 2026-08-06

第十三轮同款 bug 修复（SPEC-round13）：prewrite_gate GBK 混入不崩；env_preflight parse_list argv 越界守卫。

## [2.33.4] - 2026-08-06

第十二轮共享件同步（SPEC-round12）：citation_guard_core 的 _http_get_json
补 ssl.SSLError / BadStatusLine 异常覆盖（fail-closed，retry 语义不变）。

## [2.33.3] - 2026-08-06

写保护批次（SPEC-round10-protected）：install_gate_hook settings.json 写盘原子化
+ hooks 非 list 点名报错；structure_signoff_gate 签字凭证写盘原子化；
context_guard_core 的 _nsfc_left 精确匹配（p1 不再误吞 p10_*，本家直接相关）+
_gsw_left 判定修正同步。

## [2.33.2] - 2026-08-05

第十轮共享件修复同步（SPEC-round10）：delegate_review 重复 id 往严处倒 +
--section 路径消毒（#14/#15）；citation_claim_check 非 str 摘要防崩（#16）；
citation_guard_core 连接重置/IncompleteRead fail-closed（#6）。

## [2.33.1] - 2026-08-05

参考文献章节标题识别收敛到共享件（SPEC-round9 缺陷 E2d，分支 fix/round9）。

- section_merger.py 的 `_REF_HEADING_RE`（`^\s*(参考文献|References)\s*$`，只认
  两种整行）换成 `_shared/ref_section.py` vendored 副本的
  `is_reference_heading`。修前 `## **8. 参考文献**`（pandoc 渲染成 Heading
  段落、纯文本 "8. 参考文献"）与 `## 参考文献：` 都认不得 → merge-docx 后处理
  的"进参考文献章节停止上标"失效 → 文献列表条目编号 [N] 被误转上标。
  docx 段落文本没有 markdown 符号，而共享件只在带 # 的标题里吃编号前缀，
  故 docx 侧等价形态 = 原文与补 "# " 前缀各判一次（仍线性扫描，无正则）。
- 不误伤同力度：`## 参考文献格式说明` 这类带尾巴的标题、正文里出现
  "参考文献"的句子、文献条目首行都不触发停止。
- 验收：scripts/test_ref_heading_shared.py（同一性断言 + 两侧单元 + docx
  端到端）修前红修后绿；三份 ref_section.py 与 `_shared/` 真源 md5 一致，
  sync_vendored --check 绿。
