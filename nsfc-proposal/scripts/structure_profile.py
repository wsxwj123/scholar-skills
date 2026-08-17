#!/usr/bin/env python3
"""structure_profile.py —— 结构真源 structure_profile.json 的唯一读口与提取链 CLI。

契约：.devflow/INTERFACE-nsfc-template.md（§1 schema / §2 提取链 / §3 错误契约 /
§6.1 resolve_scope / §9 裁决）。

模块 API（另两处代码 import，签名钉死）：
    load(root) -> dict | None      # 三态见 §3.5；绝不抛异常、绝不 sys.exit
    resolve_scope(root) -> dict    # {"active": [...], "skipped": [...]}

CLI 子命令：extract-text / verify / show / confirm（propose / validate 已废止）。
全链只读用户原件（P-6）；`confirm` 是全仓唯一写 structure_profile.json 的地方。
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

SCHEMA_VERSION = "1.0"
SOURCES = ("builtin_nsfc", "extracted", "manual")
SCHEMES = ("nsfc", "other")
PROFILE_NAME = "structure_profile.json"
LARGE_CHARS = 80000          # §9 裁决 2：字符数（len(str)），与 char_offset 同一把尺
SHORT_LINE_MAX = 60

# ponytail: 「抽出正文 <200 字疑扫描件」按 utf-8 字节判——中文模板 160 字符≈480 字节，
# 按字符判会把正常小模板误杀；真扫描件抽出的文字连 200 字节都不到。只对 .pdf/.docx 生效（§9 裁决 3）。
MIN_BODY_BYTES = 200

# §5.1 封闭集：声明 funding_scheme=other 后关掉的四项（id, 人读名）
NSFC_ONLY_CHECKS = [
    ("SPA-REQUIRED", "科学问题属性四选一"),
    ("HRCK-V-RULES", "假说—目标—内容—问题对应校验"),
    ("HRCK-DIMS", "依赖一致性校验的自审维度"),
    ("SPA-JUSTIFY", "科学问题属性论证关键词提示"),
]

MINIMAL_EXAMPLE = {"schema_version": "1.0", "confirmed": True,
                   "source": "manual", "funding_scheme": "other"}

DISPOSE_CORRUPT = "处置：修复该文件；或删除它，脚本会回落到内置国自然默认。"
DISPOSE_INVALID = "处置：修正该字段；或删除该文件，脚本会回落到内置国自然默认。"
DISPOSE_UNCONFIRMED = ("处置：该结构未经用户确认。请把章节表摆给用户逐条核对后，"
                       "运行 structure_profile.py confirm。")


# =========================================================================
# 结构真源三态读取（load / show / resolve_scope 共用）
# =========================================================================

def _profile_path(root):
    return os.path.join(os.path.abspath(str(root)), PROFILE_NAME)


def _validate(data):
    """字段校验（§3.2 触发条件穷举）。返回 (字段路径, 原因) 或 None（合法）。"""
    if not isinstance(data, dict):
        return "(top-level)", "必须是 JSON 对象"
    if data.get("schema_version") != SCHEMA_VERSION:
        return "schema_version", '缺失或不等于 "1.0"'
    if data.get("source") not in SOURCES:
        return "source", "取值域为 builtin_nsfc / extracted / manual"
    if "funding_scheme" in data and data["funding_scheme"] not in SCHEMES:
        return "funding_scheme", "取值域为 nsfc / other"
    if "chapters" in data:            # 键不存在是合法缺省（§1.4）
        chapters = data["chapters"]
        if not isinstance(chapters, list) or not chapters:
            return "chapters", "必须是非空 list（键整个不存在才是合法缺省）"
        seen = {}
        for i, ch in enumerate(chapters):
            if not isinstance(ch, dict):
                return "chapters[%d]" % i, "必须是对象"
            fn = ch.get("filename")
            # 拒收字符集与生成侧 _FN_BAD_RE 同一把尺（2026-08-03 缺陷：此前只查
            # / \ ..，放行了 NUL 等控制字符与 "C:" 盘符——NUL 会让下游 open()
            # 抛 embedded null byte，traceback 裸奔）。主干（去掉 .md 后缀）里
            # 出现任一剥除字符即非法；扩展名那个点不在主干里，天然合法。
            if (not isinstance(fn, str) or not fn.endswith(".md") or fn == ".md"
                    or _FN_BAD_RE.search(fn[:-len(".md")])):
                return ("chapters[%d].filename" % i,
                        '必须是 .md 结尾的 basename（主干不含 /\\:*?"<>|. 、空白与控制字符）')
            if fn in seen:
                return "chapters[%d].filename" % i, "与 chapters[%d] 重复（同一文件会被合两遍）" % seen[fn]
            seen[fn] = i
            order = ch.get("order")
            if not isinstance(order, int) or isinstance(order, bool):
                return "chapters[%d].order" % i, "必须是整数"
    return None


def _inspect(root):
    """返回 (status, data, stderr_lines)。
    status ∈ {"absent", "corrupt", "invalid", "unconfirmed", "ok"}；
    仅 ok 时 data 非 None。stderr_lines 由调用方决定打不打（load 打、resolve_scope 不打）。"""
    if root is None:
        return "absent", None, []
    path = _profile_path(root)
    if not os.path.exists(path):
        return "absent", None, []
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        # 存在但读不出（目录/权限等）：按损坏处理，此时没有解析器行列号可给
        return "corrupt", None, [
            "STRUCTURE_PROFILE: CORRUPT %s: 读取失败（%s）" % (path, e.__class__.__name__),
            DISPOSE_CORRUPT]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        # §3.1：行号列号必须是解析器给的真实位置
        return "corrupt", None, [
            "STRUCTURE_PROFILE: CORRUPT %s: line %d column %d" % (path, e.lineno, e.colno),
            DISPOSE_CORRUPT]
    bad = _validate(data)
    if bad:
        return "invalid", None, [
            "STRUCTURE_PROFILE: INVALID %s: %s %s" % (path, bad[0], bad[1]),
            DISPOSE_INVALID]
    if data.get("confirmed") is not True:
        return "unconfirmed", None, [
            "STRUCTURE_PROFILE: UNCONFIRMED %s" % path,
            DISPOSE_UNCONFIRMED]
    # §1.2 的「当作」归一化（只改内存，绝不回写文件）
    if not isinstance(data.get("history", []), list):
        data["history"] = []
    for ch in data.get("chapters", []):
        if "required" in ch and not isinstance(ch["required"], bool):
            ch["required"] = False
    return "ok", data, []


def load(root):
    """读 <root>/structure_profile.json。三态见 INTERFACE §3.5：
    不存在 → None，零输出；坏 JSON → CORRUPT 行到 stderr，None；
    字段非法 → INVALID 行，None；confirmed != true → UNCONFIRMED 行，None；
    完全合法 → 解析后的 dict。任何情况都不抛异常、不 sys.exit。"""
    try:
        status, data, lines = _inspect(root)
    except Exception:
        return None
    for line in lines:
        print(line, file=sys.stderr)
    return data if status == "ok" else None


# =========================================================================
# §6.1 resolve_scope —— 唯一裁定函数（纯函数，只读两份磁盘文件）
# =========================================================================

def _valid_gates(root):
    """合法 gate 集合 = references/dod_checklist.json 的 gates 键集。
    checklist 定位复用 dod_project._find_checklist（不抄第二份定位规则）。
    读不到/坏 → None（调用方按「取值域无法核对」收紧处理）。"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import dod_project
        path = dod_project._find_checklist(os.path.abspath(str(root)))
        if not path:
            return None
        with open(path, encoding="utf-8") as f:
            gates = json.load(f).get("gates")
        return set(gates) if isinstance(gates, dict) else None
    except Exception:
        return None


def _dod_disabled(root):
    """读 <root>/data/dod_selection.json 的 disabled[]（§7）。
    不存在 → []（零输出）；损坏/非法 → 打 DOD_SELECTION 错误行后回落「全项都跑」。"""
    path = os.path.join(os.path.abspath(str(root)), "data", "dod_selection.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        print("DOD_SELECTION: CORRUPT %s: 读取失败（%s）" % (path, e.__class__.__name__),
              file=sys.stderr)
        print("处置：修复该文件；或删除它，脚本会回落到全项都跑。", file=sys.stderr)
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print("DOD_SELECTION: CORRUPT %s: line %d column %d" % (path, e.lineno, e.colno),
              file=sys.stderr)
        print("处置：修复该文件；或删除它，脚本会回落到全项都跑。", file=sys.stderr)
        return []
    disabled = data.get("disabled") if isinstance(data, dict) else None
    # id 必须是非空字符串——与过滤路 dod_project._load_selection 同口径。此前只判
    # not x.get("id")，truthy 的数字/布尔 id 单边放行：留痕路照记「未执行」、
    # 过滤路判 INVALID 照查，报告说没查其实查了（2026-08-03 同类分叉第三例）。
    if (not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION
            or not isinstance(disabled, list)
            or any(not isinstance(x, dict) or not isinstance(x.get("id"), str)
                   or not x.get("id") for x in disabled)):
        print("DOD_SELECTION: INVALID %s: disabled 字段非法" % path, file=sys.stderr)
        print("处置：修正该文件；或删除它，脚本会回落到全项都跑。", file=sys.stderr)
        return []
    # gate 必填且必须是 checklist 里真实存在的 gate（与过滤路 dod_project 同口径）：
    # 过滤路按 entry.gate == --gate 匹配，缺失/拼错的条目在那边永不生效；这里若照记
    # 就成了「报告说没查、其实照样查」的两路分叉（2026-08-03 缺陷）。
    # checklist 读不到时取值域无法核对，同样收紧为「关项不生效」（宁可多查）。
    if disabled:
        valid = _valid_gates(root)
        for i, entry in enumerate(disabled):
            g = entry.get("gate")
            if not isinstance(g, str) or valid is None or g not in valid:
                print("DOD_SELECTION: INVALID %s: disabled[%d].gate 缺失或不是已知 gate"
                      % (path, i), file=sys.stderr)
                print("处置：修正该条目；或删除该文件，脚本会回落到全项都跑。",
                      file=sys.stderr)
                return []
    if data.get("confirmed") is not True:
        # fail-safe 方向是收紧：未确认 = 不关任何项
        return []
    return disabled


def resolve_scope(root):
    """INTERFACE §6.1。纯函数，只读 <root>/structure_profile.json 的 funding_scheme
    与 <root>/data/dod_selection.json 的 disabled[]。无缓存、无隐藏状态。
    return {"active": [...], "skipped": [{"id","name","reason","status"}, ...]}。"""
    active = [cid for cid, _ in NSFC_ONLY_CHECKS]
    if root is None:
        return {"active": active, "skipped": []}
    skipped = []
    try:
        status, data, _ = _inspect(root)   # 静默读：错误行由 load() 的调用方打，避免重复
    except Exception:
        status, data = "absent", None
    scheme = data.get("funding_scheme", "nsfc") if status == "ok" else "nsfc"
    if scheme == "other":
        for cid, name in NSFC_ONLY_CHECKS:
            skipped.append({"id": cid, "name": name,
                            "reason": "structure_profile.funding_scheme=other",
                            "status": "未执行"})
        active = []
    try:
        disabled = _dod_disabled(root)
    except Exception:
        disabled = []
    done = {e["id"] for e in skipped}
    names = dict(NSFC_ONLY_CHECKS)
    for entry in disabled:
        cid = str(entry.get("id"))
        if cid in done:
            continue
        done.add(cid)
        # ponytail: name 取用户在 dod_selection 里写的 reason（最像人读名），兜底用 id
        skipped.append({"id": cid,
                        "name": names.get(cid) or str(entry.get("reason") or cid),
                        "reason": "dod_selection.disabled",
                        "status": "未执行"})
        if cid in active:
            active.remove(cid)
    return {"active": active, "skipped": skipped}


# =========================================================================
# round21 T3：大纲闸口的唯一作用域裁定（prewrite_gate / delegate_write /
# outline_manager 三处都 import 这里，谁都不许再手写字符串比较）
# =========================================================================

# 段落级大纲受管的节号全集。P1 恒受管（round19 现状）；P2 只在四维表被关掉的
# 项目（非国自然）里受管，见 is_managed。
MANAGED_SECTIONS = ("P1", "P2")

# 认三种形态（round21 实测）：
#   P2           裸节标识（内置写作顺序、delegate_write --section）
#   P2_研究内容   结构真源 chapters[].filename 主干（有 chapters 的项目）
#   P2.3         点分子节——流程不产，但 section_regex 允许手敲，必须堵（round19 同款洞）
# P20 / P2X / P2abc 不会被误判成 P2：第一段数字之后要么结束、要么是 . 或 _ 分隔符。
_SECTION_NUM_RE = re.compile(r"^(P\d+)(?:[._].*)?$")


def section_number_of(section):
    """把节标识归一成节号（"P1"/"P2"/...）；形态不认返回 None。只管形态，不管受不受管。"""
    if not isinstance(section, str):
        return None
    m = _SECTION_NUM_RE.match(section)
    return m.group(1) if m else None


def safe_resolve_scope(root):
    """resolve_scope 的硬化壳：任何坏形态都收敛成空 scope（= 国自然最严口径），
    绝不抛、绝不 traceback。skipped 逐元素清洗：不是对象、或没有非空字符串 id 的
    元素直接丢弃（缺 id 的元素不匹配任何检查，留着只会污染报告），好元素照常生效。
    """
    empty = {"active": [], "skipped": []}
    try:
        scope = resolve_scope(root)
    except Exception:
        sys.stderr.write("PREWRITE_GATE: WARN structure_profile unavailable, "
                         "all NSFC checks enforced\n")
        return dict(empty)
    if not isinstance(scope, dict):
        sys.stderr.write("PREWRITE_GATE: WARN structure_profile unavailable, "
                         "all NSFC checks enforced\n")
        return dict(empty)
    skipped = scope.get("skipped")
    if not isinstance(skipped, list):
        skipped = []
    clean = [e for e in skipped
             if isinstance(e, dict) and isinstance(e.get("id"), str) and e.get("id")]
    active = scope.get("active")
    return {"active": list(active) if isinstance(active, list) else [],
            "skipped": clean}


def v_rules_disabled(root):
    """四维表校验（HRCK-V-RULES）关没关。全仓唯一定义处（round21 N1）。"""
    skipped = safe_resolve_scope(root).get("skipped") or []
    return "HRCK-V-RULES" in {e.get("id") for e in skipped}


def scheme_is_other(root):
    """全仓「这是不是非国自然项目」的唯一判据（round23 由 _p2_outline_scope_enabled
    提成公开函数，函数体原样搬、行为零变化；round22 T3 修正判据）。
    仍走 safe_resolve_scope（继承 round21 全部 fail-safe：读口坏/坏 JSON/非法编码/
    未确认一律收敛空 scope → False = 国自然口径，绝不 traceback），但 skipped 里
    HRCK-V-RULES 条目按 reason 分流：
    - reason=dod_selection.disabled（用户 DoD 关项）只影响 DoD，**不反推项目类型**；
    - 其余 HRCK skipped（funding_scheme=other 写入的，或无 reason 的部分坏元素）
      沿 round21 行为视为「四维表已关 = 非国自然口径」。"""
    skipped = safe_resolve_scope(root).get("skipped") or []
    for entry in skipped:
        if entry.get("id") != "HRCK-V-RULES":
            continue
        if entry.get("reason") == "dod_selection.disabled":
            continue
        return True
    return False


def _p2_outline_scope_enabled(root):
    """P2 段落级大纲门是否启用 = 非国自然口径（round23 起纯转发 scheme_is_other）。"""
    return scheme_is_other(root)


def is_managed(section, root):
    """(节号, 是否受大纲闸口管)。P1 全体受管（round19 现状不变）；
    P2 只在非国自然口径（合法已确认 funding_scheme=other）时受管——round22 T3 起
    用户 DoD 关项（dod_selection.disabled）不再反推项目类型；其余节号一律不受管。
    读口坏掉时 P2 判不受管（国自然零影响）。"""
    num = section_number_of(section)
    if num == "P1":
        return num, True
    if num == "P2":
        return num, _p2_outline_scope_enabled(root)
    return num, False


# =========================================================================
# §2.1 extract-text
# =========================================================================

def _docx_block_texts(container, qn):
    """按文档顺序递归遍历 w:p / w:tbl（🔴 表格单元格文字必须进文本流，含嵌套表）。"""
    texts = []
    for child in container.iterchildren():
        if child.tag == qn("w:p"):
            texts.append("".join(t.text or "" for t in child.iter(qn("w:t"))))
        elif child.tag == qn("w:tbl"):
            for tr in child.findall(qn("w:tr")):
                for tc in tr.findall(qn("w:tc")):
                    texts.extend(_docx_block_texts(tc, qn))
    return texts


def _extract_docx(src):
    """返回 (rc, text)。rc: 0 成功 / 1 源损坏 / 2 用法错（缺库）。"""
    try:
        import docx
        from docx.oxml.ns import qn
    except ImportError:
        print("STRUCTURE_EXTRACT: USAGE 缺 python-docx，无法读取 .docx", file=sys.stderr)
        return 2, None
    try:
        document = docx.Document(src)
    except Exception:
        print("STRUCTURE_EXTRACT: SOURCE_CORRUPT 打不开（docx 非 zip 或已损坏）: %s" % src,
              file=sys.stderr)
        return 1, None
    text = "\n".join(_docx_block_texts(document.element.body, qn))
    return 0, text


def _extract_pdf(src):
    """依次尝试 pymupdf / pdfplumber / pypdf。返回 (rc, text)。"""
    extractors = []
    try:
        import fitz  # pymupdf

        def _fitz(path):
            with fitz.open(path) as doc:
                return "\n".join(page.get_text() for page in doc)
        extractors.append(_fitz)
    except ImportError:
        pass
    if not extractors:
        try:
            import pdfplumber

            def _plumber(path):
                with pdfplumber.open(path) as pdf:
                    return "\n".join((p.extract_text() or "") for p in pdf.pages)
            extractors.append(_plumber)
        except ImportError:
            pass
    if not extractors:
        try:
            from pypdf import PdfReader

            def _pypdf(path):
                return "\n".join((p.extract_text() or "") for p in PdfReader(path).pages)
            extractors.append(_pypdf)
        except ImportError:
            pass
    if not extractors:
        print("STRUCTURE_EXTRACT: USAGE 无可用 PDF 抽取器（pymupdf / pdfplumber / pypdf 都没装）",
              file=sys.stderr)
        return 2, None
    try:
        return 0, extractors[0](src)
    except Exception:
        print("STRUCTURE_EXTRACT: SOURCE_CORRUPT PDF 打不开或抽取失败: %s" % src, file=sys.stderr)
        return 1, None


def cmd_extract_text(args):
    src = args.source
    if not os.path.isfile(src):
        print("STRUCTURE_EXTRACT: USAGE --source 不存在: %s" % src, file=sys.stderr)
        return 2
    ext = os.path.splitext(src)[1].lower()
    if ext in (".md", ".markdown", ".txt"):
        with open(src, "rb") as f:
            raw = f.read()                     # 原文逐字节读入，一个字符不改
        text = raw.decode("utf-8", errors="replace")
        out_bytes = raw
    elif ext == ".docx":
        rc, text = _extract_docx(src)
        if rc:
            return rc
        if len(text.encode("utf-8")) < MIN_BODY_BYTES:   # §9 裁决 3：仅 pdf/docx 判此项
            print("STRUCTURE_EXTRACT: SOURCE_CORRUPT 抽出正文不足 200 字，疑为扫描件: %s" % src,
                  file=sys.stderr)
            return 1
        out_bytes = text.encode("utf-8")
    elif ext == ".pdf":
        rc, text = _extract_pdf(src)
        if rc:
            return rc
        if len(text.encode("utf-8")) < MIN_BODY_BYTES:
            print("STRUCTURE_EXTRACT: SOURCE_CORRUPT 抽出正文不足 200 字，疑为扫描件: %s" % src,
                  file=sys.stderr)
            return 1
        out_bytes = text.encode("utf-8")
    else:
        print("STRUCTURE_EXTRACT: USAGE 不支持的扩展名 %s（支持 .md/.markdown/.txt/.docx/.pdf）"
              % (ext or "(无)"), file=sys.stderr)
        return 2

    workdir = args.work_dir
    os.makedirs(workdir, exist_ok=True)
    text_path = os.path.join(workdir, "structure_source.txt")
    lines_path = os.path.join(workdir, "structure_source.lines.tsv")
    with open(text_path, "wb") as f:
        f.write(out_bytes)

    # 短行取景框：<char_offset>\t<原始行>，只收 strip 后长度 1–60 的行
    rows = []
    offset = 0
    for line in text.split("\n"):
        stripped = line.strip()
        if 1 <= len(stripped) <= SHORT_LINE_MAX:
            rows.append("%d\t%s" % (offset, line))
        offset += len(line) + 1
    with open(lines_path, "w", encoding="utf-8") as f:
        f.write("\n".join(rows) + ("\n" if rows else ""))

    text_len = len(text)                       # §9 裁决 2：字符数
    large = text_len > LARGE_CHARS
    if large:
        print("STRUCTURE_EXTRACT: SOURCE_LARGE 投影 %d 字符，建议优先读短行取景框 %s"
              % (text_len, lines_path), file=sys.stderr)
    print(json.dumps({"ok": True, "text": text_path, "lines": lines_path,
                      "text_len": text_len, "short_lines": len(rows),
                      "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                      "large": large}, ensure_ascii=False))
    return 0


# =========================================================================
# §2.3 verify —— 防编造的唯一闸门
# =========================================================================

_LEADING_NUM_RE = re.compile(r"^[（(]?[一二三四五六七八九十百0-9IVXivx]+[）)、.．]\s*")
# 净化表必须与 _validate 的 filename 规则对齐（2026-08-03 缺陷）：`.` 也换掉——
# 标题含连续点号（2..5）或以点结尾（拼上 .md 变 "..md"）都会造出 _validate 拒收
# 的 ".."，用户没手改任何东西就被 confirm 卡死。控制字符一并换掉（\s 只盖住
# \t\n\r 等几个，\x01 这类照样能进文件名）。对齐由 TestAutogenMatchesValidate
# 不变量测试盯着：生成结果必须原样过 _validate。
_FN_BAD_RE = re.compile(r'[/\\:*?"<>|\s.\x00-\x1f\x7f]')


def _autogen_filename(title, order, used):
    """§2.3 filename 预填规则（确定性）：剥一次前导编号 → 前 12 字 → 换非法字符
    （含 `.` 与控制符，保证产物天然过 _validate）→ section_{order}_{简称}.md；
    文件名撞了 → 追加 _2、_3…（递增，防三章同名再撞）。"""
    stem = _LEADING_NUM_RE.sub("", title, count=1)[:12]
    stem = _FN_BAD_RE.sub("_", stem)
    base = "section_%s_%s" % (order, stem)
    name = base + ".md"
    n = 2
    while name in used:
        name = "%s_%d.md" % (base, n)
        n += 1
    used.add(name)
    return name


def _read_json_file(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cmd_verify(args):
    for label, path in (("--draft", args.draft), ("--text", args.text)):
        if not os.path.isfile(path):
            print("用法错误：%s 指向的文件不存在: %s" % (label, path), file=sys.stderr)
            return 2
    try:
        draft = _read_json_file(args.draft)
        if not isinstance(draft, dict):
            raise ValueError("draft 顶层必须是对象")
    except Exception:
        print("用法错误：--draft 不是合法 JSON 对象: %s" % args.draft, file=sys.stderr)
        return 2
    with open(args.text, encoding="utf-8") as f:
        text = f.read()

    chapters = draft.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        print("STRUCTURE_VERIFY: EMPTY")
        print("未识别到章节结构。请手工填写结构文件，最小合法样例如下：")
        print(json.dumps(MINIMAL_EXAMPLE, ensure_ascii=False))
        print("处置：把上面的样例存为 <项目根>/structure_profile.json，再按实际章节增改。")
        return 3

    failures, checked = [], []
    for i, ch in enumerate(chapters):
        if not isinstance(ch, dict):
            failures.append("- chapters[%d] 不是对象" % i)
            continue
        title = ch.get("title")
        if not isinstance(title, str) or not title or len(title) > 200:
            failures.append("- chapters[%d].title 对不上原文：%s" % (i, title))
            continue
        off = text.find(title)     # 不变量：text[off:off+len(title)] == title
        if off < 0:
            failures.append("- chapters[%d].title 对不上原文：%s" % (i, title))
            continue
        order = ch.get("order")
        if not isinstance(order, int) or isinstance(order, bool):
            failures.append("- chapters[%d].order 必须是整数：%r" % (i, order))
            continue
        item = {"title": title, "order": order, "required": True, "char_offset": off}
        occurrences = text.count(title)
        if occurrences > 1:        # §2.3.4：重复不算失败，取首现，记次数给用户核对
            item["occurrences"] = occurrences
        if "word_max" in ch:
            word_max = ch["word_max"]
            evidence = ch.get("word_max_evidence")
            ev_ok = isinstance(evidence, str) and evidence and text.find(evidence) >= 0
            num = re.search(r"\d+", evidence) if isinstance(evidence, str) else None
            if (not ev_ok or num is None
                    or not isinstance(word_max, int) or isinstance(word_max, bool)
                    or int(num.group()) != word_max):
                failures.append("- chapters[%d].word_max_evidence 对不上原文或与 word_max 数字不符：%s"
                                % (i, evidence))
                continue
            item["word_max"] = word_max
            item["word_max_evidence"] = evidence
        checked.append(item)

    if failures:
        # 整批拒收：不写候选、不写真源（部分落盘会产出「一半核过一半编的」混合物）
        print("STRUCTURE_VERIFY: NOT_IN_SOURCE")
        for line in failures:
            print(line)
        print("处置：请逐字节照抄原文重新提取草案；或让用户按最小样例手工填写结构文件。")
        return 3

    used = set()
    for item in checked:
        item["filename"] = _autogen_filename(item["title"], item["order"], used)
        item["filename_autogen"] = True

    candidate = {"confirmed": False, "source": "extracted",
                 "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    for key in ("source_file", "funding_scheme", "template_name"):
        if key in draft:
            candidate[key] = draft[key]
    candidate["chapters"] = checked

    out_path = args.out
    parent = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(parent, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(candidate, f, ensure_ascii=False, indent=2)

    by_order = sorted(checked, key=lambda c: c["order"])
    offs = [c["char_offset"] for c in by_order]
    print(json.dumps({
        "ok": True, "candidate": out_path, "chapters": len(checked),
        "no_word_max": sum(1 for c in checked if "word_max" not in c),
        "duplicated_titles": sum(1 for c in checked if c.get("occurrences", 1) > 1),
        "offset_monotonic": all(a <= b for a, b in zip(offs, offs[1:])),
    }, ensure_ascii=False))
    return 0


# =========================================================================
# §2.4 / §2.5 confirm —— 全仓唯一写 structure_profile.json 的地方
# =========================================================================

WOBBLE_LINES = (
    "⚠️ 源文件未变（sha256 相同），但两次提取结果不同 —— 这是 AI 提取的固有波动，"
    "不是你的文件被改了。",
    "全链只读你的原件，从未写过它。请以你确认的那一份为准。",
)


def _candidate_chapters(cand):
    """候选校验；非法抛 ValueError（消息 = <字段路径> <原因>，写法同 §3.2）。

    chapters / funding_scheme 规则不自己另写一份，而是把候选拼成「confirm 落盘后
    形状」的最小 probe 喂给 _validate 预检——同一把尺，保证 confirm 绝不写出一份
    show/_inspect 立刻判 INVALID 的真源（2026-08-03 缺陷：非法 filename 曾被
    confirm 放行落盘，用户拿到一份"确认成功、其实死掉"的结构文件）。"""
    if not isinstance(cand, dict):
        raise ValueError("(top-level) 候选顶层必须是对象")
    chapters = cand.get("chapters")
    # 候选与真源在此处语义不同：真源缺 chapters 键是合法缺省（§1.4），候选必须有
    if not isinstance(chapters, list) or not chapters:
        raise ValueError("chapters 候选 chapters 必须是非空 list")
    # source 按 cmd_confirm 落盘时的同一条归一化规则拼 probe（非法值落盘为 extracted）
    probe = {"schema_version": SCHEMA_VERSION,
             "source": cand.get("source") if cand.get("source") in SOURCES else "extracted",
             "chapters": chapters}
    if "funding_scheme" in cand:
        probe["funding_scheme"] = cand["funding_scheme"]
    bad = _validate(probe)
    if bad:
        raise ValueError("%s %s" % bad)
    return chapters


def _int_order(ch):
    order = ch.get("order")
    return order if isinstance(order, int) and not isinstance(order, bool) else 0


def cmd_confirm(args):
    if not os.path.isfile(args.from_path):
        print("候选文件不存在: %s" % args.from_path, file=sys.stderr)
        return 2
    if not os.path.isdir(args.root):
        print("用法错误：--root 不是目录: %s" % args.root, file=sys.stderr)
        return 2
    try:
        cand = _read_json_file(args.from_path)
        chapters = _candidate_chapters(cand)
    except Exception as e:
        print("STRUCTURE_CANDIDATE: INVALID %s: %s" % (args.from_path, e), file=sys.stderr)
        return 1

    # 落盘章节 = §1.1 schema 字段；丢弃 filename_autogen / char_offset /
    # occurrences / word_max_evidence（只存结构，验证痕迹不进真源）
    new_chapters = []
    for ch in chapters:
        item = {"filename": ch["filename"]}
        if isinstance(ch.get("title"), str):
            item["title"] = ch["title"]
        item["order"] = ch["order"]
        if isinstance(ch.get("required"), bool):
            item["required"] = ch["required"]
        if "word_max" in ch:
            item["word_max"] = ch["word_max"]
        new_chapters.append(item)

    profile = {"schema_version": SCHEMA_VERSION, "confirmed": True,
               "confirmed_at": datetime.now(timezone.utc).isoformat()}
    profile["source"] = cand.get("source") if cand.get("source") in SOURCES else "extracted"
    for key in ("source_file", "source_sha256", "template_name", "funding_scheme"):
        if key in cand:
            profile[key] = cand[key]
    if args.note is not None:
        profile["note"] = args.note

    target = _profile_path(args.root)
    exists = os.path.exists(target)
    if exists and not args.replace:
        print("STRUCTURE_PROFILE: EXISTS %s" % target)
        print("已有确认过的结构真源。重提请加 --replace（覆盖前展示新旧 diff，旧版进 history）。")
        return 2

    history, diff_lines, changed = [], [], False
    if exists:
        try:
            old = _read_json_file(target)
            if not isinstance(old, dict):
                old = {}
        except Exception:
            old = {}
        old_chs = [c for c in (old.get("chapters") or []) if isinstance(c, dict)] \
            if isinstance(old.get("chapters"), list) else []
        old_by_title = {c.get("title"): c for c in old_chs}
        new_by_title = {c.get("title"): c for c in new_chapters}
        added = [t for t in new_by_title if t not in old_by_title]
        removed = [t for t in old_by_title if t not in new_by_title]
        renamed = [t for t in new_by_title if t in old_by_title
                   and new_by_title[t].get("filename") != old_by_title[t].get("filename")]
        common = [t for t in new_by_title if t in old_by_title]
        old_seq = sorted(common, key=lambda t: (_int_order(old_by_title[t]), str(t)))
        new_seq = sorted(common, key=lambda t: (_int_order(new_by_title[t]), str(t)))
        reordered = [b for a, b in zip(old_seq, new_seq) if a != b]
        for t in added:
            diff_lines.append("+新增 %s" % t)
        for t in removed:
            diff_lines.append("-删除 %s" % t)
        for t in renamed:
            diff_lines.append("~改名 %s" % t)
        for t in reordered:
            diff_lines.append("↕顺序变化 %s" % t)
        changed = bool(added or removed or renamed or reordered)

        summary = {"replaced_at": profile["confirmed_at"]}
        for key in ("confirmed_at", "template_name", "source_sha256"):
            if key in old:
                summary[key] = old[key]
        summary["chapters"] = [{k: c[k] for k in ("filename", "title", "order") if k in c}
                               for c in old_chs]
        history = (old.get("history") if isinstance(old.get("history"), list) else []) + [summary]

        for line in diff_lines:
            print(line)
        if (changed and old.get("source_sha256")
                and old.get("source_sha256") == profile.get("source_sha256")):
            # §2.5.3：消除「我文件被改坏了」的疑虑，字面量不许改
            for line in WOBBLE_LINES:
                print(line)

    profile["history"] = history
    profile["chapters"] = new_chapters
    with open(target, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    print(json.dumps({"ok": True, "structure_profile": target,
                      "chapters": len(new_chapters)}, ensure_ascii=False))
    return 0


# =========================================================================
# §2.4 show —— 诊断唯一入口
# =========================================================================

def _builtin_chapters():
    """内置国自然 13 件，形状与 chapters[] 同构（§9 裁决 4：没有的键不出现）。
    真源是 section_merger.ORDER 常量，不另抄一份防漂移。"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import section_merger
    return [{"filename": name, "order": (i + 1) * 10}
            for i, name in enumerate(section_merger.ORDER)]


def cmd_show(args):
    status, data, lines = _inspect(args.root)
    for line in lines:
        print(line, file=sys.stderr)
    if status in ("corrupt", "invalid"):
        return 1                                   # §9 裁决 5：CORRUPT 与 INVALID 均 exit 1
    if status == "ok":
        out = {"effective_source": "file"}
        out.update(data)
        print(json.dumps(out, ensure_ascii=False))
        missing = ["chapters[%d].word_max" % i
                   for i, ch in enumerate(data.get("chapters", []))
                   if "word_max" not in ch]
        if missing:                                # §1.3：现算不落盘
            print("未提取字段: %s" % ", ".join(missing))
        return 0
    # absent（正常态，零错误行）与 unconfirmed（错误行已打）都回内置默认
    print(json.dumps({"effective_source": "builtin_nsfc_default",
                      "funding_scheme": "nsfc",
                      "chapters": _builtin_chapters()}, ensure_ascii=False))
    return 0


# =========================================================================
# CLI
# =========================================================================

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="structure_profile.py",
        description="结构真源提取链：extract-text（投影）→ AI 写草案 → verify（逐字节核验）"
                    "→ 用户确认 → confirm（唯一落盘处）。show 为诊断入口。"
                    "AI 不得在用户逐条确认前运行 confirm。")
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("extract-text", help="把用户原件投影成纯文本（只读原件）")
    p.add_argument("--source", required=True, help="用户原件（.md/.markdown/.txt/.docx/.pdf）")
    p.add_argument("--work-dir", default="tmp", help="投影输出目录（默认 tmp）")

    p = sub.add_parser("verify", help="逐字节核验 AI 草案；任一条对不上整批拒收")
    p.add_argument("--draft", required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--out", default=os.path.join("tmp", "structure_candidate.json"))

    p = sub.add_parser("confirm", help="把用户确认过的候选落盘为结构真源（唯一写入口）")
    p.add_argument("--from", dest="from_path", required=True)
    p.add_argument("--root", required=True)
    p.add_argument("--note", default=None, help="用户确认原话摘要")
    p.add_argument("--replace", action="store_true")

    p = sub.add_parser("show", help="展示当前生效的结构（file 或内置默认）")
    p.add_argument("--root", default=".")

    args = parser.parse_args(argv)
    if args.cmd == "extract-text":
        return cmd_extract_text(args)
    if args.cmd == "verify":
        return cmd_verify(args)
    if args.cmd == "confirm":
        return cmd_confirm(args)
    if args.cmd == "show":
        return cmd_show(args)
    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
