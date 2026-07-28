# 识图产物模板 (figure-protocol)

> 被 SKILL.md 的 **Phase 6 (`/figure`)** 引用。进入识图流程、每张大图收口、落盘 `figure_analysis/figure_{N}.md` 与 `add-figure` 入库时 `Read` 本文件。
> 读图红线（Zero-Hallucination、只读符号化信息、不数散点、读不到就问）见 SKILL.md 正文，本文件提供逐图循环流程与落盘模板。

## 逐图循环流程 (8 步)

1. **进入（含自然语言触发）**：用户提到"分析 / 解读 figureN"、"写 XX 结果章节"、"这几个图是什么结果"等——**即使没打 `/figure` 命令、即使只发了图没说命令**——都应进入本流程，**不要跳过识图直接 `/write`**。进入后询问用户：该小节对应的 **Figure 编号** 与 **小图数量**（如 "Figure 2，共 A–E 五图"）。
2. **建档（含中途续接）**：确保 `figure_analysis/` 存在（无则 `mkdir -p figure_analysis`）；创建/打开 `figure_analysis/figure_{N}.md`，进度行记录声明的小图总数（如 `[0/5]`）。**若文件已存在且进度未满**（如 `[3/5]`）→ 读已写入的 Panel，从**下一个未完成 Panel** 续接，不重复识别已写的（沿用 SKILL.md §4 Anti-Overwrite，增量追加、禁止整体覆盖）。
3. **逐张索取**：请用户发送 Panel A 图片。**若用户只用文字描述图、未上传图片** → 不进入读图，转"口述数据"模式：要求用户直接给分组 + 数值 + 统计结果；AI **严禁**从图类型关键词（CCK8 / 流式等）脑补典型结果，并明确告知"我没看到图、仅凭你给的文字写，发图能核对得更准"。
4. **读图 → 中文草稿**：用中文贴出该 Panel 的图类型 / 分组 / 坐标轴与量纲(标注是否 log 轴) / 组间比较结果(含星号) / 趋势方向，并给出**中文结果 + 讨论草稿**；**❓待确认**：误差棒类型、n、星号阈值、看不清项。
5. **确认 → 英文写入**：用户确认或修正后，将草稿翻译为英文、按**结果块 + 讨论块分离**写入文档（模板见下），讨论需引文处置 `[CITE_PENDING]`。
6. **自检**：每张图写入时触发 SKILL.md §11 的 **Design / Reliability** 检查（对照设置、n、统计方法是否合理）。**Consistency（跨图一致性）不在逐图时做**——逐图时其他图尚未读取、无从比对；留到本大 figure 全部小图读完后（收口前）统一比对一次（如 Fig A 结论是否与 Fig C 矛盾），发现问题写入"❓待确认"提示用户。
7. **下一张**：索取 Panel B，重复 4–6，直至全部小图完成。
8. **收口（每完成一个大 Figure 更新一次状态）**：
   - **同步到 `figures_database.json`（用 `add-figure`，单条即可）**：把本 figure 写成**单个** JSON 对象（`figure_id` 必需、`section` = storyline 的 section_id；外加 `declared_panels`（可选，命令比对实际 panels 数、不符警告）/ `panels` / 比较对 / `p_value` / `n` / `stat_test`（供 Methods 联动）/ `data_status`，格式见下方「条目示例」），执行 `python scripts/state_manager.py add-figure <one_figure.json>`。该命令在 `FileLock` 下：① 按 `figure_id` 去重合并进 figures_database（**不覆盖其他 figure**）；② **顺带同步** `writing_progress`（追加 figure 事件）、`context_memory`（追加识图记录）、回写 `storyline.sections[].figures`——一次锁内全办，无需再调有 gate 的 `postwrite`。误传数组或缺 `figure_id` 会被拒；核心定量读不到的项 `data_status="pending"`，对接 SKILL.md §2 熔断。
   - **记识图确认到 section_memory**：执行 `python scripts/state_manager.py update <payload.json>`，payload 形如 `{"section_memory":{"section":"results_3.2","content":"Figure 2 A–E 已识别；用户确认 n=6、误差棒=SEM；Panel C 留 CITE_PENDING"}}`——让 `/write --include-draft` 写该节时能读到识图确认细节。
   - **备份**：执行 `python scripts/state_manager.py snapshot`（无 gate；现已备份 `figure_analysis/` 并写入 `version_history`）。**勿用 `postwrite`**——它有 prewrite gate（state_manager.py:2403），识图阶段没跑 write-cycle 会 `sys.exit(2)`。
   - **缩略词扫描（与 Phase 7 联动）**：扫描本 figure_{N}.md 新引入的 `Full Name (ABBR)` 模式，对每个未在 `abbreviations.json` 的缩写执行 `add-abbreviation`（first_defined_in 填本 figure 对应的 section_id）。**否则 `/write` 写正文时查表查不到、会重复展开**——这是 figure 与 Phase 7 跨阶段集成的必经一步。
   - 告知用户：`figure_analysis/figure_{N}.md` 就绪，将作为 `/write {section}` 的结果与讨论依据。

## `figure_analysis/figure_{N}.md` 模板（落盘正文用英文；下方字段中文仅为说明）

```markdown
# Figure {N}: <大图主题>   <!-- section: <section_id> -->
> 进度: [3/5 识别中 | 完成]

## Panel A — <图类型: 散点/WB/HE/荧光/CLSM/流式/拍照…>
- **分组**: <组1, 组2, …>
- **坐标/量纲**: <Y轴指标(单位); 线性/log>
- **组间比较**: <组1 vs 组2 = ***>   <!-- source: star_on_graph -->
- **❓待确认**: 误差棒类型? n=? 星号阈值?
- **结果(Results)**: <客观描述方向与比较结果，不解释>
- **讨论(Discussion)**: <基于设计/假设/本图数据的推理> <!-- [CITE_PENDING: 机制关键词] -->

## Panel B — …
```

## `figures_database.json` 条目示例（收口 `add-figure` 用；传**单个** figure 对象，命令按 `figure_id` 自动安全合并）

```json
{
  "figure_id": "Figure 2",
  "section": "results_3.2",
  "title": "Cytotoxicity of nanoparticles",
  "data_status": "ready",
  "panels": [
    {"panel": "A", "assay": "CCK-8",
     "groups": ["Control", "NP-L", "NP-H"],
     "comparisons": [{"pair": ["NP-H", "Control"], "sig": "***", "p": null, "source": "star_on_graph"}],
     "error_bar": "SD", "stat_test": "one-way ANOVA + Tukey", "n": 3}
  ]
}
```

（`data_status`：核心定量齐全=`ready`，缺核心项=`pending`；`section` 值必须 = storyline 的 section_id，代码里 `section`/`section_id` 混用，统一写 `section`。）
