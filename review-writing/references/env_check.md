# Phase 0.2 — Full Environment Check (9 steps, Step 0–8)

## SKILL_DIR Auto-Detection ("Other" clients)

Run from anywhere; uses `zotero_manager.py` as a stable cross-mode marker:

```bash
python3 -c "
import pathlib
dirs = [pathlib.Path.home()/p for p in [
    '.claude/skills/review-writing',
    '.cursor/skills/review-writing',
    '.windsurf/skills/review-writing',
    '.config/opencode/skills/review-writing']]
found = next((str(d) for d in dirs if (d/'scripts'/'zotero_manager.py').exists()), None)
print(found if found else 'NOT FOUND — run: find ~ -name zotero_manager.py -path */review-writing/*')
"
```

Run all checks sequentially. Display ✅/❌ per item. All must be ✅ before proceeding to Phase 0.5.
Values recorded here (`os`, `git_available`, `pubmed_proxy`, `search_fallback`) are written to
`outline.md` in Phase 0.5 and read directly in later phases.

**Step 0: Detect OS + Python version (always)**
```python
python3 -c "
import sys, platform
ver = sys.version_info
assert ver >= (3, 7), f'Python 3.7+ required — found {ver.major}.{ver.minor}. Upgrade at python.org'
print(f'✅ Python {ver.major}.{ver.minor}.{ver.micro}')
print(f'OS: {platform.system()}')  # Darwin | Linux | Windows
"
```
Record `os: Darwin/Linux/Windows` — written to `outline.md` later in Phase 0.5. All subsequent platform-specific commands branch on this value.
- Python < 3.7 → abort; guide user to upgrade (python.org / `brew install python` / `winget install Python.Python.3`)

**Step 1: Base dependencies (always)**
```bash
curl --version      # ❌ → system-level issue (Windows: curl available in PowerShell 5.1+)
```

**Step 2: Git availability (always — enables auto-checkpoint for rollback)**
```bash
git --version 2>/dev/null && echo "✅ git available" || echo "⚠️ git not found (auto-checkpoint disabled; no rollback)"
```
Record `git_available: true / false` — written to `outline.md` later in Phase 0.5.
Git not available → **not blocking, but ASK the user**: review-writing has no snapshot fallback, so without git there is **no rollback at all**. Prompt: "git 未安装，本技能无 git 时无任何回退手段——是否现在安装？" 愿装 → 按平台指引安装（`brew install git` / `sudo apt install git` / `winget install Git.Git`）后重跑本步；不装 → 确认知悉无回退后继续，所有 checkpoint 静默跳过（`git_available: false`）。

**Step 3: Zotero (Zotero mode only)**
```python
# Desktop app installed? (cross-platform)
python3 -c "
import platform, pathlib, sys
s = platform.system()
paths = {
  'Darwin':  pathlib.Path('/Applications/Zotero.app'),
  'Linux':   pathlib.Path('/usr/bin/zotero'),
  'Windows': pathlib.Path(r'C:/Program Files/Zotero/Zotero.exe'),
}
p = paths.get(s)
print('✅ Zotero found' if p and p.exists() else f'❌ Zotero not found at {p}')
"

# PyZotero library
python3 -c "import pyzotero; print('✅')" 2>/dev/null || echo "❌ run: pip install pyzotero"
```

**Step 4: PubMed edirect (Medical/Bio discipline)**
```python
# edirect detection (cross-platform)
python3 -c "
import shutil, platform
if shutil.which('esearch'):
    print('✅ edirect found')
elif platform.system() == 'Windows':
    print('❌ edirect not available on native Windows')
    print('   Options: (1) install WSL then run edirect inside WSL bash')
    print('            (2) skip edirect → use paper-search MCP as primary tool')
else:
    print('❌ edirect not installed')
"
```
If missing (Mac/Linux — run in bash):
```bash
sh -c "$(curl -fsSL https://ftp.ncbi.nlm.nih.gov/entrez/entrezdirect/install-edirect.sh)"
source ~/.bashrc  # or ~/.zshrc
```
If missing (Windows) → install WSL (`wsl --install` in PowerShell as Admin), then install edirect inside WSL; or auto-fallback to paper-search MCP (write `search_fallback: paper-search-mcp` to outline.md).

**Step 5: Proxy + PubMed connectivity**
```bash
PUBMED_TEST="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=test"
DIRECT=$(curl -s --max-time 4 "$PUBMED_TEST" 2>/dev/null | grep -c "Count" || echo 0)
PROXY_PORT=""
if [ "$DIRECT" -eq 0 ]; then
  for port in 7890 1080 8080 8888; do
    R=$(curl -s --proxy "http://127.0.0.1:$port" --max-time 4 "$PUBMED_TEST" 2>/dev/null | grep -c "Count" || echo 0)
    if [ "$R" -gt 0 ]; then PROXY_PORT=$port; break; fi
  done
fi
# → write to outline.md: pubmed_proxy: none / http://127.0.0.1:XXXX
# → if both fail: fallback to paper-search MCP, notify user
```

**Step 6: NCBI API Key (optional, improves rate limit)**
```bash
echo ${NCBI_API_KEY:-"not set (rate limit 3 req/s; recommended to set)"}
# To set: export NCBI_API_KEY=your_key >> ~/.bashrc
```

**Step 7: paper-search MCP availability**
```
Check if tool list includes search_pubmed / search_arxiv:
  ✅ → paper-search MCP available
  ❌ → PubMed CLI only; inform user they may optionally configure paper-search MCP
```

**Step 8: Required scripts exist (always — verify SKILL_DIR is correct first)**
```python
python3 -c "
import pathlib, sys
# SKILL_DIR common locations:
#   Claude Code:  ~/.claude/skills/review-writing/
#   Cursor:       ~/.cursor/skills/review-writing/  (or project .cursor/skills/)
#   Windsurf:     ~/.windsurf/skills/review-writing/
#   Other:        the directory from which this SKILL.md was loaded
skill_dir = pathlib.Path('[SKILL_DIR]')  # AI substitutes actual path
required = ['zotero_manager.py','export_bibtex.py',
            'matrix_manager.py','word_counter.py','citation_guard.py',
            'validate_citations.py','check_global_citation_sequence.py',
            'citation_utils.py','citation_guard_core.py','state_manager.py',
            'prewrite_gate.py','delegate_review.py','style_checker.py']  # keep aligned with Phase 0.5 REQUIRED_SCRIPTS
missing = [s for s in required if not (skill_dir/'scripts'/s).exists()]
if missing:
    print(f'❌ Missing scripts: {missing}')
    print(f'   Check SKILL_DIR is correct: {skill_dir}')
    sys.exit(1)
print(f'✅ All {len(required)} required scripts found in {skill_dir}/scripts/')
"
```
If any script is missing → abort; verify SKILL_DIR path or re-install the skill.
