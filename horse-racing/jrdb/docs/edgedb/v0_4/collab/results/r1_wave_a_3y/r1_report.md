# R1 Wave A Full 3y — Compact Research Report

Status: **DONE**  
Instruction commit: `8259b357fcf72bede30ca6723dee7ddc6a9a9bbc`  
Execution code base: `21f7c58116bbc8ee75f1d05ccfebb60ae66f0821` (preflight working-tree files were present as local changes)  
Production impact: NONE  
No market/popularity-conditioned population generation was used.

## Frozen request and input integrity

- Window: inclusive `2022-12-28 .. 2025-12-28`; `as_of_date=2025-12-28`; discovery years=3.
- Feature Mart run `36116777782`, artifact `jrdb-edge-feature-mart-parquet-36116777782`, generation `edge_feature_mart_v0_2_g20260925_pq1`: 781,161 rows; SHA-256 `82e6550639210eea6cf1fc1ac374ee8b6fc07115214fe75ea6e1bb704d3751f6.
- Stage B run `36262821119`, 47,371 templates; catalog SHA-256 `cf70098156283e42df49cc61d4988f1d2b578a4dbf4135c8121eb81262d5d2ba.
- Artifact ZIP hashes matched R1 preflight pins. No rebuilt/substitute inputs were used.

## Planner identity

- Selected `1106` templates in `6` shards; plan SHA-256 `de823224c0f10690232835b35557517c474377734b2df347ca3a9a08daa3ded8`.
- By lane: `{'PEDIGREE_BASELINE': 456, 'PEDIGREE_INTERACTION': 64, 'TRANSITION_PRIORITY': 586}`; by depth: `{'2': 123, '3': 983}`.
- Recomputed selected set and shard assignment exactly matched preflight plan: **True**.

## Phase A — C1 shards and merge

| Shard | Lane/depth | Templates | Terminal groups | Admitted before cap | Candidates | Seconds | Peak RSS MiB | Output bytes | Audit |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| pedigree_baseline-d2-s000 | PEDIGREE_BASELINE/D2 | 60 | 26454 | 5699 | 3503 | 11.149 | 599.3 | 395684 | PASS |
| pedigree_baseline-d3-s000 | PEDIGREE_BASELINE/D3 | 396 | 289024 | 69167 | 31211 | 28.413 | 693.0 | 3177646 | PASS |
| pedigree_interaction-d2-s000 | PEDIGREE_INTERACTION/D2 | 4 | 5035 | 1429 | 350 | 2.545 | 584.5 | 53700 | PASS |
| pedigree_interaction-d3-s000 | PEDIGREE_INTERACTION/D3 | 60 | 85235 | 23557 | 5948 | 10.586 | 621.8 | 569267 | PASS |
| transition_priority-d2-s000 | TRANSITION_PRIORITY/D2 | 59 | 10466 | 2086 | 932 | 3.080 | 596.9 | 120543 | PASS |
| transition_priority-d3-s000 | TRANSITION_PRIORITY/D3 | 527 | 334365 | 75768 | 26741 | 33.654 | 672.7 | 2627570 | PASS |

Merge: PASS; `68685` candidates; `0` duplicate candidate IDs; `14` selected templates yielded zero candidates; `490` templates hit 100-row cap. Total shard evaluation 89.428s; maximum single-shard RSS 693.0 MiB.

### C1 descriptive distributions by lane × depth

Values shown as min / p10 / median / p90 / max; support and ROI are descriptive, not gates.

| Lane/depth | Templates | Terminal groups | Candidates (rate/group) | n | wins | places | win ROI | place ROI | top1 win share | jackpot flags |
|---|---:|---:|---:|---:|---|---|---|---|---|---:|
| PEDIGREE_BASELINE:D2 | 60 | 26454 | 3503 (0.1324) | 24.00/27.00/51.00/201.80/1093.00 | 0.00/2.00/5.00/16.00/117.00 | 2.00/5.00/12.00/45.00/302.00 | 0.00/36.32/157.25/323.15/1371.89 | 17.50/64.05/105.09/173.44/562.86 | 0.11/0.30/0.60/0.94/1.00 | 1228 (35.1%) |
| PEDIGREE_BASELINE:D3 | 396 | 289024 | 31211 (0.1080) | 22.00/24.00/43.00/151.00/2487.00 | 0.00/2.00/4.00/13.00/219.00 | 2.00/5.00/11.00/35.00/602.00 | 0.00/40.49/183.98/387.39/1634.40 | 19.37/66.00/108.52/197.71/884.09 | 0.07/0.34/0.64/0.96/1.00 | 12890 (41.3%) |
| PEDIGREE_INTERACTION:D2 | 4 | 5035 | 350 (0.0695) | 18.00/19.00/28.00/87.10/511.00 | 0.00/1.00/3.00/8.00/46.00 | 2.00/3.00/8.00/22.00/124.00 | 0.00/49.42/259.48/568.88/1309.52 | 27.86/75.46/126.95/241.16/431.29 | 0.12/0.39/0.72/1.00/1.00 | 176 (50.3%) |
| PEDIGREE_INTERACTION:D3 | 60 | 85235 | 5948 (0.0698) | 16.00/17.00/25.00/76.00/781.00 | 0.00/1.00/3.00/7.00/90.00 | 2.00/3.00/7.00/18.00/224.00 | 0.00/40.61/261.47/555.29/2255.00 | 23.12/72.41/126.67/258.93/646.00 | 0.11/0.43/0.76/1.00/1.00 | 3266 (54.9%) |
| TRANSITION_PRIORITY:D2 | 59 | 10466 | 932 (0.0891) | 12.00/14.10/36.00/163.90/1138.00 | 0.00/1.00/3.00/14.00/80.00 | 2.00/3.00/8.00/36.00/229.00 | 0.00/24.65/186.83/425.17/1946.92 | 22.22/65.77/111.74/231.18/734.44 | 0.10/0.33/0.70/0.99/1.00 | 428 (45.9%) |
| TRANSITION_PRIORITY:D3 | 527 | 334365 | 26741 (0.0800) | 10.00/12.00/30.00/181.00/3218.00 | 0.00/1.00/3.00/14.00/286.00 | 2.00/3.00/7.00/38.00/790.00 | 0.00/30.00/180.00/537.00/3474.00 | 19.38/67.65/116.10/258.33/1729.09 | 0.07/0.34/0.71/1.00/1.00 | 12956 (48.4%) |

Recent support/ROI distributions are retained in `r1_summary.json` for n/ROI at 365d, 730d, and 1095d. Candidate counts by family: `{"PEDIGREE_CROSS": 41012, "PEDIGREE_TRANSITION_CROSS": 18531, "TRANSITION_CROSS": 9142}`.

## Phases C–F — C2A, exact metrics, incrementality, temporal evidence

- C2A shortlist: `17807` of `68685` C1 candidates; routes `{"ESTABLISHED_CURRENT": 17807}`. `EMERGING_HIGH_ORDER` contributed zero rows as expected for depths 2–3.
- Child-parent map rows: `52171`; unique parent requests `14129`; total unique exact requests `30733`.
- C2B: `30733/30733` exact results, unique IDs `30733`, missing `0`, extra `0`, duplicate results `0`; one sequential shard PASS; zero missing value branches.
- C2B window `2022-12-28 .. 2025-12-28`; feature hash matches C1.
- Execution note: the runtime lacked DuckDB and package-network access. C2A’s frozen SQL predicates were applied deterministically with PyArrow; the exact C2B evaluator ran unchanged. Parent join/summary used a deterministic Python join over unique exact metric IDs. Details and provenance are retained in the summary; broad candidate/metric artifacts remain outside Git.
- Incrementality labels are research-only. ROI deltas require strict improvement (>0) and nonnegative hit-rate delta against every immediate parent; a successful lane must retain break-even ROI (>=100) after top-three exclusion and avoid the frozen 70% top-one dependence flag. Where no arbitrary “meaningful” ROI delta exists, raw deltas are preserved and no extra cutoff was introduced.

### Label counts

| Label | Count |
|---|---:|
| INCREMENTAL_CANDIDATE | 367 |
| JACKPOT_DEPENDENT | 17350 |
| MIXED_PARENT_INCREMENTALITY | 90 |

Family counts (C1/C2 and incrementality labels):

```json
{
  "PEDIGREE_CROSS": {
    "c1_candidates": 41012,
    "c2_shortlist": 11963,
    "incrementality_labels": {
      "INCREMENTAL_CANDIDATE": 266,
      "JACKPOT_DEPENDENT": 11629,
      "MIXED_PARENT_INCREMENTALITY": 68
    }
  },
  "PEDIGREE_TRANSITION_CROSS": {
    "c1_candidates": 18531,
    "c2_shortlist": 4204,
    "incrementality_labels": {
      "INCREMENTAL_CANDIDATE": 81,
      "JACKPOT_DEPENDENT": 4106,
      "MIXED_PARENT_INCREMENTALITY": 17
    }
  },
  "TRANSITION_CROSS": {
    "c1_candidates": 9142,
    "c2_shortlist": 1640,
    "incrementality_labels": {
      "INCREMENTAL_CANDIDATE": 20,
      "JACKPOT_DEPENDENT": 1615,
      "MIXED_PARENT_INCREMENTALITY": 5
    }
  }
}
```

Temporal warning counts: `{"730D_DIRECTION_CONTRADICTS_FULL_3Y": 3402, "NO_RECENT_365D_SUPPORT": 66, "TOP3_EXCLUSION_REMOVES_BOTH_LANES": 17350, "VALUE_CONFINED_TO_ONE_YEAR": 226}`.

## Bounded review shortlist

- `100` rows (limit 100); order: incremental candidates first, non-jackpot first, then stronger minimum parent ROI delta, support, and stable candidate ID; mixed-parent rows fill remaining slots. Redundant/jackpot-dependent rows are not used to pad the file.
- Full immediate-parent comparisons (each parent condition, removed feature, exact metrics, ROI/rate deltas, and support ratio) are preserved per shortlisted child in `parent_comparisons_json`.
- Detailed join for all C2 candidates remains a temporary audit artifact; Git includes only the bounded shortlist and compact summary/report.

### Most research-relevant examples

| Candidate | Lane/family | Depth | Conditions | Label | n; win/place ROI | Ex-top3 win/place ROI | Parent count | weakest parent removed feature | temporal warnings |
|---|---|---:|---|---|---|---|---:|---|---|
| `v04c_96c98f51aff656152611257f` | PEDIGREE_BASELINE/PEDIGREE_CROSS | 2 | `frame_zone=INNER AND sire_name=アイファーソング` | INCREMENTAL_CANDIDATE | 37; 1371.89/275.68 | 192.16/105.41 | 2 | frame_zone | none |
| `v04c_fd77e97c82b00ce0eab5c710` | TRANSITION_PRIORITY/PEDIGREE_TRANSITION_CROSS | 3 | `venue_code=03 AND sire_name=ルーラーシップ AND distance_change_bucket=SHORTEN` | INCREMENTAL_CANDIDATE | 20; 920.00/359.00 | 139.50/82.00 | 3 | distance_change_bucket | none |
| `v04c_a77c679eaf6f766c86d15e23` | TRANSITION_PRIORITY/PEDIGREE_TRANSITION_CROSS | 3 | `sex_code=3 AND sire_line_code=1207 AND frame_transition=OUTER->OUTER` | INCREMENTAL_CANDIDATE | 50; 879.80/277.20 | 163.00/104.60 | 3 | sire_line_code | none |
| `v04c_61d3d9cb46c6502e0d5a88e1` | TRANSITION_PRIORITY/PEDIGREE_TRANSITION_CROSS | 3 | `distance_m=2000 AND sire_name=マジェスティックウォリアー AND surface_transition=2->2` | INCREMENTAL_CANDIDATE | 16; 779.38/202.50 | 127.50/76.88 | 3 | surface_transition | none |
| `v04c_f424e824a6c19c7e292edf00` | TRANSITION_PRIORITY/PEDIGREE_TRANSITION_CROSS | 3 | `venue_code=04 AND sire_name=レッドファルクス AND surface_transition=2->2` | INCREMENTAL_CANDIDATE | 35; 1000.29/224.29 | 144.00/56.86 | 3 | surface_transition | none |
| `v04c_eec892b9af31d94cf41bd493` | PEDIGREE_BASELINE/PEDIGREE_CROSS | 3 | `venue_code=05 AND frame_zone=OUTER AND sire_name=カルフォルニアクローム` | INCREMENTAL_CANDIDATE | 36; 715.28/407.22 | 168.33/113.61 | 3 | frame_zone | none |
| `v04c_511b1225039ffe49d0a9d3b3` | TRANSITION_PRIORITY/PEDIGREE_TRANSITION_CROSS | 3 | `broodmare_sire_line_code=1311 AND prev1_venue_code=06 AND frame_transition=OUTER->INNER` | INCREMENTAL_CANDIDATE | 55; 662.73/155.27 | 182.55/90.73 | 3 | prev1_venue_code | none |
| `v04c_49c53dbc7f757bab50bb64a0` | PEDIGREE_BASELINE/PEDIGREE_CROSS | 3 | `venue_code=09 AND running_style_code=2 AND broodmare_sire_name=ルーラーシップ` | INCREMENTAL_CANDIDATE | 25; 795.20/147.20 | 135.20/69.20 | 3 | running_style_code | none |
| `v04c_07f74c1478c27af4c37d0552` | PEDIGREE_INTERACTION/PEDIGREE_CROSS | 3 | `frame_zone=INNER AND sire_name=アイファーソング AND broodmare_sire_line_code=1206` | INCREMENTAL_CANDIDATE | 19; 1860.53/404.74 | 103.68/118.95 | 3 | broodmare_sire_line_code | none |
| `v04c_28e2a56155dceffc1d477dde` | PEDIGREE_INTERACTION/PEDIGREE_CROSS | 3 | `running_style_code=0 AND sire_name=グレーターロンドン AND broodmare_sire_line_code=1503` | INCREMENTAL_CANDIDATE | 22; 873.64/277.27 | 104.55/85.45 | 3 | broodmare_sire_line_code | none |
| `v04c_bd06a9843e4f3746502fe199` | PEDIGREE_BASELINE/PEDIGREE_CROSS | 3 | `distance_m=1200 AND sex_code=3 AND broodmare_sire_name=クロフネ` | INCREMENTAL_CANDIDATE | 28; 546.79/220.00 | 141.43/87.50 | 3 | sex_code | none |
| `v04c_6ebf2a2dd40b75aa23105a65` | PEDIGREE_BASELINE/PEDIGREE_CROSS | 3 | `venue_code=04 AND surface_code=2 AND sire_name=レッドファルクス` | INCREMENTAL_CANDIDATE | 39; 897.69/201.28 | 129.23/51.03 | 3 | surface_code | none |
| `v04c_cfaead5fc4ee988782c4cc44` | TRANSITION_PRIORITY/PEDIGREE_TRANSITION_CROSS | 3 | `race_condition_code=05 AND broodmare_sire_name=ハービンジャー AND frame_transition=MIDDLE->OUTER` | INCREMENTAL_CANDIDATE | 47; 614.89/170.85 | 105.11/85.32 | 3 | race_condition_code | none |
| `v04c_d244b3910ab5d35982d95930` | PEDIGREE_BASELINE/PEDIGREE_CROSS | 2 | `venue_code=04 AND sire_name=レッドファルクス` | INCREMENTAL_CANDIDATE | 84; 478.21/110.12 | 121.43/40.36 | 2 | venue_code | none |
| `v04c_21fca8a3edc1d4865c8607a8` | PEDIGREE_BASELINE/PEDIGREE_CROSS | 3 | `running_style_code=2 AND sire_name=サートゥルナーリア AND prev1_venue_code=08` | INCREMENTAL_CANDIDATE | 33; 572.73/144.24 | 119.39/62.42 | 3 | running_style_code | none |
| `v04c_d9e1ef34711ce08121781bd2` | TRANSITION_PRIORITY/PEDIGREE_TRANSITION_CROSS | 3 | `frame_zone=INNER AND sire_name=アイファーソング AND surface_transition=2->2` | INCREMENTAL_CANDIDATE | 29; 1750.34/351.72 | 245.17/134.48 | 3 | surface_transition | none |
| `v04c_fdc7a5f83146f32fb11f5238` | PEDIGREE_BASELINE/PEDIGREE_CROSS | 2 | `race_condition_code=OP AND sire_name=ファインニードル` | INCREMENTAL_CANDIDATE | 59; 482.03/121.86 | 176.95/60.34 | 2 | race_condition_code | none |
| `v04c_09cb52bbd3acc670f215f034` | PEDIGREE_INTERACTION/PEDIGREE_CROSS | 3 | `sire_line_code=1503 AND broodmare_sire_name=クロフネ AND prev1_venue_code=01` | INCREMENTAL_CANDIDATE | 31; 488.71/140.65 | 100.65/62.58 | 3 | sire_line_code | none |
| `v04c_5d2415f3fb5c51a5efed87ca` | PEDIGREE_BASELINE/PEDIGREE_CROSS | 3 | `venue_code=09 AND frame_zone=OUTER AND broodmare_sire_name=ルーラーシップ` | INCREMENTAL_CANDIDATE | 28; 663.57/115.71 | 117.14/53.21 | 3 | frame_zone | 730D_DIRECTION_CONTRADICTS_FULL_3Y |
| `v04c_1ed24612a32dac5e0d5176d9` | TRANSITION_PRIORITY/PEDIGREE_TRANSITION_CROSS | 3 | `condition_class_code=9 AND sire_name=リオンディーズ AND frame_transition=MIDDLE->OUTER` | INCREMENTAL_CANDIDATE | 14; 435.00/170.00 | 109.29/70.71 | 3 | frame_transition | none |

These are research review examples, not a production ranking. Each row’s full immediate-parent metrics and strongest/weakest parent comparison are in the CSV JSON columns.

## R3 recommendation

`MIXED_BRANCH_DECISION` — review each family separately before expansion. `PEDIGREE_CROSS` has the largest absolute count of all-parent incremental candidates (266 of 11,963 C2A rows); `PEDIGREE_TRANSITION_CROSS` contributes 81 of 4,204; `TRANSITION_CROSS` contributes 20 of 1,640. The high count of top-three-sensitive candidates and temporal warnings means these branches do not yet support one uniform expansion decision. Use the bounded records to decide whether only selected families merit a frozen 5-year extension or controlled depth-4 follow-up; do not launch either expansion here. No thresholds were tuned.

## GitHub state / pending merge

- Open PRs at task preflight: none returned by the GitHub connector. PR #1799 (`docs/codex-cloud-operating-guide-20261005`, head `170afef30e773572e0abb9b631355a16735e8d98`) was confirmed merged as `c8628f4c1dd571d6eea3436da21262f5dc53c171`.
- This result is now in open PR #1800 on `research/jrdb-edge-v04-r1-wave-a-3y-20261005`, content commit `395c5a1d704e07c7a0cc37509fe7cbba8d5aefdf`; it must merge before main-based downstream tasks can consume it. GitHub reported `mergeable=false` at creation time.

## Files and scope

- `r1_summary.json`, `r1_report.md`, `shortlist.csv` are the only machine-readable review outputs intended for Git.
- Broad C1 candidate Parquet, C2 exact metrics, and complete join JSONL are excluded from Git.
- Production serving, market-conditioned generation, SHADOW publication, 5-year aggregation, and depth-4+ expansion were not run or changed.
- No threshold was tuned.
