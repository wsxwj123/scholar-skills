#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import read_json, write_text


def classify_blocking_reason(reason: str) -> str:
    reason = reason or ""
    if "新增实验" in reason or "结果" in reason:
        return "缺实验/结果"
    if "新文献" in reason or "paper-search" in reason:
        return "缺文献/检索确认"
    if "图表" in reason or "补充材料" in reason:
        return "缺图表/补充材料确认"
    if "定位" in reason or "具体段落" in reason:
        return "缺定位"
    if "实质性解释" in reason or "新证据" in reason:
        return "需作者学术判断"
    return "其他待确认"


def main() -> int:
    parser = argparse.ArgumentParser(description="Write final consistency report")
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()

    project_root = Path(args.project_root)
    units = [read_json(path, {}) for path in sorted((project_root / "units").glob("*.json"))]
    state = read_json(project_root / "project_state.json", {})
    reference_coverage = read_json(project_root / "data" / "reference_coverage_audit.json", {})
    search_manifest = read_json(project_root / "reference_search_manifest.json", {})
    search_strategy = read_json(project_root / "reference_search_strategy.json", {})
    search_status = read_json(project_root / "reference_search_status.json", {})
    search_execution = read_json(project_root / "reference_search_execution.json", {})
    polish_execution = read_json(project_root / "revision_polish_execution.json", {})
    section_digests = read_json(project_root / "state" / "section_digests.json", {})
    comment_registry = read_json(project_root / "state" / "comment_registry.json", [])
    write_cycle_reports = sorted((project_root / "state" / "write_cycle_reports").glob("*.json")) if (project_root / "state" / "write_cycle_reports").exists() else []
    inputs = state.get("inputs") or {}
    polished_scope_ok = sum(1 for unit in units if unit.get("polish_scope_respected") is True)
    polished_locked_ok = sum(1 for unit in units if unit.get("polish_locked_context_ok") is True)
    lines = [
        "# Final Consistency Report",
        "",
        f"- delivery_status: `{state.get('delivery_status', 'draft')}`",
        f"- total_comments: `{len(units)}`",
        f"- completed: `{sum(1 for unit in units if unit.get('status') == 'completed')}`",
        f"- needs_author_confirmation: `{sum(1 for unit in units if unit.get('status') == 'needs_author_confirmation')}`",
        f"- comments_input_mode: `{inputs.get('comments_input_mode', 'unknown')}`",
        f"- expected_comments_mode: `{inputs.get('expected_comments_mode') or 'Not provided by user'}`",
        f"- journal_style: `{inputs.get('journal_style', 'journal-manuscript')}`",
        f"- revision_polish_driver_mode: `{polish_execution.get('driver_mode', 'Not executed')}`",
        f"- revision_polish_candidate_count: `{polish_execution.get('candidate_count', 0)}`",
        f"- revision_polish_scope_ok: `{polished_scope_ok}`",
        f"- revision_polish_locked_context_ok: `{polished_locked_ok}`",
        "",
        "| comment_id | severity | status | target_document | source_trace |",
        "|---|---|---|---|---|",
    ]
    for unit in units:
        trace = ", ".join(src.get("provider_family", "unknown") for src in unit.get("evidence_sources", [])) or "unknown"
        lines.append(f"| {unit.get('comment_id','')} | {unit.get('severity','')} | {unit.get('status','')} | {unit.get('target_document','')} | {trace} |")
    if isinstance(reference_coverage, dict) and reference_coverage:
        missing_numbers = ", ".join(str(x) for x in reference_coverage.get("missing_reference_numbers", [])) or "无"
        missing_author_year = ", ".join(reference_coverage.get("missing_author_year_citations", [])) or "无"
        lines.extend(
            [
                "",
                "## Intake And State Windows",
                "",
                f"- context_token_budget: `{(state.get('state_policy') or {}).get('context_token_budget', 'unknown')}`",
                f"- context_tail_lines: `{(state.get('state_policy') or {}).get('context_tail_lines', 'unknown')}`",
                f"- manuscript_section_digests: `{len((section_digests.get('manuscript') or []))}`",
                f"- si_section_digests: `{len((section_digests.get('si') or []))}`",
                f"- comment_registry_entries: `{len(comment_registry)}`",
                f"- comment_window_reports: `{len(write_cycle_reports)}`",
                "",
                "## Reference Coverage",
                "",
                f"- reference_coverage_ok: `{reference_coverage.get('ok', True)}`",
                f"- citation_style: `{reference_coverage.get('citation_style', 'none')}`",
                f"- reference_entries: `{reference_coverage.get('reference_entries', 0)}`",
                f"- cited_numbers_detected: `{len(reference_coverage.get('cited_numbers', []))}`",
                f"- missing_reference_numbers: `{missing_numbers}`",
                f"- author_year_citations_detected: `{len(reference_coverage.get('author_year_citations', []))}`",
                f"- missing_author_year_citations: `{missing_author_year}`",
                f"- reference_search_required: `{reference_coverage.get('reference_search_required', False)}`",
                f"- reference_search_decision: `{reference_coverage.get('reference_search_decision', 'ask')}`",
                f"- reference_search_governance_active: `{(project_root / 'reference_search_manifest.json').exists()}`",
                f"- reference_search_workflow: `{search_manifest.get('workflow') or search_strategy.get('workflow') or 'Not generated'}`",
                f"- reference_search_guard_passed: `{((search_status.get('steps') or {}).get('citation_guard_passed', False))}`",
                f"- reference_search_validated_batch_present: `{((search_status.get('steps') or {}).get('validated_batch_present', False))}`",
                f"- reference_search_execution_mode: `{search_execution.get('driver_mode') or 'Not executed'}`",
                f"- reference_search_manifest: `{str((project_root / 'reference_search_manifest.json').resolve()) if (project_root / 'reference_search_manifest.json').exists() else 'Not generated'}`",
                f"- reference_search_strategy: `{str((project_root / 'reference_search_strategy.json').resolve()) if (project_root / 'reference_search_strategy.json').exists() else 'Not generated'}`",
                f"- reference_search_status: `{str((project_root / 'reference_search_status.json').resolve()) if (project_root / 'reference_search_status.json').exists() else 'Not generated'}`",
                f"- reference_search_rounds: `{str((project_root / 'reference_search_rounds.json').resolve()) if (project_root / 'reference_search_rounds.json').exists() else 'Not generated'}`",
                f"- reference_search_task: `{str((project_root / 'reference_search_task.md').resolve()) if (project_root / 'reference_search_task.md').exists() else 'Not generated'}`",
                f"- reference_search_execution: `{str((project_root / 'reference_search_execution.json').resolve()) if (project_root / 'reference_search_execution.json').exists() else 'Not generated'}`",
            ]
        )
    if state.get("delivery_status") == "author_confirmation_required":
        lines.extend(["", "## Blocking Reasons", "", "- 当前至少一条评论仍需作者确认，故项目状态不是 ready_to_submit。", ""])
        lines.append("| comment_id | blocker_type | reason |")
        lines.append("|---|---|---|")
        for unit in units:
            if unit.get("status") != "needs_author_confirmation":
                continue
            reason = unit.get("author_confirmation_reason", "") or "未提供具体原因。"
            lines.append(f"| {unit.get('comment_id','')} | {classify_blocking_reason(reason)} | {reason} |")
    write_text(project_root / "final_consistency_report.md", "\n".join(lines) + "\n")
    print('{"ok": true}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
