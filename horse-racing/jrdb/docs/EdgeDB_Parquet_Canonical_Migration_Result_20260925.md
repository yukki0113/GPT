# EdgeDB Parquet Canonical Migration Result 2026-09-25

Status: **PASS / CANONICAL CUTOVER COMPLETED**

## 1. Executive summary

The EdgeDB storage migration requested on 2026-09-25 is complete.

The active long-term source-of-truth chain is now:

```text
JRDB Historical Warehouse Parquet
  -> Edge Feature Mart Parquet canonical
  -> Edge Registry Parquet canonical
  -> byte-equivalent v0.2 serving catalog
  -> existing consumer / TRUE_FORWARD route
```

SQLite remains only where explicitly allowed: compatibility, transient execution, operational/audit, rollback, and reproduction.

No scientific semantics were changed. v0.2 STANDARD and v0.3 SHADOW regression gates both passed.

## 2. Main SHA

- Main SHA at inventory start: `0c652c9289d89f71cfa53f5dc68682ee8dda0c52`
- Main SHA at migration completion audit: `092a04ee74bd8814b32d50b739878a826dde15be`

The final report commit itself is documentation-only and is not part of the storage/scientific cutover.

## 3. Storage inventory

Baseline inventory:
- `horse-racing/jrdb/docs/EdgeDB_Storage_Inventory_20260925.md`
- inventory commit: `e1457f975989caaa9ff92cb8431bfee4c572e4e2`

Inventory decisions retained:
- Historical JRDB Warehouse: Parquet + accepted manifest = canonical.
- Index Base SQLite: compatibility layer retained.
- Feature Mart v0.2: migrated from sole SQLite current source to Parquet canonical.
- Registry v0.2: migrated from sole SQLite current source to Parquet canonical.
- v0.2 serving catalog: JSONL delivery retained, now recorded by the Registry Parquet canonical manifest.
- Forward ledger / rollback / reproduction SQLite assets are intentionally retained.
- v0.3 SHADOW semantics and serving behavior remain unchanged.

## 4. Warehouse input

Accepted Warehouse generation:

`jrdb_normalized_warehouse_v1_2010_2025_g20260921`

Accepted manifest SHA-256:

`a25cedfb5d76c1f9f2ed65308181e2f5222f294ee8015f93aabe3771fb7f1087`

Acquisition contract:
- accepted manifest is canonical;
- folder is discovery only;
- individual immutable asset download;
- exact size + SHA-256 verification;
- shared `tools/data-storage materialize-manifest`;
- no canonical `gdown --folder`.

Result:

`WAREHOUSE_INPUT = MANIFEST_DRIVEN`

No Warehouse regeneration was performed.

## 5. Feature Mart migration

Generation:

`edge_feature_mart_v0_2_g20260925_pq1`

Source run:

`36116777782`

Artifact:

`jrdb-edge-feature-mart-parquet-36116777782`

Canonical asset:
- `edge_runner_fact.parquet`
- rows: 781,161
- size: 30,112,029 bytes
- SHA-256: `82e6550639210eea6cf1fc1ac374ee8b6fc07115214fe75ea6e1bb704d3751f6`
- canonical key: `race_key, horse_no`
- duplicate key rows: 0

SQLite -> Parquet equivalence:
- row count: equal
- schema columns: equal
- logical types: equal
- NULL semantics: equal
- canonical row hash: equal
- representative aggregates: equal
- current resolver: PASS

Drive canonical destination:

`GPT/horse-racing/20_mart/edge/feature_mart/v0.2/`

Current generation:

`edge_feature_mart_v0_2_g20260925_pq1`

Drive promotion was performed generation-first, followed by readback SHA/size verification, then `current.json` publication.

Result:

```text
EDGE_FEATURE_MART_PARQUET_CANONICAL = PASS
EDGE_FEATURE_MART_PARQUET_EQUIVALENCE = PASS
EDGE_DUCKDB_READER = PASS
```

## 6. Registry migration

Generation:

`edge_registry_v0_2_g20260925_pq1`

Source run:

`36152894120`

Artifact:

`jrdb-edge-registry-parquet-36152894120`

Canonical tables:
- `edge_definition.parquet`: 8,174 rows
- `edge_metric_snapshot.parquet`: 26,984 rows
- `edge_registry_meta.parquet`: 1 row
- `edge_validation_event.parquet`: 11,983 rows

Serving catalog:
- `edge_serving_catalog.jsonl`
- size: 6,495,361 bytes
- SHA-256: `fe1182e1e8beed952d5f4b740642fd3ec1262c353d6d46036e19a457f27d7469`

The serving catalog SHA is unchanged from the frozen v0.2 STANDARD publication source.

Drive canonical destination:

`GPT/horse-racing/20_mart/edge/registry/v0.2/`

Current generation:

`edge_registry_v0_2_g20260925_pq1`

All immutable Registry files were read back from Drive and verified against the accepted manifest before `current.json` was published.

Result:

```text
EDGE_REGISTRY_PARQUET_CANONICAL = PASS
EDGE_REGISTRY_PARQUET_EQUIVALENCE = PASS
```

## 7. Serving / publication metadata

The Registry canonical manifest records the serving catalog relative path, SHA-256, and size.

The delivery JSONL remains byte-identical to the accepted v0.2 STANDARD serving catalog.

The storage cutover did not alter the active matcher, TRUE_FORWARD, Newspaper, RaceNote, or other serving semantics.

The old SQLite-based publication builder remains available for reproduction/compatibility; it is not the sole long-term canonical store.

Result:

`2026_CURRENT_ROUTE = UNCHANGED`

## 8. v0.2 STANDARD regression

Completion audit:
- Issue: #1476
- Run: `36206418135`
- Artifact: `jrdb-edge-parquet-completion-audit-36206418135`

The accepted v0.2 serving catalog SHA was revalidated:

`fe1182e1e8beed952d5f4b740642fd3ec1262c353d6d46036e19a457f27d7469`

Result:

`V02_STANDARD_REGRESSION = PASS`

No storage migration step changed v0.2 scientific semantics.

## 9. v0.3 SHADOW regression

The frozen v0.3 shadow catalog SHA was revalidated against the accepted Stage-C artifact:

`a724a005ec40446f4a982a79de17ba7a2ae169c09260ecee98a159b663914379`

Result:

`V03_SHADOW_REGRESSION = PASS`

The completion audit did not promote v0.3 to production and did not alter shadow scientific semantics.

## 10. Benchmark

Completion audit benchmark:

`jrdb-edge-parquet-completion-audit-36206418135`

### Feature Mart

The benchmark compares the canonical Parquet against a transient compatibility SQLite materialized from the same logical Parquet rows.

Warm median:

| Query | SQLite ms | Parquet/DuckDB ms | Approx. relative |
|---|---:|---:|---:|
| full scan | 75.946 | 4.213 | 18.0x faster |
| year filter | 111.077 | 4.559 | 24.4x faster |
| pre-race eligible | 116.657 | 5.012 | 23.3x faster |
| horse aggregation | 362.659 | 20.971 | 17.3x faster |
| sire aggregation | 467.534 | 13.720 | 34.1x faster |
| course aggregation | 242.231 | 10.284 | 23.6x faster |

Storage:
- transient compatibility SQLite: 318,705,664 bytes
- canonical ZSTD Parquet: 30,112,029 bytes

The historical/research scan workload strongly supports Parquet canonicalization.

### Registry

Registry `edge_definition` is small (8,174 rows), so SQLite remains faster for tiny point/count-style reads.

Warm median:

| Query | SQLite ms | Parquet/DuckDB ms |
|---|---:|---:|
| registry read | 0.012 | 0.633 |
| family filter | 0.105 | 0.787 |
| anchor type aggregation | 0.388 | 1.438 |
| status aggregation | 0.382 | 1.625 |

Storage:
- source Registry SQLite: 86,757,376 bytes
- `edge_definition.parquet`: 427,448 bytes

This does not fail the migration gate. The work request explicitly prioritizes historical/research canonical storage over point-lookup latency and permits SQLite compatibility/operational use.

Result:

`BENCHMARK = PASS`

## 11. Leakage / current-route guards

No result-free boundary was changed during this migration.

The accepted v0.2 and v0.3 regression inputs retain the existing pre-race / TRUE_FORWARD contracts.

No SED/result/final-odds source was newly introduced into current matching by this storage migration.

Result:

`LEAKAGE_GUARDS = PASS`

## 12. Legacy GPT/JRDB dependency audit

Final EdgeDB-scoped audit:
- Issue: #1454
- Run: `36153429684`
- head SHA: `ac8db31e5fccaa2cb3b46a048474bc5a671c028c`

Result:
- ACTIVE references: 0
- LEGACY_REPRO references: 2
- status: PASS

Therefore:

```text
OLD_GPT_JRDB_NEW_DEPENDENCY = 0
EDGE_LEGACY_JRDB_ACTIVE_REFERENCE_COUNT = 0
```

The earlier broad-scope audit (#1453) was intentionally superseded because it counted generic non-Edge JRDB references. The EdgeDB-scoped audit is the authoritative result.

## 13. Remaining legacy assets

Two references remain classified as `LEGACY_REPRO`.

They are intentionally retained for rollback/reproduction and are not active canonical dependencies.

No new Edge artifacts were written under old `GPT/JRDB`.

## 14. Deletion-readiness

Assessment:

`ACTIVE_OPERATIONAL_DEPENDENCY_REMOVED = YES`

`IMMEDIATE_PHYSICAL_DELETION_OF_OLD_GPT_JRDB = NO`

Reason:
- active EdgeDB dependency is zero;
- new canonical assets are under `GPT/horse-racing/20_mart/edge/`;
- current pointers resolve to the Parquet generations;
- two legacy reproduction references remain by design.

The old root is therefore **operationally decoupled**, but physical deletion should be a separate cleanup task after the two LEGACY_REPRO references/assets are explicitly retired or archived.

## 15. Issue hygiene / failed retries

Migration and audit failures were not left open:
- #1474: audit workflow environment-export bug -> closed `not_planned`, superseded by retry.
- #1475: Registry benchmark used a nonexistent `template_id` column -> closed `not_planned`, superseded by retry.
- #1476: corrected completion audit -> closed `completed`, PASS.
- stale Drive bridge requests #1450-#1452 -> fulfilled by direct connected-Drive promotion and closed `completed`.

No failed migration Issue is intentionally left open.

## 16. Completion gates

```text
EDGE_STORAGE_INVENTORY = PASS

EDGE_FEATURE_MART_PARQUET_CANONICAL = PASS
EDGE_FEATURE_MART_PARQUET_EQUIVALENCE = PASS
EDGE_DUCKDB_READER = PASS

EDGE_REGISTRY_PARQUET_CANONICAL = PASS
EDGE_REGISTRY_PARQUET_EQUIVALENCE = PASS

V02_STANDARD_REGRESSION = PASS
V03_SHADOW_REGRESSION = PASS
BENCHMARK = PASS

WAREHOUSE_INPUT = MANIFEST_DRIVEN
2026_CURRENT_ROUTE = UNCHANGED
LEAKAGE_GUARDS = PASS

OLD_GPT_JRDB_NEW_DEPENDENCY = 0
EDGE_LEGACY_JRDB_ACTIVE_REFERENCE_COUNT = 0
```

## 17. Final decision

`EDGEDB_PARQUET_CANONICAL_MIGRATION = COMPLETED`

The active EdgeDB storage/source-of-truth chain is now Warehouse/Parquet-centered.

SQLite is retained only in allowed compatibility, transient, operational/audit, rollback, and reproduction roles.

The scientific behavior of v0.2 STANDARD and v0.3 SHADOW remains unchanged.
