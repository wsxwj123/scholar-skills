# Systematic Review Mode — Methodology Reference

> Loaded only when `Review type = systematic` (Phase 0). Adds PRISMA-2020 rigor on top of
> the normal Write-Mode phase flow. Narrative/scoping reviews ignore this file entirely.
>
> Scope boundary: this mode supports a **methodologically rigorous systematic review**
> (PRISMA flow + RoB + optional meta-analysis + GRADE). It does NOT auto-register a
> PROSPERO protocol or run a statistical meta-analysis engine — the AI produces the
> *data and structured tables*; numeric pooling (if requested) is delegated to the
> matplotlib/seaborn skill (forest/funnel) or to the user's stats tool (R `metafor`,
> Python `statsmodels`/`PythonMeta`). If the user needs PROSPERO registration, tell them
> to register at https://www.crd.york.ac.uk/prospero/ before screening — this skill does
> not submit registrations.

---

## 1. PRISMA 2020 Flow (4 stages)

Record record counts **n** at every stage and persist them with `state_manager.py`
(`set-screening-counts`). These 5 numbers ARE the PRISMA flow-diagram data.

| Stage | What it counts | state field |
|-------|----------------|-------------|
| **Identification** | Records found across all databases + other sources (registers, citation chasing) | `identified` |
| ↳ after dedup | Records remaining after duplicates removed | `deduplicated` |
| **Screening** | Records screened on title/abstract | `screened` |
| ↳ excluded | Records excluded at screening (with reason tally) | `excluded` |
| **Eligibility** | Full texts assessed → see exclusions-with-reasons table below | (covered by `screened`/`excluded`) |
| **Included** | Studies included in qualitative synthesis (and, if applicable, meta-analysis) | `included` |

Sanity invariants the AI must self-check before Phase 4:
- `deduplicated ≤ identified`
- `screened ≤ deduplicated` (or `==`, if no pre-screening removal)
- `included ≤ screened`
- `excluded` ≈ `screened − included − (full-texts not retrieved)`

**Exclusions-with-reasons table** (mandatory at eligibility stage):

```markdown
| Exclusion reason            | n  |
|-----------------------------|----|
| Wrong population            | .. |
| Wrong intervention/exposure | .. |
| Wrong outcome               | .. |
| Wrong study design          | .. |
| Full text not retrievable   | .. |
| Duplicate / preprint of incl| .. |
```

**PRISMA flow-diagram data block** — emit this so it can be rendered (text or, if the user
opts into figures, a flow diagram):

```
Identification:  identified = N   →  duplicates removed = (identified − deduplicated)
Screening:       screened = N     →  excluded = N
Eligibility:     full-text assessed = N → excluded-with-reasons = N (see table)
Included:        included = N (studies in synthesis); of which in meta-analysis = N
```

---

## 2. Inclusion / Exclusion Criteria — PICO / PECO Registration

Register **before** screening. Write to `outline.md` under an `## Eligibility (PICO/PECO)` block.

- **PICO** (intervention questions): Population · Intervention · Comparator · Outcome.
- **PECO** (exposure / observational questions): Population · Exposure · Comparator · Outcome.
- Add explicit study-design filter (e.g. "RCTs only" vs "RCTs + cohort"), language limits,
  date window, and publication-status rule (include/exclude preprints, grey literature).

```markdown
## Eligibility (PICO/PECO)
- P: ...
- I/E: ...
- C: ...
- O (primary): ...   O (secondary): ...
- Designs included: RCT / cohort / case-control / ...
- Date window: ....–....   Languages: ...   Preprints: include? yes/no
- Inclusion: <bullet list of must-haves>
- Exclusion: <bullet list of disqualifiers, mapped to the reasons table in §1>
```

---

## 3. Risk of Bias (RoB) — per-study appraisal

Assess **every included study**. Pick the tool by design:

| Study design | RoB tool | Domains | Per-study verdict |
|--------------|----------|---------|-------------------|
| RCT | **RoB 2** | randomization · deviations from intended interventions · missing outcome data · outcome measurement · selective reporting | Low / Some concerns / High |
| Non-randomized / observational | **ROBINS-I** | confounding · selection · classification of interventions · deviations · missing data · outcome measurement · selective reporting | Low / Moderate / Serious / Critical / No information |

Output a **per-study RoB table** (one row per study, one column per domain + overall):

```markdown
| Study (gid)  | D1 | D2 | D3 | D4 | D5 | (D6 D7) | Overall |
|--------------|----|----|----|----|----|---------|---------|
| Smith2023 [3]| L  | L  | SC | L  | L  |         | Some concerns |
```
Domain codes: RoB 2 → L / SC / H ; ROBINS-I → L / M / S / C / NI.

This table is the data source for a RoB "traffic-light" figure if the user opts into figures.

---

## 4. Meta-analysis (OPTIONAL — only if user requests pooling)

Only when (a) ≥2 studies report the same outcome on a comparable scale AND (b) the user
explicitly asks to pool. Otherwise stay qualitative.

**Effect measures** (pick by outcome type):

| Outcome type | Effect size |
|--------------|-------------|
| Binary | OR (odds ratio) / RR (risk ratio) / RD |
| Continuous, same scale | MD (mean difference) |
| Continuous, different scales | SMD (standardized mean difference, Hedges' g) |

**Heterogeneity:** report Cochran's **Q** (with p) and **I²** (0–100%).
Rough I² bands: <25% low · 25–50% moderate · 50–75% substantial · >75% considerable.
High heterogeneity → use random-effects (DerSimonian–Laird / REML) and explain sources
(subgroup / meta-regression / sensitivity).

**Figure data** (hand off to matplotlib/seaborn skill if user opts into figures):
- **Forest plot:** per-study effect + 95% CI + weight; pooled diamond; I²/Q annotation.
- **Funnel plot:** effect vs. standard error; Egger's test for small-study/publication bias
  (only meaningful with ≥10 studies).

The skill does NOT compute the pooled estimate itself — produce the structured per-study
effect table and tell the user which engine to run (R `metafor`, Python `PythonMeta`/`statsmodels`).

---

## 5. GRADE — certainty of evidence (per outcome)

Rate certainty **per outcome**, not per study. Start point: RCT evidence = High; observational = Low.

Final rating: **High / Moderate / Low / Very low.**

**Downgrade** (−1 or −2 each): risk of bias · inconsistency (high I²) · indirectness ·
imprecision (wide CI / few events) · publication bias.
**Upgrade** (observational only): large effect · dose-response · all plausible confounding
would reduce the observed effect.

Output a **Summary of Findings (SoF)** table:

```markdown
| Outcome | N studies (n participants) | Effect (95% CI) | Certainty (GRADE) | Reason for rating |
|---------|----------------------------|-----------------|-------------------|-------------------|
| ...     | 5 (1,240)                  | RR 0.78 (0.66–0.92) | ⊕⊕⊕⊝ Moderate | downgraded for inconsistency (I²=58%) |
```

---

## 6. Phase wiring (how this overlays the normal flow)

- **Phase 0:** Review type = systematic → register PICO/PECO (§2) into `outline.md`;
  remind user about optional PROSPERO registration.
- **Phase 2 (search):** after each search/dedup pass, update counts:
  ```bash
  python3 scripts/state_manager.py set-screening-counts --identified N --deduplicated N
  python3 scripts/state_manager.py set-screening-counts --screened N --excluded N --included N
  python3 scripts/state_manager.py get-screening-counts   # verify
  ```
  Maintain the exclusions-with-reasons table (§1) alongside the index.
- **Phase 3 (write):** build the RoB table (§3) and, if pooling, the per-study effect table (§4).
- **Phase 4 (export):** emit PRISMA flow-diagram data block (§1), RoB summary, SoF/GRADE
  table (§5); if user opted into figures, generate forest/funnel/RoB/PRISMA-flow code via
  the matplotlib/seaborn skill (see SKILL.md "配图 opt-in").
