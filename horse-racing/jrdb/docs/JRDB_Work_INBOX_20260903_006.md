# JRDB Work INBOX 2026-09-03 006

request_id: `JRDB-WORK-20260903-006`

## 1. Objective

Implement and execute the first **Debut / no-scored-history Ability development comparison** under the frozen Controller protocol.

This package is evidence generation only. It must not promote a Debut Ability model and must not inspect 2024-2025 Debut predictive performance.

## 2. Canonical inputs — read first

Use latest GitHub `main` as canonical.

Required:

- `horse-racing/jrdb/docs/Debut_Ability_Snapshot_Protocol_v0_1.md`
- `horse-racing/jrdb/docs/Debut_Ability_Model_Comparison_Protocol_v0_1.md`
- `horse-racing/jrdb/docs/Debut_Ability_Development_Order_v0_1.md`
- `horse-racing/jrdb/docs/Debut_Ability_Training_Feature_Type_Contract_v0_1.md`
- `horse-racing/jrdb/src/build_jrdb_debut_ability_snapshot.py`
- `horse-racing/jrdb/src/audit_jrdb_debut_ability_snapshot.py`
- canonical snapshot acceptance evidence: Issue #334
- canonical development coverage evidence: Issue #335
- UKC availability decision: Issue #332
- existing-horse comparison protocol/implementation only as a reusable engineering reference, not as Debut feature semantics.

## 3. Frozen boundaries

Target population:

```text
career_scored_run_count = 0
```

Official target:

```text
official RunPerf v0.1 = T1|EXPANDING|RAW
```

Periods:

- 2010-2012 = history/warm-up only
- 2013-2023 = development walk-forward
- 2024-2025 = forbidden predictive confirmation period in this package

For test year Y:

```text
train target year < Y
test target year = Y
```

No target/future preprocessing.

## 4. Implement comparator

Create a dedicated Debut comparator, suggested path:

`horse-racing/jrdb/src/compare_jrdb_debut_ability_models.py`

Do not overload the existing-horse comparator with Debut semantics unless there is a very strong code-quality reason and tests preserve both contracts exactly.

Comparator must fail closed when:

- requested predictive test year >= 2024;
- a 2024-2025 target label is read for scoring/ranking/model selection;
- target context is not PRE_RACE;
- current/same-day result enters feature history;
- market/odds/popularity columns enter predictors;
- fold preprocessing uses future/test rows;
- category vocabulary is learned from test rows.

## 5. D0 candidates

Implement all transparent references:

- `D0_SIRE`
- `D0_DAMSIRE`
- `D0_SIRE_LINE`
- `D0_DAMSIRE_LINE`

Implement regularized pedigree feature configurations exactly as frozen in `Debut_Ability_Model_Comparison_Protocol_v0_1.md`.

Distance bandwidth candidates:

```text
200, 400, 600, 800
```

Pedigree shrinkage k:

```text
0, 8, 32
```

Shared sire+damsire distance bandwidth per configuration.

## 6. D1 candidates

Implement:

```text
D1_NUMERIC = D0 + numeric training/basic fields
D1_FULL    = D1_NUMERIC + categorical training fields
```

Categorical codes must be treated as categories, not ordinal numbers.

For each fold:

- learn category vocabulary from training rows only;
- one-hot encode;
- map unseen test values to explicit unknown;
- report resulting feature dimensions / dropped zero-variance columns.

Do not add raw jockey/trainer RunPerf means to D1.

D2 residualized jockey/trainer work is out of scope.

## 7. Model grid

Ridge for every frozen D0/D1 feature configuration:

```text
alpha = 0.01, 0.1, 1, 10, 100
```

Then select the 10 highest mean-primary Ridge **feature transforms ignoring alpha duplicates** and evaluate Elastic Net only on those transforms:

```text
alpha = 0.001, 0.01, 0.1
l1_ratio = 0.1, 0.5
```

No tree/boosting/neural model in this package.

Do not alter the grid after seeing results.

## 8. Fold-local preprocessing

Numeric:

1. explicit missing flag;
2. training-fold median imputation;
3. training-fold standardization;
4. unchanged transform on test Y;
5. zero-variance training columns dropped and reported.

Categorical:

1. training-only vocabulary;
2. one-hot encoding;
3. explicit unknown for unseen test categories.

Target remains on raw official RunPerf scale.

## 9. Metrics

For each test year 2013-2023 report:

Primary:

```text
primary_year = mean(
    spearman_all_rows(predicted_ability, target_runperf),
    mean_within_race_spearman(predicted_ability, target_runperf)
)
```

Required secondary:

- Pearson
- MAE
- RMSE
- within-race Spearman
- top-predicted runner target-RunPerf-rank percentile diagnostic
- eligible row count / coverage
- annual std of primary across years

Aggregate candidates by equal-year mean.

## 10. Required strata

At minimum:

- true first start vs prior-start/no-scored-history
- sire prior present / missing
- damsire prior present / missing
- sire n `<8`, `8-31`, `>=32`
- damsire n `<8`, `8-31`, `>=32`
- CHA core index present / missing
- CYB core index present / missing
- week-ago workout index present / missing
- surface-conditioned sire evidence present / absent

## 11. Required tests

Add targeted regression tests covering at least:

1. comparator rejects target year >=2024;
2. training rows are strictly earlier years than test year;
3. numeric imputation/scaling is train-fold only;
4. categorical vocabulary is train-fold only and unseen test category maps to unknown;
5. categorical codes are not consumed as continuous raw code values;
6. D0 transparent references reproduce source columns;
7. pedigree shrinkage formula and k grid;
8. distance bandwidth selection wiring;
9. current/same-day result cannot enter predictors;
10. market fields are rejected;
11. raw jockey/trainer prior fields are absent from D1 predictor template;
12. metric calculation, equal-year aggregation, and paired annual differences;
13. Elastic Net top-10 transform filter ignores Ridge alpha duplicates as specified.

Run existing related JRDB regression tests too.

## 12. Runtime / workflow

Create an Issue-triggered development workflow with a distinct prefix, suggested:

`[JRDB_DEBUT_ABILITY_COMPARE]`

Workflow should expose major stages separately so runtime failures are diagnosable:

1. checkout/setup/tests
2. Raw fetch 2010-2023 only
3. Index Base build/audit
4. RunPerf build/audit
5. Official RunPerf build/audit
6. Debut snapshot v0.1.1 build/audit
7. Debut comparison
8. lightweight result
9. artifact upload
10. Issue comment

Do not fetch 2024-2025 Raw in the comparison workflow unless a non-predictive infrastructure requirement is unavoidable. Prefer 2010-2023 only.

Technical workflow failure must not be reported as model failure.

## 13. Real-history execution

After tests pass, execute the complete 2010-2023 development comparison on real history.

Report:

- all transparent D0 references;
- full Ridge summary;
- D1_NUMERIC / D1_FULL summaries;
- Elastic Net challengers;
- best overall and best-by-family;
- annual top-candidate metrics;
- paired annual differences versus best transparent D0 and best regularized D0;
- coefficient histories / feature dimensions for top candidates;
- required strata;
- exact candidate configuration and coverage.

The comparison report must explicitly state:

```text
2024_2025_predictive_metrics_inspected = false
model_promoted = false
```

## 14. Acceptance gates

A technical COMPLETE requires:

- upstream audits PASS;
- all required comparator tests PASS;
- every fold respects train year < test year;
- no market/current-result/same-day-result leakage;
- no 2024-2025 predictive metric access;
- all frozen D0/D1 Ridge candidates execute;
- Elastic Net top-10 procedure executes exactly;
- annual/paired/strata diagnostics produced;
- artifact uploaded and Issue result recorded.

A candidate being weak is **not** a technical failure. Return the evidence.

Do not promote a model even if one wins strongly.

## 15. OUTBOX

Return:

`JRDB_Work_OUTBOX_20260903_006.md`

using the existing Work Library Exchange Protocol.

Required fields include at minimum:

- request_id
- status
- started_from_git_sha
- finished_at_git_sha
- commits
- files_created / updated / deleted
- tests_run / test_results
- workflows_or_issues
- real_data_audits
- artifacts
- acceptance_gate_results
- methodological_changes
- assumptions
- unresolved_items
- controller_decisions_requested
- recommended_next_work_package

For the real comparison additionally summarize:

- top transparent D0
- top regularized D0
- top D1_NUMERIC
- top D1_FULL
- top Elastic Net challenger
- annual paired deltas
- any complexity/stability concerns
- confirmation that 2024-2025 predictive metrics remained unopened.

## 16. Controller boundary after completion

Work stops after returning development evidence.

Controller will decide:

- winning D0/D1 transform/model;
- whether the gain justifies D1_FULL complexity;
- whether to proceed to D2 residualized jockey/trainer development;
- when/how to freeze a Debut candidate for later 2024-2025 temporal confirmation.
