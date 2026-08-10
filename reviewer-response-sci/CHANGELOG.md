# Changelog - Reviewer Response SCI Skill

## [2.28.6] - 2026-08-10

第十六轮共享件同步（SPEC-round16，盲检判合格）：折叠报告写失败全量明细回退 stdout；delegate_review（rr fork 同构跟进）畸形返回 exit 2；中毒缓存结构性判别（联网轨或 provider 轨）。

## [2.28.5] - 2026-08-09

第十五轮共享件同步（SPEC-round15，盲检判合格）：proofread 参考文献段剥离收敛 ref_section 单一口径（新增 vendored ref_section.py）；citation_claim_check 垃圾摘要按缺失处理 + 大批量警告折叠落报告。

## [2.28.4] - 2026-08-06

第十三轮同款 bug 修复（SPEC-round13）：env_preflight parse_list argv 越界守卫。

## [2.28.3] - 2026-08-06

第十二轮共享件同步（SPEC-round12）：citation_guard_core 的 _http_get_json
补 ssl.SSLError / BadStatusLine 异常覆盖（fail-closed，retry 语义不变）。

## [2.28.2] - 2026-08-06

写保护批次（SPEC-round10-protected）：install_gate_hook settings.json 写盘原子化
+ hooks 非 list 点名报错；structure_signoff_gate 签字凭证写盘原子化；
context_guard_core 的 _gsw_left / _nsfc_left 两条判定修正同步。

## [2.28.1] - 2026-08-05

第十轮共享件修复同步（SPEC-round10）：delegate_review 重复 id 往严处倒 +
--section 路径消毒（#14/#15，fork 同构修）；citation_claim_check 非 str 摘要
防崩（#16）；citation_guard_core 连接重置/IncompleteRead fail-closed（#6）；
proofread 4 位年份不再误报数字格式不一致（#9）。
