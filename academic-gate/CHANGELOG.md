# Changelog - academic-gate

## [0.9.2] - 2026-08-06

写保护批次修复（SPEC-round10-protected，用户开维护者豁免后修）：

- install_gate_hook.py：settings.json 写盘原子化（tmp + os.replace，kill 中途
  不留截断配置，保留 .bak 双保险）；hooks 字段非 list 时点名报错（第几条
  entry、matcher、实际类型），不再吞成无定位 error。
- structure_signoff_gate.py：签字凭证写盘原子化（同款 kill 中途截断问题）。
- context_guard_core.py：`_gsw_left` 遍历时跳过无 status 键的条目——老格式
  figure_analyzed 事件不再把该节的 done 盖成 None（F10 差集门禁少拦一次的洞）；
  `_nsfc_left` 改精确匹配，`p1` 前缀不再误吞 `p10_*`（"P2" 吞 "p20_*" 同理）。
