# Phase 0-P: Polish Mode

> **Prerequisites (Polish Mode entry path):**
> Complete **Phase 0.1–0.5** first (parameter collection → environment detection → project init).
> Phase 0-P begins *after* `outline.md` and `state.json` exist and scripts are copied.
> If resuming across sessions and `outline.md` already has `os:` field → skip environment detection.

## Step 0: Verify Parameters (already collected in Phase 0.1)

Phase 0.1 has already collected all parameters (title, journal, language, etc.) and Phase 0.5 has written them to `outline.md`.
**Do NOT re-ask parameters.** Read `outline.md` Parameters section and confirm it is complete.
If any field is missing (e.g., cross-session resume with a partial `outline.md`) → ask only the missing fields.

- If `outline.md` already exists and has `os:` field → skip environment detection (already done).  
- Otherwise → run Phase 0.2 Steps 0–3 (OS + Python version + Git + Zotero check) before continuing.
- **Format-specific dependency probes** (run only for the format the user is actually importing). Each probe is **machine-checked, then HALT-on-miss with explicit consent prompt** — never silently degrade:

  - `.docx` →
    ```bash
    python3 -c "import docx; print('✅ python-docx')" 2>/dev/null \
      || echo "❌ python-docx missing"
    ```
    If ❌ → **HALT.** Ask user:
    > "python-docx is not installed. Install it now (`pip install python-docx`)? (yes / no / convert externally)"
    - On `yes` → run `python3 -m pip install python-docx` → **MANDATORY re-probe** with the
      same one-liner above. If re-probe still shows ❌:
      - Check `which python3` matches pip's interpreter; force-match with
        `python3 -m pip install python-docx` (already shown above) rather than bare `pip`.
      - If still failing, suggest `python3 -m pip install --user python-docx` to bypass
        permission/venv issues.
      - Loop until ✅ OR user switches to `convert externally`.
    - On `no` / `convert externally` → ask user to save the document as .md (Word: File →
      Save As → Markdown / Plain text) and restart Step 1.

  - `.pdf` → run all three probes once, collect the available set.

    **Cross-platform invocation** (pick the one that matches your shell):
    ```bash
    # Mac/Linux/WSL bash/zsh — heredoc directly to python3:
python3 << 'PYEOF'
import shutil, subprocess, sys
results = {}
for mod in ['pdfplumber', 'pypdf']:
    r = subprocess.run([sys.executable, '-c', f'import {mod}'],
                       capture_output=True)
    results[mod] = (r.returncode == 0)
results['pdftotext'] = bool(shutil.which('pdftotext'))
available = [k for k, v in results.items() if v]
missing   = [k for k, v in results.items() if not v]
print('AVAILABLE:', available if available else 'NONE')
print('MISSING:', missing)
sys.exit(0 if available else 2)  # exit 2 = nothing available
PYEOF
    ```
    ```powershell
    # Windows PowerShell — here-string + Out-File. NOTE: probe runs BEFORE Phase 0.5
    # creates tmp/, so write the probe file to CWD instead of tmp\:
    @'
    import shutil, subprocess, sys
    results = {}
    for mod in ['pdfplumber', 'pypdf']:
        r = subprocess.run([sys.executable, '-c', f'import {mod}'], capture_output=True)
        results[mod] = (r.returncode == 0)
    results['pdftotext'] = bool(shutil.which('pdftotext'))
    available = [k for k, v in results.items() if v]
    missing   = [k for k, v in results.items() if not v]
    print('AVAILABLE:', available if available else 'NONE')
    print('MISSING:', missing)
    sys.exit(0 if available else 2)
    '@ | Out-File -Encoding utf8 _probe.py
    python _probe.py
    Remove-Item _probe.py  # clean up
    # Read exit code: $LASTEXITCODE  (0 = at least one available; 2 = all missing)
    ```
    ```cmd
    REM Windows CMD — no heredoc/here-string; create the file IN CWD (tmp\ not yet
    REM created; Phase 0.5 will create it later):
    python -c "open('_probe.py','w',encoding='utf-8').write('import shutil,subprocess,sys\nresults={}\nfor mod in [\"pdfplumber\",\"pypdf\"]:\n    r=subprocess.run([sys.executable,\"-c\",f\"import {mod}\"],capture_output=True)\n    results[mod]=(r.returncode==0)\nresults[\"pdftotext\"]=bool(shutil.which(\"pdftotext\"))\navail=[k for k,v in results.items() if v]\nmiss=[k for k,v in results.items() if not v]\nprint(\"AVAILABLE:\",avail if avail else \"NONE\")\nprint(\"MISSING:\",miss)\nsys.exit(0 if avail else 2)\n')"
    python _probe.py
    del _probe.py
    REM Read exit code: %ERRORLEVEL%
    ```
    Decision rule:
    - **At least one ✅** → use the highest-priority available tool (pdfplumber > pypdf > pdftotext) for Step 1. Do NOT prompt the user — proceed silently.
    - **All ❌** → **HALT.** Show this exact menu to the user and wait for explicit choice:
      ```
      No PDF extractor found. Pick one to install:
        [1] pdfplumber  (recommended; handles academic multi-column layouts best)
             → pip install pdfplumber
        [2] pypdf       (lighter, faster, less accurate on complex layouts)
             → pip install pypdf
        [3] pdftotext   (CLI tool; best for plain-text PDFs)
             Mac:    brew install poppler
             Linux:  sudo apt install poppler-utils
             Windows: download poppler binaries → unzip → add bin/ to PATH
                     https://github.com/oschwartz10612/poppler-windows/releases
        [4] None — I'll convert the PDF to .docx/.md externally and retry
      Your choice? (1/2/3/4)
      ```
    - After the user picks 1/2/3:
      ```bash
      # Install whichever was chosen, then RE-RUN the probe block above to confirm.
      # Do NOT skip the re-probe — installation can silently fail (network, permissions,
      # wrong Python interpreter, binary not added to PATH).
      # If re-probe still shows AVAILABLE: NONE:
      #   - For pip installs: check `which python3` matches the interpreter used by pip;
      #     try `python3 -m pip install <pkg>` to force the same interpreter
      #   - For pdftotext: confirm the install path is in PATH.
      #       Mac/Linux/WSL: `command -v pdftotext` and `echo $PATH`
      #       Windows (PowerShell/CMD): `where pdftotext` and `echo %PATH%`
      #     If not found:
      #       Mac/Linux/WSL → `export PATH="<install-bin-dir>:$PATH"` for current session;
      #         persist by appending to `~/.zshrc` or `~/.bashrc` and `source` it.
      #       Windows → System Properties → Environment Variables → edit PATH → add the
      #         poppler `bin\` directory → **open a NEW terminal window** (PATH changes
      #         only apply to new processes) → re-run the probe.
      ```
    Only after the re-probe returns at least one ✅, advance to Step 1. Otherwise loop back to the menu (the user may pick option 4 to bail out).

Then run Phase 0.5 initialization (create folder structure + copy scripts), same as Write Mode.

## Step 1: Accept Draft

> **Placeholder convention:** `[FILE]` in the commands below = absolute or
> project-relative path to the user-provided draft (e.g. `~/Downloads/my_review.pdf`).
> AI MUST substitute it before executing. Path quoting must handle spaces — wrap with
> single quotes in bash/zsh, double quotes in PowerShell, or escape per shell rules.

**One command for ALL formats — `extract_headings.py` produces the text AND the heading truth-source in one pass** (`tmp/draft_import.md` + `tmp/heading_manifest.json`, offsets natively aligned). This replaces the old per-format inline python; the script owns the only judgment call ("what is a heading") so Step 2 can split/audit deterministically.

```
# .md / .txt / .docx / .pdf / pasted-text-saved-to-a-file — same call:
python3 scripts/extract_headings.py --source '[FILE]' \
        --text-out tmp/draft_import.md --out tmp/heading_manifest.json
```
- `.md/.txt` → `#`-based headings (high confidence).
- `.docx` → Word heading styles + **styles.xml reverse lookup** (basedOn chain / outlineLvl) so non-standard custom styles (e.g. "论文三级标题" basedOn Heading3) are NOT missed.
- `.pdf` → text extracted, `headings: []` + `warning:"no_heading_detected"` (exit 0) → triggers the no-heading path in Step 2.
- Exit contract: **0** success (incl. headless) / **1** source corrupt or <200 chars (scanned — same HALT semantics as the sanity check below) / **2** usage error / `--source` missing / missing python-docx / no PDF extractor. Non-zero → resolve with user before Step 2 (装依赖走 Step 0 流程).

> **Why explicit UTF-8 everywhere:** the script always writes `tmp/draft_import.md` as UTF-8; never re-open it with a platform-default encoding (Windows cp1252) or Chinese/Unicode drafts will mojibake.

Both files are now on disk: `tmp/draft_import.md` (byte-stream基准) and `tmp/heading_manifest.json` (标题真值).

**Post-extraction sanity check (MANDATORY after .docx / .pdf extraction — fail-safe on missing file, hard HALT on suspicious length):**
```python
python3 -c "
import pathlib, sys
p = pathlib.Path('tmp/draft_import.md')
if not p.exists():
    sys.exit('❌ Extraction produced no output file. Check: (1) [FILE] path correct? (2) PDF password-protected or corrupt? (3) Run with the next probe tool in Step 0 priority order, or convert externally.')
text = p.read_text(encoding='utf-8', errors='replace')
n = len(text.strip())
print(f'Extracted {n} chars, {len(text.splitlines())} lines')
if n < 200:
    sys.exit('❌ Suspiciously short (<200 chars) — likely scanned PDF (image-only, no text layer) or extraction failure. Run OCR (ocrmypdf / Adobe Acrobat) or convert to .docx first, then retry Step 1.')
elif n < 2000:
    sys.exit('⚠️ HALT: only {} chars extracted — very short for a full review. Verify with user that this is the complete document before continuing to Step 2 (the user may have uploaded an abstract-only file or extraction may have dropped pages).'.format(n))
print('✅ Text length looks reasonable for a review draft — safe to proceed to Step 2.')
"
```
> **Hard HALT semantics:** non-zero exit from this check **blocks Step 2 entirely**. Do NOT proceed to atomic split if any branch above triggers — first resolve the underlying extraction problem with the user.

## Step 2: Atomic Split by Heading Hierarchy (two paths + two-layer reverse verification)

> **⚠️ MANDATORY — do NOT write any file to `drafts/` until the two machine-verification layers are green AND the user explicitly confirms the proposed structure. The user-confirmation gate cannot be skipped.**

The old "AI manually detects headings and hand-splits" is replaced. The only judgment call ("what is a heading") is now owned by `extract_headings.py` (Step 1). Given a trusted heading truth-source, splitting is a pure mechanical byte-slice — no subagent, zero main-context. Only when the truth-source is untrustworthy do we fall back to an LLM. **Both reverse-verification layers always run** afterwards.

Execute in this exact order:

**2.1 Path judgment (deterministic, no AI discretion) —** read `tmp/heading_manifest.json`:
```
trusted := headings 非空  AND  无任何 confidence=="low" 的 heading
有标题路 ⇐ trusted == true      # 2.2 确定性脚本切
无标题路 ⇐ trusted == false     # 2.3 LLM 拆分子代理（含 headings:[] / low-confidence）
```
路径判据只判"有无可信标题"（heading_manifest 非空且无 low-confidence 项）——这是 manifest 里真实存在、可机械判定的字段。**覆盖缺口不在此判**（manifest 无"缺口"字段，无法在此机械判定），而是下游处理：首标题前非空正文由 split_headings 自动纳入为前导 frontmatter atom（`section_00_frontmatter.md`，§9，不报错不丢），split_audit 仅在它被丢弃（无前导 atom 覆盖）时以 `preamble_dropped` 判红；区间内漏/串/漂移由逐区比对兜。PDF imports and docx-without-styles land here as headless → no-heading path.

**2.2 Has-heading path — mechanical slice (main-session Bash, zero context):**
```
python3 scripts/split_headings.py --text tmp/draft_import.md --headings tmp/heading_manifest.json \
      --atoms-dir drafts --naming 'section_{major}_{minor}.md' --split-to-level 2 \
      --manifest-out tmp/split_manifest.json
```
Slices `text[o_i:o_{i+1}]` byte-for-byte; captions (`is_caption`) ride inside their region, not split out. Exit 0 success / 1 IO / 2 usage·headings-empty·offset-out-of-range. Main session only sees "exit 0, wrote N files" — no draft content enters context.

**§10 前后置标签块（extract_headings 自动附加，此处零改动）:** extract_headings 会把独立成短行的前置摘要标签（`摘要`/`Abstract`…）和后置标签（`致谢`/`基金`/`Author Contributions`…）识别成 `level:0 + kind` 的特殊 heading，成为额外切点。于是 split_headings 自然多产两块 atom：前置摘要块 `section_00b_abstract.md`（摘要+关键词+图形摘要，`kind=front_abstract`）、后置块 `section_zz_backmatter.md`（致谢起至文末合成一块，`kind=back_matter`）；标题+作者+机构仍走 §9 前导 `section_00_frontmatter.md`。防误判三关（行首锚定+整行≈标签+短行、后置位置门仅参考文献之后、不确定不切）与 `^toc\d` 目录条目排除都在 extract_headings 内做，cut_offsets/has_preamble/split_audit 均不感知 kind。无摘要/无后置标签时退化为现有行为。

**2.3 No-heading path — LLM split subagent** (only when `trusted==false`): dispatch a subagent per `references/split_subagent_prompt.md` (role = pure partition by semantic boundary, byte-for-byte copy, NO rewrite/citation-conversion). It returns atom files + `tmp/split_manifest.json` + a back-filled `tmp/heading_manifest.json` (its own cut offsets, `confidence:"low"`, `style_id:"llm"`). Source is given as a path (it self-Reads); the subagent prompt MUST embed the《数据与指令隔离声明》.

**2.4 Layer 1 — deterministic `split_audit.py` (always run after either path):**
```
python3 scripts/split_audit.py --text tmp/draft_import.md --headings tmp/heading_manifest.json \
      --manifest tmp/split_manifest.json --atoms-glob 'drafts/section_*.md' \
      --split-to-level 2 --root . --report tmp/split_audit_report.json
```
Per-region offset比对 (slice_i vs atom_i) catches 漏/造/串/边界漂移/乱序 all five, no false-green. **exit 0** → go to Layer 2. **exit 1** (region mismatch, fail-closed) → 回退重拆 (§回退), do NOT hand-edit files to sneak past. **exit 2** (headings空/畸形/glob命中0) → 回 2.1 路径判定. **exit 1/2 = 不得声明拆分完成.**

**2.5 Layer 2 — LLM boundary verification subagent (ALWAYS run after audit exit 0):** this is NOT redundant with Layer 1. split_audit *trusts* the heading truth-source; if the extract layer mis-identified a heading (called body text a heading, or missed a real one), split_audit compares against a wrong truth and still reports green. Layer 2 *reads content* down to the finest heading level and catches "the truth-source itself is wrong". Run the `split_boundary` DoD gate (`references/dod_checklist.json`) via `delegate_review.py`:
- Assemble `tmp/split_verify_ctx.md` = heading tree (no body) + per-atom anchor (its heading line + first/last 2–3 lines). **Never dump full body** — this keeps context bounded even for a 100-section doc.
- `pack` → subagent → `verify`. Verdict mapping (evidence MUST start with a tag): `[OK]`→pass→前进；`[WRONG]`→fail→回退重切（有标题路先修 extract_headings 真值）；`[UNCERTAIN]`→fail→**交用户裁决**（不自动动，展示上下文）. `uncertain` maps to **fail not na** — na would be waved through.

**2.6 User confirmation table (only after both layers green):** show the split map + audit result, wait for explicit "yes"/adjust. Then rebuild `outline.md` Outline section.
   ```
   section_01_01.md  ←  1.1 Introduction (820 words)
   section_02_01.md  ←  2.1 Delivery Systems (310 words)
   [machine-verified: split_audit exit 0, boundary gate pass]
   Confirm this split? (yes / adjust)
   ```
   > **Section ID is what matters, not heading depth.** `zotero_manager.py --init` parses by ID pattern (`N.` → level 1; `N.M` → level 2). **Do NOT** drop the numeric prefix (`Introduction` with no ID = invisible to --init).

**回退契约 (§7):** audit exit 1 → 有标题路查 extract_headings/split_headings bug 修后重跑；无标题路把 hard_fails 回喂 LLM 重拆。audit exit 2 → 回 2.1。LLM 核验 WRONG → 重切（有标题路先修真值）；UNCERTAIN → 交用户。**禁主会话手改文件蒙混。** 重切 N=2 仍红 → 停 + 交用户 + 附手动命令。

**Completion gate:** Step 2 is complete ONLY when `drafts/section_XX_XX.md` files exist on disk AND split_audit exit 0 AND the `split_boundary` gate passed AND the user confirmed. If any layer is red, do NOT advance to Step 3.

## Step 3: Diagnosis Report (per section — no external script needed)

Run `python3 scripts/word_counter.py --file drafts/section_XX_XX.md` for each section.  
Scan each file for banned words from the Anti-AI Writing Style rules (`references/writing_guidelines.md` §4).  
Count inline `[N]` citation occurrences per 500 words.

Display:
```
Section     | Words (EN) | Citations/500w | AI-flags | Recommendation
1.1 Bg      |  820       |  3.2           | 0        | ✅ keep
2.1 Del Sys |  180       |  0.8           | 2        | ⚠️ polish
3.1 Clin    |  0         |  —             | —        | ❌ write from scratch
```

Classification:
- **keep** — EN ≥500w (CN ≥1,500 chars) AND citations ≥2/500w AND AI-flags = 0
- **polish** — below any one threshold but has substantial content
- **rewrite** — below two or more thresholds  
- **missing** — section absent or <50 words

## Step 4: User Priority Assignment (Hard Block)

Show the diagnosis table. Ask user to label each section: `rewrite / polish / keep`.  
Accept flexible responses: "rewrite 2.1 and 3.1, polish 1.1, keep the rest."  
**Do not proceed to Step 5 until every non-missing section has an explicit label.**

## Step 5: Citation Import (Review-Specific)

```
0. Detect citation style in the imported draft:
   - Numeric style: inline [N] (or [1,2] or [1-3]) + numbered reference list at end
   - Author-year style: inline (Smith et al., 2020) + bibliography at end
   - Mixed / none: treat as "no reference list" and skip to item 5

   ⚠️ Author-year style: inform user that inline citations must be converted to [N]
   format before atomic split files can be used. Two options:
     a) Ask user to convert manually and re-upload
     b) AI converts during Step 2 split: assign [N] numbers in document order,
        rewrite inline (Author, Year) → [N] in each atomic draft file,
        build a mapping table: N → (Author, Year, Title) for Step 5 import

1. Extract reference list from tmp/draft_import.md (numbered list or bibliography).
   Parse each entry into a JSON record with these fields:
     `global_id` (int, MUST equal the original [N] number — see step 2),
     `title` (str), `authors` (list[str]), `year` (int/str),
     `journal` (str, optional), `doi` (str, optional), `pmid` (str, optional)
   Write the resulting list of records to **`tmp/existing_refs.json`** — this filename is
   consumed by step 3 below and the optional escape-hatch `--add-batch` call. Example:
   ```json
   [
     {"global_id": 1, "title": "...", "authors": ["Smith J","Lee K"], "year": 2021, "doi": "10.1038/..."},
     {"global_id": 2, "title": "...", "authors": ["..."], "year": 2020, "pmid": "31234567"}
   ]
   ```

2. ⚠️ PRESERVE original [N] numbering as gid:N — do NOT renumber.
   Renumbering would break all inline citations in the split section files.
   (If author-year conversion was done in Step 2, the assigned [N] numbers are already final.)

3. Write extracted references to data/literature_index.json (ALL modes — this is the canonical store):
     ⚠️ Every record in `tmp/existing_refs.json` MUST have a `global_id` field set to its
        original [N] number from the imported draft. Without it, Phase 3 `--add-batch` will
        re-assign a fresh gid via `_next_gid`, breaking every inline `[N]` reference in the
        atomic split files. The inline Python below hard-blocks on missing gid and reports
        the offending indices so you can fix `tmp/existing_refs.json` before retrying.

python3 -c "
import json, pathlib, sys
# encoding='utf-8' is mandatory: Windows default cp1252 will UnicodeDecodeError on UTF-8 refs
refs = json.load(open('tmp/existing_refs.json', encoding='utf-8'))
missing_gid = [i for i, r in enumerate(refs) if not isinstance(r.get('global_id'), int) or r.get('global_id') <= 0]
if missing_gid:
  more = '...' if len(missing_gid) > 5 else ''
  sys.exit(f'❌ {len(missing_gid)} refs missing valid global_id (indices: {missing_gid[:5]}{more}). Fix tmp/existing_refs.json: every entry needs an integer global_id matching its original [N] in the draft.')
idx = pathlib.Path('data/literature_index.json')
exist = json.loads(idx.read_text(encoding='utf-8')) if idx.exists() else []
known_dois = {e.get('doi','').strip().lower() for e in exist if e.get('doi','')}
known_gids = {e.get('global_id') for e in exist if isinstance(e.get('global_id'), int)}
added = skipped_dup = skipped_gid_collision = 0
for ref in refs:
  doi = ref.get('doi','').strip().lower()
  if doi and doi in known_dois:
      skipped_dup += 1
      continue
  if ref['global_id'] in known_gids:
      _g = ref['global_id']
      print(f'⚠️  gid:{_g} already in index — skipping (use --dedup repair if intentional)')
      skipped_gid_collision += 1
      continue
  # Preserve original gid (DO NOT renumber); ensure related_sections is present (empty until mapping confirmed)
  ref.setdefault('related_sections', [])
  ref.setdefault('verified', False)
  exist.append(ref)
  known_gids.add(ref['global_id'])
  if doi: known_dois.add(doi)
  added += 1
idx.write_text(json.dumps(exist, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Imported {added} references (skipped {skipped_dup} duplicate DOI, {skipped_gid_collision} gid collision)')
"

   **Git Checkpoint:** `git add -A && git commit -m "[review] Phase 0-P: citations imported"`

   [Zotero] **Default: do NOT sync to Zotero yet.** Imported references stay in `data/literature_index.json`
            with original gid preserved. Zotero items will be created **per-section** as each pending section
            gets a confirmed mapping — `--add-batch` is called inside Phase 3 (rewrite/polish branch) with the
            real section ID, using the local index as the source of truth (3-branch upsert handles back-fill of
            `zotero_key` automatically; see `cmd_add_batch` branch ②).

            Run `--init` only if the project's Zotero collection tree does not yet exist.
            Use the machine-readable `--find-root-title` probe to avoid fragile text parsing:
              python3 scripts/zotero_manager.py --status --find-root-title "[TITLE]" \
                --lib-id LIB_ID --api-key API_KEY
              # exit 0 → root exists; stdout is the key (capture and reuse as ROOT_KEY)
              # exit 3 → no match; run --init to create the collection tree:
              #          python3 scripts/zotero_manager.py --init --title "[TITLE]" \
              #            --outline outline.md --lib-id LIB_ID --api-key API_KEY
              # exit 4 → ambiguous (multiple top-level collections with same name);
              #          ask the user to pick from the printed key list

            ⚠️ Do NOT create a fake "imported" subcollection. Do NOT call --add-batch with a placeholder section
            name. Section mapping happens during Phase 3 per-section work.

            **Opt-in escape hatch** — if the user explicitly wants imported refs visible in Zotero immediately
            (e.g. for manual triage in Zotero UI), only then call --add-batch against a real, already-confirmed
            section ID from the outline:
              python3 scripts/zotero_manager.py --add-batch \
                --section "<real-section-id>" --papers tmp/existing_refs.json \
                --root-key ROOT_KEY --index data/literature_index.json \
                --lib-id LIB_ID --api-key API_KEY

4. Run citation guard:
              python3 scripts/citation_guard.py \
                --index data/literature_index.json \
                --log data/citation_guard_report.json
   → Unverifiable entries: mark verified:false, add to manual_review_queue
   → Do NOT force-fix at this stage; user decides during rewrite

5. If no reference list found → skip, set "citations_imported": false in state.json.
   Phase 3 will prompt for Round 2 search to fill gaps.
```

## Step 6: Initialize State + Route to Revision

Overwrite `state.json` (Phase 0.5's placeholder is replaced wholesale here — this is the
first time Polish Mode has enough info to construct the full record):
```python
python3 -c "
import json, pathlib
state = {
  'mode': 'polish',
  'phase': 3,
  'completed_sections': [],            # populated with the 'keep' list from Step 4
  'pending_sections': {
    'rewrite':  [],                    # filled from Step 4 user priority assignment
    'polish':   [],
    'missing':  [],
  },
  'zotero_root_key': '',               # captured from --find-root-title (Step 5) or --init
  'citations_imported': True,          # set False if Step 5 found no reference list
}
# AI: fill the four list/string fields above with real values from Steps 4-5 BEFORE running this command.
pathlib.Path('state.json').write_text(json.dumps(state, indent=2), encoding='utf-8')
print('✅ state.json initialized for Polish Mode (phase=3)')
"
```

**Git Checkpoint:** `git add -A && git commit -m "[review] Phase 0-P: polish mode initialized"`

Routing after Step 6:
| Section type | Path |
|---|---|
| `missing` | Phase 3 handles internally: run Phase 2 Round 1 search for this section, then write from scratch (do NOT leave Phase 3 to go back to Phase 2) |
| `rewrite` | Phase 3 (Round 2 search optional) |
| `polish` | Phase 3 (skip search; revise existing atomic file) |
| `keep` | Skip entirely (already in completed_sections) |

All sections complete → Phase 4 (export + compile).
