# RaceReviewDB Next-Watch Backtest Input Contract v0.1

Status: READY
Date: 2026-09-25
Repository: yukki0113/GPT
Component: RaceReviewDB Next-Watch Backtest
Checkpoint: BACKTEST_INPUT_CONTRACT_READY

## 1. Purpose

This file freezes the Turn 1 input contract for the RaceReviewDB Next-Watch
backtest.

The contract defines canonical sources, keys, date coverage, source
responsibilities and the boundary between Phase 1 ability validation and Phase 2
market-value validation.

## 2. Canonical RaceReviewDB source

Stable Drive object:

- file: RaceReviewDB_CURRENT.zip
- Drive file ID: 1UwNfrupMTHRPhkzULPvClGre4MWz2TFg

Observed generation:

jrdb_race_review_v0_1_incremental_g36094708797

Observed accepted period:

2010-01-05 through 2026-09-22

Observed relation counts:

- fact_race_context: 57,830
- fact_race_review: 57,830
- fact_horse_performance: 816,536
- fact_track_bias: 169,752

RaceReviewDB is the primary source for source-race features, stable horse
identity and next-start Phase 1 outcomes.

## 3. Canonical current raw sources

Canonical PACI folder:

- path: horse-racing/00_raw/PACI
- Drive folder ID: 1zFajenPU5jxInZCcmqZzkgiaYil3MD8r

Canonical SED folder:

- path: horse-racing/00_raw/SED
- Drive folder ID: 1mm6sU8-skS7K2XYHm2citcorUVyMyL58

The folders share the same current JRDB raw parent and are the sources already
used by RaceReviewDB incremental operation.

For 2026-05 through 2026-09-22, the observed PACI and SED daily archive names
match date-for-date.

Observed dates:

2026-05:
- 05-02, 05-03, 05-09, 05-10, 05-16, 05-17, 05-23, 05-24, 05-30, 05-31

2026-06:
- 06-06, 06-07, 06-13, 06-14, 06-20, 06-21, 06-27, 06-28

2026-07:
- 07-04, 07-05, 07-11, 07-12, 07-18, 07-19, 07-25, 07-26

2026-08:
- 08-01, 08-02, 08-08, 08-09, 08-15, 08-16, 08-22, 08-23, 08-29, 08-30

2026-09 through CURRENT:
- 09-05, 09-06, 09-12, 09-13, 09-19, 09-20, 09-21, 09-22

Total observed current-period date pairs for the backtest window: 44.

## 4. Source responsibilities

### RaceReviewDB

Use for:

- source race features
- horse_id
- race_key
- race_horse_key
- race_date
- finish
- next-start chronological mapping
- next-start Phase 1 finish outcomes
- historical self-comparison using only earlier starts

Primary source relation:

fact_horse_performance

Supporting relations:

- fact_race_review
- fact_race_context
- fact_track_bias

### Canonical SED sidecar

Use for source facts that are parsed by JRDB but are not persisted in the
RaceReviewDB v0.1 fact_horse_performance schema.

The current RaceReview source adapter explicitly projects:

- blood_registration_no
- horse_no
- finish
- abnormal_code
- final_win_odds
- final_popularity
- race_type_code
- race_class_code
- grade_code
- completed result metrics

Therefore canonical SED is the authoritative sidecar for:

- normal / abnormal result eligibility
- race-type filtering when needed
- next-start final popularity
- next-start final win odds

It may also be used as a key-level cross-check against RaceReviewDB.

### PACI

PACI is not required as a primary backtest table when the needed Review facts
are already persisted.

It remains the canonical supporting source if a future candidate feature
requires BAC/KYI context that is not persisted in RaceReviewDB.

No extra PACI feature should be silently added during v0.1 without a versioned
contract update.

## 5. Stable keys

Horse identity:

horse_id = JRDB blood_registration_no

Race identity:

race_key = raw 8-character JRDB race key

Horse-start identity:

race_horse_key = race_key + zero-padded horse_no

Backtest source key:

source_race_horse_key = race_horse_key

Next-start target key:

target_race_horse_key = the chronologically immediate later race_horse_key for
the same horse_id.

Horse name is descriptive only and must never be used to resolve the next start.

## 6. Next-start mapping contract

For each eligible source horse-start:

1. select rows with the same non-empty horse_id,
2. require target race_date > source race_date,
3. order by race_date then race_key then horse_no,
4. choose exactly the first later start,
5. retain source_race_horse_key and target_race_horse_key explicitly.

The target is the horse's next recorded JRA start in RaceReviewDB, not the next
start within the Discovery/Holdout calendar subset.

A source row may remain without a target when the horse does not start again by
RaceReviewDB CURRENT period_to.

Missing target is not an error. It is a censored / unresolved observation and
must be reported separately.

## 7. Leakage contract

Source features may use:

- the source horse-start itself
- races strictly earlier than source race_date

Source historical comparisons must not use:

- later races
- the target next start
- same-day future ordering assumptions

Target result fields must be joined only after the source feature fact is
materialized.

Discovery:

2026-05-01 through 2026-07-31 source dates

Holdout:

2026-08-01 through 2026-09-22 source dates

A Holdout source row can only have a resolved target if that next start exists
within CURRENT coverage through 2026-09-22. Late-Holdout rows will therefore
have higher right-censoring and must not be treated as failures.

## 8. Eligibility fields

RaceReviewDB remains the feature source, but exact eligibility filtering may use
SED sidecar fields because v0.1 does not persist every raw-result qualifier.

Initial eligibility should use, where available:

- non-empty horse_id
- normal completed result
- flat-race classification
- valid source race date
- unique race_horse_key

Do not infer a normal result solely from finish when canonical SED
abnormal_code is available.

Do not infer flat/jump status from an undocumented heuristic if canonical
race-type evidence is available.

## 9. Phase 1 outcome contract

Phase 1 does not require odds or payout data.

Required target outcomes:

- next_finish
- next_win
- next_top3
- next_top5
- finish_improvement
- days_to_next_start

Primary source:

RaceReviewDB target fact_horse_performance row.

Phase 1 can therefore be completed from RaceReviewDB plus SED eligibility
sidecar without a payout source.

## 10. Phase 2 market contract

Confirmed available from canonical SED:

- final_popularity
- final_win_odds

These allow:

- popularity-aware validation
- market expectation comparisons
- odds-conditioned analysis

They do not by themselves establish actual realized payout/return for every
bet type.

Turn 1 did not identify and validate a canonical payout source.

Therefore:

- popularity / final win odds: AVAILABLE
- realized win/place return: NOT YET CONTRACTED

ROI or payout-based conclusions must remain blocked until a canonical payout
source is identified and audited in Turn 7 or an earlier explicit contract
update.

## 11. Join contract between RaceReviewDB and SED

Preferred exact join:

- race_key
- horse_no

Equivalent persisted key:

- race_horse_key

Horse ID must be cross-checked when available.

For a joined row:

RaceReviewDB horse_id must equal SED blood_registration_no unless one side is
documented missing. A non-empty disagreement is a hard audit error.

Date must agree between RaceReviewDB race_date and SED result date.

Duplicate SED result keys are hard errors.

## 12. Turn 2 source scope

Turn 2 should build one candidate feature dataset from source dates:

2026-05-01 through 2026-09-22

It should not yet score rules.

Recommended acquisition strategy:

1. download RaceReviewDB CURRENT once,
2. materialize the necessary RaceReviewDB relations locally,
3. acquire only the 44 SED daily archives in the backtest window as the
   eligibility / market sidecar,
4. persist normalized SED sidecar once,
5. build candidate_signals Parquet,
6. audit and reuse the checkpoint in later turns.

PACI does not need to be re-downloaded for Turn 2 unless a missing feature is
explicitly approved.

## 13. Required Turn 2 audits

At minimum record:

- source date min/max
- source row count
- unique source_race_horse_key count
- duplicate source_race_horse_key count
- empty horse_id count
- RaceReviewDB/SED join match count
- RaceReviewDB/SED horse_id mismatch count
- abnormal-result exclusions
- non-flat exclusions
- Discovery row count
- Holdout row count
- per-date row counts

No rule outcome should be interpreted before these audits PASS.

## 14. Turn 1 result

Status:

PASS

Checkpoint:

BACKTEST_INPUT_CONTRACT_READY

No RaceReviewDB production data was modified.

The only production-side change is documentation of this backtest input
contract.
