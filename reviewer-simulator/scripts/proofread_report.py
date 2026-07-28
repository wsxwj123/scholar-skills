#!/usr/bin/env python3
"""软门禁适配:对审稿报告 HTML 跑 proofread.py 的字符级自检,只报告不阻断。

reviewer-simulator 的产物是 assets/report_template.html 填充后的审稿报告 HTML,
审稿意见正文散落在各 *_HTML / 散文占位符填充处。本脚本复用
scan_report_humanize.extract_body_text 剥离 head/script/style/footer 抽出可见正文,
dump 成临时目录里的 report.md,再调同目录 proofread.py 扫该临时目录。

关键:**不传 --fail-on**——只要 proofread 的 score/issues 报告,不触发它的硬拦逻辑。
本适配器自身对退出码软化:无论 proofread 是否因 score 阈值返回 1,本脚本一律 exit 0
(软项:只报告拼写/标点/上下标问题,不阻断审稿报告交付)。纯读 HTML,绝不写回。
临时目录用完即删。

用法:
    python proofread_report.py <报告HTML路径>
    python proofread_report.py <报告HTML路径> --report <落盘json路径>
    python proofread_report.py <报告HTML路径> --json     # 打印完整 proofread summary

退出码: 恒为 0(软项不阻断)。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scan_report_humanize import extract_body_text  # noqa: E402

_SCRIPT_DIR = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser(
        description="审稿报告正文 proofread 软体检(只报告不阻断)")
    ap.add_argument("path", help="报告 HTML 路径")
    ap.add_argument("--report", default="",
                    help="proofread summary 落盘 json 路径(默认写临时目录后丢弃)")
    ap.add_argument("--json", action="store_true",
                    help="打印 proofread 完整 summary(否则只打印精简计数)")
    args = ap.parse_args()

    html = Path(args.path).read_text(encoding="utf-8")
    body = extract_body_text(html)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        (tmp_dir / "report.md").write_text(body, encoding="utf-8")
        report_path = args.report or str(tmp_dir / "proofread_report.json")
        # 不传 --fail-on:只要 score/issues 报告,不触发 proofread 的硬拦。
        proc = subprocess.run(
            [sys.executable, str(_SCRIPT_DIR / "proofread.py"),
             "--manuscript-dir", str(tmp_dir),
             "--report", report_path],
            capture_output=True, text=True,
        )
        summary = {}
        try:
            summary = json.loads(Path(report_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass

    total = summary.get("total_issues", 0)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        if total:
            print(f"PROOFREAD_SOFT (软项,不阻断): 报告正文发现 {total} 处字符级问题,仅报告")
        else:
            print("PROOFREAD_OK (软项): 报告正文无字符级问题")
        # 展开各类型 + 前若干条明细,供人工参考(不阻断交付)
        for f in summary.get("files", []):
            if not f.get("issues_total"):
                continue
            print(f"- score={f.get('score')} types={f.get('issues_by_type', {})}")
            for i in f.get("issues", [])[:20]:
                print(f"  [{i.get('severity')}] {i.get('type')}: "
                      f"{i.get('found', i.get('detail', ''))}"
                      f"{('  -> ' + i['suggest']) if i.get('suggest') else ''}")
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    # 软项:恒 exit 0,不阻断审稿报告交付。
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
