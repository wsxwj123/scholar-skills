#!/usr/bin/env python3
"""Consistency checks across atomic response units."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from unit_glob import load_units


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def collect_unit_text(unit: dict) -> str:
    c = unit.get("content", {})
    parts = [
        c.get("response_en", ""),
        c.get("revised_excerpt_en", ""),
        " ".join(c.get("notes_core_zh", [])),
        " ".join(c.get("notes_support_zh", [])),
    ]
    return "\n".join(parts)


def _write_landing_table(path: Path, rows: list[tuple[str, str, str, str, str]]) -> None:
    """写面向用户的『承诺↔落点对照表』markdown（Step 7.5 摆给用户核对，真兑现监工卡承诺）。"""
    lines = [
        "# 承诺 ↔ 落点对照表",
        "",
        "> 回复信里每一句『已添加/已做/已补充』都应在改稿里有落点。下面把 AI 承诺的动作逐句列出，"
        "落点为『无』的行就是嘴上说了、稿里没做，交付前必须补落点或改回复。",
        "",
        "| unit | 承诺句 | 类型 | 落点 | 位置 |",
        "|---|---|---|---|---|",
    ]
    if not rows:
        lines.append("| — | （未检出承诺动作） | — | — | — |")
    for uid, promise, kind, has_landing, where in rows:
        p = promise.replace("|", "\\|")
        w = where.replace("|", "\\|")
        flag = "" if has_landing == "有" else " ⚠️"
        lines.append(f"| {uid} | {p} | {kind} | {has_landing}{flag} | {w} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Consistency checker for reviewer-response units")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--rules", default="")
    parser.add_argument("--fail-on-conflict", action="store_true")
    parser.add_argument(
        "--emit-table",
        default="",
        help="写一份面向用户的『承诺↔落点对照表』markdown 到该路径（Step 7.5 摆给用户）",
    )
    args = parser.parse_args()

    root = Path(args.project_root)
    rules_path = Path(args.rules) if args.rules else Path(__file__).resolve().parents[1] / "references" / "consistency-rules.json"
    rules = read_json(rules_path)

    units = load_units(root / "units")
    text_by_unit = {u.get("unit_id", ""): collect_unit_text(u) for u in units}
    merged_text = "\n".join(text_by_unit.values())

    warnings: list[str] = []
    conflicts: list[str] = []
    fails: list[str] = []

    for pat in rules.get("forbidden_phrase_patterns", []):
        if re.search(re.escape(pat), merged_text, flags=re.IGNORECASE):
            conflicts.append(f"Forbidden phrase detected: {pat}")

    for term_set in rules.get("conflict_term_sets", []):
        present = [t for t in term_set if re.search(re.escape(t), merged_text, flags=re.IGNORECASE)]
        if len(present) >= 2:
            conflicts.append(f"Conflicting terms co-exist: {', '.join(present)}")

    for marker in rules.get("required_markers", []):
        if marker not in merged_text:
            warnings.append(f"Required marker not found globally: {marker}")

    # --- Commitment ↔ Landing-point consistency check ---
    # Verify that action verbs promised in response_en (added/performed/revised + object)
    # can be found as corresponding entries in modification_actions or revised_excerpt_en
    # of the same unit. Non-substantive mismatch → WARN (non-blocking); a promise to add
    # NEW substantive content (experiment/analysis/figure/data...) with no landing → FAIL.
    #
    # The old regex only matched `we <verb>` with the verb glued to `we`, so
    # `we have added`, `we performed`, `we conducted`, `we now provide`, `we cited`,
    # `we discussed` and passive `changes were made` all slipped through. Allow
    # optional auxiliaries/adverbs (have/now/also/...) between `we` and the verb,
    # widen the verb table, and cover the common passive phrasing.
    ACTION_VERB_RE = re.compile(
        r"\b("
        r"we (?:have |has |now |also |then |therefore )*"
        r"(?:added|clarified|revised|corrected|updated|included|removed|expanded|moved|"
        r"replaced|performed|conducted|provided|provide|cited|discussed|incorporated|"
        r"introduced|rephrased|rewrote|modified|adjusted|carried out|supplemented)"
        r"(?: [\w]+){0,5}"
        r"|changes? (?:were|was|have been|has been) made(?: [\w]+){0,5}"
        r")",
        re.IGNORECASE,
    )
    # Auxiliaries/adverbs to skip when locating the verb + object words for keyword
    # matching, so `we have added a control` yields keywords {added, control}, not {have}.
    PROMISE_SKIP_WORDS = {"we", "have", "has", "now", "also", "then", "therefore", "changes", "change"}
    # Signal that the promise claims newly added substantive content (a new
    # experiment / dataset / figure / analysis), not a mere wording tweak.
    # Only these promises get the stricter landing-evidence requirement below.
    SUBSTANTIVE_ADD_RE = re.compile(
        r"\b(?:added|new|newly|additional|included|incorporated|expanded|performed|conducted|carried out)\b"
        r".{0,40}?"
        r"\b(?:experiment|experiments|assay|assays|analysis|analyses|dataset|datasets|data|"
        r"figure|figures|panel|panels|table|tables|cohort|sample|samples|replicate|replicates|"
        r"measurement|measurements|test|tests|model|models|group|groups|control|controls)\b",
        re.IGNORECASE,
    )
    # 面向用户的承诺↔落点对照表行：(unit_id, 承诺句, 类型, 落点有无, 位置)。
    table_rows: list[tuple[str, str, str, str, str]] = []
    for u in units:
        if u.get("section") == "email":
            continue
        uid = u.get("unit_id", "?")
        c = u.get("content", {})
        response_en = c.get("response_en", "")
        mod_actions = c.get("modification_actions", [])
        revised = c.get("revised_excerpt_en", "")
        # 跨审稿人呼应去重：本 unit 若把回复交叉指向另一条已实答的 unit
        # （content.cross_ref 非空），其承诺的落点由被指向的 canonical unit 承载，
        # 本 unit 不再重复要求落点——否则 "As noted in our response to Reviewer 2..."
        # 里的 we added X 会被误判为无落点 FAIL。
        cross_ref = str(c.get("cross_ref", "") or "").strip()

        # Skip if unit is still a placeholder (not yet filled by AI)
        if "AI_FILL_REQUIRED" in response_en or "【待AI" in response_en:
            continue

        promises = ACTION_VERB_RE.findall(response_en)
        for promise in promises:
            promise_lower = promise.lower()
            # Drop leading `we`/auxiliaries so the verb + first object words become
            # the match keywords regardless of `we have/now ...` insertions.
            content_words = [w for w in promise_lower.split() if w not in PROMISE_SKIP_WORDS]
            kws = [kw for kw in content_words[1:3] if len(kw) > 3]

            # 1) English keyword match in action reason/target or revised excerpt
            found_in_actions_en = bool(kws) and any(
                any(kw in (a.get("reason", "") + a.get("target", "")).lower() for kw in kws)
                for a in mod_actions
            )
            found_in_revised_en = bool(kws) and any(kw in revised.lower() for kw in kws)

            # 2) Chinese fields: if modification_actions has a non-placeholder action_type
            #    and response_zh / notes are filled, treat the unit as consistent.
            #    This handles bilingual units where reason/target are written in Chinese.
            response_zh = c.get("response_zh", "")
            notes_core = c.get("notes_core_zh", [])
            zh_fields_filled = (
                response_zh
                and "【待AI" not in response_zh
                and "AI_FILL_REQUIRED" not in response_zh
            )
            actions_have_type = any(
                a.get("action_type", "").strip() not in {"", "修改"}
                or a.get("reason", "").strip() not in {"", "【待AI填写：添加/删除/修改及原因】"}
                for a in mod_actions
            )
            zh_fallback_ok = zh_fields_filled and actions_have_type

            # 3) Tighten the Chinese fallback for "newly added substantive content"
            #    promises. Filled-and-non-placeholder is too weak: a promise to add
            #    a new experiment must leave an add-landing somewhere, not just a
            #    non-empty Chinese field on an unrelated caption tweak. We require
            #    the landing point (action_type / target / reason / revised excerpt,
            #    EN or ZH) to carry an addition signal; a landing that is purely a
            #    wording / unit / typo fix carries none and is downgraded to WARN.
            #    Non-substantive promises (clarified/corrected/updated wording) keep
            #    the original lenient fallback so genuine bilingual matches do not
            #    become false positives.
            if zh_fallback_ok and SUBSTANTIVE_ADD_RE.search(promise):
                revised_zh = c.get("revised_excerpt_zh", "")
                landing_text = " ".join(
                    [a.get("action_type", "") + a.get("target", "") + a.get("reason", "") for a in mod_actions]
                    + [revised, revised_zh]
                ).lower()
                has_add_action = any(a.get("action_type", "").strip() == "添加" for a in mod_actions)
                landing_has_add_signal = bool(
                    re.search(
                        r"添加|新增|新加|增设|补充|加入|纳入|added|new\b|newly|additional|"
                        r"included|incorporated|expanded|extra",
                        landing_text,
                    )
                )
                zh_fallback_ok = has_add_action or landing_has_add_signal

            found = (
                found_in_actions_en
                or found_in_revised_en
                or zh_fallback_ok
                or bool(cross_ref)
            )

            # 记一行对照表：类型(实质新增/措辞) + 落点有无 + 落点位置。
            is_substantive = bool(SUBSTANTIVE_ADD_RE.search(promise))
            if cross_ref:
                where = f"交叉引用 → {cross_ref}"
            elif found_in_actions_en:
                where = "modification_actions"
            elif found_in_revised_en:
                where = "revised_excerpt_en"
            elif zh_fallback_ok:
                where = "中文字段(response_zh/notes/actions)"
            else:
                where = "—（未找到）"
            table_rows.append((
                uid,
                promise.strip(),
                "🔴实质新增" if is_substantive else "措辞",
                "有" if found else "无",
                where,
            ))

            # A promise lives in response_en independent of whether revised_excerpt_en
            # is "无": a unit often promises (e.g.) "added a new control" while landing
            # the change in SI/main text outside the excerpt and leaving revised="无".
            # The landing point is therefore sought in modification_actions / Chinese
            # fields (all folded into `found`), NOT gated on revised being non-empty.
            # revised="无" no longer exempts the promise from the check.
            if not found:
                msg = (
                    f"[{uid}] response_en promises '{promise}' but no matching entry found "
                    f"in modification_actions, revised_excerpt_en, or Chinese fields"
                )
                # Promising NEW substantive content (a new experiment/analysis/figure/
                # dataset/control...) with no landing point is a hard failure: the reply
                # claims work that leaves no trace in the revision plan. Non-substantive
                # wording promises stay WARN.
                if SUBSTANTIVE_ADD_RE.search(promise):
                    fails.append(msg + " [SUBSTANTIVE ADDITION — no landing point]")
                else:
                    warnings.append(msg)

    if args.emit_table:
        _write_landing_table(Path(args.emit_table), table_rows)

    blocking = list(conflicts)
    blocking += [f"MISSING LANDING: {f}" for f in fails]
    if blocking:
        print("CONSISTENCY_CHECK: FAIL")
        for c in blocking:
            print(f"- {c}")
        if warnings:
            for w in warnings:
                print(f"- WARN: {w}")
        # Substantive-addition failures always block (exit 1); forbidden-phrase
        # conflicts escalate to exit 2 only under --fail-on-conflict (unchanged).
        return 2 if (args.fail_on_conflict and conflicts) else 1

    print("CONSISTENCY_CHECK: PASS")
    if warnings:
        for w in warnings:
            print(f"- WARN: {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
