# Changelog - NSFC Proposal Skill

## [2.33.4] - 2026-08-06

第十二轮共享件同步（SPEC-round12）：citation_guard_core 的 _http_get_json
补 ssl.SSLError / BadStatusLine 异常覆盖（fail-closed，retry 语义不变）。

## [2.33.3] - 2026-08-06

写保护批次（SPEC-round10-protected）：install_gate_hook settings.json 写盘原子化
+ hooks 非 list 点名报错；structure_signoff_gate 签字凭证写盘原子化；
context_guard_core 的 _nsfc_left 精确匹配（p1 不再误吞 p10_*，本家直接相关）+
_gsw_left 判定修正同步。

## [2.33.2] - 2026-08-05

第十轮共享件修复同步（SPEC-round10）：delegate_review 重复 id 往严处倒 +
--section 路径消毒（#14/#15）；citation_claim_check 非 str 摘要防崩（#16）；
citation_guard_core 连接重置/IncompleteRead fail-closed（#6）。

## [2.33.1] - 2026-08-05

参考文献章节标题识别收敛到共享件（SPEC-round9 缺陷 E2d，分支 fix/round9）。

- section_merger.py 的 `_REF_HEADING_RE`（`^\s*(参考文献|References)\s*$`，只认
  两种整行）换成 `_shared/ref_section.py` vendored 副本的
  `is_reference_heading`。修前 `## **8. 参考文献**`（pandoc 渲染成 Heading
  段落、纯文本 "8. 参考文献"）与 `## 参考文献：` 都认不得 → merge-docx 后处理
  的"进参考文献章节停止上标"失效 → 文献列表条目编号 [N] 被误转上标。
  docx 段落文本没有 markdown 符号，而共享件只在带 # 的标题里吃编号前缀，
  故 docx 侧等价形态 = 原文与补 "# " 前缀各判一次（仍线性扫描，无正则）。
- 不误伤同力度：`## 参考文献格式说明` 这类带尾巴的标题、正文里出现
  "参考文献"的句子、文献条目首行都不触发停止。
- 验收：scripts/test_ref_heading_shared.py（同一性断言 + 两侧单元 + docx
  端到端）修前红修后绿；三份 ref_section.py 与 `_shared/` 真源 md5 一致，
  sync_vendored --check 绿。
