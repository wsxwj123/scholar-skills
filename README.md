# scholar-skills

中文科研写作的 Claude Code 技能包。9 个技能 + 1 个流程门禁插件。

技能覆盖：写 SCI 论文、写综述、写国自然本子、SCI 转学位论文、返修改稿、写审稿回复、模拟审稿、纯润色、想课题。

门禁插件干两件事：在关键节点拦住 AI 跳步；每轮把项目当前状态重新注入上下文。

## 动机

长文档写作里 AI 跳步的两个成因，都不是模型能力问题。

一是注意力衰减。SKILL.md 动辄一两万 token，写到第 5 节时第 2 节定的规矩在注意力里已经很淡。

二是上下文压缩会截断文档。Claude Code 压缩上下文时，每个技能只保留 SKILL.md 的前 5000 token，后面直接丢。如果纪律条款写在后半篇，压缩后它物理上不存在了。这条是查官方文档时发现的，之前一直以为是模型不听话。

对应三个做法：

- 喂：SessionStart / UserPromptSubmit / PostToolUse 三个时机注入状态卡，压缩那一刻优先。
- 拦：PreToolUse 拦 Write/Edit 和 Bash，卡住未签字写正文、伪造签字、上一节未过盲检就开下一节。
- 减：SKILL.md 重排 + 细则下沉 references/，把执法内容压进 5000 token 线内。polish-sci 从 10918 降到 5939。

## 内容

### 技能

| 目录 | 用途 |
|---|---|
| `general-sci-writing` | 从零写 SCI 研究论文 |
| `review-writing` | 写文献综述 |
| `nsfc-proposal` | 国自然申请书（2026 模板） |
| `sci2doc` | SCI 论文转中文学位论文 |
| `revise-sci` | 按审稿意见改稿，出回复信 + 修订稿 |
| `reviewer-response-sci` | 只写审稿回复，不动主稿 |
| `reviewer-simulator` | 模拟审稿人挑刺 |
| `polish-sci` | 纯语言润色，不改数据结论 |
| `idea-bomb` | 课题构思与实验设计 |

靠 frontmatter 的 description 自动触发，不需要记命令。说"帮我写 SCI 论文"就进 general-sci-writing。

### 门禁插件

`academic-gate`。目录里带 `.claude-plugin/plugin.json`，放进 `~/.claude/skills/` 重启一次，Claude Code 自动加载 `hooks/hooks.json`，不需要手工改 settings.json。

5 个 handler，3 个脚本：

| 事件 | matcher | 脚本 | 行为 |
|---|---|---|---|
| SessionStart | startup\|clear\|compact\|resume\|fork | `context_feed_hook.py` | 注入全景状态卡 |
| UserPromptSubmit | 全部 | 同上 | 有待办才注入短卡，全绿静默 |
| PostToolUse | Write\|Edit\|MultiEdit\|NotebookEdit | 同上 | 写完某节提示送检 |
| PreToolUse | Write\|Edit\|MultiEdit\|NotebookEdit | `academic_gate_hook.py` | deny / ask / allow |
| PreToolUse | Bash | `bash_guard_hook.py` | 拦 shell 绕过 |

判定逻辑只有一份（`context_guard_core.py`），三个钩子共用，避免状态卡说 A、门禁判 B。

## 安装

### 依赖

必需：Claude Code、Python 3.7+、git。

可选：pandoc（导出 docx）、edirect（PubMed 检索，技能会在需要时提示装法）。

### 步骤

```bash
git clone https://github.com/wsxwj123/scholar-skills.git
mkdir -p ~/.claude/skills
cp -R scholar-skills/*/ ~/.claude/skills/
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills"
Copy-Item -Recurse "scholar-skills\*" "$env:USERPROFILE\.claude\skills\"
```

然后重启 Claude Code。钩子在启动时加载，不重启等于没装。

验证：

```bash
claude plugin list          # 应出现 academic-gate@skills-dir
```

### opencode / codex

技能目录本身在这两端可用，直接 clone 到对应位置即可：

```bash
cp -R scholar-skills/*/ ~/.codex/skills/            # codex
cp -R scholar-skills/*/ ~/.config/opencode/skills/  # opencode（新版本也读 ~/.claude/skills，可能不必单独放）
```

钩子在这两端不生效。codex 的 hooks 机制与 Claude Code 高度同构（事件名、hooks.json 结构、permissionDecision 都一样），但它的 `tool_input` 里没有 `file_path`（在 apply_patch 补丁文本里），需要约 20 行解析；opencode 走 in-process JS 插件，需要一个约 50 行的桥接层。两个适配都还没做。

在这两端只有技能，没有门禁。

## 用法

在项目根目录起 Claude Code，直接说需求：

```
帮我写一篇 SCI 论文，数据我一会儿给
```

流程大致是：先要素材，再把大纲摆给你确认，你确认后由**你自己**在终端跑签字命令解锁（命令技能会打印），之后逐节写，每节写完过一遍独立盲检才能开下一节。

跑起来会看到两样东西。

状态卡（自动进上下文，你在对话里通常看不到，AI 能看到）：

```
[学术项目状态卡 · academic-gate v0.8.0]
项目根：/Users/you/my-paper
技能：general-sci-writing
已完成：3.1 ✅已检  3.2 ✅已检  3.3 ⚠️写完未检
下一步：python scripts/delegate_review.py verify --section 3.3 --root "/Users/you/my-paper"
```

拦截提示：

```
[学术门禁]「structure_signoff」未通过，本次写入被拦下。
原因：结构签字缺失：大纲/故事线还没有经过用户确认。
```

被拦住说明流程被跳了，按提示补那一步。

## 排障

| 现象 | 原因 | 处置 |
|---|---|---|
| `claude plugin list` 无 `academic-gate@skills-dir` | 没重启，或目录不在 `~/.claude/skills/` 下 | 重启；确认路径 |
| 开局看不到状态卡 | 钩子没跑起来 | 见下面 Windows 两条；检查 `python3 --version` |
| 某技能不拦 | 那家 signoff 本来就是 false（返修/润色/审稿类没有大纲概念） | 正常 |

### Windows 两个坑

**`python3` 可能是空壳。** Windows 自带一个 0 字节的 `python3` 占位程序，装了真 Python 也可能还排在 PATH 前面。`python3 --version` 没有正常输出就去 设置 → 应用 → 应用执行别名 关掉 `python3.exe`。

**钩子命令是 POSIX 写法**（`exec "$(command -v python3 || command -v python)"`），纯 cmd/PowerShell 起不来。装 Git for Windows 一般能解决。

钩子起不来时的表现和没装完全一样，不报错、不提示。唯一判别法是开局看不看得到状态卡。看不到就当没保护，按流程人工盯。

### 文件写入范围

技能会在项目目录里建稿件、状态文件、git 检查点，这是它的工作。

门禁插件不写你的稿子。它在**确认是学术项目**的目录里写 `.academic_gate_audit.jsonl`，并在该目录已有 `.gitignore` 时追加一行。不是学术项目的目录不写。

## 已知局限

**不是防绕过的锁。** 拦得住忘（绝大多数情况），拦不住铁了心要绕。shell 里写文件的形态无穷，我们拦常见的，黑名单原理上不完备。绕过会在审计日志里留痕，事后可查。

**状态卡会重复。** 只要有节写完未送检，每轮都提醒。这是有意的，不是 bug，待办清空后自动安静。

**三端不齐平。** 见上面 opencode/codex 那节。

**"零残留"要说准。** 只是目录名撞上（你有个 `drafts/`）不写任何文件；但 AI 去写 `.review_pass/` 或 `structure_signoff.json` 这两个我们的凭证名时，会在那个目录留一行审计。

**没有真实写作场景的长跑验证。** 有 1022 条自动化测试覆盖行为契约（含误伤矩阵、注入清洗、大小写绕过、越界读、GBK `.gitignore` 字节不变），但测试证不了"用起来真的治忘、真的不烦"。这部分待实测。

## 反馈

误拦、漏拦、状态卡内容不对、装不上，都欢迎开 issue。误拦优先修。

## 授权

个人研究使用。内容基于公开学术写作规范整理，不含期刊或基金委的受版权保护材料。
