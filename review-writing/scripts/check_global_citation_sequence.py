#!/usr/bin/env python3
import argparse
from collections import Counter
from pathlib import Path

from citation_utils import extract_citation_ids


def collect_ids(drafts_dir):
    ids = []
    for md in sorted(Path(drafts_dir).glob("**/*.md")):
        text = md.read_text(encoding="utf-8")
        ids.extend(extract_citation_ids(text))
    return ids


def main():
    parser = argparse.ArgumentParser(description="Check global citation sequence continuity")
    parser.add_argument("--drafts-dir", default="drafts")
    args = parser.parse_args()

    ids = collect_ids(args.drafts_dir)
    if not ids:
        print("No citations found.")
        return

    uniq = sorted(set(ids))
    min_id, max_id = uniq[0], uniq[-1]
    expected = set(range(min_id, max_id + 1))
    missing = sorted(expected - set(uniq))
    freq = Counter(ids)
    duplicates = sorted([x for x, c in freq.items() if c > 1])

    print("Citation Sequence Report")
    print(f"Range: [{min_id}..{max_id}]  Unique: {len(uniq)}  Total mentions: {len(ids)}")

    if missing:
        print("[CRITICAL] Missing sequence numbers:", ", ".join(str(x) for x in missing))
        raise SystemExit(2)

    if min_id != 1:
        print(f"[WARNING] Sequence starts at {min_id}, expected 1")

    if duplicates:
        print("[INFO] Reused citation IDs:", ", ".join(str(x) for x in duplicates))

    print("[OK] Citation sequence is continuous")


if __name__ == "__main__":
    main()
