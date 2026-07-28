#!/usr/bin/env python3
"""Generate per-paragraph polish task packs, then validate the polished results.

脚本不假装自己会改写。真正的语言润色由主 agent 按 SKILL.md 的 prompt 逐段执行。
本脚本负责两件确定性的事:

  pack    读 units/<idx>.json -> 为每段生成润色任务包(原文 + 该段 section_type
          对应的被动语态目标区间 + 句长上限 + 红线清单),写到
          polish_manifest.json,并把每段 polished_text 预填为 raw_text(占位,
          待主 agent 覆盖)写到 polished/<idx>.json。

  verify  读 polished/<idx>.json -> 逐段跑红线校验:
            · 数值守卫(numeric_tokens_preserved):一个都不能增删
            · 不确定性动词不升级(detect_certainty_upgrade)
            · 引用标记 [n] / DOI 集合不变
            · 去AI(find_ai_style_markers):残留即记 flag
            · 句长(英文≤30词 / 中文≤50字)软检查
            · meaning_changed 必须 false
          每段写回 polish_risk_flags;任一红线破 -> ok=false(但不 exit 1,
          交付级 fail-closed 由 strict_gate.py 负责)。

被动阈值/句长上限来自 references/polish_rules.json,可配,不硬卡。
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from common import (
    detect_certainty_upgrade,
    find_ai_style_markers,
    normalize_ws,
    numeric_tokens_preserved,
    read_json,
    write_json,
)
from strict_gate import is_soft_ai_marker

CITATION_RE = re.compile(r"\[\d+(?:\s*[-,]\s*\d+)*\]", re.IGNORECASE)
DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"]+", re.IGNORECASE)

DEFAULT_RULES = {
    "passive_target": {
        "methods": [0.30, 0.70],
        "results": [0.20, 0.55],
        "abstract": [0.0, 0.40],
        "intro": [0.0, 0.30],
        "discussion": [0.0, 0.30],
        "other": [0.0, 0.40],
    },
    "max_sentence_words_en": 30,
    "max_sentence_chars_zh": 50,
}


def load_rules(skill_root: Path) -> dict:
    rules_path = skill_root / "references" / "polish_rules.json"
    data = read_json(rules_path, None)
    if isinstance(data, dict) and data.get("passive_target"):
        return data
    return DEFAULT_RULES


def citation_set(text: str) -> set[str]:
    norm = normalize_ws(text)
    cites = {re.sub(r"\s+", "", m.group(0)) for m in CITATION_RE.finditer(norm)}
    cites |= {m.group(0).lower() for m in DOI_RE.finditer(norm)}
    return cites


def is_chinese(text: str) -> bool:
    return bool(re.search(r"[一-鿿]", text))


def passive_ratio_en(text: str) -> float:
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", normalize_ws(text)) if s.strip()]
    if not sentences:
        return 0.0
    passive = 0
    for s in sentences:
        if re.search(r"\b(?:is|are|was|were|be|been|being)\b\s+\w+(?:ed|en)\b", s, re.IGNORECASE):
            passive += 1
    return round(passive / len(sentences), 3)


def long_sentence_flags(text: str, rules: dict) -> list[str]:
    flags: list[str] = []
    norm = normalize_ws(text)
    if is_chinese(norm):
        limit = rules["max_sentence_chars_zh"]
        parts = [p for p in re.split(r"[。!?；]", norm) if p.strip()]
        if any(len(p) > limit for p in parts):
            flags.append(f"sentence >{limit} chars (zh)")
    else:
        limit = rules["max_sentence_words_en"]
        parts = [p for p in re.split(r"(?<=[.!?])\s+", norm) if p.strip()]
        if any(len(p.split()) > limit for p in parts):
            flags.append(f"sentence >{limit} words (en)")
    return flags


def cmd_pack(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root)
    skill_root = Path(__file__).resolve().parent.parent
    rules = load_rules(skill_root)
    units_dir = project_root / "units"
    polished_dir = project_root / "polished"
    polished_dir.mkdir(parents=True, exist_ok=True)

    index = read_json(project_root / "units_index.json", {"units": []})
    tasks = []
    for entry in index.get("units", []):
        idx = entry["idx"]
        unit = read_json(units_dir / f"{idx}.json", None)
        if unit is None:
            continue
        section_type = unit["section_type"]
        passive_lo, passive_hi = rules["passive_target"].get(
            section_type, rules["passive_target"]["other"]
        )
        task = {
            "idx": idx,
            "section_type": section_type,
            "raw_text": unit["raw_text"],
            "passive_target": [passive_lo, passive_hi],
            "max_sentence_words_en": rules["max_sentence_words_en"],
            "max_sentence_chars_zh": rules["max_sentence_chars_zh"],
            "red_lines": {
                "preserve_citations": sorted(citation_set(unit["raw_text"])),
                "preserve_numeric": unit["has_numeric"],
                "no_certainty_upgrade": True,
                "no_meaning_change": True,
            },
            "intensity": args.intensity,
        }
        tasks.append(task)
        # 预填占位:polished_text=raw_text,待主 agent 覆盖
        write_json(
            polished_dir / f"{idx}.json",
            {
                "idx": idx,
                "section_type": section_type,
                "prose": unit.get("prose", True),
                "raw_text": unit["raw_text"],
                "polished_text": unit["raw_text"],
                "meaning_changed": False,
                "polish_note": "",
                "polish_risk_flags": [],
                "polished_by": "PLACEHOLDER",
            },
        )

    write_json(
        project_root / "polish_manifest.json",
        {"intensity": args.intensity, "rules": rules, "tasks": tasks},
    )
    print(json.dumps({"ok": True, "tasks": len(tasks), "intensity": args.intensity}, ensure_ascii=False))
    return 0


def validate_unit(raw: str, polished: str, rules: dict, section_type: str, is_nonprose: bool = False) -> dict:
    num = numeric_tokens_preserved(raw, polished)
    cert = detect_certainty_upgrade(raw, polished)
    raw_cites = citation_set(raw)
    pol_cites = citation_set(polished)
    cites_ok = raw_cites == pol_cites
    # 非散文(参考文献/作者名单/图注等)保留原文不润色,去AI/句长检测不适用;红线仍查
    ai_markers = [] if is_nonprose else find_ai_style_markers(polished)
    flags: list[str] = []
    if not num["ok"]:
        flags.append(f"numeric changed introduced={num['introduced']} dropped={num['dropped']}")
    if not cert["ok"]:
        flags.append(f"certainty upgraded: {cert['introduced_strong_verbs']}")
    if not cites_ok:
        flags.append(f"citation set changed lost={sorted(raw_cites - pol_cites)} added={sorted(pol_cites - raw_cites)}")
    if ai_markers:
        flags.append(f"ai markers: {ai_markers}")
    if not is_nonprose:
        flags.extend(long_sentence_flags(polished, rules))
    return {
        "numbers_ok": num["ok"],
        "certainty_ok": cert["ok"],
        "citations_ok": cites_ok,
        "ai_markers": ai_markers,
        "polish_risk_flags": flags,
    }


def cmd_verify(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root)
    skill_root = Path(__file__).resolve().parent.parent
    rules = load_rules(skill_root)
    polished_dir = project_root / "polished"
    index = read_json(project_root / "units_index.json", {"units": []})

    all_ok = True
    results = []
    for entry in index.get("units", []):
        idx = entry["idx"]
        unit = read_json(polished_dir / f"{idx}.json", None)
        if unit is None:
            all_ok = False
            results.append({"idx": idx, "ok": False, "error": "polished unit missing"})
            continue
        raw = unit["raw_text"]
        polished = unit.get("polished_text", "")
        meaning_changed = bool(unit.get("meaning_changed", False))
        is_nonprose = unit.get("prose") is False or unit.get("polished_by") == "unchanged-nonprose"
        report = validate_unit(raw, polished, rules, unit.get("section_type", "other"), is_nonprose)
        # C 反AI降软:软标志(破折号/长句/scare quotes 等)只记 flag 不判 unit 不通过;
        # 仅 AI 套话禁词表等硬标志影响 unit_ok(与 strict_gate 交付口径一致)。
        hard_ai_markers = [m for m in report["ai_markers"] if not is_soft_ai_marker(m)]
        unit_ok = (
            report["numbers_ok"]
            and report["certainty_ok"]
            and report["citations_ok"]
            and not hard_ai_markers
            and not meaning_changed
            and unit.get("polished_by") != "PLACEHOLDER"
        )
        if unit.get("polished_by") == "PLACEHOLDER":
            report["polish_risk_flags"].append("not yet polished (PLACEHOLDER)")
        if meaning_changed:
            report["polish_risk_flags"].append("meaning_changed=true")
        unit["polish_risk_flags"] = report["polish_risk_flags"]
        write_json(polished_dir / f"{idx}.json", unit)
        all_ok = all_ok and unit_ok
        results.append({"idx": idx, "ok": unit_ok, "flags": report["polish_risk_flags"]})

    print(json.dumps({"ok": all_ok, "units": results}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Pack polish tasks / verify polished units")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_pack = sub.add_parser("pack", help="生成逐段润色任务包")
    p_pack.add_argument("--project-root", required=True)
    p_pack.add_argument("--intensity", choices=["light", "standard", "deep"], default="standard")
    p_pack.set_defaults(func=cmd_pack)

    p_ver = sub.add_parser("verify", help="校验主 agent 产出的 polished 单元(红线)")
    p_ver.add_argument("--project-root", required=True)
    p_ver.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
