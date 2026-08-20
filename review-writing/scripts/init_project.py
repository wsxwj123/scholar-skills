#!/usr/bin/env python3
"""
init_project.py — Phase 0.5 project scaffolding for the review-writing skill.

Creates the project folder structure, copies the active scripts, runs git init +
initial commit (if git is available), and writes the initial state.json + outline.md.
Replaces the inline `python3 << PYEOF ... PYEOF` block that previously lived in SKILL.md
Phase 0.5 — same effect, no placeholder-substitution-in-Python risk.

Usage (AI passes the three resolved paths/values):
  python3 scripts/init_project.py \
    --title "Review Title" \
    --base  "/path/to/project/base"      \   # default: current working directory
    --skill-dir "/Users/<name>/.claude/skills/review-writing"

Cross-platform: pure pathlib, no shell heredoc. Works on Mac/Linux/Windows.
The AI fills outline.md Parameters/Environment fields AFTER this runs (this only writes
the template skeleton, identical to the previous inline version).
"""

import sys as _sys
try:  # Windows GBK 控制台/管道捕获下 emoji print 防 UnicodeEncodeError
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
import argparse
import pathlib
import re
import shutil
import subprocess
import sys

# Minimum-viable set: full copy below mirrors ALL scripts/*.py, so this list is
# only a post-copy sanity assertion (not the copy source). No drift risk if it
# lags behind SKILL.md — a new script still gets copied by the glob.
REQUIRED_SCRIPTS = [
    "zotero_manager.py",
    "export_bibtex.py",
    "matrix_manager.py",
    "word_counter.py",
    "citation_guard.py",
    "validate_citations.py",
    "check_global_citation_sequence.py",
    "citation_utils.py",
    "citation_guard_core.py",  # imported by citation_guard.py + validate_citations.py
    "state_manager.py",  # used in Phase 2.5 None Mode (reindex) + set-phase/complete-section
    "prewrite_gate.py",  # Phase 3 Per-Section Cycle 开写前置闸门
    "delegate_review.py",  # Phase 3 section-dod 盲检委托 pack/verify
    "style_checker.py",  # 去 AI 风格检测
    "proofread.py",  # Phase 3 R21 字符级机器硬门禁(可阻断)
    "check_online_verified.py",  # DoD R2b 判据(本节引文是否真过了联网核验)
    "compile_manuscript.py",  # Phase 4 Step 4/4d 跨平台合并（替 bash 的 cat / grep）
    "consolidate_references.py",  # Phase 4 合并参考文献为单一列表
    "export_docx.py",  # Phase 5d 最终 docx 交付物(需 templates/reference.docx)
    "structure_signoff_gate.py",  # vendored: 结构签字硬门(SIGNOFF_CMD)
    "session_journal.py",  # vendored: 跨会话接续(RESUME_CMD)
    "citation_claim_check.py",  # vendored: 承重论点↔引文核证(CITATION_CHECK_CMD)
]

# scripts/ 下的 .json 分两类：**分发资产**（门禁清单）和**运行时产物**
# （hook_heartbeat.json —— 门禁钩子每次触发都会写，内容是"上一个用户正在写哪份稿"）。
# .py 侧可以全量镜像（新脚本自动跟上，漏拷会当场报错），.json 侧必须反过来走白名单：
# 漏拷分发资产是响的失败（脚本立刻报缺文件），误拷运行时产物是哑的失败（把别人的
# 工作痕迹静默塞进新项目）。默认不拷才是安全侧。新增要分发的 json 就往这里加一条。
DISTRIBUTED_JSON = {"gate_registry.json"}

STATE_JSON = '{"phase": 0, "completed_sections": [], "zotero_root_key": "", "authors": []}\n'

OUTLINE_TEMPLATE = """# Review Configuration (READ THIS FILE at the start of every phase)

## Parameters
- Title: {title}
- Target Journal: [user input]
- Language: [English / Chinese]
- Reference Manager: [Zotero / None / EndNote]
- Word Count Target: [EN: 7,000–10,000 words / CN: 15,000–20,000 chars]
- Citation Requirements（软目标，非硬门禁，按学科填实际值）: 生物医学/临床约 120–200、工程/CS 约 60–120、人文社科按传统定；以覆盖领域主线为准，不凑数。类型按论点性质择用、非固定配额：背景/综述性论述用 Review，机制/实验结论必须引 Original（不得用 Review 顶替），临床结论引 Clinical Trial，新兴论点确无正式发表时才引 Preprint（标 [Preprint]，按需非强制）。
- Discipline: [Medical-Biomedical / CS-AI / Interdisciplinary]

## Environment (filled after detection, read directly in later phases)
- os: [Darwin / Linux / Windows]
- git_available: [true / false]
- pubmed_proxy: [none / http://127.0.0.1:XXXX]
- zotero_lib_id: [numeric ID]
- search_fallback: [paper-search-mcp (when edirect unavailable)]
- subagent_model: [model name / same as main session]

## Research Question
- RQ / PICO: [filled after user confirms]

## Outline (filled after confirmation)
### 1. Introduction
#### 1.1 Background
#### 1.2 Scope
...

## Current Status
- Phase: Phase 0 complete
- Completed sections: none
- Zotero root collection key: [filled after Phase 1]
"""


_ILLEGAL_DIR_CHARS = '<>:"/\\|?*'


def _safe_dirname(title: str) -> str:
    """把综述标题变成各平台都合法的文件夹名。

    学术标题带冒号是常态（"Deep Learning: A Review"），Windows 下 : ? * < > | " /
    全非法、macOS 下 / 非法 —— 原样当目录名会在 Phase 0.5 当场 OSError。
    这里只清目录名；**原始标题完整写进 outline.md 的 Title 字段**（目录名可以脏，
    标题不能丢）。控制字符一并清掉（路径注入 + 终端转义两防）。
    """
    cleaned = "".join("-" if (ch in _ILLEGAL_DIR_CHARS or ord(ch) < 32) else ch
                      for ch in (title or ""))
    cleaned = re.sub(r"[-\s]{2,}", "-", cleaned).strip()
    # Windows 不允许结尾是点或空格；"." / ".." 会指向父目录，必须挡掉
    cleaned = cleaned.strip(" .")[:120].strip(" .-")
    return cleaned or "review-project"


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 0.5 project scaffolding")
    parser.add_argument("--title", required=True, help="Review title (becomes project folder name)")
    parser.add_argument("--base", default=".", help="Project base location (default: current working directory)")
    parser.add_argument("--skill-dir", required=True, help="Directory containing this skill (scripts/ live here)")
    args = parser.parse_args()

    base = pathlib.Path(args.base).expanduser().resolve()
    skill_dir = pathlib.Path(args.skill_dir).expanduser().resolve()
    dirname = _safe_dirname(args.title)
    proj = base / dirname
    if dirname != args.title:
        print(f"ℹ️  标题含文件名非法字符，目录名用清洗后的 {dirname!r}"
              f"（原标题 {args.title!r} 已完整写进 outline.md 的 Title 字段）")

    for d in ["drafts", "exports", "scripts", "data", "tmp", "figures"]:
        (proj / d).mkdir(parents=True, exist_ok=True)

    # Initialize figures index (needed by Phase 3 Step 3 in ALL modes)
    fig_index = proj / "figures" / "figure_index.md"
    if not fig_index.exists():
        fig_index.write_text("# Figure Index\n\n", encoding="utf-8")

    # Full copy: mirror ALL scripts/*.py into the project (except tests and this
    # bootstrap itself). Root-causes whitelist drift — SKILL.md adding/renaming a
    # script (or an import dependency) can never silently miss a copy again.
    copied = 0
    for src in sorted((skill_dir / "scripts").glob("*.py")):
        if src.name.startswith("test_") or src.name == "init_project.py":
            continue
        shutil.copy(src, proj / "scripts" / src.name)
        copied += 1
    # json 侧走白名单（见 DISTRIBUTED_JSON）。
    for name in sorted(DISTRIBUTED_JSON):
        src = skill_dir / "scripts" / name
        if src.is_file():
            shutil.copy(src, proj / "scripts" / name)
            copied += 1

    # REQUIRED_SCRIPTS kept as a minimum-viable-set assertion: full copy should
    # already include them; if any is absent the skill install is broken.
    missing = [n for n in REQUIRED_SCRIPTS if not (proj / "scripts" / n).exists()]
    if missing:
        sys.exit(f"❌ Missing required scripts after copy: {missing}. Verify --skill-dir={skill_dir}")

    # export_docx.py resolves templates/reference.docx as __file__.parent.parent/
    # templates/reference.docx — i.e. proj/templates/reference.docx once copied.
    # Ship the baked house-style template so Phase 5d docx export does not crash.
    ref_docx = skill_dir / "templates" / "reference.docx"
    if ref_docx.exists():
        (proj / "templates").mkdir(parents=True, exist_ok=True)
        shutil.copy(ref_docx, proj / "templates" / "reference.docx")

    print(f"✅ Project created at: {proj}")
    print(f"   Copied {copied} files (all scripts/*.py + whitelisted json: "
          f"{', '.join(sorted(DISTRIBUTED_JSON))})")

    # state.json + outline.md —— 已存在就保留（同 figure_index.md 的守卫）。
    # 无条件覆盖会让重跑 init 把 {"phase":3,"completed_sections":[...]} 打回 phase 0、
    # 把写好的大纲换成空模板，等于整个项目进度静默清零。
    # Title 用原始标题（含冒号等目录名放不下的字符），不用清洗过的目录名。
    outline_text = OUTLINE_TEMPLATE.format(title=args.title)
    for name, content in (("state.json", STATE_JSON), ("outline.md", outline_text)):
        path = proj / name
        if path.exists():
            print(f"⏭️ {name} 已存在，保留原文件（如需重建请手动删除）")
        else:
            path.write_text(content, encoding="utf-8")
            print(f"✅ Wrote {name}")

    # Git auto-checkpoint init (skip if git not available)
    if shutil.which("git"):
        subprocess.run(["git", "init"], cwd=str(proj), check=True)
        gitignore = proj / ".gitignore"
        gitignore.write_text(".DS_Store\nThumbs.db\n__pycache__/\n*.pyc\nlogs/\n*.lock\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=str(proj), check=True)
        subprocess.run(["git", "commit", "-m", "[review] Phase 0: project initialized"], cwd=str(proj), check=True)
        print("✅ Git repo initialized with initial commit")
    else:
        print("ℹ️  Git not found — auto-checkpoint disabled (no rollback)")

    # 强制门禁 hook 自动安装 + 打印结构签字命令（共享，跨全部学术技能）。
    _install_gate_hook(proj)

    print(f"\nNext: cd into {proj} before any Phase 1–4 command.")


def _install_gate_hook(proj) -> None:
    """调共享安装器 install_gate_hook.py 自动装强制门禁 hook（备份/校验/回滚 +
    心跳探测），回显其人话状态；并打印结构签字 / 接续 / 引文核证三条命令。

    双轨定位（故意不同，勿顺手统一）：
    - 纯库脚本（structure_signoff_gate / session_journal / citation_claim_check）
      已 vendored 进本技能 scripts/，就地取用 `pathlib.Path(__file__).resolve().parent`，
      不依赖 _shared。
    - installer（install_gate_hook.py）= 同目录 vendored 副本优先，会把门禁四件套部署到
      ~/.claude/academic-gate/（稳定位置，不随技能目录增删而动），settings.json 的 hook 指向那里；
      _shared 仅完整仓库回退。所以下面两个 base 不一样，这是有意为之。
    任何异常全吞——门禁自检绝不能反过来卡住技能。"""
    import json as _json
    import subprocess as _sp
    try:
        scripts_dir = pathlib.Path(__file__).resolve().parent
        installer = scripts_dir / "install_gate_hook.py"     # vendored 副本(单技能分发也在)
        if not installer.is_file():
            installer = scripts_dir.parents[1] / "_shared" / "install_gate_hook.py"  # 完整仓库回退
        if installer.is_file():
            proc = _sp.run([sys.executable or "python", str(installer)],
                           capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace")
            line = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout.strip() else ""
            res = _json.loads(line) if line else {}
            status, msg = res.get("status", ""), res.get("message", "")
            icon = {"active": "🛡️", "installed": "🛡️", "degraded": "⚠️", "error": "ℹ️"}.get(status, "ℹ️")
            if msg:
                print(f"{icon} 门禁保护[{status}]: {msg}")
        else:
            # installer 缺失 → 物理门禁装不上，降级为提示词纪律。
            print("⚠️ 门禁保护[degraded]: 缺 install_gate_hook.py（scripts/ 与 _shared/ 均无），物理拦截不可用，降级为提示词纪律。")
            print("   签字仅留痕、无强制拦截，需人工守住「未签字不写正文」。")
            print("   修复：重装完整技能仓库，或补回 _shared/install_gate_hook.py。")
        # 以下三条命令均指本地 vendored 副本，不依赖 _shared，故 installer 缺失时照常打印。
        # 解释器用 sys.executable：硬写 "python" 在纯净 macOS 上 command not found
        # （SKILL.md 开篇已注明 macOS 12.3 起系统不再自带 python），而 SIGNOFF_CMD
        # 是解锁 Phase 3 正文写作的硬门，打不出能跑的命令等于把用户堵死。
        py = sys.executable or "python3"
        signoff = scripts_dir / "structure_signoff_gate.py"
        if signoff.is_file():
            print(f'SIGNOFF_CMD: "{py}" "{signoff}" confirm --root "{proj}" --note "<用户确认原话>"')
        else:
            print('⚠️ 缺 scripts/structure_signoff_gate.py(vendored 副本)——跑 python3 _shared/sync_vendored.py --sync 或重装完整技能包')
        journal = scripts_dir / "session_journal.py"
        if journal.is_file():
            print(f'RESUME_CMD: "{py}" "{journal}" resume --root "{proj}"')
        else:
            print('⚠️ 缺 scripts/session_journal.py(vendored 副本)——跑 python3 _shared/sync_vendored.py --sync 或重装完整技能包')
        citecheck = scripts_dir / "citation_claim_check.py"
        if citecheck.is_file():
            print(f'CITATION_CHECK_CMD: "{py}" "{citecheck}" --root "{proj}"')
        else:
            print('⚠️ 缺 scripts/citation_claim_check.py(vendored 副本)——跑 python3 _shared/sync_vendored.py --sync 或重装完整技能包')
        # references/ 不镜像进项目，四道 DoD 盲检门的 --checklist 必须用技能目录绝对路径。
        # SKILL.md 里所有 `--checklist "[DOD_CHECKLIST]"` 都用这里打印的值，全程沿用。
        dod = scripts_dir.parent / "references" / "dod_checklist.json"
        if dod.is_file():
            print(f'DOD_CHECKLIST: {dod}')
        else:
            print('⚠️ 缺 references/dod_checklist.json——四道 DoD 盲检门无法运行，重装完整技能包')
    except Exception:
        pass


if __name__ == "__main__":
    main()
