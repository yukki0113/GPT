# JRDB Feature Audit — Stage A Report

Date: 2026-10-05  
Lane: RaceNote 0.5.x candidate research  
Active prediction cohort: `RaceNote-Human-Context-Reader-0.4.6-candidate` (unchanged)  
Baseline repository commit: `537bed7945deff65d0543dc108483c29e56f858f`

## Scope and method

This is a structural lineage audit; no outcomes, 2026 BTDAY results, feature weights, or performance measures were used. The reproducible catalog contains 41 conceptual feature rows. Related scalar dimensions are grouped into vectors where they share one record and interpretation (for example four pace indices and their ranks); it is not a row-per-byte transcription of every field in every JRDB record.

The lineage trace followed the production PACI fixed-width parser and normalizer in `horse-racing/jrdb/src/racenote_jrdb.py`, the Analysis v1.4 schema and RaceNote Analysis/history paths, and a checked-in forecast Reader from BTDay 0048. For the v0.4.6 surface, the utility applies the same market-object removal performed by `racenote_prepare_forecast_input.bind` before checking the witness paths. Reader View v0.1 is lossless apart from hoisting common context, so its output paths represent the same feature payload as the underlying RaceNote bundle.

The machine-readable inventory and generator are:

- `horse-racing/jrdb/docs/racenote/research-work/feature_inventory_stage_a.json`
- `horse-racing/jrdb/tools/audit_racenote_feature_lineage_stage_a.py`

## Inventory counts

There are 41 conceptual rows in 11 categories:

| Category | Count |
|---|---:|
| Suitability/context | 6 |
| Class/level | 2 |
| Ability/performance | 5 |
| JRDB composites/marks | 3 |
| Jockey/trainer | 4 |
| Pace/position | 6 |
| Training/condition | 7 |
| Market | 1 |
| Analysis history/trends | 4 |
| Pedigree | 2 |
| PACI extensions | 1 |
| **Total** | **41** |

| Lineage/exposure status | Count |
|---|---:|
| `CURRENT_VISIBLE` | 16 |
| `DERIVED_VISIBLE` | 21 |
| `CURRENT_HIDDEN` | 2 |
| `DERIVED_HIDDEN` | 0 |
| `UNKNOWN_LINEAGE` | 2 |
| `LEGACY_ONLY` | 0 |
| **Total** | **41** |

These are inventory-status counts, not importance or quality judgments. `CURRENT_HIDDEN` includes the KYI opening/base odds and popularity, present in DAY PREP but removed when the v0.4.6 clean Reader is bound, and Analysis Lite columns not serialized into the compact historical-profile Reader features.

## Current v0.4.6 visible feature summary

The clean Reader exposes the following JRDB-derived evidence groups:

- **Race and suitability context:** surface, distance, class, grade, race-condition symbols; runner distance/surface/heavy-track fit and JRDB class.
- **Ability and JRDB ratings:** IDM, total/info/jockey/stable/longshot indices, jockey expected top-two rate, JRDB marks, and horse-level ratings.
- **Pace and position:** running style, four pace/position indices and ranks, projected mid-race/last-three-furlong/finish order and lane, start index, late-break rate, and pace symbol.
- **Current condition and connections:** improvement and stable-evaluation labels, jockey/trainer identity and base, farm identity/rank, training index and arrow, one main workout's clocks/indices/context, plus CYB training/condition indices, counts, grades and comment fields.
- **Past performance:** up to five linked pre-target PACI runs with JRDB performance metrics and available ZKB notes; up to three older Analysis runs; as-of-exclusive career/surface/distance/venue summaries; and race-level historical trends.
- **Pedigree:** pre-race identity fields and sire/broodmare-sire historical context summaries. Enrichment explicitly declares `scoring: false`.

The evidence witness has market fields in its pre-bind DAY PREP Reader. `racenote_prepare_forecast_input.bind` removes market objects from race and horse objects, and the clean Reader does not expose the KYI base odds/ranks. This is a transport boundary: the full RaceNote evidence bundle and the v0.4.6 clean prediction input are distinct surfaces.

## Hidden-but-available candidates

- **KYI base win/place odds and ranks:** parsed and available in DAY PREP, excluded from the market-blind clean input.
- **Analysis Lite columns outside emitted profile summaries:** meeting number/day, course code, age/sex, line codes, and explicit previous-result keys are stored in the v1.4 fact table but not emitted as historical-profile features in this Reader path. Some identity pieces are separately surfaced by pedigree enrichment.
- **Further PACI/record-family fields:** the fixed-width parser supports additional fields/record families whose use varies by pipeline. The inventory records the unresolved family at a high level rather than claiming every parser field is a clean Reader candidate.

The catalog does not imply these hidden values should be exposed. That decision belongs to later evidence stages.

## Obvious semantic overlap groups

1. **Ability/composite family:** IDM, total index, info index, longshot index, and their corresponding JRDB marks. The marks are categorical encodings alongside numeric ratings; composition formulae are not established here.
2. **Pace and position family:** pace indices, ranks, projected positions, running style, start index, and late-break rate. They describe related race mechanics but have distinct source meanings.
3. **Condition/training family:** KYI training index/arrow, CHA workout clock and clock indices, CYB training index/condition index, improvement code, stable evaluation/index, and farm rank. These should not be treated as duplicates solely by naming.
4. **Suitability/history family:** KYI fit categories overlap conceptually with same-surface/same-distance history and pedigree-context summaries.
5. **Historical performance:** PACI recent runs, Analysis older runs, horse historical-profile summaries, and pedigree-context summaries reuse past results at different granularities.
6. **Class/level:** BAC race class/grade and KYI individual JRDB class are both level descriptors but are not interchangeable.

Candidate pairs/groups are recorded per row in `overlap_candidates` for Stage B/C design; no redundancy judgment is made in Stage A.

## Unresolved lineage

- The official construction/calibration formulas for JRDB composite indices, class codes, expected top-two rate, and marks are not present in the parser. The catalog records raw-source offsets and preserves the provider value as supplied; formula lineage remains unknown.
- `field_context` has no matching field in the selected clean Reader witness, and its precise producer/schema path was not established in this pass. It remains `UNKNOWN_LINEAGE` and is not counted as a confirmed visible v0.4.6 feature.
- The catalog’s PACI extension row represents record-family reach at a high level. Full parser-field exhaustiveness across all optional PACI records needs a separate parser/schema crosswalk before claiming a complete byte-level catalog.
- The Reader witness is one committed 2026 race. It verifies schema-path exposure and market stripping, not race/date completeness or optional-value non-null rates.

## Stage B input recommendation

Start with the instructed **2023-01-01 through 2025-12-31** window. Build candidate inputs from the visible JRDB groups above, keeping source channels distinct: KYI indices/ratings, pace and suitability, training sources (KYI/CHA/CYB), recent and older performance, history summaries/trends, and pedigree context. Carry the two hidden groups only as separately labeled availability candidates if a later stage explicitly permits clean-input changes. Preserve year-by-year views and measure sample size, stability, market independence, and overlap before proposing any priority tiers. Do not use 2026 BTDAY outcomes for selection; no Stage B performance conclusion is made here.

## Changed artifacts and checks

Created:

- `horse-racing/jrdb/tools/audit_racenote_feature_lineage_stage_a.py`
- `horse-racing/jrdb/docs/racenote/research-work/feature_inventory_stage_a.json`
- `horse-racing/jrdb/docs/racenote/research-work/reports/20261005_JRDB_FEATURE_AUDIT_STAGE_A_REPORT.md`

The v0.4.6 Reader, prediction logic, schemas, and active cohort were not edited. The pre-existing untracked `asa-server-manager/dist/` directory was left untouched.

Reproducibility check: ran the generator twice against the committed BTDay 0048 Reader witness. Both runs emitted 41 rows and identical counts. The JSON SHA-256 was identical on both runs: `8B5F8D66C661BF88E41062827CD89BCB61AD4F7F03A06F1CF0F09DEE15502CAC`. Exposure assertions check that expected visible paths exist and market-hidden fields do not survive clean binding.

Relevant commit SHA: `537bed7945deff65d0543dc108483c29e56f858f` (starting HEAD; these new audit artifacts are not committed in this run).
