# JRDB PWA 独自指数 Feature Registry v0.1

## 1. 目的

PWA新聞向け独自指数で検証する特徴量を、役割・source・availability・優先度・欠損方針・検証状態とともに管理する。

本Registryは `JRDB_PWA_Index_Design_v0_1.md` の実装台帳であり、最終係数や採否は development / holdout 後に更新する。

Status:

- `CORE_BUILD`: v0で必ず生成する
- `TEST`: v0で比較する
- `JRDB_TEST`: 独自Core完成後に追加価値を測る
- `LATER`: 後続候補
- `UNRESOLVED`: source/意味/availability監査が必要

Availability:

- `HISTORICAL`: 対象日より前の結果から生成
- `PRE_RACE`: 対象レース前に取得可能
- `CURRENT_RESULT`: 対象レース結果。予測入力禁止

---

## 2. RunPerf / Baseline

| feature | role | source | availability | status | note |
|---|---|---|---|---|---|
| course_base_time | RunPerf | BAC+SED | HISTORICAL | CORE_BUILD | venue×surface×distance rolling baseline |
| class_adjustment | RunPerf | BAC+SED | HISTORICAL | CORE_BUILD | CourseBaseとの差。二重class補正禁止 |
| expected_time | RunPerf | derived | HISTORICAL | CORE_BUILD | course_base_time + class_adjustment |
| race_representative_time | RunPerf | SED | CURRENT_RESULT | CORE_BUILD | 上位3頭中央値を初期候補 |
| day_track_bias | RunPerf | BAC+SED | CURRENT_RESULT | CORE_BUILD | historical run確定後の補正用途 |
| time_residual | RunPerf | derived | CURRENT_RESULT | CORE_BUILD | ExpectedTime - AdjustedTime |
| margin_sec | RunPerf | SED | CURRENT_RESULT | CORE_BUILD | 同レース実時計から自前算出 |
| rank_percentile | RunPerf | SED | CURRENT_RESULT | CORE_BUILD | B0 benchmark |
| jrdb_raw_score | Benchmark | SED | CURRENT_RESULT | JRDB_TEST | independent RunPerf benchmark |
| jrdb_idm | Benchmark | SED | CURRENT_RESULT | JRDB_TEST | independent RunPerf benchmark |

RunPerf candidate IDs: `B0`, `B1`, `T0`, `T1`, `T2`, `T3`, `J0`, `J1`。

---

## 3. Ability — Existing Horses

| feature | role | source | availability | status | missing / shrinkage |
|---|---|---|---|---|---|
| recent_performance | Ability | historical RunPerf | HISTORICAL | CORE_BUILD | valid recent runs only; decay比較 |
| peak_performance | Ability | historical RunPerf | HISTORICAL | CORE_BUILD | best1/best2 weighting比較 |
| peak_gap | Ability | derived | HISTORICAL | CORE_BUILD | peak - recent |
| performance_stability | Ability | historical RunPerf | HISTORICAL | CORE_BUILD | MAD候補; <3 runs missing |
| surface_fit | Ability | RunPerf+BAC | HISTORICAL | CORE_BUILD | shrink, unknown≠0 |
| distance_fit | Ability | RunPerf+BAC | HISTORICAL | CORE_BUILD | continuous distance kernel + shrink |
| course_fit | Ability | RunPerf+BAC | HISTORICAL | CORE_BUILD | venue→turn/surface hierarchical backoff |
| going_fit | Ability | RunPerf+SED | HISTORICAL | CORE_BUILD | same-going vs same-surface; strong shrink |
| jockey_general_effect | Ability | KYI+RunPerf | HISTORICAL | CORE_BUILD | horse-quality-adjusted residual |
| jockey_surface_effect | Ability | KYI+RunPerf | HISTORICAL | CORE_BUILD | shrink |
| weight_relative | Ability | KYI | PRE_RACE | CORE_BUILD | current weight - race mean |
| jockey_course_effect | Ability | KYI+RunPerf | HISTORICAL | TEST | strong shrink |
| trainer_general_effect | Ability | trainer+RunPerf | HISTORICAL | TEST | quality-adjusted residual |
| pedigree_prior | Ability | UKC+RunPerf | HISTORICAL | TEST | career evidence増加でweight減衰 |
| age_curve | Ability | profile+RunPerf | HISTORICAL/PRE_RACE | TEST | continuous/month-aware候補 |
| bodyweight_absolute | Ability | current entry | PRE_RACE | TEST | 主力扱いしない |

---

## 4. Edge — Core

### 4.1 Condition change

| feature | source | availability | status | definition |
|---|---|---|---|---|
| distance_fit_gain | Ability feature history | PRE_RACE | CORE_BUILD | current distance fit - previous-condition fit |
| surface_fit_gain | Ability feature history | PRE_RACE | CORE_BUILD | current - previous |
| course_fit_gain | Ability feature history | PRE_RACE | CORE_BUILD | current - previous |
| going_fit_gain | Ability feature history | PRE_RACE | CORE_BUILD | current - previous |
| class_change | BAC/KYI history | PRE_RACE | CORE_BUILD | up/down/same |
| class_gap | RunPerf+current class baseline | PRE_RACE | CORE_BUILD | previous RunPerf - current-class expected level |

### 4.2 Rest / stable cycle

| feature | source | availability | status | definition |
|---|---|---|---|---|
| rest_days | race history | PRE_RACE | CORE_BUILD | days since last run |
| rest_deviation | race history | PRE_RACE | CORE_BUILD | current log interval - horse historical median |
| stable_cycle | KYI | PRE_RACE | CORE_BUILD/PLUS | entry date / nth run; actual available_from audit required |
| trainer_first_up_effect | trainer+residual | HISTORICAL | TEST | first-up residual effect |
| trainer_second_up_effect | trainer+residual | HISTORICAL | TEST | second-up residual effect |

### 4.3 Training

Detailed semantics: `JRDB_Training_Index_Definitions.md`.

| feature | source | availability | status | note |
|---|---|---|---|---|
| workout_delta_prev | CHA / prepared workout | PRE_RACE | CORE_BUILD | current - previous |
| workout_delta_baseline | CHA / prepared workout | PRE_RACE | CORE_BUILD | current - historical EWMA |
| finish_index_delta | CHA/CYB | PRE_RACE | CORE_BUILD | current - baseline |
| training_volume_change | CYB | PRE_RACE | CORE_BUILD | A/B/C/D; context interaction |
| training_pattern | CYB | PRE_RACE | CORE_BUILD | amount × intensity pattern |
| training_course_type | CYB | PRE_RACE | TEST | slope/course/combined |
| jrdb_workout_index | CHA/CYB | PRE_RACE | JRDB_TEST | standardized workout material |
| jrdb_finish_index | CYB | PRE_RACE | JRDB_TEST | preparation state |
| jrdb_training_arrow | KYI | PRE_RACE | JRDB_TEST | human judgment; prioritize independent incremental test |
| jrdb_training_score | KYI | PRE_RACE | JRDB_TEST | expert-paper-derived score |

### 4.4 Pace / race interaction

| feature | source | availability | status | definition |
|---|---|---|---|---|
| early_position_propensity | historical running position | HISTORICAL | CORE_BUILD | recency-weighted normalized early position |
| late_performance | historical run | HISTORICAL | CORE_BUILD | relative late strength |
| race_pace_pressure | all runners historical style | PRE_RACE | CORE_BUILD | race-level forward pressure |
| leader_gap | all runners | PRE_RACE | CORE_BUILD | top early propensity - second |
| front_runner_count | all runners | PRE_RACE | CORE_BUILD | explanatory / candidate model input |
| pace_fit | derived | PRE_RACE | CORE_BUILD | style × race pressure residual model |
| jockey_style_fit | jockey+style residual | HISTORICAL/PRE_RACE | TEST | incremental after jockey/style main effects |
| jrdb_expected_position | KYI | PRE_RACE | JRDB_TEST | Addition Test |
| jrdb_expected_ten | KYI | PRE_RACE | JRDB_TEST | Addition Test |
| jrdb_running_style | KYI | PRE_RACE | JRDB_TEST | benchmark/addition |

### 4.5 Hidden Performance

| feature | source | availability | status | definition |
|---|---|---|---|---|
| finish_runperf_gap | SED+RunPerf | HISTORICAL | CORE_BUILD | RunPerf rank percentile - finish rank percentile |
| margin_residual | SED | HISTORICAL | CORE_BUILD | margin relative to finish-position expectation |
| late_strength_residual | SED/run features | HISTORICAL | CORE_BUILD | late strength given position/pace |
| early_load | pace+position | HISTORICAL | CORE_BUILD | early position × pace pressure |
| start_position_shock | historical positions | HISTORICAL | CORE_BUILD | actual early position - expected propensity |
| jrdb_slow_start | SED | HISTORICAL | JRDB_TEST | JRDB judgment/addition |
| jrdb_positioning | SED | HISTORICAL | JRDB_TEST | JRDB judgment/addition |
| jrdb_interference | SED | HISTORICAL | JRDB_TEST | total trouble |
| jrdb_early_interference | SED | HISTORICAL | JRDB_TEST | section trouble |
| jrdb_mid_interference | SED | HISTORICAL | JRDB_TEST | section trouble |
| jrdb_late_interference | SED | HISTORICAL | JRDB_TEST | section trouble |

### 4.6 Other changes

| feature | source | availability | status | note |
|---|---|---|---|---|
| jockey_change_delta | jockey effects | PRE_RACE | CORE_BUILD | current - previous jockey effect |
| weight_delta | KYI/SED history | PRE_RACE | CORE_BUILD | current - previous carried weight |
| bodyweight_delta | entry/result history | PRE_RACE if current weight available | CORE_BUILD/LIVE_BOUNDARY | published timingによりavailability要確認 |
| equipment_change | KYI | PRE_RACE | TEST | v0はblinker中心 |
| jockey_trainer_pair_effect | KYI+trainer+residual | HISTORICAL | TEST | pair residual after main effects |

---

## 5. Pedigree / Debut Ability

| feature | source | availability | status | shrinkage / note |
|---|---|---|---|---|
| sire_runperf | UKC+RunPerf | HISTORICAL | CORE_BUILD | time-aware, leave-one-horse-out |
| sire_debut_runperf | UKC+RunPerf | HISTORICAL | CORE_BUILD | first-career-run only |
| sire_surface_fit | UKC+RunPerf | HISTORICAL | CORE_BUILD | offspring baseline residual |
| sire_distance_fit | UKC+RunPerf | HISTORICAL | CORE_BUILD | continuous distance fit |
| damsire_runperf | UKC+RunPerf | HISTORICAL | CORE_BUILD | shrink |
| damsire_debut_runperf | UKC+RunPerf | HISTORICAL | CORE_BUILD | shrink |
| damsire_surface_fit | UKC+RunPerf | HISTORICAL | CORE_BUILD | shrink |
| damsire_distance_fit | UKC+RunPerf | HISTORICAL | CORE_BUILD | shrink |
| sire_line_runperf | UKC/codebook+RunPerf | HISTORICAL | CORE_BUILD | new/low-sample sire backoff |
| damsire_line_runperf | UKC/codebook+RunPerf | HISTORICAL | CORE_BUILD | backoff |
| dam_offspring_runperf | UKC+RunPerf | HISTORICAL | TEST | dam identity audit first |
| dam_offspring_debut_runperf | UKC+RunPerf | HISTORICAL | TEST | siblings debut prior |
| sire_x_damsire_line_effect | UKC+RunPerf | HISTORICAL | LATER | strong shrink / minimum n |

Pedigree prior weight is expected to decline as career race evidence increases; exact curve is data-selected.

---

## 6. Debut Training

| feature | source | availability | status | note |
|---|---|---|---|---|
| debut_workout_index | CHA/JRDB prepared | PRE_RACE | CORE_BUILD | cohort-relative absolute level |
| debut_finish_index | CHA/CYB | PRE_RACE | CORE_BUILD | cohort-relative |
| debut_effort_efficiency | CHA | PRE_RACE | CORE_BUILD | performance conditional on effort |
| debut_pair_strength | CHA | PRE_RACE | CORE_BUILD | pair result + opponent class/effort |
| training_volume | CYB | PRE_RACE | CORE_BUILD | debut absolute information |
| training_pattern | CYB | PRE_RACE | CORE_BUILD | amount × intensity |
| training_course_type | CYB | PRE_RACE | CORE_BUILD | slope/course/combined |
| jockey_debut_effect | KYI+RunPerf | HISTORICAL | CORE_BUILD | quality-adjusted |
| trainer_debut_effect | trainer+RunPerf | HISTORICAL | CORE_BUILD | quality-adjusted |
| workout_exceptionalness | derived | PRE_RACE | TEST | Debut Edge candidate |
| training_volume_surprise | derived | PRE_RACE | TEST | Debut Edge candidate |

---

## 7. JRDB Addition Candidates

独自Coreへ直接混ぜず、追加価値を個別測定する。

| feature group | examples | status |
|---|---|---|
| condition judgment | uptrend, distance aptitude, heavy aptitude | JRDB_TEST |
| training judgment | training arrow, training score, finish index, stable evaluation | JRDB_TEST |
| trouble judgment | slow start, positioning, interference | JRDB_TEST |
| pace prediction | expected ten, expected position, race pace prediction | JRDB_TEST |
| finished/composite predictions | total index, upset/longshot composite, final marks | BENCHMARK / normally not ingredient |

---

## 8. Physical / Institutional Conditional Factors

| feature | role | status | policy |
|---|---|---|---|
| weight_relative | Ability | CORE_BUILD | race-relative burden |
| weight_delta | Edge | CORE_BUILD | previous-run change |
| bodyweight_delta | Edge / live boundary | TEST | context with rest/age |
| age_in_months | prior / interaction | TEST | not fixed age bonus |
| sex | interaction | TEST | standalone weak prior |
| sex_x_season | Edge interaction | TEST | e.g. "summer mares" hypothesis |
| weight_x_handicap | Edge interaction | TEST | handicap-race hypothesis |
| weight_x_distance | interaction | LATER | only if stable |
| bodyweight_x_surface | interaction | LATER | only if stable |

---

## 9. Confidence Registry

Candidate components:

- career_count
- recent_run_count
- surface_fit_neff
- distance_fit_neff
- course_fit_neff
- going_fit_neff
- pedigree_sample_size
- workout_history_count
- prediction_uncertainty

Confidence does not reduce Ability score directly. It is an independent uncertainty indicator.

---

## 10. Feature persistence contract

Final value only must not be persisted.

For each shrinkable feature, keep where applicable:

```text
<feature>_raw
<feature>_shrunk
<feature>_n
<feature>_neff
<feature>_missing
<feature>_config
```

Every scored snapshot also keeps:

```text
formula_version
model_version
source_snapshot
calculated_at
as_of_exclusive
validation_status
```

---

## 11. Validation record contract

Each candidate should eventually have a Git-managed decision record containing at least:

```text
feature
role
source
available_from
development_period
model_baseline
effect_size
direction_consistency
incremental_metrics
applicable_conditions
holdout_result
decision
model_version
notes
```

Decision values:

- `CORE`
- `PLUS`
- `REJECT`
- `REVISIT`

---

## 12. Immediate build scope

### Ability v0 first build

```text
recent_performance
peak_performance
performance_stability
surface_fit
distance_fit
course_fit
going_fit
jockey_general_effect
weight_relative
```

### Edge v0 first build

```text
distance_fit_gain
class_change
class_gap
rest_days
rest_deviation
workout_delta_baseline
pace_fit
finish_runperf_gap
```

### Debut v0 first build

```text
sire_debut_runperf
damsire_debut_runperf
sire/damsire surface and distance fit
debut_workout_index
debut_finish_index
jockey_debut_effect
trainer_debut_effect
```

This subset is intentionally small. Additional features are promoted only after incremental validation.
