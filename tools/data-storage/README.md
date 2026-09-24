# Common Parquet / DuckDB Data Storage v0.2

Project-neutral conversion, validation, query, benchmark, and immutable-asset materialization utilities shared by `horse-racing`, `local-horse-racing`, and `boat-racing`.

The durable analytical data is Parquet. DuckDB is used as an in-process query engine and does not require a persistent `.duckdb` file. Project-specific columns, keys, partitions, and validation rules belong in each project's YAML config, not in this package.

## Supported scope

- SQLite table to Parquet (streaming batches)
- One or more CSV files to Parquet with an optional fixed schema
- ZSTD and Snappy compression
- Single-file and Hive-partitioned Parquet datasets
- DuckDB SQL over a file, glob-compatible dataset directory, or partitioned dataset
- row count, schema hash, canonical-key uniqueness, NULL, min/max, and key-sample validation
- machine-readable audit JSON; conversion is successful only when validation passes
- SQLite/Parquet storage and query benchmark with repeated median timing
- manifest-driven immutable asset materialization from Google Drive/source indexes
- exact size + SHA-256 verification with SHA-keyed local cache
- dependency diagnostics with `DEPENDENCY_MISSING` and a non-zero CLI exit

Parquet is not an operational-database replacement. Keep SQLite where transactions, frequent updates, constraints, or indexed point lookups dominate. Use this package for rebuilt/append-oriented warehouse and mart datasets.

## Install

From the repository root:

```bash
python -m venv .venv-data-storage
.venv-data-storage/bin/python -m pip install -r tools/data-storage/requirements.txt
```

DuckDB is pinned to `1.1.3`. Newer wheels must be separately qualified on all execution CPUs before the pin is raised.

## CLI

Set the package root once:

```bash
export PYTHONPATH="$PWD/tools/data-storage"
python -m data_storage check-deps
```

Direct SQLite conversion:

```bash
python -m data_storage convert \
  --input source.sqlite \
  --input-format sqlite \
  --table training_runner \
  --output training_runner.parquet \
  --compression zstd \
  --sort-by race_date race_key horse_no \
  --audit training_runner.audit.json
```

Config-driven execution (recommended for projects):

```bash
python -m data_storage run-config horse-racing/jrdb/config/storage/training_research.yaml
```

Query Parquet directly. SQL uses the view name `data`:

```bash
python -m data_storage query training_runner.parquet \
  "SELECT year, count(*) FROM data GROUP BY year ORDER BY year"
```

Validation and benchmark can be run independently:

```bash
python -m data_storage validate path/to/config.yaml
python -m data_storage benchmark path/to/config.yaml --output benchmark.json
```

All commands print JSON. `run-config` and `validate` exit non-zero when validation fails.
Conversion also fails closed when the target path already exists; use a new/versioned target rather than silently overwriting a prior generation.

## Manifest-driven materialization

For accepted manifests whose `assets` list records `relative_path`, `sha256`, and `size_bytes`:

```bash
PYTHONPATH=tools/data-storage \
  python -m data_storage materialize-manifest \
  --manifest /tmp/warehouse/manifest.json \
  --output-root /tmp/warehouse/materialized \
  --cache-dir /tmp/warehouse/cache \
  --audit /tmp/warehouse/materialization_audit.json
```

When the manifest contains a `families` list with `family`, `staging_folder_id`, and `asset_count`, the command discovers those public Drive folders, resolves each manifest asset, downloads files individually, and accepts them only after exact size and SHA-256 verification.

`gdown --folder` bulk download is deliberately not used for canonical acquisition. Folder access is discovery only. Consumer workflows should call this materializer instead of implementing their own Drive folder-download loops.

Useful options:

```text
--folder LABEL=FOLDER_ID     add/override a public Drive source folder
--folder-label LABEL         materialize only selected manifest folder refs
--source-index FILE.json     add path -> file_id/url/local_path source entries
--backend auto|direct|gdown  choose individual-file transfer backend
--cache-dir DIR              reuse SHA-verified immutable objects
```

See `docs/MANIFEST_MATERIALIZATION.md` for the operational contract and recovery rules.

## Config contract

See [`config/schema.example.yaml`](config/schema.example.yaml). Relative paths are resolved against the config file directory.

| Key | Meaning |
|---|---|
| `source.format` | `sqlite` or `csv` |
| `source.path` / `source.paths` | input path or CSV paths/globs |
| `source.table` | SQLite table |
| `source.columns` | optional selected SQLite columns |
| `source.schema` | optional CSV `{column: arrow_type}` map |
| `target.path` | Parquet file, or directory when partitioned |
| `target.compression` | `zstd` or `snappy` |
| `target.partition_by` | optional Hive partition columns |
| `keys.canonical` | uniqueness and sample-comparison key |
| `sort_by` | source-side SQLite order before writing |
| `validation.*` | count, unique key, non-null, ranges, expected columns |
| `audit.path` | machine-readable result JSON |

Supported fixed CSV types include `string`, signed/unsigned integers, `float32`, `float64`, `bool`, `date32`, `date64`, and `timestamp_ms`.

## Partition guidance

Avoid race/day-sized files. Start unpartitioned for datasets in the low hundreds of MB. For multi-year growth, benchmark `year`; consider `year/month` or `year/venue` only when query pruning offsets the extra files. The writer never externally ZIPs Parquet because that removes direct range/column access.

## Benchmark contract

Benchmark SQL refers to `{table}`. It is replaced by the configured SQLite table or the DuckDB `data` view. Each query runs multiple times and reports the median plus every run. `warm` reuses one connection; `cold` reconnects each time (OS cache is not forcibly cleared, so it is a connection-cold measurement).

```yaml
benchmark:
  repeats: 5
  modes: [warm, cold]
  sources:
    - {name: sqlite, engine: sqlite, path: source.sqlite, table: records}
    - {name: parquet_zstd, engine: parquet, path: records.parquet}
  queries:
    - name: count
      sql: SELECT count(*) FROM {table}
```

## Tests

```bash
PYTHONPATH=tools/data-storage .venv-data-storage/bin/python -m pytest tools/data-storage/tests -q
```

Fixtures cover SQLite and CSV conversion, both compression codecs, partitioning, DuckDB query, row/schema/key/NULL validation, invalid config, benchmark execution, non-zero validation failure, manifest path resolution, SHA-verified materialization, cache verification, and ambiguous source rejection.

## GitHub Actions

`.github/workflows/data_storage.yml` provides a shared runner for tests and config files whose inputs are available in the checkout. Project workflows that download authenticated or large inputs should install these requirements and call the same CLI in that job; do not copy the Python implementation. Output Parquet/audit files are artifacts unless a project explicitly publishes them to its external data store.

For immutable Warehouse-style inputs, workflows should call `materialize-manifest`; they should not use `gdown --folder` as the transfer contract.

## v0.2 boundaries

No Iceberg/Delta/DuckLake, distributed execution, fine-grained Parquet updates, or persistent DuckDB database is created. Parquet-to-CSV/SQLite export can be added when a concrete delivery consumer requires it.
