#!/usr/bin/env python3
"""split_headings.py —— 有标题路确定性机械拆分（功能② · INTERFACE §3，跨家共享）.

按 heading_manifest 偏移机械切 text[o_i:o_{i+1}]，逐字节写入 atom 文件（只切不改写）。
图注（is_caption）随所在分区走，不单切；--split-to-level 控制拆到多深（level<=N 才作切点）。
只写 atom 文件 + split_manifest.json；不改 draft_import.md / heading_manifest.json。

退出码（INTERFACE §3）：
  0  成功
  1  IO 类硬错
  2  用法错 / text 或 headings 缺失 / headings 为空 / char_offset 越界（畸形真值）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

CITATION_RE = re.compile(r"\[(\d+(?:\s*[-,]\s*\d+)*)\]")
NUM_PREFIX_RE = re.compile(r"^\s*(\d+(?:[.\-]\d+)*)")
CH_PREFIX_RE = re.compile(r"^\s*第\s*(\d+)\s*章")  # 中文"第X章"命名兜底：只认"章"，不含 节/篇/部


def cut_offsets(headings, split_to_level=None):
    """切点选择的单一真源（INTERFACE §7 F1）——split_headings 与 split_audit 都调它，物理杜绝切点漂移。

    切点 = not is_caption 且 (split_to_level is None 或 level<=split_to_level) 的标题，
    按 char_offset 升序返回这些切点标题对象（各自 char_offset 即区间边界）。
    split_to_level=None → 不设层级上限（切所有非图注标题，等价旧 split_audit 行为）。
    """
    cut = [h for h in headings
           if not h.get("is_caption")
           and (split_to_level is None or h.get("level", 1) <= split_to_level)]
    return sorted(cut, key=lambda h: h.get("char_offset", 0))


def has_preamble(text, cuts):
    """前导区间的单一真源（INTERFACE §9）——split_headings 产前导 atom、split_audit 加前导区间都调它，
    物理杜绝两脚本判据分叉。首标题前 text[0:cuts[0]] 有非空正文 → True（该区间纳入为前导 atom）。"""
    return bool(cuts) and cuts[0] > 0 and bool(text[:cuts[0]].strip())


def _die(code, msg):
    sys.stderr.write(msg.rstrip() + "\n")
    sys.exit(code)


def _name_for(tmpl, i, htext, seen):
    m = NUM_PREFIX_RE.match(htext or "")
    cm = CH_PREFIX_RE.match(htext or "") if not m else None
    if m:
        comps = re.split(r"[.\-]", m.group(1))
    else:
        comps = [cm.group(1)] if cm else []
    major = comps[0] if comps else str(i + 1)
    minor = "_".join(comps[1:]) if len(comps) > 1 else "0"
    short = re.sub(r"[\\/:*?\"<>|\s]+", "", (htext or ""))[:20] or ("s%02d" % i)
    keys = {"major": major, "minor": minor, "index": i, "i": i, "n": i + 1,
            "group": major, "原编号": (m.group(1) if m else (cm.group(1) if cm else str(i + 1))),
            "标题简称": short, "title": short}
    try:
        name = tmpl.format(**keys)
    except (KeyError, IndexError, ValueError):
        name = "section_%02d.md" % i
    if name in seen:  # ponytail: dedup 保证唯一，防同前缀标题（如 2.1.1 / 2.1.2）撞名
        stem, ext = os.path.splitext(name)
        name = "%s_%02d%s" % (stem, i, ext)
    seen.add(name)
    return name


def main(argv=None):
    ap = argparse.ArgumentParser(description="有标题路确定性机械拆分")
    ap.add_argument("--text", required=True)
    ap.add_argument("--headings", required=True)
    ap.add_argument("--atoms-dir", required=True)
    ap.add_argument("--naming", required=True)
    ap.add_argument("--split-to-level", type=int, required=True)
    ap.add_argument("--manifest-out", required=True)
    args = ap.parse_args(argv)

    if not os.path.isfile(args.text):
        _die(2, "text not found: %s" % args.text)
    if not os.path.isfile(args.headings):
        _die(2, "headings not found: %s" % args.headings)
    try:
        with open(args.text, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        _die(1, "cannot read text: %s" % e)
    try:
        with open(args.headings, encoding="utf-8") as f:
            hd = json.load(f)
    except (OSError, ValueError) as e:
        _die(2, "malformed headings json: %s" % e)

    headings = hd.get("headings")
    if not isinstance(headings, list) or not headings:
        _die(2, "headings empty or missing (should not reach 有标题路)")

    # 越界/畸形 char_offset → 拒绝（畸形真值）
    tlen = len(text)
    for h in headings:
        off = h.get("char_offset")
        if not isinstance(off, int) or off < 0 or off > tlen:
            _die(2, "char_offset out of range: %r" % off)

    # 切点 = 非图注 且 level<=split-to-level 的标题（共享真源 cut_offsets，与 split_audit 同口径）
    cut_headings = cut_offsets(headings, args.split_to_level)
    if not cut_headings:
        _die(2, "no cut points at split-to-level=%d" % args.split_to_level)

    cuts = [h["char_offset"] for h in cut_headings]
    # §9：首个切点之前的非空正文（摘要/关键词/无编号引言）纳入为前导 atom（frontmatter），
    # 不再报错、不丢。前导区间 [0:cuts[0]] 前插为 region 0，其余各标题 atom 顺延。
    pre = has_preamble(text, cuts)
    bounds = ([0] if pre else []) + cuts + [tlen]
    # region_headings[i] is None → 前导 frontmatter atom；否则为对应切点标题
    region_headings = ([None] if pre else []) + cut_headings
    captions = [h for h in headings if h.get("is_caption")]

    try:
        os.makedirs(args.atoms_dir, exist_ok=True)
        os.makedirs(os.path.dirname(os.path.abspath(args.manifest_out)), exist_ok=True)
    except OSError as e:
        _die(1, "cannot create output dirs: %s" % e)

    seen = set()
    atoms = []
    try:
        for i, h in enumerate(region_headings):
            start, end = bounds[i], bounds[i + 1]
            chunk = text[start:end]
            if h is None:  # §9 前导 frontmatter atom（title 标 frontmatter、level 0）
                name = "section_00_frontmatter.md"
                seen.add(name)
                title, level = "frontmatter", 0
            elif h.get("kind") == "front_abstract":  # §10 前置块2 摘要+关键词+图形摘要
                name = "section_00b_abstract.md"
                seen.add(name)
                title, level = h["text"], h.get("level", 0)
            elif h.get("kind") == "back_matter":  # §10 后置块 致谢/基金/CoI/贡献（合成一个 atom）
                name = "section_zz_backmatter.md"
                seen.add(name)
                title, level = h["text"], h.get("level", 0)
            else:
                name = _name_for(args.naming, i, h["text"], seen)
                title, level = h["text"], h.get("level", 1)
            fpath = os.path.join(args.atoms_dir, name)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(chunk)
            fig_ids = [c["text"] for c in captions if start <= c["char_offset"] < end]
            cites = sorted({int(n) for mt in CITATION_RE.findall(chunk)
                            for n in re.split(r"[-,]", mt) if n.strip().isdigit()})
            atoms.append({
                "id": os.path.splitext(name)[0],
                "file": os.path.join(args.atoms_dir, name),
                "title": title,
                "heading_level": level,
                "char_start": start,
                "char_end": end,
                "figure_ids": fig_ids,
                "citation_numbers": cites,
            })
    except OSError as e:
        _die(1, "cannot write atom file: %s" % e)

    manifest = {"source_file": hd.get("text_file", args.text),
                "offsets_source": "heading_manifest", "atoms": atoms}
    with open(args.manifest_out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    sys.stdout.write(json.dumps(
        {"ok": True, "exit": 0, "atoms": len(atoms)}, ensure_ascii=False) + "\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
