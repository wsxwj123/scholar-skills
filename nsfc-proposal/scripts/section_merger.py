#!/usr/bin/env python3
"""Merge section files into final manuscript."""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
from pathlib import Path

ORDER = [
    "00_摘要_中文.md",
    "00_摘要_英文.md",
    "B1_预算说明_直接费用.md",
    "B2_预算说明_合作外拨.md",
    "B3_预算说明_其他来源.md",
    "P1_立项依据.md",
    "P2_研究内容.md",
    "P3_1_研究基础与可行性分析.md",
    "P3_2_工作条件.md",
    "P3_3_正在承担的相关项目.md",
    "P3_4_完成基金项目情况.md",
    "P4_其他需要说明的情况.md",
    "REF_参考文献.md",
]


def _p2_children(sections_dir: Path) -> list[Path]:
    pats = sorted(sections_dir.glob("P2_*.md"))
    children = [p for p in pats if p.name != "P2_研究内容.md"]

    def key(p: Path):
        m = re.match(r"P2_([0-9.]+)_", p.name)
        if not m:
            return (999,)
        return tuple(int(x) for x in m.group(1).split("."))

    return sorted(children, key=key)


def validate_order(sections_dir: Path) -> dict:
    present = {p.name for p in sections_dir.glob("*.md")}
    required = set(ORDER) - {"P2_研究内容.md"}

    missing = sorted(x for x in required if x not in present)
    if "P2_研究内容.md" not in present:
        p2_parts = _p2_children(sections_dir)
        if not p2_parts:
            missing.append("P2_研究内容.md or P2_xxx split files")

    return {
        "ok": not missing,
        "missing": missing,
        "present_count": len(present),
    }


def merge(sections_dir: Path, output_path: Path) -> list[str]:
    merged: list[str] = []
    used = []
    for name in ORDER:
        p = sections_dir / name
        if name == "P2_研究内容.md" and not p.exists():
            for c in _p2_children(sections_dir):
                merged.append(c.read_text(encoding="utf-8").strip())
                used.append(c.name)
            continue
        if p.exists():
            merged.append(p.read_text(encoding="utf-8").strip())
            used.append(name)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n\n\f\n\n".join(x for x in merged if x), encoding="utf-8")
    return used


def merge_selected(sections_dir: Path, selected: list[str], output_path: Path) -> list[str]:
    merged: list[str] = []
    used: list[str] = []

    allowed = set(ORDER) | {"P2"}
    normalized: list[str] = []
    for item in selected:
        key = item.strip()
        if not key:
            continue
        if key == "P2":
            normalized.append("P2_研究内容.md")
            continue
        if key.endswith(".md"):
            normalized.append(key)
        elif key in ORDER:
            normalized.append(key)
        else:
            normalized.append(f"{key}.md")

    for name in normalized:
        if name not in allowed:
            continue
        p = sections_dir / name
        if name == "P2_研究内容.md" and not p.exists():
            for c in _p2_children(sections_dir):
                merged.append(c.read_text(encoding="utf-8").strip())
                used.append(c.name)
            continue
        if p.exists():
            merged.append(p.read_text(encoding="utf-8").strip())
            used.append(name)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n\n\f\n\n".join(x for x in merged if x), encoding="utf-8")
    return used


# 正文参考文献角标：纯数字方括号，形如 [1] / [2,3] / [4-6] / [2，3]（全角逗号）。
# 限定纯数字 + 分隔符，天然排除 [图1]/[表2]（含中文）与公式区间等。
_CITATION_RE = re.compile(r"\[\d+(?:[-,，]\d+)*\]")
# 参考文献章节标题：进入后停止上标处理，避免误伤列表条目编号 [1] 张三...
_REF_HEADING_RE = re.compile(r"^\s*(参考文献|References)\s*$")


def _is_ref_heading(text: str) -> bool:
    # 去掉可能的 markdown 标题残留符号后匹配
    stripped = text.strip().lstrip("#").strip()
    return bool(_REF_HEADING_RE.match(stripped))


def _superscript_citations(docx_path: Path) -> int:
    """后处理 docx：把正文裸写的参考文献角标 [N]/[N,M]/[N-M] 设为上标。

    边界处理：
    - 一旦遇到"参考文献/References"标题段落，停止处理后续所有段落（列表条目编号 [1] 不动）。
    - 仅匹配纯数字方括号；[图1]/[表2] 含中文，不匹配。
    - pandoc 已把 ^[1]^ 渲染成上标的 run（run.font.superscript=True）跳过，避免重复。
    返回被设为上标的角标 run 数量。
    """
    from docx import Document
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    doc = Document(str(docx_path))
    changed = 0
    in_references = False

    for para in doc.paragraphs:
        if not in_references and _is_ref_heading(para.text):
            in_references = True
        if in_references:
            continue

        # 重建段落 runs：对每个 run 内的角标拆分出独立上标 run。
        for run in list(para.runs):
            if run.font.superscript:
                continue  # 已是上标（来自 ^[N]^），不重复处理
            text = run.text
            if not text or "[" not in text:
                continue
            matches = list(_CITATION_RE.finditer(text))
            if not matches:
                continue

            # 把原 run 拆成 [前缀][角标(上标)][后缀]... 序列。
            # 复用原 run 作为第一段，其余 run 插到其后，继承字体格式。
            segments: list[tuple[str, bool]] = []  # (text, is_superscript)
            cursor = 0
            for m in matches:
                if m.start() > cursor:
                    segments.append((text[cursor:m.start()], False))
                segments.append((m.group(), True))
                cursor = m.end()
            if cursor < len(text):
                segments.append((text[cursor:], False))

            run.text = segments[0][0]
            if segments[0][1]:
                run.font.superscript = True
                changed += 1
            ref_el = run._element
            for seg_text, is_sup in segments[1:]:
                new_run = copy.deepcopy(run._element)
                # 清空文本节点后重设
                for t in new_run.findall(qn("w:t")):
                    new_run.remove(t)
                new_t = OxmlElement("w:t")
                new_t.set(qn("xml:space"), "preserve")
                new_t.text = seg_text
                new_run.append(new_t)
                # 设置/清除上标
                rpr = new_run.find(qn("w:rPr"))
                if rpr is None:
                    rpr = OxmlElement("w:rPr")
                    new_run.insert(0, rpr)
                for va in rpr.findall(qn("w:vertAlign")):
                    rpr.remove(va)
                if is_sup:
                    va = OxmlElement("w:vertAlign")
                    va.set(qn("w:val"), "superscript")
                    rpr.append(va)
                    changed += 1
                ref_el.addnext(new_run)
                ref_el = new_run

    if changed:
        doc.save(str(docx_path))
    return changed


def merge_docx(md_path: Path, docx_path: Path) -> dict:
    docx_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["pandoc", "-f", "markdown+superscript+subscript", str(md_path), "-o", str(docx_path)]
    # 默认套用国自然字体模板（正文宋体小四+黑体标题，eastAsia 已锁）。
    # 模板是已提交的样式资产，缺失=安装损坏。硬失败让用户重生成，
    # 不要 silently 产出字体不受控的 docx。
    reference_docx = Path(__file__).resolve().parent.parent / "templates" / "reference.docx"
    if not reference_docx.exists():
        return {
            "ok": False,
            "error": (
                f"reference.docx 模板缺失: {reference_docx}。"
                "请先运行 `python scripts/make_reference_docx.py` 重新生成后再导出 docx。"
            ),
        }
    cmd += ["--reference-doc", str(reference_docx)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    except FileNotFoundError:
        return {"ok": False, "error": "pandoc not found"}

    if proc.returncode != 0:
        return {"ok": False, "error": proc.stderr.strip()[:500]}

    # 后处理：把正文裸写的参考文献角标 [N]/[N,M]/[N-M] 设为上标（参考文献列表/图表号不动）。
    try:
        superscripted = _superscript_citations(docx_path)
    except Exception as exc:  # 后处理失败不应让已生成的 docx 作废
        return {"ok": True, "output": str(docx_path), "superscript_warning": str(exc)}
    return {"ok": True, "output": str(docx_path), "citations_superscripted": superscripted}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_merge = sub.add_parser("merge")
    p_merge.add_argument("--sections-dir", default="sections")
    p_merge.add_argument("--output", default="output/申请书_合并.md")
    p_merge.add_argument("--only", default="", help="Comma-separated section filenames or aliases, e.g. P1_立项依据.md,P2,REF_参考文献.md")

    p_docx = sub.add_parser("merge-docx")
    p_docx.add_argument("--input", default="output/申请书_合并.md")
    p_docx.add_argument("--output", default="output/申请书_合并.docx")

    p_valid = sub.add_parser("validate-order")
    p_valid.add_argument("--sections-dir", default="sections")

    args = parser.parse_args()

    if args.cmd == "validate-order":
        print(json.dumps(validate_order(Path(args.sections_dir)), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "merge":
        sections_dir = Path(args.sections_dir)
        if args.only.strip():
            selected = [x.strip() for x in args.only.split(",") if x.strip()]
            used = merge_selected(sections_dir, selected, Path(args.output))
            if not used:
                print(json.dumps({"ok": False, "error": "no selected sections found", "only": selected}, ensure_ascii=False, indent=2))
                return 2
        else:
            valid = validate_order(sections_dir)
            if not valid["ok"]:
                print(json.dumps(valid, ensure_ascii=False, indent=2))
                return 2
            used = merge(sections_dir, Path(args.output))
        print(json.dumps({"ok": True, "output": args.output, "merged_files": used}, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "merge-docx":
        result = merge_docx(Path(args.input), Path(args.output))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 2

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
