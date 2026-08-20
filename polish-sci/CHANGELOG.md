# Changelog - Polish SCI Skill

## [2.26.2] - 2026-08-20

第二十六轮（中文 Windows 兼容，两条外部用户实证的上游 bug）：① `install_gate_hook.py` 选解释器由"只判在不在 PATH"改成"先实跑一次再定"——Windows 商店那个 0 字节 `python3.exe` 占位程序在 PATH 里存在、实跑 rc=9009，此前会被选中，导致门禁三个钩子静默失效且不报错；② `env_preflight.py` / `proofread_polished.py` / `install_gate_hook.py`的 subprocess 文本调用补 `encoding="utf-8", errors="replace"`——`text=True` 缺 `encoding=` 时按 locale 解码，cp936 中文 Windows 下遇 UTF-8 输出即 `UnicodeDecodeError`。判定逻辑与输出格式零改动。

## [2.26.1] - 2026-08-17

第二十五轮：去 AI 套话词表收编共享真源 `scripts/ai_cliche_terms.py`（vendored，开发真源 `_shared/`）——`common.py` 的 `AI_CLICHE_TERMS_EN`(25)/`AI_CLICHE_TERMS_ZH`(18，含 3 条「……」留白) 改为直接绑定 `EFFECTIVE_EN/ZH["polish-sci"]` tuple，字面量删除；逐条逐序不变，`find_ai_style_markers`/`strict_gate` 判定与 marker 顺序零变化。

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
