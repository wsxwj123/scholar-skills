#!/usr/bin/env python3
"""
研究方向配置管理器

功能：
- 加载/保存研究方向配置
- 配置验证
- 默认配置管理
- 用户自定义配置支持
"""

import sys as _sys
try:  # Windows GBK 控制台/管道捕获下 emoji print 防 UnicodeEncodeError
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import jsonschema
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False


class FieldConfigManager:
    """研究方向配置管理器"""

    DEFAULT_FIELD = "default"
    SKILL_CONFIGS_DIR = Path(__file__).parent.parent / "configs"

    def __init__(self, project_config_dir: Optional[Path] = None, user_config_dir: Optional[Path] = None):
        self.project_config_dir = project_config_dir
        self.user_config_dir = user_config_dir or Path.home() / ".general-sci-writing" / "configs"
        self.legacy_user_config_dir = Path.home() / ".article-writing" / "configs"
        self._configs: Dict[str, dict] = {}
        self._current_field = self.DEFAULT_FIELD

    def _get_search_paths(self) -> List[Path]:
        """获取配置搜索路径列表"""
        paths = []
        if self.project_config_dir and self.project_config_dir.exists():
            paths.append(self.project_config_dir)
        if self.user_config_dir and self.user_config_dir.exists():
            paths.append(self.user_config_dir)
        if self.legacy_user_config_dir and self.legacy_user_config_dir.exists():
            paths.append(self.legacy_user_config_dir)
        if self.SKILL_CONFIGS_DIR.exists():
            paths.append(self.SKILL_CONFIGS_DIR)
        return paths

    def load_config(self, field_id: str) -> dict:
        """加载指定研究方向的配置"""
        if field_id in self._configs:
            return self._configs[field_id]

        config = None
        for search_path in self._get_search_paths():
            config_path = search_path / f"{field_id}.json"
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                break

        if config is None:
            raise FileNotFoundError(f"配置文件不存在: {field_id}")

        self._configs[field_id] = config
        return config

    def get_current_config(self) -> dict:
        """获取当前激活的配置"""
        if not self._current_field:
            self._current_field = self.DEFAULT_FIELD
        return self.load_config(self._current_field)

    def set_current_field(self, field_id: str) -> bool:
        """设置当前研究方向"""
        try:
            config = self.load_config(field_id)
            self._current_field = field_id
            return True
        except FileNotFoundError:
            return False

    def get_current_field(self) -> str:
        """获取当前研究方向ID"""
        return self._current_field or self.DEFAULT_FIELD

    def list_available_fields(self) -> List[Dict[str, str]]:
        """列出所有可用的研究方向"""
        fields = []
        seen_ids = set()

        for search_path in self._get_search_paths():
            if not search_path.exists():
                continue
            for config_file in search_path.glob("*.json"):
                if config_file.name.startswith("_"):
                    continue
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    if "field_id" not in config:
                        continue
                    field_id = config["field_id"]
                    if field_id not in seen_ids:
                        seen_ids.add(field_id)
                        fields.append({
                            "id": field_id,
                            "name": config.get("field_name", field_id),
                            "name_en": config.get("field_name_en", ""),
                            "source": str(search_path.name)
                        })
                except (json.JSONDecodeError, IOError):
                    continue

        return fields

    def validate_config(self, config: dict) -> Tuple[bool, List[str]]:
        """验证配置是否符合 Schema"""
        errors = []
        required = ["field_id", "field_name", "reviewer_concerns", "experiment_types"]

        for field in required:
            if field not in config:
                errors.append(f"缺少必需字段: {field}")

        if JSONSCHEMA_AVAILABLE:
            schema_path = self.SKILL_CONFIGS_DIR / "_schema.json"
            if schema_path.exists():
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schema = json.load(f)
                try:
                    jsonschema.validate(config, schema)
                except jsonschema.ValidationError as e:
                    errors.append(f"Schema验证失败: {e.message}")

        return len(errors) == 0, errors

    def create_config_from_template(self, field_id: str, field_name: str, output_dir: Optional[Path] = None) -> Path:
        """从模板创建新配置"""
        template = {
            "field_id": field_id,
            "field_name": field_name,
            "field_name_en": field_id.replace("_", " ").title(),
            "target_journals": [],
            "reviewer_concerns": {
                "by_system": {},
                "by_experiment": {},
                "mitigation_strategies": {}
            },
            "experiment_types": ["Characterization", "Experimental"],
            "literature_search_examples": {
                "gap_statement": "当前研究领域的局限性...",
                "innovation_claim": "本研究的创新点...",
                "methodology": "方法学描述..."
            },
            "default_figure_requirements": {
                "require_n_value": True,
                "require_scale_bar": False,
                "require_statistical_test": True
            },
            "word_limits": {
                "abstract": 250,
                "introduction": [800, 1500],
                "methods": [1000, 3000],
                "results": [2000, 4000],
                "discussion": [1500, 3000],
                "conclusion": [200, 500]
            }
        }

        output_dir = output_dir or self.user_config_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{field_id}.json"

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(template, f, ensure_ascii=False, indent=2)

        return output_path

    def export_config(self, field_id: str, output_path: Path) -> bool:
        """导出配置到指定路径"""
        try:
            config = self.load_config(field_id)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False


def get_manager(project_config_dir: Optional[Path] = None) -> FieldConfigManager:
    """获取配置管理器实例"""
    return FieldConfigManager(project_config_dir=project_config_dir)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="研究方向配置管理器")
    parser.add_argument("action", choices=["list", "load", "create", "validate", "export"],
                       help="操作类型")
    parser.add_argument("--field", help="研究方向ID")
    parser.add_argument("--name", help="研究方向名称（创建时使用）")
    parser.add_argument("--project-dir", type=Path, help="项目配置目录路径")
    parser.add_argument("--output", type=Path, help="输出路径（导出时使用）")

    args = parser.parse_args()
    manager = FieldConfigManager(project_config_dir=args.project_dir)

    if args.action == "list":
        fields = manager.list_available_fields()
        print("可用研究方向:")
        for f in fields:
            print(f"  - {f['id']}: {f['name']} ({f.get('source', 'unknown')})")

    elif args.action == "load" and args.field:
        try:
            config = manager.load_config(args.field)
            print(json.dumps(config, ensure_ascii=False, indent=2))
        except FileNotFoundError as e:
            print(f"错误: {e}")
            exit(1)

    elif args.action == "create" and args.field and args.name:
        path = manager.create_config_from_template(args.field, args.name)
        print(f"已创建配置文件: {path}")

    elif args.action == "validate" and args.field:
        try:
            config = manager.load_config(args.field)
            valid, errors = manager.validate_config(config)
            if valid:
                print("✓ 配置验证通过")
            else:
                print("✗ 配置验证失败:")
                for e in errors:
                    print(f"  - {e}")
        except FileNotFoundError as e:
            print(f"错误: {e}")
            exit(1)

    elif args.action == "export" and args.field and args.output:
        if manager.export_config(args.field, args.output):
            print(f"已导出配置文件: {args.output}")
        else:
            print("导出失败")
            exit(1)
