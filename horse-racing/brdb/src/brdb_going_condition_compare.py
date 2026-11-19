#!/usr/bin/env python3
"""Research-only, manifest-verified Analysis v1.4 going comparison.

Uses the accepted annual JRDB Analysis Parquet fact table, never a duplicate Raw
parser. Returns descriptive *observed* sire offspring statistics by matched
venue/distance/course scopes. Never returns a suitability judgement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path

VERSION = 'brdb-going-condition-comparison-v0.4-candidate'
GOING = {'10':'良','11':'良','12':'良', '20':'稍重','21':'稍重','22':'稍重',
         '30':'重','31':'重','32':'重','40':'不良','41':'不良','42':'不良'}
SCOPE_LABELS = ('VENUE_COURSE_DISTANCE','VENUE_DISTANCE','ALL_VENUES_DISTANCE',
                'VENUE_BAND','ALL_VENUES_BAND')
BANDS = ((0,1399,'SHORT'),(1400,1799,'MILE'),(1800,2399,'MIDDLE'),(2400,9999,'LONG'))


def require(condition, reason):
    if not condition: raise ValueError(reason)


def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def band(m):
    return next(b for lo,hi,b in BANDS if lo<=m<=hi)


def counts(n,w,top3):
    require(all(type(x) is int and x>=0 for x in (n,w,top3)) and w<=top3<=n,'count invalid')
    return {'starts':n,'wins':w,'top3':top3,'win_rate':round(w/n,6) if n else None,
            'top3_rate':round(top3/n,6) if n else None}


def observation(good, wet):
    """Keep small-sample positive observation while showing uncertainty.

    `wet` is slightly heavy/heavy/bad aggregated across same exact scope.
    Both are NORMAL_FINISHERS_ONLY. No suitability effect is inferred.
    """
    n0,w0,t0=good; n1,w1,t1=wet
    result={'good':counts(n0,w0,t0),'non_good':counts(n1,w1,t1),
            'comparison_status':'OBSERVED' if n0 and n1 else 'INSUFFICIENT_COMPARISON',
            'sample_status':'LOW_SAMPLE' if min(n0,n1)<20 else 'DESCRIPTIVE',
            'difference_top3_pp':round(100*(t1/n1-t0/n0),2) if n0 and n1 else None,
            'interpretation_status':'OBSERVATION_ONLY','prediction_eligible':False,
            'display_eligible':False,'suitability_claim':False}
    return result


def _input_field(field):
    require(field['contract_version']=='brdb-common-analysis-v0.1-candidate','common contract')
    require(field['release_status']=='RESEARCH_ONLY','research-only required')
    require(field['policy']['prediction_safe'] is False and
            field['policy']['production_authorized'] is False,'authorization violation')
    race=field['race'];d=race['target_date']
    require(field['as_of_exclusive']==d,'as-of mismatch')
    require(race['surface_code'] in ('1','2') and
            type(race['distance_m']) is int and race['distance_m']>0,'target context')
    ids=set();numbers=set()
    for h in field['horses']:
        require(re.fullmatch(r'[0-9]{8}',h['horse_id']) is not None,'horse id')
        require(h['horse_id'] not in ids and h['horse_no'] not in numbers,'duplicate horse')
        require(h['pedigree']['sire_name'],'sire missing')
        ids.add(h['horse_id']); numbers.add(h['horse_no'])
    require(len(ids)==race['field_size'],'full cohort required')
    return race


def _load_parts(manifest_path, objects_root, target):
    mf=json.loads(Path(manifest_path).read_text('utf-8'))
    require(mf['artifact_type']=='jrdb_analysis' and mf['schema_version']=='v1.4', 'source contract')
    require(mf['validation_status'] in ('PASS','SUCCESS'), 'manifest unvalidated')
    require(mf['fact_table']['name']=='fact_entry_result_lite','unexpected fact relation')
    require(mf['fact_table']['canonical_key']==['race_key','horse_no'],'canonical join contract')
    require(mf['storage_format']=='parquet','non-Parquet source')
    parts=mf['fact_table']['partitions']; seen=set(); paths=[];checked=0
    root=Path(objects_root).resolve()
    for p in parts:
        yr=int(p['year']); require(yr not in seen,'duplicate year partition');seen.add(yr)
        require(re.fullmatch(r'[0-9a-f]{64}',p['sha256']) is not None,'bad SHA')
        require(int(p['rows'])>0 and int(p['size_bytes'])>0,'invalid partition manifest')
        expected=Path('objects')/'fact_entry_result_lite'/f'year={yr}'/(p['sha256']+'.parquet')
        require(Path(p['relative_path'])==expected,'unexpected partition path')
        # All manifest paths must be validated, including post-target year partitions.
        path=(root/expected).resolve();require(path.is_relative_to(root),'unsafe path')
        require(path.is_file() and path.stat().st_size==p['size_bytes'],'partition missing or size mismatch')
        require(sha(path)==p['sha256'],'partition SHA mismatch')
        checked+=1
        if yr <= date.fromisoformat(target).year:paths.append(str(path))
    require(paths,'no historical partitions')
    return mf,paths,checked


def build(common,manifest_path,objects_root):
    race=_input_field(common);cutoff=race['target_date']; mf,paths,checked=_load_parts(manifest_path,objects_root,cutoff)
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError('Pinned shared Data Storage DuckDB runtime is required') from exc
    con=duckdb.connect(database=':memory:')
    try:
        # read_parquet is supplied explicit, hash-verified paths, not free SQL from user.
        con.execute('CREATE TEMP VIEW source AS SELECT * FROM read_parquet([' + ','.join("'"+str(path).replace("'","''")+"'" for path in paths) + '], union_by_name=true)')
        required={'race_date','race_key','horse_no','horse_id','sire_name','track_type','distance',
                  'venue_code','course_code','track_condition_code','finish','abnormal_code'}
        available={row[0] for row in con.execute('DESCRIBE source').fetchall()}
        require(required<=available,f'Analysis fact missing columns: {sorted(required-available)}')
        # Historical profile as-of is not independently verified in Analysis v1.4.
        # Do not infer historic family pedigree validity from a later profile.
        cutoff_rows=con.execute('SELECT count(*), count(distinct (race_key,horse_no)) FROM source WHERE race_date < ?', [cutoff]).fetchone()
        require(cutoff_rows[0]==cutoff_rows[1],'duplicate result race+horse number')
        # Source completeness of provided year partitions; as-of filters still apply.
        full_count=con.execute('SELECT count(*) FROM source').fetchone()[0]
        require(full_count==sum(p['rows'] for p in mf['fact_table']['partitions'] if p['year']<=date.fromisoformat(cutoff).year),'manifest total row mismatch')
        unknown=con.execute('''SELECT count(*) FROM source WHERE race_date<? AND track_type IN ('1','2')
               AND (track_condition_code IS NULL OR track_condition_code NOT IN ('''+','.join('?' for _ in GOING)+'))',[cutoff,*GOING]).fetchone()[0]
        require(unknown==0,'unknown or absent track condition code in historical source')
        invalid=con.execute('''SELECT count(*) FROM source WHERE race_date<? AND track_type IN ('1','2')
          AND (abnormal_code IS NULL OR abnormal_code NOT IN ('0','1','2','3','4','5','6')
            OR (abnormal_code='0' AND (try_cast(finish AS INT) IS NULL OR try_cast(finish AS INT) NOT BETWEEN 1 AND 18)))''',[cutoff]).fetchone()[0]
        require(invalid==0,'unrecognized result code/normal finish')
        # Select only *normal finishers*. Nonfinishers are excluded from both good and wet.
        # The denominator policy is explicit and must be reviewed before production.
        con.execute('''CREATE TEMP TABLE eligible AS SELECT sire_name,venue_code,course_code,
            try_cast(distance AS INT) AS distance_m,
            CASE WHEN try_cast(distance AS INT)<1400 THEN 'SHORT'
                 WHEN try_cast(distance AS INT)<1800 THEN 'MILE'
                 WHEN try_cast(distance AS INT)<2400 THEN 'MIDDLE' ELSE 'LONG' END AS band,
            CASE WHEN track_condition_code IN ('10','11','12') THEN '良'
                 ELSE '道悪' END AS bucket,
            try_cast(finish AS INT) AS finish
            FROM source
            WHERE race_date<? AND track_type=? AND abnormal_code='0' AND
                  try_cast(finish AS INT) BETWEEN 1 AND 18 AND sire_name IS NOT NULL
                  AND length(trim(sire_name))>0 AND distance IS NOT NULL''',
            [cutoff,race['surface_code']])
        all_h=[];total_obs=0
        for h in common['horses']:
            sire=h['pedigree']['sire_name'];v=race['venue_code'];m=race['distance_m'];b=band(m);cc=race.get('course_code')
            scopes=[]
            for scope in SCOPE_LABELS:
                where='sire_name=?'; params=[sire]
                if scope in ('VENUE_COURSE_DISTANCE','VENUE_DISTANCE','VENUE_BAND'):
                    where+=' AND venue_code=?';params.append(v)
                if scope=='VENUE_COURSE_DISTANCE':
                    if cc is None:scopes.append({'scope_key':scope,'scope_status':'CONTEXT_UNAVAILABLE','observation':None});continue
                    where+=' AND course_code=? AND distance_m=?';params.extend((cc,m))
                elif scope in ('VENUE_DISTANCE','ALL_VENUES_DISTANCE'):
                    where+=' AND distance_m=?';params.append(m)
                else:where+=' AND band=?';params.append(b)
                r=con.execute('''SELECT bucket,count(*)::INT,sum((finish=1)::INT)::INT,
                      sum((finish<=3)::INT)::INT FROM eligible WHERE '''+where+' GROUP BY bucket', params).fetchall()
                d={bucket:(n,w,t) for bucket,n,w,t in r}
                comp=observation(d.get('良',(0,0,0)),d.get('道悪',(0,0,0)))
                if comp['comparison_status']=='OBSERVED':total_obs+=1
                scopes.append({'scope_key':scope,'scope_status':'RESEARCH_OBSERVED','observation':comp})
            all_h.append({'horse_id':h['horse_id'],'horse_no':h['horse_no'],'sire_name':sire,
                          'scopes':scopes,'findings':[{'kind':'GOOD_VS_NON_GOOD',
                            'scope_key':s['scope_key'],'delta_top3_pp':s['observation']['difference_top3_pp'],
                            'sample_status':s['observation']['sample_status'],
                            'interpretation_status':'OBSERVATION_ONLY',
                            'prediction_eligible':False,'display_eligible':False}
                            for s in scopes if s['observation'] and s['observation']['comparison_status']=='OBSERVED']})
        return {'contract_version':VERSION,'release_status':'RESEARCH_ONLY','race':race,
                'as_of_exclusive':cutoff,'historical_profile_asof':'AS_OF_UNVERIFIED',
                'denominator':'NORMAL_FINISHERS_ONLY',
                'scope_policy':'SURFACE_FIXED_GOOD_VS_SLIGHTLY_HEAVY_HEAVY_BAD',
                'source':{'generation_id':mf['generation_id'],
                          'manifest_sha256':sha(manifest_path),'verified_partitions':checked,
                          'source_total_rows':full_count,'eligible_rows':con.execute('SELECT count(*) FROM eligible').fetchone()[0],
                          'target_day_results_excluded':True},
                'policy':{'prediction_safe':False,'production_authorized':False,'display_authorized':False,
                          'suitability_claim':False},
                'total_scope_comparisons':total_obs,'horses':all_h}
    finally:con.close()


def cli():
    a=argparse.ArgumentParser();a.add_argument('--common',required=True)
    a.add_argument('--manifest',required=True);a.add_argument('--objects-root',required=True)
    a.add_argument('--output',required=True);a.add_argument('--receipt',required=True)
    args=a.parse_args()
    payload=build(json.loads(Path(args.common).read_text('utf-8')),args.manifest,args.objects_root)
    Path(args.output).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    receipt={k:payload[k] for k in ('contract_version','release_status','race','source','total_scope_comparisons','historical_profile_asof','denominator')}
    Path(args.receipt).write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'RESEARCH_ONLY','scope_comparisons':payload['total_scope_comparisons']},ensure_ascii=False))

if __name__=='__main__':cli()
