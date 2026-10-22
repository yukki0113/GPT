# BRDB Horse Review Contract v0.1

Status: **FROZEN (descriptive review)**  
Date: 2026-10-22

## Identity and API

Canonical identity is `horse_id = JRDB blood_registration_no`. Horse-name fallback is prohibited.

`BloodReviewEngine(reader).horse_review(horse_id, target_context, *, pedigree_context=None)` returns one result. `reviews_for_horses(horse_ids, target_context, *, pedigree_contexts=None)` returns one result per requested unique ID and has exactly the same semantics as single review. Callers must supply a complete, unique field cohort to the RaceNote adapter.

## Input

`target_context` requires `target_date` (YYYY-MM-DD or YYYYMMDD), nonempty `venue`, `surface` (芝/ダート/turf/dirt), and `distance` (integer, 600–5000 metres). It normalizes to `target_date` ISO, `venue`, `surface`, `distance`. Invalid context returns `UNSUPPORTED_CONTEXT`.

Optional `pedigree_context` must come from `adapt_racenote_bundle` with exact race date, venue, surface, distance, canonical horse IDs and complete cohort. Producer attests `race_date < target_date`, `as_of_exclusive = target_date`, P2-0.1, non-scoring, exact condition scope and no result fields. Sire and broodmare-sire names must match canonical Reader facts. A mismatched role is withheld; a mismatched cohort rejects the adapter input. Zero starts is factual evidence.

## Frozen output fields

`horse_id`, `status`, `contract_version = brdb-review-v0.1`, `target_context`, `facts` (`sire_name`, `dam_name`, `broodmare_sire_name`), `classification` (`sire_line`, `broodmare_sire_line`, `regional_type`), `review` (`overall_score`, `components`, `positive_factors`, `negative_factors`, `summary`, `pedigree_context`), `coverage` (`status`, `pedigree_fields`, `pedigree_context`), `confidence`, `provenance` (`generation_id`, `pedigree_schema_version`, `taxonomy_version`, `review_logic_version`, `p2_source`).

Only Reader facts may populate `facts` and official lineage classifications. `regional_type` and `overall_score` are always null; component/factor arrays are empty. P2 output is a whitelisted descriptive aggregate: starts, wins, top3, derived win/top3 rates, as-of, source and sample band. Race results and arbitrary input keys never pass through.

## Status and coverage

- `NO_HORSE_ID`: empty identity.
- `UNSUPPORTED_CONTEXT`: context could not be normalized.
- `NO_PEDIGREE`: no canonical Reader row, or all three pedigree names absent.
- `AS_OF_UNVERIFIED`: canonical `profile_data_date` is missing, malformed, or later than target date. All pedigree facts and P2 are withheld.
- `PARTIAL`: at least one pedigree name exists but all three names and both P2 roles are not available.
- `AVAILABLE`: three pedigree names and both P2 roles available.

`coverage.status` is FULL/PARTIAL/NONE for three pedigree names. `coverage.pedigree_context` is FULL/PARTIAL/NONE for two P2 roles. Missing evidence is never scored as zero. `confidence = DESCRIPTIVE_ONLY` describes evidence type, not predictive certainty.

## PWA boundary

PWA may consume this review result without reading BRDB Parquet or RaceNote history directly. This freeze does not enable PWA integration, scoring, regional taxonomy or a production serving change.
