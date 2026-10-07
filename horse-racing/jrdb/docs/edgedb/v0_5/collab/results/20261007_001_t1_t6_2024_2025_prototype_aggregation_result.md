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

## Task and execution provenance

- Instruction source: `horse-racing/jrdb/docs/edgedb/v0_5/collab/instructions/20261007_001_t1_t6_2024_2025_prototype_aggregation_instruction.md` at commit `360f8756d894fa0ee137165694cd6c25c6865675`.
- Executed source commit: `ab6392f2181d67f9157e4da8b4435fbd86054115`.
- Data Storage fallback Issue: #1869; request `edgedb-v05-t1-t6-2024-2025-20261007-final-year-dists`.
- Actions run: [37586491097](https://github.com/yukki0113/GPT/actions/runs/37586491097), PASS; artifact `data-storage-fallback-37586491097`, digest `sha256:70c250442621c112b75b3b07b57222d999ec4ece1cc988a0d9cf58592100d8fd`. The artifact contains candidate Parquet, raw n<5 Parquet, candidate CSV, summary JSON, feature audit, redundancy JSON, shortlist, report, fallback audit, and logs.
- Fallback audit records DuckDB 1.1.3, PyArrow 25.0.1, Python 3.12.14; aggregation step exit code 0, elapsed 8.64 seconds. `production_publication=false`.
- Local Data Storage preflight returned `DEPENDENCY_MISSING`; one install attempt failed because managed proxy `proxy:8080` denied network access. Reported as `LOCAL_DATA_STORAGE_BLOCKED`, `fallback_candidate=true`; the documented Actions route was used.
- Analysis artifact was resolved and validated as accepted source provenance; discovery and metric scans used the frozen Feature Mart rows for 2022-2025 only.
- `race_horse_key` is not an explicit Feature Mart column; runner identity for overlap audit is reconstructed from canonical `race_key` + `horse_no`. Previous-race semantics are represented by existing canonical `distance_change_bucket` and `surface_transition` fields (87.6826% coverage in the eligible discovery rows).

### Aggregate counts and redundancy

- 94,330 eligible runner rows in the 2024-2025 discovery window.
- 16,937 condition groups across executable families: 7,303 with evaluation support n>=5 and 9,634 retained in raw-only n<5 output.
- Supported class counts: MICRO 2,621; SMALL 1,882; MEDIUM 1,475; LARGE 1,325. All n>=5 candidates remain, regardless of ROI or jackpot dependence.
- Freshness counts: CURRENT 1,399; DECAYING 1,312; EMERGING 156; OLD_ONLY 25; VOLATILE 2,012; INSUFFICIENT_HISTORY 2,399. Research labels are multi-label and are not a rank score.
- Redundancy audit: 135,220 overlapping pairs, 667 suggested review pairs, 260 suggested clusters at advisory Jaccard >=0.80 or exact subset; raw candidates were not removed.
- The full candidate Parquet/CSV and machine-readable diagnostics remain in the Actions artifact linked above; compact JSON summaries are checked in beside this report.

## Candidate counts and distributions

| Family | All groups | n>=5 | n<5 raw only | Support classes | Freshness | Research labels |
|---|---:|---:|---:|---|---|---|
| T1 | 800 | 725 | 75 | {"LARGE":550,"MEDIUM":106,"MICRO":46,"RAW_ONLY":75,"SMALL":23} | {"CURRENT":321,"DECAYING":166,"EMERGING":43,"INSUFFICIENT_HISTORY":15,"OLD_ONLY":3,"VOLATILE":177} | {"CURRENT_BUT_LOW_SUPPORT":8,"DECAYING":166,"EMERGING":43,"INSUFFICIENT":15,"LONGSHOT_EVIDENCE":614,"NICHE_VALUE_NEGATIVE":365,"NICHE_VALUE_POSITIVE":360,"SATURATED_OR_PRICED":274,"WEAK":492} |
| T2 | 12939 | 4767 | 8172 | {"LARGE":191,"MEDIUM":1004,"MICRO":2076,"RAW_ONLY":8172,"SMALL":1496} | {"CURRENT":659,"DECAYING":804,"EMERGING":80,"INSUFFICIENT_HISTORY":1845,"OLD_ONLY":17,"VOLATILE":1362} | {"CURRENT_BUT_LOW_SUPPORT":197,"DECAYING":804,"EMERGING":80,"INSUFFICIENT":1845,"LONGSHOT_EVIDENCE":1724,"NICHE_VALUE_NEGATIVE":2575,"NICHE_VALUE_POSITIVE":2186,"SATURATED_OR_PRICED":1291,"WEAK":3205} |
| T3 | 928 | 523 | 405 | {"LARGE":177,"MEDIUM":80,"MICRO":164,"RAW_ONLY":405,"SMALL":102} | {"CURRENT":134,"DECAYING":84,"EMERGING":9,"INSUFFICIENT_HISTORY":160,"VOLATILE":136} | {"CURRENT_BUT_LOW_SUPPORT":23,"DECAYING":84,"EMERGING":9,"INSUFFICIENT":160,"LONGSHOT_EVIDENCE":288,"NICHE_VALUE_NEGATIVE":350,"NICHE_VALUE_POSITIVE":161,"SATURATED_OR_PRICED":101,"WEAK":376} |
| T4 | 656 | 264 | 392 | {"LARGE":54,"MEDIUM":86,"MICRO":73,"RAW_ONLY":392,"SMALL":51} | {"CURRENT":43,"DECAYING":61,"EMERGING":4,"INSUFFICIENT_HISTORY":73,"VOLATILE":83} | {"CURRENT_BUT_LOW_SUPPORT":11,"DECAYING":61,"EMERGING":4,"INSUFFICIENT":73,"LONGSHOT_EVIDENCE":131,"NICHE_VALUE_NEGATIVE":232,"NICHE_VALUE_POSITIVE":30,"SATURATED_OR_PRICED":17,"WEAK":195} |
| T6 | 1614 | 1024 | 590 | {"LARGE":353,"MEDIUM":199,"MICRO":262,"RAW_ONLY":590,"SMALL":210} | {"CURRENT":242,"DECAYING":197,"EMERGING":20,"INSUFFICIENT_HISTORY":306,"OLD_ONLY":5,"VOLATILE":254} | {"CURRENT_BUT_LOW_SUPPORT":29,"DECAYING":197,"EMERGING":20,"INSUFFICIENT":306,"LONGSHOT_EVIDENCE":572,"NICHE_VALUE_NEGATIVE":435,"NICHE_VALUE_POSITIVE":463,"SATURATED_OR_PRICED":326,"WEAK":707} |

### Family metric distributions (n>=5)

| Family | n median (p10-p90) | Overall win ROI median (p10-p90) | Overall place ROI median (p10-p90) | 2024 win/place ROI medians | 2025 win/place ROI medians | Longshot place hits median (p90) |
|---|---:|---:|---:|---:|---:|---:|
| T1 | 101.0 (23.0-250.0) | 54.7 (15.4-130.2) | 67.8 (39.4-109.1) | 45.9375 / 64.35146443514644 | 48.028169014084504 / 63.14049586776859 | 3.0 (10.0) |
| T2 | 11.0 (5.0-34.0) | 18.7 (0.0-176.6) | 55.6 (0.0-147.4) | 0.0 / 45.0 | 0.0 / 41.81818181818182 | 0.0 (2.0) |
| T3 | 19.0 (5.0-183.0) | 31.9 (0.0-138.6) | 57.9 (0.0-132.6) | 6.808510638297872 / 55.0 | 0.0 / 48.392857142857146 | 1.0 (7.0) |
| T4 | 22.0 (6.0-80.0) | 0.0 (0.0-149.4) | 44.0 (0.0-136.0) | 0.0 / 26.229508196721312 | 0.0 / 31.428571428571427 | 0.0 (3.0) |
| T6 | 23.0 (6.0-234.0) | 31.7 (0.0-146.0) | 62.5 (0.0-125.0) | 20.0 / 58.333333333333336 | 18.536585365853657 / 54.82837528604119 | 1.0 (8.0) |

Metrics are unweighted per-runner rates. Returns are separate, with ROI based on 100-yen stakes. Longshot hits mean place/top-3 hits at popularity >=5/8/10; popularity, odds, and payouts do not define groups. Top1/top3 dependence is descriptive, not a rejection gate.

## Human review examples

| Type | Candidate | Memo | Template | Support | n | Wins | Places | Win ROI | Place ROI | 2024 Place ROI | 2025 Place ROI | 22-23 Context Place ROI | 5+/8+/10+ hits | Max hit popularity | Largest place payout | Parent Δ place rate | Freshness | Jackpot | Redundancy |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|---|---|
| promising_positive | v05-94b6f1d7c7285dba02b8b53d | エピファネイア産駒は芝・良馬場で、近年、親条件より複勝率が高い | T6_SIRE_SURFACE_GOING | LARGE | 1538 | 145 | 452 | 75.6 | 71.3 | 74.5 | 67.9 | 76.8 | 104/36/12 | 14 | 1950 | 1.2pp | CURRENT | DESCRIPTIVE | SUGGESTED_REDUNDANT |
| promising_positive | v05-d858f933b434d8dfce050607 | ロードカナロア産駒は芝・良馬場で、近年、親条件より複勝率が高い | T6_SIRE_SURFACE_GOING | LARGE | 1264 | 151 | 372 | 69.8 | 78.5 | 72.2 | 85.7 | 74.1 | 89/37/19 | 16 | 3570 | 0.5pp | CURRENT | DESCRIPTIVE | REPRESENTATIVE |
| promising_positive | v05-a43f61f7a2846337ec1775db | ドゥラメンテ産駒は芝・良馬場で、近年、親条件より複勝率が高い | T6_SIRE_SURFACE_GOING | LARGE | 998 | 91 | 250 | 92.6 | 64.2 | 62.2 | 66.6 | 75.6 | 69/23/12 | 15 | 2070 | 0.1pp | CURRENT | DESCRIPTIVE | REPRESENTATIVE |
| promising_positive | v05-f398a06ada772cdf6e11757e | ルーラーシップ産駒は芝・良馬場で、近年、親条件より複勝率が高い | T6_SIRE_SURFACE_GOING | LARGE | 834 | 52 | 175 | 72.6 | 77.8 | 95.7 | 54.2 | 66.5 | 57/30/15 | 16 | 5840 | 0.4pp | CURRENT | DESCRIPTIVE | REPRESENTATIVE |
| promising_negative | v05-ddbd88d51edb8f683244ec4b | キズナ産駒は芝・良馬場で、近年、親条件より複勝率が低い | T6_SIRE_SURFACE_GOING | LARGE | 1490 | 174 | 433 | 81.9 | 67.8 | 70.9 | 64.6 | 105.6 | 89/30/11 | 15 | 2870 | -0.2pp | DECAYING | DESCRIPTIVE | REPRESENTATIVE |
| promising_negative | v05-dc2bf5ee5aee9528370a9866 | モーリス産駒は芝・良馬場で、近年、親条件より複勝率が低い | T6_SIRE_SURFACE_GOING | LARGE | 1205 | 107 | 291 | 80.5 | 80.1 | 75.6 | 84.8 | 75.4 | 91/39/17 | 16 | 5710 | -0.0pp | CURRENT | DESCRIPTIVE | SUGGESTED_REDUNDANT |
| promising_negative | v05-0b269386500708c383a995db | ドレフォン産駒はダート・良馬場で、近年、親条件より複勝率が低い | T6_SIRE_SURFACE_GOING | LARGE | 1123 | 98 | 297 | 82.4 | 85.0 | 79.4 | 91.4 | 73.3 | 106/45/27 | 16 | 3810 | -0.1pp | CURRENT | DESCRIPTIVE | NO_SUGGESTED_CLUSTER |
| promising_negative | v05-32ebd97b461eb3ce486db7b7 | ゴールドシップ産駒は芝・良馬場で、近年、親条件より複勝率が低い | T6_SIRE_SURFACE_GOING | LARGE | 991 | 53 | 186 | 56.5 | 63.8 | 63.2 | 64.6 | 77.0 | 79/31/11 | 14 | 3400 | -1.5pp | CURRENT | DESCRIPTIVE | SUGGESTED_REDUNDANT |
| longshot_evidence | v05-94b6f1d7c7285dba02b8b53d | エピファネイア産駒は芝・良馬場で、近年、親条件より複勝率が高い | T6_SIRE_SURFACE_GOING | LARGE | 1538 | 145 | 452 | 75.6 | 71.3 | 74.5 | 67.9 | 76.8 | 104/36/12 | 14 | 1950 | 1.2pp | CURRENT | DESCRIPTIVE | SUGGESTED_REDUNDANT |
| longshot_evidence | v05-ddbd88d51edb8f683244ec4b | キズナ産駒は芝・良馬場で、近年、親条件より複勝率が低い | T6_SIRE_SURFACE_GOING | LARGE | 1490 | 174 | 433 | 81.9 | 67.8 | 70.9 | 64.6 | 105.6 | 89/30/11 | 15 | 2870 | -0.2pp | DECAYING | DESCRIPTIVE | REPRESENTATIVE |
| longshot_evidence | v05-d858f933b434d8dfce050607 | ロードカナロア産駒は芝・良馬場で、近年、親条件より複勝率が高い | T6_SIRE_SURFACE_GOING | LARGE | 1264 | 151 | 372 | 69.8 | 78.5 | 72.2 | 85.7 | 74.1 | 89/37/19 | 16 | 3570 | 0.5pp | CURRENT | DESCRIPTIVE | REPRESENTATIVE |
| longshot_evidence | v05-dc2bf5ee5aee9528370a9866 | モーリス産駒は芝・良馬場で、近年、親条件より複勝率が低い | T6_SIRE_SURFACE_GOING | LARGE | 1205 | 107 | 291 | 80.5 | 80.1 | 75.6 | 84.8 | 75.4 | 91/39/17 | 16 | 5710 | -0.0pp | CURRENT | DESCRIPTIVE | SUGGESTED_REDUNDANT |
| saturated_or_priced | v05-94b6f1d7c7285dba02b8b53d | エピファネイア産駒は芝・良馬場で、近年、親条件より複勝率が高い | T6_SIRE_SURFACE_GOING | LARGE | 1538 | 145 | 452 | 75.6 | 71.3 | 74.5 | 67.9 | 76.8 | 104/36/12 | 14 | 1950 | 1.2pp | CURRENT | DESCRIPTIVE | SUGGESTED_REDUNDANT |
| saturated_or_priced | v05-d858f933b434d8dfce050607 | ロードカナロア産駒は芝・良馬場で、近年、親条件より複勝率が高い | T6_SIRE_SURFACE_GOING | LARGE | 1264 | 151 | 372 | 69.8 | 78.5 | 72.2 | 85.7 | 74.1 | 89/37/19 | 16 | 3570 | 0.5pp | CURRENT | DESCRIPTIVE | REPRESENTATIVE |
| saturated_or_priced | v05-a43f61f7a2846337ec1775db | ドゥラメンテ産駒は芝・良馬場で、近年、親条件より複勝率が高い | T6_SIRE_SURFACE_GOING | LARGE | 998 | 91 | 250 | 92.6 | 64.2 | 62.2 | 66.6 | 75.6 | 69/23/12 | 15 | 2070 | 0.1pp | CURRENT | DESCRIPTIVE | REPRESENTATIVE |
| saturated_or_priced | v05-f398a06ada772cdf6e11757e | ルーラーシップ産駒は芝・良馬場で、近年、親条件より複勝率が高い | T6_SIRE_SURFACE_GOING | LARGE | 834 | 52 | 175 | 72.6 | 77.8 | 95.7 | 54.2 | 66.5 | 57/30/15 | 16 | 5840 | 0.4pp | CURRENT | DESCRIPTIVE | REPRESENTATIVE |
| weak_noisy | v05-002232961f6c57513e6bc88b | ダイワメジャー産駒は新潟芝2000mで、近年、親条件より複勝率が高い | T2_SIRE_COURSE | MICRO | 9 | 0 | 3 | 0.0 | 50.0 | 52.0 | 47.5 | 143.3 | 0/0/0 | 2 | 190 | 13.2pp | DECAYING | DESCRIPTIVE | NO_SUGGESTED_CLUSTER |
| weak_noisy | v05-04a3f150546fe3f65d45df39 | モーリス産駒は中京芝2200mで、近年、親条件より複勝率が低い | T2_SIRE_COURSE | MICRO | 9 | 0 | 1 | 0.0 | 33.3 | 0.0 | 60.0 | 133.6 | 0/0/0 | 4 | 300 | -12.2pp | VOLATILE | ONE_BIG_HIT | NO_SUGGESTED_CLUSTER |
| weak_noisy | v05-0504f624af17aeb01c7fdf6d | タイムパラドックス産駒は東京ダート1600mで、近年、親条件より複勝率が高い | T2_SIRE_COURSE | MICRO | 9 | 0 | 2 | 0.0 | 136.7 | 246.0 | 0.0 | 33.3 | 2/2/2 | 10 | 760 | 15.1pp | VOLATILE | DESCRIPTIVE | NO_SUGGESTED_CLUSTER |
| weak_noisy | v05-054e87832429ba2a70d529a0 | ジョーカプチーノ産駒は中山芝1200mで、近年、親条件より複勝率が低い | T2_SIRE_COURSE | MICRO | 9 | 0 | 1 | 0.0 | 25.6 | 32.9 | 0.0 | 57.5 | 0/0/0 | 4 | 230 | -9.0pp | DECAYING | ONE_BIG_HIT | NO_SUGGESTED_CLUSTER |
| redundant_cluster | v05-e75929fc846526e39d109247 | バゴ産駒は芝・良馬場で、近年、親条件より複勝率が低い | T6_SIRE_SURFACE_GOING | LARGE | 271 | 15 | 45 | 85.3 | 74.4 | 82.5 | 63.2 | 38.7 | 23/12/7 | 15 | 2350 | -1.0pp | CURRENT | DESCRIPTIVE | REPRESENTATIVE |
| redundant_cluster | v05-549c84f6146c8b81286af793 | ディープインパクト産駒は距離延長で、近年、親条件より複勝率が高い | T3_SIRE_DISTANCE_CHANGE | LARGE | 176 | 8 | 44 | 30.7 | 83.5 | 61.0 | 125.9 | 57.8 | 22/7/3 | 15 | 1950 | 1.6pp | VOLATILE | DESCRIPTIVE | REPRESENTATIVE |
| redundant_cluster | v05-00759608271ce05674ef97c1 | アイルハヴアナザー産駒はダート・良馬場で、近年、親条件より複勝率が高い | T6_SIRE_SURFACE_GOING | MEDIUM | 37 | 1 | 1 | 48.1 | 11.1 | 15.8 | 0.0 | 64.1 | 1/0/0 | 7 | 410 | 1.0pp | DECAYING | ONE_BIG_HIT | REPRESENTATIVE |
| redundant_cluster | v05-00a151f40bcb9f72bed78e52 | サクソンウォリアー産駒は芝・良馬場で、近年、親条件より複勝率が低い | T6_SIRE_SURFACE_GOING | LARGE | 88 | 10 | 27 | 90.8 | 83.5 | 85.3 | 81.6 | 42.2 | 10/2/0 | 9 | 750 | -0.6pp | CURRENT | DESCRIPTIVE | REPRESENTATIVE |

## Desired-pattern check

- Sire × turf one-turn: BLOCKED pending canonical course-topology mapping.
- Sire × distance extension: EXPRESSIBLE; uses existing canonical >=200m EXTEND buckets (EXTEND and LARGE_EXTEND aggregated).
- Sire × first dirt: BLOCKED; no true career-first flag exists in the frozen mart, and prior surface alone is not treated as first exposure.

## Failure modes and next research issues

- Ordinary course and sire-course conditions may dominate output; review the n/ROI distributions and the presentation redundancy suggestions before widening templates.
- n<5 groups remain in raw audit only; all n>=5 MICRO candidates remain, including jackpot-heavy cases.
- Semantic duplicates are suggested at Jaccard >=0.80 or exact subset, but no raw candidate is removed; threshold is advisory only.
- FIRST_DIRT, FIRST_TURF, FIRST_BLINKERS and semantic topology remain blocked due to unavailable canonical features/mapping in this input generation.
- Candidate-level overlap joins are the main runtime/memory cost; timing is in fallback audit.

## Verification

- Focused local unit tests: 9 passed; `py_compile` passed for the aggregation module and test module.
- Actions fallback audit: PASS; exact execution commit and upstream artifact digests are recorded above.

## Recommendation

PARTIAL_WITH_BLOCKED_FAMILIES. T1, sire-course T2, T3, surface-switch T4, and T6 are executed; T2 topology, T4 first-surface, and T5 are blocked. No v0.2/v0.3/v0.4 manifest, RaceNote, Newspaper, or PWA consumer was changed.
