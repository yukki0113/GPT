# JRDB Work INBOX 20260901-003

request_id: JRDB-WORK-20260901-003
issued_at: 2026-09-01 JST
controller_role: JRDB independent-index design / methodological governance
work_role: implementation / Git / Actions / real-data audit
continuation_of: JRDB-WORK-20260901-002
required_outbox_filename: JRDB_Work_OUTBOX_20260901_003.md
optional_artifact_manifest: JRDB_Work_ARTIFACTS_20260901_003.md

## 1. Objective

Official RunPerf v0.1 is complete. Build and audit the **pre-race Ability feature snapshot infrastructure** on top of official RunPerf without fitting or selecting an Ability model.

The output must retain every eligible pre-race target runner, including debut horses, and must be auditable for strict `history_date < target_date` chronology.

Do not redesign RunPerf.

## 2. Read first

File Library:
- `JRDB_Work_OUTBOX_20260901_002.md`
- `JRDB_Work_Library_Exchange_Protocol_v0_1.md`

GitHub `yukki0113/GPT` latest main:
- `horse-racing/jrdb/README.md`
- `horse-racing/jrdb/.gpt/CONTEXT.md`
- `horse-racing/jrdb/.gpt/WORKFLOW.md`
- `horse-racing/jrdb/docs/Work_Library_Exchange_Protocol_v0_1.md`
- `horse-racing/jrdb/docs/RunPerf_v0_1.md`
- `horse-racing/jrdb/docs/Ability_Development_Protocol_v0_1.md`
- `horse-racing/jrdb/docs/JRDB_PWA_Index_Design_v0_1.md`
- `horse-racing/jrdb/docs/JRDB_PWA_Index_Feature_Registry_v0_1.md`
- `horse-racing/jrdb/schema/jrdb_index_base_schema_v0_1.sql`
- `horse-racing/jrdb/schema/jrdb_official_runperf_schema_v0_1.sql`
- related current builders/audits/tests/workflows

`Ability_Development_Protocol_v0_1.md` is the methodological contract for this package.

## 3. Period policy

Do not call 2024-2025 a pristine Ability holdout.

Use only structural/coverage checks in 003.

- 2010-2012: warm-up/history formation
- 2013-2023: later Ability development period
- 2024-2025: later post-freeze temporal confirmation; no model/feature tuning in 003
- 2026 onward: preferred prospective published-pipeline evaluation

003 must not rank feature candidates by 2024-2025 outcomes.

## 4. Task A — Ability snapshot schema

Create an auditable SQLite schema, suggested path:

`horse-racing/jrdb/schema/jrdb_ability_snapshot_schema_v0_1.sql`

Exact normalization is an implementation choice, but the database must clearly separate:

1. build/provenance metadata
2. target pre-race runner identity/context
3. Ability feature values/candidates
4. feature provenance / source-date diagnostics as needed
5. target/evaluation official RunPerf, if stored, as a clearly separate CURRENT_RESULT table or contract

Do not expose target-result fields as feature columns.

Mandatory snapshot identity/provenance:

```text
race_date
race_key
horse_no
horse_id
as_of_exclusive
feature_builder_version
formula_version
source_snapshot
calculated_at
validation_status
race_context_availability
```

Debut runners must remain represented.

Market/odds/popularity columns are forbidden in Ability feature tables.

## 5. Task B — Snapshot builder

Suggested path:

`horse-racing/jrdb/src/build_jrdb_ability_snapshot.py`

Inputs should be audited Index Base + audited official RunPerf or the minimal equivalent reproducible source chain.

Every historical RunPerf source used for a target date D must satisfy:

```text
history_race_date < D
```

Same-day completed results must not enter another target's published feature snapshot.

Only official RunPerf rows with valid scored status may enter horse performance history.

### 5.1 Target runner retention / career evidence

Persist at minimum:

```text
career_scored_run_count
recent_scored_run_count
last_scored_run_date
rest_days
is_debut
```

`is_debut = 1` when no prior scored official RunPerf exists before target date.

Do not drop debut runners because historical features are missing.

### 5.2 Recent performance candidates

Latest 5 valid historical official RunPerf rows maximum.

Produce all candidates, do not select:

```text
recent_perf_d070
recent_perf_d080
recent_perf_d090
recent_perf_d100
```

Newest history weight = 1.0; older weights decay geometrically.

Persist n/neff/missing/config as appropriate.

### 5.3 Peak / gap

Latest-5 window:

```text
peak_best1_last5
peak_best2_mean_last5
```

Keep raw peak and recent components. Do not preselect a blend.

Derived peak gaps may be added per recent candidate if transparent.

### 5.4 Stability

```text
performance_mad_last5
```

Require >=3 valid prior runs; otherwise NULL + missing flag.

### 5.5 Surface fit raw components

Use up to latest 12 valid prior official RunPerf rows.

Persist at minimum:

```text
surface_same_mean_raw
surface_overall_mean_raw
surface_fit_delta_raw
surface_fit_n
surface_fit_neff
surface_fit_missing
```

Untried/unknown != 0.

### 5.6 Distance fit candidates

Use continuous kernel, initial bandwidth candidates:

```text
200m
400m
600m
800m
```

Recommended documented kernel:

```text
exp(-abs(history_distance-current_distance)/bandwidth)
```

Persist each candidate separately plus n/neff/missing/config.

Also preserve exact-distance count and nearest historical distance difference for diagnostics.

Do not select a bandwidth.

### 5.7 Course fit raw/backoff components

Persist exact venue x surface evidence separately from backoff evidence.

Minimum:

```text
course_exact_mean_raw
course_exact_delta_raw
course_exact_n
course_exact_neff
course_surface_backoff_mean_raw
course_fit_missing
```

Do not invent an exact-course estimate when no evidence exists.

### 5.8 Going-fit availability first

Historical going may use completed historical result labels.

Target current-going must come from a verified PRE_RACE source available at the intended publication snapshot.

Forbidden:
- target SED final track condition
- other CURRENT_RESULT target going
- result-derived silent backfill

Before implementing current-going fit, audit the JRDB raw/schema/source definition to determine whether a trustworthy PRE_RACE target-going value exists historically.

If it does:
- document source and availability
- implement same-going/same-surface raw evidence and counts

If it does not:
- keep current-going-dependent feature NULL/missing
- report annual availability coverage
- do not remove `going_fit` from the registry
- do not substitute CURRENT_RESULT

This is a key acceptance point.

### 5.9 Jockey general effect infrastructure

Do not use raw win rate or raw jockey RunPerf average as the designed `jockey_general_effect`.

For each historical ride R:

1. build a horse-only expected baseline from that horse's scored runs strictly before R;
2. where a horse-only baseline cannot be formed, exclude the ride from this initial residual estimator but count it for coverage;
3. calculate

```text
jockey_residual_R = official_runperf_R - horse_only_expected_before_R
```

4. for target date D, aggregate only residual rides with `ride_date < D`.

Persist raw past-only jockey residual mean, n, latest source date/lag where useful, and missing flag.

Final shrinkage is not selected in 003.

If an explicit horse-only baseline detail must be chosen, use the simplest transparent past-only baseline and document it; do not tune it using 2024-2025. If the choice is methodological rather than technical, report to Controller instead of silently optimizing.

### 5.10 Weight relative

From current PRE_RACE runner entries:

```text
weight_relative = current_carried_weight - current_race_mean_carried_weight
```

Persist:

```text
current_carried_weight
race_mean_carried_weight
weight_relative
race_valid_weight_count
weight_relative_missing
```

No target-result carried weight substitution.

## 6. Task C — Evaluation target separation

If current official RunPerf for the target race is stored in the snapshot DB, use a separate table or explicit CURRENT_RESULT target contract.

It may be used only for later evaluation.

003 audit may check join coverage/counts, but must not use 2024-2025 target values to choose feature definitions or parameters.

## 7. Task D — Audit

Suggested path:

`horse-racing/jrdb/src/audit_jrdb_ability_snapshot.py`

Fail closed on at least:

- SQLite integrity failure
- duplicate target `(race_key, horse_no)`
- missing mandatory target pre-race identity
- historical source date >= target date
- same-day result leakage
- target CURRENT_RESULT column used as feature input
- target SED/final going used as current-going feature
- official RunPerf chronology/provenance mismatch
- future coefficient backfill inherited/reintroduced
- debut runner dropped solely because career history=0
- unknown/untried aptitude silently encoded as zero without missing flag
- non-finite populated numeric feature
- market/odds/popularity column in Ability feature schema
- CURRENT_RESULT_FALLBACK race context treated as valid PRE_RACE
- invalid n/neff/missing relationships

Audit should report, by year where practical:

- target runner count
- PRE_RACE-valid target count
- excluded/fallback target count
- debut runner count/rate
- existing-horse count
- career-count distribution/bands
- each feature/candidate coverage and missing rate
- recent-history n distribution
- surface/course/distance evidence distributions
- current-going PRE_RACE availability coverage
- jockey residual feature coverage / ride counts
- weight_relative coverage
- target label join coverage (structural only)
- max historical source date / source lag diagnostics proving `< target_date`
- violation counts

## 8. Task E — Tests

Add regression tests that cover at minimum:

1. strict prior-date history use
2. same-day history exclusion
3. recent decay calculations
4. peak/stability behavior
5. untried surface remains NULL + missing
6. distance kernel candidate arithmetic/neff
7. course missing/backoff contract
8. target-result going cannot be used
9. debut row retained with history features missing
10. jockey residual uses prior horse baseline and prior rides only
11. weight_relative uses PRE_RACE field data
12. fallback target context not treated as valid PRE_RACE
13. duplicate key fail
14. market column fail / absent schema
15. non-finite feature fail

Run relevant existing Index Base / official RunPerf regression tests too.

## 9. Task F — Real-history workflow

Create or extend an Issue-triggered workflow for structural Ability snapshot generation/audit.

Suggested title prefix:

```text
[JRDB_ABILITY_SNAPSHOT_AUDIT]
```

Required real-history path:

```text
JRDB Raw 2010-2025
  -> Index Base
  -> Index Base audit
  -> RunPerf EXPANDING
  -> RunPerf audit
  -> Official RunPerf v0.1
  -> Official RunPerf audit
  -> Ability pre-race feature snapshot
  -> Ability snapshot audit
  -> lightweight report/artifact
```

Use existing authenticated history fetch. Do not transport annual Raw through chat.

The workflow may generate 2024-2025 feature snapshots and structural coverage counts, but must not compute/report Ability predictive performance or use those target outcomes for tuning.

## 10. Task G — Real-history acceptance

Run 2010-2025 structural snapshot audit.

Acceptance requires at least:

- all upstream gates PASS
- Ability snapshot audit PASS
- chronology violation 0
- same-day result leakage 0
- target-result input leakage 0
- target SED going leakage 0
- duplicate 0
- market contamination 0
- debut retention violation 0
- fallback PRE_RACE misuse 0
- non-finite populated feature 0
- n/neff/missing contract violations 0

Coverage shortfalls are not automatically failures if they reflect real availability and are explicitly missing; report them instead of imputing forbidden data.

## 11. Task H — Documentation

Add/update operational documentation describing:

- snapshot schema
- feature definitions/candidate grids
- chronology
- going availability finding
- jockey residual baseline implementation
- real-history coverage
- known exclusions/missingness
- exact work boundary: no Ability model selection yet

Do not change Feature Registry status from CORE_BUILD/TEST to CORE/REJECT based only on structural coverage.

## 12. Forbidden in 003

- changing `T1|EXPANDING|RAW`
- recomputing historical RunPerf with later coefficients
- selecting recent decay
- selecting distance bandwidth
- selecting shrinkage constants
- fitting or choosing A0/A1/A2
- feature selection based on predictive performance
- evaluating 2024-2025 Ability predictive performance
- calling 2024-2025 a pristine Ability holdout
- using odds/popularity/market data
- using current target result as Ability input
- using target SED final track condition as current-going input
- dropping debut horses
- replacing missing aptitude with zero

## 13. Work autonomy

Work may decide:

- exact SQLite normalization/indexes
- performance optimizations with identical semantics
- technical workflow structure
- test organization
- audit-report layout
- meaning-preserving bug fixes

If a semantic feature definition must change, or a required pre-race source is fundamentally unavailable and a replacement is proposed, stop that branch and report the choice to Controller.

## 14. Required OUTBOX

Create and make searchable in File Library:

`JRDB_Work_OUTBOX_20260901_003.md`

Status enum must follow the Exchange Protocol exactly:

- `COMPLETE`
- `PARTIAL`
- `BLOCKED`
- `FAILED`

Do not use `COMPLETED_PASS` or another custom status.

Mandatory additions beyond the protocol:

```text
continuation_of: JRDB-WORK-20260901-002
main_start_sha
main_finish_sha
pr_or_commits
real_history_issue
real_history_run_id
artifact_id
ability_snapshot_acceptance
annual_target_counts
annual_debut_counts
feature_coverage
current_going_availability_finding
jockey_residual_coverage
weight_relative_coverage
all_violation_counts
2024_2025_predictive_metrics_inspected: false
ready_for_ability_model_protocol: true/false
controller_decisions_requested
```

If multiple artifacts matter, also create:

`JRDB_Work_ARTIFACTS_20260901_003.md`

COMPLETE means the 2010-2025 structural Ability snapshot build/audit passed all semantic/chronology gates. It does not mean an Ability model exists.
