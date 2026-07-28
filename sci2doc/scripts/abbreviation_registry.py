#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缩略语注册表

功能：
1. 注册缩略语（英文缩写、中文全称、英文全称、首次出现位置）
2. 查询缩略语是否已注册
3. 自动剥离已注册缩略语的冗余展开
4. 生成排序后的缩略语对照表
5. 持久化存储为 JSON

作者：Sci2Doc Team
"""

import argparse
import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# 路径 & IO 工具（复用 state_manager 的安全写入模式）
# ---------------------------------------------------------------------------

try:
    from state_manager import safe_json_load, safe_json_dump, file_lock, resolve_path
except Exception:  # pragma: no cover
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from state_manager import safe_json_load, safe_json_dump, file_lock, resolve_path

REGISTRY_FILENAME = "abbreviation_registry.json"


# ---------------------------------------------------------------------------
# 核心数据结构
# ---------------------------------------------------------------------------
# registry = {
#   "PCR": {
#     "full_cn": "聚合酶链式反应",
#     "full_en": "Polymerase Chain Reaction",
#     "first_chapter": "2",
#     "first_section": "2.1"
#   },
#   ...
# }
# ---------------------------------------------------------------------------


def registry_path(project_root):
    """返回注册表 JSON 文件的绝对路径"""
    return resolve_path(project_root, REGISTRY_FILENAME)


def load_registry(project_root):
    """加载注册表，不存在则返回空 dict"""
    path = registry_path(project_root)
    return safe_json_load(path, default={})


def save_registry(project_root, registry):
    """原子写入注册表"""
    path = registry_path(project_root)
    with file_lock(path, exclusive=True):
        safe_json_dump(path, registry)


# ---------------------------------------------------------------------------
# 注册 / 查询
# ---------------------------------------------------------------------------


def register(project_root, abbr, full_cn="", full_en="", chapter="", section=""):
    """
    注册一个缩略语。如果已存在则跳过（不覆盖首次出现位置）。

    Returns:
        dict: {"registered": bool, "already_known": bool, "abbr": str}
    """
    key = abbr.strip()
    if not key:
        return {"registered": False, "already_known": False, "abbr": key, "error": "empty abbreviation"}

    path = registry_path(project_root)
    with file_lock(path, exclusive=True):
        registry = safe_json_load(path, default={})
        if key in registry:
            return {"registered": False, "already_known": True, "abbr": key}
        registry[key] = {
            "full_cn": full_cn.strip(),
            "full_en": full_en.strip(),
            "first_chapter": _normalize_chapter(str(chapter)),
            "first_section": str(section).strip(),
        }
        safe_json_dump(path, registry)
    return {"registered": True, "already_known": False, "abbr": key}


def register_batch(project_root, items):
    """
    批量注册缩略语。

    Args:
        items: list of dict, 每个 dict 包含 abbr, full_cn, full_en, chapter, section

    Returns:
        dict: {"registered_count": int, "skipped_count": int, "details": list}
    """
    path = registry_path(project_root)
    details = []
    registered_count = 0
    skipped_count = 0

    with file_lock(path, exclusive=True):
        registry = safe_json_load(path, default={})

        for item in items:
            key = item.get("abbr", "").strip()
            if not key:
                details.append({"abbr": key, "action": "skipped", "reason": "empty"})
                skipped_count += 1
                continue
            if key in registry:
                details.append({"abbr": key, "action": "skipped", "reason": "already_known"})
                skipped_count += 1
                continue
            registry[key] = {
                "full_cn": item.get("full_cn", "").strip(),
                "full_en": item.get("full_en", "").strip(),
                "first_chapter": _normalize_chapter(str(item.get("chapter", ""))),
                "first_section": str(item.get("section", "")).strip(),
            }
            details.append({"abbr": key, "action": "registered"})
            registered_count += 1

        # P4: 无变更时跳过写入
        if registered_count > 0:
            safe_json_dump(path, registry)

    return {
        "registered_count": registered_count,
        "skipped_count": skipped_count,
        "details": details,
    }


def is_known(project_root, abbr):
    """检查缩略语是否已注册"""
    registry = load_registry(project_root)
    return abbr.strip() in registry


def get_all(project_root):
    """返回按字母排序的完整缩略语表"""
    registry = load_registry(project_root)
    sorted_items = sorted(registry.items(), key=lambda x: x[0].upper())
    return sorted_items


def get_info(project_root, abbr):
    """获取单个缩略语的详细信息"""
    registry = load_registry(project_root)
    key = abbr.strip()
    if key not in registry:
        return None
    info = dict(registry[key])
    info["abbr"] = key
    return info


def unregister(project_root, abbr):
    """
    删除一个已注册的缩略语。

    Returns:
        dict: {"removed": bool, "abbr": str}
    """
    key = abbr.strip()
    path = registry_path(project_root)
    with file_lock(path, exclusive=True):
        registry = safe_json_load(path, default={})
        if key not in registry:
            return {"removed": False, "abbr": key, "reason": "not_found"}
        del registry[key]
        safe_json_dump(path, registry)
    return {"removed": True, "abbr": key}


def update_entry(project_root, abbr, full_cn=None, full_en=None, chapter=None, section=None):
    """
    更新已注册缩略语的字段（仅更新非 None 参数）。

    Returns:
        dict: {"updated": bool, "abbr": str, "fields": list}
    """
    key = abbr.strip()
    path = registry_path(project_root)
    with file_lock(path, exclusive=True):
        registry = safe_json_load(path, default={})
        if key not in registry:
            return {"updated": False, "abbr": key, "reason": "not_found"}
        updated_fields = []
        if full_cn is not None:
            registry[key]["full_cn"] = full_cn.strip()
            updated_fields.append("full_cn")
        if full_en is not None:
            registry[key]["full_en"] = full_en.strip()
            updated_fields.append("full_en")
        if chapter is not None:
            registry[key]["first_chapter"] = _normalize_chapter(str(chapter))
            updated_fields.append("first_chapter")
        if section is not None:
            registry[key]["first_section"] = str(section).strip()
            updated_fields.append("first_section")
        if updated_fields:
            safe_json_dump(path, registry)
    return {"updated": True, "abbr": key, "fields": updated_fields}


# ---------------------------------------------------------------------------
# 自动提取缩略语（从 Markdown 文本中）
# ---------------------------------------------------------------------------

# 标准氨基酸三字母残基代码（用于排除 Ser5 / Thr7 / Pro12 这类位点标记，
# 而非误删 P53 / Bcl2 / Th1 等真实缩略语）
_AMINO_ACID_CODES = {
    "Ala", "Arg", "Asn", "Asp", "Cys", "Gln", "Glu", "Gly", "His", "Ile",
    "Leu", "Lys", "Met", "Phe", "Pro", "Ser", "Thr", "Trp", "Tyr", "Val",
}

# 匹配模式：
#   中文模式: "聚合酶链式反应（PCR）" 或 "聚合酶链式反应(PCR)"
#   英文模式: "Polymerase Chain Reaction (PCR)" 或 "PCR（Polymerase Chain Reaction）"
#   混合模式: "聚合酶链式反应（Polymerase Chain Reaction, PCR）"

_PATTERN_CN_ABBR = re.compile(
    r'([\u4e00-\u9fff][\u4e00-\u9fff\u0391-\u03a9\u03b1-\u03c9]{1,19})'  # 中文全称（首字汉字，可含希腊字母）
    r'[（(]'                                # 左括号
    r'([a-zA-Z][A-Za-z0-9\-]{1,15})'       # 英文缩写（允许小写开头如 mRNA）
    r'[）)]'                                # 右括号
)

_PATTERN_EN_ABBR = re.compile(
    r'([A-Za-z\u0391-\u03a9\u03b1-\u03c9][a-z\u0391-\u03a9\u03b1-\u03c9]+(?:-[A-Za-z\u0391-\u03a9\u03b1-\u03c9]+)*(?:\s+[A-Za-z\u0391-\u03a9\u03b1-\u03c9]+(?:-[A-Za-z\u0391-\u03a9\u03b1-\u03c9]+)*){1,8})' # 英文全称（首词大小写均可、含希腊字母）
    r'\s*[（(]'                             # 左括号
    r'([a-zA-Z\u0391-\u03a9\u03b1-\u03c9][A-Za-z0-9\u0391-\u03a9\u03b1-\u03c9]*(?:-[A-Za-z0-9\u0391-\u03a9\u03b1-\u03c9]+)*)'  # 英文缩写（允许小写开头、含希腊字母、不以连字符结尾）
    r'[）)]'                                # 右括号
)

_PATTERN_MIXED = re.compile(
    r'(?<![\u4e00-\u9fff])'                # 左侧不紧跟中文字（防贪婪截断使中文前缀过长）
    r'([\u4e00-\u9fff][\u4e00-\u9fff\u0391-\u03a9\u03b1-\u03c9]{1,19}?)'  # 中文全称（首字汉字，可含希腊字母如"干扰素γ"，非贪婪）
    r'[（(]'                                 # 左括号
    r'([A-Za-z\u0391-\u03a9\u03b1-\u03c9][a-z\u0391-\u03a9\u03b1-\u03c9]+(?:-[A-Za-z\u0391-\u03a9\u03b1-\u03c9]+)*(?:\s+[A-Za-z\u0391-\u03a9\u03b1-\u03c9]+(?:-[A-Za-z\u0391-\u03a9\u03b1-\u03c9]+)*){1,8})'   # 英文全称（首词大小写均可、含希腊字母）
    r'[,，]\s*'                              # 逗号分隔
    r'([a-zA-Z\u0391-\u03a9\u03b1-\u03c9][A-Za-z0-9\u0391-\u03a9\u03b1-\u03c9]*(?:-[A-Za-z0-9\u0391-\u03a9\u03b1-\u03c9]+)*)'  # 英文缩写（允许小写开头、含希腊字母、不以连字符结尾）
    r'[）)]'                                 # 右括号
)


# ---------------------------------------------------------------------------
# 中文全称前缀修剪
# ---------------------------------------------------------------------------

# 常见动词/介词/连词前缀，出现在术语名称前但不属于术语本身
# 注意：仅匹配多字词组，避免单字（以/用/对/在/为/是/的/与/和）误删
_CN_PREFIX_VERBS = re.compile(
    r'^(?:'
    # 主语前缀（指示词+名词+动词链）
    r'(?:这种|这一|这个|该|此|其|它|他|他们)?(?:现象|效应|过程|机制|状态|情况|作用|概念|特征|特性|特点|行为|模式|方式|结构|功能|能力|活性|表达)?'
    r'(?:被|被称为|是|为|即|由此|因此|因而|故|从而|进而)?'
    r')*'
    r'(?:本研究|本文|本实验|本课题)?'
    r'(?:采用|使用|利用|运用|通过|基于|借助|引入|结合|应用|'
    r'称为|简称|即为|又称|又叫|也称|也叫|亦称|'
    r'以及|同时|并且|而且|进而|因此|从而|由此)*'
)


def _trim_cn_prefix(cn_text):
    """
    修剪中文全称前的动词/介词前缀。

    例如: "本研究采用聚合酶链式反应" → "聚合酶链式反应"
          "同时使用高效液相色谱" → "高效液相色谱"
    """
    if not cn_text:
        return cn_text
    trimmed = _CN_PREFIX_VERBS.sub('', cn_text)
    # 如果修剪后为空或太短（<2字），保留原文
    if len(trimmed) < 2:
        return cn_text
    return trimmed


# 英文句首功能词（出现在术语全称前但不属于术语本身）。
# 仅用于修剪全称开头：句首代词/冠词/指示词/常见介词。
# 不影响夹在术语中间的连接小词（如 Center for Disease Control 里的 for），
# 因为修剪只从左侧逐词进行，遇到首个大写内容词即停。
_EN_PREFIX_FUNCTION_WORDS = {
    "we", "i", "the", "this", "that", "these", "those", "it", "they",
    "here", "a", "an", "in", "of", "on", "for", "by", "to", "as", "at",
    "our", "their", "its", "his", "her", "such",
}


def _trim_en_prefix(en_text):
    """
    修剪英文全称开头的句首功能词与小写词。

    全称应以大写内容词为起点。从左逐词修剪：
      - 首词属于句首功能词（We/The/This/In/Of...）→ 剥掉
      - 首词全小写（如 used/is）→ 剥掉
      - 首词为大写且非功能词 → 停止

    例如: "We used Polymerase Chain Reaction" → "Polymerase Chain Reaction"
          "The Blood Brain Barrier" → "Blood Brain Barrier"
          "Center for Disease Control" → 不变（首词 Center 即大写内容词）
    """
    if not en_text:
        return en_text
    words = en_text.split()
    idx = 0
    while idx < len(words):
        w = words[idx]
        if w.lower() in _EN_PREFIX_FUNCTION_WORDS:
            idx += 1
            continue
        if w[:1].islower():
            idx += 1
            continue
        break
    trimmed = " ".join(words[idx:])
    # 修剪后为空（整串都是功能词/小写）则保留原文，避免误删
    if not trimmed:
        return en_text
    return trimmed


def extract_abbreviations(md_content):
    """
    从 Markdown 文本中提取缩略语定义。

    Returns:
        list of dict: [{"abbr": "PCR", "full_cn": "...", "full_en": "..."}, ...]
    """
    found = {}

    def _valid_abbr(abbr):
        """
        缩略语有效性校验：
        1. 必须包含至少一个大写字母
        2. 排除氨基酸位点标记（如 Ser5 / Thr7 / Pro12），即标准三字母残基代码后跟纯数字。
           仅排除已知残基代码，避免误删 P53 / Bcl2 / Th1 等真实缩略语。
        """
        import re as _re
        if not any(c.isupper() for c in abbr):
            return False
        # 排除"氨基酸位点标记"：标准三字母残基代码（Ser/Thr/Pro...）后跟纯数字
        site_match = _re.match(r'^([A-Z][a-z]{2})\d+$', abbr)
        if site_match and site_match.group(1) in _AMINO_ACID_CODES:
            return False
        return True

    # 混合模式优先（最完整）
    for m in _PATTERN_MIXED.finditer(md_content):
        cn, en, abbr = m.group(1), m.group(2), m.group(3)
        if abbr not in found and _valid_abbr(abbr):
            found[abbr] = {"abbr": abbr, "full_cn": _trim_cn_prefix(cn), "full_en": en}

    # 英文模式
    for m in _PATTERN_EN_ABBR.finditer(md_content):
        en, abbr = m.group(1), m.group(2)
        if abbr not in found and _valid_abbr(abbr):
            found[abbr] = {"abbr": abbr, "full_cn": "", "full_en": _trim_en_prefix(en)}

    # 中文模式
    for m in _PATTERN_CN_ABBR.finditer(md_content):
        cn, abbr = m.group(1), m.group(2)
        if not _valid_abbr(abbr):
            continue
        trimmed = _trim_cn_prefix(cn)
        if abbr not in found:
            found[abbr] = {"abbr": abbr, "full_cn": trimmed, "full_en": ""}
        elif not found[abbr]["full_cn"]:
            found[abbr]["full_cn"] = trimmed

    return list(found.values())


# ---------------------------------------------------------------------------
# 剥离冗余展开
# ---------------------------------------------------------------------------


def _normalize_chapter(ch):
    """Normalize chapter number: strip leading zeros, whitespace."""
    s = str(ch).strip()
    try:
        return str(int(s))
    except (ValueError, TypeError):
        return s


def _build_strip_patterns(registry, current_chapter, current_section):
    """
    为已注册且非首次出现的缩略语构建剥离正则。

    策略：
    1. 优先用注册表中的精确 full_cn 匹配（避免吞噬前置动词）
    2. full_cn 为空时回退到通用中文模式
    3. 英文全称和混合模式同理
    """
    patterns = []
    norm_ch = _normalize_chapter(current_chapter)
    norm_sec = str(current_section).strip() if current_section else ""

    for abbr, info in registry.items():
        first_ch = _normalize_chapter(info.get("first_chapter", ""))
        first_sec = info.get("first_section", "").strip()

        # 如果当前章节就是首次出现章节，保留展开
        if norm_ch == first_ch:
            if norm_sec == first_sec or not norm_sec:
                continue

        escaped_abbr = re.escape(abbr)
        full_cn = info.get("full_cn", "").strip()
        full_en = info.get("full_en", "").strip()

        # 模式3（最长优先）: "中文全称（English Full Name, ABBR）" → "ABBR"
        if full_cn and full_en:
            patterns.append((
                re.compile(
                    re.escape(full_cn)
                    + r'[（(]'
                    + re.escape(full_en)
                    + r'[,，]\s*'
                    + escaped_abbr
                    + r'[）)]'
                ),
                abbr,
            ))

        # 模式1: "中文全称（ABBR）" → "ABBR"
        if full_cn:
            patterns.append((
                re.compile(
                    re.escape(full_cn) + r'[（(]' + escaped_abbr + r'[）)]'
                ),
                abbr,
            ))
        else:
            # 回退：通用中文模式（可能吞噬动词，但无更好选择）
            patterns.append((
                re.compile(
                    r'[\u4e00-\u9fff]{2,20}[（(]' + escaped_abbr + r'[）)]'
                ),
                abbr,
            ))

        # 模式2: "English Full Name (ABBR)" → "ABBR"
        if full_en:
            patterns.append((
                re.compile(
                    re.escape(full_en) + r'\s*[（(]' + escaped_abbr + r'[）)]',
                    re.IGNORECASE,
                ),
                abbr,
            ))
        else:
            patterns.append((
                re.compile(
                    r'[A-Z][a-z]+(?:-[A-Za-z]+)*(?:\s+[A-Za-z]+(?:-[A-Za-z]+)*){1,8}\s*[（(]' + escaped_abbr + r'[）)]'
                ),
                abbr,
            ))

        # 通用混合回退（full_cn 或 full_en 缺失时）
        if not (full_cn and full_en):
            patterns.append((
                re.compile(
                    r'[\u4e00-\u9fff]{2,20}[（(][A-Z][a-z]+(?:-[A-Za-z]+)*(?:\s+[A-Za-z]+(?:-[A-Za-z]+)*){1,8}[,，]\s*'
                    + escaped_abbr + r'[）)]'
                ),
                abbr,
            ))

    return patterns


def strip_redundant_expansions(project_root, md_content, chapter, section=""):
    """
    自动剥离已注册缩略语在非首次出现章节中的冗余展开。

    Args:
        project_root: 项目根目录
        md_content: Markdown 文本
        chapter: 当前章节号
        section: 当前小节号（可选）

    Returns:
        tuple: (cleaned_content, strip_report)
            strip_report = {"stripped_count": int, "details": list}
    """
    registry = load_registry(project_root)
    if not registry:
        return md_content, {"stripped_count": 0, "details": []}

    patterns = _build_strip_patterns(registry, chapter, section)
    if not patterns:
        return md_content, {"stripped_count": 0, "details": []}

    details = []
    result = md_content
    total_stripped = 0

    for regex, replacement in patterns:
        matches = list(regex.finditer(result))
        if matches:
            count = len(matches)
            total_stripped += count
            details.append({
                "abbr": replacement,
                "occurrences_stripped": count,
                "sample": matches[0].group(0)[:80],
            })
            result = regex.sub(replacement, result)

    return result, {
        "stripped_count": total_stripped,
        "details": details,
    }


# ---------------------------------------------------------------------------
# 提取 + 注册 + 剥离 一体化
# ---------------------------------------------------------------------------


def process_section_markdown(project_root, md_content, chapter, section=""):
    """
    一体化处理：提取新缩略语 → 注册 → 剥离冗余展开。

    典型调用时机：AI 生成某小节 markdown 后、保存前。

    Args:
        project_root: 项目根目录
        md_content: 原始 Markdown 文本
        chapter: 章节号
        section: 小节号

    Returns:
        tuple: (cleaned_content, report)
    """
    # Step 1: 提取新缩略语
    extracted = extract_abbreviations(md_content)

    # Step 2: 批量注册（附带章节信息）
    items = []
    for item in extracted:
        items.append({
            "abbr": item["abbr"],
            "full_cn": item.get("full_cn", ""),
            "full_en": item.get("full_en", ""),
            "chapter": chapter,
            "section": section,
        })

    reg_result = {"registered_count": 0, "skipped_count": 0, "details": []}
    if items:
        reg_result = register_batch(project_root, items)

    # Step 3: 剥离冗余展开（用更新后的注册表）
    cleaned, strip_result = strip_redundant_expansions(
        project_root, md_content, chapter, section
    )

    return cleaned, {
        "extracted_count": len(extracted),
        "registration": reg_result,
        "stripping": strip_result,
    }


# ---------------------------------------------------------------------------
# 生成缩略语对照表（用于论文前置页）
# ---------------------------------------------------------------------------


def generate_abbreviation_table_markdown(project_root):
    """
    生成缩略语对照表的 Markdown 文本（三线表格式）。

    Returns:
        str: Markdown 表格文本，如果无缩略语则返回空字符串
    """
    items = get_all(project_root)
    if not items:
        return ""

    lines = [
        "# 主要缩略语对照表",
        "",
        "| 缩略语 | 英文全称 | 中文全称 |",
        "|---|---|---|",
    ]
    for abbr, info in items:
        full_en = (info.get("full_en", "") or "").replace("|", "\\|")
        full_cn = (info.get("full_cn", "") or "").replace("|", "\\|")
        safe_abbr = abbr.replace("|", "\\|")
        lines.append(f"| {safe_abbr} | {full_en} | {full_cn} |")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 交叉引用验证
# ---------------------------------------------------------------------------


def validate_cross_references(project_root):
    """
    验证注册表中 first_chapter/first_section 指向的 markdown 文件
    确实包含该缩略语的展开定义。

    Returns:
        dict: {"valid_count": int, "invalid_count": int, "details": list}
    """
    from pathlib import Path

    registry = load_registry(project_root)
    if not registry:
        return {"valid_count": 0, "invalid_count": 0, "details": []}

    atomic_dir = Path(project_root) / "atomic_md"
    alt_dir = Path(project_root) / "02_分章节文档"
    details = []
    valid_count = 0
    invalid_count = 0

    for abbr, info in registry.items():
        first_ch = _normalize_chapter(info.get("first_chapter", ""))
        first_sec = info.get("first_section", "").strip()

        if not first_ch:
            details.append({
                "abbr": abbr, "status": "invalid",
                "reason": "missing first_chapter",
            })
            invalid_count += 1
            continue

        # 尝试 atomic_md/ 和 02_分章节文档/ 两个目录
        chapter_dir = None
        for base in (atomic_dir, alt_dir):
            candidate = base / f"第{first_ch}章"
            if candidate.is_dir():
                chapter_dir = candidate
                break
        if chapter_dir is None:
            details.append({
                "abbr": abbr, "status": "invalid",
                "reason": f"chapter dir not found: 第{first_ch}章",
            })
            invalid_count += 1
            continue

        # 查找匹配 section 的 md 文件
        target_files = []
        if first_sec:
            for md_file in chapter_dir.glob("*.md"):
                if md_file.name.startswith(first_sec + "_") or md_file.name.startswith(first_sec + "."):
                    target_files.append(md_file)
            # 宽松回退：section 编号前缀匹配
            if not target_files:
                for md_file in chapter_dir.glob(f"{first_sec}*"):
                    if md_file.suffix == ".md":
                        target_files.append(md_file)
        if not target_files:
            # 搜索整个章节目录
            target_files = list(chapter_dir.glob("*.md"))

        # 在目标文件中搜索缩略语展开
        found = False
        full_cn = info.get("full_cn", "").strip()
        full_en = info.get("full_en", "").strip()
        escaped_abbr = re.escape(abbr)
        # 匹配 "（ABBR）" 或 "（全称，ABBR）"
        # 允许左括号后跟任意非右括号字符，以逗号结尾，再接缩略语
        search_pattern = re.compile(
            r'[（(](?:[^）)]*?[,，]\s*)?' + escaped_abbr + r'[）)]'
        )

        for md_file in target_files:
            try:
                content = md_file.read_text(encoding="utf-8")
            except Exception:
                continue
            if search_pattern.search(content):
                found = True
                break

        if found:
            details.append({"abbr": abbr, "status": "valid"})
            valid_count += 1
        else:
            reason = f"expansion not found in 第{first_ch}章"
            if first_sec:
                reason += f" section {first_sec}"
            details.append({"abbr": abbr, "status": "invalid", "reason": reason})
            invalid_count += 1

    return {
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "details": details,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="缩略语注册表管理")
    parser.add_argument("--project-root", default=".", help="项目根目录")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # register
    reg_p = subparsers.add_parser("register", help="注册缩略语")
    reg_p.add_argument("--abbr", required=True, help="缩写")
    reg_p.add_argument("--full-cn", default="", help="中文全称")
    reg_p.add_argument("--full-en", default="", help="英文全称")
    reg_p.add_argument("--chapter", default="", help="首次出现章节")
    reg_p.add_argument("--section", default="", help="首次出现小节")

    # query
    query_p = subparsers.add_parser("query", help="查询缩略语")
    query_p.add_argument("--abbr", required=True, help="缩写")

    # list
    subparsers.add_parser("list", help="列出所有缩略语")

    # extract
    extract_p = subparsers.add_parser("extract", help="从 Markdown 文件提取缩略语")
    extract_p.add_argument("--file", required=True, help="Markdown 文件路径")
    extract_p.add_argument("--chapter", default="", help="章节号")
    extract_p.add_argument("--section", default="", help="小节号")
    extract_p.add_argument("--auto-register", action="store_true", help="自动注册提取到的缩略语")

    # process
    proc_p = subparsers.add_parser("process", help="一体化处理：提取+注册+剥离")
    proc_p.add_argument("--file", required=True, help="Markdown 文件路径")
    proc_p.add_argument("--chapter", required=True, help="章节号")
    proc_p.add_argument("--section", default="", help="小节号")
    proc_p.add_argument("--in-place", action="store_true", help="原地覆写文件")

    # table
    subparsers.add_parser("table", help="生成缩略语对照表 Markdown")

    # strip
    strip_p = subparsers.add_parser("strip", help="剥离冗余展开")
    strip_p.add_argument("--file", required=True, help="Markdown 文件路径")
    strip_p.add_argument("--chapter", required=True, help="当前章节号")
    strip_p.add_argument("--section", default="", help="当前小节号")
    strip_p.add_argument("--in-place", action="store_true", help="原地覆写文件")

    # unregister
    unreg_p = subparsers.add_parser("unregister", help="删除已注册缩略语")
    unreg_p.add_argument("--abbr", required=True, help="要删除的缩写")

    # update
    upd_p = subparsers.add_parser("update", help="更新已注册缩略语字段")
    upd_p.add_argument("--abbr", required=True, help="缩写")
    upd_p.add_argument("--full-cn", default=None, help="中文全称")
    upd_p.add_argument("--full-en", default=None, help="英文全称")
    upd_p.add_argument("--chapter", default=None, help="首次出现章节")
    upd_p.add_argument("--section", default=None, help="首次出现小节")

    # validate (cross-reference)
    subparsers.add_parser("validate", help="交叉引用验证：检查注册表与 markdown 文件一致性")

    args = parser.parse_args()
    project_root = os.path.abspath(args.project_root)

    if args.command == "register":
        result = register(
            project_root,
            abbr=args.abbr,
            full_cn=args.full_cn,
            full_en=args.full_en,
            chapter=args.chapter,
            section=args.section,
        )
        print(json.dumps(result, ensure_ascii=False))

    elif args.command == "query":
        info = get_info(project_root, args.abbr)
        if info:
            print(json.dumps({"found": True, **info}, ensure_ascii=False))
        else:
            print(json.dumps({"found": False, "abbr": args.abbr}, ensure_ascii=False))

    elif args.command == "list":
        items = get_all(project_root)
        output = {abbr: info for abbr, info in items}
        print(json.dumps({"count": len(items), "registry": output}, ensure_ascii=False, indent=2))

    elif args.command == "extract":
        if not os.path.exists(args.file):
            print(json.dumps({"error": f"文件不存在: {args.file}"}, ensure_ascii=False))
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()
        extracted = extract_abbreviations(content)
        if args.auto_register and extracted:
            items = [
                {
                    "abbr": e["abbr"],
                    "full_cn": e.get("full_cn", ""),
                    "full_en": e.get("full_en", ""),
                    "chapter": args.chapter,
                    "section": args.section,
                }
                for e in extracted
            ]
            reg_result = register_batch(project_root, items)
            print(json.dumps({
                "extracted": extracted,
                "registration": reg_result,
            }, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({"extracted": extracted}, ensure_ascii=False, indent=2))

    elif args.command == "process":
        if not os.path.exists(args.file):
            print(json.dumps({"error": f"文件不存在: {args.file}"}, ensure_ascii=False))
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()
        cleaned, report = process_section_markdown(
            project_root, content, args.chapter, args.section
        )
        if args.in_place:
            with open(args.file, "w", encoding="utf-8") as f:
                f.write(cleaned)
            report["written_to"] = args.file
        else:
            report["cleaned_preview"] = cleaned[:500] + ("..." if len(cleaned) > 500 else "")
        print(json.dumps(report, ensure_ascii=False, indent=2))

    elif args.command == "table":
        md = generate_abbreviation_table_markdown(project_root)
        if md:
            print(md)
        else:
            print("（无已注册缩略语）")

    elif args.command == "strip":
        if not os.path.exists(args.file):
            print(json.dumps({"error": f"文件不存在: {args.file}"}, ensure_ascii=False))
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()
        cleaned, report = strip_redundant_expansions(
            project_root, content, args.chapter, args.section
        )
        if args.in_place:
            with open(args.file, "w", encoding="utf-8") as f:
                f.write(cleaned)
            report["written_to"] = args.file
        else:
            report["cleaned_preview"] = cleaned[:500] + ("..." if len(cleaned) > 500 else "")
        print(json.dumps(report, ensure_ascii=False, indent=2))

    elif args.command == "unregister":
        result = unregister(project_root, args.abbr)
        print(json.dumps(result, ensure_ascii=False))

    elif args.command == "update":
        result = update_entry(
            project_root,
            abbr=args.abbr,
            full_cn=args.full_cn,
            full_en=args.full_en,
            chapter=args.chapter,
            section=args.section,
        )
        print(json.dumps(result, ensure_ascii=False))

    elif args.command == "validate":
        result = validate_cross_references(project_root)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
