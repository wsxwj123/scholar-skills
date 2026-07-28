#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from common import discover_global_skill, global_skill_install_paths


DEFAULT_BACKUP_REPO = ""  # 配置为你自己的技能备份仓库 git URL；留空则跳过自动安装


def clone_skill_subdir(repo_url: str, skill_name: str, destination_root: Path) -> Path:
    subprocess.run(
        ["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", repo_url, str(destination_root)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "-C", str(destination_root), "sparse-checkout", "set", skill_name],
        check=True,
        capture_output=True,
        text=True,
    )
    skill_dir = destination_root / skill_name
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        raise FileNotFoundError(f"Missing SKILL.md in cloned skill directory: {skill_dir}")
    return skill_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure a global skill exists in Codex/OpenCode skill roots")
    parser.add_argument("--skill-name", required=True)
    parser.add_argument("--install-if-missing", action="store_true")
    parser.add_argument("--repo-url", default=DEFAULT_BACKUP_REPO)
    parser.add_argument("--target", choices=("codex", "opencode", "both"), default="both")
    args = parser.parse_args()

    existing = [str(path) for path in discover_global_skill(args.skill_name)]
    missing_targets = []
    for candidate in global_skill_install_paths(args.skill_name):
        cand_norm = str(candidate).replace("\\", "/")  # Windows 反斜杠归一为正斜杠,避免 ".config/opencode" 子串匹配失效
        if args.target == "codex" and ".codex" not in cand_norm:
            continue
        if args.target == "opencode" and ".config/opencode" not in cand_norm:
            continue
        if not (candidate / "SKILL.md").exists():
            missing_targets.append(candidate)

    installed_paths: list[str] = []
    if missing_targets and args.install_if_missing:
        with tempfile.TemporaryDirectory(prefix="revise_sci_skill_install_") as tmpdir:
            cloned_skill = clone_skill_subdir(args.repo_url, args.skill_name, Path(tmpdir) / "repo")
            for target in missing_targets:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(cloned_skill, target, dirs_exist_ok=True)
                installed_paths.append(str(target.resolve()))

    print(
        json.dumps(
            {
                "ok": True,
                "skill_name": args.skill_name,
                "existing_paths": existing,
                "missing_targets": [str(path) for path in missing_targets],
                "installed_paths": installed_paths,
                "repo_url": args.repo_url,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
