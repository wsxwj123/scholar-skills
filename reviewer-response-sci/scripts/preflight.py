#!/usr/bin/env python3
"""Preflight checks before running reviewer-response pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_OWN_SKILL = "reviewer-response-sci"


def check_project_owner(project_root: Path, force_shared: bool) -> None:
    """Fail-closed if project_root already belongs to another skill.

    reviewer-response and revise-sci can be pointed at the same dir; their unit
    schemas differ, so writing our units into a revise-sci project (or vice
    versa) corrupts both. project_state.json carries the owning skill; if it
    names a different skill, abort unless --force-shared is given.
    """
    state_p = project_root / "project_state.json"
    if not state_p.exists():
        return
    try:
        owner = json.loads(state_p.read_text(encoding="utf-8")).get("skill", "")
    except Exception:
        return  # unreadable/malformed: don't block on it
    if owner and owner != _OWN_SKILL and not force_shared:
        sys.exit(
            f"PROJECT_ROOT 冲突: {project_root} 已属于技能 '{owner}',"
            f" 非 {_OWN_SKILL}。换一个 --project-root,或加 --force-shared 强制共享目录。"
        )


def check_docx_path(p: Path, label: str, errors: list[str]) -> None:
    if not p.exists():
        errors.append(f"Missing {label}: {p}")
        return
    if p.suffix.lower() != ".docx":
        errors.append(f"{label} must be .docx: {p}")
    if p.stat().st_size == 0:
        errors.append(f"{label} is empty: {p}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight checks for reviewer-response pipeline")
    parser.add_argument("--comments", required=True)
    parser.add_argument("--manuscript", required=True)
    parser.add_argument("--si", default="")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output-html", required=True)
    parser.add_argument("--force-shared", action="store_true",
                        help="允许在已属于其他技能的 PROJECT_ROOT 上运行(跳过所有权冲突检查)")
    args = parser.parse_args()

    errors: list[str] = []

    comments = Path(args.comments)
    manuscript = Path(args.manuscript)
    si = Path(args.si) if args.si else None
    project_root = Path(args.project_root)
    output_html = Path(args.output_html)

    # Fail-closed: don't scribble our units into another skill's project dir.
    check_project_owner(project_root, args.force_shared)

    check_docx_path(comments, "comments_docx", errors)
    check_docx_path(manuscript, "manuscript_docx", errors)
    if si:
        check_docx_path(si, "si_docx", errors)

    # Output path sanity
    if output_html.suffix.lower() != ".html":
        errors.append(f"output_html must end with .html: {output_html}")

    # Project root must be creatable/writable
    try:
        project_root.mkdir(parents=True, exist_ok=True)
        probe = project_root / ".preflight_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except Exception as e:  # noqa: BLE001
        errors.append(f"project_root not writable: {project_root} ({e})")

    # python-docx availability
    try:
        import docx  # type: ignore # noqa: F401
    except Exception as e:  # noqa: BLE001
        errors.append(f"python-docx unavailable: {e}")

    if errors:
        print("PREFLIGHT: FAIL")
        for e in errors:
            print(f"- {e}")
        return 1

    summary = {
        "comments_docx": str(comments.resolve()),
        "manuscript_docx": str(manuscript.resolve()),
        "si_docx": str(si.resolve()) if si else "",
        "project_root": str(project_root.resolve()),
        "output_html": str(output_html.resolve()),
    }
    print("PREFLIGHT: PASS")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
