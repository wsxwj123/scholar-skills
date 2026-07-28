#!/usr/bin/env python3
# delegate_write.py —— general-sci-writing 撰写编排入口（薄封装：import 本家 vendored 共享核心）
#
# 逻辑全在 delegate_write_core.py（四家逐字节一致，L4 md5 守卫）。本文件只声明 gsw
# 的账本映射 config：大纲取 storyline.json（节键 `id`）、本节文献切片来自
# literature_matrix.json（section→refs 映射表，ref 是 citation_number）。
#
# 注：共享核心已 config 化 outline_id_field，直接认 storyline 的 `id`，故不再需要
# 派生 .orch_outline.json sidecar（旧兜底，已随核心修好而删）。storyline 仍是唯一真源。

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from delegate_write_core import (  # noqa: E402
    BARE_NUM_RE, KEY_RE, SECTION_RE, main,
)

__all__ = ["BARE_NUM_RE", "KEY_RE", "SECTION_RE", "CONFIG", "main"]

CONFIG = {
    "family": "general-sci-writing",
    # gsw 小节 id：introduction / methods / discussion / conclusion（纯词）与 results_3.1
    # （词_点分号）并存，故不强制含数字。首字符字母，其后字母/数字/下划线/点。
    "section_regex": r"^[A-Za-z][A-Za-z0-9_.]*$",
    # gsw 大纲：storyline.json，节标识字段是 `id`（核心 config 直接认，无需 sidecar）。
    "outline_files": ["storyline.json"],
    "outline_id_field": "id",
    "index_path": "literature_index.json",       # 项目根 list
    "index_shape": "root_list",
    "index_id_field": "citation_number",         # gsw 条目主键（引文编号）
    # 本节文献切片：literature_matrix.json，section→refs 映射表（ref=citation_number），按本 section 切（§7）
    "lit_section": {"mode": "matrix_map", "file": "literature_matrix.json"},
}


if __name__ == "__main__":
    main(CONFIG)
