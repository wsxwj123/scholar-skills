#!/usr/bin/env python3
"""B7 去AI脚本兜底，从生成后的审稿报告 HTML 抽正文文本后跑 humanizer_zh 检测。

reviewer-simulator 的产物是 assets/report_template.html 填充后的 HTML，审稿意见
正文散落在各 *_HTML / 散文占位符填充处。本脚本剥离 head/script/style/footer，
对剩余可见正文去标签后调用 humanizer_zh.scan_text + rhythm_check，核查 rubric
第七节"审稿意见自身去AI"5项（三项禁用 + 中文句长≤50 + 节奏）。

用法:
    python scan_report_humanize.py <报告HTML路径>
    python scan_report_humanize.py --text <纯文本路径>   # 直接扫纯文本/markdown中间产物

B7 阻断项（severity=ERROR 命中即 exit 1）：humanizer BANNED 模板句式/套话/修辞
（如"综上所述""革命性的""值得注意的是"）+ 去AI必禁三项 装饰破折号 decorative_dash /
scare quotes / 解释性冒号（均硬门禁、禁止使用）。
中文单句超50字 仍为软提示（WARNING，不阻断，仅供人工修润），其余（VAGUE 措辞/bullet/节奏）同为 WARNING。

退出码: 0=无 ERROR 级违规（可有软提示 WARNING）; 1=命中 ERROR 级（BANNED/破折号/scare quotes/解释性冒号）违规。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import humanizer_zh as h  # noqa: E402


def extract_body_text(html: str) -> str:
    """剥离 head/script/style/footer 后去标签，得到审稿正文可见文本。"""
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    html = re.sub(r"<!DOCTYPE[^>]*>", "", html, flags=re.I)
    for tag in ("head", "script", "style", "footer", "nav"):
        html = re.sub(rf"<{tag}\b.*?</{tag}>", "", html, flags=re.S | re.I)
    # skip-link 等导航锚点（非审稿正文）
    html = re.sub(r"<a\b[^>]*class=\"[^\"]*skip-link[^\"]*\"[^>]*>.*?</a>", "", html, flags=re.S | re.I)
    # 每个标签边界转双换行：使每个 DOM 文本节点成独立段落，避免相邻元素文本被
    # 拼成假长句（rhythm_check 按空行分段）；内联标签拆开只会让句变短（漏报方向），
    # 不产生跨节点误报。<br> 视为句内软换行（单换行）。
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    html = re.sub(r"</?[a-zA-Z][^>]*>", "\n\n", html)
    text = html
    # HTML 实体最小还原
    for ent, ch in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                    ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " ")):
        text = text.replace(ent, ch)
    # 每个非空行=一个 DOM 文本节点，用空行分隔使其各自成段，
    # 杜绝 rhythm_check 跨节点把短文本拼成假长句。
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="审稿报告正文去AI检测（B7 脚本兜底）")
    ap.add_argument("path", help="报告 HTML 路径（或 --text 时为纯文本路径）")
    ap.add_argument("--text", action="store_true", help="输入已是纯文本/markdown，不去标签")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    raw = Path(args.path).read_text(encoding="utf-8")
    text = raw if args.text else extract_body_text(raw)

    scan = h.scan_text(text)
    rhythm = h.rhythm_check(text)

    # B7 阻断项：severity=ERROR = humanizer BANNED 套话句式 + 去AI必禁三项(破折号/scare quotes/解释性冒号，硬门禁)。
    # 中文超50字 仍为软提示(WARNING，不阻断)。
    violations = [i for i in scan["issues"] if i.get("severity") == "ERROR"]
    others = [i for i in scan["issues"] if i.get("severity") != "ERROR"]
    long_sents = [i for i in rhythm["issues"] if i.get("type") == "cn_sentence_too_long"]
    rhythm_other = [i for i in rhythm["issues"] if i.get("type") != "cn_sentence_too_long"]
    violations_total = len(violations)  # 句长(long_sents)已降软，不再计入阻断

    if args.json:
        print(json.dumps(
            {"path": args.path, "scan": scan, "rhythm": rhythm,
             "b7_violation_count": violations_total,
             "warning_count": len(others) + len(rhythm_other)},
            ensure_ascii=False, indent=2))
        return 1 if violations_total else 0

    soft_total = len(others) + len(rhythm_other) + len(long_sents)
    if violations_total:
        print(f"HUMANIZE_FAILED (套话主干违规 {violations_total} 处，须修复后重跑)")
    else:
        print("HUMANIZE_OK (无套话主干违规)")
    print(f"- 套话主干违规: {violations_total}  软提示WARNING: {soft_total}")

    for i in violations:
        print(f"  [B7] {i['code']}: {i.get('text','')[:50]}  -> {i.get('suggestion','')}")
    for i in long_sents:
        print(f"  [WARN] cn_sentence_too_long({i['cn_chars']}字，已降软): {i.get('text','')[:50]}")
    for i in others:
        print(f"  [WARN] {i['code']}: {i.get('text','')[:50]}  -> {i.get('suggestion','')}")
    for i in rhythm_other:
        print(f"  [WARN] {i.get('type')}: para={i.get('paragraph')}")

    return 1 if violations_total else 0


if __name__ == "__main__":
    raise SystemExit(main())
