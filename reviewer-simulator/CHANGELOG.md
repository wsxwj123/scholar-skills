# CHANGELOG

## [2.29.15] - 2026-08-17

第二十五轮：与 nsfc-proposal 共用的 12 条正则 + VAGUE 6 条收编共享真源 `scripts/ai_cliche_terms.py`（vendored，开发真源 `_shared/`）——`humanizer_zh.py` 的 `BANNED_PATTERNS` 15 条改由具名常量拼装（RSIM_TEMPLATE_TRANSITION/RSIM_AI_TRANSITION/RSIM_METAPHOR_NOUN4 差异层带家名，排列顺序本家口径、与 nsfc 有意不同），`VAGUE_PATTERNS = list(VAGUE_TABLE)`。判定行为零变化，`BULLET_PATTERNS` 3 条本家独有不动。

## [2.29.14] - 2026-08-10

第十六轮共享件同步（SPEC-round16，盲检判合格）：delegate_review（base 同步）畸形返回 exit 2；中毒缓存结构性判别（联网轨或 provider 轨，真实账本 271→271 回归锁）。

## [2.29.13] - 2026-08-09

第十五轮（SPEC-round15，盲检判合格）：C4 SKILL.md:130 空 index 措辞点破——豁免的是写作步骤（报告不写外部文献结论），不是脚本退出码，citation_guard 空 index 仍 exit 2 属正常返回（命令本体未动）；共享件同步：proofread 参考文献段剥离收敛 ref_section 单一口径（新增 vendored ref_section.py）。

## [2.29.12] - 2026-08-06

第十四轮（SPEC-round14）：5 处硬编码 ~/.claude/skills 路径改为 $SKILL_DIR 动态解析（新增技能安装目录解析节，三 runtime 安装位列出）；本机 9 条命令实测全 exit 0，脚本名/参数/退出码语义未动。

## [2.29.11] - 2026-08-06

第十三轮同款 bug 修复（SPEC-round13）：env_preflight parse_list argv 越界守卫。

## [2.29.10] - 2026-08-06

第十二轮共享件同步（SPEC-round12）：citation_guard_core 的 _http_get_json
补 ssl.SSLError / BadStatusLine 异常覆盖（fail-closed，retry 语义不变）。
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
