> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

# Project Directory Structure（init 后项目根的完整目录树）

```
${save_path}/
├── atomic_md/              # 原子化 markdown（唯一写作源）
│   ├── 第1章/
│   │   ├── 1.1_引言.md
│   │   └── ...
│   ├── 第2章/
│   └── 缩略词表.md
├── 02_分章节文档/           # 单章 docx 输出（merge --to-docx）
├── 02_分章节文档_md/        # 单章 md 合并中间产物
├── 03_合并文档/             # 全文 docx 输出（merge-full --to-docx）
├── 03_合并文档_md/          # 全文 md 合并中间产物
├── 04_图表文件/             # 图表描述文件 + 自定义格式模板证据文件（AI/用户手动放置）
├── scripts/                # 技能脚本副本（init 自包含拷入；SKILL 命令 `python3 scripts/xxx.py` 即指向此处）
├── materials/              # 原始材料素材档（material_ingest.py 生成，可选）
│   ├── materials_archive.json  # 素材总索引
│   └── <name>.md           # 每材料一个结构化素材档
├── .state/                 # gate-check 状态
├── backups/                # 快照备份 / section-snapshot（自动创建）
├── project_state.json      # 项目状态
├── thesis_profile.json     # 论文配置
├── context_memory.md       # 运行时上下文记忆
├── chapter_index.json      # 章节结构索引
├── literature_index.json   # 文献引用索引
├── figures_index.json      # 图表引用索引
├── figure_map.json         # SCI图号→论文图号映射（自动生成）
├── history_log.json        # 操作历史
├── abbreviation_registry.json  # 缩写注册表（自动生成）
├── mcp_literature_cache.json   # MCP 文献检索缓存（citation_guard 自动生成）
├── citation_guard_report.json  # citation_guard 运行报告（自动生成）
├── manual_review_queue.json    # 待人工核验引用队列（citation_guard 自动生成）
├── verification_run_log.json   # citation_guard 运行日志（自动生成）
└── references_rendered.md      # GB/T 7714 著录渲染输出（reference_renderer 自动生成）
```
