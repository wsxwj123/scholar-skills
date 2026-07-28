#!/usr/bin/env python3
"""Diagnosis aggregator for section/global checks."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import citation_validator
import consistency_mapper
import humanizer_zh
import word_counter


# 诚实化声明：D-01/D-02/D-04 是无法机械评判的实质维度，本引擎只报统计、不给质量等级。
QUALITY_DISCLAIMER = (
    "⚠ 字数/条目数/引用数等均为机械统计，不代表质量。"
    "科学意义(D-01)、创新性(D-02)、可行性(D-04)的实质判断须专家或委托盲检，本引擎不做实质评判。"
    "本报告的等级/通过状态仅覆盖形式规范与内部一致性；立意是否够格、创新是否真新、"
    "引文是否支持论点、研究空白真伪，均未自动核验。"
)


def _grade_from_ratio(ok: float) -> str:
    if ok >= 0.95:
        return "A"
    if ok >= 0.8:
        return "B"
    if ok >= 0.6:
        return "C"
    return "D"


def _grade_from_issue_count(cnt: int) -> str:
    if cnt == 0:
        return "A"
    if cnt <= 2:
        return "B"
    if cnt <= 5:
        return "C"
    return "D"


def _grade_to_score(g: str) -> int:
    return {"A": 4, "B": 3, "C": 2, "D": 1}.get(g, 1)


def _score_to_grade(score: float) -> str:
    if score >= 3.8:
        return "A"
    if score >= 3.0:
        return "B+"
    if score >= 2.0:
        return "C"
    return "D"


def _section_consistency_snapshot(consistency_path: Path, section_stem: str) -> dict[str, Any]:
    cm = consistency_mapper.load_map(consistency_path)
    return consistency_mapper.query_by_section(cm, section_stem)


def diagnose_section(path: Path, consistency_path: Path, allow_lists: bool = False) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    style = humanizer_zh.scan_text(text, allow_lists=allow_lists)
    rhythm = humanizer_zh.rhythm_check(text)
    words = word_counter.count_text(text)

    d07 = _grade_from_issue_count(style["count"] + rhythm["count"])
    d08 = "A" if words > 0 else "D"

    dims = {
        "D-07": {"name": "写作风格", "grade": d07},
        "D-08": {"name": "格式规范", "grade": d08},
    }
    worst = "D" if any(v["grade"] == "D" for v in dims.values()) else ("C" if any(v["grade"] == "C" for v in dims.values()) else "B")

    return {
        "section": path.name,
        "grade": worst,
        "word_count": words,
        "style": style,
        "rhythm": rhythm,
        "dimension_scores": dims,
        "section_consistency_context": _section_consistency_snapshot(consistency_path, path.stem),
    }


def diagnose_all(sections_dir: Path, consistency_path: Path) -> list[dict[str, Any]]:
    reports = []
    for p in sorted(sections_dir.glob("*.md")):
        allow_lists = p.name.startswith("P3_3") or p.name.startswith("P3_4") or p.name.startswith("P4_")
        reports.append(diagnose_section(p, consistency_path, allow_lists=allow_lists))
    return reports


def _global_dimensions(
    sections_dir: Path,
    cm: dict[str, Any],
    section_reports: list[dict[str, Any]],
    consistency: dict[str, Any],
    citation_matrix: dict[str, Any] | None,
    page_limit: int,
) -> dict[str, dict[str, Any]]:

    # D-01 科学意义与立项依据 —— 仅统计，不评质量等级（字数/引用数是可灌水的机械代理，
    # 是否有真科学价值须专家/盲检判断）
    p1 = sections_dir / "P1_立项依据.md"
    p1_text = p1.read_text(encoding="utf-8") if p1.exists() else ""
    p1_cits = len(citation_validator.extract_citation_numbers(p1_text))
    d01_stats = {"p1_字数": len(p1_text), "p1_引用条数": p1_cits}

    # D-02 创新性 —— 仅统计创新点条目数，不评质量（条目多≠创新真）
    in_count = len(cm.get("innovations", []))
    d02_stats = {"创新点条目数": in_count}

    # D-03 研究方案合理性
    d03 = "A" if consistency.get("V-03", {}).get("pass") and consistency.get("V-06", {}).get("pass") else "D"

    # D-04 可行性 —— 仅统计可行性证据条数及来源合规，不评质量（证据够不够硬须专家判断）
    f_count = len(cm.get("feasibility_evidence", []))
    d04_stats = {"可行性证据条数": f_count, "F来源合规(V-07)": bool(consistency.get("V-07", {}).get("pass"))}

    # D-05 四维对应完整性
    core_rules = ["V-01", "V-02", "V-03", "V-05", "V-06"]
    d05 = "A" if all(consistency.get(r, {}).get("pass") for r in core_rules) else "D"

    # D-06 跨节逻辑一致性
    d06 = "A" if consistency.get("V-08", {}).get("pass") and consistency.get("V-10", {}).get("pass") else "C"

    # D-07 写作风格
    style_issues = sum(r["style"]["count"] + r["rhythm"]["count"] for r in section_reports)
    d07 = _grade_from_issue_count(style_issues)

    # D-08 格式规范
    pages = word_counter.estimate_pages(sum(r["word_count"] for r in section_reports))
    matrix_ok = citation_matrix.get("ok") if citation_matrix else True
    d08 = "A" if pages <= page_limit and matrix_ok else "C"

    # D-09 预算合理性
    budget_files = [
        sections_dir / "B1_预算说明_直接费用.md",
        sections_dir / "B2_预算说明_合作外拨.md",
        sections_dir / "B3_预算说明_其他来源.md",
    ]
    budget_present = all(p.exists() for p in budget_files)
    d09 = "A" if budget_present and consistency.get("V-09", {}).get("pass") else ("C" if budget_present else "D")

    # D-10 摘要质量
    abs_cn = (sections_dir / "00_摘要_中文.md").read_text(encoding="utf-8") if (sections_dir / "00_摘要_中文.md").exists() else ""
    abs_en = (sections_dir / "00_摘要_英文.md").read_text(encoding="utf-8") if (sections_dir / "00_摘要_英文.md").exists() else ""
    abs_cn_words = word_counter.count_text(abs_cn)
    abs_en_words = len((abs_en or "").split())
    d10 = "A" if abs_cn_words <= 400 and abs_en_words <= 300 and abs_cn_words > 0 and abs_en_words > 0 else "C"

    _stat_note = "统计信息，不代表质量；实质判断须专家或委托盲检，本引擎不做实质评判。"
    dims = {
        "D-01": {"name": "科学意义与立项依据", "kind": "statistic", "stats": d01_stats, "note": _stat_note},
        "D-02": {"name": "创新性", "kind": "statistic", "stats": d02_stats, "note": _stat_note},
        "D-03": {"name": "研究方案合理性", "grade": d03},
        "D-04": {"name": "可行性", "kind": "statistic", "stats": d04_stats, "note": _stat_note},
        "D-05": {"name": "四维对应完整性", "grade": d05},
        "D-06": {"name": "跨节逻辑一致性", "grade": d06},
        "D-07": {"name": "写作风格", "grade": d07},
        "D-08": {"name": "格式规范", "grade": d08},
        "D-09": {"name": "预算合理性", "grade": d09},
        "D-10": {"name": "摘要质量", "grade": d10},
    }
    return dims


def full_review(
    sections_dir: Path,
    consistency_path: Path,
    index_path: Path | None = None,
    p1_path: Path | None = None,
    ref_path: Path | None = None,
    page_limit: int = 30,
) -> dict[str, Any]:
    section_reports = diagnose_all(sections_dir, consistency_path)
    total_words = sum(r["word_count"] for r in section_reports)
    pages = word_counter.estimate_pages(total_words)

    cm = consistency_mapper.load_map(consistency_path)
    consistency = consistency_mapper.validate(cm)

    citation_matrix = None
    if index_path and p1_path and ref_path:
        idx = citation_validator.load_json(index_path, {"metadata": {}, "entries": []})
        p1_text = p1_path.read_text(encoding="utf-8") if p1_path.exists() else ""
        ref_text = ref_path.read_text(encoding="utf-8") if ref_path.exists() else ""
        citation_matrix = citation_validator.matrix_check(p1_text, idx, ref_text)

    dimensions = _global_dimensions(sections_dir, cm, section_reports, consistency, citation_matrix, page_limit)
    # D-01/D-02/D-04 为纯统计项（无 grade），不计入等级/门控计算
    grades = [d["grade"] for d in dimensions.values() if "grade" in d]
    d_count = sum(1 for g in grades if g == "D")
    c_count = sum(1 for g in grades if g == "C")

    avg_score = sum(_grade_to_score(g) for g in grades) / len(grades)
    overall_grade = _score_to_grade(avg_score)

    if d_count > 0:
        pass_status = "blocked"
        overall_grade = "D"
    elif c_count > 3:
        pass_status = "conditional"
        if overall_grade == "A":
            overall_grade = "B+"
    else:
        pass_status = "pass" if pages <= page_limit else "conditional"

    return {
        "review_type": "L2_full",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": QUALITY_DISCLAIMER,
        "overall_grade": overall_grade,
        "pass_status": pass_status,
        "section_reports": section_reports,
        "dimensions": dimensions,
        "c_count": c_count,
        "d_count": d_count,
        "consistency_validation": consistency,
        "citation_matrix": citation_matrix,
        "page_estimate": pages,
        "total_words": total_words,
        "page_limit": page_limit,
    }


def export_markdown(report: dict[str, Any], title: str = "NSFC申请书评审报告") -> str:
    lines = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"> {report.get('disclaimer', QUALITY_DISCLAIMER)}")
    lines.append("")
    lines.append(f"- 时间: {report.get('timestamp', '')}")
    lines.append(f"- 总评等级（仅形式与内部一致性）: {report.get('overall_grade', '')}")
    lines.append(f"- 通过状态（仅形式与内部一致性）: {report.get('pass_status', '')}")
    lines.append(f"- 总字数: {report.get('total_words', 0)}")
    lines.append(f"- 页数估算: {report.get('page_estimate', 0)} / 限制 {report.get('page_limit', 30)}")
    lines.append("")

    lines.append("## 维度评分")
    for did, detail in report.get("dimensions", {}).items():
        if detail.get("kind") == "statistic":
            stat_str = "，".join(f"{k}={v}" for k, v in (detail.get("stats") or {}).items())
            lines.append(f"- {did} {detail.get('name')}: [仅统计] {stat_str}（{detail.get('note', '')}）")
        else:
            lines.append(f"- {did} {detail.get('name')}: {detail.get('grade')}")

    lines.append("")
    lines.append("## 节级结果")
    for sec in report.get("section_reports", []):
        lines.append(f"- {sec['section']}: {sec['grade']} (字数 {sec['word_count']}, 风格问题 {sec['style']['count']})")

    lines.append("")
    lines.append("## 一致性规则")
    for rid, detail in report.get("consistency_validation", {}).items():
        mark = "PASS" if detail.get("pass") else "FAIL"
        lines.append(f"- {rid} [{detail.get('severity')}]: {mark}")
        if not detail.get("pass"):
            locs = detail.get("locations", []) or []
            if locs:
                lines.append(f"  - 关键位置: {locs[0].get('source_file') or locs[0].get('source_section')}")

    cm = report.get("citation_matrix")
    if cm:
        lines.append("")
        lines.append("## 引用矩阵")
        lines.append(f"- ok: {cm.get('ok')}")
        lines.append(f"- orphan_citations: {cm.get('orphan_citations')}")
        lines.append(f"- orphan_entries: {cm.get('orphan_entries')}")
        lines.append(f"- order_match: {cm.get('order_match')}")

    return "\n".join(lines)


def _export_polish_review(report: dict[str, Any]) -> str:
    lines = []
    lines.append("# 申请书评审报告")
    lines.append("")
    lines.append(f"> {report.get('disclaimer', QUALITY_DISCLAIMER)}")
    lines.append("")
    lines.append("## 总体评价")
    lines.append(
        f"本次机械自审的综合等级为 {report.get('overall_grade')}，通过状态为 {report.get('pass_status')}，"
        "该等级仅覆盖形式规范与内部一致性。科学问题凝练、研究设计可证伪性、创新实质性等"
        "须由专家或委托盲检判断，本引擎不做实质评判。"
    )
    lines.append("")
    stat_dims = {k: v for k, v in report.get("dimensions", {}).items() if v.get("kind") == "statistic"}
    if stat_dims:
        lines.append("## 统计信息（非质量评分）")
        for did, detail in stat_dims.items():
            stat_str = "，".join(f"{k}={v}" for k, v in (detail.get("stats") or {}).items())
            lines.append(f"- {did} {detail.get('name')}：{stat_str}")
        lines.append("（以上为字数/条目数统计，不代表质量；实质判断须专家或盲检。）")
        lines.append("")
    lines.append("## 一、科学问题与立项依据")
    lines.append("围绕D-01、D-05和引用矩阵核查立项依据是否形成完整论证链。")
    lines.append("")
    lines.append("## 二、研究假说与研究设计")
    lines.append("围绕D-02、D-03检查假说、目标、研究内容与关键科学问题是否闭环。")
    lines.append("")
    lines.append("## 三、逻辑一致性")
    lines.append("基于V-01~V-10规则检查跨节术语与映射完整性。")
    lines.append("")
    lines.append("## 四、可行性与研究基础")
    lines.append("围绕D-04检查每个关键方法是否存在有效可行性证据。")
    lines.append("")
    lines.append("## 五、写作质量")
    lines.append("围绕D-07检查反AI违规、段落叙事和节奏问题。")
    lines.append("")
    lines.append("## 六、格式与规范")
    lines.append("围绕D-08、D-10检查页数、摘要字数和引用顺序一致性。")
    lines.append("")
    lines.append("## 七、逐条问题清单")

    for did, detail in report.get("dimensions", {}).items():
        if detail.get("grade") in {"C", "D"}:
            lines.append(f"- [{detail.get('grade')}] {did} {detail.get('name')} 需要修订。")

    cm = report.get("citation_matrix") or {}
    if cm and not cm.get("ok", True):
        lines.append("- [D] 引用矩阵不一致，需要修复孤立引用/条目与顺序问题。")

    if lines[-1].startswith("## 七"):
        lines.append("- 当前未发现C/D级问题。")

    lines.append("")
    lines.append("## 八、可执行修复动作")
    for i, act in enumerate(_build_fix_actions(report), 1):
        lines.append(f"{i}. {act['title']}")
        lines.append(f"   - 位置: {act['location']}")
        lines.append(f"   - 动作: {act['action']}")
        lines.append(f"   - 验收: {act['acceptance']}")

    return "\n".join(lines)


def _build_fix_actions(report: dict[str, Any]) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    dims = report.get("dimensions", {})
    for did, detail in dims.items():
        grade = detail.get("grade")
        if grade not in {"C", "D"}:
            continue

        if did == "D-01":
            actions.append(
                {
                    "title": "补强P1立项依据证据链",
                    "location": "sections/P1_立项依据.md",
                    "action": "补充近5年高质量文献并增加问题-假说-目标连贯论证段。",
                    "acceptance": "P1字数与引用满足内部阈值，且引用矩阵通过。",
                }
            )
        elif did == "D-03":
            actions.append(
                {
                    "title": "修复研究内容-方法映射",
                    "location": "data/consistency_map.json",
                    "action": "确保每个RC具备mapped_to_method且对应方法存在可行性证据F。",
                    "acceptance": "V-03/V-06全部PASS。",
                }
            )
        elif did == "D-07":
            actions.append(
                {
                    "title": "清理写作风格风险",
                    "location": "sections/*.md（优先C/D节）",
                    "action": "移除模板化连接词、空泛判断和AI痕迹句型，压缩空洞段落。",
                    "acceptance": "style+rhythm问题数降到阈值内，节级评分提升到B及以上。",
                }
            )
        elif did == "D-08":
            actions.append(
                {
                    "title": "修复格式与引用顺序",
                    "location": "sections/P1_立项依据.md + sections/REF_参考文献.md",
                    "action": "执行matrix-check并按P1首现顺序重排引用，控制总页数不超限。",
                    "acceptance": "citation_matrix.ok=true 且页数<=page_limit。",
                }
            )
        else:
            actions.append(
                {
                    "title": f"修复 {did} {detail.get('name')}",
                    "location": "相关章节与一致性映射",
                    "action": "按该维度定义补齐缺失证据、映射关系与章节论证。",
                    "acceptance": "该维度评分提升到B及以上。",
                }
            )

    cv = report.get("consistency_validation", {})
    for rid, rule in cv.items():
        if rule.get("pass"):
            continue
        locs = rule.get("locations", []) or []
        loc = "data/consistency_map.json"
        if locs:
            first = locs[0]
            loc = first.get("source_file") or first.get("source_section") or loc
        actions.append(
            {
                "title": f"修复一致性规则 {rid}",
                "location": str(loc),
                "action": f"根据{rid}规则补齐映射并校正孤立实体，必要时同步章节文字与术语。",
                "acceptance": f"{rid} 由 FAIL 变为 PASS。",
            }
        )

    cm = report.get("citation_matrix") or {}
    if cm and not cm.get("ok", True):
        actions.append(
            {
                "title": "修复引用矩阵三向一致性",
                "location": "sections/P1_立项依据.md + sections/REF_参考文献.md + data/literature_index.json",
                "action": "清理孤立引用/条目，确保P1首现顺序与REF和index一致。",
                "acceptance": "matrix-check 输出 ok=true, three_way_match=true。",
            }
        )

    if not actions:
        actions.append(
            {
                "title": "维持当前质量",
                "location": "全局",
                "action": "未发现关键缺陷，保持当前结构并仅做小幅语言润色。",
                "acceptance": "下一次full-review维持A/B+。",
            }
        )
    return actions


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sec = sub.add_parser("diagnose-section")
    p_sec.add_argument("--section", required=True)
    p_sec.add_argument("--consistency", default="data/consistency_map.json")
    p_sec.add_argument("--allow-lists", action="store_true")

    p_all = sub.add_parser("diagnose-all")
    p_all.add_argument("--sections-dir", default="sections")
    p_all.add_argument("--consistency", default="data/consistency_map.json")

    p_full = sub.add_parser("full-review")
    p_full.add_argument("--sections-dir", default="sections")
    p_full.add_argument("--consistency", default="data/consistency_map.json")
    p_full.add_argument("--index", default="data/literature_index.json")
    p_full.add_argument("--p1", default="sections/P1_立项依据.md")
    p_full.add_argument("--ref", default="sections/REF_参考文献.md")
    p_full.add_argument("--output", default="data/diagnosis_report.json")
    p_full.add_argument("--page-limit", type=int, default=30)

    p_export = sub.add_parser("export-report")
    p_export.add_argument("--input", default="data/diagnosis_report.json")
    p_export.add_argument("--output", default="data/diagnosis_report.md")

    p_polish = sub.add_parser("polish-review")
    p_polish.add_argument("--sections-dir", default="sections")
    p_polish.add_argument("--consistency", default="data/consistency_map.json")
    p_polish.add_argument("--index", default="data/literature_index.json")
    p_polish.add_argument("--p1", default="sections/P1_立项依据.md")
    p_polish.add_argument("--ref", default="sections/REF_参考文献.md")
    p_polish.add_argument("--json-output", default="data/diagnosis_report.json")
    p_polish.add_argument("--md-output", default="data/polish_review_report.md")
    p_polish.add_argument("--page-limit", type=int, default=30)

    args = parser.parse_args()

    if args.cmd == "diagnose-section":
        report = diagnose_section(Path(args.section), Path(args.consistency), allow_lists=args.allow_lists)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "diagnose-all":
        reports = diagnose_all(Path(args.sections_dir), Path(args.consistency))
        print(json.dumps(reports, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "full-review":
        report = full_review(
            sections_dir=Path(args.sections_dir),
            consistency_path=Path(args.consistency),
            index_path=Path(args.index),
            p1_path=Path(args.p1),
            ref_path=Path(args.ref),
            page_limit=args.page_limit,
        )
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        blocked = report.get("pass_status") == "blocked"
        print(json.dumps({"ok": not blocked, "output": str(out), "overall_grade": report["overall_grade"], "pass_status": report.get("pass_status"), "note": "等级/通过仅覆盖形式与内部一致性；立意/创新/可行性实质须专家或盲检，本引擎不核验"}, ensure_ascii=False))
        return 1 if blocked else 0

    if args.cmd == "export-report":
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        md = export_markdown(payload)
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(json.dumps({"ok": True, "output": str(out)}, ensure_ascii=False))
        return 0

    if args.cmd == "polish-review":
        report = full_review(
            sections_dir=Path(args.sections_dir),
            consistency_path=Path(args.consistency),
            index_path=Path(args.index),
            p1_path=Path(args.p1),
            ref_path=Path(args.ref),
            page_limit=args.page_limit,
        )
        json_out = Path(args.json_output)
        md_out = Path(args.md_output)
        json_out.parent.mkdir(parents=True, exist_ok=True)
        md_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        md_out.write_text(_export_polish_review(report), encoding="utf-8")
        print(json.dumps({"ok": True, "json_output": str(json_out), "md_output": str(md_out), "overall_grade": report["overall_grade"]}, ensure_ascii=False))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
