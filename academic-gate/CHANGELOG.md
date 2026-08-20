# Changelog - academic-gate

## [0.9.3] - 2026-08-20

第二十六轮（中文 Windows 兼容）：解释器探测从"只判存在"改成"先实跑再定"。

- `hooks/hooks.json` 五条命令：`$(command -v python3 || command -v python)` 改成
  `$(python3 -c '' >/dev/null 2>&1 && command -v python3 || command -v python)`。
  Windows 商店那个 0 字节 `python3.exe` 占位程序会让 `command -v` 成功（`||` 永不触发），
  但实跑 rc=9009 → 五个钩子退出码 49、静默失效不报错。外部用户在 Windows 11 中文版
  实测这一改法把三个钩子的退出码从 49 变回 0。
- `scripts/install_gate_hook.py`（vendored，真源 `_shared/`）：`_interpreter()` 同病同治，
  按 `_hook_command_runs()` 的思路加 `_runs()` 探针，`python3 -c ""` 能 rc=0 才认。
- 全部 subprocess 文本调用显式 `encoding="utf-8", errors="replace"`：`text=True` 缺
  `encoding=` 时按 locale 解码，cp936 中文 Windows 下遇 UTF-8 输出即 `UnicodeDecodeError`。

🔴 **发布说明必写：本版改了钩子定义（`hooks/hooks.json`），Codex 端用户升级后必须
重跑一次 `/hooks` 把五条钩子重新信任**——Codex 按钩子定义算 hash 记账，定义一变就当
没信任过，没信任的钩子会被直接跳过且不报错（改 `scripts/` 里的 Python 不影响信任）。

## [0.9.2] - 2026-08-06

写保护批次修复（SPEC-round10-protected，用户开维护者豁免后修）：

- install_gate_hook.py：settings.json 写盘原子化（tmp + os.replace，kill 中途
  不留截断配置，保留 .bak 双保险）；hooks 字段非 list 时点名报错（第几条
  entry、matcher、实际类型），不再吞成无定位 error。
- structure_signoff_gate.py：签字凭证写盘原子化（同款 kill 中途截断问题）。
- context_guard_core.py：`_gsw_left` 遍历时跳过无 status 键的条目——老格式
  figure_analyzed 事件不再把该节的 done 盖成 None（F10 差集门禁少拦一次的洞）；
  `_nsfc_left` 改精确匹配，`p1` 前缀不再误吞 `p10_*`（"P2" 吞 "p20_*" 同理）。
