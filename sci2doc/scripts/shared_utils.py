#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
共享工具函数

避免 heading_level / classify_heading / normalize_text / infer_project_root_for_profile
在多个脚本中重复定义。
"""

import os
import re


def normalize_text(value):
    """标准化标题文本用于匹配。"""
    return re.sub(r"\s+", "", (value or "").lower())


def heading_level(style_name):
    """
    解析 Heading 样式级别；非标题返回 None。
    """
    if not style_name:
        return None
    m = re.match(r"^(?:Heading|标题)\s*(\d+)$", style_name, flags=re.IGNORECASE)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def classify_heading(text):
    """
    根据标题文本分类章节类型。

    Returns:
        str: body | review | references | toc | abstract | acknowledgement | appendix
    """
    t = normalize_text(text)
    if not t:
        return "body"

    chapter_prefix_cn = r"(第[一二三四五六七八九十百千万0-9]+章)?"
    chapter_prefix_en = r"(chapter[0-9ivxlcdm]+)?"
    patterns = {
        "review": [
            rf"^{chapter_prefix_cn}综述$",
            rf"^{chapter_prefix_cn}文献综述$",
            rf"^{chapter_prefix_cn}研究综述$",
            rf"^{chapter_prefix_en}literaturereview$",
            rf"^{chapter_prefix_en}reviewofliterature$",
        ],
        "references": [
            rf"^{chapter_prefix_cn}参考文献$",
            rf"^{chapter_prefix_en}references$",
        ],
        "toc": [r"^目录$", r"tableofcontents", r"^contents$"],
        "abstract": [
            rf"^{chapter_prefix_cn}(中文|英文)?摘要$",
            rf"^{chapter_prefix_en}abstract$",
        ],
        "acknowledgement": [
            rf"^{chapter_prefix_cn}致谢$",
            rf"^{chapter_prefix_en}acknowledg(e)?ment$",
        ],
        "appendix": [
            rf"^{chapter_prefix_cn}附录$",
            rf"^{chapter_prefix_en}appendix$",
        ],
        "achievements": [
            rf"^{chapter_prefix_cn}攻读(博士|硕士)?(学位)?期间(取得的|的)?(研究)?成果$",
            rf"^{chapter_prefix_cn}攻读期间成果$",
        ],
        "declaration": [
            rf"^{chapter_prefix_cn}独创性声明$",
            rf"^{chapter_prefix_cn}学位论文原创性声明$",
        ],
        "abbreviation_table": [
            rf"^{chapter_prefix_cn}缩略语表$",
            rf"^{chapter_prefix_cn}缩略词表$",
            rf"^{chapter_prefix_cn}(主要)?符号(与)?缩略语表$",
            r"^abbreviations?$",
        ],
    }
    for section_type, regex_list in patterns.items():
        for regex in regex_list:
            if re.search(regex, t):
                return section_type
    return "body"


def is_chapter_level_heading(level, text):
    """
    判断是否为章级标题（最顶层，即"第N章/Chapter N"形式，或文档中的一级标题）。

    Args:
        level: 标题层级数字（Markdown 的 # 数量，或 Word 的 Heading 级别）
        text:  标题文本（已去除 # 前缀）

    Returns:
        bool
    """
    t = normalize_text(text)
    # 明确带"第N章 / Chapter N"前缀的标题一定是章级
    if re.search(r"第[一二三四五六七八九十百千万0-9]+章", t):
        return True
    if re.search(r"chapter[0-9ivxlcdm]+", t):
        return True
    # 对于 Markdown，#（level=1）视为章级
    if level == 1:
        return True
    # 对于 Word，Heading 1 视为章级
    if level == 1:
        return True
    return False


def classify_lines_with_chapter_scope(lines, extra_exclude=None):
    """
    对文本行列表进行章作用域继承分类。

    规则：
    - 遇到章级标题（# 或 "第N章"前缀）时，判断该章类型，其下所有更深
      级别子标题**继承**该章类型，直到下一个同级或更浅章级标题。
    - 摘要章（abstract）计入正文（不排除）。
    - extra_exclude: 额外排除的章节标题文本列表（normalize_text 后比较）。

    Args:
        lines: 文本行列表（str）
        extra_exclude: 额外排除标题集合（normalize_text 后的字符串列表）

    Yields:
        (line_text, section_type) — 每行及其所属章节类型
    """
    extra_exclude_set = set()
    if extra_exclude:
        for t in extra_exclude:
            extra_exclude_set.add(normalize_text(t))

    heading_re = re.compile(r"^(#{1,6})\s+(.+)$")
    # (min_level_of_chapter, chapter_type)
    # 初始状态：正文
    chapter_type = "body"
    chapter_min_level = None  # 当前章的 # 级别

    for line in lines:
        stripped = line.strip()
        m = heading_re.match(stripped)
        if m:
            level = len(m.group(1))
            title_text = m.group(2).strip()
            t_norm = normalize_text(title_text)

            is_chapter = is_chapter_level_heading(level, title_text)

            if is_chapter or (chapter_min_level is not None and level <= chapter_min_level):
                # 新章：重新判定章类型
                raw_type = classify_heading(title_text)
                # extra_exclude 优先：标题在额外排除列表中 → 强制为 review（排除）
                if t_norm in extra_exclude_set:
                    raw_type = "review"
                # abstract 不排除：计入正文
                if raw_type == "abstract":
                    raw_type = "body"
                chapter_type = raw_type
                chapter_min_level = level
            # 子标题：继承当前章类型（不更新 chapter_type）
            yield stripped, chapter_type
        else:
            yield stripped, chapter_type


def classify_paragraphs_with_chapter_scope(paragraphs_with_levels, extra_exclude=None):
    """
    对 (text, heading_level_or_None) 序列进行章作用域继承分类。

    用于 check_quality.py（Word docx 的段落流）。

    Args:
        paragraphs_with_levels: iterable of (text: str, level: int|None)
            level 为 None 表示普通段落，int 表示 Heading 级别
        extra_exclude: 额外排除标题文本列表

    Yields:
        (text, heading_level_or_None, section_type)
    """
    extra_exclude_set = set()
    if extra_exclude:
        for t in extra_exclude:
            extra_exclude_set.add(normalize_text(t))

    chapter_type = "body"
    chapter_min_level = None

    for text, level in paragraphs_with_levels:
        if level is not None:
            t_norm = normalize_text(text)
            is_chapter = is_chapter_level_heading(level, text)

            if is_chapter or (chapter_min_level is not None and level <= chapter_min_level):
                raw_type = classify_heading(text)
                if t_norm in extra_exclude_set:
                    raw_type = "review"
                if raw_type == "abstract":
                    raw_type = "body"
                chapter_type = raw_type
                chapter_min_level = level
            yield text, level, chapter_type
        else:
            yield text, level, chapter_type


def infer_project_root_for_profile(docx_path):
    """
    从 docx 路径向上查找 thesis_profile.json，找到后返回其所在目录。
    找不到时返回 docx 所在目录，保持向后兼容。
    """
    current = os.path.abspath(os.path.dirname(docx_path))
    while True:
        candidate = os.path.join(current, "thesis_profile.json")
        if os.path.exists(candidate):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return os.path.abspath(os.path.dirname(docx_path))
