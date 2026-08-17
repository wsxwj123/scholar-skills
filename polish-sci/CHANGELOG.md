# Changelog - Polish SCI Skill

## [2.26.0] - 2026-08-17

第二十二轮 P0 流程完整性（R3）：解除 DoD 自引用。`strict_gate.py` 增 `--unit-checks-only` preclose 模式——只跑现役逐 unit 全部机械检查，任一问题 rc=1；unit 全过后在读取 `.review_return_polish-dod.json` 之前即返回 rc=0，成功唯一输出 `STRICT_UNIT_CHECKS: PASS`（绝不输出最终交付 `STRICT_GATE: PASS`）。DoD JSON 的 PL-G1~G6 六条脚本命令全部改带该 flag（盲检期机械预检不再依赖尚未产生的 PL-G11）；SKILL 最终交付命令保持无 flag 的 bare gate——缺有效 PL-G11 仍 rc=1，强度不降。

## [2.25.7] - 2026-08-10

第十六轮共享件同步（SPEC-round16，盲检判合格）：delegate_review 畸形返回（顶层非数组）exit 2，与"审查发现问题"的 exit 1 语义分清（base 6 家同步）。

## [2.25.6] - 2026-08-09

第十五轮共享件同步（SPEC-round15，盲检判合格）：proofread 参考文献段剥离收敛 ref_section 单一口径（新增 vendored ref_section.py；此前文献条目被拼写/单位检查空转误报）；另修 test_delegate_review 坏 fixture（tmp→tmp_path，pytest 与直跑双通）。

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
