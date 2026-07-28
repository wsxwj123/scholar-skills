#!/usr/bin/env python3
"""统一开工前环境预检（全部学术技能共用，字节一致分发）。

软门禁语义：检测 OS / Python / git（+ 技能可选工具），写 <root>/env_status.json，
末行打印机器可读状态 `PRECHECK: OK | ASK | BLOCKED`。
- 必需缺失（Python 过低）          -> BLOCKED，exit 1，引导升级。
- 可选缺失（git / 技能传入的工具） -> ASK，  exit 0，列出缺项 + 安装指引（由 SKILL 逐项问用户）。
- 全齐                              -> OK，   exit 0。

用法:
  python3 env_preflight.py [root]                      # 仅 Python+git
  python3 env_preflight.py [root] --cli esearch,blastn # 额外检 CLI（shutil.which）
  python3 env_preflight.py [root] --py pyzotero,docx   # 额外检 Python 模块（可导入）
"""
import sys as _sys
try:  # Windows GBK 控制台/管道捕获下 emoji print 防 UnicodeEncodeError
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import sys
import json
import shutil
import platform
import importlib.util
from pathlib import Path

MIN_PY = (3, 7)

INSTALL_HINT = {
    "git": {"Darwin": "brew install git", "Linux": "sudo apt install git", "Windows": "winget install Git.Git"},
    "esearch": {"_": 'sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"（Windows 需 WSL）'},
    "pyzotero": {"_": "pip install pyzotero"},
    "docx": {"_": "pip install python-docx"},
}


def hint(tool: str, osname: str) -> str:
    h = INSTALL_HINT.get(tool, {})
    return h.get(osname) or h.get("_") or f"自行安装 {tool}"


def parse_list(flag: str, argv) -> list:
    if flag in argv:
        raw = argv[argv.index(flag) + 1]
        return [x.strip() for x in raw.split(",") if x.strip()]
    return []


def main():
    argv = sys.argv[1:]
    root = Path(argv[0]).expanduser() if argv and not argv[0].startswith("--") else Path.cwd()
    cli_tools = parse_list("--cli", argv)
    py_mods = parse_list("--py", argv)

    ver = sys.version_info
    osname = platform.system()
    git_available = shutil.which("git") is not None

    missing = []  # (tool, hint)
    if not git_available:
        missing.append(("git", hint("git", osname)))
    for t in cli_tools:
        if shutil.which(t) is None:
            missing.append((t, hint(t, osname)))
    for m in py_mods:
        if importlib.util.find_spec(m) is None:
            missing.append((m, hint(m, osname)))

    root.mkdir(parents=True, exist_ok=True)
    (root / "env_status.json").write_text(
        json.dumps(
            {
                "os": osname,
                "python": f"{ver.major}.{ver.minor}.{ver.micro}",
                "git_available": git_available,
                "missing_optional": [t for t, _ in missing],
            },
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )

    print(f"OS: {osname} | Python {ver.major}.{ver.minor}.{ver.micro}")
    if ver < MIN_PY:
        print(f"❌ 需要 Python {MIN_PY[0]}.{MIN_PY[1]}+ — 升级: python.org / brew install python / winget install Python.Python.3")
        print("PRECHECK: BLOCKED")
        return 1
    print("✅ Python OK")

    # 强制门禁 hook 自动安装 + 心跳探测（共享，跨全部学术技能）。零手动步骤：
    # 未装→自动装(备份/校验/回滚)并提示重启一次;装了没心跳→环境不透传,提示人工盯防。
    # polish-sci 本就逐段停给用户核对,不需要签字闸,故不打印 SIGNOFF_CMD。
    _install_gate_hook()

    for tool, h in missing:
        print(f"⚠️ 缺 {tool} — 安装: {h}")
    if missing:
        print("PRECHECK: ASK " + ",".join(t for t, _ in missing))
    else:
        print("PRECHECK: OK")
    return 0


def _install_gate_hook() -> None:
    """双轨:接续库 session_journal.py 已 vendored 进本技能 scripts/(与本文件同目录),
    纯本地引用、不依赖 _shared;门禁安装器 install_gate_hook.py=同目录 vendored 副本优先,
    部署四件套到 ~/.claude/academic-gate/,_shared 仅完整仓库回退。
    调安装器回显其人话消息,随后照 SIGNOFF_CMD 样式打印 RESUME_CMD/LOG_CMD(绝对路径,
    免相对路径 cwd 依赖)。polish-sci 无签字闸(逐段停即核对),故不打印 SIGNOFF_CMD。
    任何异常都吞掉——门禁自检绝不能反过来卡住技能。"""
    import json as _json
    import subprocess as _sp
    try:
        here = Path(__file__).resolve().parent
        installer = here / "install_gate_hook.py"          # vendored 副本(单技能分发也在)
        if not installer.is_file():
            installer = here.parents[1] / "_shared" / "install_gate_hook.py"  # 完整仓库回退
        if not installer.is_file():
            print("⚠️ 未找到 install_gate_hook.py(scripts/ 与 _shared/ 均无):物理门禁 hook 无法安装,产物保护降级为提示词纪律。"
                  "修复:安装完整技能仓库(含 skills/_shared/)或手动补齐。")
        else:
            proc = _sp.run([sys.executable or "python", str(installer)],
                           capture_output=True, text=True, timeout=30)
            line = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout.strip() else ""
            res = _json.loads(line) if line else {}
            status, msg = res.get("status", ""), res.get("message", "")
            icon = {"active": "🛡️", "installed": "🛡️", "degraded": "⚠️", "error": "ℹ️"}.get(status, "ℹ️")
            if msg:
                print(f"{icon} 门禁保护[{status}]: {msg}")
        # 跨会话接续:vendored 副本就在本文件同目录,纯本地引用。polish-sci 无签字闸,
        # 只出接续 + 决定日志两条。
        journal = Path(__file__).resolve().parent / "session_journal.py"
        if journal.is_file():
            print(f'RESUME_CMD: python "{journal}" resume --root <project_root>')
            print(f'LOG_CMD: python "{journal}" log --root <project_root> --note "<用户临时要求原话>"')
        else:
            print("⚠️ 缺少 scripts/session_journal.py(vendored 副本):跨会话接续不可用。"
                  "修复:跑 python3 _shared/sync_vendored.py --sync 或重装完整技能包。")
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
