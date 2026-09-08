# Debut Ability Snapshot v0.2 — Implementation Conformance Record

Date: 2026-09-08

## Status

**IMPLEMENTATION CONFORMANCE ACCEPTED FOR STRUCTURAL VALIDATION**

This record documents the implementation step for `Debut_Ability_Snapshot_Protocol_v0_2.md`.

## 1. Why v0.2 does not require a new behavioral implementation

The behavioral change that motivated v0.2 was already implemented and accepted before the protocol number was promoted:

- Issue #332: Controller confirmed target-date UKC archives are PRE_RACE available.
- Issue #333: implementation changed profile resolution to latest UKC observation with `data_date <= race_date` and retained exact selected `profile_data_date` provenance.
- Issue #334: same-day-UKC snapshot rerun passed structural audit with all violations zero.
- Issue #335: 2010-2023 structural coverage was accepted and judged sufficient to freeze the first comparison protocol.

Therefore v0.2 is a protocol formalization of the already-accepted v0.1.1 behavioral implementation, not a second algorithmic change.

## 2. Canonical implementation behavior

`src/build_jrdb_debut_ability_snapshot.py` already enforces:

```text
profile selection: latest UKC data_date <= target race_date
historical scored/start chronology: strictly before target race_date
same-day result availability for priors: forbidden
current target result as feature: forbidden
```

The selected UKC source date is persisted in `profile_data_date`. Canonical same-day selection is derived as:

```text
profile_data_date == race_date
```

`profile_prior_day_available` and `profile_same_day_observation_exists` remain separate provenance diagnostics.

The implementation batches targets by race date and only updates historical result/start state after the entire target date has been built, preventing same-day result leakage into pedigree/people priors.

## 3. Version lineage

The implementation artifact continues to carry its historical builder identifier `build_jrdb_debut_ability_snapshot_v0_1_1` because no behavioral code delta is required for v0.2 conformance.

The governing operational protocol for new structural acceptance work is now `Debut_Ability_Snapshot_Protocol_v0_2.md`.

This separation preserves implementation lineage rather than relabeling unchanged code as a new algorithm.

## 4. Regression evidence

Issue #484 (`[JRDB_DEBUT_ABILITY_SMOKE] 20260908-v0.2-conformance`) ran from main head:

```text
9ddae86140a8bd9f9b8bbd8114d5ce20a526fc01
```

Result:

```text
status=success
run_id=34187972341
```

The workflow compiled the Debut snapshot/audit/coverage path and ran the focused Debut snapshot and coverage regression tests.

## 5. Predictive boundary

This implementation-conformance step performs no predictive comparison and selects no model.

```text
2024_2025_predictive_metrics_inspected = false
model_selected = false
```

The next gate is a fresh 2010-2023 structural audit/coverage run under the v0.2 protocol. Only after that gate is accepted may the Debut comparison protocol be frozen. Predictive comparison execution is a separate later step.
