#!/usr/bin/env python3
"""Materialize Analysis v1.3 compatibility SQLite from a Parquet manifest."""
from __future__ import annotations
import argparse, json, sqlite3, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"tools"/"data-storage"))
from data_storage.query import connect_parquet

FACT="fact_entry_result_lite"; META=("meta_analysis_build","meta_analysis_ingest_batch")

def load_parquet(sqlite: sqlite3.Connection, table: str, path: Path) -> None:
    duck=connect_parquet(path)
    try:
        cols=[r[0] for r in duck.execute("DESCRIBE data").fetchall()]
        rows=duck.execute("SELECT * FROM data").fetchall()
    finally: duck.close()
    marks=",".join("?" for _ in cols); names=",".join(f'"{x}"' for x in cols)
    sqlite.executemany(f'INSERT INTO "{table}" ({names}) VALUES ({marks})',rows)

def materialize(manifest_path: Path, output: Path, schema: Path) -> dict:
    if output.exists(): raise FileExistsError(output)
    manifest=json.loads(manifest_path.read_text(encoding="utf-8")); root=manifest_path.parents[2]
    db=sqlite3.connect(output)
    try:
        db.executescript(schema.read_text(encoding="utf-8"))
        # Empty metadata table schema comes from v1.3 SQL; values are copied after facts.
        for part in manifest["fact_table"]["partitions"]: load_parquet(db,FACT,root/part["relative_path"])
        for table,entry in manifest["metadata_tables"].items(): load_parquet(db,table,root/entry["relative_path"])
        db.commit(); integrity=db.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity!="ok": raise RuntimeError(integrity)
        return {"status":"PASS","rows":db.execute(f"SELECT COUNT(*) FROM {FACT}").fetchone()[0],"integrity_check":integrity}
    finally: db.close()

def main():
 p=argparse.ArgumentParser();p.add_argument("--manifest",type=Path,required=True);p.add_argument("--out",type=Path,required=True);p.add_argument("--schema",type=Path,default=Path(__file__).resolve().parents[1]/"schema"/"jrdb_analysis_schema_v1_3.sql");a=p.parse_args();print(materialize(a.manifest,a.out,a.schema))
if __name__=="__main__":main()
