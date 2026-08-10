# Changelog - sci2doc Skill

## [2.31.7] - 2026-08-09

第十五轮（SPEC-round15，盲检判合格）：C3 data_trace_gate 两处文件读取补 errors="replace"（GBK 混入不再 UnicodeDecodeError 裸崩，盲检实证两处均为真暴露面）；共享件同步：citation_claim_check 垃圾摘要按缺失处理 + 警告折叠落报告、delegate_write_core 键类型归一 + 缺条目报出 + 畸形 exit 2。另修 test_data_trace_gate 直跑空转（补 __main__，8 条真执行）。

## [2.31.6] - 2026-08-06

第十三轮同款 bug 修复（SPEC-round13）：prewrite_gate GBK 混入不崩；env_preflight parse_list argv 越界守卫。

## [2.31.5] - 2026-08-06

第十二轮共享件同步（SPEC-round12）：citation_guard_core 的 _http_get_json
补 ssl.SSLError / BadStatusLine 异常覆盖（fail-closed，retry 语义不变）。

## [2.31.4] - 2026-08-06

写保护批次（SPEC-round10-protected）：install_gate_hook settings.json 写盘原子化
+ hooks 非 list 点名报错；structure_signoff_gate 签字凭证写盘原子化；
context_guard_core 的 _gsw_left / _nsfc_left 两条判定修正同步。

## [2.31.3] - 2026-08-05

第十轮共享件修复同步（SPEC-round10）：delegate_review 重复 id 往严处倒 +
--section 路径消毒（#14/#15）；citation_claim_check 非 str 摘要防崩（#16）；
citation_guard_core 连接重置/IncompleteRead fail-closed（#6）。

## [2.31.2] - 2026-08-05

citation_guard 离线时 report `ok` 压 false（SPEC-round9 缺陷 E1，分支 fix/round9）。

- 缺陷：report `"ok": status in ("verified", "unverified")` —— 离线跑
  （status=unverified，一轮没做任何联网核验）照样 ok=true，只看 ok 的调用方会
  误判"文献已核实"；旁边注释"ok=本次没查出问题"的语义本身易误读。
- 修复：ok 改为 `status == "verified"`，语义=整体可采信；退出码与 ok 解耦
  （E1b 用户口径）：离线无硬失败仍 exit 0，条目有真硬失败/空索引仍非 0，
  退出码行为一字不变。不新增 failure_reason 码。
- 验收：scripts/test_e1_offline_ok.py 修前红（离线 ok=true）修后绿。
