#!/usr/bin/env python3
"""abbreviation_consistency.py — 综述缩略语一致性扫描门禁（review-writing 变体）。

移植自 general-sci-writing/scripts/abbreviation_consistency.py。差异：
- review-writing 没有 abbreviations.json 注册表，缩略语只在正文内联定义
  （`Full Name (ABBR)`），因此本变体纯扫稿件，不读注册表。
- 扫描目录为 `drafts/**/*.md`（递归，与 check_global_citation_sequence.py 对齐），
  排除 merge 衍生物（Full_Manuscript.md / Draft_Round*）。
- Title 取首个 draft 文件的一级 # 标题，或文件名含 'title'/'00_' 的文件。

逻辑（综述缩略语多 → B4 首次定义、B3 全文统一）：
  - duplicate_definition：同一缩写在多个 draft 文件首次定义（B3 全文统一）。
  - undefined_use：直接用了 ABBR，但全稿无内联定义、且不在白名单（B4 首次定义）。
  - title_abbreviation：Title 出现缩写（titles 不应含缩写）。
任一问题 → exit 1（与 gsw 一致：默认 fail-closed）；`--report-only` 时仅打印不阻断。

被 SKILL.md B3/B4 DoD 引用。
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys

# 复用 style_checker 的散文提取（剥离参考文献块 / figure legend / 代码块）。
# 综述参考文献区充斥作者姓名首字母缩写（"Zhang YW"、"Cao MM"），若不剥离会被
# 误判为"未定义缩略语"，是真稿最大误报源。fail-soft：import 失败则退回原文。
try:
    _sc_dir = os.path.dirname(os.path.abspath(__file__))
    if _sc_dir not in sys.path:
        sys.path.insert(0, _sc_dir)
    from style_checker import _extract_prose as _strip_nonprose
except Exception:  # pragma: no cover
    def _strip_nonprose(text: str) -> str:
        return text

# 同步自 general-sci-writing/scripts/abbreviation_consistency.py:UNIVERSAL_ABBREVIATIONS。
UNIVERSAL_ABBREVIATIONS = {
    "DNA", "RNA", "PCR", "HIV", "WHO", "FDA", "NIH", "USA", "UK", "EU",
    "AI", "ML", "API", "URL", "PDF", "HTML", "JSON", "XML", "CSV",
    "ATP", "ADP", "GTP", "NADH", "NADPH", "CO2", "H2O", "NaCl",
    "pH", "RNA-seq", "DNA-seq", "ChIP-seq", "RT-PCR", "qPCR", "ELISA",
    "FACS", "FISH", "GFP", "RFP", "BSA", "PBS", "DMSO", "EDTA",
    "SD", "SEM", "CI", "OD", "MW", "kDa", "bp", "kb",
}

# 缩写 token 子模式（与 gsw 同步）：大写起头，总长 >=2，连字符段后允许希腊字母，
# 完整捕获 IFN-γ / TGF-β / IL-1β 而非残缺 "IFN-"。
_ABBR_TOKEN = r"[A-Z](?:[A-Z0-9]+(?:-[A-Z0-9Α-Ωα-ω]+)*|(?:-[A-Z0-9Α-Ωα-ω]+)+)"

# 匹配定义模式，兼容半角/全角括号 [（(] [）)] 与全角逗号 [,，]（参考 sci2doc）。
# 两种形态：
#   A) 英文全称在括号外：  Full Name (ABBR) / Full Name（ABBR）
#   B) 全角场景全称在括号内、逗号分隔： 聚焦超声（focused ultrasound，FUS）
# 捕获组：group(1)=A 形态全称，group(2)=B 形态全称，group(3)=缩写。
DEFINITION_PATTERN = re.compile(
    r"(?:"
    r"((?:[A-Za-z][\w\-]*\s+){1,6})[（(]"
    r"|"
    r"[（(]\s*([A-Za-z][\w\- ]*?)\s*[,，]\s*"
    r")"
    r"(" + _ABBR_TOKEN + r")[）)]"
)

# 匹配裸用缩写。
BARE_ABBR_PATTERN = re.compile(r"\b(" + _ABBR_TOKEN + r")\b")


def is_merged_derivative(path: str) -> bool:
    name = os.path.basename(path).lower()
    return name == "full_manuscript.md" or (
        name.startswith("draft_round") and name.endswith("_manuscript.md")
    )


def collect_draft_files(drafts_dir: str) -> list[str]:
    pattern = os.path.join(drafts_dir, "**", "*.md")
    files = sorted(glob.glob(pattern, recursive=True))
    return [f for f in files if not is_merged_derivative(f)]


def find_title_file(files: list[str]) -> str | None:
    for f in files:
        name = os.path.basename(f).lower()
        if "title" in name or name.startswith("00_"):
            return f
    return files[0] if files else None


def extract_title_line(filepath: str) -> str:
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
    first_def: dict = {}
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                content = _strip_nonprose(f.read())
        except OSError:
            continue
        for match in DEFINITION_PATTERN.finditer(content):
            full_name = (match.group(1) or match.group(2) or "").strip()
            abbr = match.group(3).strip().upper()
            first_def.setdefault(abbr, []).append((fp, full_name))
    return first_def


def scan_bare_uses(files: list[str], defined: set) -> dict:
    bare: dict = {}
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                content = _strip_nonprose(f.read())
        except OSError:
            continue
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
            "综述缩略语一致性扫描（B3 全文统一 / B4 首次定义）："
            "重复定义 / 未定义就用 / Title 出现缩写。"
        )
    )
    parser.add_argument("--drafts-dir", default="drafts",
                        help="目录，含 review 草稿 *.md（递归扫描）")
    parser.add_argument("--report-only", action="store_true",
                        help="仅打印问题，不阻断（默认 fail-closed exit 1）")
    args = parser.parse_args()

    drafts_dir = os.path.abspath(args.drafts_dir)
    if not os.path.isdir(drafts_dir):
        print(f"ABBR_CHECK_FAIL: drafts dir not a directory: {drafts_dir}")
        return 0 if args.report_only else 1

    files = collect_draft_files(drafts_dir)
    if not files:
        print("ABBR_CHECK_OK: no draft files found")
        return 0

    issues: list[str] = []

    # 1. 重复定义（B3 全文统一）
    definitions = scan_definitions(files)
    for abbr, occurrences in definitions.items():
        distinct_files = {os.path.basename(fp) for fp, _ in occurrences}
        if len(distinct_files) > 1:
            issues.append(
                f"duplicate_definition: {abbr} first-defined in multiple files: "
                f"{sorted(distinct_files)}"
            )

    # 2. 未定义就用（B4 首次定义）
    all_defined = set(definitions.keys())
    bare_uses = scan_bare_uses(files, all_defined)
    for abbr, fps in bare_uses.items():
        files_short = sorted({os.path.basename(fp) for fp in fps})
        issues.append(
            f"undefined_use: {abbr} used without definition in {files_short}"
        )

    # 3. Title 出现缩写
    title_file = find_title_file(files)
    title_text = extract_title_line(title_file) if title_file else ""
    for abbr in scan_title_abbreviations(title_text):
        issues.append(
            f"title_abbreviation: {abbr} appears in Title ({title_text!r}); "
            f"titles must not contain abbreviations"
        )

    if issues:
        for line in issues:
            print(f"ABBR_CHECK_FAIL: {line}")
        return 0 if args.report_only else 1

    print(f"ABBR_CHECK_OK: defined={len(definitions)} files_scanned={len(files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
