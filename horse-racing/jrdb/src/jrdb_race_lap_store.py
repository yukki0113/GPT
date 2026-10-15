"""Read-only physical access to one immutable JRDB race-lap Parquet snapshot."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from jrdb_race_lap_contract import (
    COLUMN_TYPES, DATASET_SCHEMA_VERSION, LOGIC_VERSION, decode_row, normalize_race_key,
)


class RaceLapStoreError(RuntimeError):
    """The physical dataset cannot satisfy the race-lap contract."""


class RaceLapStore:
    """Use a fresh in-memory DuckDB connection per call; no persistent database.

    The supplied Parquet must remain immutable for this instance's lifetime.
    Constructor validation scans every row, prioritizing correctness in v0.1.
    """

    def __init__(self, parquet_path: Path) -> None:
        self.path = Path(parquet_path).resolve()
        if not self.path.is_file():
            raise RaceLapStoreError(f"Parquet file not found: {self.path}")
        try:
            import duckdb
        except ImportError as exc:
            raise RaceLapStoreError("RaceLapStore requires duckdb; use tools/data-storage requirements") from exc
        self._duckdb = duckdb
        try:
            description = self._query("DESCRIBE SELECT * FROM read_parquet(?, hive_partitioning=false)", [str(self.path)])
            actual = {r["column_name"]: r["column_type"] for r in description}
            for name, kind in COLUMN_TYPES.items():
                if actual.get(name) != kind:
                    raise RaceLapStoreError(f"required column/type mismatch: {name}: expected {kind}, got {actual.get(name)}")
            rows = self._query(self._select(), [str(self.path)])
            seen = set()
            dates = []
            for raw in rows:
                row = self._decode(raw)
                key = row["race_key"]
                if key in seen:
                    raise RaceLapStoreError(f"duplicate race_key: {key}")
                seen.add(key)
                dates.append(row["race_date"])
            if not rows:
                raise RaceLapStoreError("empty dataset has no verifiable schema/logic version")
            self._metadata = {
                "parquet_path": str(self.path), "race_count": len(rows),
                "dataset_schema_version": DATASET_SCHEMA_VERSION,
                "shape_logic_version": LOGIC_VERSION,
                "min_race_date": min(dates), "max_race_date": max(dates),
            }
        except RaceLapStoreError:
            raise
        except (ValueError, TypeError, KeyError) as exc:
            raise RaceLapStoreError(f"invalid race-lap dataset: {exc}") from exc

    @staticmethod
    def _select() -> str:
        columns = ", ".join(f'"{name}"' for name in COLUMN_TYPES)
        return f"SELECT {columns} FROM read_parquet(?, hive_partitioning=false)"

    def _query(self, sql: str, params: list[Any]) -> list[dict[str, Any]]:
        connection = self._duckdb.connect(":memory:")
        try:
            cursor = connection.execute(sql, params)
            names = [column[0] for column in cursor.description]
            return [dict(zip(names, values, strict=True)) for values in cursor.fetchall()]
        except self._duckdb.Error as exc:
            raise RaceLapStoreError(f"cannot read race-lap Parquet: {exc}") from exc
        finally:
            connection.close()

    @staticmethod
    def _decode(raw: dict[str, Any]) -> dict[str, Any]:
        try:
            return decode_row(raw)
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            raise RaceLapStoreError(f"invalid stored race {raw.get('race_key')!r}: {exc}") from exc

    def metadata(self) -> dict[str, object]:
        return dict(self._metadata)

    def get(self, race_key: str) -> dict[str, object] | None:
        key = normalize_race_key(race_key)
        return self.get_many([key])[key]

    def get_many(self, race_keys: Iterable[str]) -> dict[str, dict[str, object] | None]:
        keys = list(dict.fromkeys(normalize_race_key(key) for key in race_keys))
        result: dict[str, dict[str, object] | None] = dict.fromkeys(keys)
        if not keys:
            return result
        marks = ", ".join("?" for _ in keys)
        rows = self._query(self._select() + f" WHERE race_key IN ({marks})", [str(self.path), *keys])
        for raw in rows:
            row = self._decode(raw)
            key = row["race_key"]
            if result[key] is not None:
                raise RaceLapStoreError(f"duplicate lookup result: {key}")
            result[key] = row
        return result
