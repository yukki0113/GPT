from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from data_storage.benchmark import benchmark
from data_storage.config import load_config
from data_storage.query import execute_query
from data_storage.runner import run_config
from data_storage.errors import ConfigError


def sqlite_fixture(tmp_path: Path, duplicate: bool = False) -> Path:
    path = tmp_path / "source.sqlite"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE records(event_date TEXT NOT NULL, entity_id INTEGER NOT NULL, value REAL)")
        rows = [("2026-01-01", 1, 1.5), ("2026-01-02", 2, None)]
        if duplicate:
            rows.append(rows[0])
        connection.executemany("INSERT INTO records VALUES(?,?,?)", rows)
    return path


def base_config(tmp_path: Path, duplicate: bool = False, compression: str = "zstd") -> dict:
    source = sqlite_fixture(tmp_path, duplicate)
    return {
        "source": {"format": "sqlite", "path": str(source), "table": "records"},
        "target": {"format": "parquet", "path": str(tmp_path / f"data-{compression}.parquet"), "compression": compression},
        "keys": {"canonical": ["event_date", "entity_id"]},
        "sort_by": ["event_date", "entity_id"],
        "validation": {"require_unique_key": True, "require_row_count_match": True, "non_null_columns": ["event_date", "entity_id"], "range_columns": ["event_date", "value"]},
        "audit": {"path": str(tmp_path / "audit.json")},
    }


@pytest.mark.parametrize("compression", ["zstd", "snappy"])
def test_sqlite_to_parquet_and_query(tmp_path: Path, compression: str):
    config = base_config(tmp_path, compression=compression)
    result = run_config(config)
    assert result["status"] == "success"
    assert result["row_count_source"] == result["validation"]["row_count_target"] == 2
    assert result["validation"]["schema_match"] is True
    columns, rows = execute_query(config["target"]["path"], "SELECT COUNT(*) n FROM data WHERE value IS NOT NULL")
    assert columns == ["n"] and rows == [(1,)]
    assert Path(config["audit"]["path"]).exists()


def test_csv_schema_to_parquet(tmp_path: Path):
    source = tmp_path / "source.csv"
    source.write_text("event_date,entity_id,value\n2026-01-01,1,1.5\n", encoding="utf-8")
    config = {
        "source": {"format": "csv", "path": str(source), "encoding": "utf-8", "delimiter": ",", "schema": {"event_date": "string", "entity_id": "int64", "value": "float64"}},
        "target": {"path": str(tmp_path / "csv.parquet"), "compression": "zstd"},
        "keys": {"canonical": ["event_date", "entity_id"]},
        "validation": {"require_unique_key": True, "require_row_count_match": True},
    }
    result = run_config(config)
    assert result["status"] == "success"
    assert result["validation"]["row_count_target"] == 1


def test_duplicate_is_validation_failure_and_cli_nonzero(tmp_path: Path):
    config = base_config(tmp_path, duplicate=True)
    config_path = tmp_path / "config.yaml"
    import yaml
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    completed = subprocess.run([sys.executable, "-m", "data_storage", "run-config", str(config_path)], capture_output=True, text=True)
    assert completed.returncode != 0
    assert json.loads(completed.stdout)["status"] == "VALIDATION_FAILED"


def test_partitioned_dataset(tmp_path: Path):
    config = base_config(tmp_path)
    config["target"]["path"] = str(tmp_path / "partitioned")
    config["target"]["partition_by"] = ["entity_id"]
    result = run_config(config)
    assert result["status"] == "success"
    assert len(list((tmp_path / "partitioned").rglob("*.parquet"))) == 2


def test_benchmark_runner(tmp_path: Path):
    config = base_config(tmp_path)
    assert run_config(config)["status"] == "success"
    config["benchmark"] = {
        "repeats": 2, "modes": ["warm"],
        "sources": [
            {"name": "sqlite", "engine": "sqlite", "path": config["source"]["path"], "table": "records"},
            {"name": "parquet", "engine": "parquet", "path": config["target"]["path"]},
        ],
        "queries": [{"name": "count", "sql": "SELECT COUNT(*) FROM {table}"}],
    }
    result = benchmark(config)
    assert result["status"] == "success"
    assert result["queries"][0]["results"]["parquet"]["warm"]["rows_returned"] == 1


def test_invalid_config(tmp_path: Path):
    path = tmp_path / "bad.yaml"
    path.write_text("source: []\n", encoding="utf-8")
    with pytest.raises(Exception):
        load_config(path)


def test_existing_target_fails_closed(tmp_path: Path):
    config = base_config(tmp_path)
    assert run_config(config)["status"] == "success"
    with pytest.raises(ConfigError, match="target already exists"):
        run_config(config)
