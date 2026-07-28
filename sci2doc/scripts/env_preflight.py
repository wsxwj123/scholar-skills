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
    _install_gate_hook()

    for tool, h in missing:
        print(f"⚠️ 缺 {tool} — 安装: {h}")
    if missing:
        print("PRECHECK: ASK " + ",".join(t for t, _ in missing))
    else:
        print("PRECHECK: OK")
    return 0


def _install_gate_hook() -> None:
    """调共享安装器 install_gate_hook.py 装物理门禁 hook，回显其人话消息，
    并打印结构签字 / 接续 / 引文核证三条命令。

    双轨定位（故意不同，勿顺手统一）：
    - 纯库脚本（structure_signoff_gate / session_journal / citation_claim_check）
      已 vendored 进本技能 scripts/，就地取用 `Path(__file__).resolve().parent`，
      不依赖 _shared。
    - installer（install_gate_hook.py）= 同目录 vendored 副本优先，会把门禁四件套部署到
      ~/.claude/academic-gate/（稳定位置，不随技能目录增删而动），settings.json 的 hook 指向那里；
      _shared 仅完整仓库回退。所以下面两个 base 不一样，这是有意为之。
    任何异常都吞掉——门禁自检绝不能反过来卡住技能。"""
    import json as _json
    import subprocess as _sp
    try:
        scripts_dir = Path(__file__).resolve().parent
        installer = scripts_dir / "install_gate_hook.py"     # vendored 副本(单技能分发也在)
        if not installer.is_file():
            installer = scripts_dir.parents[1] / "_shared" / "install_gate_hook.py"  # 完整仓库回退
        if installer.is_file():
            proc = _sp.run([sys.executable or "python", str(installer)],
                           capture_output=True, text=True, timeout=30)
            line = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout.strip() else ""
            res = _json.loads(line) if line else {}
            status, msg = res.get("status", ""), res.get("message", "")
            icon = {"active": "🛡️", "installed": "🛡️", "degraded": "⚠️", "error": "ℹ️"}.get(status, "ℹ️")
            if msg:
                print(f"{icon} 门禁保护[{status}]: {msg}")
        else:
            # installer 缺失 → 物理门禁装不上，降级为提示词纪律。
            print("⚠️ 门禁保护[degraded]: 缺 install_gate_hook.py（scripts/ 与 _shared/ 均无），物理拦截不可用，降级为提示词纪律。")
            print("   签字仅留痕、无强制拦截，需人工守住「未签字不写正文」。")
            print("   修复：重装完整技能仓库，或补回 _shared/install_gate_hook.py。")
        # 以下三条命令均指本地 vendored 副本，不依赖 _shared，故 installer 缺失时照常打印。
        signoff = scripts_dir / "structure_signoff_gate.py"
        if signoff.is_file():
            print(f'SIGNOFF_CMD: python "{signoff}" confirm --root <project_root> --note "<用户确认原话>"')
        else:
            print('⚠️ 缺 scripts/structure_signoff_gate.py(vendored 副本)——跑 python3 _shared/sync_vendored.py --sync 或重装完整技能包')
        journal = scripts_dir / "session_journal.py"
        if journal.is_file():
            print(f'RESUME_CMD: python "{journal}" resume --root <project_root>')
        else:
            print('⚠️ 缺 scripts/session_journal.py(vendored 副本)——跑 python3 _shared/sync_vendored.py --sync 或重装完整技能包')
        citecheck = scripts_dir / "citation_claim_check.py"
        if citecheck.is_file():
            print(f'CITATION_CHECK_CMD: python "{citecheck}" --root <project_root> --evidence <project_root>/claim_evidence.json')
        else:
            print('⚠️ 缺 scripts/citation_claim_check.py(vendored 副本)——跑 python3 _shared/sync_vendored.py --sync 或重装完整技能包')
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
