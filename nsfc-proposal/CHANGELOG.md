# Changelog - NSFC Proposal Skill

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
