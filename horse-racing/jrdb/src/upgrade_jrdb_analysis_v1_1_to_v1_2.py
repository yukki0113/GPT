#!/usr/bin/env python3
"""Upgrade an existing Analysis Lite v1.1 DB to v1.2 and backfill first-previous-result keys from annual KYI Raw."""
from __future__ import annotations
import argparse, json, re, sqlite3, zipfile
from pathlib import Path

VERSION="1.0-production"

def text(raw:bytes,o:int,w:int)->str:
    return raw[o:o+w].decode('cp932','replace').strip()
def num(raw:bytes,o:int,w:int):
    try:return int(text(raw,o,w))
    except:return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--db',type=Path,required=True)
    ap.add_argument('--raw-root',type=Path,required=True)
    ap.add_argument('--years',nargs='+',type=int,required=True)
    args=ap.parse_args()
    conn=sqlite3.connect(args.db)
    cols={r[1] for r in conn.execute('pragma table_info(fact_entry_result_lite)')}
    if 'prev_result_key_1' not in cols: conn.execute('alter table fact_entry_result_lite add column prev_result_key_1 TEXT')
    if 'prev_race_key_1' not in cols: conn.execute('alter table fact_entry_result_lite add column prev_race_key_1 TEXT')
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS meta_analysis_ingest_batch(
      batch_id INTEGER PRIMARY KEY,target_date TEXT NOT NULL,builder_version TEXT NOT NULL,
      schema_version TEXT NOT NULL,started_at TEXT NOT NULL,finished_at TEXT,status TEXT NOT NULL,
      source_manifest TEXT,source_sha256s TEXT,race_count INTEGER,row_count INTEGER,
      replaced_row_count INTEGER,message TEXT);
    CREATE INDEX IF NOT EXISTS ix_analysis_ingest_date ON meta_analysis_ingest_batch(target_date,status);
    ''')
    total=0
    batch=[]
    for year in sorted(args.years):
        zp=args.raw_root/'KYI'/f'KYI_{year}.zip'
        with zipfile.ZipFile(zp) as zf:
            names=[n for n in zf.namelist() if re.fullmatch(r'KYI\d{6}\.txt',Path(n).name,re.I)]
            for name in names:
                for raw in zf.read(name).splitlines():
                    rk=text(raw,0,8); hn=num(raw,8,2)
                    pr=text(raw,203,16) or None; rr=text(raw,283,8) or None
                    if pr or rr:
                        batch.append((pr,rr,rk,hn)); total+=1
                    if len(batch)>=50000:
                        conn.executemany('UPDATE fact_entry_result_lite SET prev_result_key_1=?,prev_race_key_1=? WHERE race_key=? AND horse_no=?',batch);batch=[]
    if batch: conn.executemany('UPDATE fact_entry_result_lite SET prev_result_key_1=?,prev_race_key_1=? WHERE race_key=? AND horse_no=?',batch)
    conn.commit()
    filled=conn.execute("select count(*) from fact_entry_result_lite where prev_result_key_1 is not null or prev_race_key_1 is not null").fetchone()[0]
    integrity=conn.execute('pragma integrity_check').fetchone()[0]
    print(json.dumps({'updated_candidates':total,'filled_rows':filled,'integrity_check':integrity,'size_bytes':args.db.stat().st_size},indent=2))
    conn.close()
if __name__=='__main__':main()
