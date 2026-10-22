> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

# Citation Zero-Hallucination Gate：规则、学科路由、来源策略与引用类型（命令行在 SKILL.md 正文）

`--write-back` 由脚本把每条 `verified` 与 `verification_details.checked_at` 落回 `literature_index.json`（AI 不手动改 `verified`）。据此下一轮核验对**已 verified 且未过 TTL** 的条目自动短路复用、跳过在线重验；`sci-source-seed` 种子（`verified=false`）与过期/未验条目照常走完整在线核验，撤稿与新鲜度安全不受影响。报告字段 `reused_fresh_verified_count` 记录本轮命中短路的条目数。

Rules:
- Immediately after each retrieval/import batch updates `literature_index.json`, run the guard once before any drafting.
- If guard exits non-zero or report `ok=false`, stop writing and resolve the queue first.
- When bidirectional verification fails (`title_mismatch`|`doi_invalid_or_unresolved`|`pmid_invalid_or_unresolved`|`id_mismatch`), set `verified=false` immediately and route entry to `manual_review_queue` for manual confirmation before正文引用.
- Unverified references must not be cited in chapter markdown.
- Every cited entry must carry traceability fields (`source_provider` + `source_id`) and DOI/PMID whenever available.

**Topic-dependent routing (MANDATORY):**
- Life science / medicine / clinical / biochemistry / pharmacology → **PubMed CLI first** (`esearch`/`efetch`/`einfo`, `~/edirect/`, requires `< /dev/null`, proxy `http://127.0.0.1:<PROXY_PORT>`). Auto-install if missing: `sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"`. **Windows:** edirect 在 Windows PowerShell/CMD 不可用，用 WSL bash，或自动回退 paper-search MCP。
- CS / AI / engineering / physics / interdisciplinary → **paper-search MCP first** (`mcp__paper-search-mcp__search_arxiv` etc.).
- Fallback to the other source when primary yields no results.

> **跨平台命令说明：** 本文档内联的 `python3 scripts/xxx.py` 命令在 Windows 上用 `python` 或 `py` 代替 `python3`。

`literature_index.json` 必需字段 schema 见 `references/format_profile_schema.md § literature_index.json schema`。

- Source provider policy is strict:
  - Allowed: `pubmed-cli` (life science primary), `paper-search` (CS/AI primary / fallback / preprints).
  - Forbidden: `websearch`, `openalex-cli` (pyalex), `tavily`。`citation_guard.py` 以 `source_provider_not_allowed` 拒绝这些来源。
  - 无 DOI/PMID 的条目不予放行，进入 `manual_review_queue` 人工核实。
  - **Serial Search (MANDATORY):** Execute all retrieval calls sequentially. Never parallelize. Enforce ≥1s interval between consecutive calls.
  - **Citation Type by Context (MANDATORY):**
    - Background / field overview → Reviews or Systematic Reviews preferred.
    - Specific mechanistic/experimental claims → Original Articles (do NOT substitute a Review as the sole support).
    - Clinical efficacy/safety claims → Clinical Trials.
    - Emerging/cutting-edge claims → Preprints (label as [Preprint]; only when no peer-reviewed equivalent exists).
- This guard does not change existing chapter writing workflow; it only validates reference correctness.
- For final delivery strict mode, run with `--require-mcp`.
