#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from common import comment_nature, read_json, reviewer_sort_key, write_json, write_text


def render_issue_matrix(units: list[dict]) -> str:
    lines = [
        "# Issue Matrix",
        "",
        "| comment_id | reviewer原话 | 问题本质 | 证据来源 | 修改动作 | 目标位置 | 状态 |",
        "|---|---|---|---|---|---|---|",
    ]
    for unit in units:
        evidence = ", ".join(src.get("provider_family", "Not provided by user") for src in unit.get("evidence_sources", [])) or "Not provided by user"
        actions = " / ".join(x.get("action", "未开始") for x in unit.get("modification_actions", [])) or "未开始"
        atomic = unit.get("atomic_location", {})
        location = atomic.get("manuscript_section_id") or atomic.get("si_section_id") or "待定位"
        status = unit.get("status", "not_started")
        lines.append(
            f"| {unit['comment_id']} | {unit['reviewer_comment_en']} | {comment_nature(unit['reviewer_comment_en'])} | {evidence} | {actions} | {location} | {status} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build index.json and issue_matrix.md")
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()

    project_root = Path(args.project_root)
    units = [read_json(path, {}) for path in sorted((project_root / "units").glob("*.json"))]
    grouped: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for unit in units:
        grouped[unit["reviewer"]][unit["severity"]].append(unit)

    reviewers = []
    for reviewer in sorted(grouped.keys(), key=reviewer_sort_key):
        sections = []
        for severity in ("major", "minor"):
            items = grouped[reviewer].get(severity, [])
            if not items:
                continue
            sections.append(
                {
                    "id": f"{reviewer.replace(' ', '-').lower()}-{severity}",
                    "label": severity.capitalize(),
                    "items": [{"comment_id": unit["comment_id"], "unit_file": f"units/*_{unit['comment_id']}.json"} for unit in items],
                }
            )
        reviewers.append({"label": reviewer, "id": reviewer.replace(" ", "-").lower(), "sections": sections})

    write_json(project_root / "index.json", {"toc": {"root": "审稿回复目录", "reviewers": reviewers}})
    write_text(project_root / "issue_matrix.md", render_issue_matrix(units))
    print('{"ok": true}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
