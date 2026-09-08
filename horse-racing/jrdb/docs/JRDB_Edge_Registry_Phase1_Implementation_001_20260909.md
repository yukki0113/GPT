# JRDB Edge Registry Phase1 — Implementation 001 (2026-09-09)

## Status

`IMPLEMENTED_FOUNDATION / DISCOVERY_READY`

This package starts the JRDB Edge Registry as a derived statistical knowledge layer shared by PWA newspaper, RaceNote/GPT, and the independent-index Edge layer.

## Implemented

### 1. Factor-specific temporal Validation Policy

Added:

- `config/jrdb_edge_validation_policies_v0_1.json`
- `src/jrdb_edge_validation.py`

Validation is not a universal fixed calendar split. Candidates are routed by factor nature:

- `STRUCTURAL` — stable course/track/frame structure; calendar-block stability
- `LIFECYCLE` — established pedigree factors; relative lifecycle segments
- `DYNAMIC` — jockey/trainer/human relations; rolling windows + expiry
- `EMERGING` — young sire / young or low-sample human factor; WATCH/PROVISIONAL with frequent review

PEDIGREE and HUMAN candidates may move from EMERGING into their mature validation class as age/sample accumulates.

### 2. Edge Registry storage contract

Added:

- `schema/jrdb_edge_registry_schema_v0_1.sql`

The schema keeps Edge identity, positive/negative polarity, Performance and Value signals separately, temporal status, metrics snapshots, and append-only validation events.

No Phase1 discovery result is automatically added to the independent index score.

### 3. Leakage-safe Edge Feature Mart

Added:

- `schema/jrdb_edge_feature_mart_schema_v0_1.sql`
- `src/build_jrdb_edge_feature_mart.py`

The Mart is one race x one runner. Current BAC/KYI/pre-race profile facts and strict-prior previous-run facts are condition inputs. Target finish, odds, popularity and payouts are label columns only.

Initial derived transitions:

- distance change bucket
- surface transition
- frame-zone transition

Future-dated horse profile observations are excluded by as-of join. `CURRENT_RESULT_FALLBACK` race context is marked non-pre-race and excluded from eligible discovery.

### 4. Canonical candidate templates

Added:

- `config/jrdb_edge_candidate_templates_v0_1.json`

Phase1 candidate complexity is fixed as one Anchor + at most two Modifiers. Free numeric threshold search is prohibited.

Initial enabled templates include:

- course x frame zone
- sire x turn x exact distance
- sire x surface x exact distance
- sire line x turn x exact distance
- sire x distance change
- sire x surface transition
- sire x frame transition

Human templates are present but disabled until a horse-quality-adjusted residual baseline is connected. Raw jockey/trainer pair win/place rate is not accepted as formal Edge evidence.

### 5. Template-driven candidate discovery

Added:

- `src/jrdb_edge_discovery.py`

Candidate discovery computes candidate statistics against the same Anchor baseline and selects its temporal Validation Policy. It emits deterministic candidate IDs and descriptive metrics but always keeps `promotion_status = NOT_VALIDATED` until a temporal validator is applied.

Core metrics include:

- sample count
- unique horses / races
- win/place rate
- win/place ROI
- baseline place rate / ROI
- Performance lift
- ROI ratio versus baseline
- approximate largest-return concentration

## Tests added

- `tests/test_jrdb_edge_validation.py`
- `tests/test_build_jrdb_edge_feature_mart.py`
- `tests/test_jrdb_edge_discovery.py`

The first two test groups were locally exercised during implementation and passed 7 tests in total before the discovery module was added. The discovery regression tests are committed with the module; repository CI coverage for the new Edge paths is still to be wired.

## Historical source readiness

The existing JRDB Index Base full-audit path has already completed a real 2010-2025 hash-enabled build/audit successfully in Issue #276 / run `33422716468`.

Recorded full-build facts:

- runner rows: 781,161
- runner_pre -> result match: 100%
- previous links: 2,919,703 total / 2,740,251 resolved
- previous-link resolution: 93.8538%
- previous-1 resolution: 96.6689%
- as-of profile coverage: 89.4767%
- fallback races: 53
- SQLite integrity: ok
- audit status: PASS

This proves the longitudinal source is reproducibly buildable. The 1.7GB Index Base produced by that audit was a workflow-temporary artifact, so the Edge full-history execution must rebuild it from Raw or add a dedicated persisted Edge pipeline rather than assuming the old SQLite file is still present.

## Not complete yet

The following are intentionally not claimed as complete in Implementation 001:

1. temporal slice validator that promotes/rejects candidates under STRUCTURAL/LIFECYCLE/DYNAMIC/EMERGING rules
2. multiple-testing / confidence / return-concentration final gates
3. generation of the first 2010-2025 Edge Registry
4. Drive publication of `edge_registry.sqlite`, active JSONL/CSV, manifest and audit
5. pre-race Edge Matcher
6. PWA/RaceNote integration
7. automatic index scoring

## Next implementation package

Implementation 002 should add the temporal validator and signal gates, then run the enabled Phase1 templates on the full historical source. The first outputs should remain research/shadow artifacts until validation and concentration audits pass.
