# Changelog - General SCI Writing Skill

## [2.36.3] - 2026-08-06

第十二轮小批（SPEC-round12）：`_http_get_json` 异常覆盖补 ssl.SSLError /
http.client.BadStatusLine（此前仍逃逸致整批核验 traceback 死亡，本机 Clash
MITM 环境高发；retry 语义逐点等价，HTTPError 分支顺序未动）；SKILL.md 四处
`<本技能>` 占位符改为"项目内 scripts 绝对路径"口径（部署后跑的是 /init
拷进项目的副本，不是技能安装目录）。

## [2.36.2] - 2026-08-06

写保护批次（SPEC-round10-protected）：install_gate_hook settings.json 写盘原子化
+ hooks 非 list 点名报错；structure_signoff_gate 签字凭证写盘原子化；
context_guard_core 的 _gsw_left 跳过无 status 键条目（老格式 figure 事件不再
盖掉 done）+ _nsfc_left 精确匹配（p1 不再误吞 p10_*）。

## [2.36.1] - 2026-08-05

第十一轮：文档失配修正 + 死重清除（SPEC-round11-docs，分支 fix/round11-docs）。

- 文档与现实对齐：素材就位步骤标明"信息性探查不阻断"（≠硬检查）；/rename-figure
  写成真实子命令；citation_guard 两处命令显式带 --report/--manual-review；
  删掉不存在的具名代理写法；/resume 两套口径统一；submission-guide Phase 引用
  8→11；compliance-gate 六项→七项；references 地图补 5 行；§1 拷贝步加
  env_status 残留清理。
- 死重删除：templates/search_rules.json（零消费者）、writing-templates 里
  figures/figure_index.md 断头注册流程、dod_checklist 的 journal-study-dod
  死 gate、reporting_checklists 的 STROBE/TRIPOD/ClinPK 悬空映射（同步修正
  submission-guide 的虚假承诺）。

## [2.36.0] - 2026-08-05

第十轮：外部审计 46 条经四路独立验证（35 真/6 部分/5 假）后修复 20 条脚本 bug
（SPEC-round10，分支 fix/round10，盲检首判 #2 不合格返工后复检合格）。

- 数据安全：FileLock 重试耗尽 fail-closed raise（#1）；restore 改先拷后换，
  copytree 中途失败现稿原样保留（#21）；账本写回原子化 + .bak + list 形状
  非 dict 条目不丢（#5-①）；prune 透传 protect，mtime 打平刚建备份必留（#20）。
- 门禁/判定：figure_analyzed 事件写侧改名 + 读侧跳过无 status 条目，
  不再吃掉节的 done 状态（#2）；merge 排除 Draft_Round 旧中间稿（#3）；
  delegate_review 重复 id 往严处倒 + --section 路径消毒（#14/#15，三向同修）；
  extract_numeric_section 优先带小数节号（#13）。
- 健壮性：GBK 混入不裸崩（#8/#12，errors="replace" / except 补 UnicodeDecodeError）；
  _http_get_json 对连接重置/IncompleteRead fail-closed（#6，共享件）；
  citation_claim_check 非 str 摘要防崩（#16，共享件）；env_preflight argv
  越界防护（#17）；引文区间展开 500 上限（#22 两处）。
- 误报消除：proofread 4 位年份不再误报数字格式不一致（#9，共享件铺 6 家）；
  export_bibtex 缺年份不再静默编 2024（#10）；中文全称（ABBR）定义认得出（#11）；
  跨节聚类数值归一化（"45%" vs "45.0%" 不再误报漂移）（#19）。

## [2.35.4] - 2026-08-05

citation_guard 离线时 report `ok` 压 false（SPEC-round9 缺陷 E1，分支 fix/round9）。

- 缺陷：report `"ok": status in ("verified", "unverified")` —— 离线跑
  （status=unverified，一轮没做任何联网核验）照样 ok=true，只看 ok 的调用方会
  误判"文献已核实"；旁边注释"ok=本次没查出问题"的语义本身易误读。
- 修复：ok 改为 `status == "verified"`，语义=整体可采信；退出码与 ok 解耦
  （E1b 用户口径）：离线无硬失败仍 exit 0，条目有真硬失败/空索引仍非 0，
  退出码行为一字不变。不新增 failure_reason 码。
- 验收：scripts/test_e1_offline_ok.py 修前红（离线 ok=true）修后绿。

## [2.35.3] - 2026-08-05

行首特征误判三连修复（SPEC-gsw-block-recognition，分支 fix/gsw-block-recognition）。
三个缺陷同族：脚本按"行首特征"判断文字块性质，判错了就多报（假报警）或漏查（假阴性）。

⚠️ 版本号未 bump：SPEC D6 要求 frontmatter 2.35.2→2.35.3，但同一份 SPEC 与任务书
的文件边界都写明"明确不许碰 SKILL.md"，两条指令冲突。按"指令矛盾停下上报"处理，
SKILL.md frontmatter 仍是 2.35.2，待主会话裁决后补 bump。

### D1 ref_section 认得"编号包在加粗里"的参考文献标题

- 缺陷：`## **8. References**`（编号被 `**` 包住，两份真稿同位置复发）被
  `is_reference_heading` 判 False——先剥编号后剥装饰符号，顺序对不上。
  相邻形态（`## **References**` / `## 8. References` / `## References`）全部正常。
  后果：116 条文献泄进 prose，score 19（剥掉后 49）、115 条 bullet 假报警、
  字数统计把 116 条算进正文词数；该函数是五处调用的唯一口径。
- 修法：装饰符号剥掉之后再吃一次编号前缀（仍只在带 # 的标题里吃，裸行口径不变）。
  识别路径保持线性，无正则、无回溯；`__main__` 自检原有 YES/NO 一字未动，
  新增夹心 YES×3（`## **8. References**` 等）与 NO×4（`## **8. References** extra` /
  `## **7. Competing Interests**` / `## **8. Reference genome**` / 裸 `**8. References**`）。

### D2 硬换行的正文续行不再被当图注整行剥掉

- 缺陷：pandoc 硬换行让正文句子的续行以 `Figure <数字>` 开头，被
  `FIGURE_LEGEND_RE` 无条件当图注剥掉（真稿 3 处），同性质的 `Figure S4C` 续行
  因 S 前缀不匹配正则反而幸存——主图被剥、附图留下，漏查方向。
- 修法（`_extract_prose`）：结构性判据"图注是独立段落、续行在段落中间"——
  行首匹配 `Figure/Fig./Table + 编号` 的行仅在**段落起点**（前一行空行/块边界/
  文件开头）才剥；上一行非空（未完句与完句两种都测）一律留下被检查。
  独立成段的 `Figure 5: caption` / `Table 2: ...` 照样剥，力度与续行侧相同。

### D3 CRediT 作者贡献块与通讯作者行不再当正文扫

- 缺陷：`## **5. Author Contributions**` 下的 CRediT 角色行
  （`Wenjie Xu: Conceptualization, Methodology, ...`）与
  `Corresponding authors:` 邮箱行，每行稳定命中一条 explanatory_colon_in_prose
  （真稿 10 条假阳性）。这是期刊模板 boilerplate，不是正文 prose。
- 修法（`_extract_prose`，单函数内，未动架构）：新增两个行级判据——
  ① CRediT 行：冒号后整段按逗号/分号切开后**每一项**都落在 CRediT 14 角色
  封闭标准词表内（归一化破折号三态、&/and、大小写），不枚举人名；
  ② 通讯作者行：冒号前头部整体落在封闭标签集（corresponding author(s) /
  correspondence (to)）内。命中的行整行剥出 prose。
  不误伤：正文解释性冒号（`The mechanism is simple: Drug X inhibits Y.`）照样报
  （hard_fail）；统计方法 `Correspondence analysis showed: ...` 头部不在标签集，不剥。

### 复现/验收

- `scripts/test_block_recognition.py`（gitignore 排除，不分发）：10 条用例，
  修前 7 红（exit 1）修后全绿（exit 0）；三条缺陷各自"拦得住 + 不误伤"两侧同力度。
- 已知边界（登记，不处理）：`Key contribution: Validation.` 这种整段恰好只有一个
  CRediT 角色词的电报句会被剥——它本就撞解释性冒号硬门禁，同方向；
  作者忘空行的真图注（紧贴上一正文行）此后会被当续行留下，漏查方向，与 SPEC 口径一致。
- style_checker md5 锁（tests/acceptance/test_style_checker_guard.py）按预期撞锁：
  登记 771606659667f12024aa92650b6e93f1 → 实得 d916c339990b4eae0f98876a76d2cf97，
  开发代理未改锁，待主会话确认后刷新。

## [2.35.2] - 2026-08-05

/init 把 docx 字体模板拷进项目（SPEC-gsw-init-template，分支 fix/gsw-init-template）。

### §1 Command Logic 第 3 步补上 reference.docx

- 缺陷：`/init` 只把 `templates/*.json` 扁平拷到项目根，`templates/reference.docx`
  从不进项目 → 每个新项目第一次 `/merge` 导 docx 必撞一次硬失败
  （exit 2、`reason: reference_doc_missing`），用户要多跑一条
  `python scripts/make_reference_docx.py` 自愈命令才能继续。
- 修法：第 3 步改为 `cp [Skill_Path]/templates/*.json [Skill_Path]/templates/reference.docx [Target_Path]/`，
  模板与 json 一样扁平落到项目根（`merge_manuscript.py` 候选位第 3 位
  `cwd/reference.docx` 自动认出，与 `make_reference_docx.py` 默认落点一致）。
  不建 `templates/` 目录，其余 4 步一字不变。
- 覆盖语义：与 §1 现有步骤一致——全部用裸 `cp`，目标已存在即覆盖，
  无"跳过已存在"保护（如实登记，未发明新语义）。改字体的正规路径
  （重跑 `make_reference_docx.py` 覆盖项目根 `reference.docx`）不受影响。
- 文档口径同步三处：§1 第 3 步、Phase 0 Copy Resources 清单、
  Phase 16 docx 段（删"项目目录里模板缺失是常态（/init 不把 templates/ 拷进项目）"
  这句已过时的话，改为"init 已拷、老项目或被删时才缺、硬失败与自愈语义不变"）。
- 复现/验收测试：`scripts/test_init_reference_docx.py`（gitignore 排除，不分发）。
  守两层：SKILL.md 第 3 步拷贝指令被删即红；裸临时目录照指令初始化后
  首次 merge exit 0 且 docx 产出、项目模板与技能仓模板 md5 一致。

## [2.35.1] - 2026-08-05

参考文献识别收敛 + docx 模板口径改正（SPEC-gsw-refconverge，分支 fix/gsw-refconverge）。

### style_checker 参考文献段识别收敛到 ref_section 单一口径

- style_checker 里原有一份独立的段标题识别（`REF_HEADING_RE` + `_is_reference_label_line`，
  词表只有 References/参考文献/Bibliography 三条），与同目录 `ref_section.py`
  对同一份稿判定不一致：`## Reference List` / `#References` / `## 7. References` /
  `## 引用文献` / 裸行 `Reference` / `References and Notes` 全认不得（条目泄进 prose
  被当正文扫，误报），`####### References` 反而误开块（整段被误剥，漏报）。
- 删除旧实现，`_extract_prose` 直接调 `ref_section.is_reference_heading`
  （函数对象同一性）；非参考文献标题关块语义不变（`## Appendix` 后的正文仍被检查）。
- 有意的行为变化：`####### References`（7 个 # 在 markdown 里不是标题）其后条目
  此后被当正文扫。识别路径保持线性消费，未回正则。
- 复现/验收测试：`scripts/test_style_ref_converge.py`（gitignore 排除，不分发）。

### SKILL.md Phase 16 docx 模板口径改正

- 原文「缺失=安装损坏」与现行事实不符：`/init` 不把 `templates/` 拷进项目，
  项目里缺模板是常态；`make_reference_docx.py` 能在裸目录用 pandoc 兜底自产模板，
  merge 自动认出 `./reference.docx`。改为「缺失是常态、docx 步骤失败但 md 照常落盘、
  一条命令自愈」，三条命令已在裸目录实测走通。

## [2.35.0] - 2026-08-04

收尾批·文档层。这一批的重点不是"把写错的字改对"，是**把会反复写错的结构拆掉**。

### 🔴 `$WORKROOT` 用 21 次、定义 0 次 → 改成写死的相对路径

- Phase 10 步骤 9/10/11（数值 / 交叉引用 / 方法学三层核查）的全部命令都依赖
  `$WORKROOT`，而 SKILL.md 从头到尾没定义过它。用户照着复制，shell 把它展开成
  空串 → `manuscript not found: /_numeric_fulltext.md`。
- 修法不是"补一句 `WORKROOT=...` 的定义"（那还是留着一个必须记得先跑的前置步骤，
  且 bash 赋值在 PowerShell 上照样不成立），而是**全部换成写死的 `.state/check/`**：
  21 处不再有变量，任何一条都能单独原样复制执行。`.state/` 已在 `.gitignore`、
  不属于 `managed_globs`（`manuscripts/*.md`），`merge_manuscript` 会自动建目录。
  实测三条锚脚本（`numeric_candidates` / `structure_outline` / `methods_terms`）
  在该路径下全部 exit 0，且不干扰步骤 7/8 的扫描范围。

### 🔴 版本号三处不一致 → 收成一处

- 原状：frontmatter `2.34.0`、SKILL.md 正文 `2.20.0`、README / QUICK_REFERENCE /
  USAGE_GUIDE / TEST_CHECKLIST 全是 `2.20.0`。
- **根因是"同一个数手写在 6 处"**，逐一改齐下次照样漂。改成
  **frontmatter 的 `version:` 是全仓唯一写死处**，其余文档一律不再写版本号、
  只写"以 frontmatter 为准"。CHANGELOG 是变更史，最新条与 frontmatter 对齐。

### 🔴 硬编码行号引用 → 换成函数名

- `SKILL.md` 与 `references/figure-protocol.md` 都写着"prewrite gate
  （state_manager.py:2403）"，而 2403 行早就漂到别处（真正的判定在
  `postwrite_state()` 里）。两处改成引用函数名，不再写行号。

### SKILL.md 内部矛盾逐条改准

- `--journal` 说取 `storyline.json` 的 `target_journal` → 实际在
  `project_config.json`（`storyline_template` 只有 `innovation_core` /
  `main_hypothesis` / `sections` 三个键，根本没这个字段）。
- "六项判定细则"与紧接着的"七项合规检查"打架 → `compliance-gate.md` 实为 7 节，改 7。
- "step8–11 全部通过 → 进 Phase 10.5" → Phase 10 实为步骤 1–11，改"步骤 1–11"。
- frontmatter 说 Phase 13B"不出回复包"，正文 13B step 4 明写生成
  `reviews/response_letter.md` → 按正文为准改 frontmatter：13B 出**内部**
  response letter，不出正式投稿用的完整回复包，正式回复包走 reviewer-response-sci。
- 写作禁忌"严禁简略…视为失败"与"深度控制（软提示，非硬门）"打架 → 明确前者是
  质量要求不是落盘阻断，门禁口径以后者为准。

### 根目录四份文档：能跑的写清楚，跑不了的不许留

- `README.md` / `QUICK_REFERENCE.md` 里 `config_manager.py load drug_delivery`
  是位置参数写法，argparse 只有 `--field` / `--name`，原样跑 **exit 2**（实测）
  → 全部改成 `--field` 写法，并显式写明这条坑。
- 三份文档都指向 `tests/test_state_manager.py` / `tests/test_citation_guard.py`
  与 `unittest discover -s tests`，而**技能里根本没有 `tests/` 目录**（实测
  exit 1）。测试是 `scripts/test_*.py`，被 `.gitignore` 排除、不随包分发 →
  改成如实说明"技能不分发测试，装完能自查的只有 py_compile"。
- `TEST_CHECKLIST.md` 原来声称 "Status: PASS (20 tests)"，指的是不存在的测试
  → 改成行为契约清单（改脚本的人要保证不倒退的行为），不再冒充测试报告。
- `RUNTIME_LAYOUT.md` 原来只列 5 项运行时产物，实跑（`/init` 到 `/check`）产出
  远不止 → 按实测重写，补上 `.state/transactions/`、`.state/check/`、
  `backups/snapshot_*`、`env_status.json`、`active_field_config.json`、
  各类报告、`structure_signoff.json`、`decisions_log.md` 等。
- `USAGE_GUIDE.md` 整篇是 v2.0 时代的演示（`/check` 只出三行 Quality Report、
  没有结构签字门禁、`/journal-study` 还在），演示的流程已经不存在
  → **内容清空、改为指向真入口的路牌**。不重写：它唯一还准确的内容
  （citation_guard 命令、`set-field`）在 README 与 QUICK_REFERENCE 都有，
  重写一份等于再造一个漂移源。建议后续直接删除该文件。

### 新增一致性护栏

- `scripts/test_doc_consistency.py`（本机自测，不随包分发）静态锁死五类漂移：
  版本号只许一处、不许出现 `xxx.py:<行号>`、shell 变量必须在同文件定义过、
  文档提到的技能内路径必须真实存在、`config_manager.py` 不许写成位置参数。
  修前 24 处红，修后全绿。

## [2.34.0] - 2026-08-04

盲检打回三条，前两条致命，其中 R-1 是上一批自己引进的。

### 🔴 R-1 覆盖前的"快照保险"装反了，比不装还糟（上一批 2.33.0 引进）

- 快照目录按**秒**命名。同一秒内第二次调用目录已存在 → 跳过 mkdir → 先把**已被
  破坏的现状** `copy2` 盖进旧快照 → 再崩在 `copytree("manuscripts")` 上 →
  `except OSError` 吞掉、只打一句 Warning → **写入照常进行**。
  实测：10 张图变 1 张、唯一的快照也被改成 1 张、两条命令都 exit 0 报成功、
  payload 还被自动删掉——原始数据没有任何找回路径。
- 现在撞名一律另起 `snapshot_<ts>_2/_3`（`os.makedirs` 不带 `exist_ok`，捕
  `FileExistsError` 重试），**已建立的快照绝不被后来者改写**；顺带解掉 `snapshot`
  子命令同秒连跑抛未捕获 `FileExistsError`（exit 1）。
- `update` 的覆盖前快照失败改为 **fail-closed**：整文件覆盖拿不到回退点就中止，
  非 0 退出并保留 payload，不再"打个 Warning 继续写"。

### 🔴 R-2 缩表防护只认一种数据形状

- 旧判据枚举 `entries/items/references/data` 四个包装键，而 gsw 自己的状态文件
  用的是别的键：`figures_database`（`{"figures":[…]}` 10→1）、`storyline`
  （`{"sections":[…]}` 5→1）、`mentor_plan`（`{"rounds":{…}}` 写第二轮顶掉第一轮）
  实测全部 exit 0 静默丢数据。`mentor_plan` 尤其要紧——SKILL.md 明确指示 AI 用
  `update` 往它写每一轮，照做就会抹掉上一轮。
- 改成与键名无关的判据：**新旧同为容器、元素变少即拦**，dict 按 `len()` 计数；
  dict 里原有的键在新内容中消失同样算丢（`rounds` 从 `{"1":…}` 变 `{"2":…}` 时
  len 没变但第一轮确实没了）。只沿两边同名的 dict 键递归，不进 list 元素内部——
  改某一条的字段是正常编辑，不该被当成丢数据。
- 不误拦对照实测：文献索引追加、图库条数不变改内容、故事线加一节、mentor_plan
  保留第一轮加写第二轮、submission_state 写新内容，全部照常放行。

### 🟡 R-3 引文核证读不了"按编号做键"的索引（`_shared/`，6 家共享）

- `citation_claim_check._load_ledger` 没有 dict_values 分支。2.33.1 把
  `--write-back` 修好（不再顺手造 `entries`）之后，`{"1":{…},"2":{…}}` 这类索引
  对它彻底不可见：`ledger_entries` 恒 0，「机制/疗效声明不得挂综述」这条纪律
  没有索引可依据、静默不执行。
- 「哪些键是文献条目」的判据搬进 `_shared/citation_guard_core.py` 当唯一真源，
  gsw/rw/sci2doc/reviewer-simulator 四家 `citation_guard.py` 改为导入，
  `_load_ledger` 用同一份判据。该形状下条目内不一定再存一份编号，故**原键即
  ref_id**；其余四种形状行为逐条对照不变。

### 📄 文档改准（盲检独立发现）

- SKILL.md `:206/:383/:394/:414` 四处仍写"项目里没有 `references/`"，与 `:56`
  和 /init 第 5 步直接矛盾、实测为假（`references/` 已进项目，相对路径也能跑通）。
  改成"项目内有 `references/`，但 cwd 不一定在项目根，所以一律用 Phase 0 打印的
  绝对路径"——照旧写法下一个 AI 会据此把第 5 步的拷贝删回去。
- 2.33.1 里"review-writing 本轮未动"与事实不符，已改准。

## [2.33.1] - 2026-08-04

### 🔴 `citation_guard.py --write-back` 把"按编号做键"的索引写成两份

- 索引形如 `{"1": {...}, "2": {...}}` 时，写回分支只认
  `entries/papers/items/references/data` 五种 key，其余一律落到 `out["entries"]`
  —— 原键原样留着、另起一份副本，同一批文献在同一个文件里存了两份。
  而所有读取侧（`_normalize_index`、`citation_claim_check._load_ledger`）都**优先读
  `entries`**，于是用户之后手工改原键的内容**对所有检查不可见，且没有任何提示**。
  实测：改完原键 1 的标题再跑一次 write-back，`entries[0]` 仍是旧标题，两份已分叉。
- 现在 dict_values 形状按原键写回原位，不再新建 `entries`。读写两侧共用
  `_dict_entry_keys()` 挑条目，保证一一对应；`metadata`（写回自己产的账本头）
  排除在条目之外，否则第二次跑会把它当成一条缺标题的文献判 fail。
- 其余四种形状（裸 list / entries / papers / items）逐字节不变，已对照实测。
  同一处缺陷在 sci2doc 2.31.1、reviewer-simulator 2.29.6 一并修掉；
  review-writing 同缺陷也已修（commit bf0c811），其 `citation_guard.py` 的验收考卷
  md5 锁由主会话同步刷新——本条此前写的"rw 本轮未动"与事实不符，已改准。

## [2.33.0] - 2026-08-04

### 🔴 P0：两条让第二节开不了写的死锁 + 一道被架空的硬门禁 + 一处静默毁数据

- **`write-cycle --finalize` 的 `--status` 默认改 `done`**。此前默认 `updated`，而
  `prewrite_gate` 只认 `done/completed/finalized`，且**全技能文档里 `--status` 出现 0 次**
  —— 照文档抄的人第一节收口后，第二节 `prev_section_done` 必 FAIL、永远开不了写。
  真没写完仍可显式 `--status draft`，下一节照样被拦。
- **`references/` 不进项目的相对路径全部改绝对路径**。`/init` 只拷 scripts/templates/configs，
  而盲检命令写的是 `--checklist references/dod_checklist.json` → 项目根 cwd 下必
  `exit 2` → `.review_pass/<节>.json` 永不落盘 → 下一节被硬拦。改由 Phase 0
  `env_preflight.py` 打印 `DOD_CHECKLIST` / `PREP_PROMPT` / `WRITER_PROMPT` 绝对路径，
  SKILL.md 用占位符引用。
- **`citation_guard.py --require-mcp` 不再被 30 天缓存架空**（改的是 `_shared/`
  共享件，7 家同步）。此前 `entry_is_fresh_verified` 只看 `verified` + 时间戳，不看当初
  那次核验的强度：一条 `--offline` 验过的编造文献（编造标题 + 编造 DOI + 编造 PMID）
  能被 `--require-mcp` 一路短路放行 `exit 0`。现在缓存只有在**当初至少和本轮一样严**
  （`sources.mcp` / `sources.online_check` 为真）时才准复用；无额外要求时照旧短路，
  不联网、无性能倒退；字段缺失或结构不对一律收紧。
- **`state_manager.py update` 三处危险修掉**：① 一个字段都没匹配上时不再打印
  "Successfully updated:" 然后删掉输入文件，改为非 0 退出 + 保留 payload + 报清哪个字段；
  ② 整文件覆盖会让条目数变少时直接阻断（此前传 1 条进去原有 30 条静默消失），
  覆盖前另拍一次全量快照可 `/rollback`；③ 补上 `FileLock("state_update")`，
  与 postwrite / add-figure / add-abbreviation / rename-figure 口径一致。
  先全量校验再落笔，不留"写了一半"的中间态。
- **`figure_analysis_gate.py` 补 GBK 控制台防护**。它是唯一没加 stdout reconfigure 的
  门禁脚本，而失败原因里带 `❓待确认`（GBK 编不出）→ 中文 Windows 上用户被拦住却只
  看到一段 Traceback，看不到真正原因。

## [2.20.0] - 2026-06-11

### 🔒 写作前"读 references"硬门禁（闭环 progressive disclosure 风险）
- `write-cycle --section` 预加载时按 section 类型列出**必读 references 清单**（anti-ai-protocol 通用；results/discussion 加 figure_analysis + writing-templates + citation-policy；methods/intro 加 writing-templates）。
- `write-cycle --finalize` 新增**强制 `--refs-confirmed` 声明**：缺失则 `exit 2` 阻断落盘（`error: refs_not_confirmed`），把"忘记读 references、凭记忆写作"从软约束变成硬门禁。
- SKILL.md / README / QUICK_REFERENCE 所有 `--finalize` 示例同步加 `--refs-confirmed`；P0#10 补门禁说明。
- 新增 `required_refs_for_section()` + `state_manager.py` write-cycle 的 `confirm_refs` 参数。
- **鲁棒性补洞**：`required_refs_for_section()` 对**非标准 section 命名**（如 `uptake`/`characterization`，不含 results/methods 字样）采用"宁多勿漏"——识别不出类型即给全正文 refs，避免门禁因命名退化成只读 anti-ai 而失效。
- **诚实边界**：脚本强制 AI **显式声明**已读，但无法验证它是否真读了内容——挡得住"忘记"，挡不住"故意绕过"。这是文本指令转代码门禁能到达的上限。

## [2.19.0] - 2026-06-11

### 🧹 SKILL.md 结构重构（提升 AI 遵守率）
- **Progressive disclosure**：将 anti-AI 协议、文献政策、统计决策树、投稿指南、章节写作模板、识图模板 6 块参考资料从 SKILL.md 外移到新建的 `references/` 子目录，SKILL.md 各阶段改为按需 `Read` 指针。再原地精简 §11 强制交互结构（33→6 行）与 §1 路径初始化。常驻上下文从 86.8K 字符（914 行）降至 65.1K（692 行，**-25%**）。
- **Phase 编号线性化**：原混乱编号（3.5/3.55/3.6/3.7/4.5/4.8/4.9/5/6.6）重排为连续整数 `Phase 0–16`，消除"Phase 5 物理排在 Phase 4.8 之前"的错位；所有交叉引用同步更新。
- **P0 红线分层**：开头新增「🔴 P0 红线」区（10 条违反即报废级规则）+「📁 references/ 参考文件地图」索引表，建立指令优先级层次。指令通胀词频下降（必须 108→89，严禁 49→42）。
- **清理开发痕迹**：删除正文中 11 处 `Bug X 修复` 内部标记与版本号区的内联 changelog（变更历史统一归口本文件）。

## [2.16.2] - 2026-03-07

### 📚 Protocol and Document Sync
- Clarified the response protocol: Part 1 and Part 3 remain mandatory in user-visible replies, while the Status Dashboard is maintained internally by default and rendered only on explicit audit/log requests.
- Updated `QUICK_REFERENCE.md`, `README.md`, `USAGE_GUIDE.md`, `TEST_CHECKLIST.md`, and `RUNTIME_LAYOUT.md` so documentation matches the current runtime behavior.
- Normalized source-file references in runtime docs (`SKILL.md`, `scripts/config_manager.py`, `configs/*.json`) to remove stale path/case drift.

## [2.16.1] - 2026-03-07

### 🔒 Citation Verification Hardening
- `scripts/citation_guard.py` now enforces provider family policy: only `paper-search` and restricted `tavily` entries are accepted.
- Tavily entries carrying DOI/PMID are blocked; Tavily no-identifier entries are routed to `manual_review_queue.json` and remain unverified.
- Bidirectional verification failures (`title_mismatch`, DOI/PMID mismatch, `id_mismatch`) now force `verified=false` and append an explicit manual-confirmation reason.
- `citation_guard_report.json` now records provider policy details for auditability.
- Added regression tests covering provider allowlist, Tavily restrictions, manual review routing, and bidirectional verification failure handling.

## [2.15.2] - 2026-02-12

### ✅ Reliability Hardening
- `write-cycle` is now strict-preflight by default; use `--preflight-lenient` only for debugging.
- `sync-literature --apply` now blocks by default when `dedup_conflicts` is detected.
- Added explicit override `--allow-conflicts` for manual, reviewed exceptions.
- Added bounded retention for runtime artifacts:
  - `.state/reports/` report files are capped.
  - `.state/load_cache.json` cache entries are capped.
- Fixed cache invalidation precision by switching file signature to nanosecond mtime.
- Added regression tests for nature reference style, conflict blocking, cache invalidation, and strict-default write-cycle.


## [2.15.1] - 2026-02-11

### 🔧 同步自动化与文献一致性修复

#### 核心变更
- **Postwrite Automation (回复后自动同步)**:
  - `state_manager.py` 新增 `postwrite` 强化参数，支持一条命令同步全局进度与记忆（`writing_progress` + `context_memory`）。
- **Literature Dedup + Renumber Sync (文献去重与编号同步)**:
  - 新增 `sync-literature` 命令，按 DOI → PMID → 元数据键 → 精确标题 → 模糊标题 五层策略自动去重 `literature_index.json`，重复项元数据合并而非丢弃。
  - 去重后自动重写 `manuscripts/*.md` 中的 `[n]` 引用编号，避免正文与索引错位。
- **Global/Section Load De-duplication (加载去重)**:
  - `global_history` 收敛为核心全局状态，避免与 section 级索引重复加载。

## [2.15.0] - 2026-02-11

### 🧠 记忆与Token控制升级

#### 核心变更
- **Section-Local Context Protocol (章节级上下文隔离)**:
  - `/write [section]` 仅允许加载该章节相关上下文，默认拒绝跨章节正文读取。
  - 新增章节白名单载入理念：仅项目配置、章节提纲、章节图数据、章节文献、当前章节草稿、章节记忆。
- **Dual Memory Model (双层记忆模型)**:
  - 引入 `section_memory/<section_id>.md` 作为章节记忆层，与全局 `context_memory.md` 分离。
  - 明确全局记忆仅保存决策与约束，章节细节沉淀到 section 级文件，降低“串章”风险。
- **Token Budget Guard (预算熔断器)**:
  - `state_manager.py` 的加载流程新增 token 预算估算与自动降载机制。
  - 超预算时按优先级自动裁剪：先压缩正文与章节记忆，再压缩文献/图数据，避免上下文爆炸。
- **Scoped Loading CLI (作用域加载命令扩展)**:
  - `load` 命令支持 `--section`、`--token-budget`、`--tail-lines`，用于章节定向加载与预算控制。
  - 输出中新增 `loaded_files` 与 `budget_report`，可用于验证“只读当前章节”是否生效。

## [2.14.0] - 2026-01-30

### 📏 严谨性与完整性升级

#### 核心变更
- **Point-by-Point Response Protocol (逐条致密回复协议)**:
  - 将 "逐条致密回复" 列为最高优先级的系统执行红线 (Final Enforcement #6)。
  - 强制 AI 必须细致回答用户的所有问题，严禁忽略或简略回答，确保学术交流的深度与完整性。
- **Figure Caption Generation (图注生成协议)**:
  - Phase 4 写作流程新增 "Figure Caption Generation" 步骤。
  - 强制在每小节末尾生成 Figure Legends，并包含具体的统计信息 (n=X) 和显微标尺 (scale bar = X μm)。

## [2.13.0] - 2026-01-30

### 🔄 SI 持久化与主动管理

#### 核心变更
- **SI Persistence Protocol**: 引入 `si_database.json` 作为新的核心状态文件，强制记录所有在对话中确认的 Supplementary Information。
- **Auto-Persistence**: `state_manager.py` 脚本升级，支持自动加载和保存 `si_database.json`。
- **Proactive Query Loop**: 在 Phase 4 (Writing) 的 SI 建议环节，增加了对 `si_database.json` 的检查步骤。若发现缺失证据且数据库为空，必须主动询问用户并立即保存反馈。
- **Strict Enforcement**: 将 "SI Must Be Persisted" 列为最高优先级的系统执行红线，严禁仅在 Memory 中提及 SI。

## [2.11.0] - 2026-01-30

### 🛡️ 检索健壮性升级

#### 核心变更
- **Abstract Recovery Protocol (摘要补全协议)**: 针对检索结果中摘要缺失的情况，建立了强制性的三级回退机制。
  - **Mandatory Chain**: Google Scholar (Primary) > Semantic Scholar > Tavily。
  - **Strict Policy**: 严禁因摘要缺失直接丢弃相关性高的文献，必须跑完上述补全流程。仅当所有工具失效时才允许标记为 Missing。

## [2.10.0] - 2026-01-30

### 🤖 自动化与输出净化

#### 核心变更
- **State Manager Automation**: 引入 `scripts/state_manager.py`，实现跨平台、标准化的状态加载与原子化更新，彻底告别手动读写多个状态文件的繁琐。
- **Clean Output Protocol**: 强制 `[Context Check]` 块仅作为内部验证日志，**严禁**出现在用户最终回复中，提供沉浸式的无干扰交互体验。
- **Version Compatibility**: 脚本内置 `context_memory.md` 的版本轮转逻辑 (v-1, v-2)，确保历史回溯功能的稳定性。

## [2.9.0] - 2024-01-30

### 📏 引用规范与上下文强化

#### 核心变更
- **Strict Citation Format**: 强制正文引用使用 `[n]` 格式，严禁其他变体。在每个小节末尾自动附上该节引用的参考文献列表（Vancouver style）。
- **Mandatory Context Read**: 强化了上下文检查协议，明确要求在每次回复前读取所有 5 个核心文件（含 `writing_progress.json`）。
- **Final Enforcement**: 将引用格式规则加入到最高优先级的系统执行指令中。

---

## [2.8.0] - 2024-01-30

### 🔄 全局状态持久化 (Continuity Upgrade)

#### 核心变更
- **Global Context Persistence**: 强制在**每次回复结束前**自动更新 `context_memory.md`。无论是在进行问答、头脑风暴还是写作，当前的对话状态、决策和待办事项都会被实时保存。
- **Auto-Snapshot Logic**: 智能快照现在会监控 `context_memory.md` 的实质性变更，确保在对话中断后能无缝恢复到最新状态。

---

## [2.7.0] - 2024-01-29

### 🚫 去除 AI 味关键升级

#### 核心变更
- **NO BULLET POINTS POLICY (段落式写作强制令)**:
  - 明确禁止在正文（Abstract, Intro, Results, Discussion）中使用列点符号。
  - 强制要求使用逻辑连接词（Furthermore, Consequently）将观点串联成连贯段落，模拟真人科学家的写作习惯。
- **Final System Enforcement**:
  - 在 Skill 末尾增加了最高优先级的执行指令，再次强调"强制交互版块"（反向拷问/你可能想知道）和"禁止列点"规则，防止 LLM 在长上下文中遗忘。

---

## [2.6.0] - 2024-01-29

### 💬 交互深度恢复

#### 核心变更
- **强制交互版块恢复**: 在 v2.x 迭代中遗漏的 "反向拷问" 和 "你可能想知道" 版块已重新实装为强制输出协议。
- **Reverse Interrogation**: 每次回复都必须挑战用户的假设或指出盲点。
- **Proactive Suggestions**: 每次回复都必须预测用户的下一步需求。

---

## [2.5.0] - 2024-01-29

### 🛡️ 逻辑完整性升级 (SI重构)

#### 核心变更
- **SI 认知重构**: 明确定义 SI 为 "Integral Evidence Chain" (完整证据链) 而非单纯的防御工具。Main Text 展示"结果与意义"，SI 展示"确信度与过程细节"。
- **Context-Aware SI 建议**: 废除机械的药剂学套路提问。AI 必须基于当前小节的具体逻辑断点（Logical Gap），主动分析缺失的中间证据（如阴性对照、优化过程、方法验证），并据此提出精准的 SI 建议。

---

## [2.4.0] - 2024-01-29

### 🛡️ 逻辑完整性升级

#### 核心变更
- **SI 主动建议与整合回路 (SI Proactive Loop)**:
  - 在撰写 Results 小节时，AI 不再是一次性输出。
  - **Reflect**: 完成初稿后，AI 必须基于药剂学专业知识，主动反思"需要什么补充证据？"（如处方筛选、稳定性、阴性对照）。
  - **Propose**: 向用户建议具体的 SI 列表。
  - **Integrate**: 获得用户反馈后，自动重写该小节，将 SI 引用（如 `Figure S1`）自然融入论证逻辑，形成最终版。

---

## [2.3.0] - 2024-01-29

### 🛡️ 逻辑熔断与检索优化

#### 核心变更
- **数据依赖熔断 (Hard Stop)**: 在撰写 Results/Discussion 章节前，强制检查 Figure 数据的完整性。若数据状态为 `pending`，AI 必须立即停止并请求数据，严禁编造或使用占位符。
- **文献检索优先级调整**:
  - **Primary**: PubMed (医学/药剂学首选)
  - **Secondary**: Semantic Scholar (速度/广度) + bioRxiv (预印本)
  - **Fallback**: Google Scholar (仅作补充)
  - **Forbidden**: Tavily (禁止用于学术检索)

---

## [2.2.0] - 2024-01-29

### 🛡️ 安全与规范升级

#### 核心变更
- **原子化文件管理**: 强制执行"一小节一文件"策略（如 `04_Results_3.1_Characterization.md`），彻底解决大文件覆盖导致的数据丢失问题。
- **写入安全协议**: 在执行 `write_file` 前必须先读取旧文件比对差异，若存在覆盖风险，自动创建 `.bak` 备份。
- **严格工具纪律**: 明确锁定文献检索工具优先级。
  - **Primary**: `paper-search` (PubMed/Scholar), `arxiv` (Preprints).
  - **Forbidden**: 禁止使用 `tavily` 检索学术引用（仅限宽泛概念查询）。

---

## [2.1.0] - 2024-01-28

### 🎉 核心升级

#### 生态兼容
- **BibTeX 导出**: 新增 `/export_bib` 命令，支持将 `literature_index.json` 导出为 `references.bib`，方便导入 Zotero/EndNote。
- **本地脚本实装**: 提供了 `scripts/export_bibtex.py` 和 `scripts/merge_manuscript.py`，支持脱离对话环境的自动化操作。

#### 写作质量
- **自我修正回路**: 在 `/write` 命令中植入 "Draft -> Critique -> Polish" 隐式思维链。AI 在输出前必须进行自我反思和润色，确保语言简练且逻辑严密。

---

## [2.0.0] - 2024-01-28

### 🔥 重大重构

#### 核心逻辑
- **Results & Discussion 融合**: 废弃独立 Discussion 章节。采用"数据呈现 -> 即时讨论 (机制/对比/意义)"的融合写作模式。
- **智能快照系统**: AI 主动判断快照时机（生成内容/关键决策/新数据），而非僵化触发。
- **上下文显式验证**: 强制检查并汇报历史文件（Storyline, Literature, Figures）的读取状态，杜绝幻觉。
- **弹性写作深度**: 引入 "Key Section" vs "Supporting Section" 概念。核心论点强制深度展开 (>200词)，次要数据简洁陈述。

#### 文件变更
- 更新 `storyline.json` 结构以支持融合章节。
- 重写 `skill.md` 以反映新的交互协议。

---

## [1.0.0] - 2024-01-27

### 🎉 初始发布

#### 核心功能
- ✅ 完整的Nature级SCI论文写作工作流
- ✅ 8个阶段的写作流程
- ✅ 12个全局命令系统
- ✅ 持久化记忆系统（3版本context_memory）
- ✅ 完整备份的版本控制
- ✅ 分阶段文献检索
- ✅ 审稿人视角模拟
- ✅ 质量控制系统
