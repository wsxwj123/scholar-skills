---
name: academic-gate
description: 学术写作技能的结构签字物理门禁说明。本目录同时是一个 Claude Code 插件——放进 ~/.claude/skills/ 后重启一次，PreToolUse 钩子由 Claude Code 自动加载，拦截"未确认大纲就写正文"。当用户问门禁为什么拦我、怎么解锁、怎么确认结构签字、门禁没生效怎么办时使用。
---

# 学术写作结构签字门禁

## 这是什么

8 家学术写作技能（general-sci-writing / review-writing / nsfc-proposal / sci2doc / revise-sci / reviewer-response-sci / reviewer-simulator / polish-sci）共用的一道**物理门禁**：

> **用户没有明确确认大纲/storyline 之前，任何写入正文文件的操作都会被拦下。**

这不是提示词纪律，是 `PreToolUse` 钩子在工具层拦截——AI 想跳步也跳不过去。

## 🔴 为什么做成插件（本目录的存在理由）

**旧做法**：钩子由技能的 Phase 0 调 `install_gate_hook.py` 安装，写进 `~/.claude/settings.json`。

**旧做法的致命缺陷**：安装这一步**依赖 AI 真的去执行**。而这道门禁的作用恰恰是拦住"AI 想跳步"——**最需要它的场景（AI 跳过流程），恰恰是它不会被装上的场景**。这是循环依赖。

**现做法**：本目录带 `.claude-plugin/plugin.json`，Claude Code 启动时把它当 `academic-gate@skills-dir` 插件加载，**钩子由 Claude Code 自己装，全程不经过 AI**。

## 装法

把本目录放进 `~/.claude/skills/`，**重启一次 Claude Code**。验证：

```bash
claude plugin list        # 应出现 academic-gate@skills-dir
```

⚠️ 钩子在启动时加载，**无法热生效**——放进去当次会话仍然没有保护，重启后才有。

## 被拦住了怎么办

拦截信息形如：

```
[学术门禁]「structure_signoff」未通过：<项目根> 尚未落盘结构签字
```

**这说明流程被跳了，不是 bug。** 正确做法：

1. 回到对应技能的流程，把大纲/storyline 跟用户过一遍
2. **用户明确确认后**（且仅在此之后），运行该技能打印的 `SIGNOFF_CMD` 落盘签字
3. 再继续写正文

🔴 **严禁在用户未确认时自行运行 confirm** —— 那等于伪造用户签字。

## 门禁没生效怎么办

按顺序排查：

| 现象 | 原因 | 处置 |
|---|---|---|
| `claude plugin list` 里没有 `academic-gate@skills-dir` | 没重启，或目录不在 `~/.claude/skills/` 下 | 重启；确认目录位置 |
| 有插件但不拦 | `gate_registry.json` 里该技能 `signoff: false` | 查 registry，这可能是有意的 |
| opencode / codex 里不拦 | **这两端从来就不读 Claude Code 的钩子配置**——门禁在那两端从未生效过 | 已知限制，不是回归 |
| 拦截理由显示两次 | 插件钩子 + 旧的自装钩子并存 | 无害（两条指向同一份逻辑、不会误放行）；跑一次任一技能的 `env_preflight` 会自动摘掉旧的 |
| **Windows 上五个钩子全都不响** | 钩子命令是 POSIX shell 形态（`exec "$(command -v python3 \|\| command -v python)" …`），Windows 原生 cmd/PowerShell 跑不了 | 在 **Git Bash / WSL 等 POSIX shell 环境**里启动 Claude Code。**开局没看到学术项目状态卡 = 钩子没在岗**——这是最快的自检：卡片首行会带 `academic-gate v<版本号>`。<br>🔴 注意此时**拦层也一起哑了**（门禁等于不存在且不会报错），别把"没被拦"当成"检查通过了"。<br>TODO：命令形态改造成跨壳可跑（本轮未做，改动面涉及全部 5 条 handler，需单独验证） |

## 目录内容

```
academic-gate/
├── .claude-plugin/plugin.json   插件声明（name 写死，不靠目录名推导）
├── hooks/hooks.json             5 条 handler：喂 3 个事件 + 拦 Write 类 + 拦 Bash
├── scripts/
│   ├── academic_gate_hook.py    【拦·写文件】PreToolUse(Write|Edit|MultiEdit|NotebookEdit)。
│   │                            判是不是学术项目 → 伪造签字/盲检凭证、未补盲检就写新正文、
│   │                            未结构签字 → deny；认不出项目一律放行（fail-open）
│   ├── bash_guard_hook.py       【拦·Bash】PreToolUse(Bash)。**会 deny 你的 Bash 命令**：
│   │                            AI 代跑 structure_signoff_gate.py confirm、用 shell 绕开
│   │                            脚本直写 structure_signoff.json / .review_pass/、经 shell
│   │                            写未过盲检的受管正文。黑名单、拦常见形态，不完备
│   ├── context_feed_hook.py     【喂】SessionStart / UserPromptSubmit / PostToolUse。
│   │                            **每轮会往 AI 上下文注入一段文本**（项目状态卡：项目根、
│   │                            技能、哪些节声明完成但没盲检、盲检命令）。非学术项目输出空、
│   │                            全绿时也不注入；只读项目文件，不写你的项目目录
│   ├── context_guard_core.py    三个钩子共用的唯一判定实现（分档/差集/清洗/审计）+
│   │                            排障 CLI：python3 context_guard_core.py explain <路径>
│   ├── structure_signoff_gate.py 签字落盘/校验
│   └── gate_registry.json       各技能的受管文件范围与 signoff 开关
└── SKILL.md                     本文件
```

**这个插件会在你机器上写的东西**（只此三处）：`<项目根>/.academic_gate_audit.jsonl`（只记
deny/ask 与"这次没检查成"，同目录已有 `.gitignore` 时追加一行忽略、没有则不创建）、
`${CLAUDE_PLUGIN_DATA}` 下的去重/待报小文件、插件自己目录里的心跳。**不联网、不读密钥。**
陌生目录的边界如实说：撞了通用产物名（如 `drafts/section_*.md`）的目录**零残留**；但写到
我们的凭证名（`.review_pass/` 或 `structure_signoff.json`）时会在那个目录留一行审计。

上面 5 个 `.py` 与 `gate_registry.json` 跟 `_shared/` 逐字节一致，由 `sync_vendored.py` 守卫。**改任一份都要走同步流程**，别单独改这里的副本。
