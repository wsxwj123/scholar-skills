# 06 Polish Mode 流程

---

## 〇、润色的本质定义

润色**不是**单纯的语言修改。润色是对整份申请书的一次全面审视与反思：

- 实验设计是否合理？技术路线是否可行？
- 研究思路是否清晰？逻辑链是否完整？
- 研究假说是否成立？是否有充分的文献支撑？
- 研究内容与方法是否匹配？是否有遗漏或冗余？
- 关键科学问题是否真正"关键"？是否与假说对应？
- 创新性是否有实质内容？是否避免了空话和夸大？
- 可行性证据是否充分？前期基础是否支撑研究方案？
- 各部分之间是否存在逻辑冲突或表述不一致？

因此，Polish Mode的基本流程与Write Mode保持一致——同样使用脚本约束、同样执行一致性验证、同样遵循门控机制。区别仅在于：Write Mode从零构建，Polish Mode在现有草稿基础上优化。

润色前必须先以严厉评审专家的视角生成完整审查报告（参照sci2doc skill的评审规则），写入本地文件，然后根据审查报告逐条逐条修改标书。

---

## 一、流程总览

```
Step 0  导入草稿 → extract 抽标题真值 → 机械原子化拆分（两路+两层反向核验+用户确认+签字）
Step 1  严格评审报告生成（以评审专家视角，写入本地文件）
Step 2  与用户协商修改优先级与字数
Step 3  根据评审报告逐条修改（按优先级逐节处理）
Step 4  跨节一致性修复
Step 5  全文自审 → 终稿
```

---

## Step 0: 导入与原子化拆分

### 0.1 接收草稿

支持格式：`.md` / `.docx` / `.txt` / 直接粘贴文本

### 0.2 抽取标题真值（extract_headings）

**唯一判断项"什么是标题"由脚本一次性拥有**，后续拆分/审计纯机械，不再靠主会话肉眼认标题。所有格式同一条命令：

```bash
python3 scripts/extract_headings.py --source '<整稿路径>' \
        --text-out tmp/draft_import.md --out tmp/heading_manifest.json
```

- `.md/.txt` → 认 `#` 标题（high confidence）；`.docx` → Word 标题样式 + styles.xml 反查（basedOn 链/outlineLvl，自定义样式不漏）；`.pdf`/无样式 docx → `headings:[]` + `warning:"no_heading_detected"`（exit 0，触发无标题路）。
- 退出码：0 成功（含 headless）/ 1 源损坏或 <200 字（疑扫描件）/ 2 用法错·缺依赖。非 0 先与用户解决再往下。
- **抽后 sanity check（.docx/.pdf 抽取后必做）**：`tmp/draft_import.md` 不存在或 `<200 字` → 硬 HALT（疑扫描件/漏页/抽取失败），先解决再进 0.3。

### 0.3 原子化拆分（两路 + 两层反向核验 + 用户确认 + 签字）

> **⚠️ 两层机器核验皆绿 且 用户明确确认结构前，不得声明拆分完成、不得进入 Step 1。**

**0.3.1 路径判定**（读 `tmp/heading_manifest.json`，纯机械无 AI 裁量）：`trusted = headings 非空 且 无任何 low-confidence 项`。

**0.3.2 有标题路（trusted）——机械字节切**（主会话 Bash，零上下文，草稿内容不进上下文）：

```bash
python3 scripts/split_headings.py --text tmp/draft_import.md --headings tmp/heading_manifest.json \
        --atoms-dir sections --naming 'section_{major}_{标题简称}.md' \
        --split-to-level <草稿最小标题层级> --manifest-out tmp/split_manifest.json
```

- **原子落 `sections/`**（gate_registry 已登记 `sections/*.md`）；切 `text[o_i:o_{i+1}]` 逐字节，图注（is_caption）随区间内不外切。
- **原子名反映该节实际标题文本**（如 "2 研究内容" → `section_2_研究内容.md`），适配任意基金模板/待润色材料，**不硬套国自然固定 P1-P4**；认不出编号的裸中文序号节由 index 兜底命名，仍产唯一名不崩不丢。国自然 P1-P4 语义名的桥接留"模板驱动第1期"由结构真源统一处理，本轮不做。

**0.3.3 无标题路（headless：.pdf / 无 Word 标题样式的 .docx / 纯 .txt）——HALT 兜底**：`trusted==false` 时**不派拆分、不派 LLM、不写任何 atom 到 `sections/`**，向用户输出明确停止信号 + 提示"未检出可靠标题层级，请将草稿转成带 `#`/Word 标题样式的 .md/.docx 重传，或补标题后再拆"。**绝不静默乱拆。**（headless 是国自然常见交付形态——.txt 粘贴 / 手打"一、立项依据"不套样式的 docx；后续若需打通 headless LLM 拆分路，再 vendored `split_subagent_prompt.md`。）

**0.3.4 Layer 1（确定性 split_audit，两路后恒跑）**：

```bash
python3 scripts/split_audit.py --text tmp/draft_import.md --headings tmp/heading_manifest.json \
        --manifest tmp/split_manifest.json --atoms-glob 'sections/*.md' \
        --split-to-level <N> --root . --report tmp/split_audit_report.json
```

逐区 offset 比对（slice_i vs atom_i）抓漏/造/串/边界漂移/乱序五类，无假绿。**exit 0** → 进 Layer 2；**exit 1**（region mismatch / preamble_dropped，fail-closed）→ 回退重拆，**禁手改文件蒙混**；**exit 2**（headings 空/畸形/glob 命中 0）→ 回 0.3.1。exit 1/2 = 不得声明拆分完成。

**0.3.5 Layer 2（LLM 边界反向核验，split_audit exit 0 后恒跑）**：跑 `split_boundary` gate（`references/dod_checklist.json`）via `delegate_review.py`——组 `tmp/split_verify_ctx.md`（标题树 + 各 atom 锚定行，**不含全文正文**）→ pack → 独立子代理 → verify。此层与 Layer 1 不冗余：split_audit *信任*标题真值，若 extract 层把正文误当标题/漏认真标题，Layer 1 比错真值仍报绿；Layer 2 读内容到最细标题级，抓"真值本身错"。verdict 映射（evidence 须以标签开头）：`[OK]`→pass 前进 / `[WRONG]`→fail 回退重切（有标题路先修 extract_headings 真值）/ `[UNCERTAIN]`→**fail 交用户裁决**（不自动动，展示上下文）。uncertain 映射 fail 非 na（na 会被放过）。

**0.3.6 用户确认拆分表**（两层皆绿后）：展示 split map + audit 结果，等用户明确 "yes"/adjust。

```
section_2_研究内容.md   ←  2 研究内容 (1200 字)
section_3_研究方案.md   ←  3 研究方案 (900 字)
[machine-verified: split_audit exit 0, split_boundary gate pass]
确认此拆分？(yes / adjust)
```

**0.3.7 结构签字解锁 Step 3**：用户确认后落签字，解锁后续逐节 Write/Edit：

```bash
python3 scripts/structure_signoff_gate.py confirm --root . --note "<用户确认拆分表的要点/原话>"
```

**铁律**：confirm 只能在"两层核验皆绿 + 用户在对话中明确对拆分表说 yes"之后跑，**AI 不得代替用户自行 confirm**。拆分脚本经 Bash 写 `sections/*.md` **不经 Write/Edit 工具**，故未签也能落盘拆分产物（与 Write Mode 同机理，hook 只 PreToolUse 拦 Write/Edit）；真正被 signoff 门控的是 Step 3 逐节改写——未签时对 `sections/*.md` 的每次 Write/Edit 被 hook deny。

### 0.4 拆分后初始化

```
├─ 创建 proposal_profile.json（mode: "polish"）
├─ 创建空的 consistency_map.json
├─ 创建空的 literature_index.json
├─ 从草稿中提取已有参考文献 → 录入 literature_index.json
├─ 从草稿中提取逻辑实体 → 初始化 consistency_map.json
│   ├─ 识别科学问题(SQ)
│   ├─ 识别假说(H)、目标(O)、内容(RC)、关键科学问题(KSQ)
│   ├─ 识别方法(M)、创新点(IN)、可行性证据(F)
│   └─ 建立初步映射关系
└─ snapshot("polish_step0_import")
```

---

## Step 1: 严格评审报告生成

**核心原则：** 以严厉的基金评审专家视角审查整份标书，不留情面，不做严重性降级。评审报告必须写入本地文件 `data/polish_review_report.md`，作为后续逐条修改的依据。

参照sci2doc skill的评审规则，评审报告需覆盖两个层面：节级诊断 + 全局诊断。

### 1.1 评审报告生成流程

```
1. 加载所有原子文件 + consistency_map + literature_index
2. 对每个原子文件执行节级诊断（7个类别）
3. 对全局逻辑执行全局诊断
4. 以评审专家视角撰写完整评审意见（段落式，非列表）
5. 写入 data/polish_review_report.md（人类可读的完整评审报告）
6. 同时写入 data/diagnosis_report.json（结构化数据，供脚本使用）
7. HALT → 展示评审报告 → 用户审阅
```

### 1.2 评审报告格式（data/polish_review_report.md）

评审报告本身也必须遵循段落式叙事，模拟真实评审专家的书面意见：

```markdown
# 申请书评审报告

## 总体评价

[以评审专家口吻，段落式撰写总体印象，包括：
 研究选题的科学价值判断、整体逻辑是否自洽、
 主要优点（简述）、核心问题（重点展开）]

## 一、科学问题与立项依据

[评审P1：科学问题是否真正存在科学空白？立项依据的逻辑链
 是否完整？文献综述是否充分且准确？是否存在伪问题？
 具体指出哪些段落的论证不充分，哪些文献引用有问题]

## 二、研究假说与研究设计

[评审P2核心：假说是否可证伪？实验设计是否能验证假说？
 研究内容是否有遗漏？方法是否可行？关键科学问题是否
 真正"关键"？创新点是否有实质内容？]

## 三、逻辑一致性

[评审四维对应：假说-目标-内容-问题是否一一对应？
 跨节术语是否统一？是否存在逻辑冲突？]

## 四、可行性与研究基础

[评审P3：前期基础是否支撑研究方案？每个关键方法
 是否有可行性证据？工作条件是否满足？]

## 五、写作质量

[评审写作：是否有AI痕迹？是否段落式叙事？
 节奏是否单调？是否有空话套话？]

## 六、格式与规范

[字数、页数、参考文献格式、三线表、AI声明等]

## 七、逐条问题清单

[按严重性排序，每条包含：问题描述、所在位置、修改建议]
```

### 1.3 节级诊断

对每个原子文件检查，结构化存入 `diagnosis_report.json`：

```json
{
  "section": "P2_2.2.1_纳米药物的构建与表征.md",
  "issues": [
    {
      "severity": "ERROR",
      "category": "design",
      "description": "实验设计缺少阴性对照组，无法排除非特异性效应",
      "location": "第3段",
      "suggestion": "补充空白纳米载体对照组和游离药物对照组"
    },
    {
      "severity": "ERROR",
      "category": "anti_ai",
      "description": "第2段使用了'不仅...而且...'句式",
      "location": "第2段第3句",
      "suggestion": "拆分为两个独立陈述句"
    },
    {
      "severity": "WARNING",
      "category": "narrative",
      "description": "第4段使用了项目符号列表展开论述",
      "location": "第4段",
      "suggestion": "改为段落式阐述"
    },
    {
      "severity": "INFO",
      "category": "word_count",
      "description": "本节约1200字，占P2总字数15%",
      "location": "全节",
      "suggestion": "字数合理"
    }
  ]
}
```

### 1.4 全局诊断

```json
{
  "global_issues": [
    {
      "severity": "ERROR",
      "category": "hypothesis",
      "description": "假说H-2缺乏可证伪性——'纳米药物具有良好的生物相容性'是预期结果而非可检验假说",
      "suggestion": "重新表述为可证伪的假说，如'X修饰可将溶血率降低至Y%以下'"
    },
    {
      "severity": "ERROR",
      "category": "consistency",
      "description": "假说H-2在研究内容中无对应RC",
      "suggestion": "补充RC-2或删除H-2"
    },
    {
      "severity": "ERROR",
      "category": "citation",
      "description": "参考文献[15]在正文中未被引用",
      "suggestion": "删除或在P1中补充引用"
    },
    {
      "severity": "WARNING",
      "category": "word_count",
      "description": "全文估算约28000字，可能超30页",
      "suggestion": "建议精简P1（当前9500字）和P2（当前10000字）"
    }
  ]
}
```

### 1.5 诊断类别（扩展为8类）

| 类别 | 检查内容 |
|------|---------|
| `design` | 实验设计合理性、对照组设置、样本量、统计方法 |
| `hypothesis` | 假说可证伪性、假说与证据的逻辑关系 |
| `anti_ai` | 禁用句式、禁用修辞、禁用词汇 |
| `narrative` | 是否段落式叙事、是否有列点 |
| `consistency` | 四维对应、跨节逻辑 |
| `citation` | 引用完整性、文献真实性 |
| `word_count` | 各节字数、总字数、页数估算 |
| `structure` | 是否符合2026模板结构要求 |
| `style` | 节奏控制、段落开头多样性、语气 |

---

## Step 2: 与用户协商

### 2.1 展示评审报告

将 `data/polish_review_report.md` 的核心内容展示给用户，按严重级别排序：ERROR → WARNING → INFO。

与用户讨论评审报告中的每个核心问题，特别是涉及研究设计、假说合理性、逻辑一致性的问题。这些问题不能简单通过语言润色解决，需要用户做出学术判断。

### 2.2 协商修改优先级

根据评审报告，与用户逐条确认：
- 哪些问题需要重写（实验设计缺陷、假说不成立等）
- 哪些问题需要润色（语言风格、格式规范等）
- 哪些评审意见用户不认同（需要用户说明理由）
- 各节目标字数

### 2.3 协商结果写入

```json
// proposal_profile.json 追加
{
  "polish_plan": {
    "rewrite_sections": ["P1_立项依据", "P2_2.5_特色与创新之处"],
    "polish_sections": ["P2_2.2.1_纳米药物的构建与表征", "P2_2.2.2_..."],
    "keep_sections": ["P3_3_正在承担的相关项目", "P3_4_完成基金项目情况"],
    "word_targets": {
      "P1_立项依据": { "current": 9500, "target": 7500 },
      "P2_total": { "current": 10000, "target": 8000 }
    }
  }
}
```

---

## Step 3: 根据评审报告逐条修改

按 polish_plan 中的优先级（rewrite → polish）逐节处理。修改流程与Write Mode保持一致，同样使用脚本约束。

### 3.1 单节修改流程

```
对每个待处理的原子文件：

1. write-cycle 加载上下文（与Write Mode相同的脚本调用）
   ├─ 当前节原文
   ├─ consistency_map 中关联条目
   ├─ 评审报告中该节的issues（从polish_review_report提取）
   └─ token预算分配

2. 逐条修改（对照评审报告的问题清单）
   ├─ 先处理 design/hypothesis 类问题（学术实质）
   ├─ 再处理 consistency 类问题（逻辑一致性）
   ├─ 再处理 anti_ai/narrative/style 类问题（写作风格）
   ├─ 最后处理 word_count/structure 类问题（格式规范）
   ├─ 应用反AI写作风格（三层改写）
   └─ 段落式叙事检查

3. 同步更新（与Write Mode相同的脚本约束）
   ├─ consistency_map.json（如有实体变更）
   ├─ literature_index.json（如有引用变更，仅P1）
   ├─ context_memory.md
   ├─ project_state.json
   └─ history_log.json

4. 节级自审（L1 Quick Review，与Write Mode相同）
   └─ 任何D级 → 自动修正 → 重新自审

5. HALT → 展示修改内容 + 对照评审报告标注已解决的问题
   ├─ 确认 → 进入下一节
   └─ 需要调整 → 与用户讨论后修改 → 重新HALT
```

### 3.2 修改优先级规则

```
学术实质 > 逻辑一致性 > 写作风格 > 格式规范

即：先确保研究设计合理、假说成立，
    再确保各节逻辑自洽，
    再处理语言风格问题，
    最后调整格式和字数。
```

### 3.3 P1特殊处理

如果P1需要润色，额外执行：
- 文献验证流程（Check 1-5）
- 引用-索引一致性矩阵检查
- 补充检索（如文献不足30篇）

### 3.4 修改过程中的沟通机制

润色过程中随时准备与用户沟通讨论。遇到以下情况必须HALT并与用户协商：

- 评审报告中的问题涉及研究方向调整
- 假说需要重新表述或删除
- 研究内容需要增删
- 用户的原始设计与评审意见存在根本分歧
- 修改可能导致其他节需要连锁调整

---

## Step 4: 跨节一致性修复

所有节修改完成后：

```
1. 执行 consistency_map 全部验证规则（V-01~V-10）
2. 检查关键词在各节的出现情况
3. 修复不一致项
4. 如修复涉及多节 → 逐节修改并HALT确认
5. snapshot("polish_step4_consistency")
```

---

## Step 5: 全文自审与终稿

```
1. 执行自审模块（见07_自审与评审模块.md）
2. 生成L2全文评审报告 → HALT → 用户审阅
3. 根据评审报告逐条修正（与Step 3流程一致）
4. 对照 polish_review_report.md 中的原始问题清单，
   逐条确认是否已解决，未解决的标注原因
5. 页数估算 → 超30页则建议精简
6. 按正确标书顺序合并（见08_合并规则）
7. 生成终稿
8. snapshot("polish_final")
```

---

## 六、Polish Mode与Write Mode的一致性保证

| 机制 | Write Mode | Polish Mode |
|------|-----------|-------------|
| 脚本约束 | state_manager全流程调度 | 同 |
| 一致性追踪 | consistency_map + V-01~V-10 | 同 |
| 文献验证 | citation_validator 5项Check | 同 |
| 反AI检查 | humanizer_zh 全规则 | 同 |
| 门控机制 | 每Phase门控 + HALT | 每Step门控 + HALT |
| 快照回滚 | 自动快照 + 回滚 | 同 |
| 同步更新 | sync-all强制检查 | 同 |
| 节级自审 | L1 Quick Review | 同 |
| 全文评审 | L2 Full Review | 同 + 额外的polish_review_report |
| 交互规范 | 见09_交互规范 | 同 |
