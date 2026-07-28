# Review Writing Humanizer Upgrade Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Integrate `humanizer-zh` principles into `review-writing` to eliminate "AI flavor" from generated academic text.

**Architecture:**
- **SKILL.md:** Add strict "Anti-AI" rules.
- **Reviewer Simulator:** Add a "Turing Test" critique dimension.

**Tech Stack:** Markdown.

---

### Task 1: Update SKILL.md with Humanizer Protocols

**Goal:** Enforce human-like writing at the prompt level.

**Files:**
- Modify: `~/.config/opencode/skills/review-writing/SKILL.md`

**Step 1: Add "Anti-AI Writing Style" Section**
Insert this under "FINAL SYSTEM ENFORCEMENT":

**### 8. Anti-AI Writing Style (Humanizer Protocol)**
**Ban List (Do NOT use):**
- **Words**: Moreover, Crucial, Landscape, Tapestry, Realm, Pivot, Foster, Underscore, Delve into, Spearhead.
- **Phrases**: "It is worth noting", "In conclusion", "As mentioned above", "Serves as", "Acts as".
- **Patterns**:
    - **Negative Parallelism**: "Not only X, but also Y" (Unless X and Y are truly distinct and surprising).
    - **False Range**: "From A to B" (Unless A and B cover a real spectrum).
    - **The "Ing" Tail**: "...highlighting the importance of..." (Stop doing this. Start a new sentence.)

**Enforcement:**
- **Use "Is"**: Don't say "X serves as a Y". Say "X is a Y".
- **Be Direct**: Don't say "This study sheds light on...". Say "This study showed...".
- **Vary Sentence Length**: Mix short (5-10 words) and long sentences. AI tends to write medium-length sentences exclusively.

---

### Task 2: Update Reviewer Critique Template

**Goal:** Make the reviewer check for AI-isms.

**Files:**
- Modify: `~/.config/opencode/skills/review-writing/templates/review_critique.md`

**Step 1: Add "Turing Test Check"**
Add a new section:
**6. Turing Test (AI Flavor Check)**
- Does it use words like "Delve", "Landscape", "Crucial"? (-1 point each)
- Does it have "In conclusion" or "To summarize"? (Lazy transitions)
- Is the tone too "Salesy" or "Promotional"? (Academic writing should be dry/neutral)
- **Verdict**: If it sounds like ChatGPT, Reject.

**Execute:**
1.  Update `SKILL.md`.
2.  Update `templates/review_critique.md`.
3.  Package.

Return a summary.