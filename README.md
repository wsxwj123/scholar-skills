# scholar-skills

中文科研写作的 AI 技能包：9 个写作技能 + 1 个流程门禁插件。装进 Claude Code（Codex / OpenCode 也能装技能），说人话就开工，不用记命令。

## 简介

| 目录 | 用途 |
|---|---|
| `general-sci-writing` | 从零写 SCI 研究论文 |
| `review-writing` | 写文献综述 |
| `nsfc-proposal` | 国自然申请书（2026 模板）；给它模板文件也能写省基金 / 校级 / 博士后等结构不同的本子 |
| `sci2doc` | SCI 论文转中文学位论文 |
| `revise-sci` | 按审稿意见改稿，出回复信 + 修订稿 |
| `reviewer-response-sci` | 只写审稿回复，不动主稿 |
| `reviewer-simulator` | 模拟审稿人挑刺 |
| `polish-sci` | 纯语言润色，不改数据结论 |
| `idea-bomb` | 课题构思与实验设计 |
| `academic-gate` | 流程门禁插件，见下 |

**怎么触发**：技能靠自身描述自动匹配，直接说"帮我写 SCI 论文""改一下这份审稿意见回复"就会进对应技能。每家可以单独装，装一家就只拿一家。

**它和直接问 AI 的区别**：这些技能把写作拆成固定阶段，每个阶段有脚本化的检查闸口，没过就不让进下一步。查的东西包括引文真实性与撤稿状态、图表交叉引用、占位符残留、字数与页数、去 AI 腔、结构完整性等。写完一节要送独立盲检，判不过就得改。

**门禁插件**：`academic-gate` 在会话开始、每次提问、每次写文件时注入当前项目的状态卡，并拦下没走完流程的写入，防的是 AI 在长文档里跳步。它拦得住忘，拦不住铁了心要绕（shell 那条路堵不完），绕过会在审计日志里留痕。Claude Code 和 Codex 上生效（Codex 装完要跑一次 `/hooks` 逐条信任），OpenCode 那端只有技能。想关掉或锁更死见「卸载」末尾两节。

各技能的用法、参数、已知限制看它自己目录下的 `SKILL.md`，变更记录看 `CHANGELOG.md`。

## 安装

需要 Claude Code、Python 3.7+、git。可选 pandoc（导出 docx）、edirect（PubMed 检索，技能会在需要时提示装法）。

### macOS / Linux / Git Bash

装 Claude Code 一端：

```bash
git clone https://github.com/wsxwj123/scholar-skills.git /tmp/scholar-skills && mkdir -p ~/.claude/skills && for d in /tmp/scholar-skills/*/; do cp -R "${d%/}" ~/.claude/skills/; done && rm -rf /tmp/scholar-skills && echo "装好了，现在重启 Claude Code"
```

三端一起装（多装的两端只有技能，没有门禁）：

```bash
git clone https://github.com/wsxwj123/scholar-skills.git /tmp/scholar-skills && for t in ~/.claude/skills ~/.codex/skills ~/.config/opencode/skills; do mkdir -p "$t"; for d in /tmp/scholar-skills/*/; do cp -R "${d%/}" "$t"/; done; done && rm -rf /tmp/scholar-skills && echo "三端装好了，现在重启 Claude Code"
```

### Windows PowerShell

```powershell
git clone https://github.com/wsxwj123/scholar-skills.git $env:TEMP\scholar-skills
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills"
Get-ChildItem "$env:TEMP\scholar-skills" -Directory -Force |
  Where-Object { $_.Name -ne '.git' } |
  ForEach-Object { Copy-Item -Recurse -Force $_.FullName "$env:USERPROFILE\.claude\skills\" }
Remove-Item -Recurse -Force "$env:TEMP\scholar-skills"
```

只拷子目录，不把仓库根的 README 之类扫进技能目录。Windows 上还得装 [Git for Windows](https://git-scm.com/downloads/win)，否则钩子跑不起来。

### 懒得敲命令：把下面这段丢给你的 AI

```
帮我装 https://github.com/wsxwj123/scholar-skills 这个技能包。

要求：
1. clone 到临时目录，把仓库根下的每个子目录（general-sci-writing、review-writing、
   nsfc-proposal、sci2doc、revise-sci、reviewer-response-sci、reviewer-simulator、
   polish-sci、idea-bomb、academic-gate，共 10 个）整个拷进我这台机器的全局技能目录。
   我用哪些客户端你先问我，对应目录是：
     Claude Code  → ~/.claude/skills/
     Codex        → ~/.codex/skills/
     OpenCode     → ~/.config/opencode/skills/
2. 一个都别漏，尤其 academic-gate，它是流程门禁插件，漏了就只有技能没有拦截。
3. 装完删掉临时目录，然后告诉我：
   - 要重启一次客户端才生效（钩子在启动时加载，不重启等于没装，而且不会报错）
   - 重启后怎么验证（跑 claude plugin list 看有没有 academic-gate@skills-dir）
4. 别改我的 ~/.claude/settings.json，也别改任何已有配置。这个包不需要改配置。
5. 如果我的机器上已经装过旧版，直接覆盖即可，不用备份（内容都在 GitHub 上）。
```

**更新到最新版**：重跑上面任一条安装命令即可，直接覆盖，不用先卸载。

### 装完必须重启一次客户端

钩子在启动时加载，不重启等于没装，且不会报错。

### 验证装上了

```bash
claude plugin list
```

输出里应出现 `academic-gate@skills-dir`。再在项目目录里开个会话，问 AI 一句"当前项目状态卡说了什么"。状态卡开头会打出门禁版本号（形如 `academic-gate v0.9.1`），据此可判断装的是不是最新版。

**钩子起不来时的表现和没装完全一样，不报错、不提示。** 唯一判别法就是上面这两条，看不到就当没保护。

### 装不上的三个常见原因

**没重启，或目录放错了。** 必须在 `~/.claude/skills/` 下，不是 `~/.claude/plugins/`。

**Windows 上 `python3` 可能是空壳。** Windows 自带一个 0 字节的 `python3` 占位程序，装了真 Python 也可能还排在 PATH 前面。`python3 --version` 没有正常输出，就去 设置 → 应用 → 应用执行别名 关掉 `python3.exe`。另外钩子命令是 POSIX 写法，纯 cmd / PowerShell 起不来，装 Git for Windows 一般能解决。

**解释器名不一致。** 文档示例统一写 `python3`，但 Windows 上常常只有 `python`（干净的 macOS 又只有 `python3`）。各技能已写明 AI 执行脚本前先探测一次；若 AI 照抄命令报 `python3: command not found`，告诉它"这台机器只有 python"即可。

### 它会往哪写文件

技能会在**项目目录**里建稿件、状态文件、git 检查点，这是它的工作。

门禁插件不写你的稿子。它在确认是学术项目的目录里写 `.academic_gate_audit.jsonl`，并在该目录已有 `.gitignore` 时追加一行；不是学术项目的目录不写。门禁插件不碰 `~/.claude/settings.json`（例外见卸载一节）。

## 卸载

删目录就行：

```bash
cd ~/.claude/skills && rm -rf general-sci-writing review-writing nsfc-proposal sci2doc \
  revise-sci reviewer-response-sci reviewer-simulator polish-sci idea-bomb academic-gate
```

钩子定义住在 `academic-gate/hooks/hooks.json` 里，目录没了钩子跟着没，`settings.json` 里不留任何东西。重启一次生效。

### ⚠️ 别只删 academic-gate

**只删门禁目录、留着技能，会让门禁改走旧路径，反而写进你的 `settings.json`。**

每家技能开工时都会自检一次门禁：发现插件不在，就判定这台机器还没保护，于是把门禁脚本复制到 skills 之外的一个固定位置（故意不随技能目录增删），再往 `settings.json` 的 `PreToolUse` 追加一条。

这条自装路径只动它自己的东西（只认命令里含 `academic_gate_hook.py` 的条目），你的 `env` / `model` / `permissions` / `statusLine` / 你自己的钩子全部原样保留，改之前还会存一份 `settings.json.bak-gatehook`。但它没有反向的卸载动作，删技能不会把它清掉。真踩了的话手动清两处：

```bash
rm -rf ~/.claude/academic-gate
```

再打开 `~/.claude/settings.json`，把 `hooks.PreToolUse` 里那个命令含 `academic_gate_hook.py` 的对象删掉。残留本身无害（它只在识别出学术项目时才管事），只是每次写文件会被白调起来一次。

### 不想删，只想关拦截

新建 `~/.claude/academic-gate.local.json`，内容：

```json
{ "enforcement_enabled": false, "note": "我自己盯流程" }
```

拦截停了，状态卡提醒和技能自己的流程脚本照常。恢复就删掉这个文件，或把值改成 `true`。

只有 JSON 的 `false` 才算关。文件不存在、JSON 坏了、值写成字符串 `"false"`、读不出来，一律按"保护开着"处理，坏文件不会静默把保护关掉。当前是开是关，跑一次任一技能的开局脚本就会打印出来。

这个文件在写保护清单里，AI 用写文件工具改不动：你关了它不会被 AI 打开，你开着它也不会被 AI 关掉。

### 反过来：想锁得更死

门禁自己的文件 AI 用写文件工具改不动，但 shell 那条路堵不完。两个不依赖这层黑名单的办法：

```bash
touch ~/.claude/academic-gate.local.json && chmod 444 ~/.claude/academic-gate.local.json
```

文件里留一个 `{}` 就行，保护照常开着，同时这个文件谁也写不进去。

另一个是用 Claude Code 自带的 `permissions.deny`，按路径禁掉对门禁目录和这个开关文件的 `Write` / `Edit` / `Bash`。怎么配看官方文档，我们不替你改 `settings.json`。

### codex / opencode

那两端从来不读 Claude Code 的钩子配置，本来就没挂钩子，删目录就是删干净了：

```bash
# 把 <目录> 换成上面那串同样的名字
cd ~/.codex/skills            && rm -rf <目录>...   # codex
cd ~/.config/opencode/skills  && rm -rf <目录>...   # opencode
```

## 反馈

误拦、漏拦、状态卡内容不对、装不上，都欢迎开 issue。误拦优先修。

有 2600 多条自动化测试覆盖行为契约，但测试证不了"用起来真的治忘、真的不烦"，这部分待实测。

## 授权

个人研究使用。内容基于公开学术写作规范整理，不含期刊或基金委的受版权保护材料。
