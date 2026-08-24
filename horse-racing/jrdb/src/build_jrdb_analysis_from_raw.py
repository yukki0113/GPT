#!/usr/bin/env python3
"""Build JRDB Analysis Lite v1.2 directly from annual Raw ZIPs.

Production rebuild path using BAC/KYI/SED/CYB/UKC. v1.2 adds first-previous-result keys
while retaining the validated one-entry-per-row Analysis design.
"""
from __future__ import annotations
import argparse, datetime as dt, re, sqlite3, zipfile
from pathlib import Path

VERSION="1.1-production"
SCHEMA_VERSION="v1.2"
FACT_COLUMNS=(
"race_date","year","venue_code","race_no","track_type","distance","race_condition_code","track_condition_code","grade_code",
"race_key","horse_no","frame_no","horse_id","horse_name","sex_code","age","sire_name","broodmare_sire_name","sire_line_code",
"broodmare_sire_line_code","jockey_name","running_style","distance_aptitude","uptrend","training_index","finish","abnormal_code",
"final_win_odds","final_win_popularity","win_payout","place_payout","prev_result_key_1","prev_race_key_1")

def text(raw,o,w): return raw[o:o+w].decode('cp932','replace').strip()
def num(raw,o,w):
    try:return int(text(raw,o,w).replace(',',''))
    except:return None

def date_from_name(name,year):
    m=re.fullmatch(r'[A-Z]+(\d{6})\.txt',Path(name).name,re.I)
    if not m:return None
    x=m.group(1)
    if int(x[:2])!=year%100:return None
    try:return dt.date(year,int(x[2:4]),int(x[4:6])).isoformat()
    except:return None

def canonical_members(zf,kind):
    pat=re.compile(rf'^{kind}\d{{6}}\.txt$',re.I)
    return sorted([n for n in zf.namelist() if pat.fullmatch(Path(n).name)],key=lambda n:Path(n).name.upper())

def ukc(raw):
    if len(raw)!=290: return None
    bd=text(raw,157,8); by=int(bd[:4]) if len(bd)>=4 and bd[:4].isdigit() else None
    return dict(sex_code=text(raw,44,1),birth_year=by,sire_name=text(raw,49,36),broodmare_sire_name=text(raw,121,36),
                sire_line_code=text(raw,276,4),broodmare_sire_line_code=text(raw,280,4),data_date=text(raw,268,8))

def build(raw_root:Path,years:list[int],out:Path,schema:Path):
    if out.exists(): raise SystemExit(f'Refusing to overwrite existing DB: {out}')
    c=sqlite3.connect(out); c.execute('pragma journal_mode=MEMORY'); c.execute('pragma synchronous=OFF')
    c.executescript(schema.read_text(encoding='utf-8'))
    started=dt.datetime.now().isoformat(timespec='seconds')
    bid=c.execute("insert into meta_analysis_build(builder_version,schema_version,started_at,status) values(?,?,?,?)",(VERSION,SCHEMA_VERSION,started,'RUNNING')).lastrowid
    races={}; entries={}; results={}; training={}; horses={}
    for year in sorted(years):
        with zipfile.ZipFile(raw_root/'UKC'/f'UKC_{year}.zip') as zf:
            for m in canonical_members(zf,'UKC'):
                for raw in zf.read(m).splitlines():
                    p=ukc(raw)
                    if p is None: continue
                    hid=text(raw,0,8); old=horses.get(hid)
                    if old is None or str(p['data_date'])>=str(old['data_date']): horses[hid]=p
        with zipfile.ZipFile(raw_root/'BAC'/f'BAC_{year}.zip') as zf:
            for m in canonical_members(zf,'BAC'):
                d=date_from_name(m,year)
                for raw in zf.read(m).splitlines():
                    rk=text(raw,0,8); races.setdefault(rk,dict(race_date=d,year=year,venue_code=text(raw,0,2),race_no=num(raw,6,2),distance=num(raw,20,4),track_type=text(raw,24,1),race_condition_code=text(raw,29,2),track_condition_code=None,grade_code=text(raw,35,1)))
        with zipfile.ZipFile(raw_root/'KYI'/f'KYI_{year}.zip') as zf:
            for m in canonical_members(zf,'KYI'):
                for raw in zf.read(m).splitlines():
                    rk,hn=text(raw,0,8),num(raw,8,2)
                    entries.setdefault((rk,hn),dict(frame_no=num(raw,323,1),horse_id=text(raw,10,8),horse_name=text(raw,18,36),jockey_name=text(raw,171,12),running_style=text(raw,89,1),distance_aptitude=text(raw,90,1),uptrend=text(raw,91,1),prev_result_key_1=text(raw,203,16) or None,prev_race_key_1=text(raw,283,8) or None))
        with zipfile.ZipFile(raw_root/'SED'/f'SED_{year}.zip') as zf:
            for m in canonical_members(zf,'SED'):
                d=date_from_name(m,year)
                for raw in zf.read(m).splitlines():
                    rk,hn=text(raw,0,8),num(raw,8,2); tc=text(raw,69,2)
                    if rk not in races:
                        races[rk]=dict(race_date=d,year=year,venue_code=text(raw,0,2),race_no=num(raw,6,2),distance=num(raw,62,4),track_type=text(raw,66,1),race_condition_code=None,track_condition_code=tc,grade_code=None)
                    elif not races[rk]['track_condition_code']: races[rk]['track_condition_code']=tc
                    results.setdefault((rk,hn),dict(finish=num(raw,140,2),abnormal_code=text(raw,142,1),final_win_odds=num(raw,174,6),final_win_popularity=num(raw,180,2),win_payout=num(raw,341,7),place_payout=num(raw,348,7)))
        with zipfile.ZipFile(raw_root/'CYB'/f'CYB_{year}.zip') as zf:
            for m in canonical_members(zf,'CYB'):
                for raw in zf.read(m).splitlines(): training.setdefault((text(raw,0,8),num(raw,8,2)),num(raw,29,3))
    rows=[]; missing=0
    for key,e in entries.items():
        r=races.get(key[0]); rs=results.get(key)
        if r is None or rs is None: continue
        hp=horses.get(str(e['horse_id']),{})
        if not hp: missing+=1
        by=hp.get('birth_year'); age=int(r['year'])-int(by) if by else None
        rows.append((r['race_date'],r['year'],r['venue_code'],r['race_no'],r['track_type'],r['distance'],r['race_condition_code'],r['track_condition_code'],r['grade_code'],key[0],key[1],e['frame_no'],e['horse_id'],e['horse_name'],hp.get('sex_code'),age,hp.get('sire_name'),hp.get('broodmare_sire_name'),hp.get('sire_line_code'),hp.get('broodmare_sire_line_code'),e['jockey_name'],e['running_style'],e['distance_aptitude'],e['uptrend'],training.get(key),rs['finish'],rs['abnormal_code'],rs['final_win_odds'],rs['final_win_popularity'],rs['win_payout'],rs['place_payout'],e['prev_result_key_1'],e['prev_race_key_1']))
    sql=f"insert into fact_entry_result_lite({','.join(FACT_COLUMNS)}) values({','.join('?' for _ in FACT_COLUMNS)})"
    c.executemany(sql,rows); c.execute('analyze')
    c.execute("update meta_analysis_build set finished_at=?,status='SUCCESS',row_count=? where build_id=?",(dt.datetime.now().isoformat(timespec='seconds'),len(rows),bid)); c.commit()
    c.execute('vacuum')
    result=dict(rows=len(rows),missing_profile_rows=missing,prev1_nonblank=c.execute("select count(*) from fact_entry_result_lite where prev_result_key_1 is not null or prev_race_key_1 is not null").fetchone()[0],integrity_check=c.execute('pragma integrity_check').fetchone()[0],size_bytes=out.stat().st_size)
    c.close(); return result

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--years',nargs='+',type=int,required=True); ap.add_argument('--raw-root',type=Path,required=True); ap.add_argument('--db',type=Path,required=True); ap.add_argument('--schema',type=Path,default=Path(__file__).resolve().parents[1]/'schema'/'jrdb_analysis_schema_v1_2.sql'); a=ap.parse_args()
    for k,v in build(a.raw_root,a.years,a.db,a.schema).items(): print(f'{k}: {v}')
if __name__=='__main__':main()
