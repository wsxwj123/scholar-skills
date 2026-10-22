> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

## 🎮 全局命令系统

| 命令 | 功能 | 说明 |
|------|------|------|
| `/init` | 初始化项目 | - |
| `/resume` | 恢复写作 | 先跑 `session_journal.py resume`（即 RESUME_CMD）贴接续报告、与用户握手确认（见 `SKILL.md` 的「会话接续协议（Mandatory）」节），确认后再 `state_manager.py load` → 读 `last_section` → `write-cycle --section [last_section]` |
| `/preview` | 预审报告 | - |
| `/storyline` | 构建提纲 | 自动规划融合式章节 |
| `/figure-plan` | 主图集规划 | storyline 确认后、识图前，规划 Figure 1–N 信息载荷与 main/SI 分配；允许回修 storyline（见 Phase 2.5） |
| `/literature` | 文献检索 | - |
| `/stat-helper` | 统计方法选择助手 | 不知道用 t-test/ANOVA/非参时触发，按决策树询问（见 Phase 5） |
| `add-stat-method` | 注入统计方法到 figure panel | /stat-helper 输出后落地用：`add-stat-method --figure-id "Figure 2" --panel A --stat-test "one-way ANOVA + Tukey" --n 6 --error-bar SEM --software "GraphPad Prism v10.1"` |
| `/change-journal` | 中途转投另一家期刊 | 改 word_limits→重查投稿包变化项（见 Phase 2） |
| `/upgrade-scripts` | 升级项目内的 scripts/ 到最新版 | 项目用了几个月技能更新后,补 add-figure 等新命令（见 Phase 0） |
| `/figure` | Figure 识图与讨论 | 逐张读图→读图清单确认→存 `figure_analysis/figure_{N}.md` 作正文依据；只读符号化信息，读不到问用户（见 Phase 6） |
| `/rename-figure` | 重整 figure 编号 | 全局改名 + 同步 figures_database/storyline/正文/识图文件：`python scripts/state_manager.py rename-figure --old "Figure 3" --new "Figure 5" --dry-run` 先预览，确认后去掉 `--dry-run` 真改 |
| `/write` | 撰写章节 | **章节局部读取 + 自我修正 + 智能快照** |
| `/journal-study` | 🚫 已停用（DEPRECATED） | 期刊语言风格适配改到末尾 `polish-sci`；结构约束由 Phase 2 `target_journal` 早已捕获（见 Phase 8.6 停用说明） |
| `/abstract` | 撰写摘要 | 全文完成后最后写，≤250词，含定量结果 |
| `/compliance-check` | 投稿前合规门禁 | /check 通过后强制执行：伦理批号+试验注册号+报告规范+统计完整性+ICMJE署名+reviewer COI+Keywords，缺一阻断（见 Phase 10.5） |
| `/submission-pack` | 投稿包准备 | Cover letter+DAS+CRediT+COI+Funding+Highlights+Keywords+eTOC+Graphical Abstract+Source Data+Acks+checklist（见 Phase 11） |
| `/presubmission-inquiry` | Nature/Cell 系预审询函 | ≤1 页 inquiry,省 4-6 周等审稿（见 Phase 12） |
| `/proofread` | 机械错误最终校对 | 拼写/中文标点/单位/术语一致性/数字格式/Methods 时态(脚本 proofread.py) |
| `/mentor-review` | 导师批注循环 | 录入批注→逐条执行→改动追踪→重审准备→轮次管理（见 Phase 14） |
| `/check` | 质量检查 | 含 style_checker 去AI检测 |
| `/reviewer` | 审稿人模拟 | - |
| `/snapshot` | 手动快照 | AI也会智能触发 |
| `/rollback` | 版本回滚 | - |
| `/merge` | 最终合并 | - |
| `/export_bib`| **导出参考文献**| **新增：生成 references.bib** |
| `/stats` | 进度仪表盘 | - |

`/stats` 脚本入口：`python scripts/state_manager.py stats`  
`/stats`（按章节看字数）：`python scripts/state_manager.py stats --section [section_id]`

---

# 版本说明（原 SKILL.md 716–718，2026-10-19 拆分保留；“本文件”已改写为 SKILL.md）

**版本**：以 `SKILL.md` frontmatter 的 `version:` 为准（**全仓唯一写死处**，别处一律不再另写一个数）；变更历史见 `CHANGELOG.md`。

---
