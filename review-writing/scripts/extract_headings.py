#!/usr/bin/env python3
"""extract_headings.py —— 标题真值生产者（功能② · INTERFACE §1，跨家共享）.

一趟同产两文件，偏移天然一致：
  - <text-out>  正文纯文本 draft_import.md（切片/审计的字节流基准）
  - <out>       heading_manifest.json（标题真值，char_offset 索引 draft_import.md）

不变量：对每个 heading，draft_import.md[char_offset : char_offset+len(text)] == text。

来源判定按扩展名：.md/.markdown → markdown（无第三方依赖，主覆盖）；
.docx → python-docx + styles.xml 反查（basedOn 链 / outlineLvl，识别非标准样式）；
.pdf → 抽文本、headings 置空（触发无标题路）。

退出码（INTERFACE §1）：
  0  成功（含 headings:[] 的 headless 情形，必写出两文件）
  1  源损坏（docx 非 zip / pdf 打不开 / 抽出 <200 字疑扫描件）
  2  用法错 / --source 不存在 / 缺 python-docx / 无可用 PDF 抽取器
只走 CLI，单行 JSON 到 stdout。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

MIN_BODY_CHARS = 200  # <此长度的 docx/pdf 抽取视为扫描件，HALT（markdown 不受限）
ATX_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*$")
# 保守的内容启发式：仅在 docx 无任何样式标题时，作 low-confidence 兜底（编号+短行）。
NUMBERED_RE = re.compile(r"^\s*\d+(?:[.\-]\d+){0,4}[.、\s]")
CAPTION_STYLE_RE = re.compile(r"caption|题注|图注|表注|表名|表头", re.IGNORECASE)
# §10 附带修复：Word 目录条目样式（toc 1/toc2…）挂 outlineLvl，会被反查误当 L1 标题，排除。
TOC_STYLE_RE = re.compile(r"^toc\s*\d", re.IGNORECASE)

# --- §10 前后置标签识别（标签只是 level:0 + kind 的额外切点，cut_offsets 零改动）---
LABEL_MAXLEN = 40  # 归一后长度上限（§10 短行约束；exact-match 已隐含更严边界，这是兜底）
_LABEL_WS_RE = re.compile(r"[\s　]+")
# 允许前置编号（如"一、致谢"、"5. Acknowledgements"、"(1)"）
_LEAD_NUM_RE = re.compile(r"^[（(]?[一二三四五六七八九十0-9IVXivx]{0,3}[、.．)）]?")


def _norm_label(s):
    """§10-C0 归一：去首尾空白 → 折叠去全半角空白 → 去尾冒号 → 小写（英文大小写不敏感）。"""
    s = _LABEL_WS_RE.sub("", s.strip()).rstrip(":：")
    return s.lower()


def _mk_labels(labels):
    return {_norm_label(x) for x in labels}


# B1 摘要类 → front_abstract（切点，取首个）
FRONT_ABSTRACT_LABELS = _mk_labels([
    "摘要", "中文摘要", "内容摘要", "Abstract", "Summary"])
# B3 后置类 → back_matter（切点，位置门后取最早一个）。关键词/分类号类不成切点，不识别。
BACK_MATTER_LABELS = _mk_labels([
    "致谢", "致  谢", "谢辞",
    "Acknowledgement", "Acknowledgements", "Acknowledgment", "Acknowledgments",
    "基金资助", "资助", "项目资助", "基金", "Funding", "Funding Statement", "Financial Support",
    "利益冲突", "利益冲突声明", "Conflict of Interest", "Conflicts of Interest",
    "Competing Interests", "Competing Interest", "Declaration of Interests",
    "作者贡献", "作者贡献声明", "Author Contributions", "Author Contribution", "CRediT",
    "数据可用性", "数据可用性声明", "Data Availability", "Data Availability Statement",
    "补充材料", "支持信息", "Supplementary Material", "Supplementary Materials",
    "Supporting Information", "Supplementary",
    "攻读学位期间主要的研究成果", "攻读学位期间发表的论文"])
# §11 R1 参考文献锚点：back_matter 本是参考文献之后的块，无此锚点则后置标签不自动成切点。
REFERENCES_LABELS = _mk_labels([
    "参考文献", "参考书目", "引用文献",
    "References", "Reference", "Bibliography", "Works Cited", "Literature Cited"])


def _match_label(norm, labelset):
    """整行归一后 == 标签，或去掉前置编号后 == 标签（§10-C1 行首锚定 + 整行≈标签）。"""
    if norm in labelset:
        return True
    stripped = _LEAD_NUM_RE.sub("", norm, count=1)
    return stripped != norm and stripped in labelset


def detect_labels(text, headings):
    """§10 标签识别 pass —— 把独立成短行的前后置标签识别成 level:0 + kind 特殊 heading。

    防误判三关：① 行首锚定+整行≈标签+短行（_match_label + LABEL_MAXLEN，挡句内含"基金/致谢"词）；
    ② 后置位置门（back_matter 只在最后一个正文标题之后才算，挡正文"受XX基金资助"）；
    ③ 不确定不切（不满足→不进切点，交现有行为/LLM/用户）。
    front_abstract 只取首个（须在首个正文标题前）；back_matter 位置门后只取最早一个。
    §11 后置门加硬（confidence 决定是否成切点，消费方 cut_points 判据=非图注且 confidence!='low'）：
      R1 back_matter 成 high 切点须其前存在参考文献锚点（REFERENCES_LABELS 标题/标签），
         否则标 confidence='low'（保留 heading 供 §2 路由/LLM 核验，但不进 cut_points）。
      R2 front_abstract 成 high 切点须其后存在正文标题（body_offs 非空——含编号标题/参考文献），
         否则 'low'——避免"仅一行摘要"把 headless 稿翻成有标题路。
    返回新增 heading 列表（含 kind），调用方合并进 headings 并按 char_offset 重排。
    """
    real_offsets = {h["char_offset"] for h in headings}
    body_offs = [h["char_offset"] for h in headings
                 if not h.get("is_caption") and h.get("level", 0) >= 1 and not h.get("kind")]
    first_body_off = min(body_offs) if body_offs else None
    last_body_off = max(body_offs) if body_offs else None

    def _ref_anchor_before(target_off):
        # R1：target 之前是否存在参考文献类真标题（非图注、非 kind 标签）
        return any(not h.get("is_caption") and h.get("char_offset", 0) < target_off
                   and _match_label(_norm_label(h.get("text", "")), REFERENCES_LABELS)
                   for h in headings)

    front = None
    back_candidates = []
    pos = 0
    for line in text.splitlines(keepends=True):
        off = pos
        pos += len(line)
        if off in real_offsets:  # 已是样式/编号真标题，不重复识别
            continue
        body = line.rstrip("\r\n")
        norm = _norm_label(body)
        if not norm or len(norm) > LABEL_MAXLEN:
            continue
        if _match_label(norm, FRONT_ABSTRACT_LABELS):
            # 前置门：须在首个正文标题之前（或全文无正文标题）
            if front is None and (first_body_off is None or off < first_body_off):
                # R2：其后须存在正文标题才成 high 切点；否则 low（不翻路由）。front 恒在首个 body 之前，故 body_offs 非空即等价"其后有正文标题"。
                conf = "high" if body_offs else "low"
                front = {"text": body, "level": 0, "char_offset": off,
                         "style_id": "label:front_abstract", "is_caption": False,
                         "confidence": conf, "kind": "front_abstract"}
        elif _match_label(norm, BACK_MATTER_LABELS):
            # 后置位置门：须在最后一个正文标题之后（挡正文中部"受XX基金资助"）
            if last_body_off is not None and off > last_body_off:
                back_candidates.append((off, body))

    result = []
    if front is not None:
        result.append(front)
    if back_candidates:
        off, body = min(back_candidates)  # 只取最早一个作切点，其余不切（已在后置块内）
        # R1：其前须存在参考文献锚点才成 high 切点；否则 low（不静默切正文尾段，交 LLM/用户）。
        conf = "high" if _ref_anchor_before(off) else "low"
        result.append({"text": body, "level": 0, "char_offset": off,
                       "style_id": "label:back_matter", "is_caption": False,
                       "confidence": conf, "kind": "back_matter"})
    return result


def _die(code, msg):
    sys.stderr.write(msg.rstrip() + "\n")
    sys.exit(code)


def _emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# markdown
# ---------------------------------------------------------------------------
def extract_markdown(src_path):
    with open(src_path, encoding="utf-8") as f:
        raw = f.read()
    out = []
    headings = []
    pos = 0
    for line in raw.splitlines(keepends=True):
        body = line.rstrip("\r\n")  # S3：CRLF 源标题残留 \r 一并剥除
        nl = line[len(body):]
        m = ATX_RE.match(body)
        if m:
            htext = m.group(2).strip()
            headings.append({
                "text": htext,
                "level": len(m.group(1)),
                "char_offset": pos,
                "style_id": "md:" + m.group(1),
                "is_caption": False,
                "confidence": "high",
            })
            out.append(htext)
            pos += len(htext)
        else:
            out.append(body)
            pos += len(body)
        out.append(nl)
        pos += len(nl)
    text = "".join(out)
    headings = sorted(headings + detect_labels(text, headings),
                      key=lambda h: h["char_offset"])
    return text, headings


# ---------------------------------------------------------------------------
# docx —— styles.xml 反查（basedOn 链 + outlineLvl）
# ---------------------------------------------------------------------------
def _docx_outline_map(doc):
    """从 styles.xml 建 styleId/name -> 层级(outlineLvl+1) 的映射（非标准样式反查）。"""
    from docx.oxml.ns import qn
    out = {}
    styles_el = doc.styles.element
    for st in styles_el.findall(qn("w:style")):
        sid = st.get(qn("w:styleId"))
        name_el = st.find(qn("w:name"))
        name = name_el.get(qn("w:val")) if name_el is not None else None
        ppr = st.find(qn("w:pPr"))
        if ppr is None:
            continue
        ol = ppr.find(qn("w:outlineLvl"))
        if ol is None:
            continue
        try:
            lvl = int(ol.get(qn("w:val"))) + 1
        except (TypeError, ValueError):
            continue
        if sid:
            out[sid] = lvl
        if name:
            out[name] = lvl
    return out


def _level_from_style_chain(style):
    """跟 base_style（basedOn）链找 Heading N / Title，返回层级或 None。"""
    seen = set()
    s = style
    while s is not None and id(s) not in seen:
        seen.add(id(s))
        name = (getattr(s, "name", None) or "").strip().lower()
        if name == "title":
            return 1
        m = re.match(r"heading\s*(\d+)", name)
        if m:
            return int(m.group(1))
        s = getattr(s, "base_style", None)
    return None


def extract_docx(src_path):
    try:
        import docx  # python-docx
    except Exception:
        _die(2, "python-docx not available")
    try:
        doc = docx.Document(src_path)
    except Exception as e:  # 非 zip / 损坏包
        _die(1, "corrupt or unreadable docx: %s" % e)

    outline_map = _docx_outline_map(doc)
    out = []
    headings = []
    pos = 0
    for p in doc.paragraphs:
        text = p.text
        style = p.style
        sname = (getattr(style, "name", None) or "")
        sid = getattr(style, "style_id", None)
        if TOC_STYLE_RE.match(sid or "") or TOC_STYLE_RE.match(sname or ""):
            # §10 附带修复：目录条目样式带 outlineLvl / basedOn Heading，不当标题
            level, is_caption = None, False
        else:
            level = _level_from_style_chain(style)
            if level is None:
                level = outline_map.get(sid) or outline_map.get(sname)
            is_caption = bool(CAPTION_STYLE_RE.search(sname))
        stripped = text.strip()
        if stripped:
            if is_caption:
                headings.append({"text": stripped, "level": 0, "char_offset": pos,
                                 "style_id": sname or "caption", "is_caption": True,
                                 "confidence": "high"})
            elif level is not None:
                headings.append({"text": stripped, "level": level, "char_offset": pos,
                                 "style_id": sname or ("outline:%d" % level),
                                 "is_caption": False, "confidence": "high"})
        out.append(text)
        pos += len(text)
        out.append("\n")
        pos += 1
    full = "".join(out)
    headings = sorted(headings + detect_labels(full, headings),
                      key=lambda h: h["char_offset"])
    return full, headings


# ---------------------------------------------------------------------------
# pdf —— 抽文本，headings 置空（触发无标题路）
# ---------------------------------------------------------------------------
def extract_pdf(src_path, pdf_tool=None):
    tools = [pdf_tool] if pdf_tool else ["pymupdf", "pdfplumber", "pypdf"]
    text = None
    for t in tools:
        try:
            if t == "pymupdf":
                import fitz
                d = fitz.open(src_path)
                text = "\n".join(pg.get_text() for pg in d)
            elif t == "pdfplumber":
                import pdfplumber
                with pdfplumber.open(src_path) as pdf:
                    text = "\n".join((pg.extract_text() or "") for pg in pdf.pages)
            elif t == "pypdf":
                import pypdf
                r = pypdf.PdfReader(src_path)
                text = "\n".join((pg.extract_text() or "") for pg in r.pages)
            if text is not None:
                break
        except ImportError:
            continue
        except Exception as e:
            _die(1, "pdf open failed: %s" % e)
    if text is None:
        _die(2, "no usable PDF extractor (install pymupdf/pdfplumber/pypdf)")
    return text, []


def main(argv=None):
    ap = argparse.ArgumentParser(description="标题真值生产者（draft_import.md + heading_manifest.json）")
    ap.add_argument("--source", required=True)
    ap.add_argument("--text-out", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pdf-tool", choices=["pymupdf", "pdfplumber", "pypdf", "pdftotext"])
    args = ap.parse_args(argv)

    if not os.path.isfile(args.source):
        _die(2, "source not found: %s" % args.source)

    ext = os.path.splitext(args.source)[1].lower()
    if ext in (".md", ".markdown", ".txt"):
        text, headings = extract_markdown(args.source)
    elif ext == ".docx":
        text, headings = extract_docx(args.source)
        if len(text.strip()) < MIN_BODY_CHARS and not headings:
            _die(1, "extracted <%d chars from docx (scanned?)" % MIN_BODY_CHARS)
    elif ext == ".pdf":
        text, headings = extract_pdf(args.source, args.pdf_tool)
        if len(text.strip()) < MIN_BODY_CHARS:
            _die(1, "extracted <%d chars from pdf (scanned?)" % MIN_BODY_CHARS)
    else:
        _die(2, "unsupported source extension: %s" % ext)

    os.makedirs(os.path.dirname(os.path.abspath(args.text_out)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.text_out, "w", encoding="utf-8") as f:
        f.write(text)

    manifest = {
        "source_file": os.path.abspath(args.source),
        "text_file": args.text_out,
        "text_len": len(text),
        "headings": headings,
        "warning": None if headings else "no_heading_detected",
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    _emit({"ok": True, "exit": 0, "headings": len(headings),
           "headless": not headings, "text_len": len(text)})
    sys.exit(0)


if __name__ == "__main__":
    main()
