#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图表编号注册表管理

功能：
1. 注册中文图编号与 SCI 原图的映射关系
2. 字母子图转数字：A→1, B→2, ..., Z→26
3. 章节优先编号：第N章第M个图 = 图N-M
4. 冲突检测与验证
5. 导出映射表
6. 与 atomic_md 中的 [图] 标记交叉验证

作者：Sci2Doc Team
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

# ---------------------------------------------------------------------------
# 路径工具
# ---------------------------------------------------------------------------

def resolve_path(project_root, *parts):
    return os.path.join(os.path.abspath(project_root), *parts)


def _figure_map_path(project_root):
    return resolve_path(project_root, "figure_map.json")


# ---------------------------------------------------------------------------
# 字母 → 数字 转换
# ---------------------------------------------------------------------------

def letter_to_number(letter):
    """
    将子图字母转换为序号。
    A/a → 1, B/b → 2, ..., Z/z → 26。
    非字母输入返回 None。
    """
    if not letter or not isinstance(letter, str) or len(letter) != 1:
        return None
    ch = letter.upper()
    if 'A' <= ch <= 'Z':
        return ord(ch) - ord('A') + 1
    return None


def number_to_letter(num):
    """序号转子图字母：1→A, 2→B, ..., 26→Z。"""
    if not isinstance(num, int) or num < 1 or num > 26:
        return None
    return chr(ord('A') + num - 1)


# ---------------------------------------------------------------------------
# 源图解析
# ---------------------------------------------------------------------------

# 匹配 "Figure 1A", "Figure 2B", "Fig. 3C", "Figure 10", "Fig 4a" 等
_SOURCE_FIGURE_RE = re.compile(
    r'(?:Figure|Fig\.?)\s*(\d+)\s*([A-Za-z])?',
    re.IGNORECASE,
)


def parse_source_figure(source_str):
    """
    解析 SCI 原图标识。

    输入示例：
      "Figure 1A" → {"figure_num": 1, "subfigure": "A", "subfigure_seq": 1}
      "Fig. 3"    → {"figure_num": 3, "subfigure": None, "subfigure_seq": None}
      "Figure 10B" → {"figure_num": 10, "subfigure": "B", "subfigure_seq": 2}

    返回 dict 或 None（无法解析时）。
    """
    if not source_str:
        return None
    m = _SOURCE_FIGURE_RE.search(source_str)
    if not m:
        return None
    fig_num = int(m.group(1))
    sub = m.group(2)
    sub_upper = sub.upper() if sub else None
    sub_seq = letter_to_number(sub) if sub else None
    return {
        "figure_num": fig_num,
        "subfigure": sub_upper,
        "subfigure_seq": sub_seq,
    }


# ---------------------------------------------------------------------------
# 中文图编号
# ---------------------------------------------------------------------------

# 匹配 "图1-1", "图 3-6", "图12-2" 等
_CN_FIGURE_RE = re.compile(r'图\s*(\d+)\s*[-]\s*(\d+)')


def make_cn_figure_id(chapter, seq):
    """生成中文图编号：图{chapter}-{seq}。"""
    return f"图{chapter}-{seq}"


def parse_cn_figure_id(cn_id):
    """
    解析中文图编号。
    "图3-2" → {"chapter": 3, "seq": 2}
    返回 dict 或 None。
    """
    if not cn_id:
        return None
    m = _CN_FIGURE_RE.search(cn_id)
    if not m:
        return None
    return {"chapter": int(m.group(1)), "seq": int(m.group(2))}


# ---------------------------------------------------------------------------
# 注册表 CRUD
# ---------------------------------------------------------------------------

def load_figure_map(project_root):
    """加载 figure_map.json，不存在则返回空 dict。"""
    path = _figure_map_path(project_root)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, OSError):
        return {}


def save_figure_map(project_root, figure_map):
    """保存 figure_map.json（原子写入 + 文件锁）。"""
    path = _figure_map_path(project_root)
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)

    lock_file = path + ".lock"
    import tempfile

    # Acquire simple file lock (cross-platform)
    fd_lock = None
    try:
        try:
            import fcntl
            fd_lock = open(lock_file, "a+", encoding="utf-8")
            fcntl.flock(fd_lock.fileno(), fcntl.LOCK_EX)
        except ImportError:
            pass  # No fcntl on Windows; skip locking

        # Atomic write via temp file + rename
        fd, tmp_path = tempfile.mkstemp(prefix=".tmp_figmap_", suffix=".json", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(figure_map, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
    finally:
        if fd_lock is not None:
            try:
                import fcntl
                fcntl.flock(fd_lock.fileno(), fcntl.LOCK_UN)
            except (ImportError, OSError):
                pass
            fd_lock.close()


def register_figure(project_root, chapter, seq, source_figure, title="", overwrite=False):
    """
    注册一条图映射。

    Args:
        chapter: 章节号 (int)
        seq: 章内序号 (int)
        source_figure: SCI 原图标识，如 "Figure 1A"
        title: 中文图标题（可选）
        overwrite: 是否覆盖已有映射

    Returns:
        dict: {"ok": bool, "cn_id": str, "message": str}
    """
    chapter = int(chapter)
    seq = int(seq)
    cn_id = make_cn_figure_id(chapter, seq)

    parsed = parse_source_figure(source_figure)
    if parsed is None:
        return {"ok": False, "cn_id": cn_id, "message": f"无法解析源图标识：{source_figure}"}

    figure_map = load_figure_map(project_root)

    # 冲突检测
    if cn_id in figure_map and not overwrite:
        existing = figure_map[cn_id]
        return {
            "ok": False,
            "cn_id": cn_id,
            "message": f"编号冲突：{cn_id} 已映射到 {existing.get('source_figure', '?')}，使用 --overwrite 覆盖",
        }

    # 反向冲突：同一 source_figure 是否已被其他 cn_id 占用
    for existing_cn, entry in figure_map.items():
        if existing_cn == cn_id:
            continue
        if entry.get("source_figure", "").upper() == source_figure.upper():
            return {
                "ok": False,
                "cn_id": cn_id,
                "message": f"源图冲突：{source_figure} 已被 {existing_cn} 占用",
            }

    figure_map[cn_id] = {
        "source_figure": source_figure,
        "chapter": chapter,
        "seq": seq,
        "parsed_source": parsed,
        "title": title or "",
        "registered_at": datetime.now().isoformat(timespec="seconds"),
    }

    save_figure_map(project_root, figure_map)
    return {"ok": True, "cn_id": cn_id, "message": f"已注册 {cn_id} ← {source_figure}"}


def unregister_figure(project_root, cn_id):
    """删除一条映射。"""
    figure_map = load_figure_map(project_root)
    if cn_id not in figure_map:
        return {"ok": False, "message": f"{cn_id} 不存在"}
    del figure_map[cn_id]
    save_figure_map(project_root, figure_map)
    return {"ok": True, "message": f"已删除 {cn_id}"}


def list_figures(project_root, chapter=None):
    """
    列出映射表。可按章节过滤。
    返回 list[dict]。
    """
    figure_map = load_figure_map(project_root)
    results = []
    for cn_id, entry in sorted(figure_map.items()):
        if chapter is not None and entry.get("chapter") != int(chapter):
            continue
        results.append({"cn_id": cn_id, **entry})
    return results


# ---------------------------------------------------------------------------
# 验证
# ---------------------------------------------------------------------------

def validate_figure_map(project_root):
    """
    验证 figure_map.json 的完整性：
    1. 每章编号连续（图N-1, 图N-2, ...）
    2. 无重复 source_figure
    3. 所有 source_figure 可解析

    Returns:
        dict: {"ok": bool, "errors": list[str], "warnings": list[str]}
    """
    figure_map = load_figure_map(project_root)
    errors = []
    warnings = []

    if not figure_map:
        return {"ok": True, "errors": [], "warnings": ["figure_map.json 为空或不存在"]}

    # 按章分组
    by_chapter = {}
    source_seen = {}
    for cn_id, entry in figure_map.items():
        ch = entry.get("chapter")
        seq = entry.get("seq")
        src = entry.get("source_figure", "")

        # 解析检查
        parsed = parse_cn_figure_id(cn_id)
        if parsed is None:
            errors.append(f"无法解析中文编号：{cn_id}")
            continue

        if parsed["chapter"] != ch or parsed["seq"] != seq:
            errors.append(f"{cn_id} 的 chapter/seq 字段与编号不一致")

        # source 可解析性
        if src and parse_source_figure(src) is None:
            errors.append(f"{cn_id} 的 source_figure 无法解析：{src}")

        # 重复 source 检测
        src_upper = src.upper()
        if src_upper in source_seen:
            errors.append(f"源图重复：{src} 同时映射到 {source_seen[src_upper]} 和 {cn_id}")
        else:
            source_seen[src_upper] = cn_id

        by_chapter.setdefault(ch, []).append(seq)

    # 连续性检查
    for ch, seqs in sorted(by_chapter.items()):
        seqs_sorted = sorted(seqs)
        expected = list(range(1, len(seqs_sorted) + 1))
        if seqs_sorted != expected:
            missing = set(expected) - set(seqs_sorted)
            if missing:
                errors.append(f"第 {ch} 章图编号不连续，缺少：{sorted(missing)}")

    ok = len(errors) == 0
    return {"ok": ok, "errors": errors, "warnings": warnings}


def cross_validate_with_markdown(project_root, chapter=None):
    """
    交叉验证 figure_map.json 与 atomic_md 中的 [图] 标记。

    检查：
    1. atomic_md 中引用的图编号是否都在 figure_map 中注册
    2. figure_map 中注册的图编号是否都在 atomic_md 中被引用

    Returns:
        dict: {"ok": bool, "unregistered": list, "unreferenced": list}
    """
    figure_map = load_figure_map(project_root)
    registered_ids = set(figure_map.keys())

    # 扫描 atomic_md
    referenced_ids = set()
    atomic_dir = resolve_path(project_root, "atomic_md")
    if not os.path.isdir(atomic_dir):
        return {"ok": True, "unregistered": [], "unreferenced": list(registered_ids)}

    chapters_to_scan = []
    if chapter is not None:
        ch_dir = os.path.join(atomic_dir, f"第{chapter}章")
        if os.path.isdir(ch_dir):
            chapters_to_scan.append(ch_dir)
    else:
        for entry in sorted(os.listdir(atomic_dir)):
            ch_dir = os.path.join(atomic_dir, entry)
            if os.path.isdir(ch_dir) and entry.startswith("第"):
                chapters_to_scan.append(ch_dir)

    for ch_dir in chapters_to_scan:
        for fname in sorted(os.listdir(ch_dir)):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(ch_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read()
            except (OSError, UnicodeDecodeError):
                continue
            for m in _CN_FIGURE_RE.finditer(content):
                cn_id = f"图{m.group(1)}-{m.group(2)}"
                referenced_ids.add(cn_id)

    # 过滤 registered_ids 到指定章节
    if chapter is not None:
        chapter = int(chapter)
        registered_ids = {
            cid for cid in registered_ids
            if figure_map.get(cid, {}).get("chapter") == chapter
        }

    unregistered = sorted(referenced_ids - registered_ids)
    unreferenced = sorted(registered_ids - referenced_ids)
    ok = len(unregistered) == 0
    return {"ok": ok, "unregistered": unregistered, "unreferenced": unreferenced}


# ---------------------------------------------------------------------------
# 导出
# ---------------------------------------------------------------------------

def export_figure_table(project_root, fmt="markdown"):
    """
    导出图映射表。

    Args:
        fmt: "markdown" | "json"

    Returns:
        str
    """
    figures = list_figures(project_root)
    if fmt == "json":
        return json.dumps(figures, ensure_ascii=False, indent=2)

    if not figures:
        return "（无图映射记录）"

    lines = [
        "| 中文编号 | 原图标识 | 章节 | 序号 | 图标题 |",
        "|----------|----------|------|------|--------|",
    ]
    for fig in figures:
        cn_id = fig.get("cn_id", "")
        src = fig.get("source_figure", "")
        ch = fig.get("chapter", "")
        seq = fig.get("seq", "")
        title = fig.get("title", "")
        lines.append(f"| {cn_id} | {src} | {ch} | {seq} | {title} |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="图表编号注册表管理")
    parser.add_argument("--project-root", required=True, help="项目根目录")
    sub = parser.add_subparsers(dest="command")

    # register
    p_reg = sub.add_parser("register", help="注册图映射")
    p_reg.add_argument("--chapter", type=int, required=True, help="章节号")
    p_reg.add_argument("--seq", type=int, required=True, help="章内序号")
    p_reg.add_argument("--source", required=True, help="SCI 原图标识，如 'Figure 1A'")
    p_reg.add_argument("--title", default="", help="中文图标题")
    p_reg.add_argument("--overwrite", action="store_true", help="覆盖已有映射")

    # unregister
    p_unreg = sub.add_parser("unregister", help="删除图映射")
    p_unreg.add_argument("--cn-id", required=True, help="中文图编号，如 '图2-1'")

    # list
    p_list = sub.add_parser("list", help="列出映射表")
    p_list.add_argument("--chapter", type=int, help="按章节过滤")
    p_list.add_argument("--format", choices=["json", "markdown"], default="json", help="输出格式")

    # validate
    sub.add_parser("validate", help="验证映射表完整性")

    # cross-validate
    p_cross = sub.add_parser("cross-validate", help="与 atomic_md 交叉验证")
    p_cross.add_argument("--chapter", type=int, help="按章节过滤")

    # export
    p_export = sub.add_parser("export", help="导出映射表")
    p_export.add_argument("--format", choices=["json", "markdown"], default="markdown", help="输出格式")

    args = parser.parse_args()
    project_root = args.project_root

    if args.command == "register":
        result = register_figure(
            project_root,
            chapter=args.chapter,
            seq=args.seq,
            source_figure=args.source,
            title=args.title,
            overwrite=args.overwrite,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result["ok"]:
            sys.exit(1)

    elif args.command == "unregister":
        result = unregister_figure(project_root, args.cn_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result["ok"]:
            sys.exit(1)

    elif args.command == "list":
        figures = list_figures(project_root, chapter=args.chapter)
        if args.format == "markdown":
            print(export_figure_table(project_root, fmt="markdown"))
        else:
            print(json.dumps(figures, ensure_ascii=False, indent=2))

    elif args.command == "validate":
        result = validate_figure_map(project_root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result["ok"]:
            sys.exit(1)

    elif args.command == "cross-validate":
        result = cross_validate_with_markdown(project_root, chapter=args.chapter)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result["ok"]:
            sys.exit(1)

    elif args.command == "export":
        print(export_figure_table(project_root, fmt=args.format))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
