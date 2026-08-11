#!/usr/bin/env python3
# delegate_write.py —— nsfc-proposal 撰写编排入口（薄封装：import 本家 vendored 共享核心）
#
# 逻辑全在 delegate_write_core.py（四家逐字节一致，L4 md5 守卫）。本文件只声明 nsfc
# 的账本映射 config：section 形态 P1..P7；文献库是 data/literature_index.json 的 dict
# 形态 {metadata, entries:[...]}，条目主键 id；本节文献切片无独立矩阵，
# 走 entries[].used_in_sections 含本 PX 过滤（§7）。核心已 config 化 index_shape=data_dict，
# 直接读原生 dict，不再需要主会话把 data/ 布局投影成 root list。

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from delegate_write_core import (  # noqa: E402
    BARE_NUM_RE, KEY_RE, SECTION_RE, _claim_set_hash, main,
)

__all__ = ["BARE_NUM_RE", "KEY_RE", "SECTION_RE", "CONFIG", "main"]

CONFIG = {
    "family": "nsfc-proposal",
    "section_regex": r"^P\d+(\.\d+)*$",  # P1 / P2.3 等
    # 🔴 只能有这一个候选。共享核心的 load_outline 会**依次试**候选表，任一候选里有
    # sections[] 就正常返回、核心不报错 —— 而本地闸口只看 data/outline.json 在不在。
    # 多留一个候选＝多一条绕过路径：实测在项目根手写三行 project_state.json
    # （{"sections":[{"section_id":"P1"}]}）就能让未经确认的"大纲"rc=0 出包，
    # 连承重核证那道拦截一起空过。project_state.json 是本轮之前"主会话临时投影"
    # 那套的残留、已被真大纲取代；storyline.json 是 gsw 产物、nsfc 永不产出。
    "outline_files": ["data/outline.json"],
    "outline_id_field": "section_id",
    "index_path": "data/literature_index.json",   # dict {metadata, entries:[...]}
    "index_shape": "data_dict",
    "index_entries_key": "entries",
    "index_id_field": "id",                        # 条目主键 L-001 等
    # 无独立矩阵：used_in_sections 含本 PX 过滤（§7）
    "lit_section": {"mode": "index_used_in", "file": None},
}


GATE_SUBCOMMANDS = ("pack-write", "pack-prep")
GATE_SECTION = "P1"


def _gate_args(argv):
    """用 argparse 自己解析出 (section, root)，规则由构造保证与共享核心一致。

    🔴 不许改回手写 argv 扫描：argparse 默认接受无歧义的长选项前缀缩写，
    `--sec P1` 照样被解析成 `--section P1`。手抄那套规则等于把 parser 的语义
    复制到离 parser 最远的地方 —— 核心以后加个短选项或改 allow_abbrev，
    这里不会报错，只会**静默失配、且失配方向是放行**（round19 首版实测：
    `--sec` 让未确认的大纲 rc=0 出包，连 fail-closed 那道保险一起废掉）。
    写命令行的正是本闸口要约束的 AI 自己，缩写一个参数比伪造签名便宜得多。

    parse_known_args 把 `--out` 等本闸口不关心的参数收进 unknown，不报错。
    """
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--section")
    p.add_argument("--root")
    try:
        ns, _unknown = p.parse_known_args(argv[1:])
    except SystemExit:
        # 参数畸形（缺值等）：交给共享核心的 parser 去报，闸口不介入
        return None, None
    return ns.section, ns.root


def _in_gate_scope(section):
    """P1 及其子节都归大纲管。

    section_regex 允许 `P1.1`（`^P\\d+(\\.\\d+)*$`），只认恰等于 "P1" 就会漏
    `--section P1.1` —— 与 outline_files 那条 fallthrough 是同一类「作用域判小了」
    的洞。当前流程不用子节号，先把口子按住。P2 起一律不介入（D1：大纲只做 P1）。
    """
    return isinstance(section, str) and (
        section == GATE_SECTION or section.startswith(GATE_SECTION + "."))


def _gate_die(reason, detail=""):
    sys.stderr.write("OUTLINE_GATE: %s%s\n" % (reason, (" " + detail) if detail else ""))
    sys.exit(2)


def outline_gate(argv):
    """P1 大纲闸口：没经用户确认 / 被改过 / 核证过期，一律不许出任务包。

    只在 pack-write / pack-prep 且 --section P1 时介入；verify-write 与其余节
    行为与改造前逐字节相同。大纲文件不存在时也不介入 —— 那句
    `outline has no section: P1` 由共享核心报，比闸口的话更可操作。

    🔴 fail-closed：outline_manager 不可用（缺文件/import 炸/返回值形态不对）时
    **拦住**，不许 try/except 放行 —— 检查器坏了却照常出包就是新的假绿点。
    """
    if not argv or argv[0] not in GATE_SUBCOMMANDS:
        return
    section, root = _gate_args(argv)
    if not _in_gate_scope(section):
        return
    if not root:
        return
    outline_file = os.path.join(root, "data", "outline.json")
    if not os.path.exists(outline_file):
        return

    try:
        import outline_manager
        result = outline_manager.check(root)
        ok, reason = result
        if not isinstance(ok, bool):
            raise TypeError("check() 第一个返回值不是布尔: %r" % (ok,))
    except Exception:
        _gate_die("outline_checker_unavailable",
                  "outline_manager.py 缺失或不可用，无法确认大纲已经用户点头；"
                  "先修好它再出包")
    if not ok:
        _gate_die(reason, "跑 outline_manager.py check --root %s 看详情" % root)

    if argv[0] != "pack-write":
        return  # pack-prep 正是为了产核证草案，不做核证过期闸

    ev_path = os.path.join(root, "claim_evidence.json")
    if not os.path.isfile(ev_path):
        return  # 缺证据/坏 JSON 交给共享核心报，它的文案更可操作
    try:
        with open(ev_path, "r", encoding="utf-8") as f:
            evidence = json.load(f)
    except Exception:
        return

    # 形态错与指纹错分开报：把「键名写错」诊断成「论点变了」，会把人指向重跑核证、
    # 重取摘要那条昂贵又无效的路，而实际只要改一个键名。
    expected = _claim_set_hash(_load_bearing_claims(outline_file))
    if isinstance(evidence, dict) and not isinstance(evidence.get("rows"), list):
        _gate_die("claim_evidence_bad_shape",
                  "claim_evidence.json 形态不对：顶层需为对象，承载证据行的数组键"
                  '必须叫 rows —— {"outline_claim_set_hash": ..., "rows": [...]}。'
                  "（写成 claims 会让共享的 citation_claim_check.py 硬报 bad_evidence。"
                  "这是键名问题，不用重跑核证。）")
    got = evidence.get("outline_claim_set_hash") if isinstance(evidence, dict) else None
    if not isinstance(got, str) or got != expected:
        _gate_die("claim_evidence_stale",
                  "大纲论点已变更，需重跑核证：指纹原样抄自 .prep_task_P1.json"
                  "（重跑 pack-prep 拿新指纹）。"
                  "若顶层还是老的裸 list 形态，它没有承载指纹的位置，"
                  '先改成 {"outline_claim_set_hash": ..., "rows": [...]}。')


def _load_bearing_claims(outline_file):
    """取 P1 的派生承重论点。走到这里 check() 已经过了，文件必然是好的。"""
    with open(outline_file, "r", encoding="utf-8") as f:
        doc = json.load(f)
    for sec in doc.get("sections") or []:
        if isinstance(sec, dict) and sec.get("section_id") == GATE_SECTION:
            return sec.get("load_bearing_claims") or []
    return []


if __name__ == "__main__":
    outline_gate(sys.argv[1:])
    main(CONFIG)
