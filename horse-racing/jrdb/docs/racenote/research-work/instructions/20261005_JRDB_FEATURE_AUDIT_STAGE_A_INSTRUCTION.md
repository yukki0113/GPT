# JRDB Feature Audit — Stage A Instruction

Status: READY FOR EXECUTION  
Date: 2026-10-05  
Research lane: RaceNote 0.5.x candidate research  
Active prediction cohort: v0.4.6 unchanged

## Objective

Create a source-traceable inventory of JRDB-derived features that could matter to RaceNote prediction.

Answer:

1. What relevant JRDB/PACI and derived Analysis fields exist?
2. Which reach RaceNote?
3. Which reach the clean Reader used by v0.4.6?
4. Which are raw vs derived/composite?
5. Which fields appear semantically overlapping?
6. Which potentially useful fields exist but are currently hidden?

Stage A is structural only. Do not tune predictive weights or modify active v0.4.6 behavior.

## Trace scope

Trace fields through:

```text
JRDB raw / PACI
-> parser / normalized representation
-> Analysis / derived data
-> RaceNote evidence
-> Reader View
-> v0.4.6 clean Reader
```

Include numeric indices, ability/performance measures, training/condition measures, pace/position measures, class/level indicators, suitability/context fields, jockey/trainer/stable information, pedigree-derived information and JRDB composite ratings available to the project.

## Required inventory columns

At minimum:

| field_id | display_name | category | source_record | source_field | raw_or_derived | derivation_source | current_racenote_exposure | current_reader_exposure | current_v046_visible | semantic_notes | overlap_candidates |
|---|---|---|---|---|---|---|---|---|---|---|---|

Classify each field as one of:

- CURRENT_VISIBLE
- CURRENT_HIDDEN
- DERIVED_VISIBLE
- DERIVED_HIDDEN
- UNKNOWN_LINEAGE
- LEGACY_ONLY

These statuses describe lineage/exposure only, not predictive quality.

## Non-goals

Do not:

- change the v0.4.6 Reader or prediction logic;
- add a composite score;
- optimize weights;
- use 2026 BTDAY outcomes for feature selection;
- run a long historical performance sweep;
- classify fields as useful/useless from intuition alone.

## Historical horizon for later stages

Stage A itself requires no outcome analysis.

Stage B must start with **2023-2025**.

Only if that result is inconclusive because of sample size, instability or weak separation may Stage B2 extend to **2021-2025**.

If five years still show no stable practical signal, stop. Do not keep widening the period. Record that no robust fixed feature priority was established and retain the 0.4.x Human-Context approach.

## Deliverables

Create:

1. a machine-readable feature inventory;
2. a Markdown Stage A report in `../reports/`;
3. any focused lineage utility required for reproducibility;
4. deterministic checks/tests where practical.

The report must include:

- field counts by category/status;
- current v0.4.6 visible feature summary;
- hidden-but-available candidate summary;
- obvious overlap groups;
- unresolved lineage items;
- repository artifacts changed;
- relevant commit SHA(s);
- recommendation for the Stage B input set, without ranking predictive quality.

## Acceptance criteria

Stage A is acceptable only if:

- inventory generation is reproducible;
- current Reader exposure is distinguished from merely existing JRDB fields;
- derived/composite fields are identified;
- unknown lineage is reported rather than guessed;
- v0.4.6 prediction behavior is unchanged;
- the report is sufficient to design Stage B without reconstructing the implementation chat.
