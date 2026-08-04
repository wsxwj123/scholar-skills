# General SCI Writing Skill - Test Checklist

> 版本号只写在 `SKILL.md` frontmatter 的 `version:` 一处，本文件不再另写。

## Scope
本文件是**行为契约清单**：改 `scripts/` 下任何脚本的人，要保证下面这些行为不倒退。
它不是"测试报告"——**技能不随包分发测试**，装到用户机上没有任何可跑的测试套件。

## 自动化覆盖在哪
- **本机开发自测**：`scripts/test_*.py`（被 `.gitignore` 排除、不进分发包）。
  跑法：`cd scripts && for f in test_*.py; do python3 "$f" >/dev/null 2>&1 && echo "PASS $f" || echo "FAIL $f"; done`
- **门禁契约与验收考卷**：在技能仓之外的 `skills-testkit/` 与 `tests/acceptance/`，
  同样不随包分发。
- **装完能自查的只有语法编译**：
  ```bash
  python3 -m py_compile scripts/citation_guard.py scripts/state_manager.py
  ```

## 行为契约（改脚本前先看，改完逐条对）

### 硬门禁 / 写作周期
- 手工 `preflight + load` 不足以打开 `prewrite` 阶段的硬门禁
- `write-cycle` 能建立合法的 prewrite gate；默认走 strict 预检
- `write-cycle --finalize` 在 sync apply 成功时能闭合 gate
- `postwrite` 在没跑过 write-cycle 时必须 `sys.exit(2)`（识图阶段请用 `snapshot`）

### 引用同步
- `sync-literature --dry-run` 产出预览与报告文件
- `sync-literature --apply` 重写正文引用号并严格重建 References 段
- 区间引用 `[1-4]` 与表格内引用 `| Ref | [3] |` 都被正确重映射
- 存在 dedup 冲突时默认阻断 apply；`--allow-conflicts` 才显式放行
- 校验失败时 rollback 能恢复到上一状态
- `--backup-keep` 的备份保留策略生效
- 参考文献样式 `nature` 渲染成预期形态

### 文献核验（citation_guard）
- 非白名单 provider family 被拒
- 任何 `source_provider=tavily` 条目被拒（带不带 DOI/PMID 都一样）
- tavily 反向核验后端（标题交叉比对）仍可用
- 双向核验失败强制 `verified=false` 并要求人工确认
- `citation_guard_report.json` 暴露 provider policy
- **绝不因为加了 `--offline` 就给未核验条目发证**

### 加载与产物隔离
- 章节局部加载走缓存并按预算裁剪；源文件变更后缓存失效
- 运行时产物隔离在 `.state/` 与 `backups/` 下（清单见 `RUNTIME_LAYOUT.md`）
- 报告/缓存有保留上限，不无限增长

### 配置
- `set-field` 持久化当前研究方向配置与 reviewer concerns
- `config_manager.py` 的子命令只认 `--field` / `--name`，位置参数写法必须 exit 2
