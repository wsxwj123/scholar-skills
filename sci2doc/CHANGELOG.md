# Changelog - sci2doc Skill

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
