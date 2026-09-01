# JRDB Work INBOX 20260901-004

request_id: `JRDB-WORK-20260901-004`  
issued_at: 2026-09-01 JST  
continuation_of: `JRDB-WORK-20260901-003`  
required_outbox_filename: `JRDB_Work_OUTBOX_20260901_004.md`

## 1. Objective

Use the accepted Ability pre-race snapshot to build and execute the **existing-horse Ability development comparison** for 2013-2023.

This package produces evidence only. It must not promote an official Ability model and must not inspect 2024-2025 Ability predictive performance.

Debut Ability is explicitly out of scope and remains a later dedicated model.

## 2. Read first

File Library:

- `JRDB_Work_OUTBOX_20260901_003.md`
- `JRDB_Work_Library_Exchange_Protocol_v0_1.md`

GitHub `yukki0113/GPT` latest main:

- `horse-racing/jrdb/README.md`
- `horse-racing/jrdb/.gpt/CONTEXT.md`
- `horse-racing/jrdb/.gpt/WORKFLOW.md`
- `horse-racing/jrdb/docs/Work_Library_Exchange_Protocol_v0_1.md`
- `horse-racing/jrdb/docs/RunPerf_v0_1.md`
- `horse-racing/jrdb/docs/Ability_Development_Protocol_v0_1.md`
- `horse-racing/jrdb/docs/Ability_Model_Comparison_Protocol_v0_1.md`
- `horse-racing/jrdb/docs/JRDB_PWA_Index_Design_v0_1.md`
- `horse-racing/jrdb/docs/JRDB_PWA_Index_Feature_Registry_v0_1.md`
- `horse-racing/jrdb/schema/jrdb_ability_snapshot_schema_v0_1.sql`
- 003 builder/audit/tests/workflow/docs

`Ability_Model_Comparison_Protocol_v0_1.md` is authoritative for candidate definitions, folds, preprocessing, metrics, and boundaries.

## 3. 003 accepted state

003 was accepted structurally:

- total target runners: `781161`
- PRE_RACE-valid target runners: `780426`
- debut runners retained: `85739`
- current-going verified PRE_RACE availability: `0`
- same-day leakage: `0`
- target-result feature leakage: `0`
- target SED going leakage: `0`
- fallback PRE_RACE misuse: `0`
- duplicate: `0`
- market columns: `0`
- 2024-2025 Ability predictive metrics inspected: `false`

RunPerf v0.1 remains `T1|EXPANDING|RAW`.

## 4. Scope rows

Comparison rows are existing horses only:

```text
career_scored_run_count >= 1
```

Target label:

```text
ability_current_result.official_runperf_raw
```

Use only rows whose target official RunPerf score status is `OK` and whose target pre-race context is valid.

Do not include debut rows in model fitting/evaluation.

## 5. Development folds

Exactly:

```text
2013 test <- rows with target year <= 2012
2014 test <- rows with target year <= 2013
...
2023 test <- rows with target year <= 2022
```

No 2024-2025 target labels may be read by the comparator.

The comparator should actively reject a requested development end >= 2024.

## 6. A0 implementation

Implement the four transparent candidates from the frozen protocol:

```text
A0_D070
A0_D080
A0_D090
A0_D100
```

A0 has no fitted coefficient and predicts with the corresponding recent-performance feature directly.

Report annual and aggregate metrics for all four.

Do not auto-adopt a decay.

## 7. A1 feature transformation

Implement the frozen feature template and transformations exactly as documented.

A1 must exclude:

- `rest_days`
- going fit
- odds/popularity/market
- target result other than evaluation label
- target finish/result diagnostics as model input

Candidate axes:

```text
recent decay:       070 / 080 / 090 / 100
distance bandwidth: 200 / 400 / 600 / 800
aptitude shrink k:  0 / 4 / 12
jockey shrink k:    0 / 20 / 100
```

Aptitude shrink formula:

```text
raw_delta * neff / (neff + k)
```

Jockey shrink formula:

```text
raw_residual * n / (n + k_jockey)
```

Use explicit missing flags as frozen in the protocol.

## 8. Ridge grid

For every feature configuration compare:

```text
alpha = 0.01, 0.1, 1, 10, 100
```

Fit each test-year model using only earlier target years.

Store/report coefficient history for top candidates.

## 9. Elastic Net challenger

After the full Ridge development grid is available, identify the 10 highest mean-primary **feature transforms ignoring alpha duplicates**.

For those transforms only, evaluate:

```text
alpha = 0.001, 0.01, 0.1
l1_ratio = 0.1, 0.5
```

This is a frozen procedural development search, not holdout validation.

A2/nonlinear models are forbidden in 004.

## 10. Fold-local preprocessing

For every fold:

1. fit imputation statistics on training rows only;
2. keep explicit missing flags;
3. impute numeric missing values with training-fold median;
4. fit scaling mean/std on training rows only after imputation;
5. apply unchanged parameters to test year;
6. drop/report zero-variance training columns for that fold.

Add leakage tests proving no test-year statistic enters preprocessing.

## 11. Metrics

Implement exactly the protocol metrics.

Primary per year:

```text
primary_year = mean(
  spearman_all_rows(prediction, target_runperf),
  mean_within_race_spearman(prediction, target_runperf)
)
```

Within-race Spearman requires >=3 eligible scored runners.

Required secondary metrics:

- Pearson
- MAE
- RMSE
- mean within-race Spearman
- top-predicted target-RunPerf-rank percentile diagnostic
- row/race coverage
- year-to-year SD

Required strata:

- career count = 1
- career count = 2
- career count = 3-5
- career count >= 6
- surface history present / untried
- exact distance history present / absent
- course exact evidence present / absent

Equal-year aggregation is mandatory.

## 12. Comparison report

Create a machine-readable JSON report plus a lightweight summary suitable for Issue comment.

Minimum contents:

- protocol metadata and source SHA
- development years
- holdout_touched=false
- training/test counts by fold
- A0 results
- full Ridge grid compact results
- Elastic Net compact results
- top 20 overall candidates
- best A0 / best Ridge / best Elastic Net
- annual metrics for top candidates
- paired annual deltas versus best A0
- coefficient histories for top regularized models
- feature-transform configuration
- strata diagnostics
- preprocessing/leakage checks

Do not create an `official_ability` table or model version in this package.

## 13. Tests

Add tests covering at minimum:

1. comparator rejects 2024+ development end
2. train year < test year for every fold
3. fold-local imputation/scaling cannot read test year
4. A0 arithmetic
5. shrink formulas including k=0
6. distance-bandwidth candidate selection by config only, not hidden global selection
7. Ridge grid executes
8. Elastic Net top-10 transform procedural filter
9. primary metric arithmetic
10. within-race Spearman minimum-runner rule
11. career strata
12. no debut rows in comparison
13. no market/current-result feature input
14. no going feature use
15. deterministic results with fixed solver settings

Run relevant 003 snapshot/audit and official RunPerf tests as regression gates.

## 14. Real-history workflow

Add an Issue-triggered workflow, suggested prefix:

```text
[JRDB_ABILITY_COMPARE]
```

Workflow path:

```text
JRDB Raw 2010-2023 only
  -> Index Base
  -> Index Base audit
  -> RunPerf EXPANDING
  -> RunPerf audit
  -> official RunPerf
  -> official RunPerf audit
  -> Ability snapshot through 2023
  -> Ability snapshot audit
  -> existing-horse Ability comparison 2013-2023
  -> lightweight result + artifact + Issue comment
```

Prefer fetching only through 2023 so 2024-2025 labels are physically absent from the comparison run.

Do not reuse a 2010-2025 snapshot DB if a clean 2010-2023 build is practical.

## 15. Acceptance gates

Technical/infrastructure acceptance requires:

- all upstream audits PASS
- snapshot audit PASS
- comparator status PASS
- development_end=2023
- holdout_touched=false
- chronology violations 0
- preprocessing leakage violations 0
- market/current-result feature leakage 0
- debut rows used in comparator 0
- all requested A0/Ridge/Elastic Net candidates executed or explicitly documented if mathematically degenerate
- required annual/paired/strata diagnostics present

Predictive ranking itself is not an acceptance gate. A weak model result is valid evidence and must be returned without changing the protocol.

## 16. Forbidden

- inspecting or reporting 2024-2025 Ability predictive performance
- changing official RunPerf
- using target SED current-going
- using rest_days in A1
- adding odds/popularity
- fitting A2/nonlinear models
- silently changing candidate grids after results
- promoting an official Ability model
- forcing existing-horse A1 onto debut horses and calling Ability complete

## 17. Required OUTBOX

Create in File Library:

`JRDB_Work_OUTBOX_20260901_004.md`

Status enum:

- `COMPLETE`
- `PARTIAL`
- `BLOCKED`
- `FAILED`

Required additions:

```text
continuation_of: JRDB-WORK-20260901-003
main_start_sha
main_finish_sha
pr_or_commits
real_history_issue
real_history_run_id
artifact_id
comparison_status
development_years
holdout_touched
best_a0
best_ridge
best_elastic_net
top_candidates
paired_vs_best_a0
career_strata_summary
preprocessing_leakage_violations
all_violation_counts
2024_2025_predictive_metrics_inspected: false
model_promoted: false
ready_for_controller_model_decision: true/false
controller_decisions_requested
```

COMPLETE means the frozen 2013-2023 existing-horse comparison executed correctly. It does not mean an official Ability model has been selected.
