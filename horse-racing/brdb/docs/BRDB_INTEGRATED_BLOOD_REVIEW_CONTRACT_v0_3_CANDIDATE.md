# BRDB integrated blood review v0.3 candidate — D4 supplemental research attachment

Status: **RESEARCH CONTRACT CANDIDATE ACCEPTED / ADAPTER VALIDATED / NOT PRODUCTION AUTHORIZED**  
Date: 2026-11-17  
Contract ID: `brdb-integrated-blood-review-v0.3-candidate`

## Purpose

v0.3 candidate is a new, additive research contract that attaches the accepted D4 non-scoring supplemental sidecar to an existing `brdb-integrated-blood-review-v0.2-candidate` payload.

It does **not** modify:
- frozen `brdb-review-v0.1`;
- existing `brdb-integrated-blood-review-v0.2-candidate`;
- D4 `brdb-d4-supplemental-research-v0.1`;
- BRDB CURRENT;
- RaceNote / PWA / Newspaper production interfaces.

The adapter's only role is deterministic contract composition. It does not reinterpret evidence or create a blood score.

## Added v0.3 fields

Top level:
- `contract_version = brdb-integrated-blood-review-v0.3-candidate`;
- `supplemental_research`.

Each horse:
- `supplemental_status`;
- `supplemental_insights`.

All v0.2 fields are preserved by deep copy.

### supplemental_research

The block preserves D4 boundary/provenance fields:
- `sidecar_schema_version`;
- frozen base/integrated contract identifiers;
- `release_status=RESEARCH_SIDECAR_ONLY`;
- `research_only=true`;
- `prediction_safe=false`;
- `historical_asof_status=AS_OF_UNVERIFIED`;
- `no_forecast_or_score=true`;
- `source_time_guard`;
- source generations;
- exact D3/research-field SHA provenance;
- D4 aggregate coverage.

### supplemental_insights

Items are copied from D4 without recomputation:
- source lane/name;
- condition scope;
- observed counts/rates and sample status;
- optional D3 temporal diagnostic;
- `interpretation_status=OBSERVATION_ONLY_AS_OF_UNVERIFIED`;
- `contribution_to_score=null`.

Zero supplemental items is valid and must not be treated as a negative factor.

## Fail-closed merge requirements

`src/brdb_integrated_review_v03_candidate.py` rejects the merge unless:

1. base contract is exactly v0.2 candidate and remains `RESEARCH_CANDIDATE`;
2. D4 sidecar is exactly `brdb-d4-supplemental-research-v0.1`;
3. D4 remains research-only, prediction-unsafe, AS_OF_UNVERIFIED and no-score;
4. target date, venue, surface, distance and field size match;
5. full-field `(horse_id, horse_no)` identities match exactly and remain horse-number ordered;
6. D4 reviewed-horse coverage equals field size;
7. every D4 horse remains `AS_OF_UNVERIFIED`;
8. D4 factors are empty, summary null and confidence UNASSESSED;
9. every supplemental item remains observation-only and contributes no score.

No name fallback or fuzzy identity reconciliation is allowed.

## Interpretation boundary

v0.3 does **not** authorize:
- automatic positive/negative/unknown factor generation from D4;
- confidence promotion;
- summary generation;
- score, rank, probability, mark or forecast;
- PWA display;
- RaceNote production use;
- promotion of D3 historical evidence to as-of verified.

The selected PACI real-field source has independent user-side pre-off availability evidence in `BRDB_PACI_RACE_DAY_PROVENANCE_20261117.md`, but that does not change D3's `AS_OF_UNVERIFIED` status.

## Machine-readable artifacts

- Schema: `schema/brdb_integrated_review_v0_3_candidate.schema.json`
- Adapter: `src/brdb_integrated_review_v03_candidate.py`
- Fixed example: `tests/fixtures/brdb_integrated_review_v0_3_candidate_example.json`
- Regression tests: `tests/test_brdb_integrated_review_v03_candidate.py`

Existing v0.2 schema/example/tests remain unchanged.

## Acceptance gate

Research-contract acceptance requires:
1. exact v0.2 regression remains PASS;
2. v0.3 JSON Schema validates the fixed example and adapter output;
3. fixed adapter output equals the committed v0.3 example;
4. identity/race mismatch fails closed;
5. prediction-safe/as-of promotion fails closed;
6. D4 factor or score-contribution injection fails closed;
7. zero supplemental evidence remains valid;
8. v0.2 factors/summary/confidence are preserved;
9. CI uses a real JSON Schema validator rather than silently skipping validation.

Passing these gates accepts only the **contract composition layer**, not M7 production graduation.


## Acceptance evidence — 2026-11-17

Exact branch CI:
- BRDB research PR tests: Actions run `44027606413` — **PASS**
  - P0-2 research tests: 4 PASS
  - P1-1 condition report tests: 4 PASS
  - P1-2 annual stability tests: 4 PASS
  - existing v0.2 integrated contract regression: **6 PASS**
  - v0.3 candidate adapter/schema tests: **12 PASS**
  - `jsonschema>=4.22,<5` installed in CI; v0.3 fixed fixture and adapter output were validated by Draft 2020-12 schema.
- Repository-wide EdgeDB decommission T4 regression: Actions run `44027606430` — **PASS**.

The accepted v0.3 test set confirms:
- fixed fixture is schema-valid;
- adapter output equals the committed fixture;
- base input is not mutated;
- full-field identity/race mismatches fail closed;
- prediction-safe and as-of promotion fail closed;
- injected D4 factors or score contribution fail closed;
- zero supplemental evidence remains valid;
- existing v0.2 factors/summary/confidence remain unchanged.

This acceptance is limited to the **research contract composition layer**. M7 production promotion remains unaccepted.
