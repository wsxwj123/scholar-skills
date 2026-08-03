#!/usr/bin/env python3
"""Merge section files into final manuscript."""

from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
from pathlib import Path

try:
    import structure_profile  # 同目录；INTERFACE §1-§3 的三态回落在它内部处理
except ImportError:  # structure_profile.py 尚未落地/半安装 → 一律走内置默认
    structure_profile = None

# 内置国自然 2026 章节清单（结构真源缺失时的 fallback，INTERFACE §0；勿删）
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

# merge 的排除名单（INTERFACE §4.2 reason=not_a_chapter；当前只有 figure_prompts.md）
NOT_A_CHAPTER = {"figure_prompts.md"}


def _sort_key(name: str) -> list:
    """INTERFACE §4.1 排序键：按 (\\d+(?:\\.\\d+)*) 切段；
    数字段 → (0, (int, …))，非数字段 → (1, str)。认小数点：2.2 < 2.2.1 < 2.10。"""
    key = []
    for part in re.split(r"(\d+(?:\.\d+)*)", name):
        if not part:
            continue
        if re.fullmatch(r"\d+(?:\.\d+)*", part):
            key.append((0, tuple(int(x) for x in part.split("."))))
        else:
            key.append((1, part))
    return key


def _load_profile(root) -> dict | None:
    """读 <root>/structure_profile.json。缺失/损坏/非法/未确认 → None（走内置默认）。"""
    if structure_profile is None:
        return None
    return structure_profile.load(str(root))


def _p2_children(sections_dir: Path) -> list[Path]:
    children = [p for p in sections_dir.glob("P2_*.md") if p.name != "P2_研究内容.md"]
    return sorted(children, key=lambda p: _sort_key(p.name))


def validate_order(sections_dir: Path, profile: dict | None = None) -> dict:
    present = {p.name for p in sections_dir.glob("*.md")}

    if profile is not None:
        chapters = profile.get("chapters") or []
        if chapters:
            # INTERFACE §4.2：必需件集 = required == true 的 filename 集合
            wanted = {c.get("filename") for c in chapters if c.get("required") is True}
            missing = sorted(x for x in wanted if x not in present)
            return {"ok": not missing, "missing": missing, "present_count": len(present)}
        if profile.get("funding_scheme", "nsfc") == "other":
            # 非国自然 + 章节表缺省 → 必需件集为空，ok 恒 true
            return {"ok": True, "missing": [], "present_count": len(present)}
        # nsfc + 章节表缺省 → 同无真源，落到内置默认

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


def _collect(sections_dir: Path) -> tuple[list[str], list[dict]]:
    """收 sections/*.md 全部现场文件（INTERFACE §4.2 + §9-12「清单外就丢」已废止），
    减 not_a_chapter 与 p2_parent_present 两类；empty 在 merge 读内容时判。"""
    present = sorted((p.name for p in sections_dir.glob("*.md")), key=_sort_key)
    p2_parent = "P2_研究内容.md" in present
    names: list[str] = []
    excluded: list[dict] = []
    for n in present:
        if n in NOT_A_CHAPTER:
            excluded.append({"file": n, "reason": "not_a_chapter"})
        elif p2_parent and n.startswith("P2_") and n != "P2_研究内容.md":
            excluded.append({"file": n, "reason": "p2_parent_present"})
        else:
            names.append(n)
    return names, excluded


def _apply_profile_order(names: list[str], profile: dict | None) -> list[str]:
    """chapters 有内容 → 表内按 order 升序在前（同 order 按 §4.1 键稳定），
    表外按 §4.1 键排末尾；无真源 / chapters 缺省 → 保持 §4.1 键序。"""
    chapters = (profile or {}).get("chapters") or []
    if not chapters:
        return names
    present = set(names)
    head: list[str] = []
    listed: set[str] = set()
    ordered = sorted(chapters, key=lambda c: (c.get("order", 0), _sort_key(str(c.get("filename", "")))))
    for c in ordered:
        fn = c.get("filename")
        if fn in present and fn not in listed:
            head.append(fn)
            listed.add(fn)
    tail = [n for n in names if n not in listed]  # names 已按 §4.1 键有序
    return head + tail


def merge(sections_dir: Path, output_path: Path, profile: dict | None = None) -> tuple[list[str], list[dict]]:
    """合并现场文件。返回 (merged_files, excluded)。
    merged_files 语义 = 进了产物的文件：空文件不进，记 excluded reason=empty（§4.2 已拍板）。"""
    names, excluded = _collect(sections_dir)
    names = _apply_profile_order(names, profile)

    merged: list[str] = []
    used: list[str] = []
    for name in names:
        text = (sections_dir / name).read_text(encoding="utf-8").strip()
        if not text:
            excluded.append({"file": name, "reason": "empty"})
            continue
        merged.append(text)
        used.append(name)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n\n\f\n\n".join(merged), encoding="utf-8")
    return used, excluded


def _merge_selected(sections_dir: Path, selected: list[str], output_path: Path) -> tuple[list[str], list[dict], int]:
    """merge --only。返回 (merged_files, excluded, found)。
    found = 解析到现场文件的条数（含空文件）；=0 时 CLI 报「一个都没命中」exit 2。"""
    merged: list[str] = []
    used: list[str] = []
    excluded: list[dict] = []
    found = 0

    # INTERFACE §4.2：allowed = sections/ 下现场存在的文件名 ∪ {P2_研究内容.md}
    #（并入 P2 是为了父件不在场时别名仍能展开细粒度子文件）
    allowed = {p.name for p in sections_dir.glob("*.md")} | {"P2_研究内容.md"}
    normalized: list[str] = []
    for item in selected:
        key = item.strip()
        if not key:
            continue
        if key == "P2":
            normalized.append("P2_研究内容.md")
        elif key.endswith(".md"):
            normalized.append(key)
        else:
            normalized.append(f"{key}.md")

    def _take(path: Path) -> None:
        nonlocal found
        found += 1
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            excluded.append({"file": path.name, "reason": "empty"})
            return
        merged.append(text)
        used.append(path.name)

    for name in normalized:
        if name not in allowed:
            continue
        p = sections_dir / name
        if name == "P2_研究内容.md" and not p.exists():
            for c in _p2_children(sections_dir):
                _take(c)
            continue
        if p.exists():
            _take(p)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n\n\f\n\n".join(merged), encoding="utf-8")
    return used, excluded, found


def merge_selected(sections_dir: Path, selected: list[str], output_path: Path) -> list[str]:
    """兼容壳：保留旧签名/返回值（既有调用方与自测用）。CLI 走 _merge_selected。"""
    return _merge_selected(sections_dir, selected, output_path)[0]


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


def _resolve_root(args) -> str:
    """INTERFACE §9-1：--root 默认 = --sections-dir 的父目录（merge-docx 无 sections-dir，默认 .）。"""
    if getattr(args, "root", None):
        return args.root
    return str(Path(getattr(args, "sections_dir", "sections")).parent)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    root_help = "项目根（结构真源 structure_profile.json 所在目录；默认 = --sections-dir 的父目录）"

    p_merge = sub.add_parser("merge")
    p_merge.add_argument("--sections-dir", default="sections")
    p_merge.add_argument("--output", default="output/申请书_合并.md")
    p_merge.add_argument("--only", default="", help="Comma-separated section filenames or aliases, e.g. P1_立项依据.md,P2,REF_参考文献.md")
    p_merge.add_argument("--root", default=None, help=root_help)

    p_docx = sub.add_parser("merge-docx")
    p_docx.add_argument("--input", default="output/申请书_合并.md")
    p_docx.add_argument("--output", default="output/申请书_合并.docx")
    p_docx.add_argument("--root", default=None, help=root_help)

    p_valid = sub.add_parser("validate-order")
    p_valid.add_argument("--sections-dir", default="sections")
    p_valid.add_argument("--root", default=None, help=root_help)

    args = parser.parse_args()

    if args.cmd == "validate-order":
        profile = _load_profile(_resolve_root(args))
        print(json.dumps(validate_order(Path(args.sections_dir), profile), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "merge":
        sections_dir = Path(args.sections_dir)
        if args.only.strip():
            # --only 是用户显式点名，不读结构真源、不做章节校验（现役行为不变）
            selected = [x.strip() for x in args.only.split(",") if x.strip()]
            used, excluded, found = _merge_selected(sections_dir, selected, Path(args.output))
            if not found:
                print(json.dumps({"ok": False, "error": "no selected sections found", "only": selected}, ensure_ascii=False, indent=2))
                return 2
        else:
            profile = _load_profile(_resolve_root(args))
            valid = validate_order(sections_dir, profile)
            if not valid["ok"]:
                print(json.dumps(valid, ensure_ascii=False, indent=2))
                return 2
            used, excluded = merge(sections_dir, Path(args.output), profile)
        print(json.dumps({"ok": True, "output": args.output, "merged_files": used, "excluded": excluded}, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "merge-docx":
        result = merge_docx(Path(args.input), Path(args.output))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 2

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
