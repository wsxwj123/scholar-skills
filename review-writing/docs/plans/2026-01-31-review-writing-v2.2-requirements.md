# Review Writing v2.2 Requirements Update Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Update `review-writing` skill to enforce 7 strict new user requirements regarding process control, writing style, and interaction protocol.

**Architecture:**
- **SKILL.md:** The central enforcement point. Will be rewritten to include "MANDATORY PROTOCOLS" section.
- **Workflow:** Change from "Iterative Loop" to "Stop-and-Wait Loop".

**Tech Stack:** Markdown.

---

### Task 1: Update SKILL.md Core Protocols

**Goal:** Embed the 7 requirements into the skill definition.

**Files:**
- Modify: `~/.config/opencode/skills/review-writing/SKILL.md`

**Step 1: Rewrite "Core Interactive Protocol"**
- **Protocol 1 (State):** "Before EVERY response, run `state_manager.py load`. After EVERY response, run `state_manager.py update` AND `snapshot`."
- **Protocol 2 (Step-by-Step):** "STOP after completing ONE subsection. Do not proceed to the next until the user explicitly says 'Continue'. Report: Main content, Narrative logic, Ref count."
- **Protocol 3 (Human Supervision):** "Full-auto mode is BANNED. You serve as a co-pilot, not a ghostwriter."
- **Protocol 4 (Search Logic):** Define: "PubMed (Core) -> Semantic Scholar (Links) -> Google Scholar (Recent)".
- **Protocol 5 (Writing Style):** "NO BULLET POINTS in main text. Use cohesive paragraphs. Tone: Native academic English, natural flow."
- **Protocol 6 (Local Refs):** "Append a 'References' list at the end of every drafted markdown file."
- **Protocol 7 (Interaction):** "POINT-BY-POINT RESPONSE. Address every single user question/instruction separately. Do not ignore anything."

**Execute:**
1.  Read `SKILL.md`.
2.  Apply changes strictly.

Return a summary.