#!/usr/bin/env python3
"""Build an immutable JRDB Edge Registry Parquet generation from Registry SQLite."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from data_storage.convert import convert
from data_storage.validate import validate

ARTIFACT_TYPE = "jrdb_edge_registry"
SCHEMA_VERSION = "v0.2"
TABLES = (
    ("edge_registry_meta", ["registry_version"]),
    ("edge_definition", ["edge_id"]),
    ("edge_metric_snapshot", ["edge_id", "snapshot_id"]),
    ("edge_validation_event", ["validation_id"]),
)


class EdgeRegistryParquetError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def build_generation(
    *, sqlite_path: Path, output_root: Path, generation_id: str,
    serving_jsonl: Path | None = None,
) -> dict[str, Any]:
    if not sqlite_path.is_file():
        raise EdgeRegistryParquetError(f"Registry SQLite missing: {sqlite_path}")
    generation_dir=output_root/"generations"/generation_id
    if generation_dir.exists():
        raise FileExistsError(generation_dir)
    generation_dir.mkdir(parents=True)

    with sqlite3.connect(f"file:{sqlite_path.resolve()}?mode=ro",uri=True) as con:
        existing={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required={name for name,_ in TABLES}
    if not required.issubset(existing):
        raise EdgeRegistryParquetError(f"missing registry tables: {sorted(required-existing)}")

    table_assets={}
    audits={}
    for table, keys in TABLES:
        target=generation_dir/f"{table}.parquet"
        config={
            "source":{"format":"sqlite","path":str(sqlite_path),"table":table,"batch_size":50000},
            "target":{"path":str(target),"compression":"zstd","partition_by":[]},
            "keys":{"canonical":keys},
            "sort_by":keys,
            "validation":{"require_row_count_match":True,"require_unique_key":True},
        }
        conversion=convert(config)
        validation=validate(config,conversion)
        if validation.get("status")!="success" or validation.get("passed") is not True:
            raise EdgeRegistryParquetError(f"{table}: data-storage validation failed")
        table_assets[table]={
            "relative_path":f"generations/{generation_id}/{table}.parquet",
            "rows":int(conversion["row_count_source"]),
            "size_bytes":target.stat().st_size,
            "sha256":_sha256(target),
            "canonical_key":keys,
        }
        audits[table]={"conversion":conversion,"validation":validation}

    serving_asset=None
    if serving_jsonl is not None:
        if not serving_jsonl.is_file():
            raise EdgeRegistryParquetError(f"serving JSONL missing: {serving_jsonl}")
        dest=generation_dir/"edge_serving_catalog.jsonl"
        dest.write_bytes(serving_jsonl.read_bytes())
        serving_asset={
            "relative_path":f"generations/{generation_id}/edge_serving_catalog.jsonl",
            "size_bytes":dest.stat().st_size,
            "sha256":_sha256(dest),
        }

    audit_path=generation_dir/"audit.json"
    audit_payload={
        "status":"PASS","artifact_type":ARTIFACT_TYPE,"schema_version":SCHEMA_VERSION,
        "generation_id":generation_id,"tables":audits,
    }
    audit_path.write_text(json.dumps(audit_payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")

    manifest={
        "artifact_type":ARTIFACT_TYPE,
        "schema_version":SCHEMA_VERSION,
        "storage_format":"parquet",
        "storage_version":"1",
        "generation_id":generation_id,
        "validation_status":"PASS",
        "created_at":dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_sqlite_sha256":_sha256(sqlite_path),
        "tables":table_assets,
        "serving_catalog":serving_asset,
        "audit":{
            "relative_path":f"generations/{generation_id}/audit.json",
            "size_bytes":audit_path.stat().st_size,
            "sha256":_sha256(audit_path),
        },
    }
    manifest_path=generation_dir/"manifest.json"
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return {
        "status":"PASS","generation_id":generation_id,
        "table_rows":{k:v["rows"] for k,v in table_assets.items()},
        "manifest":str(manifest_path),"manifest_sha256":_sha256(manifest_path),
        "serving_sha256":serving_asset["sha256"] if serving_asset else None,
    }


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--sqlite",type=Path,required=True)
    p.add_argument("--output-root",type=Path,required=True)
    p.add_argument("--generation-id",required=True)
    p.add_argument("--serving-jsonl",type=Path)
    p.add_argument("--result-json",type=Path)
    a=p.parse_args()
    result=build_generation(sqlite_path=a.sqlite,output_root=a.output_root,generation_id=a.generation_id,serving_jsonl=a.serving_jsonl)
    if a.result_json:
        a.result_json.parent.mkdir(parents=True,exist_ok=True)
        a.result_json.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))


if __name__=="__main__":
    main()
