# Output Template (One-Shot Hierarchical HTML)

Produce **one single HTML file**.

## Required hierarchy
- TOC Level 1: `回复审稿人的邮件`
- TOC Level 1: `Reviewer #1`, `Reviewer #2`, ...
- TOC Level 2 (inside reviewer): `Major`, `Minor`
- TOC Level 3 (inside section): `Comment 1`, `Comment 2`, ...

## Required page schema for each leaf comment
1. 审稿人意图理解
   - 先展示该条 reviewer 原始意见（English）
   - 再展示“应如何理解”中英对照（上下排列）
2. Response to Reviewer（中英对照）
   - English box + 中文 box（上下排列）
   - 两个 box 都必须有复制按钮
3. 可能需要修改的正文/附件内容（中英对照）
   - English box + 中文 box（上下排列）
   - 若不需要修改，写 `无`
   - 两个 box 都必须有复制按钮
4. 修改说明（中文，含 🔴 / 🟡）
5. Evidence Attachments (Text + Image + Table)

## Interaction requirements
- Click TOC item to show one corresponding page.
- Keep only one content page visible at a time.
- Responsive layout for desktop and mobile.

## Missing data behavior
- If no image/table data available, keep module and fill `Not provided by user`.
- If revised excerpt is not confidently extractable, keep explicit placeholder and do not fabricate.

## UI 验收对照（由 `scripts/build_full_package.py` 的 `render_html()` 硬编码实现，AI 无需手工实现）
以下细则在重渲/排错时用于核对脚本输出，不是 AI 手写 HTML 的清单。

### TOC 层级与严重度配色
- TOC 层级：`回复审稿人的邮件`（顶）→ `Reviewer #N` → `Major`/`Minor`/`General` → `Comment k`（叶）。
  - 若 reviewer 用 `General Comments` 作小节标签（非 Major/Minor），映射为 Level 2 节点 `General`，并按 minor 严重度配背景色。
  - 无显式 Major/Minor 标签时按内容推断严重度；歧义时默认 `Minor`。
- 叶节点用**背景色**表示严重度（不靠 TOC 符号标记）：
  - major：背景 `#FEE2E2`（浅红），左边框 `3px solid #DC2626`
  - minor：背景 `#FEF3C7`（浅琥珀），左边框 `3px solid #D97706`
  - general：同 minor（浅琥珀）

### 交互
- TOC 支持层级折叠/展开：`Reviewer #N` 与 `Major/Minor` 两级均可折叠；折叠一个 reviewer 便于聚焦另一个。
- 两栏布局支持可拖拽分割：左 TOC / 右内容之间有可拖动分隔条，可拖拽调整 TOC 宽度；宽度偏好用 `localStorage` 持久化；窄屏/移动端隐藏分隔条、回退单列。
- 所有复制按钮中文标签 `复制`。

### 每个叶页的 box 布局（脚本生成）
1. 审稿人意图块：原始意见(EN) + 中文直译 + 中文意图理解；不含英文释义。
2. Response 块：中文在上、英文在下；各带 `复制`。
3. 修改候选块：Quick Location（section/段落 index/Word 检索句）；atomic 定位字段（`manuscript_unit_id`/`si_unit_id`/相对路径/段落与句子 index）默认 `details/summary` 折叠；Original Text 聚焦片段默认折叠；revised EN + 中文译文各带 `复制`；无修改写 `无`；不渲染独立 `Tracked Edit` 或 Section 3 内的独立 `修改说明` 卡。
4. 修改说明块：单一合并卡，子项 A=动作列表（添加/删除/修改+原因），子项 B=`🔴 Core`/`🟡 Support` 汇总。
5. 证据区：文本/图/表；无图修改则不渲染图片占位；有图修改先渲染显式图片占位块。

## Frontend Design Spec（由脚本硬编码，AI 无需手写）
- Color palette: primary `#0F4C81` (deep blue), core marker `#B42318` (red), support marker `#B54708` (amber), background `#F4F7FB`, panel `#FFFFFF`, border `#D9E2EC`
- Typography: `"Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif`; body 14px/1.6; headings bold; code/path `monospace`
- Card spacing: `padding: 14px 16px`, `border-radius: 10px`, `margin-bottom: 12px`
- Responsive breakpoint: ≤980px switch to single-column, sidebar becomes top nav
