# material_ingest_guide — 通用材料分析落盘指南

## 用途

`scripts/material_ingest.py` 将学位论文写作前的多种原始材料（实验数据、组会笔记、参考PDF/Word、结果图片等）分析后落盘为结构化素材档，供 AI 按章扩写时取证引用，避免凭空生成。

## 快速用法

```bash
# 处理整个材料目录
python3 scripts/material_ingest.py --dir /path/to/raw_materials --save-path /project

# 处理指定文件列表
python3 scripts/material_ingest.py \
    --list data.xlsx notes.md fig1.png \
    --save-path /project

# 试跑不写文件
python3 scripts/material_ingest.py --dir /path/to/raw_materials --dry-run
```

`--save-path` 默认为当前目录；`materials/` 目录会自动创建。

重复运行幂等：已处理的文件（按 SHA256 hash 前12位判断）直接跳过，新文件追加。

---

## 输出结构

```
${save_path}/materials/
├── materials_archive.json       # 总索引（所有材料的 entry 数组）
├── <safe_name_1>.md             # 每材料一个结构化素材档
├── <safe_name_2>.md
└── ...
```

---

## materials_archive.json schema

每个 entry 字段如下：

| 字段 | 类型 | 说明 |
|---|---|---|
| `filename` | string | 原始文件名 |
| `source_path` | string | 文件绝对路径 |
| `file_type` | string | `text` / `tabular` / `document` / `image` / `unsupported` |
| `status` | string | `ok` / `skip` / `pending_confirm` / `error` |
| `safe_name` | string | 用于 .md 文件名的安全片段 |
| `ingested_at` | string | ISO 8601 摘入时间 |
| `file_hash` | string | SHA256 前12位（幂等key） |
| `summary` | string | 一行摘要 |
| `key_points` | string[] | 可引用要点列表（来自材料实际内容） |
| `reason` | string | skip/pending_confirm 时说明原因 |
| `sheets` | array | tabular 类型的 sheet 详情（列名、行数、数值范围） |
| `headings` | string[] | text 类型的标题节点列表 |

---

## 各格式处理规则

### md / txt（text 类型）

- 读取全文（UTF-8，错误替换）
- 提取 Markdown 标题列表（`#`~`####`）
- 取前10段的首句作为 key_points（每条 ≤200 字符）
- 素材档中附前 3000 字符预览

### xlsx / csv（tabular 类型）

- xlsx：需要 `openpyxl`（`pip3 install openpyxl`）；缺库则 `status=skip`，不报错
- 提取：sheet 名、列名、行数、每列数值范围（min/max/mean）
- **只提取实际存在的数值**；空列、文本列标记 `n_numeric=0`，不臆造数值
- key_points 格式：`[SheetName] N行×M列；ColName 范围 [min, max]`

### PDF / Word（document 类型）

- PDF：需要 `pdfminer.six`（`pip3 install pdfminer.six`）；缺库则 `status=skip` 并提示使用 `/pdf` 技能
- Word：需要 `python-docx`（`pip3 install python-docx`）；缺库则 `status=skip` 并提示使用 `/docx` 技能
- 扫描件/加密 PDF 提取文本为空时同样 `status=skip`，不报错
- 提取成功时：前3000字符预览 + 前8段首句作为 key_points

### 图片（image 类型）

- 支持：`.png .jpg .jpeg .tif .tiff .gif .bmp`
- **只记录文件路径和大小，不做任何 OCR 或内容臆测**
- `status=pending_confirm`，素材档中显示「待确认」区，等待用户口述图内容后手动补充

---

## 图片不臆测红线

图片处理器不调用任何视觉识别或 OCR。这是对齐 sci2doc 核心原则"不臆造实验数据"的强制约束：

- AI 看到图片 entry 时，**必须**等用户补充 `待确认` 区后才能将图内信息用于写作
- 禁止从文件名猜测图内容（如 "western_blot.png" 不代表图中有 western blot 结果）
- 用户确认内容后，手动编辑对应 `.md` 文件的「待确认（❓）」区即可

---

## 素材档（每材料 .md）结构

```
# 素材档：<filename>

- 来源路径：<path>
- 类型：<file_type>
- 状态：<status>
- 摘入时间：<ISO>
- 文件哈希：<hash>

## 内容摘要
<summary>

## 可引用要点
- <point 1>
- <point 2>
...

## 表结构详情           # tabular 类型专有
### Sheet: <name>
- 行数 / 列名 / 数值范围

## 文本预览（前 3000 字符）   # text / document 类型
```
<preview>
```

## 处理说明              # skip / pending_confirm 时
> <reason>

## 待确认（❓）
> 请在此补充图内容描述、数据解释、结论说明等需要人工确认的信息。
```

---

## 扩写时引用规则

1. 每次写作时优先从 `materials/materials_archive.json` 检索相关 entry
2. 引用数值/结论时，**必须**能追溯到对应 entry 的 `source_path` 和 `key_points`
3. `status=skip` 的材料不可引用其内容（尚未提取）
4. `status=pending_confirm` 的图片不可引用任何内容描述（等用户确认）
5. 素材档中的 key_points 是实际内容的直接摘录，不是 AI 总结——可作为引用依据
