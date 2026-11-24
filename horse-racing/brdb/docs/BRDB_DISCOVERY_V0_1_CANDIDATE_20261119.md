# BRDB Discovery v0.1 candidate — 2026-11-19

Status: **RESEARCH ONLY / NOT FOR PREDICTION OR PUBLICATION**.

## Input and boundary

Reads `brdb-common-analysis-v0.1-candidate` JSON produced by the separate M7 adapter. Never reads PACI or Parquet directly; preserves full race and `(horse_no,horse_id)` identity. Does not alter the source. It is a downstream experiment, **not a replacement for existing M7 v0.3**. All output has `prediction_safe=false`, `production_authorized=false`, `display_authorized=false`.

## Deterministic discovery rules

1. `SIRE_BASELINE_COMPARISON`: for `VENUE_COURSE_EXACT`, `VENUE_DISTANCE`, and `ALL_VENUES_DISTANCE`, records observed sire top-3 rate vs **same-scope** provided baseline, with starts, top3, baseline starts, baseline rate, signed percentage-point difference. `ABOVE/BELOW/EQUAL` is purely the sign of the arithmetic difference; no quality or aptitude verdict.
2. `BMS_TARGET_BAND_OBSERVATION`: records maternal-grandsire top-3 observations only for same target surface and target distance band, if an observed sample exists. This **does not assert** maternal distance compensation.
3. Missing samples do not produce findings. The detector never treats null rates as 0%, nor aggregates nested/overlapping scopes.
4. Pairing and relatives are not promoted to findings: historical as-of remains unverified in this M7 set. Similar restraints apply to regional roots, ancestral crosses and actual going/mud suitability: validated input dimensions or taxonomy not yet established.

`finding_id`, `kind`, `interpretation_status`, `evidence_refs`, `scope_key`, `metrics`, `signal`, `sample_status`, and `historical_asof_status` are included for audit. No natural-language review or Tips, score, probability, suitability, confidence, betting opinion, or ranking are generated. The observation findings are *candidate research observations*, not approved PWA text.

## Local research replay

```
python brdb_discovery.py --input /path/to/private/common_analysis.json --output /path/to/private/discovery.json
python -m unittest -v test_brdb_discovery.py
```

For the private 2026-11-15 Tokyo12R M7 run (18 horses), 71 candidate observations were produced; all display and prediction flags remained false. The 8 synthetic regression tests passed. Private input/output and observed horse-level findings must not be committed to public Git. The checked fixture is synthetic, not an accepted evidence of published or pre-race validation.

## Next scientific gates

- Verified historical cutoff and baseline population definitions per evidence lane, independently tested before RaceNote use.
- Going (良/稍重/重/不良) per historical race, with data coverage and as-of integrity for a going-specific observation.
- Distance-complement claims: define a measurable comparative hypothesis with a matched-control design or calibration, rather than assuming a maternal grandsire's long-distance success compensates for sire's short-distance profile.
- Pairing/relatives: source as-of provenance and duplicate overlap controls. Roots/cross: official lineage identity and taxonomic/condition evidence.
- PWA wording editor and user acceptance after research-only findings are separately approved for display. BRDB output cannot authorize itself.
