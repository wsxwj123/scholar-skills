#!/usr/bin/env python3
"""Produce polish_change_report.md: per-paragraph what changed + risk flags + why-unchanged.

逐段对照 raw_text 与 polished_text,报告:是否改动、风险 flag、未改原因
(占位未润色 / 红线锁定不可改 / 已合规无需改)。纯报告,不改稿。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import normalize_ws, read_json, write_text


def reason_unchanged(unit: dict) -> str:
    if unit.get("polished_by") == "PLACEHOLDER":
        return "尚未润色(占位)"
    note = normalize_ws(unit.get("polish_note", ""))
    return note or "原文已合规,无需改动"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate polish change report")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    project_root = Path(args.project_root)
    output = Path(args.output) if args.output else project_root / "polish_change_report.md"
    polished_dir = project_root / "polished"
    index = read_json(project_root / "units_index.json", {"units": []})

    lines = ["# Polish Change Report", ""]
    changed_count = 0
    flagged_count = 0
    for entry in index.get("units", []):
        idx = entry["idx"]
        unit = read_json(polished_dir / f"{idx}.json", None)
        if unit is None:
            continue
        raw = normalize_ws(unit.get("raw_text", ""))
        polished = normalize_ws(unit.get("polished_text", ""))
        changed = raw != polished
        flags = unit.get("polish_risk_flags", [])
        if changed:
            changed_count += 1
        if flags:
            flagged_count += 1
        lines.append(f"## Unit {idx} · {unit.get('section_type', 'other')}")
        if changed:
            lines.append("**改动**: 是")
            lines.append("")
            lines.append("原文:")
            lines.append(f"> {raw}")
            lines.append("")
            lines.append("润色后:")
            lines.append(f"> {polished}")
        else:
            lines.append("**改动**: 否")
            lines.append(f"未改原因: {reason_unchanged(unit)}")
        if flags:
            lines.append("")
            lines.append("**风险 flag**:")
            for flag in flags:
                lines.append(f"- {flag}")
        lines.append("")

    summary = f"共 {len(index.get('units', []))} 段,改动 {changed_count} 段,带风险 flag {flagged_count} 段。"
    lines.insert(2, summary)
    lines.insert(3, "")
    write_text(output, "\n".join(lines) + "\n")
    print(json.dumps({"ok": True, "output": str(output.resolve()),
                      "changed": changed_count, "flagged": flagged_count}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
