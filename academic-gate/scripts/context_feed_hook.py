#!/usr/bin/env python3
"""喂层钩子 —— 把"这个项目现在真实的状态"当场从文件读出来，喂回 AI 的上下文。

挂三个事件（academic-gate/hooks/hooks.json）：
  SessionStart(startup|clear|compact|resume|fork) → 全景状态卡（压缩/恢复后重建）
  UserPromptSubmit                                → 短版卡（有话要说才注入）
  PostToolUse(Write|Edit|MultiEdit|NotebookEdit)  → 写完受管正文的一行提醒

三事件统一输出 hookSpecificOutput.additionalContext：PostToolUse 上的裸 stdout
只进 debug log、**静默丢失**，统一成 JSON 才三处都算数。

设计铁律：
- **恒 exit 0**：非 0 会在 transcript 刷 hook error 噪音。
- **fail-open**：任何异常、认不出项目、非学术目录 → 输出空。喂层不是安全边界，
  它坏了不该妨碍用户。
- 状态卡**全部写成陈述句**：措辞像系统命令会触发 Claude 自身的注入防御，把文本
  原样甩给用户而不是当上下文用（官方明文警告）。改成祈使句 = 这层白做。
- 一切插值内容过 context_guard_core.sanitize_field()：节 id、文件名、路径全都
  来自被审查目录，公开分发后那就是别人写的东西。
"""
from __future__ import annotations

# 🔴 stdout/stderr 强制 UTF-8（照抄 academic_gate_hook.py:27-32 的既有写法）。
# 不加这段：中文状态卡在 cp1252/cp437 上 print() 抛 UnicodeEncodeError → 非 0 退出
# → transcript 刷错误。喂层虽是 fail-open，也不该以"炸一次"的方式失败。
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import json
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import context_guard_core as core  # noqa: E402  （同目录 vendored，纯 stdlib）

EVENTS = ("SessionStart", "UserPromptSubmit", "PostToolUse")
STDIN_LIMIT = 1024 * 1024
LIMITS = {"SessionStart": 2500, "UserPromptSubmit": 600, "PostToolUse": 300}
TRUNC_NOTE = "（状态卡过长已截断，完整信息见项目文件）"


def _debug(exc: BaseException) -> None:
    if os.environ.get("CONTEXT_GUARD_DEBUG"):
        try:
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stderr)
        except Exception:
            pass


def _read_payload():
    data = sys.stdin.buffer.read(STDIN_LIMIT + 1)
    if len(data) > STDIN_LIMIT:
        return None  # 超大输入直接放弃（正常事件 JSON 远小于 1 MB）
    try:
        payload = json.loads(data.decode("utf-8", "replace"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _fit(lines: list, limit: int) -> str:
    text = "\n".join(lines)
    if len(text) <= limit:
        return text
    while len(lines) > 1:
        lines.pop()
        text = "\n".join(lines + [TRUNC_NOTE])
        if len(text) <= limit:
            return text
    return text[:limit]


def _review_state(root: Path, sid: str) -> str:
    passed, _ = core.review_passed(root, sid)
    # 路径一律走 core 的唯一构造入口（sid 是外部输入，自己拼会绕开校验）
    cert = core.review_pass_path(root, sid)
    try:
        exists = cert is not None and cert.is_file()
    except OSError:
        exists = False
    if not exists:
        return "不存在"
    return "passed=true" if passed else "passed≠true"


def _outline_readable(root: Path) -> bool:
    """这个项目的大纲这会儿还取得出结构投影吗。

    直接复用签字门禁的 build_fingerprint（同目录 vendored），不另写一套"大纲在哪"
    的判据——两套判据迟早各说各话。取不出/import 不到一律按"读得出"处理：
    状态卡是 fail-open 的，宁可少说一句，也不误报"大纲没了"。
    """
    try:
        import structure_signoff_gate as ssg
        return ssg.build_fingerprint(root) is not None
    except Exception:
        return True


def _signoff_line(root: Path) -> str:
    try:
        obj = json.loads((root / "structure_signoff.json").read_text(encoding="utf-8"))
        ok = isinstance(obj, dict) and bool(obj.get("confirmed"))
        line = ("结构签字：structure_signoff.json 存在，confirmed=%s"
                % ("true" if ok else "false"))
        # 存量签字没有大纲绑定信息（升级前落的）——照常放行，但要把这个事实说出来，
        # 否则用户以为"签字绑着大纲"，实际改了纲也不会有人拦。只描述项目事实，
        # 不描述拦不拦（INTERFACE §8.10）。
        if ok and not isinstance(obj.get("outline_fingerprint"), dict):
            line += "（已确认，未绑定大纲；下次 confirm 会自动绑定）"
        elif ok and not _outline_readable(root):
            # 绑过大纲、但这次读不出那份大纲（被挪走/删了/坏了）。签字文件看着还在，
            # 绑定关系实际已经落空；不说出来的话，用户和模型两侧都以为还绑着。
            # 同样只描述项目事实，不描述拦不拦（INTERFACE §8.10）。
            line += "（已绑定大纲，但本次读不出大纲文件）"
        return line
    except FileNotFoundError:
        return "结构签字：structure_signoff.json 不存在"
    except Exception:
        return "结构签字：structure_signoff.json 存在但解析失败"


def _snapshot(root: Path, skill: str, registry: dict) -> dict:
    declared = core.declared_sections(root, skill, registry)
    pending = [s for s in declared if not core.review_passed(root, s)[0]]
    manual = core.manual_passed(root, skill, registry)
    return {"declared": declared, "pending": pending, "manual": manual}


def _full_card(root: Path, ev, registry: dict, snap: dict, notice: str) -> str:
    ver = core.plugin_version()
    root_s = core.sanitize_field(str(root), "text", 200)
    lines = ["[学术项目状态卡 · academic-gate v%s 从项目文件读出，非会话记忆]" % ver]
    # 🔴 这一句必须待在卡片前部的不可截断区：_fit 从末尾往回砍，排在后面的话
    # "开态有、关态无"这条断言会因为卡片变长而在无关处失灵。
    # 用户关掉拦截层时整行删除（那时它是假话），且**不新增任何"当前不拦"的陈述**——
    # 状态卡的读者是模型，把"现在没人管你"喂给被约束方是反效果。
    if not core.enforcement_disabled():
        lines.append("本项目存在已声明完成但无盲检标记的节时，"
                     "academic-gate 会拦下新正文文件的写入。")
    lines += [
        "项目根：%s" % root_s,
        "技能：%s" % core.sanitize_field(ev.skill, "ident"),
        _signoff_line(root),
    ]
    declared = snap["declared"]
    if declared:
        lines.append("节完成态（取自项目状态文件，逐节列出已声明完成的节）：")
        for raw in declared[:core.LIST_MAX]:
            shown = core.sanitize_field(raw, "ident")
            lines.append("  %s  已声明完成  .review_pass/%s.json %s"
                         % (shown, shown, _review_state(root, raw)))
        if len(declared) > core.LIST_MAX:
            lines.append("  …等 %d 项" % len(declared))
    else:
        lines.append("节完成态：项目状态文件里暂无已声明完成的节。")
    if snap["manual"]:
        lines.append("人工放行的盲检：%s（manual=true，reason 见对应 json 文件）"
                     % "、".join(core.sanitize_list(snap["manual"], "ident")))
    if snap["pending"]:
        lines.append("已声明完成但无盲检标记的节：%s"
                     % "、".join(core.sanitize_list(snap["pending"], "ident")))
    lines.append("本项目的盲检命令：%s" % core.verify_command(ev.skill, root))
    if ev.unknown:
        lines.append("未知项：%s。" % "；".join(core.sanitize_list(ev.unknown, "text", 120)))
    if notice:
        lines.append(notice)
    return _fit(lines, LIMITS["SessionStart"])


def _short_card(root: Path, ev, snap: dict, notice: str) -> str:
    ver = core.plugin_version()
    lines = ["[学术项目状态卡·短版 · academic-gate v%s] 技能=%s 项目根=%s"
             % (ver, core.sanitize_field(ev.skill, "ident"),
                core.sanitize_field(str(root), "text", 200))]
    if snap["pending"]:
        lines.append("已声明完成但无盲检标记的节：%s"
                     % "、".join(core.sanitize_list(snap["pending"], "ident")))
    if snap["manual"]:
        lines.append("人工放行的盲检：%s（manual=true）"
                     % "、".join(core.sanitize_list(snap["manual"], "ident")))
    if ev.unknown:
        lines.append("未知项：%s。" % "；".join(core.sanitize_list(ev.unknown, "text", 120)))
    if notice:
        lines.append(notice)
    lines.append("本项目的盲检命令：%s" % core.verify_command(ev.skill, root))
    return _fit(lines, LIMITS["UserPromptSubmit"])


def _post_line(root: Path, skill: str, rel: str) -> str:
    ver = core.plugin_version()
    head = ("[学术项目 · academic-gate v%s] 刚写入 %s（%s 受管正文）。本项目该节的盲检命令是 "
            % (ver, core.sanitize_field(rel, "text", 200),
               core.sanitize_field(skill, "ident")))
    line = head + core.verify_command(skill, root) + "。"
    if len(line) > LIMITS["PostToolUse"]:
        # 命令行比根路径重要：先砍 --root，再硬截（宁可短，不可掉命令）
        line = head + core.verify_command(skill, root, with_root=False) + "。"
    if len(line) > LIMITS["PostToolUse"]:
        line = line[:LIMITS["PostToolUse"]]
    return line


def _emit(event: str, text: str) -> None:
    if not text:
        return
    sys.stdout.write(json.dumps(
        {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}},
        ensure_ascii=False) + "\n")


def run() -> None:
    payload = _read_payload()
    if payload is None:
        return
    event = payload.get("hook_event_name")
    if event not in EVENTS:          # 不猜、不按默认事件处理
        return
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return
    try:
        cwd_real = Path(os.path.realpath(cwd))
        if not cwd_real.is_dir():
            return
    except OSError:
        return

    # 上一次"路径没解析出来 / 弱证据未拦"的待报（NOTICE_MODE="B"），读后即删。
    notice = core.pop_notice(str(cwd_real)) if event == "UserPromptSubmit" else ""

    registry = core.load_registry()
    if core.registry_unreadable() and event in ("SessionStart", "UserPromptSubmit"):
        # 注册表读不出来 = 认不出任何项目 = 后面什么都不会说。不留这一行的话，
        # `chmod 000 gate_registry.json` 就成了"一声不吭地让门禁整体失效"。
        # 只陈述基础设施坏了这个事实，不说拦不拦（INTERFACE §8.10）。
        _emit(event, "[学术门禁 v%s] 门禁读不出自己的技能清单文件 %s"
                     "（文件在，但打不开或内容不可用，常见原因是权限被改或文件损坏）。"
                     "请用户检查该文件。" % (core.plugin_version(), core.REGISTRY_NAME))
        return
    ev = core.detect(cwd_real, registry)
    if ev.tier != "strong" or ev.root is None:
        # 非学术项目零打扰；唯一例外是有待报要捎话。
        if notice:
            _emit(event, "[academic-gate v%s] %s" % (core.plugin_version(), notice))
        return

    root = ev.root
    snap = _snapshot(root, ev.skill, registry)

    if event == "SessionStart":
        # F1 不受"按需注入"约束：压缩/恢复后的重建时刻，全绿也要给一张全景卡。
        _emit(event, _full_card(root, ev, registry, snap, notice))
        return

    if event == "PostToolUse":
        paths = core.extract_file_paths(payload)
        if not paths:
            return
        rel = core.rel_to_root(paths[0], root)
        if rel is None:
            return
        skill = core.skill_for_rel(ev, registry, rel)
        if not skill:
            return  # 写的不是受管产物 → 不打扰
        if not (snap["pending"] or snap["manual"] or ev.unknown):
            return  # 按需注入：全绿不说话
        text = _post_line(root, skill, rel)
    else:  # UserPromptSubmit
        if not (snap["pending"] or snap["manual"] or ev.unknown or notice):
            return
        text = _short_card(root, ev, snap, notice)

    # 内容去重：同一张卡不连着注两遍（省上下文，不是正确性；存不下就照常注）。
    # SessionStart 不参与去重——它就是"重建"的时刻，重复也得给。
    # 🔴 带 notice 的这一张必须跳过去重：notice 是 pop 出来的（读后即删），一旦被
    # 去重吃掉就**永久丢失**——而它记的正是"上一次没执行门禁检查"，最不该丢的一条。
    if not notice and core.card_is_duplicate(str(root), text):
        return
    _emit(event, text)


def main() -> None:
    try:
        run()
    except Exception as exc:   # fail-open：喂层任何异常都静默，绝不妨碍用户
        _debug(exc)


if __name__ == "__main__":
    main()
    sys.exit(0)
