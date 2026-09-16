from __future__ import annotations

import sqlite3
import statistics
import time
from pathlib import Path

from .common import size_bytes
from .query import connect_parquet


def _run_sqlite(path: Path, table: str, sql: str, repeats: int, cold: bool) -> dict:
    timings, rows = [], None
    connection = None
    try:
        if not cold:
            connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        for _ in range(repeats):
            current = sqlite3.connect(f"file:{path}?mode=ro", uri=True) if cold else connection
            started = time.perf_counter()
            result = current.execute(sql.replace("{table}", f'"{table}"')).fetchall()
            timings.append((time.perf_counter() - started) * 1000)
            rows = len(result)
            if cold:
                current.close()
    finally:
        if connection is not None:
            connection.close()
    return {"median_ms": round(statistics.median(timings), 3), "runs_ms": [round(v, 3) for v in timings], "rows_returned": rows}


def _run_parquet(path: Path, sql: str, repeats: int, cold: bool) -> dict:
    timings, rows = [], None
    connection = None
    try:
        if not cold:
            connection = connect_parquet(path)
        for _ in range(repeats):
            current = connect_parquet(path) if cold else connection
            started = time.perf_counter()
            result = current.execute(sql.replace("{table}", "data")).fetchall()
            timings.append((time.perf_counter() - started) * 1000)
            rows = len(result)
            if cold:
                current.close()
    finally:
        if connection is not None:
            connection.close()
    return {"median_ms": round(statistics.median(timings), 3), "runs_ms": [round(v, 3) for v in timings], "rows_returned": rows}


def benchmark(config: dict) -> dict:
    spec = config.get("benchmark") or {}
    repeats = int(spec.get("repeats", 5))
    modes = spec.get("modes") or ["warm"]
    sources = spec.get("sources") or []
    queries = spec.get("queries") or []
    result = {"repeats": repeats, "storage": [], "queries": []}
    for source in sources:
        path = Path(source["path"]).resolve()
        result["storage"].append({"name": source["name"], "engine": source["engine"], "path": str(path), "size_bytes": size_bytes(path)})
    for query in queries:
        entry = {"name": query["name"], "results": {}}
        for source in sources:
            path = Path(source["path"]).resolve()
            entry["results"][source["name"]] = {}
            for mode in modes:
                cold = mode == "cold"
                if source["engine"] == "sqlite":
                    measured = _run_sqlite(path, source["table"], query["sql"], repeats, cold)
                elif source["engine"] == "parquet":
                    measured = _run_parquet(path, query["sql"], repeats, cold)
                else:
                    continue
                entry["results"][source["name"]][mode] = measured
        result["queries"].append(entry)
    result["status"] = "success"
    return result

