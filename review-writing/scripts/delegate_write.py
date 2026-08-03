#!/usr/bin/env python3
# delegate_write.py —— review-writing 撰写编排入口（薄封装：import 本家 vendored 共享核心）
#
# 逻辑全在 delegate_write_core.py（四家逐字节一致，L4 md5 守卫）。本文件只声明 rw
# 的账本映射 config：文献库/矩阵都在 data/ 下，条目主键 global_id。
# 本节文献切片来自 data/synthesis_matrix.json——每行已按节展开成 {global_id, section_id}
# 单值形态（related_sections 在 index 条目上，bootstrap 时展开），故走 matrix_rows 而非
# matrix_related；矩阵行自带 title/abstract，切片天然带摘要。

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from delegate_write_core import (  # noqa: E402
    BARE_NUM_RE, KEY_RE, SECTION_RE, main,
)

__all__ = ["BARE_NUM_RE", "KEY_RE", "SECTION_RE", "CONFIG", "main"]

CONFIG = {
    "family": "review-writing",
    "section_regex": r"^\d+(\.\d+)*$",
    # rw 的大纲真源是 outline.md（state_manager.STATE_FILES["storyline"]），从不产出
    # project_state.json / storyline.json——原先照抄 sci2doc 的那两个文件名，rw 这条路
    # 从来没通过。核心已支持 .md 候选（按 `##+ 编号 标题` 抽节）。
    "outline_files": ["outline.md"],
    "outline_id_field": "section_id",
    "index_path": "data/literature_index.json",   # rw 文献库在 data/ 下，list
    "index_shape": "root_list",
    "index_id_field": "global_id",                 # rw 条目主键
    # 本节文献切片：data/synthesis_matrix.json 富行，按 section_id==本节 切（行键 global_id，§7）
    "lit_section": {"mode": "matrix_rows", "file": "data/synthesis_matrix.json",
                    "id_field": "global_id", "section_field": "section_id"},
}


if __name__ == "__main__":
    main(CONFIG)
