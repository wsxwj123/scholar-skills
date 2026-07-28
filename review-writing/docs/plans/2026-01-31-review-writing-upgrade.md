# Review Writing Skill Upgrade Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Upgrade the `review-writing` skill to support long-form writing stability (anti-amnesia), deep critique (reviewer simulation), and workflow optimizations (figure-first, scope management).

**Architecture:** 
- **Script-First Approach:** Move logic from `SKILL.md` to Python scripts (`state_manager.py`, `scope_manager.py`) to reduce token usage and increase reliability.
- **Memory Compression:** Implement a "sliding window" or "summary-based" context loading in `state_manager.py`.
- **Workflow Enforcement:** Update `SKILL.md` to mandate Figure-First design and Reviewer Critique loops.

**Tech Stack:** Python 3 (standard library), Markdown, JSON.

---

### Task 1: Upgrade `state_manager.py` for Memory Compression

**Goal:** Prevent token overflow by implementing "Smart Loading" and "Memory Compaction".

**Files:**
- Modify: `~/.config/opencode/skills/review-writing/scripts/state_manager.py`

**Step 1: Implement `compact_memory` function**
Add a function that reads `context_memory.md`, identifies completed sections (older than N turns or marked as "Archived"), and replaces detailed logs with a high-level summary.
*Constraint:* Keep the last 5 turns or current active section detailed.

**Step 2: Implement `smart_load` for Literature Index**
Modify `load_state` to accept an optional `--section` argument.
If provided, filter `literature_index.json` to only return papers tagged with that section (or global papers), instead of the full 150+ list.

**Step 3: Test Compaction**
Create a test file `tests/test_state_manager.py` (temporary) to verify that a large memory file is correctly compressed without losing the "Current Task" context.

**Step 4: Commit**
(No git commit needed as this is a local skill, but ensure file is saved).

---

### Task 2: Implement `scope_manager.py` for Scope Management

**Goal:** Allow dynamic refactoring of the review outline without breaking the project state.

**Files:**
- Create: `~/.config/opencode/skills/review-writing/scripts/scope_manager.py`

**Step 1: Define `ScopeManager` class**
- `load_storyline()`: Read `storyline.md` and parse it into a structured object (sections, status, key points).
- `add_section(title, position)`: Insert new section.
- `remove_section(title)`: Remove section (check if data exists, warn user).
- `rename_section(old, new)`: Rename and update references in `progress.json`.

**Step 2: Implement CLI interface**
- `python scope_manager.py add "New Section Title" --after "Introduction"`
- `python scope_manager.py remove "Old Section"`

**Step 3: Test Scope Changes**
Verify that modifying the storyline updates `storyline.md` correctly and preserves the status of unchanged sections.

---

### Task 3: Create Reviewer Critique Templates

**Goal:** Provide the "Reviewer Simulator" with specific criteria for high-impact reviews.

**Files:**
- Create: `~/.config/opencode/skills/review-writing/templates/review_critique.md`

**Step 1: Define Critique Dimensions**
Create a markdown template with sections:
1.  **Novelty & Insight:** "Does this section just summarize? Where is the new perspective?"
2.  **Critical Arbitration:** "Are conflicts resolved or just stated?"
3.  **Evidence Strength:** "Are claims supported by primary literature (not just reviews)?"
4.  **Visual Potential:** "Could this text be a figure?"

**Step 2: Define "Fatal Flaws" List**
- "A did X, B did Y" structure (Laundry List).
- Citing only reviews.
- Vague statements ("Much progress has been made").

---

### Task 4: Update `SKILL.md` Workflow (Figure-First & Reviewer)

**Goal:** Enforce the new workflows in the main skill definition.

**Files:**
- Modify: `~/.config/opencode/skills/review-writing/SKILL.md`

**Step 1: Add Phase 2.1 "Figure First"**
Insert a step before "Drafting":
- **Mandatory:** Define the "Figure Concept" for this section.
- **Action:** Update `figures/figure_index.md` before writing text.

**Step 2: Add Phase 2.X "Reviewer Critique"**
Insert a step after "Drafting":
- **Mandatory:** "Simulate a Nature Reviewer".
- **Action:** Read `templates/review_critique.md`, critique the draft, and demand revisions *before* showing the user (Self-Correction).

**Step 3: Integrate Scripts**
- Replace manual "Update Index" instructions with `python scripts/state_manager.py update ...`.
- Add `/refactor` command usage linked to `scripts/scope_manager.py`.

**Step 4: Package**
Run `package_skill.py`.

---

### Task 5: Final Integration & Verification

**Goal:** Ensure all components work together.

**Step 1: Test Project Setup**
Run `scripts/setup_review_project.py test_project`.

**Step 2: Test State Loading**
Run `scripts/state_manager.py load`.

**Step 3: Test Scope Change**
Run `scripts/scope_manager.py add "Test Section"`.
Check `storyline.md`.

**Step 4: Cleanup**
Remove test project.
