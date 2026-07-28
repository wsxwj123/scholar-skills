# Academic Writing Guidelines for High-Impact Reviews

## 1. Storytelling & Logic
High-impact reviews are not summaries; they are arguments.
- **Micro-Macro Connection:** Connect specific molecular mechanisms or algorithmic details to broader clinical or scientific implications.
- **Synthesis:** Do not list studies ("A did X, B did Y"). Instead, synthesize ("While A suggests X, B's findings in context Z indicate Y, suggesting a conditional mechanism...").
- **Arbitration:** When studies conflict, be the judge. Analyze *why* they conflict (sample size, methodology, population) rather than just stating the conflict exist.

## 2. Academic Phrasebank

### Introducing a Gap
- "However, a critical question remains regarding..."
- "Despite these advances, the mechanism underlying X has not been fully elucidated."
- "Current approaches fail to address..."

### Synthesizing & Comparing
- "Conversely, recent data from [Author] challenges this view by demonstrating..."
- "In alignment with [Author A], [Author B] observed that..."
- "This discrepancy may be attributed to differences in..."

### Critical Analysis (Arbitration)
- "Although [Study A] reported positive results, the lack of a control group limits the interpretability of these findings."
- "Ideally, future studies should control for X to verify this association."
- "This suggests that the efficacy of X is likely context-dependent."

### Concluding & Outlook
- "Taken together, these findings implicate..."
- "Ultimately, translating these findings into clinical practice will require..."
- "We propose a revised model where..."

### Evidence Type Discipline（`article_type`，决策15）
每条 `data/literature_index.json` 条目带 `article_type` 字段（枚举 `original_research | review |
meta_analysis | systematic_review | clinical_trial | preprint | book_chapter | guideline | other | unknown`）。
入表时默认 `unknown`，真值由 `citation_guard.py --write-back` 从 PubMed pubtype 优先级解析回填（缺=unknown）。
纪律（DoD R9 已覆盖，机械联动在共享 `citation_claim_check.py`）：
- **承重的机制断言 / 疗效因果结论**（`claim_kind∈{mechanism,efficacy}`）**不得以综述（review /
  systematic_review）代替原著撑腰**——引 `original_research`，或疗效可引 `meta_analysis` / `clinical_trial`。
- 综述里"承重**背景**引用综述"是合法的（`claim_kind=background` 引 review 放行）——靠 `claim_kind` 精确区分，
  不一刀切。`article_type`/`claim_kind` 任一缺失/`unknown` → 机械纪律只 warning 不拦（向后兼容存量项目）。
- `preprint` 在正文该处须标 `[Preprint]`。

## 3. Structural Templates

### The Funnel Introduction
1. **Broad Context:** Historical importance or disease burden.
2. **Narrowing:** Specific sub-field or recent tech breakthrough.
3. **The Gap:** What is missing? Why is a review needed *now*?
4. **The Hook:** What this review offers (e.g., "We propose a unifying framework...").

### The Thematic Body Paragraph
1. **Topic Sentence:** The main claim of the paragraph.
2. **Evidence:** Citations and data supporting the claim.
3. **Counter-evidence/Nuance:** Complexity and conflicting data.
4. **Synthesis/Mini-conclusion:** What does this mean for the section's argument?

## 4. Anti-AI Writing Style

### English Mode
- **Ban List:** Moreover, Crucial, Landscape, Tapestry, Realm, Pivot, Foster, Underscore, Delve into, Spearhead
- **Phrases to Avoid:** It is worth noting, In conclusion, As mentioned above, Serves as, Acts as
- **Structure Ban:** No "Not only...but also"; No "From A to B"; No metaphors/similes (e.g. "like…", "as if…", "serves as a bridge/cornerstone/springboard" — state facts directly); No trailing "-ing" clauses (e.g., ban ", reflecting a shift toward…"; ban ", ensuring that…"; ban ", highlighting the importance of…" — recast as a new finite clause or sentence).
- **Sentence length — soft guide (not a hard gate):** Aim for single sentences ≤30 words; a sentence running longer is a rhythm prompt to consider splitting, not a blocker. style_checker flags this as `info` (advisory) — do not fail a section on length alone.
- **Rhythm:** Mix short sentences (≤12 words) with mid-range (25–30 words). Avoid long runs of 3+ consecutive similar-length sentences.
- **Voice (review-specific) — soft guide:** For literature reviews, active voice is primary; passive around ≤30% per paragraph is a target, not a hard limit. Excess passive reads stiff, so trim where natural; style_checker reports it as `info` (advisory), not a gate failure. Reviews still avoid the 50–70% passive norm of original research articles.
- **Synonym cycling — ban:** Within the same paragraph, use one consistent term for each concept. Do not cycle synonyms (e.g., do not alternate "tumor microenvironment / TME / cancer stroma" within one paragraph — pick one and use it). Cycle across paragraphs is acceptable for stylistic variety.
- **Transitions:** Ban "Furthermore / In addition / Moreover" bolted-on. Embed causality into main clause.

### Chinese Mode
- **Ban List:** 值得注意的是、不仅如此、此外、综上所述、总而言之、深入探讨、至关重要、在此背景下、显而易见
- **Structure Ban:** 一方面……另一方面……; 随着……的不断发展; 日益受到关注; 禁任何比喻（明喻/暗喻/借喻，如"如同/犹如/像…一样"及"…的桥梁/基石/催化剂"类比喻名词——直接陈述事实）
- **Rhythm:** Short sentences ≤15 characters, long sentences 30–60 characters. Avoid 3+ consecutive same-pattern sentences.

### Deep Rewriting (Anti-Similarity Protocol)
- **Lexical:** Replace non-terminological generic words. Verbatim phrase ≥4 consecutive words → decompose and reconstruct.
- **Syntactic:** Alternate active/passive. Embed causality. No templated transitions.
- **Structural:** Alternate "claim-then-evidence" vs "evidence-then-claim". Insert judgment sentences ("This likely reflects…").

### Three Additional AI-Marker Bans

**1. Decorative em-dashes (—): hard gate, banned**
- **Banned:** Using — or —— as a pause, supplement, or emphasis device (e.g., "The result was clear, cells died"). Em-dashes are prohibited; style_checker flags any em-dash as a `high` issue and sets hard_fail, failing the gate regardless of score.
- **Allowed:** Hyphens in compound modifiers (dose-dependent), numeric ranges (1990–2005), and en-dashes in structured labels.
- **Fix:** Recast as a comma, period, or separate sentence. "The result was clear—cells died" → "The result was clear: cells died at 48 h."

**2. Scare quotes on ordinary phrases**
- **Ban:** Wrapping a self-coined word or plain phrase in double quotes to signal novelty or irony (e.g., "precision" approaches, a "crosstalk" between pathways).
- **Allowed:** First-definition of a term being formally introduced ("molecular switch" is used here to denote…), direct quotation from a cited source, already-fixed technical metaphors cited in the literature.
- **Fix:** Either commit to the term without quotes, or introduce it with an explicit definition clause.

**3. Explanatory colons as decoration**
- **Ban:** "Concept: explanation" sentence structure used as a stylistic flourish (e.g., "The implication is stark: resistance emerges rapidly").
- **Allowed:** Ratios and times (3:1, 12:00), list introductions ("Three criteria were applied:"), figure/table captions ("Figure 1: …"), section headings.
- **Fix:** Merge into a subordinate clause or split into two sentences. "The implication is stark: resistance emerges rapidly" → "Resistance emerges rapidly, which has a stark implication for treatment sequencing."

### Abbreviation / Acronym Management
- **First-use rule (EN):** `Full Name (ABBR)` on first occurrence in the manuscript body. Subsequent uses → ABBR only.
- **First-use rule (CN):** `中文全称（英文全称, ABBR）` on first occurrence. Example: `光动力疗法（Photodynamic Therapy, PDT）`.
- **Title & Abstract:** Do NOT use abbreviations in the title. In the abstract, re-define any abbreviation used (abstract is read independently from the body).
- **Universally known exceptions:** DNA, RNA, PCR, HIV, WHO, FDA — may be used without expansion.
- **Abbreviation registry:** Maintain `exports/abbreviation_list.md` (auto-generated in Phase 4 Step 4c). Format:

  ```
  | Abbreviation | Full Name | First Defined In |
  |---|---|---|
  | PDT | Photodynamic Therapy | Section 1.1 |
  | ROS | Reactive Oxygen Species | Section 2.1 |
  ```
- **Cross-section consistency:** When writing Section N, check if the abbreviation was already defined in a previous section. During Phase 3 the registry does not exist yet (Phase 4 generates it) — grep the already-written `drafts/section_*.md` files for the `Full Name (ABBR)` pattern. If already defined, use ABBR directly — do NOT re-expand.

### Character-Level Typesetting Contract

Inline formatting in section drafts must follow these rules (reviews are usually English; rules written in English).

- **Italic via `*...*`** — apply to:
  - Species Latin names: `*E. coli*`, `*Arabidopsis*`, `*Staphylococcus aureus*`.
  - Gene names (per convention): `*TP53*`, `*BRCA1*`.
  - Statistical symbols: `*p*`, `*t*`, `*n*`, `*F*`, `*r*` (e.g. `*p* < 0.05`, `*n* = 30`).
  - Latin abbreviations: `*in vitro*`, `*in vivo*`, `*et al.*`, `*via*`, `*ex vivo*`, `*de novo*`.
- **Superscript `^...^` / subscript `~...~`** (pandoc syntax, reserved for future docx export):
  - Superscript: `10^6^`, `cm^2^`, `μm^2^`.
  - Subscript: `H~2~O`, `CO~2~`, `IC~50~`.
  - Never write bare `H2O` / `CO2` / `IC50` — always mark sub/superscripts.
- **Bold `**...**`** — only for emphasis or headings. Do NOT use bold for species names, genes, or statistical symbols (those are italic).
- **Half-width / full-width punctuation:**
  - English, numbers, and DOIs use half-width characters and punctuation throughout.
  - If a sentence contains Chinese, use full-width punctuation for the in-sentence Chinese punctuation; keep half-width for embedded English/number/DOI tokens.

> Note: `^...^` / `~...~` render only when docx export uses pandoc with the `+superscript+subscript` extensions (a later completion item; see SKILL.md Phase 4). In plain Markdown preview they may show as literal carets/tildes — this is expected and the source markup is correct.

## 5. Figure Prompt Template

**Trigger:** Run ONCE after ALL sections in Phase 3 are complete (all sections in `completed_sections`).
Generate prompts for every entry in `figures/figure_index.md`. Write output to `figures/figure_prompts.md`.

```
[FIGURE PROMPT — Figure N: <title>]
TYPE: Schematic | Conceptual overview | Data plot | Workflow | Mechanistic pathway
SUBJECT: <specific scientific content>
STYLE: BioRender style, scientific diagram, white background (#FFFFFF), publication-quality
COLOR SCHEME: Primary #2E86AB | Secondary #A23B72 | Accent #F18F01 | Neutral #4A4A4A | BG #FFFFFF
ELEMENTS:
  - <Element 1>: <shape, position, connections>
  - <Element 2>: ...
LAYOUT: <Single/Multi-panel> | <aspect ratio> | reading direction left→right
TYPOGRAPHY: Sans-serif (Arial/Helvetica), 8-10pt labels, English only
KEY MESSAGE: <one sentence>
AVOID: 3D effects, drop shadows, gradients, decorative borders, excessive text
```

## 6. Future Directions / Open Questions Template (Phase 4 Step 5b)

Required format for the structured "Future Directions" section. ≥3 items, each with gap reason + breakthrough path:

```markdown
## Future Directions and Open Questions

**1. [Direction title]**
Current knowledge gap: [why it cannot be answered now]. Recommended approach: [specific method/resource/data type].

**2. [Direction title]**
Current knowledge gap: [...]. Recommended approach: [...].

**3. [Direction title]**
Current knowledge gap: [...]. Recommended approach: [...].
```

Rules:
- ≥3 specific, actionable directions (not "further studies are needed")
- Each item must explain *why* current knowledge cannot answer it
- Each item must name a concrete breakthrough path (specific method/technology/data)
- Must correspond to arguments already established in the body — no new concepts

## 7. Manuscript Metadata Block (Phase 4 Step 5c)

Append to end of `exports/Final_Review.md` before export:

```markdown
---
## Manuscript Metadata
- Search cutoff date: [YYYY-MM-DD — the date of the final search run]
- Databases searched: [e.g., PubMed, arXiv, Google Scholar] (see data/search_log.json for full log)
- Conflicts of interest: [author statement — ask user to provide, default: "None declared"]
- Funding: [funding statement — ask user to provide, default: "Not specified"]
```

> search_log.json was populated by `append-search-log` calls during Phase 2. If search_log.json is absent, reconstruct dates from git log.
