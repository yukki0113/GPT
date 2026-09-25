# RaceReviewDB Operation Contract v0.1

Status: OPERATIONAL  
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

Consumers must depend on the stable Drive file ID, not on an immutable
generation file name.

## 3. Historical foundation and current accepted snapshot

Historical foundation generation:

jrdb_postrace_review_v0_1_2010_2025_g36046073323

Source Warehouse:

jrdb_normalized_warehouse_v1_2010_2025_g20260921

Historical accepted period:

2010-01-05 through 2025-12-28

Historical foundation row counts:

- fact_race_context: 55,268
- fact_race_review: 55,268
- fact_horse_performance: 781,161
- fact_track_bias: 162,624

The immutable historical foundation is retained under Drive snapshots/.

Current operational generation as of 2026-09-25:

jrdb_race_review_v0_1_incremental_g36094708797

Current accepted period:

2010-01-05 through 2026-09-22

Current row counts:

- fact_race_context: 57,830
- fact_race_review: 57,830
- fact_horse_performance: 816,536
- fact_track_bias: 169,752

Current snapshot_object_hash:

092b70b78520197660975df98c8d3eafcec160507a048be5f66edb42dcce5f67

Immutable current-generation snapshot Drive file ID:

1zgDYVB3KqsqSiHcrwr-xZh2rg3Pmqh_f

The bytes promoted to RaceReviewDB_CURRENT.zip were re-downloaded from Drive
after replacement and verified against the accepted candidate artifact.

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

The reference read-only implementation is:

src/jrdb_postrace_review_reader.py

Supported consumer operations include:

- metadata()
- horse_history(horse_id, before_date=...)
- histories_for_horses(horse_ids, before_date=...)
- race_review(race_key)

A missing horse history returns no rows. It must not fall back to name matching.

Consumers must not mutate RaceReviewDB through the reader.

## 6. Incremental sources

Current-period Review updates use a completed PACI + SED pair for every race
date.

Canonical PACI source:

horse-racing/00_raw/PACI

PACI Drive folder ID:

1zFajenPU5jxInZCcmqZzkgiaYil3MD8r

Canonical SED source:

horse-racing/00_raw/SED

Source responsibilities:

- PACI supplies BAC and KYI pre-race/context records.
- canonical SED supplies completed result records.
- PACI and SED dates must match exactly.
- the updater must not rely on an SED member being embedded in PACI.

PACI/SED parsing uses jrdb_raw.Parser. The incremental Review layer owns no
fixed-width byte offsets.

Required logical relations:

- BAC from PACI
- KYI from PACI
- SED from the canonical SED archive

## 7. Normal incremental update contract

Reference implementation:

src/jrdb_postrace_review_incremental.py

Acquisition implementation:

src/jrdb_postrace_review_acquire.py

Workflow:

.github/workflows/jrdb-race-review-incremental.yml

Request issue prefix:

[JRDB_RACE_REVIEW_INCREMENTAL]

Request lines must contain paired dates:

PACI|<Drive file id>|PACIyymmdd.zip
SED|<Drive file id>|SEDyymmdd.zip

One request may contain one date or multiple chronological dates.

The workflow verifies that PACI and SED date coverage is identical before
calculation.

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

## 8. Normal operating procedure

Routine operation after completed race data is available is fixed as follows:

1. confirm canonical PACI and canonical SED exist for every target date,
2. create one [JRDB_RACE_REVIEW_INCREMENTAL] request with paired PACI/SED
   Drive IDs,
3. acquisition validates every requested archive and required member,
4. incremental calculation advances a staging copy of CURRENT,
5. complete-snapshot audit and manifest verification must PASS,
6. retain the successful generation ZIP under Drive snapshots/,
7. replace RaceReviewDB_CURRENT.zip bytes in place,
8. preserve Drive file ID 1UwNfrupMTHRPhkzULPvClGre4MWz2TFg,
9. re-download CURRENT and verify generation_id, period_to and artifact bytes.

A calculation artifact is only a candidate until Drive CURRENT replacement and
read-back verification are complete.

Do not update CURRENT when acquisition, calculation, audit, manifest
verification, or acceptance evidence fails.

## 9. Incremental calculation

The updater does not rebuild the 2010-2025 Warehouse during ordinary updates.

It seeds rolling Review history from persisted CURRENT relations:

- fact_race_review supplies winner time / class / venue / surface / distance
- fact_race_context supplies pace balance

Because the original historical operational seed does not persist all detailed
standard dimensions, incremental seeding uses the persisted broader standard
scopes when necessary. This is explicit fallback, not hidden imputation.

Each new date is processed before that date is added to rolling history.

Therefore a target race cannot affect its own historical standard or pace
percentile.

## 10. Date replacement and historical correction

For every ordinary target race_date, all four relations are replaced atomically
in the staging DuckDB:

- fact_race_context
- fact_race_review
- fact_horse_performance
- fact_track_bias

The date is deleted first and the newly audited rows are inserted in one
transaction.

This makes retrying the current last date idempotent.

### Historical correction rule

If corrected data has target_date < CURRENT period_to, ordinary incremental
update must reject it.

The required recovery is:

1. identify the earliest corrected race date,
2. restore or reconstruct an accepted state immediately before that date,
3. replay the corrected date and every later completed date in chronological
   order,
4. audit the complete rebuilt candidate,
5. retain the rebuilt immutable snapshot,
6. replace stable Drive CURRENT only after all gates PASS.

Never patch only the corrected old date while retaining later derived Review
facts.

## 11. Publication contract

After all requested dates are applied:

1. the complete staged database is audited,
2. year-partitioned ZSTD Parquet objects are produced,
3. immutable generation manifest/audit files are written,
4. current.json is promoted inside the candidate only after hard gates PASS,
5. the workflow uploads a complete next-snapshot artifact.

Drive synchronization then performs:

1. retain the new generation ZIP under snapshots/,
2. replace RaceReviewDB_CURRENT.zip bytes in place,
3. preserve the stable Drive CURRENT file ID,
4. re-read Drive CURRENT before considering publication complete.

The accepted CURRENT Drive ID therefore remains stable across generations.

## 12. Hard gates

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
- PACI/SED date coverage mismatch
- historical correction without replay

Warnings do not silently become zero/neutral feature values.

## 13. Validation and workflow roles

Permanent unit/CI workflow:

.github/workflows/jrdb-postrace-review-tests.yml

It compiles the Review modules, including the incremental updater and read-only
reader, and runs the post-race Review unit-test suite.

Input acquisition diagnostic workflow:

.github/workflows/jrdb-race-review-input-smoke.yml

This is a troubleshooting/smoke path for validating requested PACI + SED input
availability. It is not the normal publication path.

Candidate acceptance workflow:

.github/workflows/jrdb-race-review-acceptance.yml

The current v0.1 acceptance workflow records the bounded real-data acceptance
used for the 2026-09-22 initial operational cutover. It is tied to that
candidate/run and is acceptance evidence, not a generic routine publication
workflow.

Routine publication is owned by the incremental workflow plus Drive promotion
and read-back verification described above.

## 14. Real-data acceptance evidence

Initial 2026 catch-up candidate:

- incremental run: 36094708797
- generation_id: jrdb_race_review_v0_1_incremental_g36094708797
- acceptance run: 36096119374
- acceptance Issue: #1323
- result: PASS

Acceptance verified:

- duplicate_race_horse_key = 0
- duplicate_race_key = 0
- orphan_horse_to_race = 0
- orphan_race_to_context = 0
- empty_horse_id_2026 = 0
- 2026 distinct Review dates = 80
- 2026 period = 2026-01-04 through 2026-09-22
- repeated horse_id continuity across starts
- as-of exclusive history before the next start
- completed race becomes visible after the race date
- unknown horse_id returns empty history without name fallback

## 15. Track bias status

fact_track_bias is available as a descriptive Review relation.

v0.1 operational updates keep adjusted/shrunk causal bias fields in shadow when
they are not calibrated.

This must not block adding the underlying race and horse Review rows.

## 16. Consumer responsibility

RaceReviewDB supplies evidence and derived Review facts.

It does not define:

- RaceNote prose policy
- RL weighting
- prediction feature weights
- duplicate-evidence handling inside another model
- UI presentation

Those are consumer-project responsibilities.

Consumers should record the RaceReviewDB generation_id used for reproducibility.

## 17. Issue lifecycle

RaceReviewDB request Issues must not remain open after their execution path has
ended.

Use the repository-wide failed-Issue policy:

- successful request -> close / completed
- failed request superseded by a successful retry -> close / not_planned or
  duplicate
- request that never executed and was superseded -> close / not_planned
- obsolete path after migration -> close / not_planned

At the v0.1 operational cutover there are no open RaceReviewDB request Issues.

The failed/superseded catch-up chain (#1305 through #1311) is closed
not_planned. The successful input smoke #1317 and real-data acceptance #1323
are closed completed.

## 18. Operational completion criteria

RaceReviewDB v0.1 is operational because all of the following have been
satisfied:

- complete historical snapshot accepted
- Drive immutable historical snapshot retained
- stable Drive CURRENT entrypoint exists
- PACI + canonical SED paired incremental updater has completed successfully
- chronological append is supported
- last-date retry/replace is idempotent
- historical correction is fail-closed and replay semantics are documented
- horse history lookup uses blood registration number
- as-of exclusive lookup is implemented and real-data accepted
- real 2026 current-period catch-up passed end-to-end
- updated generation is retained immutably under snapshots/
- updated CURRENT was synchronized back to the stable Drive file ID
- Drive CURRENT was re-downloaded and verified after replacement
- failed/superseded RaceReviewDB Issues are closed

Operational cutover:

2026-09-25

Operational status:

RaceReviewDB v0.1 operational = COMPLETE

From this point this component owns RaceReviewDB maintenance. How RaceNote, RL
or another project consumes the database remains outside this component's
publication contract.
