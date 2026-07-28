#!/usr/bin/env python3
"""Hard gate checks for atomic reviewer-response project."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from unit_glob import load_units


REQUIRED_UNIT_KEYS = ["unit_id", "order", "reviewer", "section", "comment_number", "title", "source", "links", "content", "status"]
REQUIRED_CONTENT_KEYS = ["reviewer_comment_zh", "reviewer_comment_en", "response_en", "atomic_location", "revised_excerpt_en", "notes_core_zh", "notes_support_zh", "evidence"]
REQUIRED_LINK_KEYS = ["anchors", "manuscript_unit_ids", "si_unit_ids"]
PLACEHOLDERS = {"", "none", "n/a", "无", "not provided by user", "[ai_fill_required] response to reviewer in english.", "[ai_fill_required] revised manuscript/si text in english."}


def _norm(s: object) -> str:
    if s is None:
        return ""
    return str(s).strip().lower()


def _is_placeholder_text(v: object) -> bool:
    n = _norm(v)
    if n in PLACEHOLDERS:
        return True
    return ("待ai" in n) or ("ai_fill_required" in n)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Strict gate for reviewer-response atomic project")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--require-links", action="store_true", help="Fail if a comment unit has no manuscript/si links")
    parser.add_argument("--allow-placeholder", action="store_true", help="Allow placeholder revised text without failing")
    args = parser.parse_args()

    root = Path(args.project_root)
    errors: list[str] = []

    state_p = root / "project_state.json"
    index_p = root / "index.json"
    units_dir = root / "units"
    m_dir = root / "manuscript_units"
    s_dir = root / "si_units"

    for p in [state_p, index_p, units_dir, m_dir]:
        if not p.exists():
            errors.append(f"Missing required path: {p}")

    if errors:
        print("STRICT_GATE: FAIL")
        for e in errors:
            print(f"- {e}")
        return 1

    state = read_json(state_p)
    index_data = read_json(index_p)
    units = load_units(units_dir)
    unit_map = {u.get("unit_id", ""): u for u in units}

    # Basic key checks
    for u in units:
        for k in REQUIRED_UNIT_KEYS:
            if k not in u:
                errors.append(f"Unit {u.get('unit_id','<unknown>')} missing key: {k}")
        content = u.get("content", {})
        for k in REQUIRED_CONTENT_KEYS:
            if k not in content:
                errors.append(f"Unit {u.get('unit_id')} content missing key: {k}")
        links = u.get("links", {})
        for k in REQUIRED_LINK_KEYS:
            if k not in links:
                errors.append(f"Unit {u.get('unit_id')} links missing key: {k}")

    # Count checks
    expected_total = state.get("counts", {}).get("total_units")
    if expected_total is not None and expected_total != len(units):
        errors.append(f"total_units mismatch: state={expected_total}, actual={len(units)}")

    # TOC leaf count vs comment unit count
    leaf_ids = []
    for rv in index_data.get("toc", {}).get("reviewers", []):
        for sec in rv.get("sections", []):
            for item in sec.get("items", []):
                leaf_ids.append(item.get("unit_id"))

    comment_units = [u for u in units if u.get("section") != "email"]
    if len(leaf_ids) != len(comment_units):
        errors.append(f"TOC leaf count mismatch: toc={len(leaf_ids)}, comment_units={len(comment_units)}")

    for uid in leaf_ids:
        if uid not in unit_map:
            errors.append(f"TOC references missing unit_id: {uid}")

    m_units_all = [read_json(p) for p in sorted(m_dir.glob("*.json"))]
    s_units_all = [read_json(p) for p in sorted(s_dir.glob("*.json"))] if s_dir.exists() else []
    m_ids = {u.get("unit_id") for u in m_units_all}
    s_ids = {u.get("unit_id") for u in s_units_all}

    # Source atomic-unit structure checks (manuscript/SI)
    def _check_source_units(units_all: list[dict], label: str) -> None:
        section_like_count = 0
        caption_count = 0
        for u in units_all:
            for key in ["unit_id", "paragraph_index", "text", "unit_type", "section_unit_id"]:
                if key not in u:
                    errors.append(f"{label} unit {u.get('unit_id','<unknown>')} missing key: {key}")
            utype = u.get("unit_type")
            if utype in {"section_block", "section_heading"}:
                section_like_count += 1
            if utype == "figure_caption":
                caption_count += 1
        if not units_all:
            errors.append(f"{label} units are empty")
            return
        if section_like_count == 0 and label == "manuscript":
            errors.append(f"{label} has no section-level units (section_block/section_heading)")
        # Caption may be zero when document has no figures; do not hard-fail on caption_count == 0.

    _check_source_units(m_units_all, "manuscript")
    if s_units_all:
        _check_source_units(s_units_all, "si")

    # Link validity
    for u in comment_units:
        links = u.get("links", {})
        m_links = links.get("manuscript_unit_ids", [])
        s_links = links.get("si_unit_ids", [])
        content = u.get("content", {})
        status = u.get("status", {})

        for mid in m_links:
            if mid not in m_ids:
                errors.append(f"Unit {u.get('unit_id')} links unknown manuscript unit: {mid}")
        for sid in s_links:
            if sid and sid not in s_ids:
                errors.append(f"Unit {u.get('unit_id')} links unknown si unit: {sid}")

        if args.require_links and not (m_links or s_links):
            errors.append(f"Unit {u.get('unit_id')} has no manuscript/si links")

        # Substantive-quality checks
        response_en = _norm(content.get("response_en"))
        revised_en = _norm(content.get("revised_excerpt_en"))
        original_en = _norm(content.get("original_excerpt_en"))
        excerpt_state = _norm(status.get("excerpt_state"))

        if not args.allow_placeholder and _is_placeholder_text(response_en):
            errors.append(f"Unit {u.get('unit_id')} response_en is placeholder/empty")

        if not args.allow_placeholder and _is_placeholder_text(revised_en):
            errors.append(f"Unit {u.get('unit_id')} revised_excerpt_en is placeholder/empty")

        if not args.allow_placeholder:
            ai_fields = [
                ("reviewer_comment_zh", content.get("reviewer_comment_zh")),
                ("reviewer_intent_zh", content.get("reviewer_intent_zh")),
                ("response_zh", content.get("response_zh")),
                ("revised_excerpt_zh", content.get("revised_excerpt_zh")),
            ]
            for field_name, value in ai_fields:
                if _is_placeholder_text(value):
                    errors.append(f"Unit {u.get('unit_id')} {field_name} is placeholder/empty")

            notes_core = content.get("notes_core_zh", [])
            notes_support = content.get("notes_support_zh", [])
            if not notes_core or any(_is_placeholder_text(x) for x in notes_core):
                errors.append(f"Unit {u.get('unit_id')} notes_core_zh is placeholder/empty")
            if not notes_support or any(_is_placeholder_text(x) for x in notes_support):
                errors.append(f"Unit {u.get('unit_id')} notes_support_zh is placeholder/empty")

        if original_en not in PLACEHOLDERS and revised_en not in PLACEHOLDERS and revised_en == original_en:
            errors.append(f"Unit {u.get('unit_id')} revised_excerpt_en is identical to original_excerpt_en")

        if excerpt_state == "needs_manual_revision" and not args.allow_placeholder:
            errors.append(f"Unit {u.get('unit_id')} excerpt_state=needs_manual_revision (manual revision required)")

        atomic_loc = content.get("atomic_location", {})
        m_uid = _norm(atomic_loc.get("manuscript_unit_id"))
        m_sent_idx = atomic_loc.get("manuscript_sentence_index")
        if m_uid in {"", "none"}:
            errors.append(f"Unit {u.get('unit_id')} missing atomic_location.manuscript_unit_id")
        if m_sent_idx is None:
            errors.append(f"Unit {u.get('unit_id')} missing atomic_location.manuscript_sentence_index")

    if errors:
        print("STRICT_GATE: FAIL")
        for e in errors:
            print(f"- {e}")
        return 1

    print("STRICT_GATE: PASS")
    print(f"- units: {len(units)}")
    print(f"- toc leaf items: {len(leaf_ids)}")
    print(f"- manuscript units: {len(m_ids)}")
    print(f"- si units: {len(s_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
