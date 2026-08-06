# Changelog - Polish SCI Skill

## [2.25.5] - 2026-08-06

第十四轮（SPEC-round14）：SKILL.md 自家破折号清除——第 89 行不再把"——"当标点用（自家硬禁项，言行一致化），规则内容与强度一字未变。

## [2.25.4] - 2026-08-06

第十三轮同款 bug 修复（SPEC-round13）：env_preflight parse_list argv 越界守卫。

## [2.25.3] - 2026-08-06

写保护批次（SPEC-round10-protected）：install_gate_hook settings.json 写盘原子化
+ hooks 非 list 点名报错；structure_signoff_gate 签字凭证写盘原子化；
context_guard_core 的 _gsw_left / _nsfc_left 两条判定修正同步。

## [2.25.2] - 2026-08-05

第十轮共享件修复同步（SPEC-round10）：delegate_review 重复 id 往严处倒 +
--section 路径消毒（#14/#15）；proofread 4 位年份不再误报数字格式不一致（#9）。
