#!/usr/bin/env python3
# delegate_write.py —— sci2doc 撰写编排入口（薄封装：import 本家 vendored 共享核心）
#
# 逻辑全在 delegate_write_core.py（四家逐字节一致，L4 md5 守卫）。本文件只声明 sci2doc
# 的账本映射 config：section 形态（点分数字）、大纲文件、本节文献切片来源。
#
# 子命令 / 退出码契约见 delegate_write_core.py 头注（对外不变）。

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from delegate_write_core import (  # noqa: E402
    BARE_NUM_RE, KEY_RE, SECTION_RE, main,
)

# 保留白盒测试引用面（scripts/test_delegate_write.py 引 dw.SECTION_RE 等）
__all__ = ["BARE_NUM_RE", "KEY_RE", "SECTION_RE", "CONFIG", "main"]

CONFIG = {
    "family": "sci2doc",
    "section_regex": r"^\d+(\.\d+)*$",
    "outline_files": ["project_state.json", "storyline.json"],
    "outline_id_field": "section_id",           # project_state.sections[].section_id
    "index_path": "literature_index.json",       # 项目根 list
    "index_shape": "root_list",
    "index_id_field": "id",
    # 本节文献切片：新建 chapter_matrix.json 富行式，按 section_id==X.Y 切（§2.6/§7 决策14）
    "lit_section": {"mode": "matrix_rows", "file": "chapter_matrix.json",
                    "id_field": "id", "section_field": "section_id"},
}


if __name__ == "__main__":
    main(CONFIG)
