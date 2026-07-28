#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import read_json, write_json


def default_row(item: dict, section_id: str, evidence_round: int) -> dict:
    claim_ids = item.get("claim_ids") or []
    return {
        "global_id": item.get("global_id"),
        "section_id": section_id,
        "claim_id": claim_ids[0] if claim_ids else None,
        "evidence_round": evidence_round,
        "source_tier": item.get("source_tier", "revision-citation"),
        "study_type": item.get("study_type", "unknown"),
        "year": item.get("year", "N/A"),
        "journal": item.get("journal", "N/A"),
        "title": item.get("title", "N/A"),
        "abstract": item.get("abstract", ""),
        "key_finding": item.get("key_finding", "N/A"),
        "effect_size": item.get("effect_size", "N/A"),
        "limitation": item.get("limitation", "N/A"),
        "relevance_score": item.get("relevance_score", None),
        "confidence": item.get("confidence", None),
        "updated_in_round3": False,
        "comment_ids": item.get("comment_ids", []),
        "reference_entry": item.get("reference_entry", ""),
    }


def upsert_rows(existing_rows: list[dict], new_rows: list[dict]) -> list[dict]:
    by_key = {(row.get("global_id"), row.get("section_id")): row for row in existing_rows}
    for row in new_rows:
        key = (row.get("global_id"), row.get("section_id"))
        if key in by_key:
            merged = dict(by_key[key])
            merged.update({k: v for k, v in row.items() if v not in (None, "", [])})
            by_key[key] = merged
        else:
            by_key[key] = row
    return [by_key[key] for key in sorted(by_key.keys(), key=lambda x: (x[1], x[0]))]


def cmd_bootstrap(args: argparse.Namespace) -> int:
    index = read_json(Path(args.index), [])
    if not isinstance(index, list):
        raise SystemExit("literature_index must be a list")
    matrix_path = Path(args.matrix)
    existing = read_json(matrix_path, [])
    existing = existing if isinstance(existing, list) else []

    rows = []
    for item in index:
        if not isinstance(item, dict):
            continue
        sections = item.get("related_sections") or ["unassigned"]
        for section in sections:
            rows.append(default_row(item, str(section), args.round))

    merged = upsert_rows(existing, rows)
    write_json(matrix_path, merged)
    print(f"Bootstrap complete: {len(rows)} candidate rows, {len(merged)} total matrix rows")
    return 0


def cmd_focus(args: argparse.Namespace) -> int:
    matrix = read_json(Path(args.matrix), [])
    rows = [row for row in matrix if str(row.get("section_id", "")).startswith(args.section)]
    print(json.dumps({"section": args.section, "count": len(rows), "rows": rows[: args.limit]}, ensure_ascii=False, indent=2))
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    matrix = read_json(Path(args.matrix), [])
    rows = matrix if isinstance(matrix, list) else []
    if args.section:
        rows = [row for row in rows if str(row.get("section_id", "")).startswith(args.section)]
    missing_claim = [row for row in rows if not row.get("claim_id")]
    missing_key = [
        row
        for row in rows
        if row.get("key_finding") in (None, "", "N/A") or row.get("limitation") in (None, "", "N/A")
    ]
    report = {
        "section": args.section or "",
        "rows": len(rows),
        "missing_claim": len(missing_claim),
        "missing_key_fields": len(missing_key),
        "round_distribution": {
            "1": sum(1 for row in rows if row.get("evidence_round") == 1),
            "2": sum(1 for row in rows if row.get("evidence_round") == 2),
            "3": sum(1 for row in rows if row.get("evidence_round") == 3),
        },
    }
    if args.report:
        write_json(Path(args.report), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.fail_on_gap and (report["missing_claim"] > 0 or report["missing_key_fields"] > 0):
        raise SystemExit(2)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review-writing style synthesis matrix manager for revise-sci")
    sub = parser.add_subparsers(dest="command", required=True)

    bootstrap = sub.add_parser("bootstrap")
    bootstrap.add_argument("--index", required=True)
    bootstrap.add_argument("--matrix", required=True)
    bootstrap.add_argument("--round", type=int, default=2)

    focus = sub.add_parser("focus")
    focus.add_argument("--matrix", required=True)
    focus.add_argument("--section", required=True)
    focus.add_argument("--limit", type=int, default=20)

    audit = sub.add_parser("audit")
    audit.add_argument("--matrix", required=True)
    audit.add_argument("--section", default="")
    audit.add_argument("--report", default="")
    audit.add_argument("--fail-on-gap", action="store_true")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "bootstrap":
        return cmd_bootstrap(args)
    if args.command == "focus":
        return cmd_focus(args)
    if args.command == "audit":
        return cmd_audit(args)
    raise SystemExit(2)


if __name__ == "__main__":
    raise SystemExit(main())
