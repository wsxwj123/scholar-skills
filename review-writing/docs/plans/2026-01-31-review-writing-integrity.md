# Review Writing Integrity Upgrade Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Fortify the `review-writing` skill with a Basic Research Synthesis Matrix and a Citation Integrity Guard.

**Architecture:**
- **Schema:** `matrix_schema.json` defines the structure AI must fill.
- **Validation:** `validate_citations.py` checks Drafts vs. Index.
- **Cleanup:** `export_bibtex.py` enhanced to ignore unused papers.

**Tech Stack:** Python 3, JSON.

---

### Task 1: Create Basic Research Matrix Schema

**Goal:** Define the mandatory fields for data extraction in basic research reviews.

**Files:**
- Create: `~/.config/opencode/skills/review-writing/data/matrix_schema.json` (Template)

**Step 1: Define Fields**
Create a JSON file with `columns` definition:
1.  `Delivery System` (Nanoparticle, Liposome...)
2.  `Preparation Method` (Microfluidics...)
3.  `Drug Release Mechanism` (pH, Enzyme, Light...) **[NEW]**
4.  `Targeting Strategy` (Active/Passive)
5.  `Disease Model` (Cell line, Orthotopic...)
6.  `Key Target/Pathway` (STING, PD-L1...)
7.  `Administration Route` (i.v., i.t., oral...) **[NEW]**
8.  `Key Finding`
9.  `Contribution`
10. `Limitation`

**Step 2: Add Usage Instructions**
Add a `_meta` field explaining how to use this schema (e.g., "Fill this row for every paper you cite as a primary source").

---

### Task 2: Create Citation Validator Script

**Goal:** Detect when `[n]` in text doesn't match `global_id` in database.

**Files:**
- Create: `~/.config/opencode/skills/review-writing/scripts/validate_citations.py`

**Step 1: Script Logic**
- Scan all `drafts/*.md` files.
- Regex find `\[(\d+)\]`.
- Load `data/literature_index.json`.
- Identify:
    - **Orphans**: ID in text, not in DB. (Error)
    - **Unused**: ID in DB, not in text. (Warning)
- Print a clear report.

**Step 2: CLI**
- `python scripts/validate_citations.py`

**Step 3: Test**
- Create `tests/test_validator.py` with mock drafts and index.

---

### Task 3: Enhance BibTeX Export (Cleanup)

**Goal:** Allow exporting ONLY the citations actually used in the drafts.

**Files:**
- Modify: `~/.config/opencode/skills/review-writing/scripts/export_bibtex.py`

**Step 1: Add `--clean` flag**
- Update `export_bibtex.py` to accept `--clean`.
- If flag is present:
    - Run the logic from Task 2 (scan drafts for used IDs).
    - Filter the `literature_index` to only include used IDs.
    - Generate `.bib` file.
    - Report "Exported X references (excluded Y unused)".

---

### Task 4: Update SKILL.md Workflow

**Goal:** Enforce the new Matrix and Validation steps.

**Files:**
- Modify: `~/.config/opencode/skills/review-writing/SKILL.md`

**Step 1: Update Phase 2 (Synthesis)**
- "Before drafting, you MUST fill the **Synthesis Matrix** using the schema in `data/matrix_schema.json`. Ensure you extract 'Release Mechanism' and 'Admin Route'."

**Step 2: Update Phase 3 (Refinement)**
- "Run `python scripts/validate_citations.py` to check for errors."
- "Run `python scripts/export_bibtex.py --clean` to generate the final clean bibliography."

**Step 3: Package**
- Run `package_skill.py`.

---

### Task 5: Verify

**Goal:** Integration test.

**Step 1:** Setup test project.
**Step 2:** Add 2 papers (ID 1, 2).
**Step 3:** Write a draft citing only `[1]`.
**Step 4:** Run validator -> Expect "Unused: [2]".
**Step 5:** Run export --clean -> Expect only ref_1 in bib file.
