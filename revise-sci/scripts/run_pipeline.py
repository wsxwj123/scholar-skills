#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pipeline_gate as PG
from common import autodiscover_reference_source, compute_tree_signature, directory_signature, normalize_ws, path_signature, read_json, write_json


def _pause(phase: str) -> int:
    """round22 预期人工/独立动作停点：机器可识别状态行 + rc=3。"""
    print(f"PIPELINE_PAUSED phase={phase}")
    return 3


def _reject(error_code: str, message: str, **extra) -> int:
    """非法状态转换/坏参数/坏回执：结构化 JSON 行 + rc=2。"""
    payload = {"error_code": error_code, "message": message}
    payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False))
    print(f"PIPELINE_REJECTED: {message}", file=sys.stderr)
    return 2


def _save_state(project_root: Path, state: dict) -> None:
    PG.atomic_write_json(project_root / "project_state.json", state)

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
    # round22：恢复 *.py/*.md/*.json 全覆盖——DoD 真源(references/*.json)变化也要使旧 receipt 失效
    return compute_tree_signature(script_dir.parent, patterns=("*.py", "*.md", "*.json"))


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


def _opening_steps(args, script_dir: Path, project_root: Path, py: str, common_args: list[str]) -> None:
    """开段：preflight → atomize → issue index → state refresh（按产物缺失补齐）。
    到 inventory 停点为止，绝不触碰 revise_units。"""
    if not (project_root / "precheck_report.md").exists():
        preflight_args = common_args + (["--force-shared"] if args.force_shared else [])
        run_step([py, str(script_dir / "preflight.py")] + preflight_args)
    search_results_path = effective_paper_search_results_path(args, project_root)
    if search_results_path and not has_citation_guard_outputs(project_root):
        guard_args = [py, str(script_dir / "citation_guard.py"), "--paper-search-results",
                      str(search_results_path), "--project-root", args.project_root, "--allow-unverified"]
        guard_args.append("--offline" if args.offline_citation_verify else "--live")
        run_step(guard_args)
    if not has_units(project_root):
        run_step([py, str(script_dir / "atomize_comments.py"), "--comments", args.comments, "--project-root", args.project_root])
    if not has_manuscript_sections(project_root):
        atomize_doc_args = [py, str(script_dir / "atomize_manuscript.py"), "--manuscript", args.manuscript, "--project-root", args.project_root]
        if args.si:
            atomize_doc_args.extend(["--si", args.si])
        run_step(atomize_doc_args)
    for helper in ("manuscript_index.py", "extract_docx_images.py"):  # 辅助产物 best-effort
        try:
            subprocess.run([py, str(script_dir / helper), "--manuscript", args.manuscript,
                            "--project-root", args.project_root],
                           text=True, capture_output=True, timeout=180)
        except Exception:
            pass
    if not has_issue_index(project_root):
        run_step([py, str(script_dir / "build_issue_matrix.py"), "--project-root", args.project_root])
    if not has_state_outputs(project_root):
        run_step([py, str(script_dir / "state_manager.py"), "--project-root", args.project_root, "refresh"])


def _methods_na_reason(args) -> str:
    """综述类型 Methods 轨明确 na；实验稿运行；缺失/非法类型保守运行（返回空串=运行）。"""
    style = getattr(args, "journal_style", "") or "journal-manuscript"
    if style in PG.REVIEW_JOURNAL_STYLES:
        return (f"review article (journal_style={style}): Methods 方法学漏写轨 not applicable，"
                "因为综述稿无实验方法学章节可核")
    return ""


def _revision_and_anchor_steps(args, script_dir: Path, project_root: Path, py: str,
                               resolved_references_source: str) -> None:
    """策略齐备后的改稿与交付段：revise → polish → literature → merge/export →
    final consistency → 三条确定性锚（numeric → xref → Methods）。"""
    search_results_path = effective_paper_search_results_path(args, project_root)
    revise_args = [py, str(script_dir / "revise_units.py"), "--project-root", args.project_root]
    if search_results_path:
        revise_args.extend(["--paper-search-results", str(project_root / "paper_search_validated.json")])
    run_step(revise_args)
    run_step([py, str(script_dir / "build_issue_matrix.py"), "--project-root", args.project_root])
    polish_args = [py, str(script_dir / "polish_revisions.py"), "--project-root", args.project_root]
    if args.revision_polish_runner:
        polish_args.extend(["--revision-polish-runner", args.revision_polish_runner])
    if args.opencode_driver_command:
        polish_args.extend(["--opencode-driver-command", args.opencode_driver_command])
    run_step(polish_args)
    if not has_literature_outputs(project_root):
        run_step([py, str(script_dir / "build_literature_index.py"), "--project-root", args.project_root])
        run_step([py, str(script_dir / "matrix_manager.py"), "bootstrap",
                  "--index", str(project_root / "data" / "literature_index.json"),
                  "--matrix", str(project_root / "data" / "synthesis_matrix.json"), "--round", "2"])
        run_step([py, str(script_dir / "matrix_manager.py"), "audit",
                  "--matrix", str(project_root / "data" / "synthesis_matrix.json"),
                  "--report", str(project_root / "data" / "synthesis_matrix_audit.json")])
    run_step([py, str(script_dir / "merge_manuscript.py"), "--project-root", args.project_root, "--output-md", args.output_md])
    run_step([py, str(script_dir / "reference_sync.py"), "--project-root", args.project_root, "--output-md", args.output_md])
    if not has_reference_registry_outputs(project_root):
        reference_registry_args = [py, str(script_dir / "build_reference_registry.py"),
                                   "--project-root", args.project_root, "--output-md", args.output_md]
        if resolved_references_source:
            reference_registry_args.extend(["--references-source", resolved_references_source])
        reference_registry_args.extend(["--reference-search-decision", args.reference_search_decision])
        run_step(reference_registry_args)
    export_args = [py, str(script_dir / "export_docx.py"), "--project-root", args.project_root,
                   "--output-md", args.output_md, "--output-docx", args.output_docx]
    if args.reference_docx:
        export_args.extend(["--reference-docx", args.reference_docx])
    if args.manuscript and Path(args.manuscript).suffix.lower() == ".docx":
        export_args.extend(["--manuscript-docx", args.manuscript])
    export_args.extend(["--journal-style", args.journal_style])
    if args.allow_rebuild_fallback:
        export_args.append("--allow-rebuild-fallback")
    run_step(export_args)
    # 固定顺序确定性锚：final consistency → numeric → xref(outline) → Methods
    run_step([py, str(script_dir / "final_consistency_report.py"), "--project-root", args.project_root])
    anchor_manuscript = args.output_docx if Path(args.output_docx).exists() else args.output_md
    run_step([py, str(script_dir / "numeric_candidates.py"), "--manuscript", anchor_manuscript,
              "--project-root", args.project_root])
    run_step([py, str(script_dir / "structure_outline.py"), "--manuscript", anchor_manuscript,
              "--project-root", args.project_root])
    if not _methods_na_reason(args):
        run_step([py, str(script_dir / "methods_terms.py"), "--manuscript", anchor_manuscript,
                  "--project-root", args.project_root])


def _print_inventory_summary(inventory: dict) -> None:
    print(f"COMMENT_INVENTORY: {len(inventory.get('items', []))} 条意见，确认命令：")
    for item in inventory.get("items", []):
        print(f"  - {item['comment_id']} [{item['reviewer']}] {item['comment_text'][:30]}")
    print(f"  --resume --confirm-comment-inventory {inventory['inventory_sha256']}")


def _install_fresh_gate(args, project_root: Path, epoch: int) -> int:
    """opening 完成后：生成 inventory、落 pipeline_gate、停在 inventory 确认点。"""
    state = read_json(project_root / "project_state.json", {}) or {}
    inventory = PG.build_inventory(project_root, Path(args.comments), epoch)
    PG.atomic_write_json(PG.inventory_path(project_root), inventory)
    gate = PG.new_gate(epoch=epoch)
    gate["inventory_sha256"] = inventory["inventory_sha256"]
    state["pipeline_gate"] = gate
    _save_state(project_root, state)
    _print_inventory_summary(inventory)
    return _pause("awaiting_comment_confirmation")


def _migrate_round22(args, project_root: Path, state: dict, skill_signature: str) -> int:
    """显式迁移：在普通 skill-signature 比较之前处理。只保留产物、绝不推断
    历史确认/复核；一律落回第一个未证明的人为闸口（inventory 确认）。"""
    old_signature = str(state.get("skill_signature", ""))
    if state.get("skill") != "revise-sci" or old_signature not in PG.LEGACY_SIGNATURE_ALLOWLIST:
        return _reject(
            "migration_signature_not_allowlisted",
            "迁移只接受 skill=revise-sci 且旧 skill signature 精确命中 pre-round22 发布版 allowlist；"
            "未知旧版请显式 rebuild（--force-rebuild），不会自动删旧产物",
            skill_signature=old_signature)
    changed = resume_inputs_changed(project_root, args)
    if changed:
        return _reject(
            "migration_input_identity_changed",
            f"迁移要求输入指纹与旧项目一致；已变化: {', '.join(changed)}。请显式 rebuild（--force-rebuild）",
            changed_inputs=changed)
    inventory = PG.build_inventory(project_root, Path(args.comments), 1)
    PG.atomic_write_json(PG.inventory_path(project_root), inventory)
    gate = PG.new_gate(epoch=1)
    gate["inventory_sha256"] = inventory["inventory_sha256"]
    gate["migrated_from"] = {
        "legacy_skill_signature": old_signature,
        "migrated_at": datetime.now(timezone.utc).isoformat(),
    }
    state["legacy_skill_signature"] = old_signature
    state["skill_signature"] = skill_signature
    state["pipeline_gate"] = gate
    _save_state(project_root, state)
    print("MIGRATED: pre-round22 项目已迁移到 pipeline_gate schema v1；既有产物保留，"
          "不推断任何历史确认/独立复核，回到意见 inventory 确认点。")
    _print_inventory_summary(inventory)
    return _pause("awaiting_comment_confirmation")


def _checklist_path(script_dir: Path) -> Path:
    return script_dir.parent / "references" / "dod_checklist.json"


def _enter_detection(args, script_dir: Path, project_root: Path, py: str,
                     state: dict, gate: dict, rerun_anchors_only: bool,
                     resolved_references_source: str) -> int:
    """（重）进入 detection：跑确定性锚 → 绑定 delivery/audit manifest → 任务包 → 停点。"""
    if rerun_anchors_only:
        run_step([py, str(script_dir / "final_consistency_report.py"), "--project-root", args.project_root])
        anchor = args.output_docx if Path(args.output_docx).exists() else args.output_md
        run_step([py, str(script_dir / "numeric_candidates.py"), "--manuscript", anchor, "--project-root", args.project_root])
        run_step([py, str(script_dir / "structure_outline.py"), "--manuscript", anchor, "--project-root", args.project_root])
        if not _methods_na_reason(args):
            run_step([py, str(script_dir / "methods_terms.py"), "--manuscript", anchor, "--project-root", args.project_root])
    else:
        _revision_and_anchor_steps(args, script_dir, project_root, py, resolved_references_source)
    state = read_json(project_root / "project_state.json", {}) or state
    state["pipeline_gate"] = gate
    delivery = PG.delivery_manifest_sha(project_root, state)
    gate["delivery_manifest_sha256"] = delivery
    gate["audit_manifest_sha256"] = PG.audit_manifest_sha(project_root, delivery)
    gate["dod_manifest_sha256"] = None
    gate["phase"] = "awaiting_audit_detection"
    task = PG.write_detection_task(project_root, gate, _methods_na_reason(args))
    _save_state(project_root, state)
    print(f"DETECTION_TASK: audit/detection_task.json task_manifest_sha256={task['task_manifest_sha256']}")
    if _methods_na_reason(args):
        print(f"METHODS_TRACK: na reason={_methods_na_reason(args)}")
    return _pause("awaiting_audit_detection")


def _restart_detection(args, script_dir: Path, project_root: Path, py: str,
                       state: dict, gate: dict, resolved_references_source: str,
                       note: str) -> int:
    """内容/裁决处置后开启新 epoch，旧 receipt 因 epoch 不匹配全部逻辑失效。"""
    new_epoch = int(gate["epoch"]) + 1
    inventory = PG.build_inventory(project_root, Path(args.comments), new_epoch)
    PG.atomic_write_json(PG.inventory_path(project_root), inventory)
    strategies, _problems = PG.collect_strategies(project_root)
    fresh = PG.new_gate(epoch=new_epoch)
    fresh["migrated_from"] = gate.get("migrated_from")
    fresh["inventory_sha256"] = inventory["inventory_sha256"]
    fresh["revision_input_sha256"] = PG.revision_input_sha(inventory["inventory_sha256"], strategies)
    state["pipeline_gate"] = fresh
    print(f"EPOCH_ADVANCED: {note}（epoch {gate['epoch']} → {new_epoch}，下游 receipt 逻辑失效）")
    return _enter_detection(args, script_dir, project_root, py, state, fresh,
                            rerun_anchors_only=True,
                            resolved_references_source=resolved_references_source)


def _enter_dod(args, script_dir: Path, project_root: Path, py: str,
               state: dict, gate: dict) -> int:
    """独立 DoD 阶段：先 preclose 机械预检（不依赖 closure receipt），再发独立任务包。"""
    run_step([py, str(script_dir / "strict_gate.py"), "--project-root", args.project_root, "--preclose"])
    state = read_json(project_root / "project_state.json", {}) or state
    state["pipeline_gate"] = gate
    checklist = _checklist_path(script_dir)
    gate["dod_manifest_sha256"] = PG.dod_manifest_sha(project_root, state, checklist)
    gate["phase"] = "awaiting_dod_review"
    task = PG.write_dod_task(project_root, gate, checklist)
    _save_state(project_root, state)
    print(f"DOD_TASK: audit/revision-dod_task.json task_manifest_sha256={task['task_manifest_sha256']}")
    print("独立 DoD 盲检返回请写 .review_return_revision-dod.json（round22 envelope，回传 task hash）")
    return _pause("awaiting_dod_review")


def _handle_adjudication(args, script_dir: Path, project_root: Path, py: str,
                         resolved_references_source: str, state: dict, gate: dict) -> int:
    audited = args.confirm_audit_adjudication
    if audited != gate.get("audit_manifest_sha256"):
        return _reject("adjudication_manifest_mismatch",
                       "被审 audit manifest 摘要与当前不符（旧裁决不得盖新章）")
    adjudication = read_json(project_root / "audit" / "adjudication.json", None)
    if not isinstance(adjudication, dict) or not isinstance(adjudication.get("decisions"), list):
        return _reject("adjudication_missing", "audit/adjudication.json 缺失/坏 schema")
    if adjudication.get("epoch") != gate["epoch"] or \
            adjudication.get("audited_audit_manifest_sha256") != audited:
        return _reject("adjudication_binding_mismatch", "adjudication 的 epoch/被审 manifest 绑定不符")
    receipt = read_json(project_root / PG.RECEIPTS_DIR / "audit_reverse.json", None)
    if not isinstance(receipt, dict) or receipt.get("epoch") != gate["epoch"]:
        return _reject("audit_reverse_receipt_missing", "audit_reverse receipt 缺失或 epoch 不符")
    confirmed_ids = {
        row["finding_id"]
        for track in (receipt.get("tracks") or {}).values() if isinstance(track, dict)
        for row in (track.get("findings") or []) if row.get("result") == "confirmed"
    }
    decided: set[str] = set()
    has_fix = False
    for decision in adjudication["decisions"]:
        if not isinstance(decision, dict):
            return _reject("adjudication_bad_decision", "decision 必须是对象")
        fid = decision.get("finding_id")
        action = decision.get("action")
        if fid not in confirmed_ids:
            return _reject("adjudication_unknown_finding",
                           f"decision 引用了非本轮 confirmed finding id: {fid!r}（ID 由 pipeline 生成，须逐字对应）")
        if fid in decided:
            return _reject("adjudication_duplicate_finding", f"finding {fid} 重复裁决")
        decided.add(fid)
        if action == "fix":
            has_fix = True
        elif action == "accept_with_rationale":
            if not normalize_ws(str(decision.get("rationale", ""))):
                return _reject("adjudication_empty_rationale",
                               f"finding {fid}: accept_with_rationale 的 rationale 不得为空")
        else:
            return _reject("adjudication_bad_action", f"finding {fid}: action 非法 {action!r}")
    missing = confirmed_ids - decided
    if missing:
        return _reject("adjudication_incomplete", f"confirmed finding 未逐条裁决: {sorted(missing)}")
    state_now = read_json(project_root / "project_state.json", {}) or state
    state_now["pipeline_gate"] = gate
    delivery_now = PG.delivery_manifest_sha(project_root, state_now)
    if has_fix:
        if delivery_now == gate.get("delivery_manifest_sha256"):
            return _reject("fix_without_delivery_change",
                           "action=fix 要求当前交付物已实际修改；delivery manifest 未变化")
        return _restart_detection(args, script_dir, project_root, py, state_now, gate,
                                  resolved_references_source, "adjudication fix 处置")
    if PG.audit_manifest_sha(project_root, delivery_now) != audited:
        return _reject("accept_manifest_drifted",
                       "accept_with_rationale 要求当前 manifest 仍等于被审 manifest；已漂移，须重新检测")
    print("ADJUDICATION_ACCEPTED: 全部 confirmed finding 已带理由接受，进入独立 DoD。")
    return _enter_dod(args, script_dir, project_root, py, state_now, gate)


def _handle_dod_review(args, script_dir: Path, project_root: Path, py: str,
                       state: dict, gate: dict) -> int:
    task = read_json(project_root / "audit" / "revision-dod_task.json", None)
    if not isinstance(task, dict) or "task_manifest_sha256" not in task:
        return _reject("dod_task_missing", "audit/revision-dod_task.json 缺失/损坏")
    if task.get("epoch") != gate["epoch"] or task.get("dod_manifest_sha256") != gate["dod_manifest_sha256"]:
        return _reject("dod_task_stale", "DoD 任务包与当前 epoch/dod manifest 不符")
    return_path = project_root / ".review_return_revision-dod.json"
    if not return_path.is_file():
        return _reject("dod_return_missing",
                       "独立 DoD 返回缺失：.review_return_revision-dod.json（round22 envelope）")
    verify = subprocess.run(
        [py, str(script_dir / "delegate_review.py"), "verify",
         "--checklist", str(_checklist_path(script_dir)), "--gate", "revision-dod",
         "--return", str(return_path), "--workdir", args.project_root,
         "--expect-task-manifest", task["task_manifest_sha256"]],
        text=True, capture_output=True, encoding="utf-8", errors="replace")
    if verify.stdout:
        print(verify.stdout.strip())
    if verify.returncode != 0:
        return _reject("dod_verify_failed",
                       f"独立 DoD verify 未通过（task hash 不符/坏回执/裁决问题），exit={verify.returncode}",
                       stderr=verify.stderr.strip()[-500:])
    receipt = {
        "schema_version": PG.SCHEMA_VERSION,
        "epoch": gate["epoch"],
        "dod_manifest_sha256": gate["dod_manifest_sha256"],
        "checklist_sha256": task["checklist_sha256"],
        "task_manifest_sha256": task["task_manifest_sha256"],
        "review_return_sha256": PG.file_sha(return_path),
    }
    PG.atomic_write_json(project_root / PG.RECEIPTS_DIR / "revision_dod.json", receipt)
    envelope = read_json(return_path, {}) or {}
    print("DOD_VERDICTS（意见 × 回复 × 改稿 × 结局，逐项独立裁决）:")
    for row in envelope.get("review", []):
        if isinstance(row, dict):
            print(f"  - {row.get('id')}: {row.get('verdict')} | {normalize_ws(str(row.get('evidence', '')))[:60]}")
    gate["phase"] = "awaiting_dod_user_confirmation"
    _save_state(project_root, state)
    print(f"确认收口命令：--resume --confirm-dod-closure {gate['dod_manifest_sha256']}")
    return _pause("awaiting_dod_user_confirmation")


def _handle_closure(args, script_dir: Path, project_root: Path, py: str,
                    resolved_references_source: str, state: dict, gate: dict) -> int:
    checklist = _checklist_path(script_dir)
    current = PG.dod_manifest_sha(project_root, state, checklist)
    if current != gate.get("dod_manifest_sha256"):
        return _restart_detection(args, script_dir, project_root, py, state, gate,
                                  resolved_references_source, "final 前 dod manifest 变化")
    if args.confirm_dod_closure != gate["dod_manifest_sha256"]:
        return _reject("closure_sha_mismatch",
                       "确认摘要与当前 dod_manifest_sha256 不符（摘要过期/错配）")
    receipt_path = project_root / PG.RECEIPTS_DIR / "revision_dod.json"
    receipt = read_json(receipt_path, None)
    if not isinstance(receipt, dict) or receipt.get("epoch") != gate["epoch"] \
            or receipt.get("dod_manifest_sha256") != gate["dod_manifest_sha256"]:
        return _reject("dod_receipt_invalid", "revision_dod receipt 缺失或绑定不符，须先通过独立 DoD verify")
    closure = {
        "schema_version": PG.SCHEMA_VERSION,
        "epoch": gate["epoch"],
        "dod_manifest_sha256": gate["dod_manifest_sha256"],
        "dod_receipt_sha256": PG.file_sha(receipt_path),
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    }
    PG.atomic_write_json(project_root / PG.RECEIPTS_DIR / "dod_closure.json", closure)
    gate["phase"] = "complete"
    _save_state(project_root, state)
    print("DOD_CLOSURE_CONFIRMED: 用户已收口，运行最终 bare strict gate。")
    run_step([py, str(script_dir / "strict_gate.py"), "--project-root", args.project_root])
    print("PIPELINE_COMPLETE")
    return 0


def _handle_detection_returns(args, script_dir: Path, project_root: Path, py: str,
                              resolved_references_source: str, state: dict, gate: dict) -> int:
    task = read_json(project_root / "audit" / "detection_task.json", None)
    if not isinstance(task, dict) or "task_manifest_sha256" not in task:
        return _reject("detection_task_missing", "audit/detection_task.json 缺失/损坏，无法校验检测返回")
    findings, errors = PG.validate_detection_returns(project_root, task, gate)
    if errors:
        return _reject("detection_returns_invalid",
                       "detection 三轨返回未通过校验（缺轨/坏 schema/task hash 不符/空证据）: " + "; ".join(errors))
    real = {track: rows for track, rows in findings.items() if rows}
    if not real:
        print("DETECTION_CLEAN: 三轨均无 finding，直接进入独立 DoD（不制造空 reverse 任务）。")
        return _enter_dod(args, script_dir, project_root, py, state, gate)
    tasks = PG.write_reverse_tasks(project_root, gate, real)
    for track, task_payload in tasks.items():
        print(f"REVERSE_TASK: {track}-verify checklist={track}_verify_checklist.json "
              f"task_manifest_sha256={task_payload['task_manifest_sha256']}")
        print(f"  返回写 .review_return_{track}-verify.json（envelope 回传 task hash；"
              "pass=confirmed / fail|na=refuted / problems=未核）")
    gate["phase"] = "awaiting_audit_reverse_verification"
    _save_state(project_root, state)
    return _pause("awaiting_audit_reverse_verification")


def _handle_reverse_returns(args, script_dir: Path, project_root: Path, py: str,
                            state: dict, gate: dict) -> int:
    tracks: dict[str, dict] = {}
    all_results: dict[str, list] = {}
    errors: list[str] = []
    for track in PG.AUDIT_TRACKS:
        task = PG.read_reverse_task(project_root, track)
        if task is None:
            tracks[track] = {"status": "no_findings"}
            continue
        if task.get("epoch") != gate["epoch"] or task.get("audit_manifest_sha256") != gate["audit_manifest_sha256"]:
            errors.append(f"{track}-verify 任务包与当前 epoch/audit manifest 不符（stale task）")
            continue
        results, track_errors = PG.interpret_reverse_return(project_root, track, task)
        if track_errors:
            errors.extend(track_errors)
            continue
        all_results[track] = results
        tracks[track] = {
            "status": "verified",
            "task_manifest_sha256": task["task_manifest_sha256"],
            "checklist_sha256": task["checklist_sha256"],
            "review_return_sha256": PG.file_sha(project_root / f".review_return_{track}-verify.json"),
            "findings": results,
        }
    if errors:
        return _reject("reverse_returns_invalid",
                       "反向验证返回未通过校验（problems 即未核，fail-closed）: " + "; ".join(errors))
    receipt = {
        "schema_version": PG.SCHEMA_VERSION,
        "epoch": gate["epoch"],
        "audit_manifest_sha256": gate["audit_manifest_sha256"],
        "tracks": tracks,
    }
    PG.atomic_write_json(project_root / PG.RECEIPTS_DIR / "audit_reverse.json", receipt)
    confirmed = [row for rows in all_results.values() for row in rows if row["result"] == "confirmed"]
    for track, rows in all_results.items():
        for row in rows:
            print(f"REVERSE_VERDICT: {row['finding_id']} verdict={row['verdict']} -> {row['result']}")
    if confirmed:
        print("确认属实的 finding 需要用户逐条裁决：写 audit/adjudication.json"
              "（action=fix|accept_with_rationale）后 --resume --confirm-audit-adjudication <audit_manifest_sha256>")
        gate["phase"] = "awaiting_audit_adjudication"
        _save_state(project_root, state)
        return _pause("awaiting_audit_adjudication")
    print("REVERSE_CLEAN: 全部 finding 被反向验证剔除（refuted），进入独立 DoD。")
    return _enter_dod(args, script_dir, project_root, py, state, gate)


def _dispatch_gate(args, script_dir: Path, project_root: Path, py: str,
                   resolved_references_source: str, state: dict, gate: dict) -> int:
    phase = gate["phase"]
    comments_path = Path(args.comments)

    # ---- 通用前置：上游内容变化使旧确认失效（内容摘要绑定，不认路径/mtime）----
    inventory = read_json(PG.inventory_path(project_root), None)
    current_comments_sha = PG.file_sha(comments_path)
    if not isinstance(inventory, dict) or inventory.get("comments_source_sha256") != current_comments_sha:
        fresh_epoch = int(gate["epoch"]) + 1
        inventory = PG.build_inventory(project_root, comments_path, fresh_epoch)
        PG.atomic_write_json(PG.inventory_path(project_root), inventory)
        new_gate = PG.new_gate(epoch=fresh_epoch)
        new_gate["migrated_from"] = gate.get("migrated_from")
        new_gate["inventory_sha256"] = inventory["inventory_sha256"]
        state["pipeline_gate"] = new_gate
        _save_state(project_root, state)
        print("INPUT_CHANGED: 审稿信内容已变化，旧 inventory 确认失效（epoch+1），请重新确认。")
        _print_inventory_summary(inventory)
        return _pause("awaiting_comment_confirmation")
    if inventory.get("inventory_sha256") != gate.get("inventory_sha256"):
        inventory = PG.build_inventory(project_root, comments_path, int(gate["epoch"]))
        PG.atomic_write_json(PG.inventory_path(project_root), inventory)
        rebuilt = PG.new_gate(epoch=int(gate["epoch"]))
        rebuilt["migrated_from"] = gate.get("migrated_from")
        rebuilt["inventory_sha256"] = inventory["inventory_sha256"]
        state["pipeline_gate"] = rebuilt
        _save_state(project_root, state)
        print("INVENTORY_CHANGED: 意见 inventory 与已确认摘要不一致，旧确认失效，已按 units 重建，请重新确认。")
        _print_inventory_summary(inventory)
        return _pause("awaiting_comment_confirmation")

    # ---- 用户确认 flag：只在对应 phase 合法 ----
    if args.confirm_comment_inventory:
        if phase != "awaiting_comment_confirmation":
            return _reject("confirm_in_wrong_phase",
                           f"--confirm-comment-inventory 只在 awaiting_comment_confirmation 合法，当前 phase={phase}（非法状态转换）")
        if args.confirm_comment_inventory != inventory["inventory_sha256"]:
            return _reject("inventory_sha_mismatch",
                           "确认摘要与当前 inventory_sha256 不符（内容摘要绑定，摘要过期须重新核对）")
        gate["phase"] = "awaiting_revision_strategies"
        _save_state(project_root, state)
        print("INVENTORY_CONFIRMED: 请为每个 unit 填写 revision_strategy"
              f"（合法闭集 {'/'.join(PG.STRATEGY_CANONICAL)}）后 --resume。")
        return _pause("awaiting_revision_strategies")
    if args.confirm_audit_adjudication:
        if phase != "awaiting_audit_adjudication":
            return _reject("confirm_in_wrong_phase",
                           f"--confirm-audit-adjudication 只在 awaiting_audit_adjudication 合法，当前 phase={phase}（非法状态转换）")
        return _handle_adjudication(args, script_dir, project_root, py, resolved_references_source, state, gate)
    if args.confirm_dod_closure:
        if phase != "awaiting_dod_user_confirmation":
            return _reject("confirm_in_wrong_phase",
                           f"--confirm-dod-closure 只在 awaiting_dod_user_confirmation 合法，当前 phase={phase}（非法状态转换）")
        return _handle_closure(args, script_dir, project_root, py, resolved_references_source, state, gate)

    # ---- 普通 resume 按 phase 自动推进 ----
    if phase == "awaiting_comment_confirmation":
        _print_inventory_summary(inventory)
        return _pause(phase)
    if phase == "awaiting_revision_strategies":
        strategies, problems = PG.collect_strategies(project_root)
        if problems:
            print("REVISION_STRATEGY_GATE: 以下 unit 的 revision_strategy 缺失/非法，不得进入改稿：")
            for problem in problems:
                print(f"  - {problem}")
            return _pause(phase)
        gate["revision_input_sha256"] = PG.revision_input_sha(inventory["inventory_sha256"], strategies)
        _save_state(project_root, state)
        return _enter_detection(args, script_dir, project_root, py, state, gate,
                                rerun_anchors_only=False,
                                resolved_references_source=resolved_references_source)
    # detection 之后的阶段：策略/inventory 摘要变化 → 不得凭旧产物继续
    strategies, strategy_problems = PG.collect_strategies(project_root)
    if not strategy_problems and gate.get("revision_input_sha256") and \
            PG.revision_input_sha(inventory["inventory_sha256"], strategies) != gate["revision_input_sha256"]:
        return _restart_detection(args, script_dir, project_root, py, state, gate,
                                  resolved_references_source, "revision_strategy 变化")
    if phase == "awaiting_audit_detection":
        return _handle_detection_returns(args, script_dir, project_root, py,
                                         resolved_references_source, state, gate)
    if phase == "awaiting_audit_reverse_verification":
        return _handle_reverse_returns(args, script_dir, project_root, py, state, gate)
    if phase == "awaiting_audit_adjudication":
        print("等待用户裁决：写 audit/adjudication.json 后运行 "
              "--resume --confirm-audit-adjudication <audited_audit_manifest_sha256>")
        return _pause(phase)
    if phase == "awaiting_dod_review":
        return _handle_dod_review(args, script_dir, project_root, py, state, gate)
    if phase == "awaiting_dod_user_confirmation":
        print("等待用户收口：--resume --confirm-dod-closure <dod_manifest_sha256>")
        return _pause(phase)
    if phase == "complete":
        run_step([py, str(script_dir / "strict_gate.py"), "--project-root", args.project_root])
        print("PIPELINE_COMPLETE")
        return 0
    return _reject("unknown_phase", f"pipeline_gate.phase 非法: {phase!r}")


def _round22_run(args, script_dir: Path, project_root: Path, py: str,
                 common_args: list[str], resolved_references_source: str,
                 skill_signature: str) -> int:
    state_path = project_root / "project_state.json"
    state = read_json(state_path, {}) or {}
    gate = state.get("pipeline_gate")
    active_confirms = [flag for flag in (
        args.confirm_comment_inventory, args.confirm_audit_adjudication, args.confirm_dod_closure,
    ) if flag]
    if len(active_confirms) > 1:
        return _reject("multiple_confirm_flags", "一次只允许一个确认 flag")

    if args.migrate_round22:
        if not args.resume:
            return _reject("migrate_requires_resume", "--migrate-round22 必须与 --resume 同用")
        if gate is not None:
            return _reject("already_migrated", "项目已有 pipeline_gate，无需迁移")
        if not state:
            return _reject("nothing_to_migrate", "空目录没有可迁移的旧项目 state")
        return _migrate_round22(args, project_root, state, skill_signature)

    if gate is None:
        if state:
            # 旧项目（无 pipeline_gate）：默认 fail-closed，不自动放行、不推断确认。
            if active_confirms:
                return _reject(
                    "confirm_flag_in_legacy_project",
                    "旧项目缺 pipeline_gate，确认 flag 属非法状态转换（phase 不存在）；"
                    "先 --resume --migrate-round22 迁移")
            print("LEGACY PROJECT: 缺 pipeline_gate（pre-round22 项目）。"
                  "非破坏性暂停：既有产物一律保留；请用 --resume --migrate-round22 显式迁移"
                  "（仅接受 allowlist 内旧 signature），或另指新 --project-root 重建。")
            return _pause("legacy_project_requires_migration")
        if active_confirms:
            return _reject(
                "confirm_flag_before_first_run",
                "首跑预传确认 flag 属非法状态转换：当前无 pipeline_gate phase，"
                "先跑一次 pipeline 生成 inventory 停点")
        _opening_steps(args, script_dir, project_root, py, common_args)
        return _install_fresh_gate(args, project_root, epoch=1)

    if not PG.gate_schema_complete(gate):
        return _reject("pipeline_gate_schema_incomplete",
                       "pipeline_gate schema_version=1 字段不完整，fail-closed（删字段不得当 legacy）")
    if str(state.get("skill_signature", "")) != skill_signature:
        return _reject("skill_signature_mismatch",
                       "技能已升级：旧确认/回执不得继续使用，请重新走各人工闸口"
                       "（或确属旧版项目时另指新 root 重建）")
    if args.resume_from:
        old_epoch = int(gate["epoch"])
        clear_outputs_from_step(project_root, Path(args.output_md), Path(args.output_docx), args.resume_from)
        _opening_steps(args, script_dir, project_root, py, common_args)
        return _install_fresh_gate(args, project_root, epoch=old_epoch + 1)
    return _dispatch_gate(args, script_dir, project_root, py, resolved_references_source, state, gate)


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
    parser.add_argument("--resume-keep-unaffected", action="store_true", help="round22 起由 pipeline_gate 状态机接管输入变化处理（epoch+1 使旧确认失效）；本 flag 保留兼容、不再单独生效。")
    parser.add_argument("--confirm-comment-inventory", default="",
                        help="round22 人工闸口：确认意见 inventory（传 inventory_sha256，仅 awaiting_comment_confirmation 合法）")
    parser.add_argument("--confirm-audit-adjudication", default="",
                        help="round22 人工闸口：确认 audit 裁决（传 audited_audit_manifest_sha256，仅 awaiting_audit_adjudication 合法）")
    parser.add_argument("--confirm-dod-closure", default="",
                        help="round22 人工闸口：DoD 收口确认（传 dod_manifest_sha256，仅 awaiting_dod_user_confirmation 合法）")
    parser.add_argument("--migrate-round22", action="store_true",
                        help="pre-round22 旧项目显式迁移（与 --resume 同用；只接受 allowlist 内旧 skill signature）")
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
    # round22：--resume-from 单独可用（状态机自会 epoch+1 使下游证明失效）
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

    # round22 起：输入变化 / skill 升级 / resume-from 一律由 pipeline_gate 状态机
    # 处理（epoch+1 使旧确认与 receipt 逻辑失效），不再依赖本处的前置检查。

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

    # round22：一键 pipeline 全量走状态机（fresh 开段→inventory 停点→策略门→
    # 三层 audit→独立 DoD→用户收口→final bare gate）。各子脚本直接入口不受影响。
    return _round22_run(args, script_dir, project_root, py, common_args,
                        resolved_references_source, skill_signature)


if __name__ == "__main__":
    raise SystemExit(main())
