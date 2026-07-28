#!/usr/bin/env python3
import argparse
import json
import re
import os
import time
from difflib import SequenceMatcher
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl
except Exception:  # pragma: no cover
    fcntl = None


def load_json(path, default):
    p = Path(path)
    if not p.exists():
        return default
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data
    except Exception:
        return default


def save_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def resolve_matrix_paths(matrix_path):
    read_path = Path(matrix_path)
    write_path = read_path

    # Canonical source is synthesis_matrix.json; auto-fallback from legacy literature_matrix.json.
    if read_path.name == "synthesis_matrix.json" and not read_path.exists():
        legacy = read_path.with_name("literature_matrix.json")
        if legacy.exists():
            read_path = legacy
    return read_path, write_path


@contextmanager
def matrix_lock(timeout=20):
    lock_path = Path("logs") / ".matrix.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o644)
    start = time.time()
    acquired = False
    try:
        while True:
            try:
                if fcntl is None:
                    acquired = True
                    break
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                if time.time() - start > timeout:
                    raise TimeoutError(f"matrix lock timeout after {timeout}s: {lock_path}")
                time.sleep(0.05)
        yield
    finally:
        if acquired and fcntl is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except Exception:
                pass
        os.close(fd)


def normalize(text):
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", str(text).lower()).strip()


def section_id_matches(row_section_id, query_section):
    """前缀匹配: '2.1' 匹配 '2.1 模式菌底盘 (Model Organisms)'"""
    rs = str(row_section_id).strip()
    qs = str(query_section).strip()
    if not qs:
        return False
    return rs == qs or rs.startswith(qs + " ")


def _tokens(text):
    return [t for t in normalize(text).split() if t]


def semantic_score(row, claim):
    row_text = " ".join([str(row.get("title", "")), str(row.get("abstract", "")), str(row.get("key_finding", ""))])
    claim_text = " ".join([str(claim.get("text", "")), " ".join(claim.get("keywords", []) if isinstance(claim.get("keywords"), list) else [])])

    row_tokens = set(_tokens(row_text))
    claim_tokens = set(_tokens(claim_text))
    if not row_tokens or not claim_tokens:
        token_overlap = 0.0
    else:
        token_overlap = len(row_tokens & claim_tokens) / len(row_tokens | claim_tokens)

    char_sim = SequenceMatcher(None, normalize(row_text), normalize(claim_text)).ratio()
    return 0.7 * token_overlap + 0.3 * char_sim


def default_row(item, section_id, evidence_round):
    return {
        "global_id": item.get("global_id"),
        "section_id": section_id,
        "claim_id": None,
        "evidence_round": evidence_round,
        "source_tier": item.get("source_tier", "core"),
        "study_type": item.get("study_type", "unknown"),
        "year": item.get("year", "N/A"),
        "journal": item.get("journal", "N/A"),
        "title": item.get("title", "N/A"),
        "abstract": item.get("abstract", ""),
        "key_finding": item.get("key_finding", "N/A"),
        "effect_size": item.get("effect_size", "N/A"),
        "limitation": item.get("limitation", "N/A"),
        "relevance_score": item.get("relevance_score", None),
        "confidence": item.get("confidence", None),
        "updated_in_round3": False,
    }


def upsert_rows(existing_rows, new_rows):
    by_key = {}
    for row in existing_rows:
        key = (row.get("global_id"), row.get("section_id"))
        by_key[key] = row

    for row in new_rows:
        key = (row.get("global_id"), row.get("section_id"))
        if key in by_key:
            merged = dict(by_key[key])
            merged.update({k: v for k, v in row.items() if v not in (None, "", [])})
            by_key[key] = merged
        else:
            by_key[key] = row

    return [by_key[k] for k in sorted(by_key.keys(), key=lambda x: (x[1], x[0]))]


def cmd_bootstrap(args):
    with matrix_lock():
        index = load_json(args.index, [])
        if not isinstance(index, list):
            raise SystemExit("literature_index must be a list")

        matrix_read, matrix_write = resolve_matrix_paths(args.matrix)
        existing = load_json(matrix_read, [])
        existing = existing if isinstance(existing, list) else []

        rows = []
        for item in index:
            if not isinstance(item, dict):
                continue
            gid = item.get("global_id")
            if not isinstance(gid, int) or gid <= 0:
                continue

            sections = item.get("related_sections")
            if args.section:
                sections = [args.section]
            elif not isinstance(sections, list) or not sections:
                sections = ["unassigned"]

            for section in sections:
                rows.append(default_row(item, section, args.round))

        merged = upsert_rows(existing, rows)
        save_json(matrix_write, merged)
    print(f"Bootstrap complete: {len(rows)} candidate rows, {len(merged)} total matrix rows")


def cmd_focus(args):
    matrix_read, _ = resolve_matrix_paths(args.matrix)
    matrix = load_json(matrix_read, [])
    if not isinstance(matrix, list):
        raise SystemExit("synthesis_matrix must be a list")

    subset = [r for r in matrix if section_id_matches(r.get("section_id", ""), args.section)]
    payload = {
        "section": args.section,
        "count": len(subset),
        "rows": subset[: args.limit],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def cmd_bind_claims(args):
    claims = load_json(args.claims, [])
    if not isinstance(claims, list):
        raise SystemExit("claims must be a list")

    with matrix_lock():
        matrix_read, matrix_write = resolve_matrix_paths(args.matrix)
        matrix = load_json(matrix_read, [])
        if not isinstance(matrix, list):
            raise SystemExit("synthesis_matrix must be a list")

        updated = 0
        for row in matrix:
            if not section_id_matches(row.get("section_id", ""), args.section):
                continue

            hay = normalize(" ".join([str(row.get("title", "")), str(row.get("abstract", "")), str(row.get("key_finding", ""))]))
            best = None
            best_hits = 0
            best_semantic = 0.0
            for claim in claims:
                kws = claim.get("keywords") or []
                if not isinstance(kws, list):
                    kws = []
                hits = sum(1 for kw in kws if normalize(kw) and normalize(kw) in hay)
                sem = semantic_score(row, claim)
                if hits > best_hits or (hits == best_hits and sem > best_semantic):
                    best_hits = hits
                    best_semantic = sem
                    best = claim

            if best and (best_hits >= args.min_hits or best_semantic >= args.semantic_threshold):
                row["claim_id"] = best.get("claim_id")
                row["evidence_round"] = 2
                row["semantic_score"] = round(best_semantic, 4)
                updated += 1

        save_json(matrix_write, matrix)
    print(f"Bound claims for section={args.section}: {updated} rows updated")
    if args.fail_on_no_update and updated == 0:
        raise SystemExit(2)


def cmd_mark_round3(args):
    with matrix_lock():
        matrix_read, matrix_write = resolve_matrix_paths(args.matrix)
        matrix = load_json(matrix_read, [])
        if not isinstance(matrix, list):
            raise SystemExit("synthesis_matrix must be a list")

        touched = 0
        for row in matrix:
            if args.section and not section_id_matches(row.get("section_id", ""), args.section):
                continue
            if row.get("claim_id") in (None, ""):
                continue
            row["updated_in_round3"] = True
            row["evidence_round"] = 3
            touched += 1

        save_json(matrix_write, matrix)
    print(f"Round3 mark complete: {touched} rows")


def cmd_audit(args):
    matrix_read, _ = resolve_matrix_paths(args.matrix)
    matrix = load_json(matrix_read, [])
    if not isinstance(matrix, list):
        raise SystemExit("synthesis_matrix must be a list")

    rows = matrix
    if args.section:
        rows = [r for r in rows if section_id_matches(r.get("section_id", ""), args.section)]

    missing_claim = [r for r in rows if not r.get("claim_id")]
    missing_key = [
        r
        for r in rows
        if r.get("key_finding") in (None, "", "N/A") or r.get("limitation") in (None, "", "N/A")
    ]

    report = {
        "section": args.section,
        "rows": len(rows),
        "missing_claim": len(missing_claim),
        "missing_key_fields": len(missing_key),
        "round_distribution": {
            "r1": sum(1 for r in rows if r.get("evidence_round") == 1),
            "r2": sum(1 for r in rows if r.get("evidence_round") == 2),
            "r3": sum(1 for r in rows if r.get("evidence_round") == 3),
        },
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.fail_on_gap and (report["missing_claim"] > 0 or report["missing_key_fields"] > 0):
        raise SystemExit(2)


def build_parser():
    parser = argparse.ArgumentParser(description="Manage synthesis matrix across 3 evidence rounds")
    sub = parser.add_subparsers(dest="command", required=True)

    p_boot = sub.add_parser("bootstrap", help="Round-1 bootstrap from literature index")
    p_boot.add_argument("--index", default="data/literature_index.json")
    p_boot.add_argument("--matrix", default="data/synthesis_matrix.json")
    p_boot.add_argument("--section", default=None)
    p_boot.add_argument("--round", type=int, default=1)
    p_boot.set_defaults(func=cmd_bootstrap)

    p_focus = sub.add_parser("focus", help="Show section-scoped matrix subset")
    p_focus.add_argument("--matrix", default="data/synthesis_matrix.json")
    p_focus.add_argument("--section", required=True)
    p_focus.add_argument("--limit", type=int, default=20)
    p_focus.set_defaults(func=cmd_focus)

    p_bind = sub.add_parser("bind-claims", help="Round-2 bind claim IDs by keyword matching")
    p_bind.add_argument("--matrix", default="data/synthesis_matrix.json")
    p_bind.add_argument("--section", required=True)
    p_bind.add_argument("--claims", required=True, help="JSON list of {claim_id,text,keywords[]}")
    p_bind.add_argument("--min-hits", type=int, default=2, help="Minimum keyword hits required for claim binding")
    p_bind.add_argument(
        "--semantic-threshold",
        type=float,
        default=0.35,
        help="Fallback semantic score threshold when keyword hits are below --min-hits",
    )
    p_bind.add_argument(
        "--fail-on-no-update",
        action="store_true",
        help="Exit with code 2 when no row is bound to any claim",
    )
    p_bind.set_defaults(func=cmd_bind_claims)

    p_r3 = sub.add_parser("mark-round3", help="Mark rows as round-3 refreshed")
    p_r3.add_argument("--matrix", default="data/synthesis_matrix.json")
    p_r3.add_argument("--section", default=None)
    p_r3.set_defaults(func=cmd_mark_round3)

    p_audit = sub.add_parser("audit", help="Quality audit for matrix completeness")
    p_audit.add_argument("--matrix", default="data/synthesis_matrix.json")
    p_audit.add_argument("--section", default=None)
    p_audit.add_argument("--fail-on-gap", action="store_true")
    p_audit.set_defaults(func=cmd_audit)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
