#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sci2Doc thesis profile helpers.

统一维护论文目标参数，避免文档规范与脚本阈值冲突。
"""

import json
import os
import tempfile

DEFAULT_FORMAT_PROFILE = {
    "mode": "default_generic",
    "status": "ready",
    "university_name": "示例大学",
    "degree_type": "博士学位论文",
    "source_template_files": [],
    "requirements_summary": [],
    "missing_requirements": [],
    "allow_docx_generation": True,
}

DEFAULT_PAGE_MARGINS_CM = {
    "top": 2.54,
    "bottom": 2.54,
    "left": 3.17,
    "right": 3.17,
}

DEFAULT_HEADER_DISTANCE_CM = 1.5
DEFAULT_FOOTER_DISTANCE_CM = 1.75
DEFAULT_GRADUATE_SCHOOL_NAME = "示例大学研究生院"
DEFAULT_DECLARATION_SCHOOL_NAME = "示例大学"
DEFAULT_SCHOOL_CODE = "[学校代码]"
ALLOWED_PAGE_NUMBER_FORMATS = {"decimal", "lowerRoman", "upperRoman", "lowerLetter", "upperLetter"}

DEFAULT_PAGE_NUMBERING = {
    "front_matter": {"format": "lowerRoman", "start": 1},
    "body": {"format": "decimal", "start": 1},
    "back_matter": {"format": "decimal", "start": None},
}

DEFAULT_STYLE_PROFILE = {
    "heading1": {
        "font_latin": "Times New Roman",
        "font_east_asia": "SimHei",
        "font_size_pt": 16.0,
        "bold": True,
        "alignment": "center",
        "line_spacing_rule": "exact",
        "line_spacing_pt": 20.0,
        "space_before_pt": 18.0,
        "space_after_pt": 12.0,
        "first_line_indent_cm": 0.0,
    },
    "heading2": {
        "font_latin": "Times New Roman",
        "font_east_asia": "SimSun",
        "font_size_pt": 14.0,
        "bold": False,
        "alignment": "left",
        "line_spacing_rule": "exact",
        "line_spacing_pt": 20.0,
        "space_before_pt": 10.0,
        "space_after_pt": 8.0,
        "first_line_indent_cm": 0.0,
    },
    "heading3": {
        "font_latin": "Times New Roman",
        "font_east_asia": "SimSun",
        "font_size_pt": 12.0,
        "bold": False,
        "alignment": "left",
        "line_spacing_rule": "exact",
        "line_spacing_pt": 20.0,
        "space_before_pt": 10.0,
        "space_after_pt": 8.0,
        "first_line_indent_cm": 0.0,
    },
    "body": {
        "font_latin": "Times New Roman",
        "font_east_asia": "SimSun",
        "font_size_pt": 12.0,
        "bold": False,
        "alignment": "justify",
        "line_spacing_rule": "exact",
        "line_spacing_pt": 20.0,
        "space_before_pt": 0.0,
        "space_after_pt": 0.0,
        "first_line_indent_cm": 0.74,
    },
    "figure_caption": {
        "font_latin": "Times New Roman",
        "font_east_asia": "KaiTi",
        "font_size_pt": 10.5,
        "bold": False,
        "alignment": "center",
        "line_spacing_rule": "single",
        "line_spacing_pt": None,
        "space_before_pt": 0.0,
        "space_after_pt": 12.0,
        "first_line_indent_cm": 0.0,
    },
    "table_caption": {
        "font_latin": "Times New Roman",
        "font_east_asia": "KaiTi",
        "font_size_pt": 10.5,
        "bold": False,
        "alignment": "center",
        "line_spacing_rule": "single",
        "line_spacing_pt": None,
        "space_before_pt": 12.0,
        "space_after_pt": 0.0,
        "first_line_indent_cm": 0.0,
    },
    "table_cell": {
        "font_latin": "Times New Roman",
        "font_east_asia": "SimSun",
        "font_size_pt": 10.5,
        "bold": False,
        "alignment": "center",
        "line_spacing_rule": "single",
        "line_spacing_pt": None,
        "space_before_pt": 0.0,
        "space_after_pt": 0.0,
        "first_line_indent_cm": 0.0,
        "header_bold": True,
    },
    "header": {
        "font_latin": "Times New Roman",
        "font_east_asia": "SimSun",
        "font_size_pt": 10.5,
        "bold": False,
    },
    "footer": {
        "font_latin": "Times New Roman",
        "font_east_asia": "SimSun",
        "font_size_pt": 9.0,
        "bold": False,
    },
    "front_matter": {
        "zh_abstract": {
            "title_text": "摘  要",
            "label_text": "摘要：",
            "keywords_label_text": "关键词：",
            "title": {
                "font_latin": "Times New Roman",
                "font_east_asia": "SimHei",
                "font_size_pt": 16.0,
                "bold": True,
                "alignment": "center",
                "line_spacing_rule": "single",
                "line_spacing_pt": None,
                "space_before_pt": 0.0,
                "space_after_pt": 0.0,
                "first_line_indent_cm": 0.0,
            },
            "label": {
                "font_latin": "Times New Roman",
                "font_east_asia": "SimHei",
                "font_size_pt": 14.0,
                "bold": True,
                "alignment": "left",
                "line_spacing_rule": "one_point_five",
                "line_spacing_pt": None,
                "space_before_pt": 0.0,
                "space_after_pt": 0.0,
                "first_line_indent_cm": 0.0,
            },
            "body": {
                "font_latin": "Times New Roman",
                "font_east_asia": "SimSun",
                "font_size_pt": 14.0,
                "bold": False,
                "alignment": "justify",
                "line_spacing_rule": "one_point_five",
                "line_spacing_pt": None,
                "space_before_pt": 0.0,
                "space_after_pt": 0.0,
                "first_line_indent_cm": 0.74,
            },
            "keywords_label": {
                "font_latin": "Times New Roman",
                "font_east_asia": "SimHei",
                "font_size_pt": 14.0,
                "bold": True,
                "alignment": "left",
                "line_spacing_rule": "one_point_five",
                "line_spacing_pt": None,
                "space_before_pt": 0.0,
                "space_after_pt": 0.0,
                "first_line_indent_cm": 0.0,
            },
            "keywords_body": {
                "font_latin": "Times New Roman",
                "font_east_asia": "SimSun",
                "font_size_pt": 14.0,
                "bold": False,
                "alignment": "left",
                "line_spacing_rule": "one_point_five",
                "line_spacing_pt": None,
                "space_before_pt": 0.0,
                "space_after_pt": 0.0,
                "first_line_indent_cm": 0.0,
            },
        },
        "en_abstract": {
            "title_text": "ABSTRACT",
            "label_text": "Abstract：",
            "keywords_label_text": "Keywords：",
            "title": {
                "font_latin": "Times New Roman",
                "font_east_asia": "Times New Roman",
                "font_size_pt": 16.0,
                "bold": True,
                "alignment": "center",
                "line_spacing_rule": "single",
                "line_spacing_pt": None,
                "space_before_pt": 0.0,
                "space_after_pt": 0.0,
                "first_line_indent_cm": 0.0,
            },
            "label": {
                "font_latin": "Times New Roman",
                "font_east_asia": "Times New Roman",
                "font_size_pt": 14.0,
                "bold": True,
                "alignment": "left",
                "line_spacing_rule": "one_point_five",
                "line_spacing_pt": None,
                "space_before_pt": 0.0,
                "space_after_pt": 0.0,
                "first_line_indent_cm": 0.0,
            },
            "body": {
                "font_latin": "Times New Roman",
                "font_east_asia": "Times New Roman",
                "font_size_pt": 14.0,
                "bold": False,
                "alignment": "justify",
                "line_spacing_rule": "one_point_five",
                "line_spacing_pt": None,
                "space_before_pt": 0.0,
                "space_after_pt": 0.0,
                "first_line_indent_cm": 0.74,
            },
            "keywords_label": {
                "font_latin": "Times New Roman",
                "font_east_asia": "Times New Roman",
                "font_size_pt": 14.0,
                "bold": True,
                "alignment": "left",
                "line_spacing_rule": "one_point_five",
                "line_spacing_pt": None,
                "space_before_pt": 0.0,
                "space_after_pt": 0.0,
                "first_line_indent_cm": 0.0,
            },
            "keywords_body": {
                "font_latin": "Times New Roman",
                "font_east_asia": "Times New Roman",
                "font_size_pt": 14.0,
                "bold": False,
                "alignment": "left",
                "line_spacing_rule": "one_point_five",
                "line_spacing_pt": None,
                "space_before_pt": 0.0,
                "space_after_pt": 0.0,
                "first_line_indent_cm": 0.0,
            },
        },
        "toc": {
            "title_text": "目  录",
            "title": {
                "font_latin": "Times New Roman",
                "font_east_asia": "SimHei",
                "font_size_pt": 16.0,
                "bold": True,
                "alignment": "center",
                "line_spacing_rule": "one_point_five",
                "line_spacing_pt": None,
                "space_before_pt": 0.0,
                "space_after_pt": 12.0,
                "first_line_indent_cm": 0.0,
            },
            "level1": {
                "font_latin": "Times New Roman",
                "font_east_asia": "SimHei",
                "font_size_pt": 12.0,
                "bold": False,
                "alignment": "left",
                "line_spacing_rule": "one_point_five",
                "line_spacing_pt": None,
                "space_before_pt": 0.0,
                "space_after_pt": 0.0,
                "first_line_indent_cm": 0.0,
            },
            "level2": {
                "font_latin": "Times New Roman",
                "font_east_asia": "SimSun",
                "font_size_pt": 12.0,
                "bold": False,
                "alignment": "left",
                "line_spacing_rule": "one_point_five",
                "line_spacing_pt": None,
                "space_before_pt": 0.0,
                "space_after_pt": 0.0,
                "first_line_indent_cm": 0.74,
            },
            "level3": {
                "font_latin": "Times New Roman",
                "font_east_asia": "SimSun",
                "font_size_pt": 12.0,
                "bold": False,
                "alignment": "left",
                "line_spacing_rule": "one_point_five",
                "line_spacing_pt": None,
                "space_before_pt": 0.0,
                "space_after_pt": 0.0,
                "first_line_indent_cm": 1.48,
            },
        },
        "abbreviation_table": {
            "title_text": "主要缩略语对照表",
            "empty_text": "暂无已注册缩略语",
            "title": {
                "font_latin": "Times New Roman",
                "font_east_asia": "SimHei",
                "font_size_pt": 16.0,
                "bold": True,
                "alignment": "center",
                "line_spacing_rule": "exact",
                "line_spacing_pt": 20.0,
                "space_before_pt": 18.0,
                "space_after_pt": 12.0,
                "first_line_indent_cm": 0.0,
            },
        },
    },
}

_ALIGNMENT_OPTIONS = {"left", "center", "right", "justify"}
_LINE_SPACING_RULE_OPTIONS = {"exact", "single", "one_point_five"}


DEFAULT_PROFILE = {
    "schema_version": "1.0",
    "language": "zh-CN",
    "targets": {
        "body_target_chars": None,  # derived from degree_type at load time: 硕士→30000, 博士→50000
        "abstract_min_chars": 1500,
        "abstract_max_chars": 2500,
        "review_in_scope": False,
        "review_target_chars": 0,
        "references_min_count": 80,
        # 按章软文献地板（warning，不阻断；总量 references_min_count 仍为硬门）。
        # None → load 时按 degree_type 填充：博 {intro_review:30, research:12}；硕地板更低。
        "per_chapter_ref_floor": None,
        "min_chapters": 5,
    },
    "chapter_targets": {},
    "structure": {
        "pattern": "intro + research_chapters + conclusion",
        "research_chapter_required_sections": [
            "引言",
            "材料与方法",
            "结果与讨论",
            "实验结论",
            "小结",
        ],
    },
    "rules": {
        "references_at_end": True,
        "atomic_md_required": True,
        "experiment_one_figure_or_table": True,
        "result_discussion_linked_to_methods": True,
        "self_check_after_chapter": True,
        "snapshot_after_section_summary": True,
        "humanizer_required": True,
    },
    "format_profile": DEFAULT_FORMAT_PROFILE,
}


def resolve_profile_path(project_root, profile_path=None):
    if profile_path:
        return profile_path if os.path.isabs(profile_path) else os.path.abspath(os.path.join(project_root, profile_path))
    return os.path.abspath(os.path.join(project_root, "thesis_profile.json"))


def deep_merge(base, override):
    if not isinstance(base, dict):
        return override
    if not isinstance(override, dict):
        return base
    merged = dict(base)
    for k, v in override.items():
        if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
            merged[k] = deep_merge(merged[k], v)
        else:
            merged[k] = v
    return merged


def _normalize_string_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if not isinstance(value, list):
        return []
    normalized = []
    for item in value:
        text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized


def _normalize_optional_float(value):
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _normalize_page_margins(raw_margins):
    raw_margins = raw_margins if isinstance(raw_margins, dict) else {}
    return {
        "top": _normalize_optional_float(raw_margins.get("top")),
        "bottom": _normalize_optional_float(raw_margins.get("bottom")),
        "left": _normalize_optional_float(raw_margins.get("left")),
        "right": _normalize_optional_float(raw_margins.get("right")),
    }


def _normalize_optional_int(value):
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_page_numbering(raw_page_numbering):
    raw_page_numbering = raw_page_numbering if isinstance(raw_page_numbering, dict) else {}
    normalized = {}
    for zone, default in DEFAULT_PAGE_NUMBERING.items():
        zone_raw = raw_page_numbering.get(zone) if isinstance(raw_page_numbering.get(zone), dict) else {}
        fmt = _normalize_text(zone_raw.get("format"), default["format"])
        if fmt not in ALLOWED_PAGE_NUMBER_FORMATS:
            fmt = default["format"]
        start = _normalize_optional_int(zone_raw.get("start"))
        if start is not None and start <= 0:
            start = default["start"]
        normalized[zone] = {
            "format": fmt,
            "start": start if "start" in zone_raw or zone_raw.get("start") is not None else default["start"],
        }
    return normalized


def _raise_validation_error(field_path, expected, actual):
    raise ValueError(f"{field_path}: expected {expected}, got {actual}")


def _validate_string_list_field(field_path, value):
    if value is None:
        return
    if isinstance(value, str):
        return
    if not isinstance(value, list):
        _raise_validation_error(field_path, "string or array of strings", type(value).__name__)
    for idx, item in enumerate(value):
        if not isinstance(item, str):
            _raise_validation_error(f"{field_path}[{idx}]", "string", type(item).__name__)


def _validate_positive_number(field_path, value, allow_zero=False):
    if value is None:
        return
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        _raise_validation_error(field_path, "number", type(value).__name__)
    if allow_zero:
        if value < 0:
            _raise_validation_error(field_path, "number >= 0", value)
    elif value <= 0:
        _raise_validation_error(field_path, "number > 0", value)


def _validate_style_entry(field_path, value):
    if not isinstance(value, dict):
        _raise_validation_error(field_path, "object", type(value).__name__)
    allowed_keys = {
        "font_latin",
        "font_east_asia",
        "font_size_pt",
        "bold",
        "alignment",
        "line_spacing_rule",
        "line_spacing_pt",
        "space_before_pt",
        "space_after_pt",
        "first_line_indent_cm",
    }
    unknown = set(value.keys()) - allowed_keys
    if unknown:
        _raise_validation_error(f"{field_path}.{sorted(unknown)[0]}", f"one of {sorted(allowed_keys)}", "unknown field")
    for key in ("font_latin", "font_east_asia", "alignment", "line_spacing_rule"):
        if key in value and not isinstance(value[key], str):
            _raise_validation_error(f"{field_path}.{key}", "string", type(value[key]).__name__)
    if "bold" in value and not isinstance(value["bold"], bool):
        _raise_validation_error(f"{field_path}.bold", "boolean", type(value["bold"]).__name__)
    for key in ("font_size_pt", "line_spacing_pt", "space_before_pt", "space_after_pt", "first_line_indent_cm"):
        if key in value:
            _validate_positive_number(f"{field_path}.{key}", value[key], allow_zero=True)


def _validate_style_profile_patch(style_profile):
    if not isinstance(style_profile, dict):
        _raise_validation_error("format_profile.style_profile", "object", type(style_profile).__name__)
    allowed_top_keys = {
        "heading1",
        "heading2",
        "heading3",
        "body",
        "figure_caption",
        "table_caption",
        "table_cell",
        "header",
        "footer",
        "front_matter",
    }
    unknown = set(style_profile.keys()) - allowed_top_keys
    if unknown:
        _raise_validation_error(
            f"format_profile.style_profile.{sorted(unknown)[0]}",
            f"one of {sorted(allowed_top_keys)}",
            "unknown field",
        )
    for key in ("heading1", "heading2", "heading3", "body", "figure_caption", "table_caption", "header", "footer"):
        if key in style_profile:
            _validate_style_entry(f"format_profile.style_profile.{key}", style_profile[key])
    if "table_cell" in style_profile:
        _validate_style_entry("format_profile.style_profile.table_cell", style_profile["table_cell"])
        header_bold = style_profile["table_cell"].get("header_bold")
        if header_bold is not None and not isinstance(header_bold, bool):
            _raise_validation_error("format_profile.style_profile.table_cell.header_bold", "boolean", type(header_bold).__name__)
    if "front_matter" in style_profile:
        front_matter = style_profile["front_matter"]
        if not isinstance(front_matter, dict):
            _raise_validation_error("format_profile.style_profile.front_matter", "object", type(front_matter).__name__)
        allowed_sections = {"zh_abstract", "en_abstract", "toc", "abbreviation_table"}
        unknown = set(front_matter.keys()) - allowed_sections
        if unknown:
            _raise_validation_error(
                f"format_profile.style_profile.front_matter.{sorted(unknown)[0]}",
                f"one of {sorted(allowed_sections)}",
                "unknown field",
            )
        for section in ("zh_abstract", "en_abstract"):
            if section in front_matter:
                section_value = front_matter[section]
                if not isinstance(section_value, dict):
                    _raise_validation_error(
                        f"format_profile.style_profile.front_matter.{section}",
                        "object",
                        type(section_value).__name__,
                    )
                allowed_keys = {"title_text", "label_text", "keywords_label_text", "title", "label", "body", "keywords_label", "keywords_body"}
                unknown = set(section_value.keys()) - allowed_keys
                if unknown:
                    _raise_validation_error(
                        f"format_profile.style_profile.front_matter.{section}.{sorted(unknown)[0]}",
                        f"one of {sorted(allowed_keys)}",
                        "unknown field",
                    )
                for text_key in ("title_text", "label_text", "keywords_label_text"):
                    if text_key in section_value and not isinstance(section_value[text_key], str):
                        _raise_validation_error(
                            f"format_profile.style_profile.front_matter.{section}.{text_key}",
                            "string",
                            type(section_value[text_key]).__name__,
                        )
                for style_key in ("title", "label", "body", "keywords_label", "keywords_body"):
                    if style_key in section_value:
                        _validate_style_entry(
                            f"format_profile.style_profile.front_matter.{section}.{style_key}",
                            section_value[style_key],
                        )
        if "toc" in front_matter:
            toc_value = front_matter["toc"]
            if not isinstance(toc_value, dict):
                _raise_validation_error("format_profile.style_profile.front_matter.toc", "object", type(toc_value).__name__)
            allowed_keys = {"title_text", "title", "level1", "level2", "level3"}
            unknown = set(toc_value.keys()) - allowed_keys
            if unknown:
                _raise_validation_error(
                    f"format_profile.style_profile.front_matter.toc.{sorted(unknown)[0]}",
                    f"one of {sorted(allowed_keys)}",
                    "unknown field",
                )
            if "title_text" in toc_value and not isinstance(toc_value["title_text"], str):
                _raise_validation_error("format_profile.style_profile.front_matter.toc.title_text", "string", type(toc_value["title_text"]).__name__)
            for style_key in ("title", "level1", "level2", "level3"):
                if style_key in toc_value:
                    _validate_style_entry(f"format_profile.style_profile.front_matter.toc.{style_key}", toc_value[style_key])
        if "abbreviation_table" in front_matter:
            abbr_value = front_matter["abbreviation_table"]
            if not isinstance(abbr_value, dict):
                _raise_validation_error("format_profile.style_profile.front_matter.abbreviation_table", "object", type(abbr_value).__name__)
            allowed_keys = {"title_text", "empty_text", "title"}
            unknown = set(abbr_value.keys()) - allowed_keys
            if unknown:
                _raise_validation_error(
                    f"format_profile.style_profile.front_matter.abbreviation_table.{sorted(unknown)[0]}",
                    f"one of {sorted(allowed_keys)}",
                    "unknown field",
                )
            for text_key in ("title_text", "empty_text"):
                if text_key in abbr_value and not isinstance(abbr_value[text_key], str):
                    _raise_validation_error(
                        f"format_profile.style_profile.front_matter.abbreviation_table.{text_key}",
                        "string",
                        type(abbr_value[text_key]).__name__,
                    )
            if "title" in abbr_value:
                _validate_style_entry("format_profile.style_profile.front_matter.abbreviation_table.title", abbr_value["title"])


def validate_format_profile_patch(format_profile):
    if not isinstance(format_profile, dict):
        _raise_validation_error("format_profile", "object", type(format_profile).__name__)
    allowed_keys = {
        "mode",
        "status",
        "university_name",
        "degree_type",
        "source_template_files",
        "requirements_summary",
        "missing_requirements",
        "allow_docx_generation",
        "page_margins_cm",
        "header_distance_cm",
        "footer_distance_cm",
        "graduate_school_name",
        "declaration_authorization_school_name",
        "school_code",
        "header_left_text",
        "style_profile",
        "page_numbering",
        "exclude_from_body_count",
    }
    unknown = set(format_profile.keys()) - allowed_keys
    if unknown:
        _raise_validation_error(f"format_profile.{sorted(unknown)[0]}", f"one of {sorted(allowed_keys)}", "unknown field")
    if "mode" in format_profile and format_profile["mode"] not in {"default_generic", "custom"}:
        _raise_validation_error("format_profile.mode", "'default_generic' or 'custom'", format_profile["mode"])
    if "status" in format_profile and format_profile["status"] not in {"ready", "pending_template"}:
        _raise_validation_error("format_profile.status", "'ready' or 'pending_template'", format_profile["status"])
    for key in (
        "university_name",
        "degree_type",
        "graduate_school_name",
        "declaration_authorization_school_name",
        "school_code",
        "header_left_text",
    ):
        if key in format_profile and not isinstance(format_profile[key], str):
            _raise_validation_error(f"format_profile.{key}", "string", type(format_profile[key]).__name__)
    if "degree_type" in format_profile and isinstance(format_profile["degree_type"], str):
        dt = format_profile["degree_type"]
        _valid_degree = (
            "博士" in dt or "硕士" in dt
            or "doctoral" in dt.lower() or "master" in dt.lower()
        )
        if not _valid_degree:
            _raise_validation_error(
                "format_profile.degree_type",
                "含'博士'/'硕士'(或 doctoral/master) 的字符串",
                repr(dt),
            )
    if "exclude_from_body_count" in format_profile:
        _validate_string_list_field("format_profile.exclude_from_body_count", format_profile["exclude_from_body_count"])
    for key in ("source_template_files", "requirements_summary", "missing_requirements"):
        if key in format_profile:
            _validate_string_list_field(f"format_profile.{key}", format_profile[key])
    if "allow_docx_generation" in format_profile and not isinstance(format_profile["allow_docx_generation"], bool):
        _raise_validation_error("format_profile.allow_docx_generation", "boolean", type(format_profile["allow_docx_generation"]).__name__)
    if "page_margins_cm" in format_profile:
        margins = format_profile["page_margins_cm"]
        if not isinstance(margins, dict):
            _raise_validation_error("format_profile.page_margins_cm", "object", type(margins).__name__)
        unknown = set(margins.keys()) - {"top", "bottom", "left", "right"}
        if unknown:
            _raise_validation_error("format_profile.page_margins_cm", "top/bottom/left/right keys only", f"unknown field {sorted(unknown)[0]}")
        for key, value in margins.items():
            _validate_positive_number(f"format_profile.page_margins_cm.{key}", value)
    for key in ("header_distance_cm", "footer_distance_cm"):
        if key in format_profile:
            _validate_positive_number(f"format_profile.{key}", format_profile[key])
    if "style_profile" in format_profile:
        _validate_style_profile_patch(format_profile["style_profile"])
    if "page_numbering" in format_profile:
        page_numbering = format_profile["page_numbering"]
        if not isinstance(page_numbering, dict):
            _raise_validation_error("format_profile.page_numbering", "object", type(page_numbering).__name__)
        unknown = set(page_numbering.keys()) - {"front_matter", "body", "back_matter"}
        if unknown:
            _raise_validation_error("format_profile.page_numbering", "front_matter/body/back_matter keys only", f"unknown field {sorted(unknown)[0]}")
        for zone, zone_value in page_numbering.items():
            if not isinstance(zone_value, dict):
                _raise_validation_error(f"format_profile.page_numbering.{zone}", "object", type(zone_value).__name__)
            unknown = set(zone_value.keys()) - {"format", "start"}
            if unknown:
                _raise_validation_error(
                    f"format_profile.page_numbering.{zone}",
                    "'format' and 'start' keys only",
                    f"unknown field {sorted(unknown)[0]}",
                )
            if "format" in zone_value and zone_value["format"] not in ALLOWED_PAGE_NUMBER_FORMATS:
                _raise_validation_error(
                    f"format_profile.page_numbering.{zone}.format",
                    f"one of {sorted(ALLOWED_PAGE_NUMBER_FORMATS)}",
                    zone_value["format"],
                )
            if "start" in zone_value:
                start = zone_value["start"]
                if start is not None and (not isinstance(start, int) or isinstance(start, bool) or start <= 0):
                    _raise_validation_error(f"format_profile.page_numbering.{zone}.start", "positive integer or null", start)


def validate_project_info_patch(project_info):
    if not isinstance(project_info, dict):
        _raise_validation_error("project_info", "object", type(project_info).__name__)
    allowed_keys = {
        "title",
        "title_en",
        "author",
        "student_id",
        "supervisor",
        "co_supervisor",
        "major",
        "research_direction",
        "department",
        "classification",
        "udc",
        "abstract_zh",
        "keywords_zh",
        "abstract_en",
        "keywords_en",
        "save_path",
        "source_paper",
    }
    unknown = set(project_info.keys()) - allowed_keys
    if unknown:
        _raise_validation_error(f"project_info.{sorted(unknown)[0]}", f"one of {sorted(allowed_keys)}", "unknown field")
    for key in allowed_keys - {"keywords_zh", "keywords_en"}:
        if key in project_info and not isinstance(project_info[key], str):
            _raise_validation_error(f"project_info.{key}", "string", type(project_info[key]).__name__)
    for key in ("keywords_zh", "keywords_en"):
        if key in project_info:
            _validate_string_list_field(f"project_info.{key}", project_info[key])


def _normalize_text(value, default=""):
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _normalize_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y", "on"}:
            return True
        if lowered in {"false", "0", "no", "n", "off"}:
            return False
    return bool(value)


def _normalize_alignment(value, default):
    text = _normalize_text(value, default).lower()
    return text if text in _ALIGNMENT_OPTIONS else default


def _normalize_line_spacing_rule(value, default):
    text = _normalize_text(value, default).lower()
    return text if text in _LINE_SPACING_RULE_OPTIONS else default


def _normalize_style_entry(raw_style, default_style):
    raw_style = raw_style if isinstance(raw_style, dict) else {}
    default_style = default_style if isinstance(default_style, dict) else {}
    merged_style = deep_merge(default_style, raw_style)
    return {
        "font_latin": _normalize_text(merged_style.get("font_latin"), default_style.get("font_latin", "Times New Roman")),
        "font_east_asia": _normalize_text(merged_style.get("font_east_asia"), default_style.get("font_east_asia", "SimSun")),
        "font_size_pt": _normalize_optional_float(merged_style.get("font_size_pt")),
        "bold": _normalize_bool(merged_style.get("bold"), default_style.get("bold", False)),
        "alignment": _normalize_alignment(merged_style.get("alignment"), default_style.get("alignment", "left")),
        "line_spacing_rule": _normalize_line_spacing_rule(
            merged_style.get("line_spacing_rule"),
            default_style.get("line_spacing_rule", "single"),
        ),
        "line_spacing_pt": _normalize_optional_float(merged_style.get("line_spacing_pt")),
        "space_before_pt": _normalize_optional_float(merged_style.get("space_before_pt")),
        "space_after_pt": _normalize_optional_float(merged_style.get("space_after_pt")),
        "first_line_indent_cm": _normalize_optional_float(merged_style.get("first_line_indent_cm")),
    }


def normalize_style_profile(raw_style_profile=None):
    raw_style_profile = raw_style_profile if isinstance(raw_style_profile, dict) else {}
    merged = deep_merge(DEFAULT_STYLE_PROFILE, raw_style_profile)
    front_matter = merged.get("front_matter") if isinstance(merged.get("front_matter"), dict) else {}
    default_front_matter = DEFAULT_STYLE_PROFILE["front_matter"]
    normalized_front_matter = {}

    for section_key in ("zh_abstract", "en_abstract"):
        section_raw = front_matter.get(section_key) if isinstance(front_matter.get(section_key), dict) else {}
        section_default = default_front_matter[section_key]
        normalized_front_matter[section_key] = {
            "title_text": _normalize_text(section_raw.get("title_text"), section_default["title_text"]),
            "label_text": _normalize_text(section_raw.get("label_text"), section_default["label_text"]),
            "keywords_label_text": _normalize_text(
                section_raw.get("keywords_label_text"),
                section_default["keywords_label_text"],
            ),
            "title": _normalize_style_entry(section_raw.get("title"), section_default["title"]),
            "label": _normalize_style_entry(section_raw.get("label"), section_default["label"]),
            "body": _normalize_style_entry(section_raw.get("body"), section_default["body"]),
            "keywords_label": _normalize_style_entry(
                section_raw.get("keywords_label"),
                section_default["keywords_label"],
            ),
            "keywords_body": _normalize_style_entry(
                section_raw.get("keywords_body"),
                section_default["keywords_body"],
            ),
        }

    toc_raw = front_matter.get("toc") if isinstance(front_matter.get("toc"), dict) else {}
    toc_default = default_front_matter["toc"]
    normalized_front_matter["toc"] = {
        "title_text": _normalize_text(toc_raw.get("title_text"), toc_default["title_text"]),
        "title": _normalize_style_entry(toc_raw.get("title"), toc_default["title"]),
        "level1": _normalize_style_entry(toc_raw.get("level1"), toc_default["level1"]),
        "level2": _normalize_style_entry(toc_raw.get("level2"), toc_default["level2"]),
        "level3": _normalize_style_entry(toc_raw.get("level3"), toc_default["level3"]),
    }

    abbr_raw = front_matter.get("abbreviation_table") if isinstance(front_matter.get("abbreviation_table"), dict) else {}
    abbr_default = default_front_matter["abbreviation_table"]
    normalized_front_matter["abbreviation_table"] = {
        "title_text": _normalize_text(abbr_raw.get("title_text"), abbr_default["title_text"]),
        "empty_text": _normalize_text(abbr_raw.get("empty_text"), abbr_default["empty_text"]),
        "title": _normalize_style_entry(abbr_raw.get("title"), abbr_default["title"]),
    }

    table_cell_raw = merged.get("table_cell") if isinstance(merged.get("table_cell"), dict) else {}
    table_cell_default = DEFAULT_STYLE_PROFILE["table_cell"]
    table_cell = _normalize_style_entry(table_cell_raw, table_cell_default)
    table_cell["header_bold"] = _normalize_bool(table_cell_raw.get("header_bold"), table_cell_default.get("header_bold", True))

    return {
        "heading1": _normalize_style_entry(merged.get("heading1"), DEFAULT_STYLE_PROFILE["heading1"]),
        "heading2": _normalize_style_entry(merged.get("heading2"), DEFAULT_STYLE_PROFILE["heading2"]),
        "heading3": _normalize_style_entry(merged.get("heading3"), DEFAULT_STYLE_PROFILE["heading3"]),
        "body": _normalize_style_entry(merged.get("body"), DEFAULT_STYLE_PROFILE["body"]),
        "figure_caption": _normalize_style_entry(
            merged.get("figure_caption"),
            DEFAULT_STYLE_PROFILE["figure_caption"],
        ),
        "table_caption": _normalize_style_entry(
            merged.get("table_caption"),
            DEFAULT_STYLE_PROFILE["table_caption"],
        ),
        "table_cell": table_cell,
        "header": _normalize_style_entry(merged.get("header"), DEFAULT_STYLE_PROFILE["header"]),
        "footer": _normalize_style_entry(merged.get("footer"), DEFAULT_STYLE_PROFILE["footer"]),
        "front_matter": normalized_front_matter,
    }


# custom 模式版式必填项：正文 + 各级标题的字体/字号/行距，缺任一即不放行。
# 只查 raw（用户实际填写值），不查 normalize 后的 default 填充值——否则等于"自己校自己"。
_REQUIRED_STYLE_KEYS = ("body", "heading1", "heading2", "heading3")


def _custom_style_profile_missing(raw_style_profile):
    """custom 模式下检查用户是否给全了正文/各级标题的字体、字号、行距。

    返回 True 表示缺失（需拦在 pending_template）。
    """
    if not isinstance(raw_style_profile, dict):
        return True
    for key in _REQUIRED_STYLE_KEYS:
        entry = raw_style_profile.get(key)
        if not isinstance(entry, dict):
            return True
        # 字体（中文字形）
        if not str(entry.get("font_east_asia", "")).strip():
            return True
        # 字号
        try:
            if entry.get("font_size_pt") is None or float(entry["font_size_pt"]) <= 0:
                return True
        except (TypeError, ValueError):
            return True
        # 行距：规则或磅值至少给一项
        has_rule = bool(str(entry.get("line_spacing_rule", "")).strip())
        has_pt = entry.get("line_spacing_pt") is not None
        if not (has_rule or has_pt):
            return True
    return False


def normalize_format_profile(raw_profile=None):
    raw_profile = raw_profile if isinstance(raw_profile, dict) else {}
    merged = deep_merge(DEFAULT_FORMAT_PROFILE, raw_profile)
    explicit_allow_docx_generation = raw_profile.get("allow_docx_generation") if "allow_docx_generation" in raw_profile else None

    mode = str(merged.get("mode", "default_generic")).strip() or "default_generic"
    if mode not in {"default_generic", "custom"}:
        mode = "default_generic"

    status = str(merged.get("status", "ready")).strip() or "ready"
    if status not in {"ready", "pending_template"}:
        status = "ready"

    source_template_files = _normalize_string_list(merged.get("source_template_files"))
    requirements_summary = _normalize_string_list(merged.get("requirements_summary"))
    missing_requirements = _normalize_string_list(merged.get("missing_requirements"))

    university_name = str(merged.get("university_name", "")).strip()
    if mode == "default_generic" and not university_name:
        university_name = "示例大学"

    degree_type = str(merged.get("degree_type", "")).strip()
    if mode == "default_generic" and not degree_type:
        degree_type = "博士学位论文"

    page_margins_cm = _normalize_page_margins(raw_profile.get("page_margins_cm"))
    header_distance_cm = _normalize_optional_float(raw_profile.get("header_distance_cm"))
    footer_distance_cm = _normalize_optional_float(raw_profile.get("footer_distance_cm"))
    graduate_school_name = str(raw_profile.get("graduate_school_name", "")).strip()
    declaration_authorization_school_name = str(raw_profile.get("declaration_authorization_school_name", "")).strip()
    school_code = str(raw_profile.get("school_code", "")).strip()
    header_left_text = str(raw_profile.get("header_left_text", "")).strip()
    style_profile = normalize_style_profile(raw_profile.get("style_profile"))
    page_numbering = _normalize_page_numbering(raw_profile.get("page_numbering"))

    if mode == "default_generic":
        status = "ready"
        missing_requirements = []
        allow_docx_generation = True
        page_margins_cm = dict(DEFAULT_PAGE_MARGINS_CM)
        header_distance_cm = DEFAULT_HEADER_DISTANCE_CM
        footer_distance_cm = DEFAULT_FOOTER_DISTANCE_CM
        graduate_school_name = DEFAULT_GRADUATE_SCHOOL_NAME
        declaration_authorization_school_name = DEFAULT_DECLARATION_SCHOOL_NAME
        school_code = DEFAULT_SCHOOL_CODE
        header_left_text = f"{university_name}{degree_type}"
    else:
        # 每次 normalize 从当前字段实际值重算 missing，不累加旧条目
        missing_requirements = []
        if not university_name:
            missing_requirements.append("院校名称")
        if not degree_type:
            missing_requirements.append("学位类型")
        if not source_template_files and not requirements_summary:
            missing_requirements.append("格式模板或详细格式要求")
        if any(page_margins_cm[key] is None for key in ("top", "bottom", "left", "right")):
            missing_requirements.append("页边距规范")
        if header_distance_cm is None or footer_distance_cm is None:
            missing_requirements.append("页眉页脚距离规范")
        if _custom_style_profile_missing(raw_profile.get("style_profile")):
            missing_requirements.append("正文与各级标题版式规范（字体/字号/行距）")
        # status 由字段是否齐全决定，不继承旧值
        if missing_requirements:
            status = "pending_template"
        else:
            status = "ready"
        # allow_docx 同样由 status 决定；explicit_allow_docx_generation 仅用于在 ready 状态下
        # 用户主动禁止生成（None 表示未显式设置，False 若由 pending→ready 变化前写入则忽略）
        if explicit_allow_docx_generation is None or status == "ready":
            allow_docx_generation = status == "ready"
        else:
            allow_docx_generation = False
        if not graduate_school_name and university_name:
            graduate_school_name = f"{university_name}研究生院"
        if not declaration_authorization_school_name and university_name:
            declaration_authorization_school_name = university_name
        if not header_left_text and university_name and degree_type:
            header_left_text = f"{university_name}{degree_type}"
        if not school_code:
            school_code = DEFAULT_SCHOOL_CODE

    return {
        "mode": mode,
        "status": status,
        "university_name": university_name,
        "degree_type": degree_type,
        "source_template_files": source_template_files,
        "requirements_summary": requirements_summary,
        "missing_requirements": missing_requirements,
        "allow_docx_generation": allow_docx_generation,
        "page_margins_cm": page_margins_cm,
        "header_distance_cm": header_distance_cm,
        "footer_distance_cm": footer_distance_cm,
        "graduate_school_name": graduate_school_name,
        "declaration_authorization_school_name": declaration_authorization_school_name,
        "school_code": school_code,
        "header_left_text": header_left_text,
        "style_profile": style_profile,
        "page_numbering": page_numbering,
    }


def build_format_render_context(raw_format_profile=None):
    format_profile = normalize_format_profile(raw_format_profile)
    page_margins = format_profile.get("page_margins_cm") or {}
    university_name = format_profile.get("university_name") or "示例大学"
    degree_type = format_profile.get("degree_type") or "博士学位论文"

    return {
        "mode": format_profile.get("mode"),
        "status": format_profile.get("status"),
        "university_name": university_name,
        "degree_type": degree_type,
        "page_margins_cm": {
            "top": page_margins.get("top") if page_margins.get("top") is not None else DEFAULT_PAGE_MARGINS_CM["top"],
            "bottom": page_margins.get("bottom") if page_margins.get("bottom") is not None else DEFAULT_PAGE_MARGINS_CM["bottom"],
            "left": page_margins.get("left") if page_margins.get("left") is not None else DEFAULT_PAGE_MARGINS_CM["left"],
            "right": page_margins.get("right") if page_margins.get("right") is not None else DEFAULT_PAGE_MARGINS_CM["right"],
        },
        "header_distance_cm": (
            format_profile.get("header_distance_cm")
            if format_profile.get("header_distance_cm") is not None
            else DEFAULT_HEADER_DISTANCE_CM
        ),
        "footer_distance_cm": (
            format_profile.get("footer_distance_cm")
            if format_profile.get("footer_distance_cm") is not None
            else DEFAULT_FOOTER_DISTANCE_CM
        ),
        "graduate_school_name": format_profile.get("graduate_school_name") or DEFAULT_GRADUATE_SCHOOL_NAME,
        "declaration_authorization_school_name": (
            format_profile.get("declaration_authorization_school_name") or university_name
        ),
        "school_code": format_profile.get("school_code") or DEFAULT_SCHOOL_CODE,
        "header_left_text": format_profile.get("header_left_text") or f"{university_name}{degree_type}",
        "style_profile": normalize_style_profile(format_profile.get("style_profile")),
        "page_numbering": _normalize_page_numbering(format_profile.get("page_numbering")),
    }


def ensure_format_profile(profile):
    if not isinstance(profile, dict):
        profile = {}
    profile["format_profile"] = normalize_format_profile(profile.get("format_profile"))
    return profile


def _derive_body_target(profile):
    """
    当 body_target_chars 为 None（未显式设置）时，按 degree_type 填充默认值：
    硕士 → 30000，其他（博士）→ 50000。
    """
    targets = profile.setdefault("targets", {})
    if targets.get("body_target_chars") is None:
        degree = str(profile.get("format_profile", {}).get("degree_type", "")).strip()
        if "硕士" in degree or "master" in degree.lower():
            targets["body_target_chars"] = 30000
        else:
            targets["body_target_chars"] = 50000
    return profile


def _derive_per_chapter_ref_floor(profile):
    """按章软文献地板：per_chapter_ref_floor 为 None 时按 degree_type 填充默认值。
    博 {intro_review:30, research:12}；硕地板更低 {intro_review:20, research:8}。"""
    targets = profile.setdefault("targets", {})
    if targets.get("per_chapter_ref_floor") is None:
        degree = str(profile.get("format_profile", {}).get("degree_type", "")).strip()
        if "硕士" in degree or "master" in degree.lower():
            targets["per_chapter_ref_floor"] = {"intro_review": 20, "research": 8}
        else:
            targets["per_chapter_ref_floor"] = {"intro_review": 30, "research": 12}
    return profile


def load_profile(project_root, profile_path=None):
    path = resolve_profile_path(project_root, profile_path)
    if not os.path.exists(path):
        return _derive_per_chapter_ref_floor(_derive_body_target(ensure_format_profile(deep_merge(DEFAULT_PROFILE, {})))), path
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return _derive_per_chapter_ref_floor(_derive_body_target(ensure_format_profile(deep_merge(DEFAULT_PROFILE, payload)))), path


def save_profile(path, profile):
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_profile_", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def parse_chapter_target_spec(spec):
    """
    Parse '2:12000' -> ('2', 12000).
    """
    if ":" not in spec:
        raise ValueError("chapter target must use '<chapter>:<chars>' format")
    chapter, value = spec.split(":", 1)
    chapter = str(chapter).strip()
    chars = int(value)
    if chars <= 0:
        raise ValueError("chapter target chars must be positive")
    return chapter, chars
