# JPDB P1.1 — Historical batch Reader validation (2026-11-19)

**Result: P1.1 Candidate implementation / focused verification PASS; official start-denominator acceptance REVIEW_REQUIRED.** RaceNote and CURRENT were not changed.

## Exact source / execution

- Repaired and accepted historical Warehouse generation: `jrdb_normalized_warehouse_v1_2010_2025_g20261118_bacfix`.
- Source SED: 2023 `47,672`, 2024 `47,181`, 2025 `47,884` = **142,737** all-surface entries; **138,491** flat entries. All nine pinned public Drive inputs verified in the runner; new Reader verifies the three immutable SED Parquet hashes and sizes again.
- [GitHub Issue #2652](https://github.com/yukki0113/GPT/issues/2652) and [Actions run 44434809478](https://github.com/yukki0113/GPT/actions/runs/44434809478): **SUCCESS** / read-only DuckDB 1.1.3, Python 3.12.16, PyArrow 25.0.1.
- Artifact: [`data-storage-fallback-44434809478`](https://github.com/yukki0113/GPT/actions/runs/44434809478/artifacts/14488936260).
- Reproducible source commit at test: `14e6639f721cee1659a7833405dc18e82c54aed2`.
- Aggregate-only `output/jpdb_p11_performance_smoke_20261119.json` SHA256 `c1334896ffd07274fba02651310d03bdf49526287f984cc29b121fa700c572a6`, 807 bytes. Fallback audit SHA256 `df260b21d7aead404f37224743c9d8ce981e2c0d4b5866ab8cdba53621f7dc27`. No licensed individual jockey/race rows or rider IDs in artifact.

## Verification results

| Check | Evidence | Result |
|---|---|---|
| P1.1 synthetic `test_jpdb_performance_reader_v11.py` | 4 tests; exclusions, classification, 90/365-day windows, zero history, code validation | PASS |
| Original v0.1 regression `test_jpdb_history_reader.py` | 4 tests, unchanged original `rider_history()` behavior | PASS |
| Actual SED batch result | 12 jockey codes chosen only inside controlled runtime | 12 / 12 independent SQL match |
| Real input covered by 12-rider smoke | 27,233 historical flat source entries at D=2025-11-15 | PASS |
| Source start | 2023-01-01 returns NO_HISTORY for all selected riders | PASS |
| Target day exclusion | D=2025-11-15; no D or later races ingested | PASS |
| Actual flat SED unknown abnormal code | **0** | PASS |
| Actual flat SED malformed normal-finish records | **0** | PASS |
| Actual flat SED demotion code `5` | **1** | **Explicit REVIEW category** |
| Historical source availability | `JPDB_SED_PRIOR_DAY_ASSUMED_AVAILABLE_V1` | **ASSUMPTION**, not independently attested |

The new P1.1 class `JPDBPerformanceReader` inherits old `JPDBHistoryReader` and adds `rider_histories(target_date, jockey_codes)`. Three periods (`ROLLING_3Y`, `RECENT_365D`, `RECENT_90D`) are aggregated in three **batch** GROUP BY queries, not per jockey. Every cell includes mutually exclusive abnormal classification and surface identity. 64-code request bound; duplicates fail closed.

## Denominator decision / limits

- The output `population_filter_id=JPDB_FLAT_RIDE_START_V1_CANDIDATE` is **not** the approved official win-rate population. `actual_starts_candidate = normal_finishers + dnf + demotion_review`, but `demotion_review > 0` causes `start_basis_*_rate_candidate=null` and `start_rate_status=REVIEW_REQUIRED`. Likewise unknown codes and invalid normal finishing times/positions prevent rate promotion. Do not silently assign demotion as win/loss.
- Other cells with zero unresolved records may have candidate win/top3 rates; these remain `CANDIDATE_ONLY` rather than certified rider probabilities or ability scores.
- `sample_support_status` uses <30 starts as an **experimental descriptive** threshold, not a confidence/selection recommendation. No Wilson intervals, P2 condition analysis or P3 ability correction implemented here.
- Reader history is strictly earlier than target D, and inherited source is the approved **prior-day availability assumption**, not exact historical revision replay.
- No source writes, RaceNote/PWA integration, prediction score or 2026 YTD source. P1.2 still needs accepted daily 2026 SED and boundary validation.

**Disposition:** P1.1 code, batch API, CORE diagnostic and source validation **PASS**. The single abnormal `5` policy remains consciously unresolved for final official start-basis percentage; downstream feature use must recognize `CANDIDATE_ONLY` and `REVIEW_REQUIRED`.
