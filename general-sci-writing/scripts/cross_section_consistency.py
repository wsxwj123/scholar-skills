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
  python3 cross_section_consistency.py --root <project_root>
扫 <root>/manuscripts/*.md（排除合并稿 full_manuscript.md / Draft_Round*）。
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
# 默认只扫 percent + p_value（高置信、低噪声）。
# sample_size(n=) 默认**关闭**：真稿里不同图/不同实验的样本量本就允许不同，
# 跨段聚类会刷出海量合法差异的假嫌疑；n 改错又罕见，漏报代价低。需要时用
# --include-sample-size 显式开启（B2 场景）。
VALUE_PATTERNS = [
    # p 值 p<0.05 / p = 0.001
    ("p_value", re.compile(r"\bp\s*[<=>]\s*(0?\.\d+)\b", re.IGNORECASE)),
    # 百分比 45% / 47.3%。负向预查只挡数字/小数点（防止 12.5% 里 5 被单独抓），
    # 不能用 \w——Unicode 下中文算 \w，会让"存活率45%"这种中文紧贴数字时漏匹配。
    ("percent", re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*%")),
]
SAMPLE_SIZE_PATTERN = ("sample_size", re.compile(r"\bn\s*=\s*(\d+)\b", re.IGNORECASE))

# 标签词必须紧贴数值：只在数值左侧这个字符窗口内找标签词。窗口外的词（多为
# 远处的实验动作短语）一律不作标签 → 杜绝"加入/培养至…"这类垃圾标签误报。
LABEL_WINDOW = 14

# References / 参考文献 段标题：命中后该段及之后到下一个一级标题之间视为引用区，
# 整段跳过（PMID、编号、卷期页码全是数字噪声）。
REF_HEADING = re.compile(
    r"^\s*#{0,6}\s*(references?|bibliography|参考文献|引用文献)\b", re.IGNORECASE
)
# 一级/二级标题（用于判断引用区结束）。
HEADING = re.compile(r"^\s*#{1,6}\s+\S")

# 裸引用号 [12] / [3-6] / [171,209]：剥掉，避免把引用编号当数值。
CITATION_BRACKET = re.compile(r"\[[\d,\s\-–]+\]")

# 标签词候选：数值紧邻**前侧**的上下文关键词。
#   英文：≥3 字母的词（survival / rate / efficiency ...），允许连字符。
#   中文：≥2 个中日韩统一表意文字（存活率 / 降解效率 ...）。
# 单字母 / 纯数字 / 1-2 字母缩写不作标签（噪声太大）。
_EN_WORD = r"[A-Za-z][A-Za-z\-]{2,}"
_CN_WORD = r"[一-鿿]{2,}"
LABEL_TOKEN = re.compile(rf"({_EN_WORD}|{_CN_WORD})")

# 中文科学指标词：以典型指标后缀结尾（率/量/数/度/比/值/积/活力/效率 …），前缀
# 1-4 个**非词边界**汉字。词边界字（组/的/为/在/与/和/至/末/后/则/该/经/被/将…）
# 用于切断"实验组存活率"这类粘连，使跨段只对齐核心指标"存活率"。非贪婪取最短，
# 配合 finditer 取末尾紧邻匹配 → 稳定跨段对齐。
_CN_METRIC_SUFFIX = "率|量|数|度|比|值|积|长|力|效|径|温|压|龄"
# 词边界/虚词字：不进入指标词前缀。
_CN_BOUNDARY = "当组的为在与和至末后则该经被将于由从把对及或者之其此该每各"
CN_METRIC_TOKEN = re.compile(
    rf"((?:(?![{_CN_BOUNDARY}])[一-鿿]){{1,4}}(?:{_CN_METRIC_SUFFIX}))"
)

# 连接词：可被跳过的虚词/动词，本身不作标签核心，但夹在两个指标词之间时不阻断
# 短语（如 "survival rate was 45%" 里的 was）。注意 rate/level/ratio 等**不在**
# 此列——它们是指标名的核心成分（survival rate vs response rate 靠它们区分）。
CONNECTOR_WORDS = {
    "the", "and", "for", "with", "was", "were", "are", "is", "that", "this",
    "approximately", "about", "than", "from", "into", "between", "respectively",
    "increased", "decreased", "reduced", "showed", "shown", "compared", "reached",
    "remained", "overall", "around", "only", "still", "also", "had", "has",
    "observed", "measured", "found", "being", "been", "which", "their", "its",
    "cohort", "group", "groups", "treated", "control",
}

# 标签黑名单：这些是**实验操作参数**而非结果指标，不同步骤本就允许不同数值
# （细胞接种密度、培养汇合度、洗涤时长…）。命中 → 不报，避免操作参数刷假嫌疑。
LABEL_BLOCKLIST = {
    "细胞密度", "接种密度", "密度", "汇合度", "融合度", "饱和度",
    "min pbs", "pbs", "min", "rpm", "transwell",
}


def normalize_label(token: str) -> str:
    """归一化标签词：小写、去尾复数 's'。中文原样。"""
    t = token.strip().lower()
    if re.fullmatch(_EN_WORD, token) and len(t) > 3 and t.endswith("s"):
        t = t[:-1]  # survival rates -> survival rate（粗糙单复数归一）
    return t


def collect_manuscript_files(root: str) -> list[str]:
    pattern = os.path.join(root, "manuscripts", "*.md")
    files = sorted(glob.glob(pattern))
    return [
        f for f in files
        if os.path.basename(f).lower() != "full_manuscript.md"
        and not os.path.basename(f).startswith("Draft_Round")
    ]


def split_body_lines(content: str) -> list[str]:
    """逐行返回正文行，剔除 References/参考文献 段（标题→下一个标题之间）。"""
    out: list[str] = []
    in_ref = False
    for line in content.splitlines():
        if REF_HEADING.match(line):
            in_ref = True
            continue
        if in_ref:
            # 引用区在下一个普通标题处结束（非 references 标题）。
            if HEADING.match(line) and not REF_HEADING.match(line):
                in_ref = False
            else:
                continue
        out.append(line)
    return out


def _cn_label(text_before: str) -> str | None:
    """中文：取数值左侧紧邻的最后一个『指标词』（以率/量/度/比/值…结尾）。

    中文无空格，贪婪分词会把"存活率"粘进"实验组存活率为"，跨段无法对齐。改为
    按指标后缀抓词：取末尾紧邻的 CN_METRIC_TOKEN 匹配（≤5 字 + 指标后缀），既稳又
    能跨段相等。要求该词紧邻数值（结束位置距数值 ≤ LABEL_WINDOW）。
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

    中文优先：先按指标后缀抓最近的中文指标词（_cn_label）。
    英文：从数值向左收集指标词，跳过连接虚词（CONNECTOR_WORDS），最多取 2 个拼成
    短语（survival rate vs response rate 可区分）；最近指标词须紧邻数值，否则 None。
    """
    cn = _cn_label(text_before)
    if cn is not None:
        return None if cn in LABEL_BLOCKLIST else cn

    n = len(text_before)
    # 只取英文 token（中文已在上面处理）。
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
    """返回 [{label, kind, value, location, context}]，每个带标签的数值一条。"""
    pairs: list[dict] = []
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            continue
        fname = os.path.basename(fp)
        for lineno, raw in enumerate(split_body_lines(content), start=1):
            line = CITATION_BRACKET.sub(" ", raw)  # 去裸引用号
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
    """同 (label, kind) 跨**不同位置**出现**不同 value** → 嫌疑。

    保守：
      - 同一行内的同标签数值不算跨段（如 "分别为 45% 和 47%" 是并列，非漂移）。
      - 至少 2 个不同 value 且分布在 ≥2 个不同位置才报。
    """
    by_key: dict[tuple[str, str], list[dict]] = {}
    for p in pairs:
        by_key.setdefault((p["label"], p["kind"]), []).append(p)

    suspicions: list[dict] = []
    for (label, kind), items in by_key.items():
        # 每个独特 value 取首个出现位置代表。
        value_to_item: dict[str, dict] = {}
        for it in items:
            value_to_item.setdefault(it["value"], it)
        distinct_values = list(value_to_item.keys())
        if len(distinct_values) < 2:
            continue
        # 必须分布在 ≥2 个不同位置（行）才算跨段漂移。
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


# ---------------------------------------------------------------------------
# 双向 section 对账（--reconcile-sections）：storyline.json 的 section_id ↔
# manuscripts/*.md 文件。报告式：正向找孤儿（manuscripts 有、storyline 没有）、
# 反向找漏建（storyline 有、manuscripts 缺）。有差异 exit 1，全齐 exit 0。
# gsw 文件名不强绑 section_id（04_Results_3.1_Characterization.md ↔ results_3.1），
# 故映射用「文件名边界匹配 或 文件内容含该 section_id 字符串」双信号。
# ---------------------------------------------------------------------------
def load_storyline_section_ids(root: str) -> list[str]:
    """storyline.json 的 sections[].id（fallback section_id），保序去空。"""
    path = os.path.join(root, "storyline.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    out: list[str] = []
    for item in payload.get("sections") or []:
        if isinstance(item, dict):
            sid = item.get("id") or item.get("section_id")
            if sid:
                out.append(str(sid))
    return out


def _section_terms(section: str) -> set[str]:
    raw = section.strip().lower()
    return {v for v in {raw, raw.replace("_", "."), raw.replace(".", "_"),
                        raw.replace("-", "_"), raw.replace("-", ".")} if v}


def _file_covers_section(basename: str, content: str, section: str) -> bool:
    """文件是否覆盖该 section_id：文件名边界匹配 或 正文含 section_id 变体。"""
    base = basename.lower()
    body = content.lower()
    for term in sorted(_section_terms(section), key=len, reverse=True):
        esc = re.escape(term)
        if re.search(rf"(^|[_\-.]){esc}([_\-.]|$)", base):
            return True
        if term in body:
            return True
    return False


def reconcile_sections(root: str) -> dict:
    section_ids = load_storyline_section_ids(root)
    files = collect_manuscript_files(root)
    file_contents: dict[str, str] = {}
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                file_contents[fp] = f.read()
        except OSError:
            file_contents[fp] = ""

    # 反向：storyline 有、manuscripts 缺（漏建）。
    missing = [
        sid for sid in section_ids
        if not any(_file_covers_section(os.path.basename(fp), c, sid)
                   for fp, c in file_contents.items())
    ]
    # 正向：manuscripts 有、storyline 没有（孤儿）——文件不匹配任何 section_id。
    orphans = [
        os.path.basename(fp) for fp, c in file_contents.items()
        if not any(_file_covers_section(os.path.basename(fp), c, sid)
                   for sid in section_ids)
    ]
    return {
        "storyline_section_ids": section_ids,
        "manuscript_files": [os.path.basename(fp) for fp in files],
        "missing_in_manuscripts": missing,   # storyline 有、稿子缺
        "orphan_manuscripts": orphans,       # 稿子有、storyline 无
        "ok": not missing and not orphans,
    }


def run_reconcile(root: str) -> int:
    if not os.path.isdir(root):
        print(json.dumps({"ok": False, "summary": f"root not a directory: {root}"}))
        return 1
    r = reconcile_sections(root)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    if r["ok"]:
        print("SECTION_RECONCILE_OK: storyline 与 manuscripts 一一对应。", file=sys.stderr)
        return 0
    if r["missing_in_manuscripts"]:
        print("SECTION_RECONCILE_MISSING（storyline 有、稿子漏建）: "
              + ", ".join(r["missing_in_manuscripts"]), file=sys.stderr)
    if r["orphan_manuscripts"]:
        print("SECTION_RECONCILE_ORPHAN（稿子有、storyline 未列）: "
              + ", ".join(r["orphan_manuscripts"]), file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="跨段数值一致性检查（WARN 级，扫 manuscripts/*.md）。"
    )
    parser.add_argument("--root", required=True,
                        help="project root，含 manuscripts/")
    parser.add_argument("--json", action="store_true",
                        help="仅输出 JSON（默认也输出 JSON + 人读摘要行）")
    parser.add_argument("--include-sample-size", action="store_true",
                        help="额外扫 n=<int> 样本量（默认关闭，噪声高）")
    parser.add_argument("--reconcile-sections", action="store_true",
                        help="双向对账 storyline.json section_id ↔ manuscripts/*.md："
                             "报漏建/孤儿；有差异 exit 1，全齐 exit 0（报告式，非门禁）")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    if args.reconcile_sections:
        return run_reconcile(root)

    if not os.path.isdir(root):
        print(json.dumps({"suspicions": [], "files_scanned": 0,
                          "summary": f"root not a directory: {root}"}))
        return 0  # WARN 级，永不硬拦

    patterns = list(VALUE_PATTERNS)
    if args.include_sample_size:
        patterns.append(SAMPLE_SIZE_PATTERN)

    files = collect_manuscript_files(root)
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
    return 0  # 始终 WARN 级


if __name__ == "__main__":
    sys.exit(main())
