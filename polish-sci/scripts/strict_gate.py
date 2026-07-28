#!/usr/bin/env python3
"""Delivery gate for polish-sci. Fail-closed: any breach -> exit 1.

交付前对每个 polished 单元逐项核验,任一不过即 exit 1,阻断"声明润色完成":
  · numbers_ok        数值/统计量集合与原文一致(numeric_tokens_preserved)
  · certainty_ok      不确定性动词未升级(detect_certainty_upgrade)
  · citations_ok      引用标记 [n] / DOI 集合不变
  · no AI markers     find_ai_style_markers 无残留
  · meaning 未变      meaning_changed=false
  · 非占位            polished_by != PLACEHOLDER(确认确实润色过)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from common import (
    detect_certainty_upgrade,
    find_ai_style_markers,
    named_tokens_preserved,
    normalize_ws,
    numeric_order_preserved,
    numeric_tokens_preserved,
    read_json,
)

CITATION_RE = re.compile(r"\[\d+(?:\s*[-,]\s*\d+)*\]", re.IGNORECASE)
DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"]+", re.IGNORECASE)

# 学术散文里长句/-ing 分词/修辞铺陈是正当修辞,降为软提示
# (记入 polish_risk_flags/报告,不阻断交付)。去AI必禁三项——破折号(em dash)、
# scare quotes、解释性冒号——例外:硬门禁、禁止使用,不在软集,由 strict_gate 对其 fail-close。
# 硬拦主干还含 AI 套话禁词表(delve into / cliche: … )。
_SOFT_AI_MARKERS = frozenset({
    "not only...but also",
    "rhetorical question",
    "trailing -ing clause",
})


def is_soft_ai_marker(marker) -> bool:
    m = str(marker)
    return m in _SOFT_AI_MARKERS or m.startswith("sentence >")


def citation_set(text: str) -> set[str]:
    norm = normalize_ws(text)
    cites = {re.sub(r"\s+", "", m.group(0)) for m in CITATION_RE.finditer(norm)}
    cites |= {m.group(0).lower() for m in DOI_RE.finditer(norm)}
    return cites


def citation_order(text: str) -> list[str]:
    """引用标记按文档顺序排成序列。[3][5] 绑的两句互换位置会改变顺序,
    集合比对看不出,顺序比对拦得下。"""
    norm = normalize_ws(text)
    return [re.sub(r"\s+", "", m.group(0)) for m in CITATION_RE.finditer(norm)]


def check_unit(unit: dict) -> tuple[bool, list[str]]:
    raw = unit.get("raw_text", "")
    polished = unit.get("polished_text", "")
    problems: list[str] = []

    if unit.get("polished_by") == "PLACEHOLDER":
        problems.append("unit not polished (PLACEHOLDER)")

    num = numeric_tokens_preserved(raw, polished)
    if not num["ok"]:
        problems.append(f"numeric changed: introduced={num['introduced']} dropped={num['dropped']}")

    numo = numeric_order_preserved(raw, polished)
    if not numo["ok"]:
        problems.append(f"numeric order changed: raw={numo['raw_seq']} polished={numo['polished_seq']}")

    named = named_tokens_preserved(raw, polished)
    if not named["ok"]:
        problems.append(
            "named/unit changed: "
            f"italic_dropped={named['italic_dropped']} italic_added={named['italic_added']} "
            f"unit_dropped={named['unit_dropped']} unit_added={named['unit_added']}"
        )

    cert = detect_certainty_upgrade(raw, polished)
    if not cert["ok"]:
        problems.append(f"certainty upgraded: {cert['introduced_strong_verbs']}")

    raw_cites, pol_cites = citation_set(raw), citation_set(polished)
    if raw_cites != pol_cites:
        problems.append(f"citations changed: lost={sorted(raw_cites - pol_cites)} added={sorted(pol_cites - raw_cites)}")

    raw_cite_seq, pol_cite_seq = citation_order(raw), citation_order(polished)
    if raw_cite_seq != pol_cite_seq:
        problems.append(f"citation order changed: raw={raw_cite_seq} polished={pol_cite_seq}")

    # 非散文(参考文献/作者名单/图注等)保留原文不润色,去AI检测不适用;红线(数值/引用/语气/meaning)仍查
    is_nonprose = unit.get("prose") is False or unit.get("polished_by") == "unchanged-nonprose"
    markers = [] if is_nonprose else find_ai_style_markers(polished)
    # C 反AI降软:句长、-ing 拖尾、not only...but also、修辞问句降为软提示不阻断交付;
    # 去AI必禁三项(破折号/scare quotes/解释性冒号)与 AI 套话禁词表仍硬拦 fail-close。
    blocking = [m for m in markers if not is_soft_ai_marker(m)]
    if blocking:
        problems.append(f"ai markers: {blocking}")

    if bool(unit.get("meaning_changed", False)):
        problems.append("meaning_changed=true")

    return (not problems, problems)


def independent_meaning_verdict(project_root: Path) -> tuple[bool, str]:
    """⑥ meaning_changed 不认改写方自填。

    改写方在 polished/<idx>.json 里自填 meaning_changed=false 只是自证,标 false 即蒙混。
    语义等价的唯一权威是独立 PL-G11 盲检子代理的裁决(delegate_review 写的
    <root>/.review_return_polish-dod.json)。这里要求其中 PL-G11 verdict==pass 且证据非空;
    缺文件 / 缺 PL-G11 / 非 pass / 空证据 一律视为"未核",fail-closed 拦下。"""
    ret = project_root / ".review_return_polish-dod.json"
    if not ret.is_file():
        return False, ("缺独立 PL-G11 盲检返回(.review_return_polish-dod.json);"
                       "改写方自填 meaning_changed=false 不作数,请先跑 delegate_review 委托独立子代理盲检语义等价")
    try:
        data = json.loads(ret.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f".review_return_polish-dod.json 解析失败: {exc}"
    if not isinstance(data, list):
        return False, "盲检返回格式非法(应为 JSON 数组)"
    entry = next((e for e in data if isinstance(e, dict) and e.get("id") == "PL-G11"), None)
    if entry is None:
        return False, "盲检返回缺 PL-G11 语义等价裁决;meaning_changed 自填不足信"
    verdict = entry.get("verdict")
    evidence = (entry.get("evidence") or "").strip()
    if verdict != "pass":
        return False, f"PL-G11 独立语义等价盲检未通过(verdict={verdict!r}): {evidence or '(无证据)'}"
    if not evidence:
        return False, "PL-G11 verdict=pass 但证据为空,视为未核(防无证据橡皮图章)"
    return True, "PL-G11 独立语义等价盲检通过"


def main() -> int:
    parser = argparse.ArgumentParser(description="polish-sci delivery gate (fail-closed)")
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()

    project_root = Path(args.project_root)
    polished_dir = project_root / "polished"
    index = read_json(project_root / "units_index.json", {"units": []})
    entries = index.get("units", [])

    if not entries:
        sys.stderr.write("[strict_gate] units_index.json 为空或缺失\n")
        print("STRICT_GATE: FAIL")
        return 1

    failures: list[dict] = []
    nonprose: list[dict] = []
    for entry in entries:
        idx = entry["idx"]
        unit = read_json(polished_dir / f"{idx}.json", None)
        if unit is None:
            failures.append({"idx": idx, "problems": ["polished unit missing"]})
            continue
        if unit.get("prose") is False or unit.get("polished_by") == "unchanged-nonprose":
            raw_preview = normalize_ws(unit.get("raw_text", ""))[:120]
            nonprose.append({"idx": idx, "heading": unit.get("heading", ""), "raw_preview": raw_preview})
        ok, problems = check_unit(unit)
        if not ok:
            failures.append({"idx": idx, "problems": problems})

    summary = {"checked": len(entries), "failed": len(failures),
               "nonprose_unpolished": nonprose, "failures": failures}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    # 被判为"非散文"而整段原样保留的段落:逐条点名给作者复核判定是否误判(拿不准应润色)。
    if nonprose:
        sys.stderr.write(f"[strict_gate] {len(nonprose)} 段判为非散文未润色,请逐段复核判定是否误判:\n")
        for item in nonprose:
            sys.stderr.write(f"  · unit {item['idx']} [{item['heading']}] {item['raw_preview']}\n")
    if failures:
        print("STRICT_GATE: FAIL")
        sys.stderr.write("[strict_gate] fail-closed:不得向用户声明润色完成。\n")
        return 1
    # ⑥ 语义等价只认独立 PL-G11 盲检,改写方自填 meaning_changed=false 不足信。
    mv_ok, mv_reason = independent_meaning_verdict(project_root)
    if not mv_ok:
        print("STRICT_GATE: FAIL")
        sys.stderr.write(f"[strict_gate] fail-closed:{mv_reason}\n")
        return 1
    print("STRICT_GATE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
