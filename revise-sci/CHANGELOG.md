# Revise-Sci Changelog

## [2.30.2] - 2026-08-20

第二十六轮（中文 Windows 兼容，两条外部用户实证的上游 bug）：① `install_gate_hook.py` 选解释器由"只判在不在 PATH"改成"先实跑一次再定"——Windows 商店那个 0 字节 `python3.exe` 占位程序在 PATH 里存在、实跑 rc=9009，此前会被选中，导致门禁三个钩子静默失效且不报错；② `env_preflight.py` / `run_pipeline.py`(2 处) / `ensure_global_skill.py`(2 处) / `install_gate_hook.py`的 subprocess 文本调用补 `encoding="utf-8", errors="replace"`——`text=True` 缺 `encoding=` 时按 locale 解码，cp936 中文 Windows 下遇 UTF-8 输出即 `UnicodeDecodeError`。判定逻辑与输出格式零改动。

## [2.30.1] - 2026-08-17

第二十五轮：去 AI 套话词表收编共享真源 `scripts/ai_cliche_terms.py`（vendored，开发真源 `_shared/`）——`common.py` 的 `AI_CLICHE_TERMS_EN`(27，尾部 moreover/furthermore 两条 L_REVISE_ONLY 有意差异)/`AI_CLICHE_TERMS_ZH`(18，含 3 条「……」留白) 改为直接绑定 `EFFECTIVE_EN/ZH["revise-sci"]` tuple，字面量删除；逐条逐序不变，`AI_STYLE_BANNED_PATTERNS`/`SOFT_STYLE_MARKERS`/hard·soft markers 全不动。

## [2.30.0] - 2026-08-17

第二十二轮 P0 流程完整性（R1）：一键 pipeline 接入可恢复状态机（`project_state.json.pipeline_gate` schema v1 + epoch，退出码 0=complete/1=失败/2=坏参数坏回执非法转换/3=预期暂停）。原子化后生成 `audit/comment_inventory.json` 并停点等 `--resume --confirm-comment-inventory <sha256>`（不调 revise_units）；确认后逐 unit 强制四选一 `revision_strategy`（别名归一 push_back）。final consistency 后固定顺序跑 numeric/xref/Methods 确定性锚（综述 Methods 记 na+理由），三层独立核查走 round22 envelope 双向绑定 `task_manifest_sha256`：detection 三轨返回自动校验、有真 finding 才生成 reverse 任务（pipeline 生成稳定 finding ID=`<track>-<canonical sha256 前12位>`）、极性 pass=confirmed/fail|na=refuted/problems=未核 rc=2，confirmed 须用户 `audit/adjudication.json` 逐条 fix（开新 epoch 重检）或 accept_with_rationale（manifest 未漂移）。DoD 解环：DoD JSON 七条与 pipeline 预检全用 `strict_gate --preclose`（`STRICT_PRECLOSE: PASS`，绝不冒充 final）；独立 DoD verify（delegate_review envelope 模式 `--expect-task-manifest`）+ 用户 `--confirm-dod-closure` 后才跑最终 bare gate（唯一 `STRICT_GATE: PASS`）。bare gate 自验 skill signature 与 receipt/closure 链，缺 `pipeline_gate` 默认 rc=2，legacy 仅 `--legacy-direct`+精确 allowlist signature 降级；上游内容变化 epoch+1 使旧确认/receipt 逻辑失效；旧项目 `--resume --migrate-round22` 显式迁移（保留产物、不推断确认）。skill signature 恢复 `*.py/*.md/*.json`。

## [2.29.6] - 2026-08-10

第十六轮共享件同步（SPEC-round16，盲检判合格）：折叠报告写失败全量明细回退 stdout；delegate_review（revise fork 同构跟进）畸形返回 exit 2；中毒缓存结构性判别（联网轨或 provider 轨）。

## [2.29.5] - 2026-08-09

第十五轮共享件同步（SPEC-round15，盲检判合格）：proofread 参考文献段剥离收敛 ref_section 单一口径（新增 vendored ref_section.py）；citation_claim_check 垃圾摘要按缺失处理 + 大批量警告折叠落报告。

## [2.29.4] - 2026-08-06

第十三轮同款 bug 修复（SPEC-round13）：cross_section_consistency GBK 不崩 + 聚类数值归一（45% 与 45.0% 不再误报漂移）；env_preflight argv 守卫。

## [2.29.3] - 2026-08-06

第十二轮共享件同步（SPEC-round12）：citation_guard_core 的 _http_get_json
补 ssl.SSLError / BadStatusLine 异常覆盖（fail-closed，retry 语义不变）。

## [2.29.2] - 2026-08-06

写保护批次（SPEC-round10-protected）：install_gate_hook settings.json 写盘原子化
+ hooks 非 list 点名报错；structure_signoff_gate 签字凭证写盘原子化；
context_guard_core 的 _gsw_left / _nsfc_left 两条判定修正同步。

## [2.29.1] - 2026-08-05

第十轮共享件修复同步（SPEC-round10）：delegate_review 重复 id 往严处倒 +
--section 路径消毒（#14/#15，fork 同构修）；citation_claim_check 非 str 摘要
防崩（#16）；citation_guard_core 连接重置/IncompleteRead fail-closed（#6）；
proofread 4 位年份不再误报数字格式不一致（#9）。

## 第十七轮完成记录（2026-03-09）

1. 已完成语义角色定位增强：`revise_units.py` 新增 `front/introduction/methods/results/discussion/conclusion` 角色映射，并在缺少显式结构锚点时尝试按评论语义将抽象评论路由到最可能 section。
2. 已完成单候选 section 的语义兜底：当评论没有结构化 hint，但语义角色只对应一个 section 时，系统可保守地使用该 section，而不再一律降级。
3. 已完成 `location_strategy` 落盘，便于后续审计具体采用了 `citation-anchor / response-seed / evidence-anchor / structured-heading / semantic-role / lexical-fallback` 中哪一种定位路径。
4. 已完成 profile-based Word 导出：`export_docx.py` 现在支持 `journal-manuscript / nature-review / cell-press / lancet-review` 四套 manuscript profile。
5. 已完成 Word 参考文献编号保留：当 markdown 文末 references 使用显式编号时，导出的 Word 不再丢失编号文本。
6. 已完成 `journal_style` 在 `preflight.py / run_pipeline.py / final_consistency_report.py / strict_gate.py` 中的贯通与审计。
7. 已完成 references 区块清洗回写：`build_reference_registry.py` 会过滤掉章节标题/目录项这类伪参考文献，并把干净的 bibliography 重新写回 markdown。
