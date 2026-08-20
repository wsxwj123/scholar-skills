#!/usr/bin/env python3
"""学术门禁 hook 安装器 + 心跳探测。各技能 env_preflight/init_project 调它一次。

Phase B 架构:"N 份安装能力,装出 1 个钩子"。本脚本被 vendored 进每个技能的
scripts/(与 _shared/ 真源同一份代码),运行时做两件事:
  1) 把门禁四件套(signoff_gate/hook/installer/registry)部署到技能目录之外的
     稳定位置 ~/.claude/academic-gate/(带 bundle 版本比较,旧不覆盖新);
  2) 往 ~/.claude/settings.json 的 hooks.PreToolUse 写一条指向 academic-gate
     副本的 hook entry(精确命令比对:旧 _shared 路径的 entry 会被迁移替换,
     重复 entry 收敛为一条;绝不留悬空路径)。
这样 settings.json 永远只指稳定位置,删任何技能目录都不会产生悬空 entry;
钩子文件若丢失,下次任一技能 preflight 会从自带副本重新部署(自愈)。

动手前先确认这台机器真在用 Claude Code(见 _claude_code_evidence):这些技能同时被镜像到
~/.codex/skills 与 ~/.config/opencode/skills,而那两个运行端从不读 ~/.claude/settings.json。
探测不到任何 Claude Code 痕迹就干净跳过,不去凭空创建 ~/.claude/ 塞一堆没人读的文件。
判据只认"我们造不出来的证据",且宁可误判成"装了"——多写一次垃圾可以,关掉真用户的门禁不行。

安全三重保险不变:改 settings.json 前备份(.bak-gatehook)、写前写后 JSON 校验、
失败即从备份回滚。部署四件套按 signoff→hook→installer→registry 顺序复制,
registry(hook 的开关+版本提交点)最后落盘:中途被杀只造成暂时 fail-open 放行,
不会半新半旧误拦。

输出:一行 JSON {status, action, message}。status ∈ installed|active|degraded|error。
参数:--force 同版重刷部署(修复损坏的 academic-gate)。stdlib-only、跨平台。
"""
from __future__ import annotations

import sys as _sys
try:  # Windows GBK 控制台/管道捕获下 emoji print 防 UnicodeEncodeError
    # 调用方(init_project/env_preflight)用 capture_output=True 拉本脚本的一行 JSON,
    # 崩了会被外层 except 全吞 → 一行门禁状态都不打印,用户完全看不到门禁没装上。
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HOOK_TAG = "academic_gate_hook.py"  # 识别我们的 hook entry(新旧路径都含此子串)
# 与 context_guard_core.SWITCH_NAME 同值(只用来拼给用户看的提示语,判定一律走 core)。
# 两处同值由 test_context_guard_core.py 的一条断言守着,漂了会红。
SWITCH_FILE_NAME = "academic-gate.local.json"
HEARTBEAT_NAME = "hook_heartbeat.json"
HEARTBEAT_FRESH_SEC = 24 * 3600  # 24h 内 fire 过算新鲜

# 部署四件套,顺序要紧:registry 是 hook 的开关(读不到→fail-open),放最后落盘。
# 心跳是运行时产物,绝不复制(把旧机器的心跳拷过去会把 degraded 伪装成 active)。
BUNDLE = (
    "structure_signoff_gate.py",
    "academic_gate_hook.py",
    "install_gate_hook.py",
    # 2026-07-28 起 academic_gate_hook.py 的判定全走 context_guard_core.py(三个钩子
    # 共用的唯一判定实现)。不一起部署的话,legacy 装法的 hook 一 import 就炸 → 拦层
    # 静默失效。这是"legacy 装法仍保留拦层"这条设计意图的必要条件。
    "context_guard_core.py",
    "gate_registry.json",
)


def _self_dir() -> Path:
    """本脚本所在目录(可能是 _shared/ 真源,也可能是某技能 scripts/ 的 vendored 副本)。"""
    return Path(__file__).resolve().parent


def _gate_dir() -> Path:
    """钩子的稳定部署位:在 skills/ 之外,不随任何技能目录的增删而动。"""
    return Path.home() / ".claude" / "academic-gate"


def _plugin_dir() -> Path:
    """academic-gate @skills-dir 插件目录:Claude Code 启动时自动加载其 hooks,
    不经过本安装器。它在场时本安装器让位(不写 settings、摘掉自己写过的 entry),
    否则同一次写入会被两条钩子各拦一次(不误放行,但噪音)。"""
    return Path.home() / ".claude" / "skills" / "academic-gate"


def _plugin_present() -> bool:
    d = _plugin_dir()
    return ((d / ".claude-plugin" / "plugin.json").is_file()
            and (d / "scripts" / "academic_gate_hook.py").is_file())


def _settings_path() -> Path:
    return Path.home() / ".claude" / "settings.json"


# Claude Code 自己注入的运行时变量(本安装器/技能从不设置它们)
CLAUDE_ENV_VARS = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_PROJECT_DIR",
                   "CLAUDE_PLUGIN_ROOT", "CLAUDE_CODE_SSE_PORT")
# ~/.claude/ 下由本安装器亲手造的东西 —— 它们绝不能当证据,否则跑过一次判据就永远为真
OUR_ARTIFACTS = {"academic-gate", "settings.json", "settings.json.bak-gatehook"}


def _settings_is_foreign(p: Path) -> bool:
    """settings.json 里存在不是本安装器写的内容 → 有人真配过 Claude Code。
    先按 remove 语义摘掉我们自己的 hook entry 再看还剩什么:只剩空壳 = 全是我们造的,不算证据。"""
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return p.is_file()  # 存在却读不出/非 JSON:肯定不是我们写的(我们写前写后都校验)
    if not isinstance(data, dict):
        return True
    _reconcile_entries(data, remove=True)
    hooks = data.get("hooks")
    if isinstance(hooks, dict) and not any(hooks.values()):
        data.pop("hooks", None)
    return bool(data)


def _claude_code_evidence() -> str | None:
    """这台机器在用 Claude Code 的证据(人话字符串),一条都找不到才返回 None。
    刻意宽松:任一条成立就照常安装。误判成"没装"会把真用户的门禁关掉,是最坏的失败方向;
    误判成"装了"只是多写一次没人读的文件。所有判据都不认本安装器自己的产物(见 OUR_ARTIFACTS)。"""
    for name in CLAUDE_ENV_VARS:
        if os.environ.get(name):
            return f"环境变量 {name}"
    if shutil.which("claude"):
        return "PATH 上有 claude 命令"
    home = Path.home()
    if (home / ".claude.json").is_file():
        return "~/.claude.json(Claude Code 主配置)"
    root = home / ".claude"
    try:
        for child in root.iterdir():
            if child.name not in OUR_ARTIFACTS:
                return f"~/.claude/{child.name}"
    except OSError:
        return None  # 目录不存在/读不了 = 没痕迹
    if _settings_is_foreign(root / "settings.json"):
        return "~/.claude/settings.json 里有用户自己的配置"
    return None


def _interpreter() -> str:
    """挑 hook 命令用的解释器:探测 PATH 上真实存在的裸名(fire 时再由 PATH 解析)。
    全新 macOS 只有 python3 没有 python(裸写 python → exit 127,Claude Code 对非 2
    退出码不阻断,物理锁会静默失效);老 Windows 反之只有 python。按探测不按平台猜,
    还能覆盖'Windows 装了 python3 别名'等平台规则会猜错的组合。两个裸名都不在
    PATH(极罕见,毕竟本脚本正在被某个 Python 跑)时退回 sys.executable 绝对路径
    兜底——绝对路径有 venv 删了跟着死的风险,故只作最后手段。
    每次安装/自检都重新探测:解释器环境变了(如 pyenv 卸载),_reconcile_entries
    的精确命令比对会自动把旧 entry 迁移成新命令,自愈。
    只判"在不在 PATH"不够:Windows 商店的 0 字节 python3.exe 占位程序照样能被
    shutil.which 命中,实跑却 rc=9009 → 选中它=三个钩子静默失效(round26 外部用户
    实测)。所以按 _hook_command_runs 的思路,选之前先试跑一次。"""
    for name in ("python3", "python"):
        exe = shutil.which(name)
        if exe and _runs(exe):
            return name
    return sys.executable or "python3"


def _runs(exe: str) -> bool:
    """空跑一段空代码,能 rc=0 才算真解释器(占位程序/损坏安装都会在此出局)。"""
    try:
        return subprocess.run([exe, "-c", ""], capture_output=True,
                              timeout=15).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _target_command() -> str:
    hook = _gate_dir() / "academic_gate_hook.py"
    interp = _interpreter()
    if " " in interp or os.sep in interp or (os.altsep and os.altsep in interp):
        interp = f'"{interp}"'  # 绝对路径兜底时可能含空格/分隔符,加引号
    # hook 路径引号包以容纳空格
    return f'{interp} "{hook}"'


def _hook_command_runs() -> bool:
    """双保险:把写进 settings 的那条命令原样经 shell 真跑一遍(灌良性 {} 输入,
    hook 无 file_path 会静默 exit 0)。跑不起来(127 解释器缺失/126 不可执行/超时)
    即物理锁实际失效,必须报 degraded 告警,不许假装 installed。
    shell=True 是刻意的:Claude Code 执行 hook 命令就是经 shell(PATH 解析/引号
    语义都走 shell),用列表形式测不到真实执行路径;命令串全部来自自控路径
    (探测的裸解释器名 + 本脚本拼的 hook 路径),无用户输入,无注入面。"""
    try:
        p = subprocess.run(_target_command(), shell=True, input="{}",
                           capture_output=True, text=True, timeout=15,
                           encoding="utf-8", errors="replace")
        return p.returncode == 0
    except Exception:
        return False


def _bundle_version(d: Path) -> int:
    """bundle 整包单版本 = 该目录 gate_registry.json 的 version(缺/坏=0)。"""
    try:
        return int(json.loads((d / "gate_registry.json").read_text(encoding="utf-8")).get("version", 0))
    except Exception:
        return 0


def _gate_complete() -> bool:
    return all((_gate_dir() / n).is_file() for n in BUNDLE)


def _deploy(force: bool) -> tuple[bool, str]:
    """把四件套从本目录部署到 academic-gate/。返回 (ok, action)。
    版本比较:目标 >= 自带 且完整 → 跳过;更旧/缺/不完整 → 覆盖;--force → 强制重刷。"""
    src = _self_dir()
    missing = [n for n in BUNDLE if not (src / n).is_file()]
    if missing:
        return False, f"部署源缺文件({', '.join(missing)})"
    sv, tv = _bundle_version(src), _bundle_version(_gate_dir())
    if not force and tv >= sv and _gate_complete():
        return True, "deploy-current"
    _gate_dir().mkdir(parents=True, exist_ok=True)
    for name in BUNDLE:  # 按 BUNDLE 顺序,registry 最后
        shutil.copyfile(src / name, _gate_dir() / name)
    return True, f"deployed-v{sv}"


def _heartbeat_status(hb_dir: Path | None = None) -> str:
    """心跳读钩子运行目录(缺省=部署位 academic-gate/;插件模式传插件 scripts/),
    不是本脚本目录——vendored 副本的同目录永远不会有心跳,读错位置会恒报 degraded。"""
    hb = (hb_dir or _gate_dir()) / HEARTBEAT_NAME
    if not hb.is_file():
        return "none"
    try:
        data = json.loads(hb.read_text(encoding="utf-8"))
        age = time.time() - int(data.get("last_fire_epoch", 0))
        return "fresh" if age <= HEARTBEAT_FRESH_SEC else "stale"
    except Exception:
        return "none"


def _reconcile_entries(settings: dict, remove: bool = False) -> tuple[bool, bool]:
    """把 settings 里我们的 hook entry 收敛为恰好一条、指向 academic-gate。
    返回 (changed, migrated)。migrated=True 表示删过旧路径/重复 entry。
    只动含 HOOK_TAG 的 hook 项;同 entry 里用户自己的其它 hook 原样保留。
    remove=True(插件在场):所有我们的 entry 一律摘除、不再补写——门禁由插件钩子承担。"""
    target_cmd = _target_command()
    # hooks/PreToolUse 可能被其它工具写成显式 null:coerce 成空容器,别抛异常退化成含糊 error
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
        settings["hooks"] = hooks
    pretool = hooks.get("PreToolUse")
    if not isinstance(pretool, list):
        pretool = []
        hooks["PreToolUse"] = pretool
    kept_target = False
    migrated = False
    new_pretool = []
    for idx, entry in enumerate(pretool):
        if not isinstance(entry, dict):
            new_pretool.append(entry)
            continue
        hlist = entry.get("hooks", []) or []
        if not isinstance(hlist, list):
            # 点名报错，别让它以 AttributeError 溺死在宽 except 里（无定位信息）
            raise TypeError(
                "settings.json hooks.PreToolUse 第 %d 条 entry（matcher=%r）的 "
                "hooks 字段应为 list，实际是 %s——请手动修正该文件后重试"
                % (idx, entry.get("matcher"), type(hlist).__name__))
        new_hlist = []
        for h in hlist:
            cmd = str(h.get("command", ""))
            if HOOK_TAG in cmd:
                if not remove and cmd == target_cmd and not kept_target:
                    kept_target = True
                    new_hlist.append(h)
                else:
                    migrated = True  # 旧路径(如 _shared)/重复条目/插件在场,删
            else:
                new_hlist.append(h)
        if new_hlist:
            if len(new_hlist) != len(hlist):
                entry = {**entry, "hooks": new_hlist}
            new_pretool.append(entry)
    if not remove and not kept_target:
        new_pretool.append({
            "matcher": "Write|Edit",
            "hooks": [{"type": "command", "command": target_cmd, "timeout": 60}],
        })
    changed = migrated or (not remove and not kept_target)
    if changed:
        hooks["PreToolUse"] = new_pretool
    return changed, migrated


def _install(settings_path: Path, remove: bool = False) -> tuple[bool, str]:
    """确保 settings.json 里恰有一条指向 academic-gate 的门禁 entry。
    返回 (ok, action):already-present | installed | migrated | 失败原因。
    remove=True:反向——摘光我们的 entry(returns removed | already-present)。"""
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    original = settings_path.read_text(encoding="utf-8") if settings_path.is_file() else None
    backup = None
    if original is not None:
        try:
            settings = json.loads(original)
            if not isinstance(settings, dict):
                return False, "settings.json 不是对象，跳过自动安装（请手动配置 hook）"
        except Exception:
            return False, "settings.json 解析失败（可能手动编辑出错），跳过自动安装，未改动"
        backup = settings_path.with_suffix(".json.bak-gatehook")
        shutil.copyfile(settings_path, backup)
    else:
        settings = {}

    changed, migrated = _reconcile_entries(settings, remove)
    if not changed:
        return True, "already-present"

    new_text = json.dumps(settings, ensure_ascii=False, indent=2)
    try:
        json.loads(new_text)  # 写前自校验
    except Exception:
        return False, "生成的 settings.json 非法，已放弃安装（原文件未动）"

    tmp_path = settings_path.with_name(settings_path.name + ".tmp-gatehook")
    # 原子写盘：先写同目录临时文件再 os.replace。直接 write_text 中途被 kill 会留下
    # 截断残文、用户原配置丢失（备份回滚代码在写完之后，进程死了没机会跑）。
    try:
        tmp_path.write_text(new_text, encoding="utf-8")
        if original is not None:
            shutil.copymode(settings_path, tmp_path)  # 保住用户原文件的权限位
        os.replace(tmp_path, settings_path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    # 写后再校验一次,坏了立即从备份回滚
    try:
        json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception:
        if backup and backup.is_file():
            shutil.copyfile(backup, settings_path)
        return False, "写入后校验失败，已从备份回滚，settings.json 未被破坏"
    if remove:
        return True, "removed"
    return True, ("migrated" if migrated else "installed")


def _read_switch() -> tuple[bool, str, str]:
    """(用户关了吗, 清洗过的理由, 开关文件最后修改日期)。

    🔴 单独包一层 try、失败一律按"开"：main() 的宽 except 会把任何异常变成
    status=error 且**跳过安装**。把 import 裸放进去，core 缺失/损坏就等于门禁不装了
    —— 而现状是 core 缺失照装不误，不许把失败方向翻过来。
    """
    try:
        sys.path.insert(0, str(_self_dir()))
        import context_guard_core as core
        if not core.enforcement_disabled():
            return False, "", ""
        note = core.sanitize_field(core.switch_note(), "text", 200) if core.switch_note() else ""
        try:
            mtime = time.strftime("%Y-%m-%d",
                                  time.localtime(core.switch_path().stat().st_mtime))
        except Exception:
            mtime = ""
        return True, note, mtime
    except Exception:
        return False, "", ""


def _disabled_message(note: str, mtime: str) -> str:
    """给**用户**看的那段话（安装器 stdout 是用户唯一真会看到的地方）。
    只回显 note 与 mtime；settings.json 的任何内容、任何环境变量值一律不进这里。"""
    where = "~/.claude/%s 里 enforcement_enabled=false" % SWITCH_FILE_NAME
    if mtime:
        where += "，最后修改 %s" % mtime
    if note:
        where += "；你写的理由：%s" % note
    return ("学术门禁的拦截层已被你关闭（%s）。本次不安装、不部署任何钩子，"
            "也不会再自动写回 settings.json。流程脚本与状态卡照常工作。"
            "要恢复拦截：删掉该文件，或把 enforcement_enabled 改成 true。" % where)


def main() -> None:
    result = {"status": "error", "action": "none", "message": ""}
    force = "--force" in sys.argv[1:]
    try:
        disabled, note, mtime = _read_switch()
        if disabled:
            # 摘 entry 只对 legacy 装法有意义（插件的 hooks.json 跨层级合并、删不掉），
            # 目的是让存量机器上那份不认识开关的陈旧 hook 不再被调起。
            ok, action = _install(_settings_path(), remove=True)
            if ok:
                result.update(status="disabled", action="user-killswitch",
                              message=_disabled_message(note, mtime))
            else:
                result.update(status="degraded", action="user-killswitch", message=(
                    "开关已生效（钩子读到开关会放行），但 settings.json 里的旧 hook 条目"
                    "没能摘除：" + action + "。settings.json 未被破坏。"
                    "若那条指向的是旧版钩子，请手动删除该条目。"))
            print(json.dumps(result, ensure_ascii=False))
            sys.exit(0)

        if _plugin_present():
            # 插件模式:钩子由 Claude Code 启动时自动加载,本安装器只负责"别再重复装一条"。
            # 不部署 ~/.claude/academic-gate/(插件自带三件套),并摘掉本安装器曾写过的 entry。
            ok, action = _install(_settings_path(), remove=True)
            hb = _heartbeat_status(_plugin_dir() / "scripts")
            if hb == "fresh":
                result.update(status="active", action="plugin", message=(
                    "门禁由 academic-gate 插件承担，已在岗（近期触发过）。跳步会被物理拦截。"
                    + ("已摘掉旧的自装 hook 条目（避免重复拦截）。" if action == "removed" else "")))
            else:
                result.update(status="degraded", action="plugin", message=(
                    "已装 academic-gate 插件，但未探测到它触发过——可能是刚放进 skills/ "
                    "还没重启（钩子在启动时加载，无法热生效），或当前运行端不透传 hook"
                    "（opencode / codex 从不读 Claude Code 钩子配置）。重启一次再看；"
                    "在此之前当作【未受保护】，按开场监工卡人工盯防。"
                    + ("已摘掉旧的自装 hook 条目。" if action == "removed" else "")))
            if not ok:
                result.update(status="degraded", action="plugin", message=(
                    "已装 academic-gate 插件；但清理旧的自装 hook 条目失败：" + action +
                    "。功能不受影响（可能被拦两次，噪音而已）。"))
            print(json.dumps(result, ensure_ascii=False))
            sys.exit(0)

        # 插件分支之后、_deploy 之前:_deploy 是第一个会凭空 mkdir ~/.claude/ 的动作,
        # 必须赶在它前面;又不能抢在插件分支前——插件在场时让位的逻辑优先级不变
        # (且插件目录本身就在 ~/.claude/skills/ 下,必然是 Claude Code 在用,不会互相打架)。
        if _claude_code_evidence() is None:
            result.update(status="degraded", action="skipped-no-claude-code", message=(
                "没在这台机器上找到任何 Claude Code 的痕迹（没有 CLAUDECODE 等运行时变量、"
                "PATH 上没有 claude 命令、~/.claude/ 下也没有非本安装器生成的文件），"
                "已跳过门禁安装——hook 配置只有 Claude Code 会读，硬装只会在你不用的目录里"
                "留一堆垃圾。⚠️ 这意味着在本机（如 codex / opencode 运行端）物理拦截【不生效】："
                "请当作未受保护，按开场监工卡逐项人工盯防，别指望门禁会自动拦。"
                "若你其实在用 Claude Code 却看到这条，说明本次没探测到它——"
                "在 Claude Code 里跑一次本技能即可自动安装。"))
            print(json.dumps(result, ensure_ascii=False))
            sys.exit(0)

        dok, daction = _deploy(force)
        if not _gate_complete():
            # 部署失败且目标也不完整:不写 entry(写了就是悬空路径,会拦死一切写入)
            result.update(status="degraded", action="deploy-failed", message=(
                f"门禁部署失败({daction})且 ~/.claude/academic-gate/ 不完整，"
                "未写入 settings.json（避免悬空 hook 路径）。请当作未受保护，按监工卡人工盯防。"))
            print(json.dumps(result, ensure_ascii=False))
            sys.exit(0)

        ok, action = _install(_settings_path())
        if not ok:
            result.update(status="degraded", action="install-skipped", message=(
                "未能自动安装门禁 hook：" + action + "。请当作未受保护，按监工卡人工盯防。"))
        elif not _hook_command_runs():
            # 双保险:entry 写对了但命令本身跑不起来(如解释器缺失)=物理锁静默失效
            result.update(status="degraded", action=action, message=(
                "门禁 hook 已写入 settings.json，但该命令在本机跑不起来"
                "（未找到 python3/python 解释器？）——物理拦截未生效。"
                "请安装 Python3 后重新运行本技能（会自动修复 hook 命令）；"
                "在此之前当作未受保护，按监工卡人工盯防。"))
        elif action == "already-present":
            hb = _heartbeat_status()
            if hb == "fresh":
                result.update(status="active", action="none",
                              message="强制门禁 hook 已在岗（近期触发过）。跳步会被物理拦截。")
            else:
                result.update(status="degraded", action="none", message=(
                    "门禁 hook 已写入 settings.json，但从未探测到它触发过——"
                    "说明当前运行环境可能不透传 hook，或安装后尚未重启会话。请把它当作【未受保护】："
                    "按开场监工卡逐项人工盯防，别信任'门禁会自动拦'。"))
        else:  # installed / migrated
            extra = ("（已把旧路径的 hook 条目迁移到稳定位置 ~/.claude/academic-gate/）"
                     if action == "migrated" else "")
            result.update(status="installed", action=action, message=(
                "已安装强制门禁保护到 settings.json（原文件已备份）" + extra +
                "。⚠️ 需【重启一次本会话/客户端】后生效——hook 在启动时加载，无法热生效。"
                "重启后再来用即受保护。注意：升级前就写到一半的旧项目，重启后再写正文可能被"
                "'结构签字缺失'拦一次——按提示补跑一次 structure_signoff confirm 即可继续，属正常迁移。"))
    except Exception as e:  # 安装器绝不能反过来卡住技能
        result.update(status="error", action="none",
                      message=f"门禁自检异常（不影响技能继续）：{e}")

    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
