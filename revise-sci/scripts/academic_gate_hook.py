#!/usr/bin/env python3
"""共享学术门禁 hook —— 一个 PreToolUse hook 服务全部学术技能。

它是"扳机"，判定一律走 context_guard_core（三个钩子唯一共用的判定实现，绝不在
这里重写一套）。拦到一次 Write/Edit/MultiEdit/NotebookEdit（Codex 端是
apply_patch）时，按下面的顺序决策：

  ① F8 证据分档（先算一次，后面全部复用）
     none  → 放行（绝大多数写入走这里，开销≈向上找几次文件）
     weak  → 目标是受保护文件或受管产物 → ask；否则放行
     strong→ 进 ②
  ② F6 受保护文件（structure_signoff.json / .review_pass/*.json）→ deny
  ③ F10 差集锁（新建/空的受管正文 + 存在"声明完成但没盲检"的节）→ deny
  ④ 既有 signoff 门禁（signoff:true 的 4 家）exit≠0 → deny
  ⑤ 都不命中 → 放行

🔴 分档排第一、F6 也走分档：否则"陌生目录里写一个同名文件就被无条件 deny"，
直接违背"不误伤陌生人"这条红线（插件是要公开分发的）。

设计铁律：
- fail-open 的**边界**：认不出项目 / 无标记文件 → 放行；但**已判定命中后自身
  出错**（编码、JSON 拼装、写审计失败）绝不静默放行，必须仍输出 deny/ask。
- 恒 exit 0（deny 通过 JSON 表达，不用 exit 2）。
- 只碰"受管产物路径"与两类受保护文件，其余一切写入零影响。
- 三端共用：路径归一化在 core 的 extract_file_paths()（Codex 的 tool_input 里
  没有 file_path，改文件的信息全在 apply_patch 补丁文本里）；解析不出路径时
  **不走静默路径**，留审计 rule="path-parse-failed"。
- Codex 上 ask 折成 **allow + 审计**（见 _is_codex 与 main 里的分支）：那端不支持
  ask，会判钩子失败然后照常执行工具。弱档本就是"撞名的陌生项目"，硬拦保护力不增
  而误伤巨大（那端没有"允许一次"）；不静默由审计兑现。Claude Code 侧 ask 不变。

stdin: PreToolUse 事件 JSON。stdout: 命中时一个决策 JSON，放行时完全为空。
"""
from __future__ import annotations

# 🔴 stdout/stderr 强制 UTF-8（照抄 env_preflight.py:17-20 的既有写法）。
# 不加这段的后果（已实测复现）：deny 理由含中文，在英文语系 Windows（cp1252）
# 与 cp437 上 print() 抛 UnicodeEncodeError → 脚本非 0 退出 → Claude Code 只认
# exit 2 为阻断、其余一律"非阻断错误"放行 → **门禁在真正命中拦截的那一刻自己炸掉、
# 然后放行**。fail-open 是对"认不出项目"的设计取向，不该被编码问题借去用。
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import context_guard_core as core  # noqa: E402  （同目录 vendored，纯 stdlib）

HEARTBEAT_NAME = "hook_heartbeat.json"
GATE_SUBPROCESS_TIMEOUT = 8      # 内层；外层 hook timeout 15 s，8<15 是硬约束
WRITE_TOOLS = {"apply_patch", "Write", "Edit", "MultiEdit", "NotebookEdit"}

REASON_F6_SIGNOFF = (
    "[学术门禁] structure_signoff.json 是结构签字凭证，只能由用户本人在自己终端运行 "
    "structure_signoff_gate.py confirm 产生。当前这次写入不是该脚本产生的，已拦下。"
    "正确做法：把完整大纲展示给用户，等用户在对话里明确确认，再由用户本人运行 confirm。"
)
REASON_F6_CERT = (
    "[学术门禁] .review_pass/{sid}.json 是盲检通过凭证，只能由 delegate_review.py verify "
    "产生。直接写这个文件等于自己给自己发合格证，已拦下。正确做法：跑 delegate_review.py "
    "pack → 派独立子代理盲检 → delegate_review.py verify --return <返回json>。"
)
REASON_F8_ASK = (
    "[academic-gate 插件] 这个目录里有 {marker}，名字与学术写作技能的项目标记相同，"
    "但文件内容不像学术写作项目（缺 {missing}）。是否按学术写作项目对这次写入执行流程门禁？"
    "选\"否\"则本次照常写入。"
)
REASON_F10 = (
    "[学术门禁] 本项目有已声明完成但没有盲检标记的节：{sections}。新正文文件的写入已拦下。"
    "本项目的盲检命令形态是 {cmd}。补齐这些节的盲检标记后即可继续。"
    "（已存在文件的修改不受此拦截影响。）"
)
NOTICE_PARSE_FAILED = (
    "[academic-gate v{ver}] 本次工具调用的目标文件路径未能解析（tool_name={tool}），"
    "学术写作流程门禁这一次没有执行检查。"
)
NOTICE_PARSE_FAILED_LATER = (
    "上一次工具调用（{tool}）的目标路径未能解析，那一次没有执行门禁检查。"
)


def _shared_dir() -> Path:
    return Path(__file__).resolve().parent


def _write_heartbeat(reason: str, extra: dict | None = None) -> None:
    """记录 hook 确实 fire 了一次。preflight 读它判断 hook 是否在岗。
    失败绝不抛（心跳是辅助，不能反过来拖垮 hook）。"""
    try:
        hb = {"last_fire_epoch": int(time.time()), "reason": reason}
        if extra:
            hb.update(extra)
        # 原子写：并发的钩子进程同时写心跳，直接 write_text 被打断会留半截 JSON，
        # preflight 读到就报"心跳损坏"（本该是"在岗"）。
        core._atomic_write(_shared_dir() / HEARTBEAT_NAME,
                           json.dumps(hb, ensure_ascii=False))
    except Exception:
        pass


def _section_from_filename(file_path: Path) -> str:
    """从产物文件名抽 section_id：取数字/点组合，如 section_2.1.md→2.1、
    results_3.2.md→3.2。抽不出返回文件名主干（让门禁自己报错，不在这瞎猜）。"""
    stem = file_path.stem
    m = re.search(r"(\d+(?:[._]\d+)*)", stem)
    return m.group(1).replace("_", ".") if m else stem


def _gates_for(skill_cfg: dict, registry: dict) -> list:
    """该技能要跑哪些门禁。signoff:true → 共享结构签字门禁；否则无(仅心跳)。"""
    if skill_cfg.get("signoff") and registry.get("signoff_gate"):
        return [registry["signoff_gate"]]
    return []


def _run_gates(gates: list, root: Path, file_path: Path) -> tuple:
    """跑门禁。返回 (blocked, message)。任一 gate exit≠0 即 blocked。"""
    py = sys.executable or "python"
    section = _section_from_filename(file_path)
    subs = {
        "{python}": py,
        "{project_root}": str(root),
        "{file_path}": str(file_path),
        "{section}": section,
        "{shared_dir}": str(_shared_dir()),
    }

    def _subst(tok: str) -> str:
        for k, v in subs.items():
            tok = tok.replace(k, v)
        return tok

    for gate in gates:
        cmd = [_subst(tok) for tok in gate.get("command", [])]
        if not cmd:
            continue
        try:
            # 🔴 显式 encoding/errors：text=True 会按 locale 解码，非 UTF-8 locale
            # （中文 Windows、LANG=C 的容器）下门禁的中文输出解码即抛，被下面的宽
            # except 吞成"跑不起来"→ **真拦截被静默放行**。这正是文件头 UTF-8 那段
            # 警告过的同一类事故，换了个地方复发。
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace",
                                  timeout=GATE_SUBPROCESS_TIMEOUT, cwd=str(root))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # 门禁超时/不存在 → 按既有设计 fail-open 放行，不误伤用户
            return False, ""
        except Exception as exc:
            # 其余异常属"我自己出问题了"，不是"这不是学术项目"：仍放行，但必须留痕
            core.audit_append(root, event="PreToolUse", rule="internal-error",
                              decision="unchecked", detail=type(exc).__name__)
            return False, ""
        if proc.returncode != 0:
            # 🔴 门禁脚本的输出要过清洗再进 deny 理由：registry 的 command 可以指向
            # 任意脚本，它的 stdout 就是外部文本，而 deny 理由是官方明说给 Claude 看的。
            # 这是 8 个注入出口里最后一个没设防的。
            raw = (proc.stdout or "").strip() or (proc.stderr or "").strip()
            detail = core.sanitize_field(raw, "text", 800) if raw else ""
            return True, (
                f"[学术门禁] 「{gate.get('name','gate')}」未通过，本次写入被拦下。\n"
                f"原因：{detail}\n"
                f"这不是 bug——是流程门禁在阻止跳步。请先补上门禁要求的步骤"
                f"（跑对应脚本、过上一节盲检等），过了再写。"
            )
    return False, ""


def _emit(decision: str, reason: str) -> None:
    """输出决策。**已判定命中后拼装/编码失败也绝不静默放行**：兜底用纯 ASCII
    精简文案再发一次。"""
    payload = {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }}
    try:
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    except Exception:
        try:
            sys.stdout.write(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason":
                    "[academic-gate] blocked by academic writing gate.",
            }}) + "\n")
            sys.stdout.flush()
        except Exception:
            pass


def _emit_context(text: str) -> None:
    try:
        sys.stdout.write(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "additionalContext": text}},
            ensure_ascii=False) + "\n")
    except Exception:
        pass


def _infra_guard(payload: dict, tool_name: str) -> bool:
    """门禁自身文件的写保护。命中即 deny，返回 True。

    🔴 位置铁律：调用点必须在 `core.load_registry()` **之前**。把它放进 _judge 或
    放在读注册表之后，AI 只要先把 gate_registry.json 写成 `{}`，main() 就在读注册表
    那一步返回了 —— 一票废掉包括这条保护在内的一切。本判定因此不依赖注册表、不依赖
    项目根、不依赖分档，是整个钩子里最不依赖状态的一条。
    """
    if tool_name not in WRITE_TOOLS:
        return False          # 只拦写不拦读
    for raw in core.infra_target_strings(payload):
        try:
            cat = core.protected_infra(raw, payload.get("cwd"))
        except Exception:
            cat = "unparsable"   # 判据自己炸了也不放行（本条唯一 fail-closed）
        if not cat:
            continue
        reason = (core.REASON_INFRA_SWITCH if cat == "killswitch"
                  else core.REASON_INFRA.format(
                      target=core.sanitize_field(raw, "text", 200)))
        _emit("deny", reason)     # 先出决策，再写审计：审计失败不得改变决策
        core.audit_append(None, event="PreToolUse", tool=tool_name,
                          rule=core.INFRA_RULE, decision="deny", skill="",
                          target=core.sanitize_field(raw, "text", 180),
                          detail="%s tool" % cat)
        return True
    return False


def _judge(path: Path, registry: dict):
    """对一个目标路径做一次判定。返回 None=放行，否则 (decision, reason, 审计字段)。"""
    ev = core.detect_for_path(path, registry)
    if ev.tier == "none" or ev.root is None:
        return None                      # 认不出项目 → 放行（不写审计）
    root = ev.root
    rel = core.rel_to_root(path, root)
    if rel is None:
        return None                      # realpath 后落在项目根外 → 不属于本项目
    protected = core.is_protected_file(rel)
    skill = core.skill_for_rel(ev, registry, rel)
    _write_heartbeat("gate_evaluated", {"tier": ev.tier, "skill": ev.skill or "", "file": rel})

    if ev.tier == "weak":
        if not (protected or skill):
            return None                  # 撞名但目标既非受保护也非受管 → 放行
        missing = core.sanitize_list(ev.missing_signature, "ident") or ["关键字段"]
        reason = REASON_F8_ASK.format(
            marker=core.sanitize_field(ev.matched_state_file, "text", 120),
            missing="、".join(missing))
        # 🔴 审计落点按目标分两种（weak 就是"我不确定这是不是学术项目"）：
        #  · 目标是受保护凭证（structure_signoff.json / .review_pass/*.json）——文件名
        #    指名道姓就是我们的凭证，不是"路过的陌生人"，证据留在项目内；
        #  · 目标只是撞了 managed_globs（drafts/section_*.md 这类通用名）——那才是
        #    真正的误伤面，**一个字节都不许落在人家目录里**，留痕改落 CLAUDE_PLUGIN_DATA
        #    （root=None + rule 在 NO_ROOT_RULES 里）。
        # 审计 detail 里用空格分隔：全角冒号不在清洗白名单里，会被剔成"…文件state.json"
        audit_root = root if protected else None
        return ("ask", reason, audit_root, "F8-weak-ask", "", rel,
                "撞名 state 文件 %s" % ev.matched_state_file)

    # ---- strong
    if protected == "signoff":
        return ("deny", REASON_F6_SIGNOFF, root, "F6-protected-signoff", ev.skill, rel,
                "伪造结构签字文件")
    if protected == "cert":
        sid = core.sanitize_field(Path(rel).stem, "ident")
        return ("deny", REASON_F6_CERT.format(sid=sid), root, "F6-protected-cert",
                ev.skill, rel, "伪造盲检证书")
    if not skill:
        return None                      # 不是任何在场技能的受管产物 → 放行
    cfg = (registry.get("skills") or {}).get(skill) or {}

    if cfg.get("signoff"):
        # F10 只在"新建受管正文"时评估：已存在且非空文件的修改一律不拦，否则被
        # 差集点名的那一节自己也改不了，会把整个项目锁死。
        # 判"不存在或为空"而不是"不存在"：`touch x.md && Edit x.md` 是 AI 的日常写法。
        if not core.nonempty(path):
            pending = core.pending_review(root, skill, registry)
            if pending:
                shown = core.sanitize_list(pending, "ident")
                reason = REASON_F10.format(
                    sections="、".join(shown),
                    cmd=core.verify_command(skill, root))
                return ("deny", reason, root, "F10-subset-lock", skill, rel,
                        "%s 声明完成但无盲检标记" % pending[0])
        blocked, message = _run_gates(_gates_for(cfg, registry), root, path)
        if blocked:
            return ("deny", message, root, "signoff-gate", skill, rel, "结构签字未通过")
    return None


def _handle_parse_failure(payload: dict, tool_name: str) -> None:
    """路径解析失效：判不了就不敢拦（仍放行），但**绝不走"认不出项目"的静默路径**。

    Codex 上直读 file_path 恒 None → 若按静默 fail-open 处理，门禁形同虚设却一声
    不吭，这是最危险的失效形态。fail-open 是给"确认不是学术项目"的，不是给"我没
    看懂这次调用"的——两者必须在日志与上下文里可区分。
    """
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict) or not tool_input:
        return                            # 空 tool_input 没有可判信息，不构成解析失效
    if tool_name not in WRITE_TOOLS:
        return
    keys = " ".join(sorted(str(k) for k in tool_input.keys()))
    core.audit_append(None, event="PreToolUse", tool=tool_name,
                      rule="path-parse-failed", decision="unchecked",
                      detail="%s / %s" % (tool_name, keys))
    if core.NOTICE_MODE == "A":
        _emit_context(NOTICE_PARSE_FAILED.format(ver=core.plugin_version(), tool=tool_name))
    else:
        cwd = payload.get("cwd")
        if isinstance(cwd, str) and cwd:
            try:
                key = os.path.realpath(cwd)
            except Exception:
                key = cwd
            core.push_notice(key, NOTICE_PARSE_FAILED_LATER.format(tool=tool_name))


def _is_codex(payload: dict) -> bool:
    """这一次调用是不是 Codex 发来的。**只认一个信号**：tool_name == "apply_patch"。

    依据（Codex 官方 hooks 文档）：matcher 可以写 apply_patch/Edit/Write 三种别名，
    但**钩子输入里的 tool_name 恒为 "apply_patch"**。Claude Code 侧不存在这个工具名，
    且我们 hooks.json 的 matcher 是 Write|Edit|MultiEdit|NotebookEdit，Claude Code 上
    根本不会有 tool_name="apply_patch" 的调用抵达本脚本 → 这个信号不会误伤现役行为。

    没用"file_path 缺失"当信号：那和"字段恰好为空"分不清。也没用环境变量——Codex 给
    插件钩子设 PLUGIN_ROOT/PLUGIN_DATA（Claude Code 只设 CLAUDE_PLUGIN_ROOT），可以当
    备用信号，但它只在"以插件形式安装"时存在，而那时 tool_name 已经够用了，白加一条
    误判面。若哪天 Codex 改了 tool_name，PLUGIN_ROOT 是现成的补充信号。
    """
    return payload.get("tool_name") == "apply_patch"


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return                            # 读不到输入：放行
    if not isinstance(payload, dict):
        return
    tool_name = payload.get("tool_name")
    tool_name = tool_name if isinstance(tool_name, str) else ""

    # 顺序铁律：infra 保护 → 用户开关 → 原有门禁。前两步都在读注册表之前。
    if _infra_guard(payload, tool_name):
        return
    if core.enforcement_disabled():
        return                            # 用户关了拦截层：本层全放行（infra 保护不受影响）

    registry = core.load_registry()
    if not registry.get("skills"):
        return                            # 无注册表：放行（既有行为不变）

    paths = core.extract_file_paths(payload)
    if not paths:
        _handle_parse_failure(payload, tool_name)
        return

    for path in paths:                    # 一次 apply_patch 可改多个文件，任一命中即拦
        try:
            verdict = _judge(path, registry)
        except Exception as exc:
            # 判定过程自身出错 → 放行（未判定成功不算命中），但必须留痕：
            # 这一条与"认不出项目"的静默放行长得一样，日志里不能也长得一样。
            core.audit_append(None, event="PreToolUse", tool=tool_name or "Write",
                              rule="internal-error", decision="unchecked",
                              detail="judge %s" % type(exc).__name__)
            verdict = None
        if verdict is None:
            continue
        decision, reason, root, rule, skill, target, detail = verdict
        if decision == "ask" and _is_codex(payload):
            # Codex 不支持 ask（那端会判钩子失败然后照常执行工具）。折成放行而不是拦：
            # ask 只出在弱证据档 = "只是撞了通用目录名的陌生项目"，真正在用本技能的项目
            # 有状态签名、走强证据档、在 Codex 上照拦不误。硬拦弱档保护力一点没多，代价
            # 却是把陌生项目卡死——Codex 的拦截框没有"允许一次"，唯一出路是去 /hooks 停
            # 掉整个插件。放行对陌生项目本就是正确默认；原来担心的"静默"由这条审计兑现。
            # rule 保持 "F8-weak-ask"：它在 core.NO_ROOT_RULES 白名单里，改名会让这一档
            # （root=None，只能落 CLAUDE_PLUGIN_DATA）的留痕被静默丢弃。
            core.audit_append(root, event="PreToolUse", tool=tool_name or "Write",
                              rule=rule, decision="allow", skill=skill, target=target,
                              detail=(detail + " codex 无 ask 档按放行").strip())
            continue                      # 同一段 patch 里的其余文件照判（可能有强档命中）
        _emit(decision, reason)           # 先出决策，再写审计：审计失败不得影响决策
        core.audit_append(root, event="PreToolUse", tool=tool_name or "Write",
                          rule=rule, decision=decision, skill=skill,
                          target=target, detail=detail)
        return


def _forward_to_deployed() -> bool:
    """悬空防护:本文件若从开发真源 skills/_shared/ 被 settings.json 旧 entry 调起,
    且稳定部署副本 ~/.claude/academic-gate/ 已存在,则转发执行部署副本(单一运行时,
    心跳/registry 都落部署位)。_shared 里本文件因此永远不裸删:旧 entry 指过来时
    有文件可执行,不会 python 找不到路径 exit 2 拦死一切写入。
    测试可用环境变量 ACADEMIC_GATE_NO_FORWARD=1 关闭转发(直接测本文件逻辑)。

    🔴 转发前先把已 import 的 context_guard_core 从 sys.modules 里摘掉：本文件在
    import 阶段就加载了 _shared 那份 core,而 core 的 shared_dir() 是按**模块文件
    位置**算 registry/插件版本的。不摘,部署副本会复用 _shared 那份模块对象 → 读的
    是 _shared 的 registry,"心跳/registry 都落部署位"这句就成了假话(两份 registry
    版本不同时,判定用的是开发版而不是部署版)。"""
    if os.environ.get("ACADEMIC_GATE_NO_FORWARD"):
        return False
    here = Path(__file__).resolve()
    if "/_shared/" not in str(here).replace("\\", "/"):
        return False  # 部署副本/vendored 副本直接跑自己
    deployed = Path.home() / ".claude" / "academic-gate" / "academic_gate_hook.py"
    if not deployed.is_file() or deployed.resolve() == here:
        return False
    try:
        import runpy
        sys.modules.pop("context_guard_core", None)
        runpy.run_path(str(deployed), run_name="__main__")
        return True
    except SystemExit:
        raise
    except Exception:
        return False  # 转发失败回落本地逻辑(fail-open 精神)


if __name__ == "__main__":
    if not _forward_to_deployed():
        main()
    sys.exit(0)
