# Existing-Horse Ability Feature Decision v0.1

## Status

**FROZEN AFTER 2013-2023 DEVELOPMENT AND 2024-2025 PASS_STRONG CONFIRMATION**

This record maps the tested Ability feature candidates to the production-candidate Existing-Horse Ability v0.1 specification. It supplements the broader Feature Registry without redefining untested features.

## CORE in Existing-Horse Ability v0.1

| component | production setting | decision |
|---|---|---|
| recent_performance | `recent_perf_d070` | CORE |
| peak_performance | `peak_best1_last5`, `peak_best2_mean_last5` | CORE |
| peak_gap | `peak_best2_mean_last5 - recent_perf_d070` | CORE |
| performance_stability | `performance_mad_last5` | CORE |
| surface_fit | `surface_fit_delta_raw`, aptitude k=0 | CORE |
| distance_fit | `distance_d200_delta_raw`, bandwidth 200m, aptitude k=0 | CORE |
| course_fit | `course_exact_delta_raw`, aptitude k=0 | CORE |
| jockey_general_effect | `jockey_residual_mean_raw`, jockey k=0 | CORE |
| weight_relative | current PRE_RACE relative carried weight | CORE |
| career evidence | `log1p(career_scored_run_count)` | CORE |
| missingness | explicit missing flags from frozen A1 template | CORE |

`k=0` means no numerical shrink after evidence exists; missing evidence remains missing and is handled only through the frozen missing-flag + train-fold median preprocessing contract.

## Not in Existing-Horse Ability v0.1

| component | decision | reason |
|---|---|---|
| going_fit | REVISIT | verified historical target PRE_RACE going availability was zero; target SED final going is forbidden |
| rest_days | EDGE | state/change timing belongs to Edge under the frozen protocol |
| jockey_surface_effect | REVISIT | not part of the frozen A1 comparison template |
| jockey_course_effect | REVISIT | not part of the frozen A1 comparison template |
| trainer_general_effect | REVISIT | not part of the frozen A1 comparison template |
| pedigree_prior for existing horses | REVISIT | not required for v0.1 existing-horse winner; remains important for debut/low-history path |
| age_curve | REVISIT | not tested in frozen v0.1 comparison |
| bodyweight_absolute | REVISIT | not tested in frozen v0.1 comparison |
| odds/popularity/market | FORBIDDEN | Ability boundary |

## Evidence

Development 2013-2023:

- frozen Elastic Net mean primary: `0.490990` approximately;
- best A0 D070: `0.473766` approximately;
- Elastic Net delta vs A0 positive in 11/11 development years.

Temporal confirmation 2024-2025:

- 2024 delta vs A0 D070: `+0.017550366255286942`;
- 2025 delta vs A0 D070: `+0.01776975122981478`;
- mean delta: `+0.01766005874255086`;
- classification: `PASS_STRONG`;
- A1 prediction coverage: 1.0 in both years.

## Boundaries

These decisions apply to existing horses with `career_scored_run_count >= 1` only. They do not decide the Debut Ability feature set, Edge features, or later incremental additions. Any later feature addition must demonstrate incremental value under a new predeclared protocol; 2024-2025 can no longer be used as untouched selection evidence.
