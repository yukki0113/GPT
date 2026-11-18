# JRDB Normalized Warehouse Operation v1

## Current contract

The authoritative JRDB pointer is the Drive file:

`GPT/horse-racing/10_warehouse/jrdb/v1/current.json`

It is intentionally distinct from the sibling NAR canonical `CURRENT.json`. Do not read, overwrite, or repurpose the NAR pointer for JRDB consumers.

The pointer resolves to immutable final-generation evidence:

```
jrdb/v1/
  current.json
  generations/<generation_id>/manifest.json
  generations/<generation_id>/audit.json
```

A final manifest uses `asset_reference_mode: staging_immutable_reference`: its assets point to the published, content-addressed Parquet objects in family staging. It never copies, regenerates, or reuploads those objects.

## Accepted generation — CURRENT (updated 2026-11-18)

- **Generation: `jrdb_normalized_warehouse_v1_2010_2025_g20261118_bacfix`**.
- Status: **`PASS` / `accepted`**, confirmed by Drive `current.json` readback.
- Families: BAC, KYI, CHA, CYB, SED, SKB, ZED, ZKB, HJC, UKC.
- Coverage: 2010–2025; 192 Parquet assets; duplicate references 0.
- Exactly one asset changed: `bac/year=2025`, **3,402 → 3,455 rows**, 53 restored race keys, same schema hash and canonical key. The other 191 assets are inherited byte-identically from the predecessor.
- `current.json` file ID **`1uB0IQecWNKNn_ASZx4_0MhlWNXUmFrYA`** remains unchanged, and now resolves to the new final `generations/<generation_id>/manifest.json` and `audit.json`.
- New `bac/year=2025` content-addressed Parquet: SHA256 `b26a364978143fbd6e9d30289db0eb85e9b33e9fe612759b23a85ffbb78a3bb9`, Drive object `1nvDnqBnv69KdMgH200lqOEg6E2VTNtpX`.
- **Old accepted generation** `jrdb_normalized_warehouse_v1_2010_2025_g20260921` is retained immutable for provenance/rollback, but **is no longer CURRENT**. Its generation-pinned historical index set remains an archival snapshot, not an alternative active CURRENT.
- Exceptional repair used an **accepted-generation single-partition successor** with explicit `successor_lineage` / `staging_partition_override` and a dedicated patch audit, rather than silently mutating the predecessor BAC staging manifest. The ordinary 10-family initial finalizer described below remains unchanged. Detailed receipt: [`JRDB_Warehouse_BAC_2025_Repair_Promotion_20261118.md`](JRDB_Warehouse_BAC_2025_Repair_Promotion_20261118.md).

**Consumer rule:** For new/current Warehouse research and consumers, resolve `jrdb/v1/current.json` first; verify the referenced final manifest/audit semantic SHA and use its BAC 2025 asset. Do not mix predecessor-generation `warehouse_drive_index_bac_v1.json` with CURRENT without an explicit immutable historical replay requirement.

The final audit records per-relation canonical keys and schema hashes. A relation may have historical schema variants only when its canonical key is invariant; cross-family audit remains PASS.

## Finalization procedure

1. Read each family staging folder and capture its `manifest.json`, `audit.json`, `completion_marker.json`, sidecar inventory, and object listing into a snapshot.
2. Run:

   ```bash
   python horse-racing/jrdb/src/finalize_jrdb_warehouse_from_staging.py \
     --snapshot <staging-snapshot.json> \
     --generation-id <immutable-generation-id> \
     --output-dir <empty-output-dir>
   ```

3. The finalizer requires exactly the ten families and verifies: completion status, expected year coverage, relation asset counts, no duplicate object references, manifest/audit PASS, required sidecars, Drive listing/SHA/size agreement, provenance columns, schema/canonical-key consistency, and cross-family evidence.
4. Only on PASS, upload the output `manifest.json` and `audit.json` to a new immutable `generations/<generation_id>/` folder. Refetch both files and compare their SHA-256 values.
5. Only after that readback succeeds, create or replace the JRDB-only `jrdb/v1/current.json`; refetch it and verify its generation ID and manifest/audit paths.

## Guardrails

- Do not rebuild JRDB Raw or re-normalize an accepted family merely to finalize.
- Do not reupload family Parquet assets. Before any exceptional asset repair, list Drive first; upload only when the identical SHA-named object is absent and refetch afterward.
- Do not modify the NAR `CURRENT.json`.
- PACI daily normalization and consumer migration (Analysis, RaceNote, Eval, backtest) are separate follow-on work.
