#!/usr/bin/env python3
"""heading_locate.py —— 无标题路的标题定位（Polish 0.3.3，nsfc-proposal 2.42.0 新增）.

两个子命令，都不含任何国自然专属判断：
  lines   给整稿每一行加行号，写成 "行号<TAB>行内容"，供子代理认标题时引用行号。
  locate  读子代理交回的标题清单（行号、原句、层级），按行号定位、核对原句，
          写出与 extract_headings.py 同格式的 heading_manifest.json，
          之后由 split_headings.py 与 split_audit.py 原样切分与核验。

行的定义：读入时按文本模式处理换行（回车加换行、单独的回车都换成换行），与 split_headings.py、
split_audit.py 读同一个稿子的方式一致；然后按 U+000A 切开；文本以换行结尾时最后那个空段不算一行；
行号从 1 起；行内容不含回车。字符偏移、text_len 都按处理后的文本计，按 Python str 下标（码点），
与 extract_headings.py 的 char_offset 同口径。
第 1 行开头的 U+FEFF（BOM）不算内容：比较原句时去掉，清单里该项的 text 不含它，char_offset 仍是 0。

退出码：
  0  成功；stdout 一行 JSON
  1  locate 的清单内容错误（ITEM_INVALID / LINE_OUT_OF_RANGE / TEXT_MISMATCH /
     ORDER / LEVEL_JUMP / NO_HEADINGS），一次报全，--out 不创建、不改动
  2  用法错 / 输入文件缺失、读不出、不是 UTF-8 / 清单不是 JSON 或形状不对 / 写失败
写文件一律先写同目录临时文件再整体替换；写失败退出码 2，不留临时文件。
人读的报错行走 stderr，以 "HEADING_LOCATE: " 开头。
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
import tempfile

PREFIX = "HEADING_LOCATE: "
LEVEL_MIN = 1
LEVEL_MAX = 6
BOM = chr(0xFEFF)


def _err(msg):
    sys.stderr.write(PREFIX + msg.rstrip() + "\n")


def _die(code, msg):
    _err(msg)
    sys.exit(code)


def _emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")


def split_lines(text):
    """按 U+000A 切行；末尾换行后的空段不算一行。行内容不含换行（回车已在读入时换成换行）。"""
    parts = text.split("\n")
    if parts and parts[-1] == "":
        parts.pop()
    return parts


def strip_bom_first(lines):
    """比较与写清单用：第 1 行开头的 BOM 不算内容。偏移仍按原文算。"""
    if lines and lines[0].startswith(BOM):
        return [lines[0][1:]] + lines[1:]
    return lines


def line_offsets(lines):
    """每行行首的字符偏移。"""
    offsets = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line) + 1
    return offsets


def read_text(path, what):
    """读 UTF-8 文本，按文本模式处理换行（与 split_headings.py 一致）。缺失、读不出、不是 UTF-8 一律退出码 2。"""
    if not os.path.isfile(path):
        _die(2, "%s 不存在，检查路径后重跑：%s" % (what, path))
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError as e:
        _die(2, "%s 不是合法 UTF-8，把文件转成 UTF-8 后重跑：%s（%s）" % (what, path, e))
    except OSError as e:
        _die(2, "%s 读不出，检查权限后重跑：%s（%s）" % (what, path, e))


def atomic_write(path, data, what="输出文件"):
    """先写同目录临时文件再整体替换。失败退出码 2，stderr 含 无法写入，不留临时文件。"""
    target = os.path.abspath(path)
    parent = os.path.dirname(target)
    tmp_name = None
    try:
        os.makedirs(parent, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=".heading_locate_", suffix=".tmp", dir=parent)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(data)
        os.replace(tmp_name, target)
        tmp_name = None
    except OSError as e:
        _die(2, "无法写入%s，检查目标路径是否可写、是否被目录占用：%s（%s）" % (what, path, e))
    finally:  # 写到一半被 Ctrl+C 打断也不留临时文件；KeyboardInterrupt 照常往外抛
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


# ---------------------------------------------------------------- lines

def cmd_lines(args):
    text = read_text(args.text, "--text")
    lines = split_lines(text)
    out = "".join("%d\t%s\n" % (i + 1, line) for i, line in enumerate(lines))
    atomic_write(args.out, out)
    _emit({"ok": True, "exit": 0, "lines": len(lines)})
    return 0


# ---------------------------------------------------------------- locate

def check_headings(items, lines):
    """逐项全部检查，返回 (errors, located)。

    errors：[{"index", "code", "line", "detail"}]
    located：类型合法且行号、原句都对上的项，[(index, line_no, level)]
    规则 4、5 以上一个类型合法项为基准，上一项本身行号或原句不对时下一项可能连带报错，属预期。
    """
    errors = []
    located = []
    total = len(lines)
    if not items:
        errors.append({"index": None, "code": "NO_HEADINGS", "line": None,
                       "detail": "headings 是空列表，至少写出一个标题。"})
        return errors, located

    prev_line = None
    prev_level = None
    first_valid = True
    for index, item in enumerate(items):
        line_no = item.get("line") if isinstance(item, dict) else None
        text = item.get("text") if isinstance(item, dict) else None
        level = item.get("level") if isinstance(item, dict) else None
        type_ok = (isinstance(item, dict) and is_int(line_no) and isinstance(text, str)
                   and text.strip() != "" and is_int(level) and LEVEL_MIN <= level <= LEVEL_MAX)
        if not type_ok:
            errors.append({"index": index, "code": "ITEM_INVALID",
                           "line": line_no if is_int(line_no) else None,
                           "detail": "第 %d 项（序号从 0 起）字段不合法。line 要写整数，"
                                     "text 要写去掉首尾空白后非空的字符串，level 要写 1 到 6 的整数。" % index})
            continue

        in_range = 1 <= line_no <= total
        text_ok = False
        if not in_range:
            if total == 0:
                detail = "第 %d 项的 line 为 %d，但稿子是空的，没有任何一行。先检查抽取结果。" % (index, line_no)
            else:
                detail = ("第 %d 项的 line 为 %d，整稿共 %d 行，把 line 改到 1 到 %d 之间。"
                          % (index, line_no, total, total))
            errors.append({"index": index, "code": "LINE_OUT_OF_RANGE", "line": line_no, "detail": detail})
        else:
            actual = lines[line_no - 1].strip()
            given = text.strip()
            if line_no == 1 and given.startswith(BOM):  # 子代理把第 1 行的 BOM 抄进来也不算错
                given = given[1:]
            if given != actual:
                errors.append({"index": index, "code": "TEXT_MISMATCH", "line": line_no,
                               "detail": "第 %d 项的 text 与第 %d 行的内容不同。清单写的是 %s，整稿该行是 %s。"
                                         "把 text 改成整稿原句，或改正 line。"
                                         % (index, line_no, text.strip(), actual)})
            else:
                text_ok = True

        if prev_line is not None and line_no <= prev_line:
            errors.append({"index": index, "code": "ORDER", "line": line_no,
                           "detail": "第 %d 项的 line %d 不大于上一项的 line %d。按整稿顺序排列各项，同一行不要列两次。"
                                     % (index, line_no, prev_line)})

        if first_valid:
            if level != 1:
                errors.append({"index": index, "code": "LEVEL_JUMP", "line": line_no,
                               "detail": "第一个标题的 level 要写 1，现在写的是 %d。" % level})
        elif level - prev_level >= 2:
            errors.append({"index": index, "code": "LEVEL_JUMP", "line": line_no,
                           "detail": "第 %d 项的 level 从 %d 跳到 %d，一次只能加深一级，往回退可以退任意级。"
                                     % (index, prev_level, level)})

        if in_range and text_ok:
            located.append((index, line_no, level))
        prev_line = line_no
        prev_level = level
        first_valid = False
    return errors, located


def duplicate_advisories(located, lines):
    """某项的行内容去空白后在别的行也出现时，给一条 DUPLICATE_TEXT 提示。"""
    by_text = {}
    for i, line in enumerate(lines):
        by_text.setdefault(line.strip(), []).append(i + 1)
    advisory = []
    for index, line_no, _level in located:
        others = [n for n in by_text.get(lines[line_no - 1].strip(), []) if n != line_no]
        if others:
            advisory.append({"code": "DUPLICATE_TEXT", "index": index, "line": line_no, "also_on": others})
    return advisory


def inherit_source_file(out_path, fallback):
    """运行前 --out 已存在、是 JSON 对象且 source_file 是字符串时沿用，否则用 --text 原样。"""
    try:
        with open(out_path, "r", encoding="utf-8") as f:
            old = json.load(f)
    except (OSError, ValueError, UnicodeDecodeError):
        return fallback
    if isinstance(old, dict) and isinstance(old.get("source_file"), str):
        return old["source_file"]
    return fallback


def cmd_locate(args):
    text = read_text(args.text, "--text")
    raw = read_text(args.headings_in, "--headings-in")
    try:
        doc = json.loads(raw)
    except ValueError as e:
        _die(2, "--headings-in 不是合法 JSON，改好后重跑：%s（%s）" % (args.headings_in, e))
    if not isinstance(doc, dict):
        _die(2, "--headings-in 顶层要是 JSON 对象，形如 {\"headings\": [...]}：%s" % args.headings_in)
    items = doc.get("headings")
    if not isinstance(items, list):
        _die(2, "--headings-in 缺 headings 键或它不是列表：%s" % args.headings_in)

    raw_lines = split_lines(text)
    lines = strip_bom_first(raw_lines)  # 比较与写清单不算 BOM
    errors, located = check_headings(items, lines)
    if errors:
        for e in errors:
            _err("%s index=%s line=%s %s" % (e["code"], e["index"], e["line"], e["detail"]))
        _emit({"ok": False, "exit": 1, "errors": errors})
        return 1

    offsets = line_offsets(raw_lines)  # 偏移按原文算，BOM 留在第一个小文件开头
    headings = []
    for index, line_no, level in located:
        headings.append({"text": lines[line_no - 1], "level": level,
                         "char_offset": offsets[line_no - 1], "style_id": "llm",
                         "is_caption": False, "confidence": "low"})
    manifest = {"source_file": inherit_source_file(args.out, args.text),
                "text_file": args.text, "text_len": len(text), "headings": headings,
                "warning": None, "located_by": "heading_locate"}
    atomic_write(args.out, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", "--out")
    _emit({"ok": True, "exit": 0, "headings": len(headings),
           "split_to_level": max(level for _i, _l, level in located),
           "advisory": duplicate_advisories(located, lines)})
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="无标题路的标题定位：给整稿编行号；按行号核对清单并写出 heading_manifest.json")
    sub = ap.add_subparsers(dest="command")
    p_lines = sub.add_parser("lines", help="给整稿每一行加行号")
    p_lines.add_argument("--text", required=True)
    p_lines.add_argument("--out", required=True)
    p_locate = sub.add_parser("locate", help="按行号定位清单里的标题并写出 heading_manifest.json")
    p_locate.add_argument("--text", required=True)
    p_locate.add_argument("--headings-in", required=True)
    p_locate.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    if args.command == "lines":
        return cmd_lines(args)
    if args.command == "locate":
        return cmd_locate(args)
    ap.print_usage(sys.stderr)
    _err("缺少子命令，写 lines 或 locate。")
    return 2


if __name__ == "__main__":
    sys.exit(main())
