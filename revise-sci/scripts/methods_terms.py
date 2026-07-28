#!/usr/bin/env python3
"""方法术语命中（方法学一致性核查·第 1 层**弱锚焦点图**，reviewer-simulator 本家非共享）。

拿内置实验方法术语词典客观扫全稿，输出"稿子里哪些方法术语字面出现在哪些句、落在哪个
region、命中句是否邻接图引用"，外加"方法学章节下有哪些小节标题"，写
<project-root>/methods_terms.json + stdout 末行摘要 JSON。

**这是弱锚，不是权威真值**（顶层 authority="weak_focus_map"）——结果侧"用了什么方法"一般无
字面 token（是语义），故本脚本**只报命中、只标注，从不判任何方法是否漏写、是否本研究做的**。
判断主体 100% 在第 2 层 LLM 视角⑦ + 第 3 层反向验证。词典求高精准+覆盖常见、不求穷尽，词典
外方法由第 2 层 LLM 语义补。

复用同目录 manuscript_index.py（8 家逐字节共享文件，绝不改，只 import）的读稿/区分正文与参考
区/图正则能力；复用 numeric_candidates.py 的 region 检测/断句/逐行读 md；复用
structure_outline.py 的小节标题解析（三者皆 import 非修改，绝不改被 import 的脚本）。

CLI:
  python methods_terms.py --manuscript <docx|md|markdown|txt> --project-root <root>

退出码：0=正常（含空稿/无命中）；2=用法/输入错（缺参 / 文件不存在 / 不支持类型 / 解析失败）。
契约见 .devflow/INTERFACE-methods-consistency.md §1。
"""
import sys as _sys
try:  # Windows GBK 控制台/管道捕获下防 UnicodeEncodeError
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

# manuscript_index.py 是 8 家逐字节共享文件，绝不改，只 import 复用其读稿层/图正则。
from manuscript_index import (
    normalize_ws,
    write_json,
    read_manuscript_paragraphs,
    reference_section_spans,
    body_row_indices,
    is_heading,
    FIG_INTEXT_RE,
    FIG_CAPTION_RE,
    FIG_BARE_RE,
)
# numeric_candidates / structure_outline 是本家非共享脚本，import 复用其 region/断句/小节解析
# （复用非修改，绝不改这两个脚本）。
from numeric_candidates import _match_region, read_md_lines, _split_sentences
from structure_outline import (
    _split_number_title,
    _passes_section_guardrails,
    TABLE_CAPTION_RE,
    TABLE_BARE_RE,
)

SUPPORTED_SUFFIXES = {".docx", ".md", ".markdown", ".txt"}

# ---------------------------------------------------------------------------
# 内置方法术语词典（~24 个常见实验方法，每方法一簇别名，以 manuscript_index
# UNIVERSAL_ABBREVIATIONS 的 PCR/ELISA/FACS/... 为种子扩）。三类别名分开存以配不同匹配护栏：
#   cn   —— 中文别名，无边界歧义 → 直接子串命中（case-sensitive）
#   abbr —— 大写缩写/带数字缩写 → CJK-aware 字母数字边界匹配（case-sensitive，避免 IF 命中英文 if）
#   en   —— 英文词/词组 → 字母边界匹配（case-insensitive）
# canonical 为归一键：同一方法的中英别名归到同一 canonical，供第 2/3 层跨表述聚合。
# ---------------------------------------------------------------------------
METHOD_DICT: dict[str, dict[str, list[str]]] = {
    "flow_cytometry": {
        "cn": ["流式细胞术", "流式细胞仪", "流式分析"],
        "abbr": ["FACS"],
        "en": ["flow cytometry"],
    },
    "western_blot": {
        "cn": ["免疫印迹", "蛋白质印迹", "蛋白印迹"],
        "abbr": ["WB"],
        "en": ["western blotting", "western blot", "immunoblotting", "immunoblot"],
    },
    "qpcr": {
        "cn": ["实时荧光定量PCR", "实时定量PCR", "荧光定量PCR", "定量PCR"],
        "abbr": ["RT-qPCR", "qRT-PCR", "qPCR", "QPCR", "RT-PCR"],
        "en": ["real-time pcr", "real time pcr", "quantitative pcr"],
    },
    "pcr": {
        "cn": ["聚合酶链式反应", "聚合酶链反应"],
        "abbr": ["PCR"],
        "en": ["polymerase chain reaction"],
    },
    "ihc": {
        "cn": ["免疫组织化学", "免疫组化"],
        "abbr": ["IHC"],
        "en": ["immunohistochemistry", "immunohistochemical"],
    },
    "immunofluorescence": {
        "cn": ["免疫荧光"],
        "abbr": ["IF"],
        "en": ["immunofluorescence"],
    },
    "elisa": {
        "cn": ["酶联免疫吸附"],
        "abbr": ["ELISA"],
        "en": [],
    },
    "sequencing": {
        "cn": ["高通量测序", "转录组测序", "单细胞测序", "测序"],
        "abbr": ["RNA-seq", "scRNA-seq", "RNA-Seq", "scRNA-Seq"],
        "en": ["sequencing", "rna sequencing"],
    },
    "immunoprecipitation": {
        "cn": ["免疫共沉淀", "免疫沉淀"],
        "abbr": ["Co-IP", "co-IP", "CoIP", "IP"],
        "en": ["immunoprecipitation", "co-immunoprecipitation"],
    },
    "chip": {
        "cn": ["染色质免疫沉淀"],
        "abbr": ["ChIP", "CHIP"],
        "en": ["chromatin immunoprecipitation"],
    },
    "cck8": {
        "cn": [],
        "abbr": ["CCK-8", "CCK8"],
        "en": [],
    },
    "mtt": {
        "cn": [],
        "abbr": ["MTT"],
        "en": [],
    },
    "transwell": {
        "cn": ["小室实验"],
        "abbr": ["Transwell"],
        "en": ["transwell"],
    },
    "wound_healing": {
        "cn": ["细胞划痕实验", "划痕实验", "划痕"],
        "abbr": [],
        "en": ["wound healing"],
    },
    "confocal": {
        "cn": ["激光共聚焦", "共聚焦"],
        "abbr": [],
        "en": ["confocal"],
    },
    "mass_spec": {
        "cn": ["质谱分析", "质谱"],
        "abbr": ["LC-MS", "LC-MS/MS", "MS/MS", "MS"],
        "en": ["mass spectrometry"],
    },
    "tunel": {
        "cn": [],
        "abbr": ["TUNEL"],
        "en": [],
    },
    "he_staining": {
        "cn": ["苏木素伊红染色", "苏木精伊红", "苏木素伊红", "HE染色"],
        "abbr": [],
        "en": ["h&e staining", "he staining"],
    },
    "animal_experiment": {
        "cn": ["动物实验", "移植瘤", "裸鼠", "荷瘤"],
        "abbr": [],
        "en": ["xenograft", "animal experiment"],
    },
    "colony_formation": {
        "cn": ["克隆形成", "集落形成", "平板克隆"],
        "abbr": [],
        "en": ["colony formation"],
    },
    "transfection": {
        "cn": ["转染"],
        "abbr": ["siRNA", "shRNA"],
        "en": ["transfection"],
    },
    "luciferase": {
        "cn": ["双荧光素酶", "荧光素酶报告"],
        "abbr": [],
        "en": ["luciferase", "dual-luciferase"],
    },
    "electron_microscopy": {
        "cn": ["透射电镜", "扫描电镜", "电子显微镜"],
        "abbr": ["TEM", "SEM"],
        "en": ["electron microscopy"],
    },
    "edu": {
        "cn": [],
        "abbr": ["EdU", "EDU"],
        "en": [],
    },
}


def _build_matchers(method_dict: dict[str, dict[str, list[str]]]):
    """把词典编译成三条合并正则（cn/abbr/en 各一），扫描一句 = 定数次 finditer（O(句长)），
    与词典大小无关 —— 避免 O(词典×文本) 的逐词重扫。alternation 按别名长度降序排，让
    finditer 在同一位置优先吃最长别名（RT-PCR 先于 PCR）。返回 (cn_re, cn_map, abbr_re,
    abbr_map, en_re, en_map)；某类别为空时对应 re 为 None。"""
    cn_pairs, abbr_pairs, en_pairs = [], [], []
    for canon, groups in method_dict.items():
        for a in groups.get("cn", []):
            cn_pairs.append((a, canon))
        for a in groups.get("abbr", []):
            abbr_pairs.append((a, canon))
        for a in groups.get("en", []):
            en_pairs.append((a, canon))
    cn_pairs.sort(key=lambda x: -len(x[0]))
    abbr_pairs.sort(key=lambda x: -len(x[0]))
    en_pairs.sort(key=lambda x: -len(x[0]))

    cn_map = {a: c for a, c in cn_pairs}
    abbr_map = {a: c for a, c in abbr_pairs}
    en_map = {a.lower(): c for a, c in en_pairs}

    cn_re = (re.compile("|".join(re.escape(a) for a, _ in cn_pairs))
             if cn_pairs else None)
    # CJK-aware 字母数字边界：WB 不吃 WBC 子串、IP 不吃 IPTG，但兼容中文相邻（用WB检测）。
    abbr_re = (re.compile(r"(?<![A-Za-z0-9])(?:"
                          + "|".join(re.escape(a) for a, _ in abbr_pairs)
                          + r")(?![A-Za-z0-9])")
               if abbr_pairs else None)
    # 英文词/词组：字母边界（IF 走 abbr 不进这里；en 里都是多字符词，case-insensitive）。
    en_re = (re.compile(r"(?<![A-Za-z])(?:"
                        + "|".join(re.escape(a) for a, _ in en_pairs)
                        + r")(?![A-Za-z])", re.IGNORECASE)
             if en_pairs else None)
    return cn_re, cn_map, abbr_re, abbr_map, en_re, en_map


_CN_RE, _CN_MAP, _ABBR_RE, _ABBR_MAP, _EN_RE, _EN_MAP = _build_matchers(METHOD_DICT)


def _scan_methods(sent: str) -> list[tuple[str, str]]:
    """扫一句里所有方法术语命中，返回按出现序的 [(term_原文, canonical), ...]。

    三类正则各 finditer 一次，合并后按 (start 升序, 长度降序) 解重叠：同一文本片段被跨类别
    或长短别名重复命中时只留最长/最靠前一条（防 RT-PCR 又被切出 PCR 双计）。同一 canonical
    在不同位置的多次命中**不去重**（各自 start 不重叠），照契约各列一条。
    """
    raw: list[tuple[int, int, str, str]] = []
    if _CN_RE:
        for m in _CN_RE.finditer(sent):
            raw.append((m.start(), m.end(), m.group(), _CN_MAP[m.group()]))
    if _ABBR_RE:
        for m in _ABBR_RE.finditer(sent):
            raw.append((m.start(), m.end(), m.group(), _ABBR_MAP[m.group()]))
    if _EN_RE:
        for m in _EN_RE.finditer(sent):
            raw.append((m.start(), m.end(), m.group(), _EN_MAP[m.group().lower()]))
    raw.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    out: list[tuple[str, str]] = []
    last_end = -1
    for s, e, term, canon in raw:
        if s >= last_end:  # 与已保留命中不重叠才收（重叠的更短/更后者丢弃）
            out.append((term, canon))
            last_end = e
    return out


def _extract_methods_sections(rows: list[dict[str, Any]],
                              body_indices: list[int]) -> list[dict[str, Any]]:
    """Methods 区段下的小节标题清单：region 跟踪到 Methods 时，正文区里 heading 样式或
    过护栏的裸编号行进清单（复用 structure_outline 的小节判定，图/表题注不算）。"""
    body_set = set(body_indices)
    out: list[dict[str, Any]] = []
    current_region = "Body"
    for idx, row in enumerate(rows):
        text = normalize_ws(row.get("text", ""))
        reg = _match_region(text)
        if reg:
            current_region = reg
        if idx not in body_set or not text or current_region != "Methods":
            continue
        if (FIG_CAPTION_RE.match(text) or TABLE_CAPTION_RE.match(text)
                or FIG_BARE_RE.match(text) or TABLE_BARE_RE.match(text)):
            continue
        style = (row.get("style_name", "") or "").lower()
        number, title = _split_number_title(text)
        if style.startswith("heading"):
            is_section = True
        elif number is not None:
            is_section = _passes_section_guardrails(text)
        else:
            is_section = False
        if not is_section:
            continue
        out.append({
            "number": number,
            "title": title,
            "para_index": row.get("paragraph_index"),
        })
    return out


def _read_docx_table_cells(path: Path) -> list[tuple[str, str]]:
    """遍历 docx 表格单元格，返回 [(cell_text, region)]。region 由文档序里就近的区段标题推断。

    直接按文档序遍历底层 w:tr/w:tc XML（不碰 python-docx row.cells/cell._tc，避免合并单元格
    重复返回 + lxml 瞬时代理 id() 复用致 flaky，照 numeric_candidates._read_docx_tables 纪律）。
    """
    from docx import Document
    from docx.oxml.ns import qn

    w_p, w_tbl, w_tr, w_tc, w_t = (qn("w:p"), qn("w:tbl"), qn("w:tr"),
                                   qn("w:tc"), qn("w:t"))

    def _el_text(el) -> str:
        return normalize_ws("".join(t.text or "" for t in el.iter(w_t)))

    doc = Document(str(path))
    out: list[tuple[str, str]] = []
    region = "Body"
    for child in doc.element.body.iterchildren():
        if child.tag == w_p:
            text = _el_text(child)
            if not text:
                continue
            reg = _match_region(text)
            if reg:
                region = reg
        elif child.tag == w_tbl:
            for tr in child.findall(w_tr):  # 直接子 w:tr，不下钻嵌套表
                for tc in tr.findall(w_tc):
                    ct = _el_text(tc)
                    if ct:
                        out.append((ct, region))
    return out


def build_methods_terms(manuscript_path: Path) -> dict[str, Any]:
    suffix = manuscript_path.suffix.lower()
    if suffix in {".md", ".markdown", ".txt"}:
        rows = read_md_lines(manuscript_path)
    else:
        rows = read_manuscript_paragraphs(manuscript_path)

    ref_spans = reference_section_spans(rows)
    body_indices = body_row_indices(rows, ref_spans)
    body_set = set(body_indices)

    # (term, canonical, region, sentence, para_index, source, has_figure_adjacent)
    raw_hits: list[tuple[str, str, str, str, Optional[int], str, bool]] = []
    current_region = "Body"
    for idx, row in enumerate(rows):
        text = normalize_ws(row.get("text", ""))
        reg = _match_region(text)
        if reg:
            current_region = reg
        # 参考区外 + 非小标题行才扫（小标题命中噪音大、且方法学小节标题另列 methods_sections）。
        if idx not in body_set or is_heading(row):
            continue
        para_index = row.get("paragraph_index")
        for sent in _split_sentences(text):
            has_fig = bool(FIG_INTEXT_RE.search(sent))
            sent_norm = normalize_ws(sent)
            for term, canon in _scan_methods(sent):
                raw_hits.append((term, canon, current_region, sent_norm,
                                 para_index, "body", has_fig))

    if suffix == ".docx":
        for cell_text, region in _read_docx_table_cells(manuscript_path):
            for sent in _split_sentences(cell_text):
                has_fig = bool(FIG_INTEXT_RE.search(sent))
                sent_norm = normalize_ws(sent)
                for term, canon in _scan_methods(sent):
                    raw_hits.append((term, canon, region, sent_norm,
                                     None, "table", has_fig))

    method_hits: list[dict[str, Any]] = []
    for i, (term, canon, region, sent, para, source, has_fig) in enumerate(raw_hits, 1):
        method_hits.append({
            "id": f"mth-{i:04d}",
            "term": term,
            "canonical": canon,
            "region": region,
            "sentence": sent,
            "location": {"para_index": para, "source": source},
            "has_figure_adjacent": has_fig,
        })

    methods_sections = _extract_methods_sections(rows, body_indices)
    distinct = len({h["canonical"] for h in method_hits})

    return {
        "authority": "weak_focus_map",
        "method_hits": method_hits,
        "methods_sections": methods_sections,
        "summary": {
            "method_hits": len(method_hits),
            "distinct_canonical": distinct,
            "methods_sections": len(methods_sections),
            # 弱锚失效信号（纯提示、退出码不变）：有方法词命中却一个方法学小节都没认出，
            # 多半是该稿方法学小节名不在 _REGION_KEYS 词表内 → region 全程停 Body、下游
            # 章范围门的兜底判据把每章都判"无方法学结构→跳过"、方法学核查静默空转。
            # 判据下沉到脚本（确定性），主 agent 读这个布尔量告警、不再自己算。
            # method_hits==0（通篇无方法词）是正常空结果，恒为 false。
            "weak_anchor_suspect": bool(method_hits) and not methods_sections,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="扫全稿命中方法术语，当方法学一致性核查第 1 层弱锚焦点图。"
    )
    parser.add_argument("--manuscript", required=True, help="成稿路径（docx / md / markdown / txt）。")
    parser.add_argument("--project-root", required=True, help="输出根目录，methods_terms.json 写这里。")
    args = parser.parse_args()

    manuscript_path = Path(args.manuscript).expanduser().resolve()
    project_root = Path(args.project_root).expanduser().resolve()

    # 用法/输入错：显式 sys.exit(2)（不用 raise SystemExit(字符串)，那会变 exit 1）。
    if not manuscript_path.exists():
        print(f"manuscript not found: {manuscript_path}", file=sys.stderr)
        sys.exit(2)
    if manuscript_path.suffix.lower() not in SUPPORTED_SUFFIXES:
        print(f"unsupported manuscript type: {manuscript_path.suffix}", file=sys.stderr)
        sys.exit(2)

    # 解析失败（损坏/加密/空包 docx、编码错等）套 try/except 兜成 exit 2，禁止裸抛成 exit 1。
    try:
        result = build_methods_terms(manuscript_path)
    except Exception as exc:  # noqa: BLE001  # 契约要求：解析失败 → exit 2
        print(f"failed to parse manuscript: {exc}", file=sys.stderr)
        sys.exit(2)

    write_json(project_root / "methods_terms.json", result)
    print(json.dumps({
        "ok": True,
        "method_hits": result["summary"]["method_hits"],
        "distinct_canonical": result["summary"]["distinct_canonical"],
        "methods_sections": result["summary"]["methods_sections"],
        "weak_anchor_suspect": result["summary"]["weak_anchor_suspect"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
