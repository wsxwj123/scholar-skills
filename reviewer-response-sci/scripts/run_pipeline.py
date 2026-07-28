#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl
except Exception:  # pragma: no cover
    fcntl = None


def run(cmd: list[str]) -> tuple[int, float]:
    t0 = time.time()
    print("RUN:", " ".join(cmd))
    p = subprocess.run(cmd)
    dt = time.time() - t0
    return p.returncode, dt


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _signature(args: argparse.Namespace) -> str:
    payload = {
        "comments": str(Path(args.comments).resolve()),
        "manuscript": str(Path(args.manuscript).resolve()),
        "si": str(Path(args.si).resolve()) if args.si else "",
        "project_root": str(Path(args.project_root).resolve()),
        "output_html": str(Path(args.output_html).resolve()),
        "title": args.title,
        "require_links": bool(args.require_links),
        "allow_placeholder": bool(args.allow_placeholder),
        "fail_on_conflict": bool(args.fail_on_conflict),
        "fail_on_gap": bool(args.fail_on_gap),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


@contextmanager
def _pipeline_lock(project_root: Path):
    lock_path = project_root / "logs" / ".pipeline.lock"
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


def _load_checkpoint(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_checkpoint(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="One-shot pipeline: preflight + build + gates + report + html gate")
    parser.add_argument("--comments", required=True)
    parser.add_argument("--manuscript", required=True)
    parser.add_argument("--si", default="")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output-html", required=True)
    parser.add_argument("--title", default="Reviewer Response Full Package")
    parser.add_argument("--require-links", action="store_true")
    parser.add_argument("--allow-placeholder", action="store_true", help="Allow placeholder revised text in strict gate")
    parser.add_argument("--fail-on-conflict", action="store_true", help="Fail pipeline if consistency conflicts found")
    parser.add_argument("--fail-on-gap", action="store_true", help="Fail pipeline if final consistency report has gaps")
    parser.add_argument("--resume", action="store_true", help="Resume from last successful checkpoint if signature matches")
    parser.add_argument("--force-shared", action="store_true", help="Allow running on a PROJECT_ROOT owned by another skill (skip ownership conflict check)")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    project_root = Path(args.project_root)

    preflight = script_dir / "preflight.py"
    build = script_dir / "build_full_package.py"
    gate = script_dir / "strict_gate.py"
    consistency = script_dir / "consistency_check.py"
    final_report = script_dir / "final_consistency_report.py"
    html_gate = script_dir / "html_format_check.py"
    final_content_gate = script_dir / "final_content_gate.py"
    risk_check = script_dir / "risk_check.py"
    citation_guard = script_dir / "citation_guard.py"
    citation_tracker = script_dir / "citation_ref_tracker.py"
    state_mgr = script_dir / "state_manager.py"
    render_html_script = script_dir / "render_from_atomic_json.py"

    preflight_cmd = [sys.executable, str(preflight), "--comments", args.comments, "--manuscript", args.manuscript, "--project-root", args.project_root, "--output-html", args.output_html]
    if args.si:
        preflight_cmd.extend(["--si", args.si])
    if args.force_shared:
        preflight_cmd.append("--force-shared")

    build_cmd = [sys.executable, str(build), "--comments", args.comments, "--manuscript", args.manuscript, "--project-root", args.project_root, "--output-html", args.output_html, "--title", args.title]
    if args.si:
        build_cmd.extend(["--si", args.si])

    gate_cmd = [sys.executable, str(gate), "--project-root", args.project_root]
    if args.require_links:
        gate_cmd.append("--require-links")
    if args.allow_placeholder:
        gate_cmd.append("--allow-placeholder")

    consistency_cmd = [sys.executable, str(consistency), "--project-root", args.project_root]
    if args.fail_on_conflict:
        consistency_cmd.append("--fail-on-conflict")

    report_cmd = [sys.executable, str(final_report), "--project-root", args.project_root]
    if args.fail_on_gap:
        report_cmd.append("--fail-on-gap")

    final_content_cmd = [sys.executable, str(final_content_gate), "--project-root", args.project_root]
    if args.allow_placeholder:
        final_content_cmd.append("--allow-placeholder")

    html_cmd = [sys.executable, str(html_gate), args.output_html]
    render_html_cmd = [sys.executable, str(render_html_script), "--project-root", args.project_root, "--output-html", args.output_html, "--title", args.title]
    risk_cmd = [sys.executable, str(risk_check), "--project-root", args.project_root]
    citation_guard_cmd = [sys.executable, str(citation_guard), "--project-root", args.project_root]
    citation_tracker_cmd = [sys.executable, str(citation_tracker), "--project-root", args.project_root]
    state_sync_cmd = [sys.executable, str(state_mgr), "sync", "--project-root", args.project_root, "--pipeline-status", "pass"]

    # Steps marked as always_run are never skipped by --resume (re-run every time).
    # render_html must always run so the HTML reflects the latest filled units.
    ALWAYS_RUN_STEPS = {"render_html"}

    steps = [
        ("preflight", preflight_cmd),
        ("build", build_cmd),
        ("strict_gate", gate_cmd),
        ("final_content_gate", final_content_cmd),
        ("consistency", consistency_cmd),
        ("final_report", report_cmd),
        # Always re-render HTML from the current units JSON before gate validation.
        # This ensures filled units are reflected even when --resume skips build.
        ("render_html", render_html_cmd),
        ("html_gate", html_cmd),
        ("risk_check", risk_cmd),
        ("citation_guard", citation_guard_cmd),
        ("citation_ref_tracker", citation_tracker_cmd),
        ("state_sync", state_sync_cmd),
    ]

    tx_dir = project_root / "logs" / "transactions"
    ckpt_path = project_root / "logs" / "checkpoints" / "pipeline_checkpoint.json"
    sig = _signature(args)

    with _pipeline_lock(project_root):
        checkpoint = _load_checkpoint(ckpt_path)
        completed = set()
        if args.resume and checkpoint.get("signature") == sig:
            completed = set(checkpoint.get("completed_steps", []))

        logs = checkpoint.get("steps", []) if (args.resume and checkpoint.get("signature") == sig) else []

        checkpoint_state = {
            "signature": sig,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "completed_steps": sorted(completed),
            "steps": logs,
        }
        _save_checkpoint(ckpt_path, checkpoint_state)

        pipeline_status = "pass"
        failed_step = ""
        failed_code = 0

        for step, cmd in steps:
            if step in completed and step not in ALWAYS_RUN_STEPS:
                print(f"SKIP (resume): {step}")
                continue
            rc, dt = run(cmd)
            status = "pass" if rc == 0 else "fail"
            logs.append({"step": step, "cmd": cmd, "duration_sec": round(dt, 3), "status": status, "return_code": rc})
            if rc != 0:
                pipeline_status = "fail"
                failed_step = step
                failed_code = rc
                checkpoint_state = {
                    "signature": sig,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                    "completed_steps": sorted(completed),
                    "steps": logs,
                    "pipeline_status": pipeline_status,
                    "failed_step": failed_step,
                    "failed_code": failed_code,
                }
                _save_checkpoint(ckpt_path, checkpoint_state)
                break
            completed.add(step)
            checkpoint_state = {
                "signature": sig,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "completed_steps": sorted(completed),
                "steps": logs,
                "pipeline_status": pipeline_status,
            }
            _save_checkpoint(ckpt_path, checkpoint_state)

        tx_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
        tx_file = tx_dir / f"tx_{ts}.json"
        tx_payload = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "project_root": str(project_root.resolve()),
            "output_html": str(Path(args.output_html).resolve()),
            "title": args.title,
            "require_links": args.require_links,
            "allow_placeholder": args.allow_placeholder,
            "fail_on_conflict": args.fail_on_conflict,
            "fail_on_gap": args.fail_on_gap,
            "resume": args.resume,
            "pipeline_status": pipeline_status,
            "failed_step": failed_step,
            "failed_code": failed_code,
            "steps": logs,
        }
        tx_file.write_text(json.dumps(tx_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print("TRANSACTION_LOG:", tx_file)

        tracked_files = [
            script_dir / "build_full_package.py",
            script_dir / "strict_gate.py",
            script_dir / "html_format_check.py",
            script_dir / "render_from_atomic_json.py",
            script_dir.parent / "SKILL.md",
            project_root / "index.json",
            project_root / "project_state.json",
            Path(args.output_html),
        ]
        snapshot = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "project_root": str(project_root.resolve()),
            "output_html": str(Path(args.output_html).resolve()),
            "inputs": {
                "comments": str(Path(args.comments).resolve()),
                "manuscript": str(Path(args.manuscript).resolve()),
                "si": str(Path(args.si).resolve()) if args.si else "",
            },
            "files": [],
        }
        for p in tracked_files:
            if p.exists():
                snapshot["files"].append(
                    {
                        "path": str(p.resolve()),
                        "sha256": _sha256_file(p),
                        "size": p.stat().st_size,
                    }
                )
            else:
                snapshot["files"].append({"path": str(p.resolve()), "missing": True})

        snapshot_path = project_root / "logs" / "version_snapshot.json"
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        print("VERSION_SNAPSHOT:", snapshot_path)

    if pipeline_status == "pass":
        print("PIPELINE: PASS")
        return 0
    print(f"PIPELINE: FAIL (step={failed_step}, code={failed_code})")
    return failed_code or 1


if __name__ == "__main__":
    raise SystemExit(main())
