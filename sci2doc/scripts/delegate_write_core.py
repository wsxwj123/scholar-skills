#!/usr/bin/env python3
# delegate_write_core.py —— 撰写编排共享核心（八家/四家共用，四家逐字节一致）
#
# 试点批 sci2doc 的 delegate_write 逻辑抽到这里，做成四家共用核心。各家账本从哪取、
# 体裁差异（section 形态 / 本节文献切片来源 / 大纲文件）全部经 config 传入，核心不写死某家路径。
#
# 子命令：
#   pack-write   主会话生成撰写任务包 .write_task_<section>.json（本节原料嵌入 + 全局框架给路径，INTERFACE §1）
#   verify-write 机械校验撰写子代理返回 .write_return_<section>.json（V1-V9，编号权焊死保险 V2/V3，INTERFACE §2）
#   pack-prep    主会话生成备料任务包 .prep_task_<section>.json（比撰写包小，INTERFACE §2A）
#
# 退出码：0=OK；1=verify 校验不过（fail-closed）；2=用法错/文件不存在/JSON 畸形。
#
# 薄封装用法（各家 scripts/delegate_write.py）——数据布局全由 config 声明，核心不写死某家：
#   from delegate_write_core import main
#   main({
#     "family": "...", "section_regex": ...,
#     "outline_files": [...],            # 大纲候选文件；取第一个存在且含 sections 列表的
#     "outline_id_field": "section_id",  # 大纲里节标识字段（gsw storyline 用 "id"）
#     "index_path": "literature_index.json",  # 相对根；rw/nsfc 在 "data/..."
#     "index_shape": "root_list",        # 或 "data_dict"（dict {metadata, entries:[...]}）
#     "index_entries_key": "entries",    # index_shape=data_dict 时取哪个键
#     "index_id_field": "id",            # index 条目主键（rw=global_id / gsw=citation_number）
#     "lit_section": {"mode": "matrix_rows"|"matrix_map"|"matrix_related"|"index_used_in",
#                     "file": "...",            # 矩阵文件相对路径（index_used_in 为 None）
#                     "id_field": "id",         # 矩阵行 ref 主键（rw=global_id）
#                     "section_field": "section_id",       # matrix_rows 行的节字段
#                     "related_field": "related_sections"} # matrix_related 行的多节字段
#   })

import argparse
import hashlib
import json
import os
import re
import sys

# sci2doc/GSW/RW 默认 section 形态（点分数字）；nsfc 走 config 覆盖为 ^P\d+$。
SECTION_RE = re.compile(r"^\d+(\.\d+)*$")
KEY_RE = re.compile(r"\[@([A-Za-z0-9:_\-]+)\]")
# 裸数字引用：[5] / [5,6] / [5-7]（中文标记 [数据来源]/[图] 等不含数字，不命中）
BARE_NUM_RE = re.compile(r"\[\s*\d+(\s*[-,，]\s*\d+)*\s*\]")


def die(msg, code=2):
    sys.stderr.write(msg + "\n")
    sys.exit(code)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _section_re(config):
    pat = (config or {}).get("section_regex")
    return re.compile(pat) if pat else SECTION_RE


def _outline_files(config):
    return (config or {}).get("outline_files") or ["project_state.json", "storyline.json"]


def _outline_id_field(config):
    """各家大纲里节标识字段名：sci2doc/rw/nsfc=section_id；gsw storyline=id。"""
    return (config or {}).get("outline_id_field", "section_id")


def _index_path(config):
    return (config or {}).get("index_path", "literature_index.json")


def _index_id_field(config):
    """literature_index 条目主键字段：sci2doc/nsfc=id；rw=global_id；gsw=citation_number。"""
    return (config or {}).get("index_id_field", "id")


def load_outline(root, config=None):
    """从 config 指定的大纲文件（默认 project_state.json / storyline.json）读 sections 列表。"""
    for fn in _outline_files(config):
        p = os.path.join(root, fn)
        if os.path.isfile(p):
            try:
                data = load_json(p)
            except Exception:
                die("outline JSON 畸形: %s" % fn)
            secs = data.get("sections") if isinstance(data, dict) else data
            if isinstance(secs, list):
                return secs
    return []


def _find_section(sections, section, config):
    """按 config 指定的 outline_id_field 在大纲里找本节（gsw 用 id，其余用 section_id）。"""
    oid = _outline_id_field(config)
    return next((s for s in sections if s.get(oid) == section), None)


def _load_lit(root, config=None):
    """按 config 读 literature_index：缺→[]；畸形→exit2（承重账本不容 JSON 坏）。

    index_path 相对根路径（rw/nsfc 在 data/ 下）；index_shape:
      root_list  条目就是顶层 list（sci2doc/gsw/rw）
      data_dict  dict {metadata, entries:[...]}，取 entries（nsfc）
    """
    cfg = config or {}
    try:
        data = load_json(os.path.join(root, _index_path(cfg)))
    except FileNotFoundError:
        return []
    except Exception:
        die("literature_index JSON 畸形")
    if cfg.get("index_shape") == "data_dict":
        entries = data.get(cfg.get("index_entries_key", "entries")) if isinstance(data, dict) else None
        return entries if isinstance(entries, list) else []
    return data if isinstance(data, list) else []


def resolve_section_refs(root, section, config, lit):
    """按各家 config 解析"分给本节的文献"，返回 [(ref_id, matrix_row, lit_entry)]。

    行/条目字段名全经 config 取（index_id_field / lit_section.id_field / section_field /
    related_field），核心不写死某家字段。四种 mode（§2.6/§7 四家切片来源）：
      matrix_rows   矩阵行按 row[section_field]==section 切（sci2doc chapter_matrix；
                    rw data/synthesis_matrix，行 {global_id, section_id} 单值，故也走本 mode）
      matrix_map    gsw：literature_matrix.json，section→refs 映射表（ref 可为 int）
      matrix_related 矩阵行按 row[related_field] 含 section 切（当前无家使用，保留通用）
      index_used_in nsfc：无独立矩阵，literature_index entries[].used_in_sections 含 section 过滤
    矩阵文件缺/畸形 → 当空处理（不炸；承重防线在承重核证侧，不在切片侧）。matrix_row 无则为 {}。
    """
    cfg = (config or {}).get("lit_section") or {}
    mode = cfg.get("mode", "matrix_rows")
    id_field = _index_id_field(config)              # index 条目主键（join 用）
    row_id = cfg.get("id_field", "id")              # 矩阵行的 ref 主键：rw=global_id
    section_field = cfg.get("section_field", "section_id")   # 矩阵行的节字段
    related_field = cfg.get("related_field", "related_sections")
    lit_by_id = {e.get(id_field): e for e in lit}

    if mode == "index_used_in":
        out = []
        for e in lit:
            if section in (e.get("used_in_sections") or []):
                out.append((e.get(id_field), {}, e))
        return out

    # 其余三种 mode 读矩阵文件
    fname = cfg.get("file")
    matrix = []
    if fname:
        try:
            matrix = load_json(os.path.join(root, fname))
        except Exception:
            matrix = []

    if mode == "matrix_map":
        # {section: [ids]} 或 {section: [{id:..}]} 或 {"sections": {section: [...]}}
        # ref 可为标量（gsw citation_number 是 int）或 dict。
        m = matrix if isinstance(matrix, dict) else {}
        refs = m.get(section)
        if refs is None:
            refs = (m.get("sections") or {}).get(section) if isinstance(m.get("sections"), dict) else None
        refs = refs or []
        out = []
        for r in refs:
            rid = r if isinstance(r, (str, int)) else (r.get(row_id) if isinstance(r, dict) else None)
            if rid is not None:
                out.append((rid, r if isinstance(r, dict) else {}, lit_by_id.get(rid, {})))
        return out

    rows = matrix if isinstance(matrix, list) else (matrix.get("rows", []) if isinstance(matrix, dict) else [])

    if mode == "matrix_related":
        out = []
        for mr in rows:
            if section in (mr.get(related_field) or []):
                rid = mr.get(row_id)
                out.append((rid, mr, lit_by_id.get(rid, {})))
        return out

    # 默认 matrix_rows（sci2doc 单值 section_field / row_id；rw 同形态但 global_id + data/ 矩阵）
    out = []
    for mr in rows:
        if mr.get(section_field) == section:
            rid = mr.get(row_id)
            out.append((rid, mr, lit_by_id.get(rid, {})))
    return out


# ---------------------------------------------------------------------------
# pack-write
# ---------------------------------------------------------------------------

STYLE_RULES = {
    "forbidden": ["破折号", "scare quotes", "解释性冒号", "AI 禁词"],
    "citation": "正文引用只写 [@key]（key=literature_index 的 id 或 new:<slug>），绝不写裸数字 [5]",
    "table": "三线表用管道语法",
}
ROLE = ("撰写工人：看不到别节写作过程，只按本任务包写本节；全局框架按需 Read refs 路径"
        "（只读，禁写任何账本文件）；承重句只准挂内嵌 certified_claims 里的 ref_key。")
PREP_ROLE = ("备料工人：只判本节承重句 ↔ 引文支撑，产草案（.claim_evidence_draft_X.Y.json）；"
             "禁写账本、禁联网；evidence_quote 只能引账本 abstract 原文（子串）；user_confirmed 一律置 false。")


def _lit_section_for_write(pairs):
    """pack-write 的 lit_section 全条形态（INTERFACE §1.2）。"""
    lit_section = []
    for rid, mr, e in pairs:
        lit_section.append({
            "key": rid,
            "title": e.get("title") or mr.get("title", ""),
            "authors": e.get("authors", []),
            "year": e.get("year"),
            "journal": e.get("journal", ""),
            "doi": e.get("doi"),
            "pmid": e.get("pmid"),
            "abstract": e.get("abstract") or mr.get("abstract", ""),
            "article_type": e.get("article_type", mr.get("article_type", "unknown")),
            "current_number": e.get("current_number"),
        })
    return lit_section


def cmd_pack_write(args, config):
    section = args.section
    root = args.root
    if not _section_re(config).match(section):
        die("section 格式非法: %s" % section)
    if not os.path.isdir(root):
        die("root not a directory: %s" % root)

    sections = load_outline(root, config)
    sec = _find_section(sections, section, config)
    if sec is None:
        die("outline has no section: %s" % section)

    lit = _load_lit(root, config)
    try:
        claim_rows = load_json(os.path.join(root, "claim_evidence.json"))
    except FileNotFoundError:
        claim_rows = []
    except Exception:
        die("claim_evidence JSON 畸形")
    if isinstance(claim_rows, dict):
        claim_rows = claim_rows.get("claims", claim_rows.get("rows", []))
    if not isinstance(claim_rows, list):
        claim_rows = []

    load_bearing_outline = sec.get("load_bearing_claims") or []
    sec_rows = [r for r in claim_rows if r.get("section") == section]
    sec_lb_rows = [r for r in sec_rows if r.get("is_load_bearing")]

    # 承重句核证机械拦（INTERFACE §1.3 后两条）
    if load_bearing_outline and not sec_rows:
        die("本节有承重论点但缺 claim_evidence，先建证据对")
    if any(not r.get("user_confirmed") for r in sec_lb_rows):
        die("certified_claims 未完成人工核证")

    certified = [
        {"claim_id": r.get("claim_id", ""), "claim_sentence": r.get("claim_sentence", ""),
         "ref_key": r.get("ref_id", ""), "verdict": r.get("verdict", ""),
         "evidence_quote": r.get("evidence_quote", "")}
        for r in sec_lb_rows
        if r.get("user_confirmed") and r.get("verdict") in ("support", "weak")
    ]

    pairs = resolve_section_refs(root, section, config, lit)
    lit_section = _lit_section_for_write(pairs)
    warning = "lit_section empty" if not lit_section else None

    matrix_file = ((config or {}).get("lit_section") or {}).get("file")
    outline_files = _outline_files(config)
    outline_path = os.path.join(root, outline_files[0])

    embed = {
        "role": ROLE,
        "section_id": section,
        "section_target": {
            "title": sec.get("title", ""),
            "core_argument": sec.get("core_argument", ""),
            "scientific_question": sec.get("scientific_question", ""),
            "load_bearing_claims": load_bearing_outline,
            "target_words": sec.get("target_words"),
        },
        "certified_claims": certified,
        "lit_section": lit_section,
        "figures": [],
        "neighbor_digest": [],
        "abbrev_table": [],
        "data_sources": [],
        "style_rules": STYLE_RULES,
        "return_contract": {
            "return_path": ".write_return_%s.json" % section,
            "fields": ["section_id", "markdown", "new_refs", "new_abbrev",
                       "new_claims", "placeholders"],
        },
    }
    refs = {
        "outline_path": outline_path,
        "lit_index_path": os.path.join(root, _index_path(config)),
        "matrix_path": os.path.join(root, matrix_file) if matrix_file else None,
        "progress_path": outline_path,
    }
    pack = {"section_id": section, "embed": embed, "refs": refs}

    out = args.out or os.path.join(root, ".write_task_%s.json" % section)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(pack, f, ensure_ascii=False, indent=2)

    sys.stderr.write("TASK_PATH=%s\n" % os.path.abspath(out))
    res = {"ok": True, "section": section, "task_path": out}
    if warning:
        res["warning"] = warning
    print(json.dumps(res, ensure_ascii=False))
    sys.exit(0)


# ---------------------------------------------------------------------------
# pack-prep（INTERFACE §2A.2）
# ---------------------------------------------------------------------------

def _claim_set_hash(load_bearing_outline):
    payload = json.dumps(sorted(load_bearing_outline), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cmd_pack_prep(args, config):
    section = args.section
    root = args.root
    # 错误契约同 pack-write（§2A.2）：section 格式非法→2；root 非目录→2；本节不在 outline→2。
    if not _section_re(config).match(section):
        die("section 格式非法: %s" % section)
    if not os.path.isdir(root):
        die("root not a directory: %s" % root)

    sections = load_outline(root, config)
    sec = _find_section(sections, section, config)
    if sec is None:
        die("outline has no section: %s" % section)

    lit = _load_lit(root, config)
    load_bearing_outline = sec.get("load_bearing_claims") or []
    pairs = resolve_section_refs(root, section, config, lit)

    lit_section = [
        {"ref_id": rid,
         "title": e.get("title") or mr.get("title", ""),
         "abstract": e.get("abstract") or mr.get("abstract", ""),
         "role": mr.get("role", "")}
        for rid, mr, e in pairs
    ]
    warning = "lit_section empty" if not lit_section else None

    pack = {
        "section_id": section,
        "role": PREP_ROLE,
        "section_target": {
            "core_argument": sec.get("core_argument", ""),
            "load_bearing_claims": load_bearing_outline,
        },
        "lit_section": lit_section,
        "outline_claim_set_hash": _claim_set_hash(load_bearing_outline),
        "return_contract": {
            "return_path": ".claim_evidence_draft_%s.json" % section,
            "schema": {
                "top": '{"section":"X.Y","claims":[...]}',
                "claim": ["section", "claim_sentence", "is_load_bearing", "claim_kind",
                          "ref_id", "retrieved_abstract", "verdict", "evidence_quote",
                          "user_confirmed"],
                "note": "verdict∈support/weak/contradict/unknown；user_confirmed 一律 false；"
                        "evidence_quote 必须是账本 abstract 子串；空草案 {\"claims\":[]} 合法。",
            },
        },
    }

    out = args.out or os.path.join(root, ".prep_task_%s.json" % section)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(pack, f, ensure_ascii=False, indent=2)

    sys.stderr.write("TASK_PATH=%s\n" % os.path.abspath(out))
    res = {"ok": True, "section": section, "task_path": out}
    if warning:
        res["warning"] = warning
    print(json.dumps(res, ensure_ascii=False))
    sys.exit(0)


# ---------------------------------------------------------------------------
# verify-write（家无关：只读任务包内嵌 lit_section + literature_index，INTERFACE §2）
# ---------------------------------------------------------------------------

def _fail1(msg):
    sys.stderr.write("VERIFY_WRITE: FAIL %s\n" % msg)
    print(json.dumps({"ok": False, "problems": [msg]}, ensure_ascii=False))
    sys.exit(1)


def cmd_verify_write(args, config):
    section = args.section
    root = args.root
    task_path = args.task or os.path.join(root, ".write_task_%s.json" % section)
    ret_path = args.ret or os.path.join(root, ".write_return_%s.json" % section)

    # V9：文件存在
    if not os.path.isfile(ret_path):
        die("文件不存在: %s" % ret_path)
    if not os.path.isfile(task_path):
        die("文件不存在: %s" % task_path)

    try:
        ret = load_json(ret_path)
    except Exception:
        die("返回必须是 JSON 对象（畸形 JSON）")
    task = load_json(task_path)

    # V8：JSON 对象 + 有 markdown 字段
    if not isinstance(ret, dict):
        die("返回必须是 JSON 对象")
    if "markdown" not in ret:
        die("缺 markdown 字段")

    markdown = ret.get("markdown")
    new_refs = ret.get("new_refs") or []
    new_claims = ret.get("new_claims") or []

    if not isinstance(new_refs, list):
        die("new_refs 非数组")
    if not isinstance(new_claims, list):
        die("new_claims 非数组")

    task_section_id = task.get("section_id") or task.get("embed", {}).get("section_id")
    lit_section = task.get("embed", {}).get("lit_section") or task.get("lit_section") or []
    if not isinstance(lit_section, list):
        die("lit_section 非数组")

    lit = _load_lit(root, config)
    id_field = _index_id_field(config)

    # V1：markdown 非空
    if not (isinstance(markdown, str) and markdown.strip()):
        _fail1("markdown 为空")

    # V2：无裸数字引用
    if BARE_NUM_RE.search(markdown):
        _fail1("正文出现裸数字引用，只允许 [@key]")

    # V5：new_refs key 合法（new: 前缀）且唯一——先于 V3
    seen = set()
    for nr in new_refs:
        key = nr.get("key", "")
        if not (isinstance(key, str) and key.startswith("new:")) or key in seen:
            _fail1("new_refs key 非法或重复")
        seen.add(key)
    # V4：new_refs 每条 doi/pmid 至少一个
    for nr in new_refs:
        if not (nr.get("doi") or nr.get("pmid")):
            _fail1("new_refs 条目缺 DOI 和 PMID")

    verified_ids = {e.get(id_field) for e in lit if e.get("verified", True)}
    lit_section_keys = {item.get("key") for item in lit_section}
    valid_cite = verified_ids | lit_section_keys
    new_key_set = {nr.get("key") for nr in new_refs}

    # V3：每个 [@key] 可解析
    for key in KEY_RE.findall(markdown):
        if key.startswith("new:"):
            if key not in new_key_set:
                _fail1("引用键无法解析: %s" % key)
        elif key not in valid_cite:
            _fail1("引用键无法解析: %s" % key)

    # V6：section_id 一致
    if ret.get("section_id") != task_section_id:
        _fail1("section_id 不匹配")

    # V7：new_claims 的 ref_key 可解析（纯结构，非承重语义门）
    all_ids = {e.get(id_field) for e in lit} | new_key_set
    for nc in new_claims:
        rk = nc.get("ref_key")
        if rk not in all_ids:
            _fail1("new_claims 的 ref_key 无法解析: %s" % rk)

    print(json.dumps({"ok": True, "section": section,
                      "checks": ["V1", "V2", "V3", "V4", "V5", "V6", "V7"]},
                     ensure_ascii=False))
    sys.exit(0)


# ---------------------------------------------------------------------------
# entry
# ---------------------------------------------------------------------------

def main(config):
    p = argparse.ArgumentParser(description="撰写任务包 + 备料任务包 + 返回校验（共享核心）")
    sub = p.add_subparsers(dest="cmd", required=True)

    pw = sub.add_parser("pack-write")
    pw.add_argument("--section", required=True)
    pw.add_argument("--root", required=True)
    pw.add_argument("--out", default=None)

    pp = sub.add_parser("pack-prep")
    pp.add_argument("--section", required=True)
    pp.add_argument("--root", required=True)
    pp.add_argument("--out", default=None)

    vw = sub.add_parser("verify-write")
    vw.add_argument("--section", required=True)
    vw.add_argument("--root", required=True)
    vw.add_argument("--return", dest="ret", default=None)
    vw.add_argument("--task", dest="task", default=None)

    args = p.parse_args()
    if args.cmd == "pack-write":
        cmd_pack_write(args, config)
    elif args.cmd == "pack-prep":
        cmd_pack_prep(args, config)
    elif args.cmd == "verify-write":
        cmd_verify_write(args, config)
