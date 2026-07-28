# WHY-HOW-WHAT Lightweight Structured-Comparison Mode

> Loaded when `Review type = why-how-what` (Phase 0). A middle weight between a one-line
> quick summary and a full narrative review: structure each paper across three layers and
> compare them in a single matrix. No PRISMA, no RoB, no GRADE. Lighter than narrative —
> no enforced ≥150-citation floor, no multi-section storyline; the deliverable is the
> comparison matrix plus a short synthesis paragraph per dimension.

---

## 1. The three layers

For every paper, extract exactly these three:

| Layer | Question it answers | What to capture |
|-------|---------------------|-----------------|
| **WHY** | Motivation / problem | The gap or problem the paper targets; why it matters |
| **HOW** | Method / approach | Design, model, dataset, technique, sample — the mechanism of the work |
| **WHAT** | Findings / contribution | Key result, effect, claim; limitations if stated |

Keep each cell to 1–3 sentences. This mode is for *fast structured triage*, not exhaustive synthesis.

---

## 2. Comparison matrix (the core deliverable)

One row per paper, the three layers as columns. Reuse the existing `gid`/citation scheme.

```markdown
| Paper (gid)     | WHY (motivation/problem) | HOW (method)           | WHAT (finding/contribution) |
|-----------------|--------------------------|------------------------|-----------------------------|
| Smith2023 [1]   | ...                      | ...                    | ...                         |
| Lee2024 [2]     | ...                      | ...                    | ...                         |
```

Persist to `data/synthesis_matrix.json` via the normal matrix flow if Zotero/index mode is
active; otherwise keep it inline in the draft.

---

## 3. Cross-paper synthesis (short)

After the matrix, write one short paragraph per layer:
- **WHY synthesis:** which problems cluster together? which gap is over-/under-served?
- **HOW synthesis:** dominant methods vs. outliers; methodological trends or splits.
- **WHAT synthesis:** where findings agree, where they conflict, and the *why* of conflicts.

End with a 2–4 sentence "so what" takeaway. No full storyline arc required.

---

## 4. Phase wiring (lightweight overlay)

- **Phase 0:** Review type = why-how-what → skip the heavy citation-floor reminder; set a
  light target (e.g. "10–30 papers" unless user specifies).
- **Phase 2 (search):** normal serial search; no PRISMA counting.
- **Phase 3 (write):** fill the WHY/HOW/WHAT matrix (§2) instead of long thematic sections,
  then the per-layer synthesis (§3). Anti-AI writing rules still apply to the synthesis prose.
- **Phase 4:** standard citation validation + export; no RoB/GRADE artifacts.
