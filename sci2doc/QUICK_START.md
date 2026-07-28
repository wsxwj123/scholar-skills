# Sci2Doc Quick Start

> 用最短流程完成：初始化 -> 原子化写作 -> 章节自检 -> 全文合并

## 1. 安装依赖

```bash
pip3 install python-docx
pip3 install docxcompose
pip3 install pdfminer.six
```

说明：
- `docxcompose` 用于高保真 docx 合并，可选。
- `pdfminer.six` 用于 Step 0 提取 PDF 源材料文本，处理 PDF 格式 SCI 论文时必需。

## 2. 初始化项目

🔴 运行 init 前必须先与用户确认样式（见 3.1）。`--format-mode` 默认 `default_generic`，会静默落成内置默认模板格式并立即放行 docx 导出——**不要省略该参数把它当默认值跑**，必须显式传入用户已确认的样式：

```bash
# 用户确认用内置默认模板格式后：
python3 scripts/state_manager.py --project-root "${save_path}" init \
  --title "论文题目" --author "作者" --major "专业" \
  --format-mode default_generic

# 用户选自定义、但模板信息尚不完整时（保持 pending_template，禁止导出 docx）：
python3 scripts/state_manager.py --project-root "${save_path}" init \
  --title "论文题目" --author "作者" --major "专业" \
  --format-mode custom --university-name "XX大学" --degree-type "工学博士" \
  --missing-requirement "页边距" --missing-requirement "页眉页脚距离"
```

## 3. 确认并设置目标配置

```bash
python3 scripts/state_manager.py --project-root "${save_path}" profile --show
python3 scripts/state_manager.py --project-root "${save_path}" profile \
  --body-target 50000 --abstract-min 1500 --abstract-max 2500 \
  --references-min 80 --min-chapters 5 \
  --chapter-target 1:12000 --chapter-target 2:17000
```

## 3.1 样式二选一

- `默认设置`：直接使用内置默认博士论文格式模板。
- `自定义样式`：必须先写入院校、页边距、页眉页脚距离，以及详细文字规范或模板证据。

如果自定义信息不完整，项目状态会自动保持为 `pending_template`，允许继续整理 markdown，但禁止导出 `.docx` 和格式验收。

## 3.2 结构化 JSON 更新

推荐把明确的格式要求写进 `format_profile_json`，把封面/摘要等信息写进 `project_info_json`。

```bash
python3 scripts/state_manager.py --project-root "${save_path}" profile \
  --format-profile-json '{
    "page_margins_cm": {"top": 2.8, "bottom": 2.6, "left": 3.0, "right": 3.1},
    "header_distance_cm": 1.2,
    "footer_distance_cm": 1.6,
    "page_numbering": {
      "front_matter": {"format": "upperRoman", "start": 1},
      "body": {"format": "decimal", "start": 1},
      "back_matter": {"format": "decimal", "start": null}
    },
    "style_profile": {
      "body": {"font_east_asia": "SimSun", "font_size_pt": 12, "line_spacing_pt": 20},
      "heading1": {"font_east_asia": "SimHei", "font_size_pt": 16}
    }
  }' \
  --project-info-json '{
    "classification": "R73",
    "udc": "616-006",
    "abstract_zh": "这里写中文摘要",
    "keywords_zh": ["肿瘤学", "人工智能"],
    "abstract_en": "Write English abstract here",
    "keywords_en": ["oncology", "artificial intelligence"]
  }'
```

限制：
- `--format-profile-json` 和 `--project-info-json` 只接受 JSON object。
- 未知字段、错误类型、非法页码格式都会被脚本直接拒绝。
- 支持的页码格式：`decimal`、`lowerRoman`、`upperRoman`、`lowerLetter`、`upperLetter`。

## 3.3 只有文字要求时怎么映射

如果用户不给 `.docx/.dotx` 模板，只给规则文本，优先映射到这些字段：

- “正文宋体小四，固定值 20 磅，两端对齐，首行缩进 2 字符” -> `style_profile.body`
- “一级标题黑体三号居中，段前 18 磅，段后 12 磅” -> `style_profile.heading1`
- “中文摘要标题黑体三号，摘要正文宋体四号 1.5 倍行距” -> `style_profile.front_matter.zh_abstract`
- “目录前置页用大写罗马数字，正文从 1 开始” -> `page_numbering`
- “页边距上 2.8 下 2.6 左 3.0 右 3.1，页眉 1.2，页脚 1.6” -> `page_margins_cm` + `header_distance_cm` + `footer_distance_cm`

## 4. 写前门禁

```bash
python3 scripts/state_manager.py --project-root "${save_path}" \
  write-cycle --chapter 2 --token-budget 6000 --tail-lines 80 --json-summary
```

## 5. 原子化小节

目录约定：`${save_path}/atomic_md/第2章/`

命名约定：`2.1_引言.md`、`2.2_实验A_材料方法.md` ...

校验编号：

```bash
python3 scripts/atomic_md_workflow.py --project-root "${save_path}" validate --chapter 2
python3 scripts/atomic_md_workflow.py --project-root "${save_path}" \
  validate --chapter 2 --enforce-research-structure
python3 scripts/atomic_md_workflow.py --project-root "${save_path}" validate-experiment-map --chapter 2
```

## 6. 小结完成即快照

```bash
python3 scripts/atomic_md_workflow.py --project-root "${save_path}" \
  section-snapshot --chapter 2 --section 2.3
```

## 7. 合并章节并自检

```bash
python3 scripts/atomic_md_workflow.py --project-root "${save_path}" merge --chapter 2 --to-docx
python3 scripts/atomic_md_workflow.py --project-root "${save_path}" \
  self-check --target "${save_path}/02_分章节文档/第2章_自动合并.docx"
```

提示：
- 配置了 `chapter_targets` 时，章节自检按章节目标判断。
- 参考文献下限在全文总检阶段检查，不在章节自检阶段卡住。

## 8. 章节收口

```bash
python3 scripts/state_manager.py --project-root "${save_path}" \
  write-cycle --chapter 2 --finalize --summary "第2章完成并通过自检" --snapshot
```

## 9. 合并全文

```bash
python3 scripts/atomic_md_workflow.py --project-root "${save_path}" merge-full --to-docx
```

## 10. 全文总检

```bash
# 字数统计（支持 .md / atomic_md 目录，自动检测路径类型）
python3 scripts/state_manager.py --project-root "${save_path}" word-count
# 或直接指定路径：
python3 scripts/count_words.py "${save_path}/atomic_md"

python3 scripts/check_quality.py "${save_path}/03_合并文档/完整博士论文.docx" \
  --output json --enforce-full-structure \
  --md "${save_path}/03_合并文档_md/完整博士论文.md" --md-checks xref
```

> `--md-checks xref` 是必带窄口：md 侧只放行 `交叉引用` 类断链（`issue_summary.xref_broken > 0` → Step 9 HALT 交用户逐条裁决），其余 12 类未验证的 md 检查会因 sci2doc 自己强制的 `[图]`/`[表]`/`[实验]` 标记把总分压穿 80 线、让退出码因与交叉引用无关的理由翻 1。

## 硬规则提醒

- 正文字数下限：博士 ≥50,000 / 硕士 ≥30,000（用户可在此基础上上调，不可下调）
- 各章字数必须先和用户协商后写入 profile
- 中文摘要 1500-2500
- 参考文献统一放全书末尾
- 综述由用户另写，不纳入本技能正文考核
- 研究章结构固定：引言/材料与方法/结果与讨论/实验结论/小结
- 一个实验至少一个独立图或表
- 表格使用三线表（管道表语法自动转换）
- 缩略语首次出现写全称，后续仅用缩略语
- 引用格式：英文方括号 + 英文逗号，编号升序
- 禁止破折号、问句、比喻、主观夸大、排比句式

## 缩略语 CLI

```bash
# 写前：查询已注册缩略语
python3 scripts/abbreviation_registry.py --project-root "${save_path}" list

# 写后：提取 + 注册 + 去除冗余展开（就地修改）
python3 scripts/abbreviation_registry.py --project-root "${save_path}" \
  process --file "${md_file}" --chapter 2 --section 2.1 --in-place

# 生成缩略语表 markdown
python3 scripts/abbreviation_registry.py --project-root "${save_path}" table

# 交叉引用校验（注册表 vs 实际 md 文件）
python3 scripts/abbreviation_registry.py --project-root "${save_path}" validate
```

## 图号注册 CLI

```bash
# 注册映射
python3 scripts/figure_registry.py --project-root "${save_path}" register \
  --chapter 2 --seq 1 --source "Figure 1A" --title "PMG对HepG2细胞形态的影响"

# 列出所有映射（可按章过滤）
python3 scripts/figure_registry.py --project-root "${save_path}" list --chapter 2

# 删除映射
python3 scripts/figure_registry.py --project-root "${save_path}" unregister --cn-id "图2-1"

# 校验连续性
python3 scripts/figure_registry.py --project-root "${save_path}" validate

# 与 atomic_md 标记交叉验证
python3 scripts/figure_registry.py --project-root "${save_path}" cross-validate --chapter 2

# 导出映射表（markdown）
python3 scripts/figure_registry.py --project-root "${save_path}" export --format markdown
```

## Humanization 自检命令

```bash
python3 scripts/atomic_md_workflow.py --project-root "${save_path}" \
  self-check --target "${save_path}/02_分章节文档/第N章_自动合并.docx"
```

## 参考文献著录渲染

```bash
# 从 literature_index.json 渲染 GB/T 7714 著录条目
python3 scripts/reference_renderer.py --index "${save_path}/literature_index.json" \
  --output "${save_path}/references_rendered.md"

# 只渲染某章
python3 scripts/reference_renderer.py --index "${save_path}/literature_index.json" \
  --chapter 2

# 校验著录格式（集成在 check_quality.py 中）
python3 scripts/check_quality.py "${save_path}/03_合并文档/完整博士论文.docx" \
  --output json --enforce-full-structure
```

## 新增检查项速查

| 检查项 | 类别 | 级别 | 说明 |
|--------|------|------|------|
| 三线表边框 | 三线表 | error/warning | 顶底 1.5pt、表头分隔 0.5pt、无竖线 |
| 引用格式 | 引用格式 | error | 中文逗号/括号、缺逗号、逆序范围 |
| 引用排序 | 引用格式 | warning | 编号未升序 |
| 破折号 | 标点规范 | error | 正文中使用了—— |
| 问句 | 陈述规范 | warning | 正文出现？ |
| 比喻 | 修辞规范 | error | 犹如/如同/...的桥梁等 |
| 主观夸大 | 客观性 | warning | 令人震惊/远超预期等 |
| 过度书面化 | 语言通俗性 | warning | 有鉴于此/毋庸置疑等 |
| 排比句式 | 修辞规范 | warning | 连续3句相同前缀 |
| 缩略语一致性 | 缩略语 | error/warning | 首次未展开/冗余展开 |
