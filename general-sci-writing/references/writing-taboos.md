> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

## 🛡️ 写作禁忌
1. **严禁割裂**：不得在 Results 中仅罗列数值而将解释全部推迟至 Discussion。
2. **严禁简略**：Key Findings 仅以一两句话带过属于深度不足，**须补充展开**——但这是写作要求，**不是落盘阻断**（字数/深度的门禁口径以 §融合写作策略"深度控制（软提示，非硬门）"为准：不足不拦落盘）。
3. **严禁遗忘**：每次写作前须执行预加载（write-cycle 完整命令与白名单见 §13）。全局历史与进度必须读取；正文草稿默认不读取（续写/改写时才加 `--include-draft`），避免无稿场景污染上下文。

### ❌ 反例黑名单（Anti-Patterns）
- ❌ 跳过图集先行：故事线未确认就启动图集规划，或图集未规划就直接识图、写正文（流程必须 storyline → figure-plan → figure → write）。
- ❌ 用 websearch / tavily / openalex 查文献：检索阶段只允许 PubMed CLI（生命科学）或 paper-search MCP（CS/AI），跨库聚合工具一律禁用。
- ❌ 编造文献：引用未带 source_provider + source_id、未过 citation_guard 双向核验，或用知识库充当已检索文献。
- ❌ 用 Review 顶替原始文献：机制论点和实验论点必须引 Original Articles。
- ❌ 从像素估定量：读 WB／荧光／IHC／散点图时估强度、阳性率、共定位、数散点反推 n，或对图做病理判读；读不到就问用户。
- ❌ 编数据或填占位符：缺核心定量（P 值／关键 n／效应量）时继续写，或用 “XX%” 之类占位符顶替。
- ❌ 手改派生稿：编辑 Full_Manuscript.md 或 .docx，而不是改 manuscripts/ 下的原子化源文件。
- ❌ 把整个 Results 或 Introduction 写进一个文件，违反一个 sub-section 一个 markdown 的原子化规则。
- ❌ 连续自动写多节：每节落盘前不展示字数、引用、figure、缩略词、占位数给用户确认就直接写。
- ❌ 主 agent 自评 DoD 当通过：节末检查必须委托独立subagent盲检，上一节 verify 未 exit 0 就开写下一节。
- ❌ 带 CITE_PENDING / DATA_PENDING / REF_DROPPED 占位跑 /merge，跳过 Phase 10 占位扫描门禁。
- ❌ 先写超期刊上限 30% 再砍：storyline 必须在 target_journal 字数上限内编排。
- ❌ Discussion 漏写 Limitations 段，或正文用列点符号，或用装饰性破折号（em-dash —/——/␣–␣，一个都不许有），硬禁、命中即 fail。（单句超 30 词为软提示，见提醒酌情改，不列入硬性反例。）
- ❌ 投稿包残留 `{{VAR}}` 占位、伪造 reviewer 邮箱、瞒报 COI，或 Source Data 数值与图不对应。

