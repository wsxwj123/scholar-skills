#!/usr/bin/env python3
import argparse
import datetime
import json
import os
import sys
import time
from urllib import error, parse, request

# J4 完整性 / J5 自引 / J7 时效：用同目录 vendored 的 citation_guard_core
# （sync_vendored.py 纳管，与 _shared 真源逐字节一致）。此处曾内联一份"镜像 core
# 语义"的副本，结果同一个 bug 要修两遍（J5 整串作者不拆分），故删内联改 import。
from citation_guard_core import check_completeness, check_recency, check_self_citation
from citation_utils import extract_citation_ids


def scan_drafts(root_dir):
    used_ids = set()

    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".md"):
                filepath = os.path.join(dirpath, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    used_ids.update(str(x) for x in extract_citation_ids(content))
    return used_ids


def load_index(index_path):
    with open(index_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        data = data.get("papers", list(data.values()))

    if not isinstance(data, list):
        raise ValueError("literature_index.json must be a list or a dict with 'papers'.")

    entries = []
    for item in data:
        if not isinstance(item, dict):
            continue
        gid = item.get("global_id")
        if isinstance(gid, int) and gid > 0:
            entries.append(item)

    return entries


def validate_local(used_ids, index_entries):
    index_ids = {str(item["global_id"]) for item in index_entries}
    orphans = used_ids - index_ids
    unused = index_ids - used_ids
    return orphans, unused


def detect_duplicate_global_ids(index_entries):
    """Find global_id values shared by more than one index entry.

    Duplicate global_ids mean two distinct papers collapse onto the same
    citation number [n] -- data corruption that is always fatal. Returns a
    dict {gid: [entry, ...]} for gids appearing more than once.
    """
    groups = {}
    for item in index_entries:
        gid = str(item["global_id"])
        groups.setdefault(gid, []).append(item)
    return {gid: items for gid, items in groups.items() if len(items) > 1}


def validate_traceability(index_entries):
    failures = []
    for item in index_entries:
        gid = item.get("global_id")
        title = str(item.get("title") or "").strip()
        src_provider = str(item.get("source_provider") or "").strip()
        src_id = str(item.get("source_id") or "").strip()
        doi = str(item.get("doi") or "").strip()
        pmid = str(item.get("pmid") or "").strip()

        if not title:
            failures.append((gid, "title_missing", "title is empty"))
        if not (doi or pmid):
            failures.append((gid, "identifier_missing", "missing DOI/PMID"))
        if not (src_provider and src_id):
            failures.append((gid, "source_trace_missing", "missing source_provider/source_id"))
    return failures


def check_doi_online(doi, timeout=8):
    url = "https://api.crossref.org/works/" + parse.quote(doi)
    req = request.Request(url, headers={"User-Agent": "review-writing-validator/1.0"})
    with request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            return False, f"HTTP {resp.status}"
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
        returned = (
            data.get("message", {}).get("DOI", "")
            if isinstance(data, dict)
            else ""
        )
        if returned and returned.lower() == doi.lower():
            return True, "ok"
        return False, "DOI mismatch"


def _pmid_item_valid(item):
    # NCBI esummary 对不存在 PMID 仍返回带 uid 的占位项，但附带 error 字段
    # （如 "cannot get document summary"）。必须同时排除 error 才算真实存在。
    return bool(isinstance(item, dict) and item.get("uid") and not item.get("error"))


def check_pmid_online(pmid, timeout=8):
    url = (
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?"
        + parse.urlencode({"db": "pubmed", "id": pmid, "retmode": "json"})
    )
    req = request.Request(url, headers={"User-Agent": "review-writing-validator/1.0"})
    with request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            return False, f"HTTP {resp.status}"
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
        result = data.get("result", {}) if isinstance(data, dict) else {}
        item = result.get(str(pmid), {}) if isinstance(result, dict) else {}
        if _pmid_item_valid(item):
            return True, "ok"
        return False, "PMID not found"


def _is_transient_error(reason):
    text = str(reason).lower()
    transient_tokens = ["urlerror", "timed out", "timeout", "temporary", "429", "500", "502", "503", "504"]
    return any(tok in text for tok in transient_tokens)


def _check_with_retry(identifier, checker, timeout=8, retries=2, backoff=0.6):
    attempts = 0
    while True:
        attempts += 1
        try:
            ok, reason = checker(identifier, timeout=timeout)
        except error.HTTPError as e:
            ok, reason = False, f"HTTPError {e.code}"
        except error.URLError as e:
            ok, reason = False, f"URLError {e.reason}"
        except Exception as e:  # noqa: BLE001
            ok, reason = False, f"Error {e}"

        if ok:
            return True, reason, attempts
        if attempts > retries or not _is_transient_error(reason):
            return False, reason, attempts
        time.sleep(backoff * (2 ** (attempts - 1)))


def validate_live(index_entries, timeout=8, retries=2, backoff=0.6):
    checked = 0
    passed = 0
    failures = []

    for item in index_entries:
        gid = item["global_id"]
        doi = str(item.get("doi", "")).strip()
        pmid = str(item.get("pmid", "")).strip()

        if not doi and not pmid:
            failures.append((gid, "missing_identifier", "Need DOI or PMID for live validation"))
            continue

        checked += 1

        if doi:
            ok, reason, attempts = _check_with_retry(
                doi,
                check_doi_online,
                timeout=timeout,
                retries=retries,
                backoff=backoff,
            )
        else:
            ok, reason, attempts = _check_with_retry(
                pmid,
                check_pmid_online,
                timeout=timeout,
                retries=retries,
                backoff=backoff,
            )

        if ok:
            passed += 1
        else:
            failures.append((gid, "live_check_failed", f"{reason} (attempts={attempts})"))

    return {
        "checked": checked,
        "passed": passed,
        "failed": len(failures),
        "failures": failures,
    }


def filter_entries_by_used_ids(index_entries, used_ids):
    return [item for item in index_entries if str(item.get("global_id")) in used_ids]


def main():
    parser = argparse.ArgumentParser(description="Validate citation integrity for review-writing projects")
    parser.add_argument("--drafts-dir", default="drafts", help="Draft markdown directory")
    parser.add_argument(
        "--index-path",
        default=os.path.join("data", "literature_index.json"),
        help="Path to literature_index.json",
    )
    parser.add_argument("--live", action="store_true", help="Run online DOI/PMID validation")
    parser.add_argument("--timeout", type=int, default=8, help="HTTP timeout seconds for live checks")
    parser.add_argument("--retries", type=int, default=2, help="Retry count for transient live-check failures")
    parser.add_argument("--retry-backoff", type=float, default=0.6, help="Base backoff seconds for live-check retries")
    parser.add_argument(
        "--live-used-only",
        action="store_true",
        help="When used with --live, validate only citations actually referenced in drafts",
    )
    parser.add_argument("--fail-on-orphan", action="store_true", help="Exit non-zero if orphan citations exist")
    parser.add_argument("--fail-on-live", action="store_true", help="Exit non-zero if live checks fail")
    parser.add_argument("--fail-on-trace", action="store_true", help="Exit non-zero if source traceability checks fail")
    # Citation-integrity gates (J4 completeness fail-closed; J5/J7 advisory WARN).
    parser.add_argument("--gates", action="store_true",
                        help="Run J4 completeness + J5 self-citation + J7 recency gates")
    parser.add_argument("--state-path", default="state.json",
                        help="state.json holding manuscript authors (J5)")
    parser.add_argument("--current-year", type=int, default=None,
                        help="Current year for J7 recency (default: system clock)")
    parser.add_argument("--fail-on-incomplete", action="store_true",
                        help="Exit non-zero if any J4-incomplete entry exists (fail-closed)")
    args = parser.parse_args()

    if not os.path.exists(args.drafts_dir):
        print(f"Error: Drafts directory not found at {args.drafts_dir}")
        sys.exit(1)

    if not os.path.exists(args.index_path):
        print(f"Error: Index file not found at {args.index_path}")
        sys.exit(1)

    used_ids = scan_drafts(args.drafts_dir)
    try:
        entries = load_index(args.index_path)
    except Exception as e:  # noqa: BLE001
        print(f"Error loading index: {e}")
        sys.exit(1)

    orphans, unused = validate_local(used_ids, entries)
    duplicate_gids = detect_duplicate_global_ids(entries)
    unique_gid_count = len({str(item["global_id"]) for item in entries})

    print("-" * 40)
    print("VALIDATION REPORT")
    print("-" * 40)
    print(f"Draft citations: {len(used_ids)}")
    print(f"Index entries (with valid global_id): {len(entries)}")
    print(f"Unique global_ids: {unique_gid_count}")

    if duplicate_gids:
        print("-" * 40)
        print("DUPLICATE global_id CHECK")
        print("-" * 40)
        for gid in sorted(duplicate_gids, key=int):
            items = duplicate_gids[gid]
            print(f"[DUP-FAIL] global_id={gid} 被 {len(items)} 条 index 条目共用")
            for item in items:
                pmid = str(item.get("pmid") or "").strip() or "-"
                doi = str(item.get("doi") or "").strip() or "-"
                title = str(item.get("title") or "").strip() or "-"
                print(f"           PMID={pmid} DOI={doi} title={title}")
    else:
        print("[OK] No duplicate global_ids")

    if orphans:
        print(f"[CRITICAL] Orphan citations: {', '.join(sorted(orphans, key=int))}")
    else:
        print("[OK] No orphan citations")

    if unused:
        print(f"[WARNING] Unused index entries: {', '.join(sorted(unused, key=int))}")
    else:
        print("[OK] No unused index entries")

    trace_failures = validate_traceability(entries)
    if trace_failures:
        print("-" * 40)
        print("TRACEABILITY CHECK")
        print("-" * 40)
        for gid, code, reason in trace_failures:
            print(f"[TRACE-FAIL] global_id={gid} code={code} reason={reason}")
    else:
        print("[OK] Traceability checks passed")

    live_failures = 0
    if args.live:
        target_entries = entries
        if args.live_used_only:
            target_entries = filter_entries_by_used_ids(entries, used_ids)
        live = validate_live(
            target_entries,
            timeout=args.timeout,
            retries=max(0, args.retries),
            backoff=max(0.0, args.retry_backoff),
        )
        live_failures = live["failed"]
        print("-" * 40)
        print("LIVE DOI/PMID CHECK")
        print("-" * 40)
        print(
            f"Checked: {live['checked']}  Passed: {live['passed']}  Failed: {live['failed']}"
        )
        for gid, code, reason in live["failures"]:
            print(f"[LIVE-FAIL] global_id={gid} code={code} reason={reason}")

    incomplete_entries = []
    if args.gates:
        # J4 — per-entry completeness.
        raw_only_count = 0
        partial = []
        for item in entries:
            res = check_completeness(item)
            gid = item.get("global_id")
            if res["status"] == "incomplete":
                incomplete_entries.append((gid, res["missing_fields"]))
            elif res["status"] == "raw_only":
                raw_only_count += 1
            elif res["missing_fields"]:
                partial.append((gid, res["missing_fields"]))

        # J5 — self-citation (authors from state.json).
        manuscript_authors = []
        if os.path.exists(args.state_path):
            try:
                with open(args.state_path, "r", encoding="utf-8") as f:
                    state = json.load(f)
                a = state.get("authors") if isinstance(state, dict) else None
                if isinstance(a, list):
                    manuscript_authors = [str(x) for x in a]
            except (OSError, ValueError):
                pass
        self_cite = check_self_citation(entries, manuscript_authors)

        # J7 — recency.
        current_year = args.current_year or datetime.datetime.now(datetime.timezone.utc).year
        recency = check_recency(entries, current_year)

        print("-" * 40)
        print("CITATION-INTEGRITY GATES")
        print("-" * 40)
        print(f"J4 completeness: incomplete={len(incomplete_entries)} "
              f"raw_only={raw_only_count} partial={len(partial)} [fail-closed]")
        for gid, miss in incomplete_entries:
            print(f"[J4-FAIL] global_id={gid} missing={miss}")
        if self_cite["status"] == "skipped":
            print(f"J5 self-citation: skipped ({self_cite['reason']}) [warn]")
        else:
            print(f"J5 self-citation: status={self_cite['status']} "
                  f"ratio={self_cite['self_ratio']} ({self_cite['count']}/"
                  f"{self_cite['total_with_authors']}) threshold={self_cite['threshold']} [warn]")
        if recency["status"] == "skipped":
            print(f"J7 recency: skipped ({recency['reason']}) [warn]")
        else:
            print(f"J7 recency: status={recency['status']} "
                  f"recent_ratio={recency['recent_ratio']} "
                  f"({recency['recent_count']}/{recency['total_with_year']} within "
                  f"{recency['window']}y) min={recency['min_recent_ratio']} [warn]")

    # Duplicate global_ids are unconditional data corruption: always fatal,
    # independent of any --fail-on-* switch.
    should_fail = (
        bool(duplicate_gids)
        or (args.fail_on_orphan and bool(orphans))
        or (args.fail_on_live and live_failures > 0)
        or (args.fail_on_trace and bool(trace_failures))
        or (args.fail_on_incomplete and bool(incomplete_entries))
    )
    # 诚实化：PASS 只代表引文簿记与可达性过关，不代表论点被文献支持。
    if not should_fail:
        print(
            "[SCOPE] PASS 仅覆盖引文簿记与可达性（编号唯一/无孤儿/DOI·PMID 可解析/字段完整）；"
            "论点是否被文献支持、结论科学价值未核验。")
    if should_fail:
        sys.exit(2)


if __name__ == "__main__":
    main()
