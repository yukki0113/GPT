# BRDB B5 — debut whole-field review v0.1 candidate (2026-11-24 JST)

Status: **PASS_RESEARCH_ONLY** for the 4-race real PACI proof with frozen 2016–2025 result inputs. Not prediction-safe or production-authorized. This is an independent non-scoring candidate, not the existing newspaper/RaceNote contract or a B7 prediction result. B6 is next.

## Inputs and boundaries

Main observed f757c45380813dcbee2a3f24e0376b5e45191205; development branch parent e2ff7dbc468ce4cd2282590d3cf92674d14f07a5. PACI261101.zip from canonical private Drive PACI folder, 343989 bytes, SHA256 1d9a098c35ae167ce22bcfc9de186088c9a0331a7c009ecf5028c1e8472aedb6. Local canonical JRDB BAC/KYI/UKC methods, archive reader and helpers transcribed unchanged from jrdb_raw.py Git blob e2c7e982df684cd96fb87f81f0127b6567cabd64 (relevant source excerpt length 14370 characters and FNV-1a 1039103296 matched connector; local excerpt SHA256 6f59af874cb140eb5ac564f67d98d19e1406cf9943a7f530ead1449b1ebe64d8; not full module byte certification). Full jrdb_ukc.py blob 15cc607e012085186c9cbd64d41c913acb43cf98 and brdb_parent_relation.py blob 8bc50225ccdaacf9d2618d40740d229e841db77c matched exact local Git blob hashes. No new fixed-width parsing. Committed runner imports canonical modules from repository layout; local test only used the relevant verified Reader source subset.

B3.setup / B1.verify_input reverify all ten Analysis and UKC year partitions and accepted immutable pedigree/lineage master hashes; B3 cohort SQL and B4 path/early SQL and runner are hash-pinned and reused unchanged. Existing offline runtime DuckDB 2.0.1 / PyArrow 25.0.1. Analysis manifest 39b4e94d31e5dc9507bd3aa037aa227c7c8dcefe0ddf3f744ec1e687a6965f1d; Warehouse manifest 174eaf459f56eb1afe55bc157a2dcf0226a212bf6c00ba062ce5a3e641b2a269; pedigree generation 5279af0bd8226cde as B4. Historical outcome cutoff exclusive 2026-01-01; 2016 establishes history, B2/B3 population 2017–2025. **2026 history gap explicitly true.** This is a bounded research proof; not a comprehensive as-of 2026 result store or lifetime debut certification. No target SED, finish, odds, rank or marks used. No target post-race result used for classification. Existing Z unchanged.

## Contract and integration

A1 BAC race class and KYI declared field identity (race_key, horse_no, 8-digit horse_id) validated; no omission for missing blood data. Only date-matched PACI archive with strict BAC/KYI field-size agreement. UKC joined by canonical horse_id; missing/invalid/conflicting/future profile unavailable, not discarded. Age derived from birth year and target year. Individual prior references from KYI and frozen classified history separate from A1 race class. 54 NO_PRIOR_START_OBSERVED_HISTORY_INCOMPLETE, 1 PRIOR_HISTORY_UNRESOLVED (2026 prior reference outside frozen history); no lifetime-first-start claim.

Target-only parent resolution via canonical HorseMasterIndex / resolve_first_generation, empty alias index; candidate uniqueness, expected sex, exact name+birth-year candidate and independent BMS/lineage guards, official code, distinct ID and older birth checks. Latest observed profile date <= target date; same-day PACI precedence. New target edges only in temporary overlay; no change to persistent parent master, historical statistics, CURRENT. Historical relatives use B4 exact dam graph and profile/date guards, first three actual starts before condition filtering; only results < frozen cutoff. No inferred relationship by horse name alone. Static historical relation timing remains AS_OF_UNVERIFIED.

Each horse has exactly 40 population cells: two B2 cohorts x four B3 lanes x five B2 scopes. Explicit evidence_id, matching identity key and dimension, starts/wins/top3, distinct horses/races, baseline and resolved denominator, pair marginals, max history date. Unavailable source = null group counts/rate; known key but no matched sample = zero counts and null rate. LOW_SAMPLE N<30; DESCRIPTIVE otherwise, not an aptitude judgment. Relative evidence separate with exact target/relative identity, path/relationship, scope, first/early history and result keys, distinct history statuses; no pooling to win probability. Cohorts/scopes/lanes/related horses overlap, not independent. Strict Draft 2020-12 candidate schema with closed objects, research flags and semantic validator. No score, probability prediction, marks, ranking, recommendation or production promotion.

## Real field results

| Race | Surface/distance | Declared | Reviewed |
|---|---|---:|---:|
| 05264b04 Tokyo 4R | turf 1600 | 14 | 14 |
| 05264b05 Tokyo 5R | turf 2000 | 8 | 8 |
| 08264b05 Kyoto 5R | turf 1600 | 17 | 17 |
| 08264b06 Kyoto 6R | dirt 1800 | 16 | 16 |
| Total | | 55 | 55 |

55/55 PACI UKC profiles; sire IDs 46, BMS IDs 27, both IDs 24, lineage pair 55, dam 42 (12 no candidate, 1 conflict), granddam 20. All declared runners retained. No current-result or future-result leakage detected.

| Lane | DESCRIPTIVE | LOW_SAMPLE | NO_SAMPLE | SOURCE_UNAVAILABLE |
|---|---:|---:|---:|---:|
| SIRE_ID | 271 | 113 | 76 | 90 |
| BMS_ID | 185 | 55 | 30 | 280 |
| PARENT_ID_PAIR | 14 | 86 | 140 | 310 |
| LINEAGE_CODE_PAIR | 490 | 52 | 8 | 0 |
| Total | 960 | 306 | 254 | 680 |

2,200 population cells; 1,266 positive-N. B4 relative audit: 39 targets with confirmed relatives, 38 with eligible first history, 37 with at least one relative's full three early starts; 13 source unavailable, 3 no confirmed relative, 1 no eligible first history. 279 target-relative pairs (1 full sibling, 86 maternal half siblings, 46 same dam sire unresolved, 146 maternal aunt/uncle), 173 with eligible first history, 34 first history unresolved, 72 no prior observed start within frozen window. 147 pairs complete early window. Five scopes => 1,395 relative cells: 476 LOW_SAMPLE, 389 NO_SAMPLE, 170 FIRST_START_UNRESOLVED, 360 NO_PRIOR_OBSERVED_START. No independent support or prediction claim.

## Validation and reproducibility

B5 synthetic tests 6/6, real-field validation/negative tests 6/6, B1–B4 regression 15/15 PASS (27/27). Rejected duplicate/missing identity, invalid/non-A1 entry, future/conflicting profile, wrong dimension/evidence ID, future outcome, wrong flags and incorrect zero/low-N status. Draft202012 schema both runs zero errors with date format checker; injected score rejected. Two independent local runs byte-identical review and receipt. Library readback both outputs byte-identical. Source files stored in research/ and schema/; Git blob identity verified before commit.

SHA256:
- run_brdb_b5_local.py 731ac75c2dca9f2664b305aed895f1055e9af95017136c9edcb786634d1d3041
- test_brdb_b5_research.py 71218bfc84b388f8b24655cb43e8ae70b3c17421c4b718feedfc1aeaa4502cad
- schema/brdb_debut_review_v0_1_candidate.schema.json 8444963bcb3634e77619876e04fb6fdbeb48ad1fdcb5fbeddaffb85234611948

Private Library /BRDB/Development_B5_20261124/:
- PRIVATE_b5_review.json 6a05d0cc69fcf1f2db899a9025904599e3c54c9718c8abd20e2516436087e00d
- b5_receipt.json af901a7ae8b79154a49ed26ecd99de2e450c0b6f82bbee802ed658934f6900f8
- tests.log and source/schema copies.

Replay with B3 private input layout, canonical JRDB source from main and PACI SHA:
    PYTHONPATH=tools/data-storage python horse-racing/brdb/research/run_brdb_b5_local.py --input-root /private/input --paci /private/PACI261101.zip --paci-sha256 1d9a098c35ae167ce22bcfc9de186088c9a0331a7c009ecf5028c1e8472aedb6 --race-key 05264b04 --race-key 05264b05 --race-key 08264b05 --race-key 08264b06 --output-dir /private/output
    BRDB_B5_REVIEW=/private/output/PRIVATE_b5_review.json PYTHONPATH=tools/data-storage:horse-racing/brdb/research python -m unittest test_brdb_b5_research test_brdb_b4_research test_brdb_b3_research test_brdb_b1_b2_research -v

Use Draft202012Validator with FormatChecker on candidate JSON in environment with jsonschema. No private result rows, raw archive or horse-level outputs committed. No merge/publish.

Next B6: verify actual current JPDB contract, preserve separate lanes, strict race/horse keys, missingness and dependence. B7 separate pre-fixed time-split predictive comparison; 2026 historical gap and original delivery availability limitations must be addressed for any appropriate prospective/performance evaluation. Existing RaceNote Z, PWA, frozen contracts and CURRENT unchanged.
