# JRDB Historical Warehouse — BAC 2025 accepted successor promotion

- Date: 2026-11-18 JST
- User decision: **Keep one active Warehouse CURRENT** instead of maintaining a JPDB-only BAC overlay.
- Outcome: **CURRENT promotion complete, Drive readback PASS**.
- Canonical Drive CURRENT: `GPT/horse-racing/10_warehouse/jrdb/v1/current.json`, file ID `1uB0IQecWNKNn_ASZx4_0MhlWNXUmFrYA`.
- Canonical new generation ID: `jrdb_normalized_warehouse_v1_2010_2025_g20261118_bacfix`.
- Previous accepted generation (immutable, retained for audit/rollback, **not active CURRENT**): `jrdb_normalized_warehouse_v1_2010_2025_g20260921`.

## 1. Recovery and 2025 partition rebuild

The annual `BAC_2025.zip` was re-fetched through the existing authenticated JRDB workflow: [annual run 44255757100](https://github.com/yukki0113/GPT/actions/runs/44255757100), Issue [#2642](https://github.com/yukki0113/GPT/issues/2642). Its SHA256 `aeab5d807c12640b908152eb24249c872b4aaafcfc7e97baaafda440994c5491` exactly matched the original canonical annual archive.

Two missing daily BAC sources were already re-fetched through [run 44250027970](https://github.com/yukki0113/GPT/actions/runs/44250027970) ([Issue #2641](https://github.com/yukki0113/GPT/issues/2641)), independently checked as 36 races each.

A dedicated **Actions-Native** deterministic job [run 44256139418](https://github.com/yukki0113/GPT/actions/runs/44256139418), [Issue #2644](https://github.com/yukki0113/GPT/issues/2644), used:
- repository `horse-racing/jrdb/tools/repair_2025_bac_warehouse_partition.py`;
- authoritative `jrdb_raw.py`, `jrdb_warehouse_normalize.py`, `build_jrdb_normalized_warehouse.py`;
- shared `tools/data-storage/` PyArrow + DuckDB;
- original 109-day annual BAC plus complete replacements for only 2025-12-13/14;
- explicit source SHA checks, row counts and duplicate race-key checks.

Output Parquet:
- `objects/bac/year=2025/b26a364978143fbd6e9d30289db0eb85e9b33e9fe612759b23a85ffbb78a3bb9.parquet`
- SHA256: `b26a364978143fbd6e9d30289db0eb85e9b33e9fe612759b23a85ffbb78a3bb9`
- Size: **171,165 bytes**
- Rows: **3,455** (previously **3,402**; exactly 53 restored)
- Schema hash unchanged: `4adf70bd4114bfaace40872fc46704c5fa9f6f259dd943ce3dcf98a66e44ff90`
- Original raw 109 member count unchanged; 107 daily members untouched, 2 replaced.
- Stored in existing BAC content-addressed object folder (alongside, not overwriting old object), Drive ID `1nvDnqBnv69KdMgH200lqOEg6E2VTNtpX`.
- **Verified after native Drive upload by re-fetch and SHA match**.

## 2. Immutable generation successor and checks

The previous accepted final manifest + audit + CURRENT were fetched and their contract SHA was verified:
- 192 assets, exactly 10 families, canonical key and year coverage for all relations 2010–2025.
- Parent final manifest SHA (semantic canonical JSON): `a25cedfb5d76c1f9f2ed65308181e2f5222f294ee8015f93aabe3771fb7f1087`.
- Parent final audit SHA (semantic canonical JSON): `fafcdc9eb4966391fa9e075bc425be46011a69f5c89ab6f1855af3d7ce883c6f`.

A **single-partition accepted successor** was generated, not an in-place mutation of the predecessor. Only `bac/year=2025` asset was replaced. The other **191 immutable Parquet references remain byte-identical**. The BAC family reference contains an explicit `staging_partition_override`; the final manifest has `successor_lineage`, preventing false claims that the prior BAC staging manifest contains the repair asset. The predecessor BAC staging manifest/audit were not overwritten.

Validation before promotion:
- New family set: 10; assets: 192; unique object references: 192.
- Each relation continues to span all 16 annual partitions; canonical-key/provenance schema checks pass.
- New BAC schema and canonical key equal previous `bac/year=2025` values.
- New BAC Parquet byte SHA matches the file fetched back from Drive.
- 2025 KYI/SED race-key coverage **3,455/3,455** from the preceding raw-source P0 audit, and the repaired BAC archive contains exactly those 3,455 keys.
- New final manifest SHA (semantic canonical JSON): `174eaf459f56eb1afe55bc157a2dcf0226a212bf6c00ba062ce5a3e641b2a269`.
- New final audit SHA (semantic canonical JSON): `a94d0a4ab45b2b861c0de47c624ff7cb773b0ef354db933688960d0cee4282c9`.
- Final generation manifest/audit/current all uploaded and **read back byte-identical** to locally validated output.

Generation:
- [Immutable generation folder](https://drive.google.com/drive/folders/1AD9vCXasr5Gs1bCbfjkFpGO52i2nprJn)
- [manifest.json](https://drive.google.com/file/d/1dAqJf4qie3y3LEX_cfU8uxOzI7kj2AXq/view)
- [audit.json](https://drive.google.com/file/d/1P1AteKFYE5N2ykrESHMb4Jm9M6ESBNsw/view)
- New generation-local [current.json](https://drive.google.com/file/d/1mItdtGIpRVBd6NmRzFapIFM51eOyDJlz/view)

## 3. Single active CURRENT cutover

**Updated the existing canonical CURRENT file in place** via native Google Drive connector (preserving file ID `1uB0IQecWNKNn_ASZx4_0MhlWNXUmFrYA`). Its new content has:
- `status=accepted`
- `generation_id=jrdb_normalized_warehouse_v1_2010_2025_g20261118_bacfix`
- `manifest=generations/jrdb_normalized_warehouse_v1_2010_2025_g20261118_bacfix/manifest.json`
- `audit=generations/jrdb_normalized_warehouse_v1_2010_2025_g20261118_bacfix/audit.json`
- `manifest_sha256=174eaf459f56eb1afe55bc157a2dcf0226a212bf6c00ba062ce5a3e641b2a269`
- `final_audit_sha256=a94d0a4ab45b2b861c0de47c624ff7cb773b0ef354db933688960d0cee4282c9`

Post-cutover: retrieved the **same canonical CURRENT file ID** from Drive, and the downloaded 627-byte content was byte-identical to the validated new pointer (SHA256 `12dc312ce0f5ecb2aabfdda3abe77793941e430ad308f4aecaedaa3e7a816a35`). **CURRENT promotion PASS**.

## 4. Routing and non-targets

- The single authoritative active Warehouse entrypoint is `jrdb/v1/current.json`; do not use an independent JPDB-only BAC overlay for ordinary research.
- The prior `warehouse_drive_index_bac_v1.json` and `jrdb_historical_warehouse_drive_index_set_v1.json` are generation-pinned historical indices. Preserve them as exact references to the previous immutable generation; **do not treat them as alternative CURRENT**, and do not silently mix their BAC/2025 with the new final manifest.
- Existing 2010–2024 assets and nine other families have not been rebuilt.
- Historical Raw `BAC_2025.zip` remains unchanged; the repaired annual Raw is preserved separately as source evidence. Existing SED/KYI remain unchanged.
- This accepted Warehouse correction is **not** permission to use historical completed-race outcomes in current-race pre-race features. JPDB as-of availability still requires explicit historical snapshot checks.
- **JPDB research scope remains 2023-01-01 onward.** Warehouse retains broader 2010–2025 accepted scope for other consumers.
- JPDB refresh cadence and production RaceNote integration remain undecided/unapproved.

## 5. Operational follow-up

Consumers that resolve the Drive CURRENT dynamically now receive the corrected 2025 BAC object. **Generation-pinned consumers do not auto-migrate**: any hard-coded 2025 BAC Parquet SHA or 2025 historical index must be independently reviewed before binding to CURRENT. No RaceNote prediction logic, frozen evaluations, or existing releases were changed. Old immutable generation remains for rollback and provenance.
