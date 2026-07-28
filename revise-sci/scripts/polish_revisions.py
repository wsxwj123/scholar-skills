#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import revise_units
from common import (
    build_section_markdown,
    detect_certainty_upgrade,
    hard_ai_style_markers,
    soft_ai_style_markers,
    normalize_ws,
    numeric_tokens_preserved,
    polish_changed_text_locally,
    read_json,
    write_json,
    write_text,
)


def polish_candidates(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        unit
        for unit in units
        if unit.get("status") == "completed"
        and (unit.get("revision_plan") or {}).get("scope") not in {"", "none", None}
    ]


def candidate_payload(unit: dict[str, Any]) -> dict[str, Any]:
    plan = unit.get("revision_plan") or {}
    return {
        "comment_id": unit.get("comment_id"),
        "editorial_intent": unit.get("editorial_intent"),
        "scope": plan.get("scope"),
        "change_scope": plan.get("change_scope", plan.get("scope")),
        "section_heading": (unit.get("atomic_location") or {}).get("section_heading", ""),
        "paragraph_index": (unit.get("atomic_location") or {}).get("paragraph_index"),
        "original_fragment": plan.get("original_fragment", ""),
        "raw_fragment": plan.get("raw_fragment", ""),
        "locked_prefix": plan.get("locked_prefix", ""),
        "locked_suffix": plan.get("locked_suffix", ""),
        "paragraph_before": plan.get("paragraph_before", ""),
        "evidence_boundary_note": plan.get("evidence_boundary_note", ""),
        "citation_strings": plan.get("citation_strings", []),
        "author_confirmation_reason": unit.get("author_confirmation_reason", ""),
    }


def build_manifest(project_root: Path, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    manifest = {
        "workflow": "revise-sci-polish",
        "source_skills": ["article-writing", "review-writing", "sci2doc", "humanizer-zh"],
        "role": "revision-fragment polisher",
        "scope_rule": "Only polish newly added or modified sentences. Keep untouched original text immutable.",
        "anti_ai_rules": {
            "forbidden_terms": [
                "delve into",
                "comprehensive landscape",
                "pivotal role",
                "realm",
                "tapestry",
                "underscore",
                "testament",
                "Moreover",
                "Crucial",
                "Landscape",
                "Pivot",
                "Foster",
                "Spearhead",
                "It is worth noting",
                "As mentioned above",
                "serves as",
                "acts as",
            ],
            "forbidden_structures": [
                "not only... but also",
                "rhetorical question",
                "trailing -ing clause (', reflecting/ensuring/highlighting/suggesting/demonstrating/indicating/revealing ...')",
                "decorative contrast",
                "em dash",
                "parallel structure repeated across 3+ consecutive sentences (same opening words or same syntactic frame)",
                "slogan-like closing line",
                "English sentence exceeding 30 words (split into two shorter sentences instead)",
                "Chinese sentence exceeding 50 characters (split or restructure)",
                "nested subordinate clause deeper than 2 levels in Chinese",
            ],
            "style_constraints": [
                "Keep scientific meaning unchanged.",
                "Keep evidence boundary unchanged.",
                "Do not add citations, data, statistics, mechanisms, figure labels, or claims.",
                "Stay within roughly ±15% of the raw changed fragment length.",
                "Prefer direct, evidence-bounded wording.",
                "Use declarative technical prose only.",
                "Avoid metaphor, promotional tone, and decorative transitions.",
                "Keep domain terminology unchanged and only rewrite the non-terminological wording around it.",
                "Every English sentence must be ≤30 words; split at conjunctions or semicolons if needed.",
                "No trailing -ing participial clause appending unsupported inference (', reflecting that ...', etc.).",
            ],
        },
        "output_schema": {
            "results": [
                {
                    "comment_id": "R1-Major-01",
                    "polished_fragment": "...",
                    "edit_decision": "minimal-cleanup | sentence-polish | paragraph-polish | unchanged",
                    "meaning_changed": False,
                    "scope_respected": True,
                    "ai_style_flags_removed": ["serves as"],
                    "notes": "short internal note",
                }
            ]
        },
        "candidates": [candidate_payload(unit) for unit in candidates],
    }
    write_json(project_root / "revision_polish_manifest.json", manifest)
    return manifest


def build_polish_prompt(project_root: Path, output_path: Path, candidates: list[dict[str, Any]]) -> str:
    lines = [
        "# Revise-Sci Revision Polishing Task",
        "",
        f"PROJECT_ROOT={project_root.resolve()}",
        f"OUTPUT_JSON_PATH={output_path.resolve()}",
        "",
        "You are the revision-fragment polisher inside the revise-sci workflow.",
        "",
        "You polish ONLY the already modified or newly added fragment created for a reviewer comment.",
        "You are not a general rewriter.",
        "You must not rewrite untouched original text.",
        "",
        "You must follow these source policies together:",
        "- article-writing: evidence-bounded, direct, anti-slop, self-correction",
        "- review-writing: anti-AI academic style, anti-similarity rewriting, restrained rhythm",
        "- sci2doc: declarative academic prose, no metaphor, no rhetorical flourish, no em dash",
        "- humanizer-zh: remove mechanical AI markers and templated phrasing",
        "",
        "Task:",
        "Polish only `raw_fragment`, using `locked_prefix` and `locked_suffix` as immutable context.",
        "Do not modify any text outside the revised fragment.",
        "",
        "Non-negotiable constraints:",
        "1. Preserve scientific meaning exactly.",
        "2. Preserve evidence boundary exactly.",
        "3. Do not add data, citations, mechanisms, statistics, figure references, or stronger claims.",
        "4. Do not rewrite locked context.",
        "5. Keep output length within about ±15% of the raw fragment.",
        "6. If safe polishing is not possible, perform minimal cleanup only.",
        "",
        "Forbidden words and phrases:",
        "delve into, comprehensive landscape, pivotal role, realm, tapestry, underscore, testament, moreover, crucial, spearhead, foster, it is worth noting, as mentioned above, serves as, acts as",
        "",
        "Forbidden structures:",
        "not only... but also...",
        "rhetorical questions",
        "decorative contrast structures",
        "trailing -ing clauses used as unsupported inference (', reflecting/ensuring/highlighting/suggesting/demonstrating/indicating/revealing ...')",
        "em dash",
        "parallel structure repeated across 3+ consecutive sentences (same opening words or same syntactic frame)",
        "grand significance claims not already supported",
        "slogan-like concluding lines",
        "English sentences longer than 30 words (split instead)",
        "Chinese sentences longer than 50 characters (split instead)",
        "Chinese nested subordinate clauses deeper than 2 levels",
        "",
        "Style requirements:",
        "- declarative sentences only",
        "- precise and direct",
        "- neutral and evidence-bounded",
        "- keep domain terminology unchanged",
        "- vary rhythm mildly, but do not become ornamental",
        "- preserve uncertainty when present",
        "- avoid repetitive AI transitions",
        "",
        "Silent self-check before finalizing:",
        "- Did I change meaning?",
        "- Did I strengthen the claim?",
        "- Did I touch locked context?",
        "- Did I introduce any banned AI phrase or fake sophistication?",
        "- Did I keep the sentence natural but restrained?",
        "",
        "Return JSON only.",
        "Schema:",
        "{",
        '  "results": [',
        "    {",
        '      "comment_id": "R1-Major-01",',
        '      "polished_fragment": "...",',
        '      "edit_decision": "minimal-cleanup | sentence-polish | paragraph-polish | unchanged",',
        '      "meaning_changed": false,',
        '      "scope_respected": true,',
        '      "ai_style_flags_removed": ["..."],',
        '      "notes": "short internal note"',
        "    }",
        "  ]",
        "}",
        "Do not include explanations outside JSON.",
        "",
        "Candidates:",
    ]
    for unit in candidates:
        payload = candidate_payload(unit)
        lines.extend(
            [
                f"- {payload['comment_id']} | scope={payload['scope']} | change_scope={payload['change_scope']} | section={payload['section_heading']} | paragraph_index={payload['paragraph_index']}",
                f"  locked_prefix: {payload['locked_prefix'] or '无'}",
                f"  original_fragment: {payload['original_fragment'] or '无'}",
                f"  raw_fragment: {payload['raw_fragment'] or '无'}",
                f"  locked_suffix: {payload['locked_suffix'] or '无'}",
                f"  evidence_boundary_note: {payload['evidence_boundary_note'] or '无'}",
                f"  citation_strings: {', '.join(payload['citation_strings']) if payload['citation_strings'] else '无'}",
            ]
        )
    return "\n".join(lines) + "\n"


def validate_output_payload(payload: Any, candidates: list[dict[str, Any]]) -> list[str]:
    rows = payload.get("results", []) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return ["revision polish output must be a list or {'results': [...]} payload"]
    valid_ids = {unit.get("comment_id") for unit in candidates}
    errors: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            errors.append("revision polish rows must be JSON objects")
            continue
        comment_id = normalize_ws(str(row.get("comment_id", "")))
        fragment = normalize_ws(str(row.get("polished_fragment", "")))
        if not comment_id or comment_id not in valid_ids:
            errors.append("revision polish row has an unknown comment_id")
        if not fragment:
            errors.append(f"revision polish row {comment_id or '<unknown>'} is missing polished_fragment")
        if row.get("meaning_changed") not in {False, None}:
            errors.append(f"revision polish row {comment_id or '<unknown>'} must keep meaning_changed=false")
        if row.get("scope_respected") not in {True, None}:
            errors.append(f"revision polish row {comment_id or '<unknown>'} must keep scope_respected=true")
    return errors


def run_polish_driver(
    project_root: Path,
    candidates: list[dict[str, Any]],
    runner: str,
    opencode_driver: str,
) -> tuple[str, dict[str, Any] | None, dict[str, Any]]:
    output_path = project_root / "revision_polish_results.json"
    prompt = build_polish_prompt(project_root, output_path, candidates)
    write_text(project_root / "revision_polish_prompt.md", prompt)
    if not candidates:
        return "not-required", {"results": []}, {"ok": True, "driver_mode": "not-required", "result_rows": 0}

    if runner:
        command = shlex.split(runner) + ["--input-json", str(project_root / "revision_polish_manifest.json"), "--output", str(output_path), "--project-root", str(project_root)]
        completed = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", errors="replace")
        if completed.returncode == 0 and output_path.exists():
            payload = read_json(output_path, None)
            errors = validate_output_payload(payload, candidates)
            if not errors:
                rows = payload.get("results", []) if isinstance(payload, dict) else payload
                return "local-runner", payload, {"ok": True, "driver_mode": "local-runner", "command": command, "result_rows": len(rows)}
        return "local-heuristic-fallback", None, {
            "ok": True,
            "driver_mode": "local-heuristic-fallback",
            "fallback_reason": "configured revision polish runner failed or produced invalid output",
            "command": command,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }

    if opencode_driver:
        command = shlex.split(opencode_driver) + ["--dir", str(project_root), prompt]
        completed = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", errors="replace")
        if completed.returncode == 0 and output_path.exists():
            payload = read_json(output_path, None)
            errors = validate_output_payload(payload, candidates)
            if not errors:
                rows = payload.get("results", []) if isinstance(payload, dict) else payload
                return "opencode-driver", payload, {"ok": True, "driver_mode": "opencode-driver", "command": command, "result_rows": len(rows)}
        return "local-heuristic-fallback", None, {
            "ok": True,
            "driver_mode": "local-heuristic-fallback",
            "fallback_reason": "opencode polish driver failed or produced invalid output",
            "command": command,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }

    return "local-heuristic", None, {
        "ok": True,
        "driver_mode": "local-heuristic",
        "result_rows": len(candidates),
    }


def fragment_map_from_payload(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if payload is None:
        return {}
    rows = payload.get("results", []) if isinstance(payload, dict) else payload
    mapping: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        mapping[normalize_ws(str(row.get("comment_id", "")))] = {
            "polished_fragment": normalize_ws(str(row.get("polished_fragment", ""))),
            "edit_decision": normalize_ws(str(row.get("edit_decision", ""))),
            "meaning_changed": row.get("meaning_changed", False),
            "scope_respected": row.get("scope_respected", True),
            "ai_style_flags_removed": row.get("ai_style_flags_removed", []) or [],
            "notes": normalize_ws(str(row.get("notes", ""))),
        }
    return mapping


def apply_polished_fragment(plan: dict[str, Any], polished_fragment: str) -> str:
    scope = plan.get("scope")
    paragraph_before = normalize_ws(plan.get("paragraph_before", ""))
    if scope == "sentence_replace":
        return revise_units.replace_sentence_at(paragraph_before, int(plan.get("target_sentence_index") or 0), polished_fragment)
    if scope == "sentence_append":
        return revise_units.append_sentence_to_paragraph(paragraph_before, polished_fragment)
    if scope == "paragraph_replace":
        return normalize_ws(polished_fragment)
    return normalize_ws(plan.get("paragraph_after_raw", paragraph_before))


def update_indexes(
    project_root: Path,
    manuscript_index: dict[str, Any],
    si_index: dict[str, Any],
    processed_units: list[dict[str, Any]],
) -> None:
    updated_text_by_section_paragraph: dict[tuple[str, int], str] = {}
    for unit in processed_units:
        if unit.get("status") != "completed":
            continue
        atomic = unit.get("atomic_location") or {}
        section_id = atomic.get("manuscript_section_id") or atomic.get("si_section_id")
        paragraph_index = atomic.get("paragraph_index")
        if not section_id or paragraph_index is None:
            continue
        updated_text_by_section_paragraph[(section_id, int(paragraph_index))] = unit.get("revised_excerpt_en", "")

    for index_name, index_data in (
        ("manuscript_section_index.json", manuscript_index),
        ("si_section_index.json", si_index),
    ):
        for section in index_data.get("sections", []):
            for paragraph in section.get("paragraphs", []):
                key = (section.get("section_id"), int(paragraph.get("paragraph_index")))
                if key in updated_text_by_section_paragraph:
                    paragraph["current_text"] = updated_text_by_section_paragraph[key]
            write_text(project_root / section["file"], build_section_markdown(section))
        write_json(project_root / index_name, index_data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Polish only revised fragments while preserving untouched manuscript text")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--revision-polish-runner", default="")
    parser.add_argument("--opencode-driver-command", default="")
    parser.add_argument("--disable-opencode-driver", action="store_true")
    args = parser.parse_args()

    project_root = Path(args.project_root)
    manuscript_index = read_json(project_root / "manuscript_section_index.json", {"sections": []})
    si_index = read_json(project_root / "si_section_index.json", {"sections": []})
    units_paths = sorted((project_root / "units").glob("*.json"))
    units = [read_json(path, {}) for path in units_paths]
    candidates = polish_candidates(units)
    build_manifest(project_root, candidates)

    runner = normalize_ws(args.revision_polish_runner or os.environ.get("REVISE_SCI_REVISION_POLISH_RUNNER", ""))
    opencode_driver = normalize_ws(
        args.opencode_driver_command
        or os.environ.get("REVISE_SCI_REVISION_POLISH_OPENCODE_DRIVER_COMMAND", "")
        or ("opencode run" if shutil.which("opencode") and not args.disable_opencode_driver else "")
    )

    driver_mode, payload, execution = run_polish_driver(project_root, candidates, runner, opencode_driver)
    fragment_map = fragment_map_from_payload(payload)

    processed_units: list[dict[str, Any]] = []
    polished_comment_ids: list[str] = []
    all_risk_flags: list[dict[str, Any]] = []
    for unit_path, unit in zip(units_paths, units):
        plan = unit.get("revision_plan") or {}
        if unit.get("status") == "completed" and plan.get("scope") not in {"", "none", None}:
            payload_row = fragment_map.get(unit.get("comment_id", ""), {})
            locked_raw_fragment = normalize_ws(plan.get("raw_fragment", ""))
            raw_fragment = normalize_ws(payload_row.get("polished_fragment") or plan.get("raw_fragment", ""))
            polished_fragment = polish_changed_text_locally(raw_fragment)
            polished_paragraph = apply_polished_fragment(plan, polished_fragment)
            unit["revised_excerpt_en"] = polished_paragraph
            unit["revision_plan"]["polished_fragment"] = polished_fragment
            unit["revision_plan"]["paragraph_after_polished"] = polished_paragraph
            unit["revision_plan"]["polish_edit_decision"] = payload_row.get("edit_decision") or "local-cleanup"
            unit["revision_plan"]["polish_notes"] = payload_row.get("notes", "")
            unit["revision_plan"]["ai_style_flags_removed"] = payload_row.get("ai_style_flags_removed", [])
            unit["polish_applied"] = True
            unit["polish_driver_mode"] = driver_mode
            locked_prefix = normalize_ws(plan.get("locked_prefix", ""))
            locked_suffix = normalize_ws(plan.get("locked_suffix", ""))
            # C反AI降软：只用 hard 子集判 fail-close；句长/破折号等 soft 项仅记录上报。
            guard_markers = hard_ai_style_markers(polished_fragment)
            unit["polish_soft_style_flags"] = soft_ai_style_markers(polished_fragment)
            unit["polish_scope_respected"] = payload_row.get("scope_respected", True)
            unit["polish_meaning_changed"] = payload_row.get("meaning_changed", False)
            unit["polish_locked_context_ok"] = (
                (not locked_prefix or polished_paragraph.startswith(locked_prefix))
                and (not locked_suffix or polished_paragraph.endswith(locked_suffix))
            )

            comment_id = unit.get("comment_id", "")
            # A: numeric drift guard, compares locked raw fragment vs polished fragment.
            numeric_check = numeric_tokens_preserved(locked_raw_fragment, polished_fragment)
            unit["polish_numbers_ok"] = numeric_check["ok"]
            # B: certainty-upgrade guard, blocks hedge to strong-claim upgrades.
            certainty_check = detect_certainty_upgrade(locked_raw_fragment, polished_fragment)
            unit["polish_certainty_ok"] = certainty_check["ok"]

            # C: structured risk flags (fail behavior preserved; flags are additive).
            risk_flags: list[dict[str, Any]] = []
            if not numeric_check["ok"]:
                detail_parts = []
                if numeric_check["introduced"]:
                    detail_parts.append(f"introduced {numeric_check['introduced']}")
                if numeric_check["dropped"]:
                    detail_parts.append(f"dropped {numeric_check['dropped']}")
                risk_flags.append({
                    "type": "numeric_drift",
                    "fragment_id": comment_id,
                    "detail": "; ".join(detail_parts),
                })
            if not certainty_check["ok"]:
                risk_flags.append({
                    "type": "certainty_upgrade",
                    "fragment_id": comment_id,
                    "detail": f"hedge {certainty_check['raw_hedges']} upgraded to {certainty_check['introduced_strong_verbs']}",
                })
            if guard_markers:
                risk_flags.append({
                    "type": "overstatement",
                    "fragment_id": comment_id,
                    "detail": f"banned AI-style markers: {guard_markers}",
                })
            if unit["polish_meaning_changed"] is not False or unit["polish_scope_respected"] is not True:
                risk_flags.append({
                    "type": "invented_claim",
                    "fragment_id": comment_id,
                    "detail": "polish driver reported meaning change or scope violation",
                })
            unit["polish_risk_flags"] = risk_flags
            all_risk_flags.extend(risk_flags)

            unit["polish_guard_ok"] = (
                len(guard_markers) == 0
                and unit["polish_scope_respected"]
                and unit["polish_meaning_changed"] is False
                and numeric_check["ok"]
                and certainty_check["ok"]
            )
            polished_comment_ids.append(unit.get("comment_id"))
        else:
            unit["polish_applied"] = False
            unit["polish_driver_mode"] = "not-required"
            unit["polish_guard_ok"] = True
            unit["polish_scope_respected"] = True
            unit["polish_meaning_changed"] = False
            unit["polish_locked_context_ok"] = True
            unit["polish_numbers_ok"] = True
            unit["polish_certainty_ok"] = True
            unit["polish_risk_flags"] = []
        processed_units.append(unit)
        write_json(unit_path, unit)
        write_text(project_root / "comment_records" / f"{unit['comment_id']}.md", revise_units.render_comment_record(unit))

    update_indexes(project_root, manuscript_index, si_index, processed_units)
    write_text(project_root / "response_to_reviewers.md", revise_units.render_response_to_reviewers(processed_units))
    write_text(project_root / "manuscript_edit_plan.md", revise_units.render_edit_plan(processed_units))

    state = read_json(project_root / "project_state.json", {})
    state["revision_polish"] = {
        "driver_mode": driver_mode,
        "candidate_count": len(candidates),
        "polished_comment_ids": polished_comment_ids,
    }
    write_json(project_root / "project_state.json", state)

    execution["candidate_count"] = len(candidates)
    execution["polished_comment_ids"] = polished_comment_ids
    execution["polish_risk_flags"] = all_risk_flags
    write_json(project_root / "revision_polish_execution.json", execution)
    print(json.dumps({"ok": True, "driver_mode": driver_mode, "candidate_count": len(candidates)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
