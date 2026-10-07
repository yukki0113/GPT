# 20261007_002 — EdgeDB v0.5 Prototype Scientific Correction + ROI Gate

Status: TODO / CORRECTIVE FOLLOW-UP  
Date: 2026-10-07  
Design authority: ChatGPT  
Execution worker: Codex  
Target PR: #1871  
Production impact: NONE

## Objective

Correct the first v0.5 prototype implementation from instruction 001 before merge.

This task must preserve the healthy execution foundation from PR #1871 while fixing the scientific semantics and review gate so the output behaves like a useful TARGET-style memo discovery system rather than a broad condition-statistics enumerator.

Continue on PR #1871. Do not open a new superseding PR unless the existing branch becomes unusable.

---

## Required reading

Before changes, read:

- `horse-racing/jrdb/docs/edgedb/v0_5/EdgeDB_v0_5_Niche_Value_Memo_Discovery_Design_20261007.md`
- `horse-racing/jrdb/docs/edgedb/v0_5/collab/instructions/20261007_001_t1_t6_2024_2025_prototype_aggregation_instruction.md`
- current PR #1871 diff and result report
- PR #1871 review comment from ChatGPT
- `horse-racing/jrdb/src/jrdb_raw.py`
- canonical Warehouse/Analysis/Feature Mart manifests and resolvers
- `tools/data-storage/README.md`
- `tools/data-storage/docs/CODEX_LOCAL_FIRST_ACTIONS_FALLBACK.md`

---

## 1. Core scientific correction: separate Performance and Value labels

The current prototype stores performance and return metrics separately but conflates them again in research labels.

Current incorrect behavior:

```
parent_delta.place_rate > 0
-> NICHE_VALUE_POSITIVE
```

and:

```
parent_delta.place_rate < 0
-> NICHE_VALUE_NEGATIVE
```

This is not acceptable.

A higher place rate is Performance evidence, not automatically betting Value.

### Required label separation

Introduce explicit occurrence/performance labels such as:

- PERFORMANCE_POSITIVE
- PERFORMANCE_NEGATIVE

These may use:

- place_rate
- win_rate
- parent-relative place-rate delta
- parent-relative win-rate delta

Keep these separate from betting-value labels.

### Positive Value label

For this v0.5 prototype, the primary positive Edge adoption gate is intentionally simple:

> **2024-2025 place ROI >= 100%**

with:

> **n >= 5**

Therefore:

```
NICHE_VALUE_POSITIVE
iff
overall_2024_2025.place_roi >= 100
AND overall_2024_2025.n >= 5
```

This is the canonical first-pass positive adoption gate for instruction 002.

Do not add a significance test requirement.
Do not require ROI excluding top1 to remain >=100.
Do not require both 2024 and 2025 individually to exceed 100.

### Why this gate exists

The purpose is to stop signal flooding.

The v0.5 positive Edge shortlist should answer:

> In the current 2024-2025 regime, did this condition at least return 100 yen or more per 100 yen place stake when all qualifiers are counted?

This is a strict presentation/adoption gate, not a claim that the condition is a standalone betting strategy.

### ROI strength band

Attach a simple descriptive strength band:

- VALUE_100_119
- VALUE_120_149
- VALUE_150_PLUS

Do not use the band to alter candidate membership.

### One-hit / jackpot rule remains unchanged

A candidate such as:

```
n=5
places=1
place payout=810
place ROI=162
```

must still pass the positive Value gate.

Do not reject it because:

- place ROI ex top1 = 0;
- top1 contribution = 100%;
- only one longshot caused the profit.

Instead retain labels such as:

- MICRO
- LONGSHOT_EVIDENCE
- ONE_BIG_HIT
- NICHE_VALUE_POSITIVE
- VALUE_150_PLUS

This is intentional.

---

## 2. Negative Edge remains a separate lane

Do not define negative Edge as merely:

```
place ROI < 100
```

That would make most ordinary conditions negative and recreate signal flooding.

Negative Edge means:

> a condition that gives a meaningful reason to downgrade/re-check a horse relative to a natural parent/context.

For instruction 002, keep negative classification conservative and explicit.

Suggested initial gate:

- n >= 5;
- parent comparison available;
- both:
  - place_rate materially below parent; and
  - place_roi below parent;
- avoid labeling tiny floating-point differences as negative.

Use a simple frozen threshold for prototype review, for example:

```
delta_place_rate <= -0.03
AND delta_place_roi <= -20 percentage points
```

If implementation evidence shows a different simple threshold is materially more appropriate, document it before executing and do not tune it to cherry-pick named sires.

Negative Edge is not required to have place ROI below any absolute universal threshold.

Keep:

- PERFORMANCE_NEGATIVE
- NICHE_VALUE_NEGATIVE

as distinct labels.

---

## 3. Review shortlist must use the ROI gate

The current result report selects "promising_positive" from positive place-rate delta and sorts by support size.

This produced broad, low-ROI T6 examples such as sire × turf × GOOD.

Replace this behavior.

### Positive shortlist eligibility

A candidate may enter the positive Value review shortlist only if:

```
n >= 5
AND place_roi_2024_2025 >= 100
```

### Preserve raw research table

Do not delete candidates below 100% place ROI from the raw candidate Parquet.

The 100% gate is for:

- adoption/review shortlist;
- eventual positive Edge publication consideration;
- signal-density control.

Raw research metrics remain available for diagnostics.

### Balanced shortlist

Do not sort all examples only by support size.

Produce balanced review examples across:

- T1 course × frame
- T2 sire × course
- T3 sire × distance extension/shortening
- T4 sire × surface switch / first surface when available
- T5 first blinkers when available
- T6 sire × surface × going

And across evidence types:

- positive Value
- longshot evidence
- EMERGING
- CURRENT
- MICRO positive Value
- saturated/obvious
- negative Edge
- redundancy example

If a family has no candidate meeting the positive ROI gate, state that explicitly instead of filling the slot with a low-ROI row.

---

## 4. Re-audit T5, FIRST_DIRT, FIRST_TURF

Instruction 001 allowed use of canonical:

- Feature Mart
- Warehouse
- Analysis

The first implementation blocked these features because they are absent from the frozen Feature Mart.

That is insufficient investigation.

### 4.1 FIRST_BLINKERS

Repository evidence:

- canonical KYI Warehouse annual Parquet exists for 2022-2025 and earlier;
- `jrdb_raw.Parser.kyi` parses `blinker_code`.

Required audit:

1. inspect KYI Warehouse Parquet schema for blinker_code;
2. verify horse identity field and chronology;
3. determine whether exact first-use semantics can be derived:
   - current race blinker active;
   - no prior known race for same horse with blinker active before target date;
4. verify no leakage;
5. report coverage.

If derivable, implement T5.

If not derivable, BLOCKED is acceptable only with the exact missing field/semantic documented.

Do not stop merely because Feature Mart lacks the column.

### 4.2 FIRST_DIRT / FIRST_TURF

Do not infer first surface from prev1 only.

Required audit:

1. identify canonical horse_id across historical starts;
2. inspect exact historical surface chronology;
3. derive:
   - FIRST_DIRT = current dirt and no earlier career dirt start;
   - FIRST_TURF = current turf and no earlier career turf start;
4. target race itself must not be included in prior-history check;
5. verify chronological coverage is sufficient.

Prefer canonical Warehouse/Analysis history.

If the historical source starts too late to prove true career-first for some horses, classify those rows as UNKNOWN and exclude them from first-surface membership rather than guessing.

If exact semantics remain impossible, document why.

---

## 5. Re-audit course topology

Current BLOCKED state may be valid, but complete the audit.

Repository facts already include:

- BAC `turn_code`
- BAC `layout_code`
- venue
- surface
- distance
- current Edge facts `turn_code`

Required:

1. search repository/JRDB metadata for an authoritative course layout map;
2. determine whether:
   `venue + surface + distance + layout/turn`
   can deterministically map to:
   - ONE_TURN
   - TWO_TURN
   - STRAIGHT
   - OTHER
3. do not infer topology from distance alone.

If no authoritative mapping can be established, keep BLOCKED and record the exact missing mapping source.

---

## 6. Candidate count / signal-density review

The raw n>=5 count of 7,303 is acceptable as research storage.

It is not acceptable as the effective Edge signal set.

After applying the positive Value gate and conservative negative gate, report:

- raw n>=5 candidates
- positive Value candidates:
  - place ROI >=100
  - n>=5
- positive Value by family
- positive Value by support class
- negative Edge candidates
- longshot-evidence positive candidates
- positive candidates after redundancy representative selection

The purpose is to measure whether the v0.5 gate actually reduces serving density.

Do not respond to high counts by raising minimum n above 5 unless explicitly instructed later.

---

## 7. Saturation / obvious-condition diagnostics

A condition can have:

- positive performance;
- but place ROI below 100.

That should not be called positive Value.

Use a descriptive state such as:

- PERFORMANCE_POSITIVE
- SATURATED_OR_PRICED

Example logic:

```
delta_place_rate > 0
AND place_roi < 100
```

This is useful for famous biases whose performance advantage is already priced into the market.

Do not surface these as positive Edge candidates.

---

## 8. Market diagnostics remain post-freeze only

No change to this rule.

Popularity/odds/payout may not define candidate membership.

The 100% place ROI gate is applied only after the pre-race condition group has been defined.

This is a review/adoption gate, not a candidate-generation condition.

Maintain tests proving:

- candidate ID/membership does not depend on popularity;
- candidate ID/membership does not depend on payout;
- candidate ID/membership does not depend on odds.

---

## 9. Freshness remains descriptive

Do not require:

- 2024 place ROI >=100;
- AND 2025 place ROI >=100.

The canonical gate is the combined 2024-2025 place ROI >=100.

Retain yearly values to classify:

- EMERGING
- CURRENT
- DECAYING
- VOLATILE
- etc.

Examples:

```
2024 = 72
2025 = 156
overall 2024-25 = 112
```

may pass and be labelled EMERGING.

```
2024 = 150
2025 = 65
overall = 104
```

may pass the Value gate but should carry DECAYING/VOLATILE warning.

The warning does not automatically remove the candidate in instruction 002.

---

## 10. Redundancy handling

Keep raw candidates.

For the positive Value shortlist:

- cluster high-overlap/nested candidates;
- choose one presentation representative;
- report suppressed candidate IDs.

Prefer the simplest human-readable representative when evidence is substantially equivalent.

Do not show three near-identical signals on the same horse merely because all three individually exceed ROI 100.

The review report must include:

- pre-cluster positive count
- post-cluster representative count
- largest clusters
- representative-selection rule

---

## 11. Required result report update

Update the existing result report in PR #1871 rather than creating a disconnected alternative report.

Required sections:

### A. Scientific correction

Document:

- old incorrect Value label rule;
- new Performance vs Value label separation;
- exact positive Value gate.

### B. Positive ROI gate effect

Table by T1-T6:

```
family
raw n>=5
place ROI >=100
MICRO/SMALL/MEDIUM/LARGE counts
LONGSHOT_EVIDENCE counts
post-redundancy representative count
```

### C. Positive Value examples

Show representative rows with:

- memo
- n
- places
- 2024-25 place ROI
- 2024 place ROI
- 2025 place ROI
- 2022-23 context place ROI
- largest place payout
- 5+/8+/10+ hit counts
- support class
- freshness
- parent performance delta
- value strength band
- redundancy status

### D. Negative examples

Show only candidates satisfying the conservative negative gate.

### E. Blocked-family re-audit

For:

- FIRST_BLINKERS
- FIRST_DIRT
- FIRST_TURF
- course topology

record:

- sources inspected;
- schemas/fields found;
- derivation attempted;
- PASS/BLOCKED;
- exact reason.

### F. Recommendation

Return one of:

- READY_FOR_RESEARCH_REVIEW
- PARTIAL_WITH_BLOCKED_FAMILIES
- SCIENTIFIC_OUTPUT_TOO_NOISY
- EXECUTION_BLOCKED

Do not publish/promote.

---

## 12. Required tests

Add/modify focused tests for:

1. positive Value gate:
   - n=5 and place ROI=100 => pass;
   - n=5 and place ROI=99.9 => fail;
   - n=4 and place ROI=500 => fail from positive shortlist;
2. one-hit candidate:
   - n=5, one 810-yen place payout => ROI 162 and pass;
   - ex-top1 ROI=0 must not invalidate it;
3. Performance label independence:
   - positive place-rate delta + ROI<100 => PERFORMANCE_POSITIVE but not NICHE_VALUE_POSITIVE;
4. saturated example:
   - performance positive + ROI<100 => SATURATED_OR_PRICED;
5. negative gate requires meaningful deterioration, not tiny delta;
6. 2024 and 2025 do not each have to exceed 100;
7. popularity/odds/payout do not alter candidate membership;
8. n>=5 support policy unchanged;
9. redundancy does not delete raw research rows;
10. if implemented:
   - FIRST_BLINKERS chronology;
   - FIRST_DIRT/FIRST_TURF chronology;
   - UNKNOWN history handling;
   - course topology mapping fixtures.

---

## 13. Execution route

Reuse the current deterministic implementation and artifact chain where practical.

If Warehouse enrichment requires Parquet/DuckDB:

1. local `.venv-data-storage`;
2. check-deps;
3. one normal repair attempt;
4. if blocked by managed proxy/network:
   - use `[DATA_STORAGE_FALLBACK]`;
5. inspect run/artifact/audit;
6. continue.

Do not replace canonical Parquet/DuckDB logic with ad-hoc pandas/SQLite because of local dependency restrictions.

---

## 14. PR handling

Continue PR #1871.

Before final review:

- resync with latest `main`;
- resolve current `mergeable=false`;
- keep production impact NONE;
- do not touch:
  - v0.2 STANDARD publication
  - v0.3 SHADOW publication
  - v0.4 OBSERVE_ONLY publication
  - `current_manifest.json`
  - RaceNote scoring
  - Newspaper/PWA serving

Do not merge PR #1871 yourself.

Return it for ChatGPT review.

---

## Acceptance gate

Instruction 002 is accepted only if:

1. Performance and Value labels are distinct;
2. positive Edge review/adoption gate is exactly:
   - n >= 5;
   - 2024-2025 place ROI >= 100%;
3. jackpot/top1 exclusion is diagnostic only;
4. a one-hit MICRO candidate can pass;
5. low-ROI performance-positive rows no longer appear as positive Value examples;
6. negative Edge is conservative and not equivalent to ROI<100;
7. T5/FIRST_DIRT/FIRST_TURF are audited against Warehouse/history, not blocked solely due to Feature Mart absence;
8. course topology receives a complete metadata audit;
9. raw 7,303-style research population is preserved while the effective Value shortlist is materially reduced;
10. redundancy is applied to the review/presentation layer;
11. tests pass;
12. PR #1871 is resynced and reviewable;
13. production remains unchanged.

---

## Non-goals

- no automatic betting strategy;
- no requirement for ROI ex-top1 >=100;
- no requirement for both years individually >=100;
- no increase of minimum support beyond n=5;
- no arbitrary deep-cross expansion;
- no popularity-conditioned candidate generation;
- no v0.5 publication;
- no PWA/RaceNote production migration.
