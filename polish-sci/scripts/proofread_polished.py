#!/usr/bin/env python3
"""门禁适配:对润色输出跑 proofread.py 的字符级自检,只报告不改稿。

把各 polished/<idx>.json 的 polished_text dump 成临时目录里的 <idx>.md,
再调同目录 proofread.py 扫该临时目录(--fail-on misspelling,chinese_punct,subsup_bare)。
纯读 polished/ + 输出报告,绝不写回任何 json/docx/原稿。临时目录用完即删。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from common import read_json

_SCRIPT_DIR = Path(__file__).resolve().parent
FAIL_ON = "misspelling,chinese_punct,subsup_bare"


def main() -> int:
    parser = argparse.ArgumentParser(description="Proofread gate over polished output")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--report", default="")
    args = parser.parse_args()

    project_root = Path(args.project_root)
    report = Path(args.report) if args.report else project_root / "proofread_report.json"
    polished_dir = project_root / "polished"
    index = read_json(project_root / "units_index.json", {"units": []})

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for entry in index.get("units", []):
            idx = entry["idx"]
            unit = read_json(polished_dir / f"{idx}.json", None)
            if unit is None:
                continue
            (tmp_dir / f"{idx}.md").write_text(
                unit.get("polished_text", ""), encoding="utf-8")
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
