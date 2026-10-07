# EdgeDB v0.5 T1-T6 Prototype Aggregation

Status: PARTIAL_WITH_BLOCKED_FAMILIES

Discovery: 2024-01-01 through 2025-12-31 (inclusive). Context only: 2022-01-01 through 2023-12-31. 2026 excluded.

## Source provenance

- Feature Mart: edge_feature_mart_v0_2_g20260925_pq1, 781,161 rows, coverage 2010-01-05 .. 2025-12-28, manifest SHA-256 2b7d1d61a3b6b582f10d7bcdd6655ccb3f8abb2479b117935a49aa1b87aa68c8, Parquet SHA-256 82e6550639210eea6cf1fc1ac374ee8b6fc07115214fe75ea6e1bb704d3751f6, artifact run 36116777782 / sha256:19d713da2e6ebf57965de98952fbf18d79f9ddfd5c1996833af3267b1a53f725.
- Warehouse: jrdb_normalized_warehouse_v1_2010_2025_g20260921, source manifest SHA-256 a25cedfb5d76c1f9f2ed65308181e2f5222f294ee8015f93aabe3771fb7f1087.
- Analysis: analysis-v1_4-canonical-20260928-02, 517,622 rows, manifest SHA-256 e9c391e76fac86a15526e8ab453558e68fc00400a18674e26edf64aad9feec9e, artifact run 36437363166 / sha256:d159c2fca9959d9b144d55f9b3ba98228158cc38b85fcc730032a53f29252a55. Candidate and metric scans are bounded to 2022-2025; no 2026 result enters discovery or ranking.

## Execution route

- Local Data Storage: DEPENDENCY_MISSING; one requirements install blocked by managed proxy (proxy:8080 operation not permitted); fallback_candidate=true.
- Runtime: Python 3.12.14, DuckDB 1.1.3, PyArrow 25.0.1.
- Candidate groups use only pre-race features. Outcome and market diagnostics are queried only after the frozen 2024-2025 candidate table is created.

## Feature availability

| Feature | Availability / role | Coverage |
|---|---|---:|
| race_date | PRE_RACE_CANDIDATE | 100.0% (94,330/94,330) |
| race_key | PRE_RACE_CANDIDATE | 100.0% (94,330/94,330) |
| horse_no | PRE_RACE_CANDIDATE | 100.0% (94,330/94,330) |
| horse_id | PRE_RACE_CANDIDATE | 100.0% (94,330/94,330) |
| venue_code | PRE_RACE_CANDIDATE | 100.0% (94,330/94,330) |
| surface_code | PRE_RACE_CANDIDATE | 100.0% (94,330/94,330) |
| distance_m | PRE_RACE_CANDIDATE | 100.0% (94,330/94,330) |
| frame_no | PRE_RACE_CANDIDATE | 100.0% (94,330/94,330) |
| sire_name | PRE_RACE_CANDIDATE | 99.9989% (94,329/94,330) |
| distance_change_bucket | PRE_RACE_CANDIDATE | 87.6826% (82,711/94,330) |
| surface_transition | PRE_RACE_CANDIDATE | 87.6826% (82,711/94,330) |
| track_condition_bucket | PRE_RACE_CANDIDATE | 100.0% (94,330/94,330) |
| label_finish | POST_RACE_EVALUATION_ONLY | 100.0% (94,330/94,330) |
| label_win_hit | POST_RACE_EVALUATION_ONLY | 100.0% (94,330/94,330) |
| label_place_hit | POST_RACE_EVALUATION_ONLY | 100.0% (94,330/94,330) |
| label_win_payout | POST_RACE_EVALUATION_ONLY | 7.2808% (6,868/94,330) |
| label_place_payout | POST_RACE_EVALUATION_ONLY | 21.6198% (20,394/94,330) |
| label_final_win_odds | POST_RACE_EVALUATION_ONLY | 99.6258% (93,977/94,330) |
| label_final_win_popularity | POST_RACE_EVALUATION_ONLY | 100.0% (94,330/94,330) |
| FIRST_DIRT / FIRST_TURF | BLOCKED: not present in frozen Feature Mart; prior-surface difference is not substituted | — |
| FIRST_BLINKERS | BLOCKED: KYI blinker code is not present in frozen Feature Mart | — |
| Course topology | BLOCKED: no complete canonical venue+surface+distance(+variant) lookup established | — |

## Candidate counts and distributions

| Family | All groups | n>=5 | n<5 raw only | Support classes | Freshness | Research labels |
|---|---:|---:|---:|---|---|---|
| T1 | 800 | 725 | 75 | {"LARGE":550,"MEDIUM":106,"MICRO":46,"RAW_ONLY":75,"SMALL":23} | {"CURRENT":321,"DECAYING":166,"EMERGING":43,"INSUFFICIENT_HISTORY":15,"OLD_ONLY":3,"VOLATILE":177} | {"CURRENT_BUT_LOW_SUPPORT":8,"DECAYING":166,"EMERGING":43,"INSUFFICIENT":15,"LONGSHOT_EVIDENCE":614,"NICHE_VALUE_NEGATIVE":114,"NICHE_VALUE_POSITIVE":100,"PERFORMANCE_NEGATIVE":479,"PERFORMANCE_POSITIVE":449,"SATURATED_OR_PRICED":274,"WEAK":492} |
| T2 | 12939 | 4767 | 8172 | {"LARGE":191,"MEDIUM":1004,"MICRO":2076,"RAW_ONLY":8172,"SMALL":1496} | {"CURRENT":659,"DECAYING":804,"EMERGING":80,"INSUFFICIENT_HISTORY":1845,"OLD_ONLY":17,"VOLATILE":1362} | {"CURRENT_BUT_LOW_SUPPORT":197,"DECAYING":804,"EMERGING":80,"INSUFFICIENT":1845,"LONGSHOT_EVIDENCE":1724,"NICHE_VALUE_NEGATIVE":1679,"NICHE_VALUE_POSITIVE":1102,"PERFORMANCE_NEGATIVE":3375,"PERFORMANCE_POSITIVE":2741,"SATURATED_OR_PRICED":1291,"WEAK":3205} |
| T3 | 928 | 523 | 405 | {"LARGE":177,"MEDIUM":80,"MICRO":164,"RAW_ONLY":405,"SMALL":102} | {"CURRENT":134,"DECAYING":84,"EMERGING":9,"INSUFFICIENT_HISTORY":160,"VOLATILE":136} | {"CURRENT_BUT_LOW_SUPPORT":23,"DECAYING":84,"EMERGING":9,"INSUFFICIENT":160,"LONGSHOT_EVIDENCE":288,"NICHE_VALUE_NEGATIVE":138,"NICHE_VALUE_POSITIVE":93,"PERFORMANCE_NEGATIVE":413,"PERFORMANCE_POSITIVE":235,"SATURATED_OR_PRICED":101,"WEAK":376} |
| T4 | 656 | 264 | 392 | {"LARGE":54,"MEDIUM":86,"MICRO":73,"RAW_ONLY":392,"SMALL":51} | {"CURRENT":43,"DECAYING":61,"EMERGING":4,"INSUFFICIENT_HISTORY":73,"VOLATILE":83} | {"CURRENT_BUT_LOW_SUPPORT":11,"DECAYING":61,"EMERGING":4,"INSUFFICIENT":73,"LONGSHOT_EVIDENCE":131,"NICHE_VALUE_NEGATIVE":133,"NICHE_VALUE_POSITIVE":49,"PERFORMANCE_NEGATIVE":245,"PERFORMANCE_POSITIVE":54,"SATURATED_OR_PRICED":17,"WEAK":195} |
| T6 | 1614 | 1024 | 590 | {"LARGE":353,"MEDIUM":199,"MICRO":262,"RAW_ONLY":590,"SMALL":210} | {"CURRENT":242,"DECAYING":197,"EMERGING":20,"INSUFFICIENT_HISTORY":306,"OLD_ONLY":5,"VOLATILE":254} | {"CURRENT_BUT_LOW_SUPPORT":29,"DECAYING":197,"EMERGING":20,"INSUFFICIENT":306,"LONGSHOT_EVIDENCE":572,"NICHE_VALUE_NEGATIVE":104,"NICHE_VALUE_POSITIVE":186,"PERFORMANCE_NEGATIVE":564,"PERFORMANCE_POSITIVE":607,"SATURATED_OR_PRICED":326,"WEAK":707} |

### Family metric distributions (n>=5)

| Family | n median (p10-p90) | Overall win ROI median (p10-p90) | Overall place ROI median (p10-p90) | 2024 win/place ROI medians | 2025 win/place ROI medians | Longshot place hits median (p90) |
|---|---:|---:|---:|---:|---:|---:|
| T1 | 101.0 (23.0-250.0) | 54.7 (15.4-130.2) | 67.8 (39.4-109.1) | 45.9375 / 64.35146443514644 | 48.028169014084504 / 63.14049586776859 | 3.0 (10.0) |
| T2 | 11.0 (5.0-34.0) | 18.7 (0.0-176.6) | 55.6 (0.0-147.4) | 0.0 / 45.0 | 0.0 / 41.81818181818182 | 0.0 (2.0) |
| T3 | 19.0 (5.0-183.0) | 31.9 (0.0-138.6) | 57.9 (0.0-132.6) | 6.808510638297872 / 55.0 | 0.0 / 48.392857142857146 | 1.0 (7.0) |
| T4 | 22.0 (6.0-80.0) | 0.0 (0.0-149.4) | 44.0 (0.0-136.0) | 0.0 / 26.229508196721312 | 0.0 / 31.428571428571427 | 0.0 (3.0) |
| T6 | 23.0 (6.0-234.0) | 31.7 (0.0-146.0) | 62.5 (0.0-125.0) | 20.0 / 58.333333333333336 | 18.536585365853657 / 54.82837528604119 | 1.0 (8.0) |

Metrics are unweighted per-runner rates. Returns are separate, with ROI based on 100-yen stakes. Longshot hits mean place/top-3 hits at popularity >=5/8/10; popularity, odds, and payouts do not define groups. Top1/top3 dependence is descriptive, not a rejection gate.

### Positive Value gate by family

| Family | Raw n>=5 | ROI>=100 | MICRO | SMALL | MEDIUM | LARGE | Longshot positive | Post-redundancy reps |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| T1 | 725 | 100 | 14 | 7 | 21 | 58 | 92 | 100 |
| T2 | 4767 | 1102 | 500 | 362 | 209 | 31 | 884 | 1073 |
| T3 | 523 | 93 | 39 | 21 | 14 | 19 | 75 | 93 |
| T4 | 264 | 49 | 12 | 11 | 16 | 10 | 46 | 49 |
| T6 | 1024 | 186 | 60 | 51 | 33 | 42 | 153 | 185 |

Gate: `overall_2024_2025.place_roi >= 100 AND n >= 5`. Positive labels are absolute ROI-gated; performance labels use parent-relative occurrence rates. Negative Edge uses the conservative dual deterioration gate. Representative rule: Within suggested Jaccard >= 0.80 or exact-subset components of ROI-qualified candidates only, choose lowest condition depth, then largest recent n, then candidate ID; raw candidates are retained.

#### Largest positive Value redundancy clusters

| Representative | Cluster size | Suppressed positive candidate IDs |
|---|---:|---|
| v05-971f98c5c9616673e88b466d | 5 | v05-2d71b3bf5d2364dda150e0b3, v05-36932ffe6ca98a1175f78a60, v05-3897a6ee881a57218ea386e6, v05-7e084b5a18ec70b127117e72 |
| v05-39ec333e58fed6561c997a20 | 4 | v05-7c45ccb74ddf1a601743e1a0, v05-aaf0445d2f736c1dfdfe6394, v05-dcddd99f791ee0a7a37b195a |
| v05-424480a6f54e77fc4a9e149a | 4 | v05-2fe3ab649fb5fa41b73efffe, v05-849bf4192fc283e1e69680cd, v05-a8086178efbf40926e20a5f5 |
| v05-3f20d1d83c6120df9965b813 | 3 | v05-32a5c91ba2ae4632f8ce4d1b, v05-4efb9ee6b8d2b29ff0c366ae |
| v05-4789db27c353ab9eb63e8959 | 3 | v05-7610f9feb7a38d3aabe96cc7, v05-ea5d985d97a3838c411f67ac |
| v05-7ffbae0b53e4bf8836752334 | 3 | v05-58a310531f88cc014bcda9ae, v05-7b415fbcbe98ddad5aaeb677 |
| v05-bb6e406fa22dd7aa70ae1042 | 3 | v05-81c8ce60f08c0dc350dedc6f, v05-d1ae3913f03d0f8570321027 |
| v05-2706e22ceabe46817834a751 | 2 | v05-d2a521bfc978d1d4a71e7f39 |
| v05-3ccaf20c760f18fcc6324366 | 2 | v05-bc57e17f130057121340cdb1 |
| v05-5056f673a5dfab937d7ef5ff | 2 | v05-498fc42ed4af65abc0daaf4e |

## Human review examples

| Type | Candidate | Memo | Template | Support | n | Wins | Places | Win ROI | Place ROI | 2024 Place ROI | 2025 Place ROI | 22-23 Context Place ROI | 5+/8+/10+ hits | Max hit popularity | Largest place payout | Parent Δ place rate | Value band | Freshness | Jackpot | Redundancy |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|---|---|---|
| positive_value | v05-7bfd3cf14969877bc589a27c | 中山ダート1200mは7枠で、近年、親条件より複勝率が高い | T1_COURSE_FRAME | LARGE | 470 | 34 | 105 | 84.4 | 108.0 | 103.4 | 112.6 | 66.6 | 41/18/8 | 16 | 5630 | 3.1pp | VALUE_100_119 | EMERGING | DESCRIPTIVE | NO_SUGGESTED_CLUSTER |
| positive_value | v05-e79ee0c3f7db5c35a2f8705c | 京都芝1600mは8枠で、近年、親条件より複勝率が高い | T1_COURSE_FRAME | LARGE | 276 | 26 | 77 | 96.1 | 103.1 | 114.0 | 85.2 | 91.9 | 34/12/6 | 12 | 2010 | 6.0pp | VALUE_100_119 | CURRENT | DESCRIPTIVE | NO_SUGGESTED_CLUSTER |
| positive_value | v05-f3045c1c5f451e1e825f6f6e | シニスターミニスター産駒は京都ダート1800mで、近年、親条件より複勝率が高い | T2_SIRE_COURSE | LARGE | 125 | 20 | 45 | 112.2 | 109.2 | 133.4 | 75.2 | 180.0 | 21/7/2 | 11 | 1180 | 8.3pp | VALUE_100_119 | VOLATILE | DESCRIPTIVE | NO_SUGGESTED_CLUSTER |
| positive_value | v05-b93b888356f90cc2c5ca4652 | エピファネイア産駒は東京芝1600mで、近年、親条件より複勝率が高い | T2_SIRE_COURSE | LARGE | 92 | 9 | 35 | 307.2 | 115.9 | 140.2 | 97.1 | 72.6 | 10/6/2 | 14 | 1950 | 12.1pp | VALUE_100_119 | CURRENT | ONE_BIG_HIT | NO_SUGGESTED_CLUSTER |
| positive_value | v05-0cdf0a7051d2145310ce0270 | モーリス産駒は距離延長で、近年、親条件より複勝率が低い | T3_SIRE_DISTANCE_CHANGE | LARGE | 421 | 29 | 82 | 130.5 | 106.2 | 114.3 | 97.7 | 69.0 | 42/18/10 | 16 | 7030 | -3.8pp | VALUE_100_119 | CURRENT | DESCRIPTIVE | REPRESENTATIVE |
| positive_value | v05-7bd2f6c9349bea59e893c21f | シルバーステート産駒は距離延長で、近年、親条件より複勝率が高い | T3_SIRE_DISTANCE_CHANGE | LARGE | 307 | 18 | 65 | 135.8 | 101.3 | 93.0 | 109.3 | 61.7 | 30/14/9 | 16 | 2980 | 0.2pp | VALUE_100_119 | EMERGING | DESCRIPTIVE | NO_SUGGESTED_CLUSTER |
| positive_value | v05-c98b14f4a0ae9188a963b4a9 | サトノダイヤモンド産駒は芝→ダート替わりで、近年、親条件より複勝率が低い | T4_SIRE_SURFACE_SWITCH | LARGE | 103 | 4 | 22 | 31.8 | 116.0 | 76.9 | 154.4 | 118.8 | 12/5/3 | 14 | 2480 | -1.7pp | VALUE_100_119 | VOLATILE | DESCRIPTIVE | NO_SUGGESTED_CLUSTER |
| positive_value | v05-d4b1809fa461f264468596a6 | モーリス産駒はダート→芝替わりで、近年、親条件より複勝率が低い | T4_SIRE_SURFACE_SWITCH | LARGE | 93 | 3 | 8 | 276.5 | 116.7 | 8.9 | 213.5 | 108.1 | 6/3/2 | 16 | 5710 | -14.7pp | VALUE_100_119 | VOLATILE | ONE_BIG_HIT | NO_SUGGESTED_CLUSTER |
| positive_value | v05-971f98c5c9616673e88b466d | イスラボニータ産駒は芝・良馬場で、近年、親条件より複勝率が高い | T6_SIRE_SURFACE_GOING | LARGE | 556 | 48 | 149 | 135.1 | 102.3 | 124.7 | 80.7 | 69.9 | 64/25/11 | 14 | 3950 | 2.9pp | VALUE_100_119 | CURRENT | DESCRIPTIVE | REPRESENTATIVE |
| positive_value | v05-b354d8b92c360ccf7c3d3674 | マインドユアビスケッツ産駒はダート・稍重以上で、近年、親条件より複勝率が高い | T6_SIRE_SURFACE_GOING | LARGE | 241 | 18 | 54 | 128.8 | 100.5 | 76.8 | 119.1 | 92.8 | 24/13/8 | 16 | 3530 | 1.7pp | VALUE_100_119 | EMERGING | DESCRIPTIVE | NO_SUGGESTED_CLUSTER |
| longshot_evidence | v05-94b6f1d7c7285dba02b8b53d | エピファネイア産駒は芝・良馬場で、近年、親条件より複勝率が高い | T6_SIRE_SURFACE_GOING | LARGE | 1538 | 145 | 452 | 75.6 | 71.3 | 74.5 | 67.9 | 76.8 | 104/36/12 | 14 | 1950 | 1.2pp | — | CURRENT | DESCRIPTIVE | SUGGESTED_REDUNDANT |
| longshot_evidence | v05-ddbd88d51edb8f683244ec4b | キズナ産駒は芝・良馬場で、近年、親条件より複勝率が低い | T6_SIRE_SURFACE_GOING | LARGE | 1490 | 174 | 433 | 81.9 | 67.8 | 70.9 | 64.6 | 105.6 | 89/30/11 | 15 | 2870 | -0.2pp | — | DECAYING | DESCRIPTIVE | REPRESENTATIVE |
| longshot_evidence | v05-d858f933b434d8dfce050607 | ロードカナロア産駒は芝・良馬場で、近年、親条件より複勝率が高い | T6_SIRE_SURFACE_GOING | LARGE | 1264 | 151 | 372 | 69.8 | 78.5 | 72.2 | 85.7 | 74.1 | 89/37/19 | 16 | 3570 | 0.5pp | — | CURRENT | DESCRIPTIVE | REPRESENTATIVE |
| emerging | v05-7bfd3cf14969877bc589a27c | 中山ダート1200mは7枠で、近年、親条件より複勝率が高い | T1_COURSE_FRAME | LARGE | 470 | 34 | 105 | 84.4 | 108.0 | 103.4 | 112.6 | 66.6 | 41/18/8 | 16 | 5630 | 3.1pp | VALUE_100_119 | EMERGING | DESCRIPTIVE | NO_SUGGESTED_CLUSTER |
| emerging | v05-7bd2f6c9349bea59e893c21f | シルバーステート産駒は距離延長で、近年、親条件より複勝率が高い | T3_SIRE_DISTANCE_CHANGE | LARGE | 307 | 18 | 65 | 135.8 | 101.3 | 93.0 | 109.3 | 61.7 | 30/14/9 | 16 | 2980 | 0.2pp | VALUE_100_119 | EMERGING | DESCRIPTIVE | NO_SUGGESTED_CLUSTER |
| emerging | v05-0265c9ce15efd4856c760b60 | 阪神ダート1800mは5枠で、近年、親条件より複勝率が高い | T1_COURSE_FRAME | LARGE | 256 | 28 | 68 | 86.6 | 103.2 | 75.8 | 115.2 | 66.5 | 25/11/7 | 16 | 3180 | 3.1pp | VALUE_100_119 | EMERGING | DESCRIPTIVE | NO_SUGGESTED_CLUSTER |
| current | v05-971f98c5c9616673e88b466d | イスラボニータ産駒は芝・良馬場で、近年、親条件より複勝率が高い | T6_SIRE_SURFACE_GOING | LARGE | 556 | 48 | 149 | 135.1 | 102.3 | 124.7 | 80.7 | 69.9 | 64/25/11 | 14 | 3950 | 2.9pp | VALUE_100_119 | CURRENT | DESCRIPTIVE | REPRESENTATIVE |
| current | v05-0cdf0a7051d2145310ce0270 | モーリス産駒は距離延長で、近年、親条件より複勝率が低い | T3_SIRE_DISTANCE_CHANGE | LARGE | 421 | 29 | 82 | 130.5 | 106.2 | 114.3 | 97.7 | 69.0 | 42/18/10 | 16 | 7030 | -3.8pp | VALUE_100_119 | CURRENT | DESCRIPTIVE | REPRESENTATIVE |
| current | v05-e79ee0c3f7db5c35a2f8705c | 京都芝1600mは8枠で、近年、親条件より複勝率が高い | T1_COURSE_FRAME | LARGE | 276 | 26 | 77 | 96.1 | 103.1 | 114.0 | 85.2 | 91.9 | 34/12/6 | 12 | 2010 | 6.0pp | VALUE_100_119 | CURRENT | DESCRIPTIVE | NO_SUGGESTED_CLUSTER |
| micro_positive_value | v05-0504f624af17aeb01c7fdf6d | タイムパラドックス産駒は東京ダート1600mで、近年、親条件より複勝率が高い | T2_SIRE_COURSE | MICRO | 9 | 0 | 2 | 0.0 | 136.7 | 246.0 | 0.0 | 33.3 | 2/2/2 | 10 | 760 | 15.1pp | VALUE_120_149 | VOLATILE | DESCRIPTIVE | NO_SUGGESTED_CLUSTER |
| micro_positive_value | v05-0e11a3e306fcf291ec0d3a93 | メンデルスゾーン産駒は中山ダート1800mで、近年、親条件より複勝率が高い | T2_SIRE_COURSE | MICRO | 9 | 1 | 4 | 455.6 | 140.0 | 180.0 | 0.0 | 100.0 | 1/1/1 | 10 | 700 | 7.4pp | VALUE_120_149 | VOLATILE | ONE_BIG_HIT | NO_SUGGESTED_CLUSTER |
| micro_positive_value | v05-12cf0ab18993dd4cd2e85517 | アドマイヤマーズ産駒は福島芝1800mで、近年、親条件より複勝率が高い | T2_SIRE_COURSE | MICRO | 9 | 1 | 3 | 106.7 | 124.4 | 160.0 | 0.0 | — | 2/0/0 | 7 | 720 | 5.8pp | VALUE_120_149 | INSUFFICIENT_HISTORY | ONE_BIG_HIT | NO_SUGGESTED_CLUSTER |
| saturated_or_priced | v05-94b6f1d7c7285dba02b8b53d | エピファネイア産駒は芝・良馬場で、近年、親条件より複勝率が高い | T6_SIRE_SURFACE_GOING | LARGE | 1538 | 145 | 452 | 75.6 | 71.3 | 74.5 | 67.9 | 76.8 | 104/36/12 | 14 | 1950 | 1.2pp | — | CURRENT | DESCRIPTIVE | SUGGESTED_REDUNDANT |
| saturated_or_priced | v05-d858f933b434d8dfce050607 | ロードカナロア産駒は芝・良馬場で、近年、親条件より複勝率が高い | T6_SIRE_SURFACE_GOING | LARGE | 1264 | 151 | 372 | 69.8 | 78.5 | 72.2 | 85.7 | 74.1 | 89/37/19 | 16 | 3570 | 0.5pp | — | CURRENT | DESCRIPTIVE | REPRESENTATIVE |
| saturated_or_priced | v05-a43f61f7a2846337ec1775db | ドゥラメンテ産駒は芝・良馬場で、近年、親条件より複勝率が高い | T6_SIRE_SURFACE_GOING | LARGE | 998 | 91 | 250 | 92.6 | 64.2 | 62.2 | 66.6 | 75.6 | 69/23/12 | 15 | 2070 | 0.1pp | — | CURRENT | DESCRIPTIVE | REPRESENTATIVE |
| negative_edge | v05-f208589c42a8e8b8f06c4f1e | オルフェーヴル産駒は距離延長で、近年、親条件より複勝率が低い | T3_SIRE_DISTANCE_CHANGE | LARGE | 308 | 10 | 43 | 45.0 | 43.7 | 47.1 | 40.2 | 93.1 | 21/5/1 | 11 | 1390 | -3.5pp | — | DECAYING | DESCRIPTIVE | NO_SUGGESTED_CLUSTER |
| negative_edge | v05-fe485fd68f71c7302a2ec4ff | 京都ダート1400mは2枠で、近年、親条件より複勝率が低い | T1_COURSE_FRAME | LARGE | 282 | 16 | 46 | 92.0 | 46.3 | 52.8 | 36.6 | 70.7 | 15/5/4 | 12 | 1800 | -4.2pp | — | DECAYING | DESCRIPTIVE | NO_SUGGESTED_CLUSTER |
| negative_edge | v05-b793e6173a75ef378bc8b3dd | リアルスティール産駒はダート・稍重以上で、近年、親条件より複勝率が低い | T6_SIRE_SURFACE_GOING | LARGE | 263 | 24 | 55 | 46.4 | 51.9 | 62.9 | 45.7 | 93.9 | 15/4/0 | 8 | 890 | -3.1pp | — | DECAYING | DESCRIPTIVE | NO_SUGGESTED_CLUSTER |
| redundant_cluster | v05-2706e22ceabe46817834a751 | プリサイスエンド産駒はダート・良馬場で、近年、親条件より複勝率が低い | T6_SIRE_SURFACE_GOING | MEDIUM | 44 | 2 | 8 | 57.0 | 139.3 | 108.5 | 183.9 | 78.4 | 5/3/3 | 15 | 2860 | -1.5pp | VALUE_120_149 | VOLATILE | ONE_BIG_HIT | REPRESENTATIVE |
| redundant_cluster | v05-39ec333e58fed6561c997a20 | グレーターロンドン産駒は芝・良馬場で、近年、親条件より複勝率が高い | T6_SIRE_SURFACE_GOING | LARGE | 227 | 29 | 62 | 168.8 | 102.2 | 110.8 | 93.8 | 85.2 | 30/13/5 | 12 | 1760 | 1.9pp | VALUE_100_119 | CURRENT | DESCRIPTIVE | REPRESENTATIVE |
| redundant_cluster | v05-3ccaf20c760f18fcc6324366 | レーヴミストラル産駒は芝・良馬場で、近年、親条件より複勝率が高い | T6_SIRE_SURFACE_GOING | SMALL | 16 | 0 | 3 | 0.0 | 550.6 | 1018.3 | 270.0 | 0.0 | 3/3/3 | 16 | 6110 | 3.0pp | VALUE_150_PLUS | VOLATILE | DESCRIPTIVE | REPRESENTATIVE |

## Scientific correction

The earlier prototype labeled any positive parent-relative place-rate difference as NICHE_VALUE_POSITIVE and any negative difference as NICHE_VALUE_NEGATIVE. That conflated occurrence performance with betting value.

The corrected labels are separate: PERFORMANCE_POSITIVE / PERFORMANCE_NEGATIVE use parent-relative place-rate or win-rate deltas. NICHE_VALUE_POSITIVE requires combined 2024-2025 place ROI >=100% and n>=5. Bands (100-119, 120-149, 150+) are descriptive. The gate uses combined years and allows one-hit/top1-driven MICRO candidates. NICHE_VALUE_NEGATIVE requires n>=5, an available parent, delta place rate <=-0.03, and delta place ROI <=-20 percentage points.

Candidate membership remains pre-race and market-blind; popularity, odds, and payouts are attached after groups are frozen. Raw n>=5 candidates below the Value gate remain in the Parquet research table.

## Blocked-family re-audit

| Feature | Canonical source and fields | Result |
|---|---|---|
| FIRST_BLINKERS | Warehouse KYI 2010-2025: blood_registration_no, race_key_raw, horse_no, blinker_code; codes 1/2/3 = first-worn/re-worn/active | Schema PASS; chronology fixture tests pass; full join BLOCKED because Warehouse Parquet is not an Actions input artifact |
| FIRST_DIRT / FIRST_TURF | Warehouse ZED/SED 2010-2025: blood_registration_no, race_key_raw, race_date, surface_code, horse_no | Schema PASS; tested helper excludes target and preserves UNKNOWN for censored history; full join awaits Warehouse materialization/source duplicate audit |
| Course topology | BAC: race_key_raw, surface, distance, turn_code, layout_code; codebooks map turn direction/layout class | BLOCKED; no authoritative one-turn/two-turn crosswalk; raw codes do not encode turn count |
| Warehouse provenance | jrdb_normalized_warehouse_v1_2010_2025_g20260921; manifest SHA-256 a25cedfb5d76c1f9f2ed65308181e2f5222f294ee8015f93aabe3771fb7f1087 | KYI/ZED/SED/BAC each contain 16 annual partitions for 2010-2025; family manifest hashes and fields are in t1_t6_summary.json |

## Desired-pattern check

- Sire × turf one-turn: BLOCKED pending canonical course-topology mapping.
- Sire × distance extension: EXPRESSIBLE; uses existing canonical >=200m EXTEND buckets (EXTEND and LARGE_EXTEND aggregated).
- Sire × first dirt: source schema supports chronology derivation, but the full join was not run because canonical Warehouse Parquet was not a fallback input.

## Failure modes and next research issues

- The n>=5 research population stays intact; only the presentation layer applies ROI eligibility and overlap representatives.
- Positive redundancy uses ROI-qualified candidates only; suppressed IDs remain in summary metadata and raw candidate rows remain in Parquet.
- T4/T5 history must be rerun after canonical Warehouse annual assets are materialized and source duplicates reconciled.
- Course topology remains blocked because repository metadata lacks an authoritative turn-count map.

## Recommendation

PARTIAL_WITH_BLOCKED_FAMILIES. Scientific labels and ROI shortlist are corrected. T1/T2/T3/T4-switch/T6 remain executable; true first surface and T5 await Warehouse asset materialization; topology remains blocked after metadata audit. Production impact NONE; no v0.2/v0.3/v0.4 manifest, RaceNote, Newspaper, or PWA consumer was changed.

## Instruction 002 execution provenance

- Corrective instruction: `20261007_002_v05_prototype_scientific_correction_and_roi_gate_instruction.md`, source commit `d0c1ab9f9f84356605a5cbac86c6c388b511217f`.
- Implementation source: `a43f150b9900163a629b95fe809cd37800f5236b`; PR #1871 remains open and unmerged.
- Actions Data Storage fallback: Issue #1875, run [37590302135](https://github.com/yukki0113/GPT/actions/runs/37590302135), PASS; artifact `data-storage-fallback-37590302135`, digest `sha256:c1444592c9e01bd6b85562418d52b3b011f461e7f95c8c951d3de450f91eb675`. DuckDB 1.1.3 / PyArrow 25.0.1; aggregation exit code 0. `production_publication=false`.
- Corrected gate results: raw n>=5 remains 7,303; 1,530 meet the positive Value gate; 1,500 are positive presentation representatives; 2,168 meet the conservative negative gate; 1,250 positive Value candidates also carry LONGSHOT_EVIDENCE. The full 7,303-row candidate Parquet and 9,634-row raw-only Parquet remain in the Actions artifact.
- Family positive/representative counts: T1 100/100; T2 1,102/1,073; T3 93/93; T4 49/49; T6 186/185.
- Focused local verification: 14 tests passed; `py_compile` passed for implementation and tests.
- Warehouse chronology/topology audit used the canonical manifest and annual schemas from Drive. KYI/ZED/SED support exact identity/history derivation; the full join remains blocked because the accepted Actions fallback input contract does not transport those Drive Parquets. BAC has no turn-count category and repository metadata has no authoritative topology crosswalk.
