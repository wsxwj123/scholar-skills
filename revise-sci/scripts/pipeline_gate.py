#!/usr/bin/env python3
"""round22 revise-sci 一键 pipeline 的状态机与 manifest 核心。

run_pipeline.py（编排/停点）与 strict_gate.py（bare gate 的 closure 链自验）共用。
只约束一键 pipeline 的承诺流程；各子脚本直接入口不经此模块（零回归边界）。

设计要点（PLAN-round22 §1）：
- project_state.json 增 pipeline_gate（schema_version=1 + epoch + phase + 各摘要）；
- 同一 epoch 内只允许合法前进；上游内容变化 epoch+1，旧 receipt 因 epoch 不匹配失效；
- 确认/回执一律绑定内容摘要（canonical JSON / 文件 SHA-256），路径相同不等于内容相同；
- state/receipt 写盘一律单文件原子替换（tmp+fsync+replace）。
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from common import normalize_ws, read_json

SCHEMA_VERSION = 1
PHASES = (
    "awaiting_comment_confirmation",
    "awaiting_revision_strategies",
    "awaiting_audit_detection",
    "awaiting_audit_reverse_verification",
    "awaiting_audit_adjudication",
    "awaiting_dod_review",
    "awaiting_dod_user_confirmation",
    "complete",
)
# 迁移只认这枚精确的 pre-round22 发布版 skill signature（正向证据 allowlist）
LEGACY_SIGNATURE_ALLOWLIST = (
    "23721343dc1eee1302cea469e6245535acccb7cd46da73cb6925b692a303ccee",
)
ABSENT = "absent:v1"
STRATEGY_CANONICAL = ("comply", "partial", "push_back", "needs_data")
STRATEGY_ALIASES = {
    "comply": "comply", "partial": "partial", "push_back": "push_back",
    "needs_data": "needs_data",
    # 现役别名（SKILL 语境里的驳回类）归一到 push_back
    "驳回": "push_back", "reject": "push_back", "pushback": "push_back",
}
AUDIT_TRACKS = ("numeric", "xref", "methods")
REVIEW_JOURNAL_STYLES = {"nature-review", "lancet-review"}


def canonical_sha(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def file_sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def file_sha_or_absent(path: Path) -> str:
    p = Path(path)
    return file_sha(p) if p.is_file() else ABSENT


def self_hashed(payload: dict[str, Any], field: str) -> dict[str, Any]:
    """带自身摘要字段的 JSON：只对移除该字段后的 payload 计算摘要（禁循环摘要）。"""
    body = {k: v for k, v in payload.items() if k != field}
    out = dict(payload)
    out[field] = canonical_sha(body)
    return out


def atomic_write_json(path: Path, payload: Any) -> None:
    """单文件原子替换：tmp + fsync + os.replace。任何失败不留半成品。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def new_gate(epoch: int = 1, phase: str = PHASES[0]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "epoch": epoch,
        "phase": phase,
        "inventory_sha256": None,
        "revision_input_sha256": None,
        "delivery_manifest_sha256": None,
        "audit_manifest_sha256": None,
        "dod_manifest_sha256": None,
        "migrated_from": None,
    }


GATE_KEYS = frozenset(new_gate())


def gate_schema_complete(gate: Any) -> bool:
    return isinstance(gate, dict) and GATE_KEYS.issubset(gate)


# ---------------------------------------------------------------- inventory --

def build_inventory(project_root: Path, comments_path: Path, epoch: int) -> dict[str, Any]:
    """确定性意见 inventory：reviewer + comment_id + 原意见规范空白文本。"""
    items = []
    for unit_path in sorted((project_root / "units").glob("*.json")):
        unit = read_json(unit_path, {}) or {}
        comment_id = normalize_ws(str(unit.get("comment_id", "")))
        if not comment_id:
            continue
        items.append({
            "comment_id": comment_id,
            "reviewer": normalize_ws(str(unit.get("reviewer", ""))),
            "comment_text": normalize_ws(str(unit.get("reviewer_comment_original", ""))),
        })
    payload = {
        "schema_version": SCHEMA_VERSION,
        "epoch": epoch,
        "comments_source_sha256": file_sha(comments_path),
        "items": items,
    }
    return self_hashed(payload, "inventory_sha256")


def inventory_path(project_root: Path) -> Path:
    return project_root / "audit" / "comment_inventory.json"


# ---------------------------------------------------------------- strategies --

def collect_strategies(project_root: Path) -> tuple[dict[str, str], list[str]]:
    """逐 unit 校验 revision_strategy。返回 (comment_id→canonical, 问题清单)。"""
    canonical: dict[str, str] = {}
    problems: list[str] = []
    for unit_path in sorted((project_root / "units").glob("*.json")):
        unit = read_json(unit_path, {}) or {}
        comment_id = normalize_ws(str(unit.get("comment_id", ""))) or unit_path.name
        raw = normalize_ws(str(unit.get("revision_strategy", "")))
        mapped = STRATEGY_ALIASES.get(raw) or STRATEGY_ALIASES.get(raw.lower())
        if mapped is None:
            problems.append(f"{comment_id}: revision_strategy 缺失/非法: {raw!r}"
                            f"（合法闭集 {'/'.join(STRATEGY_CANONICAL)}，现役别名先归一化）")
        else:
            canonical[comment_id] = mapped
    return canonical, problems


def revision_input_sha(inventory_sha: str, strategies: dict[str, str]) -> str:
    return canonical_sha({
        "inventory_sha256": inventory_sha,
        "strategies": sorted(strategies.items()),
    })


# ---------------------------------------------------------------- manifests --

def _sorted_units_entries(project_root: Path) -> list[list[str]]:
    return [
        [f"units/{p.name}", file_sha(p)]
        for p in sorted((project_root / "units").glob("*.json"))
    ]


def delivery_manifest_sha(project_root: Path, state: dict[str, Any]) -> str:
    """交付物 manifest：最终修订稿 md/docx、response md/docx、edit plan、
    final consistency report、排序后的 units/*.json（缺失记 absent:v1）。"""
    outputs = state.get("outputs") or {}
    entries: list[list[str]] = []
    for label, value in (
        ("output_md", outputs.get("output_md", "")),
        ("output_docx", outputs.get("output_docx", "")),
        ("response_md", outputs.get("response_md", str(project_root / "response_to_reviewers.md"))),
        ("response_docx", outputs.get("response_docx", str(project_root / "response_to_reviewers.docx"))),
    ):
        entries.append([label, file_sha_or_absent(Path(value)) if value else ABSENT])
    for name in ("manuscript_edit_plan.md", "final_consistency_report.md"):
        entries.append([name, file_sha_or_absent(project_root / name)])
    entries.extend(_sorted_units_entries(project_root))
    return canonical_sha({"schema_version": SCHEMA_VERSION, "files": entries})


def audit_manifest_sha(project_root: Path, delivery_sha: str) -> str:
    return canonical_sha({
        "schema_version": SCHEMA_VERSION,
        "delivery_manifest_sha256": delivery_sha,
        "numeric_candidates.json": file_sha_or_absent(project_root / "numeric_candidates.json"),
        "outline.json": file_sha_or_absent(project_root / "outline.json"),
        "methods_terms.json": file_sha_or_absent(project_root / "methods_terms.json"),
    })


def finding_id(track: str, finding: dict[str, Any]) -> str:
    """<track>-<canonical item sha256 前12位>。canonical item = schema 校验后的
    finding 原对象：不增删字段、不注入默认值；对象键排序、紧凑分隔符、
    ensure_ascii=False 的 UTF-8。findings 外层重排不改单项 ID。"""
    return f"{track}-{canonical_sha(finding).removeprefix('sha256:')[:12]}"


# ---------------------------------------------------------------- detection --

def write_detection_task(project_root: Path, gate: dict[str, Any],
                         methods_na_reason: str = "") -> dict[str, Any]:
    inputs: list[list[str]] = []
    for name in ("numeric_candidates.json", "outline.json", "methods_terms.json"):
        path = project_root / name
        if path.is_file():
            inputs.append([name, file_sha(path)])
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "epoch": gate["epoch"],
        "delivery_manifest_sha256": gate["delivery_manifest_sha256"],
        "audit_manifest_sha256": gate["audit_manifest_sha256"],
        "inputs": inputs,
    }
    if methods_na_reason:
        payload["methods_track"] = {"status": "na", "reason": methods_na_reason}
    task = self_hashed(payload, "task_manifest_sha256")
    atomic_write_json(project_root / "audit" / "detection_task.json", task)
    return task


_DETECTION_REQUIRED = {
    "schema_version", "epoch", "track", "delivery_manifest_sha256",
    "audit_manifest_sha256", "task_manifest_sha256", "status", "reason", "findings",
}


def validate_detection_returns(project_root: Path, task: dict[str, Any],
                               gate: dict[str, Any]) -> tuple[dict[str, list], list[str]]:
    """校验三轨 detection return（round22 envelope）。返回 (track→findings, 错误)。
    Methods 跳过必须 status=na + 非空 reason + findings=[]；其他轨不得 na。"""
    findings: dict[str, list] = {}
    errors: list[str] = []
    for track in AUDIT_TRACKS:
        path = project_root / "audit" / f"detection_{track}.json"
        if not path.is_file():
            errors.append(f"detection return missing: audit/detection_{track}.json")
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            errors.append(f"detection_{track}.json unreadable/bad JSON: {exc.__class__.__name__}")
            continue
        if not isinstance(payload, dict) or not _DETECTION_REQUIRED.issubset(payload):
            missing = sorted(_DETECTION_REQUIRED - set(payload or {})) if isinstance(payload, dict) else "not an object"
            errors.append(f"detection_{track}.json bad schema: {missing}")
            continue
        if payload["task_manifest_sha256"] != task["task_manifest_sha256"]:
            errors.append(f"detection_{track}.json task_manifest_sha256 mismatch (stale return)")
            continue
        if payload["epoch"] != gate["epoch"]:
            errors.append(f"detection_{track}.json epoch mismatch")
            continue
        if payload["track"] != track:
            errors.append(f"detection_{track}.json track mismatch: {payload['track']!r}")
            continue
        status = payload["status"]
        rows = payload["findings"]
        if not isinstance(rows, list):
            errors.append(f"detection_{track}.json findings must be a list")
            continue
        if status == "na":
            if track != "methods":
                errors.append(f"detection_{track}.json status=na is only legal for the methods track")
                continue
            # 只有 pipeline 在 task 里明确声明 Methods 轨 na（综述类型）才接受 na；
            # 实验稿/保守运行场景的 methods na 属非法跳过。
            if (task.get("methods_track") or {}).get("status") != "na":
                errors.append("detection_methods.json status=na 但本项目 Methods 轨按实验稿运行（不得跳过）")
                continue
            if not normalize_ws(str(payload["reason"])) or rows:
                errors.append("detection_methods.json na requires a non-empty reason and findings=[]")
                continue
            findings[track] = []
            continue
        if status != "completed":
            errors.append(f"detection_{track}.json unsupported status: {status!r}")
            continue
        bad = [row for row in rows if not isinstance(row, dict) or not row]
        if bad:
            errors.append(f"detection_{track}.json contains non-object findings")
            continue
        if track == "numeric":
            for row in rows:
                if not normalize_ws(str(row.get("evidence_quote", ""))):
                    errors.append("detection_numeric.json finding has empty evidence_quote")
                    break
            else:
                findings[track] = rows
            continue
        findings[track] = rows
    return findings, errors


# ------------------------------------------------------- reverse verification --

_POLARITY_CHECK = {
    "numeric": ("零容差极性：两处取值针对同一指标/对象/分组/时间点/单位且不完全相等 → pass=矛盾属实(confirmed)；"
                "非同一测量或取值实际一致 → fail=假矛盾剔除(refuted)；无法核验 → na。逐字证据必填。"),
    "xref": ("极性：被引编号在全文找不到定义处(caption/小节标题行，引用句自身不算) → pass=悬空确认；"
             "找到定义处或指向合理 → fail=剔除；无法核验 → na。必须区分定义处与引用处。"),
    "methods": ("两条件极性：本研究确实使用该方法 且 方法学未交代/未指向补充材料/未引用文献描述 → pass=漏写确认；"
                "方法学已写/指向补充材料/引用文献描述/结果只是引用他人 → fail=剔除；无法核验 → na。"),
}


def write_reverse_tasks(project_root: Path, gate: dict[str, Any],
                        track_findings: dict[str, list]) -> dict[str, dict[str, Any]]:
    """为每个有真 finding 的轨生成动态 checklist + 绑定 task。返回 track→task。
    finding ID 由 pipeline 生成并写进 checklist/task，检测代理不自造 ID。"""
    tasks: dict[str, dict[str, Any]] = {}
    for track, rows in track_findings.items():
        if not rows:
            continue
        gate_name = f"{track}-verify"
        ids = [finding_id(track, row) for row in rows]
        items = [{
            "id": fid,
            "name": f"{track} finding {fid}",
            "check": _POLARITY_CHECK[track],
            "finding": row,
        } for fid, row in zip(ids, rows)]
        checklist = {"skill": "revise-sci",
                     "gates": {gate_name: {"title": f"{track} 反向验证(round22)", "items": items}}}
        checklist_file = project_root / f"{track}_verify_checklist.json"
        atomic_write_json(checklist_file, checklist)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "epoch": gate["epoch"],
            "audit_manifest_sha256": gate["audit_manifest_sha256"],
            "checklist_sha256": file_sha(checklist_file),
            "finding_ids": ids,
        }
        task = self_hashed(payload, "task_manifest_sha256")
        atomic_write_json(project_root / "audit" / f"{gate_name}_task.json", task)
        tasks[track] = task
    return tasks


def read_reverse_task(project_root: Path, track: str) -> dict[str, Any] | None:
    payload = read_json(project_root / "audit" / f"{track}-verify_task.json", None)
    return payload if isinstance(payload, dict) else None


def interpret_reverse_return(project_root: Path, track: str, task: dict[str, Any],
                             ) -> tuple[list[dict[str, Any]], list[str]]:
    """读 .review_return_<track>-verify.json（round22 envelope），先核 task hash，
    再逐条解释 verdict：pass=confirmed、fail/na=refuted、problems=未核(rc=2)。"""
    errors: list[str] = []
    return_path = project_root / f".review_return_{track}-verify.json"
    if not return_path.is_file():
        return [], [f"missing reverse return: .review_return_{track}-verify.json"]
    try:
        payload = json.loads(return_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [], [f".review_return_{track}-verify.json bad JSON: {exc.__class__.__name__}"]
    if not isinstance(payload, dict):
        return [], [f".review_return_{track}-verify.json must be a round22 envelope object"]
    if payload.get("task_manifest_sha256") != task["task_manifest_sha256"]:
        return [], [f"{track}-verify return task_manifest_sha256 mismatch (verify前先核 task hash)"]
    review = payload.get("review")
    if not isinstance(review, list):
        return [], [f"{track}-verify return review must be a list"]
    expected_ids = list(task.get("finding_ids") or [])
    seen: dict[str, dict[str, Any]] = {}
    for entry in review:
        if not isinstance(entry, dict) or "id" not in entry:
            errors.append(f"{track}-verify return has malformed entry")
            continue
        eid = entry["id"]
        if eid not in expected_ids:
            errors.append(f"{track}-verify return references unknown finding id: {eid}")
            continue
        if eid in seen:
            errors.append(f"{track}-verify return duplicates id: {eid}")
            continue
        verdict = entry.get("verdict")
        if verdict not in {"pass", "fail", "na"}:
            errors.append(f"{track}-verify {eid}: verdict 非法 ({verdict!r})")
            continue
        if not normalize_ws(str(entry.get("evidence", ""))):
            errors.append(f"{track}-verify {eid}: evidence 为空（problems=未核）")
            continue
        seen[eid] = entry
    for eid in expected_ids:
        if eid not in seen and not any(eid in e for e in errors):
            errors.append(f"{track}-verify 缺漏未裁决: {eid}")
    results = [{
        "finding_id": eid,
        "verdict": seen[eid]["verdict"],
        "result": "confirmed" if seen[eid]["verdict"] == "pass" else "refuted",
    } for eid in expected_ids if eid in seen]
    return results, errors


# ------------------------------------------------------------ DoD manifest --

def dod_manifest_inputs(project_root: Path, state: dict[str, Any],
                        checklist_path: Path) -> list[list[str]]:
    """DoD manifest 的单一真源：枚举 preclose 实际读取的科学状态/证据文件
    （含引用/polish/coverage/units 与 project_state 科学字段投影），外加 DoD
    checklist 与盲审 pack 的 comments 源。明确排除 .pipeline_receipts/* 与
    pipeline_gate 字段，避免 closure 与自身循环。preclose/final 与 hash builder
    共用本函数。"""
    entries: list[list[str]] = []
    projection = {k: v for k, v in state.items() if k != "pipeline_gate"}
    entries.append(["project_state:projection", canonical_sha(projection)])
    outputs = state.get("outputs") or {}
    comments_path = str((state.get("inputs") or {}).get("comments_path") or "")
    entries.append(["inputs/comments", file_sha_or_absent(Path(comments_path)) if comments_path else ABSENT])
    entries.append(["references/dod_checklist.json", file_sha_or_absent(checklist_path)])
    for label, value in (("output_md", outputs.get("output_md", "")),
                         ("output_docx", outputs.get("output_docx", ""))):
        entries.append([label, file_sha_or_absent(Path(value)) if value else ABSENT])
    fixed = (
        "response_to_reviewers.md", "response_to_reviewers.docx",
        "manuscript_edit_plan.md", "final_consistency_report.md",
        "manuscript_section_index.json", "si_section_index.json",
        "index.json", "issue_matrix.md",
        "numeric_candidates.json", "outline.json", "methods_terms.json",
        "reference_sync_report.json", "claim_evidence.json",
        "paper_search_guard_report.json",
        "data/literature_index.json", "data/synthesis_matrix.json",
        "data/synthesis_matrix_audit.json", "data/reference_registry.json",
        "data/reference_coverage_audit.json",
        "revision_polish_manifest.json", "revision_polish_execution.json",
        "state/section_digests.json", "state/comment_registry.json",
    )
    for name in fixed:
        entries.append([name, file_sha_or_absent(project_root / name)])
    for pattern in ("units/*.json", "comment_records/*.md",
                    "state/comment_windows/*.json", "state/write_cycle_reports/*.json"):
        for path in sorted(project_root.glob(pattern)):
            entries.append([str(path.relative_to(project_root)).replace(os.sep, "/"), file_sha(path)])
    return entries


def dod_manifest_sha(project_root: Path, state: dict[str, Any], checklist_path: Path) -> str:
    return canonical_sha({
        "schema_version": SCHEMA_VERSION,
        "entries": dod_manifest_inputs(project_root, state, checklist_path),
    })


def write_dod_task(project_root: Path, gate: dict[str, Any], checklist_path: Path) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "epoch": gate["epoch"],
        "dod_manifest_sha256": gate["dod_manifest_sha256"],
        "checklist_sha256": file_sha(checklist_path),
    }
    task = self_hashed(payload, "task_manifest_sha256")
    atomic_write_json(project_root / "audit" / "revision-dod_task.json", task)
    return task


RECEIPTS_DIR = ".pipeline_receipts"
_DOD_RECEIPT_REQUIRED = {"schema_version", "epoch", "dod_manifest_sha256",
                         "checklist_sha256", "task_manifest_sha256", "review_return_sha256"}
_CLOSURE_REQUIRED = {"schema_version", "epoch", "dod_manifest_sha256",
                     "dod_receipt_sha256", "confirmed_at"}


def verify_closure_chain(project_root: Path, state: dict[str, Any],
                         checklist_path: Path) -> list[str]:
    """bare strict gate 的 closure 链自验：不能只靠 pipeline 不调用。"""
    errors: list[str] = []
    gate = state.get("pipeline_gate")
    if not gate_schema_complete(gate):
        return ["pipeline_gate schema_version=1 字段不完整（删字段不得降级 legacy）"]
    if gate.get("phase") != "complete":
        errors.append(f"pipeline_gate phase={gate.get('phase')!r}：无用户收口确认(dod_closure)不得运行最终 bare gate")
    receipt_path = project_root / RECEIPTS_DIR / "revision_dod.json"
    closure_path = project_root / RECEIPTS_DIR / "dod_closure.json"
    receipt = read_json(receipt_path, None)
    closure = read_json(closure_path, None)
    if not isinstance(receipt, dict) or not _DOD_RECEIPT_REQUIRED.issubset(receipt):
        errors.append("revision_dod receipt 缺失/坏 schema")
        return errors
    if not isinstance(closure, dict) or not _CLOSURE_REQUIRED.issubset(closure):
        errors.append("dod_closure 缺失/坏 schema（无用户收口确认）")
        return errors
    if closure["dod_receipt_sha256"] != file_sha(receipt_path):
        errors.append("dod_closure.dod_receipt_sha256 与 revision_dod receipt 实际摘要不符（closure 链被篡改）")
    if not (closure["epoch"] == receipt["epoch"] == gate["epoch"]):
        errors.append("closure/receipt/pipeline_gate epoch 不一致（epoch 变化使旧 closure 逻辑失效）")
    if not (closure["dod_manifest_sha256"] == receipt["dod_manifest_sha256"] == gate["dod_manifest_sha256"]):
        errors.append("closure/receipt/gate 的 dod_manifest_sha256 不一致")
    current = dod_manifest_sha(project_root, state, checklist_path)
    if current != gate["dod_manifest_sha256"]:
        errors.append("dod manifest 已变化：独立 review、DoD receipt 与 closure 全部逻辑失效，须回 pipeline 重走 DoD")
    return_path = project_root / ".review_return_revision-dod.json"
    if not return_path.is_file() or file_sha(return_path) != receipt["review_return_sha256"]:
        errors.append("revision-dod raw return 缺失或与 receipt 绑定摘要不符")
    return errors
