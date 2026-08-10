# Changelog - Review Writing Skill

## [2.36.10] - 2026-08-10

第十七轮技术债清零（SPEC-round17，盲检 M1-M6 变异全红判合格）：缩写检查依赖断裂由静默降级改 fail-closed——style_checker/ref_section 导入失败即 ABBR_CHECK_ERROR exit 2 点名中止（此前恒等回退致参考文献区作者姓名首字母全量假阳、零提示；--report-only 同样不放行；依赖齐全路径逐字不变）；prewrite_gate 检查器故障（exit 2）改走"本项检查未执行"档（ok=None + 真实原因 warning，可见不阻断），不再反着说"未通过、必须清零"。

## [2.36.9] - 2026-08-10

第十六轮技术债清理（SPEC-round16，盲检判合格）：µCT 类非 ASCII 相黏不再拆出裸缩写误判死门（十五轮枚举边界类改结构性 \w 减 CJK；"ROS可诱导"检出不倒退）。共享件同步：折叠报告写失败全量明细回退 stdout；delegate_review 畸形返回 exit 2；new_refs/new_claims 元素级校验；中毒缓存结构性判别（联网轨或 provider 轨，真实账本 271→271 回归锁）。

## [2.36.8] - 2026-08-09

第十五轮（SPEC-round15，盲检 20 变异全红判合格）：C5 prewrite_gate 缩写子进程显式 utf-8 解码（跨平台不再走 locale 默认）；C6 裸缩写边界 \b 换 ASCII lookaround，"ROS可诱导"类 CJK 相黏扫得出（英文行为一字不变）；共享件同步：proofread 参考文献剥离收敛 ref_section 单一口径、citation_claim_check 垃圾摘要按缺失处理 + 大批量警告折叠落报告、delegate_write_core 键类型归一 + 缺条目报出 + 畸形 exit 2。

## [2.36.7] - 2026-08-06

第十三轮同款 bug 修复（SPEC-round13）：prewrite_gate/style_checker GBK 混入不崩；abbreviation_consistency 中文全称（ABBR）认得 + GBK 不崩。

## [2.36.6] - 2026-08-06

第十二轮共享件同步（SPEC-round12）：citation_guard_core 的 _http_get_json
补 ssl.SSLError / BadStatusLine 异常覆盖（fail-closed，retry 语义不变）。

## [2.36.5] - 2026-08-06

写保护批次（SPEC-round10-protected）：install_gate_hook settings.json 写盘原子化
+ hooks 非 list 点名报错；structure_signoff_gate 签字凭证写盘原子化；
context_guard_core 的 _gsw_left / _nsfc_left 两条判定修正同步。

## [2.36.4] - 2026-08-05

第十轮共享件修复同步（SPEC-round10）：delegate_review 重复 id 往严处倒 +
--section 路径消毒（#14/#15）；citation_claim_check 非 str 摘要防崩（#16）；
citation_guard_core 连接重置/IncompleteRead fail-closed（#6）；
proofread 4 位年份不再误报数字格式不一致（#9）。

## [2.36.3] - 2026-08-05

citation_guard 离线时 report `ok` 压 false（SPEC-round9 缺陷 E1，分支 fix/round9）。

- 缺陷：report `"ok": status in ("verified", "unverified")` —— 离线跑
  （status=unverified，一轮没做任何联网核验）照样 ok=true，只看 ok 的调用方会
  误判"文献已核实"；旁边注释"ok=本次没查出问题"的语义本身易误读。
- 修复：ok 改为 `status == "verified"`，语义=整体可采信；退出码与 ok 解耦
  （E1b 用户口径）：引入 `unblocked = status in ("verified", "unverified")`
  同时喂退出码与 stderr 的 PASS 提示门——离线无硬失败仍 exit 0、stderr 文本与
  触发条件一字不变，条目有真硬失败/空索引仍非 0。不新增 failure_reason 码。
- 验收：scripts/test_e1_offline_ok.py 修前红（离线 ok=true）修后绿。

## [2.36.2] - 2026-08-05

参考文献识别收敛到共享件（SPEC-round9 缺陷 E2b/E2c，分支 fix/round9）。

- style_checker.py 删掉自带的独立识别实现（REF_HEADING_RE 前缀匹配 +
  `_is_reference_label_line` 三条词表，即 gsw 第六轮已删的那套），改为模块级
  import `_shared/ref_section.py` 的 vendored 副本（与 gsw/nsfc 逐字节一致）。
  修前 7 个案例与 ref_section 全部分歧：`## Reference List` / `#References` /
  `## 7. References` / `## 引用文献` / 裸行 `Reference` / `References and Notes`
  认不得（文献条目泄进 prose 误报），`####### References` 反而误开块
  （整段被误剥漏报）。修后分歧归零（`####### References` 一例是有意的判严
  方向变化：7 个 # 不是 markdown 标题，其后条目此后被当正文扫）。
- E2c 用户拍板 D2/D3 一并对齐 gsw 第八轮：图注剥行加段落起点判据
  （pandoc 硬换行的正文续行 `Figure 5E ...` 不再被整行误剥，独立成段的
  真图注照样剥）；CRediT 作者贡献行 / 通讯作者 boilerplate 剥出 prose
  （封闭标准词表判据，不枚举人名；正文真解释性冒号照样 hard_fail）。
- rw 独有逻辑原样保留：review 语态阈值 ≤30%（info 软提示）、长句 >30 词检查、
  `from X to Y` 模式不收（误报）、默认目录 drafts/、--passive-max 参数。
- 验收：scripts/test_style_ref_converge.py（7 分歧 + 不误伤 + 线性时间）、
  scripts/test_block_recognition.py（D1/D2/D3 两侧）修前红修后绿；
  三份 ref_section.py 与 `_shared/` 真源 md5 一致，sync_vendored --check 绿。
