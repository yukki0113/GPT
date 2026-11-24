# BRDB cross-lane discovery v0.2 candidate — 2026-11-19

Status: **RESEARCH-ONLY / LOCAL REAL-FIELD REPLAY / NOT PREDICTION OR PWA AUTHORIZED**.

## Scope and intended consumer

This module consumes the `brdb-common-analysis-v0.1-candidate` all-horse JSON and reuses the v0.1 discovery preflight. It constructs evidence-referenced **cross-lane observation pairs**, not suitability factors, predictive features or review prose. It does not touch PACI, BRDB CURRENT, RaceNote or Newspaper/PWA.

### Deterministic observations

1. `SIRE_BMS_DISTANCE_BAND_COOBSERVATION`: same target surface and the same distance-band, comparing the sire's progeny cohort against offspring with the target broodmare sire. The two populations are distinct and may overlap. **A high maternal result does not prove the mother compensates for sire's distance profile.**
2. `PAIRING_SIRE_SCOPE_COOBSERVATION`: father-line × maternal-grandsire-line cohort and sire cohort at identical surface, venue, course/distance scope. The paired cohort can overlap with sire's cohort. No causal impact is inferred from any percentage-point difference.

Each output contains two unique original `evidence_refs`, two distinct sample counts / top-three rates, observed rate difference, possible-overlap warning and immutable `display_eligible=false`, `prediction_eligible=false`, `causal_claim=false`, `suitability_claim=false`. `PAIRING` historical-as-of is always `AS_OF_UNVERIFIED` in this candidate. Zero-start samples do not become findings.

The original v0.1 findings (71 in the private replay) are **not merged or counted as novel findings**. v0.2 produces an independent set of 71 cross-observations on the same private 18-horse replay: 18 sire/BMS same-band co-observations, 53 pairing/sire matched-scope co-observations. These are observations, not 71 validated favourable factors. Their count overlaps the v0.1 count numerically by coincidence.

### Explicitly deferred

- **近親**: common v0.1 exposes relationship counts, not per-relative evidence and same-condition performance links. The private ④ detail sidecar must be projected into a separate, lossless, validated evidence contract; no inferred performance from mere number of relatives.
- **道悪**: the current common v0.1 scope has surface/distance/course, but no confirmed historical going (良/稍重/重/不良) dimension. Need canonical JRDB race context join and as-of coverage before comparison.
- **距離補完**: comparing sire and maternal cohorts alone is insufficient for a counterfactual or transfer-of-aptitude claim. The review may later surface both facts as distinct observations once display approved, but must not turn them into validated compensation.
- **系統・国籍ルーツ**: reviewed official taxonomy and condition-level empirical validation still required.

## Full-cohort replay

Private inputs from Library `/BRDB/M7/`: 2026-11-15 Tokyo12R, `race_key=05265412`, 18 horses. Ran common v0.1 adapter (local private data) then v0.2. Tested with synthetic fixture: **9/9 PASS**. Output validated with `brdb_cross_discovery_v0_2_candidate.schema.json`: **0 errors**.

All per-horse real replay JSON stays private. **Do not commit private M7 output, common private adapter output or synthetic fixture accidentally derived from private names.** The included fixture in the prior v0.1 package is deliberately synthetic.

Run locally with the adjacent v0.1 `brdb_discovery.py` on `PYTHONPATH`:

```bash
PYTHONPATH=../brdb_discovery:. python -m unittest -v test_brdb_cross_discovery.py
PYTHONPATH=../brdb_discovery:. python brdb_cross_discovery.py --input /private/common_analysis.json --output /private/cross_discovery.json
```

## Next gate

1. Verify the official historical going source and record-level integrity before introducing going-specific observations.
2. Add a guarded lossless relatives evidence projection, anchored by canonical relative IDs, individual race dates, and source SHA.
3. Define condition-comparable statistical evaluation including overlap de-duplication and temporal train/test separation before claiming pairing/compensation/aptitude.
4. Review PWA editorial wording separately; M6-P remains independent for RaceNote prediction authorization.
