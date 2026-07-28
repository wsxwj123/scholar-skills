#!/usr/bin/env python3
"""data_trace_gate.py — sci2doc「数据溯源硬门」。

堵编数据：凡含实验数值的小节，正文必须为这些数值标注来源
    [数据来源] materials/<素材档>#<字段>
脚本校验：(1) 标记存在；(2) 标记指向真实的 materials/*.md 素材档；
(3) #<字段> 片段确实出现在该素材档里。fail-closed（违规 exit 2）。

纳入节 DoD / prewrite 前置闸门。只做机械可判定检查，不替代委托盲检、
也不判断数值本身对不对——只逼「每个数值都能追到 materials 素材档的某字段」。

CLI:
  python3 data_trace_gate.py --section 2.1 --root <project_root>
  python3 data_trace_gate.py --file atomic_md/第2章/2.1_xx.md [--file ...] --root <project_root>
  python3 data_trace_gate.py --selftest        # 内置自检

退出码：0=通过（无数值或数值都已溯源）；2=fail-closed（数值缺标记/标记失效）；1=用法错误。
输出末行为机器可读 JSON：{ok, section, files, numeric_files, violations:[...]}
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

# 测量/统计信号：出现即认定该节含实验数值，必须溯源。
_UNIT = (
    r"(?:%|‰|μg|µg|ug|mg|kg|ng|pg|μL|µL|uL|mL|dL|μM|µM|uM|nM|mM|mol|mmol|"
    r"μmol|nmol|pmol|U/L|U/mL|IU|kDa|Da|bp|kb|rpm|×?g|nm|μm|µm|um|mm|cm|"
    r"℃|°C|kPa|mmHg|mM|h|hr|min|sec|ms|d|周|天|次|倍|fold)"
)
_MEASURE_RE = re.compile(r"\d+(?:\.\d+)?\s*" + _UNIT, re.IGNORECASE)
_STAT_RE = re.compile(r"[pP]\s*[<>=]\s*0?\.\d+|±\s*\d|\bn\s*=\s*\d+|\br\s*=\s*0?\.\d+")

# 溯源标记：[数据来源] materials/<path>#<field>
_TRACE_RE = re.compile(r"\[数据来源\]\s*materials/([^\s#\]]+)(?:#([^\s\]]+))?")

# 扫描裸数字时先剔除这些「非数据」token（图号/表号/实验号/章号/引用/编号列表）。
_NONDATA_RE = re.compile(
    r"图\s*\d+[-.]?\d*|表\s*\d+[-.]?\d*|图\d+|表\d+|EXP[-\d]+|"
    r"第\s*[一二三四五六七八九十百千0-9]+\s*[章节]|"
    r"\[\d+(?:[-,]\d+)*\]|Fig(?:ure)?\.?\s*\d+|Table\s*\d+"
)


def _strip_nondata(text: str) -> str:
    return _NONDATA_RE.sub(" ", text)


def has_numeric_data(text: str) -> bool:
    """该节文本是否含需溯源的实验数值。"""
    cleaned = _strip_nondata(text)
    if _MEASURE_RE.search(cleaned):
        return True
    if _STAT_RE.search(cleaned):
        return True
    # 三线表数据行：含 | 分隔且单元格里有裸数字（排除分隔行/纯表头）。
    for line in cleaned.splitlines():
        if "|" not in line:
            continue
        if re.match(r"^\|?[\s:]*-{3,}", line.strip()):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        for c in cells:
            if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", c):
                return True
    return False


def parse_section(section: str):
    m = re.match(r"^\s*(\d+)\.(\d+)\s*$", str(section))
    if m:
        return m.group(1), m.group(2)
    m2 = re.match(r"^\s*(\d+)\s*$", str(section))
    if m2:
        return m2.group(1), None
    return str(section), None


def resolve_section_files(root: str, section: str):
    chapter, sub = parse_section(section)
    cdir = os.path.join(root, "atomic_md", f"第{chapter}章")
    if not os.path.isdir(cdir):
        return []
    if sub is None:
        return sorted(glob.glob(os.path.join(cdir, "*.md")))
    hits = sorted(glob.glob(os.path.join(cdir, f"{chapter}.{sub}_*.md")))
    return hits


def check_trace_markers(root: str, text: str):
    """校验文中所有 [数据来源] 标记，返回 (valid_marker_count, violations[])。"""
    violations = []
    valid = 0
    markers = list(_TRACE_RE.finditer(text))
    for m in markers:
        rel, field = m.group(1), m.group(2)
        if not field:
            violations.append(f"[数据来源] materials/{rel} 缺 #<字段>，必须指向具体字段")
            continue
        # 允许省略 .md 后缀
        candidates = [os.path.join(root, "materials", rel)]
        if not rel.endswith(".md"):
            candidates.append(os.path.join(root, "materials", rel + ".md"))
        mat_path = next((p for p in candidates if os.path.isfile(p)), None)
        if not mat_path:
            violations.append(f"[数据来源] 素材档不存在：materials/{rel}（须为真实 materials/*.md）")
            continue
        if not mat_path.endswith(".md"):
            violations.append(f"[数据来源] materials/{rel} 不是 .md 素材档")
            continue
        try:
            content = open(mat_path, "r", encoding="utf-8").read()
        except OSError as e:
            violations.append(f"[数据来源] 无法读取 materials/{rel}：{e}")
            continue
        if field not in content:
            violations.append(f"[数据来源] materials/{rel}#{field}：字段 “{field}” 未出现在该素材档")
            continue
        valid += 1
    return valid, violations


def gate(root: str, files):
    root = os.path.abspath(root)
    violations = []
    numeric_files = []
    for fp in files:
        try:
            text = open(fp, "r", encoding="utf-8").read()
        except OSError as e:
            violations.append(f"{os.path.basename(fp)}: 无法读取（{e}）")
            continue
        base = os.path.basename(fp)
        valid_markers, marker_viol = check_trace_markers(root, text)
        violations.extend(f"{base}: {v}" for v in marker_viol)
        if has_numeric_data(text):
            numeric_files.append(base)
            if valid_markers == 0:
                violations.append(
                    f"{base}: 含实验数值但无有效 [数据来源] materials/<档>#<字段> 标记（疑似编数据）")
    return violations, numeric_files


def main():
    ap = argparse.ArgumentParser(description="sci2doc 数据溯源硬门：含数值章节必须标注 materials 来源。")
    ap.add_argument("--section", help="章.节，如 2.1")
    ap.add_argument("--file", action="append", default=[], help="直接指定 md 文件（可多次）")
    ap.add_argument("--root", help="project root（--section 时必填）")
    ap.add_argument("--selftest", action="store_true", help="运行内置自检")
    args = ap.parse_args()

    if args.selftest:
        return _selftest()

    root = os.path.abspath(args.root or ".")
    files = []
    if args.section:
        if not args.root:
            print("用法错误：--section 需配合 --root")
            return 1
        files = resolve_section_files(root, args.section)
        if not files:
            print(f"DATA_TRACE_GATE: FAIL 未找到 section {args.section} 的 md 文件")
            print(json.dumps({"ok": False, "section": args.section, "files": [],
                              "numeric_files": [], "violations": ["section files not found"]},
                             ensure_ascii=False))
            return 2
    files += [f for f in args.file if f]
    if not files:
        print("用法错误：需 --section 或 --file")
        return 1

    violations, numeric_files = gate(root, files)
    ok = not violations
    result = {
        "ok": ok,
        "section": args.section,
        "files": [os.path.basename(f) for f in files],
        "numeric_files": numeric_files,
        "violations": violations,
    }
    if not ok:
        for v in violations:
            print(f"DATA_TRACE_GATE: FAIL {v}")
    else:
        print("DATA_TRACE_GATE: OK")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if ok else 2


def _selftest():
    import tempfile

    root = tempfile.mkdtemp()
    mats = os.path.join(root, "materials")
    os.makedirs(mats)
    open(os.path.join(mats, "wb_data.md"), "w", encoding="utf-8").write(
        "# WB\n## 可引用要点\n- Bax/Bcl-2 比值\n- PMG 20 μg/mL 处理\n")

    # 1) 无数值 → 通过
    f0 = os.path.join(root, "n0.md")
    open(f0, "w", encoding="utf-8").write("本节介绍实验背景，见图2-1，引用[3]。")
    v, _ = gate(root, [f0])
    assert not v, v

    # 2) 有数值无标记 → 拦
    f1 = os.path.join(root, "n1.md")
    open(f1, "w", encoding="utf-8").write("PMG 20 μg/mL 使凋亡率升至 45.3%（p<0.05）。")
    v, nf = gate(root, [f1])
    assert v and nf == ["n1.md"], (v, nf)

    # 3) 有数值+有效标记 → 通过
    f2 = os.path.join(root, "n2.md")
    open(f2, "w", encoding="utf-8").write(
        "PMG 20 μg/mL 使凋亡率升至 45.3%（p<0.05）。[数据来源] materials/wb_data.md#PMG")
    v, _ = gate(root, [f2])
    assert not v, v

    # 4) 标记指向不存在素材档 → 拦
    f3 = os.path.join(root, "n3.md")
    open(f3, "w", encoding="utf-8").write(
        "凋亡率 45.3%。[数据来源] materials/ghost.md#字段")
    v, _ = gate(root, [f3])
    assert v, "should flag missing material"

    # 5) 标记缺 #字段 → 拦
    f4 = os.path.join(root, "n4.md")
    open(f4, "w", encoding="utf-8").write(
        "凋亡率 45.3%。[数据来源] materials/wb_data.md")
    v, _ = gate(root, [f4])
    assert v, "should flag missing field"

    # 6) 字段不在素材档 → 拦
    f5 = os.path.join(root, "n5.md")
    open(f5, "w", encoding="utf-8").write(
        "凋亡率 45.3%。[数据来源] materials/wb_data.md#不存在字段")
    v, _ = gate(root, [f5])
    assert v, "should flag field not found"

    print("data_trace_gate selftest: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
