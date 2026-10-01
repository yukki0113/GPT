# RaceReviewDB 2024–2025 Time / Pace Historical OOS 分析 v0.1

## 検証結論

条件を2026年9月から変更せず、RRDBの凍結済み2024–2025年sourceレースから同一horse_idの直後の平地出走へ連結して評価した。source featuresはsource race時点のRRDB保存値を使用。OOSの結果を見た閾値調整、S/A昇格、HVルール変更はしていない。

能力面は次走着順で評価した。過去年のSED原票が入力にないため、人気・オッズ・複勝払戻・市場ROI・高配当寄与は判定不能であり、0としては扱わずNULLのまま出力した。

## 1. Data audit

```json
{
  "status": "PASS",
  "source_period": "2024-01-01..2025-12-31",
  "rrdb_snapshot_max_date": "2026-09-27",
  "source_period_flat_entry_count": 92279,
  "source_starts_flat_with_result_count": 91597,
  "source_to_next_flat_start_mapped_count": 81767,
  "source_without_next_flat_start_in_snapshot_count": 9830,
  "duplicate_source_key_count": 0,
  "duplicate_source_target_mapping_count": 0,
  "target_date_le_source_date_count": 0,
  "horse_id_mismatch_count": 0,
  "source_time_missing_count": 682,
  "time_class_equivalent_missing_count": 0,
  "time_class_numeric_missing_count": 68570,
  "class_curve_non_monotonic_count": 68570,
  "time_class_quality_gate_eligible_count": 13197,
  "historical_standard_end_date_missing_count": 0,
  "historical_standard_asof_violation_count": 0,
  "standard_sample_count_distribution": {
    "n": 81767,
    "min": 1.0,
    "p10": 12.0,
    "median": 29.0,
    "p90": 117.0,
    "max": 407.0
  },
  "standard_scope_level_counts": {
    "2.0": 40873,
    "1.0": 26145,
    "3.0": 12098,
    "4.0": 1886,
    "5.0": 510,
    "6.0": 255
  },
  "standard_confidence_counts": {
    "LOW": 41095,
    "MEDIUM": 29842,
    "HIGH": 10696,
    "FALLBACK": 134
  },
  "pace_percentile_missing_count": 3894,
  "pace_asof_recompute_mismatch_count": 0,
  "pace_percentile_coverage": {
    "n": 77873,
    "min": 0.0,
    "p10": 10.201632261161786,
    "median": 50.37593984962406,
    "p90": 90.26745913818722,
    "max": 100.0
  },
  "pace_sample_count_distribution": {
    "n": 81767,
    "min": 0.0,
    "p10": 256.0,
    "median": 785.0,
    "p90": 1704.0,
    "max": 2102.0
  },
  "corner4_frontness_missing_count": 0,
  "last3f_percentile_missing_count": 1,
  "winner_gap_missing_count": 0,
  "closing_gain_missing_count": 74139,
  "source_abnormal_or_unplaced_excluded_count": 682,
  "target_finish_unclassified_count": 569,
  "target_abnormal_code_available": false,
  "target_sed_join_missing_count": 81767,
  "sed_historical_archives_available": false,
  "sed_join_status": "UNAVAILABLE_NO_HISTORICAL_SED_ARCHIVE",
  "market_outcomes_available": false,
  "market_rows_set_to_zero": false,
  "oos_start_date": "2024-01-06",
  "oos_end_date": "2025-12-28",
  "target_end_date": "2026-09-27",
  "source_target_identity_mismatch_count": 0,
  "source_target_key_unique_count": 81767,
  "mapped_target_key_unique_count": 81767,
  "frozen_rule_version": "next-watch-rules-discovery-v0.1",
  "hv_performance_q80_threshold": -0.09305555555555287,
  "thresholds_reoptimized": false,
  "formal_rules_changed": false,
  "signals": {
    "TIME_CLASS_PLUS1": {
      "evaluable_n": 13197,
      "positive_n": 386
    },
    "TIME_CLASS_PLUS2": {
      "evaluable_n": 13197,
      "positive_n": 104
    },
    "TC-A_WIN_PLUS1": {
      "evaluable_n": 13197,
      "positive_n": 173
    },
    "TC-B_FINISH_2_5_PLUS1": {
      "evaluable_n": 13197,
      "positive_n": 182
    },
    "TC-C_FINISH_6PLUS_PLUS1": {
      "evaluable_n": 13197,
      "positive_n": 31
    },
    "FRONT_EXPOSURE": {
      "evaluable_n": 77873,
      "positive_n": 11448
    },
    "FRONT_SURVIVE_GAP05": {
      "evaluable_n": 80605,
      "positive_n": 4612
    },
    "FRONT_SURVIVE_GAP08": {
      "evaluable_n": 80071,
      "positive_n": 6096
    },
    "FRONT_SURVIVE_HALF": {
      "evaluable_n": 79572,
      "positive_n": 7692
    },
    "FRONT_SURVIVE_OR": {
      "evaluable_n": 79547,
      "positive_n": 7760
    },
    "FRONT_SURVIVE_STRICT": {
      "evaluable_n": 80630,
      "positive_n": 4544
    },
    "REAR_EXPOSURE": {
      "evaluable_n": 77873,
      "positive_n": 8098
    },
    "REAR_HIGH_LAST3F80": {
      "evaluable_n": 80653,
      "positive_n": 2608
    },
    "REAR_HIGH_LAST3F90": {
      "evaluable_n": 81092,
      "positive_n": 1610
    },
    "REAR_HIGH_LAST3F90_GAP05": {
      "evaluable_n": 81348,
      "positive_n": 748
    },
    "REAR_HIGH_LAST3F90_CLOSING_POSITIVE": {
      "evaluable_n": 79506,
      "positive_n": 0
    },
    "HV01": {
      "evaluable_n": 81767,
      "positive_n": 6014
    },
    "HV02": {
      "evaluable_n": 81767,
      "positive_n": 3165
    },
    "POSITION_RECOVERY": {
      "evaluable_n": 38567,
      "positive_n": 10216
    },
    "HV07_POSITION_RECOVERY": {
      "evaluable_n": 38567,
      "positive_n": 3060
    },
    "TC1_FRONT05": {
      "evaluable_n": 77271,
      "positive_n": 57
    },
    "TC1_FRONT08": {
      "evaluable_n": 75744,
      "positive_n": 66
    },
    "TC1_FRONT_OR": {
      "evaluable_n": 74345,
      "positive_n": 70
    },
    "TC1_REAR90": {
      "evaluable_n": 80081,
      "positive_n": 2
    },
    "TC1_REAR90_GAP05": {
      "evaluable_n": 80902,
      "positive_n": 1
    },
    "HV01_TC1": {
      "evaluable_n": 76341,
      "positive_n": 79
    },
    "HV02_TC1": {
      "evaluable_n": 78833,
      "positive_n": 31
    },
    "HV01_FRONT05": {
      "evaluable_n": 81698,
      "positive_n": 398
    },
    "HV01_REAR90": {
      "evaluable_n": 81732,
      "positive_n": 91
    },
    "HV02_FRONT05": {
      "evaluable_n": 81747,
      "positive_n": 97
    },
    "HV02_REAR90": {
      "evaluable_n": 81749,
      "positive_n": 30
    }
  },
  "note": "Pace percentile is read from the immutable RRDB source race context. Its builder enforces history_date < target race_date; race standard sample_end_date is independently verified below.",
  "pace_asof_recomputed_race_count": 6335,
  "pace_source_feature_missing_race_count": 327,
  "pace_asof_policy_strictly_prior_verified": true
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

## 8. Popularity, odds, payouts and high payouts

Historical SED/PACI archives for 2024–2025 were not present in the supplied inputs. The market CSV therefore contains explicit `UNAVAILABLE_NO_2024_2025_SED_ARCHIVE` rows for all predefined popularity/odds buckets; payout values, place hit, ROI, high-payout counts, and payout concentration are NULL. The high-payout examples CSV is an empty schema-bearing file, not a zero-hit finding.

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

Classification is descriptive: SUPPORTED requires N>=30, positive full-period matched top3 lift and positive direction in at least 3 half-year blocks with N>=10; MIXED is positive overall but weaker block consistency; NOT_SUPPORTED is no positive overall lift; INSUFFICIENT_SAMPLE has N<30. It does not imply statistical significance or formal adoption. Market value remains unclassified because SED is missing.

## 10. Required questions

- Q1–Q2: TIME_CLASS_PLUS1 OOS ability is in section 2; under/overvaluation and ROI cannot be judged without SED.
- Q3–Q4: FRONT_SURVIVE_GAP05 and FRONT_SURVIVE_OR are in section 3 with the half-field sensitivity.
- Q5: REAR_HIGH_LAST3F90 is in section 4.
- Q6–Q7: TC1_FRONT and TC1_REAR rows in section 6 compare against TIME_CLASS_PLUS1.
- Q8–Q9: HV01/HV02 overlap and `HV*_TC1` composites appear in section 6; their N and matched lifts show whether they add to parents.
- Q10: POSITION_RECOVERY is tabulated alongside Pace Opposition in sections 3–5; compare matched lifts and coverage.

## 11. Outputs

- OOS fact: `analysis/oos/rrdb_2024_2025_signal_oos_fact.parquet`
- Signal summary: `analysis/oos/rrdb_2024_2025_signal_oos_summary.parquet/.csv`
- Half-year blocks: `analysis/oos/rrdb_2024_2025_signal_oos_blocks.csv`
- Market availability: `analysis/oos/rrdb_2024_2025_signal_oos_market.csv`
- High-payout examples/status: `analysis/oos/rrdb_2024_2025_signal_oos_high_payout.csv`
- Cluster bootstrap: `analysis/oos/rrdb_2024_2025_signal_oos_bootstrap.csv`
- Audit: `analysis/oos/rrdb_2024_2025_signal_oos_audit.json`
- Reproducer: `src/analyze_rrdb_signal_oos.py`

## 12. Constraints

Next-finish averages and medians include only classified target finishes (`target_finish>0`); win/top3/top5 rates include every mapped next start, with unclassified finishes not counted as placing. Historical RRDB ends at 2026-09-27; starts after snapshot are unobserved. No official S/A or frozen threshold was changed.
