#!/usr/bin/env python3
"""section_parts.py —— 拆分后小文件的归属（P1 到 P4、其他）：拆分表、用户确认、读取（2.42.0 新增）.

三个子命令：
  table    读 split_manifest.json 与主会话写的归属草稿 tmp/parts_draft.json，校验后写出按连续
           同归属分组的拆分表（Markdown）。stdout 一行 JSON。
  confirm  只能由用户在自己的终端运行。按组（缺省）或逐行把每个小文件的归属过一遍，输入 确认 后
           原子写归属文件。stdout 是给人看的交互文字。
  show     判定归属文件的状态。stdout 一行 JSON。
人读的报错行走 stderr，以 "SECTION_PARTS: " 开头。

归属文件位置（唯一规则）：小文件目录的父目录下的 section_parts.json。

================ 读取接口（humanizer_zh.py 与 diagnosis_engine.py 按这里接线） ================

  result = read_parts(sections_dir)
      参数：小文件目录（scan-all 的位置参数，diagnose-all 的 --sections-dir）。
      不抛异常、不退出、不读 tmp/ 下任何文件；只看归属文件本身与小文件目录里现有的文件名。
      返回 dict：
        "status"        "absent" / "corrupt" / "invalid" / "dir_mismatch" / "ok"
        "path"          归属文件的绝对路径
        "parts"         {小文件名: 归属} 的完整映射（ok 时为归属文件 rows 里的全部行，含
                        不认识的归属；其余状态为空 dict）
        "stderr"        要打到 stderr 的行（已带 SECTION_PARTS: 前缀；absent 时为空列表），
                        调用方整段写到 stderr 一次即可
        "confirmed_at"  记录值（ok 时），否则 None
        "released"      ok 时生效且归属会放行、文件又存在的小文件名列表，否则空列表
        "detail"        一句中文说明
      调用方在 import 本模块失败时自行打一行
        SECTION_PARTS: READER_UNAVAILABLE <异常类型名>
      并视为不放行（只在归属文件存在时打；归属文件存在与否可用 parts_path(sections_dir) 判断）。

  checks = releases(result, filename)
      返回该文件按归属文件应放行的检查名集合（frozenset），本轮只有 "cn_numbered"
      （即 --allow-cn-numbered 的口径）。不生效的行、不认识的归属、不存在的文件返回空集。
      放行哪些部分见 RELEASE_BY_PART（在本模块里），增减部分只改这张表。

  should_release(result, filename, check="cn_numbered") -> bool
      两个检查脚本只调用这个函数，不自己判断归属取值。三种放行来源取并集、只加不撤，
      并集由调用方做：文件名以 P2 开头、--allow-cn-numbered、本函数。

退出码：table 0 / 1（草稿与清单不符）/ 2（文件缺失或畸形、越根、写失败）；
confirm 0 / 1（校验不过、用户中止、EOF、SIGINT）/ 2（同 table，另加小文件目录不对）/ 3（不是终端）；
show：absent 与 ok 为 0，其余 1。
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import tempfile
import unicodedata

PREFIX = "SECTION_PARTS: "
PARTS_FILE = "section_parts.json"
SCHEMA_VERSION = "1.0"
PARTS = ("P1", "P2", "P3", "P4", "其他")
DEFAULT_CONFIRM_MODE = "by-group"       # 确认粒度缺省值，换缺省只改这里（by-group / each-row）
CHECK_CN_NUMBERED = "cn_numbered"       # 即 --allow-cn-numbered 的口径
RELEASE_BY_PART = {                      # 归属对应放行哪些检查；放行哪些部分见本表
    "P2": frozenset({CHECK_CN_NUMBERED}),
    "P3": frozenset({CHECK_CN_NUMBERED}),
}
BASIS_LINE = "比较基准是抽取后的 draft_import.md，原件里的表格文字、自动编号、加粗不在其中。"
COPY_HINT = "把以上文字整段复制回聊天窗口。"
FRONT_LABEL = "（首段）"
PLACEHOLDER = chr(0xFFFD)                # 显示控制字符时的占位符，全文一致
TITLE_MAX = 40
FRONT_LONG = 300
TABLE_HEADER = ["| 序号 | 文件名 | 级别 | 标题 | 字数 | 归属 | 提示 |", "|---|---|---|---|---|---|---|"]
SENTENCE_ENDS = ("。", "！", "？", "；")
ROW_PART_RE = re.compile(r"^(\d+)\s+(\S+)$")
VERSION_RE = re.compile(r"^(\d+)\.(\d+)$")


def _err(msg):
    """人读的报错行。文件名、路径、标题可能混在里面，整行过 display_safe，控制字符不直达终端。"""
    sys.stderr.write(PREFIX + display_safe(msg.rstrip()) + "\n")


def _emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _say(text=""):
    """confirm 的终端输出。整行过 display_safe，与 _err 同一口径。"""
    sys.stdout.write(display_safe(text) + "\n")
    sys.stdout.flush()


class Fail(Exception):
    """带退出码的失败；信息已经打到 stderr。"""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


# ============================================================ 读取接口

def parts_path(sections_dir):
    """归属文件的绝对路径：小文件目录的父目录下的 section_parts.json。"""
    return os.path.join(os.path.dirname(os.path.abspath(sections_dir)), PARTS_FILE)


def normalize_part(value):
    """P1 到 P4 大小写都认，其他原样；不认识的返回 None。"""
    if not isinstance(value, str):
        return None
    v = value.strip()
    if v == "其他":
        return v
    u = v.upper()
    if u in PARTS:
        return u
    return None


def _result(status, path, detail, stderr=None, parts=None, confirmed_at=None, released=None):
    return {"status": status, "path": path, "parts": parts or {}, "stderr": stderr or [],
            "confirmed_at": confirmed_at, "released": released or [], "detail": detail}


def _bad_sections_dir(value):
    if not isinstance(value, str) or not value.strip():
        return True
    if os.path.isabs(value) or value.startswith(("/", "\\")):
        return True
    return any(seg == ".." for seg in re.split(r"[\\/]+", value))


def _invalid_reason(doc):
    """返回 (原因, 是否更高版本)；合法时返回 (None, False)。"""
    if not isinstance(doc, dict):
        return "顶层不是对象", False
    ver = doc.get("schema_version")
    if ver != SCHEMA_VERSION:
        higher = False
        m = VERSION_RE.match(ver) if isinstance(ver, str) else None
        if m and (int(m.group(1)), int(m.group(2))) > (1, 0):
            higher = True
        return "schema_version 不是 %s" % SCHEMA_VERSION, higher
    if doc.get("confirmed") is not True:
        return "confirmed 不是 true", False
    if _bad_sections_dir(doc.get("sections_dir")):
        return "sections_dir 不是非空相对路径或含 ..", False
    rows = doc.get("rows")
    if not isinstance(rows, list) or not rows:
        return "rows 不是非空列表", False
    seen = set()
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            return "第 %d 行不是对象" % i, False
        f = row.get("file")
        if not isinstance(f, str) or not f.endswith(".md") or "/" in f or "\\" in f:
            return "第 %d 行的 file 不是以 .md 结尾的文件名" % i, False
        if f in seen:
            return "file 重复 %s" % f, False
        seen.add(f)
    return None, False


def read_parts(sections_dir):
    """按模块头注释的读取接口判定归属文件状态。不抛异常、不退出。"""
    path = parts_path(sections_dir)
    fix = PREFIX + "归属文件不生效，全部文件不按归属放行。重新在你自己的终端运行 section_parts.py confirm 生成它。"
    if not os.path.lexists(path):
        return _result("absent", path, "归属文件不存在。")
    shown_path = display_safe(path)  # stderr 里的路径与文件名都过 display_safe，控制字符不直达终端
    corrupt = _result("corrupt", path, "归属文件读不出或不是合法 UTF-8 JSON。",
                      [PREFIX + "CORRUPT " + shown_path, fix])
    if not os.path.isfile(path):  # 目录、命名管道、设备一律不去 open，否则会卡死或报错
        return corrupt
    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except Exception:  # 含极深嵌套 JSON 抛的 RecursionError；本函数承诺不抛异常
        return corrupt
    reason, higher = _invalid_reason(doc)
    if reason is not None:
        lines = [PREFIX + "INVALID %s %s" % (shown_path, display_safe(reason))]
        if higher:
            lines.append(PREFIX + "归属文件的 schema_version 比本技能认识的高，先升级技能再用。")
        lines.append(fix)
        return _result("invalid", path, "归属文件字段非法，" + reason + "。", lines)
    recorded = os.path.normpath(doc["sections_dir"]).replace("\\", "/").rstrip("/")
    actual = os.path.basename(os.path.normpath(os.path.abspath(sections_dir)))
    if recorded != actual:
        return _result("dir_mismatch", path,
                       "归属文件记录的小文件目录是 %s，本次是 %s。" % (recorded, actual),
                       [PREFIX + "DIR_MISMATCH " + shown_path, fix])

    try:
        present = set(os.listdir(sections_dir))
    except OSError:
        present = set()
    parts = {}
    lines = []
    released = []
    for row in doc["rows"]:
        name = row["file"]
        part = row.get("part")
        parts[name] = part
        if part not in PARTS:
            lines.append(PREFIX + "UNKNOWN_PART " + display_safe(name))
            continue
        if name not in present:
            lines.append(PREFIX + "MISSING_FILE " + display_safe(name))
            continue
        if RELEASE_BY_PART.get(part):
            released.append(name)
    unlisted = [n for n in sorted(present) if n.endswith(".md") and n not in parts
                and os.path.isfile(os.path.join(sections_dir, n))]
    if unlisted:
        shown = "、".join(display_safe(n) for n in unlisted[:5]) + ("等" if len(unlisted) > 5 else "")
        lines.append(PREFIX + "UNLISTED %d %s 这些文件没有归属记录，按没有归属处理，照文件名规则检查。"
                     % (len(unlisted), shown))
    confirmed_at = doc.get("confirmed_at")
    if released:
        lines.append(PREFIX + "按 section_parts.json 放行 %d 个文件（confirmed_at %s）"
                     % (len(released), display_safe(str(confirmed_at))))
    return _result("ok", path, "归属文件有效。", lines, parts, confirmed_at, released)


def releases(result, filename):
    """该文件按归属文件应放行的检查名集合。"""
    if not isinstance(result, dict) or result.get("status") != "ok":
        return frozenset()
    if filename not in (result.get("released") or []):
        return frozenset()
    return RELEASE_BY_PART.get(result["parts"].get(filename), frozenset())


def should_release(result, filename, check=CHECK_CN_NUMBERED):
    return check in releases(result, filename)


# ============================================================ 公共校验（table 与 confirm）

def _load_json(path, what):
    if not os.path.isfile(path):
        _err("%s 不存在，检查路径后重跑：%s" % (what, path))
        raise Fail(2)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError, UnicodeDecodeError) as e:
        _err("%s 读不出或不是合法 UTF-8 JSON：%s（%s）" % (what, path, e))
        raise Fail(2)


def _inside_root(path, root, base=None):
    """base 为 None 时相对路径按命令行语义从当前目录起算（--manifest、--out，即实际读写的路径）；
    传 root 时相对 --root 解析（atoms[].file，按 INTERFACE 1.3、2.2）。"""
    root_real = os.path.realpath(root)
    if os.path.isabs(path):
        full = path
    elif base is None:
        full = os.path.abspath(path)
    else:
        full = os.path.join(base, path)
    real = os.path.realpath(full)
    return real == root_real or real.startswith(root_real + os.sep), real


def _check_escape(path, root, what, base=None):
    ok, real = _inside_root(path, root, base)
    if not ok:
        _err("%s escapes --root: %s" % (what, path))
        raise Fail(2)
    return real


def load_inputs(manifest_path, draft_path, root):
    """2.2 第 1 条的退出码 2 校验。返回 (atoms 列表, 草稿 parts 对象, 每个小文件的实际路径)。"""
    _check_escape(manifest_path, root, "--manifest")
    mf = _load_json(manifest_path, "--manifest")
    atoms = mf.get("atoms") if isinstance(mf, dict) else None
    if not isinstance(atoms, list) or not atoms:
        _err("--manifest 的 atoms 要是非空列表：%s" % manifest_path)
        raise Fail(2)
    paths = []
    for i, atom in enumerate(atoms):
        fp = atom.get("file") if isinstance(atom, dict) else None
        if not isinstance(fp, str) or not fp:
            _err("--manifest 第 %d 项（序号从 0 起）缺 file。" % i)
            raise Fail(2)
        paths.append(_check_escape(fp, root, "manifest atom 'file'", base=root))
    draft = _load_json(draft_path, "--draft")
    parts = draft.get("parts") if isinstance(draft, dict) else None
    if not isinstance(draft, dict) or not isinstance(parts, dict):
        _err("--draft 顶层要是对象且 parts 是对象，形如 {\"parts\": {\"文件名\": \"P2\"}}：%s" % draft_path)
        raise Fail(2)
    return atoms, parts, paths


def validate_draft(atoms, parts, paths):
    """2.2 第 2 条：全部检查完一次报出。返回 errors 列表（空表示通过）。"""
    errors = []
    names = []
    for atom, real in zip(atoms, paths):
        name = os.path.basename(atom["file"])
        names.append(name)
        if name not in parts:
            errors.append({"code": "MISSING_PART", "file": name,
                           "detail": "草稿里没有这个文件，给它补一个归属。"})
        elif parts[name] not in PARTS:
            errors.append({"code": "BAD_PART", "file": name,
                           "detail": "归属 %r 不在 P1、P2、P3、P4、其他 之中。" % (parts[name],)})
        if not os.path.isfile(real):
            errors.append({"code": "ATOM_MISSING", "file": name,
                           "detail": "清单里的小文件不存在：%s" % atom["file"]})
    for key in parts:
        if key not in names:
            errors.append({"code": "UNKNOWN_FILE", "file": key,
                           "detail": "草稿里这个文件名不在清单里，删掉它或改成清单里的文件名。"})
    return errors


def _report_errors(errors):
    for e in errors:
        _err("%s %s %s" % (e["code"], e["file"], e["detail"]))


# ============================================================ 行与分组

def _nonblank_count(text):
    return sum(1 for ch in text if not ch.isspace())


def build_rows(atoms, parts, paths):
    """每个小文件一行：file、title、level、part、draft_part、count、container、table_like。"""
    rows = []
    for atom, real in zip(atoms, paths):
        name = os.path.basename(atom["file"])
        try:
            with open(real, "r", encoding="utf-8", newline="") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            content = ""
        title = atom.get("title")
        title = title if isinstance(title, str) else ""
        level = atom.get("heading_level")
        level = level if isinstance(level, int) and not isinstance(level, bool) else 0
        rest = content.split("\n", 1)[1] if "\n" in content else ""
        rows.append({"file": name, "title": title, "level": level, "part": parts[name],
                     "draft_part": parts[name], "count": _nonblank_count(content),
                     "container": level >= 1 and rest.strip() == "",
                     "table_like": ("|" in title) or ("\t" in title)})
    return rows


def group_rows(rows):
    """按清单顺序，把连续且归属相同的行合成一组。返回 [(part, [行序号（0 起）])]。"""
    groups = []
    for i, row in enumerate(rows):
        if groups and groups[-1][0] == row["part"]:
            groups[-1][1].append(i)
        else:
            groups.append((row["part"], [i]))
    return groups


def display_safe(text):
    """给拆分表与终端显示用：控制字符（Unicode 类别 Cc、Cf，含 ESC、BEL、NUL、C1、方向符）换成占位符，
    其余照常。归属文件里存的 title 不经过这里，保持原样。"""
    return "".join(PLACEHOLDER if unicodedata.category(ch) in ("Cc", "Cf") else ch for ch in text)


def display_title(title):
    t = display_safe(title).strip()
    if t == "frontmatter":
        return FRONT_LABEL
    t = t.replace("|", "｜")
    if len(t) > TITLE_MAX:
        t = t[:TITLE_MAX] + "…"
    return t


def hints_for(rows, groups, index):
    row = rows[index]
    shown = display_title(row["title"])
    hints = []
    if row["container"]:
        hints.append("容器")
    gi = next(k for k, (_p, members) in enumerate(groups) if index in members)
    if len(groups[gi][1]) == 1 and 0 < gi < len(groups) - 1:
        if groups[gi - 1][0] == groups[gi + 1][0] != groups[gi][0]:
            hints.append("前后同属他组")
    if row["title"].strip().endswith(SENTENCE_ENDS):
        hints.append("疑似正文句")
    if row["table_like"]:
        hints.append("疑似表格行")
    if shown == FRONT_LABEL and row["count"] > FRONT_LONG:
        hints.append("首段较长")
    return "、".join(hints)


def _data_line(rows, groups, index):
    row = rows[index]
    return "| %d | %s | %d | %s | %d | %s | %s |" % (
        index + 1, display_safe(row["file"]), row["level"], display_title(row["title"]), row["count"],
        row["part"], hints_for(rows, groups, index))


def render_table(rows):
    groups = group_rows(rows)
    out = ["# 拆分表",
           "共 %d 行，分 %d 组。" % (len(rows), len(groups)),
           BASIS_LINE,
           "一行是一个小文件，按原稿顺序排列，连续且归属相同的行合成一组。",
           "归属取值：P1 立项依据，P2 研究内容，P3 研究基础与工作条件，P4 其他需要说明的情况，其他。",
           "提示列只给人看：容器表示只有标题没有正文；前后同属他组表示这一行夹在两个同归属的组之间，多半要改；"
           "疑似正文句、疑似表格行、首段较长提示这一行可能切错了。",
           "看完表后在你自己的终端运行 section_parts.py confirm 逐组确认，要改的行在终端里写序号和归属。",
           ""]
    for k, (part, members) in enumerate(groups, start=1):
        out.append("### 第 %d 组 归属 %s，%d 行" % (k, part, len(members)))
        out.extend(TABLE_HEADER)
        for index in members:
            out.append(_data_line(rows, groups, index))
        out.append("")
    return "\n".join(out), groups


# ============================================================ 原子写

def atomic_write(path, data, what="输出文件"):
    target = os.path.abspath(path)
    parent = os.path.dirname(target)
    tmp_name = None
    try:
        os.makedirs(parent, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=".section_parts_", suffix=".tmp", dir=parent)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(data)
        os.replace(tmp_name, target)
        tmp_name = None
    except OSError as e:
        _err("无法写入%s，检查目标路径是否可写、是否被目录占用：%s（%s）" % (what, path, e))
        raise Fail(2)
    finally:  # 写到一半被 Ctrl+C 打断也不留临时文件；KeyboardInterrupt 照常往外抛
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


# ============================================================ table

def cmd_table(args):
    out_real = _check_escape(args.out, args.root, "--out")  # 写到解析后的真实路径，与越根检查的对象一致
    atoms, parts, paths = load_inputs(args.manifest, args.draft, args.root)
    errors = validate_draft(atoms, parts, paths)
    if errors:
        _report_errors(errors)
        _emit({"ok": False, "exit": 1, "errors": errors})
        return 1
    rows = build_rows(atoms, parts, paths)
    text, groups = render_table(rows)
    atomic_write(out_real, text, "拆分表")
    _emit({"ok": True, "exit": 0, "rows": len(rows), "groups": len(groups),
           "p2_files": [r["file"] for r in rows if r["part"] == "P2"], "out": args.out})
    return 0


# ============================================================ confirm

def normalize_input(line):
    """NFKC 归一（全角字母数字转半角），再去首尾空白。"""
    return unicodedata.normalize("NFKC", line).strip()


def parse_row_part(text):
    """序号归属，例如 7 P2。返回 (序号, 归属) 或 None。"""
    m = ROW_PART_RE.match(text)
    if not m:
        return None
    part = normalize_part(m.group(2))
    if part is None:
        return None
    return int(m.group(1)), part


def _read_line(prompt):
    """返回归一后的一行；EOF 抛 EOFError。"""
    sys.stdout.write(prompt)
    sys.stdout.flush()
    line = sys.stdin.readline()
    if line == "":
        raise EOFError
    return normalize_input(line)


def _print_group(rows, groups, gi):
    part, members = groups[gi]
    _say("第 %d 组，归属 %s，共 %d 行：" % (gi + 1, part, len(members)))
    for index in members:
        _print_row(rows, groups, index)


def _print_row(rows, groups, index):
    row = rows[index]
    hint = hints_for(rows, groups, index)
    _say("  %d. %s  级别 %d  标题 %s  当前归属 %s%s" % (
        index + 1, display_safe(row["file"]), row["level"], display_title(row["title"]), row["part"],
        ("  提示 " + hint) if hint else ""))


def _unrecognized(extra):
    _say("无法识别这一行输入。" + extra)


def _apply_change(rows, index, part):
    rows[index]["part"] = part


def confirm_by_group(rows, groups):
    for gi, (_part, members) in enumerate(groups):
        _say()
        _print_group(rows, groups, gi)
        while True:
            text = _read_line("这一组没问题就直接按回车；要改某一行就写序号、空格、归属（例如 7 P2）再回车：")
            if text == "":
                break
            parsed = parse_row_part(text)
            if parsed and (parsed[0] - 1) in members:
                _apply_change(rows, parsed[0] - 1, parsed[1])
                _say()
                _print_group(rows, groups, gi)
                continue
            _unrecognized("本组的序号是 %d 到 %d，归属只能写 P1、P2、P3、P4 或 其他。" % (members[0] + 1, members[-1] + 1))


def confirm_each_row(rows, groups):
    last_gi = None
    for gi, (_part, members) in enumerate(groups):
        for index in members:
            if gi != last_gi:
                _say()
                _say("第 %d 组，归属 %s，共 %d 行：" % (gi + 1, _part, len(members)))
                last_gi = gi
            _print_row(rows, groups, index)
            while True:
                text = _read_line("保留当前归属就直接按回车；要改就只写新的归属（P1、P2、P3、P4 或 其他）再回车：")
                if text == "":
                    break
                part = normalize_part(text)
                if part is not None:
                    _apply_change(rows, index, part)
                    break
                _unrecognized("只写一个归属，P1、P2、P3、P4 或 其他。")


def _print_summary(rows):
    changed = [r for r in rows if r["part"] != r["draft_part"]]
    p2 = [r["file"] for r in rows if r["part"] == "P2"]
    _say()
    _say("汇总：共 %d 行，你改动了 %d 行。" % (len(rows), len(changed)))
    for r in changed:
        _say("  %s 由 %s 改为 %s" % (display_safe(r["file"]), r["draft_part"], r["part"]))
    _say("归属 P2 的文件共 %d 个：" % len(p2))
    for name in p2:
        _say("  " + display_safe(name))


def confirm_summary(rows):
    """返回 True 表示用户输入了 确认。其它输入返回 False。"""
    n = len(rows)
    while True:
        _print_summary(rows)
        text = _read_line("没问题就输入 确认 两个字再回车；还要改某一行就写序号、空格、归属（例如 3 其他）再回车；输入别的内容会退出且不保存：")
        if text == "确认":
            return True
        parsed = parse_row_part(text)
        if parsed and 1 <= parsed[0] <= n:
            _apply_change(rows, parsed[0] - 1, parsed[1])
            continue
        return False


def _confirm_fail(code, *lines):
    for line in lines:
        _err(line)
    sys.stderr.write(COPY_HINT + "\n")
    sys.stderr.flush()
    return code


def cmd_confirm(args):
    try:
        atoms, parts, paths = load_inputs(args.manifest, args.draft, args.root)
        dirs = {os.path.dirname(p) for p in paths}
        root_real = os.path.realpath(args.root)
        if len(dirs) != 1 or os.path.dirname(next(iter(dirs))) != root_real:
            _err("小文件目录不对：所有小文件要在同一个目录里，且这个目录的父目录就是 --root。"
                 "检查 --root 和清单里的 file 后重跑。")
            raise Fail(2)
        sections_real = next(iter(dirs))
        errors = validate_draft(atoms, parts, paths)
        if errors:
            _report_errors(errors)
            raise Fail(1)
    except Fail as e:
        return _confirm_fail(e.code)

    if not sys.stdin.isatty():
        return _confirm_fail(3, "NOT_A_TERMINAL 这个命令只能由你本人在终端里运行，不能由 AI 代跑。",
                             "请在你自己的终端里运行：Mac 打开 终端，Windows 打开 PowerShell 或 cmd"
                             "（Git Bash 里要写成 winpty python）。")

    rows = build_rows(atoms, parts, paths)
    groups = group_rows(rows)
    mode = "each-row" if args.each_row else ("by-group" if args.by_group else DEFAULT_CONFIRM_MODE)
    _say("逐个确认小文件的归属。共 %d 行，分 %d 组。" % (len(rows), len(groups)))
    _say(BASIS_LINE)
    try:
        if mode == "each-row":
            confirm_each_row(rows, groups)
        else:
            confirm_by_group(rows, groups)
        if not confirm_summary(rows):
            return _confirm_fail(1, "ABORTED 没有输入 确认，归属文件没有写入。重新运行本命令可以再来一次。")
    except (EOFError, KeyboardInterrupt):
        _say()
        return _confirm_fail(1, "ABORTED 输入被中断，归属文件没有写入。重新运行本命令可以再来一次。")

    target = os.path.join(root_real, PARTS_FILE)
    doc = {"schema_version": SCHEMA_VERSION, "confirmed": True,
           "confirmed_at": datetime.datetime.now().astimezone().isoformat(),
           "confirmed_via": "terminal", "mode": mode, "note": args.note or "",
           "sections_dir": os.path.basename(sections_real),
           "rows": [{"file": r["file"], "title": r["title"], "level": r["level"], "part": r["part"],
                     "draft_part": r["draft_part"], "changed_by_user": r["part"] != r["draft_part"]}
                    for r in rows]}
    try:
        atomic_write(target, json.dumps(doc, ensure_ascii=False, indent=2) + "\n", "归属文件")
    except Fail as e:
        return _confirm_fail(e.code)
    _say("已写入归属文件：%s" % target)
    _say("下一步：回到聊天窗口告诉 AI 归属已确认。")
    return 0


# ============================================================ show

def cmd_show(args):
    result = read_parts(args.sections_dir)
    p2 = []
    if result["status"] == "ok":
        p2 = [n for n in result["released"] if result["parts"].get(n) == "P2"]
    _emit({"status": result["status"], "path": result["path"], "p2_files": p2,
           "detail": display_safe(result["detail"])})
    return 0 if result["status"] in ("absent", "ok") else 1


# ============================================================ main

def _configure_streams():
    """只在命令行入口做：Windows GBK 控制台下中文防 UnicodeEncodeError，confirm 读标准输入也按 UTF-8。
    被 humanizer_zh.py、diagnosis_engine.py 导入时不改它们的输出编码。"""
    for stream in (sys.stdout, sys.stderr, sys.stdin):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def main(argv=None):
    _configure_streams()
    ap = argparse.ArgumentParser(description="拆分后小文件的归属：拆分表、用户在自己终端确认、读取状态")
    sub = ap.add_subparsers(dest="command")
    p_table = sub.add_parser("table", help="写出按连续同归属分组的拆分表")
    p_table.add_argument("--manifest", required=True)
    p_table.add_argument("--draft", required=True)
    p_table.add_argument("--out", required=True)
    p_table.add_argument("--root", default=".")
    p_confirm = sub.add_parser("confirm", help="只能由用户本人在自己的终端运行，确认后写归属文件")
    p_confirm.add_argument("--manifest", required=True)
    p_confirm.add_argument("--draft", required=True)
    p_confirm.add_argument("--root", required=True)
    mode = p_confirm.add_mutually_exclusive_group()
    mode.add_argument("--by-group", action="store_true")
    mode.add_argument("--each-row", action="store_true")
    p_confirm.add_argument("--note", default="")
    p_show = sub.add_parser("show", help="判定归属文件的状态")
    p_show.add_argument("--sections-dir", default="sections")
    args = ap.parse_args(argv)
    try:
        if args.command == "table":
            return cmd_table(args)
        if args.command == "confirm":
            return cmd_confirm(args)
        if args.command == "show":
            return cmd_show(args)
    except Fail as e:
        return e.code
    ap.print_usage(sys.stderr)
    _err("缺少子命令，写 table、confirm 或 show。")
    return 2


if __name__ == "__main__":
    sys.exit(main())
