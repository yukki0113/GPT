# Debut Ability development staging v0.1

## Status

**METHODOLOGICAL STAGING — FROZEN BEFORE DEBUT PREDICTIVE COMPARISON**

This document fixes the order of Debut/no-scored-history Ability development. It does not freeze numeric candidate grids; those are defined only after structural snapshot audit is accepted.

## 1. Period boundary

- 2010-2012: history formation / warm-up
- 2013-2023: predictive development walk-forward
- 2024-2025: post-freeze temporal confirmation only
- 2026 onward: prospective evaluation preferred

No 2024-2025 Debut Ability predictive metric may be inspected before the final development candidate and confirmation gate are frozen.

## 2. Cohort

Primary source path:

```text
career_scored_run_count = 0
```

Always report separately:

```text
true first start
prior start(s) but no valid scored official RunPerf
```

Do not silently apply Existing-Horse Ability v0.1 to either group.

## 3. Staged model development

### Stage D0 — pedigree baseline

Build a transparent horse-side prior using only past-only pedigree evidence available in `Debut Ability Snapshot v0.1`.

Candidate ingredients may include:

- sire debut prior
- broodmare-sire debut prior
- sire-line / broodmare-sire-line backoff
- surface-conditioned pedigree evidence
- distance-kernel pedigree candidates

Shrinkage/bandwidth grids must be frozen in the later comparison protocol before predictive results are inspected.

### Stage D1 — pedigree + target preparation/context

Challenge D0 using horse-side PRE_RACE information:

- CHA raw workout fields
- CYB raw training fields
- current carried-weight relative value
- sex / pre-race age when valid
- explicit missing flags

Categorical CHA/CYB codes must use explicit categorical encoding; never infer numeric ordering unless a later protocol documents that ordering from the code definition.

Regularized linear models are the first challenger family. Nonlinear models are not introduced until the linear incremental value is established.

### Stage D2 — residualized people effects

Raw `jockey_debut_runperf_raw` and `trainer_debut_runperf_raw` are diagnostics/infrastructure only. They are not final people-effect features.

After D1 is frozen inside each development fold:

1. generate strictly past-only / out-of-fold D1 predictions for historical debut runs;
2. compute historical residual:

```text
people_residual = official_runperf - D1_horse_side_expected
```

3. aggregate jockey/trainer residuals using only rides/runs before each target date;
4. apply explicitly predeclared shrinkage candidates;
5. test D2 = D1 + residualized people effects.

No target-year fit statistic or target result may enter the historical people residual prior.

## 4. Evaluation target and chronology

Target remains:

```text
official RunPerf v0.1 = T1|EXPANDING|RAW
```

All target labels are evaluation-only.

Development fold Y:

```text
train labels: year < Y
test labels:  year = Y
```

All feature evidence must remain strict-as-of target date under `Debut_Ability_Snapshot_Protocol_v0_1.md`.

## 5. Mandatory diagnostics

Later comparison must report at minimum:

- annual equal-year primary metric
- within-race ranking metric where cohort size permits
- Pearson / MAE / RMSE
- prediction/label coverage
- true-first-start stratum
- prior-start/no-scored-history stratum
- pedigree profile availability strata
- CHA present/missing
- CYB present/missing
- sire/damsire sample-size bands
- major distance-evidence bands

Weak or missing strata are evidence; do not silently impute result-derived information.

## 6. Boundary before comparison protocol

Do not freeze numeric shrinkage, bandwidth, regularization, one-hot category handling details, or a final D0/D1/D2 candidate until the 2010-2025 structural snapshot audit has been accepted and its coverage report reviewed.

The structural audit may influence which **pre-race available** candidates are practical, but must not inspect 2024-2025 Debut predictive performance.
