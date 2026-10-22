> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

# 第三部分·二：外部基准与技术合规审计检查点（TOOL_USAGE_RULES / SEARCH_EVIDENCE_GATE / CITATION_GUARD_RULE）

<TOOL_USAGE_RULES>
**检索工具调用指令（学科路由，Mandatory）：**
1. **判断论文所属学科**：
   - 生命科学 / 医学 / 临床 / 生化 / 药学 → **首选 PubMed CLI**
   - CS / AI / 工程 / 物理 / 跨学科 → **首选 paper-search MCP**（arXiv/Google Scholar）
2. **PubMed CLI**（生命科学首选）：`esearch`/`efetch`/`einfo`（路径 `~/edirect/`），调用时必须追加 `< /dev/null`，走代理 `http_proxy=http://127.0.0.1:<PROXY_PORT>`（将 `<PROXY_PORT>` 替换为本机代理端口；无需代理可省略 `http_proxy`）。
   **Windows：** `< /dev/null` 与下面的 `sh`/`curl` 安装脚本在原生 cmd/PowerShell 不可用，请在 WSL 下运行 PubMed CLI，或跳过它改用 paper-search MCP（见第 3 条）。
   可用性检查：若 `~/edirect/esearch` 不存在，自动安装：`sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"`
3. **paper-search MCP**（CS/AI首选 / 预印本 / PubMed无结果时fallback）：`mcp__paper-search-mcp__search_arxiv`、`mcp__paper-search-mcp__search_pubmed` 等。

**【严禁】**：`tavily`、`websearch`、`openalex`（pyalex），**禁止用于文献检索**，无论何种情况。
**串行执行（MANDATORY）：** 所有检索调用（含 PubMed CLI 与 paper-search MCP）必须串行执行，禁止并行，每次间隔 ≥1s。
</TOOL_USAGE_RULES>

**检索→门禁衔接（必读）：** 上述检索命中的每篇文献，必须把其 `source_provider`+`source_id`（以及 title/doi/pmid）写入 `data/literature_index.json` 后，再运行 citation_guard；否则 index 为空，门禁空转（见下方空 index 豁免）。

<SEARCH_EVIDENCE_GATE>
**⑥ 检索证据门（新颖性/相似研究/与文献矛盾类批评的硬前提）：** 凡属"**此工作不新颖 / 已有高度相似研究 / 与已发表文献矛盾**"这三类批评，**必须先真的检索、并在报告里留下检索确已发生的痕迹**：写出检索工具与检索式（如 `PubMed: "keyword A" AND "keyword B", 2020-2026`）、命中日期（YYYY-MM-DD），并**指名具体相似/矛盾文献**（标题 + DOI/PMID，且已按上文写入 `literature_index.json` 过 citation_guard）。
- **空 index 豁免不豁免空口断言**：`literature_index.json` 为空（`status=empty`）只豁免"外部文献结论核验"这一步——豁免的是写作步骤（报告里不写外部文献结论），不是脚本退出码；citation_guard 对空 index 仍 exit 2，这是正常返回不是失败，判定以 report 的 `status=="empty"` 字段为准。**绝不豁免**上述三类批评。没有检索痕迹与具名文献，就**不许**写"该研究缺乏新颖性""已有类似工作"之类断言（这是最常见的凭空批评）。想下这类结论，必须先补检索、留痕、具名；否则只能改写为"作者需自证新颖性/补充与近三年文献的对比"这类**要求作者举证**的中性表述，不得由审稿人空口定性。
</SEARCH_EVIDENCE_GATE>

<CITATION_GUARD_RULE>
任何写入评审报告正文的外部文献结论，必须先通过统一核验脚本。**脚本位于技能安装目录的 `scripts/` 下（≠用户 CWD），调用时必须用其绝对路径**；技能安装目录以 `$SKILL_DIR` 指代，按文首【技能安装目录解析】从本 SKILL.md 实际加载位置动态解析（不是固定路径，各 runtime 安装位不同）。`--index` 等数据文件仍用 `$WORKROOT/data/...`（锚定 CWD，见第四步初始化）：
`python "$SKILL_DIR/scripts/citation_guard.py" --index "$WORKROOT/data/literature_index.json" --mcp-cache "$WORKROOT/data/mcp_literature_cache.json" --mcp-ttl-days 30 --manual-review "$WORKROOT/data/manual_review_queue.json" --log "$WORKROOT/data/verification_run_log.json" --report "$WORKROOT/data/citation_guard_report.json"`

硬门禁：
1. 仅当 `citation_guard_report.json` 中 `ok=true` 才允许把该文献作为证据写入评审报告。
2. 若 `ok=false` 或命令失败，必须改写为“待核验”并禁止下结论。
3. 报告中不得出现任何无法追溯来源（`source_provider` + `source_id`）的文献陈述。
4. 该门禁只负责证据核验，不改变 TOOL_USAGE_RULES 中的学科路由检索顺序。
5. **空 index 豁免：** 当稿件无外部文献引用需核验（`literature_index.json` 为 `[]`）时，脚本返回 `ok=false`、`status="empty"`，这是"无可核验项"而非"核验失败"。此情形下**跳过本门禁，不得因空 index 阻断交付**；报告中相应不出现任何外部文献结论即可。仅当 index 非空且 `ok=false` 时才触发第 2 条改写。**注意：空 index 豁免只免"外部文献结论核验"，不免新颖性/相似研究/与文献矛盾三类批评的检索举证，见上方 `SEARCH_EVIDENCE_GATE`。**注：citation_guard 对空/缺失 index 返回退出码 2，判定以 report 的 `status=="empty"` 字段为准，**勿用退出码判断成败**。
</CITATION_GUARD_RULE>

如无任何可用工具支持,则靠语言特征和文本分析人工判断；外部基准核查与技术合规审计的逐项清单见 **`references/review_rubric.md`** 第三节。


