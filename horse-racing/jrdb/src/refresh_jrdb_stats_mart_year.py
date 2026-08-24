#!/usr/bin/env python3
"""Refresh one or more yearly Stats Mart partitions from Analysis Lite."""
from __future__ import annotations
import argparse, json, sqlite3
from pathlib import Path

VERSION='1.0-production'

def aggregate(conn: sqlite3.Connection, year:int, dim:str):
    name={'sire':'sire_name','jockey':'jockey_name','frame':'frame_no'}[dim]
    where=(f"trim(coalesce({name},''))<>''" if dim!='frame' else 'frame_no is not null')
    sql=f'''SELECT year,venue_code,track_type,distance,coalesce(track_condition_code,''),{name},
      count(*),sum(finish=1),sum(finish=2),sum(finish=3),sum(finish between 1 and 3),
      sum(coalesce(win_payout,0)),sum(coalesce(place_payout,0))
      FROM fact_entry_result_lite WHERE year=? AND {where}
      GROUP BY year,venue_code,track_type,distance,coalesce(track_condition_code,''),{name}'''
    return list(conn.execute(sql,(year,)))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--analysis',type=Path,required=True);ap.add_argument('--mart',type=Path,required=True);ap.add_argument('--years',nargs='+',type=int,required=True);a=ap.parse_args()
    src=sqlite3.connect(a.analysis); dst=sqlite3.connect(a.mart)
    out=[]
    try:
        for year in sorted(set(a.years)):
            if src.execute('select count(*) from fact_entry_result_lite where year=?',(year,)).fetchone()[0]==0: raise SystemExit(f'No Analysis rows for year {year}')
            sire=aggregate(src,year,'sire'); jockey=aggregate(src,year,'jockey'); frame=aggregate(src,year,'frame')
            dst.execute('begin immediate')
            for table in ['mart_sire_yearly','mart_jockey_yearly','mart_frame_yearly']: dst.execute(f'delete from {table} where year=?',(year,))
            dst.executemany('insert into mart_sire_yearly values('+','.join('?'*13)+')',sire)
            dst.executemany('insert into mart_jockey_yearly values('+','.join('?'*13)+')',jockey)
            dst.executemany('insert into mart_frame_yearly values('+','.join('?'*13)+')',frame)
            dst.execute('commit')
            out.append({'year':year,'sire_rows':len(sire),'jockey_rows':len(jockey),'frame_rows':len(frame)})
        print(json.dumps({'refreshed':out,'integrity_check':dst.execute('pragma integrity_check').fetchone()[0]},ensure_ascii=False,indent=2))
    except Exception:
        if dst.in_transaction: dst.execute('rollback')
        raise
    finally:
        src.close();dst.close()
if __name__=='__main__':main()
