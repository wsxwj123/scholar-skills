# 文献政策 (citation-policy)

> 被 SKILL.md 的 Role 区与 **Phase 3 (`/literature`)** 引用。检索文献、入库、核验前 `Read` 本文件。
> 底线（不编造文献）已在 SKILL.md 顶部 P0#1 常驻；本文件是完整执行细则。

## 文献检索工具（学科路由，Mandatory）

1. **判断学科类型**：
   - 生命科学 / 医学 / 临床 / 生化 / 药学 → **首选 PubMed CLI**
   - CS / AI / 工程 / 物理 / 跨学科 → **首选 paper-search MCP**（arXiv/Google Scholar）
2. **PubMed CLI**（生命科学首选）：`esearch`/`efetch`/`einfo`（路径 `~/edirect/`），必须带 `< /dev/null`，走代理 `http_proxy=http://127.0.0.1:<PROXY_PORT>`。
   - 示例：`export http_proxy=http://127.0.0.1:<PROXY_PORT> && esearch -db pubmed -query "xxx" < /dev/null | efetch -format abstract`
   - 可用性检查：若 `~/edirect/esearch` 不存在，自动安装：`sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"`
   - **Windows：** edirect 在 PowerShell/CMD 不可用，请用 WSL bash，或自动回退 paper-search MCP。
3. **paper-search MCP**（CS/AI首选 / 预印本 / PubMed无结果时fallback）：`mcp__paper-search-mcp__search_arxiv`、`mcp__paper-search-mcp__search_pubmed` 等。
4. **严禁**：`tavily`、`websearch`、`openalex`（pyalex）— 无论有无 DOI/PMID。
5. **串行执行（Mandatory）**：所有检索调用（含 paper-search MCP 与 PubMed CLI）必须串行执行，禁止并行，每次间隔 ≥1s。

## 文献真实性硬约束 (Zero-Fabrication Policy)

1. **零容忍**：严禁编造虚拟文献；严禁把不同文献的标题/作者/期刊/年份/DOI 交叉拼接成"新文献"。
2. **来源强制**：写入 `literature_index.json` 的每条文献必须来自 MCP 检索原始结果，并保留可追溯来源信息（至少包含 `source_provider` + `source_id`，如 PMID/DOI/arXiv ID/S2 ID 之一）。
3. **Provider 白名单**：`citation_guard.py` 允许入库的 `source_provider` 仅限 `pubmed-cli`（首选）、`paper-search`（CS/AI首选/备用/预印本）；`tavily`、`openalex-cli`、`websearch` 一律阻断，不得作为检索/入库来源。文献**检索**阶段严禁使用 tavily。
4. **Tavily 边界**：`tavily` 仅用于文献真实性的反向核验（佐证已入库条目的标题/元数据），**不得作为检索来源**；任何 `source_provider=tavily` 的条目一律判为失败，禁止入库（带 DOI/PMID 也不例外）。
5. **入库前核对**：入库前必须核对"标题-作者-DOI/ID"来自同一条原始记录；任一关键字段冲突则判定为无效条目，禁止入库。
6. **双向核验失败处理**：若出现 `title_mismatch`、`doi_invalid_or_unresolved`、`pmid_invalid_or_unresolved`、`id_mismatch`，必须立即设为 `verified=false`，写入 `manual_review_queue.json`，禁止正文引用。
7. **不确定处理**：无法完成同源核验的条目必须标记为 `unverified`；未带 `source_provider` / `source_id` 的条目不得入库。`unverified` 与 `needs_manual_review=true` 条目都**禁止在正文使用 `[n]` 引用**，也不得进入参考文献列表。
8. **补全边界**：摘要补全协议仅允许补全 `abstract` 字段，禁止改写已核验文献的核心元数据（标题/作者/期刊/年份/DOI）。
9. **强制核验门禁**：任何正文写作前与交付前，必须执行：
   - `python scripts/citation_guard.py --index literature_index.json --mcp-cache mcp_literature_cache.json --mcp-ttl-days 30 --manual-review manual_review_queue.json --log verification_run_log.json --report citation_guard_report.json --write-back`（Windows 用 `python` 或 `py` 代替 `python3`）
   - **`--write-back` 必带（别靠 AI 记得）**：它把每条 `verified` + `verification_details.checked_at` 落盘回 `literature_index.json`。这是 L1 逐条短路的前提。下次核验时，TTL（`--mcp-ttl-days`）内的已验条目直接复用落盘结果、跳过在线抓取；不写回则每次全量重验，等于白验。过期/未验条目仍照常重新核验，门禁强度不变。
   - 若返回非零或报告 `ok=false`，立即阻断写作；必须先处理 `manual_review_queue.json` 后再继续。
   - guard 报告必须显式包含 provider policy、bidirectional failure 与 manual review 触发原因，便于追溯。
   - 不改变检索优先级（学科路由：生命科学→PubMed CLI / CS/AI→paper-search MCP）；仅增加核验门禁。
   - Phase 3 结束时和最终交付前，`--require-mcp` 为强制参数（非建议），确保所有文献有 MCP 证据轨。

## 引用类型按语境（Citation Type by Context，MANDATORY）

- 背景/综述性表述 → 优先引用 Reviews 或 Systematic Reviews，也可引用 Original Articles 作为直接证据支撑。
- 具体机制/实验论点 → 必须以 Original Articles 为主要证据；严禁用 Review 代替 Original Article 作为具体实验论点的唯一支撑。
- 临床疗效/安全性论点 → Clinical Trials（与 Original Articles 同等优先级）。
- 前沿/新兴论点 → Preprints（仅在无同行评审等效文献时使用；引用列表须标注 [Preprint]）。

## 分节重编号规则 (Section-Level Renumbering，MANDATORY)

> 被 SKILL.md 的 **Phase 3 (`/literature`)** 引用。文献编号、分节分配、增量检索同步的完整细则在此；SKILL.md 主文件只保留触发点与脚本硬门禁命令。

### 首轮检索后强制分配与重编号

1. **首轮完成即分配**：第一轮文献检索完成后，必须将每条已核验文献分配到目标小节（`section_id`），禁止保持"未分配"状态进入写作阶段。
2. **矩阵落地**：在用户确认后，必须将"小节-文献"映射写入文献矩阵（建议存入 `storyline.json` 的矩阵字段，或独立 `literature_matrix.json`），作为后续正文撰写唯一依据。
   - **小节粒度硬要求**：矩阵中的 `section_id` 必须与 `storyline.sections[].id` 一一对应到"小节级"（如 `results_3.1`, `results_3.2`）；禁止只写到大章级（如仅 `results`）。
3. **先重排后写作**：在开始任何小节正文前，必须按"小节顺序 + 小节内引用优先级"对 `literature_index.json` 重新编号为连续 `1..N`，不得沿用"检索时间顺序编号"。
4. **分节引用约束**：撰写某小节时，只允许引用该小节矩阵内文献；后续新检索到的文献若理论上应归属前文小节，必须先触发全局重编号与正文同步，再继续写作。
5. **一致性收口**：每轮写作收口仍必须执行权威 finalize 命令（完整 flag 见 SKILL.md P0#10），确保正文 `[n]`、各小节参考列表与全局索引三者一致。

### 后续增量检索同流程

1. **全程一致**：第二轮及后续每一轮新增文献，必须重复执行"分配到小节 → 更新矩阵 → 全局重编号 → 同步落盘"，严禁仅追加到索引末尾后直接写正文。
2. **实时更新触发**：只要发生以下任一动作，必须立即更新 `literature_index.json` 与文献矩阵并执行同步：新增文献、文献重分配到其他小节、删除文献、合并去重、修改核心元数据（标题/作者/DOI/年份）。
3. **写作前一致性检查**：开始任一小节写作前，必须确认"正文引用号、`literature_index.json`、文献矩阵"三者一致；任一不一致必须先同步修复，禁止继续生成正文。
4. **冲突优先级**：当"新检索文献应出现在前文小节"与"当前小节写作"冲突时，优先执行全局重编号与全稿引用同步，再恢复写作。

---

## 承重声明的引文类型纪律（article_type，Mandatory）

入库条目带 `article_type` 字段（`citation_guard.py --write-back` 从 PubMed pubtype 优先级解析落值：`original_research`/`review`/`meta_analysis`/`systematic_review`/`clinical_trial`/`preprint`/`guideline`/`other`/`unknown`；非 PubMed/人工导入 → `unknown`）。承重引用选型纪律：

1. **承重机制/实验声明的 ref 应为 `original_research`，不得以 `review`/`systematic_review` 代替**：机制句、因果句、"我们/该研究测得/证明"这类承重实验声明，必须挂做出该原始观测的原始研究，不能只挂一篇综述转述。综述可作背景铺垫引用（`claim_kind=background`），但不能作机制/实验证据的唯一支撑。
2. **疗效声明**（`claim_kind=efficacy`）可挂 `meta_analysis`/`clinical_trial`（荟萃/临床试验是疗效的合法上位证据），但不得只挂 `review`。
3. **preprint 承重需标注**：以 `preprint` 作承重证据时正文该处须显式标 `[Preprint]`，提示未经同行评审。
4. **机械联动**：以上由共享 `citation_claim_check.py` 的 `claim_kind × article_type` 纪律机械核（承重机制/疗效声明挂综述 → exit 2；任一字段 `unknown`/缺 → 只 warning 不硬拦，不误杀存量项目）；DoD 盲检 gate 另有对应盲检项。字段缺失一律 fail-safe，不炸。

---

## 中文文献支线（Chinese Literature Manual Track，按需触发）

SCI 论文通常只在少数场景需引中文文献（中药/中医、临床路径、地方流行病学、政策文献等）。中文期刊普遍**无 DOI、无 PMID**，`citation_guard` 双向核验跑不通，故走"AI 发现 → 用户人工取证 → 责任标记"的合规通道，绝不绕过护栏自动入库。

1. **检索（AI 自动）**：用 `mcp__paper-search-mcp__search_google_scholar` 检索中文关键词（Google Scholar 覆盖中文核心期刊，免费可调；**不要**用知网/万方/维普——无开放 API，反爬严，无法自动调用）。
2. **AI 仅返回候选清单**：标题 / 作者 / 期刊 / 年份 / Scholar 链接。**严禁直接入库**，因为缺 DOI/PMID 无法过 `citation_guard`。
3. **用户人工取证**（必选其一）：
   - **路径 A（推荐）**：去 CNKI / 万方 / 维普 / 期刊官网搜该篇，记下 **DOI** 或 **CSTR**（中科院中文 DOI）→ AI 用此 ID 走 `citation_guard` 双向核验入库（与英文文献同流程）。
   - **路径 B**：用户提供原文 PDF + 完整元数据 → AI 入库，但条目必须带 `verified=false`、`needs_manual_review=true`、`requires_human_attest=true`（用户书面确认"我对这条负责"才允许在正文 `[n]` 引用）→ 进入 `manual_review_queue.json`。
   - **路径 C**：以上都做不到 → **不引该条**，找等价英文文献替代。
4. **正文引用规则**：路径 A 与英文条目同等；路径 B 入库的条目，每次在正文写 `[n]` 前 AI 必须主动提醒"该条为人工背书条目，是否仍要引用"，用户确认后才写入。
5. **导出**：`/export_bib` 时路径 B 条目在 .bib 中加 note 字段标注 `[CN-Manual]`，方便投稿前人工复核。
