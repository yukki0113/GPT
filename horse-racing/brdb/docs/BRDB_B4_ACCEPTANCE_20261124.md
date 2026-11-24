# BRDB B4 — older siblings and maternal relatives: debut / early-start evidence v0.1 (2026-11-24 JST)

Status: **PASS_RESEARCH_ONLY** for the bounded historical cohort and exact canonical relation coverage. Not production-authorized, prediction-safe, or a global lifetime-first-start certification. B5 remains a separate whole-field pre-race candidate contract and real PACI acceptance. No frozen BRDB/RaceNote/PWA/current data changed.

## Scope / provenance

Main observed 151ccbf2c2a40f1d3f0ffa0c3e6e2f4ff21b4efe. The change from B3's main is BRDB README and JRDB JPDB/RaceNote independent evidence contract work, not B1–B3 research input changes. Existing B4 branch parent 95f34adba1b4f3f9f85bfe946a88060202564e71. Read handoff, basic design, B3 acceptance, existing relatives v0.1 and historical relations v0.4. Extend the existing guarded canonical dam graph policy to historical first/early starts; do not change the existing 2026 relatives consumer. Exact B3 setup / B2 cohort / B1 classifier and date-guarded join reused.

- Analysis v1.4 manifest SHA256 39b4e94d31e5dc9507bd3aa037aa227c7c8dcefe0ddf3f744ec1e687a6965f1d; 2016–2025 10/10 partitions reverified, 481627 entries. Unknown actual-start status and same-horse same-day duplicates 0.
- Warehouse current accepted 2010–2025 g20261118_bacfix semantic manifest SHA 174eaf459f56eb1afe55bc157a2dcf0226a212bf6c00ba062ce5a3e641b2a269; 10/10 UKC year files, original archive SHAs, unique horse/date and member-date validation as in B3.
- Research generation 5279af0bd8226cde; manifest 7efb70ab370cafd18d39eb20ea4fc2bb32490653364a58b44b1382cf9fa5f16c, pedigree_fact 1e7574f78703d79d8d83797f9e350a8927b728fc68c659cf5d340ee0f79b3536, parent_relation c90482851f91b8f2d99ec88407f4246471d10b38f18163464f88760cb197ff85.
- Reused pinned Python 3.13.5 / DuckDB 2.0.1 / PyArrow 25.0.1 runtime, dependency_report success. No new parser or remote computation.

## Research contract

Target cohort is the exact B2 A1 actual starters and FIRST_OBSERVED_JRA_START_CANDIDATE, 2017–2025, cutoff 2026-01-01. 2016 only contributes history / left-edge assessment. Union deduplicates exact target race_key/horse_no/horse_id/date; both cohort memberships retained. In this actual window A1 is entirely contained in first candidate, 42,348 distinct targets. Do not add cohort totals.

Use only existing RESOLVED_EXACT parent_master edges with candidate_count=1, valid 8-digit IDs and accepted role guard. Recheck child/parent name, birth year, sex and independent BMS name/year/lineage for dam edges, sire name/year/lineage for sire edges, using observed profiles not later than target date. Prefer dated UKC on equal dates; ancestor/relative master profiles allowed only when profile_data_date <= target_date; target requires dated UKC matching B1. A resolved ID from the static graph is still AS_OF_UNVERIFIED. No new name-based or alias relation inference; existing 439 RESOLVED_ALIAS dam edges not adopted in this exact-only version, recorded as scope limitation. Preserve user accepted annual UKC/KYI provider equivalence; do not recertify original delivery bytes or claim independent historical graph availability.

Paths: same dam older siblings and maternal aunt/uncle via dam's dam, both born strictly before target. Full sibling only if both sire identities agree; maternal half only if both guarded sire IDs differ; otherwise SAME_DAM_SIRE_UNVERIFIED. Missing target/ancestor/profile, not older, and failed guard explicitly distinguished. Unavailable is not proof of absent kin. Candidate/rejected paths stored only as private audit; only RESOLVED paths enter evidence. No self relation. One target-relative pair for history, preserve all path labels/counts; no independent support claim.

Early window is first three actual observed JRA starts, determined before condition filtering, only when B1 first observed start candidate is confirmed in the available data; no lifetime-first certification. Exclude 1/2 cancellation/exclusion; 0/3/4/5/6 actual starts; win/top3 only codes 0/5 with official finish. Results strictly race_date < target_date; zero same-day / future. Retain first race class and first race key, observed result keys, max history date, counts and dates. FIRST_START_UNRESOLVED (including left edge), NO_PRIOR_OBSERVED_START, NO_SAMPLE separated, rate null when zero starts. Five nested B2 scopes ALL/SURFACE/SURFACE_DISTANCE/SURFACE_MONTH/SURFACE_AGE; first 3 are not renumbered per scope. At most three starts per relative per scope, every positive cell LOW_SAMPLE. Partial early window explicitly counted (1 or 2 vs 3). No pooling relatives' results into target win probability or scoring.

## Real audit

| Cohort | Targets | Dam resolved | Granddam resolved | Any relative | Any first history | Any complete 3-start history |
|---|---:|---:|---:|---:|---:|---:|
| A1 actual starters | 35836 | 26892 | 12259 | 24467 | 20434 | 19299 |
| First observed candidate | 42348 | 31561 | 14300 | 28687 | 23702 | 22393 |

Distinct cohort union: target unavailable 10787 (no dated target profile 14; no exact dam edge 10757; dam guard mismatch 16). Resolved dam but no confirmed older relative 2874; relatives but no eligible first history 4985; descriptive first history 23702. Granddam resolved 14300, unresolved exact edge 17261 among resolved dams. Candidate paths 236959; accepted 174169; 61937 no profile by target, 849 not older, 4 guard mismatch. 40825 distinct relative IDs across targets; same target-relative path overlap 0 in real cohort, cross-target reuse substantial. Synthetic overlap preserved but history deduplicated.

| Relationship | Accepted target-relative paths | Unique relative IDs within role |
|---|---:|---:|
| FULL_SIBLING | 4228 | 3417 |
| MATERNAL_HALF_SIBLING | 44587 | 21016 |
| SAME_DAM_SIRE_UNVERIFIED | 38636 | 19332 |
| MATERNAL_AUNT_UNCLE | 86718 | 18541 |

Role unique counts overlap; do not sum as unique relatives. A1 pairs 149055: first 61817, first unresolved 32151, no prior observed start 55087; complete 3 starts 53388. Distinct union 174169 pairs: first candidate 71471, first unresolved 37680, no prior observed start 65018; complete early 61666, partial early 9805. First-candidate relative IDs 22298, unresolved 6774, no prior 11768 (can overlap across targets due to different dates).

| Scope | Cells | First-start evidence | Any early evidence | Three matching early starts | NO_SAMPLE with otherwise eligible first history |
|---|---:|---:|---:|---:|---:|
| ALL | 174169 | 71471 | 71471 | 61666 | 0 |
| SURFACE | 174169 | 43895 | 53970 | 26114 | 17501 |
| SURFACE_DISTANCE | 174169 | 10865 | 20016 | 1837 | 51455 |
| SURFACE_MONTH | 174169 | 4884 | 10691 | 15 | 60780 |
| SURFACE_AGE | 174169 | 28256 | 36029 | 9955 | 35442 |

870845 scope cells, nested and not independent. Per-relative first/early wins, top3, dates and evidence result keys in private output. No pooled kin aptitude or significance claims.

## Validation / reproducibility

B4 synthetic 6/6 PASS: exact canonical roles; unavailable/future/younger/conflict/alias rejection; overlapping path dedup; actual-start and strict target date; left-edge/unknown and zero null; early-window not renumbered under scope. B1–B3 focused regressions 9/9 PASS. Two independent full local executions produced identical three private gzip CSVs and receipt. Input verification and identity, cardinality, path uniqueness, history bounds, coverage reconciliation and scope counts PASS. Library raw readback all four outputs identical to first run.

Source SHA256:
- brdb_b4_relative_paths_v0_1.sql e7a878add05326aab2a7232adb0fec84b61836ef5534f7cb7e512533cd1153ee
- brdb_b4_relative_early_results_v0_1.sql d0348aaa888d0c131805d20c3abc85cb354da4effc217b20bcb50bcbb4ac1783
- run_brdb_b4_local.py dc1817610aedfb72b94990c5c33949da45aa331bd8d1fae919d020540fe951a3
- test_brdb_b4_research.py c2c77826da3f9f97127ea1209b4fbe131504a74eb6bff9ff5d3684ae7f950174

Private Library /BRDB/Development_B4_20261124/:
- b4_receipt.json a9cb6731b1af956bcbec00b240c03bff7c428deee39f8c3aff5d9af44600f26a
- PRIVATE_b4_target_coverage.csv.gz 8f93662bf6ee6a0d3631c73d6ef904eac469ba25a5f3fd5c994466d0eb2ef8ae
- PRIVATE_b4_relative_paths.csv.gz 392b5cb77f4fdfb4c61921483426a0c486fc011eb8354c41e397aac98a616530
- PRIVATE_b4_relative_stats.csv.gz 4347c7aeaf5957827202fa058ebe254d2c26b274e2d8386a480d81f4abfbe8fe

Replay with B3 private input layout:
    PYTHONPATH=tools/data-storage python horse-racing/brdb/research/run_brdb_b4_local.py --input-root /private/input --output-dir /private/output
    PYTHONPATH=tools/data-storage:horse-racing/brdb/research python -m unittest test_brdb_b4_research test_brdb_b3_research test_brdb_b1_b2_research -v

Next B5: target field from pre-race PACI, separate race-class and individual eligibility (do not use realized target start/finish status); non-scoring schema with B2/B3/B4 evidence, explicit SOURCE_UNAVAILABLE/NO_SAMPLE/LOW_SAMPLE, static relation temporal warning; all horses with strict identity and reproducible real-data replay. Historical audit cohort is not a pre-race target consumer. A4 can improve unresolved identity later; B7 evaluates prediction. No licensed horse-level rows in Git; no merge or publication authorization.
