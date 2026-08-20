#!/usr/bin/env python3
"""可选 git 检查点，叠加在各技能 state_manager snapshot 之上（不替换）。

静默退化为 no-op 的两种情况（snapshot 仍是回退兜底）：
  1. 本机无 git；
  2. 项目根已落在他人的 git 仓库内（不污染用户已有仓库）。

子命令:
  init   <root>          # 非已有仓库时 git init + .gitignore + 首 commit
  commit <root> <msg>    # git 可用且本项目自有 .git 时提交，无变更也不报错
  status <root>          # 供 DoD 自检：打印本项目 git commit 数（none=仅 snapshot）

commit/init 内联 -c user.* 以防裸机无 git 全局配置导致提交失败。
"""
import sys
import shutil
import subprocess
from pathlib import Path

GITIGNORE = ".DS_Store\nThumbs.db\n__pycache__/\n*.pyc\nlogs/\n*.lock\n*.tmp\n"
IGNORE_MARK = "# --- added by skill git_checkpoint ---"
IDENT = ["-c", "user.name=skill", "-c", "user.email=skill@local"]


def ensure_gitignore(root: Path) -> str:
    """三态：created / appended / unchanged。
    用户已有 .gitignore 时绝不整写（2026-08-03 缺陷：此前无条件 write_text
    抹掉用户文件，而 git 刚要 init、没有任何历史可回退）——只把缺失的必需
    条目追加到末尾（段前带标记注释），原有内容一行不动；全齐则一字不动。"""
    path = root / ".gitignore"
    if not path.exists():
        path.write_text(GITIGNORE, encoding="utf-8")
        return "created"
    text = path.read_text(encoding="utf-8", errors="replace")
    have = {ln.strip() for ln in text.splitlines()}
    missing = [e for e in GITIGNORE.splitlines() if e not in have]
    if not missing:
        return "unchanged"
    lead = "" if (not text or text.endswith("\n")) else "\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(lead + IGNORE_MARK + "\n" + "\n".join(missing) + "\n")
    return "appended"


def git_ok():
    return shutil.which("git") is not None


def inside_other_repo(root: Path) -> bool:
    r = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(root), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        return False
    return Path(r.stdout.strip()).resolve() != root.resolve()


def cmd_init(root: Path) -> int:
    if not git_ok():
        print("git_unavailable: snapshot-only")
        return 0
    if (root / ".git").exists():
        print("git_already_init")
        return 0
    if inside_other_repo(root):
        print("inside_other_repo: skip git, snapshot-only")
        return 0
    print(f"gitignore_{ensure_gitignore(root)}")
    subprocess.run(["git", "init"], cwd=str(root), check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=str(root), check=True)
    subprocess.run(
        ["git", *IDENT, "commit", "-m", "[skill] project initialized", "--allow-empty"],
        cwd=str(root), check=True, capture_output=True,
    )
    print("git_init_ok")
    return 0


def cmd_commit(root: Path, msg: str) -> int:
    if not git_ok() or not (root / ".git").exists():
        print("git_skip: snapshot is the rollback")
        return 0
    subprocess.run(["git", "add", "-A"], cwd=str(root), check=True)
    subprocess.run(
        ["git", *IDENT, "commit", "-m", msg, "--allow-empty"],
        cwd=str(root), capture_output=True,
    )
    print(f"git_commit_ok: {msg}")
    return 0


def cmd_status(root: Path) -> int:
    if not (root / ".git").exists():
        print("git_status: none (snapshot-only)")
        return 0
    r = subprocess.run(
        ["git", "log", "--oneline"], cwd=str(root), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    n = len([x for x in r.stdout.splitlines() if x.strip()])
    print(f"git_status: {n} commits")
    return 0


def main() -> int:
    sub = sys.argv[1] if len(sys.argv) > 1 else ""
    root = Path(sys.argv[2]).expanduser() if len(sys.argv) > 2 else Path.cwd()
    if sub == "init":
        return cmd_init(root)
    if sub == "commit":
        msg = sys.argv[3] if len(sys.argv) > 3 else "[skill] checkpoint"
        return cmd_commit(root, msg)
    if sub == "status":
        return cmd_status(root)
    print("usage: git_checkpoint.py {init|commit <msg>|status} <project_root>")
    return 2


if __name__ == "__main__":
    sys.exit(main())
