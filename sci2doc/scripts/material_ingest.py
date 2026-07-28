#!/usr/bin/env python3
"""
material_ingest.py — 通用材料分析落盘脚本

将实验数据/笔记/参考文献/图片等多格式原始材料分析后写入
materials/ 目录，供后续按章扩写引用。不臆造任何数据和结论。

用法：
    python3 scripts/material_ingest.py --dir /path/to/materials [--save-path /project]
    python3 scripts/material_ingest.py --list file1.md file2.xlsx file3.png [--save-path /project]
    python3 scripts/material_ingest.py --dir /path/to/materials --dry-run
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# ─── 可选库检测 ─────────────────────────────────────────────────────────────

def _try_import(module_name):
    try:
        import importlib
        return importlib.import_module(module_name)
    except ImportError:
        return None

# ─── 工具函数 ────────────────────────────────────────────────────────────────

def safe_name(filename: str) -> str:
    """
    将文件名转为合法的目录/文件名片段（无空格、无特殊字符）。

    为避免不同特殊字符文件名经压缩后碰撞，追加来源文件名的短 hash 后缀。
    示例：「实验 #1.xlsx」→ experiment__1_a3f2b1
    """
    stem = Path(filename).stem
    slug = re.sub(r"[^\w\-]", "_", stem)[:52]
    suffix_hash = hashlib.sha256(filename.encode("utf-8")).hexdigest()[:6]
    return f"{slug}_{suffix_hash}"


def file_hash(path: Path) -> str:
    """计算文件 SHA256 前 12 位，用于幂等性判断。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


# ─── 各格式处理器 ────────────────────────────────────────────────────────────

def process_text(path: Path) -> dict:
    """md / txt：读全文，提取要点（前 5000 字符 + 标题列表）。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"status": "error", "error": str(e), "key_points": [], "summary": ""}

    # 提取 Markdown 标题作为结构线索
    headings = re.findall(r"^#{1,4}\s+(.+)", text, re.MULTILINE)
    word_count = len(text)
    preview = text[:3000].strip()

    # 简单要点提取：每段首句（非空、非标题）
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip() and not p.strip().startswith("#")]
    # splitlines() 跨平台处理 \r\n/\r；(... or [''])[0] 防空段 IndexError
    key_points = [(p.splitlines() or [''])[0][:200] for p in paragraphs[:10] if p]

    return {
        "status": "ok",
        "char_count": word_count,
        "headings": headings[:20],
        "preview": preview,
        "key_points": key_points,
        "summary": f"共 {word_count} 字符，{len(headings)} 个标题节点",
    }


def process_tabular(path: Path) -> dict:
    """xlsx / csv：提取表结构（sheet名/列名/行数/数值范围），不臆造内容。"""
    suffix = path.suffix.lower()
    result = {"status": "ok", "sheets": [], "key_points": []}

    if suffix == ".xlsx":
        openpyxl = _try_import("openpyxl")
        if openpyxl is None:
            return {
                "status": "skip",
                "reason": "openpyxl 未安装；运行 `pip3 install openpyxl` 后重试",
                "key_points": [],
                "summary": "跳过（缺依赖）",
            }
        try:
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        except Exception as e:
            return {"status": "error", "error": str(e), "key_points": [], "summary": ""}

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                result["sheets"].append({"sheet": sheet_name, "rows": 0, "columns": []})
                continue

            headers = [str(c) if c is not None else "" for c in rows[0]]
            data_rows = rows[1:]
            row_count = len(data_rows)

            # 数值范围分析
            col_stats = []
            for col_idx, col_name in enumerate(headers):
                vals = []
                for row in data_rows:
                    if col_idx < len(row) and row[col_idx] is not None:
                        try:
                            vals.append(float(row[col_idx]))
                        except (TypeError, ValueError):
                            pass
                if vals:
                    col_stats.append({
                        "col": col_name,
                        "n_numeric": len(vals),
                        "min": round(min(vals), 6),
                        "max": round(max(vals), 6),
                        "mean": round(sum(vals) / len(vals), 6),
                    })
                else:
                    col_stats.append({"col": col_name, "n_numeric": 0})

            sheet_info = {
                "sheet": sheet_name,
                "rows": row_count,
                "columns": headers,
                "numeric_stats": col_stats,
            }
            result["sheets"].append(sheet_info)

            kp = f"[{sheet_name}] {row_count} 行 × {len(headers)} 列"
            if col_stats:
                numeric_cols = [s for s in col_stats if s.get("n_numeric", 0) > 0]
                if numeric_cols:
                    sample = numeric_cols[0]
                    kp += f"；{sample['col']} 范围 [{sample['min']}, {sample['max']}]"
            result["key_points"].append(kp)

        wb.close()
        result["summary"] = f"{len(wb.sheetnames)} 个 sheet"

    elif suffix == ".csv":
        try:
            with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.reader(f)
                all_rows = list(reader)
        except Exception as e:
            return {"status": "error", "error": str(e), "key_points": [], "summary": ""}

        if not all_rows:
            result["summary"] = "空文件"
            return result

        headers = all_rows[0]
        data_rows = all_rows[1:]
        row_count = len(data_rows)

        col_stats = []
        for col_idx, col_name in enumerate(headers):
            vals = []
            for row in data_rows:
                if col_idx < len(row):
                    try:
                        vals.append(float(row[col_idx]))
                    except (TypeError, ValueError):
                        pass
            if vals:
                col_stats.append({
                    "col": col_name,
                    "n_numeric": len(vals),
                    "min": round(min(vals), 6),
                    "max": round(max(vals), 6),
                    "mean": round(sum(vals) / len(vals), 6),
                })
            else:
                col_stats.append({"col": col_name, "n_numeric": 0})

        sheet_info = {
            "sheet": "default",
            "rows": row_count,
            "columns": headers,
            "numeric_stats": col_stats,
        }
        result["sheets"].append(sheet_info)

        kp = f"{row_count} 行 × {len(headers)} 列"
        numeric_cols = [s for s in col_stats if s.get("n_numeric", 0) > 0]
        if numeric_cols:
            sample = numeric_cols[0]
            kp += f"；{sample['col']} 范围 [{sample['min']}, {sample['max']}]"
        result["key_points"].append(kp)
        result["summary"] = f"{row_count} 行 × {len(headers)} 列（CSV）"

    return result


def process_document(path: Path) -> dict:
    """PDF / Word：有库则提取文本；无库则标记跳过，不报错。"""
    suffix = path.suffix.lower()
    result = {"status": "ok", "key_points": [], "summary": ""}

    if suffix == ".pdf":
        pdfminer_hl = _try_import("pdfminer.high_level")
        if pdfminer_hl is None:
            return {
                "status": "skip",
                "reason": "pdfminer 未安装；请先用 /pdf 技能（pdf-viewer:view-pdf）提取文本，或 `pip3 install pdfminer.six`",
                "key_points": [],
                "summary": "跳过（需 /pdf 技能或安装 pdfminer.six）",
            }
        try:
            text = pdfminer_hl.extract_text(str(path))
        except Exception as e:
            return {"status": "error", "error": str(e), "key_points": [], "summary": ""}

        if not text or not text.strip():
            return {
                "status": "skip",
                "reason": "PDF 提取文本为空（可能是扫描件），请用 /pdf 技能人工阅读",
                "key_points": [],
                "summary": "跳过（扫描件或加密 PDF）",
            }

        preview = text[:3000].strip()
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        # splitlines() 跨平台处理 \r\n/\r；(... or [''])[0] 防空段 IndexError
        key_points = [(p.splitlines() or [''])[0][:200] for p in paragraphs[:8] if p]
        result["preview"] = preview
        result["char_count"] = len(text)
        result["key_points"] = key_points
        result["summary"] = f"共 {len(text)} 字符（PDF 文本层提取）"

    elif suffix in (".docx", ".doc"):
        docx_mod = _try_import("docx")
        if docx_mod is None:
            return {
                "status": "skip",
                "reason": "python-docx 未安装；请先用 /docx 技能提取文本，或 `pip3 install python-docx`",
                "key_points": [],
                "summary": "跳过（需 /docx 技能或安装 python-docx）",
            }
        try:
            doc = docx_mod.Document(str(path))
            paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        except Exception as e:
            return {"status": "error", "error": str(e), "key_points": [], "summary": ""}

        text = "\n\n".join(paras)
        key_points = [p[:200] for p in paras[:8]]
        result["char_count"] = len(text)
        result["key_points"] = key_points
        result["preview"] = text[:3000]
        result["summary"] = f"共 {len(paras)} 段落，{len(text)} 字符（Word 文本提取）"

    return result


def process_image(path: Path) -> dict:
    """图片：只记录路径和元信息，不做 OCR 臆测。"""
    size_bytes = path.stat().st_size
    size_kb = round(size_bytes / 1024, 1)
    return {
        "status": "pending_confirm",
        "reason": "图片仅记录路径和元信息，不做 OCR 臆测。请用户口述或确认图内容后手动补充到对应 .md 的「待确认」区。",
        "file_size_kb": size_kb,
        "key_points": [],
        "summary": f"图片文件 {size_kb} KB，内容待用户确认",
    }


# ─── 类型路由 ────────────────────────────────────────────────────────────────

EXT_MAP = {
    ".md": ("text", process_text),
    ".txt": ("text", process_text),
    ".csv": ("tabular", process_tabular),
    ".xlsx": ("tabular", process_tabular),
    ".pdf": ("document", process_document),
    ".docx": ("document", process_document),
    ".doc": ("document", process_document),
    ".png": ("image", process_image),
    ".jpg": ("image", process_image),
    ".jpeg": ("image", process_image),
    ".tif": ("image", process_image),
    ".tiff": ("image", process_image),
    ".gif": ("image", process_image),
    ".bmp": ("image", process_image),
}


def detect_type(path: Path):
    return EXT_MAP.get(path.suffix.lower())


# ─── 素材档写入 ───────────────────────────────────────────────────────────────

def write_material_md(materials_dir: Path, entry: dict) -> None:
    """为单个材料写结构化 .md 素材档。"""
    fname = entry["safe_name"] + ".md"
    out = materials_dir / fname

    lines = [
        f"# 素材档：{entry['filename']}",
        "",
        f"- **来源路径**：`{entry['source_path']}`",
        f"- **类型**：{entry['file_type']}",
        f"- **状态**：{entry['status']}",
        f"- **摘入时间**：{entry['ingested_at']}",
        f"- **文件哈希**：{entry['file_hash']}",
        "",
    ]

    if entry.get("summary"):
        lines += ["## 内容摘要", "", entry["summary"], ""]

    if entry.get("key_points"):
        lines += ["## 可引用要点", ""]
        for kp in entry["key_points"]:
            lines.append(f"- {kp}")
        lines.append("")

    # 表格详情
    if entry["file_type"] == "tabular" and entry.get("sheets"):
        lines += ["## 表结构详情", ""]
        for sheet in entry["sheets"]:
            lines.append(f"### Sheet: {sheet['sheet']}")
            lines.append(f"- 行数：{sheet['rows']}")
            lines.append(f"- 列名：{', '.join(str(c) for c in sheet.get('columns', []))}")
            numeric = [s for s in sheet.get("numeric_stats", []) if s.get("n_numeric", 0) > 0]
            if numeric:
                lines.append("- 数值列范围：")
                for s in numeric:
                    lines.append(f"  - `{s['col']}`：[{s['min']}, {s['max']}]，均值 {s['mean']}，共 {s['n_numeric']} 个数值")
            lines.append("")

    # 文本预览
    if entry.get("preview"):
        lines += ["## 文本预览（前 3000 字符）", "", "```", entry["preview"][:3000], "```", ""]

    # 跳过说明
    if entry["status"] in ("skip", "pending_confirm") and entry.get("reason"):
        lines += ["## 处理说明", "", f"> {entry['reason']}", ""]

    # 待确认区
    lines += [
        "## 待确认（❓）",
        "",
        "> 请在此补充图内容描述、数据解释、结论说明等需要人工确认的信息。",
        "",
    ]

    out.write_text("\n".join(lines), encoding="utf-8")


# ─── 主流程 ──────────────────────────────────────────────────────────────────

def load_archive(archive_path: Path) -> dict:
    if archive_path.exists():
        try:
            return json.loads(archive_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"version": 1, "generated_at": now_iso(), "entries": []}


def save_archive(archive_path: Path, archive: dict) -> None:
    archive["updated_at"] = now_iso()
    archive_path.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")


def ingest_file(path: Path, materials_dir: Path, archive: dict, dry_run: bool) -> dict:
    """处理单个文件，返回 entry dict；幂等（按 hash 去重）。"""
    type_info = detect_type(path)
    if type_info is None:
        return {
            "filename": path.name,
            "source_path": str(path),
            "file_type": "unsupported",
            "status": "skip",
            "reason": f"不支持的文件类型 {path.suffix}",
            "key_points": [],
            "summary": "跳过（不支持的类型）",
            "safe_name": safe_name(path.name),
            "ingested_at": now_iso(),
            "file_hash": "",
        }

    file_type, processor = type_info
    fhash = file_hash(path)

    # 幂等检查：同 hash 已存在则跳过
    existing = next((e for e in archive["entries"] if e.get("file_hash") == fhash), None)
    if existing:
        print(f"  [skip-dup] {path.name}（hash {fhash} 已存在）")
        return existing

    print(f"  [process]  {path.name} → {file_type}")
    result = processor(path)

    entry = {
        "filename": path.name,
        "source_path": str(path.resolve()),
        "file_type": file_type,
        "status": result.get("status", "ok"),
        "safe_name": safe_name(path.name),
        "ingested_at": now_iso(),
        "file_hash": fhash,
        "summary": result.get("summary", ""),
        "key_points": result.get("key_points", []),
    }

    # 透传扩展字段到 archive（不写入 entry，避免 json 过大）
    if "sheets" in result:
        entry["sheets"] = result["sheets"]
    if "headings" in result:
        entry["headings"] = result["headings"]
    if result.get("status") in ("skip", "pending_confirm") and result.get("reason"):
        entry["reason"] = result["reason"]

    # 透传给 md 用的预览字段（不入 archive，只用于写 md）
    entry["_preview"] = result.get("preview", "")

    if not dry_run:
        write_material_md(materials_dir, entry)

    # 不把 _preview 写入 archive
    archive_entry = {k: v for k, v in entry.items() if k != "_preview"}
    return archive_entry


def collect_files(args) -> list:
    paths = []
    if args.dir:
        d = Path(args.dir)
        if not d.is_dir():
            print(f"[error] --dir {args.dir} 不存在或不是目录", file=sys.stderr)
            sys.exit(1)
        for p in sorted(d.iterdir()):
            if p.is_file() and not p.name.startswith("."):
                paths.append(p)
    if args.list:
        for f in args.list:
            p = Path(f)
            if p.is_file():
                paths.append(p)
            else:
                print(f"[warn] 文件不存在，跳过：{f}", file=sys.stderr)
    return paths


def main():
    parser = argparse.ArgumentParser(
        description="通用材料分析落盘 — 将多格式原始材料分析后写入 materials/ 素材档"
    )
    parser.add_argument("--dir", help="材料目录（处理目录下所有文件）")
    parser.add_argument("--list", nargs="+", help="指定文件列表")
    parser.add_argument(
        "--save-path",
        default=".",
        help="sci2doc 项目根目录（materials/ 将创建于此，默认当前目录）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印分析结果，不写文件")
    args = parser.parse_args()

    if not args.dir and not args.list:
        parser.error("需要 --dir 或 --list 之一")

    save_path = Path(args.save_path)
    materials_dir = save_path / "materials"

    if not args.dry_run:
        materials_dir.mkdir(parents=True, exist_ok=True)

    archive_path = materials_dir / "materials_archive.json"
    archive = load_archive(archive_path) if not args.dry_run else {"version": 1, "entries": []}

    files = collect_files(args)
    if not files:
        print("[warn] 没有找到任何文件")
        return

    print(f"\n材料目录：{materials_dir}")
    print(f"待处理文件：{len(files)} 个\n")

    new_entries = []
    for path in files:
        entry = ingest_file(path, materials_dir, archive, args.dry_run)
        # 幂等：只追加新条目
        if not any(e.get("file_hash") == entry.get("file_hash") and entry.get("file_hash") for e in archive["entries"]):
            archive["entries"].append(entry)
            new_entries.append(entry)

    if not args.dry_run:
        save_archive(archive_path, archive)

    # 汇总报告
    print(f"\n{'='*50}")
    print(f"{'[DRY RUN] ' if args.dry_run else ''}摘入完成")
    print(f"  总条目：{len(archive['entries'])}，本次新增：{len(new_entries)}")
    by_status = {}
    for e in archive["entries"]:
        s = e.get("status", "ok")
        by_status[s] = by_status.get(s, 0) + 1
    for s, n in sorted(by_status.items()):
        print(f"  {s}: {n}")
    if not args.dry_run:
        print(f"  archive → {archive_path}")
        print(f"  素材档  → {materials_dir}/<name>.md")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
