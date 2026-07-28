#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原子化 Markdown 章节工作流工具

目标：
1) 每个小节独立 .md 文件
2) 校验小节编号连续（文件名前缀）
3) 合并为章节总 .md（可选转为 .docx）

约定：
- 小节文件放在: <project_root>/atomic_md/第{chapter}章/
- 文件命名: <章节编号>_<标题>.md, 如: 2.1_研究对象.md
- 编号前缀必须可解析为数字层级，且与 chapter 一致
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from thesis_profile import load_profile
except Exception:  # pragma: no cover
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from thesis_profile import load_profile


SECTION_FILE_RE = re.compile(r"^(?P<num>\d+(?:\.\d+)*)_(?P<title>.+)\.md$")


@dataclass(order=True)
class SectionFile:
    number: tuple
    number_text: str
    title: str
    path: Path


def parse_number_tuple(text):
    parts = text.split(".")
    out = []
    for p in parts:
        if not p.isdigit():
            raise ValueError(f"invalid section number segment: {p}")
        out.append(int(p))
    return tuple(out)


def default_chapter_dir(project_root, chapter):
    return Path(project_root) / "atomic_md" / f"第{chapter}章"


def discover_section_files(chapter_dir):
    files = []
    for p in sorted(chapter_dir.glob("*.md")):
        m = SECTION_FILE_RE.match(p.name)
        if not m:
            continue
        number_text = m.group("num")
        title = m.group("title")
        number = parse_number_tuple(number_text)
        files.append(SectionFile(number=number, number_text=number_text, title=title, path=p))
    return sorted(files)


def validate_section_files(chapter, section_files):
    errors = []
    chapter_i = int(chapter)
    by_parent = {}

    for sf in section_files:
        if sf.number[0] != chapter_i:
            errors.append(f"{sf.path.name}: 编号应属于第{chapter_i}章，实际为 {sf.number_text}")
            continue
        key = (len(sf.number), sf.number[:-1])
        current = sf.number[-1]
        if key not in by_parent:
            if current != 1:
                errors.append(f"{sf.path.name}: 编号起始应为 ...1，实际为 {sf.number_text}")
            by_parent[key] = current
            continue
        expected = by_parent[key] + 1
        if current != expected:
            errors.append(
                f"{sf.path.name}: 编号不连续，期望 {'.'.join(map(str, sf.number[:-1] + (expected,)))}，实际 {sf.number_text}"
            )
        by_parent[key] = current

    return errors


def check_first_heading_matches_filename(section_file):
    heading_re = re.compile(r"^##\s+(?P<num>\d+(?:\.\d+)*)\s+")
    try:
        text = section_file.path.read_text(encoding="utf-8")
    except Exception as e:
        return [f"{section_file.path.name}: 读取失败: {e}"]
    for line in text.splitlines():
        m = heading_re.match(line.strip())
        if not m:
            continue
        got = m.group("num")
        if got != section_file.number_text:
            return [f"{section_file.path.name}: 首个二级标题编号 {got} 与文件名前缀 {section_file.number_text} 不一致"]
        return []
    return [f"{section_file.path.name}: 未找到二级标题（格式示例：## {section_file.number_text} 小节标题）"]


# 方法章节表格存在性检查
_PIPE_TABLE_LINE_RE = re.compile(r"^\|.+\|$")
_METHODS_TABLE_KEYWORDS = ["试剂", "耗材", "仪器", "设备", "分组"]


def check_methods_sections_have_tables(section_files):
    """检查材料与方法相关小节是否包含 Markdown 管道表格。

    对文件名或标题中包含关键词（试剂/耗材/仪器/设备/分组）的小节，
    要求至少存在一个 Markdown 管道表格（``| col | col |``）。
    返回警告列表（不阻断，但会在报告中显示）。
    """
    warnings = []
    for sf in section_files:
        name_lower = sf.path.name.lower()
        title_lower = (sf.title or "").lower()
        combined = name_lower + title_lower
        matched_kw = [kw for kw in _METHODS_TABLE_KEYWORDS if kw in combined]
        if not matched_kw:
            continue
        try:
            text = sf.path.read_text(encoding="utf-8")
        except Exception:
            continue
        has_table = any(
            _PIPE_TABLE_LINE_RE.match(line.strip())
            for line in text.splitlines()
            if not re.match(r"^\|[-:\s|]+\|$", line.strip())  # skip separator rows
        )
        if not has_table:
            warnings.append(
                f"{sf.path.name}: 含关键词「{'、'.join(matched_kw)}」但未发现 Markdown 管道表格，"
                f"材料与方法相关小节应使用三线表呈现结构化数据"
            )
    return warnings


def normalize_title_text(text):
    return re.sub(r"\s+", "", (text or ""))


_INTRO_KEYWORDS = ("引言", "前言", "概述", "背景")
_CONCLUSION_KEYWORDS = ("实验结论", "小结", "结论", "总结")
_METHOD_KEYWORDS_FULL = ("材料与方法", "研究对象与方法", "实验方法", "方法学")


def _is_non_results_title(normalized_text):
    """判断标题是否属于非结果与讨论类小节（引言/方法/结论/小结）。"""
    t = normalized_text
    if not t:
        return True
    for kw in _INTRO_KEYWORDS:
        if kw in t:
            return True
    for kw in _METHOD_KEYWORDS_FULL:
        if kw in t:
            return True
    # 单独的"方法"需排除"方法学"已匹配的情况，且避免误伤含"方法"的结果小节
    # 仅当标题以"方法"结尾或"方法"前紧跟"与/和"时才算方法小节
    if re.search(r"(?:与|和)方法|方法$", t):
        return True
    for kw in _CONCLUSION_KEYWORDS:
        if kw in t:
            return True
    return False


def title_matches_required_section(title, required_name):
    t = normalize_title_text(title)
    r = normalize_title_text(required_name)
    if not t or not r:
        return False
    if r == "结果与讨论":
        # 排除法：不属于引言/方法/结论/小结的小节，即为结果与讨论
        return not _is_non_results_title(t)
    return r in t


def validate_research_chapter_sections(project_root, section_files, profile_path=None):
    profile, _ = load_profile(project_root, profile_path)
    required = (
        profile.get("structure", {}).get("research_chapter_required_sections", [])
        if isinstance(profile, dict)
        else []
    )
    if not isinstance(required, list) or not required:
        return []
    titles = [sf.title for sf in section_files]
    errors = []
    for req in required:
        if not any(title_matches_required_section(title, req) for title in titles):
            errors.append(f"研究章结构缺项：缺少“{req}”相关小节")
    return errors


def validate(
    project_root,
    chapter,
    chapter_dir=None,
    strict_heading=True,
    enforce_research_structure=False,
    profile_path=None,
):
    cdir = Path(chapter_dir) if chapter_dir else default_chapter_dir(project_root, chapter)
    if not cdir.exists():
        payload = {"ok": False, "error": "chapter_dir_not_found", "chapter_dir": str(cdir)}
        print(json.dumps(payload, ensure_ascii=False))
        return 2

    files = discover_section_files(cdir)
    if not files:
        payload = {"ok": False, "error": "no_section_files", "chapter_dir": str(cdir)}
        print(json.dumps(payload, ensure_ascii=False))
        return 2

    errors = validate_section_files(chapter, files)
    if strict_heading:
        for sf in files:
            errors.extend(check_first_heading_matches_filename(sf))
    if enforce_research_structure:
        errors.extend(validate_research_chapter_sections(project_root, files, profile_path=profile_path))

    # 检查方法小节是否包含表格（警告级别，不阻断）
    table_warnings = check_methods_sections_have_tables(files)

    payload = {
        "ok": len(errors) == 0,
        "chapter": str(chapter),
        "chapter_dir": str(cdir),
        "file_count": len(files),
        "files": [f.path.name for f in files],
        "errors": errors,
        "table_warnings": table_warnings,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if not errors else 2


def merge(project_root, chapter, chapter_dir=None, output_md=None, to_docx=False, docx_output=None):
    cdir = Path(chapter_dir) if chapter_dir else default_chapter_dir(project_root, chapter)
    files = discover_section_files(cdir)
    if not files:
        print(json.dumps({"ok": False, "error": "no_section_files", "chapter_dir": str(cdir)}, ensure_ascii=False))
        return 2

    errors = validate_section_files(chapter, files)
    for sf in files:
        errors.extend(check_first_heading_matches_filename(sf))
    if errors:
        print(json.dumps({"ok": False, "error": "validation_failed", "errors": errors}, ensure_ascii=False))
        return 2

    output_md_path = Path(output_md) if output_md else (
        Path(project_root) / "02_分章节文档_md" / f"第{chapter}章_合并.md"
    )
    output_md_path.parent.mkdir(parents=True, exist_ok=True)

    parts = []
    for sf in files:
        body = sf.path.read_text(encoding="utf-8").strip()
        parts.append(body)
    merged_text = "\n\n".join(parts).strip() + "\n"
    output_md_path.write_text(merged_text, encoding="utf-8")

    payload = {
        "ok": True,
        "chapter": str(chapter),
        "output_md": str(output_md_path),
        "merged_files": [f.path.name for f in files],
    }

    if to_docx:
        if docx_output:
            output_docx_path = Path(docx_output)
        else:
            output_docx_path = Path(project_root) / "02_分章节文档" / f"第{chapter}章_自动合并.docx"
        output_docx_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            from markdown_to_docx import convert_markdown_file
        except Exception:
            # fallback to same-dir import in isolated execution contexts
            script_dir = Path(__file__).resolve().parent
            sys.path.insert(0, str(script_dir))
            from markdown_to_docx import convert_markdown_file

        ok = convert_markdown_file(str(output_md_path), str(output_docx_path))
        payload["docx_output"] = str(output_docx_path)
        payload["docx_converted"] = bool(ok)
        if not ok:
            payload["ok"] = False
            payload["error"] = "markdown_to_docx_failed"
            print(json.dumps(payload, ensure_ascii=False))
            return 1

    print(json.dumps(payload, ensure_ascii=False))
    return 0


def extract_chapter_no(name):
    m = re.search(r"第(\d+)章", name)
    if not m:
        return 10**9
    return int(m.group(1))


# ---------------------------------------------------------------------------
# 全文合并排序：前置部分 → 正文章节 → 后置部分
# ---------------------------------------------------------------------------

_FRONT_MATTER_ORDER = [
    ("封面", 1),
    ("题名", 2),
    ("独创性", 3),
    ("授权", 4),
    ("中文摘要", 5),
    ("摘要", 6),       # 如果没有"中文摘要"则匹配"摘要"
    ("英文摘要", 7),
    ("abstract", 8),
    ("目录", 9),
    ("缩略", 10),
    ("符号", 11),
]

_BACK_MATTER_ORDER = [
    ("参考文献", 1),
    ("致谢", 2),
    ("攻读", 3),
    ("成果", 4),
    ("附录", 5),
]


def _full_merge_sort_key(path):
    """为全文合并生成排序键: (大类, 子序号, 文件名)。

    大类:
      0 = 前置部分 (封面/摘要/目录等)
      1 = 正文章节 (第X章)
      2 = 后置部分 (参考文献/致谢等)
      3 = 未识别
    """
    name = path.name if hasattr(path, "name") else os.path.basename(str(path))
    name_lower = name.lower().replace(" ", "")

    # 正文章节
    m = re.search(r"第(\d+)章", name)
    if m:
        return (1, int(m.group(1)), name)

    # 前置部分
    for keyword, order in _FRONT_MATTER_ORDER:
        if keyword in name_lower:
            return (0, order, name)

    # 后置部分
    for keyword, order in _BACK_MATTER_ORDER:
        if keyword in name_lower:
            return (2, order, name)

    # 未识别 → 放在正文章节之后、后置部分之前
    return (1, 10**6, name)


def merge_full(project_root, input_dir=None, output_md=None, to_docx=False, docx_output=None):
    source_dir = Path(input_dir) if input_dir else Path(project_root) / "02_分章节文档_md"
    if not source_dir.exists():
        print(json.dumps({"ok": False, "error": "input_dir_not_found", "input_dir": str(source_dir)}, ensure_ascii=False))
        return 2

    front_matter_dir = Path(project_root) / "atomic_md"
    front_matter_files = []
    if front_matter_dir.exists():
        front_matter_files = [p for p in front_matter_dir.glob("*.md") if p.is_file()]

    chapter_files = [p for p in source_dir.glob("*.md") if p.is_file()]
    chapter_files = sorted(front_matter_files + chapter_files, key=_full_merge_sort_key)
    if not chapter_files:
        print(json.dumps({"ok": False, "error": "no_chapter_md_files", "input_dir": str(source_dir)}, ensure_ascii=False))
        return 2

    output_md_path = Path(output_md) if output_md else Path(project_root) / "03_合并文档_md" / "完整博士论文.md"
    output_md_path.parent.mkdir(parents=True, exist_ok=True)
    merged = []
    for p in chapter_files:
        merged.append(p.read_text(encoding="utf-8").strip())
    output_md_path.write_text("\n\n".join(merged).strip() + "\n", encoding="utf-8")

    payload = {
        "ok": True,
        "input_dir": str(source_dir),
        "output_md": str(output_md_path),
        "merged_files": [p.name for p in chapter_files],
    }

    if to_docx:
        output_docx_path = Path(docx_output) if docx_output else Path(project_root) / "03_合并文档" / "完整博士论文.docx"
        output_docx_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            from markdown_to_docx import convert_markdown_file
        except Exception:
            script_dir = Path(__file__).resolve().parent
            sys.path.insert(0, str(script_dir))
            from markdown_to_docx import convert_markdown_file
        ok = convert_markdown_file(str(output_md_path), str(output_docx_path))
        payload["docx_output"] = str(output_docx_path)
        payload["docx_converted"] = bool(ok)
        if not ok:
            payload["ok"] = False
            payload["error"] = "markdown_to_docx_failed"
            print(json.dumps(payload, ensure_ascii=False))
            return 1

    print(json.dumps(payload, ensure_ascii=False))
    return 0


def validate_experiment_map(project_root, chapter, chapter_dir=None):
    """
    Validate two rules:
    1) Results/Discussion maps to method experiments one-by-one.
    2) One experiment has at least one standalone figure/table marker.

    Marker convention in atomic markdown:
    - In methods sections: [实验] EXP-2-1
    - In results/discussion sections: [对应实验] EXP-2-1
    - Figure/table markers: [图] 图2-1 或 [表] 表2-1
    """
    cdir = Path(chapter_dir) if chapter_dir else default_chapter_dir(project_root, chapter)
    if not cdir.exists():
        print(json.dumps({"ok": False, "error": "chapter_dir_not_found", "chapter_dir": str(cdir)}, ensure_ascii=False))
        return 2

    files = discover_section_files(cdir)
    if not files:
        print(json.dumps({"ok": False, "error": "no_section_files", "chapter_dir": str(cdir)}, ensure_ascii=False))
        return 2

    exp_re = re.compile(r"^\[实验\]\s*(?P<id>[A-Za-z0-9_.:-]+)\s*$")
    link_re = re.compile(r"^\[对应实验\]\s*(?P<id>[A-Za-z0-9_.:-]+)\s*$")
    figtab_re = re.compile(r"^\[(图|表)\]\s*(?P<label>.+?)\s*$")

    method_experiments = set()
    linked_experiments = []
    figtab_count_by_exp = {}
    errors = []
    
    def normalize_title(text):
        return re.sub(r"\s+", "", (text or ""))

    def is_methods_title(text):
        t = normalize_title(text)
        if not t:
            return False
        if "结果" in t and "讨论" in t:
            return False
        method_keywords = ("材料与方法", "研究对象与方法", "实验方法", "方法学", "方法")
        return any(k in t for k in method_keywords)

    def is_results_discussion_title(text):
        t = normalize_title(text)
        if not t:
            return False
        # 排除法：不属于引言/方法/结论/小结的小节，即为结果与讨论
        return not _is_non_results_title(t)

    for sf in files:
        text = sf.path.read_text(encoding="utf-8")
        title = sf.title
        section_kind = "other"
        if is_methods_title(title):
            section_kind = "methods"
        elif is_results_discussion_title(title):
            section_kind = "results_discussion"

        current_exp = None
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            m_exp = exp_re.match(line)
            if m_exp:
                exp_id = m_exp.group("id")
                if section_kind != "methods":
                    errors.append(f"{sf.path.name}: [实验] 标记应仅出现在“材料与方法”相关小节")
                    continue
                method_experiments.add(exp_id)
                current_exp = exp_id
                figtab_count_by_exp.setdefault(exp_id, 0)
                continue
            m_link = link_re.match(line)
            if m_link:
                exp_id = m_link.group("id")
                if section_kind != "results_discussion":
                    errors.append(f"{sf.path.name}: [对应实验] 标记应仅出现在“结果与讨论”相关小节")
                    continue
                linked_experiments.append(exp_id)
                current_exp = exp_id
                figtab_count_by_exp.setdefault(exp_id, 0)
                continue
            m_ft = figtab_re.match(line)
            if m_ft and section_kind == "results_discussion" and current_exp:
                figtab_count_by_exp[current_exp] = figtab_count_by_exp.get(current_exp, 0) + 1

        if section_kind == "results_discussion":
            has_link = any(link_re.match(x.strip()) for x in text.splitlines())
            if not has_link:
                errors.append(f"{sf.path.name}: 结果与讨论小节缺少 [对应实验] 标记")

    linked_set = set(linked_experiments)
    for exp_id in sorted(method_experiments):
        if exp_id not in linked_set:
            errors.append(f"实验 {exp_id}: 在材料与方法中定义，但未在结果与讨论中出现 [对应实验] 映射")

    for exp_id in sorted(linked_set):
        if exp_id not in method_experiments:
            errors.append(f"实验 {exp_id}: 在结果与讨论中出现 [对应实验]，但未在材料与方法中定义 [实验]")

    for exp_id in sorted(linked_set):
        if figtab_count_by_exp.get(exp_id, 0) <= 0:
            errors.append(f"实验 {exp_id}: 缺少 [图] 或 [表] 标记，违反“一实验一图/表”规则")

    payload = {
        "ok": len(errors) == 0,
        "chapter": str(chapter),
        "chapter_dir": str(cdir),
        "method_experiments": sorted(method_experiments),
        "linked_experiments": sorted(linked_set),
        "figure_or_table_count_by_experiment": figtab_count_by_exp,
        "errors": errors,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if not errors else 2


def infer_chapter_from_path(docx_path):
    name = Path(docx_path).name
    m = re.search(r"第(\d+)章", name)
    if m:
        return m.group(1)
    return None


def self_check(project_root, target_path, profile_path=None, chapter=None):
    path = Path(target_path)
    if not path.exists():
        print(json.dumps({"ok": False, "error": "path_not_found", "path": str(path)}, ensure_ascii=False))
        return 2

    try:
        from count_words import count_words
    except Exception:
        script_dir = Path(__file__).resolve().parent
        sys.path.insert(0, str(script_dir))
        from count_words import count_words

    try:
        profile, _ = load_profile(project_root, profile_path)
    except Exception as e:
        print(
            json.dumps(
                {"ok": False, "error": "profile_load_failed", "path": str(path), "detail": str(e)},
                ensure_ascii=False,
            )
        )
        return 2
    targets = profile.get("targets", {}) if isinstance(profile, dict) else {}
    chapter_targets = profile.get("chapter_targets", {}) if isinstance(profile, dict) else {}
    chapter_id = str(chapter) if chapter is not None else infer_chapter_from_path(target_path)
    body_target = int(targets.get("body_target_chars", 80000))
    if isinstance(chapter_targets, dict) and chapter_id and chapter_id in chapter_targets:
        body_target = int(chapter_targets.get(chapter_id))
    review_target = int(targets.get("review_target_chars", 0))
    review_in_scope = bool(targets.get("review_in_scope", False))
    references_min_count = int(targets.get("references_min_count", 80))
    min_chapters = int(targets.get("min_chapters", 5))
    if chapter_id:
        # 章节自检阶段不要求达到"全文参考文献下限"。
        references_min_count = 0

    wc = count_words(
        str(path),
        exclude_references=True,
        body_target_chars=body_target,
        review_target_chars=review_target,
        review_in_scope=review_in_scope,
    )

    # 质量报告仅在 docx 文件时运行（md 模式下跳过）
    qr = {"success": True, "overall_score": 100, "issue_summary": {"error": 0}}
    is_docx = str(path).lower().endswith(".docx")
    if is_docx:
        try:
            from check_quality import generate_quality_report
        except Exception:
            script_dir = Path(__file__).resolve().parent
            sys.path.insert(0, str(script_dir))
            from check_quality import generate_quality_report
        qr = generate_quality_report(
            str(path),
            verbose=False,
            body_target_chars=body_target,
            review_target_chars=review_target,
            review_in_scope=review_in_scope,
            references_min_count=references_min_count,
            min_chapters=min_chapters,
            enforce_full_structure=False,
        )

    body_completion_rate = float(wc.get("targets", {}).get("body_completion_rate", 0.0) or 0.0)
    word_passed = bool(wc.get("success")) and body_completion_rate >= 1.0
    quality_passed = (
        bool(qr.get("success"))
        and int(qr.get("overall_score", 0) or 0) >= 80
        and int(qr.get("issue_summary", {}).get("error", 0) or 0) == 0
    )

    # md 模式下也检查方法小节是否包含表格
    table_warnings = []
    if chapter_id:
        try:
            cdir = default_chapter_dir(project_root, int(chapter_id))
            if cdir.exists():
                files = discover_section_files(cdir)
                table_warnings = check_methods_sections_have_tables(files)
        except Exception:
            pass

    payload = {
        "ok": word_passed and quality_passed,
        "path": str(path),
        "chapter": chapter_id,
        "effective_body_target": body_target,
        "checks": {
            "word_passed": word_passed,
            "quality_passed": quality_passed,
            "quality_skipped": not is_docx,
            "body_completion_rate": body_completion_rate,
            "overall_score": qr.get("overall_score"),
            "error_count": qr.get("issue_summary", {}).get("error"),
        },
        "table_warnings": table_warnings,
        "word_count": wc,
        "quality_check": qr,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["ok"] else 1


def section_snapshot(project_root, chapter, section):
    try:
        from state_manager import backup_project_state
    except Exception:
        script_dir = Path(__file__).resolve().parent
        sys.path.insert(0, str(script_dir))
        from state_manager import backup_project_state

    snapshot_dir = backup_project_state(project_root)
    payload = {
        "ok": True,
        "project_root": os.path.abspath(project_root),
        "chapter": str(chapter),
        "section": str(section),
        "snapshot_dir": snapshot_dir,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


def parse_args():
    parser = argparse.ArgumentParser(description="原子化 Markdown 章节工作流工具")
    parser.add_argument("--project-root", default=".", help="项目根目录")
    sub = parser.add_subparsers(dest="command", required=True)

    v = sub.add_parser("validate", help="校验小节文件命名与编号连续性")
    v.add_argument("--chapter", required=True, help="章节号，如 2")
    v.add_argument("--chapter-dir", help="自定义章节原子文件目录")
    v.add_argument("--no-heading-check", action="store_true", help="不校验首个二级标题与文件名前缀一致性")
    v.add_argument(
        "--enforce-research-structure",
        action="store_true",
        help="按 thesis_profile 的 research_chapter_required_sections 校验研究章必备小节",
    )
    v.add_argument("--profile", help="thesis_profile.json 路径（可选）")

    m = sub.add_parser("merge", help="合并原子化小节 md 为章节 md，可选转 docx")
    m.add_argument("--chapter", required=True, help="章节号，如 2")
    m.add_argument("--chapter-dir", help="自定义章节原子文件目录")
    m.add_argument("--output-md", help="输出合并 md 路径")
    m.add_argument("--to-docx", action="store_true", help="合并后自动转为 docx")
    m.add_argument("--docx-output", help="输出 docx 路径")

    mf = sub.add_parser("merge-full", help="合并全部章节 md 为全文 md，可选转全文 docx")
    mf.add_argument("--input-dir", help="章节 md 目录（默认 <project_root>/02_分章节文档_md）")
    mf.add_argument("--output-md", help="全文 md 输出路径")
    mf.add_argument("--to-docx", action="store_true", help="合并后自动转为全文 docx")
    mf.add_argument("--docx-output", help="全文 docx 输出路径")

    vm = sub.add_parser("validate-experiment-map", help="校验实验映射和一实验一图/表规则")
    vm.add_argument("--chapter", required=True, help="章节号，如 2")
    vm.add_argument("--chapter-dir", help="自定义章节原子文件目录")

    s = sub.add_parser("self-check", help="章节完成后立即自检（字数+质量）")
    s.add_argument("--docx", dest="target", help="(deprecated alias for --target) .md 文件或目录路径")
    s.add_argument("--target", dest="target", help="待检查的 .md 文件或目录路径")
    s.add_argument("--profile", help="thesis_profile.json 路径（可选）")
    s.add_argument("--chapter", help="章节号（可选，不提供时从文件名推断）")

    snap = sub.add_parser("section-snapshot", help="小结完成后立即快照")
    snap.add_argument("--chapter", required=True, help="章节号")
    snap.add_argument("--section", required=True, help="小节编号，如 2.3")

    return parser.parse_args()


def main():
    args = parse_args()
    root = os.path.abspath(args.project_root)
    if args.command == "validate":
        code = validate(
            project_root=root,
            chapter=args.chapter,
            chapter_dir=args.chapter_dir,
            strict_heading=(not args.no_heading_check),
            enforce_research_structure=args.enforce_research_structure,
            profile_path=getattr(args, "profile", None),
        )
        sys.exit(code)
    if args.command == "merge":
        code = merge(
            project_root=root,
            chapter=args.chapter,
            chapter_dir=args.chapter_dir,
            output_md=args.output_md,
            to_docx=args.to_docx,
            docx_output=args.docx_output,
        )
        sys.exit(code)
    if args.command == "merge-full":
        code = merge_full(
            project_root=root,
            input_dir=args.input_dir,
            output_md=args.output_md,
            to_docx=args.to_docx,
            docx_output=args.docx_output,
        )
        sys.exit(code)
    if args.command == "validate-experiment-map":
        code = validate_experiment_map(
            project_root=root,
            chapter=args.chapter,
            chapter_dir=args.chapter_dir,
        )
        sys.exit(code)
    if args.command == "self-check":
        target = args.target
        if not target:
            print(json.dumps({"ok": False, "error": "missing --target or --docx"}, ensure_ascii=False))
            sys.exit(2)
        sys.exit(self_check(root, target, args.profile, args.chapter))
    if args.command == "section-snapshot":
        sys.exit(section_snapshot(root, args.chapter, args.section))


if __name__ == "__main__":
    main()
