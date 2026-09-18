# JRDB Normalized Warehouse 2025 Pilot Audit

## Scope

- Input: canonical `GPT/horse-racing/00_raw` annual ZIPs for BAC, KYI, CHA, CYB, SED, SKB, ZED, ZKB, UKC, and HJC (2025 only)
- Output: local pilot workspace only; no Drive Warehouse publication, `current.json` update, consumer switch, or Raw mutation

## Input verification

- All 10 requested 2025 ZIPs were available from the canonical Raw folders.
- `SED_2025.zip` first arrived truncated (3,186,688 bytes vs Drive metadata 5,859,134 bytes). A single fresh retrieval produced the expected size and passed `unzip -t`.
- The other nine retrieved ZIPs passed ZIP integrity checks.

## Builder verification

- The first run exposed a Python compatibility defect in the temporary Parquet file name (`datetime.timestamp_ns`). It was replaced with `time.time_ns`.
- Builder and all-family fixture tests passed after the correction.

## Fail-closed audit result

The real-data build stopped before publication because UKC 2025 violates the current canonical-key contract:

| Check | Result |
| --- | --- |
| Source records | 47,239 |
| Canonical key | `horse_id + data_date` |
| Duplicate key groups | 20 |
| Extra rows | 20 |
| Duplicate payloads | All 20 groups are byte-identical Raw records within the same member |

Examples occur in `UKC251213.txt` and `UKC251214.txt`; each duplicate pair has distinct source record ordinals and the same `source_record_sha256`.

No row was dropped and the canonical key was not silently changed. The implementation request requires the source delivery structure to be reviewed and the canonical grain or an explicit lossless duplicate policy to be defined before conversion resumes.

## Result

`BLOCKED_BY_UKC_DUPLICATE_GRAIN`

The frozen Raw inventory is complete. The remaining gate is a documented UKC duplicate-handling decision; after that, rerun this same 2025 ten-family pilot before any full historical build.
