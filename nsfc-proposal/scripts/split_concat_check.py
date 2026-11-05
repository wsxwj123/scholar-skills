#!/usr/bin/env python3
"""split_concat_check.py —— 拆分后的逐字节拼接核对（Polish 0.3，nsfc-proposal 2.42.0 新增）.

按 split_manifest.json 的 atoms 顺序读每个小文件的原始字节，拼起来与 --text 的原始字节
逐字节比较，证明拆分没有改动任何字符。另查小文件目录里不在清单里的 .md 文件。
split_audit.py 会归一空白（换行改空格、删末尾换行都查不出），本脚本补这个盲区。
有标题路与无标题路都跑。只读，不写任何文件。

退出码：
  0  字节完全相同且无多余文件；stdout {"ok": true, "exit": 0, "atoms", "bytes"}
  1  有问题；stdout {"ok": false, "exit": 1, "problems": [...]}，问题代码：
     BYTES_DIFFER / LENGTH_DIFFER / ATOM_MISSING / STRAY_FILE
  2  用法错 / --text 或 --manifest 缺失、读不出 / manifest 不是 JSON、atoms 不是非空列表、
     某项缺 file / 某个 file 越根（stderr 含 escapes）
人读的报错行走 stderr，以 "SPLIT_CONCAT_CHECK: " 开头。
"""
from __future__ import annotations

import sys as _sys
try:  # Windows GBK 控制台下中文报错防 UnicodeEncodeError
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import argparse
import json
import os
import sys

PREFIX = "SPLIT_CONCAT_CHECK: "


def _err(msg):
    sys.stderr.write(PREFIX + msg.rstrip() + "\n")


def _die2(msg):
    _err(msg)
    sys.exit(2)


def _emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")


def read_bytes(path, what):
    if not os.path.isfile(path):
        _die2("%s 不存在，检查路径后重跑：%s" % (what, path))
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError as e:
        _die2("%s 读不出，检查权限后重跑：%s（%s）" % (what, path, e))


def load_manifest(path):
    raw = read_bytes(path, "--manifest")
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        _die2("--manifest 不是合法 UTF-8 JSON：%s（%s）" % (path, e))
    atoms = doc.get("atoms") if isinstance(doc, dict) else None
    if not isinstance(atoms, list) or not atoms:
        _die2("--manifest 的 atoms 要是非空列表：%s" % path)
    return atoms


def resolve_atoms(atoms, root):
    """返回 [(清单里的 file, 实际路径)]；file 缺失或越根退出码 2。"""
    root_real = os.path.realpath(root)
    resolved = []
    for i, atom in enumerate(atoms):
        fp = atom.get("file") if isinstance(atom, dict) else None
        if not isinstance(fp, str) or not fp:
            _die2("--manifest 第 %d 项（序号从 0 起）缺 file。" % i)
        full = fp if os.path.isabs(fp) else os.path.join(root, fp)
        real = os.path.realpath(full)
        if real != root_real and not real.startswith(root_real + os.sep):
            _die2("manifest atom 'file' escapes --root: %s" % fp)
        resolved.append((fp, real))
    return resolved


def first_difference(expected, actual):
    """返回第一个不同字节的偏移；共同前缀全同时返回 None。"""
    n = min(len(expected), len(actual))
    if expected[:n] == actual[:n]:
        return None
    for i in range(n):
        if expected[i] != actual[i]:
            return i
    return None


def atom_at(offset, spans):
    """spans：[(atom_index, start, end)]，返回覆盖 offset 的 atom_index。"""
    for index, start, end in spans:
        if start <= offset < end:
            return index
    return spans[-1][0] if spans else None


def stray_files(resolved):
    """所有小文件所在目录里，直接位于该目录下、扩展名 .md、不在清单里的文件。"""
    listed = {real for _fp, real in resolved}
    dirs = []
    for _fp, real in resolved:
        d = os.path.dirname(real)
        if d not in dirs:
            dirs.append(d)
    found = []
    for d in dirs:
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        for name in names:
            full = os.path.join(d, name)
            if name.lower().endswith(".md") and os.path.isfile(full) and os.path.realpath(full) not in listed:
                found.append(name)
    return found


def check(text_bytes, resolved):
    problems = []
    pieces = []
    spans = []
    pos = 0
    missing = False
    for index, (fp, real) in enumerate(resolved):
        if not os.path.isfile(real):
            problems.append({"code": "ATOM_MISSING", "atom": fp})
            missing = True
            continue
        try:
            with open(real, "rb") as f:
                data = f.read()
        except OSError:
            problems.append({"code": "ATOM_MISSING", "atom": fp})
            missing = True
            continue
        pieces.append(data)
        spans.append((index, pos, pos + len(data)))
        pos += len(data)

    if not missing:
        joined = b"".join(pieces)
        diff = first_difference(text_bytes, joined)
        if diff is not None:
            index = atom_at(diff, spans)
            problems.append({"code": "BYTES_DIFFER", "atom_index": index,
                             "atom": os.path.basename(resolved[index][1]), "byte_offset": diff})
        elif len(joined) != len(text_bytes):
            problems.append({"code": "LENGTH_DIFFER",
                             "detail": "前缀全同，拼接后 %d 字节，整稿 %d 字节。"
                                       % (len(joined), len(text_bytes))})

    for name in stray_files(resolved):
        problems.append({"code": "STRAY_FILE", "file": name})
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description="拆分后逐字节拼接核对（只读）")
    ap.add_argument("--text", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv)

    text_bytes = read_bytes(args.text, "--text")
    atoms = load_manifest(args.manifest)
    resolved = resolve_atoms(atoms, args.root)
    problems = check(text_bytes, resolved)

    if problems:
        for p in problems:
            _err(" ".join("%s=%s" % (k, v) for k, v in p.items()))
        _emit({"ok": False, "exit": 1, "problems": problems})
        return 1
    _emit({"ok": True, "exit": 0, "atoms": len(resolved), "bytes": len(text_bytes)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
