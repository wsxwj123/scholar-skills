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

# 匹配两类首展定义模式（括号兼容半角 () 与全角 （）；逗号兼容半角 , 与全角 ，）：
#   A) 英文惯例 "Full Name (ABBR)"：全称在括号外，括号内仅 ABBR。
#      如 "reactive oxygen species (ROS)" / "Photodynamic Therapy (PDT)"。
#   B) 中文惯例 "（Full Name，ABBR）"：全称与 ABBR 同在括号内、以逗号分隔。
#      如 "聚焦超声（focused ultrasound，FUS）"。
# 两类合并为一个正则，full name 落在 group(1) 或 group(3)，ABBR 落在 group(2) 或 group(4)。
DEFINITION_PATTERN = re.compile(
    r"\b((?:[A-Za-z][\w\-]*\s+){1,6})[（(](" + _ABBR_TOKEN + r")[）)]"
    r"|[（(]((?:[A-Za-z][\w\-]*\s*){1,6})[，,]\s*(" + _ABBR_TOKEN + r")[）)]"
)

# 匹配裸用缩写（独立词，全大写/数字，可含 -希腊字母后缀；不产生悬空尾 "-"）
BARE_ABBR_PATTERN = re.compile(r"\b(" + _ABBR_TOKEN + r")\b")


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
        with open(filepath, "r", encoding="utf-8") as f:
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
            with open(fp, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            continue
        for match in DEFINITION_PATTERN.finditer(content):
            # 两条分支：A) group(1)/group(2) 英文外置全称；B) group(3)/group(4) 中文括号内全称。
            full_name = (match.group(1) or match.group(3) or "").strip()
            abbr = (match.group(2) or match.group(4) or "").strip().upper()
            first_def.setdefault(abbr, []).append((fp, full_name))
    return first_def


def scan_bare_uses(files: list[str], defined: set) -> dict:
    """abbr_upper -> [file, ...]，仅记录裸用且未定义的缩写。"""
    bare: dict = {}
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                content = f.read()
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
