#!/usr/bin/env python3
"""Calibration mode for reviewer-simulator (lightweight optional mode).

Measures how well this skill's accept/reject judgements agree with a gold
standard set, reporting FNR / FPR / balanced accuracy.

Convention (see references/review_rubric.md section 九):
- "reject" is the positive class (the manuscript the skill should stop).
- Each record needs two fields:
    truth     : "accept" | "reject"  (gold standard)
    predicted : "accept" | "reject"  (skill verdict mapped: 接收/小修->accept, 大修/拒稿->reject)

Input: a JSON array of such records. Empty / missing gold set -> graceful
structured notice (status="empty"), not a crash.

Usage:
    python calibration.py --input gold_set.json
    echo '[]' | python calibration.py --input -
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LABELS = {"accept", "reject"}
EMPTY_NOTICE = (
    "calibration 模式需要您提供一组已知最终结果（accept/reject）的论文集才能"
    "校准本技能的判定可信度；请提供后重试。"
)


def load_records(path: str):
    if path == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("input must be a JSON array of records")
    return data


def normalize_label(v):
    if not isinstance(v, str):
        return None
    v = v.strip().lower()
    return v if v in LABELS else None


def compute(records):
    tp = fp = tn = fn = 0          # positive class = reject
    skipped = []
    for i, rec in enumerate(records):
        truth = normalize_label(rec.get("truth")) if isinstance(rec, dict) else None
        pred = normalize_label(rec.get("predicted")) if isinstance(rec, dict) else None
        if truth is None or pred is None:
            skipped.append(i)
            continue
        if truth == "reject" and pred == "reject":
            tp += 1
        elif truth == "accept" and pred == "reject":
            fp += 1
        elif truth == "accept" and pred == "accept":
            tn += 1
        else:  # truth reject, pred accept
            fn += 1
    return tp, fp, tn, fn, skipped


def main():
    ap = argparse.ArgumentParser(
        description="Calibrate reviewer-simulator verdicts against a gold standard set."
    )
    ap.add_argument("--input", required=True,
                    help='JSON array file of records ({"truth","predicted"}), or "-" for stdin')
    args = ap.parse_args()

    try:
        records = load_records(args.input)
    except FileNotFoundError:
        print(json.dumps({"status": "empty", "notice": EMPTY_NOTICE,
                          "reason": "input file not found"}, ensure_ascii=False))
        return
    except (ValueError, json.JSONDecodeError) as e:
        print(json.dumps({"status": "error", "notice": str(e)}, ensure_ascii=False))
        raise SystemExit(1)

    if not records:
        print(json.dumps({"status": "empty", "notice": EMPTY_NOTICE}, ensure_ascii=False))
        return

    tp, fp, tn, fn, skipped = compute(records)
    n = tp + fp + tn + fn
    if n == 0:
        print(json.dumps({"status": "empty", "notice": EMPTY_NOTICE,
                          "reason": "no valid records (all skipped)",
                          "skipped_indices": skipped}, ensure_ascii=False))
        return

    fnr = fn / (fn + tp) if (fn + tp) else None   # among true reject
    fpr = fp / (fp + tn) if (fp + tn) else None   # among true accept
    if fnr is not None and fpr is not None:
        balanced_accuracy = ((1 - fnr) + (1 - fpr)) / 2
    else:
        balanced_accuracy = None

    warnings = []
    if n < 10:
        warnings.append("样本过小（n<10），指标仅供参考，置信度低。")
    if fnr is None:
        warnings.append("金标准集中无 reject 样本，FNR 不可计算。")
    if fpr is None:
        warnings.append("金标准集中无 accept 样本，FPR 不可计算。")
    if skipped:
        warnings.append(f"{len(skipped)} 条记录字段缺失/非法已跳过（索引 {skipped}）。")

    result = {
        "status": "ok",
        "n": n,
        "confusion_matrix": {"TP": tp, "FP": fp, "TN": tn, "FN": fn,
                             "_note": "positive class = reject"},
        "FNR": fnr,
        "FPR": fpr,
        "balanced_accuracy": balanced_accuracy,
        "warnings": warnings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
