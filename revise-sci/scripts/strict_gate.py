#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys
try:  # Windows GBK 控制台/管道捕获下 emoji print 防 UnicodeEncodeError
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import argparse
from pathlib import Path

from common import ALLOWED_PROVIDER_FAMILIES, blocked_placeholder_found, hard_ai_style_markers, soft_ai_style_markers, normalize_ws, read_docx_paragraphs, read_json


REQUIRED_RESPONSE_HEADINGS = [
    "# 回复审稿人的邮件",
    "#### 2) Response to Reviewer（中英对照）",
    "#### 5) Evidence Attachments",
]


def missing_atomic_fields(unit: dict) -> list[str]:
    atomic = unit.get("atomic_location") or {}
    if normalize_ws(unit.get("original_excerpt_en")) in {"", "无"}:
        return []
    required = {
        "section_file": atomic.get("section_file"),
        "paragraph_index": atomic.get("paragraph_index"),
        "matched_sentence": atomic.get("matched_sentence"),
    }
    return [key for key, value in required.items() if value in {"", None, "无"}]


def section_label(unit: dict) -> str:
    return "si section" if unit.get("target_document") == "si" else "manuscript section"


def _load_claim_check():
    """Import citation_claim_check. 同目录 vendored 副本优先(scripts/citation_claim_check.py),
    不存在再回退 skills/_shared/citation_claim_check.py。两处都无 → 打一行大字告警并返回 None,
    调用方保持 fail-open(return []),绝不倒卡技能。"""
    import importlib.util
    here = Path(__file__).resolve().parent
    for candidate in (here / "citation_claim_check.py",
                      here.parents[1] / "_shared" / "citation_claim_check.py"):
        if not candidate.is_file():
            continue
        spec = importlib.util.spec_from_file_location("_vendored_citation_claim_check", candidate)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    import sys as _sys
    print("⚠️ citation_claim_check 库缺失，引文核证子检查跳过(fail-open)，请补 vendored 副本"
          "(python3 _shared/sync_vendored.py --sync)。", file=_sys.stderr)
    return None


def _citation_claim_failures(project_root: Path) -> list[str]:
    """B④: 有新引文献自动收口时，必须存在 claim_evidence.json 且承重句核证通过。
    复用共享 citation_claim_check._row_blockers，不重复实现判定逻辑。"""
    ev_path = project_root / "claim_evidence.json"
    if not ev_path.is_file():
        return [
            "completed new-citation comments require claim_evidence.json "
            "(new reference ↔ supported response claim); build it and pass citation_claim_check.py"
        ]
    module = _load_claim_check()
    if module is None:
        return []  # 刻意 fail-open:库缺失时不倒卡技能，交由人工核（与 hook 降级同理），绝不塞 blocker
    try:
        rows = module._load_evidence(ev_path)
    except Exception as exc:
        return [f"claim_evidence.json is unreadable: {exc}"]
    blockers: list[str] = []
    for row in rows:
        blockers.extend(module._row_blockers(row))
    return [f"citation_claim_check: {b}" for b in blockers]


def completed_citation_units(units: list[dict]) -> list[dict]:
    return [
        unit
        for unit in units
        if unit.get("status") == "completed" and unit.get("editorial_intent") == "citation"
    ]


def approved_search_governance_failures(project_root: Path, reference_coverage: dict) -> list[str]:
    failures: list[str] = []
    if not isinstance(reference_coverage, dict) or reference_coverage.get("reference_search_decision") != "approved":
        return failures

    manifest_path = project_root / "reference_search_manifest.json"
    strategy_path = project_root / "reference_search_strategy.json"
    status_path = project_root / "reference_search_status.json"
    rounds_path = project_root / "reference_search_rounds.json"
    task_path = project_root / "reference_search_task.md"
    execution_path = project_root / "reference_search_execution.json"
    paper_results_path = project_root / "paper_search_results.json"
    paper_validated_path = project_root / "paper_search_validated.json"
    guard_report_path = project_root / "paper_search_guard_report.json"
    literature_index_path = project_root / "data" / "literature_index.json"
    synthesis_matrix_path = project_root / "data" / "synthesis_matrix.json"
    synthesis_audit_path = project_root / "data" / "synthesis_matrix_audit.json"
    reference_sync_path = project_root / "reference_sync_report.json"

    for artifact in (manifest_path, task_path, strategy_path, status_path, rounds_path):
        if not artifact.exists():
            failures.append(f"reference search approved but {artifact.name} is missing")
    if failures:
        return failures

    manifest = read_json(manifest_path, {})
    strategy = read_json(strategy_path, {})
    status = read_json(status_path, {})
    rounds = read_json(rounds_path, {})
    guard_report = read_json(guard_report_path, {})
    execution = read_json(execution_path, {})

    if manifest.get("workflow") != "review-writing":
        failures.append("reference_search_manifest.json must declare workflow review-writing")
    if manifest.get("reference_search_decision") != "approved":
        failures.append("reference_search_manifest.json must keep reference_search_decision approved")
    if manifest.get("governance_active") is not True:
        failures.append("reference_search_manifest.json must keep governance_active true")
    if manifest.get("allowed_provider_families") != ["paper-search"]:
        failures.append("reference_search_manifest.json must restrict allowed_provider_families to paper-search")
    if "websearch" not in (manifest.get("forbidden_provider_families") or []):
        failures.append("reference_search_manifest.json must forbid websearch")
    verification_policy = manifest.get("verification_policy") or {}
    if verification_policy.get("dual_verification_required") is not True:
        failures.append("reference_search_manifest.json must require dual verification")
    if verification_policy.get("allow_unverified") is not False:
        failures.append("reference_search_manifest.json must disallow unverified search rows")
    if "citation_guard.py" not in normalize_ws(str(verification_policy.get("guard_command") or "")):
        failures.append("reference_search_manifest.json must include citation_guard.py as mandatory guard command")
    if len((manifest.get("workflow_rules") or {}).get("rounds") or []) != 3:
        failures.append("reference_search_manifest.json must describe exactly three search rounds")

    if strategy.get("workflow") != "review-writing":
        failures.append("reference_search_strategy.json must declare workflow review-writing")
    provider_policy = strategy.get("provider_policy") or {}
    if provider_policy.get("primary") != ["paper-search"]:
        failures.append("reference_search_strategy.json must restrict primary providers to paper-search")
    if "websearch" not in (provider_policy.get("forbidden") or []):
        failures.append("reference_search_strategy.json must forbid websearch")
    if "citation_guard.py" not in normalize_ws(str(strategy.get("mandatory_guard_command") or "")):
        failures.append("reference_search_strategy.json must declare citation_guard.py as mandatory guard command")
    if len(strategy.get("round_model") or []) != 3:
        failures.append("reference_search_strategy.json must declare a three-round model")
    required_outputs = strategy.get("required_outputs") or []
    for required in ("data/literature_index.json", "data/synthesis_matrix.json", "data/synthesis_matrix_audit.json"):
        if required not in required_outputs:
            failures.append(f"reference_search_strategy.json missing required output {required}")

    if rounds.get("workflow") != "review-writing":
        failures.append("reference_search_rounds.json must declare workflow review-writing")
    round_entries = rounds.get("rounds") or []
    if len(round_entries) != 3:
        failures.append("reference_search_rounds.json must describe exactly three rounds")
    else:
        for expected_round, round_entry in enumerate(round_entries, start=1):
            if round_entry.get("round") != expected_round:
                failures.append("reference_search_rounds.json round ordering is invalid")
            if round_entry.get("provider_family") != "paper-search":
                failures.append("reference_search_rounds.json must restrict provider_family to paper-search")
        if not any((round_entry.get("queries") or []) for round_entry in round_entries):
            failures.append("reference_search_rounds.json must include at least one executable search query")

    if status.get("reference_search_decision") != "approved":
        failures.append("reference_search_status.json must keep reference_search_decision approved")
    if status.get("governance_active") is not True:
        failures.append("reference_search_status.json must keep governance_active true")
    steps = status.get("steps") or {}
    if steps.get("search_round_plan_generated") is not rounds_path.exists():
        failures.append("reference_search_status.json step search_round_plan_generated is inconsistent with reference_search_rounds.json")
    if steps.get("paper_search_batch_imported") is not paper_results_path.exists():
        failures.append("reference_search_status.json step paper_search_batch_imported is inconsistent with paper_search_results.json")
    if steps.get("validated_batch_present") is not paper_validated_path.exists():
        failures.append("reference_search_status.json step validated_batch_present is inconsistent with paper_search_validated.json")
    guard_passed = bool((guard_report.get("summary") or {}).get("all_rows_guard_verified", False))
    if steps.get("citation_guard_passed") is not guard_passed:
        failures.append("reference_search_status.json step citation_guard_passed is inconsistent with paper_search_guard_report.json")
    if steps.get("literature_index_built") is not literature_index_path.exists():
        failures.append("reference_search_status.json step literature_index_built is inconsistent with literature_index artifact presence")
    if steps.get("synthesis_matrix_audited") is not synthesis_audit_path.exists():
        failures.append("reference_search_status.json step synthesis_matrix_audited is inconsistent with synthesis_matrix_audit artifact presence")
    if steps.get("reference_sync_completed") is not reference_sync_path.exists():
        failures.append("reference_search_status.json step reference_sync_completed is inconsistent with reference_sync_report.json")

    if paper_results_path.exists():
        if not paper_validated_path.exists():
            failures.append("approved reference search batch is missing paper_search_validated.json")
        if not guard_report_path.exists():
            failures.append("approved reference search batch is missing paper_search_guard_report.json")
        if not guard_passed:
            failures.append("approved reference search batch has not passed citation_guard.py")
        for artifact in (literature_index_path, synthesis_matrix_path, synthesis_audit_path):
            if not artifact.exists():
                failures.append(f"approved reference search batch is missing canonical artifact {artifact.name}")
    if execution_path.exists():
        if execution.get("ok") is not True:
            failures.append("reference_search_execution.json exists but reports ok=false")
        if execution.get("driver_mode") not in {"local-runner", "opencode-driver"}:
            failures.append("reference_search_execution.json has unsupported driver_mode")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Hard gate for revise-sci outputs")
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()

    project_root = Path(args.project_root)
    state = read_json(project_root / "project_state.json", {})
    units = [read_json(path, {}) for path in sorted((project_root / "units").glob("*.json"))]
    failures: list[str] = []
    soft_style_notes: list[str] = []  # C反AI降软：句长/破折号等只上报、不阻断

    response_md = project_root / "response_to_reviewers.md"
    response_text = response_md.read_text(encoding="utf-8") if response_md.exists() else ""
    edit_plan_path = project_root / "manuscript_edit_plan.md"
    edit_plan_text = edit_plan_path.read_text(encoding="utf-8") if edit_plan_path.exists() else ""
    reference_sync_report = read_json(project_root / "reference_sync_report.json", {})
    covered_reference_comments = set(reference_sync_report.get("covered_comment_ids", []))
    literature_index_path = project_root / "data" / "literature_index.json"
    synthesis_matrix_path = project_root / "data" / "synthesis_matrix.json"
    synthesis_audit_path = project_root / "data" / "synthesis_matrix_audit.json"
    reference_registry_path = project_root / "data" / "reference_registry.json"
    reference_coverage_path = project_root / "data" / "reference_coverage_audit.json"
    revision_polish_manifest_path = project_root / "revision_polish_manifest.json"
    revision_polish_execution_path = project_root / "revision_polish_execution.json"
    state_dir = project_root / "state"
    section_digests_path = state_dir / "section_digests.json"
    comment_registry_path = state_dir / "comment_registry.json"
    literature_index = read_json(literature_index_path, [])
    synthesis_matrix = read_json(synthesis_matrix_path, [])
    synthesis_audit = read_json(synthesis_audit_path, {})
    reference_coverage = read_json(reference_coverage_path, {})
    revision_polish_execution = read_json(revision_polish_execution_path, {})
    reference_search_decision = normalize_ws(str((state.get("inputs") or {}).get("reference_search_decision") or "ask"))
    comments_input_mode = normalize_ws(str((state.get("inputs") or {}).get("comments_input_mode") or ""))
    expected_comments_mode = normalize_ws(str((state.get("inputs") or {}).get("expected_comments_mode") or ""))
    journal_style = normalize_ws(str((state.get("inputs") or {}).get("journal_style") or "journal-manuscript"))
    citation_units = completed_citation_units(units)

    if comments_input_mode in {"", "unsupported", "html-unknown"}:
        failures.append("project_state missing a supported comments_input_mode")
    if expected_comments_mode and expected_comments_mode != comments_input_mode:
        failures.append("project_state expected_comments_mode does not match detected comments_input_mode")
    if journal_style not in {"journal-manuscript", "nature-review", "cell-press", "lancet-review"}:
        failures.append("project_state journal_style is missing or unsupported")
    for artifact in (section_digests_path, comment_registry_path):
        if not artifact.exists():
            failures.append(f"missing state artifact: {artifact.name}")

    for artifact in (revision_polish_manifest_path, revision_polish_execution_path):
        if not artifact.exists():
            failures.append(f"missing polish artifact: {artifact.name}")
    if isinstance(revision_polish_execution, dict) and revision_polish_execution.get("ok") is not True:
        failures.append("revision polish execution reports ok=false")

    for artifact in (reference_registry_path, reference_coverage_path):
        if not artifact.exists():
            failures.append(f"missing reference artifact: {artifact.name}")
    if isinstance(reference_coverage, dict) and not reference_coverage.get("ok", True):
        failures.append("reference coverage audit reports unresolved citation coverage gaps")
    # Guard against a vacuous PASS: when the manuscript body carries in-text
    # citations but the reference registry came up empty (or no references
    # section was located), the coverage audit must not be treated as clean.
    # Manuscripts with no in-text citations at all are legitimately exempt.
    if isinstance(reference_coverage, dict):
        has_in_text_citations = bool(reference_coverage.get("cited_numbers")) or bool(reference_coverage.get("author_year_citations"))
        registry_empty = int(reference_coverage.get("reference_entries", 0) or 0) == 0
        references_section_found = bool(reference_coverage.get("references_section_found", False))
        if has_in_text_citations and registry_empty:
            failures.append("manuscript has in-text citations but the reference registry is empty (no reference entries were recognized)")
        elif has_in_text_citations and not references_section_found:
            failures.append("manuscript has in-text citations but no references section was located")
    if any((project_root / name).exists() for name in ("paper_search_results.json", "paper_search_validated.json", "paper_search_guard_report.json")) and reference_search_decision != "approved":
        failures.append("paper-search artifacts exist but reference_search_decision is not approved")
    if isinstance(reference_coverage, dict) and reference_coverage.get("reference_search_required") and reference_coverage.get("reference_search_decision") == "ask":
        failures.append("reference search decision required before searching and filling new references")
    if isinstance(reference_coverage, dict) and reference_coverage.get("reference_search_required") and reference_coverage.get("reference_search_decision") == "approved":
        failures.append("reference search approved but no validated retrieval batch has closed the reference gaps yet")
    failures.extend(approved_search_governance_failures(project_root, reference_coverage))

    if citation_units:
        for artifact in (literature_index_path, synthesis_matrix_path, synthesis_audit_path):
            if not artifact.exists():
                failures.append(f"missing literature artifact: {artifact.name}")
        if isinstance(synthesis_audit, dict):
            if synthesis_audit.get("missing_claim", 0) > 0:
                failures.append("synthesis_matrix_audit reports missing_claim gaps")
            if synthesis_audit.get("missing_key_fields", 0) > 0:
                failures.append("synthesis_matrix_audit reports missing_key_fields gaps")
        # B②：新引文献必须过真实性双验且不许 --offline 跳过交付。
        guard_report = read_json(project_root / "paper_search_guard_report.json", {})
        guard_summary = guard_report.get("summary", {}) if isinstance(guard_report, dict) else {}
        if not guard_summary.get("online_check"):
            failures.append(
                "completed new-citation comments but citation_guard ran offline "
                "(paper_search_guard_report.json summary.online_check!=true); "
                "rerun citation_guard.py --live before delivery（不许 --offline 交付）"
            )
        if not guard_summary.get("all_rows_guard_verified"):
            failures.append("completed new-citation comments but citation_guard reports unverified rows (all_rows_guard_verified!=true)")
        # B④：新引文献 ↔ 它支撑的回复论点，须过 citation_claim_check（承重句 contradict/未确认硬拦）。
        failures.extend(_citation_claim_failures(project_root))

    for unit in units:
        comment_id = unit.get("comment_id", "<unknown>")
        for key in (
            "comment_id",
            "reviewer_comment_en",
            "reviewer_comment_zh_literal",
            "intent_zh",
            "response_en",
            "response_zh",
            "revised_excerpt_en",
            "revised_excerpt_zh",
        ):
            if blocked_placeholder_found(unit.get(key)):
                failures.append(f"{comment_id}: placeholder in {key}")
        if unit.get("severity") == "major" and unit.get("status") not in {"completed", "needs_author_confirmation", "push_back"}:
            failures.append(f"{comment_id}: invalid major status")
        if not unit.get("modification_actions"):
            failures.append(f"{comment_id}: missing modification_actions")
        if not unit.get("notes_core_zh") or not unit.get("notes_support_zh"):
            failures.append(f"{comment_id}: missing notes")
        if not unit.get("evidence_sources"):
            failures.append(f"{comment_id}: missing evidence_sources")
        for source in unit.get("evidence_sources", []):
            if source.get("provider_family") not in ALLOWED_PROVIDER_FAMILIES:
                failures.append(f"{comment_id}: invalid provider family {source.get('provider_family')}")
        revision_plan = unit.get("revision_plan") or {}
        if unit.get("status") == "completed" and revision_plan.get("scope") not in {"", "none", None}:
            if unit.get("polish_applied") is not True:
                failures.append(f"{comment_id}: completed revision is missing revision polishing state")
            if unit.get("polish_driver_mode") in {"", "pending", "not-required", None}:
                failures.append(f"{comment_id}: completed revision is missing a valid polish_driver_mode")
            polished_fragment = normalize_ws(str(revision_plan.get("polished_fragment") or revision_plan.get("raw_fragment") or ""))
            if not polished_fragment:
                failures.append(f"{comment_id}: polished fragment is missing")
            elif hard_ai_style_markers(polished_fragment):
                failures.append(f"{comment_id}: polished fragment still contains banned AI-style markers")
            soft_here = soft_ai_style_markers(polished_fragment)
            if soft_here:
                soft_style_notes.append(f"{comment_id}: {', '.join(soft_here)}")
            if unit.get("polish_guard_ok") is not True:
                failures.append(f"{comment_id}: polish_guard_ok is false")
            if unit.get("polish_scope_respected") is not True:
                failures.append(f"{comment_id}: polish_scope_respected is false")
            if unit.get("polish_meaning_changed") is not False:
                failures.append(f"{comment_id}: polish_meaning_changed must remain false")
            if unit.get("polish_locked_context_ok") is not True:
                failures.append(f"{comment_id}: polish_locked_context_ok is false")
            if unit.get("polish_numbers_ok") is not True:
                failures.append(f"{comment_id}: polish_numbers_ok is false (numeric drift between raw and polished fragment)")
            if unit.get("polish_certainty_ok") is not True:
                failures.append(f"{comment_id}: polish_certainty_ok is false (cautious verb upgraded to a strong claim)")

        atomic_failures = missing_atomic_fields(unit)
        if atomic_failures:
            failures.append(f"{comment_id}: incomplete atomic_location fields: {', '.join(atomic_failures)}")

        required_response_snippets = [
            unit.get("reviewer_comment_en", ""),
            unit.get("response_en", ""),
        ]
        if unit.get("status") == "completed":
            required_response_snippets.append(unit.get("revised_excerpt_en", ""))
        if any(snippet and snippet not in response_text for snippet in required_response_snippets):
            failures.append(f"{comment_id}: missing comment mapping in response_to_reviewers.md")

        if comment_id not in edit_plan_text:
            failures.append(f"{comment_id}: edit plan missing comment_id")
        elif unit.get("status") == "completed" and unit.get("revised_excerpt_en") not in edit_plan_text:
            failures.append(f"{comment_id}: edit plan missing revised excerpt")

        if unit.get("status") == "completed" and unit.get("editorial_intent") == "citation":
            if comment_id not in covered_reference_comments:
                failures.append(f"{comment_id}: completed citation unit missing reference_sync coverage")
            entry = None
            if isinstance(literature_index, list):
                for candidate in literature_index:
                    if comment_id in (candidate.get("comment_ids") or []) or comment_id in (candidate.get("claim_ids") or []):
                        entry = candidate
                        break
            if not entry:
                failures.append(f"{comment_id}: literature_index missing citation mapping")
            elif isinstance(synthesis_matrix, list):
                has_matrix_row = any(
                    row.get("global_id") == entry.get("global_id")
                    and (
                        row.get("claim_id") == comment_id
                        or comment_id in (row.get("comment_ids") or [])
                    )
                    for row in synthesis_matrix
                )
                if not has_matrix_row:
                    failures.append(f"{comment_id}: synthesis_matrix missing citation mapping")

        section_file = (unit.get("atomic_location") or {}).get("section_file", "")
        if unit.get("status") == "completed":
            if not section_file:
                failures.append(f"{comment_id}: missing section_file for completed unit")
            else:
                section_path = project_root / section_file
                if not section_path.exists():
                    failures.append(f"{comment_id}: missing output section file {section_path}")
                else:
                    section_text = section_path.read_text(encoding="utf-8")
                    if unit.get("revised_excerpt_en") not in section_text:
                        failures.append(f"{comment_id}: completed excerpt not found in {section_label(unit)}")

    if len(list((project_root / "comment_records").glob("*.md"))) != len(units):
        failures.append("comment_records count does not match units count")
    for unit in units:
        record_path = project_root / "comment_records" / f"{unit.get('comment_id', '')}.md"
        if not record_path.exists():
            failures.append(f"{unit.get('comment_id', '<unknown>')}: missing comment_record file")
        comment_window_path = state_dir / "comment_windows" / f"{unit.get('comment_id', '')}.json"
        write_cycle_report_path = state_dir / "write_cycle_reports" / f"{unit.get('comment_id', '')}.json"
        if not comment_window_path.exists():
            failures.append(f"{unit.get('comment_id', '<unknown>')}: missing comment_window state artifact")
        if not write_cycle_report_path.exists():
            failures.append(f"{unit.get('comment_id', '<unknown>')}: missing write_cycle_report state artifact")
        else:
            write_cycle_report = read_json(write_cycle_report_path, {})
            if int(write_cycle_report.get("token_budget", 0) or 0) <= 0:
                failures.append(f"{unit.get('comment_id', '<unknown>')}: invalid token budget in write_cycle_report")

    if not response_md.exists():
        failures.append("missing response_to_reviewers.md")
    else:
        for heading in REQUIRED_RESPONSE_HEADINGS:
            if heading not in response_text:
                failures.append(f"response_to_reviewers.md missing heading: {heading}")
        for label in ("**Text**", "**Image**", "**Table**"):
            if response_text.count(label) < len(units):
                failures.append(f"response_to_reviewers.md missing per-comment evidence block: {label}")

    response_docx = project_root / "response_to_reviewers.docx"
    if not response_docx.exists():
        failures.append("missing output: response_to_reviewers.docx")
    else:
        try:
            response_docx_rows = read_docx_paragraphs(response_docx)
        except Exception:
            failures.append("response_to_reviewers.docx is not a readable docx")
        else:
            response_docx_texts = [normalize_ws(row.get("text", "")) for row in response_docx_rows if normalize_ws(row.get("text", ""))]
            if "回复审稿人的邮件" not in response_docx_texts:
                failures.append("response_to_reviewers.docx missing top-level title")
            if sum(1 for text in response_docx_texts if text.startswith("Comment ")) < len(units):
                failures.append("response_to_reviewers.docx missing comment headings")
            if response_docx_texts.count("2) Response to Reviewer（中英对照）") < len(units):
                failures.append("response_to_reviewers.docx missing response section headings")
            if response_docx_texts.count("5) Evidence Attachments") < len(units):
                failures.append("response_to_reviewers.docx missing evidence section headings")

    manuscript_index = read_json(project_root / "manuscript_section_index.json", {"sections": []})
    section_files = {section.get("file") for section in manuscript_index.get("sections", [])}
    for unit in units:
        section_file = (unit.get("atomic_location") or {}).get("section_file")
        if section_file and unit.get("target_document") == "manuscript" and section_file not in section_files:
            failures.append(f"{unit.get('comment_id', '<unknown>')}: atomic section_file not found in manuscript index")

    for required_file in (
        Path(state.get("outputs", {}).get("output_md", project_root / "missing.md")),
        Path(state.get("outputs", {}).get("output_docx", project_root / "missing.docx")),
        edit_plan_path,
        project_root / "reference_sync_report.json",
        reference_registry_path,
        reference_coverage_path,
    ):
        if not required_file.exists():
            failures.append(f"missing output: {required_file}")

    output_docx = Path(state.get("outputs", {}).get("output_docx", project_root / "missing.docx"))
    if output_docx.exists():
        try:
            manuscript_docx_rows = read_docx_paragraphs(output_docx)
        except Exception:
            failures.append("output_docx is not a readable docx")
        else:
            manuscript_texts = [normalize_ws(row.get("text", "")) for row in manuscript_docx_rows if normalize_ws(row.get("text", ""))]
            if not manuscript_texts:
                failures.append("output_docx missing readable manuscript content")
            if isinstance(reference_coverage, dict) and int(reference_coverage.get("reference_entries", 0) or 0) > 0:
                if not any(text == "References" or text == "参考文献" for text in manuscript_texts):
                    failures.append("output_docx missing references heading")
                if not any(text.startswith("1.") or text.startswith("1 ") for text in manuscript_texts):
                    failures.append("output_docx missing numbered reference entries")

    if state.get("delivery_status") == "ready_to_submit" and any(unit.get("status") == "needs_author_confirmation" for unit in units):
        failures.append("delivery_status ready_to_submit conflicts with needs_author_confirmation units")

    if state.get("counts", {}).get("comment_units") not in {None, len(units)}:
        failures.append("project_state comment_units does not match units count")

    # 📢 非阻断的响亮提醒:统计最终 response 正文里仍待作者处理的标记。命中不判 FAIL,
    # 只醒目提示,防止半成品被当成成品交付。"Not provided by user" 是 Image/Table 证据块
    # 的默认模板文案,属正常留白,故从 Not provided 计数中排除以免狼来了。
    pending_confirm = response_text.count("需作者确认")
    not_provided = sum(
        1 for line in response_text.splitlines()
        if "Not provided" in line and "Not provided by user" not in line
    )
    if pending_confirm or not_provided:
        print("=" * 60)
        print("📢 交付前提醒:最终 response 正文仍有待你处理之处 —")
        if pending_confirm:
            print(f"   · {pending_confirm} 处标记为「需作者确认」(定位/证据不足,需你补全后重跑)")
        if not_provided:
            print(f"   · {not_provided} 处标记为「Not provided」(非默认图/表留白,需你补内容)")
        print("   这些不阻断门禁,但直接投稿前请逐一核对。")
        print("=" * 60)

    if soft_style_notes:
        print("=" * 60)
        print("🟡 去AI软提示(句长>30词——只提示、不阻断,建议回片段修订;破折号等属硬门禁,见 FAIL 段):")
        for note in soft_style_notes:
            print(f"   · {note}")
        print("=" * 60)

    if failures:
        print("STRICT_GATE: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("STRICT_GATE: PASS")
    print(
        "注意:PASS 仅覆盖形式层(引文编号/去AI/结构/占位符/文件完整性)。"
        "改写是否改变原意、科学结论是否正确、数据是否一致均未自动核验,须作者逐条核对。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
