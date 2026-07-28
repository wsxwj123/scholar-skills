#!/usr/bin/env python3
"""cross_section_consistency.py — 跨段数值一致性检查（半自动 WARN 级）。

改稿第一痛点：改了正文里的数字，忘了同步摘要 / 图注 / 结论。本脚本扫同一
数值在多段落出现时的「漂移」：同一标签词（如 survival rate / 存活率 / n /
p 值）在不同段落带了**不同数值** → 报「疑似不一致」嫌疑，供 AI 或人复核。

定位（保守优先，误报比漏报更伤信任）：
  - 只抓高价值数值模式：百分比 `\\d+%`、样本量 `n=\\d+`、p 值
    `p[<=>]0.\\d+`、带标签数值（"survival rate ... 45%" / "分别为 X 和 Y"）。
  - 每个数值绑定一个**归一化标签词**（数值紧邻的上下文关键词）。
  - 跨段聚类：同一标签词在不同段落出现不同数值 → 嫌疑（列两处位置+值）。
  - 只在「同标签词 + 数值不同」高置信时报；纯巧合的相同/不同数字不报；
    拿不准不报。
  - 排除 References / 参考文献 块与裸引用号 `[12]`（PMID/编号不是科学数值）。

输出结构化 JSON（exit 0，WARN 级，永不硬拦）：
  {"suspicions": [{"label", "kind", "values": [{"value","location","context"}]}],
   "files_scanned", "summary"}

CLI:
  python3 cross_section_consistency.py --project-root <root> [--drafts-dir drafts]
扫 <root>/<drafts-dir>/*.md（改稿章节，按 revise-sci 的 drafts/section_*.md
结构；排除 _deprecated/ 与合并稿）。
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# 数值模式：只抓高价值、低歧义的科学数值。每条带一个 kind 标签。
# 顺序敏感——p 值/n= 先于裸百分比，避免被通用百分比误吞。
# ---------------------------------------------------------------------------
# 默认只扫 percent + p_value（高置信、低噪声）。sample_size(n=) 默认**关闭**：
# 真稿里不同图/不同实验的样本量本就允许不同，跨段聚类会刷出海量假嫌疑；n 改错
# 又罕见，漏报代价低。需要时用 --include-sample-size 显式开启。
VALUE_PATTERNS = [
    ("p_value", re.compile(r"\bp\s*[<=>]\s*(0?\.\d+)\b", re.IGNORECASE)),
    # 负向预查只挡数字/小数点；不能用 \w（Unicode 下中文算 \w，"存活率45%"会漏）。
    ("percent", re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*%")),
]
SAMPLE_SIZE_PATTERN = ("sample_size", re.compile(r"\bn\s*=\s*(\d+)\b", re.IGNORECASE))

# 标签词必须紧贴数值：只在数值左侧这个字符窗口内找标签词，杜绝远处动作短语误判。
LABEL_WINDOW = 14

REF_HEADING = re.compile(
    r"^\s*#{0,6}\s*(references?|bibliography|参考文献|引用文献)\b", re.IGNORECASE
)
HEADING = re.compile(r"^\s*#{1,6}\s+\S")
CITATION_BRACKET = re.compile(r"\[[\d,\s\-–]+\]")

_EN_WORD = r"[A-Za-z][A-Za-z\-]{2,}"
_CN_WORD = r"[一-鿿]{2,}"
LABEL_TOKEN = re.compile(rf"({_EN_WORD}|{_CN_WORD})")

# 中文科学指标词：以指标后缀结尾，前缀 1-4 个非词边界汉字。词边界字（组/的/为/
# 在/末/后…）切断"实验组存活率"粘连，使跨段只对齐核心指标"存活率"。
_CN_METRIC_SUFFIX = "率|量|数|度|比|值|积|长|力|效|径|温|压|龄"
_CN_BOUNDARY = "当组的为在与和至末后则该经被将于由从把对及或者之其此该每各"
CN_METRIC_TOKEN = re.compile(
    rf"((?:(?![{_CN_BOUNDARY}])[一-鿿]){{1,4}}(?:{_CN_METRIC_SUFFIX}))"
)

# 连接词：可跳过的虚词/动词，本身不作标签核心，但夹在指标词之间不阻断短语。
# rate/level/ratio 等**不在**此列——它们是指标名核心（survival vs response rate）。
CONNECTOR_WORDS = {
    "the", "and", "for", "with", "was", "were", "are", "is", "that", "this",
    "approximately", "about", "than", "from", "into", "between", "respectively",
    "increased", "decreased", "reduced", "showed", "shown", "compared", "reached",
    "remained", "overall", "around", "only", "still", "also", "had", "has",
    "observed", "measured", "found", "being", "been", "which", "their", "its",
    "cohort", "group", "groups", "treated", "control",
}

# 标签黑名单：实验操作参数（接种密度/汇合度/洗涤时长…）而非结果指标，不同步骤
# 本就允许不同数值 → 不报，避免操作参数刷假嫌疑。
LABEL_BLOCKLIST = {
    "细胞密度", "接种密度", "密度", "汇合度", "融合度", "饱和度",
    "min pbs", "pbs", "min", "rpm", "transwell",
}


def normalize_label(token: str) -> str:
    t = token.strip().lower()
    if re.fullmatch(_EN_WORD, token) and len(t) > 3 and t.endswith("s"):
        t = t[:-1]
    return t


def collect_manuscript_files(root: str, drafts_dir: str) -> list[str]:
    """扫改稿章节：<root>/<drafts_dir>/*.md。排除 _deprecated/ 与合并稿。"""
    pattern = os.path.join(root, drafts_dir, "*.md")
    files = sorted(glob.glob(pattern))
    out = []
    for f in files:
        base = os.path.basename(f).lower()
        # 排除合并稿 / 派生物（与 gsw 对齐的命名约定）。
        if base in ("full_manuscript.md", "merged.md", "final.md"):
            continue
        if base.startswith("draft_round"):
            continue
        out.append(f)
    return out


def split_body_lines(content: str) -> list[str]:
    """逐行返回正文行，剔除 References/参考文献 段（标题→下一个标题之间）。

    revise 的 section_*.md 每章自带 '## References' 块，必须剔除（块内全是
    PMID / 编号噪声，否则跨章 PMID 数字会刷出海量假嫌疑）。
    """
    out: list[str] = []
    in_ref = False
    for line in content.splitlines():
        if REF_HEADING.match(line):
            in_ref = True
            continue
        if in_ref:
            if HEADING.match(line) and not REF_HEADING.match(line):
                in_ref = False
            else:
                continue
        out.append(line)
    return out


def _cn_label(text_before: str) -> str | None:
    """中文：取数值左侧紧邻的最后一个『指标词』（以率/量/度/比/值…结尾）。

    中文无空格，贪婪分词会把"存活率"粘进"实验组存活率为"无法跨段对齐；改按指标
    后缀抓词，取末尾紧邻的 CN_METRIC_TOKEN 匹配，要求紧邻数值。
    """
    n = len(text_before)
    matches = list(CN_METRIC_TOKEN.finditer(text_before))
    if not matches:
        return None
    last = matches[-1]
    if n - last.end() > LABEL_WINDOW:
        return None
    return last.group(1)


def label_for(text_before: str) -> str | None:
    """取数值左侧**紧邻**的指标短语作标签（归一化）。无则 None。

    中文优先 _cn_label；英文向左收集指标词跳过连接虚词，最多 2 词拼短语
    （survival rate vs response rate 可区分），最近词须紧邻数值否则 None。
    """
    cn = _cn_label(text_before)
    if cn is not None:
        return None if cn in LABEL_BLOCKLIST else cn

    n = len(text_before)
    tokens = [m for m in LABEL_TOKEN.finditer(text_before)
              if re.fullmatch(_EN_WORD, m.group(1))]
    content_words: list[str] = []
    seen_content_near = False
    for m in reversed(tokens):
        norm = normalize_label(m.group(1))
        if norm in CONNECTOR_WORDS:
            if not seen_content_near:
                if n - m.end() > LABEL_WINDOW:
                    break
                continue
            break
        if not seen_content_near:
            if n - m.end() > LABEL_WINDOW:
                break
            seen_content_near = True
        content_words.append(norm)
        if len(content_words) >= 2:
            break
    if content_words:
        label = " ".join(reversed(content_words))
        return None if label in LABEL_BLOCKLIST else label
    return None


def extract_pairs(files: list[str], patterns: list) -> list[dict]:
    pairs: list[dict] = []
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            continue
        fname = os.path.basename(fp)
        for lineno, raw in enumerate(split_body_lines(content), start=1):
            line = CITATION_BRACKET.sub(" ", raw)
            if not line.strip():
                continue
            for kind, pat in patterns:
                for m in pat.finditer(line):
                    value = m.group(1)
                    before = line[: m.start()]
                    label = label_for(before)
                    if label is None:
                        continue
                    pairs.append({
                        "label": label,
                        "kind": kind,
                        "value": value,
                        "location": f"{fname}:L{lineno}",
                        "context": line.strip()[:160],
                    })
    return pairs


def cluster_suspicions(pairs: list[dict]) -> list[dict]:
    by_key: dict[tuple[str, str], list[dict]] = {}
    for p in pairs:
        by_key.setdefault((p["label"], p["kind"]), []).append(p)

    suspicions: list[dict] = []
    for (label, kind), items in by_key.items():
        value_to_item: dict[str, dict] = {}
        for it in items:
            value_to_item.setdefault(it["value"], it)
        distinct_values = list(value_to_item.keys())
        if len(distinct_values) < 2:
            continue
        distinct_locs = {it["location"] for it in value_to_item.values()}
        if len(distinct_locs) < 2:
            continue
        suspicions.append({
            "label": label,
            "kind": kind,
            "values": [
                {
                    "value": value_to_item[v]["value"],
                    "location": value_to_item[v]["location"],
                    "context": value_to_item[v]["context"],
                }
                for v in distinct_values
            ],
        })
    suspicions.sort(key=lambda s: (s["kind"], s["label"]))
    return suspicions


def main() -> int:
    parser = argparse.ArgumentParser(
        description="跨段数值一致性检查（WARN 级，扫改稿章节 drafts/*.md）。"
    )
    parser.add_argument("--project-root", required=True,
                        help="project root，含改稿章节目录")
    parser.add_argument("--drafts-dir", default="drafts",
                        help="改稿章节目录名（相对 project-root，默认 drafts）")
    parser.add_argument("--json", action="store_true",
                        help="仅输出 JSON（默认也输出 JSON + 人读摘要行）")
    parser.add_argument("--include-sample-size", action="store_true",
                        help="额外扫 n=<int> 样本量（默认关闭，噪声高）")
    args = parser.parse_args()

    root = os.path.abspath(args.project_root)
    if not os.path.isdir(root):
        print(json.dumps({"suspicions": [], "files_scanned": 0,
                          "summary": f"root not a directory: {root}"}))
        return 0

    patterns = list(VALUE_PATTERNS)
    if args.include_sample_size:
        patterns.append(SAMPLE_SIZE_PATTERN)

    files = collect_manuscript_files(root, args.drafts_dir)
    pairs = extract_pairs(files, patterns)
    suspicions = cluster_suspicions(pairs)

    result = {
        "suspicions": suspicions,
        "files_scanned": len(files),
        "summary": (
            f"{len(suspicions)} suspected cross-section numeric drift(s) "
            f"across {len(files)} file(s); WARN only, review needed."
        ),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not args.json and suspicions:
        print("XSEC_CONSISTENCY_WARN: 疑似跨段数值不一致（需人/AI 复核，未硬拦）:",
              file=sys.stderr)
        for s in suspicions:
            vals = " | ".join(f"{v['value']}@{v['location']}" for v in s["values"])
            print(f"  [{s['kind']}] {s['label']}: {vals}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
