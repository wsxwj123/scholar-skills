#!/usr/bin/env python3
"""Blind review delegation helper for academic writing skills.

固定"委托独立子代理盲检"的流程步骤,消除主 agent 自评失真 + 防止漏检。

为什么需要:主 agent 带着写作上下文自评 DoD 会失真(默认自己写的都对)
且容易漏项。本脚本把"委托盲检"拆成两个确定性步骤:

  pack    读 checklist JSON 的指定 gate -> 打印给独立子代理的"盲检任务包"
          (角色框定 + 待检文件 + 完整清单 + 返回格式)。
  verify  读子代理返回的 JSON + checklist -> 校验每个清单项都被裁决、
          fail/na 附证据;任一缺项 / verdict=fail / 证据为空 -> 退出码 1
          (fail-closed,阻断"声明本节完成")。

checklist JSON 是 DoD 清单的唯一机器可读真源(SKILL.md 散文与之逐项对应),
脚本固定步骤后,AI 即使失忆也不会漏检或自评放水。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

VALID_VERDICTS = {"pass", "fail", "na"}


def _load_json(path: str) -> Any:
    p = Path(path)
    if not p.exists():
        sys.stderr.write(f"[delegate_review] 文件不存在: {path}\n")
        sys.exit(2)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"[delegate_review] JSON 解析失败 {path}: {exc}\n")
        sys.exit(2)


def _get_gate(checklist: dict, gate: str) -> dict:
    gates = checklist.get("gates", {})
    if not isinstance(gates, dict):
        sys.stderr.write(
            f"[delegate_review] checklist 'gates' 必须是对象(dict)，实际为 {type(gates).__name__}\n"
        )
        sys.exit(2)
    if gate not in gates:
        avail = ", ".join(sorted(gates)) or "(空)"
        sys.stderr.write(f"[delegate_review] 未知 gate '{gate}'。可用: {avail}\n")
        sys.exit(2)
    return gates[gate]


def _get_items(gate_obj: Any, gate: str) -> list:
    """校验 gate 对象结构并返回其 items 列表。

    防止畸形 checklist(gate 非 dict / items 非 list / item 非 dict 或缺 id)
    在 pack/verify 用 `it["id"]` 时抛 TypeError。全部走友好 stderr + exit 2。
    """
    if not isinstance(gate_obj, dict):
        sys.stderr.write(
            f"[delegate_review] gate '{gate}' 必须是对象(dict)，实际为 {type(gate_obj).__name__}\n"
        )
        sys.exit(2)
    items = gate_obj.get("items")
    if not isinstance(items, list):
        sys.stderr.write(
            f"[delegate_review] gate '{gate}' 的 'items' 必须是数组(list)，实际为 {type(items).__name__}\n"
        )
        sys.exit(2)
    for idx, it in enumerate(items):
        if not isinstance(it, dict):
            sys.stderr.write(
                f"[delegate_review] gate '{gate}' 第 {idx} 项畸形:必须是对象(dict)，实际为 {type(it).__name__}\n"
            )
            sys.exit(2)
        if "id" not in it:
            sys.stderr.write(
                f"[delegate_review] gate '{gate}' 第 {idx} 项畸形:缺少 'id' 字段\n"
            )
            sys.exit(2)
    return items


def _read_comments_text(path: str) -> str:
    """Read the original reviewer letter as plain text (.docx or .txt/.md).

    The blind reviewer needs the ORIGINAL letter, not the already-parsed units:
    a comment collapsed into one unit is invisible when checking against units alone.
    """
    p = Path(path)
    if not p.exists():
        sys.stderr.write(f"[delegate_review] 审稿信文件不存在: {path}\n")
        sys.exit(2)
    if p.suffix.lower() == ".docx":
        try:
            from docx import Document  # python-docx is a skill dependency
        except ImportError:
            sys.stderr.write(
                "[delegate_review] 读取 .docx 需 python-docx；请改传纯文本审稿信(.txt/.md)\n"
            )
            sys.exit(2)
        doc = Document(str(p))
        return "\n".join(par.text for par in doc.paragraphs)
    return p.read_text(encoding="utf-8", errors="replace")


def cmd_pack(args: argparse.Namespace) -> int:
    checklist = _load_json(args.checklist)
    skill = checklist.get("skill", "?")
    gate = _get_gate(checklist, args.gate)
    items = _get_items(gate, args.gate)
    item_ids = [it["id"] for it in items]

    # 打印给子代理的盲检任务包(纯文本,跨平台可粘贴)
    lines: list[str] = []
    lines.append(f"# 盲检任务包 · {skill} · gate={args.gate}")
    lines.append(f"## {gate.get('title', args.gate)}")
    if gate.get("applies_when"):
        lines.append(f"适用条件:{gate['applies_when']}")
    lines.append("")
    lines.append("## 你的角色")
    lines.append(
        "你是独立审稿子代理,**没有本稿的写作上下文**。不得假设作者意图、"
        "不得因'像是写好了'而默认通过。只依据下列文件的**实际内容**逐项裁决。"
    )
    lines.append("")
    lines.append("## 待检文件")
    for f in args.files:
        lines.append(f"- {f}")
    lines.append("")
    if getattr(args, "comments", None):
        comments_text = _read_comments_text(args.comments)
        lines.append("## 审稿信原文(逐条点名核对，防漏回/答非所问)")
        lines.append(
            "下面是**未经解析的原始审稿信全文**。逐条覆盖类清单项(如 RR7/RR14/RR15)"
            "**必须以本原文为准**，而不是只看已生成的 units：把原信中每一条独立诉求(含"
            "连续散文里的多个问点、`(i)(ii)`、罗马数字、项目符号、一段多诉求)逐个点名，"
            "回到 units 里找到对应回复；**找不到对应 unit = 漏回(fail)**，回复不对题 = 答非所问(fail)。"
        )
        lines.append("")
        lines.append("```text")
        lines.append(comments_text.strip())
        lines.append("```")
        lines.append("")
    lines.append("## 检查清单(逐项裁决,不得跳过)")
    for it in items:
        seg = f"- [{it['id']}] {it.get('name', '')}:{it.get('check', '')}"
        if it.get("severity") == "soft":
            seg += "  · 🟡软项(仅报告不阻断,但仍须逐项裁决并附证据)"
        if it.get("script"):
            seg += f"  · 先跑脚本核:`{it['script']}`"
        lines.append(seg)
    lines.append("")
    lines.append("## 返回格式(只返这个 JSON,不要别的文字)")
    lines.append("```json")
    lines.append(
        json.dumps(
            [{"id": item_ids[0] if item_ids else "X1", "verdict": "pass|fail|na", "evidence": "证据/原因"}],
            ensure_ascii=False,
        )
    )
    lines.append("```")
    lines.append(
        "规则:每个清单 id 必须出现一次;verdict ∈ {pass,fail,na};"
        "evidence 对每个 id 都必填——pass 须给出据以判定通过的具体证据(文件位置/脚本输出/原文),fail/na 须指出问题所在。空证据一律视为未裁决,拦截。"
    )
    lines.append("")
    return_path = str(Path(args.workdir) / f".review_return_{args.gate}.json")
    lines.append(f"## 返回写到这个文件(约定路径,主 agent 据此跑 verify)")
    lines.append(return_path)
    print("\n".join(lines))
    # 同时把约定路径打到 stderr,方便主 agent 脚本直接取用而不必解析任务包
    sys.stderr.write(f"RETURN_PATH={return_path}\n")
    return 0


def _project_root_for_verify(args: argparse.Namespace) -> str:
    """推导 .review_pass 落盘的项目根。

    优先级:--root 显式 > --workdir(pack 约定的项目根目录) >
    --return 父目录 > --checklist 父目录。确保与 prewrite_gate 读取的
    <root>/.review_pass/ 落在同一项目根。
    """
    if getattr(args, "root", None):
        return args.root
    if getattr(args, "workdir", None) and args.workdir != ".":
        return args.workdir
    if getattr(args, "return_path", None):
        return str(Path(args.return_path).resolve().parent)
    if getattr(args, "checklist", None):
        return str(Path(args.checklist).resolve().parent)
    return args.workdir or "."


def cmd_verify(args: argparse.Namespace) -> int:
    checklist = _load_json(args.checklist)
    gate = _get_gate(checklist, args.gate)
    items = _get_items(gate, args.gate)
    expected = [it["id"] for it in items]
    # 软项(severity=soft):仍进任务包被裁决,但其 fail/缺裁决/空证据只汇报不阻断,
    # 不计入 ok/退出码。未标 severity 的项默认硬项,行为与旧版完全一致(向后兼容)。
    soft_ids = {it["id"] for it in items if it.get("severity") == "soft"}

    returned = _load_json(args.return_path)
    if not isinstance(returned, list):
        sys.stderr.write("[delegate_review] 子代理返回必须是 JSON 数组\n")
        return 1

    by_id: dict[str, dict] = {}
    problems: list[str] = []
    for entry in returned:
        if not isinstance(entry, dict) or "id" not in entry:
            problems.append(f"返回项格式非法: {entry!r}")
            continue
        by_id[entry["id"]] = entry

    fails: list[str] = []
    soft_flags: list[str] = []
    for eid in expected:
        is_soft = eid in soft_ids
        entry = by_id.get(eid)
        if entry is None:
            (soft_flags if is_soft else problems).append(
                f"{eid}: 软项未裁决(不阻断)" if is_soft else f"缺漏未裁决: {eid}")
            continue
        verdict = entry.get("verdict")
        if verdict not in VALID_VERDICTS:
            (soft_flags if is_soft else problems).append(f"{eid}: verdict 非法 ({verdict!r})")
            continue
        evidence = (entry.get("evidence") or "").strip()
        if not evidence and not is_soft:
            problems.append(f"{eid}: verdict={verdict} 但 evidence 为空（每项裁决都须附证据，pass 也不例外，防无证据橡皮图章）")
        if verdict == "fail":
            (soft_flags if is_soft else fails).append(f"{eid}: {evidence or '(无证据)'}")

    extra = [k for k in by_id if k not in set(expected)]
    if extra:
        problems.append(f"返回了清单外的 id: {', '.join(extra)}")

    # soft_flags 只汇报,不影响 ok / 退出码(软项不阻断交付)
    ok = not problems and not fails
    summary = {
        "gate": args.gate,
        "ok": ok,
        "checked": len(expected),
        "fails": fails,
        "soft_flags": soft_flags,
        "problems": problems,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not ok:
        sys.stderr.write(
            "[delegate_review] 盲检未通过(fail-closed):不得向用户声明本节/本报告完成。\n"
        )
        return 1
    # 全过且提供了 --section 时,落盘通过标记供下一节 prewrite_gate 硬校验。
    # 标记写入失败不改变 verify 结果(仍 exit 0),仅打 warning。
    if getattr(args, "section", None):
        try:
            root = _project_root_for_verify(args)
            pass_dir = Path(root) / ".review_pass"
            pass_dir.mkdir(parents=True, exist_ok=True)
            marker = {"passed": True, "gate": args.gate, "section": args.section}
            (pass_dir / f"{args.section}.json").write_text(
                json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            sys.stderr.write(
                f"[delegate_review] 警告:盲检通过标记落盘失败({exc});verify 结果不受影响。\n"
            )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="盲检委托:固定委托独立子代理的流程步骤")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_pack = sub.add_parser("pack", help="生成盲检任务包")
    p_pack.add_argument("--checklist", required=True, help="DoD 清单 JSON 路径")
    p_pack.add_argument("--gate", required=True, help="清单内的 gate id")
    p_pack.add_argument("--files", nargs="+", required=True, help="待检文件路径")
    p_pack.add_argument("--comments", default=None,
                        help="原始审稿信路径(.docx/.txt/.md)；传入后全文嵌入任务包，供盲检子代理逐条点名核对漏回/答非所问。强烈建议传")
    p_pack.add_argument("--workdir", default=".", help="项目工作目录,用于推导 .review_return_<gate>.json 落点(默认 cwd)")
    p_pack.set_defaults(func=cmd_pack)

    p_ver = sub.add_parser("verify", help="校验子代理返回(fail-closed)")
    p_ver.add_argument("--checklist", required=True, help="DoD 清单 JSON 路径")
    p_ver.add_argument("--gate", required=True, help="清单内的 gate id")
    p_ver.add_argument("--return", dest="return_path", default=None,
                       help="子代理返回的 JSON 路径(默认用 pack 约定的 .review_return_<gate>.json)")
    p_ver.add_argument("--workdir", default=".", help="项目工作目录,用于推导返回文件与 .review_pass 落点(默认 cwd)")
    p_ver.add_argument("--section", default=None,
                       help="本次盲检对应的 section id;提供后全过会在 <root>/.review_pass/<section>.json 落盘通过标记(供下一节 prewrite_gate 硬校验)。不传则行为与旧版完全一致")
    p_ver.add_argument("--root", default=None,
                       help=".review_pass 落盘的项目根(默认推导自 --workdir/--return/--checklist)")
    p_ver.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    if getattr(args, "cmd", None) == "verify" and not args.return_path:
        args.return_path = str(Path(args.workdir) / f".review_return_{args.gate}.json")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
