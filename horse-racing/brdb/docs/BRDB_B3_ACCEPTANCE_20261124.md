# BRDB B3 — BMS and ordered pairing debut statistics v0.1 (2026-11-24 JST)

Status: **PASS_RESEARCH_ONLY**. B3 descriptive research complete; not prediction-safe, no production authorization. B4 is next. B1/B2 inputs, contracts and existing output bytes unchanged. Existing Z confidence remains.

## Scope and inputs

Main observed 8cda30dccf91ca52ea8c20b5120ba3e544f00967 (two commits since B1/B2 main; only JRDB JPDB and NAR files changed). Work branch parent 45cb0fc15d55c96cc9195a6ad7bbefa08686a07f. Read B1/B2 acceptance and new milestone handoff. Reused exact source of B1 classifier, guarded dated join, B2 cohort CTE and shared data_storage.query/common/dependencies, verified against Git blobs. Existing offline venv Python 3.13.5 / DuckDB 2.0.1 / PyArrow 25.0.1; dependency_report success, registry unchanged. No new parser, external data transfer or Actions.

Reverified B1/B2 inputs using its verify_input:
- Analysis v1.4 2016–2025 10/10 partitions SHA and size, manifest 39b4e94d31e5dc9507bd3aa037aa227c7c8dcefe0ddf3f744ec1e687a6965f1d.
- Warehouse 10/10 UKC partitions SHA and size, manifest semantic SHA 174eaf459f56eb1afe55bc157a2dcf0226a212bf6c00ba062ce5a3e641b2a269, audit semantic SHA a94d0a4ab45b2b861c0de47c624ff7cb773b0ef354db933688960d0cee4282c9. 10/10 original UKC archive SHA verified, duplicate horse/date and member-date mismatch zero.
- Research generation 5279af0bd8226cde, manifest/pedigree_fact/parent_relation exact SHA from B1/B2. Also extracted lineage_code_master.parquet from the existing #2223 SHA-pinned ZIP (672c6c1f78f632db60a1f7c2e8304b63e0576e51efef79f0cf473351aa8fd0d4), 83 unique codes, SHA 6263f4b239e9018e03fe6ce8333ba843b05c2eac32470369368e7be0fe7bd54b.
- Joined 481,627 rows, unique race_key/horse_no, zero future profiles. Historical UKC provider equivalence accepted as before; static relation IDs not independently as-of-certified. Do not replace with future master names.

## Contract

Exact B2 cohorts: A1 actual starters and FIRST_OBSERVED_JRA_START_CANDIDATE, both 2017–2025 (2016 only establishes history). 2025-01-01 and 2026-01-01 cutoffs, race_date strictly less than cutoff. Code 1/2 excluded; 0/3/4/5/6 actual starts; official win and top3 for codes 0/5. Same five scopes ALL/SURFACE/SURFACE_DISTANCE/SURFACE_MONTH/SURFACE_AGE. Cohorts overlap, scopes nest and lanes share horses/results. Never sum as independent evidence.

Four lanes: SIRE_ID (B2 reference), BMS_ID (guarded static individual), PARENT_ID_PAIR (ordered sire_id, bms_id; both required), LINEAGE_CODE_PAIR (ordered dated sire_line, bms_line; valid 4-digit and exact membership of official master; no fallback to Analysis or static name). Separate ID/classification domains. Reverse order never collapsed. Baseline all cohort and lane-resolved baseline; paired marginal rates calculated for each parent/classification within SAME pair-eligible cohort+scope+dimension, including the pair itself; NOT independent support, causal interaction or demonstrated nick. Counts of starts, unique horses/races, normal finishers, wins/top3, rate and max history date. LOW_SAMPLE N<30; absence of resolved groups represented by NO_RESOLVED_GROUP null keys, zero starts and null group rate. No target-level NO_SAMPLE certification until B5. False prediction_safe / production_authorized throughout.

## Real results, cutoff 2026-01-01

| Cohort | All starts | Sire ID | BMS ID | Both IDs | Both codes |
|---|---:|---:|---:|---:|---:|
| A1 actual starters | 35836 | 26048 | 16184 | 11250 | 35836 |
| First observed JRA candidate | 42348 | 30761 | 18881 | 13153 | 42334 |

ID overlap A1 both 11250 / sire-only 14798 / BMS-only 4934 / neither 4854; first candidate both 13153 / sire-only 17608 / BMS-only 5728 / neither 5859. Sum per cohort equals all starts; no inferred IDs. All 14 missing code-pair rows are missing dated UKC.

| Cohort | Lane | ALL unique groups | ALL groups N<30 | All five scopes groups | All five scopes N<30 |
|---|---|---:|---:|---:|---:|
| A1 | SIRE_ID | 355 | 226 | 7581 | 6672 |
| A1 | BMS_ID | 220 | 160 | 4246 | 3703 |
| A1 | PARENT_ID_PAIR | 4087 | 4058 | 30849 | 30782 |
| A1 | LINEAGE_CODE_PAIR | 525 | 417 | 9055 | 8137 |
| First observed | SIRE_ID | 372 | 234 | 8863 | 7818 |
| First observed | BMS_ID | 224 | 161 | 4859 | 4265 |
| First observed | PARENT_ID_PAIR | 4483 | 4446 | 35487 | 35403 |
| First observed | LINEAGE_CODE_PAIR | 576 | 457 | 10667 | 9590 |

B3 new three lanes 95,163 positive-N observations (91,880 low-N); sire reference 16,444; five no-resolved-group cells total, four in new lanes and one sire. 2025-01-01 cutoff three new lanes 85,779 positive-N groups (82,853 low-N). Counts not independent, not unique horses. Individual pair extremely sparse: 99.77% low-N across all scopes; 29/4087 A1 and 37/4483 first-observed ALL pairs have N>=30. Lineage pair is broader but not individual identity or evidence of predictive superiority.

All-scope resolved top3: A1 all 8013/35836, sire 5827/26048, BMS 3451/16184, pair 2426/11250, line 8013/35836. First-observed all 8533/42348, sire 6192/30761, BMS 3639/18881, pair 2560/13153, line 8531/42334. Differences in resolved populations are selection/composition differences; not predictive value. No rank/marks/recommendation generated.

## Validation and artifacts

B2 regression re-executed exact source for both cutoffs and CSV SHA matched prior accepted artifacts; B3 sire reference identical per group including raw counts, denominators and max dates (two-way EXCEPT ALL). Per-scope reconciliation of all lane resolved starts/wins/top3; no duplicate group keys, future dates, invalid count bounds or null pair marginals. Two full independent runs plus repeated queries per cutoff yielded byte-identical CSV and receipt. Focused synthetic B3 5/5 PASS (ordered pairing / same-eligible marginal; missing, invalid and future code; cutoff and abnormal/nonstarter/cohort differences; low-N and overlapping scopes; deterministic); B1/B2 regressions 4/4 PASS.

Sources (SHA256):
- research/brdb_b3_debut_statistics_v0_1.sql eee017a885d66949efc7466efb28d99959426a97debf8e57a38a766687c587b1
- research/run_brdb_b3_local.py d0cf57fc967a1ab98436a339ca10cc32c97bcbbfd2e202724fe6e67005d866b6
- research/test_brdb_b3_research.py cda3aded11d669a4d4ab0f78faef71d9027ee34585bd6ac68faead825eee063c

Private Library /BRDB/Development_B3_20261124/ contains sources, receipt and compressed stats. Readback raw gzip SHA and decompressed CSV SHA both verified.
- b3_receipt.json 543cb9c60879def29395309690283fb9adc64b722adaf30081a404fe4e19b11d
- PRIVATE_b3_stats_2025-01-01.csv.gz 2e79e33ca60a5d5faf10ce57935084ecae8f62f84a7c2ca71abe62d925ffbda2 (CSV ee1aa77792cfab278234a16e51449ebfee98b19d71ae06146a26c1a37d6b3508)
- PRIVATE_b3_stats_2026-01-01.csv.gz df3306b743361a341dcaf2a0f09beecac664b2687c7d7df010eae1e6e0dc798a (CSV a2715a23d10c967c46634bf19c790e7c2891fe1efc724c8892090deb5702f3b0)

Replay using B1/B2 private input layout plus pedigree/lineage_code_master.parquet:
    PYTHONPATH=tools/data-storage python horse-racing/brdb/research/run_brdb_b3_local.py --input-root /private/input --output-dir /private/output
    PYTHONPATH=tools/data-storage:horse-racing/brdb/research python -m unittest test_brdb_b3_research test_brdb_b1_b2_research -v

B4: older siblings/maternal relatives first-start and early performance, canonical relation and pre-target date, explicit unresolved counts, overlapping relative paths not additive. B5 whole-field research candidate, missing/NO_SAMPLE; B7 comparative predictive evidence. No production publication or changes to CURRENT, RaceNote, PWA, frozen contracts. No licensed records or private identity-level statistics in Git.
