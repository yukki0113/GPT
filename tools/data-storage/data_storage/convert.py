from __future__ import annotations

import csv
import glob
import sqlite3
import time
from pathlib import Path
from typing import Iterable, Iterator

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from .common import quote_identifier, sha256_file, size_bytes
from .errors import ConfigError

SQLITE_TYPES = {
    "INT": pa.int64(),
    "REAL": pa.float64(),
    "FLOA": pa.float64(),
    "DOUB": pa.float64(),
    "BLOB": pa.binary(),
    "BOOL": pa.bool_(),
}

ARROW_TYPES = {
    "string": pa.string(), "utf8": pa.string(), "binary": pa.binary(),
    "int8": pa.int8(), "int16": pa.int16(), "int32": pa.int32(), "int64": pa.int64(),
    "uint8": pa.uint8(), "uint16": pa.uint16(), "uint32": pa.uint32(), "uint64": pa.uint64(),
    "float32": pa.float32(), "float64": pa.float64(), "bool": pa.bool_(),
    "date32": pa.date32(), "date64": pa.date64(), "timestamp_ms": pa.timestamp("ms"),
}


def _arrow_type(name: str) -> pa.DataType:
    try:
        return ARROW_TYPES[name.lower()]
    except KeyError as exc:
        raise ConfigError(f"unsupported schema type: {name}") from exc


def _configured_schema(mapping: dict | None) -> pa.Schema | None:
    if not mapping:
        return None
    if not isinstance(mapping, dict):
        raise ConfigError("schema must be a column/type mapping")
    return pa.schema([(name, _arrow_type(kind)) for name, kind in mapping.items()])


def _sqlite_schema(connection: sqlite3.Connection, table: str, columns: list[str] | None) -> pa.Schema:
    rows = connection.execute(f"PRAGMA table_info({quote_identifier(table)})").fetchall()
    if not rows:
        raise ConfigError(f"SQLite table not found: {table}")
    selected = set(columns) if columns else None
    fields = []
    for _, name, declared, not_null, *_ in rows:
        if selected is not None and name not in selected:
            continue
        upper = (declared or "").upper()
        dtype = next((value for key, value in SQLITE_TYPES.items() if key in upper), None)
        # CREATE TABLE AS SELECT (used for safe, short-lived projections) does
        # not retain declared SQLite types. Recover the concrete storage class so
        # BLOB provenance columns remain binary rather than being coerced to text.
        if dtype is None:
            sample = connection.execute(
                f"SELECT typeof({quote_identifier(name)}) FROM {quote_identifier(table)} "
                f"WHERE {quote_identifier(name)} IS NOT NULL LIMIT 1"
            ).fetchone()
            storage_class = sample[0] if sample else "text"
            dtype = {"integer": pa.int64(), "real": pa.float64(), "blob": pa.binary(), "null": pa.string()}.get(storage_class, pa.string())
        fields.append(pa.field(name, dtype, nullable=not bool(not_null)))
    if selected and selected != {field.name for field in fields}:
        missing = sorted(selected - {field.name for field in fields})
        raise ConfigError(f"unknown SQLite columns: {missing}")
    return pa.schema(fields)


def _sqlite_batches(path: Path, table: str, columns: list[str] | None, sort_by: list[str], batch_size: int) -> tuple[pa.Schema, Iterator[pa.RecordBatch], int]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    schema = _sqlite_schema(connection, table, columns)
    select = ", ".join(quote_identifier(field.name) for field in schema)
    order = ", ".join(quote_identifier(name) for name in sort_by)
    sql = f"SELECT {select} FROM {quote_identifier(table)}" + (f" ORDER BY {order}" if order else "")
    count = connection.execute(f"SELECT COUNT(*) FROM {quote_identifier(table)}").fetchone()[0]
    cursor = connection.execute(sql)

    def batches() -> Iterator[pa.RecordBatch]:
        try:
            while rows := cursor.fetchmany(batch_size):
                arrays = [pa.array([row[index] for row in rows], type=field.type) for index, field in enumerate(schema)]
                yield pa.RecordBatch.from_arrays(arrays, schema=schema)
        finally:
            connection.close()

    return schema, batches(), count


def _csv_batches(paths: list[Path], encoding: str, delimiter: str, schema: pa.Schema | None) -> tuple[pa.Schema, Iterator[pa.RecordBatch], int]:
    convert_options = pacsv.ConvertOptions(column_types=schema) if schema else pacsv.ConvertOptions()
    read_options = pacsv.ReadOptions(encoding=encoding)
    parse_options = pacsv.ParseOptions(delimiter=delimiter)
    readers = [pacsv.open_csv(path, read_options=read_options, parse_options=parse_options, convert_options=convert_options) for path in paths]
    if not readers:
        raise ConfigError("no CSV input matched")
    first_schema = readers[0].schema
    count = 0
    for path in paths:
        with path.open("r", encoding=encoding, newline="") as handle:
            count += max(sum(1 for _ in csv.reader(handle, delimiter=delimiter)) - 1, 0)

    def batches() -> Iterator[pa.RecordBatch]:
        for reader in readers:
            if reader.schema != first_schema:
                raise ConfigError("CSV schemas differ")
            yield from reader

    return first_schema, batches(), count


def _write_batches(schema: pa.Schema, batches: Iterable[pa.RecordBatch], output: Path, compression: str, partition_by: list[str]) -> int:
    compression = compression.lower()
    if compression not in {"zstd", "snappy"}:
        raise ConfigError("compression must be zstd or snappy")
    if partition_by:
        output.mkdir(parents=True, exist_ok=True)
        ds.write_dataset(
            batches, output, schema=schema, format="parquet",
            partitioning=partition_by, partitioning_flavor="hive",
            basename_template="part-{i}.parquet",
            existing_data_behavior="overwrite_or_ignore",
            use_threads=False,
            max_rows_per_file=2_000_000,
            max_rows_per_group=100_000,
            file_options=ds.ParquetFileFormat().make_write_options(compression=compression),
        )
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        writer = pq.ParquetWriter(output, schema, compression=compression, write_statistics=True)
        try:
            for batch in batches:
                writer.write_batch(batch)
        finally:
            writer.close()
    return size_bytes(output)


def convert(config: dict) -> dict:
    started = time.perf_counter()
    source, target = config["source"], config["target"]
    source_format = str(source.get("format", "")).lower()
    output = Path(target["path"]).resolve()
    if output.exists():
        raise ConfigError(f"target already exists; use a new or versioned path: {output}")
    compression = str(target.get("compression", "zstd")).lower()
    partition_by = list(target.get("partition_by") or [])
    configured_schema = _configured_schema(source.get("schema"))
    if source_format == "sqlite":
        input_path = Path(source["path"]).resolve()
        schema, batches, source_count = _sqlite_batches(
            input_path, source["table"], source.get("columns"), list(config.get("sort_by") or []), int(source.get("batch_size", 50_000))
        )
        inputs = [input_path]
    elif source_format == "csv":
        raw_paths = source.get("paths") or [source.get("path")]
        inputs = []
        for raw in raw_paths:
            inputs.extend([Path(item) for item in sorted(glob.glob(raw, recursive=True))] if any(char in raw for char in "*?[") else [Path(raw)])
        inputs = [path.resolve() for path in inputs if path]
        schema, batches, source_count = _csv_batches(inputs, source.get("encoding", "utf-8"), source.get("delimiter", ","), configured_schema)
    else:
        raise ConfigError("source.format must be sqlite or csv")
    target_size = _write_batches(schema, batches, output, compression, partition_by)
    return {
        "operation": f"{source_format}_to_parquet",
        "input": [str(path) for path in inputs],
        "output": str(output),
        "compression": compression,
        "partition_by": partition_by,
        "row_count_source": source_count,
        "input_size_bytes": sum(path.stat().st_size for path in inputs),
        "output_size_bytes": target_size,
        "input_sha256": {path.name: sha256_file(path) for path in inputs},
        "schema": [{"name": field.name, "type": str(field.type), "nullable": field.nullable} for field in schema],
        "elapsed_seconds": round(time.perf_counter() - started, 6),
    }
