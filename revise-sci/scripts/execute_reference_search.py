#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from common import normalize_ws, read_json, write_json, write_text


def ensure_review_writing_governance(project_root: Path) -> list[str]:
    errors: list[str] = []
    manifest = read_json(project_root / "reference_search_manifest.json", {})
    strategy = read_json(project_root / "reference_search_strategy.json", {})
    rounds = read_json(project_root / "reference_search_rounds.json", {})
    if manifest.get("workflow") != "review-writing":
        errors.append("reference_search_manifest.json must declare workflow review-writing")
    if strategy.get("workflow") != "review-writing":
        errors.append("reference_search_strategy.json must declare workflow review-writing")
    if rounds.get("workflow") != "review-writing":
        errors.append("reference_search_rounds.json must declare workflow review-writing")
    if (manifest.get("allowed_provider_families") or []) != ["paper-search"]:
        errors.append("reference_search_manifest.json must restrict providers to paper-search")
    if (strategy.get("provider_policy") or {}).get("primary") != ["paper-search"]:
        errors.append("reference_search_strategy.json must restrict primary providers to paper-search")
    if "citation_guard.py" not in normalize_ws(str(strategy.get("mandatory_guard_command") or "")):
        errors.append("reference_search_strategy.json must include citation_guard.py as mandatory guard command")
    if len(rounds.get("rounds") or []) != 3:
        errors.append("reference_search_rounds.json must define three search rounds")
    return errors


def validate_output_payload(payload: Any) -> list[str]:
    errors: list[str] = []
    rows = payload.get("results", []) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return ["paper-search runner output must be a list or {'results': [...]} payload"]
    for row in rows:
        if not isinstance(row, dict):
            errors.append("paper-search runner rows must be JSON objects")
            continue
        citations = row.get("citations", []) or []
        if not isinstance(citations, list):
            errors.append("paper-search runner row citations must be a list")
            continue
        for citation in citations:
            provider = normalize_ws(
                str(citation.get("source_provider") or citation.get("provider_family") or citation.get("provider") or "")
            ).lower()
            if not provider.startswith("paper-search"):
                errors.append("paper-search runner emitted a non paper-search citation provider")
    return errors


def update_status(project_root: Path, output_exists: bool) -> None:
    status_path = project_root / "reference_search_status.json"
    status = read_json(status_path, {})
    steps = status.get("steps") or {}
    steps["search_round_plan_generated"] = (project_root / "reference_search_rounds.json").exists()
    steps["paper_search_batch_imported"] = output_exists
    status["steps"] = steps
    write_json(status_path, status)


def write_execution_request(project_root: Path, blocked_reason: str, runner_env: str) -> None:
    lines = [
        "# Reference Search Execution Request",
        "",
        "当前项目已进入 approved 检索状态，但本地 Python 主流水线没有可用的 `paper-search` runner，因此无法自动执行检索调用。",
        "",
        f"- blocked_reason: {blocked_reason}",
        f"- expected_env: {runner_env}",
        f"- rounds_file: {str((project_root / 'reference_search_rounds.json').resolve())}",
        "",
        "## 处理方式",
        "",
        "1. 配置本地 `paper-search` runner，并令其支持以下参数：`--rounds-json <path> --output <path> --project-root <path>`。",
        "2. 或者配置 `REVISE_SCI_OPENCODE_DRIVER_COMMAND`，让系统通过 `opencode run` 风格 driver 自动执行 approved 检索。",
        "3. 重新运行 `run_pipeline.py --reference-search-decision approved --auto-run-reference-search`。",
        "4. 若不使用本地自动 driver，则由后续 agent 按 `reference_search_rounds.json` 执行 paper-search MCP，并把结果写入 `paper_search_results.json`。",
        "",
    ]
    write_text(project_root / "reference_search_execution_request.md", "\n".join(lines))


def build_opencode_prompt(project_root: Path, rounds_path: Path, output_path: Path) -> str:
    return "\n".join(
        [
            "# Revise-Sci Approved Reference Search Execution",
            "",
            f"PROJECT_ROOT={project_root.resolve()}",
            f"ROUNDS_JSON_PATH={rounds_path.resolve()}",
            f"OUTPUT_JSON_PATH={output_path.resolve()}",
            "WORKFLOW=review-writing",
            "ALLOWED_PROVIDER_FAMILIES=paper-search",
            "FORBIDDEN_PROVIDER_FAMILIES=websearch,tavily,general-web-search",
            "",
            "You are executing an approved revise-sci reference search cycle.",
            "Requirements:",
            "1. Read reference_search_manifest.json, reference_search_strategy.json, reference_search_rounds.json, data/reference_coverage_audit.json, and units/*.json under PROJECT_ROOT.",
            "2. Use only paper-search for retrieval. Do not use tavily or any free-form web search.",
            "3. Build OUTPUT_JSON_PATH as a JSON object with a top-level `results` array.",
            "4. For citation supplement items, include `comment_id`, `confirmed`, `formatted_citation_text`, `target_section_heading` and/or `target_paragraph_index`, and `citations`.",
            "5. Each citation object must include `source_provider`, `source_id` or `source`, `title`, and at least one identifier among `doi`/`pmid` when available.",
            "6. Do not write any prose output in place of the JSON file. The pipeline will run citation_guard.py next.",
            "",
            "Expected row schema example:",
            '{',
            '  "results": [',
            '    {',
            '      "comment_id": "R1-Major-01",',
            '      "confirmed": true,',
            '      "formatted_citation_text": "(Smith et al., 2023)",',
            '      "target_section_heading": "Introduction",',
            '      "target_paragraph_index": 1,',
            '      "citations": [',
            '        {',
            '          "source_provider": "paper-search",',
            '          "source_id": "PMID:123456",',
            '          "pmid": "123456",',
            '          "title": "Example title",',
            '          "authors": ["Smith J"],',
            '          "journal": "Example Journal",',
            '          "year": 2023',
            '        }',
            '      ]',
            '    }',
            '  ]',
            '}',
            "",
            "After writing OUTPUT_JSON_PATH, stop.",
        ]
    )


def run_opencode_driver(project_root: Path, rounds_path: Path, output_path: Path, driver_command: str) -> subprocess.CompletedProcess[str]:
    prompt = build_opencode_prompt(project_root, rounds_path, output_path)
    write_text(project_root / "reference_search_opencode_prompt.md", prompt)
    command = shlex.split(driver_command) + ["--dir", str(project_root), prompt]
    return subprocess.run(command, text=True, capture_output=True, encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute approved paper-search rounds via a local runner hook")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--paper-search-runner", default="")
    parser.add_argument("--opencode-driver-command", default="")
    parser.add_argument("--disable-opencode-driver", action="store_true")
    parser.add_argument("--rounds-json", default="")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    project_root = Path(args.project_root)
    rounds_path = Path(args.rounds_json) if args.rounds_json else project_root / "reference_search_rounds.json"
    output_path = Path(args.output) if args.output else project_root / "paper_search_results.json"
    runner = normalize_ws(args.paper_search_runner or os.environ.get("REVISE_SCI_PAPER_SEARCH_RUNNER", ""))
    opencode_driver = normalize_ws(
        args.opencode_driver_command
        or os.environ.get("REVISE_SCI_OPENCODE_DRIVER_COMMAND", "")
        or ("opencode run" if shutil.which("opencode") and not args.disable_opencode_driver else "")
    )

    errors = ensure_review_writing_governance(project_root)
    if not rounds_path.exists():
        errors.append(f"missing rounds file: {rounds_path}")
    if errors:
        write_json(
            project_root / "reference_search_execution.json",
            {"ok": False, "executed": False, "runner_available": bool(runner), "errors": errors},
        )
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False))
        return 1

    if not runner:
        if opencode_driver:
            completed = run_opencode_driver(project_root, rounds_path, output_path, opencode_driver)
            if completed.returncode != 0:
                write_json(
                    project_root / "reference_search_execution.json",
                    {
                        "ok": False,
                        "executed": True,
                        "runner_available": False,
                        "driver_mode": "opencode-driver",
                        "command": shlex.split(opencode_driver) + ["--dir", str(project_root), "<prompt>"],
                        "returncode": completed.returncode,
                        "stdout": completed.stdout,
                        "stderr": completed.stderr,
                    },
                )
                update_status(project_root, output_exists=False)
                if completed.stdout:
                    print(completed.stdout.strip())
                if completed.stderr:
                    print(completed.stderr.strip(), file=sys.stderr)
                return completed.returncode
            payload = read_json(output_path, None)
            validation_errors = validate_output_payload(payload)
            if validation_errors:
                write_json(
                    project_root / "reference_search_execution.json",
                    {
                        "ok": False,
                        "executed": True,
                        "runner_available": False,
                        "driver_mode": "opencode-driver",
                        "command": shlex.split(opencode_driver) + ["--dir", str(project_root), "<prompt>"],
                        "errors": validation_errors,
                    },
                )
                update_status(project_root, output_exists=False)
                print(json.dumps({"ok": False, "errors": validation_errors}, ensure_ascii=False))
                return 1
            rows = payload.get("results", []) if isinstance(payload, dict) else payload
            write_json(
                project_root / "reference_search_execution.json",
                {
                    "ok": True,
                    "executed": True,
                    "runner_available": False,
                    "driver_mode": "opencode-driver",
                    "command": shlex.split(opencode_driver) + ["--dir", str(project_root), "<prompt>"],
                    "result_rows": len(rows or []),
                    "output": str(output_path.resolve()),
                },
            )
            update_status(project_root, output_exists=True)
            print(json.dumps({"ok": True, "driver_mode": "opencode-driver", "result_rows": len(rows or []), "output": str(output_path.resolve())}, ensure_ascii=False))
            return 0

        blocked_reason = "No local paper-search runner or opencode driver is configured."
        write_execution_request(project_root, blocked_reason, "REVISE_SCI_PAPER_SEARCH_RUNNER / REVISE_SCI_OPENCODE_DRIVER_COMMAND")
        write_json(
            project_root / "reference_search_execution.json",
            {
                "ok": False,
                "executed": False,
                "runner_available": False,
                "driver_mode": "none",
                "blocked_reason": blocked_reason,
                "rounds_json": str(rounds_path.resolve()),
                "output": str(output_path.resolve()),
            },
        )
        update_status(project_root, output_exists=False)
        print(json.dumps({"ok": False, "blocked_reason": blocked_reason}, ensure_ascii=False))
        return 2

    command = shlex.split(runner) + ["--rounds-json", str(rounds_path), "--output", str(output_path), "--project-root", str(project_root)]
    completed = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        write_json(
            project_root / "reference_search_execution.json",
            {
                "ok": False,
                "executed": True,
                "runner_available": True,
                "command": command,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            },
        )
        update_status(project_root, output_exists=False)
        if completed.stdout:
            print(completed.stdout.strip())
        if completed.stderr:
            print(completed.stderr.strip(), file=sys.stderr)
        return completed.returncode

    payload = read_json(output_path, None)
    validation_errors = validate_output_payload(payload)
    if validation_errors:
        write_json(
            project_root / "reference_search_execution.json",
            {
                "ok": False,
                "executed": True,
                "runner_available": True,
                "command": command,
                "errors": validation_errors,
            },
        )
        update_status(project_root, output_exists=False)
        print(json.dumps({"ok": False, "errors": validation_errors}, ensure_ascii=False))
        return 1

    rows = payload.get("results", []) if isinstance(payload, dict) else payload
    write_json(
        project_root / "reference_search_execution.json",
        {
            "ok": True,
            "executed": True,
            "runner_available": True,
            "driver_mode": "local-runner",
            "command": command,
            "result_rows": len(rows or []),
            "output": str(output_path.resolve()),
        },
    )
    update_status(project_root, output_exists=True)
    print(json.dumps({"ok": True, "driver_mode": "local-runner", "result_rows": len(rows or []), "output": str(output_path.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
