#!/usr/bin/env python3
"""R2b「联网核验已生效」的机器判据。

为什么需要：R2 的 `citation_guard.py --offline` 在离线模式下 http_ok 恒 True，任何
**格式完整**的条目都判 verified（编造 DOI + 编造 PMID + 齐全 source_provider/source_id
实测 exit 0）。而 `verified` 字段住在 AI 可自由编辑的 literature_index.json 里，
Windows 上 edirect 常失效时这条 DoD 仍会报绿。本脚本查的是「联网那道到底跑没跑过、
且覆盖到本节每一条引文」，与 R2 的格式核互补，不重叠。

判据（三条同时成立才 exit 0）：
  ① data/citation_guard_report.json 存在且可解析
  ② 该报告是联网跑的：report.online_check 为 true
     （字段嵌在 report 键下；SKILL.md 用 --log 与 --report 同路径时顶层是
      report/manual_review_queue/runs 三键，故取 report，回退 runs 末条）
  ③ 本节 related_sections 命中的每条 index 条目都带 verification_details.checked_at
     （联网核验时由 --write-back 逐条落盘。report 顶层的 checked_at 是单次运行
      时间戳，证明不了逐条覆盖，绝不拿它顶替。）

fail-safe 方向是收紧：文件缺失 / 结构对不上 / online_check 非 true / 本节零命中条目
一律 exit 1，不给「查不到就当过」的口子。

CLI:
  python3 scripts/check_online_verified.py --section 2.1
    [--report data/citation_guard_report.json] [--index data/literature_index.json]
退出码：0 通过 / 1 未通过（含各种取不到证据的情形）/ 2 用法错。
"""
from __future__ import annotations

import sys as _sys
try:  # Windows GBK 控制台/管道捕获下 emoji print 防 UnicodeEncodeError
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import argparse
import json
import sys
from pathlib import Path

FAIL_HINT = ("本节引文未经联网核验，请勿声明通过。补跑 SKILL.md Phase 2 Step 6 的联网 "
             "citation_guard（不带 --offline、带 --write-back）后重核。")


def _load(path: Path):
    """读 JSON；不存在/坏档一律返回 None（调用方按 fail 处理，不静默放过）。"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _report_body(raw):
    """取报告主体：优先顶层 report 键，回退 runs 末条。取不到返回 None。"""
    if not isinstance(raw, dict):
        return None
    body = raw.get("report")
    if isinstance(body, dict):
        return body
    runs = raw.get("runs")
    if isinstance(runs, list) and runs and isinstance(runs[-1], dict):
        return runs[-1]
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="R2b：本节引文是否真的过了联网核验")
    ap.add_argument("--section", required=True, help="本节 section_id，如 2.1")
    ap.add_argument("--report", default="data/citation_guard_report.json")
    ap.add_argument("--index", default="data/literature_index.json")
    args = ap.parse_args()

    raw = _load(Path(args.report))
    if raw is None:
        print(f"[R2b] FAIL 报告不存在或无法解析：{args.report}。{FAIL_HINT}")
        return 1
    body = _report_body(raw)
    if body is None:
        print(f"[R2b] FAIL 报告结构对不上（既无 report 键也无 runs 列表）：{args.report}。{FAIL_HINT}")
        return 1
    if body.get("online_check") is not True:
        print(f"[R2b] FAIL report.online_check={body.get('online_check')!r}"
              f"（这份报告是 --offline 跑的，离线模式判不出编造文献）。{FAIL_HINT}")
        return 1

    index = _load(Path(args.index))
    if not isinstance(index, list):
        print(f"[R2b] FAIL 文献索引不存在/不是数组：{args.index}。{FAIL_HINT}")
        return 1

    section = args.section.strip()
    entries = [e for e in index
               if isinstance(e, dict) and section in (e.get("related_sections") or [])]
    if not entries:
        print(f"[R2b] FAIL 本节 {section!r} 在 {args.index} 里零条归属文献"
              f"（全库 {len(index)} 条）。要么本节确无引文——那就在盲检里把本项裁为 na 并注明；"
              f"要么是 related_sections 没填对——补好再核。")
        return 1

    missing = [e.get("global_id") for e in entries
               if not (e.get("verification_details") or {}).get("checked_at")]
    if missing:
        print(f"[R2b] FAIL 本节 {len(entries)} 条文献中 {len(missing)} 条无逐条联网核验时间戳"
              f"（verification_details.checked_at 缺失）：global_id={missing}。{FAIL_HINT}")
        return 1

    print(f"[R2b] PASS 本节 {section} 的 {len(entries)} 条文献均有逐条联网核验时间戳"
          f"（report.online_check=true）。注：本项只证明联网核验跑过且覆盖到本节，"
          f"不代表论点被这些文献支持。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
