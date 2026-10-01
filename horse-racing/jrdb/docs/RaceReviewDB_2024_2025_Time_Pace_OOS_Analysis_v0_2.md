# RaceReviewDB 2024–2025 Time / Pace Historical OOS 分析 v0.2

## 検証結論

条件を2026年9月から変更せず、RRDBの凍結済み2024–2025年sourceレースから同一horse_idの直後の平地出走へ連結して評価した。source featuresはsource race時点のRRDB保存値を使用。OOSの結果を見た閾値調整、S/A昇格、HVルール変更はしていない。

能力面はv0.1の次走着順分析を維持し、再計算していない。今回、Drive正本のSED_2024.zip / SED_2025.zipと、2026年対象開催日のSEDを取得し、targetの人気・単勝オッズ・払戻を既存factへ後付けした。signal条件、source-target mapping、能力集計は変更していない。

## 1. Data audit

```json
{
  "source_period": "2024-01-01..2025-12-31",
  "rrdb_snapshot_max_date": "2026-09-27",
  "source_period_flat_entry_count": 92279,
  "source_starts_flat_with_result_count": 91597,
  "source_to_next_flat_start_mapped_count": 81767,
  "source_without_next_flat_start_in_snapshot_count": 9830,
  "duplicate_source_key_count": 0,
  "duplicate_source_target_mapping_count": 0,
  "target_date_le_source_date_count": 0,
  "source_target_identity_mismatch_count": 0,
  "historical_standard_asof_violation_count": 0,
  "pace_asof_recompute_mismatch_count": 0,
  "source_time_missing_count": 682,
  "time_class_quality_gate_eligible_count": 13197,
  "target_finish_unclassified_count": 569,
  "frozen_rule_version": "next-watch-rules-discovery-v0.1",
  "hv_performance_q80_threshold": -0.09305555555555287,
  "thresholds_reoptimized": false,
  "formal_rules_changed": false,
  "status": "PASS",
  "archive_count": 84,
  "record_count_by_year": {
    "2024": 47181,
    "2025": 47884,
    "2026": 35995
  },
  "record_count": 131060,
  "malformed_record_count": 0,
  "record_length_error_count": 0,
  "duplicate_race_horse_key_count": 0,
  "source_fact_rows_before_enrichment": 81767,
  "source_fact_rows_after_enrichment": 81767,
  "target_join_matched_count": 81767,
  "target_join_missing_count": 0,
  "target_join_rows_by_target_year": {
    "2024": 34061,
    "2025": 41141,
    "2026": 6565
  },
  "horse_id_mismatch_count": 0,
  "target_finish_sed_vs_rrdb_mismatch_count": 0,
  "abnormal_code_distribution_in_target_join": {
    "0": 81198,
    "1": 106,
    "2": 184,
    "3": 279
  },
  "unknown_popularity_count_in_target_join": 287,
  "odds_missing_count_in_target_join": 290,
  "invalid_odds_nonpositive_count_in_target_join": 0,
  "blank_payout_count_in_target_join": 139771,
  "win_payout_blank_count_in_target_join": 75780,
  "place_payout_blank_count_in_target_join": 63991,
  "market_baseline_race_count": 7305,
  "market_baseline_all_sed_starter_count": 102262,
  "market_baseline_valid_starter_count": 101895,
  "signal_positive_n": {
    "TIME_CLASS_PLUS1": 386,
    "TIME_CLASS_PLUS2": 104,
    "TC-A_WIN_PLUS1": 173,
    "TC-B_FINISH_2_5_PLUS1": 182,
    "TC-C_FINISH_6PLUS_PLUS1": 31,
    "FRONT_SURVIVE_GAP05": 4612,
    "FRONT_SURVIVE_GAP08": 6096,
    "FRONT_SURVIVE_HALF": 7692,
    "FRONT_SURVIVE_OR": 7760,
    "FRONT_SURVIVE_STRICT": 4544,
    "REAR_HIGH_LAST3F80": 2608,
    "REAR_HIGH_LAST3F90": 1610,
    "REAR_HIGH_LAST3F90_GAP05": 748,
    "HV01": 6014,
    "HV02": 3165,
    "POSITION_RECOVERY": 10216,
    "HV07_POSITION_RECOVERY": 3060,
    "TC1_FRONT05": 57,
    "TC1_FRONT_OR": 70,
    "TC1_REAR90": 2,
    "HV01_TC1": 79,
    "HV02_TC1": 31
  },
  "expected_major_signal_positive_n": {
    "TIME_CLASS_PLUS1": 386,
    "FRONT_SURVIVE_GAP05": 4612,
    "FRONT_SURVIVE_OR": 7760,
    "REAR_HIGH_LAST3F90": 1610,
    "HV01": 6014,
    "HV02": 3165,
    "HV01_TC1": 79
  },
  "sed_join_status": "AVAILABLE_SED_2024_2025_PLUS_2026_TARGET_DATES",
  "sed_historical_archives_available": true,
  "market_outcomes_available": true,
  "market_rows_set_to_zero": false,
  "payout_blank_fields_zeroed_after_verified_race_coverage": true,
  "payout_coverage": {
    "payout_coverage_race_count": 9519,
    "payout_incomplete_race_count": 0
  },
  "market_supported_rule": "valid_market_n>=30 and positive place ROI difference against both popularity-bucket and odds-bucket weighted general-market baselines"
}
```

## 固定条件

- TIME_CLASS_PLUS1/2: Historical numeric gap `>=1` / `>=2`。`class_curve_monotonic=true`、numeric equivalentとgapが全て非NULLの場合のみ評価。
- FRONT exposure: pace percentile `>=70` and 4角 frontness `>=0.60`; survive conditions use winner gap `<=0.50` / `<=0.80`, field-size half, OR and strict variants.
- REAR exposure: pace percentile `<=30` and 4角 frontness `<=0.40`; LAST3F thresholds `>=80` / `>=90`; optional winner gap `<=0.50`.
- HV01/HV02 use exact frozen rule contract `next-watch-rules-discovery-v0.1`, performance_signal Q80 = `-0.09305555555555287`; performance_signal is `-horse_adjusted_delta_per_1000m`.
- Position Recovery uses frozen feature contract `overall_position_gain>=0.25`; missing remains unevaluable.
- Historical standard sample end date is checked strictly earlier than source date. Stored pace percentile/sample/scope is independently recomputed using strictly earlier same-surface/distance races, exact venue first, then broad venue fallback.

## 2. TIME_CLASS_PLUS1

### Primary and subtype

| signal           |   signal_evaluable_n |   N |   next_win_rate |   next_top3_rate |   next_top5_rate |   average_next_finish_classified |   average_finish_improvement |   top3_lift_vs_matched_baseline |   top3_lift_ci95_low |   top3_lift_ci95_high |   periods_with_target_top3 |
|:-----------------|---------------------:|----:|----------------:|-----------------:|-----------------:|---------------------------------:|-----------------------------:|--------------------------------:|---------------------:|----------------------:|---------------------------:|
| TIME_CLASS_PLUS1 |                13197 | 386 |           0.189 |            0.417 |            0.598 |                            5.229 |                       -2.779 |                           0.076 |                0.028 |                  0.13 |                          4 |

Matched baseline uses the same source finish band, declared class, surface, and distance category. Bootstrap resamples target races as clusters (500 replicates); intervals are for top3-rate lift only.

## 3. Front Pace Opposition


| signal               |   signal_evaluable_n |     N |   next_win_rate |   next_top3_rate |   next_top5_rate |   average_next_finish_classified |   top3_lift_vs_matched_baseline | top3_lift_ci95_low   | top3_lift_ci95_high   |   periods_with_target_top3 |
|:---------------------|---------------------:|------:|----------------:|-----------------:|-----------------:|---------------------------------:|--------------------------------:|:---------------------|:----------------------|---------------------------:|
| FRONT_EXPOSURE       |                77873 | 11448 |           0.099 |            0.278 |            0.434 |                            6.984 |                           0.057 | —                    | —                     |                          4 |
| FRONT_SURVIVE_GAP05  |                80605 |  4612 |           0.138 |            0.362 |            0.535 |                            5.977 |                           0.142 | 0.129                | 0.155                 |                          4 |
| FRONT_SURVIVE_GAP08  |                80071 |  6096 |           0.128 |            0.345 |            0.516 |                            6.17  |                           0.124 | 0.113                | 0.135                 |                          4 |
| FRONT_SURVIVE_HALF   |                79572 |  7692 |           0.121 |            0.333 |            0.508 |                            6.215 |                           0.054 | 0.045                | 0.063                 |                          4 |
| FRONT_SURVIVE_OR     |                79547 |  7760 |           0.12  |            0.332 |            0.506 |                            6.229 |                           0.111 | 0.101                | 0.121                 |                          4 |
| FRONT_SURVIVE_STRICT |                80630 |  4544 |           0.14  |            0.364 |            0.538 |                            5.95  |                           0.085 | 0.072                | 0.098                 |                          4 |

FRONT_EXPOSURE is descriptive only. Interpret FRONT_SURVIVE_GAP05 and FRONT_SURVIVE_OR as primary; the 0.8s, half-field and strict variants are sensitivity checks fixed in advance.

## 4. Rear Pace Opposition


| signal                              |   signal_evaluable_n |    N | next_win_rate   | next_top3_rate   | next_top5_rate   | average_next_finish_classified   | top3_lift_vs_matched_baseline   | top3_lift_ci95_low   | top3_lift_ci95_high   |   periods_with_target_top3 |
|:------------------------------------|---------------------:|-----:|:----------------|:-----------------|:-----------------|:---------------------------------|:--------------------------------|:---------------------|:----------------------|---------------------------:|
| REAR_EXPOSURE                       |                77873 | 8098 | 0.041           | 0.135            | 0.267            | 8.529                            | -0.085                          | —                    | —                     |                          4 |
| REAR_HIGH_LAST3F80                  |                80653 | 2608 | 0.074           | 0.234            | 0.411            | 6.880                            | 0.013                           | -0.003               | 0.029                 |                          4 |
| REAR_HIGH_LAST3F90                  |                81092 | 1610 | 0.090           | 0.266            | 0.444            | 6.537                            | 0.046                           | 0.025                | 0.067                 |                          4 |
| REAR_HIGH_LAST3F90_GAP05            |                81348 |  748 | 0.118           | 0.333            | 0.521            | 5.954                            | 0.112                           | —                    | —                     |                          4 |
| REAR_HIGH_LAST3F90_CLOSING_POSITIVE |                79506 |    0 | —               | —                | —                | —                                | —                               | —                    | —                     |                          0 |

REAR_EXPOSURE alone is descriptive. Closing gain is supplementary and has its own missingness; it is not interpreted as zero.

## 5. HV01 / HV02 and Position Recovery


| signal                 |   signal_evaluable_n |     N |   next_win_rate |   next_top3_rate |   next_top5_rate |   average_next_finish_classified |   top3_lift_vs_matched_baseline |   top3_lift_ci95_low |   top3_lift_ci95_high |   periods_with_target_top3 |
|:-----------------------|---------------------:|------:|----------------:|-----------------:|-----------------:|---------------------------------:|--------------------------------:|---------------------:|----------------------:|---------------------------:|
| HV01                   |                81767 |  6014 |           0.095 |            0.278 |            0.452 |                            6.669 |                           0.116 |                0.107 |                 0.127 |                          4 |
| HV02                   |                81767 |  3165 |           0.064 |            0.205 |            0.358 |                            7.507 |                           0.077 |                0.063 |                 0.091 |                          4 |
| POSITION_RECOVERY      |                38567 | 10216 |           0.097 |            0.299 |            0.483 |                            6.252 |                           0.07  |                0.063 |                 0.077 |                          4 |
| HV07_POSITION_RECOVERY |                38567 |  3060 |           0.072 |            0.243 |            0.428 |                            6.688 |                           0.082 |                0.066 |                 0.098 |                          4 |

HV01/HV02 thresholds come from the frozen contract. Position Recovery is reported independently from Pace Opposition.

## 6. Time × Pace / HV combinations


| signal       |   N |   next_win_rate |   next_top3_rate |   next_top5_rate |   average_next_finish_classified |   top3_lift_vs_matched_baseline |   top3_lift_ci95_low |   top3_lift_ci95_high |   periods_with_target_top3 |
|:-------------|----:|----------------:|-----------------:|-----------------:|---------------------------------:|--------------------------------:|---------------------:|----------------------:|---------------------------:|
| TC1_FRONT05  |  57 |           0.263 |            0.386 |            0.561 |                            5.561 |                          -0.031 |               -0.151 |                 0.082 |                          4 |
| TC1_FRONT_OR |  70 |           0.243 |            0.414 |            0.586 |                            5.414 |                          -0.003 |               -0.108 |                 0.101 |                          4 |
| TC1_REAR90   |   2 |           0     |            0.5   |            0.5   |                            6.5   |                           0.083 |               -0.453 |                 0.622 |                          1 |
| HV01_TC1     |  79 |           0.165 |            0.392 |            0.57  |                            5.282 |                           0.114 |                0.004 |                 0.238 |                          4 |
| HV02_TC1     |  31 |           0.097 |            0.29  |            0.548 |                            5.71  |                           0.085 |               -0.044 |                 0.227 |                          3 |

Combination baselines are their parent signal (TIME_CLASS_PLUS1 or HV01/HV02). A composite should show incremental gain over its parent, not just a high standalone hit rate.

## 7. Half-year stability


| oos_block   | signal                 |   signal_evaluable_n |    N | next_top3_rate   | next_top5_rate   | average_next_finish_classified   |   periods_with_target_top3 |
|:------------|:-----------------------|---------------------:|-----:|:-----------------|:-----------------|:---------------------------------|---------------------------:|
| 2024H1      | FRONT_SURVIVE_GAP05    |                21510 | 1382 | 0.357            | 0.535            | 6.007                            |                          1 |
| 2024H2      | FRONT_SURVIVE_GAP05    |                18712 | 1044 | 0.350            | 0.528            | 6.065                            |                          1 |
| 2025H1      | FRONT_SURVIVE_GAP05    |                21265 | 1299 | 0.357            | 0.535            | 5.949                            |                          1 |
| 2025H2      | FRONT_SURVIVE_GAP05    |                19118 |  887 | 0.393            | 0.543            | 5.868                            |                          1 |
| 2024H1      | FRONT_SURVIVE_OR       |                21309 | 2386 | 0.336            | 0.519            | 6.150                            |                          1 |
| 2024H2      | FRONT_SURVIVE_OR       |                18476 | 1696 | 0.317            | 0.489            | 6.328                            |                          1 |
| 2025H1      | FRONT_SURVIVE_OR       |                21074 | 2228 | 0.328            | 0.504            | 6.222                            |                          1 |
| 2025H2      | FRONT_SURVIVE_OR       |                18688 | 1450 | 0.350            | 0.509            | 6.252                            |                          1 |
| 2024H1      | HV01                   |                21716 | 1572 | 0.279            | 0.448            | 6.660                            |                          1 |
| 2024H2      | HV01                   |                18972 | 1329 | 0.266            | 0.414            | 6.884                            |                          1 |
| 2025H1      | HV01                   |                21410 | 1509 | 0.296            | 0.499            | 6.325                            |                          1 |
| 2025H2      | HV01                   |                19669 | 1604 | 0.271            | 0.441            | 6.823                            |                          1 |
| 2024H1      | HV01_TC1               |                20274 |   27 | 0.333            | 0.444            | 6.000                            |                          1 |
| 2024H2      | HV01_TC1               |                17772 |    4 | 0.250            | 0.500            | 6.500                            |                          1 |
| 2025H1      | HV01_TC1               |                20045 |   25 | 0.320            | 0.640            | 5.080                            |                          1 |
| 2025H2      | HV01_TC1               |                18250 |   23 | 0.565            | 0.652            | 4.409                            |                          1 |
| 2024H1      | HV02                   |                21716 |  841 | 0.197            | 0.354            | 7.452                            |                          1 |
| 2024H2      | HV02                   |                18972 |  690 | 0.201            | 0.310            | 7.717                            |                          1 |
| 2025H1      | HV02                   |                21410 |  796 | 0.217            | 0.413            | 7.152                            |                          1 |
| 2025H2      | HV02                   |                19669 |  838 | 0.205            | 0.350            | 7.725                            |                          1 |
| 2024H1      | HV02_TC1               |                20931 |   15 | 0.200            | 0.333            | 6.600                            |                          1 |
| 2024H2      | HV02_TC1               |                18325 |    0 | —                | —                | —                                |                          0 |
| 2025H1      | HV02_TC1               |                20674 |   12 | 0.250            | 0.667            | 5.667                            |                          1 |
| 2025H2      | HV02_TC1               |                18903 |    4 | 0.750            | 1.000            | 2.500                            |                          1 |
| 2024H1      | HV07_POSITION_RECOVERY |                10323 |  827 | 0.235            | 0.418            | 6.813                            |                          1 |
| 2024H2      | HV07_POSITION_RECOVERY |                 8947 |  680 | 0.244            | 0.413            | 6.801                            |                          1 |
| 2025H1      | HV07_POSITION_RECOVERY |                10274 |  855 | 0.240            | 0.446            | 6.556                            |                          1 |
| 2025H2      | HV07_POSITION_RECOVERY |                 9023 |  698 | 0.258            | 0.433            | 6.593                            |                          1 |
| 2024H1      | POSITION_RECOVERY      |                10323 | 2713 | 0.289            | 0.482            | 6.242                            |                          1 |
| 2024H2      | POSITION_RECOVERY      |                 8947 | 2351 | 0.297            | 0.484            | 6.195                            |                          1 |
| 2025H1      | POSITION_RECOVERY      |                10274 | 2740 | 0.295            | 0.481            | 6.351                            |                          1 |
| 2025H2      | POSITION_RECOVERY      |                 9023 | 2412 | 0.316            | 0.484            | 6.209                            |                          1 |
| 2024H1      | REAR_HIGH_LAST3F90     |                21592 |  391 | 0.240            | 0.468            | 6.545                            |                          1 |
| 2024H2      | REAR_HIGH_LAST3F90     |                18823 |  367 | 0.300            | 0.452            | 6.399                            |                          1 |
| 2025H1      | REAR_HIGH_LAST3F90     |                21303 |  419 | 0.258            | 0.434            | 6.641                            |                          1 |
| 2025H2      | REAR_HIGH_LAST3F90     |                19374 |  433 | 0.270            | 0.425            | 6.543                            |                          1 |
| 2024H1      | TC1_FRONT05            |                20433 |   11 | 0.364            | 0.636            | 4.545                            |                          1 |
| 2024H2      | TC1_FRONT05            |                17977 |   19 | 0.211            | 0.421            | 6.789                            |                          1 |
| 2025H1      | TC1_FRONT05            |                20260 |   16 | 0.438            | 0.562            | 5.500                            |                          1 |
| 2025H2      | TC1_FRONT05            |                18601 |   11 | 0.636            | 0.727            | 4.545                            |                          1 |
| 2024H1      | TC1_FRONT_OR           |                19518 |   13 | 0.385            | 0.615            | 4.615                            |                          1 |
| 2024H2      | TC1_FRONT_OR           |                17402 |   21 | 0.238            | 0.429            | 6.857                            |                          1 |
| 2025H1      | TC1_FRONT_OR           |                19475 |   21 | 0.429            | 0.619            | 5.238                            |                          1 |
| 2025H2      | TC1_FRONT_OR           |                17950 |   15 | 0.667            | 0.733            | 4.333                            |                          1 |
| 2024H1      | TC1_REAR90             |                21330 |    0 | —                | —                | —                                |                          0 |
| 2024H2      | TC1_REAR90             |                18607 |    0 | —                | —                | —                                |                          0 |
| 2025H1      | TC1_REAR90             |                21040 |    1 | 1.000            | 1.000            | 2.000                            |                          1 |
| 2025H2      | TC1_REAR90             |                19104 |    1 | 0.000            | 0.000            | 11.000                           |                          0 |
| 2024H1      | TIME_CLASS_PLUS1       |                 2884 |   80 | 0.388            | 0.600            | 4.912                            |                          1 |
| 2024H2      | TIME_CLASS_PLUS1       |                 3272 |   92 | 0.380            | 0.522            | 5.648                            |                          1 |
| 2025H1      | TIME_CLASS_PLUS1       |                 3348 |   87 | 0.391            | 0.632            | 5.437                            |                          1 |
| 2025H2      | TIME_CLASS_PLUS1       |                 3693 |  127 | 0.480            | 0.630            | 4.984                            |                          1 |

Rates are descriptive; small block N is shown explicitly.

## 8. Market settlement / popularity / odds / high payouts

### Main signals

ROI is returned yen divided by 100-yen stakes for every valid target starter. Refund cases (SED abnormal code 1/2) are excluded from stake; abnormal codes 3–6 remain started outcomes. Blank losing payout fields were converted to zero only after complete SED race-level payout coverage passed.

| signal | N | valid_market_n | median_popularity | median_win_odds | place_hit_rate_pct | place_ROI_pct | place_ROI_diff_vs_odds_bucket_pp | place_ROI_diff_vs_popularity_bucket_pp | market_classification |
|---|---|---|---|---|---|---|---|---|---|
| TIME_CLASS_PLUS1 | 386 | 385 | 3.00 | 5.30 | 41.30 | 76.96 | -3.54 | -2.32 | NOT_SUPPORTED |
| FRONT_SURVIVE_GAP05 | 4612 | 4593 | 4.00 | 7.10 | 36.08 | 73.80 | -5.70 | -3.96 | NOT_SUPPORTED |
| FRONT_SURVIVE_OR | 7760 | 7734 | 4.00 | 9.00 | 33.13 | 76.67 | -1.78 | -0.09 | NOT_SUPPORTED |
| REAR_HIGH_LAST3F90 | 1610 | 1602 | 6.00 | 15.40 | 26.65 | 77.87 | 2.05 | 3.93 | MARKET_SUPPORTED |
| HV01 | 6014 | 5998 | 6.00 | 15.20 | 27.66 | 80.84 | 5.00 | 6.50 | MARKET_SUPPORTED |
| HV02 | 3165 | 3156 | 7.00 | 23.90 | 20.37 | 76.49 | 3.29 | 4.44 | MARKET_SUPPORTED |
| HV01_TC1 | 79 | 78 | 4.50 | 9.00 | 39.74 | 121.41 | 44.26 | 45.42 | MARKET_SUPPORTED |

### High payout concentration

Top-one/top-three shares use total signal place payout as denominator. Excluding-payout ROI is a sensitivity only; the primary ROI retains all payouts.

| signal | max_place_payout_yen | top1_payout_share_pct | top3_payout_share_pct | place_payout_ge_500_n | place_payout_ge_1000_n | place_hit_dates_n | place_hit_half_year_blocks_n | place_ROI_ex_top1_pct | place_ROI_ex_top3_pct |
|---|---|---|---|---|---|---|---|---|---|
| TIME_CLASS_PLUS1 | 1010.00 | 3.41 | 9.25 | 8 | 1 | 103 | 6 | 74.34 | 69.84 |
| FRONT_SURVIVE_GAP05 | 2160.00 | 0.64 | 1.48 | 70 | 9 | 243 | 6 | 73.33 | 72.71 |
| FRONT_SURVIVE_OR | 5840.00 | 0.98 | 1.85 | 160 | 23 | 252 | 6 | 75.92 | 75.25 |
| REAR_HIGH_LAST3F90 | 7030.00 | 5.64 | 10.19 | 39 | 13 | 186 | 5 | 73.48 | 69.94 |
| HV01 | 4190.00 | 0.86 | 2.27 | 183 | 38 | 247 | 6 | 80.15 | 79.00 |
| HV02 | 4190.00 | 1.74 | 4.57 | 119 | 31 | 222 | 6 | 75.16 | 72.99 |
| HV01_TC1 | 1010.00 | 10.67 | 28.93 | 5 | 1 | 27 | 6 | 108.46 | 86.28 |

### Matched market baselines

Popularity-matched and odds-matched baselines are weighted by each signal's runner counts across the same fixed buckets. The comparison population is every valid SED starter in races represented in the frozen OOS fact, including runners outside the OOS source-to-target mapping. Differences are percentage points of place ROI or place-hit rate. They are descriptive, not threshold-selection evidence.

Bucket details are in `analysis/oos/rrdb_2024_2025_signal_oos_market_buckets.csv`. Half-year market results use target date and include 2026 H1 and partial H2 as supplemental blocks because mapped next starts extend through 2026-09-27. High payout rows at 500 yen or more are in `analysis/oos/rrdb_2024_2025_signal_oos_high_payout.csv`.

### Half-year market stability (required 2024–2025 blocks)

2026 target-date blocks are retained as supplemental rows in the CSV.

| signal | target_half_year | valid_market_n | median_popularity | median_win_odds | place_hit_rate_pct | place_ROI_pct |
|---|---|---|---|---|---|---|
| TIME_CLASS_PLUS1 | 2024H1 | 55 | 3.00 | 5.70 | 38.18 | 82.91 |
| TIME_CLASS_PLUS1 | 2024H2 | 95 | 3.00 | 5.10 | 41.05 | 64.00 |
| TIME_CLASS_PLUS1 | 2025H1 | 64 | 3.00 | 5.35 | 28.12 | 40.62 |
| TIME_CLASS_PLUS1 | 2025H2 | 140 | 2.50 | 5.15 | 45.71 | 90.71 |
| FRONT_SURVIVE_GAP05 | 2024H1 | 1030 | 3.00 | 6.75 | 36.80 | 71.28 |
| FRONT_SURVIVE_GAP05 | 2024H2 | 1060 | 4.00 | 7.40 | 34.15 | 70.05 |
| FRONT_SURVIVE_GAP05 | 2025H1 | 1232 | 3.50 | 6.70 | 35.06 | 71.56 |
| FRONT_SURVIVE_GAP05 | 2025H2 | 1025 | 4.00 | 7.20 | 39.02 | 82.39 |
| FRONT_SURVIVE_OR | 2024H1 | 1812 | 4.00 | 8.75 | 34.44 | 82.06 |
| FRONT_SURVIVE_OR | 2024H2 | 1709 | 5.00 | 8.90 | 31.60 | 71.39 |
| FRONT_SURVIVE_OR | 2025H1 | 2135 | 4.00 | 8.90 | 31.85 | 72.71 |
| FRONT_SURVIVE_OR | 2025H2 | 1662 | 4.00 | 9.10 | 35.02 | 80.08 |
| REAR_HIGH_LAST3F90 | 2024H1 | 299 | 6.00 | 14.60 | 24.75 | 73.68 |
| REAR_HIGH_LAST3F90 | 2024H2 | 336 | 6.00 | 14.50 | 30.95 | 98.27 |
| REAR_HIGH_LAST3F90 | 2025H1 | 431 | 6.00 | 15.30 | 26.68 | 77.96 |
| REAR_HIGH_LAST3F90 | 2025H2 | 433 | 6.00 | 16.60 | 24.71 | 68.59 |
| HV01 | 2024H1 | 1144 | 6.00 | 13.65 | 29.37 | 73.29 |
| HV01 | 2024H2 | 1317 | 6.00 | 16.90 | 27.41 | 86.37 |
| HV01 | 2025H1 | 1478 | 6.00 | 14.20 | 27.74 | 83.37 |
| HV01 | 2025H2 | 1500 | 6.00 | 15.30 | 27.53 | 77.67 |
| HV02 | 2024H1 | 584 | 7.00 | 20.95 | 20.72 | 62.67 |
| HV02 | 2024H2 | 686 | 8.00 | 29.55 | 20.70 | 85.19 |
| HV02 | 2025H1 | 771 | 7.00 | 24.00 | 19.71 | 81.43 |
| HV02 | 2025H2 | 769 | 7.00 | 23.40 | 21.07 | 72.44 |
| HV01_TC1 | 2024H1 | 20 | 5.00 | 9.55 | 30.00 | 114.00 |
| HV01_TC1 | 2024H2 | 10 | 4.00 | 7.40 | 30.00 | 44.00 |
| HV01_TC1 | 2025H1 | 11 | 5.00 | 9.40 | 27.27 | 55.45 |
| HV01_TC1 | 2025H2 | 32 | 4.00 | 10.20 | 43.75 | 133.75 |

## 9. OOS status


| signal                 | classification      |     N |   top3_lift_vs_matched_baseline |   blocks_positive |
|:-----------------------|:--------------------|------:|--------------------------------:|------------------:|
| TIME_CLASS_PLUS1       | SUPPORTED           |   386 |                           0.076 |                 3 |
| FRONT_SURVIVE_GAP05    | SUPPORTED           |  4612 |                           0.142 |                 4 |
| FRONT_SURVIVE_OR       | SUPPORTED           |  7760 |                           0.111 |                 4 |
| REAR_HIGH_LAST3F90     | SUPPORTED           |  1610 |                           0.046 |                 4 |
| HV01                   | SUPPORTED           |  6014 |                           0.116 |                 4 |
| HV02                   | SUPPORTED           |  3165 |                           0.077 |                 4 |
| POSITION_RECOVERY      | SUPPORTED           | 10216 |                           0.07  |                 4 |
| HV07_POSITION_RECOVERY | SUPPORTED           |  3060 |                           0.082 |                 4 |
| TC1_FRONT05            | NOT_SUPPORTED       |    57 |                          -0.031 |                 2 |
| TC1_FRONT_OR           | NOT_SUPPORTED       |    70 |                          -0.003 |                 2 |
| TC1_REAR90             | INSUFFICIENT_SAMPLE |     2 |                           0.083 |                 0 |
| HV01_TC1               | SUPPORTED           |    79 |                           0.114 |                 3 |
| HV02_TC1               | MIXED               |    31 |                           0.085 |                 2 |

Classification is descriptive: SUPPORTED requires N>=30, positive full-period matched top3 lift and positive direction in at least 3 half-year blocks with N>=10; MIXED is positive overall but weaker block consistency; NOT_SUPPORTED is no positive overall lift; INSUFFICIENT_SAMPLE has N<30. It does not imply statistical significance or formal adoption. Market classifications are descriptive relative-market comparisons from the SED extension in section 8; no formal rule was promoted.

## 10. Required questions

- Q1 TIME_CLASS_PLUS1: N=385, place ROI=77.0%, odds-matched difference=-3.5pt, popularity-matched difference=-2.3pt; NOT_SUPPORTED.
- Q2 FRONT_SURVIVE_GAP05: N=4593, place ROI=73.8%, odds-matched difference=-5.7pt, popularity-matched difference=-4.0pt; NOT_SUPPORTED.
- Q3 FRONT_SURVIVE_OR: N=7734, place ROI=76.7%, odds-matched difference=-1.8pt, popularity-matched difference=-0.1pt; NOT_SUPPORTED.
  FRONT_SURVIVE_OR's absolute ROI (76.7%) is 2.9pt above FRONT_SURVIVE_GAP05 (73.8%), so the broader set did not reduce raw ROI; both remain below their matched-market baselines.
- Q4 REAR_HIGH_LAST3F90: N=1602, place ROI=77.9%, odds-matched difference=+2.1pt, popularity-matched difference=+3.9pt; MARKET_SUPPORTED.
- Q5 HV01: N=5998, place ROI=80.8%, odds-matched difference=+5.0pt, popularity-matched difference=+6.5pt; MARKET_SUPPORTED.
- Q5 HV02: N=3156, place ROI=76.5%, odds-matched difference=+3.3pt, popularity-matched difference=+4.4pt; MARKET_SUPPORTED.
- Q6 HV01_TC1: N=78, place ROI=121.4%, odds-matched difference=+44.3pt, popularity-matched difference=+45.4pt; MARKET_SUPPORTED.

- Q7: 10倍以上・30倍以上でN≥30かつ同オッズ帯baselineを上回ったbucket:
  - TIME_CLASS_PLUS1, odds 30-99.9: N=33, ROI=99.7%, same-odds-bucket baseline=72.3%, difference=+27.4pt.
  - FRONT_SURVIVE_OR, odds 10-29.9: N=2201, ROI=80.4%, same-odds-bucket baseline=79.3%, difference=+1.1pt.
  - REAR_HIGH_LAST3F90, odds >=100: N=154, ROI=128.2%, same-odds-bucket baseline=50.8%, difference=+77.5pt.
  - HV01, odds 10-29.9: N=1933, ROI=90.2%, same-odds-bucket baseline=79.3%, difference=+10.9pt.
  - HV02, odds 10-29.9: N=1018, ROI=85.8%, same-odds-bucket baseline=79.3%, difference=+6.6pt.
  HV01_TC1 had positive point estimates at 10–29.9 and 30–99.9 odds, but N=21 and N=11 respectively, so they are too small for the N≥30 screen. The ≥100 bucket had N=6.
- Q8: High-payout dependence is quantified by top-one/top-three payout share and full versus top-one/top-three-excluded ROI. No payout is excluded from primary ROI. HV01_TC1 remains above 100% after excluding its largest payout (108.5%), but falls below after excluding its top three (86.3%); this shows some concentration across several payouts, not dependence on one payout.

The ability results and market settlement results are kept separate. `MARKET_SUPPORTED` means positive place-ROI differences versus both popularity- and odds-matched general-market baselines with valid market N≥30; it is a relative comparison, not a claim that absolute ROI exceeds 100%. No formal signal grade, threshold, or frozen rule changed.

## 11. Outputs

- OOS fact: `analysis/oos/rrdb_2024_2025_signal_oos_fact.parquet`
- Signal summary: `analysis/oos/rrdb_2024_2025_signal_oos_summary.parquet/.csv`
- Half-year blocks: `analysis/oos/rrdb_2024_2025_signal_oos_blocks.csv`
- Market summary: `analysis/oos/rrdb_2024_2025_signal_oos_market.csv`
- Market buckets: `analysis/oos/rrdb_2024_2025_signal_oos_market_buckets.csv`
- Market half-year blocks: `analysis/oos/rrdb_2024_2025_signal_oos_market_half_year.csv`
- Market audit: `analysis/oos/rrdb_2024_2025_signal_oos_market_audit.json`
- Market-enriched fact: `analysis/oos/rrdb_2024_2025_signal_oos_fact_with_market.parquet`
- Market enrichment reproducer: `src/enrich_rrdb_signal_oos_market.py`
- High-payout examples/status: `analysis/oos/rrdb_2024_2025_signal_oos_high_payout.csv`
- Cluster bootstrap: `analysis/oos/rrdb_2024_2025_signal_oos_bootstrap.csv`
- Audit: `analysis/oos/rrdb_2024_2025_signal_oos_audit.json`
- Reproducer: `src/analyze_rrdb_signal_oos.py`

## 12. Constraints

Next-finish averages and medians include only classified target finishes (`target_finish>0`); win/top3/top5 rates include every mapped next start, with unclassified finishes not counted as placing. Historical RRDB ends at 2026-09-27; starts after snapshot are unobserved. No official S/A or frozen threshold was changed.
