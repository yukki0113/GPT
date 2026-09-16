# Training Research Lite Parquet / DuckDB PoC

Date: 2026-09-16  
Tool: Common Data Storage v0.1  
Dataset: `jrdb_training_research_2010_2023_development_lite_v0_1`

## Decision

Adopt unpartitioned Parquet ZSTD as the long-term analytical copy for this mart. Do not replace indexed SQLite where point lookup is the primary workload. Do not externally ZIP Parquet.

At the current 686,096-row scale, year partitioning is not the default: it improves the year-filter count but creates 14 files, is 7.26% larger than one ZSTD file, and slows whole-dataset aggregation and lookup.

## Input and validation

- table: `training_runner`
- rows: 686,096
- columns: 67
- canonical key: `(race_key, horse_no)`
- source period: 2010-2023
- original SQLite: 325,054,464 bytes
- retrieved source ZIP: 87,883,009 bytes

All three Parquet forms passed:

- source and target row count: 686,096 / 686,096
- duplicate canonical-key rows: 0
- source/target schema match: true
- first 100 ordered canonical keys match: true
- required-key NULL counts: 0
- min/max checks: passed
- automated tests: 10 passed

## Storage comparison

| Form | Bytes | vs original SQLite | vs retrieved SQLite ZIP |
|---|---:|---:|---:|
| SQLite original | 325,054,464 | 100.00% | 369.87% |
| SQLite ZIP (Deflate, supplied archive) | 87,883,009 | 27.04% | 100.00% |
| SQLite no-index + VACUUM | 187,670,528 | 57.74% | 213.55% |
| SQLite no-index ZIP Deflate-9 | 53,747,748 | 16.53% | 61.16% |
| SQLite no-index ZIP LZMA | 32,912,742 | 10.13% | 37.45% |
| **Parquet ZSTD, one file** | **25,434,132** | **7.82%** | **28.94%** |
| Parquet Snappy, one file | 29,733,641 | 9.15% | 33.83% |
| Parquet ZSTD, year partition | 27,279,897 | 8.39% | 31.04% |

The unpartitioned ZSTD result is 71.06% smaller than the retrieved SQLite ZIP and 22.73% smaller than the LZMA-compressed no-index SQLite. Snappy is 16.90% larger than ZSTD on this dataset.

The year-partitioned form produced 14 Parquet files, one per year. File sizes ranged from 1,900,450 to 2,012,877 bytes (mean 1,948,564 bytes). This is manageable but unnecessarily fine for the present size.

## Query benchmark

Five repeats were run for each query. The table shows warm median milliseconds; cold/reconnected results were materially similar and are retained in the machine result used for this report.

| Query | SQLite original | SQLite no-index | Parquet ZSTD | Parquet Snappy | Year ZSTD |
|---|---:|---:|---:|---:|---:|
| COUNT all | **2.766** | 31.423 | 4.420 | 4.222 | 7.345 |
| COUNT year=2023 | 50.071 | 50.226 | 4.168 | 4.193 | **3.239** |
| selected columns + filters | 16.426 | 52.070 | 6.444 | 7.179 | **4.927** |
| workout-index GROUP BY | 321.106 | 342.124 | 7.313 | **6.632** | 13.143 |
| one horse's history | **0.140** | 59.210 | 10.196 | 12.644 | 13.426 |
| canonical-key lookup | **0.005** | 0.009 | 6.409 | 6.414 | 11.040 |
| multi-filter aggregate | 357.355 | 90.899 | 7.863 | **7.348** | 9.947 |

Interpretation:

- Unpartitioned ZSTD was about 12.0x faster for a year count, 2.5x for selected-column filtering, 43.9x for GROUP BY, and 45.4x for the multi-filter aggregate versus indexed SQLite.
- Indexed SQLite was about 72.8x faster for a single horse's indexed history and about 1,282x faster for one canonical-key lookup.
- Plain `COUNT(*)` also favored indexed SQLite by about 1.6x.
- ZSTD and Snappy query times were close. ZSTD wins the storage decision because it is 4,299,509 bytes smaller without a meaningful scan penalty.
- The no-index SQLite sometimes beat indexed SQLite on the multi-filter aggregate because the original optimizer chose indexes that were unfavorable for that broad scan. This does not alter the point-lookup conclusion.

## Conversion timing

On the Work execution environment:

| Output | Convert + validate seconds |
|---|---:|
| Parquet ZSTD | 10.903 |
| Parquet Snappy | 10.937 |
| Year-partitioned ZSTD | 10.380 |

These are operational observations, not cross-hardware performance guarantees.

## Recommended operating model

1. Preserve JRDB fixed-width raw files unchanged in `00_raw`.
2. Build normalized warehouse/mart data by batch into Parquet ZSTD.
3. For this mart, keep one unpartitioned Parquet file until scale or measured query pruning justifies year partitioning.
4. Query Parquet directly through DuckDB; do not persist a `.duckdb` file by default.
5. Keep a purpose-built SQLite delivery/operational copy only for consumers requiring millisecond point lookup or updates.
6. Treat conversion as successful only when the generated audit reports `status=success` after row, schema, key, NULL, range, and sample validation.
7. Replace older analytical SQLite/ZIP copies only after downstream consumers have been switched and a rollback generation is explicitly retained.

## Environment notes

- DuckDB `1.5.5` raised a CPU-level bus error in this Work runtime. v0.1 pins the qualified `1.1.3` wheel; raising the pin requires multi-environment qualification.
- A Work workspace file larger than roughly 256 MiB was truncated across command boundaries. The PoC used `/tmp` for the expanded 325 MB SQLite while the ZIP remained the immutable input. This reinforces the need for the common Actions/local execution route for large sources.
- The retrieved Library ZIP was 87,883,009 bytes, while an earlier observation in the request recorded 89,408,203 bytes. This report uses the bytes actually retrieved and integrity-tested for this run.

## Adoption by project

- Central horse racing: create YAML under `horse-racing/.../config/storage/`; set actual table/key/range rules and publish the validated Parquet to the project's warehouse or mart Drive folder.
- Local horse racing: create its own config under `local-horse-racing/.../config/storage/`; reuse the package and workflow unchanged.
- Boat racing: create its own config under `boat-racing/.../config/storage/`; keep race/day CSV only as delivery/interchange when needed, with Parquet as the long-history analytical form.

Project workflows may download authenticated input and invoke `python -m data_storage run-config ...` in the same job. They should not copy the conversion or validation implementation.
