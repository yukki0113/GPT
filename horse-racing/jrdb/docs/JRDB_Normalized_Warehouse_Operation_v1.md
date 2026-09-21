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

## Accepted generation

- Generation: `jrdb_normalized_warehouse_v1_2010_2025_g20260921`
- Status: `PASS` / `accepted`
- Families: BAC, KYI, CHA, CYB, SED, SKB, ZED, ZKB, HJC, UKC
- Coverage: 2010–2025
- Assets: 192
- Duplicate object references: 0

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
