# HTML Fill Guide

Use `html-template.html` as fixed layout and only replace placeholders.

## Required placeholder mapping
- `{{MANUSCRIPT_TITLE}}`: manuscript title
- `{{DATE}}`: output date
- `{{COMMENT_ID}}`: e.g., `R1-Major-01`
- `{{COMMENT_ZH}}`, `{{COMMENT_EN}}`
- `{{RESPONSE_EN}}`
- `{{REVISED_EXCERPT_EN}}`
- `{{NOTE_CORE_1}}`, `{{NOTE_CORE_2}}`
- `{{NOTE_SUPPORT_1}}`, `{{NOTE_SUPPORT_2}}`

## Evidence area
- Text: `{{EVIDENCE_TEXT}}`
- Image:
  - `{{IMAGE_1_SRC}}`: absolute local path or https URL
  - `{{IMAGE_1_ALT}}`: short alt text
  - `{{IMAGE_1_CAPTION}}`: one-sentence caption
- Table:
  - `{{ROW1_*}}`, `{{ROW2_*}}` for key correction records

## Missing attachments
If no image or table data is provided by user:
- Keep the image/table skeleton.
- Fill cells with `Not provided by user`.
- Do not fabricate values.
