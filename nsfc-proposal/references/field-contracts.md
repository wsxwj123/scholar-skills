> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

### Mandatory Field Contracts (Hidden Trip-Wires)

The following fields are silently required by scripts. Missing them causes hard failures that are **not** obvious from error messages alone.

**`data/mcp_literature_cache.json`：MCP 缓存条目必填字段：**

每条缓存记录必须包含时间戳字段 `verified_at` 或 `checked_at`（二选一即可，`_is_mcp_fresh` 按此顺序查找）。使用 `retrieved_at` 或其他名称时脚本视为时间戳缺失，触发 `mcp_timestamp_missing` 硬失败。

最小合规样例：
```json
{
  "metadata": {"schema_version": "1.0"},
  "entries": [
    {
      "doi": "10.1234/example",
      "pmid": "12345678",
      "title": "Example Paper Title",
      "verified_at": "2026-06-01T12:00:00+00:00"
    }
  ]
}
```

**`data/literature_index.json`：文献索引条目必填字段：**

凡 `used_in_sections` 含 `"P1"`（或旧值 `"P1_立项依据"`，只读兼容）的条目，若 `key_finding` 字段为空或缺失，`_context_check` 直接返回 `False`，触发 `context_mismatch` 软失败并降低 `confidence_score`。

最小合规条目：
```json
{
  "ref_number": 1,
  "title": "Example Paper Title",
  "doi": "10.1234/example",
  "pmid": "12345678",
  "used_in_sections": ["P1"],
  "key_finding": "该研究发现X蛋白通过Y通路调控Z过程（主要数据点）",
  "is_recent_5yr": true,
  "is_cn_journal": false
}
```

字段名速查：
| 字段 | 所在文件 | 若错用 | 触发失败类型 |
|------|---------|--------|------------|
| `verified_at` 或 `checked_at` | mcp_literature_cache.json 每条记录 | 写成 `retrieved_at` | `mcp_timestamp_missing`（HARD） |
| `key_finding` | literature_index.json 每条 P1 引用条目 | 字段为空/缺失 | `context_mismatch`（SOFT） |
| `search_source` | literature_index.json 每条 | 填 `tavily`/`websearch`/`openalex`/`pyalex` | `source_provider_forbidden`（HARD） |

