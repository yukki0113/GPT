# JPDB historical rider Reader v0.1 — implementation and validation (2026-11-19)

**Disposition: Reader candidate and read-only historical input verification PASS.**
No RaceNote production integration, P2/P3 ability modeling or 2026 incremental history enabled.

## Scope and source

- Implementation: `src/jpdb_history_reader.py` (`JPDBHistoryReader.rider_history(target_date, jockey_code)`).
- Tested immutable repaired Warehouse generation `jrdb_normalized_warehouse_v1_2010_2025_g20261118_bacfix`, SED 2023–2025 (47,672 + 47,181 + 47,884 = **142,737** source entries).
- Source transport: read-only, exact manifest `config/public_drive/jpdb_p0_current_2023_2025_readonly_v0_1.json`, source manifest SHA-256 `292100c9231b482180fba44f94870331b6a3202900c9ed7647ca222726851902`; independent fetch verified **9/9** inputs and Reader reverified three SED source SHA-256 values and sizes.
- User-approved SED historical policy: `JPDB_SED_PRIOR_DAY_ASSUMED_AVAILABLE_V1` (accepted final SED for events strictly before D presumed available at D). This is **not** contemporaneous publication/revision attestation.
- Diagnostic population: `JPDB_FLAT_NORMAL_FINISHERS_DIAGNOSTIC_V1`; results split all flat, turf, dirt; outcomes `0` normal, `1/2` nonstarter, `3` DNF, `5` demotion. Rates use *normal finishers* as denominator and remain diagnostic until formally reviewed.

## Verified runner

- [GitHub Issue #2651](https://github.com/yukki0113/GPT/issues/2651) — read-only fallback verification.
- [Actions run 44430147955](https://github.com/yukki0113/GPT/actions/runs/44430147955) — **success**, both Python steps exit 0.
- [Artifact 14486211786](https://github.com/yukki0113/GPT/actions/runs/44430147955/artifacts/14486211786), `data-storage-fallback-44430147955`.
- Code snapshot used in Actions: `f51ad817e8bdcad74e3781b45c0de64fcc7861b2`; DuckDB 1.1.3.
- Synthetic `tests/test_jpdb_history_reader.py`: **4/4 PASS**. Tests verify target-day/future exclusions, obstacle exclusion, nonstarter/DNF/demotion classifications, per-surface sum, zero-history null-rate behavior, invalid date/code rejection and availability-policy labels.
- Actual `tools/jpdb_history_reader_smoke.py`: **PASS**. Twelve distinct jockey codes were selected internally from the real accepted SED, and independently parameterized SQL reproduced Reader `entries`, `normal_finishes`, `wins` and `top3` for all **12/12**, without publishing individual jockey IDs or licensed horse records.
- The twelve test jockeys together cover **27,233** historical flat source entries for target **2025-11-15**; no date D or later entered any response. Boundary target 2023-01-01 returns `NO_HISTORY` and 0 entries.
- Immutable aggregate-only output `output/jpdb_reader_smoke_20261119.json` SHA-256 `87cc56fcc8baebed9948ead5e120dbd7ae7b747f24cd88decf722ba9096bc2d4`.

## Result and limits

- **PASS**: selected rider/date queries against validated actual historical Parquet, 1-to-1 verification on twelve source jockey codes, strict `race_date < D` and 2023 lower bound, stable source SHA receipt, explanatory output statuses.
- **Not proven**: specific SED revision actually published by historical T. Explicitly approved assumption means this is not a blocker to *assumption-based* JPDB backtesting, but results must state `release_time_attested=false`.
- **Not included**: target-race KYI/PACI jockey roster, 2026 SED YTD, official race-day substitution labels, opponent quality, per-course skill and population-filter final approval. This Reader does not connect to RaceNote and cannot be promoted as a production-only result merely because this focused test passed.
- See [JPDB_HISTORY_READER_V0_1_CONTRACT_20261119.md](JPDB_HISTORY_READER_V0_1_CONTRACT_20261119.md) for interface/CLI details.

**Next approved design decisions needed before RaceNote P4 consumption:** (1) source adapter for the target's candidate jockey-code roster, preserving `FINAL_KYI_PROXY` vs observed PACI; (2) freeze metric denominators/minimum sample support; (3) 2026 YTD append strategy. The Reader module itself and tests are committed; existing RaceNote interfaces were not touched.
