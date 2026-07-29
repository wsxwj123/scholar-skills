#!/usr/bin/env python3
"""结构签字门禁（共享，粗粒度）——"大纲/故事线没经用户确认，不许写正文"。

为什么是它：跳步的 AI（尤其弱模型）最常见的失误就是没等用户确认大纲/storyline
就开写正文。本门禁把"用户确认"理化成一个签字文件，hook 在每次写正文产物前
check 它——签字不存在就物理拦截写入。逐节时序仍由各技能自己的 prewrite_gate
+ token 链负责；本门禁只管这个从文件状态就能可靠判定的粗粒度不变量。

签字**绑定它签的那份大纲**（INTERFACE §8）：confirm 时把大纲的结构投影
（节号 / 标题 / 层级 / 顺序，四样，不含任何正文）写进签字文件，check 时重算比对。
大纲结构一变 → exit 3 并逐类点名哪几节变了，要求用户重新确认；
而进度 / 统计 / 时间戳这类**正常变动不进投影**，不会触发重签。

用法：
  confirm: python structure_signoff_gate.py confirm --root <project_root> [--note "用户确认要点"]
    仅当用户在对话中明确确认了大纲/storyline 后才能运行——AI 不得代替用户确认。
    写 <root>/structure_signoff.json（含 UTC 时间戳、note 与大纲结构投影），解锁正文写作。
  check:   python structure_signoff_gate.py check --root <project_root>

退出码（INTERFACE §8.6）：
  0  通过（含"存量签字未绑定大纲"与各 fail-open 情形）
  2  还没签：签字文件不存在 / 坏 JSON / confirmed≠true
  3  签过但大纲已变，要重签
  64 用法错（EX_USAGE；与 argparse 默认的 2 拆开，否则调用方分不出"参数写错"与"还没签"）

签字后大纲又大改了怎么办：由**用户本人**确认后重跑 confirm 覆盖（append 历史到 history 字段）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

SIGNOFF_NAME = "structure_signoff.json"

EX_OK = 0
EX_UNSIGNED = 2
EX_RESIGN = 3
EX_USAGE = 64

TITLE_MAX = 80        # 单个标题截断长度（INTERFACE §8.3）
NODES_MAX = 300       # 结构投影条数上限（同上）
DIFF_MAX = 10         # 每类差异最多列几条（INTERFACE §8.8）

RESIGN_MARK = "大纲已变更，需要重新确认"
UNBOUND_HINT = "本签字未绑定大纲，下次 confirm 会自动绑定。"
MALFORMED_HINT = ("本签字未绑定大纲，下次 confirm 会自动绑定"
                  "（签字里的指纹字段格式不认识，已按未绑定处理）。")
FIXIT = ("正确做法：把改动后的大纲完整展示给用户，由用户本人确认后重跑 "
         "`python structure_signoff_gate.py confirm --root <项目根>`；AI 不得代替用户确认。")

# 判定库（认这是哪家技能 + 文案清洗）。拿不到就按"不绑定"走 —— import 失败绝不能
# 翻转成"把所有人拦死"（fail-open 的方向不许被异常改写）。
try:
    import context_guard_core as _core
except Exception:                                    # pragma: no cover - 环境缺件
    _core = None


# ------------------------------------------------------------------ 结构投影

def _norm_title(value) -> str:
    """空白折叠 + 截断。不做大小写折叠、不去标点（改标点通常是改意思）。"""
    s = re.sub(r"\s+", " ", str(value)).strip()
    return s[:TITLE_MAX] + "…" if len(s) > TITLE_MAX else s


def _read_json(path: Path):
    """文件缺失 / 坏 JSON / 不可读一律 None（调用方按 fail-open 处理）。"""
    try:
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


_ID_KEYS = ("id", "section_id", "chapter", "chapter_number", "number")
_TITLE_KEYS = ("title", "heading", "name")
_CHILD_KEYS = ("chapters", "sections", "subsections", "children", "items")


def _first_str(obj: dict, keys) -> str:
    for k in keys:
        v = obj.get(k)
        if isinstance(v, (str, int, float)) and not isinstance(v, bool):
            s = str(v).strip()
            if s:
                return s
    return ""


def _walk(node, level: int, out: list) -> None:
    """递归取 [标识, 标题, 层级]。只认身份 / 标题 / 子节三类键，其余（status、进度、
    统计、正文）一概不看——这正是"每写一节都要重签"那个死法的防线。"""
    if isinstance(node, list):
        for item in node:
            _walk(item, level, out)
        return
    if not isinstance(node, dict):
        return
    ident = _first_str(node, _ID_KEYS)
    title = _norm_title(_first_str(node, _TITLE_KEYS))
    child_level = level
    if ident or title:
        out.append([ident or title, title, level])
        child_level = level + 1
    for key in _CHILD_KEYS:
        if key in node:
            _walk(node[key], child_level, out)


def _proj_gsw(root: Path):
    """general-sci-writing：storyline.json 的 sections[]。"""
    obj = _read_json(root / "storyline.json")
    if not isinstance(obj, dict) or not isinstance(obj.get("sections"), list):
        return None
    nodes: list = []
    _walk(obj["sections"], 2, nodes)
    return nodes, ["storyline.json#sections"]


_RW_HEAD_RE = re.compile(r"^(#{2,})\s+(.+)$")
_RW_ID_RE = re.compile(r"^(\d+(?:\.\d+)+)\b")


def _proj_rw(root: Path):
    """review-writing：outline.md 的可写小节标题序列。

    与 review-writing/scripts/prewrite_gate.load_outline_order 同口径（只收带子编号的
    `##+` 标题，章级/配置段标题不进链），但**层级取井号个数**而非 section_id 段数——
    同一个节号从 `## 2.2` 降成 `### 2.2` 是真实的层级变化，按段数推会看不见。
    """
    path = root / "outline.md"
    try:
        if not path.is_file():
            return None
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None
    nodes: list = []
    for line in lines:
        m = _RW_HEAD_RE.match(line)
        if not m:
            continue
        title = m.group(2).strip()
        sub = _RW_ID_RE.match(title)
        if not sub:
            continue
        sid = sub.group(1)
        nodes.append([sid, _norm_title(title[len(sid):]), len(m.group(1))])
    return nodes, ["outline.md"]


# nsfc 的实体分区：短别名与 consistency_mapper 的长键名都认（真实账本用长键，
# 模板/夹具用短键）。**只取 id 与链路，不取任何 text**——那些文字就是标书正文。
_NSFC_ENTITIES = (
    ("SQ", "scientific_questions"), ("H", "hypotheses"), ("O", "objectives"),
    ("KSQ", "key_scientific_problems"), ("RC", "research_contents"),
    ("M", "methodologies"), ("IN", "innovations"), ("F", "feasibility_evidence"),
)
_NSFC_LINK_HINTS = ("mapped", "supports", "trace", "_id", "_ids", "related", "refs")
_NSFC_ID_RE = re.compile(r"^[A-Za-z0-9._\-]{1,32}$")


def _nsfc_ids(cmap, design) -> set:
    """这一批账本里所有实体的 id。链路的值只能取自这里——见 _nsfc_links。"""
    ids = set()
    if isinstance(cmap, dict):
        for short, long in _NSFC_ENTITIES:
            items = cmap.get(short)
            if not isinstance(items, list):
                items = cmap.get(long)
            if not isinstance(items, list):
                continue
            for idx, entry in enumerate(items):
                if isinstance(entry, dict):
                    ident = _first_str(entry, _ID_KEYS) or str(idx)
                    ids.add(ident)
                    ids.add("%s-%s" % (short, ident))
    if isinstance(design, dict) and isinstance(design.get("entries"), list):
        for idx, entry in enumerate(design["entries"]):
            if isinstance(entry, dict):
                ident = _first_str(entry, _ID_KEYS) or str(idx)
                ids.add(ident)
                ids.add("ED-%s" % ident)
    return ids


def _nsfc_links(entry: dict, ids: set) -> str:
    """把"谁指向谁"压成一行。两道过滤，缺一不可（§8.4：只取 id 与链路关系，
    不取任何文字表述）：

    ① 长得像标识符（中文表述天然不匹配）；
    ② **必须能在同一批账本的 id 集合里找到**。只有 ① 的话，纯英文单词形态的
       句子片段会被当成 id 存进指纹（实测泄漏样例：related: ENGLISH_PROSE_SENTINEL）
       —— 指向一个不存在的实体本来就不是链路，丢掉不损失任何结构信息。
    """
    out = []
    for key in sorted(entry):
        low = key.lower()
        if not any(h in low for h in _NSFC_LINK_HINTS):
            continue
        val = entry[key]
        vals = val if isinstance(val, list) else [val]
        hit = [v for v in vals
               if isinstance(v, str) and _NSFC_ID_RE.match(v) and v in ids]
        if hit:
            out.append("%s=%s" % (key, ",".join(hit)))
    return ";".join(out)


def _proj_nsfc(root: Path):
    """nsfc-proposal：consistency_map 的 H/O/RC/KSQ 链路 + experimental_design 的 entries[]。"""
    cmap = _read_json(root / "data" / "consistency_map.json")
    design = _read_json(root / "data" / "experimental_design.json")
    if not isinstance(cmap, dict) and not isinstance(design, dict):
        return None
    nodes: list = []
    sources: list = []
    ids = _nsfc_ids(cmap, design)
    if isinstance(cmap, dict):
        sources.append("data/consistency_map.json")
        for short, long in _NSFC_ENTITIES:
            items = cmap.get(short)
            if not isinstance(items, list):
                items = cmap.get(long)
            if not isinstance(items, list):
                continue
            for idx, entry in enumerate(items):
                if not isinstance(entry, dict):
                    continue
                ident = _first_str(entry, _ID_KEYS) or str(idx)
                nodes.append(["%s-%s" % (short, ident), _nsfc_links(entry, ids), 2])
    if isinstance(design, dict) and isinstance(design.get("entries"), list):
        sources.append("data/experimental_design.json")
        for idx, entry in enumerate(design["entries"]):
            if not isinstance(entry, dict):
                continue
            ident = _first_str(entry, _ID_KEYS) or str(idx)
            nodes.append(["ED-%s" % ident, _nsfc_links(entry, ids), 2])
    return nodes, sources


def _proj_sci2doc(root: Path):
    """sci2doc：project_state.json 的 outline 子字段（不是整个文件——同一个文件里的
    progress/stats 每写一节就变，整文件取哈希等于每节重签）。"""
    obj = _read_json(root / "project_state.json")
    if not isinstance(obj, dict) or "outline" not in obj:
        return None
    nodes: list = []
    _walk(obj["outline"], 2, nodes)
    return nodes, ["project_state.json#outline"]


PROJECTIONS = {
    "general-sci-writing": _proj_gsw,
    "review-writing": _proj_rw,
    "nsfc-proposal": _proj_nsfc,
    "sci2doc": _proj_sci2doc,
}


def _detect_skill(root: Path) -> str:
    if _core is None:
        return ""
    try:
        return _core.detect(root).skill or ""
    except Exception:
        return ""


def _digest(nodes: list) -> str:
    return hashlib.sha256(
        json.dumps(nodes, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def build_fingerprint(root: Path):
    """返回 INTERFACE §8.1 的指纹对象；认不出技能 / 大纲读不出 → None（fail-open）。"""
    fn = PROJECTIONS.get(_detect_skill(root))
    if fn is None:
        return None
    try:
        res = fn(root)
    except Exception:
        return None
    if res is None:
        return None
    nodes, sources = res
    truncated = len(nodes) > NODES_MAX
    nodes = nodes[:NODES_MAX]
    return {"algo": "sha256-16", "skill": _detect_skill(root), "value": _digest(nodes),
            "sources": sources, "nodes": nodes, "nodes_truncated": truncated}


def _valid_fingerprint(fp) -> bool:
    if not isinstance(fp, dict) or not isinstance(fp.get("value"), str):
        return False
    nodes = fp.get("nodes")
    if not isinstance(nodes, list):
        return False
    return all(isinstance(n, (list, tuple)) and len(n) == 3 for n in nodes)


# ------------------------------------------------------------------ 差异

def _show_id(value) -> str:
    return _core.sanitize_field(value, "ident") if _core else str(value)


def _show_title(value) -> str:
    return _core.sanitize_field(value, "text", TITLE_MAX) if _core else str(value)


def _join(items) -> str:
    """每类最多列 DIFF_MAX 条，超出追加 `…等 N 项`（N = 没列出来的条数）。"""
    shown = "、".join(items[:DIFF_MAX])
    if len(items) > DIFF_MAX:
        shown += "…等 %d 项" % (len(items) - DIFF_MAX)
    return shown


def diff_lines(old: list, new: list) -> list:
    """五类差异：新增 / 删除 / 改名 / 改序 / 改层级，每类一行，有则列出、无则省略。"""
    old_map = {str(n[0]): n for n in old}
    new_map = {str(n[0]): n for n in new}
    old_ids = [str(n[0]) for n in old]
    new_ids = [str(n[0]) for n in new]
    lines = []

    added = [i for i in new_ids if i not in old_map]
    if added:
        lines.append("新增的节：" + _join(
            ["%s「%s」" % (_show_id(i), _show_title(new_map[i][1])) for i in added]))
    removed = [i for i in old_ids if i not in new_map]
    if removed:
        lines.append("删除的节：" + _join(
            ["%s「%s」" % (_show_id(i), _show_title(old_map[i][1])) for i in removed]))

    common = [i for i in new_ids if i in old_map]
    renamed = [i for i in common
               if _norm_title(old_map[i][1]) != _norm_title(new_map[i][1])]
    if renamed:
        lines.append("改名的节：" + _join(
            ["%s「%s」→「%s」" % (_show_id(i), _show_title(old_map[i][1]),
                                 _show_title(new_map[i][1])) for i in renamed]))

    # 改序只看公共节之间的相对次序：插入/删除本身已由上面两行说清，不该再把
    # "后面的节整体后移"当成一堆顺序变化刷屏。
    old_common = [i for i in old_ids if i in new_map]
    moved = [i for i in common if old_common.index(i) != common.index(i)]
    if moved:
        lines.append("顺序变化：" + _join(
            ["%s 由第 %d 位移到第 %d 位"
             % (_show_id(i), old_common.index(i) + 1, common.index(i) + 1)
             for i in moved]))

    relevel = [i for i in common if old_map[i][2] != new_map[i][2]]
    if relevel:
        lines.append("层级变化：" + _join(
            ["%s 由 %s 级变为 %s 级" % (_show_id(i), old_map[i][2], new_map[i][2])
             for i in relevel]))
    return lines


# ------------------------------------------------------------------ 子命令

def cmd_confirm(root: Path, note: str) -> int:
    path = root / SIGNOFF_NAME
    history = []
    if path.is_file():
        try:
            prev = json.loads(path.read_text(encoding="utf-8"))
            history = prev.get("history", [])
            history.append({k: prev[k] for k in ("confirmed_epoch", "note") if k in prev})
        except Exception:
            pass
    payload = {
        "confirmed": True,
        "confirmed_epoch": int(time.time()),
        "note": note or "",
        "history": history[-10:],
    }
    fp = build_fingerprint(root)
    if fp is not None:
        payload["outline_fingerprint"] = fp
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "signoff": str(path),
                      "outline_bound": fp is not None}, ensure_ascii=False))
    return EX_OK


def cmd_check(root: Path) -> int:
    path = root / SIGNOFF_NAME
    if not path.is_file():
        print(
            "结构签字缺失：大纲/故事线还没有经过用户确认。\n"
            "正确流程：① 把完整大纲/storyline 展示给用户 → ② 用户在对话里明确说'确认'"
            " → ③ 运行 python <本脚本> confirm --root <项目根> 落盘签字 → ④ 才能写正文。\n"
            "AI 不得在用户未确认时自行运行 confirm。"
        )
        return EX_UNSIGNED
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        print("structure_signoff.json 损坏（非合法 JSON），请让用户重新确认大纲后重跑 confirm。")
        return EX_UNSIGNED
    if not isinstance(data, dict):
        print("structure_signoff.json 损坏（顶层不是 JSON 对象），"
              "请让用户重新确认大纲后重跑 confirm。")
        return EX_UNSIGNED
    if data.get("confirmed") is not True:
        print("structure_signoff.json 存在但 confirmed≠true，请让用户确认大纲后重跑 confirm。")
        return EX_UNSIGNED

    if "outline_fingerprint" not in data:
        print(UNBOUND_HINT)
        return EX_OK
    old = data["outline_fingerprint"]
    if not _valid_fingerprint(old):
        print(MALFORMED_HINT)
        return EX_OK

    cur = build_fingerprint(root)
    if cur is None:
        # 大纲文件不存在 / 读不出 / 认不出是哪家：大纲坏了是另一个问题，不该
        # 表现为"签字失效"（fail-open，与门禁整体取向一致）。
        print("签字已绑定大纲，但这次读不出大纲文件（不存在或无法解析），本次不因此拦截。")
        return EX_OK
    if cur["value"] == old["value"]:
        return EX_OK

    print(RESIGN_MARK)
    if old.get("nodes_truncated") or cur.get("nodes_truncated"):
        print("大纲节点数超过可记录上限，无法逐节列出差异；请对照大纲文件自行核对后重新确认。")
    else:
        lines = diff_lines([list(n) for n in old["nodes"]], cur["nodes"])
        if lines:
            for line in lines:
                print(line)
        else:
            print("结构投影与签字里记录的一致，但签字里的校验值对不上"
                  "（可能是手工改过，或从别的项目复制而来）。")
    print(FIXIT)
    return EX_RESIGN


# ------------------------------------------------------------------ CLI

class _Parser(argparse.ArgumentParser):
    """把用法错从 argparse 默认的 2 挪到 64（EX_USAGE）。

    2 已经是"还没签"的语义，撞码会让调用方（和人）分不出"参数写错了"和
    "用户还没确认大纲"。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("%s: error: %s\n" % (self.prog, message))
        sys.exit(EX_USAGE)


def main() -> int:
    parser = _Parser(description="结构签字门禁：用户确认大纲前不许写正文")
    sub = parser.add_subparsers(dest="cmd", required=True, parser_class=_Parser)
    p_confirm = sub.add_parser("confirm", help="用户已在对话中确认大纲后落盘签字")
    p_confirm.add_argument("--root", required=True)
    p_confirm.add_argument("--note", default="", help="用户确认时的要点/原话摘录")
    p_check = sub.add_parser("check", help="校验签字是否存在(hook 调用)")
    p_check.add_argument("--root", required=True)
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        sys.stderr.write("%s: error: --root 不是目录: %s\n" % (parser.prog, root))
        return EX_USAGE
    if args.cmd == "confirm":
        return cmd_confirm(root, args.note)
    return cmd_check(root)


if __name__ == "__main__":
    sys.exit(main())
