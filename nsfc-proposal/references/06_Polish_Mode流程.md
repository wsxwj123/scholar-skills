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

旧版 `.doc` 不能直接导入，先转成 `.docx`。不要用 macOS 自带的 `textutil`，它对旧 Mac 编码的 `.doc` 会转出乱码。改用 LibreOffice，需要先安装，终端找不到 `soffice` 时用它的完整安装路径，或者在 Word 里另存为 `.docx`。命令如下，`--outdir` 用新建的空目录，避免覆盖同名的 `.docx`，`<文件.doc>` 是原件。
```bash
soffice --headless --convert-to docx --outdir <目录> <文件.doc>
```

转完抽样看开头几行是不是正常中文，乱码就停下说明。

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

#### 0.3.1 路径判定

读 `tmp/heading_manifest.json`，纯机械无 AI 裁量：`trusted = headings 非空 且 无任何 low-confidence 项`。trusted 走 0.3.2，否则走 0.3.3。两路的产物形态相同，之后都走 0.3.4 到 0.3.7。

#### 0.3.2 有标题路（trusted）

机械字节切，主会话 Bash 零上下文，草稿内容不进上下文：

```bash
python3 scripts/split_headings.py --text tmp/draft_import.md --headings tmp/heading_manifest.json \
        --atoms-dir sections --naming 'section_{major}_{标题简称}.md' \
        --split-to-level <草稿最小标题层级> --manifest-out tmp/split_manifest.json
```

- **原子落 `sections/`**（gate_registry 已登记 `sections/*.md`）；切 `text[o_i:o_{i+1}]` 逐字节，图注（is_caption）随区间内不外切。
- **原子名反映该节实际标题文本**（如 "2 研究内容" → `section_2_2研究内容.md`，标题简称含编号），适配任意基金模板/待润色材料，**不硬套国自然固定 P1-P4**；认不出编号的裸中文序号节由 index 兜底命名，仍产唯一名不崩不丢。**原子名不做 P1-P4 改名桥接。** 每个小文件属于哪个大节由 `section_parts.json` 记录（0.3.6），结构真源只管模板章节的顺序与必需件。需要按模板管住顺序/必需件时，把拆分产物登记进 `<项目根>/structure_profile.json`（`chapters[].filename` 就填这些原子名；须经用户逐条确认后 `confirm` 落盘，五步链见 SKILL.md Phase 0「模板结构提取」）。落盘后：合并顺序按真源 `chapters[].order`、`validate-order` 必需件按真源 `required: true` 集合、`prewrite_gate` 的写作顺序与 section→文件匹配按真源 filename（传入 section 是某个 filename 的前缀即命中）。没有真源时：merge 收 `sections/` 全部现场文件、按文件名数字键排序（`section_2 < section_2.1 < section_10`，不是 shell 字典序），被排除的（figure_prompts.md / P2 父子同在的子文件 / 空文件）逐一报进输出 JSON 的 `excluded[]`，不静默丢。
- 国自然 P2 的新子结构与三套固定格式见 `references/workflow-p0-p2.md` 的 Phase 2 P2 子结构真源一节；无编号的研究目标原子按 `references/workflow-polish.md` 第 0 步改名带 2.0，改名必须在 0.3.6 的归属确认之前做。

#### 0.3.3 无标题路（headless，.pdf / 无 Word 标题样式的 .docx / 纯 .txt）

`trusted==false` 时走这条路。抽取后只剩文字，原件里的表格文字、自动编号、加粗都不在 `tmp/draft_import.md` 里，所以由一个子代理按行号认标题，再由脚本按行号定位、核对原句、机械切分。子代理只交一份标题清单，不抄正文。与 review-writing 的无标题路不同，那家让子代理逐字节抄正文写小文件，本家无标题路用行号定位，产物格式与有标题路相同，两家不共用提示词。

步骤如下，命令在项目根运行。

1. 给整稿编行号，供子代理引用：

```bash
python3 scripts/heading_locate.py lines --text tmp/draft_import.md --out tmp/draft_lines.txt
```

2. 派认标题子代理。角色 prompt 用 `references/headless_heading_prompt.md`，它只读 `tmp/draft_lines.txt`，只写 `tmp/llm_headings.json`（每项三键，行号、原句、层级）。没有子代理能力的平台由主会话照同一段要求自己做。

3. 按行号定位并核对原句，写出与有标题路同格式的标题真值：

```bash
python3 scripts/heading_locate.py locate --text tmp/draft_import.md \
        --headings-in tmp/llm_headings.json --out tmp/heading_manifest.json
```

退出码 0 时 stdout 给出 `split_to_level`（各项层级的最大值），`advisory` 里的 `DUPLICATE_TEXT` 只做提示。退出码 1 是清单内容错（`ITEM_INVALID`、`LINE_OUT_OF_RANGE`、`TEXT_MISMATCH`、`ORDER`、`LEVEL_JUMP`、`NO_HEADINGS`），一次报全，`tmp/heading_manifest.json` 不动；把 stdout 的 `errors` 原样交回子代理重做，最多重试 2 次，第 3 次仍失败停下，把错误清单给用户。退出码 2 是输入文件缺失、不是 UTF-8 或清单形状不对，先修输入再跑。

4. 机械切分，命名用文档顺序号。国自然无样式稿的编号在每个大节内重新从 1 起，沿用 `{major}` 会把后面大节的 1 排到前面，所以这条路用 `{n:02d}`，小文件名的数字就是文档顺序，`section_merger.py` 按它排出的就是原稿顺序，无标题路不需要研究目标改名：

```bash
python3 scripts/split_headings.py --text tmp/draft_import.md --headings tmp/heading_manifest.json \
        --atoms-dir sections --naming 'section_{n:02d}_{标题简称}.md' \
        --split-to-level <locate 输出的 split_to_level> --manifest-out tmp/split_manifest.json
```

首个标题之前有非空文字时生成 `section_00_frontmatter.md`，这时第一个标题的小文件从 `02` 起，没有 `01` 不是漏文件，因为编号是共享拆分脚本的区间序号加 1，首段占了区间 0。标题里的 `\/:*?"<>|` 与空白会从文件名里去掉，标题简称取前 20 个字符。

5. 之后与有标题路相同，走 0.3.4 的两道核验、0.3.5 的盲检、0.3.6 的拆分表与归属确认、0.3.7 的签字。

已知限制。子代理可能把正文短句当标题，或漏认大节标题；机械核对只能保证原句与行号对得上，认得对不对靠 0.3.5 的盲检、0.3.6 拆分表的提示列和用户确认。

#### 0.3.4 Layer 1（确定性核验，两路后恒跑）

先跑 `split_audit.py`：

```bash
python3 scripts/split_audit.py --text tmp/draft_import.md --headings tmp/heading_manifest.json \
        --manifest tmp/split_manifest.json --atoms-glob 'sections/*.md' \
        --split-to-level <N> --root . --report tmp/split_audit_report.json
```

逐区 offset 比对（slice_i vs atom_i）抓漏/造/串/边界漂移/乱序五类，无假绿。**exit 0** → 接着跑拼接核对；**exit 1**（region mismatch / preamble_dropped，fail-closed）→ 回退重拆，**禁手改文件蒙混**；**exit 2**（headings 空/畸形/glob 命中 0）→ 回 0.3.1。exit 1/2 = 不得声明拆分完成。

无标题路的清单里没有图注项，稿子里有形如图 1-1 的图注，`split_audit.py` 就会输出 `figure_parity` 提示。这个提示在此路径下说明不了图注有没有丢，不必为它停下，退出码不受影响。

再跑拼接核对，两条拆分路都跑。`split_audit.py` 会归一空白，把一个换行改成空格、删掉末尾换行它查不出；拼接核对按清单顺序把小文件的原始字节拼起来，与 `tmp/draft_import.md` 逐字节比较，另查 `sections/` 里不在清单里的 `.md` 文件：

```bash
python3 scripts/split_concat_check.py --text tmp/draft_import.md --manifest tmp/split_manifest.json --root .
```

退出码 0 才进 0.3.5。`draft_import.md` 由 `extract_headings.py` 产出，抽取时换行已统一成 LF；自行放进来的回车加换行稿，先把换行转成 LF 再拆，否则小文件按 LF 写出而拼接核对比较原始字节，会报 `BYTES_DIFFER`。退出码 1 报 `BYTES_DIFFER`、`LENGTH_DIFFER`、`ATOM_MISSING` 或 `STRAY_FILE`，定位成功后不该出现，出现了停下说明，不重试、不手改；`STRAY_FILE` 多半是上次拆分的残留，处置见 0.3.6。退出码 2 是文件缺失或清单畸形。

#### 0.3.5 Layer 2（LLM 边界反向核验，Layer 1 两道都过后恒跑）

跑 `split_boundary` gate（`references/dod_checklist.json`）via `delegate_review.py`——组 `tmp/split_verify_ctx.md`（标题树 + 各 atom 锚定行，**不含全文正文**）→ pack → 独立子代理 → verify。此层与 Layer 1 不冗余：split_audit *信任*标题真值，若 extract 层把正文误当标题/漏认真标题，Layer 1 比错真值仍报绿；Layer 2 读内容到最细标题级，抓"真值本身错"。verdict 映射（evidence 须以标签开头）：`[OK]`→pass 前进 / `[WRONG]`→fail 回退重切（有标题路先修 extract_headings 真值，无标题路让子代理改清单）/ `[UNCERTAIN]`→**fail 交用户裁决**（不自动动，展示上下文）。uncertain 映射 fail 非 na（na 会被放过）。

#### 0.3.6 用户确认拆分表与归属（两层皆绿后）

拆出的小文件名不以 P1 到 P4 开头，终检对 P2 与 P3 的放行（中文括号编号的列表提示与节奏剔除，分项行与年度计划行的第一个冒号）靠归属文件 `section_parts.json` 认出它们。归属由用户确认，确认前不生效。

**第一步，主会话写归属草稿 `tmp/parts_draft.json`。** 键只写小文件名，不带 `sections/` 目录（清单里的 `file` 字段带目录，照抄会被 `table` 以 `MISSING_PART` 与 `UNKNOWN_FILE` 打回）；值取 `P1`、`P2`、`P3`、`P4`、`其他` 五个之一：

```json
{"parts": {"section_00_frontmatter.md": "其他", "section_02_（一）立项依据.md": "P1", "section_05_2.1研究内容.md": "P2"}}
```

默认值按下面的对应表给。标题命中唯一一类模板措辞就用该归属；命中两类以上的是跨部分的容器标题，标 `其他`；都不命中就沿用最近的上级行；首段标 `其他`。

| 归属 | 模板措辞 |
|---|---|
| P1 | 立项依据、研究意义、国内外研究现状、研究假说 |
| P2 | 研究内容、研究目标、研究方案、技术路线、特色与创新、拟解决的关键科学问题、年度研究计划、预期成果 |
| P3 | 研究基础、工作条件、正在承担、已完成的项目 |
| P4 | 其他需要说明的情况、申请人同年申请、与本项目相关的其他项目 |
| 其他 | 首段、参考文献、同时含两类措辞的容器标题 |

**第二步，出拆分表：**

```bash
python3 scripts/section_parts.py table --manifest tmp/split_manifest.json \
        --draft tmp/parts_draft.json --out tmp/split_table.md --root .
```

退出码 1 是草稿与清单对不上（`MISSING_PART`、`UNKNOWN_FILE`、`BAD_PART`、`ATOM_MISSING`），改草稿再跑；退出码 2 是文件缺失或越根。拆分表一行一个小文件，按原稿顺序，连续且归属相同的行合成一组，列出序号、文件名、级别、标题、字数、归属、提示。第三行固定写明比较基准：

比较基准是抽取后的 draft_import.md，原件里的表格文字、自动编号、加粗不在其中。

把 `tmp/split_table.md` 展示给用户，提示列要逐条解释。容器表示只有标题没有正文；前后同属他组表示这一行夹在两个同归属的组之间，多半要改；疑似正文句、疑似表格行、首段较长提示这一行可能切错了。用户要改的行，改 `tmp/parts_draft.json` 后重跑 table，也可以留到第三步在终端里改。

**第三步，用户在自己的终端运行 `section_parts.py confirm` 确认。** 这条命令只能由用户本人运行，AI 不得代跑，不是终端时它会退出码 3 拒绝。它拦得住无意的忘记，在不分配终端的工具环境里，AI 顺手代跑会被退出码 3 拦下。故意的绕过它拦不住。归属文件是普通文件，AI 技术上能用写文件工具直接写它，也能用伪终端驱动 `confirm`，脚本分辨不出；`confirmed_via` 是脚本自己写的，不能当证据。所以 AI 不得代跑是纪律约束，没有机制在执行它，真正的把关是用户本人看拆分表。AI 把技能脚本和项目根的绝对路径填好，整条命令给用户：

```bash
python3 "<技能目录绝对路径>/scripts/section_parts.py" confirm \
        --manifest "<项目根绝对路径>/tmp/split_manifest.json" \
        --draft "<项目根绝对路径>/tmp/parts_draft.json" --root "<项目根绝对路径>"
```

给用户的操作说明，照下面写：

1. 打开终端。Mac 用 终端 或本 App 的终端面板，Windows 用 PowerShell 或 cmd（Git Bash 里要写成 `winpty python`）。
2. 粘贴上面整条命令，按回车。
3. 屏幕会一组一组列出小文件，每行有序号、文件名、级别、标题、当前归属和提示。这一组没问题就直接按回车；某一行要改，就写序号、空格、归属再按回车，例如 `7 P2`，全角数字也认，大小写都认。改完这一组会重新列出来，再按回车。
4. 最后是汇总，列出改动了几行和归属 P2 的文件。还要改就写序号、空格、归属；没问题就输入 确认 两个字，按回车。
5. 看到 已写入归属文件 就完成了，回到聊天窗口告诉 AI。
6. 中途按 Ctrl+C、输入别的内容或关掉终端都不会保存，重新运行这条命令就能再来一次。

想一行一行看，命令末尾加 `--each-row`，每行按一次回车，要改就只写归属。命令末尾加 `--note "<一句话>"` 可以记下确认要点。

命令以退出码 1、2、3 结束时，把以上文字整段复制回聊天窗口。退出码 1 是草稿与清单对不上或用户没有确认；退出码 2 是文件缺失、越根或小文件目录的父目录不是项目根；退出码 3 是不在终端里运行。

确认后归属文件落在 `<项目根>/section_parts.json`，`humanizer_zh.py scan-all` 与 `diagnosis_engine.py` 的 diagnose-all、full-review、polish-review 读它放行归属 P2 或 P3 的小文件，stderr 会打一行 `按 section_parts.json 放行 N 个文件`，让用户看见放行来源。归属文件只记小文件名、标题、级别、归属、确认时间和小文件目录名，有效性只看它自己和 `sections/` 里现有的文件名，不读 `tmp/`。状态可用 `python3 scripts/section_parts.py show --sections-dir sections` 查看。

**会写 `tmp/split_manifest.json` 的步骤**，只有两处：0.3.2 或 0.3.3 的 `split_headings.py --manifest-out`，以及有标题路的研究目标改名（改小文件名后同步改清单里的 `file` 与 `id`，再重跑 0.3.4）。研究目标改名必须在第三步确认之前做，确认后再改名会让归属文件里的文件名对不上。

**重拆或回滚后必须重新确认归属。** 归属文件绑的是小文件名，重拆后文件名相同而边界变了它检测不到；`state_manager.py` 回滚会整个替换 `sections/`，不碰 `section_parts.json`。两种情况都要把 `tmp/parts_draft.json` 重新对一遍，再让用户跑一次第三步。重拆前先列出旧清单里的文件，经用户同意再删 `sections/` 里的残留，否则拼接核对会报 `STRAY_FILE`，合并时也会混入。

#### 0.3.7 结构签字解锁 Step 3

用户确认归属后落签字，解锁后续逐节 Write/Edit。签字命令也由用户在自己的终端运行：

```bash
python3 scripts/structure_signoff_gate.py confirm --root . --note "<用户确认拆分表的要点/原话>"
```

**铁律**：confirm 只能在"两层核验皆绿 + 用户在对话中明确对拆分表说 yes + 0.3.6 的归属确认完成"之后跑，**AI 不得代替用户自行 confirm**。拆分脚本经 Bash 写 `sections/*.md` **不经 Write/Edit 工具**，故未签也能落盘拆分产物（与 Write Mode 同机理，hook 只 PreToolUse 拦 Write/Edit）；真正被 signoff 门控的是 Step 3 逐节改写——未签时对 `sections/*.md` 的每次 Write/Edit 被 hook deny。签字指纹不含 `sections/`，也不含 `section_parts.json`，归属文件不在门禁写保护里。


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

[假说在 P1 末段（旧结构项目的假说在 P2，按实际位置评），研究设计在 P2：假说是否可证伪？实验设计是否能验证假说？
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
  "section": "P2_2.2.1_某载体的构建与表征.md",
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
    "rewrite_sections": ["P1_立项依据", "P2_2.4_本项目的特色与创新之处"],
    "polish_sections": ["P2_2.1.1_某载体的构建与表征", "P2_2.1.2_..."],
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
