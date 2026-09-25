# RaceReviewDB Operation Contract v0.1

Status: OPERATIONAL FOUNDATION  
Date: 2026-09-25  
Repository: yukki0113/GPT

## 1. Purpose

RaceReviewDB is the canonical post-race review database for JRDB-based horse
racing projects.

The primary operational requirement is not historical completeness by itself.
The primary requirement is:

1. a completed race day can be appended safely,
2. the same horse can be resolved by stable identity at a later start,
3. downstream consumers can read the latest accepted Review without knowing
   generation-specific paths,
4. a failed update cannot silently replace the accepted CURRENT snapshot.

RaceNote, RL/Training Edge and other projects decide independently how Review
features affect their own prediction or presentation logic.

## 2. Canonical Drive location

Drive root:

horse-racing/20_mart/race_review/v0_1/

Folder IDs:

- race_review: 1VQzhVzdNAi4LvhDjcZB93IVa9RNzELpB
- v0_1: 13m2MGibjEHOvBY6LmENQat4PuTZGcdwc
- snapshots: 1RYzimRvz5KJ_HxtRcBpvbhpFy7KZTqSB

Stable consumer entrypoint:

- file name: RaceReviewDB_CURRENT.zip
- Drive file ID: 1UwNfrupMTHRPhkzULPvClGre4MWz2TFg

Consumers should depend on the stable Drive file ID, not on one immutable
generation file name.

## 3. Initial accepted snapshot

Historical foundation generation:

jrdb_postrace_review_v0_1_2010_2025_g36046073323

Source Warehouse:

jrdb_normalized_warehouse_v1_2010_2025_g20260921

Accepted period:

2010-01-05 through 2025-12-28

Initial row counts:

- fact_race_context: 55,268
- fact_race_review: 55,268
- fact_horse_performance: 781,161
- fact_track_bias: 162,624

The immutable initial snapshot is retained under Drive snapshots/.

## 4. Stable identity contract

### Horse

Primary identity:

horse_id = JRDB blood_registration_no

Downstream consumers must not join Review history by horse name.

Horse name is descriptive only.

### Race

Primary identity:

race_key = raw 8-character JRDB race key

### Race-horse

Primary identity:

race_horse_key = race_key + zero-padded horse_no

These identities are persisted in fact_horse_performance.

## 5. Consumer as-of contract

For a target race on target_date, the safe default is:

race_date < target_date

Same-day Review rows are excluded by default.

The reference implementation is:

src/jrdb_postrace_review_reader.py

Supported consumer operations include:

- metadata()
- horse_history(horse_id, before_date=...)
- histories_for_horses(horse_ids, before_date=...)
- race_review(race_key)

A missing horse history returns no rows. It must not fall back to name matching.

## 6. Incremental source

Current-period Review updates use completed PACI archives.

Canonical current PACI folder:

horse-racing/00_raw/PACI

Drive folder ID:

1zFajenPU5jxInZCcmqZzkgiaYil3MD8r

PACI parsing uses jrdb_raw.Parser. The incremental Review layer owns no
fixed-width byte offsets.

Required PACI relations:

- BAC
- KYI
- SED

SED is the primary completed-result evidence. BAC and KYI provide supporting
race/entry context.

## 7. Incremental update contract

Reference implementation:

src/jrdb_postrace_review_incremental.py

Workflow:

.github/workflows/jrdb-race-review-incremental.yml

Request issue prefix:

[JRDB_RACE_REVIEW_INCREMENTAL]

Request lines:

PACI|<Drive file id>|PACIyymmdd.zip

One request may contain one date or multiple chronological dates.

### Date rules

Let current_max be CURRENT manifest period_to.

Allowed:

- target_date > current_max
  - chronological append
- target_date == current_max
  - idempotent replacement of the current last date

Rejected:

- target_date < current_max
  - historical correction requires replay from the corrected date forward

This fail-closed rule prevents a correction to an old race from leaving later
derived standards and pace distributions inconsistent.

## 8. Incremental calculation

The updater does not rebuild the 2010-2025 Warehouse.

It seeds rolling Review history from persisted CURRENT relations:

- fact_race_review supplies winner time / class / venue / surface / distance
- fact_race_context supplies pace balance

Because the original historical operational seed does not persist all detailed
standard dimensions, incremental seeding uses the persisted broader standard
scopes when necessary. This is explicit fallback, not hidden imputation.

Each new date is processed before that date is added to rolling history.

Therefore a target race cannot affect its own historical standard or pace
percentile.

## 9. Date replacement

For every target race_date, all four relations are replaced atomically in the
staging DuckDB:

- fact_race_context
- fact_race_review
- fact_horse_performance
- fact_track_bias

The date is deleted first and the newly audited rows are inserted in one
transaction.

This makes retrying the last date idempotent.

## 10. Publication

After all requested dates are applied:

1. the complete staged database is audited,
2. year-partitioned ZSTD Parquet objects are produced,
3. immutable generation manifest/audit files are written,
4. current.json is promoted only after hard gates PASS,
5. the workflow uploads a complete next-snapshot artifact.

Drive synchronization then performs:

1. retain the new generation ZIP under snapshots/,
2. replace RaceReviewDB_CURRENT.zip bytes in place,
3. preserve the stable Drive CURRENT file ID.

The accepted CURRENT Drive ID therefore remains stable across generations.

## 11. Hard gates

Promotion fails on at least:

- duplicate race key
- duplicate race-horse key
- orphan horse -> race
- schema mismatch
- Review version mismatch
- non-finite persisted numerics
- standard future leakage
- missing immutable object
- Parquet schema/count/key re-read mismatch
- requested date mismatch
- historical correction without replay

Warnings do not silently become zero/neutral feature values.

## 12. Track bias status

fact_track_bias is available as a descriptive Review relation.

v0.1 operational updates keep adjusted/shrunk causal bias fields in shadow when
they are not calibrated.

This must not block adding the underlying race and horse Review rows.

## 13. Consumer responsibility

RaceReviewDB supplies evidence and derived Review facts.

It does not define:

- RaceNote prose policy
- RL weighting
- prediction feature weights
- duplicate-evidence handling inside another model
- UI presentation

Those are consumer-project responsibilities.

Consumers should record the RaceReviewDB generation_id used for reproducibility.

## 14. Operational completion criteria

RaceReviewDB v0.1 foundation is considered operational when all are true:

- complete historical snapshot accepted
- Drive immutable snapshot retained
- stable Drive CURRENT entrypoint exists
- PACI incremental updater passes CI
- chronological append is supported
- last-date retry/replace is idempotent
- historical correction is fail-closed
- horse history lookup uses blood registration number
- as-of exclusive lookup is tested
- one real current-period PACI update passes end-to-end
- updated CURRENT is synchronized back to the stable Drive file ID

After these conditions are met, this thread owns RaceReviewDB maintenance only.
How RaceNote, RL or another project consumes the database is out of scope here.
