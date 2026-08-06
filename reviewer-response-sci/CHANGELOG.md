# Changelog - Reviewer Response SCI Skill

## [2.28.2] - 2026-08-06

写保护批次（SPEC-round10-protected）：install_gate_hook settings.json 写盘原子化
+ hooks 非 list 点名报错；structure_signoff_gate 签字凭证写盘原子化；
context_guard_core 的 _gsw_left / _nsfc_left 两条判定修正同步。

## [2.28.1] - 2026-08-05

第十轮共享件修复同步（SPEC-round10）：delegate_review 重复 id 往严处倒 +
--section 路径消毒（#14/#15，fork 同构修）；citation_claim_check 非 str 摘要
防崩（#16）；citation_guard_core 连接重置/IncompleteRead fail-closed（#6）；
proofread 4 位年份不再误报数字格式不一致（#9）。
