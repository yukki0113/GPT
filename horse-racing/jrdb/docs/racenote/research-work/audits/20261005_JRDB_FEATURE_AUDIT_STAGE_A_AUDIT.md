# JRDB Feature Audit — Stage A Audit

Date: 2026-10-05  
Reviewed commit: `21f7c58116bbc8ee75f1d05ccfebb60ae66f0821`  
Decision: **ACCEPT_WITH_NOTES**

## 1. Conclusion

Stage A is accepted as a sufficient structural basis for the first historical audit.

The work satisfies the important Stage A goals:

- active v0.4.6 prediction behavior was not changed;
- JRDB/PACI -> RaceNote -> Reader exposure was separated from mere source availability;
- 41 conceptual feature groups were catalogued;
- current-visible, hidden, derived and unknown-lineage states were distinguished;
- market fields were correctly identified as present pre-bind but excluded from the clean v0.4.6 Reader;
- obvious overlap families were documented without prematurely declaring redundancy;
- the inventory generator is reproducible against a committed clean Reader witness.

Proceed to Stage B, subject to the notes below.

## 2. Accepted findings

The inventory contains 41 conceptual rows:

- 37 confirmed visible in the v0.4.6 clean Reader;
- 4 not confirmed visible;
- 2 explicitly left as `UNKNOWN_LINEAGE`.

The most relevant direct JRDB families for the next stage are already identifiable:

- IDM / total / information / jockey / stable / longshot indices;
- jockey expected top-two rate;
- JRDB class and marks;
- running style and suitability categories;
- pace/position indices and ranks;
- projected positions;
- start index / late-break rate;
- KYI training index / arrow / qualitative condition;
- CHA workout clocks and clock indices;
- CYB training/condition analysis;
- farm rank/index information.

This is sufficient to design a focused three-year feature audit.

## 3. Notes before Stage B

### A. Conceptual rows must be expanded to scalar leaves

Stage A intentionally groups related values, for example:

- `horse.pace_indices` contains four numeric axes;
- `horse.pace_ranks` contains four ranks;
- `horse.forecast_positions` contains multiple order/margin/lane dimensions;
- `horse.workout` contains clocks and several clock indices;
- `horse.training_analysis` contains counts plus multiple indices.

Stage B must not score these groups as one feature.

Each analyzable numeric/ordinal leaf must receive a stable feature id and be evaluated independently.

### B. Separate candidate features from stratification/context fields

Race surface, distance, class, age/sex, venue and similar fields are important for stratification but are not themselves the first-stage "JRDB index quality" candidates.

Stage B should primarily audit direct pre-race JRDB numeric/ordinal/categorical ratings. Race/context fields should be used to define broad slices.

### C. Do not make hidden target-day market a candidate feature

Final odds/popularity and payouts may be used only as post-race evaluation labels/controls for:

- market independence;
- ROI;
- popularity-stratified lift.

They must not become predictor inputs or be exposed to the active v0.4.6 Reader.

### D. Coverage must be measured before full aggregation

The Stage A witness proves schema-path exposure, not 2023-2025 historical availability.

Stage B must first report, per scalar candidate:

- available rows;
- missing rate;
- covered races;
- covered years;
- source family coverage.

No silent imputation or fallback to another feature is allowed.

### E. Stage A report commit reference is stale

The report's "Relevant commit SHA" records the starting HEAD
`537bed7945deff65d0543dc108483c29e56f858f`, while the submitted Stage A work is commit
`21f7c58116bbc8ee75f1d05ccfebb60ae66f0821`.

This is a documentation/provenance note only and does not invalidate the inventory.

### F. Stage A is a reviewed conceptual inventory, not byte-exhaustive PACI documentation

The generator uses a curated `ROWS` catalog and explicitly leaves optional PACI record-family exhaustiveness unresolved.

That is acceptable for the current research purpose. Stage B must not claim that unlisted PACI fields were proven useless or absent.

## 4. Stage B scope decision

Do **not** analyze all 41 conceptual rows equally.

Primary Stage B scope:

**direct pre-race JRDB-provided ratings / indices / ordinal evaluations that are visible to v0.4.6 or are part of the same current PACI evidence surface.**

Defer as separate research families:

- free-text comments;
- horse/jockey/trainer identity strings;
- RaceNote historical-profile aggregates;
- race trends;
- pedigree-context aggregates;
- older-run containers as whole objects;
- unknown-lineage optional PACI fields.

Past-run JRDB metrics may be used later as lag/history features, but they should not be mixed into the first current-race index audit.

## 5. Historical window decision

Stage B uses only:

**2023-01-01 through 2025-12-31**

Do not automatically extend to five years.

After Stage B report/audit:

- if sample/coverage/stability is genuinely inconclusive, issue a separate Stage B2 instruction for 2021-2025;
- if three years already show clear stable behavior, proceed toward Stage C;
- if three years show weak behavior but sample is already ample, do not assume that more years will rescue it.

## 6. Next canonical instruction

Proceed with:

`docs/racenote/research-work/instructions/20261005_JRDB_FEATURE_AUDIT_STAGE_B_INSTRUCTION.md`

Active v0.4.6 prediction logic remains unchanged throughout Stage B.
