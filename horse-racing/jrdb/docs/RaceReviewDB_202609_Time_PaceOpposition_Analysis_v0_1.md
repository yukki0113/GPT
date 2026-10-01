# RaceReviewDB 2026年9月 前走タイム・展開逆行分析 v0.1

Status: ANALYSIS_COMPLETE / DATA_AUDIT_PASS / RESEARCH_ONLY
Date: 2026-10-01

9月全3,137エントリーを保持して分析を完了した。前走タイム上位20%は次走好走を拾うが、
上位10%に絞ることは市場価値の改善につながらなかった。前走6着以下×タイム上位20%は
複勝回収率114.47%で、着順だけでは見えない候補として残る。
前傾前受けをタイム評価へ足した追加価値は今回確認できない。
後傾後方は単独では弱く、上がりpercentile 90以上との組み合わせで初めて有望な結果になった。
これらは9月の探索的記述結果であり、S/Aの条件・凍結閾値は変更しない。

## 1. 母集団・精算・リーク境界

- 1行=target entrant。horse_idはJRDB血統登録番号8桁を文字列として保持し、馬名結合はしない。
- PACI/KYI + BACで全頭とtarget条件を形成する。前走はtarget_dateより厳密に前の直近完成済みJRA平地走。
- 全エントリーと取消・除外・障害を台帳から削除しない。主分析は平地・実出走・前走履歴あり。
- 取消/除外は返還扱いでstakeから除く。中止は実出走の不的中として残す。
- 前走特徴Parquetを確定・hash保存してからSED結果を結合する。
- 複勝hitは払戻>0で判定。小頭数3着の不的中を区別する。
- SEDの払戻欄空白は不的中の0円に正規化し、raw_blank列に原状態を残す。払戻対象着順の空白は監査で拒否する。
- DAY_TRACK_OPPOSITIONは今回未実装でNULL。既存タイム補正はRRDBのleave-one-race-out仕様を継承する。

| audit | count |
| --- | --- |
| target_runner_count | 3137 |
| target_started_count | 3128 |
| target_flat_started_count | 3039 |
| usable_previous_rrdb_start_count | 2686 |
| no_previous_history_count | 451 |
| usable_flat_started_count | 2590 |
| duplicate_count | 0 |
| sed_join_missing_count | 0 |
| settlement_identity_mismatch_count | 0 |
| pace_feature_missing_count | 745 |
| performance_feature_missing_count | 0 |
| corner4_feature_missing_count | 1 |
| closing_gain_missing_count | 2475 |
| previous_date_violation_count | 0 |
| historical_standard_date_violation_count | 0 |
| rrdb_object_hash_verified_count | 51 |

| target_date | paci_entrants | races | started | flat_started | previous_history | no_previous_history |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-09-05 | 455 | 36 | 452 | 444 | 389 | 66 |
| 2026-09-06 | 491 | 36 | 491 | 484 | 450 | 41 |
| 2026-09-12 | 316 | 24 | 315 | 307 | 272 | 44 |
| 2026-09-13 | 314 | 24 | 313 | 303 | 296 | 18 |
| 2026-09-19 | 287 | 24 | 286 | 274 | 225 | 62 |
| 2026-09-20 | 334 | 24 | 334 | 322 | 273 | 61 |
| 2026-09-21 | 159 | 12 | 158 | 158 | 134 | 25 |
| 2026-09-22 | 161 | 12 | 161 | 147 | 138 | 23 |
| 2026-09-26 | 313 | 24 | 312 | 306 | 253 | 60 |
| 2026-09-27 | 307 | 24 | 306 | 294 | 256 | 51 |

RRDB generation: `jrdb_race_review_v0_1_incremental_g36514429467`。収録は`2026-09-27`まで。参照moduleの取得時mainは`ffa600b46e75daa2ad7d1a8bc2c4088c2366a267`。

履歴あり2,686頭のうち主分析に入るのは2,590頭。タイム評価は全2,590頭にある。
ペース×4角位置が揃う共通母集団は1,848頭（71.35%）。欠損742頭を不利なし=0に補完しない。
RRDB全頭履歴に存在する前走レース1,082件を監査し、percentile有効865件・欠損217件。
percentile有効値は、source dateより前の同surface/distance・venue優先履歴から既存percentile_rankで再計算し、
sample_count / scope_levelを含め不一致0件。標準タイムsample_end_dateもsource dateより前である。
closing_gainは大半欠損であり、「後傾後方×上がり90×closing_gain>0」の観測対象は0頭。
これは条件の成績不良ではなく検証不能を意味する。

月全体の分位は特徴量だけから計算した記述用境界で、当時日次で固定されていた運用ルールではない。
target結果・人気・オッズで境界を選ばない。上位20%=signal>=q80、上位10%=signal>=q90で同値は分割しない。
そのため上位20%は519頭となる。Historical OOSへ進む場合は、この数値境界を固定して適用する。

| field | 0 | 0.5 | 0.7 | 0.8 | 0.9 | 1 |
| --- | --- | --- | --- | --- | --- | --- |
| performance_signal | -8.76 | -0.65 | -0.28 | -0.06 | 0.21 | 2.08 |
| front_pace_opposition_raw | 0.00 | 0.20 | 0.36 | 0.46 | 0.64 | 1.00 |
| rear_pace_opposition_raw | 0.00 | 0.15 | 0.30 | 0.40 | 0.57 | 1.00 |

## 2. タイム評価単独

performance_signal=-horse_adjusted_delta_per_1000m。高いほど良い。
能力予測としてはbottom50→top10で複勝的中率が14.36%→37.45%へ上昇する。
一方でtop10の回収率は75.98%に下がり、人気平均4.80・単勝オッズ中央値7.9倍。
能力の強さと市場の過小評価は一致しない。

| stratum | n | place_hits | place_hit_rate_pct | stake_yen | place_payout_yen | place_roi_pct | popularity_mean | popularity_median | win_odds_mean | win_odds_median |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bottom50 | 1295 | 186 | 14.36 | 129500 | 86320 | 66.66 | 8.91 | 9.00 | 81.50 | 39.80 |
| 50-70 | 514 | 125 | 24.32 | 51400 | 36800 | 71.60 | 6.72 | 6.00 | 34.25 | 15.40 |
| 70-80 | 262 | 77 | 29.39 | 26200 | 30840 | 117.71 | 6.00 | 5.00 | 30.64 | 12.30 |
| 80-90 | 260 | 91 | 35.00 | 26000 | 26960 | 103.69 | 5.74 | 5.00 | 24.04 | 10.80 |
| top10 | 259 | 97 | 37.45 | 25900 | 19680 | 75.98 | 4.80 | 4.00 | 18.21 | 7.90 |

### 前走着順×タイム分位

| signal | stratum | n | place_hits | place_hit_rate_pct | stake_yen | place_payout_yen | place_roi_pct | popularity_mean | popularity_median | win_odds_mean | win_odds_median |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bottom50 | 1-3 | 119 | 49 | 41.18 | 11900 | 11860 | 99.66 | 4.78 | 4.00 | 15.20 | 9.10 |
| bottom50 | 4-5 | 178 | 30 | 16.85 | 17800 | 8410 | 47.25 | 6.52 | 6.00 | 29.83 | 15.80 |
| bottom50 | 6-9 | 444 | 61 | 13.74 | 44400 | 27790 | 62.59 | 8.83 | 9.00 | 71.72 | 41.20 |
| bottom50 | 10+ | 554 | 46 | 8.30 | 55400 | 38260 | 69.06 | 10.62 | 11.00 | 120.17 | 80.10 |
| 50-70 | 1-3 | 170 | 61 | 35.88 | 17000 | 14450 | 85.00 | 4.72 | 4.00 | 14.17 | 8.90 |
| 50-70 | 4-5 | 118 | 28 | 23.73 | 11800 | 8800 | 74.58 | 6.10 | 6.00 | 21.99 | 14.80 |
| 50-70 | 6-9 | 155 | 26 | 16.77 | 15500 | 8910 | 57.48 | 7.92 | 8.00 | 47.97 | 24.60 |
| 50-70 | 10+ | 71 | 10 | 14.08 | 7100 | 4640 | 65.35 | 9.92 | 11.00 | 72.73 | 53.60 |
| 70-80 | 1-3 | 109 | 40 | 36.70 | 10900 | 8900 | 81.65 | 4.48 | 3.00 | 12.92 | 6.70 |
| 70-80 | 4-5 | 61 | 15 | 24.59 | 6100 | 3990 | 65.41 | 5.15 | 4.00 | 19.46 | 9.90 |
| 70-80 | 6-9 | 70 | 19 | 27.14 | 7000 | 6160 | 88.00 | 7.50 | 7.50 | 37.17 | 20.90 |
| 70-80 | 10+ | 22 | 3 | 13.64 | 2200 | 11790 | 535.91 | 11.09 | 10.50 | 128.71 | 45.15 |
| 80-90 | 1-3 | 150 | 59 | 39.33 | 15000 | 12660 | 84.40 | 4.33 | 3.50 | 13.21 | 7.30 |
| 80-90 | 4-5 | 54 | 18 | 33.33 | 5400 | 5540 | 102.59 | 6.65 | 5.50 | 26.66 | 13.20 |
| 80-90 | 6-9 | 44 | 8 | 18.18 | 4400 | 3370 | 76.59 | 8.84 | 9.00 | 55.33 | 32.45 |
| 80-90 | 10+ | 12 | 6 | 50.00 | 1200 | 5390 | 449.17 | 7.92 | 8.50 | 32.98 | 20.75 |
| top10 | 1-3 | 185 | 82 | 44.32 | 18500 | 15550 | 84.05 | 3.57 | 3.00 | 9.40 | 5.50 |
| top10 | 4-5 | 36 | 9 | 25.00 | 3600 | 2130 | 59.17 | 5.81 | 5.00 | 16.16 | 12.60 |
| top10 | 6-9 | 30 | 4 | 13.33 | 3000 | 960 | 32.00 | 9.27 | 8.50 | 57.17 | 27.85 |
| top10 | 10+ | 8 | 2 | 25.00 | 800 | 1040 | 130.00 | 12.00 | 12.50 | 85.26 | 46.60 |

### 上位20/10と前走敗退馬

| signal | n | place_hits | place_hit_rate_pct | stake_yen | place_payout_yen | place_roi_pct | popularity_mean | popularity_median | win_odds_mean | win_odds_median |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL_USABLE | 2590 | 576 | 22.24 | 259000 | 200600 | 77.45 | 7.45 | 7.00 | 54.88 | 20.50 |
| PERF_TOP20 | 519 | 188 | 36.22 | 51900 | 46640 | 89.87 | 5.27 | 4.00 | 21.13 | 8.90 |
| PERF_TOP10 | 259 | 97 | 37.45 | 25900 | 19680 | 75.98 | 4.80 | 4.00 | 18.21 | 7.90 |
| FINISH_GE4 | 1857 | 285 | 15.35 | 185700 | 137180 | 73.87 | 8.68 | 9.00 | 71.51 | 33.70 |
| FINISH_GE4_PERF_TOP20 | 184 | 47 | 25.54 | 18400 | 18430 | 100.16 | 7.75 | 7.00 | 39.39 | 18.70 |
| FINISH_GE4_PERF_TOP10 | 74 | 15 | 20.27 | 7400 | 4130 | 55.81 | 7.88 | 7.50 | 40.26 | 18.55 |
| FINISH_GE6 | 1410 | 185 | 13.12 | 141000 | 108310 | 76.82 | 9.48 | 10.00 | 86.30 | 47.85 |
| FINISH_GE6_PERF_TOP20 | 94 | 20 | 21.28 | 9400 | 10760 | 114.47 | 9.13 | 9.00 | 55.61 | 29.85 |
| FINISH_GE6_PERF_TOP10 | 38 | 6 | 15.79 | 3800 | 2000 | 52.63 | 9.84 | 9.00 | 63.09 | 29.20 |

前走6着以下×top20は94頭・20的中・払戻10,760円/購入9,400円。
同じ前走6着以下1,410頭のbaseline（的中率13.12%、回収率76.82%）を上回る。
ただしROI差のtarget-race cluster bootstrap 95%区間は-23.06～+103.90ppと広く、利益を確証しない。
top10は38頭・6的中・回収率52.63%で、9月ではtop20のほうが実用候補として残る。
70-80帯・80-90帯の高ROIはそのまま記述するが、結果を見てその帯だけを正式ルールに選ばない。

既存frozen numeric thresholdも参考として比較する。9月分位と同義ではない。
既存q80=-0.0930556を使う前走6着以下は116頭、回収率108.88%。
既存ルール・S/Aは不変であり、今回の結果で置換しない。

| signal | n | place_hit_rate_pct | place_roi_pct |
| --- | --- | --- | --- |
| FROZEN_PERF_Q80 | 567 | 35.10 | 88.38 |
| FROZEN_PERF_Q90 | 283 | 36.04 | 76.25 |
| FROZEN_FINISH_GE6_Q80 | 116 | 20.69 | 108.88 |

## 3. 展開逆行単独

前傾前受け: pace percentile>=70 × corner4_frontness>=0.6。
後傾後方: pace percentile<=30 × corner4_frontness<=0.4。
90/10および0.8/0.2の狭い事前指定subtypeも出す。
rawはfront=(pct/100)×frontness、rear=(1-pct/100)×(1-frontness)。内容評価と掛けて単一scoreにしない。

| signal | n | place_hits | place_hit_rate_pct | place_roi_pct | popularity_mean | win_odds_median |
| --- | --- | --- | --- | --- | --- | --- |
| PACE_COMPLETE | 1848 | 420 | 22.73 | 81.40 | 7.41 | 19.90 |
| FRONT_HIGH | 243 | 62 | 25.51 | 87.16 | 6.47 | 13.30 |
| FRONT_VERY_HIGH | 86 | 23 | 26.74 | 68.60 | 6.29 | 13.60 |
| FRONT_EXTREME | 52 | 15 | 28.85 | 73.27 | 5.63 | 11.30 |
| REAR_HIGH | 204 | 38 | 18.63 | 75.39 | 8.62 | 38.75 |
| REAR_VERY_HIGH | 86 | 18 | 20.93 | 108.60 | 8.33 | 47.65 |
| REAR_EXTREME | 47 | 7 | 14.89 | 72.77 | 9.21 | 52.00 |
| POSITION_RECOVERY | 356 | 91 | 25.56 | 62.28 | 6.24 | 13.80 |
| POSITION_RECOVERY_LAST3F80 | 241 | 72 | 29.88 | 68.05 | 5.46 | 11.10 |
| CURRENT_HV07 | 101 | 25 | 24.75 | 66.34 | 6.91 | 17.30 |

### Pace shape × 4角frontness

| signal | stratum | n | place_hit_rate_pct | place_roi_pct |
| --- | --- | --- | --- | --- |
| BACK_LOADED | 0-.2 | 53 | 11.32 | 44.72 |
| BACK_LOADED | >.2-.4 | 65 | 21.54 | 56.46 |
| BACK_LOADED | >.4-.6 | 84 | 16.67 | 79.76 |
| BACK_LOADED | >.6-.8 | 83 | 26.51 | 81.81 |
| BACK_LOADED | >.8-1 | 126 | 33.33 | 86.35 |
| BALANCED | 0-.2 | 124 | 13.71 | 81.45 |
| BALANCED | >.2-.4 | 124 | 16.94 | 74.27 |
| BALANCED | >.4-.6 | 131 | 24.43 | 154.12 |
| BALANCED | >.6-.8 | 130 | 30.00 | 77.15 |
| BALANCED | >.8-1 | 194 | 29.90 | 69.74 |
| FRONT_LOADED | 0-.2 | 43 | 4.65 | 71.16 |
| FRONT_LOADED | >.2-.4 | 74 | 17.57 | 75.54 |
| FRONT_LOADED | >.4-.6 | 65 | 18.46 | 63.23 |
| FRONT_LOADED | >.6-.8 | 53 | 22.64 | 157.55 |
| FRONT_LOADED | >.8-1 | 98 | 24.49 | 65.61 |
| VERY_BACK_LOADED | 0-.2 | 47 | 14.89 | 72.77 |
| VERY_BACK_LOADED | >.2-.4 | 39 | 28.21 | 151.79 |
| VERY_BACK_LOADED | >.4-.6 | 49 | 16.33 | 38.78 |
| VERY_BACK_LOADED | >.6-.8 | 45 | 17.78 | 40.89 |
| VERY_BACK_LOADED | >.8-1 | 59 | 37.29 | 86.61 |
| VERY_FRONT_LOADED | 0-.2 | 30 | 13.33 | 37.00 |
| VERY_FRONT_LOADED | >.2-.4 | 21 | 14.29 | 72.86 |
| VERY_FRONT_LOADED | >.4-.6 | 29 | 27.59 | 118.97 |
| VERY_FRONT_LOADED | >.6-.8 | 36 | 27.78 | 61.67 |
| VERY_FRONT_LOADED | >.8-1 | 46 | 23.91 | 63.26 |

### Raw exposure分位

| signal | stratum | n | place_hit_rate_pct | place_roi_pct |
| --- | --- | --- | --- | --- |
| front_pace_opposition_raw | bottom50 | 922 | 19.63 | 71.79 |
| front_pace_opposition_raw | 50-70 | 371 | 25.07 | 105.50 |
| front_pace_opposition_raw | 70-80 | 185 | 22.70 | 71.73 |
| front_pace_opposition_raw | 80-90 | 185 | 32.97 | 84.76 |
| front_pace_opposition_raw | top10 | 185 | 23.24 | 87.24 |
| rear_pace_opposition_raw | bottom50 | 924 | 26.08 | 76.47 |
| rear_pace_opposition_raw | 50-70 | 369 | 23.31 | 102.01 |
| rear_pace_opposition_raw | 70-80 | 184 | 16.30 | 83.32 |
| rear_pace_opposition_raw | 80-90 | 186 | 17.74 | 72.63 |
| rear_pace_opposition_raw | top10 | 185 | 16.22 | 71.78 |

前傾前受け単独は共通baseline比で的中率+2.79pp、ROI+5.76pp。
bootstrap区間はいずれも0を跨ぎ、強い独立効果は確認できない。
後傾後方単独はbaselineを下回る。very-rearのROI108.60%はハクタカ3,110円が払戻の33.30%を占める。
POSITION_RECOVERY単独はROI62.28%、上がり80との組み合わせでも68.05%。
今回の9月では市場価値の改善が乏しいが、PACE_OPPOSITIONの全系統が一律に優れるとは判断しない。

## 4. タイム×展開逆行・上がり×展開逆行

追加価値は欠損のない共通母集団の親signalと比較する。全519頭のtop20と73頭の組み合わせを
直接比較すると母集団差が混じるため、ペース有効のtop20=362頭を親baselineとする。

| signal | n | hit_pct | roi_pct | parent | parent_n | parent_hit_pct | parent_roi_pct | hit_lift_pp | roi_lift_pp | roi_lift_ci95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PERF_TOP20 | 519 | 36.22 | 89.87 | TIME_COMPLETE | 2590 | 22.24 | 77.45 | 13.98 | 12.41 | [-5.59011204397123, 30.784682962594893] |
| PERF_TOP10 | 259 | 37.45 | 75.98 | TIME_COMPLETE | 2590 | 22.24 | 77.45 | 15.21 | -1.47 | [-21.034584255688447, 16.83267529682443] |
| FINISH_GE6_PERF_TOP20 | 94 | 21.28 | 114.47 | FINISH_GE6 | 1410 | 13.12 | 76.82 | 8.16 | 37.65 | [-23.063543555891936, 103.90082234769316] |
| FINISH_GE6_PERF_TOP10 | 38 | 15.79 | 52.63 | FINISH_GE6 | 1410 | 13.12 | 76.82 | 2.67 | -24.18 | [-67.04665706610137, 24.581344625891454] |
| FRONT_HIGH | 243 | 25.51 | 87.16 | PACE_COMPLETE | 1848 | 22.73 | 81.40 | 2.79 | 5.76 | [-19.62545570018566, 35.812182247655656] |
| REAR_HIGH | 204 | 18.63 | 75.39 | PACE_COMPLETE | 1848 | 22.73 | 81.40 | -4.10 | -6.00 | [-38.17229696484306, 36.821141197098335] |
| POSITION_RECOVERY | 356 | 25.56 | 62.28 | ALL_USABLE | 2590 | 22.24 | 77.45 | 3.32 | -15.18 | [-35.162270088885755, 3.0216432681978604] |
| POSITION_RECOVERY_LAST3F80 | 241 | 29.88 | 68.05 | LAST3F80 | 755 | 31.92 | 76.00 | -2.05 | -7.95 | [-21.8894885780699, 5.733772540034034] |
| FRONT_HIGH_PERF_TOP20 | 73 | 36.99 | 95.89 | PERF_TOP20 | 362 | 36.19 | 96.91 | 0.80 | -1.02 | [-36.257818786931225, 37.0889494399515] |
| FRONT_HIGH_PERF_TOP10 | 39 | 38.46 | 90.00 | PERF_TOP10 | 185 | 38.38 | 81.84 | 0.08 | 8.16 | [-27.23345225668437, 52.06265212315935] |
| REAR_HIGH_PERF_TOP20 | 13 | 15.38 | 20.00 | PERF_TOP20 | 362 | 36.19 | 96.91 | -20.80 | -76.91 | [-108.84658437075008, -42.889409008712825] |
| REAR_HIGH_PERF_TOP10 | 7 | 14.29 | 18.57 | PERF_TOP10 | 185 | 38.38 | 81.84 | -24.09 | -63.27 | [-94.19168946648426, -17.924723145071987] |
| REAR_HIGH_LAST3F80 | 67 | 34.33 | 99.10 | LAST3F80 | 524 | 32.63 | 79.60 | 1.69 | 19.51 | [-18.801866282704633, 70.81151897039267] |
| REAR_HIGH_LAST3F90 | 43 | 46.51 | 134.88 | LAST3F90 | 324 | 34.57 | 77.01 | 11.94 | 57.88 | [1.2840359227291258, 125.73525438744348] |
| REAR_HIGH_LAST3F90_CLOSING_GAIN | 0 | NA | NA | REAR_HIGH_LAST3F90 | 0 | NA | NA | NA | NA | NA |

前傾前受け×top20は73頭、的中率36.99%、ROI95.89%。親のtop20共通362頭は36.19%、96.91%。
タイム評価への明確な追加価値はない。top10との組み合わせでも不確実性区間は広い。
後傾後方×タイムはtop20=13頭・ROI20.00%、top10=7頭・18.57%。極小標本で、好材料とはいえない。
後傾後方×上がり90以上は43頭・20的中・ROI134.88%。親の上がり90共通324頭は34.57%、77.01%。
的中率差+11.94pp、ROI差+57.88pp。ROI差bootstrap区間は+1.28～+125.74ppだが、
多数の事前指定signalを同時比較した探索結果であり、有意性や独立性の確定として扱わない。
上がり80では67頭・ROI99.10%で、90のほうが集中するが、閾値を探索して選んだものではない。

### Source / market matched baseline

| signal | n | hit_pct | roi_pct | source_expected_hit | source_expected_roi | source_odds_expected_hit | source_odds_expected_roi | min_cell_n |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PERF_TOP20 | 519 | 36.22 | 89.87 | 32.10 | 79.57 | 35.07 | 85.50 | 1.00 |
| PERF_TOP10 | 259 | 37.45 | 75.98 | 34.02 | 80.95 | 38.54 | 87.67 | 1.00 |
| FINISH_GE6_PERF_TOP20 | 94 | 21.28 | 114.47 | 15.21 | 71.44 | 17.23 | 81.18 | 1.00 |
| FINISH_GE6_PERF_TOP10 | 38 | 15.79 | 52.63 | 13.78 | 59.85 | 12.68 | 68.07 | 1.00 |
| FRONT_HIGH | 243 | 25.51 | 87.16 | 23.74 | 82.07 | 26.30 | 76.30 | 1.00 |
| REAR_HIGH | 204 | 18.63 | 75.39 | 19.25 | 80.78 | 16.63 | 81.90 | 1.00 |
| POSITION_RECOVERY | 356 | 25.56 | 62.28 | 27.29 | 75.14 | 25.83 | 71.05 | 1.00 |
| POSITION_RECOVERY_LAST3F80 | 241 | 29.88 | 68.05 | 32.05 | 77.99 | 30.90 | 74.96 | 1.00 |
| FRONT_HIGH_PERF_TOP20 | 73 | 36.99 | 95.89 | 37.42 | 98.11 | 34.33 | 91.34 | 1.00 |
| FRONT_HIGH_PERF_TOP10 | 39 | 38.46 | 90.00 | 36.91 | 81.00 | 35.81 | 82.11 | 1.00 |
| REAR_HIGH_PERF_TOP20 | 13 | 15.38 | 20.00 | 28.01 | 87.10 | 16.48 | 65.92 | 1.00 |
| REAR_HIGH_PERF_TOP10 | 7 | 14.29 | 18.57 | 25.24 | 63.19 | 23.81 | 33.57 | 1.00 |
| REAR_HIGH_LAST3F80 | 67 | 34.33 | 99.10 | 27.58 | 64.78 | 26.31 | 70.11 | 1.00 |
| REAR_HIGH_LAST3F90 | 43 | 46.51 | 134.88 | 35.15 | 87.23 | 38.48 | 120.04 | 1.00 |
| REAR_HIGH_LAST3F90_CLOSING_GAIN | 0 | NA | NA | NA | NA | NA | NA | NA |

前走着順帯×前走芝/ダート×前走距離帯×前走クラスで親母集団を標準化し、さらにtarget odds帯を加えた比較も行った。
親は選択群を含むため、この比較は重み付けされた記述baselineであり、因果効果推定ではない。
最小セルN=1があり、細かいmatched結果は補助材料。
後傾後方×上がり90のsource-matched期待ROIは87.23%、oddsも揃えると120.04%。
市場構成を揃えた追加差は粗比較より縮小するため、独立した市場価値はOOSで再検証する。
parent-complement、hit/ROI bootstrapの全値はmatched_comparisons.jsonに保存した。

## 5. 人気・オッズ別市場価値

以下は主要signalの全odds帯。全signal/combinationについてodds帯・人気帯・開催日・前走着順帯・
芝/ダート・距離帯・class別集計をCSV/Parquetに保存した。欠損/小Nのセルを隠さない。

| signal | stratum | n | place_hits | place_hit_rate_pct | place_payout_yen | place_roi_pct | odds_roi_lift_pp |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ALL_USABLE | <5 | 360 | 215 | 59.72 | 30850 | 85.69 | 0.00 |
| ALL_USABLE | 5-9.9 | 436 | 149 | 34.17 | 34130 | 78.28 | 0.00 |
| ALL_USABLE | 10-29.9 | 736 | 159 | 21.60 | 66280 | 90.05 | 0.00 |
| ALL_USABLE | 30-99.9 | 621 | 43 | 6.92 | 37270 | 60.02 | 0.00 |
| ALL_USABLE | >=100 | 437 | 10 | 2.29 | 32070 | 73.39 | 0.00 |
| PERF_TOP20 | <5 | 153 | 98 | 64.05 | 14030 | 91.70 | 6.00 |
| PERF_TOP20 | 5-9.9 | 123 | 50 | 40.65 | 11730 | 95.37 | 17.09 |
| PERF_TOP20 | 10-29.9 | 154 | 33 | 21.43 | 13630 | 88.51 | -1.55 |
| PERF_TOP20 | 30-99.9 | 69 | 6 | 8.70 | 6190 | 89.71 | 29.69 |
| PERF_TOP20 | >=100 | 20 | 1 | 5.00 | 1060 | 53.00 | -20.39 |
| PERF_TOP10 | <5 | 97 | 62 | 63.92 | 8980 | 92.58 | 6.88 |
| PERF_TOP10 | 5-9.9 | 55 | 19 | 34.55 | 4400 | 80.00 | 1.72 |
| PERF_TOP10 | 10-29.9 | 73 | 15 | 20.55 | 5240 | 71.78 | -18.27 |
| PERF_TOP10 | 30-99.9 | 25 | 0 | 0.00 | 0 | 0.00 | -60.02 |
| PERF_TOP10 | >=100 | 9 | 1 | 11.11 | 1060 | 117.78 | 44.39 |
| FRONT_HIGH | <5 | 45 | 30 | 66.67 | 4550 | 101.11 | 15.42 |
| FRONT_HIGH | 5-9.9 | 50 | 13 | 26.00 | 2720 | 54.40 | -23.88 |
| FRONT_HIGH | 10-29.9 | 81 | 16 | 19.75 | 7490 | 92.47 | 2.41 |
| FRONT_HIGH | 30-99.9 | 45 | 2 | 4.44 | 1600 | 35.56 | -24.46 |
| FRONT_HIGH | >=100 | 22 | 1 | 4.55 | 4820 | 219.09 | 145.70 |
| REAR_HIGH | <5 | 18 | 12 | 66.67 | 1660 | 92.22 | 6.53 |
| REAR_HIGH | 5-9.9 | 23 | 10 | 43.48 | 2560 | 111.30 | 33.02 |
| REAR_HIGH | 10-29.9 | 49 | 10 | 20.41 | 3560 | 72.65 | -17.40 |
| REAR_HIGH | 30-99.9 | 54 | 4 | 7.41 | 3100 | 57.41 | -2.61 |
| REAR_HIGH | >=100 | 60 | 2 | 3.33 | 4500 | 75.00 | 1.61 |
| FINISH_GE6_PERF_TOP20 | <5 | 2 | 0 | 0.00 | 0 | 0.00 | -85.69 |
| FINISH_GE6_PERF_TOP20 | 5-9.9 | 12 | 7 | 58.33 | 2230 | 185.83 | 107.55 |
| FINISH_GE6_PERF_TOP20 | 10-29.9 | 33 | 10 | 30.30 | 4950 | 150.00 | 59.95 |
| FINISH_GE6_PERF_TOP20 | 30-99.9 | 32 | 3 | 9.38 | 3580 | 111.88 | 51.86 |
| FINISH_GE6_PERF_TOP20 | >=100 | 15 | 0 | 0.00 | 0 | 0.00 | -73.39 |
| FRONT_HIGH_PERF_TOP20 | <5 | 23 | 16 | 69.57 | 2540 | 110.43 | 24.74 |
| FRONT_HIGH_PERF_TOP20 | 5-9.9 | 15 | 4 | 26.67 | 890 | 59.33 | -18.95 |
| FRONT_HIGH_PERF_TOP20 | 10-29.9 | 28 | 7 | 25.00 | 3570 | 127.50 | 37.45 |
| FRONT_HIGH_PERF_TOP20 | 30-99.9 | 6 | 0 | 0.00 | 0 | 0.00 | -60.02 |
| FRONT_HIGH_PERF_TOP20 | >=100 | 1 | 0 | 0.00 | 0 | 0.00 | -73.39 |
| REAR_HIGH_LAST3F90 | <5 | 8 | 7 | 87.50 | 930 | 116.25 | 30.56 |
| REAR_HIGH_LAST3F90 | 5-9.9 | 11 | 5 | 45.45 | 890 | 80.91 | 2.63 |
| REAR_HIGH_LAST3F90 | 10-29.9 | 14 | 6 | 42.86 | 1950 | 139.29 | 49.23 |
| REAR_HIGH_LAST3F90 | 30-99.9 | 8 | 1 | 12.50 | 640 | 80.00 | 19.98 |
| REAR_HIGH_LAST3F90 | >=100 | 2 | 1 | 50.00 | 1390 | 695.00 | 621.61 |

### 人気帯

| signal | stratum | n | place_hits | place_hit_rate_pct | place_roi_pct |
| --- | --- | --- | --- | --- | --- |
| ALL_USABLE | 1-3 | 587 | 305 | 51.96 | 86.92 |
| ALL_USABLE | 4-6 | 587 | 147 | 25.04 | 73.30 |
| ALL_USABLE | 7-9 | 553 | 86 | 15.55 | 90.67 |
| ALL_USABLE | 10+ | 863 | 38 | 4.40 | 65.37 |
| PERF_TOP20 | 1-3 | 221 | 129 | 58.37 | 100.59 |
| PERF_TOP20 | 4-6 | 135 | 37 | 27.41 | 70.74 |
| PERF_TOP20 | 7-9 | 79 | 15 | 18.99 | 94.94 |
| PERF_TOP20 | 10+ | 84 | 7 | 8.33 | 87.62 |
| PERF_TOP10 | 1-3 | 124 | 70 | 56.45 | 87.02 |
| PERF_TOP10 | 4-6 | 64 | 20 | 31.25 | 78.59 |
| PERF_TOP10 | 7-9 | 36 | 6 | 16.67 | 77.78 |
| PERF_TOP10 | 10+ | 35 | 1 | 2.86 | 30.29 |
| FRONT_HIGH | 1-3 | 72 | 38 | 52.78 | 98.06 |
| FRONT_HIGH | 4-6 | 66 | 16 | 24.24 | 70.00 |
| FRONT_HIGH | 7-9 | 46 | 6 | 13.04 | 77.39 |
| FRONT_HIGH | 10+ | 59 | 2 | 3.39 | 100.68 |
| REAR_HIGH | 1-3 | 29 | 17 | 58.62 | 104.48 |
| REAR_HIGH | 4-6 | 40 | 13 | 32.50 | 94.25 |
| REAR_HIGH | 7-9 | 42 | 4 | 9.52 | 110.00 |
| REAR_HIGH | 10+ | 93 | 4 | 4.30 | 42.58 |
| FINISH_GE6_PERF_TOP20 | 1-3 | 11 | 7 | 63.64 | 282.73 |
| FINISH_GE6_PERF_TOP20 | 4-6 | 16 | 4 | 25.00 | 66.88 |
| FINISH_GE6_PERF_TOP20 | 7-9 | 27 | 7 | 25.93 | 128.15 |
| FINISH_GE6_PERF_TOP20 | 10+ | 40 | 2 | 5.00 | 78.00 |
| FRONT_HIGH_PERF_TOP20 | 1-3 | 34 | 20 | 58.82 | 129.71 |
| FRONT_HIGH_PERF_TOP20 | 4-6 | 17 | 5 | 29.41 | 81.76 |
| FRONT_HIGH_PERF_TOP20 | 7-9 | 13 | 2 | 15.38 | 92.31 |
| FRONT_HIGH_PERF_TOP20 | 10+ | 9 | 0 | 0.00 | 0.00 |
| REAR_HIGH_LAST3F90 | 1-3 | 15 | 11 | 73.33 | 108.67 |
| REAR_HIGH_LAST3F90 | 4-6 | 14 | 6 | 42.86 | 115.71 |
| REAR_HIGH_LAST3F90 | 7-9 | 8 | 1 | 12.50 | 65.00 |
| REAR_HIGH_LAST3F90 | 10+ | 6 | 2 | 33.33 | 338.33 |

前走6着以下×top20は5-9.9倍・10-29.9倍・30-99.9倍で各185.83/150.00/111.88%。
同odds帯の全usable baselineより高いが、各12/33/32頭と少ない。100倍以上は15頭全不的中である。
後傾後方×上がり90の100倍以上は2頭中1頭的中でROI695%。同帯liftは大きいが2頭だけなので一般化しない。

## 6. 高配当寄与・日別再現性

高配当を除いて主要評価を作り替えない。金額、日数、同odds baselineとの差を併記する。
高配当例は複勝1,000円以上。全該当signalとの対応をhigh_payout_examples.csvへ保存した。

| signal | n | place_payout_yen | max_place_payout_yen | largest_payout_share_pct | high_payout_hits | hit_days |
| --- | --- | --- | --- | --- | --- | --- |
| REAR_VERY_HIGH | 86 | 9340 | 3110 | 33.30 | 2 | 10 |
| FINISH_GE6_PERF_TOP20 | 94 | 10760 | 1810 | 16.82 | 3 | 7 |
| REAR_HIGH_LAST3F90 | 43 | 5800 | 1390 | 23.97 | 1 | 10 |

| signal | target_date | target_race_key | target_horse_no | horse_id | horse_name | previous_finish | target_finish | target_popularity | target_win_odds | target_place_payout_yen |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REAR_VERY_HIGH | 2026-09-26 | 06264801 | 11 | 24103502 | ハクタカ | 16 | 2 | 9 | 134.90 | 3110 |
| REAR_VERY_HIGH | 2026-09-05 | 06264112 | 1 | 22101987 | シルバードン | 9 | 2 | 12 | 123.60 | 1390 |
| FINISH_GE6_PERF_TOP20 | 2026-09-27 | 06264907 | 1 | 22106212 | ウインロゼライト | 10 | 3 | 14 | 96.60 | 1810 |
| FINISH_GE6_PERF_TOP20 | 2026-09-12 | 06264304 | 4 | 23103347 | カーヴドヴァン | 8 | 1 | 16 | 64.80 | 1310 |
| FINISH_GE6_PERF_TOP20 | 2026-09-05 | 09264110 | 6 | 22105475 | レディーミコノス | 12 | 2 | 3 | 10.70 | 1230 |
| REAR_HIGH_LAST3F90 | 2026-09-05 | 06264112 | 1 | 22101987 | シルバードン | 9 | 2 | 12 | 123.60 | 1390 |

| signal | stratum | n | place_hits | place_payout_yen | place_roi_pct |
| --- | --- | --- | --- | --- | --- |
| REAR_VERY_HIGH | 2026-09-05 | 13 | 2 | 1710 | 131.54 |
| REAR_VERY_HIGH | 2026-09-06 | 9 | 1 | 460 | 51.11 |
| REAR_VERY_HIGH | 2026-09-12 | 11 | 2 | 410 | 37.27 |
| REAR_VERY_HIGH | 2026-09-13 | 8 | 1 | 320 | 40.00 |
| REAR_VERY_HIGH | 2026-09-19 | 11 | 3 | 1150 | 104.55 |
| REAR_VERY_HIGH | 2026-09-20 | 5 | 1 | 270 | 54.00 |
| REAR_VERY_HIGH | 2026-09-21 | 3 | 2 | 270 | 90.00 |
| REAR_VERY_HIGH | 2026-09-22 | 9 | 2 | 720 | 80.00 |
| REAR_VERY_HIGH | 2026-09-26 | 6 | 2 | 3240 | 540.00 |
| REAR_VERY_HIGH | 2026-09-27 | 11 | 2 | 790 | 71.82 |
| FINISH_GE6_PERF_TOP20 | 2026-09-05 | 10 | 4 | 2710 | 271.00 |
| FINISH_GE6_PERF_TOP20 | 2026-09-06 | 13 | 4 | 1260 | 96.92 |
| FINISH_GE6_PERF_TOP20 | 2026-09-12 | 16 | 5 | 2830 | 176.88 |
| FINISH_GE6_PERF_TOP20 | 2026-09-13 | 11 | 2 | 810 | 73.64 |
| FINISH_GE6_PERF_TOP20 | 2026-09-19 | 4 | 1 | 290 | 72.50 |
| FINISH_GE6_PERF_TOP20 | 2026-09-20 | 9 | 0 | 0 | 0.00 |
| FINISH_GE6_PERF_TOP20 | 2026-09-21 | 12 | 2 | 560 | 46.67 |
| FINISH_GE6_PERF_TOP20 | 2026-09-22 | 1 | 0 | 0 | 0.00 |
| FINISH_GE6_PERF_TOP20 | 2026-09-26 | 5 | 0 | 0 | 0.00 |
| FINISH_GE6_PERF_TOP20 | 2026-09-27 | 13 | 2 | 2300 | 176.92 |
| REAR_HIGH_LAST3F90 | 2026-09-05 | 6 | 3 | 1880 | 313.33 |
| REAR_HIGH_LAST3F90 | 2026-09-06 | 5 | 1 | 110 | 22.00 |
| REAR_HIGH_LAST3F90 | 2026-09-12 | 4 | 3 | 620 | 155.00 |
| REAR_HIGH_LAST3F90 | 2026-09-13 | 4 | 2 | 550 | 137.50 |
| REAR_HIGH_LAST3F90 | 2026-09-19 | 3 | 1 | 200 | 66.67 |
| REAR_HIGH_LAST3F90 | 2026-09-20 | 3 | 1 | 270 | 90.00 |
| REAR_HIGH_LAST3F90 | 2026-09-21 | 3 | 2 | 270 | 90.00 |
| REAR_HIGH_LAST3F90 | 2026-09-22 | 1 | 1 | 190 | 190.00 |
| REAR_HIGH_LAST3F90 | 2026-09-26 | 11 | 5 | 1070 | 97.27 |
| REAR_HIGH_LAST3F90 | 2026-09-27 | 3 | 1 | 640 | 213.33 |

前走6着以下×top20の高配当3頭は9/5・9/12・9/27の別開催日。最大1頭は払戻の16.82%。
的中は7日、ROI>100は3日であり、1頭だけの高配当には依存していないが、日別収益は安定しない。
後傾後方×上がり90は全10日で的中、ROI>100は5日。最大シルバードン1,390円が払戻の23.97%。
全払戻5,800円から購入4,300円を引いた利益1,500円のうち1,390円をこの1頭が占めるため、
利益水準への寄与は大きい。的中の広がりと収益の集中を区別する。
very-rearは最大1頭3,110円が総利益740円を大きく上回り、特に収益の集中が強い。

## 7. Q1–Q8への回答

| 問い | 9月で得られた回答 |
|---|---|
| Q1 タイム単独は強いか | 能力予測は強い。top20的中率36.22%。市場価値は同じではなく全体ROI89.87%。 |
| Q2 前走6着以下×top20 | HVで母集団を限定せず94頭・的中率21.28%・ROI114.47%。検証候補として有望。 |
| Q3 top20とtop10 | 9月の市場価値ではtop20。top10は人気が高まり、敗退馬の標本も縮小する。 |
| Q4 前傾前受け単独 | 小幅改善だが不確実。ROI87.16%で、利益や独立効果を支持しない。 |
| Q5 後傾後方単独 | 広い定義では弱い。ROI75.39%。狭い定義の高ROIは高配当集中が強い。 |
| Q6 タイムへ展開逆行を追加 | 前傾×top20は共通タイム単独に優位なし。後傾×タイムは極小N・低ROI。 |
| Q7 位置取り改善と比較 | POSITION_RECOVERYの市場価値は弱い。全PACE_OPPOSITIONが一律優位ではない。 |
| Q8 市場価値にもなるか | 後傾後方×上がり90と敗退×タイム20は候補。独立した市場価値の確証には固定閾値OOSが必要。 |

## 8. 次の検証・正式ルールとの境界

2024-01-01～2025-12-31のHistorical OOSへ、q80=-0.0555555555555524、q90=0.21138888888889343と
今回のpace/position/last3f条件を変更せず適用する。9月で最良だった帯への再最適化は禁止。
優先候補は前走6着以下×time top20と後傾後方×last3f>=90。
time単独、finish-matched、同odds帯、common complete parent、半期block方向を再比較する。
closing_gain複合は0対象のため未検証として残し、NULL=0で判定を作らない。
正式S/Aへの昇格は行っていない。既存凍結条件と9月quantileは明確に分離する。

能力指標のtop3/top5は3着以内/5着以内の競走成績であり、複勝hitとは別指標。
中止馬はtop3/top5不成立として率の分母に残し、平均着順はfinish>0のみ。
不確実性はtarget race cluster 1,000回・seed20261001で概算。馬の反復出走や複数signalの多重性を完全には扱わない。
説明可能な固定条件の一次研究であり、ランダム化研究や因果的独立効果推定ではない。

## 9. 再現方法・成果物

```bash
python horse-racing/jrdb/src/jrdb_previous_start_research_ledger.py   --input-dir INPUT --current-zip INPUT/RaceReviewDB_CURRENT.zip   --rule-zip INPUT/frozen_rules.zip --output-dir OUTPUT --source-commit SOURCE_SHA
python horse-racing/jrdb/src/analyze_rrdb_time_pace.py   --ledger OUTPUT/rrdb_202609_all_runner_research_ledger.parquet --output-dir OUTPUT
python horse-racing/jrdb/src/report_rrdb_time_pace.py   --output-dir OUTPUT --report horse-racing/jrdb/docs/RaceReviewDB_202609_Time_PaceOpposition_Analysis_v0_1.md
python horse-racing/jrdb/tests/test_jrdb_previous_start_research_ledger.py
```

INPUTは9月10日のPACI/SED ZIP、RRDB CURRENT、既存frozen rule archive。Google Drive connectorで取得する。
Actions↔Drive direct transportは使わず、一時Issue/workflowは作成していない。
Common Readerと既存RRDB/Next-Watch helperを利用し、consumer独自のbyte sliceは追加していない。
台帳・features・集計・matched比較・audit・provenanceは`horse-racing/jrdb/analysis/tmp/`に保存する。
CSVはUTF-8 BOM、identityは文字列。表計算ソフトで開く場合は先頭ゼロを維持する。
Parquetを型保持の正本とする。
