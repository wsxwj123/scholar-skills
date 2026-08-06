# CHANGELOG

## 2.29.9 — 2026-08-06

写保护批次（SPEC-round10-protected）：install_gate_hook settings.json 写盘原子化
+ hooks 非 list 点名报错；structure_signoff_gate 签字凭证写盘原子化；
context_guard_core 的 _gsw_left / _nsfc_left 两条判定修正同步。

## 2.29.8 — 2026-08-05

第十轮共享件修复同步（SPEC-round10）：delegate_review 重复 id 往严处倒 +
--section 路径消毒（#14/#15）；citation_guard_core 连接重置/IncompleteRead
fail-closed（#6）；proofread 4 位年份不再误报数字格式不一致（#9）。

## 2.29.7 — 2026-08-05

- fix(citation_guard) E3a 数据安全：`--offline --write-back` 不再把索引里此前在线验过的
  `verified: true` 记录刷成 false——离线轮写回时 claimed-true 记录整条保留原值；
  缺新鲜时间戳/在线来源证明（防护拿不到证据）的记录同样保留并 stderr 留痕（fail-closed）。
- fix(citation_guard) E3b 缓存复用：TTL 内已在线核验的条目在线跑短路复用上次写回结果
  （复用 `_shared/citation_guard_core.py` 的 `entry_is_fresh_verified`，含
  `--require-mcp` / 在线强度的 strictness 语义）；离线跑绝不短路。
- fix(citation_guard) E1：离线时 report `ok` 压成 false（语义改为"整体可采信"，
  仅 `status=verified` 为 true）；status 仍 unverified、无硬失败仍 exit 0、
  退出码映射一字不变（verified/unverified→0，failed/empty→2）。
- 测试：新增 `scripts/test_citation_offline_writeback.py`（9 条：E3a 两步样本 +
  防护失效路径 2 条 + E3b 短路/不短路/过期缓存 3 条 + E1 三条）。
