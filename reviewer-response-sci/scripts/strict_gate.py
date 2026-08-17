#!/usr/bin/env python3
"""Hard gate checks for atomic reviewer-response project."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from unit_glob import load_units

from build_full_package import (
    ABSENT_SENTINEL,
    collect_comment_pairs,
    comment_fingerprint,
    comments_semantic_sha256,
    docx_semantic_sha256,
    extract_email,
    read_docx_text_from_bytes,
    sha256_hex,
)


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


_FINGERPRINT_RE = re.compile(r"^sha256:v1:[0-9a-f]{64}$")


def _verify_input_identity(state: dict, units: list[dict], errors: list[str]) -> None:
    """round22 源绑定：读取当前三输入，核 project_state 的 raw/semantic identity、
    重新解析出的 comment topology 与每个 unit 的 fingerprint。email unit 豁免。

    input_identity 缺失的旧项目（round22 之前构建/手工装配）不做本层检查——
    legacy 项目的收口在 build 侧（rc=2 要求新 root），gate 只对声明过身份的
    项目 fail-closed。"""
    identity = state.get("input_identity")
    if identity is None:
        return

    def _bad(msg: str) -> None:
        errors.append(f"input identity error: {msg}")

    if not isinstance(identity, dict) or not isinstance(identity.get("semantic"), dict):
        _bad("project_state.input_identity malformed/tampered (source identity unverifiable)")
        return
    semantic = identity["semantic"]

    def _load_record(label: str, allow_absent: bool) -> bytes | None:
        record = identity.get(label)
        if allow_absent and record == ABSENT_SENTINEL:
            return None
        if not (isinstance(record, dict) and isinstance(record.get("path"), str)
                and isinstance(record.get("raw_sha256"), str)):
            _bad(f"{label} identity record malformed/tampered")
            return None
        path = Path(record["path"])
        if not path.is_file():
            _bad(f"{label} source file missing/unreadable: {path}")
            return None
        try:
            data = path.read_bytes()
        except OSError as exc:
            _bad(f"{label} source file unreadable: {path} ({exc.__class__.__name__})")
            return None
        actual = "sha256:" + sha256_hex(data)
        if actual != record["raw_sha256"]:
            _bad(f"{label} raw sha256 mismatch: source bytes changed since build "
                 f"(stored {record['raw_sha256'][:23]}..., current {actual[:23]}...)")
        return data

    comments_bytes = _load_record("comments", allow_absent=False)
    manuscript_bytes = _load_record("manuscript", allow_absent=False)
    si_bytes = _load_record("si", allow_absent=True)

    # semantic identity 重算比对（能读到的输入才比，读不到的已在上面报错）
    rows = None
    if comments_bytes is not None:
        try:
            comments_text = read_docx_text_from_bytes(comments_bytes)
            rows = collect_comment_pairs(comments_text)
            current = comments_semantic_sha256(rows, extract_email(comments_text))
        except Exception as exc:
            _bad(f"comments source unparsable: {exc.__class__.__name__}")
        else:
            if current != semantic.get("comments_sha256"):
                _bad("comments semantic identity mismatch: comment topology/text/email changed")
    if manuscript_bytes is not None:
        try:
            current = docx_semantic_sha256(manuscript_bytes)
        except Exception as exc:
            _bad(f"manuscript source unparsable: {exc.__class__.__name__}")
        else:
            if current != semantic.get("manuscript_sha256"):
                _bad("manuscript semantic identity mismatch: visible text/structure changed")
    si_declared_absent = identity.get("si") == ABSENT_SENTINEL
    if si_declared_absent:
        if semantic.get("si_sha256") != ABSENT_SENTINEL:
            _bad("si semantic identity mismatch: state says absent but semantic hash present")
    elif si_bytes is not None:
        try:
            current = docx_semantic_sha256(si_bytes)
        except Exception as exc:
            _bad(f"si source unparsable: {exc.__class__.__name__}")
        else:
            if current != semantic.get("si_sha256"):
                _bad("si semantic identity mismatch: visible text/structure changed")

    # unit fingerprint：自洽（unit 自身字段重算）+ 与当前 comment topology 对齐
    comment_units = sorted(
        (u for u in units if u.get("section") != "email"),
        key=lambda u: (u.get("order", 0), str(u.get("unit_id", ""))),
    )
    stored_fingerprints: list[str] = []
    for u in comment_units:
        uid = u.get("unit_id", "<unknown>")
        stored = u.get("source", {}).get("reviewer_comment_fingerprint")
        if not (isinstance(stored, str) and _FINGERPRINT_RE.match(stored)):
            errors.append(f"unit fingerprint error: {uid} missing/invalid reviewer_comment_fingerprint")
            continue
        recomputed = comment_fingerprint(
            str(u.get("reviewer", "")), str(u.get("section", "")),
            str(u.get("comment_number", "")),
            str(u.get("content", {}).get("reviewer_comment_en", "")),
        )
        if recomputed != stored:
            errors.append(
                f"unit fingerprint mismatch: {uid} stored fingerprint does not match "
                f"its own reviewer/section/number/comment payload")
        stored_fingerprints.append(stored)
    if rows is not None and not any(e.startswith("unit fingerprint") for e in errors):
        expected = [
            comment_fingerprint(row.reviewer, row.section, row.number, row.comment_en)
            for row in rows
        ]
        if expected != stored_fingerprints:
            _bad("comment topology mismatch: current comments source does not match unit fingerprints "
                 f"(current {len(expected)} comments vs {len(stored_fingerprints)} units)")


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

    # round22：先核当前源文件与身份绑定（raw/semantic/topology/fingerprint）
    _verify_input_identity(state, units, errors)

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
