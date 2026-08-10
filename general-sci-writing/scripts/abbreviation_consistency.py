#!/usr/bin/env python3
"""abbreviation_consistency.py — Phase 10 缩略词一致性扫描门禁。

逻辑：
1. 读 abbreviations.json 取已定义清单（abbr -> full_name + first_defined_in）
2. 扫 manuscripts/*.md，识别 `Full Name (ABBR)` 模式首次定义出现处
3. 报告：
   - duplicate_definition: 同一缩写在多个 manuscript 文件首次定义
   - undefined_use: 直接用了 ABBR，但 abbreviations.json 缺、且不在 UNIVERSAL_ABBREVIATIONS 白名单
   - title_abbreviation: Title 出现缩写（在 01_*Abstract* 之前的 Title 文件或文件首行 # 标题中）
4. 任一问题 → exit 1；无问题 → exit 0
5. 依赖（style_checker/ref_section）导入失败 → exit 2 并中止，不出判定
   （"检查器自身坏了"与"检查发现问题"的 exit 1 分开，见下方 fail-closed 注释）

UNIVERSAL_ABBREVIATIONS 与 state_manager.py 保持同步副本（如 state_manager 更新需同步本文件）。

被 SKILL.md Phase 10 step7 / DoD G15 引用。
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

# 复用 style_checker 的散文提取（剥离参考文献块 / 图注 / 代码块 / CRediT 行）。
# 参考文献区充斥作者姓名首字母缩写（"Zhang YW"、"Cao MM"），不剥离会被误判为
# "未定义缩略语"，是真稿最大误报源（rw 同款文件已先行，本文件跟进同一口径）。
# fail-closed：import 失败就不出判定（round16 T3）。此前是 fail-soft 退回原文——
# 剥离静默失效，参考文献区重新进扫描，用户看到的是"YW/MM 未定义"这种假报警，
# 只会照着去改 abbreviations.json，反而污染自己的数据，而且永远不知道剥离已经没了。
# 依赖全在本技能 scripts/ 内（style_checker 只 import 标准库 + 同目录 ref_section），
# import 失败＝安装坏了，不是"环境缺可选件"，所以拒判比降级正确。
_STRIP_IMPORT_ERROR = None
try:
    _sc_dir = os.path.dirname(os.path.abspath(__file__))
    if _sc_dir not in sys.path:
        sys.path.insert(0, _sc_dir)
    from style_checker import _extract_prose as _strip_nonprose
except Exception as _exc:  # pragma: no cover
    _STRIP_IMPORT_ERROR = _exc

    def _strip_nonprose(text: str) -> str:
        # 库级调用者也别想拿到静默降级的结果。
        raise RuntimeError(
            f"style_checker._extract_prose 不可用，无法剥离非正文: {_STRIP_IMPORT_ERROR}")

# 同步自 state_manager.py:UNIVERSAL_ABBREVIATIONS（2.20.0），改一处需同步另一处。
UNIVERSAL_ABBREVIATIONS = {
    "DNA", "RNA", "PCR", "HIV", "WHO", "FDA", "NIH", "USA", "UK", "EU",
    "AI", "ML", "API", "URL", "PDF", "HTML", "JSON", "XML", "CSV",
    "ATP", "ADP", "GTP", "NADH", "NADPH", "CO2", "H2O", "NaCl",
    "pH", "RNA-seq", "DNA-seq", "ChIP-seq", "RT-PCR", "qPCR", "ELISA",
    "FACS", "FISH", "GFP", "RFP", "BSA", "PBS", "DMSO", "EDTA",
    "SD", "SEM", "CI", "OD", "MW", "kDa", "bp", "kb",
}

# 缩写 token 子模式：大写起头，总长 >=2（避免抓单字母 "A"/"I"），
# 连字符段后必须跟内容（禁悬空尾 "-"），连字符后允许希腊字母（α-ωΑ-Ω），
# 以完整捕获 IFN-γ / TGF-β / IL-1β 等而非残缺的 "IFN-"。
_ABBR_TOKEN = r"[A-Z](?:[A-Z0-9]+(?:-[A-Z0-9Α-Ωα-ω]+)*|(?:-[A-Z0-9Α-Ωα-ω]+)+)"

# 匹配三类首展定义模式（括号兼容半角 () 与全角 （）；逗号兼容半角 , 与全角 ，）：
#   A) 英文惯例 "Full Name (ABBR)"：全称在括号外，括号内仅 ABBR。
#      如 "reactive oxygen species (ROS)" / "Photodynamic Therapy (PDT)"。
#   B) 中文惯例 "（Full Name，ABBR）"：全称与 ABBR 同在括号内、以逗号分隔。
#      如 "聚焦超声（focused ultrasound，FUS）"。
#   C) 中文外置全称 "中文全称（ABBR）"：全称是括号外紧邻的一段中文（可含数字/
#      连字符，如 "程序性死亡受体1（PD-1）"）。中文无空格分词，无法像 A 那样
#      按词定界，取括号前紧邻的最长中文串；full name 仅供报告参考，判定义只看 ABBR。
#      括号内必须是纯 ABBR token，"（对照组）"这类非定义括号不会命中。
# 三类合并为一个正则，full name 落在 group(1)/(3)/(5)，ABBR 落在 group(2)/(4)/(6)。
DEFINITION_PATTERN = re.compile(
    r"\b((?:[A-Za-z][\w\-]*\s+){1,6})[（(](" + _ABBR_TOKEN + r")[）)]"
    r"|[（(]((?:[A-Za-z][\w\-]*\s*){1,6})[，,]\s*(" + _ABBR_TOKEN + r")[）)]"
    r"|((?:[一-鿿][\w\-]*){1,6})[（(](" + _ABBR_TOKEN + r")[）)]"
)

# 匹配裸用缩写（独立 token：两侧不得是词字符）。
# 此前用 \b：Python 的 \w 含 CJK，"ROS可诱导" 里 S 与 可 都是词符、边界不成立，
# 缩写后紧跟汉字的裸用永远扫不出。这里的词字符 = `\w` 减 CJK 类脚本
# （`[^\W…]` 即"是 \w 且不在这些区段"）：不用空格分词的 CJK/假名/谚文相黏即边界，
# 其余 \w 一律留在词字符侧——包括 µ(U+00B5)、希腊字母这类非 ASCII 字母，
# 所以 "µCT"/"µMRI" 这种合法复合写法不会被拆出裸 "CT"（round16 T4-gsw；
# 旧版枚举 [A-Za-z0-9_Α-Ωα-ω] 只兜住希腊字母，µ 漏网直接判死门）。
# 纯英文文本行为与旧 \b 逐条一致（test_a4_cjk_bare_abbr.py 对照锁死）。
# "PROS可" 这类整 token 按整体匹配，不会从里面抠出伪缩写 ROS。
_CJK_SCRIPTS = r"぀-ヿ㐀-䶿一-鿿가-힯豈-﫿"
_WORD_CHAR = r"[^\W" + _CJK_SCRIPTS + r"]"
BARE_ABBR_PATTERN = re.compile(
    r"(?<!" + _WORD_CHAR + r")(" + _ABBR_TOKEN + r")(?!" + _WORD_CHAR + r")"
)


def load_defined(root: str) -> dict:
    """返回 abbr_upper -> entry dict。"""
    path = os.path.join(root, "abbreviations.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return {}
    if isinstance(data, dict):
        for key in ("items", "abbreviations", "data"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            return {}
    if not isinstance(data, list):
        return {}
    out = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        abbr = (item.get("abbr") or "").strip().upper()
        if abbr:
            out[abbr] = item
    return out


def collect_manuscript_files(root: str) -> list[str]:
    pattern = os.path.join(root, "manuscripts", "*.md")
    files = sorted(glob.glob(pattern))
    # 排除合并稿与派生物（大小写不敏感，与 merge_manuscript.py 对齐）
    return [
        f for f in files
        if os.path.basename(f).lower() != "full_manuscript.md"
        and not os.path.basename(f).startswith("Draft_Round")
    ]


def find_title_file(files: list[str]) -> str | None:
    """寻找 Title 文件：文件名含 'title' 或 '00_'；否则用 Abstract 文件首行 # 标题。"""
    for f in files:
        name = os.path.basename(f).lower()
        if "title" in name or name.startswith("00_"):
            return f
    return None


def extract_title_line(filepath: str) -> str:
    """从文件首个非空 # 一级标题行取 Title 文本。"""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("# ") and not stripped.startswith("## "):
                    return stripped.lstrip("# ").strip()
    except OSError:
        return ""
    return ""


def scan_definitions(files: list[str]) -> dict:
    """abbr_upper -> [(file, full_name), ...] 按出现顺序。"""
    first_def: dict = {}
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                content = _strip_nonprose(f.read())
        except OSError:
            continue
        for match in DEFINITION_PATTERN.finditer(content):
            # 三条分支：A) group(1)/(2) 英文外置全称；B) group(3)/(4) 中文括号内全称；
            # C) group(5)/(6) 中文外置全称。
            full_name = (match.group(1) or match.group(3) or match.group(5) or "").strip()
            abbr = (match.group(2) or match.group(4) or match.group(6) or "").strip().upper()
            first_def.setdefault(abbr, []).append((fp, full_name))
    return first_def


def scan_bare_uses(files: list[str], defined: set) -> dict:
    """abbr_upper -> [file, ...]，仅记录裸用且未定义的缩写。"""
    bare: dict = {}
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                content = _strip_nonprose(f.read())
        except OSError:
            continue
        # 先剥离定义模式，避免把定义处也算作裸用
        stripped_content = DEFINITION_PATTERN.sub("", content)
        for match in BARE_ABBR_PATTERN.finditer(stripped_content):
            abbr = match.group(1).strip().upper()
            if abbr in UNIVERSAL_ABBREVIATIONS:
                continue
            if abbr in defined:
                continue
            bare.setdefault(abbr, []).append(fp)
    return bare


def scan_title_abbreviations(title_text: str) -> list[str]:
    if not title_text:
        return []
    found = []
    for match in BARE_ABBR_PATTERN.finditer(title_text):
        abbr = match.group(1).strip().upper()
        if abbr in UNIVERSAL_ABBREVIATIONS:
            continue
        found.append(abbr)
    return found


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 10 缩略词一致性扫描：重复定义 / 未定义就用 / Title 出现缩写。"
        )
    )
    parser.add_argument("--root", required=True,
                        help="project root，含 abbreviations.json 与 manuscripts/")
    args = parser.parse_args()

    # 剥离非正文这一层拿不到就不许出判定：带着失效的剥离扫，参考文献区的作者
    # 首字母会全变成"未定义缩略语"。exit 2 与"稿子有问题"的 exit 1 分开，
    # 一眼能分出是环境坏了还是稿子该改。
    if _STRIP_IMPORT_ERROR is not None:
        print(f"ABBR_CHECK_ERROR: 依赖 style_checker._extract_prose 导入失败"
              f"（{_STRIP_IMPORT_ERROR}），无法剥离参考文献/图注/代码块，"
              f"判定不可信，已中止。请检查本技能 scripts/ 目录是否完整"
              f"（style_checker.py、ref_section.py）。")
        return 2

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"ABBR_CHECK_FAIL: root not a directory: {root}")
        return 1

    defined_map = load_defined(root)
    defined = set(defined_map.keys())
    files = collect_manuscript_files(root)
    if not files:
        print("ABBR_CHECK_OK: no manuscript files found")
        return 0

    issues: list[str] = []

    # 1. 重复定义
    definitions = scan_definitions(files)
    for abbr, occurrences in definitions.items():
        distinct_files = {os.path.basename(fp) for fp, _ in occurrences}
        if len(distinct_files) > 1:
            issues.append(
                f"duplicate_definition: {abbr} first-defined in multiple files: "
                f"{sorted(distinct_files)}"
            )

    # 2. 未定义就用（综合 abbreviations.json + 本次扫到的 inline definition）
    all_defined = defined | set(definitions.keys())
    bare_uses = scan_bare_uses(files, all_defined)
    for abbr, fps in bare_uses.items():
        files_short = sorted({os.path.basename(fp) for fp in fps})
        issues.append(
            f"undefined_use: {abbr} used without definition in {files_short}"
        )

    # 3. Title 出现缩写
    title_file = find_title_file(files)
    title_text = ""
    if title_file:
        title_text = extract_title_line(title_file)
    if not title_text:
        # 兜底：取 Abstract 文件首个 # 一级标题
        for fp in files:
            if "abstract" in os.path.basename(fp).lower():
                title_text = extract_title_line(fp)
                if title_text:
                    break
    title_abbrs = scan_title_abbreviations(title_text)
    for abbr in title_abbrs:
        issues.append(
            f"title_abbreviation: {abbr} appears in Title ({title_text!r}); "
            f"titles must not contain abbreviations"
        )

    if issues:
        for line in issues:
            print(f"ABBR_CHECK_FAIL: {line}")
        return 1

    print(
        f"ABBR_CHECK_OK: defined={len(defined)} files_scanned={len(files)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
