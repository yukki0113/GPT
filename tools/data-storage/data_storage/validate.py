from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from .common import quote_identifier
from .query import connect_parquet


def _source_count(config: dict) -> int | None:
    source = config["source"]
    if source.get("format") == "sqlite":
        with sqlite3.connect(f"file:{Path(source['path']).resolve()}?mode=ro", uri=True) as connection:
            return connection.execute(f"SELECT COUNT(*) FROM {quote_identifier(source['table'])}").fetchone()[0]
    return None


def validate(config: dict, conversion: dict | None = None) -> dict:
    validation = config.get("validation") or {}
    target_path = config["target"]["path"]
    connection = connect_parquet(target_path)
    checks = []
    try:
        target_count = connection.execute("SELECT COUNT(*) FROM data").fetchone()[0]
        source_count = conversion.get("row_count_source") if conversion else _source_count(config)
        require_count = validation.get("require_row_count_match", True)
        count_pass = source_count is None or target_count == source_count or not require_count
        checks.append({"name": "row_count", "pass": count_pass, "source": source_count, "target": target_count})

        describe = connection.execute("DESCRIBE data").fetchall()
        schema = [{"name": row[0], "type": row[1], "null": row[2]} for row in describe]
        schema_hash = hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()
        expected_columns = validation.get("expected_columns")
        expected_names_pass = expected_columns is None or list(expected_columns) == [item["name"] for item in schema]
        source_schema = (conversion or {}).get("schema")
        type_aliases = {
            "string": "VARCHAR", "binary": "BLOB", "int64": "BIGINT", "int32": "INTEGER",
            "int16": "SMALLINT", "int8": "TINYINT", "uint64": "UBIGINT", "uint32": "UINTEGER",
            "uint16": "USMALLINT", "uint8": "UTINYINT", "double": "DOUBLE", "float": "FLOAT",
            "float64": "DOUBLE", "float32": "FLOAT", "bool": "BOOLEAN", "date32[day]": "DATE",
            "date64[ms]": "DATE", "timestamp[ms]": "TIMESTAMP",
        }
        source_types = {item["name"]: type_aliases.get(item["type"].lower(), item["type"].upper()) for item in source_schema or []}
        target_types = {item["name"]: item["type"].upper() for item in schema}
        source_schema_match = source_schema is None or source_types == target_types
        schema_pass = expected_names_pass and source_schema_match
        checks.append({
            "name": "schema", "pass": schema_pass, "schema_hash": schema_hash,
            "source_schema_match": source_schema_match, "columns": schema,
        })

        keys = list((config.get("keys") or {}).get("canonical") or [])
        duplicate_count = None
        distinct_count = None
        if keys:
            key_sql = ", ".join(quote_identifier(key) for key in keys)
            duplicate_count = connection.execute(
                f"SELECT COALESCE(SUM(n - 1), 0) FROM (SELECT COUNT(*) n FROM data GROUP BY {key_sql} HAVING COUNT(*) > 1)"
            ).fetchone()[0]
            distinct_count = connection.execute(f"SELECT COUNT(*) FROM (SELECT DISTINCT {key_sql} FROM data)").fetchone()[0]
            unique_pass = duplicate_count == 0 or not validation.get("require_unique_key", False)
            checks.append({"name": "canonical_key", "pass": unique_pass, "columns": keys, "distinct_count": distinct_count, "duplicate_key_count": duplicate_count})

        null_counts = {}
        required_non_null = list(validation.get("non_null_columns") or [])
        for column in required_non_null:
            count = connection.execute(f"SELECT COUNT(*) FROM data WHERE {quote_identifier(column)} IS NULL").fetchone()[0]
            null_counts[column] = count
        checks.append({"name": "nulls", "pass": all(value == 0 for value in null_counts.values()), "counts": null_counts})

        ranges = {}
        range_columns = list(validation.get("range_columns") or [])
        for column in range_columns:
            ranges[column] = dict(zip(("min", "max"), connection.execute(
                f"SELECT MIN({quote_identifier(column)}), MAX({quote_identifier(column)}) FROM data"
            ).fetchone()))
        checks.append({"name": "ranges", "pass": True, "values": ranges})

        sample_match = None
        if config["source"].get("format") == "sqlite" and keys:
            table = config["source"]["table"]
            key_sql = ", ".join(quote_identifier(key) for key in keys)
            source_db = sqlite3.connect(f"file:{Path(config['source']['path']).resolve()}?mode=ro", uri=True)
            try:
                source_sample = source_db.execute(f"SELECT {key_sql} FROM {quote_identifier(table)} ORDER BY {key_sql} LIMIT 100").fetchall()
            finally:
                source_db.close()
            target_sample = connection.execute(f"SELECT {key_sql} FROM data ORDER BY {key_sql} LIMIT 100").fetchall()
            normalized_source = [[None if value is None else str(value) for value in row] for row in source_sample]
            normalized_target = [[None if value is None else str(value) for value in row] for row in target_sample]
            sample_match = normalized_source == normalized_target
            checks.append({"name": "sample_keys", "pass": sample_match, "rows": len(source_sample)})

        passed = all(item["pass"] for item in checks)
        return {
            "status": "success" if passed else "VALIDATION_FAILED",
            "passed": passed,
            "row_count_source": source_count,
            "row_count_target": target_count,
            "distinct_key_count": distinct_count,
            "duplicate_key_count": duplicate_count,
            "schema_hash": schema_hash,
            "schema_match": schema_pass,
            "sample_match": sample_match,
            "checks": checks,
        }
    finally:
        connection.close()
