# BRDB B1 closure / B2 sire debut research v0.1 — 2026-11-24 JST

## Status

B1 **PASS_RESEARCH_ONLY (eligibility audit complete with explicit unresolved/excluded histories)**.
B2 **PASS_RESEARCH_ONLY (bounded canonical sire-ID descriptive cohort)**.
No global lifetime-first-start certification, no independent historical parent-identity as-of certification, no prediction or production authorization. B3 is next; unresolved identities are retained as coverage debt, not guessed, and the existing 11/18 provider-equivalence decision is not reopened.

## Source and replay

Main observed d96ad6c01aa9771b11b1f74bec34ec619253dc1b; B1 v0.2 source commit b4b0b02aea1c435611d29f59055f33229a6b81de, SQL SHA256 279ee9c61e9db06b487e473e60a1021b68153c1373d4b0358c58c8f10b259eb2.

- Analysis v1.4 generation analysis-v1_4-postrace-20261115-01 manifest SHA256 39b4e94d31e5dc9507bd3aa037aa227c7c8dcefe0ddf3f744ec1e687a6965f1d, 10/10 target annual partitions size+SHA PASS.
- Prior private candidate CSV is visible in Library but its Project backing could not materialize. Recovered instead using accepted JRDB Warehouse CURRENT jrdb_normalized_warehouse_v1_2010_2025_g20261118_bacfix; manifest semantic SHA256 174eaf459f56eb1afe55bc157a2dcf0226a212bf6c00ba062ce5a3e641b2a269, final audit semantic SHA256 a94d0a4ab45b2b861c0de47c624ff7cb773b0ef354db933688960d0cee4282c9. UKC partitions 10/10 matched current manifest size+SHA; embedded original annual archive SHA 10/10 matched existing Git UKC input manifest. UKC rows 480,962; duplicate horse/date 0, member-date mismatch 0.
- BRDB research generation 5279af0bd8226cde retrieved via canonical Drive folder #2223 ZIP SHA256 672c6c1f78f632db60a1f7c2e8304b63e0576e51efef79f0cf473351aa8fd0d4; manifest 7efb70ab370cafd18d39eb20ea4fc2bb32490653364a58b44b1382cf9fa5f16c; pedigree_fact 1e7574f78703d79d8d83797f9e350a8927b728fc68c659cf5d340ee0f79b3536; parent_relation c90482851f91b8f2d99ec88407f4246471d10b38f18163464f88760cb197ff85. 132,652 profiles, 397,956 relations, zero duplicate keys.
- Verified existing Python 3.13.5 / DuckDB 2.0.1 / PyArrow 25.0.1 environment and canonical data_storage.query/common. No raw parser replacement, no external data publish, no Actions required.
- Exact existing v0.2 classification CTE reused. Latest UKC by exact horse_id with member/data date <= target date; join preserves all race_key/horse_no/horse_id rows. No future profiles. Aggregate counts match accepted M6 (481,503 matched, 480,904 same day, 599 prior date, 124 missing), not a claim of byte equality with its CSV. Original delivery time remains UNATTESTED. Source-equivalence policy USER_ACCEPTED_PROVIDER_EQUIVALENCE.

## B1 real audit

| Cohort | Rows | Dated UKC | Sire guarded ID | BMS guarded ID | Both |
|---|---:|---:|---:|---:|---:|
| All entries 2016–2025 | 481627 | 481503 | 351845 | 179773 | 124509 |
| A1 entries | 39954 | 39954 | 28922 | 17326 | 11972 |
| A1 actual starters | 39789 | 39789 | 28813 | 17259 | 11925 |
| First-observed candidates | 42348 | 42334 | 30761 | 18881 | 13153 |
| First-observed A1 candidates | 35836 | 35836 | 26048 | 16184 | 11250 |

All entries: Analysis vs dated UKC sire/BMS/lineage field difference 2,866; A1 entries 266; first candidates 214. Dated facts are authoritative for this research. Parent lookup uses existing accepted parent_relation on exact child horse_id and role; permits only RESOLVED_EXACT with lineage guard, unique candidate, existing parent master, 8-digit ID, and exact dated name/birth year/lineage match. Static ID is not historical availability-certified. Never invent a parent or infer by name alone. First candidates: sire NO_CANDIDATE 11,571, CONFLICT 2, NO_DATED_PROFILE 14; BMS NO_CANDIDATE 23,451, CONFLICT 2, NO_DATED_PROFILE 14. The 14 missing dated profiles are 2025. Coverage and temporal restrictions persist, no missing identity translated to poor aptitude. First-observed candidate symbols: 00=41,123; 06=1,211; missing=14; not proof of actual overseas/local racing history. 2016 left-edge and unresolved earlier histories remain outside the candidate population as established in the preceding B1 replay. B1 completion is the audit, not universal identity resolution.

## B2 descriptive statistics (not predictive evidence)

Both cohorts use the same 2017–2025 calendar window. A1 is race class (actual starters); first-observed candidate is separate individual-history cohort. They overlap; do not pool or add. Exclude 1/2 non-starters; denominator includes 0/3/4/5/6 actual starters per B1; win and top3 use official finish for codes 0/5. Count unique horses/races, normal finishers, wins/top3 and rates. Canonical sire groups only; baseline keeps all eligible starters and additionally reports matched-ID baseline so selection bias remains visible. Scope groups: ALL, SURFACE, SURFACE_DISTANCE (exact distance), SURFACE_MONTH, SURFACE_AGE. Do not add nested scopes. LOW_SAMPLE if N<30 is a descriptive triage threshold, not a validated prediction cutoff. No sample row is not a zero-rate observation; target-field NO_SAMPLE handling belongs to B5. All historical outcome dates strictly < cutoff; static parent IDs remain AS_OF_UNVERIFIED.

| Cutoff | Cohort | Eligible starts | Sire ID starts | Sire ID count | Sire ID top3 | All baseline top3 |
|---|---|---:|---:|---:|---:|---:|
| 2026-01-01 | A1 actual starters | 35836 | 26048 | 355 | 5827 | 8013 |
| 2026-01-01 | First-observed candidate | 42348 | 30761 | 372 | 6192 | 8533 |

2025-01-01 snapshot: 15,244 groups, 13,465 low-N. 2026-01-01 snapshot: 16,444 groups, 14,490 low-N. Counts are group observations, not independent samples. Two full executions yield identical CSV bytes and receipt. Per scope, counts and sums of wins/top3 reconcile with resolved baselines, unique group key, no future/same-day outcome, no count violations. Focused synthetic 4/4 PASS: prior non-starter/abnormal starter; unresolved/unknown/left-edge/invalid prior; dated guard rejects future/mismatch/invalid guard; cutoff and denominator including abnormal finishes. No predictive validation.

## Artifacts and reproducibility

Source files in ../research:
- brdb_b1_pedigree_join_v0_1.sql SHA256 624226d5d330eed4026cc88a955fe59d30bdaba883c9844c569437ffe51ff21a
- brdb_b2_sire_debut_statistics_v0_1.sql SHA256 a98f85b2d1beba81bc7a78a2e73015da0b3cb0b67c9f99c954554efcc7cffac8
- run_brdb_b1_b2_local.py SHA256 310aadcec58596383ee93d676776884699c1ae6a6e8fad96e375a250e37789ed
- test_brdb_b1_b2_research.py SHA256 8aded3b3720bc372756fc255c8ec9aca8b2205a2c18b7e1fd67e77e70c477d00

With SHA-verified private input root containing analysis_manifest.json, objects/fact_entry_result_lite/year=YYYY/*.parquet, warehouse/{current,manifest,audit}.json, warehouse/ukc/*.parquet and pedigree/{manifest.json,pedigree_fact.parquet,parent_relation.parquet}:

    PYTHONPATH=tools/data-storage python horse-racing/brdb/research/run_brdb_b1_b2_local.py --input-root /private/input --output-dir /private/output
    PYTHONPATH=tools/data-storage:horse-racing/brdb/research python -m unittest test_brdb_b1_b2_research -v

Private Library /BRDB/Development_B1_B2_20261124/ contains outputs and source; verified exact readback of:
- b1_b2_receipt.json SHA256 9b731f40b351f530d671f17b8e4244926336bfbfb7d09259fa3975af63982866
- PRIVATE_b2_sire_stats_2025-01-01.csv SHA256 59fa2cafd01e9d5af9dc2c7faca36095b5165d1e82c558e0c4170c76ad9920df
- PRIVATE_b2_sire_stats_2026-01-01.csv SHA256 9c996773da635c30e82d81435319bcaa6bd20a28e32c0919aec33769c6e39c39

No licensed rows or private sire-level output committed to Git. Next B3: BMS ID and ordered pairing with the same cohorts, cutoffs, denominators and conditions; report missing coverage independently and no additive claims; lineage code pairing only as separate declared lane. B4 maternal relatives follows; B5 whole-field pre-race research review separate from realized-result cohort. Existing RaceNote Z, CURRENT, PWA and frozen contracts unchanged.
