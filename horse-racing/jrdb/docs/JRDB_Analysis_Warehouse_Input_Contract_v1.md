# JRDB Analysis Warehouse Input Contract v1

## Scope and source boundary

The accepted historical Warehouse is resolved only through:

`GPT/horse-racing/10_warehouse/jrdb/v1/current.json`

Its current generation is `jrdb_normalized_warehouse_v1_2010_2025_g20260921`, with coverage limited to 2010–2025. It is immutable and is not modified by Analysis.

The normal 2026 post-race path remains PACI + SED / Raw-direct. PACI daily normalization is outside this contract. Therefore Warehouse input may be promoted only for a verified historical target date within 2010–2025; it must not be represented as a replacement for an uncovered 2026 date.

## Reader and dual-read

- `src/jrdb_analysis_warehouse_adapter.py` resolves the dedicated current pointer, reads immutable family staging Parquet with DuckDB, and projects BAC/KYI/SED/CYB/UKC to the existing 34-column Analysis Lite tuple contract.
- It owns no byte offsets. Fixed-width parsing remains exclusively in `src/jrdb_raw.py`.
- `src/audit_jrdb_analysis_raw_vs_warehouse.py` is non-mutating. For the same Raw delivery it compares Raw-direct and Warehouse rows, primary keys, all logical columns, null/blank profiles, canonical row hashes, representative aggregates, and a repeated Warehouse read.

The audit must use a local, connector-downloaded immutable copy of the final `current.json`/manifest and the five required family staging roots. A supplied `--source-member-date` is strict so the Warehouse side is bound to the same Raw delivery as the Raw-direct side.

## Promotion gate

Before `update_jrdb_analysis_incremental.py --warehouse-current ...` is used for a historical date, the dual-read audit must report `status=PASS` for that exact target date and source delivery.

Only then may the Warehouse input mode replace the historical Raw-direct invocation. The Raw-direct mode remains implemented for rollback and future audit. The update semantics are unchanged: a temporary Analysis SQLite is replaced only for the target date, then the existing candidate/validation/publish chain governs any Analysis current-pointer promotion.

No feature, value correction, Analysis schema/version, Warehouse generation, historical Parquet asset, PACI daily input, RaceNote, Eval, or backtest behavior is changed by this adapter.


## Accepted operating split — 2026-09-21

The formal multi-year dual-read audit is PASS. Historical Analysis rebuild/backfill for **2010–2025** now uses Warehouse input as the standard path:

```
dedicated JRDB Warehouse current -> DuckDB reader -> Analysis
```

The Raw daily mode rejects a historical date unless `--allow-historical-raw` is supplied explicitly for rollback/audit. The Warehouse reader derives its coverage from the accepted manifest and rejects an uncovered date with a PACI/Raw instruction.

For **2026**, the standard path remains unchanged:

```
PACI + SED / Raw direct -> Analysis
```

This split is intentional. No PACI normalization, Analysis logical schema, Analysis current pointer, Warehouse generation, or consumer subsystem changed as part of the cutover. Audit evidence: `docs/JRDB_Analysis_Warehouse_Dual_Read_Audit_20260921.md`.
