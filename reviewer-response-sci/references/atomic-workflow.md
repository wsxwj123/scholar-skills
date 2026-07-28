# Atomic Workflow (Reviewer Response)

## Goal
Generate one hierarchical HTML in one shot, while storing each comment page as an atomic JSON unit for easy post-edit and re-render.

## Storage Layout
- project_root/
- project_root/project_state.json
- project_root/index.json
- project_root/units/000_email.json
- project_root/units/001_R1_major_01.json
- project_root/units/002_R1_major_02.json
- ...

## One-Shot Build
0. Run preflight checks (`preflight.py`).
1. Parse comments docx into reviewer/section/comment blocks.
2. Generate atomic JSON for each block (plus email page JSON).
3. Atomize manuscript and SI into paragraph-level JSON units.
4. Link each comment unit to manuscript/SI unit IDs via anchors.
5. Build `index.json` hierarchical TOC.
6. Render full HTML from atomic JSON.
7. Run `strict_gate.py`, `consistency_check.py`, `final_consistency_report.py`, and `html_format_check.py`.
8. Persist checkpoint + transaction logs under `logs/`.

## Incremental Edit
- Edit one unit JSON only.
- Re-run render script to regenerate final HTML.
- No need to reparse all comments.

## Hard Rules
- Do not fabricate evidence.
- Missing items must be explicitly `Not provided by user`.
- Keep page schema stable for deterministic rendering.
