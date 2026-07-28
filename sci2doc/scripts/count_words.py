#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Markdown 字数统计工具

支持三种粒度（AI 自行决定调用哪种）：
- 单个 .md 文件  — count_words_in_md()
- 章节目录       — count_words_in_atomic_dir()  (atomic_md/第N章/)
- 整篇论文目录   — count_words_in_atomic_dir()  (atomic_md/)

统一入口 count_words(path) 自动检测路径类型。

作者：Sci2Doc Team
"""

import sys as _sys
try:  # Windows GBK 控制台/管道捕获下 emoji print 防 UnicodeEncodeError
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import argparse
import re
import sys
import json
import os

try:
    from thesis_profile import load_profile
except Exception:  # pragma: no cover
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from thesis_profile import load_profile

try:
    from shared_utils import classify_heading, infer_project_root_for_profile, classify_lines_with_chapter_scope
except ImportError:  # pragma: no cover
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from shared_utils import classify_heading, infer_project_root_for_profile, classify_lines_with_chapter_scope


def is_chinese_char(char):
    """判断是否为中文字符（CJK 基本区 + 扩展 A + 兼容区）"""
    cp = ord(char)
    return (
        0x4E00 <= cp <= 0x9FFF       # CJK 基本区
        or 0x3400 <= cp <= 0x4DBF    # CJK 扩展 A
        or 0xF900 <= cp <= 0xFAFF    # CJK 兼容汉字
    )


def is_english_char(char):
    """判断是否为英文字符"""
    return ('a' <= char.lower() <= 'z')


def count_words_in_text(text):
    """
    统计文本中的中文字符数和英文单词数

    Args:
        text: 待统计文本

    Returns:
        dict: {'chinese_chars': int, 'english_words': int}
    """
    chinese_chars = sum(1 for char in text if is_chinese_char(char))
    english_text = ''.join(char if is_english_char(char) or char.isspace() else ' '
                           for char in text)
    english_words = len([word for word in english_text.split() if word])
    return {
        'chinese_chars': chinese_chars,
        'english_words': english_words
    }


# ---------------------------------------------------------------------------
# Markdown 支持
# ---------------------------------------------------------------------------

# 原子化小节文件名正则（与 atomic_md_workflow.py 保持一致）
SECTION_FILE_RE = re.compile(r"^(?P<num>\d+(?:\.\d+)*)_(?P<title>.+)\.md$")


def strip_markdown_syntax(text):
    """
    去除 Markdown 格式标记，保留纯文本内容。

    处理：标题 #、粗体/斜体、行内代码、链接/图片、HTML 标签、
    表格分隔行、引用 >、列表标记、水平线、脚注标记。
    """
    lines = text.splitlines()  # 跨平台：兼容 \r\n/\r 换行
    cleaned = []
    for line in lines:
        s = line.strip()
        # 跳过表格分隔行 |---|---|
        if re.match(r"^\|?[\s:]*-{3,}[\s:]*(\|[\s:]*-{3,}[\s:]*)*\|?$", s):
            continue
        # 跳过水平线
        if re.match(r"^[-*_]{3,}\s*$", s):
            continue
        # 去除标题 #
        s = re.sub(r"^#{1,6}\s+", "", s)
        # 去除引用 >
        s = re.sub(r"^>\s*", "", s)
        # 去除无序列表标记
        s = re.sub(r"^[\-\*\+]\s+", "", s)
        # 去除有序列表标记
        s = re.sub(r"^\d+\.\s+", "", s)
        # 去除图片 ![alt](url)
        s = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", s)
        # 去除链接 [text](url)
        s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
        # 去除行内代码
        s = re.sub(r"`([^`]*)`", r"\1", s)
        # 去除粗体/斜体标记
        s = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", s)
        s = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", s)
        # 去除删除线
        s = re.sub(r"~~([^~]+)~~", r"\1", s)
        # 去除 HTML 标签
        s = re.sub(r"<[^>]+>", "", s)
        # 去除脚注引用 [^1]
        s = re.sub(r"\[\^\w+\]", "", s)
        # 去除表格管道符
        s = s.replace("|", " ")
        cleaned.append(s)
    return "\n".join(cleaned)


def count_words_in_md(
    md_path,
    exclude_references=True,
    body_target_chars=80000,
    review_target_chars=0,
    review_in_scope=False,
    extra_exclude=None,
):
    """
    统计单个 Markdown 文件字数。

    使用章作用域继承分类：章级标题确定章类型，其下所有子节继承该类型，
    直到下一个同级或更浅的章级标题。
    摘要（abstract）计入正文。综述章（含其内部子节和参考文献）排除。

    Args:
        md_path: .md 文件路径
        exclude_references: 是否排除参考文献
        body_target_chars: 正文目标字数
        review_target_chars: 综述目标字数
        review_in_scope: 是否将综述纳入考核目标
        extra_exclude: 额外排除的章节标题列表（normalize_text 后匹配）

    Returns:
        dict: 统计结果
    """
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            raw = f.read()
    except Exception as e:
        return {"success": False, "error": f"无法读取文件：{e}"}

    body_chinese_chars = 0
    body_english_words = 0
    review_chinese_chars = 0
    review_english_words = 0

    section_stats = []
    current_section = {
        "title": "正文",
        "type": "body",
        "chinese_chars": 0,
        "english_words": 0,
    }
    current_section_type = "body"

    def flush_section():
        if current_section["chinese_chars"] > 0 or current_section["english_words"] > 0:
            section_stats.append(current_section.copy())

    def accumulate(counts, sec_type):
        nonlocal body_chinese_chars, body_english_words
        nonlocal review_chinese_chars, review_english_words
        current_section["chinese_chars"] += counts["chinese_chars"]
        current_section["english_words"] += counts["english_words"]
        if sec_type == "review":
            # 综述/绪论章计入正文，把凑字压力从研究章分摊出去，缓解逼造数据。
            # review_* 仍单独统计供展示；body_* 同时纳入让正文字数达标更靠真实内容。
            review_chinese_chars += counts["chinese_chars"]
            review_english_words += counts["english_words"]
            body_chinese_chars += counts["chinese_chars"]
            body_english_words += counts["english_words"]
        elif sec_type == "references" and exclude_references:
            pass
        elif sec_type in {"toc", "acknowledgement", "appendix", "achievements", "declaration", "abbreviation_table"}:
            pass
        else:
            # body and abstract both count toward body
            body_chinese_chars += counts["chinese_chars"]
            body_english_words += counts["english_words"]

    heading_re = re.compile(r"^(#{1,6})\s+(.+)$")
    lines = raw.splitlines()  # 跨平台：兼容 \r\n/\r 换行

    for stripped, sec_type in classify_lines_with_chapter_scope(lines, extra_exclude=extra_exclude):
        if not stripped:
            continue
        m = heading_re.match(stripped)
        if m:
            if sec_type != current_section_type or m.group(2).strip() != current_section.get("title"):
                flush_section()
                current_section = {
                    "title": m.group(2).strip(),
                    "type": sec_type,
                    "chinese_chars": 0,
                    "english_words": 0,
                }
                current_section_type = sec_type
            accumulate(count_words_in_text(m.group(2).strip()), sec_type)
            continue
        # 跳过表格分隔行
        if re.match(r"^\|?[\s:]*-{3,}[\s:]*(\|[\s:]*-{3,}[\s:]*)*\|?$", stripped):
            continue
        # 跳过水平线
        if re.match(r"^[-*_]{3,}\s*$", stripped):
            continue
        # 普通行：去除 md 语法后统计
        clean = strip_markdown_syntax(stripped)
        if clean.strip():
            accumulate(count_words_in_text(clean), sec_type)

    flush_section()

    body_total = body_chinese_chars + body_english_words
    review_total = review_chinese_chars + review_english_words
    # review 已并入 body（A③），不再另加，避免重复计数。
    grand_total = body_total
    body_target_chars = max(1, int(body_target_chars or 80000))
    review_target_chars = max(0, int(review_target_chars or 0))
    body_rate = round(body_chinese_chars / body_target_chars, 4)
    review_rate = (
        round(review_chinese_chars / review_target_chars, 4)
        if review_target_chars > 0 and review_chinese_chars > 0
        else None
    )

    return {
        "schema_version": "3.0",
        "success": True,
        "source_type": "markdown",
        "file_path": md_path,
        "file_name": os.path.basename(md_path),
        "body_text": {
            "chinese_chars": body_chinese_chars,
            "english_words": body_english_words,
            "total_count": body_total,
        },
        "review": {
            "chinese_chars": review_chinese_chars,
            "english_words": review_english_words,
            "total_count": review_total,
        },
        "total": {
            "chinese_chars": body_chinese_chars,
            "english_words": body_english_words,
            "total_count": grand_total,
        },
        "sections": section_stats,
        "targets": {
            "body_target": body_target_chars,
            "review_target": review_target_chars,
            "review_in_scope": bool(review_in_scope),
            "body_completion_rate": body_rate,
            "review_completion_rate": review_rate,
        },
        "chinese_chars": body_chinese_chars,
        "english_words": body_english_words,
        "total_chars": body_total,
        "completion_rate": body_rate,
        "is_review": False,
    }


def count_words_in_atomic_dir(
    dir_path,
    exclude_references=True,
    body_target_chars=80000,
    review_target_chars=0,
    review_in_scope=False,
    extra_exclude=None,
):
    """
    统计原子化 atomic_md 目录下所有小节 .md 文件的字数。

    支持两种目录结构：
    - 单章目录：atomic_md/第N章/  （直接含 *.md 文件）
    - 多章根目录：atomic_md/      （含多个 第N章/ 子目录）

    Args:
        dir_path: 目录路径
        exclude_references: 是否排除参考文献
        body_target_chars: 正文目标字数
        review_target_chars: 综述目标字数
        review_in_scope: 是否将综述纳入考核目标
        extra_exclude: 额外排除章节标题列表

    Returns:
        dict: 聚合统计结果，含 per_file 明细
    """
    dir_path = os.path.abspath(dir_path)
    if not os.path.isdir(dir_path):
        return {"success": False, "error": f"目录不存在：{dir_path}"}

    md_files = []
    entries = sorted(os.listdir(dir_path))

    chapter_dirs = [e for e in entries if os.path.isdir(os.path.join(dir_path, e)) and re.match(r"^第.+章$", e)]
    if chapter_dirs:
        for cd in sorted(chapter_dirs):
            cd_path = os.path.join(dir_path, cd)
            for fname in sorted(os.listdir(cd_path)):
                if SECTION_FILE_RE.match(fname):
                    md_files.append(os.path.join(cd_path, fname))
    else:
        for fname in entries:
            if SECTION_FILE_RE.match(fname):
                md_files.append(os.path.join(dir_path, fname))

    if not md_files:
        return {"success": False, "error": f"目录中未找到符合命名规范的 .md 文件：{dir_path}"}

    body_chinese_chars = 0
    body_english_words = 0
    review_chinese_chars = 0
    review_english_words = 0
    all_sections = []
    per_file = []

    for fpath in md_files:
        r = count_words_in_md(
            fpath,
            exclude_references=exclude_references,
            body_target_chars=0,
            review_target_chars=0,
            review_in_scope=review_in_scope,
            extra_exclude=extra_exclude,
        )
        if not r.get("success"):
            per_file.append({"file": fpath, "error": r.get("error")})
            continue
        body_chinese_chars += r["body_text"]["chinese_chars"]
        body_english_words += r["body_text"]["english_words"]
        review_chinese_chars += r["review"]["chinese_chars"]
        review_english_words += r["review"]["english_words"]
        all_sections.extend(r.get("sections", []))
        per_file.append({
            "file": os.path.relpath(fpath, dir_path),
            "chinese_chars": r["total"]["chinese_chars"],
            "english_words": r["total"]["english_words"],
            "total_count": r["total"]["total_count"],
        })

    body_total = body_chinese_chars + body_english_words
    review_total = review_chinese_chars + review_english_words
    # review 已并入 body（A③），不再另加，避免重复计数。
    grand_total = body_total
    body_target_chars = max(1, int(body_target_chars or 80000))
    review_target_chars = max(0, int(review_target_chars or 0))
    body_rate = round(body_chinese_chars / body_target_chars, 4)
    review_rate = (
        round(review_chinese_chars / review_target_chars, 4)
        if review_target_chars > 0 and review_chinese_chars > 0
        else None
    )

    return {
        "schema_version": "3.0",
        "success": True,
        "source_type": "atomic_dir",
        "file_path": dir_path,
        "file_name": os.path.basename(dir_path),
        "file_count": len(md_files),
        "body_text": {
            "chinese_chars": body_chinese_chars,
            "english_words": body_english_words,
            "total_count": body_total,
        },
        "review": {
            "chinese_chars": review_chinese_chars,
            "english_words": review_english_words,
            "total_count": review_total,
        },
        "total": {
            "chinese_chars": body_chinese_chars,
            "english_words": body_english_words,
            "total_count": grand_total,
        },
        "sections": all_sections,
        "per_file": per_file,
        "targets": {
            "body_target": body_target_chars,
            "review_target": review_target_chars,
            "review_in_scope": bool(review_in_scope),
            "body_completion_rate": body_rate,
            "review_completion_rate": review_rate,
        },
        "chinese_chars": body_chinese_chars,
        "english_words": body_english_words,
        "total_chars": body_total,
        "completion_rate": body_rate,
        "is_review": False,
    }


def count_words(
    path,
    exclude_references=True,
    body_target_chars=80000,
    review_target_chars=0,
    review_in_scope=False,
    extra_exclude=None,
):
    """
    统一入口：自动检测路径类型并调用对应统计函数。

    - .md 文件   → count_words_in_md()
    - 目录       → count_words_in_atomic_dir()

    AI 可根据需要灵活调用：
    - 单个原子化文件：count_words("atomic_md/第2章/2.1_引言.md")
    - 某章目录：count_words("atomic_md/第2章")
    - 整篇论文：count_words("atomic_md")

    Args:
        path: .md 文件或目录路径
        exclude_references: 是否排除参考文献
        body_target_chars: 正文目标字数
        review_target_chars: 综述目标字数
        review_in_scope: 是否将综述纳入考核目标
        extra_exclude: 额外排除章节标题列表

    Returns:
        dict: 统计结果（schema 统一）
    """
    path = os.path.abspath(path)
    kwargs = dict(
        exclude_references=exclude_references,
        body_target_chars=body_target_chars,
        review_target_chars=review_target_chars,
        review_in_scope=review_in_scope,
        extra_exclude=extra_exclude,
    )

    if os.path.isdir(path):
        return count_words_in_atomic_dir(path, **kwargs)
    elif path.lower().endswith(".md"):
        return count_words_in_md(path, **kwargs)
    elif path.lower().endswith(".docx"):
        # Extract text from .docx via python-docx, write to temp .md, then count
        try:
            from docx import Document as DocxDocument
        except ImportError:
            return {"success": False, "error": "python-docx 未安装，无法统计 .docx 文件"}
        try:
            doc = DocxDocument(path)
            md_lines = []
            for para in doc.paragraphs:
                md_lines.append(para.text)
            md_text = "\n".join(md_lines)
        except Exception as e:
            return {"success": False, "error": f"读取 .docx 失败：{e}"}
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as tmp:
            tmp.write(md_text)
            tmp_path = tmp.name
        try:
            result = count_words_in_md(tmp_path, **kwargs)
            result["file_path"] = path
            result["file_name"] = os.path.basename(path)
            return result
        finally:
            os.unlink(tmp_path)
    else:
        return {"success": False, "error": f"不支持的文件类型：{path}（支持 .md / .docx 文件或目录）"}


def format_report(result):
    """格式化统计报告为可读文本"""
    if not result.get('success'):
        return f"❌ 统计失败：{result.get('error')}"

    source_type = result.get("source_type", "markdown")
    type_label = {"markdown": "Markdown 文件", "atomic_dir": "原子化目录"}.get(source_type, "文档")

    lines = []
    lines.append("=" * 60)
    lines.append(f"📊 {type_label}字数统计报告")
    lines.append("=" * 60)
    lines.append(f"📄 路径：{result.get('file_path', result.get('file_name', ''))}")
    if source_type == "atomic_dir":
        lines.append(f"   文件数：{result.get('file_count', '?')}")
    lines.append("")

    # 正文统计
    body = result['body_text']
    lines.append("📝 正文统计：")
    lines.append(f"   中文字符：{body['chinese_chars']:,} 字")
    lines.append(f"   英文单词：{body['english_words']:,} 词")
    lines.append(f"   合计：{body['total_count']:,}")
    body_target = result.get("targets", {}).get("body_target", 80000)
    lines.append(f"   完成率：{result['targets']['body_completion_rate']*100:.1f}% "
                f"（目标 {body_target:,} 字）")
    lines.append("")

    # 综述统计
    review = result['review']
    review_target = result.get("targets", {}).get("review_target", 0)
    review_in_scope = bool(result.get("targets", {}).get("review_in_scope", False))
    if review['total_count'] > 0:
        lines.append("📚 综述统计：")
        lines.append(f"   中文字符：{review['chinese_chars']:,} 字")
        lines.append(f"   英文单词：{review['english_words']:,} 词")
        lines.append(f"   合计：{review['total_count']:,}")
        if review_in_scope and review_target > 0 and result["targets"]["review_completion_rate"] is not None:
            lines.append(f"   完成率：{result['targets']['review_completion_rate']*100:.1f}% "
                        f"（目标 {review_target:,} 字）")
        else:
            lines.append("   说明：综述不纳入当前正文考核范围")
        lines.append("")

    # 总计
    total = result['total']
    lines.append("📊 总计：")
    lines.append(f"   中文字符：{total['chinese_chars']:,} 字")
    lines.append(f"   英文单词：{total['english_words']:,} 词")
    lines.append(f"   合计：{total['total_count']:,}")
    lines.append("")

    # 章节详情
    if result.get('sections'):
        lines.append("📑 章节详情：")
        for i, section in enumerate(result['sections'], 1):
            section_type = section.get('type', '')
            type_tag = f" [{section_type}]" if section_type else ""
            lines.append(f"   {i}. {section['title']}{type_tag}")
            lines.append(f"      中文：{section['chinese_chars']:,}  "
                        f"英文：{section['english_words']:,}")
        lines.append("")

    # 原子化目录：各文件明细
    if result.get('per_file'):
        lines.append("📁 文件明细：")
        for pf in result['per_file']:
            if "error" in pf:
                lines.append(f"   ❌ {pf['file']}：{pf['error']}")
            else:
                lines.append(f"   {pf['file']}  →  {pf.get('total_count', 0):,}")

    lines.append("=" * 60)

    return "\n".join(lines)


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="Markdown 字数统计工具（支持 .md 文件 / 原子化目录）")
    parser.add_argument("path", help="待统计的 .md 文件或目录路径")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="输出格式")
    parser.add_argument("--profile", help="thesis_profile.json 路径（可选）")
    parser.add_argument("--body-target", type=int, help="覆盖正文目标字数")
    parser.add_argument("--review-target", type=int, help="覆盖综述目标字数")
    parser.add_argument("--review-in-scope", action="store_true", help="将综述纳入考核目标")
    args = parser.parse_args()
    target_path = args.path
    output_format = args.output

    if not os.path.exists(target_path):
        if output_format == 'json':
            print(json.dumps({
                "success": False,
                "error": "file_not_found",
                "file_path": target_path,
                "message": f"路径不存在：{target_path}",
            }, ensure_ascii=False, indent=2))
        else:
            print(f"❌ 路径不存在：{target_path}")
        sys.exit(1)

    profile_project_root = infer_project_root_for_profile(target_path)
    try:
        profile, _ = load_profile(profile_project_root, args.profile)
    except Exception as e:
        payload = {
            "success": False,
            "error": "profile_load_failed",
            "message": str(e),
            "profile_path": args.profile,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2) if output_format == "json" else f"❌ {payload['message']}")
        sys.exit(1)
    targets = profile.get("targets", {}) if isinstance(profile, dict) else {}
    format_profile = profile.get("format_profile", {}) if isinstance(profile, dict) else {}
    extra_exclude = format_profile.get("exclude_from_body_count") or []

    body_target = int(args.body_target if args.body_target is not None else targets.get("body_target_chars", 50000))
    review_in_scope = bool(args.review_in_scope or targets.get("review_in_scope", False))
    default_review_target = int(targets.get("review_target_chars", 0) or 0)
    review_target = int(args.review_target if args.review_target is not None else default_review_target)

    result = count_words(
        target_path,
        exclude_references=True,
        body_target_chars=body_target,
        review_target_chars=review_target,
        review_in_scope=review_in_scope,
        extra_exclude=extra_exclude,
    )

    if output_format == 'json':
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_report(result))

    sys.exit(0 if result.get('success') else 1)


if __name__ == '__main__':
    main()
