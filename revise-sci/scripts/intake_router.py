#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import detect_comments_input_mode, discover_global_skill, normalize_ws, write_json, write_text


REVIEWER_SIMULATOR_INSTALL_SOURCE = ""  # 配置为你自己的技能备份仓库 reviewer-simulator 子目录 URL；留空则跳过自动安装

MODE_LABELS = {
    "docx-review-comments": "普通结构化审稿意见 Word",
    "docx-review-letter": "decision-letter 风格审稿意见 Word",
    "reviewer-simulator-html": "reviewer-simulator 结构化 HTML",
    "reviewer-response-sci-html": "reviewer-response-sci 完整回复 HTML",
    "atomic-comment-html": "已原子化 comment-unit HTML",
    "html-unknown": "未识别 HTML",
    "unsupported": "不支持的输入类型",
    "no-comments-manuscript-only": "仅原稿、无审稿意见",
}


MODE_WORKFLOWS = {
    "docx-review-comments": [
        "按 Reviewer / Major-Minor / 编号评论拆分为 comment units",
        "按 manuscript/SI section-paragraph 做原子化",
        "逐条建立 atomic_location、回复块、正文改动和 edit plan",
        "仅对新增/修改句子做 fragment-level polish",
        "执行文献/引用 hard gate 后导出 md/docx",
    ],
    "docx-review-letter": [
        "先拆 editor email / reviewer overall statement / numbered comments",
        "将 editor/reviewer statement 作为 seeds 写入 response 渲染和定位查询",
        "对真正 numbered comments 逐条建立 atomic_location 和 response/revision blocks",
        "仅对新增/修改句子做 fragment-level polish",
        "执行 references 恢复、文献 hard gate 和最终 md/docx 导出",
    ],
    "reviewer-simulator-html": [
        "读取 critique-section / critique-list 结构化字段",
        "保留 problem_description / evidence_anchor / root_cause / author_strategy",
        "优先用这些结构化字段做定位和回复草案",
        "逐条回写 manuscript/SI 原子单元并执行 polish/gate",
    ],
    "reviewer-response-sci-html": [
        "读取 reviewer comment + response/original/revised/location seeds",
        "将这些 seeds 作为定位和回复草案提示，而非直接信任成品",
        "重新执行 revise -> polish -> literature/reference checks -> strict_gate",
        "导出新的 response_to_reviewers 与 revised manuscript",
    ],
    "atomic-comment-html": [
        "保留既有 comment_id 和 reviewer/severity 元数据",
        "直接进入 manuscript/SI 原子定位、逐条修稿、fragment polish 和最终门禁",
    ],
    "no-comments-manuscript-only": [
        "先确认是否使用 reviewer-simulator 生成结构化审稿意见",
        "若确认，则先检查 reviewer-simulator 是否已安装；缺失时先安装到全局 skill 目录",
        "生成审稿意见 HTML 后，重新进入 revise-sci intake 并确认新的 comments_input_mode",
        "确认后再进入正式的原子化 revise workflow",
    ],
}


def build_confirmation_prompt(payload: dict) -> str:
    if payload.get("manuscript_format_error"):
        return "\n".join(
            [
                "主稿格式不符合要求，已在 intake 阶段拦截：",
                f"- {payload['manuscript_format_error']}",
                "",
                "revise-sci 需要提供 .docx 主稿（与后续 preflight/pipeline 口径一致）。",
                "请改用 .docx 主稿后重新进入 intake。",
            ]
        ) + "\n"
    lines = [
        "已检测到当前输入的审稿意见分流如下：",
        f"- comments_input_mode: `{payload['detected_mode']}`",
        f"- 模式说明: {payload['mode_label']}",
        "",
        "后续将按以下流程执行：",
    ]
    for step in payload.get("workflow_steps", []):
        lines.append(f"- {step}")
    if payload.get("needs_reviewer_simulator"):
        availability = payload.get("reviewer_simulator", {})
        available_paths = availability.get("available_paths") or []
        lines.extend(
            [
                "",
                "当前未提供审稿意见。",
                "请确认是否先使用 `reviewer-simulator` 生成审稿意见，再继续 revise-sci 流程。",
                f"- reviewer-simulator 是否已安装: `{availability.get('available', False)}`",
                f"- 已发现路径: `{'; '.join(available_paths) if available_paths else 'Not found'}`",
                f"- 缺失时安装来源: `{availability.get('install_source_url', REVIEWER_SIMULATOR_INSTALL_SOURCE)}`",
            ]
        )
    if payload.get("needs_branch_guidance"):
        lines.extend(
            [
                "",
                "当前输入不属于已知分流。",
                "请确认是要参照哪一种既有分流工作，还是为这种输入新建一个 comments_input_mode 分流。",
                "无论选择哪种分流，后续都会沿用相同的原子化、fragment-level polish、state window、防失忆和 hard gate 机制。",
            ]
        )
    lines.extend(
        [
            "",
            "请同时确认：",
            "1. 是否按上述分流和流程继续；",
            "2. `project_root`（输出目录）希望放在哪里；",
            "3. 如需自定义输出文件名，请一并提供 `output_md_path` 和 `output_docx_path`。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Route revise-sci intake before running the full pipeline")
    parser.add_argument("--comments", default="")
    parser.add_argument("--manuscript", default="")
    parser.add_argument("--project-root", default="")
    parser.add_argument("--report-out", default="")
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    comments = Path(args.comments).resolve() if args.comments else None
    manuscript = Path(args.manuscript).resolve() if args.manuscript else None

    # 主稿扩展名前置校验:与 preflight 口径一致(manuscript 必须是 .docx)。
    # 提前在 intake 阶段拦截非 .docx 主稿,避免放行到 pipeline 才报错。
    manuscript_format_error = (
        f"manuscript_docx_path must be readable .docx: {manuscript}"
        if manuscript and manuscript.exists() and manuscript.suffix.lower() != ".docx"
        else ""
    )

    if manuscript_format_error:
        detected_mode = "unsupported"
    elif comments and comments.exists():
        detected_mode = detect_comments_input_mode(comments)
    elif manuscript and manuscript.exists():
        detected_mode = "no-comments-manuscript-only"
    else:
        detected_mode = "unsupported"

    reviewer_simulator_paths = [str(path) for path in discover_global_skill("reviewer-simulator")]
    supported = detected_mode in MODE_WORKFLOWS
    needs_reviewer_simulator = detected_mode == "no-comments-manuscript-only"
    needs_branch_guidance = detected_mode in {"html-unknown", "unsupported"}
    workflow_steps = MODE_WORKFLOWS.get(detected_mode, [])

    payload = {
        "ok": True,
        "detected_mode": detected_mode,
        "mode_label": MODE_LABELS.get(detected_mode, detected_mode),
        "supported": supported,
        "confirmation_required": True,
        "project_root_required": True,
        "needs_branch_guidance": needs_branch_guidance,
        "needs_reviewer_simulator": needs_reviewer_simulator,
        "manuscript_format_error": manuscript_format_error,
        "workflow_steps": workflow_steps,
        "comments_path": str(comments) if comments else "",
        "manuscript_docx_path": str(manuscript) if manuscript else "",
        "project_root": normalize_ws(args.project_root),
        "reviewer_simulator": {
            "available": bool(reviewer_simulator_paths),
            "available_paths": reviewer_simulator_paths,
            "install_source_url": REVIEWER_SIMULATOR_INSTALL_SOURCE,
        },
    }
    payload["assistant_prompt"] = build_confirmation_prompt(payload)

    if args.report_out:
        write_text(Path(args.report_out), payload["assistant_prompt"])
    if args.json_out:
        write_json(Path(args.json_out), payload)

    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
