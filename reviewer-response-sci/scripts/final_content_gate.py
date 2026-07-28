#!/usr/bin/env python3
"""Final content gate: fail delivery when AI placeholder content remains."""

from __future__ import annotations

import argparse
from pathlib import Path

from unit_glob import iter_units


def _norm(v: object) -> str:
    if v is None:
        return ""
    return str(v).strip().lower()


def _is_placeholder(v: object) -> bool:
    n = _norm(v)
    if not n:
        return True
    markers = [
        "待ai",
        "ai_fill_required",
        "not provided by user",
        "[ai_fill_required]",
    ]
    return any(m in n for m in markers)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail if placeholder content remains in units/*.json")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--allow-placeholder", action="store_true")
    args = parser.parse_args()

    if args.allow_placeholder:
        print("FINAL_CONTENT_GATE: SKIP (allow-placeholder enabled)")
        return 0

    root = Path(args.project_root)
    units_dir = root / "units"
    if not units_dir.exists():
        print("FINAL_CONTENT_GATE: FAIL")
        print(f"- Missing units directory: {units_dir}")
        return 1

    failures: list[str] = []
    for p, unit in iter_units(units_dir):
        if unit.get("section") == "email":
            continue
        uid = unit.get("unit_id", p.name)
        content = unit.get("content", {})

        required_scalar = [
            "reviewer_comment_zh",
            "reviewer_intent_zh",
            "response_zh",
            "response_en",
            "revised_excerpt_en",
            "revised_excerpt_zh",
        ]
        for k in required_scalar:
            if _is_placeholder(content.get(k)):
                failures.append(f"{uid}: placeholder in content.{k}")

        for k in ["notes_core_zh", "notes_support_zh"]:
            arr = content.get(k, [])
            if not isinstance(arr, list) or not arr:
                failures.append(f"{uid}: missing/empty content.{k}")
                continue
            if any(_is_placeholder(x) for x in arr):
                failures.append(f"{uid}: placeholder in content.{k}")

        actions = content.get("modification_actions", [])
        if not isinstance(actions, list) or not actions:
            failures.append(f"{uid}: missing/empty content.modification_actions")
        else:
            for i, act in enumerate(actions):
                reason = ""
                if isinstance(act, dict):
                    reason = act.get("reason", "")
                if _is_placeholder(reason):
                    failures.append(f"{uid}: placeholder in content.modification_actions[{i}].reason")

    if failures:
        print("FINAL_CONTENT_GATE: FAIL")
        for f in failures:
            print(f"- {f}")
        return 1

    print("FINAL_CONTENT_GATE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

