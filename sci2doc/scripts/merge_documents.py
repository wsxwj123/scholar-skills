#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
兼容入口：合并博士论文文档。

说明：
- 该脚本保留旧命令名 `merge_documents.py`，内部统一复用 `merge_chapters.py`。
- 默认目录采用当前项目布局：
  - 输入章节：02_分章节文档
  - 输出文档：03_合并文档/完整博士论文.docx
  - 前置部分（可选）：atomic_md/ 中的封面、摘要等前置 markdown
"""

import sys as _sys
try:  # Windows GBK 控制台/管道捕获下 emoji print 防 UnicodeEncodeError
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import argparse
import os
import sys
from pathlib import Path

# Ensure sibling scripts are importable regardless of CWD
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

try:
    from merge_chapters import (
        add_header_footer,
        generate_toc,
        merge_docx_files,
        resolve_merge_order,
    )
    from front_matter_renderer import render_front_matter
    from docx import Document
except Exception as e:  # pragma: no cover
    print(f"❌ 依赖加载失败：{e}")
    print("请检查 python-docx 是否已安装，并确保 merge_chapters.py 存在")
    sys.exit(1)


def _resolve(base_root, value):
    if not value:
        return None
    p = Path(value)
    if p.is_absolute():
        return str(p)
    return str((base_root / p).resolve())


def _default_front_matter(project_root):
    """Prefer materialized docx front matter, fallback to legacy paths."""
    chapter_docx_dir = project_root / "02_分章节文档"
    cover_docx = chapter_docx_dir / "封面.docx"
    title_page_docx = chapter_docx_dir / "题名页.docx"
    declaration_docx = chapter_docx_dir / "独创性声明与授权书.docx"
    abstract_docx = chapter_docx_dir / "中文摘要.docx"
    abstract_en_docx = chapter_docx_dir / "英文摘要.docx"

    # Legacy fallback: 01_前置部分 (no longer created by init, but tolerate existing projects)
    front = project_root / "01_前置部分"
    legacy_cover_docx = front / "封面.docx"
    legacy_abstract_docx = front / "中文摘要.docx"
    legacy_abstract_en_docx = front / "英文摘要.docx"

    return {
        "cover": str(cover_docx) if cover_docx.exists() else (str(legacy_cover_docx) if legacy_cover_docx.exists() else None),
        "title_page": str(title_page_docx) if title_page_docx.exists() else None,
        "declaration": str(declaration_docx) if declaration_docx.exists() else None,
        "abstract": str(abstract_docx) if abstract_docx.exists() else (str(legacy_abstract_docx) if legacy_abstract_docx.exists() else None),
        "abstract_en": str(abstract_en_docx) if abstract_en_docx.exists() else (str(legacy_abstract_en_docx) if legacy_abstract_en_docx.exists() else None),
    }


def parse_args():
    parser = argparse.ArgumentParser(description="兼容入口：调用 merge_chapters.py 合并文档")
    parser.add_argument("--project-root", default=".", help="项目根目录")
    parser.add_argument("--input-dir", help="章节目录，默认 <project_root>/02_分章节文档")
    parser.add_argument("--output", help="输出路径，默认 <project_root>/03_合并文档/完整博士论文.docx")
    parser.add_argument("--cover", help="封面文件路径（可选）")
    parser.add_argument("--title-page", help="题名页文件路径（可选）")
    parser.add_argument("--declaration", help="独创性声明/授权书文件路径（可选）")
    parser.add_argument("--abstract", help="中文摘要文件路径（可选）")
    parser.add_argument("--abstract-en", help="英文摘要文件路径（可选）")
    parser.add_argument("--title", default="论文标题", help="论文标题（用于页眉）")
    parser.add_argument("--add-toc", action="store_true", help="合并后生成目录")
    parser.add_argument("--add-header", action="store_true", help="合并后添加页眉页脚")
    parser.add_argument("--require-high-fidelity", action="store_true", help="要求使用 docxcompose 高保真合并")
    return parser.parse_args()


def main():
    args = parse_args()
    project_root = Path(args.project_root).resolve()

    print("⚠️  merge_documents.py 已切换为兼容包装器，请优先使用 merge_chapters.py")

    input_dir = Path(
        _resolve(project_root, args.input_dir) if args.input_dir else project_root / "02_分章节文档"
    )
    output_path = Path(
        _resolve(project_root, args.output)
        if args.output
        else project_root / "03_合并文档" / "完整博士论文.docx"
    )

    if not input_dir.exists():
        print(f"❌ 章节目录不存在：{input_dir}")
        sys.exit(1)

    render_front_matter(str(project_root), overwrite=False, to_docx=True)
    defaults = _default_front_matter(project_root)
    cover = _resolve(project_root, args.cover) if args.cover else defaults["cover"]
    title_page = _resolve(project_root, args.title_page) if args.title_page else defaults["title_page"]
    declaration = _resolve(project_root, args.declaration) if args.declaration else defaults["declaration"]
    abstract = _resolve(project_root, args.abstract) if args.abstract else defaults["abstract"]
    abstract_en = _resolve(project_root, args.abstract_en) if args.abstract_en else defaults["abstract_en"]

    file_list = resolve_merge_order(
        input_dir=str(input_dir),
        cover=cover,
        title_page=title_page,
        declaration=declaration,
        abstract=abstract,
        abstract_en=abstract_en,
    )

    if not file_list:
        print(f"❌ 未找到可合并 docx 文件：{input_dir}")
        sys.exit(1)

    print(f"📁 待合并文件数：{len(file_list)}")
    result = merge_docx_files(
        file_list,
        str(output_path),
        require_high_fidelity=args.require_high_fidelity,
    )

    if not result.get("success"):
        print(f"❌ 合并失败：{result.get('error')}")
        sys.exit(1)

    if args.add_toc or args.add_header:
        doc = Document(str(output_path))
        if args.add_toc:
            generate_toc(doc)
        if args.add_header:
            add_header_footer(doc, args.title, project_root=str(project_root))
        doc.save(str(output_path))

    print("✅ 合并完成")
    print(f"📄 输出文件：{output_path}")
    print(f"🔧 合并引擎：{result.get('merge_engine', 'unknown')}")


if __name__ == "__main__":
    main()
