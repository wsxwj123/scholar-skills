#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from common import autodiscover_reference_source, compute_tree_signature, directory_signature, normalize_ws, path_signature, read_json, write_json

STEP_ORDER = (
    "preflight",
    "citation_guard",
    "atomize_comments",
    "atomize_manuscript",
    "issue_index",
    "state_refresh",
    "revise",
    "polish",
    "literature",
    "reference_registry",
    "reference_search_execute",
    "export",
    "final_report",
    "gate",
)
REFERENCE_SEARCH_DECISIONS = ("ask", "approved", "declined")


def run_step(cmd: list[str]) -> None:
    completed = subprocess.run(cmd, text=True, capture_output=True, encoding="utf-8", errors="replace")
    if completed.stdout:
        print(completed.stdout.strip())
    if completed.stderr:
        print(completed.stderr.strip(), file=sys.stderr)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def has_units(project_root: Path) -> bool:
    return (project_root / "units").exists() and any((project_root / "units").glob("*.json"))


def has_manuscript_sections(project_root: Path) -> bool:
    return (project_root / "manuscript_section_index.json").exists() and any((project_root / "manuscript_sections").glob("*.md"))


def has_issue_index(project_root: Path) -> bool:
    return (project_root / "index.json").exists() and (project_root / "issue_matrix.md").exists()


def has_revision_outputs(project_root: Path) -> bool:
    return (
        (project_root / "response_to_reviewers.md").exists()
        and (project_root / "manuscript_edit_plan.md").exists()
        and (project_root / "comment_records").exists()
        and any((project_root / "comment_records").glob("*.md"))
    )


def has_state_outputs(project_root: Path) -> bool:
    state_dir = project_root / "state"
    return (
        (state_dir / "section_digests.json").exists()
        and (state_dir / "comment_registry.json").exists()
    )


def has_polish_outputs(project_root: Path) -> bool:
    return (
        (project_root / "revision_polish_manifest.json").exists()
        and (project_root / "revision_polish_execution.json").exists()
    )


def has_citation_guard_outputs(project_root: Path) -> bool:
    return (project_root / "paper_search_guard_report.json").exists() and (project_root / "paper_search_validated.json").exists()


def has_literature_outputs(project_root: Path) -> bool:
    return (
        (project_root / "data" / "literature_index.json").exists()
        and (project_root / "data" / "synthesis_matrix.json").exists()
        and (project_root / "data" / "synthesis_matrix_audit.json").exists()
    )


def has_reference_registry_outputs(project_root: Path) -> bool:
    return (
        (project_root / "data" / "reference_registry.json").exists()
        and (project_root / "data" / "reference_coverage_audit.json").exists()
    )


def has_pending_citation_units(project_root: Path) -> bool:
    units_dir = project_root / "units"
    if not units_dir.exists():
        return False
    for unit_path in units_dir.glob("*.json"):
        unit = read_json(unit_path, {})
        if unit.get("status") != "needs_author_confirmation":
            continue
        if unit.get("editorial_intent") == "citation":
            return True
        for source in unit.get("evidence_sources", []) or []:
            if source.get("provider_family") == "paper-search" and source.get("source") == "candidate-search-required":
                return True
    return False


def default_paper_search_results_path(project_root: Path) -> Path:
    return project_root / "paper_search_results.json"


def normalize_runner_value(value: str) -> str:
    return value.strip()


def effective_paper_search_results_path(args: argparse.Namespace, project_root: Path) -> Path | None:
    if args.paper_search_results:
        return Path(args.paper_search_results).resolve()
    default_path = default_paper_search_results_path(project_root)
    if default_path.exists():
        return default_path.resolve()
    return None


def resolve_references_source(args: argparse.Namespace) -> Path | None:
    if getattr(args, "references_source", ""):
        return Path(args.references_source).resolve()
    comments = Path(args.comments)
    manuscript = Path(args.manuscript)
    attachments = Path(args.attachments_dir) if getattr(args, "attachments_dir", "") else None
    project_root = Path(args.project_root)
    return autodiscover_reference_source(comments, attachments, project_root, manuscript)


def current_input_signatures(args: argparse.Namespace) -> dict:
    references_source = resolve_references_source(args)
    return {
        "comments_path": path_signature(Path(args.comments)),
        "manuscript_docx_path": path_signature(Path(args.manuscript)),
        "si_docx_path": path_signature(Path(args.si)) if args.si else path_signature(None),
        "attachments_dir_path": directory_signature(Path(args.attachments_dir)) if args.attachments_dir else directory_signature(None),
        "reference_docx_path": path_signature(Path(args.reference_docx)) if args.reference_docx else path_signature(None),
        "journal_style": getattr(args, "journal_style", "journal-manuscript"),
        "paper_search_results_path": path_signature(Path(args.paper_search_results)) if args.paper_search_results else path_signature(None),
        "references_source_path": path_signature(references_source),
        "reference_search_decision": getattr(args, "reference_search_decision", "ask"),
        "expected_comments_mode": getattr(args, "expected_comments_mode", ""),
        "auto_run_reference_search": bool(getattr(args, "auto_run_reference_search", False)),
        "paper_search_runner": normalize_runner_value(getattr(args, "paper_search_runner", "")),
        "opencode_driver_command": normalize_runner_value(getattr(args, "opencode_driver_command", "")),
        "revision_polish_runner": normalize_runner_value(getattr(args, "revision_polish_runner", "")),
        "context_token_budget": int(getattr(args, "context_token_budget", 4200)),
        "context_tail_lines": int(getattr(args, "context_tail_lines", 80)),
    }


def resume_inputs_changed(project_root: Path, args: argparse.Namespace) -> list[str]:
    state = read_json(project_root / "project_state.json", {})
    previous = state.get("input_signatures", {})
    current = current_input_signatures(args)
    changed = []
    for key, value in current.items():
        if previous.get(key) != value:
            changed.append(key)
    return changed


# --resume-keep-unaffected only reasons about content inputs whose effect is
# unit-local (comments text + manuscript/SI section text). Any other changed key
# (journal_style, runners, decisions, references, budgets…) affects formatting or
# behavior globally and cannot be scoped to a unit subset — those force rebuild.
KEEP_UNAFFECTED_CONTENT_KEYS = {"comments_path", "manuscript_docx_path", "si_docx_path"}


def _section_text_map(index: dict) -> dict[str, str]:
    """section_id -> normalized concatenation of its paragraphs' ORIGINAL text."""
    out: dict[str, str] = {}
    for section in index.get("sections", []):
        sid = section.get("section_id", "")
        if not sid:
            continue
        out[sid] = normalize_ws(" ".join(p.get("text", "") for p in section.get("paragraphs", [])))
    return out


def compute_affected_units(project_root: Path, args: argparse.Namespace, py: str, script_dir: Path) -> list[str] | None:
    """Re-atomize the current comments + manuscript(+SI) into a throwaway scratch
    project and diff against the live curated state. Returns the sorted list of
    comment_ids whose comment text changed OR whose anchored section text changed.
    Returns None if the scratch re-atomize failed (caller must then refuse to keep)."""
    with tempfile.TemporaryDirectory(prefix="revise_resume_") as scratch:
        scratch_root = Path(scratch)
        try:
            subprocess.run(
                [py, str(script_dir / "atomize_comments.py"), "--comments", args.comments, "--project-root", str(scratch_root)],
                text=True, capture_output=True, check=True, timeout=180,
            )
            atomize_doc = [py, str(script_dir / "atomize_manuscript.py"), "--manuscript", args.manuscript, "--project-root", str(scratch_root)]
            if args.si:
                atomize_doc.extend(["--si", args.si])
            subprocess.run(atomize_doc, text=True, capture_output=True, encoding="utf-8", errors="replace", check=True, timeout=300)
        except Exception:
            return None

        fresh_comments = {
            normalize_ws(str(read_json(p, {}).get("comment_id", ""))): normalize_ws(str(read_json(p, {}).get("reviewer_comment_original", "")))
            for p in (scratch_root / "units").glob("*.json")
        }
        fresh_ms = _section_text_map(read_json(scratch_root / "manuscript_section_index.json", {"sections": []}))
        fresh_si = _section_text_map(read_json(scratch_root / "si_section_index.json", {"sections": []}))

    live_ms = _section_text_map(read_json(project_root / "manuscript_section_index.json", {"sections": []}))
    live_si = _section_text_map(read_json(project_root / "si_section_index.json", {"sections": []}))
    changed_sections = {
        sid for sid in set(live_ms) | set(fresh_ms) if live_ms.get(sid) != fresh_ms.get(sid)
    } | {
        sid for sid in set(live_si) | set(fresh_si) if live_si.get(sid) != fresh_si.get(sid)
    }

    affected: set[str] = set()
    live_comments: dict[str, str] = {}
    for unit_path in sorted((project_root / "units").glob("*.json")):
        unit = read_json(unit_path, {})
        cid = normalize_ws(str(unit.get("comment_id", "")))
        if not cid:
            continue
        live_comments[cid] = normalize_ws(str(unit.get("reviewer_comment_original", "")))
        atomic = unit.get("atomic_location") or {}
        sid = atomic.get("manuscript_section_id") or atomic.get("si_section_id") or ""
        if sid and sid in changed_sections:
            affected.add(cid)
    # comment text added / removed / changed
    for cid in set(live_comments) | set(fresh_comments):
        if live_comments.get(cid) != fresh_comments.get(cid):
            affected.add(cid)
    return sorted(affected)


def refresh_stored_signatures(project_root: Path, args: argparse.Namespace) -> None:
    state = read_json(project_root / "project_state.json", {})
    stored = state.get("input_signatures", {})
    stored.update(current_input_signatures(args))
    state["input_signatures"] = stored
    state.setdefault("skill", "revise-sci")
    write_json(project_root / "project_state.json", state)


def current_skill_signature(script_dir: Path) -> str:
    return compute_tree_signature(script_dir.parent, patterns=("*.py", "*.md"))


def clear_project_outputs(project_root: Path) -> None:
    removable_dirs = [
        "units",
        "manuscript_sections",
        "si_sections",
        "comment_records",
        "data",
        "state",
    ]
    removable_files = [
        "precheck_report.md",
        "attachments_manifest.json",
        "project_state.json",
        "index.json",
        "issue_matrix.md",
        "manuscript_section_index.json",
        "si_section_index.json",
        "response_to_reviewers.md",
        "response_to_reviewers.docx",
        "manuscript_edit_plan.md",
        "final_consistency_report.md",
        "paper_search_guard_report.json",
        "paper_search_validated.json",
        "literature_index_report.json",
        "reference_sync_report.json",
        "reference_search_manifest.json",
        "reference_search_task.md",
        "reference_search_strategy.json",
        "reference_search_status.json",
        "reference_search_rounds.json",
        "reference_search_execution.json",
        "reference_search_execution_request.md",
        "paper_search_results.json",
        "revision_polish_manifest.json",
        "revision_polish_prompt.md",
        "revision_polish_results.json",
        "revision_polish_execution.json",
    ]
    for dirname in removable_dirs:
        path = project_root / dirname
        if path.exists():
            shutil.rmtree(path)
    for filename in removable_files:
        path = project_root / filename
        if path.exists():
            path.unlink()


def clear_step_outputs(project_root: Path, output_md: Path, output_docx: Path, step_name: str) -> None:
    if step_name == "preflight":
        clear_project_outputs(project_root)
        for artifact in (output_md, output_docx):
            if artifact.exists():
                artifact.unlink()
        return

    if step_name == "citation_guard":
        for filename in ("paper_search_guard_report.json", "paper_search_validated.json"):
            path = project_root / filename
            if path.exists():
                path.unlink()
        return

    if step_name == "atomize_comments":
        units_dir = project_root / "units"
        if units_dir.exists():
            shutil.rmtree(units_dir)
        return

    if step_name == "atomize_manuscript":
        for dirname in ("manuscript_sections", "si_sections"):
            path = project_root / dirname
            if path.exists():
                shutil.rmtree(path)
        for filename in ("manuscript_section_index.json", "si_section_index.json"):
            path = project_root / filename
            if path.exists():
                path.unlink()
        return

    if step_name == "issue_index":
        for filename in ("index.json", "issue_matrix.md"):
            path = project_root / filename
            if path.exists():
                path.unlink()
        return

    if step_name == "state_refresh":
        state_dir = project_root / "state"
        if state_dir.exists():
            shutil.rmtree(state_dir)
        return

    if step_name == "revise":
        records_dir = project_root / "comment_records"
        if records_dir.exists():
            shutil.rmtree(records_dir)
        state_dir = project_root / "state"
        for name in ("comment_windows", "write_cycle_reports", "comment_memory"):
            path = state_dir / name
            if path.exists():
                shutil.rmtree(path)
        for filename in ("comment_cycle_log.json",):
            path = state_dir / filename
            if path.exists():
                path.unlink()
        for filename in ("response_to_reviewers.md", "response_to_reviewers.docx", "manuscript_edit_plan.md"):
            path = project_root / filename
            if path.exists():
                path.unlink()
        return

    if step_name == "polish":
        for filename in ("revision_polish_manifest.json", "revision_polish_prompt.md", "revision_polish_results.json", "revision_polish_execution.json"):
            path = project_root / filename
            if path.exists():
                path.unlink()
        return

    if step_name == "literature":
        data_dir = project_root / "data"
        for filename in ("literature_index.json", "synthesis_matrix.json", "synthesis_matrix_audit.json", "literature_index_report.json"):
            path = data_dir / filename
            if path.exists():
                path.unlink()
        return

    if step_name == "reference_registry":
        data_dir = project_root / "data"
        for filename in ("reference_registry.json", "reference_coverage_audit.json"):
            path = data_dir / filename
            if path.exists():
                path.unlink()
        for filename in ("reference_sync_report.json", "reference_recovery_request.md"):
            path = project_root / filename
            if path.exists():
                path.unlink()
        for filename in ("reference_search_manifest.json", "reference_search_task.md", "reference_search_strategy.json", "reference_search_status.json", "reference_search_rounds.json"):
            path = project_root / filename
            if path.exists():
                path.unlink()
        if output_md.exists():
            output_md.unlink()
        return

    if step_name == "reference_search_execute":
        for filename in ("reference_search_execution.json", "reference_search_execution_request.md"):
            path = project_root / filename
            if path.exists():
                path.unlink()
        auto_results = default_paper_search_results_path(project_root)
        if auto_results.exists():
            auto_results.unlink()
        return

    if step_name == "export":
        for artifact in (project_root / "response_to_reviewers.docx", output_docx):
            if artifact.exists():
                artifact.unlink()
        return

    if step_name == "final_report":
        report_path = project_root / "final_consistency_report.md"
        if report_path.exists():
            report_path.unlink()
        return


def clear_outputs_from_step(project_root: Path, output_md: Path, output_docx: Path, start_step: str) -> None:
    start_index = STEP_ORDER.index(start_step)
    for step_name in STEP_ORDER[start_index:]:
        clear_step_outputs(project_root, output_md, output_docx, step_name)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the revise-sci pipeline end to end")
    parser.add_argument("--comments", required=True)
    parser.add_argument("--manuscript", required=True)
    parser.add_argument("--si", default="")
    parser.add_argument("--attachments-dir", default="")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output-md", required=True)
    parser.add_argument("--output-docx", required=True)
    parser.add_argument("--reference-docx", default="")
    parser.add_argument(
        "--journal-style",
        choices=("journal-manuscript", "nature-review", "cell-press", "lancet-review"),
        default="journal-manuscript",
    )
    parser.add_argument("--paper-search-results", default="")
    parser.add_argument("--references-source", default="")
    parser.add_argument("--reference-search-decision", choices=REFERENCE_SEARCH_DECISIONS, default="ask")
    parser.add_argument("--expected-comments-mode", default="")
    parser.add_argument("--live-citation-verify", action="store_true")
    parser.add_argument("--offline-citation-verify", action="store_true")
    parser.add_argument("--auto-run-reference-search", action="store_true")
    parser.add_argument("--paper-search-runner", default="")
    parser.add_argument("--revision-polish-runner", default="")
    parser.add_argument("--opencode-driver-command", default="")
    parser.add_argument("--context-token-budget", type=int, default=4200)
    parser.add_argument("--context-tail-lines", type=int, default=80)
    parser.add_argument("--force-shared", action="store_true", help="跳过 preflight 的 PROJECT_ROOT 归属冲突检测(该目录已被别的技能占用时)。与独立 preflight.py 的同名逃生口保持一致。")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--resume-from", choices=STEP_ORDER)
    parser.add_argument("--resume-keep-unaffected", action="store_true", help="On --resume with changed inputs, if the change touches no located comment unit (comments/manuscript/si only), keep all curated units and continue instead of demanding a full rebuild. If any unit is affected, list them and stop.")
    parser.add_argument("--force-rebuild", action="store_true")
    parser.add_argument("--allow-rebuild-fallback", action="store_true", help="Forwarded to export_docx: accept an md full-rebuild (reformatted, tables/figure-positions lost) when in-place format-preserving export is rejected. Off by default (export hard-stops and asks).")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    project_root = Path(args.project_root)
    output_md_path = Path(args.output_md)
    output_docx_path = Path(args.output_docx)
    py = sys.executable
    resolved_references_source = str(resolve_references_source(args) or "")
    skill_signature = current_skill_signature(script_dir)

    if args.resume and args.force_rebuild:
        print("--resume and --force-rebuild cannot be used together", file=sys.stderr)
        raise SystemExit(2)
    if args.resume_from and not args.resume:
        print("--resume-from requires --resume", file=sys.stderr)
        raise SystemExit(2)
    if args.live_citation_verify and args.offline_citation_verify:
        print("--live-citation-verify and --offline-citation-verify cannot be used together", file=sys.stderr)
        raise SystemExit(2)

    # PROJECT_ROOT 归属冲突检测(fail-closed):必须在 force-rebuild/resume 清空 state 之前做。
    # 否则下面的 clear_project_outputs 会先删掉 project_state.json，冲突信号丢失、preflight 的
    # 同名检查(那时才跑)读到空 state 而放行——即这两条清空路径能绕过冲突检测。--force-shared 跳过。
    if not args.force_shared:
        prior_skill = (read_json(project_root / "project_state.json", {}).get("skill") or "").strip()
        if prior_skill and prior_skill != "revise-sci":
            sys.exit(
                f"PROJECT_ROOT 冲突:此目录已被 {prior_skill} 使用(project_state.json 的 skill={prior_skill})。"
                f"revise-sci 与它同目录会互相覆盖 state/units;请另指空 --project-root，或确知安全时加 --force-shared 跳过。"
            )

    if args.force_rebuild:
        project_root.mkdir(parents=True, exist_ok=True)
        clear_project_outputs(project_root)

    if args.resume:
        state = read_json(project_root / "project_state.json", {})
        previous_skill_signature = state.get("skill_signature", "")
        if previous_skill_signature and previous_skill_signature != skill_signature:
            print("resume skill version changed", file=sys.stderr)
            raise SystemExit(1)
        changed_inputs = resume_inputs_changed(project_root, args)
        if changed_inputs:
            if not args.resume_keep_unaffected:
                print(f"resume inputs changed: {', '.join(changed_inputs)}", file=sys.stderr)
                print(
                    "加 --resume-keep-unaffected 可检测这些改动是否触及任何已定位的 comment unit;"
                    "若都无关则保留全部 curated units 续跑,否则会列出受影响的 units。",
                    file=sys.stderr,
                )
                raise SystemExit(1)
            non_content = sorted(set(changed_inputs) - KEEP_UNAFFECTED_CONTENT_KEYS)
            if non_content:
                print(
                    f"--resume-keep-unaffected 无法处理这些改动: {', '.join(non_content)}"
                    "(涉及排版/行为/文献等全局输入,无法按 unit 局部化),请全量重建(--force-rebuild)。",
                    file=sys.stderr,
                )
                raise SystemExit(1)
            affected = compute_affected_units(project_root, args, py, script_dir)
            if affected is None:
                print(
                    "--resume-keep-unaffected: 无法对新输入重新原子化以判定影响范围,"
                    "保守起见拒绝续跑,请检查输入或全量重建(--force-rebuild)。",
                    file=sys.stderr,
                )
                raise SystemExit(1)
            if affected:
                print(f"resume inputs changed: {', '.join(changed_inputs)}", file=sys.stderr)
                print(
                    f"--resume-keep-unaffected: 有 {len(affected)} 个 comment unit 受本次改动影响,"
                    "无法只保留无关 units 而单独重生成它们(curation 与原子化耦合)。受影响 units:",
                    file=sys.stderr,
                )
                for cid in affected:
                    print(f"  - {cid}", file=sys.stderr)
                print(
                    "请对以上 units 重新 curation 后全量重建(--force-rebuild),或用未改动的输入续跑。",
                    file=sys.stderr,
                )
                raise SystemExit(1)
            print(
                "--resume-keep-unaffected: 本次输入改动未触及任何已定位的 comment unit;"
                "保留全部 curated units,更新输入指纹后续跑。",
                file=sys.stderr,
            )
            refresh_stored_signatures(project_root, args)
        if args.resume_from:
            clear_outputs_from_step(project_root, output_md_path, output_docx_path, args.resume_from)

    common_args = [
        "--comments",
        args.comments,
        "--manuscript",
        args.manuscript,
        "--project-root",
        args.project_root,
        "--output-md",
        args.output_md,
        "--output-docx",
        args.output_docx,
        "--journal-style",
        args.journal_style,
        "--reference-search-decision",
        args.reference_search_decision,
        "--context-token-budget",
        str(args.context_token_budget),
        "--context-tail-lines",
        str(args.context_tail_lines),
    ]
    if args.expected_comments_mode:
        common_args.extend(["--expected-comments-mode", args.expected_comments_mode])
    if args.si:
        common_args.extend(["--si", args.si])
    if args.attachments_dir:
        common_args.extend(["--attachments-dir", args.attachments_dir])
    if args.reference_docx:
        common_args.extend(["--reference-docx", args.reference_docx])
    if args.paper_search_results:
        common_args.extend(["--paper-search-results", args.paper_search_results])
    if args.auto_run_reference_search:
        common_args.append("--auto-run-reference-search")
    if args.paper_search_runner:
        common_args.extend(["--paper-search-runner", args.paper_search_runner])
    if args.revision_polish_runner:
        common_args.extend(["--revision-polish-runner", args.revision_polish_runner])
    if args.opencode_driver_command:
        common_args.extend(["--opencode-driver-command", args.opencode_driver_command])
    if resolved_references_source:
        common_args.extend(["--references-source", resolved_references_source])
    if args.live_citation_verify or (args.paper_search_results and not args.offline_citation_verify):
        common_args.append("--live-citation-verify")

    search_results_path = effective_paper_search_results_path(args, project_root)

    if not args.resume or not (project_root / "precheck_report.md").exists():
        preflight_args = common_args + (["--force-shared"] if args.force_shared else [])
        run_step([py, str(script_dir / "preflight.py")] + preflight_args)
    search_results_path = effective_paper_search_results_path(args, project_root)
    if search_results_path and (not args.resume or not has_citation_guard_outputs(project_root)):
        guard_args = [
            py,
            str(script_dir / "citation_guard.py"),
            "--paper-search-results",
            str(search_results_path),
            "--project-root",
            args.project_root,
            "--allow-unverified",
        ]
        if args.offline_citation_verify:
            guard_args.append("--offline")
        else:
            guard_args.append("--live")
        run_step(guard_args)
    if not args.resume or not has_units(project_root):
        run_step([py, str(script_dir / "atomize_comments.py"), "--comments", args.comments, "--project-root", args.project_root])
    if not args.resume or not has_manuscript_sections(project_root):
        atomize_doc_args = [py, str(script_dir / "atomize_manuscript.py"), "--manuscript", args.manuscript, "--project-root", args.project_root]
        if args.si:
            atomize_doc_args.extend(["--si", args.si])
        run_step(atomize_doc_args)
    # 反向抽取图/参考交叉索引(figure_index/reference_index/manuscript_index.md),辅助产物,失败不阻断主流程
    try:
        subprocess.run(
            [py, str(script_dir / "manuscript_index.py"), "--manuscript", args.manuscript, "--project-root", args.project_root],
            text=True, capture_output=True, timeout=180,
        )
    except Exception:
        pass
    # 抠出 docx 内嵌图到 figures/,供最终 docx 嵌回。best-effort,失败/无图都不阻断
    try:
        subprocess.run(
            [py, str(script_dir / "extract_docx_images.py"), "--manuscript", args.manuscript, "--project-root", args.project_root],
            text=True, capture_output=True, timeout=120,
        )
    except Exception:
        pass
    if not args.resume or not has_issue_index(project_root):
        run_step([py, str(script_dir / "build_issue_matrix.py"), "--project-root", args.project_root])
    if not args.resume or not has_state_outputs(project_root):
        run_step([py, str(script_dir / "state_manager.py"), "--project-root", args.project_root, "refresh"])
    if not args.resume or not has_revision_outputs(project_root):
        revise_args = [py, str(script_dir / "revise_units.py"), "--project-root", args.project_root]
        if search_results_path:
            revise_args.extend(["--paper-search-results", str(project_root / "paper_search_validated.json")])
        run_step(revise_args)
        run_step([py, str(script_dir / "build_issue_matrix.py"), "--project-root", args.project_root])
    elif args.resume:
        run_step([py, str(script_dir / "build_issue_matrix.py"), "--project-root", args.project_root])
    if not args.resume or not has_polish_outputs(project_root):
        polish_args = [py, str(script_dir / "polish_revisions.py"), "--project-root", args.project_root]
        if args.revision_polish_runner:
            polish_args.extend(["--revision-polish-runner", args.revision_polish_runner])
        if args.opencode_driver_command:
            polish_args.extend(["--opencode-driver-command", args.opencode_driver_command])
        run_step(polish_args)
    if not args.resume or not has_literature_outputs(project_root):
        run_step([py, str(script_dir / "build_literature_index.py"), "--project-root", args.project_root])
        run_step(
            [
                py,
                str(script_dir / "matrix_manager.py"),
                "bootstrap",
                "--index",
                str(project_root / "data" / "literature_index.json"),
                "--matrix",
                str(project_root / "data" / "synthesis_matrix.json"),
                "--round",
                "2",
            ]
        )
        run_step(
            [
                py,
                str(script_dir / "matrix_manager.py"),
                "audit",
                "--matrix",
                str(project_root / "data" / "synthesis_matrix.json"),
                "--report",
                str(project_root / "data" / "synthesis_matrix_audit.json"),
            ]
        )
    run_step([py, str(script_dir / "merge_manuscript.py"), "--project-root", args.project_root, "--output-md", args.output_md])
    run_step([py, str(script_dir / "reference_sync.py"), "--project-root", args.project_root, "--output-md", args.output_md])
    if not args.resume or not has_reference_registry_outputs(project_root):
        reference_registry_args = [py, str(script_dir / "build_reference_registry.py"), "--project-root", args.project_root, "--output-md", args.output_md]
        if resolved_references_source:
            reference_registry_args.extend(["--references-source", resolved_references_source])
        reference_registry_args.extend(["--reference-search-decision", args.reference_search_decision])
        run_step(reference_registry_args)

    coverage_report = read_json(project_root / "data" / "reference_coverage_audit.json", {})
    should_auto_run_reference_search = (
        args.reference_search_decision == "approved"
        and args.auto_run_reference_search
        and (bool(coverage_report.get("reference_search_required")) or has_pending_citation_units(project_root))
        and effective_paper_search_results_path(args, project_root) is None
    )
    if should_auto_run_reference_search:
        execute_args = [
            py,
            str(script_dir / "execute_reference_search.py"),
            "--project-root",
            args.project_root,
        ]
        if args.paper_search_runner:
            execute_args.extend(["--paper-search-runner", args.paper_search_runner])
        if args.opencode_driver_command:
            execute_args.extend(["--opencode-driver-command", args.opencode_driver_command])
        run_step(execute_args)
        search_results_path = effective_paper_search_results_path(args, project_root)
        if search_results_path is None:
            print("approved reference search did not produce paper_search_results.json", file=sys.stderr)
            raise SystemExit(1)
        guard_args = [
            py,
            str(script_dir / "citation_guard.py"),
            "--paper-search-results",
            str(search_results_path),
            "--project-root",
            args.project_root,
            "--allow-unverified",
        ]
        if args.offline_citation_verify:
            guard_args.append("--offline")
        else:
            guard_args.append("--live")
        run_step(guard_args)
        revise_args = [py, str(script_dir / "revise_units.py"), "--project-root", args.project_root, "--paper-search-results", str(project_root / "paper_search_validated.json")]
        run_step(revise_args)
        run_step([py, str(script_dir / "build_issue_matrix.py"), "--project-root", args.project_root])
        polish_args = [py, str(script_dir / "polish_revisions.py"), "--project-root", args.project_root]
        if args.revision_polish_runner:
            polish_args.extend(["--revision-polish-runner", args.revision_polish_runner])
        if args.opencode_driver_command:
            polish_args.extend(["--opencode-driver-command", args.opencode_driver_command])
        run_step(polish_args)
        run_step([py, str(script_dir / "build_literature_index.py"), "--project-root", args.project_root])
        run_step(
            [
                py,
                str(script_dir / "matrix_manager.py"),
                "bootstrap",
                "--index",
                str(project_root / "data" / "literature_index.json"),
                "--matrix",
                str(project_root / "data" / "synthesis_matrix.json"),
                "--round",
                "2",
            ]
        )
        run_step(
            [
                py,
                str(script_dir / "matrix_manager.py"),
                "audit",
                "--matrix",
                str(project_root / "data" / "synthesis_matrix.json"),
                "--report",
                str(project_root / "data" / "synthesis_matrix_audit.json"),
            ]
        )
        run_step([py, str(script_dir / "merge_manuscript.py"), "--project-root", args.project_root, "--output-md", args.output_md])
        run_step([py, str(script_dir / "reference_sync.py"), "--project-root", args.project_root, "--output-md", args.output_md])
        reference_registry_args = [
            py,
            str(script_dir / "build_reference_registry.py"),
            "--project-root",
            args.project_root,
            "--output-md",
            args.output_md,
            "--reference-search-decision",
            args.reference_search_decision,
        ]
        if resolved_references_source:
            reference_registry_args.extend(["--references-source", resolved_references_source])
        run_step(reference_registry_args)

    # 改稿合并完成后,对最终 output_md 重跑 manuscript_index,使 abbreviation_index.json
    # 反映改后稿(供 RV-G7 缩略语首展门禁审改后稿而非改前原稿)。辅助产物,失败不阻断主流程,
    # 但须显式 warning 而非静默吞(区别于 line 488 对源稿那次的 try/except pass)。
    try:
        idx_completed = subprocess.run(
            [py, str(script_dir / "manuscript_index.py"), "--manuscript", args.output_md, "--project-root", args.project_root],
            text=True, capture_output=True, timeout=180,
        )
        if idx_completed.returncode != 0:
            print(
                f"[run_pipeline] WARNING: manuscript_index over output_md failed (exit {idx_completed.returncode}); "
                f"abbreviation_index.json may still reflect the pre-revision manuscript. stderr: {idx_completed.stderr.strip()}",
                file=sys.stderr,
            )
    except Exception as exc:
        print(
            f"[run_pipeline] WARNING: manuscript_index over output_md raised {exc!r}; "
            f"abbreviation_index.json may still reflect the pre-revision manuscript.",
            file=sys.stderr,
        )

    export_args = [
        py,
        str(script_dir / "export_docx.py"),
        "--project-root",
        args.project_root,
        "--output-md",
        args.output_md,
        "--output-docx",
        args.output_docx,
    ]
    if args.reference_docx:
        export_args.extend(["--reference-docx", args.reference_docx])
    # 传原始 manuscript docx,使改后稿默认 in-place 保原稿格式(仅 .docx 原稿生效)。
    if args.manuscript and Path(args.manuscript).suffix.lower() == ".docx":
        export_args.extend(["--manuscript-docx", args.manuscript])
    export_args.extend(["--journal-style", args.journal_style])
    if args.allow_rebuild_fallback:
        export_args.append("--allow-rebuild-fallback")
    run_step(export_args)
    run_step([py, str(script_dir / "final_consistency_report.py"), "--project-root", args.project_root])
    run_step([py, str(script_dir / "strict_gate.py"), "--project-root", args.project_root])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
