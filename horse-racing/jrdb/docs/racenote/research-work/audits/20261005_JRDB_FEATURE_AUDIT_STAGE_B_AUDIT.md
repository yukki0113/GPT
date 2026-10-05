# JRDB Feature Audit — Stage B Audit

Date: 2026-10-05  
Source: user-supplied Stage B artifact bundle  
Bundle SHA-256: `fabe407d06e31bd90f3d73a9068541581c961066abc8da4c5f246e39375ba0d1`  
Decision: **ACCEPT**

## 1. Conclusion

Stage B is accepted.

The supplied artifacts satisfy the intended three-year audit scope and support
`PROCEED_STAGE_C`.

No Stage B2 five-year extension is warranted.

The 2023-2025 sample is already large:

- 10,365 races;
- 142,737 runner entries;
- 141,523 valid-result entries;
- 73 scalar leaves derived from the Stage A inventory.

The active v0.4.6 Reader and prediction logic were not modified.

## 2. Integrity / scope checks

Confirmed from the supplied report, machine outputs and pipeline source:

- target window is 2023-01-01 through 2025-12-31 only;
- 2026 BTDAY outcomes are not used;
- pre-race source families are BAC / KYI / CHA / CYB;
- SED is joined as outcome / payout / final-popularity evaluation data only;
- no SED value is used to populate a feature;
- scalar coverage is written before outcome aggregation;
- missing values are not silently imputed;
- yearly 2023 / 2024 / 2025 views are preserved;
- market-popularity analysis is descriptive control only;
- no predictive model, optimized score or threshold search was introduced.

The Python pipeline compiles successfully.

## 3. Main findings accepted for Stage C

### Strong but market-aligned / overlapping

The following show strong, monotonic raw outcome separation across all three
years, but are also strongly aligned with final popularity and/or one another:

- IDM;
- total index;
- information index;
- jockey index;
- jockey expected top-two rate;
- KYI training index.

Examples from the combined 2023-2025 within-race quintile view:

- IDM strongest-vs-weakest win-rate gap: about 17.83 points;
- total index: about 19.46 points;
- information index: about 19.77 points;
- jockey index: about 20.25 points;
- jockey expected top-two rate: about 20.53 points;
- KYI training index: about 20.14 points.

These are useful information signals, but not evidence for a new fixed betting
score. The strongest buckets still have negative final-payout ROI.

### Moderate, less market-aligned signals

The most interesting secondary family is the pace / condition layer.

Examples:

- pace late index: about 10.28-point strongest-vs-weakest win-rate gap;
- CHA last clock index: about 5.61 points;
- CYB condition index: about 6.66 points.

Their raw separation is smaller than the leading composites, but some are less
tightly aligned with final popularity. These deserve preservation as
contextual evidence rather than being discarded merely because their headline
win rate is lower.

### Clear redundancy candidates

Observed redundancy is strong enough to justify a Reader-presentation review:

- CHA total clock index vs CYB training index:
  Spearman 1.000, top-1 overlap 1.000, top-3 overlap 1.000;
- jockey index vs jockey expected top-two rate:
  Spearman about 0.989, top-1 overlap about 0.959;
- IDM vs total index:
  Spearman about 0.952;
- provider pace numeric values and corresponding supplied ranks:
  effectively near-identical ordering;
- projected order and projected margin fields:
  very high within-race ordering overlap.

Stage C should reduce duplicate cognitive weight, not erase provenance.

### Weak / unstable candidates

The following do not justify elevated Reader priority from the three-year
evidence:

- start index;
- late-break rate;
- CHA front clock index;
- CHA middle clock index.

They may remain contextual facts, but should not be presented to the model as
co-equal headline evidence without a specific race reason.

### Coverage limits

Some suitability values have substantial missingness and must not be treated as
general all-runner ranking features.

CYB training grade has no usable three-year coverage.

## 4. Why Stage B2 is not requested

The original extension rule was to add 2021-2022 only when 2023-2025 was
genuinely inconclusive because of insufficient sample or unstable direction.

That condition is not met.

The principal numeric families have large samples and repeated yearly
direction. Extending to five years would mainly increase historical volume,
not resolve an identified ambiguity.

Proceed directly to Stage C.

## 5. Stage C principle

Stage C must not convert these findings into fixed numeric weights.

The preferred question is:

> How should the Reader present the same underlying evidence with less
> duplication and clearer information priority, while preserving Human-Context
> judgment?

The active v0.4.6 cohort remains untouched until an explicit 0.5.x candidate
Reader is separately designed and validated.

## 6. Canonical next instruction

Proceed with:

`docs/racenote/research-work/instructions/20261005_JRDB_FEATURE_AUDIT_STAGE_C_INSTRUCTION.md`
