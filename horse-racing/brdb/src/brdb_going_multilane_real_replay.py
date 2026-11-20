#!/usr/bin/env python3
"""Source-real BRDB v0.6 replay; exports aggregate audit only."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from collections import Counter

HERE=Path(__file__).resolve().parent
JRDB_SRC=HERE.parents[1]/'jrdb'/'src'
if str(JRDB_SRC) not in sys.path:sys.path.insert(0,str(JRDB_SRC))
from jrdb_raw import Parser,iter_archive_records
from brdb_going_condition_compare import _load_parts,band
from brdb_going_multilane_discovery import build_from_aggregated,GOING_STATES,SCOPE_PRIORITY,VERSION

GOING_CODES={'良':('10','11','12'),'稍重':('20','21','22'),'重':('30','31','32'),'不良':('40','41','42')}

def req(ok,msg):
    if not ok:raise ValueError(msg)

def cohort(paci,target_date,race_key):
    p=Parser(); ukc={}
    for _,raw in iter_archive_records(Path(paci),'UKC'):
        x=p.ukc(raw);ukc[x['horse_id']]=x
    bac=[p.bac(raw) for _,raw in iter_archive_records(Path(paci),'BAC') if raw[:8].decode('ascii')==race_key]
    req(len(bac)==1,'target BAC');r=bac[0]
    hs=[]
    for _,raw in iter_archive_records(Path(paci),'KYI'):
        if raw[:8].decode('ascii')!=race_key:continue
        k=p.kyi(raw);hid=k['blood_registration_no'];u=ukc.get(hid);req(u is not None,'UKC missing')
        req(u.get('sire_name') and u.get('broodmare_sire_name'),'pedigree name missing')
        req(u.get('sire_line_code') and u.get('broodmare_sire_line_code'),'line code missing')
        hs.append({'horse_no':k['horse_no'],'horse_id':hid,'sire_name':u['sire_name'],
                   'broodmare_sire_name':u['broodmare_sire_name'],'sire_line_code':u['sire_line_code'],
                   'broodmare_sire_line_code':u['broodmare_sire_line_code']})
    req(len(hs)==r['field_size'],'cohort incomplete')
    race={'race_key':race_key,'target_date':target_date,'surface_code':r['surface_code'],
          'distance_m':int(r['distance_raw']),'venue_code':race_key[:2],
          'course_code':r['course_code'],'field_size':int(r['field_size'])}
    return race,hs

def where_scope(scope,race):
    if scope=='VENUE_COURSE_DISTANCE':return 'venue_code=? AND course_code=? AND distance_m=?',[race['venue_code'],race['course_code'],race['distance_m']]
    if scope=='VENUE_DISTANCE':return 'venue_code=? AND distance_m=?',[race['venue_code'],race['distance_m']]
    if scope=='ALL_VENUES_DISTANCE':return 'distance_m=?',[race['distance_m']]
    if scope=='VENUE_BAND':return 'venue_code=? AND band=?',[race['venue_code'],band(race['distance_m'])]
    if scope=='ALL_VENUES_BAND':return 'band=?',[band(race['distance_m'])]
    raise ValueError(scope)

def main():
    ap=argparse.ArgumentParser()
    for x in ('manifest','objects-root','paci','race-key','target-date','output'):ap.add_argument('--'+x,required=True)
    a=ap.parse_args();race,horses=cohort(a.paci,a.target_date,a.race_key)
    mf,paths,checked=_load_parts(a.manifest,a.objects_root,a.target_date)
    import duckdb
    con=duckdb.connect(':memory:')
    try:
      qpaths=','.join("'"+p.replace("'","''")+"'" for p in paths)
      con.execute('CREATE TEMP VIEW source AS SELECT * FROM read_parquet(['+qpaths+'],union_by_name=true)')
      need={'race_date','horse_id','sire_name','broodmare_sire_name','sire_line_code','broodmare_sire_line_code','track_type','distance','venue_code','course_code','track_condition_code','finish','abnormal_code'}
      have={x[0] for x in con.execute('DESCRIBE source').fetchall()};req(need<=have,'analysis missing columns')
      con.execute("""CREATE TEMP TABLE eligible AS SELECT sire_name,broodmare_sire_name,sire_line_code,broodmare_sire_line_code,
        venue_code,course_code,try_cast(distance AS INT) distance_m,
        CASE WHEN try_cast(distance AS INT)<1400 THEN 'SHORT' WHEN try_cast(distance AS INT)<1800 THEN 'MILE' WHEN try_cast(distance AS INT)<2400 THEN 'MIDDLE' ELSE 'LONG' END band,
        CASE WHEN track_condition_code IN ('10','11','12') THEN '良' WHEN track_condition_code IN ('20','21','22') THEN '稍重' WHEN track_condition_code IN ('30','31','32') THEN '重' WHEN track_condition_code IN ('40','41','42') THEN '不良' ELSE NULL END going_state,
        try_cast(finish AS INT) finish FROM source WHERE race_date<? AND track_type=? AND abnormal_code='0' AND try_cast(finish AS INT) BETWEEN 1 AND 18""",[a.target_date,race['surface_code']])
      counts={}
      for h in horses:
        lanes={'sire':('sire_name=?',[h['sire_name']]),'broodmare_sire':('broodmare_sire_name=?',[h['broodmare_sire_name']]),
               'pairing':('sire_line_code=? AND broodmare_sire_line_code=?',[h['sire_line_code'],h['broodmare_sire_line_code']])}
        laneout={}
        for lname,(entity_where,entity_params) in lanes.items():
          sout={}
          for scope in SCOPE_PRIORITY:
            sw,sp=where_scope(scope,race)
            rows=con.execute(f'''SELECT going_state,count(*)::INT,sum((finish=1)::INT)::INT,sum((finish<=3)::INT)::INT
              FROM eligible WHERE going_state IS NOT NULL AND {entity_where} AND {sw} GROUP BY 1''',entity_params+sp).fetchall()
            d={g:(n,w,t) for g,n,w,t in rows};sout[scope]={g:d.get(g,(0,0,0)) for g in GOING_STATES}
          laneout[lname]=sout
        counts[h['horse_id']]=laneout
      result=build_from_aggregated(race,horses,counts,source={'generation_id':mf['generation_id'],'verified_partitions':checked,'historical_profile_asof':'AS_OF_UNVERIFIED','denominator':'NORMAL_FINISHERS_ONLY'})
      # Aggregate-only audit, safe for public Actions artifact.
      summ=result['summary']
      audit={'audit_version':'brdb-going-multilane-real-replay-audit-v0.6','status':'RESEARCH_ONLY','contract_version':VERSION,
             'race_key':race['race_key'],'target_date':race['target_date'],'horse_count':len(horses),'source':result['source'],
             'summary':summ,'relative_lane_real_input':'NOT_INCLUDED_IN_PUBLIC_CI',
             'no_horse_level_details_exported':True,'prediction_eligible':False,'display_eligible':False,'production_authorized':False}
      out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(audit,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
      print(json.dumps({'status':'RESEARCH_ONLY','horse_count':len(horses),'selected_rows':sum(x['count'] for x in summ['selected_observations']),
                        'alignments':sum(x['count'] for x in summ['cross_lane_alignments'])},ensure_ascii=False))
    finally:con.close()
if __name__=='__main__':main()
