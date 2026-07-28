# scholar-skills

中文科研写作的 Claude Code 技能包。9 个技能 + 1 个流程门禁插件。

## 简介

技能覆盖：写 SCI 论文、写综述、写国自然本子、SCI 转学位论文、返修改稿、写审稿回复、模拟审稿、纯润色、想课题。

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
| `academic-gate` | 流程门禁插件，见下 |

技能靠 frontmatter 的 description 自动触发，不用记命令。说"帮我写 SCI 论文"就进 general-sci-writing。每家可以单独装，装一家就只拿一家。

### 门禁插件在干什么

长文档写作里 AI 跳步有两个成因，都不是模型能力问题。一是注意力衰减，SKILL.md 动辄一两万 token，写到第 5 节时第 2 节定的规矩已经很淡。二是上下文压缩会截断文档——Claude Code 压缩时每个技能只保留 SKILL.md 的前 5000 token，写在后半篇的纪律条款压缩后物理上不存在了。

`academic-gate` 是个普通目录，里面有 `.claude-plugin/plugin.json`，放进 `~/.claude/skills/` 重启一次自动加载，不用手改配置。5 个 handler，3 个脚本：

| 事件 | matcher | 行为 |
|---|---|---|
| SessionStart | startup\|clear\|compact\|resume\|fork | 注入全景状态卡 |
| UserPromptSubmit | 全部 | 有待办才注入短卡，全绿静默 |
| PostToolUse | Write\|Edit\|MultiEdit\|NotebookEdit | 写完某节提示送检 |
| PreToolUse | Write\|Edit\|MultiEdit\|NotebookEdit | deny / ask / allow |
| PreToolUse | Bash | 拦 shell 绕过 |

判定逻辑只有一份（`context_guard_core.py`），三个钩子共用，避免状态卡说 A、门禁判 B。

**这不是防绕过的锁。** 拦得住忘，拦不住铁了心要绕（shell 里写文件的形态无穷，黑名单原理上不完备）。绕过会在审计日志里留痕。

**只在 Claude Code 上生效。** codex 有几乎同构的 hooks，但它的 `tool_input` 里没有 `file_path`（在 apply_patch 补丁文本里），我们的钩子会一律读到空然后放行——**门禁静默失效但不报错**，所以没往那边挂。opencode 走 in-process JS 插件，需要另写桥接层。**在这两端只有技能，没有门禁。**

## 安装

必需 Claude Code、Python 3.7+、git。可选 pandoc（导出 docx）、edirect（PubMed 检索，技能会在需要时提示装法）。

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

**然后重启 Claude Code。** 钩子在启动时加载，不重启等于没装，且不会报错。

更新就是 `git pull` 之后重跑上面那条 `cp`，再重启一次。

### 验证装上了

```bash
claude plugin list          # 应出现 academic-gate@skills-dir
```

再在项目目录里开个会话，AI 那边会收到一张状态卡（你在对话里通常看不见，问它一句"当前项目状态卡说了什么"就知道）。

**钩子起不来时的表现和没装完全一样，不报错、不提示。** 唯一判别法就是上面这两条。看不到就当没保护，按流程人工盯。

### 装不上的两个常见原因

**没重启，或目录放错了。** 必须在 `~/.claude/skills/` 下，不是 `~/.claude/plugins/`。

**Windows 上 `python3` 可能是空壳。** Windows 自带一个 0 字节的 `python3` 占位程序，装了真 Python 也可能还排在 PATH 前面。`python3 --version` 没有正常输出就去 设置 → 应用 → 应用执行别名 关掉 `python3.exe`。另外钩子命令是 POSIX 写法（`exec "$(command -v python3 || command -v python)"`），纯 cmd/PowerShell 起不来，装 Git for Windows 一般能解决。

### 它会往哪写文件

技能会在**项目目录**里建稿件、状态文件、git 检查点，这是它的工作。

门禁插件不写你的稿子。它在确认是学术项目的目录里写 `.academic_gate_audit.jsonl`，并在该目录已有 `.gitignore` 时追加一行。不是学术项目的目录不写。

门禁插件**不碰 `~/.claude/settings.json`**（见下一节的例外）。

## 卸载

删目录就行：

```bash
cd ~/.claude/skills && rm -rf general-sci-writing review-writing nsfc-proposal sci2doc \
  revise-sci reviewer-response-sci reviewer-simulator polish-sci idea-bomb academic-gate
```

钩子定义住在 `academic-gate/hooks/hooks.json` 里，目录没了钩子跟着没，`settings.json` 里不留任何东西。重启一次生效。

### ⚠️ 别只删 academic-gate

**只删门禁目录、留着技能，会让门禁改走旧路径，反而写进你的 `settings.json`。**

因为每家技能开工时都会自检一次门禁：发现插件不在，就判定这台机器还没保护，于是把门禁脚本复制到 `~/.claude/academic-gate/`（这个位置在 skills 之外，故意不随技能目录增删），再往 `settings.json` 的 `PreToolUse` 追加一条。

这条自装路径只动它自己的东西——只认命令里含 `academic_gate_hook.py` 的条目，你的 `env` / `model` / `permissions` / `statusLine` / 你自己的钩子全部原样保留，改之前还会存一份 `settings.json.bak-gatehook`。但它**没有反向的卸载动作**，删技能不会把它清掉。

真踩了的话手动清两处：

```bash
rm -rf ~/.claude/academic-gate
```

再打开 `~/.claude/settings.json`，把 `hooks.PreToolUse` 里那个命令含 `academic_gate_hook.py` 的对象删掉。

残留本身无害（它只在识别出学术项目时才管事，别的目录一律放行），只是每次写文件会被白调起来一次。

### codex / opencode

那两端从来不读 Claude Code 的钩子配置，本来就没挂钩子，删目录就是删干净了：

```bash
# 把 <目录> 换成上面那串同样的名字
cd ~/.codex/skills            && rm -rf <目录>...   # codex
cd ~/.config/opencode/skills  && rm -rf <目录>...   # opencode
```

## 反馈

误拦、漏拦、状态卡内容不对、装不上，都欢迎开 issue。误拦优先修。

有 1099 条自动化测试覆盖行为契约，但测试证不了"用起来真的治忘、真的不烦"，这部分待实测。

## 授权

个人研究使用。内容基于公开学术写作规范整理，不含期刊或基金委的受版权保护材料。
