# BRDB PACI common analysis contract v0.1 candidate — 2026-11-19

Status: **RESEARCH CANDIDATE / LOCAL E2E PASS / NOT PRODUCTION AUTHORIZED**.

## Goal

PACI-targeted BRDB produces a **machine-readable field-wide evidence bundle**; RaceNote consumes only prediction-authorized evidence, while a separate editorial formatter produces human-facing pedigree DB reviews and racing Tips for Newspaper PWA. PWA must not analyze, infer or call an LLM at view time.

This candidate **does not implement actual automated discovery, RaceNote scoring, editorial generation, production daily orchestration or deployment**. It gives a narrow adapter contract backed by real M7 Tokyo12R 2026-11-15 data.

## Exact checked private inputs

Private personal Library `/BRDB/M7/` (never commit horse-level data to public Git):

| Input | raw SHA256 |
|---|---|
| `m7_integrated_v03_05265412.json` | `96129fdd70155cea98e07e1a5725116e6d2ade7dc3ee9f8ddf1c8a625655774f` |
| `m7_relatives_detail_candidate.json` | `08ac62bb1305e075aa2e73a6298d9e9211ddadc06eff3fc031b02abd7b042211` |
| `m7_research_consumer_preview.json` | `a86cd81d9b1dd9f0cfb094bc327e2739080da15e6c2c003c7cb15686f2e20a1d` |
| `newspaper_05265412_merged.json` | `2538897a36bd958dab690370469055ea2454929b68d3f85325a1fd075484cba9` |

Preview's `source_sha256` references use **canonical/semantic** digests, not raw source bytes. The v0.3 raw digest and preview integrated-v0.3 semantic digest are intentionally different. Its integrated semantic reference matches detail's `integrated_v03_canonical_sha256` (`eedde393f3aa223e9abab5c8ff214fc017a7949fd7abf80742cc2f2df98df884`). The exact detail canonical digest cannot yet be recomputed without the existing M7 canonical-hash function; candidate tests **do not claim** full canonical-digest verification. **Before formal acceptance this must be resolved** through M7's canonical serializer, without guessing a hash algorithm.

## Measured real-field facts

- `race_key=05265412`, Tokyo turf 2000m, field size 18.
- Joined `(horse_no, eight-digit horse_id)` across integrated v0.3, relative detail, consumer preview and reconstructed merged Newspaper, exactly 18/18, no duplicates.
- M7 v0.3 evidence entries: **435**. D4 supplemental insights: **66**.
- Sire coverage: `AVAILABLE=17`, `LOW_SAMPLE=1`; BMS same.
- Pairing: `AS_OF_UNVERIFIED=18`. Relative lane: `AS_OF_UNVERIFIED=13`, `SOURCE_UNAVAILABLE=5`.
- Detailed relatives: **75 records**, **375** condition observation cells, **285** zero-start cells; 0-start rates stay `null`.
- Source M7 `observations` contains `starts`, `wins`, `top3`, rates and baselines. It **does not provide independent second/third-place counts or win/place ROI** in the integrated evidence model. New contract therefore keeps `seconds`, `thirds`, `out_of_top3`, `win_return_rate`, `place_return_rate` as `null` until separately sourced and verified. Do not turn `starts - top3` into an independently validated `out_of_top3` when the underlying meaning of exclusions is not yet contracted.
- Some integrated horse `pedigree_facts.dam_name` are `null`, while the Newspaper basic contains dam name; candidate reads dam name from exact-matched Newspaper base/basic without guessing.

## Contract structure

`contract_version`, `release_status`, `race`, `as_of_exclusive`, `sources`, `policy`, and `horses[]`.

Each horse:
- Identity: `horse_id`, `horse_no`, `horse_name`.
- `pedigree`: basic parent names plus lineage codes.
- `components.sire|broodmare_sire|pairing|relatives`: source availability and scoped statistical observations.
- `counts`: `starts`, `wins`, `top3`, `unique_horses`; optional finer finishing breakdown (explicit null).
- `rates`: `win_rate`, `top3_rate`; optional returns (explicit null).
- `baseline`: `starts`, `top3_rate`, `top3_delta_pp` (for observed comparative context, not evidence of causal benefit).
- `relatives`: status and coverage counts. Detailed relationship records remain in private source sidecar and require a separately reviewed lossless public-display projection.
- `findings[]`: typed, evidence-linked discoveries. **Empty until detection logic is implemented and evaluated**. Do not invent distances, mud aptitude, country traits or recommendations.

Across all levels preserve `LOW_SAMPLE`, `NO_SAMPLE`, `SOURCE_UNAVAILABLE`, `AS_OF_UNVERIFIED` and research-only flags. Prediction and production authorization remain `false`.

## Separation of concerns

1. **BRDB Engine**: PACI + validated BRDB evidence → all-horse common JSON; computes facts, statistics, candidate patterns, source provenance. No prose, race marks, probability, rank, tips or advice.
2. **RaceNote adapter**: reads only prediction-authorized lanes. Current M7 candidates are not prediction-safe, hence **no integration into RaceNote production scoring**; M6-P remains a separate gate.
3. **Editorial formatter**: review paragraph + detailed grounds + Tips from cited `finding_id` / `evidence_refs` only; low N may be described positively as *observed* but not as proven transferable aptitude.
4. **Newspaper/PWA adapter**: one display projection for each strict canonical horse ID, no inference at runtime. Public deployment requires independent approval and regression of schema issues #2637/#2638.

## Display decisions captured

- ③ father's progeny historical results only. Target exact venue/course/distance and all-JRA same distance preferred; no unrelated all-distances venue rollup. `1st-2nd-3rd-other` is desired, but **unavailable pending upstream extraction**. Win/top3 rates and win/place returns where verified.
- ④ user-facing title `血統DBレビュー`; initial natural-language overall comment, tap to expand evidence by sire, maternal grandsire, pairing and relatives; optional comparator to sire's usual comparable conditions.
- ⑤ relatives details are separate UI data; presentation remains to be finalized.
- ⑥ Tips call attention to discovered relationships, track/weather/roots (only when evidence establishes them). No unvalidated country-root → aptitude shortcut.
- No separate user-facing provenance section ⑦; diagnostics, N, date, availability and SHA remain stored, with minimum relevant N displayed alongside metrics.

## Acceptance and next increments

- Candidate real-field adapter: 18/18 identities, race, temporal flags, no rogue score, schema validation, no source mutation, fail-closed negative checks. Local regression **8/8 PASS**.
- **Before official contract**: confirm canonical SHA routines; verify the retained `evidence_id`, `overlap_group`, and `source_name` links against downstream use; decide 2nd/3rd finish and payoff data source; version scope semantics, zero-start values and native provenance; verify schema against current repo integrations.
- **Before RaceNote**: M6-P empirical improvement / per-lane as-of and prediction authorization; no implicit conversion of `AS_OF_UNVERIFIED`.
- **Before PWA**: review generation with evidence cites, display schema, mobile acceptance, existing Newspaper full-day schema drift fixes and user acceptance.

## Test execution

```bash
python -m unittest -v test_brdb_common_analysis_adapter.py
```

Test fixture is the private local M7 source set; GitHub CI must use synthetic fixtures and must not copy private actual per-horse JSON into the repository.
