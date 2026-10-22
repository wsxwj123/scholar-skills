> 本文件由 SKILL.md 拆分而来，仅在主文件指示时读取。

# 第七步：产出前硬门禁校验（三个脚本 + 硬门禁 6 条 + 软门禁）

在输出最终HTML前,必须执行以下校验命令并确保通过。**脚本位于技能安装目录（≠用户 CWD），须用其绝对路径 `$SKILL_DIR/scripts/...` 调用**（`$SKILL_DIR` 解析见文首【技能安装目录解析】）：
`python "$SKILL_DIR/scripts/validate_report_html.py" <生成后的报告HTML路径>`

紧接着对同一 HTML 跑审稿意见去AI脚本（B7 兜底，剥离 head/script/style/footer 后抽正文文本喂 humanizer）：
`python "$SKILL_DIR/scripts/scan_report_humanize.py" <生成后的报告HTML路径>`

再对同一 HTML 跑字符级软体检（B10 软项，抽正文喂 proofread，只报告不阻断）：
`python "$SKILL_DIR/scripts/proofread_report.py" <生成后的报告HTML路径>`

硬门禁:
1. 若存在未替换占位符(如`{{...}}`),必须终止交付并返工。
2. 头部`VERDICT_TEXT`与第十部分`FINAL_RECOMMENDATION`必须一致且只能为"拒稿/大修/小修/接收"之一。
3. `scan_report_humanize.py` 硬阻断项（severity=ERROR，exit 1）：**禁套话主干**（humanizer BANNED 模板句/套话/修辞，如"综上所述""革命性的""值得注意的是"）+ **去AI必禁三项 装饰破折号（—/——）/ scare quotes / 解释性冒号（均禁止使用，硬门禁）**。命中即 `HUMANIZE_FAILED`，须改写正文后重跑，未过不得交付。**HTML 结构引号豁免（scare quotes 只管正文散文）**：本报告以 HTML 输出，其中 HTML 标签/属性/内联样式/代码里的结构性双引号（如 `id="sec-1"`、`class="panel panel-audit"`、`<a href="...">`）是**代码语法、不是 scare quotes**，一律不得删除、改写、转全角或转弯引号——动了破坏 HTML 渲染；去 scare quotes 只针对散文里包裹词/短语的引号，绝不触碰 markup 与代码。**超50字中文长句仍为软提示（WARNING，不阻断）**，脚本会列出但不影响退出码，供人工酌情修润。脚本无法判定的"从句≤2层"由 B7 盲检人工酌情核。
4. 仅当上述校验全部通过才允许提交最终报告。
5. 若 `$SKILL_DIR/scripts/validate_report_html.py` 或 `scan_report_humanize.py` 路径不存在或执行报错，必须在报告头部注明"[自动校验不可用，已人工核查占位符与VERDICT一致性及去AI三禁]"，并逐项人工确认上述门禁，不得静默跳过。
6. 若校验未通过：不得自行静默修改报告后重新提交，必须向用户说明具体失败原因和位置，列出需要人工确认的条目，等待用户指令后再决定返工或带注释交付。

软门禁（B10，只报告不阻断）:
- `proofread_report.py` 抽报告正文喂 `proofread.py`（不传 `--fail-on`），列出拼写错误/中文标点漏进英文/上下标裸写等字符级瑕疵。**这是软项：脚本恒 exit 0，有无 issue 都不阻断交付**；发现的问题仅供人工参考修润，不作返工强制。

