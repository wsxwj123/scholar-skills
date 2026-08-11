#!/usr/bin/env python3
"""outline_manager.py —— nsfc-proposal「P1 立项依据」段落级大纲的确认与校验。

两个子命令 + 一个可 import 的纯函数入口：

  confirm --from <草稿> --root <项目根> --note "<用户确认原话>"
      校验 AI 出的草稿（tmp/outline_draft.json），通过后原子写出唯一真源
      <root>/data/outline.json，并派生 load_bearing_claims。退出码 0 / 2。

  check --root <项目根>
      只读校验「已确认且未被改动」。退出码 0（过）/ 1（不过）/ 2（参数错）。

  check(root) -> (ok, reason)
      同一份判定逻辑，供 prewrite_gate.py 与 delegate_write.py 的闸口 import。

设计约束（INTERFACE-round19 §0 不变量）：
  - 只读写 --root 子树；不联网、不读 HOME、不读环境变量。
  - 错误路径一律不落盘、不留 .tmp 残留。
  - 承重论点只有一个真源：段落上的 is_load_bearing。草稿手写 load_bearing_claims
    直接拒绝 —— 否则机器校验的账与用户读的账会分家。
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys

# 本轮唯一受管的节标识。注意它是字面量 "P1"，不是 sections/ 的文件名前缀 P1_立项依据。
MANAGED_SECTION = "P1"

OUTLINE_REL = os.path.join("data", "outline.json")

# 只应由本脚本写入的签名字段：草稿里出现任一个 = AI 试图自签，拒。
SIGNATURE_FIELDS = ("confirmed", "content_hash", "confirmed_at", "outline_claim_set_hash")
DERIVED_FIELD = "load_bearing_claims"

EX_OK = 0
EX_FAIL = 1
EX_USAGE = 2


class DraftError(Exception):
    """草稿不合格。message 里带错误码关键字，由 CLI 打到 stderr 并退 2。"""


# ---------------------------------------------------------------------------
# 哈希公式（INTERFACE §0）——两条公式都只在这里实现一次
# ---------------------------------------------------------------------------

def content_hash(sections) -> str:
    """只哈希 sections 的语义值：note / confirmed_at 变动不算大纲被改。"""
    payload = json.dumps(sections, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def claim_set_hash(claims) -> str:
    """承重指纹，与 delegate_write_core._claim_set_hash 逐字节同式（无 sha256: 前缀）。"""
    payload = json.dumps(sorted(claims), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def outline_path(root: str) -> str:
    return os.path.join(root, OUTLINE_REL)


def derive_claims(section) -> list:
    """按段落数组顺序取承重段的 conclusion。不去重、不排序 —— 去重会让指纹与段落对不上。"""
    return [p["conclusion"] for p in section.get("paragraphs", [])
            if isinstance(p, dict) and p.get("is_load_bearing") is True]


# ---------------------------------------------------------------------------
# check：只读判定（三个调用点共用）
# ---------------------------------------------------------------------------

def inspect(root: str):
    """(ok, reason, 落盘的 content_hash, 重算值)。任何异常都收成 outline_malformed。

    判定顺序固定（INTERFACE §1.2）：missing → malformed → not_confirmed → stale
    → section_missing，先命中先报。
    """
    path = outline_path(root)
    if not os.path.exists(path):
        return False, "outline_missing", None, None
    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except Exception:
        # 坏 JSON / 是目录 / 读不动，一律是「文件坏了」，不许把栈打出来。
        return False, "outline_malformed", None, None
    if not isinstance(doc, dict):
        return False, "outline_malformed", None, None

    stored = doc.get("content_hash")
    stored = stored if isinstance(stored, str) else None
    try:
        recomputed = content_hash(doc.get("sections"))
    except (TypeError, ValueError):
        # sections 里塞了不可序列化的东西 —— 同样算文件坏了
        return False, "outline_malformed", stored, None

    if doc.get("confirmed") is not True:
        return False, "outline_not_confirmed", stored, recomputed
    if stored != recomputed:
        return False, "outline_stale", stored, recomputed

    sections = doc.get("sections")
    if not isinstance(sections, list) or not any(
            isinstance(s, dict) and s.get("section_id") == MANAGED_SECTION
            for s in sections):
        return False, "outline_section_missing", stored, recomputed
    return True, None, stored, recomputed


def check(root: str):
    """(ok, reason)。纯读、不落盘、不抛异常。"""
    try:
        ok, reason, _stored, _recomputed = inspect(root)
    except Exception:
        return False, "outline_malformed"
    return ok, reason


# ---------------------------------------------------------------------------
# confirm：草稿校验
# ---------------------------------------------------------------------------

def _bad(code: str, detail: str = "") -> DraftError:
    return DraftError("%s %s" % (code, detail) if detail else code)


def _check_structure(draft):
    """错误契约 1-6 的结构与作用域部分。返回受管的那个 section。"""
    if not isinstance(draft, dict):
        raise _bad("OUTLINE_DRAFT_INVALID", "顶层必须是对象")
    sections = draft.get("sections")
    if not isinstance(sections, list) or not sections:
        raise _bad("OUTLINE_DRAFT_INVALID", "sections 必须是非空数组")
    for i, sec in enumerate(sections, 1):
        if not isinstance(sec, dict):
            raise _bad("OUTLINE_DRAFT_INVALID", "第 %d 个 section 不是对象" % i)
        if not isinstance(sec.get("section_id"), str):
            raise _bad("OUTLINE_DRAFT_INVALID", "第 %d 个 section 缺 section_id 或不是字符串" % i)
    # 先点名不受支持的节标识，再报重复：[P1, P2] 该说 P2，[P1, P1] 才说 duplicate
    for sec in sections:
        sid = sec["section_id"]
        if sid != MANAGED_SECTION:
            raise _bad("OUTLINE_SECTION_NOT_SUPPORTED",
                       "本轮只受管 %s，草稿里出现了 %r" % (MANAGED_SECTION, sid))
    if len(sections) > 1:
        raise _bad("OUTLINE_SECTION_NOT_SUPPORTED",
                   "duplicate: %s 出现了 %d 次，只允许一个条目" % (MANAGED_SECTION, len(sections)))
    return sections[0]


def _check_anti_forge(draft, section):
    """错误契约 7-8：AI 不得自签、不得手写派生字段。"""
    for field in SIGNATURE_FIELDS:
        if field in draft:
            raise _bad("OUTLINE_SELF_SIGN_FORBIDDEN",
                       "草稿顶层不得出现签名字段 %r（只能由 confirm 生成）" % field)
        if field in section:
            raise _bad("OUTLINE_SELF_SIGN_FORBIDDEN",
                       "草稿 sections[] 元素内不得出现签名字段 %r（只能由 confirm 生成）" % field)
    if DERIVED_FIELD in section:
        raise _bad("OUTLINE_DERIVED_FIELD_FORBIDDEN",
                   "%s 由承重段的 conclusion 派生，不得手写" % DERIVED_FIELD)


def _nonblank_str(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _check_granularity(section):
    """错误契约 9-12：粒度从严（D4）。段落序号一律 1 基，报错里写明第几段。"""
    paragraphs = section.get("paragraphs")
    if not isinstance(paragraphs, list) or not paragraphs:
        raise _bad("OUTLINE_PARAGRAPHS_REQUIRED", "paragraphs 必须是非空数组")
    for i, para in enumerate(paragraphs, 1):
        if not isinstance(para, dict):
            raise _bad("OUTLINE_PARAGRAPHS_REQUIRED", "第 %d 段不是对象" % i)
        for field in ("gist", "conclusion"):
            if not _nonblank_str(para.get(field)):
                raise _bad("OUTLINE_PARAGRAPHS_REQUIRED",
                           "第 %d 段的 %s 缺失或为空（每段都要写清讲什么、得出什么结论）" % (i, field))
    load_bearing = [(i, p) for i, p in enumerate(paragraphs, 1)
                    if p.get("is_load_bearing") is True]
    if not load_bearing:
        raise _bad("OUTLINE_NO_LOAD_BEARING",
                   "至少要有 1 个 is_load_bearing 为 true 的承重段（值必须是布尔 true）")
    for i, para in load_bearing:
        refs = para.get("refs")
        if not isinstance(refs, list) or not refs or not all(isinstance(r, str) for r in refs):
            raise _bad("OUTLINE_REFS_REQUIRED",
                       "第 %d 段是承重段，refs 必须是非空的字符串数组（文献 id）" % i)


def _strip_generated(draft):
    """剥掉由 confirm 生成的字段（签名 + 派生），返回新对象，不改入参。

    只在「--from 指的就是 data/outline.json 本身」时用：用户直接编辑那份被文档称作
    「唯一真源」的文件是完全正当的操作，剥完之后它就是一份普通草稿，走同一套校验。
    用户改过的内容原样保留 —— 这里只删生成物，不碰任何用户写的键。
    """
    out = {k: v for k, v in draft.items() if k not in SIGNATURE_FIELDS}
    sections = out.get("sections")
    if isinstance(sections, list):
        out["sections"] = [
            {k: v for k, v in s.items()
             if k not in SIGNATURE_FIELDS and k != DERIVED_FIELD}
            if isinstance(s, dict) else s
            for s in sections
        ]
    return out


def build_outline(draft, note: str, from_truth_source: bool = False):
    """草稿 → 落盘文档。任一校验不过抛 DraftError（此时调用方一个字节都不许写）。"""
    if from_truth_source and isinstance(draft, dict):
        draft = _strip_generated(draft)
    section = _check_structure(draft)
    _check_anti_forge(draft, section)
    _check_granularity(section)
    if not _nonblank_str(note):
        raise _bad("OUTLINE_NOTE_REQUIRED", "--note 必须给用户确认的原话摘录，AI 不得代用户确认")

    out_section = dict(section)
    out_section.setdefault("title", "")
    out_section[DERIVED_FIELD] = derive_claims(section)
    sections = [out_section]
    return {
        "confirmed": True,
        "confirmed_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "note": note,
        "content_hash": content_hash(sections),
        "sections": sections,
    }


def _atomic_write_json(path: str, payload) -> None:
    """tmp + fsync + os.replace；覆盖前把旧版留成 <path>.prev。

    fsync：这份文件是用户逐条确认出来的成果，断电丢了要重走一遍确认流程。
    .prev：防手滑覆盖（只在旧文件真的存在时留，第一次 confirm 不产生它）。
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.tmp%d" % (path, os.getpid())
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        # 备份放在 tmp 写成功之后：写不出来时不该动用户已有的文件
        if os.path.isfile(path):
            shutil.copy2(path, path + ".prev")
        os.replace(tmp, path)
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _die_usage(msg: str) -> int:
    sys.stderr.write(msg + "\n")
    return EX_USAGE


def _same_file(a: str, b: str) -> bool:
    """两个路径是不是同一个文件。用 realpath 比，软链接 / 相对路径 / ./ 前缀都算同一个。"""
    try:
        return os.path.realpath(a) == os.path.realpath(b)
    except OSError:
        return False


def cmd_confirm(args) -> int:
    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        return _die_usage("root not a directory: %s" % root)
    if not os.path.isfile(args.draft):
        return _die_usage("OUTLINE_DRAFT_MISSING 草稿不存在或不是普通文件: %s" % args.draft)
    try:
        with open(args.draft, "r", encoding="utf-8") as f:
            draft = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _die_usage("OUTLINE_DRAFT_INVALID 草稿不是合法 JSON: %s" % args.draft)
    except OSError as exc:
        return _die_usage("OUTLINE_DRAFT_MISSING 草稿读不出来: %s (%s)" % (args.draft, exc))

    path = outline_path(root)
    try:
        doc = build_outline(draft, args.note or "",
                            from_truth_source=_same_file(args.draft, path))
    except DraftError as exc:
        return _die_usage(str(exc))

    try:
        _atomic_write_json(path, doc)
    except OSError as exc:
        # 目录只读 / 文件被编辑器或网盘占用（Windows 上 os.replace 的常态失败）：
        # 报人话 + 用法错那条退出码，不要甩 traceback。
        return _die_usage("OUTLINE_WRITE_FAILED 写不进 %s：%s" % (path, exc))
    print(json.dumps({
        "ok": True,
        "outline": os.path.abspath(path),
        "sections": [MANAGED_SECTION],
        "content_hash": doc["content_hash"],
        "claim_set_hash": claim_set_hash(doc["sections"][0][DERIVED_FIELD]),
    }, ensure_ascii=False))
    return EX_OK


def cmd_check(args) -> int:
    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        return _die_usage("root not a directory: %s" % root)
    ok, reason, stored, recomputed = inspect(root)
    print(json.dumps({"ok": ok, "reason": reason,
                      "content_hash": stored, "recomputed": recomputed},
                     ensure_ascii=False))
    if ok:
        return EX_OK
    # FAIL 行走 stderr：stdout 必须保持「恰好一行 JSON」，调用方直接 json.loads 整个 stdout。
    sys.stderr.write("OUTLINE: FAIL %s - %s\n" % (reason, _remedy(reason)))
    return EX_FAIL


def _remedy(reason: str) -> str:
    return {
        "outline_missing": "还没有 P1 大纲：先出草稿给用户过目，用户点头后跑 "
                           "outline_manager.py confirm",
        "outline_malformed": "data/outline.json 坏了：修好文件，或重跑 "
                             "outline_manager.py confirm 覆盖它",
        "outline_not_confirmed": "大纲没经用户确认：跑 outline_manager.py confirm "
                                 "（AI 不得代用户确认）",
        # 🔴 这条文案必须点明「拿 data/outline.json 自己重跑」：改成的用户手改了真源，
        # 若照着去跑 --from tmp/outline_draft.json，他刚改的东西会被 AI 那份旧草稿盖掉。
        "outline_stale": "大纲被改过，需用户重新确认。改的就是 data/outline.json 本身时，"
                         "直接拿它重跑：outline_manager.py confirm "
                         "--from data/outline.json --root <项目根> --note \"<用户原话>\""
                         "（会保留你的修改，旧版自动存成 data/outline.json.prev）。"
                         "⚠️ 若改用 --from tmp/outline_draft.json，那份是 AI 的草稿，"
                         "会覆盖掉你在真源上的手改",
        "outline_section_missing": "大纲里没有 P1 这一节：确认草稿的 section_id 是 P1",
    }.get(reason, "跑 outline_manager.py check --root <项目根> 看详情")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="nsfc-proposal P1 立项依据段落级大纲：用户确认后落盘 + 开写前校验")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_confirm = sub.add_parser("confirm", help="用户确认后把草稿落成 data/outline.json")
    p_confirm.add_argument("--from", dest="draft", required=True,
                           help="草稿路径，惯例 tmp/outline_draft.json")
    p_confirm.add_argument("--root", required=True, help="项目根")
    p_confirm.add_argument("--note", default="", help="用户确认原话摘录（必填非空）")

    p_check = sub.add_parser("check", help="校验大纲已确认且未被改动")
    p_check.add_argument("--root", required=True, help="项目根")

    args = parser.parse_args(argv)
    if args.cmd == "confirm":
        return cmd_confirm(args)
    return cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
