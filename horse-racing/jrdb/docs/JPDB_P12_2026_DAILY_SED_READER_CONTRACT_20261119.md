# JPDB P1.2 — 2026 daily SED extension to historical Reader

Date: 2026-11-19. Status **IMPLEMENTED CANDIDATE / synthetic full-Reader PASS, real daily Raw integrity PASS; actual 97-file full DuckDB joined replay NOT YET EXECUTED.**

## Source of truth / observed inventory

- Existing 2023–2025 accepted Warehouse: `jrdb_normalized_warehouse_v1_2010_2025_g20261118_bacfix`. Existing SHA-pinned manifest `config/public_drive/jpdb_p0_current_2023_2025_readonly_v0_1.json`. SED three partitions **142,737** rows. 2025/2026 are **disjoint by race_date**.
- Current native Drive 2026 daily SED folder `1mm6sU8-skS7K2XYHm2citcorUVyMyL58`, daily `SEDyymmdd.zip`. Native PACI folder `1zFajenPU5jxInZCcmqZzkgiaYil3MD8r`.
- Direct native folder inventory showed **106 SED ZIP objects for 97 distinct dates** from **2026-01-04** to **2026-11-15**, plus legacy annual ZIPs. Direct PACI inventory showed **97/97 matching 2026 dates**, with zero PACI-only or SED-only dates. This is the *observed current snapshot*, not a promise of future availability or a license to re-fetch JRDB automatically.
- **Nine filenames have two Drive objects**. The selected candidate is the object with the later `modified_time` from that exact native folder inventory, then its actual bytes were fetched and SHA pinned. Comparison of SED ZIP members: five duplicate pairs had *identical* SED bytes, while four dates had **different** SED bytes (**2026-08-30, 2026-09-05, 2026-10-10, 2026-10-11**). Do not count both objects. The selection is consistent with the user-approved *accepted finalized SED* proxy; it is not an observed historical first release.
- Inventory with exact 97 selected Drive file IDs, sizes, modification times and nine duplicates: `docs/evidence/jpdb_p12_2026_sed_drive_inventory_20261119.json`. This is snapshot evidence, **not** a long-term runtime requirement to hardcode Drive object IDs.
- All 97 *selected* actual ZIPs were fetched via the **native Google Drive connector**, and validated in a local private execution directory (without uploading original licensed ZIP bytes to GitHub): **97/97 ZIP CRC, SED member/length, member hash and ZIP hash PASS**. Parsed SED fixed-size record slots: **42,185**. Independent audit-only checks of source dates, SED rider-code shape and `race_key_raw × horse_no` duplicates all **0 errors**. Of these records **40,945 flat**, **1,240 obstacle**. Abnormal code distribution 2026: `0=41,869`, `1=50`, `2=98`, `3=168`; no `5` in this snapshot.
- Local reproducibility artifact: `jpdb_p12_2026_daily_pinned_manifest.json` includes each chosen ZIP and SED-member SHA256, byte size, expected row count and all 97 dates. Exact manifest SHA256: `9e9a44349596a430b0ca87956d8ad362c224dad1a77a2da70beabd4b5d1e5484`. The companion aggregate-only audit SHA256: `78a81a08c96716d5d16f0805ba5a5f0175277a1ff18ec548f55ae26efbeb8960`. The files are available as a conversation artifact, not required to be committed as source rows.
- Manifest must be repinned if any canonical Drive SED object changes on a subsequent refresh. No automatic upload, Drive mutation, PWA or RaceNote publication is in this P1.2.

## Reader implementation

`src/jpdb_performance_reader_v12.py` exposes `JPDBPerformanceReader2026(JPDBPerformanceReader)`.

Constructor requires:
- `input_root`, `manifest`: existing historical Parquet root and SHA-pinned manifest.
- `daily_root`, `daily_manifest`: verified local selected 2026 daily ZIP root and frozen versioned manifest. Optional `expected_daily_manifest_sha256` adds explicit manifest pin.
- No Drive API inside Python. Resolve/download/verify the canonical Drive assets with the native connector before invoking this code.

Processing:
1. Existing `JPDBPerformanceReader` verifies three immutable 2023–2025 annual SED Parquet SHA/sizes, year counts and identity.
2. Validate `daily_manifest` schema `jpdb-p12-daily-sed-pinned-v1`, same approved source policy, strict sorted unique 2026 `race_date` and `expected_race_dates` (audited PACI calendar); reject missing or extra local ZIPs and incorrect selected date/name/size/SHA.
3. For every 2026 ZIP: verify ZIP SHA, `testzip()`, unique exact `SEDyymmdd.txt` member, SED-member SHA, record alignment/count. Decode exclusively with canonical `jrdb_raw.Parser.sed` and `ymd`; fail for date mismatch, invalid jockey ID, duplicate `(race_key_raw,horse_no)`, unrecognized source identity. **Do not implement JRDB byte offsets again in JPDB.**
4. Materialize an eight-column read-only projection in a DuckDB in-memory table `sed_2026` (temporary private CSV loader is deleted after COPY); historical table remains SHA-validated. Reject duplicated keys between 2025-and-earlier and 2026. Define `sed_all = sed_historical UNION ALL BY NAME sed_2026`. No source file is modified.
5. `rider_histories(target_date=D,jockey_codes=[...])` calls the same existing P1.1 parameterized batch GROUP BY (3y/365d/90d, flat/turf/dirt), with a P1.2 year-aware validator. **Every historical row has `race_date < D`**, so 2026 data cannot enter 2025 replay, and no 2026 target day data enters its own prediction.
6. Restrict 2026 target dates to year 2026 and **at most seven calendar days after** the final SED day in the pinned manifest; this is a preliminary explicit freshness safeguard. Beyond it, a new Drive inventory/snapshot is required, rather than returning a silently stale history.
7. Output `schema_version=jpdb-performance-reader-v1.2-candidate`, composite generation ID, original 2023–2025 source SHA receipts, 2026 manifest SHA, 2026 97-date/42,185-row receipts, source coverage end and `asof_policy=JPDB_SED_PRIOR_DAY_ASSUMED_AVAILABLE_V1`. Original P1.1 / v0.1 classes retain existing APIs and date checks.

## Tests / evidence boundary

- P1.2 focused synthetic ZIP plus **real historic 2023–2025 Parquet** integration test: `tests/test_jpdb_performance_reader_v12.py`.
- Existing P1.1 and v0.1 synthetic tests remain in the regression contract.
- Actual 97 daily SED files have independently passed **raw-byte inventory/record/key/date integrity** in the private local execution boundary. **Important remaining gate**: the exact combined Reader has not been executed against all 97 actual proprietary ZIPs and three actual historical Parquet partitions in the same DuckDB runtime, because that licensed daily dataset is private and the current local Python environment lacks DuckDB, while the GitHub Actions fallback is deliberately restricted to approved public read-only inputs. A synthetic E2E + a separately validated raw snapshot must not be presented as actual full real-source Reader E2E.
- Never move private/licensed daily SED source rows to a public GitHub Issue/Actions artifact. If later a DuckDB-capable native connected local environment becomes available, rerun the pinned 97-ZIP manifest with the accepted historical partitions, compare 2025/2026 boundary on actual keys/counts, and record PASS as a separate audit.

## Usage

```python
from jpdb_performance_reader_v12 import JPDBPerformanceReader2026

with JPDBPerformanceReader2026(
  input_root=verified_2023_2025_parquet,
  manifest=accepted_historical_manifest,
  daily_root=private_selected_2026_zip_folder,
  daily_manifest=private_2026_pinned_manifest,
  expected_daily_manifest_sha256="9e9a44349596a430b0ca87956d8ad362c224dad1a77a2da70beabd4b5d1e5484",
) as reader:
    response=reader.rider_histories(
        target_date="2026-11-15",
        jockey_codes=["01234","12345"],
    )
```

Codes in the example are placeholders, not validated target PACI rider IDs. Reader does not resolve the day's planned jockey. `FINAL_KYI_PROXY` and `OBSERVED_PRE_RACE_PACI` remain distinct source labels and must be implemented in P4 separately.

**No production RaceNote, PWA, predictions, Freeze or canonical Drive content was changed.**
