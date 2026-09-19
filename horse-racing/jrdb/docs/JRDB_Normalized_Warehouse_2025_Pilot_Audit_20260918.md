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

## UKC duplicate review and lossless policy

The first run stopped before publication because UKC 2025 has duplicate business keys:

| Check | Result |
| --- | --- |
| Source records | 47,239 |
| Canonical key | `horse_id + data_date` |
| Duplicate key groups | 20 |
| Extra rows | 20 |
| Duplicate payloads | All 20 groups are byte-identical Raw records within the same member |

Examples occur in `UKC251213.txt` and `UKC251214.txt`; each duplicate pair has distinct source record ordinals and the same `source_record_sha256`.

No row was dropped and the business key was not changed. The accepted lossless policy is:

- retain `horse_id + data_date` as the UKC business key;
- collapse only rows with the same business key and the same `source_record_sha256`;
- retain every Raw occurrence in `ukc_source_record_lineage`, keyed by archive hash/member/ordinal;
- fail closed if one UKC business key has more than one Raw body hash.

The completed rerun produced 47,219 UKC business rows and 47,239 lineage rows. The lineage audit records 47,219 `CANONICAL` and 20 `EXACT_SOURCE_DUPLICATE` rows.

## ZED/ZKB rolling-snapshot review

The rerun then established that ZED and ZKB are rolling historical snapshots rather than one-row result masters. In the 2025 archives, repeated `result_key` values occur across later delivery members; 1,983 ZED keys and 1,482 ZKB keys contain more than one Raw body hash. `result_key + source_member_date` is unique in both families, so this is the Warehouse grain. This preserves delivery-time corrections without choosing an arbitrary latest row.

The full-history preflight also found BAC correction re-delivery in 2013: 24 race keys were reissued in the next source-member date with a different Raw body hash. BAC therefore uses `race_key_raw + source_member_date` as its Warehouse grain, preserving the correction history without selecting an implicit latest row.

CHA has the same historical delivery behavior (339 runner keys in 2013 and 146 in 2018); its grain is therefore `race_horse_key + source_member_date`.

## Result

`PASS` — local 2025 ten-family generation `pilot-2025-cross-family-v1` completed on 2026-09-19.

All relation audits passed: record-length checks, canonical-key checks, provenance checks and HJC 36-slot expansion. Cross-family checks passed for CHA→KYI, CYB→KYI, SED→KYI, SKB→SED and ZKB→ZED. KYI→BAC reports 53 unmatched race keys as `OBSERVED_SOURCE_GAP` (not fabricated or silently discarded); this is recorded as `SOURCE_CONDITIONAL_CONTEXT` with representative keys in `audit.json`.

This is a local pilot only: no Drive Warehouse publication, `current.json` update, consumer switch, or Raw mutation occurred. The next gates are full 2010–2025 build, Drive upload/re-fetch validation, and only then `current.json` publication.
