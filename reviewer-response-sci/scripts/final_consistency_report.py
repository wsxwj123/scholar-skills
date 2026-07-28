#!/usr/bin/env python3
"""Generate final consistency report for reviewer-response project."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from unit_glob import load_units


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Final consistency report")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output", default="")
    parser.add_argument("--fail-on-gap", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root)
    units_dir = root / "units"
    m_dir = root / "manuscript_units"
    s_dir = root / "si_units"
    idx = read_json(root / "index.json")

    units = load_units(units_dir)
    comment_units = [u for u in units if u.get("section") != "email"]

    leaf_ids = []
    for rv in idx.get("toc", {}).get("reviewers", []):
        for sec in rv.get("sections", []):
            for item in sec.get("items", []):
                leaf_ids.append(item.get("unit_id"))

    linked_count = 0
    missing_excerpt_count = 0
    for u in comment_units:
        links = u.get("links", {})
        if links.get("manuscript_unit_ids") or links.get("si_unit_ids"):
            linked_count += 1
        if u.get("status", {}).get("excerpt_state") == "missing":
            missing_excerpt_count += 1

    report = {
        "counts": {
            "total_units": len(units),
            "comment_units": len(comment_units),
            "toc_leaf_items": len(leaf_ids),
            "manuscript_units": len(list(m_dir.glob("*.json"))),
            "si_units": len(list(s_dir.glob("*.json"))) if s_dir.exists() else 0,
        },
        "quality": {
            "linked_comment_units": linked_count,
            "linked_ratio": round(linked_count / len(comment_units), 4) if comment_units else 0.0,
            "missing_excerpt_count": missing_excerpt_count,
        },
        "gaps": {
            "leaf_mismatch": len(leaf_ids) != len(comment_units),
            "unlinked_comments": len(comment_units) - linked_count,
        },
    }

    out = Path(args.output) if args.output else root / "logs" / "final_consistency_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("FINAL_CONSISTENCY_REPORT: WROTE", out)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    has_gap = report["gaps"]["leaf_mismatch"] or report["gaps"]["unlinked_comments"] > 0
    if args.fail_on_gap and has_gap:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
