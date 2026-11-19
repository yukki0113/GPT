# JPDB P1.2 — 2026 daily SED + historical Reader validation record (2026-11-19)

**Current disposition (2026-11-19): P1.2 REAL COMBINED E2E PASS (read-only source/Reader acceptance).** This document preserves the original earlier OPEN gate below as historical audit context; its resolution is the addendum at the end. This separation is mandatory; do not relabel tests using synthetic 2026 as genuine 2026 historical results.

## Inventory / licensed-source read-only evidence

2026 canonical Drive `00_raw/SED` folder `1mm6sU8-skS7K2XYHm2citcorUVyMyL58`, 2026 PACI canonical folder `1zFajenPU5jxInZCcmqZzkgiaYil3MD8r`:

| Check | Observed |
|---|---|
| SED ZIP objects with `SED26xxxx.zip` names | 106 |
| Distinct 2026 SED race dates | 97 |
| 2026 PACI race dates | 97 |
| Date set mismatches (PACI-only / SED-only) | **0 / 0** |
| Duplicate SED filename dates | **9** |
| Duplicate SED pairs whose SED member bytes matched | 5 |
| Duplicate SED pairs whose SED member bytes differed | **4** |
| Differing pairs | `2026-08-30`, `2026-09-05`, `2026-10-10`, `2026-10-11` |
| Date span | 2026-01-04 to 2026-11-15 |

All **97 selected current Drive versions** were materialized *only* into a private runtime directory via the native Drive connector. Selection used the later Drive `modified_time` per duplicate date, and each chosen ZIP byte identity was pinned by SHA-256 and expected size. They were not uploaded, republished, or modified on Drive.

| Private read-only Raw integrity | Result |
|---|---|
| ZIP CRC, SED member selection, SED member SHA, fixed record length | **97 / 97 PASS** |
| Total SED result records | **42,185** |
| Flat records (surface 1 and 2) | **40,945** |
| Obstacle records | **1,240** |
| Abnormal code counts | `0=41,869`; `1=50`; `2=98`; `3=168` |
| Malformed result dates / five-digit jockey code / duplicate runner keys | **0 / 0 / 0** |
| Selected ZIP total bytes | **5,014,439** |
| Manifest schema | `jpdb-p12-daily-sed-pinned-v1` |
| SHA-256 of private 97-source pinned manifest | `9e9a44349596a430b0ca87956d8ad362c224dad1a77a2da70beabd4b5d1e5484` |
| SHA-256 of private aggregate-only audit | `78a81a08c96716d5d16f0805ba5a5f0175277a1ff18ec548f55ae26efbeb8960` |

Drive inventory selected object IDs/duplicate evidence are committed in `docs/evidence/jpdb_p12_2026_sed_drive_inventory_20261119.json` (**metadata only**). The licensed source ZIPs themselves are not committed. The private pinned manifest plus aggregate-only JSON report are packaged in the conversation artifact `jpdb-p12-source-evidence-20261119.zip`. Its ZIP SHA256 is `3b729e71cc7302b2d3ebb2ff9abf1f53dff332f589feaf8f136060098663efa1`.

## Source code and real-historical/synthetic-2026 integration

- P1.2 implementation: `src/jpdb_performance_reader_v12.py`, class `JPDBPerformanceReader2026`. It inherits P1.1, uses the canonical `jrdb_raw.Parser.sed`, validates all daily ZIP SHA, SED member SHA, day/count and identity, then defines a unified in-memory DuckDB `sed_all` view on three accepted historical Parquet years plus 2026 selected daily result rows.
- Existing P1.1 `_grouped` gained a **default-preserving optional date-validator injection**. Existing P1.1 and v0.1 callers retain their 2023–2025 time limits and response contracts.
- **GitHub [Issue #2653](https://github.com/yukki0113/GPT/issues/2653), [Actions run 44437846305](https://github.com/yukki0113/GPT/actions/runs/44437846305) SUCCESS**, read-only fallback, tested pinned repo commit `473f742793895133d7baab65bf0e300f8e2ee395`; [artifact 14488499620](https://github.com/yukki0113/GPT/actions/runs/44437846305/artifacts/14488499620).
- Three deterministic steps exit 0 (DuckDB 1.1.3, PyArrow 25.0.1). `tests/test_jpdb_performance_reader_v12.py` **4/4 PASS**, with accepted actual 2023–2025 immutable Parquet input plus synthetic 2026 ZIP fixtures. It verifies same-day exclusion, the year transition, no change in 2025 historical output, expected 2026 incremental counts, CRC/hash/missing-day/record-date fail-closed behavior, and stale/unsupported date rejection.
- `tests/test_jpdb_performance_reader_v11.py` **4/4 PASS**; `tests/test_jpdb_history_reader.py` **4/4 PASS**. All historical public read-only input receipts **9/9 verified**; no real licensed 2026 source ZIP passed to Actions.
- **12/12 regression tests PASS** in total. Historical inputs are real, 2026 test fixtures are synthetic.

## Pending acceptance gate

**The exact P1.2 integrated DuckDB Reader has NOT been run against the real 97 daily 2026 SED ZIPs and real annual historical Parquet inputs simultaneously.** Private daily SED may only be transported through native Drive to an approved runtime; current model-side container has no DuckDB/PyArrow, dependency repair from ordinary pip was blocked; repository policy prohibits inserting licensed daily Raw via GitHub Actions private Drive/API or committing its records to GitHub. Hence private raw audit PASS and synthetic E2E PASS are independently valid, but do **not** certify full real combined query correctness.

Further acceptance requires an approved DuckDB-capable local/native execution context that can hold the exact SHA-pinned private daily ZIPs *and* SHA-pinned historic Parquet sources, rerun the Reader, independently compare 2025/2026 boundary counts and several representative 2026 rider/date queries with source SQL. Until then mark production **P1.2 REAL COMBINED E2E = REVIEW_REQUIRED** and keep RaceNote P4 separate.

- Not addressed: full official `abnormal_code=5` denominator policy in 2023–2025, RaceNote pre-race rider roster, 2026 future update automation, prediction weights, PWA, Freeze.
- Historical SED availability remains the approved `JPDB_SED_PRIOR_DAY_ASSUMED_AVAILABLE_V1` assumption; no 2026 row with `race_date>=target_date` can be used in an actual target-day aggregate.


## Final real-source combined E2E — acceptance addendum (2026-11-19)

The previously OPEN gate above has now been **RESOLVED: PASS**. An approved native GPT container independently materialized all 97 exact selected real 2026 SED ZIPs through connected Drive, plus three SHA-validated accepted real 2023–2025 SED Parquet partitions. Actions [run 44449287458](https://github.com/yukki0113/GPT/actions/runs/44449287458) exported the fixed DuckDB 1.1.3 CPython 3.13 wheel; [run 44449380252](https://github.com/yukki0113/GPT/actions/runs/44449380252) exported the exact repository implementation and test source at `57c53cd58e88602ca9b38bcd09c021a5aa90ec45`. **Only open-source wheel and repository code** were transported by Actions; licensed ZIP and Parquet source bytes remained in native/private local runtime.

- Original-source evidence cross-check: 97 ZIPs / 5,014,439 bytes; CRC 97/97; 42,185 records (40,945 flat + 1,240 obstacle), agreeing with the earlier private Raw audit. A fresh locally byte-pinned daily manifest was constructed from these selected ZIPs, SHA256 `0dd1b2ce68ba1b00ea36820dd11481d527468bbea518141349d181cf6350cdeb`. This is a **new serialization/pin**, not a claim that the original private manifest SHA `9e9a...` is unchanged.
- The exact `JPDBPerformanceReader2026` joined real historic Parquet 142,737 rows and 2026 real ZIP 42,185 rows using DuckDB **1.1.3** in Python 3.13.5. The full view contains **184,922 rows**; source date overlap **0**, cross-source runner-key collisions **0**.
- An independent conditional-SUM SQL comparison, without using the P1.1 aggregate query, matched **288 rider×period×surface cells** for **12 actual rider IDs** and targets **2026-01-04, 2026-06-13, 2026-11-15, 2026-11-16**. Three windows (3 years, 365 days, 90 days) and all outcome categories were compared; no target-day leakage was observed.
- P1.1 2025 window outputs were identical to the integrated Reader; local P1.2 synthetic suite **4/4 PASS**. The real combined E2E audit was run twice with byte-identical aggregate-only JSON receipt SHA256 `beb4a65a909079f61d559fd75a4cdc3bf124890bbcace1a9c4a399e4be6e072b`.
- Machine-readable public audit (counts/hashes/status only, no licensed source rows): [`docs/evidence/jpdb_p12_real_combined_e2e_20261119.json`](evidence/jpdb_p12_real_combined_e2e_20261119.json).

**Scope of PASS:** P1.2 implementation and fixed 2026 snapshot real-source integrated read-only E2E. **Not certified:** strict historical publication time (approved as-of assumption remains), 2026 automatic refresh/CURRENT, P2/P3 model effects, P4 RaceNote integration, or official abnormal code=5 denominator resolution. Previously recorded limitations about the old managed runtime describe the *earlier attempt* and are no longer the current E2E disposition.
