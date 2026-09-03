# Debut Ability UKC Availability Decision — 2026-09-03

## Status

**FROZEN AVAILABILITY RESOLUTION — PRE-PREDICTIVE**

This record resolves the conditional UKC availability branch already declared in `Debut_Ability_Snapshot_Protocol_v0_1.md`. It does not select a Debut Ability model, feature weight, shrinkage value, distance bandwidth, or predictive hyperparameter.

## Decision

For Debut/no-scored-history Ability target date `D`, the target identity/pedigree profile may use the latest valid UKC observation satisfying:

```text
profile_data_date <= D
```

A UKC observation whose `profile_data_date == D` is classified as **PRE_RACE profile data**, not current-result data, because JRDB daily UKC archives named for the target race date were directly verified as available before racing.

Historical result-derived priors remain unchanged and must still satisfy:

```text
historical source race_date < D
```

Same-day race results remain forbidden as historical inputs.

## Evidence

Controller probe Issue #332 (`[JRDB_UKC_AVAILABILITY_PROBE] 20260903-pre-race-check`) used the repository's existing authenticated JRDB access and performed HTTP-header-only requests. Credentials and archive bodies were not exposed.

Observed on 2026-09-03 at approximately 16:30 JST:

| target archive | HTTP | Last-Modified UTC | Last-Modified JST | relation to race date |
|---|---:|---|---|---|
| `Ukc/2026/UKC260829.zip` | 200 | 2026-08-28 06:26 | 2026-08-28 15:26 | prior day |
| `Ukc/2026/UKC260830.zip` | 200 | 2026-08-29 06:57 | 2026-08-29 15:57 | prior day |
| `Ukc/2026/UKC260905.zip` | 200 | 2026-08-30 10:51 | 2026-08-30 19:51 | six days before target |
| `Ukc/2026/UKC260906.zip` | 200 | 2026-08-31 07:06 | 2026-08-31 16:06 | six days before target |

The 2026-09-05 and 2026-09-06 target-date archives were already retrievable on 2026-09-03. Therefore filename/data-date equality with the race date does not imply post-race availability for UKC.

## Snapshot implementation rule

The Debut snapshot builder must:

1. select the latest UKC observation with `data_date <= race_date`;
2. retain `profile_data_date` exactly;
3. retain whether any strict-prior-day UKC observation existed;
4. retain whether a same-day UKC observation existed;
5. allow `profile_data_date == race_date` only under this verified UKC availability decision;
6. reject any selected `profile_data_date > race_date`;
7. never relax historical RunPerf/debut-prior chronology from `< race_date` to `<= race_date`.

`profile_data_date == race_date` is sufficient provenance to identify that the selected profile was same-day UKC without adding a new predictive feature.

## Audit consequence

The Debut structural audit must no longer count same-day UKC profile selection as leakage. It must instead fail closed on:

- future UKC profile use (`profile_data_date > race_date`);
- inconsistent profile availability flags;
- missing horse identity;
- all previously frozen result chronology, market contamination, non-finite evidence, duplicate-key, and target/result separation violations.

## Relationship to prior evidence

Issues #329 and #330 remain valid evidence for the earlier strict-prior-day implementation and are not deleted or rewritten. Their very low pedigree coverage demonstrated why the availability branch had to be resolved.

After this decision, the canonical Debut snapshot/coverage evidence must be regenerated with same-day UKC permitted. Predictive comparison must not begin until that regenerated structural package passes.

## Evaluation boundary

At the time of this decision:

```text
Debut predictive metrics computed: false
2024-2025 Debut predictive metrics inspected: false
Debut model selected: false
```

This availability decision therefore does not consume the frozen Debut predictive confirmation period.
