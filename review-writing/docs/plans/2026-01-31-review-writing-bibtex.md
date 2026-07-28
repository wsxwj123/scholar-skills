# Review Writing BibTeX Upgrade Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Implement a "BibTeX Centric Pipeline" with global continuous numbering for the review-writing skill.

**Architecture:**
- **Database:** `literature_index.json` is the source of truth. Each entry has a `global_id` (1, 2, 3...).
- **Numbering:** Global sequential numbering is enforced by `state_manager.py`.
- **Export:** `export_bibtex.py` generates the `.bib` file for Zotero/EndNote.
- **Writing:** AI uses `[n]` which corresponds to `global_id`.

**Tech Stack:** Python 3, JSON.

---

### Task 1: Upgrade Data Schema & State Manager

**Goal:** Ensure every paper has a unique, sequential `global_id`.

**Files:**
- Modify: `~/.config/opencode/skills/review-writing/scripts/state_manager.py`

**Step 1: Modify `update` function**
- When adding new papers to `literature_index.json`:
    - Read the current max `global_id` (default 0).
    - Assign `global_id = max_id + 1` to the new paper.
    - Save the paper with this ID.

**Step 2: Modify `load` function**
- When `load --section` is called:
    - Filter papers by tag.
    - **Crucial:** In the output JSON, include the `global_id` field clearly (e.g., `[1] Title...`).
    - This allows the AI to see: "Ah, this is paper [15], I should cite it as [15]".

**Step 3: Test**
- Create a test that adds 3 papers and verifies they get IDs 1, 2, 3.

---

### Task 2: Create BibTeX Export Script

**Goal:** Convert the JSON index to a format Zotero can read.

**Files:**
- Create: `~/.config/opencode/skills/review-writing/scripts/export_bibtex.py`

**Step 1: Script Logic**
- Read `literature_index.json`.
- Iterate through all papers.
- Generate a BibTeX entry for each:
    ```bibtex
    @article{ref_1,
      author = {...},
      title = {...},
      year = {...},
      doi = {...},
      note = {Global ID: [1]}
    }
    ```
- Save to `references.bib` in the project root.

**Step 2: CLI**
- `python scripts/export_bibtex.py`

---

### Task 3: Update SKILL.md for Global Numbering

**Goal:** Teach AI to respect the global numbering system.

**Files:**
- Modify: `~/.config/opencode/skills/review-writing/SKILL.md`

**Step 1: Update Core Protocol**
- **Citation Rule:** "You must use the `global_id` provided in the context (e.g., `[15]`). Do NOT re-number papers starting from 1 for each chapter."
- **Workflow:** "After searching, if you find NEW papers, use `state_manager.py update` to register them. The system will assign IDs. Then use those IDs."

**Step 2: Add Export Step**
- In **Phase 3**, add "Run `python scripts/export_bibtex.py` to generate the final bibliography."

**Step 3: Package**
- Run `package_skill.py`.

---

### Task 4: Verify Full Workflow

**Goal:** Ensure the loop works.

**Step 1:** Run setup.
**Step 2:** Add a dummy paper via update.
**Step 3:** Load state, check ID.
**Step 4:** Export bibtex.
