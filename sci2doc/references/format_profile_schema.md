# Format Profile Schema & Style Selection Details

主文件只保留触发条件与硬门禁（`pending_template` 不得导出 docx）。本文件是 `format_profile` 字段字典、样式选择 Gate 细则与 `literature_index.json` schema 的权威清单。

## Style Selection Gate (full rules)

> **执行顺序：** 本 Gate 在 `### 0) Material Input Gate` 完成后执行（先确认材料，再选样式）。如无源材料，停在 Step 0，不进入 Style Selection。

Before any project initialization or drafting, the AI **must** present exactly two style options and require the user to choose one:

1. `默认设置` — use the built-in default doctoral thesis style template.
2. `自定义样式` — user must provide the target university plus detailed Word formatting requirements and/or reference template materials.

Rules:
- The choice must be written to local state via `thesis_profile.json > format_profile`.
- `project_state.json > progress.status` must mirror the operational state.
- If the user chooses custom style but the template information is incomplete, the project may still be initialized, but it **must** be marked as `pending_template`.
- `custom` can become `ready` only after the AI writes structured layout fields into local state, at minimum:
  - `format_profile.page_margins_cm.top|bottom|left|right`
  - `format_profile.header_distance_cm`
  - `format_profile.footer_distance_cm`
  - `format_profile.university_name`
  - `format_profile.degree_type`
- For requirement-driven customization, AI should prefer writing structured rules into `format_profile.style_profile` when the user provides explicit font/size/spacing/table/front-matter requirements instead of a `.docx/.dotx` file.
- `pending_template` projects may continue collecting requirements and drafting source markdown, but **must not** generate `.docx` or run final format acceptance.
- Do not silently inherit the built-in default layout numbers when switching a project from `default_generic` to `custom`. Missing structured custom layout fields mean `pending_template`, not `ready`.
- Built-in automated Word formatting applies the default template only for `default_generic`. For `custom ready`, scripts must read local structured fields instead of hardcoded default constants.
- Custom template evidence files should be stored under `04_图表文件/` or referenced by absolute path in `format_profile.source_template_files`.
- `state_manager.py init` and `state_manager.py profile` must automatically render managed front matter files into:
  - `atomic_md/封面.md`
  - `atomic_md/题名页.md`
  - `atomic_md/独创性声明与授权书.md`
  - `atomic_md/中文摘要.md`
  - `atomic_md/英文摘要.md`
  - `atomic_md/目录.md`
  - `atomic_md/缩略语表.md`
  - `02_分章节文档/封面.docx`
  - `02_分章节文档/题名页.docx`
  - `02_分章节文档/独创性声明与授权书.docx`
  - `02_分章节文档/中文摘要.docx`
  - `02_分章节文档/英文摘要.docx`
  - `02_分章节文档/目录.docx`
  - `02_分章节文档/缩略语表.docx`
- If a front matter markdown file has been manually rewritten and no longer carries the managed marker, scripts must not silently overwrite it.
- If `format_profile.status == pending_template`, managed front matter markdown may still be refreshed, but managed `.docx` front matter must be skipped.

## Single Source of Truth

The thesis target profile is stored in:
- `thesis_profile.json`

The style choice and formatting gate are also stored there:
- `format_profile.mode`: `default_generic` | `custom`
- `format_profile.status`: `ready` | `pending_template`
- `format_profile.source_template_files`
- `format_profile.requirements_summary`
- `format_profile.missing_requirements`
- `format_profile.allow_docx_generation`
- `format_profile.page_margins_cm`
- `format_profile.header_distance_cm`
- `format_profile.footer_distance_cm`
- `format_profile.header_left_text`
- `format_profile.graduate_school_name`
- `format_profile.declaration_authorization_school_name`
- `format_profile.school_code`
- `format_profile.style_profile`
- `format_profile.page_numbering`

Default profile is created by `state_manager.py init` and can be updated with:
- `state_manager.py profile`

Preferred structured update entrypoints:
- `state_manager.py profile --format-profile-json '{...}'`
- `state_manager.py profile --project-info-json '{...}'`

Structured payload rules:
- `--format-profile-json` and `--project-info-json` must decode to JSON objects only.
- Scripts must reject unknown top-level keys or wrong field types instead of silently ignoring them.
- `format_profile.page_numbering` is the canonical location for page-number orchestration:
  - `front_matter.format|start`
  - `body.format|start`
  - `back_matter.format|start`
- Allowed page number formats are:
  - `decimal`
  - `lowerRoman`
  - `upperRoman`
  - `lowerLetter`
  - `upperLetter`
- Requirement-only customization should be mapped into structured fields first:
  - page layout -> `page_margins_cm`, `header_distance_cm`, `footer_distance_cm`
  - body/heading/table/abstract rules -> `style_profile`
  - page numbering switch points -> `page_numbering`
- If the user only gives narrative formatting rules and those rules are still insufficient to fill the required structured fields, keep the project in `pending_template`.

`project_info_json` should be used for front matter content such as:
- `classification`
- `udc`
- `abstract_zh`
- `keywords_zh`
- `abstract_en`
- `keywords_en`

`project_state.json` mirrors the actionable runtime status. When custom requirements are incomplete, `progress.status` must be `pending_template`.

All scripts should follow this profile to avoid rule conflicts and to prevent accidental export under the wrong school format.

## literature_index.json schema

每条文献一个 JSON 对象，存入顶层数组：

```json
[
  {
    "id": "ref001",
    "title": "文章完整标题（从检索结果复制，勿手写）",
    "authors": ["Author A", "Author B"],
    "year": 2023,
    "journal": "Journal Name",
    "doi": "10.xxxx/xxxxx",
    "pmid": "12345678",
    "source_provider": "pubmed-cli",
    "source_id": "12345678",
    "chapter": 2,
    "verified": false,
    "key_finding": "该文献真实结论一句话（可选，供引文核证参照）",
    "claim": "本文用它支撑的论点（可选，供 citation_claim_check 对齐）"
  }
]
```

字段规则：`source_provider` 只允许 `"pubmed-cli"` 或 `"paper-search"`；`doi`/`pmid` 至少填一个；`verified` 初始为 `false`，citation_guard 通过后由脚本置 `true`；`chapter` 为该文献首次引用的章节号；未知字段填空字符串，**严禁填写推测值**。

`key_finding` / `claim` 为**引文核证**最小承载字段（B②，均可选）：`key_finding` 记该文献的真实结论、`claim` 记本文用它支撑的论点；二者仅供 `SKILL.md § Citation Claim Check` 建 `claim_evidence.json` 时对齐参照。**核证判 verdict 时以检索到的真实 abstract 为准，不看可编的 `key_finding`**。
