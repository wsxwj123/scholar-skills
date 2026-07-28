#!/usr/bin/env python3
"""State manager for atomic reviewer-response units."""

from __future__ import annotations
import sys as _sys
try:  # Windows GBK 控制台/管道捕获下 emoji print 防 UnicodeEncodeError
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import argparse
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from unit_glob import iter_units

try:
    import fcntl
except Exception:  # pragma: no cover
    fcntl = None

VALID_STATES = ["prewrite", "draft", "checked", "final"]


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


@contextmanager
def _lock(project_root: Path):
    lock_path = project_root / "logs" / ".state.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        if fcntl is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except Exception:
                pass
        os.close(fd)


def _unit_files(project_root: Path) -> list[Path]:
    return [p for p, _ in iter_units(project_root / "units")]


def _state_path(project_root: Path) -> Path:
    return project_root / "logs" / "unit_state.json"


def _load_state(project_root: Path) -> dict:
    return _read_json(_state_path(project_root), {"updated_at": "", "units": {}, "pipeline": {}})


def _sync_units(project_root: Path, state: dict) -> dict:
    units = state.setdefault("units", {})
    for fp in _unit_files(project_root):
        u = _read_json(fp, {})
        uid = u.get("unit_id")
        if not uid:
            continue
        item = units.setdefault(uid, {})
        item.setdefault("state", "final" if u.get("section") == "email" else "draft")
        item["title"] = u.get("title", uid)
        item["reviewer"] = u.get("reviewer", "")
        item["section"] = u.get("section", "")
        item["comment_number"] = str(u.get("comment_number", ""))
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    return state


def cmd_init(args) -> int:
    root = Path(args.project_root)
    with _lock(root):
        state = {"updated_at": "", "units": {}, "pipeline": {"last_run": "", "last_status": ""}}
        state = _sync_units(root, state)
        _write_json(_state_path(root), state)
    print("STATE_INIT: PASS")
    print(f"- units tracked: {len(state['units'])}")
    return 0


def cmd_sync(args) -> int:
    root = Path(args.project_root)
    with _lock(root):
        state = _load_state(root)
        before = len(state.get("units", {}))
        state = _sync_units(root, state)
        after = len(state.get("units", {}))
        if args.pipeline_status:
            state.setdefault("pipeline", {})["last_status"] = args.pipeline_status
            state["pipeline"]["last_run"] = datetime.now(timezone.utc).isoformat()
        _write_json(_state_path(root), state)
    print("STATE_SYNC: PASS")
    print(f"- units before: {before}")
    print(f"- units after: {after}")
    return 0


def cmd_set(args) -> int:
    root = Path(args.project_root)
    if args.state not in VALID_STATES:
        print(f"STATE_SET: FAIL\n- invalid state: {args.state}")
        return 1
    with _lock(root):
        state = _load_state(root)
        state = _sync_units(root, state)
        units = state.setdefault("units", {})
        if args.unit_id not in units:
            print(f"STATE_SET: FAIL\n- unknown unit_id: {args.unit_id}")
            return 1
        units[args.unit_id]["state"] = args.state
        units[args.unit_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        if args.note:
            units[args.unit_id]["note"] = args.note
        _write_json(_state_path(root), state)
    print("STATE_SET: PASS")
    print(f"- unit: {args.unit_id}")
    print(f"- state: {args.state}")
    return 0


def _snapshots_dir(project_root: Path) -> Path:
    return project_root / "logs" / "snapshots"


def cmd_snapshot(args) -> int:
    import shutil

    root = Path(args.project_root)
    units_dir = root / "units"
    if not units_dir.exists():
        print("STATE_SNAPSHOT: FAIL")
        print(f"- units dir not found: {units_dir}")
        return 1
    with _lock(root):
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        dest = _snapshots_dir(root) / f"units_{ts}"
        dest.mkdir(parents=True, exist_ok=True)
        copied = []
        for fp in _unit_files(root):
            shutil.copy2(fp, dest / fp.name)
            copied.append(fp.name)
        # also snapshot key tracking products if present
        for extra in ("index.json", "project_state.json"):
            ep = root / extra
            if ep.exists():
                shutil.copy2(ep, dest / extra)
                copied.append(extra)
    print("STATE_SNAPSHOT: PASS")
    print(f"- snapshot dir: {dest}")
    print(f"- files copied: {len(copied)}")
    return 0


def cmd_rollback(args) -> int:
    import shutil

    root = Path(args.project_root)
    snaps_dir = _snapshots_dir(root)
    if args.snapshot:
        snap = Path(args.snapshot)
        if not snap.is_absolute():
            snap = snaps_dir / args.snapshot
    else:
        candidates = sorted(p for p in snaps_dir.glob("units_*") if p.is_dir())
        if not candidates:
            print("STATE_ROLLBACK: FAIL")
            print(f"- no snapshot found under: {snaps_dir}")
            return 1
        snap = candidates[-1]
    if not snap.exists():
        print("STATE_ROLLBACK: FAIL")
        print(f"- snapshot not found: {snap}")
        return 1
    with _lock(root):
        units_dir = root / "units"
        units_dir.mkdir(parents=True, exist_ok=True)
        restored = []
        for fp in sorted(snap.glob("*.json")):
            if fp.name in ("index.json", "project_state.json"):
                shutil.copy2(fp, root / fp.name)
            else:
                shutil.copy2(fp, units_dir / fp.name)
            restored.append(fp.name)
    print("STATE_ROLLBACK: PASS")
    print(f"- from snapshot: {snap}")
    print(f"- files restored: {len(restored)}")
    for name in restored:
        print(f"  - {name}")
    return 0


_PLACEHOLDER = "[PENDING Step 7]"
_NO_CHANGE_VALUES = {"无", "无改动", "n/a", "none"}


def _is_placeholder(value: str) -> bool:
    v = value.strip()
    return (
        not v
        or v == _PLACEHOLDER
        or v.startswith("[AI_FILL_REQUIRED]")
        or v.startswith("[PENDING")
        or v.startswith("【待AI")
        or v.startswith("【待")
    )


def _is_no_change(value: str) -> bool:
    return value.strip().lower() in _NO_CHANGE_VALUES


def cmd_aggregate_edit_plan(args) -> int:
    """Back-fill manuscript_edit_plan.md [PENDING Step 7] placeholders from unit JSONs."""
    root = Path(args.project_root)
    plan_path = root / "manuscript_edit_plan.md"

    if not plan_path.exists():
        print("AGGREGATE_EDIT_PLAN: FAIL")
        print(f"- manuscript_edit_plan.md not found: {plan_path}")
        return 1

    # Load all units: uid -> content dict
    units: dict[str, dict] = {}
    for fp in _unit_files(root):
        u = _read_json(fp, {})
        uid = u.get("unit_id")
        if not uid:
            continue
        # Skip email-section units — they don't appear in manuscript_edit_plan
        if u.get("section") == "email":
            continue
        units[uid] = u.get("content", {})

    if not units:
        print("AGGREGATE_EDIT_PLAN: FAIL")
        print("- no unit JSON files found under units/")
        return 1

    lines = plan_path.read_text(encoding="utf-8").splitlines(keepends=True)
    filled: list[str] = []
    pending: list[str] = []
    skipped_no_change: list[str] = []

    for uid, content in sorted(units.items()):
        revised = content.get("revised_excerpt_en", "")

        if _is_placeholder(revised):
            pending.append(uid)
            continue

        # Determine replacement text
        if _is_no_change(revised):
            replacement = "无改动"
        else:
            revised_zh = content.get("revised_excerpt_zh", "")
            if revised_zh and not _is_no_change(revised_zh) and not _is_placeholder(revised_zh):
                replacement = f"{revised} ／ {revised_zh}"
            else:
                replacement = revised

        # Replace [PENDING Step 7] on each line that contains this uid
        replaced_on_this_uid = 0
        for i, line in enumerate(lines):
            if uid in line and _PLACEHOLDER in line:
                lines[i] = line.replace(_PLACEHOLDER, replacement, 1)
                replaced_on_this_uid += 1

        if replaced_on_this_uid:
            if _is_no_change(revised):
                skipped_no_change.append(uid)
            else:
                filled.append(uid)
        # If uid not found in plan (e.g. merged block or email), silently skip

    plan_path.write_text("".join(lines), encoding="utf-8")

    # Summary
    status = "PASS" if not pending else "WARN"
    print(f"AGGREGATE_EDIT_PLAN: {status}")
    print(f"- filled: {len(filled)}")
    if filled:
        for uid in filled:
            print(f"  ✓ {uid}")
    print(f"- no-change (无改动): {len(skipped_no_change)}")
    if skipped_no_change:
        for uid in skipped_no_change:
            print(f"  - {uid}")
    print(f"- still PENDING: {len(pending)}")
    if pending:
        print("  WARNING: the following units have no revised_excerpt_en yet:")
        for uid in pending:
            print(f"  ✗ {uid}")
        print("  → Fill revised_excerpt_en in these unit JSONs, then re-run aggregate-edit-plan.")
        return 2

    return 0


def cmd_show(args) -> int:
    root = Path(args.project_root)
    state = _load_state(root)
    if args.unit_id:
        unit = state.get("units", {}).get(args.unit_id)
        if unit is None:
            print("STATE_SHOW: FAIL")
            print(f"- unknown unit_id: {args.unit_id}")
            return 1
        print(json.dumps({args.unit_id: unit}, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="State manager for reviewer-response atomic project")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--project-root", required=True)
    p_init.set_defaults(func=cmd_init)

    p_sync = sub.add_parser("sync")
    p_sync.add_argument("--project-root", required=True)
    p_sync.add_argument("--pipeline-status", default="")
    p_sync.set_defaults(func=cmd_sync)

    p_set = sub.add_parser("set")
    p_set.add_argument("--project-root", required=True)
    p_set.add_argument("--unit-id", required=True)
    p_set.add_argument("--state", required=True)
    p_set.add_argument("--note", default="")
    p_set.set_defaults(func=cmd_set)

    p_show = sub.add_parser("show")
    p_show.add_argument("--project-root", required=True)
    p_show.add_argument("--unit-id", default="")
    p_show.set_defaults(func=cmd_show)

    p_snap = sub.add_parser("snapshot")
    p_snap.add_argument("--project-root", required=True)
    p_snap.set_defaults(func=cmd_snapshot)

    p_roll = sub.add_parser("rollback")
    p_roll.add_argument("--project-root", required=True)
    p_roll.add_argument("--snapshot", default="", help="Snapshot dir name or path; default = most recent")
    p_roll.set_defaults(func=cmd_rollback)

    p_agg = sub.add_parser("aggregate-edit-plan")
    p_agg.add_argument("--project-root", required=True)
    p_agg.set_defaults(func=cmd_aggregate_edit_plan)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
