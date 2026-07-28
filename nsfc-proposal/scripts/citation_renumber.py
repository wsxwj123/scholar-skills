#!/usr/bin/env python3
# citation_renumber.py —— nsfc-proposal 认键翻号 + 去重并表（P1 scoped，INTERFACE §3）
#
# nsfc 引文规则4：编号只在 P1（citation numbering restricted to P1，SKILL.md:108）。
# 故本脚本只作用于 sections/P1_立项依据.md 与 data/literature_index.json，不涉及别节。
# nsfc 无 reference_renderer：编号按「P1 正文首现序」分配（对齐 04_文献管理.md §4.4 矩阵检查
# 第 3 项「REF 顺序 == P1 首次引用顺序」），非 sci2doc 的 id 数字序。
#
# 两个子命令：
#   merge-refs  去重并表 new_refs（DOI→PMID→归一标题三档）→ 落 data/literature_index.json，
#               新条目 used_in_sections=["P1_立项依据"]；记 new:slug→真id 映射到 .newref_map.json
#   renumber    P1 正文 [@key]→连续 [N]，按首现序；同步把命中条目的 ref_number 设为该序号
#
# 退出码：0=OK；2=用法错/校验不过/文件畸形（renumber/merge-refs 无 1 态）。
# 账本主会话独写：本脚本是主会话侧脚本，撰写子代理绝不调用它。原子写（tempfile+os.replace）。

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone

KEY_RE = re.compile(r"\[@([A-Za-z0-9:_\-]+)\]")          # 合法引用键
ANY_AT_RE = re.compile(r"\[@([^\]]*)\]")                 # 任意 [@...]（含畸形），查畸形键
KEY_CHARS_RE = re.compile(r"^[A-Za-z0-9:_\-]+$")

P1_SECTION = "P1_立项依据"


def die(msg, code=2):
    sys.stderr.write(msg + "\n")
    sys.exit(code)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def atomic_dump(path, data):
    """原子写 JSON（tempfile 同目录 + fsync + os.replace），写一半崩溃不毁账本。"""
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def atomic_text(path, text):
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def norm_doi(doi):
    if not doi:
        return ""
    d = str(doi).strip().lower()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
    d = re.sub(r"^doi:\s*", "", d)
    return d.rstrip("/.")


def norm_pmid(pmid):
    return re.sub(r"\D", "", str(pmid)) if pmid else ""


def norm_title(title):
    if not title:
        return ""
    return re.sub(r"[^a-z0-9]+", "", str(title).lower())


def lit_path(root):
    return os.path.join(root, "data", "literature_index.json")


def load_index(root):
    """nsfc literature_index 是 dict {metadata, entries}。缺/畸形/非 dict → exit2。"""
    path = lit_path(root)
    if not os.path.isfile(path):
        die("literature_index 缺失或非数组")
    try:
        data = load_json(path)
    except Exception:
        die("literature_index 缺失或非数组")
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        die("literature_index 缺失或非数组")
    return path, data


def next_ref_id(entries):
    mx = 0
    for e in entries:
        m = re.search(r"\d+", str(e.get("id", "")))
        if m:
            mx = max(mx, int(m.group()))
    return "L-%03d" % (mx + 1)


def find_existing(entry_new, entries):
    """三档去重（同 sci2doc 语义）：("merge",id) DOI/PMID 精确同一篇；("suspected",id) 仅标题
    命中无强标识符确认（交人工，不自动合并）；(None,None) 真没命中或标识符明确冲突（作新条目）。"""
    nd = norm_doi(entry_new.get("doi"))
    np_ = norm_pmid(entry_new.get("pmid"))
    nt = norm_title(entry_new.get("title"))
    for e in entries:
        if nd and norm_doi(e.get("doi")) == nd:
            return ("merge", e.get("id"))
    for e in entries:
        if np_ and norm_pmid(e.get("pmid")) == np_:
            return ("merge", e.get("id"))
    for e in entries:
        if not (nt and norm_title(e.get("title")) == nt):
            continue
        ed = norm_doi(e.get("doi"))
        ep = norm_pmid(e.get("pmid"))
        if nd and ed and nd != ed:
            continue
        if np_ and ep and np_ != ep:
            continue
        return ("suspected", e.get("id"))
    return (None, None)


# ---------------------------------------------------------------------------
# merge-refs
# ---------------------------------------------------------------------------

def cmd_merge_refs(args):
    root = args.root
    ret_path = args.ret or os.path.join(root, ".write_return_P1.json")

    if not os.path.isfile(ret_path):
        die("文件不存在: %s" % ret_path)
    try:
        ret = load_json(ret_path)
    except Exception:
        die("返回必须是 JSON 对象（畸形 JSON）")
    if not isinstance(ret, dict):
        die("返回必须是 JSON 对象")

    new_refs = ret.get("new_refs")
    if not isinstance(new_refs, list):
        die("new_refs 非数组")

    index_path, index = load_index(root)
    entries = index["entries"]

    # nsfc P1-scoped：新条目一律挂 P1；section_id 缺不阻断（不建矩阵，仅决定 used_in_sections）。
    section_key = ret.get("section_id") or P1_SECTION

    for nr in new_refs:
        key = nr.get("key", "")
        if not (isinstance(key, str) and key.startswith("new:")):
            die("new_refs key 非法: %r" % key)
        if not (nr.get("doi") or nr.get("pmid")):
            die("new_refs 条目缺 DOI 和 PMID: %s" % key)

    mapping = {}
    merged = 0
    deduped = 0
    suspected = []
    for nr in new_refs:
        key = nr["key"]
        verdict, hit = find_existing(nr, entries)
        if verdict == "merge":
            mapping[key] = hit
            deduped += 1
            # 复用命中条目也确保挂到 P1（幂等）
            for e in entries:
                if e.get("id") == hit and section_key not in (e.get("used_in_sections") or []):
                    e.setdefault("used_in_sections", []).append(section_key)
        else:
            new_id = next_ref_id(entries)
            entries.append({
                "id": new_id,
                "title": nr.get("title", ""),
                "doi": nr.get("doi") or None,
                "pmid": nr.get("pmid") or None,
                "verified": True,
                "used_in_sections": [section_key],
                "article_type": nr.get("article_type", "unknown"),
            })
            mapping[key] = new_id
            merged += 1
            if verdict == "suspected":
                suspected.append({
                    "key": key,
                    "suspected_same_as": hit,
                    "reason": "标题命中但无共享强标识符确认，AI 判断不了，交人工裁决",
                })

    # new:slug 跨节冲突拦在落盘前（同 slug 指不同真 id 会串号）
    map_path = os.path.join(root, ".newref_map.json")
    keymap = {}
    if os.path.isfile(map_path):
        try:
            keymap = load_json(map_path)
        except Exception:
            keymap = {}
    if not isinstance(keymap, dict):
        keymap = {}
    for k, v in mapping.items():
        if k in keymap and keymap[k] != v:
            die("id 冲突: %s（slug 已映射到 %s，本次却指向 %s）" % (k, keymap[k], v))

    index.setdefault("metadata", {})["total_count"] = len(entries)
    index["metadata"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    try:
        atomic_dump(index_path, index)
    except Exception as e:
        die("literature_index 写入失败: %s" % e)

    if mapping:
        keymap.update(mapping)
        atomic_dump(map_path, keymap)

    if suspected:
        try:
            _append_dedup_review_queue(root, suspected)
        except Exception as e:
            die("dedup_review_queue 写入失败: %s" % e)

    print(json.dumps({"ok": True, "merged": merged, "deduped": deduped,
                      "mapping": mapping, "suspected_duplicates": suspected},
                     ensure_ascii=False))
    sys.exit(0)


def _append_dedup_review_queue(root, suspected):
    path = os.path.join(root, "data", "dedup_review_queue.json")
    entries = []
    if os.path.isfile(path):
        try:
            data = load_json(path)
            entries = data.get("entries", []) if isinstance(data, dict) else []
        except Exception:
            entries = []
    seen = {(e.get("key"), e.get("suspected_same_as")) for e in entries}
    for s in suspected:
        k = (s.get("key"), s.get("suspected_same_as"))
        if k in seen:
            continue
        entries.append(s)
        seen.add(k)
    atomic_dump(path, {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(entries),
        "entries": entries,
    })


# ---------------------------------------------------------------------------
# renumber（P1 scoped，首现序）
# ---------------------------------------------------------------------------

def p1_file(root):
    import glob
    matches = sorted(glob.glob(os.path.join(root, "sections", "P1_*.md")))
    return matches[0] if matches else None


def cmd_renumber(args):
    root = args.root
    prefix = "RENUMBER_CHECK: FAIL " if args.check else ""

    def fail(msg):
        die(prefix + msg)

    _, index = load_index(root)
    entries = index["entries"]

    p1 = p1_file(root)
    if not p1:
        fail("P1 正文不存在: sections/P1_*.md")

    with open(p1, encoding="utf-8") as f:
        text = f.read()

    keymap = {}
    map_path = os.path.join(root, ".newref_map.json")
    if os.path.isfile(map_path):
        try:
            keymap = load_json(map_path)
        except Exception:
            keymap = {}

    # id 冲突检测（同一 id 两条条目 → 首现序歧义）
    id_count = {}
    for e in entries:
        id_count[e.get("id")] = id_count.get(e.get("id"), 0) + 1

    # 畸形键先拦
    for m in ANY_AT_RE.finditer(text):
        grp = m.group(1)
        if not grp or not KEY_CHARS_RE.match(grp):
            fail("畸形引用键: %s" % m.group(0))

    # 首现序收集：按正文出现顺序，dedup by 解析后的真 id
    order_ids = []
    key_to_id = {}
    for m in KEY_RE.finditer(text):
        key = m.group(1)
        if key not in key_to_id:
            if key.startswith("new:"):
                rid = keymap.get(key)
                if not rid or rid not in id_count:
                    fail("未知引用键: %s（先 merge-refs 再翻号）" % key)
            else:
                if key not in id_count:
                    fail("未知引用键: %s（先 merge-refs 再翻号）" % key)
                rid = key
            if id_count.get(rid, 0) > 1:
                fail("id 冲突: %s" % rid)
            key_to_id[key] = rid
        rid = key_to_id[key]
        if rid not in order_ids:
            order_ids.append(rid)

    id_to_num = {rid: i for i, rid in enumerate(order_ids, start=1)}

    if args.check:
        print(json.dumps({"ok": True, "section": "P1", "renumbered": len(key_to_id),
                          "mapping": id_to_num}, ensure_ascii=False))
        sys.exit(0)

    def repl(m):
        return "[%d]" % id_to_num[key_to_id[m.group(1)]]

    new_text, renumbered = KEY_RE.subn(repl, text)

    # 同步 ref_number（首现序）+ 确保挂 P1；账本主会话单写
    by_id = {e.get("id"): e for e in entries}
    for rid, num in id_to_num.items():
        e = by_id.get(rid)
        if e is not None:
            e["ref_number"] = num
            if P1_SECTION not in (e.get("used_in_sections") or []):
                e.setdefault("used_in_sections", []).append(P1_SECTION)

    if args.in_place:
        atomic_text(p1, new_text)
        atomic_dump(lit_path(root), index)
    else:
        out_dir = args.out_dir or os.path.join(root, "renumber_out")
        atomic_text(os.path.join(out_dir, os.path.basename(p1)), new_text)

    print(json.dumps({"ok": True, "section": "P1", "renumbered": renumbered,
                      "mapping": id_to_num}, ensure_ascii=False))
    sys.exit(0)


def main():
    p = argparse.ArgumentParser(description="nsfc P1 认键翻号 + 去重并表")
    sub = p.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("merge-refs", help="去重并表 new_refs（新条目挂 P1）")
    m.add_argument("--root", required=True)
    m.add_argument("--return", dest="ret", default=None)

    r = sub.add_parser("renumber", help="P1 正文 [@key]→连续 [N]（首现序）")
    r.add_argument("--root", required=True)
    r.add_argument("--out-dir", dest="out_dir", default=None)
    r.add_argument("--in-place", dest="in_place", action="store_true")
    r.add_argument("--check", action="store_true")

    args = p.parse_args()
    if not os.path.isdir(args.root):
        die("root not a directory: %s" % args.root)

    if args.cmd == "merge-refs":
        cmd_merge_refs(args)
    elif args.cmd == "renumber":
        cmd_renumber(args)


if __name__ == "__main__":
    main()
