#!/usr/bin/env python3
"""Consistency map CRUD and validation for nsfc-proposal."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

SECTIONS_ALLOWED_FOR_F = {"P3_1_研究基础与可行性分析", "P3_2_工作条件"}

ENTITY_ALIASES = {
    "SQ": "scientific_questions",
    "H": "hypotheses",
    "O": "objectives",
    "KSQ": "key_scientific_problems",
    "RC": "research_contents",
    "M": "methodologies",
    "IN": "innovations",
    "F": "feasibility_evidence",
}

DEFAULT_MAP = {
    "scientific_questions": [],
    "hypotheses": [],
    "objectives": [],
    "key_scientific_problems": [],
    "research_contents": [],
    "methodologies": [],
    "innovations": [],
    "feasibility_evidence": [],
    "keywords_trace": {},
}

RULE_DOC = {
    "V-01": "每个SQ必须至少映射到一个H和一个KSQ",
    "V-02": "H/O/RC/KSQ数量相等且映射完整",
    "V-03": "每个RC至少映射到一个M",
    "V-04": "每个RC关联annual_plan_year",
    "V-05": "每个IN追溯到RC和M",
    "V-06": "每个M至少有一个F",
    "V-07": "F来源为P3_1或P3_2",
    "V-08": "关键词在摘要/P1/P2中均出现",
    "V-09": "M的budget_trace可追溯到budget_table",
    "V-10": "无孤立条目",
    "V-11": "prior_work类F条目须有representative_works且supports_technique与对应M的key_technique有交集",
    "V-12": "每个M须有非空alternative_plan（备选技术路线）",
}

# phase→应验规则集。依据 SKILL.md「V 规则分层说明」与 references/02_核心机制.md：
# Phase 2 只验 H/O/RC/KSQ/IN 结构链路；Phase 3 起加 V-12（alternative_plan）；Phase 7 全量。
# V-10 含“每个 M 被 F 覆盖”检查,F 在 Phase 2/3 尚空必假阳;其结构子检查与
# V-01/V-02/V-08 重叠不会漏,故 V-10 只在 Phase 7(F 齐全后)验。
PHASE_RULES = {
    "2": ["V-01", "V-02", "V-03", "V-04", "V-05", "V-08"],
    "3": ["V-01", "V-02", "V-03", "V-04", "V-05", "V-08", "V-12"],
    "7": list(RULE_DOC.keys()),
}


def load_map(path: Path) -> dict[str, Any]:
    if not path.exists():
        return copy.deepcopy(DEFAULT_MAP)
    data = json.loads(path.read_text(encoding="utf-8"))
    for k, v in DEFAULT_MAP.items():
        data.setdefault(k, copy.deepcopy(v))
    return data


def unknown_top_level_keys(path: Path) -> list[str]:
    """返回输入 JSON 中不属于 DEFAULT_MAP 的顶层键。

    用于堵 validate 假绿：字段名写错（如 hypotheses→h_nodes）时，load_map 会把
    错键当未知数据丢弃、正确键 setdefault 成空集合，validate 便 vacuously 全 PASS。
    这里读原始文件键名暴露此类拼写错位，由调用方据此 fail-closed。
    """
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return []
    return [k for k in data if k not in DEFAULT_MAP]


def save_map(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _ids(items: list[dict[str, Any]]) -> set[str]:
    return {x.get("id") for x in items if x.get("id")}


def _find_entity(cm: dict[str, Any], entity_id: str) -> tuple[str, dict[str, Any]] | None:
    for collection, items in cm.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if item.get("id") == entity_id:
                return collection, item
    return None


def _as_collection(entity_type: str) -> str:
    et = entity_type.strip()
    if et in DEFAULT_MAP:
        return et
    if et in ENTITY_ALIASES:
        return ENTITY_ALIASES[et]
    raise KeyError(f"unknown entity_type: {entity_type}")


def _v01(cm: dict[str, Any]) -> bool:
    sq_ids = _ids(cm.get("scientific_questions", []))
    if not sq_ids:
        return True
    h_linked: set[str] = set()
    for h in cm.get("hypotheses", []):
        for sq in h.get("mapped_from_sq", []) or []:
            h_linked.add(sq)
    k_linked: set[str] = set()
    for k in cm.get("key_scientific_problems", []):
        for sq in k.get("mapped_from_sq", []) or []:
            k_linked.add(sq)
    return all(sq in h_linked and sq in k_linked for sq in sq_ids)


def _v02(cm: dict[str, Any]) -> bool:
    hs = cm.get("hypotheses", [])
    os = cm.get("objectives", [])
    rs = cm.get("research_contents", [])
    ks = cm.get("key_scientific_problems", [])
    if not (len(hs) == len(os) == len(rs) == len(ks)):
        return False

    o_ids = _ids(os)
    r_ids = _ids(rs)
    k_ids = _ids(ks)
    for h in hs:
        if h.get("mapped_to_objective") not in o_ids:
            return False
        if h.get("mapped_to_rc") not in r_ids:
            return False
        if h.get("mapped_to_ksq") not in k_ids:
            return False
    return True


def _v03(cm: dict[str, Any]) -> bool:
    return all((rc.get("mapped_to_method") or []) for rc in cm.get("research_contents", []))


def _v04(cm: dict[str, Any]) -> bool:
    return all(rc.get("annual_plan_year") for rc in cm.get("research_contents", []))


def _v05(cm: dict[str, Any]) -> bool:
    return all(i.get("mapped_from_rc") and i.get("mapped_from_method") for i in cm.get("innovations", []))


def _v06(cm: dict[str, Any]) -> bool:
    methods = _ids(cm.get("methodologies", []))
    if not methods:
        return True
    covered = set()
    for f in cm.get("feasibility_evidence", []):
        for m in f.get("supports_method", []) or []:
            covered.add(m)
    return methods.issubset(covered)


def _v07(cm: dict[str, Any]) -> bool:
    return all(f.get("source_section") in SECTIONS_ALLOWED_FOR_F for f in cm.get("feasibility_evidence", []))


def _v08(cm: dict[str, Any]) -> bool:
    required = {"00_摘要", "P1_立项依据", "P2_研究内容"}
    for _, sections in (cm.get("keywords_trace", {}) or {}).items():
        if not required.issubset(set(sections)):
            return False
    return True


def _v09(cm: dict[str, Any]) -> bool:
    methods = cm.get("methodologies", [])
    if not methods:
        return True
    return all(m.get("budget_trace") for m in methods)


def _v10(cm: dict[str, Any]) -> bool:
    sq_ids = _ids(cm.get("scientific_questions", []))
    h_ids = _ids(cm.get("hypotheses", []))
    o_ids = _ids(cm.get("objectives", []))
    r_ids = _ids(cm.get("research_contents", []))
    k_ids = _ids(cm.get("key_scientific_problems", []))
    m_ids = _ids(cm.get("methodologies", []))
    in_ids = _ids(cm.get("innovations", []))

    sq_linked_h = set()
    sq_linked_k = set()
    for h in cm.get("hypotheses", []):
        sq_linked_h.update(h.get("mapped_from_sq", []) or [])
    for k in cm.get("key_scientific_problems", []):
        sq_linked_k.update(k.get("mapped_from_sq", []) or [])

    for sq in sq_ids:
        if sq not in sq_linked_h and sq not in sq_linked_k:
            return False

    rc_ids_with_links = set()
    for h in cm.get("hypotheses", []):
        if h.get("mapped_to_objective") not in o_ids:
            return False
        if h.get("mapped_to_rc") not in r_ids:
            return False
        if h.get("mapped_to_ksq") not in k_ids:
            return False
        rc_ids_with_links.add(h.get("mapped_to_rc"))

    for rc in cm.get("research_contents", []):
        ms = rc.get("mapped_to_method", []) or []
        if not ms:
            return False
        for mid in ms:
            if mid not in m_ids:
                return False
        rc_ids_with_links.add(rc.get("id"))
        for iid in rc.get("mapped_to_innovation", []) or []:
            if iid not in in_ids:
                return False

    for inn in cm.get("innovations", []):
        for rc in inn.get("mapped_from_rc", []) or []:
            if rc not in r_ids:
                return False
        for mid in inn.get("mapped_from_method", []) or []:
            if mid not in m_ids:
                return False

    supported_methods = set()
    for f in cm.get("feasibility_evidence", []):
        mids = f.get("supports_method", []) or []
        if not mids:
            return False
        for mid in mids:
            if mid not in m_ids:
                return False
            supported_methods.add(mid)

    if m_ids and not m_ids.issubset(supported_methods):
        return False

    return True


def _v11(cm: dict[str, Any]) -> bool:
    """V-11: prior_work类F须有representative_works，且supports_technique与对应M的key_technique有交集。"""
    m_key_tech: dict[str, str] = {
        m.get("id", ""): m.get("key_technique", "")
        for m in cm.get("methodologies", [])
    }
    for f in cm.get("feasibility_evidence", []):
        if f.get("type") != "prior_work":
            continue
        rws = f.get("representative_works", []) or []
        if not rws:
            return False
        # 检查至少一条 representative_work 的 supports_technique 与任一关联 M 的 key_technique 有字符串交集
        supported_methods = f.get("supports_method", []) or []
        matched = False
        for rw in rws:
            rw_tech = rw.get("supports_technique", "") or ""
            for mid in supported_methods:
                m_tech = m_key_tech.get(mid, "")
                if rw_tech and m_tech and (rw_tech in m_tech or m_tech in rw_tech or rw_tech == m_tech):
                    matched = True
                    break
            if matched:
                break
        if not matched:
            return False
    return True


def _v12(cm: dict[str, Any]) -> bool:
    """V-12: 每个M须有非空alternative_plan（备选技术路线）。"""
    return all(
        bool((m.get("alternative_plan") or "").strip())
        for m in cm.get("methodologies", [])
    )


def _entity_locators(cm: dict[str, Any]) -> dict[str, dict[str, Any]]:
    loc: dict[str, dict[str, Any]] = {}
    for collection, items in cm.items():
        if not isinstance(items, list):
            continue
        for item in items:
            eid = item.get("id")
            if not eid:
                continue
            loc[eid] = {
                "id": eid,
                "collection": collection,
                "source_section": item.get("source_section"),
                "statement_excerpt": str(item.get("statement", ""))[:80],
            }
    return loc


def _rule_locations(cm: dict[str, Any], rule_id: str) -> list[dict[str, Any]]:
    loc = _entity_locators(cm)

    def to_loc(eid: str) -> dict[str, Any]:
        x = loc.get(eid, {"id": eid, "collection": "unknown", "source_section": None, "statement_excerpt": ""})
        return {
            "id": x["id"],
            "source_file": f"sections/{x['source_section']}.md" if x.get("source_section") else None,
            "source_section": x.get("source_section"),
            "collection": x.get("collection"),
            "statement_excerpt": x.get("statement_excerpt"),
        }

    bad_ids: set[str] = set()
    if rule_id == "V-01":
        sq_ids = _ids(cm.get("scientific_questions", []))
        h_linked, k_linked = set(), set()
        for h in cm.get("hypotheses", []):
            h_linked.update(h.get("mapped_from_sq", []) or [])
        for k in cm.get("key_scientific_problems", []):
            k_linked.update(k.get("mapped_from_sq", []) or [])
        for sq in sq_ids:
            if sq not in h_linked or sq not in k_linked:
                bad_ids.add(sq)
    elif rule_id == "V-02":
        for h in cm.get("hypotheses", []):
            bad = False
            if h.get("mapped_to_objective") not in _ids(cm.get("objectives", [])):
                bad = True
            if h.get("mapped_to_rc") not in _ids(cm.get("research_contents", [])):
                bad = True
            if h.get("mapped_to_ksq") not in _ids(cm.get("key_scientific_problems", [])):
                bad = True
            if bad and h.get("id"):
                bad_ids.add(h["id"])
    elif rule_id == "V-03":
        for rc in cm.get("research_contents", []):
            if not (rc.get("mapped_to_method") or []):
                if rc.get("id"):
                    bad_ids.add(rc["id"])
    elif rule_id == "V-04":
        for rc in cm.get("research_contents", []):
            if not rc.get("annual_plan_year") and rc.get("id"):
                bad_ids.add(rc["id"])
    elif rule_id == "V-05":
        for inn in cm.get("innovations", []):
            if (not inn.get("mapped_from_rc")) or (not inn.get("mapped_from_method")):
                if inn.get("id"):
                    bad_ids.add(inn["id"])
    elif rule_id == "V-06":
        covered = set()
        for f in cm.get("feasibility_evidence", []):
            covered.update(f.get("supports_method", []) or [])
        for m in cm.get("methodologies", []):
            if m.get("id") and m["id"] not in covered:
                bad_ids.add(m["id"])
    elif rule_id == "V-07":
        for f in cm.get("feasibility_evidence", []):
            if f.get("source_section") not in SECTIONS_ALLOWED_FOR_F and f.get("id"):
                bad_ids.add(f["id"])
    elif rule_id == "V-08":
        required = {"00_摘要", "P1_立项依据", "P2_研究内容"}
        for kw, sections in (cm.get("keywords_trace", {}) or {}).items():
            if not required.issubset(set(sections)):
                bad_ids.add(f"KW:{kw}")
    elif rule_id == "V-09":
        for m in cm.get("methodologies", []):
            if not m.get("budget_trace") and m.get("id"):
                bad_ids.add(m["id"])
    elif rule_id == "V-10":
        if not _v10(cm):
            for coll in (
                "scientific_questions",
                "hypotheses",
                "objectives",
                "key_scientific_problems",
                "research_contents",
                "methodologies",
                "innovations",
                "feasibility_evidence",
            ):
                for item in cm.get(coll, []):
                    if item.get("id"):
                        bad_ids.add(item["id"])
    elif rule_id == "V-11":
        m_key_tech: dict[str, str] = {
            m.get("id", ""): m.get("key_technique", "")
            for m in cm.get("methodologies", [])
        }
        for f in cm.get("feasibility_evidence", []):
            if f.get("type") != "prior_work":
                continue
            rws = f.get("representative_works", []) or []
            supported = f.get("supports_method", []) or []
            matched = False
            for rw in rws:
                rw_tech = rw.get("supports_technique", "") or ""
                for mid in supported:
                    m_tech = m_key_tech.get(mid, "")
                    if rw_tech and m_tech and (rw_tech in m_tech or m_tech in rw_tech or rw_tech == m_tech):
                        matched = True
                        break
                if matched:
                    break
            if not rws or not matched:
                if f.get("id"):
                    bad_ids.add(f["id"])
    elif rule_id == "V-12":
        for m in cm.get("methodologies", []):
            if not (m.get("alternative_plan") or "").strip() and m.get("id"):
                bad_ids.add(m["id"])

    out = []
    for eid in sorted(bad_ids):
        if eid.startswith("KW:"):
            out.append(
                {
                    "id": eid,
                    "source_file": "sections/00_摘要_中文.md | sections/P1_立项依据.md | sections/P2_研究内容.md",
                    "source_section": "keywords_trace",
                    "collection": "keywords_trace",
                    "statement_excerpt": "keyword cross-section trace missing",
                }
            )
        else:
            out.append(to_loc(eid))
    return out


RULE_FNS = {
    "V-01": ("ERROR", _v01),
    "V-02": ("ERROR", _v02),
    "V-03": ("ERROR", _v03),
    "V-04": ("WARNING", _v04),
    "V-05": ("ERROR", _v05),
    "V-06": ("ERROR", _v06),
    "V-07": ("WARNING", _v07),
    "V-08": ("WARNING", _v08),
    "V-09": ("INFO", _v09),
    "V-10": ("WARNING", _v10),
    "V-11": ("WARNING", _v11),
    "V-12": ("ERROR", _v12),
}


def validate(cm: dict[str, Any], rules: list[str] | None = None) -> dict[str, dict[str, Any]]:
    """校验规则。rules 为 None 时全量计算；否则只计算并只报指定规则子集。"""
    selected = list(RULE_FNS.keys()) if rules is None else rules
    result: dict[str, dict[str, Any]] = {}
    for k in selected:
        severity, fn = RULE_FNS[k]
        passed = fn(cm)
        result[k] = {
            "rule": RULE_DOC[k],
            "severity": severity,
            "pass": passed,
            "locations": [] if passed else _rule_locations(cm, k),
        }
    return result


def register_entity(cm: dict[str, Any], entity_type: str, payload: dict[str, Any], upsert: bool = False) -> None:
    collection = _as_collection(entity_type)
    if "id" not in payload:
        raise ValueError("payload must include id")

    items = cm[collection]
    for idx, item in enumerate(items):
        if item.get("id") == payload["id"]:
            if upsert:
                merged = dict(item)
                merged.update(payload)
                items[idx] = merged
                return
            raise ValueError(f"duplicate entity id: {payload['id']}")
    items.append(payload)


def link_entity(cm: dict[str, Any], from_id: str, field: str, to_id: str) -> None:
    found = _find_entity(cm, from_id)
    if not found:
        raise KeyError(f"from_id not found: {from_id}")
    _, item = found

    if field not in item or item[field] is None:
        item[field] = []

    if isinstance(item[field], list):
        if to_id not in item[field]:
            item[field].append(to_id)
    else:
        item[field] = to_id


def unlink_entity(cm: dict[str, Any], from_id: str, field: str, to_id: str | None = None) -> None:
    found = _find_entity(cm, from_id)
    if not found:
        raise KeyError(f"from_id not found: {from_id}")
    _, item = found

    if field not in item:
        return

    if isinstance(item[field], list):
        if to_id is None:
            item[field] = []
        else:
            item[field] = [x for x in item[field] if x != to_id]
    elif to_id is None or item[field] == to_id:
        item[field] = None


def query_by_section(cm: dict[str, Any], section: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in cm.items():
        if isinstance(v, list):
            out[k] = [x for x in v if x.get("source_section") == section]
    return out


def export_readable(cm: dict[str, Any], section: str | None = None) -> str:
    payload = query_by_section(cm, section) if section else cm
    lines: list[str] = []
    for key, items in payload.items():
        if not isinstance(items, list):
            continue
        lines.append(f"## {key}")
        if not items:
            lines.append("- (empty)")
            continue
        for item in items:
            item_id = item.get("id", "<no-id>")
            statement = item.get("statement", "")
            lines.append(f"- {item_id}: {statement}")
    return "\n".join(lines)


def diff_maps(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    keys = set(a.keys()) | set(b.keys())
    for key in sorted(keys):
        av = a.get(key)
        bv = b.get(key)
        if av != bv:
            out[key] = {"before": av, "after": bv}
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default="data/consistency_map.json")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_reg = sub.add_parser("register")
    p_reg.add_argument("entity_type")
    p_reg.add_argument("payload_json")
    p_reg.add_argument("--upsert", action="store_true")

    p_link = sub.add_parser("link")
    p_link.add_argument("--from-id", required=True)
    p_link.add_argument("--field", required=True)
    p_link.add_argument("--to-id", required=True)

    p_unlink = sub.add_parser("unlink")
    p_unlink.add_argument("--from-id", required=True)
    p_unlink.add_argument("--field", required=True)
    p_unlink.add_argument("--to-id")

    p_val = sub.add_parser("validate")
    g_val = p_val.add_mutually_exclusive_group()
    g_val.add_argument("--rules", help="只验证逗号分隔的规则子集，如 V-01,V-02；不传则全量")
    g_val.add_argument("--phase", choices=sorted(PHASE_RULES.keys()), help="按阶段验证该阶段应验的规则集（语法糖）")

    p_one = sub.add_parser("validate-one")
    p_one.add_argument("rule", choices=sorted(RULE_DOC.keys()))  # V-01~V-12

    p_query = sub.add_parser("query")
    p_query.add_argument("--section", required=True)

    p_exp = sub.add_parser("export")
    p_exp.add_argument("--section")
    p_exp.add_argument("--readable", action="store_true")

    p_diff = sub.add_parser("diff")
    p_diff.add_argument("--other", required=True)

    args = parser.parse_args()
    path = Path(args.path)
    cm = load_map(path)

    if args.cmd == "register":
        register_entity(cm, args.entity_type, json.loads(args.payload_json), upsert=args.upsert)
        save_map(path, cm)
        print(json.dumps({"ok": True}, ensure_ascii=False))
        return 0

    if args.cmd == "link":
        link_entity(cm, args.from_id, args.field, args.to_id)
        save_map(path, cm)
        print(json.dumps({"ok": True}, ensure_ascii=False))
        return 0

    if args.cmd == "unlink":
        unlink_entity(cm, args.from_id, args.field, args.to_id)
        save_map(path, cm)
        print(json.dumps({"ok": True}, ensure_ascii=False))
        return 0

    if args.cmd == "validate":
        unknown_keys = unknown_top_level_keys(path)
        if unknown_keys:
            print(
                json.dumps(
                    {
                        "error": "unknown_top_level_keys",
                        "severity": "ERROR",
                        "unknown_keys": sorted(unknown_keys),
                        "allowed_keys": sorted(DEFAULT_MAP.keys()),
                        "hint": "字段名拼错会被静默丢弃导致假绿；请改用 DEFAULT_MAP 中的标准键名",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 1
        if args.phase:
            rules = PHASE_RULES[args.phase]
        elif args.rules:
            rules = [r.strip() for r in args.rules.split(",") if r.strip()]
            unknown = [r for r in rules if r not in RULE_DOC]
            if unknown:
                parser.error(f"unknown rule id(s): {', '.join(unknown)}")
        else:
            rules = None
        results = validate(cm, rules)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        has_error_fail = any(
            r.get("severity") == "ERROR" and not r.get("pass")
            for r in results.values()
        )
        return 1 if has_error_fail else 0

    if args.cmd == "validate-one":
        results = validate(cm)
        print(json.dumps({args.rule: results[args.rule]}, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "query":
        print(json.dumps(query_by_section(cm, args.section), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "export":
        if args.readable:
            print(export_readable(cm, args.section))
        else:
            data = query_by_section(cm, args.section) if args.section else cm
            print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "diff":
        other = load_map(Path(args.other))
        print(json.dumps(diff_maps(cm, other), ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
