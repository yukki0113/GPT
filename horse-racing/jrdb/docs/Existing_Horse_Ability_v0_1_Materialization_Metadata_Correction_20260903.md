# Existing-Horse Ability v0.1 materialization metadata correction — 2026-09-03

## Classification

`SEMANTICS_PRESERVING_METADATA_CORRECTION`

## Affected run

- Issue: `#321`
- Actions run: `33722753208`
- Result: materialization completed, audit failed only with `model_snapshot_contract_violation=13`.

All other audit violations were zero, including chronology, hyperparameter drift, market contamination, debut scoring, and 2024/2025 confirmation reproduction.

## Root cause

The frozen model matrix contains 22 numeric columns:

- 11 value columns,
- 10 ordinary missing flags,
- one final constant-zero missing flag for `log1p(career_scored_run_count)`.

The frozen comparison helper returned only 21 metadata names because the final constant-zero flag had no label. The numeric vector, preprocessing, fitted coefficients, predictions, rankings, development comparison, and 2024/2025 confirmation were not affected.

## Correction

Official materialization now names the already-existing final column:

```text
log1p_career_missing
```

No numeric feature value, feature order, hyperparameter, fold, model fit rule, target, or evaluation metric is changed.

A regression gate requires one metadata name per numeric model column and verifies the final column remains constant zero in the frozen feature-vector contract.

## Governance

Issue #321 is not valid final official-materialization evidence because its provenance metadata was incomplete. It must be retained as `INVALID_TECHNICAL_METADATA`, not as model/data failure.

The corrected full-history materialization/audit must run from latest main and reproduce the already-frozen 2024/2025 primary metrics within the existing tolerance before Existing-Horse Ability v0.1 materialization is accepted.
