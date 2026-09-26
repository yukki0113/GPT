# EdgeDB Storage Inventory 2026-09-25

Status: **MIGRATION BASELINE / SCIENTIFIC SEMANTICS FROZEN**

> 2026-09-26 operational update: this file remains the migration baseline. The temporary Parquet -> SQLite Feature Mart bridge described below is superseded. Current normal execution uses a DuckDB workspace derived from canonical Parquet. Registry current is read directly with DuckDB; Registry SQLite remains only as the small mutable build workspace and is converted to a Parquet candidate in the same successful full-build run.

Main SHA at inventory start: `0c652c9289d89f71cfa53f5dc68682ee8dda0c52`

## Purpose

Inventory the active EdgeDB storage/source-of-truth paths before Parquet canonical migration.
This inventory changes storage classification only. It does not change v0.2 STANDARD or v0.3 SHADOW scientific semantics.

## Active storage inventory

| Asset | Current format | Current producer | Main consumers | Current classification | Migration target |
|---|---|---|---|---|---|
| Historical JRDB Warehouse | Parquet + accepted manifest | normalized Warehouse pipeline | Warehouse adapter / v0.3 research | CANONICAL | KEEP |
| Index Base | SQLite | `build_jrdb_index_base_from_warehouse.py` or legacy Raw builder | Feature Mart builder | COMPATIBILITY | KEEP SQLITE COMPATIBILITY |
| Edge Feature Mart v0.2 | SQLite `edge_runner_fact` | `build_jrdb_edge_feature_mart_v0_2.py` | discovery / temporal validation / registry / research | CURRENT RESEARCH SOURCE | MIGRATE TO PARQUET CANONICAL |
| Candidate output | JSONL | `jrdb_edge_discovery_v0_2.py` | Registry builder | TRANSIENT / REPRO | KEEP JSONL |
| Edge Registry v0.2 | SQLite | `build_jrdb_edge_registry_v0_2.py` | guards / report / serving publication | CURRENT RESEARCH/STORAGE SOURCE | MIGRATE TO PARQUET CANONICAL |
| v0.2 serving catalog | JSONL | suggestive publication | current matcher / TRUE_FORWARD / Newspaper / RaceNote | SERVING DELIVERY | KEEP JSONL, DERIVE FROM PARQUET CANONICAL |
| Forward freeze artifact | JSON/JSONL + copied inputs | forward freeze drivers | settlement / audit | IMMUTABLE EVALUATION ARTIFACT | KEEP |
| Forward ledger | SQLite | `build_jrdb_edge_forward_ledger.py` | forward evaluation | OPERATIONAL/AUDIT SQLITE | KEEP SQLITE |
| v0.3 incremental/statistical/B2 outputs | JSONL/JSON | v0.3 shadow workflows | Stage-C shadow catalog | IMMUTABLE RESEARCH ARTIFACT | KEEP |
| v0.3 shadow catalog | JSONL | `build_jrdb_edge_v03_shadow_catalog.py` | Stage-D/E shadow matcher | SHADOW SERVING DELIVERY | KEEP JSONL; ADD PARQUET RESEARCH CANONICAL LATER |
| Publication manifest | JSON | `build_jrdb_edge_publication_manifest.py` | serving consumers/audit | PUBLICATION METADATA | RETAIN; POINT TO NEW CANONICAL GENERATION |

## Canonical decisions

### Historical input

Canonical source is the accepted JRDB Historical Warehouse generation:

`jrdb_normalized_warehouse_v1_2010_2025_g20260921`

Acquisition contract:
- accepted manifest is canonical;
- folder is discovery only;
- individual asset download;
- exact size + SHA-256;
- `tools/data-storage materialize-manifest`;
- no canonical `gdown --folder`.

### SQLite retained by design

SQLite is not prohibited. These remain valid:
- Index Base compatibility SQLite;
- temporary Parquet -> SQLite compatibility materialization: **LEGACY_REPRO ONLY; not normal operation**;
- forward ledger / audit SQLite;
- rollback/reproduction SQLite.

SQLite must not remain the sole current canonical for Feature Mart or Registry.

## Planned new canonical roots

```text
GPT/horse-racing/20_mart/edge/
  feature_mart/
    v0.2/
      current.json
      generations/<generation_id>/
        edge_runner_fact.parquet
        manifest.json
        audit.json
  registry/
    v0.2/
      current.json
      generations/<generation_id>/
        edge_registry.parquet
        edge_serving_catalog.jsonl
        manifest.json
        audit.json
  registry/
    v0.3-shadow/
  forward/
  shadow/
  publication/
```

## Current code coupling

The v0.2 Feature Mart builder currently creates SQLite directly from Index Base SQLite.
The v0.2 Registry builder/discovery/temporal validation paths currently query Feature Mart SQLite directly.
Therefore migration order is fixed:

1. Feature Mart Parquet exact canonical;
2. DuckDB/current resolver;
3. validated DuckDB execution workspace for unchanged discovery/registry semantics (SQLite bridge retired 2026-09-26);
4. Registry Parquet canonical;
5. publication metadata cutover;
6. legacy dependency audit.

## Old GPT/JRDB policy

No new Edge artifact may be published under old `GPT/JRDB`.
Any remaining references discovered later are classified:
- ACTIVE
- LEGACY_REPRO
- DEAD

Completion requires ACTIVE = 0. Legacy reproduction/rollback assets are not deleted during this migration.

## Scientific freeze

The migration must not change:
- v0.2 STANDARD semantics;
- v0.3 semantic hierarchy;
- candidate templates;
- temporal validation;
- statistical gates;
- Performance/Value separation;
- parent/incremental logic;
- matcher behavior;
- TRUE_FORWARD/settlement semantics;
- leakage boundary.

## Turn-1 gate

`EDGE_STORAGE_INVENTORY = PASS`

The migration scope and SQLite-retention boundaries are explicit. Feature Mart is the first canonical cutover target.
