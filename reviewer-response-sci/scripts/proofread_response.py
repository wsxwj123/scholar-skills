#!/usr/bin/env python3
"""门禁适配:对回复信「作者亲自写的 Response 正文」跑 proofread.py 字符级自检,只报告不改稿。

关键:只抽 content.response_en + content.response_zh(作者写给编辑的回复正文),
绝不抽 reviewer_comment_en/reviewer_comment_zh/reviewer_intent_zh(审稿人原话),
否则会误伤引用的审稿人英文(破折号/智能引号/公式等)。

把每个 units/<unit_id>.json 的作者 Response 正文 dump 成临时目录里的 <unit_id>.md,
再调同目录 proofread.py 扫该临时目录(--fail-on misspelling,chinese_punct,subsup_bare)。
纯读 units/ + 输出报告,绝不写回任何 json/html/原稿。临时目录用完即删。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from unit_glob import iter_units

_SCRIPT_DIR = Path(__file__).resolve().parent
FAIL_ON = "misspelling,chinese_punct,subsup_bare"

# 只扫这两个字段:作者写给编辑的回复正文。审稿人原话字段一律不碰。
AUTHOR_RESPONSE_FIELDS = ("response_en", "response_zh")


def _extract_author_response(unit: dict) -> str:
    """从一个原子 unit 抽取作者 Response 正文(response_en + response_zh)。
    两字段各占独立段落,中间空行分隔,让 proofread 的按行启发式正确区分中英。"""
    content = unit.get("content", {})
    parts = []
    for field in AUTHOR_RESPONSE_FIELDS:
        val = content.get(field, "")
        if isinstance(val, str) and val.strip():
            parts.append(val.strip())
    return "\n\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Proofread gate over author-written Response text in reviewer-response units")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--report", default="")
    args = parser.parse_args()

    project_root = Path(args.project_root)
    report = Path(args.report) if args.report else project_root / "proofread_response_report.json"
    units_dir = project_root / "units"

    if not units_dir.exists():
        print(json.dumps(
            {"ok": False, "error": f"units dir not found: {units_dir}"}, ensure_ascii=False))
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        dumped = 0
        for p, unit in iter_units(units_dir):
            text = _extract_author_response(unit)
            if not text:
                continue
            (tmp_dir / f"{p.stem}.md").write_text(text, encoding="utf-8")
            dumped += 1
        if dumped == 0:
            print(json.dumps(
                {"ok": True, "status": "no_author_response", "units_dir": str(units_dir)},
                ensure_ascii=False))
            return 0
        proc = subprocess.run(
            [sys.executable, str(_SCRIPT_DIR / "proofread.py"),
             "--manuscript-dir", str(tmp_dir),
             "--report", str(report),
             "--fail-on", FAIL_ON],
            capture_output=True, text=True,
        )
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
