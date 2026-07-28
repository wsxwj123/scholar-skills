#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys
try:  # Windows GBK 控制台/管道捕获下 emoji print 防 UnicodeEncodeError
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from common import normalize_ws, read_json, split_sentences, tokenize, write_json, write_text


def estimate_tokens(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value)
    text = normalize_ws(text)
    if not text:
        return 0
    word_based = max(1, len(text.split()))
    char_based = max(1, len(text) // 4)
    return max(word_based, char_based)


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def ensure_state_dirs(project_root: Path) -> dict[str, Path]:
    state_root = project_root / "state"
    paths = {
        "root": state_root,
        "comment_windows": state_root / "comment_windows",
        "write_cycle_reports": state_root / "write_cycle_reports",
        "comment_memory": state_root / "comment_memory",
        "snapshots": state_root / "snapshots",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def section_key_sentences(section: dict[str, Any], limit: int = 3) -> list[str]:
    sentences: list[str] = []
    for paragraph in section.get("paragraphs", []):
        current = normalize_ws(paragraph.get("current_text") or paragraph.get("text") or "")
        if not current:
            continue
        for sentence in split_sentences(current):
            sentences.append(sentence)
            if len(sentences) >= limit:
                return sentences
    return sentences


def build_section_digests(index_data: dict[str, Any]) -> list[dict[str, Any]]:
    digests: list[dict[str, Any]] = []
    for section in index_data.get("sections", []):
        digests.append(
            {
                "section_id": section.get("section_id", ""),
                "heading": normalize_ws(section.get("heading", "")),
                "file": section.get("file", ""),
                "paragraph_count": len(section.get("paragraphs", [])),
                "key_sentences": section_key_sentences(section),
            }
        )
    return digests


def build_comment_registry(project_root: Path) -> list[dict[str, Any]]:
    registry: list[dict[str, Any]] = []
    for unit_path in sorted((project_root / "units").glob("*.json")):
        unit = read_json(unit_path, {})
        registry.append(
            {
                "comment_id": unit.get("comment_id", ""),
                "reviewer": unit.get("reviewer", ""),
                "severity": unit.get("severity", ""),
                "status": unit.get("status", ""),
                "comment_role": unit.get("comment_role", "comment"),
                "target_document": unit.get("target_document", ""),
                "editorial_intent": unit.get("editorial_intent", ""),
            }
        )
    return registry


def digest_overlap_score(query_text: str, digest: dict[str, Any]) -> int:
    query_tokens = {token for token in tokenize(query_text) if len(token) >= 4}
    if not query_tokens:
        return 0
    digest_text = " ".join(
        [
            normalize_ws(digest.get("heading", "")),
            " ".join(normalize_ws(text) for text in digest.get("key_sentences", [])),
        ]
    )
    digest_tokens = {token for token in tokenize(digest_text) if len(token) >= 4}
    return len(query_tokens.intersection(digest_tokens))


def unit_query_text(unit: dict[str, Any]) -> str:
    parts = [
        unit.get("editor_statement_seed", ""),
        unit.get("reviewer_statement_seed", ""),
        unit.get("comment_title", ""),
        unit.get("problem_description", ""),
        unit.get("root_cause", ""),
        unit.get("author_strategy", ""),
        unit.get("reviewer_comment_original", ""),
        unit.get("reviewer_comment_en", ""),
        unit.get("response_en", ""),
    ]
    return normalize_ws(" ".join(normalize_ws(part) for part in parts if normalize_ws(str(part))))


def read_index_for_unit(project_root: Path, unit: dict[str, Any]) -> dict[str, Any]:
    if unit.get("target_document") == "si":
        return read_json(project_root / "si_section_index.json", {"sections": []})
    return read_json(project_root / "manuscript_section_index.json", {"sections": []})


def find_section(index_data: dict[str, Any], section_id: str) -> dict[str, Any] | None:
    for section in index_data.get("sections", []):
        if section.get("section_id") == section_id:
            return section
    return None


def paragraph_window(section: dict[str, Any] | None, paragraph_index: int | None, neighbor_count: int) -> dict[str, Any]:
    if not section:
        return {"target_paragraph": {}, "neighbors_before": [], "neighbors_after": []}
    paragraphs = section.get("paragraphs", [])
    target = None
    target_pos = -1
    for idx, paragraph in enumerate(paragraphs):
        if paragraph.get("paragraph_index") == paragraph_index:
            target = paragraph
            target_pos = idx
            break
    if target is None and paragraphs:
        target = paragraphs[0]
        target_pos = 0
    before = paragraphs[max(0, target_pos - neighbor_count) : target_pos] if target_pos >= 0 else []
    after = paragraphs[target_pos + 1 : target_pos + 1 + neighbor_count] if target_pos >= 0 else []
    return {
        "target_paragraph": target or {},
        "neighbors_before": before,
        "neighbors_after": after,
    }


def compact_window(window: dict[str, Any], token_budget: int) -> tuple[dict[str, Any], list[str]]:
    compaction_steps: list[str] = []
    compacted = json.loads(json.dumps(window, ensure_ascii=False))

    def current_tokens() -> int:
        return estimate_tokens(compacted)

    if current_tokens() <= token_budget:
        return compacted, compaction_steps

    compacted["related_section_digests"] = compacted.get("related_section_digests", [])[:2]
    compaction_steps.append("trim-related-digests-to-2")
    if current_tokens() <= token_budget:
        return compacted, compaction_steps

    compacted["section_window"]["neighbors_before"] = compacted["section_window"].get("neighbors_before", [])[-1:]
    compacted["section_window"]["neighbors_after"] = compacted["section_window"].get("neighbors_after", [])[:1]
    compaction_steps.append("trim-neighbor-paragraphs")
    if current_tokens() <= token_budget:
        return compacted, compaction_steps

    compacted["review_context"]["editor_statement_seed"] = normalize_ws(compacted["review_context"].get("editor_statement_seed", ""))[:240]
    compacted["review_context"]["reviewer_statement_seed"] = normalize_ws(compacted["review_context"].get("reviewer_statement_seed", ""))[:240]
    compacted["review_context"]["reviewer_comment_original"] = normalize_ws(compacted["review_context"].get("reviewer_comment_original", ""))[:500]
    compacted["review_context"]["reviewer_comment_en"] = normalize_ws(compacted["review_context"].get("reviewer_comment_en", ""))[:500]
    compaction_steps.append("trim-review-context-text")
    if current_tokens() <= token_budget:
        return compacted, compaction_steps

    compacted["related_section_digests"] = compacted.get("related_section_digests", [])[:1]
    compacted["evidence_sources"] = [
        {
            "provider_family": source.get("provider_family", ""),
            "source": source.get("source", ""),
        }
        for source in compacted.get("evidence_sources", [])
    ]
    compaction_steps.append("keep-top-related-digest-and-minimal-evidence")
    return compacted, compaction_steps


def build_comment_window(
    project_root: Path,
    unit: dict[str, Any],
    token_budget: int = 4200,
    tail_lines: int = 80,
) -> tuple[dict[str, Any], dict[str, Any]]:
    index_data = read_index_for_unit(project_root, unit)
    digests = build_section_digests(index_data)
    atomic = unit.get("atomic_location") or {}
    section_id = atomic.get("si_section_id") or atomic.get("manuscript_section_id") or ""
    section = find_section(index_data, section_id)
    neighbor_count = max(1, min(2, max(tail_lines, 20) // 40))
    section_window = paragraph_window(section, atomic.get("paragraph_index"), neighbor_count)
    query_text = unit_query_text(unit)
    related_digests = sorted(digests, key=lambda digest: (-digest_overlap_score(query_text, digest), digest.get("section_id", "")))
    if section_id:
        related_digests = [digest for digest in related_digests if digest.get("section_id") != section_id]
    related_digests = related_digests[:3]

    window = {
        "comment_id": unit.get("comment_id", ""),
        "reviewer": unit.get("reviewer", ""),
        "severity": unit.get("severity", ""),
        "comment_role": unit.get("comment_role", "comment"),
        # A③：合并意见——同 merge_group 的多条意见协调回应，窗口带上分组标识以免被封死到不能协同。
        "merge_group": unit.get("merge_group", ""),
        "merge_lead": unit.get("merge_lead", ""),
        "target_document": unit.get("target_document", "manuscript"),
        "token_budget": token_budget,
        "tail_lines": tail_lines,
        "review_context": {
            "editor_statement_seed": unit.get("editor_statement_seed", ""),
            "reviewer_statement_seed": unit.get("reviewer_statement_seed", ""),
            "reviewer_comment_original": unit.get("reviewer_comment_original", ""),
            "reviewer_comment_en": unit.get("reviewer_comment_en", ""),
            "reviewer_comment_zh_literal": unit.get("reviewer_comment_zh_literal", ""),
            "intent_zh": unit.get("intent_zh", ""),
        },
        "atomic_location": atomic,
        "section_window": {
            "target_section_id": section.get("section_id", "") if section else "",
            "target_section_heading": section.get("heading", "") if section else "",
            "target_section_file": section.get("file", "") if section else "",
            **section_window,
        },
        "revision_plan": unit.get("revision_plan", {}),
        "evidence_sources": unit.get("evidence_sources", []),
        "related_section_digests": related_digests,
    }
    estimated_tokens = estimate_tokens(window)
    compacted_window, compaction_steps = compact_window(window, token_budget)
    report = {
        "comment_id": unit.get("comment_id", ""),
        "token_budget": token_budget,
        "estimated_tokens_before_compaction": estimated_tokens,
        "estimated_tokens_after_compaction": estimate_tokens(compacted_window),
        "compacted": compaction_steps != [],
        "compaction_steps": compaction_steps,
        "target_document": unit.get("target_document", "manuscript"),
        "target_section_id": compacted_window.get("section_window", {}).get("target_section_id", ""),
    }
    return compacted_window, report


def refresh_state_artifacts(project_root: Path) -> dict[str, Any]:
    paths = ensure_state_dirs(project_root)
    manuscript_index = read_json(project_root / "manuscript_section_index.json", {"sections": []})
    si_index = read_json(project_root / "si_section_index.json", {"sections": []})
    section_digests = {
        "manuscript": build_section_digests(manuscript_index),
        "si": build_section_digests(si_index),
    }
    comment_registry = build_comment_registry(project_root)
    write_json(paths["root"] / "section_digests.json", section_digests)
    write_json(paths["root"] / "comment_registry.json", comment_registry)

    state = read_json(project_root / "project_state.json", {})
    state["state_manager"] = {
        "section_digests_path": str((paths["root"] / "section_digests.json").resolve()),
        "comment_registry_path": str((paths["root"] / "comment_registry.json").resolve()),
        "comment_windows_dir": str(paths["comment_windows"].resolve()),
        "write_cycle_reports_dir": str(paths["write_cycle_reports"].resolve()),
        "last_refresh_utc": utc_now(),
    }
    write_json(project_root / "project_state.json", state)
    return {
        "ok": True,
        "section_digest_count": len(section_digests["manuscript"]) + len(section_digests["si"]),
        "comment_registry_count": len(comment_registry),
    }


def append_comment_cycle_log(project_root: Path, comment_id: str, stage: str, summary: str, payload: dict[str, Any] | None = None) -> None:
    paths = ensure_state_dirs(project_root)
    log_path = paths["root"] / "comment_cycle_log.json"
    log = read_json(log_path, {"entries": []})
    entry = {
        "comment_id": comment_id,
        "stage": stage,
        "summary": normalize_ws(summary),
        "timestamp_utc": utc_now(),
        "payload": payload or {},
    }
    log.setdefault("entries", []).append(entry)
    write_json(log_path, log)
    memory_path = paths["comment_memory"] / f"{comment_id}.md"
    existing = memory_path.read_text(encoding="utf-8") if memory_path.exists() else ""
    new_block = "\n".join(
        [
            f"## {entry['timestamp_utc']} | {stage}",
            "",
            f"- summary: {entry['summary'] or '无'}",
            f"- payload: `{json.dumps(entry['payload'], ensure_ascii=False)}`",
            "",
        ]
    )
    write_text(memory_path, existing + new_block)


def snapshot_state(project_root: Path, label: str) -> dict[str, Any]:
    paths = ensure_state_dirs(project_root)
    state = read_json(project_root / "project_state.json", {})
    snapshot = {
        "label": normalize_ws(label) or "snapshot",
        "timestamp_utc": utc_now(),
        "delivery_status": state.get("delivery_status", "draft"),
        "counts": state.get("counts", {}),
        "comments_input_mode": (state.get("inputs") or {}).get("comments_input_mode", ""),
    }
    filename = f"{snapshot['timestamp_utc'].replace(':', '').replace('-', '')}_{snapshot['label'].replace(' ', '_')}.json"
    write_json(paths["snapshots"] / filename, snapshot)
    return {"ok": True, "snapshot_path": str((paths["snapshots"] / filename).resolve())}


def main() -> int:
    parser = argparse.ArgumentParser(description="State manager for revise-sci anti-forgetfulness and token budgeting")
    parser.add_argument("--project-root", required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("refresh")

    write_cycle_parser = subparsers.add_parser("write-cycle")
    write_cycle_parser.add_argument("--comment-id", required=True)
    write_cycle_parser.add_argument("--token-budget", type=int, default=4200)
    write_cycle_parser.add_argument("--tail-lines", type=int, default=80)
    write_cycle_parser.add_argument("--json-summary", action="store_true")

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("--comment-id", required=True)
    update_parser.add_argument("--stage", required=True)
    update_parser.add_argument("--summary", default="")
    update_parser.add_argument("--payload-json", default="")

    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("--label", default="snapshot")

    args = parser.parse_args()
    project_root = Path(args.project_root)

    if args.command == "refresh":
        print(json.dumps(refresh_state_artifacts(project_root), ensure_ascii=False))
        return 0

    if args.command == "write-cycle":
        unit = read_json(project_root / "units" / f"{args.comment_id}.json", {})
        if not unit:
            raise SystemExit(f"unknown comment_id: {args.comment_id}")
        ensure_state_dirs(project_root)
        window, report = build_comment_window(project_root, unit, token_budget=args.token_budget, tail_lines=args.tail_lines)
        write_json(project_root / "state" / "comment_windows" / f"{args.comment_id}.json", window)
        write_json(project_root / "state" / "write_cycle_reports" / f"{args.comment_id}.json", report)
        if args.json_summary:
            print(json.dumps(report, ensure_ascii=False))
        else:
            print(json.dumps({"ok": True, "comment_id": args.comment_id}, ensure_ascii=False))
        return 0

    if args.command == "update":
        payload = read_json(Path(args.payload_json), {}) if args.payload_json else {}
        append_comment_cycle_log(project_root, args.comment_id, args.stage, args.summary, payload)
        print(json.dumps({"ok": True, "comment_id": args.comment_id, "stage": args.stage}, ensure_ascii=False))
        return 0

    if args.command == "snapshot":
        print(json.dumps(snapshot_state(project_root, args.label), ensure_ascii=False))
        return 0

    raise SystemExit(2)


if __name__ == "__main__":
    raise SystemExit(main())
