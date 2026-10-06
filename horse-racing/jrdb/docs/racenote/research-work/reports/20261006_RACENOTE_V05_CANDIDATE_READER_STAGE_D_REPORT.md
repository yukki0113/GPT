# RaceNote 0.5.0 Candidate Reader — Stage D Report

Date: 2026-10-06  
Base: main `b740d9db27960981ff90e5b500cf3edb82a26aa6`  
Decision: **READY_FOR_CLEAN_BLIND_A_B**

## Implemented

| Deliverable | Path |
|---|---|
| Candidate specification | `docs/racenote/FORECAST_HUMAN_CONTEXT_READER_v0_5_0_CANDIDATE.md` |
| 73-row implementation binding | `config/racenote_reader_v050_binding.json` |
| Deterministic candidate transformer | `src/racenote_reader_v050.py` |
| Structural tests | `tests/test_racenote_reader_v050.py` |
| This report | `docs/racenote/research-work/reports/20261006_RACENOTE_V05_CANDIDATE_READER_STAGE_D_REPORT.md` |

The explicit identity is `RaceNote-Human-Context-Reader-0.5.0-candidate`. The transformer accepts the existing clean Reader View v0.1 JSON and uses its normalized paths. It does not fork evidence extraction, call prediction code, or change the current pointer. A direct CLI invocation writes compact deterministic JSON. The Stage C policy can be passed to validate the 73-row binding before transformation.

## Policy coverage and structural rules

All **73/73** Stage C entries bind to source paths and presentation behavior: 3 PRIMARY, 18 SECONDARY, 34 CONTEXT_ONLY, 17 REDUNDANT_HIDDEN, 1 INSUFFICIENT_COVERAGE. Ambiguous Stage C parent paths for CHA workout and CYB analysis details are bound to specific normalized leaves. Present source values are accounted for exactly once in normal evidence or provenance. Hidden values never appear in normal evidence. Non-policy clean runner evidence remains in `other_context`; shared statistical context remains in normal view. Source metadata is retained in provenance.

The transformer records absent, explicit null and empty-string source states separately. It never derives a provider rank, suitability default or CHA/CYB replacement. A non-equal CHA total/CYB training pair generates a divergence note with both values. The normal view groups ability, pace/position, training/condition, suitability and connections, with P/S/C tier markers. Its provenance sidecar records source family, source path, value, reason and primary representation. CONTEXT_ONLY defaults to detail even when populated. The explicit normal-view gates are jockey index and CYB training index (required normal representations), race-distance fit, surface-matched turf/dirt fit, heavy-track fit in a heavy race condition, and JRDB class when race class is known.

## Structural comparison

Fixture source: committed, market-blind files under `backtests/BTDAY-0048/20260207/forecast_prep/reader/`. Only these clean Reader inputs were opened; target results were not opened. The input was the same v0.4.6 clean Reader View passed to the candidate. Counts use compact UTF-8 JSON with sorted keys and no extra whitespace. Approximate tokens are `ceil(UTF-8 bytes / 4)`; this deterministic approximation is **not** a tokenizer measurement. Normal bytes exclude the provenance sidecar; full bytes include it.

| Clean fixture | Runners | v0.4.6 bytes / approx tokens | v0.5 normal bytes / approx tokens | v0.5 full bytes / approx tokens | Normal scalar fields | Detail fields | Duplicates removed from normal |
|---|---:|---:|---:|---:|---:|---:|---:|
| 東京1R | 16 | 194,546 / 48,637 | 181,930 / 45,483 | 337,610 / 84,403 | 378 | 639 | 199 |
| 京都11R | 16 | 305,026 / 76,257 | 293,232 / 73,308 | 446,087 / 111,522 | 412 | 646 | 199 |
| 小倉12R | 18 | 313,119 / 78,280 | 300,056 / 75,014 | 470,342 / 117,586 | 460 | 709 | 218 |

Normal-view byte reductions are **12,616 (6.48%)**, **11,794 (3.87%)** and **13,063 (4.17%)**, respectively. The full artifact grows because per-field provenance and missingness states are explicit. Every tested normal view retains BAC race context and KYI, CHA and CYB policy families. The synthetic all-present test verifies that every Stage C-required source value lands in exactly one normal or detail location; no unique Stage C-required value is discarded. These measurements are structural, not prediction-quality or model-behavior results.

## Validation

`python -m unittest horse-racing/jrdb/tests/test_racenote_reader_v050.py -q`: **9 tests passed**. Checks cover the 73-entry policy, duplicate suppression, default hiding of populated non-fit CONTEXT_ONLY fields with detail recovery, explicit missingness, CHA/CYB divergence, surface-conditional fit, target market/result rejection, explicit version identity, current-pointer separation, v0.4.6 byte/semantic non-regression on the same input, and integration with a committed clean Reader fixture.

The local copies of `src/racenote_reader_view.py`, the current pointer and the committed Tokyo fixture were checked against main by Git blob hash before testing. No active Reader or production file is changed by this PR.

## Limits and next step

The normal-view reduction is moderate because the large history and race-context evidence remains available. The full provenance sidecar is larger; an A/B runner must avoid feeding it as an independent second evidence view. Only the stated deterministic context gates are enabled; future context exposure requires an explicit binding/rule change and another structural review. The candidate has not been reviewed for prediction effect. Historical past-run results inside the already clean Reader remain historical context; target results, market and payouts are blocked.

**Next:** perform a separately authorized prospective clean-blind A/B using the same pre-race evidence for v0.4.6 and this 0.5.0 candidate. Freeze both authored decisions before opening target results or market. Compare prediction behavior and Reader usability in a later audit; do not promote the current pointer in Stage D.

Production impact: **zero**.
