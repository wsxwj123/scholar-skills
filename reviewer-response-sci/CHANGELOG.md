# Changelog - Reviewer Response SCI Skill

## [2.29.0] - 2026-08-17

第二十二轮 P0 流程完整性（R2）：评论身份与恢复安全。①高置信无编号拆分——只拆同段一致 `(i)/(ii)/(iii)` inline marker 或 ≥2 个独立请求句（Please/Could the authors/The authors should 起始），解释句与 `Please note` 附着前一请求，已编号/统一 Reply:/单句复合请求/Figure 面板不拆，合成编号 `0.1/0.2/...`、模糊块保持 `0`。②每个 comment unit 落版本化 `source.reviewer_comment_fingerprint`（`sha256:v1:`+canonical `[reviewer, section, comment_number, simplify_ws(comment_en)]`，email 豁免），人工字段按 fingerprint 映射。③`project_state.input_identity` 保存三输入 raw 字节 SHA-256 与 semantic 摘要（comments=topology+规范化 email；manuscript/SI=可见文本+段落结构；SI 缺失 `absent:v1`）；build 全量 staging 解析后写前比较：topology/text/email、manuscript/SI semantic 变化或 legacy 缺身份一律 rc=2 零产品写入，并给旧目录外新 root+新 HTML 恢复合同（旧人工回复原样保留）；raw 变化 semantic 相同则重跑 build 并保留人工字段。④resume signature v2：lock 内计算，绑定三输入字节 SHA-256+pipeline contract SHA-256（build/strict/render/unit schema），path-only 旧 checkpoint 一次性失效；build 读取时二次核 raw（`--expected-raw-sha256-json`，关 TOCTOU）；preflight 结构化拦目录型不可读输入。⑤strict gate 读当前三输入核 raw/semantic/topology/unit fingerprint。unit schema 增 `reviewer_comment_fingerprint` 字段说明。

## [2.28.6] - 2026-08-10

第十六轮共享件同步（SPEC-round16，盲检判合格）：折叠报告写失败全量明细回退 stdout；delegate_review（rr fork 同构跟进）畸形返回 exit 2；中毒缓存结构性判别（联网轨或 provider 轨）。

## [2.28.5] - 2026-08-09

第十五轮共享件同步（SPEC-round15，盲检判合格）：proofread 参考文献段剥离收敛 ref_section 单一口径（新增 vendored ref_section.py）；citation_claim_check 垃圾摘要按缺失处理 + 大批量警告折叠落报告。

## [2.28.4] - 2026-08-06

第十三轮同款 bug 修复（SPEC-round13）：env_preflight parse_list argv 越界守卫。

## [2.28.3] - 2026-08-06

第十二轮共享件同步（SPEC-round12）：citation_guard_core 的 _http_get_json
补 ssl.SSLError / BadStatusLine 异常覆盖（fail-closed，retry 语义不变）。

## [2.28.2] - 2026-08-06

写保护批次（SPEC-round10-protected）：install_gate_hook settings.json 写盘原子化
+ hooks 非 list 点名报错；structure_signoff_gate 签字凭证写盘原子化；
context_guard_core 的 _gsw_left / _nsfc_left 两条判定修正同步。

## [2.28.1] - 2026-08-05

第十轮共享件修复同步（SPEC-round10）：delegate_review 重复 id 往严处倒 +
--section 路径消毒（#14/#15，fork 同构修）；citation_claim_check 非 str 摘要
防崩（#16）；citation_guard_core 连接重置/IncompleteRead fail-closed（#6）；
proofread 4 位年份不再误报数字格式不一致（#9）。
