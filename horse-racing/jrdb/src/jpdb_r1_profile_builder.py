#!/usr/bin/env python3
"""R1 research-only target-race jockey profile; reuse accepted P1/P2 Readers.

Historical rider = SED actual. Target rider = pinned target PACI KYI scheduled
role in the stored version, not an attested pre-race capture. Never publish
licensed profile rows to GitHub. No score, direction label, market or result
of target race. This candidate does not mutate RaceNote or CURRENT.
"""
from __future__ import annotations

import argparse
import json
import re
import zipfile
from datetime import date
from pathlib import Path

from jpdb_history_reader import POLICY, SOURCE_GENERATION, JPDBHistoryReaderError, sha256, validate_jockey
from jpdb_performance_reader_v11 import _metrics, _windows, NORMAL, POPULATION, MAX_CODES
from jpdb_p2_condition_reader import COUNTS
from jpdb_p2_course_master_reader import JPDBCourseMasterReader2026, COURSE_FILES
from jrdb_raw import BODY_LENGTHS, Parser, read_fixed_records, ymd

VERSION = 'jpdb-r1-jockey-profile-v0.1-candidate'
NEWCOMER = 'A1'  # JRDB code__jrdb, competition condition, not KYI class index
SURFACES = {'1': 'turf', '2': 'dirt'}
CLASS_CODES = frozenset({'04','05','08','09','10','15','16','A1','A2','A3','OP'})
PHYSICAL = {
    'COURSE_KEY': 'course_key', 'GEOMETRY_KEY': 'geometry_key',
    'TURN_DIRECTION': 'turn_direction', 'FINAL_SLOPE': 'final_straight_slope_flag',
    'COURSE_SIZE': 'course_size_class', 'FINAL_STRAIGHT_M': 'final_straight_m',
}
# All expressions are owned by the module; no caller-supplied SQL.
SCOPED = {
    'VENUE_SURFACE': ('venue_code', 'surface_code'),
    'CLASS_ONLY': ('race_class_code',),
    'CLASS_SURFACE': ('race_class_code', 'surface_code'),
    'NEWCOMER_ALL_FLAT': ('race_class_code',),
    'NEWCOMER_SURFACE': ('race_class_code', 'surface_code'),
    'NEWCOMER_VENUE_SURFACE': ('race_class_code', 'venue_code', 'surface_code'),
    'NEWCOMER_SURFACE_DISTANCE_EXACT': ('race_class_code', 'surface_code', 'distance_m'),
}
SCOPED_SELECT = f'''COUNT(*), COUNT(*) FILTER (WHERE {NORMAL}),
    COUNT(*) FILTER (WHERE abnormal_code='1'), COUNT(*) FILTER (WHERE abnormal_code='2'),
    COUNT(*) FILTER (WHERE abnormal_code='3'), COUNT(*) FILTER (WHERE abnormal_code='5'),
    COUNT(*) FILTER (WHERE abnormal_code IS NULL OR abnormal_code NOT IN ('0','','1','2','3','5')),
    COUNT(*) FILTER (WHERE abnormal_code IN ('0','') AND
        (finish IS NULL OR field_size IS NULL OR field_size<1 OR finish NOT BETWEEN 1 AND field_size)),
    COUNT(*) FILTER (WHERE {NORMAL} AND finish=1),
    COUNT(*) FILTER (WHERE {NORMAL} AND finish<=2),
    COUNT(*) FILTER (WHERE {NORMAL} AND finish<=3), MIN(race_date), MAX(race_date)'''


def fail(message):
    raise JPDBHistoryReaderError(message)


def _day(value):
    d = date.fromisoformat(value)
    if d.isoformat() != value or d.year != 2026:
        fail('R1 v0.1 target must be an ISO date in the fixed 2026 PACI scope')
    return d


def _records(archive, suffix, kind):
    member = kind + suffix + '.txt'
    if archive.namelist().count(member) != 1:
        fail('PACI missing or duplicate required member')
    raw = archive.read(member)
    length = BODY_LENGTHS[kind] + 2
    if not raw or len(raw) % length or any(raw[i+length-2:i+length] != b'\r\n'
                                           for i in range(0, len(raw), length)):
        fail('PACI malformed fixed-length member')
    return read_fixed_records(archive, member, kind)


def read_target_paci(path: Path, *, target_date: str, expected_sha256: str):
    """Only BAC race conditions and KYI entry identities leave this function."""
    day = _day(target_date)
    suffix = day.strftime('%y%m%d')
    if path.name != f'PACI{suffix}.zip' or sha256(path) != expected_sha256:
        fail('target PACI name/date/SHA mismatch')
    parser = Parser()
    races, horses = {}, {}
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            fail('target PACI CRC mismatch')
        for row in _records(archive, suffix, 'BAC'):
            b = parser.bac(row)
            key = b['race_key_raw']
            if (ymd(b['date_raw']) != target_date or not re.fullmatch(r'[0-9]{5}[0-9a-fA-F][0-9]{2}', key)
                    or key[2:4] != suffix[:2] or key[:2] not in {f'{i:02d}' for i in range(1,11)}
                    or key in races or not isinstance(b['field_size'], int) or b['field_size'] <= 0):
                fail('invalid or duplicate target BAC identity')
            races[key] = {k:b[k] for k in ('race_key_raw','surface_code','distance_raw','turn_code',
                'layout_code','course_code','race_class_code','grade_code','field_size')}
            races[key]['venue_code'] = key[:2]
            horses[key] = {}
        for row in _records(archive, suffix, 'KYI'):
            k = parser.kyi(row)
            key, no, hid = k['race_key_raw'], k['horse_no'], k['blood_registration_no']
            if (key not in races or not isinstance(no,int) or not 1 <= no <= 99 or no in horses[key]
                    or not re.fullmatch(r'[0-9]{8}',hid or '') or hid=='00000000'):
                fail('invalid or duplicate target KYI identity')
            # All registered rows retained, including a flagged cancellation.
            # No current odds, indexes, forecast, or result fields are projected.
            horses[key][no] = {'horse_no':no, 'horse_id':hid,
                              'scheduled_jockey_code':k['jockey_code'],
                              'entry_cancel_flag_raw':k['cancel_flag']}
    for key, r in races.items():
        roster = horses[key]
        if len(roster) != r['field_size'] or len({h['horse_id'] for h in roster.values()}) != len(roster):
            fail('BAC/KYI target roster mismatch')
    return races, horses


def audit_history_class(reader, *, bac_root: Path, manifest: Path, paci_root: Path, paci_manifest: Path):
    """Verify SED competition condition against pinned BAC before using A1."""
    if sha256(manifest)!=reader.manifest_sha256 or sha256(paci_manifest)!=reader.paci_manifest_sha256:
        fail('source manifest drift before class audit')
    historical = json.loads(manifest.read_text())['artifacts']
    paths=[]
    for year in (2023,2024,2025):
        x=next(x for x in historical if x['artifact_id']==f'bac_{year}')
        p=bac_root/x['artifact_id']/x['expected_name']
        if p.stat().st_size!=x['expected_size'] or sha256(p)!=x['sha256']:
            fail('historical BAC class source drift')
        paths.append(str(p))
    current=[]
    parser=Parser()
    for x in json.loads(paci_manifest.read_text())['selected']:
        p=paci_root/x['name']
        if p.stat().st_size!=x['size'] or sha256(p)!=x['zip_sha256']:
            fail('PACI BAC class source drift')
        with zipfile.ZipFile(p) as arc:
            for row in _records(arc,p.name[4:10],'BAC'):
                b=parser.bac(row)
                if ymd(b['date_raw'])!=x['race_date']:
                    fail('PACI BAC class date mismatch')
                current.append((b['race_key_raw'],x['race_date'],b['race_class_code']))
    db=reader.db
    db.execute('CREATE TEMP TABLE r1_bac_class AS SELECT race_key_raw,race_date,race_class_code FROM read_parquet(?)',[paths])
    db.executemany('INSERT INTO r1_bac_class VALUES (?,?,?)',current)
    counts=db.execute('''SELECT COUNT(*),COUNT(DISTINCT race_key_raw) FROM r1_bac_class''').fetchone()
    if counts!=(13431,13431):
        fail('BAC class fixed cohort identity mismatch')
    bad=db.execute('''SELECT COUNT(*) FROM jpdb_course_facts s LEFT JOIN r1_bac_class b USING (race_key_raw)
        WHERE s.surface_code IN ('1','2') AND (b.race_key_raw IS NULL OR s.race_date IS DISTINCT FROM b.race_date
            OR s.race_class_code IS DISTINCT FROM b.race_class_code OR s.race_class_code IS NULL
            OR TRIM(s.race_class_code)='')''').fetchone()[0]
    if bad:
        fail('BAC/SED historical race-condition mismatch')
    codes={x[0] for x in db.execute("SELECT DISTINCT race_class_code FROM jpdb_course_facts WHERE surface_code IN ('1','2')").fetchall()}
    if not codes <= CLASS_CODES:
        fail('unrecognized flat competition condition code')
    groups=db.execute("""SELECT SUBSTR(race_date,1,4),COUNT(DISTINCT race_key_raw),COUNT(*)
        FROM jpdb_course_facts WHERE surface_code IN ('1','2') AND race_class_code='A1' GROUP BY 1 ORDER BY 1""").fetchall()
    return {'status':'PASS','flat_rows':reader.verified_flat_rows,'class_mismatches':bad,
            'newcomer_by_year':{y:{'races':n,'entries':m} for y,n,m in groups}}


def resolve_course(reader, r, target_date):
    """Use target BAC plus the already hash-verified P2 mapping/master tables.

    This query never reads target SED, outcome or actual rider to resolve course.
    """
    db=reader.db
    rows=db.execute('''SELECT m.course_key,g.geometry_key,c.turn_direction,c.final_straight_slope_flag,
        c.course_size_class,c.final_straight_m,c.physical_version_id
        FROM jpdb_course_mapping m JOIN jpdb_course_master c USING(course_key)
        JOIN jpdb_course_geometry g ON m.venue_code=g.venue_code AND m.surface_code=g.surface_code
          AND split_part(c.course_key,':',5)=g.layout_variant
          AND (m.course_code=g.jrdb_course_code OR (m.surface_code='2' AND g.jrdb_course_code IS NULL))
        WHERE m.venue_code=? AND m.surface_code=? AND m.distance_m=? AND m.turn_code=? AND m.layout_code=?
          AND m.course_code IS NOT DISTINCT FROM ? AND m.mapping_status='CONFIRMED'
          AND c.physical_data_status='PARTIAL' AND c.physical_version_id IS NOT NULL
          AND c.physical_version_id=g.physical_version_id
          AND c.physical_valid_from<=? AND g.physical_valid_from<=?
          AND (c.physical_valid_to_exclusive IS NULL OR ?<c.physical_valid_to_exclusive)
          AND (g.physical_valid_to_exclusive IS NULL OR ?<g.physical_valid_to_exclusive)''',
          [r['venue_code'],r['surface_code'],int(r['distance_raw']),r['turn_code'],r['layout_code'],
           r['course_code'].strip() or None,*([target_date]*4)]).fetchall()
    if len(rows)!=1 or not rows[0][0] or not rows[0][1]:
        fail('target BAC physical course mapping not uniquely validated')
    return dict(zip([*PHYSICAL.values(),'physical_version_id'],rows[0]))


def empty_metrics(target):
    return _metrics(dict.fromkeys(COUNTS,0),None,None,target)


def select_cell(cells, condition, target):
    matches=[c for c in cells if c['dimension_value']==condition]
    if len(matches)>1:
        fail('duplicate P2 condition cell')
    return matches[0]['metrics'] if matches else empty_metrics(target)


def scoped_metrics(db, dimension, condition, codes, lower, target):
    cols=SCOPED[dimension]
    if tuple(condition)!=cols or not codes or len(codes)>MAX_CODES:
        fail('invalid scoped aggregate request')
    filters=' AND '.join(c+'=?' for c in cols)
    placeholders=','.join('?' for _ in codes)
    rows=db.execute(f'''SELECT jockey_code,{SCOPED_SELECT} FROM jpdb_course_facts
        WHERE race_date>=? AND race_date<? AND surface_code IN ('1','2') AND {filters}
          AND jockey_code IN ({placeholders}) GROUP BY jockey_code''',
        [lower,target,*condition.values(),*codes]).fetchall()
    result={c:empty_metrics(target) for c in codes}
    for code,*values in rows:
        result[code]=_metrics(dict(zip(COUNTS,values[:-2])),values[-2],values[-1],target)
    return result


def make_evidence(race_key, no, window, dimension, condition, metrics, group, scope):
    # Unresolved outcome populations remain visible as REVIEW_REQUIRED, with
    # candidate start rates withheld by the unchanged P1 metric contract.
    # Never translate missing/no history into negative evidence.
    return {'evidence_id':f'{race_key}:{no:02d}:{window}:{dimension}',
            'dimension':dimension,'condition':condition,'scope':scope,
            'status':'TARGET_CONDITION_UNAVAILABLE' if metrics is None else metrics['sample_support_status'],
            'source_status':'TARGET_CONDITION_UNAVAILABLE' if metrics is None else ('OBSERVED' if metrics['entries'] else 'NO_OBSERVED_HISTORY'),
            'sample_n':None if metrics is None else metrics['actual_starts_candidate'],
            'metrics':metrics,'direction':'UNCLASSIFIED','redundancy_group_id':group,
            'interpretation_policy':'DESCRIPTIVE_ONLY'}


def build(reader, *, target_date, paci_path, paci_manifest, expected_paci_sha256, race_keys, class_audit):
    """All registered horses of requested flat races. R1 not prediction-safe."""
    day=_day(target_date)
    if class_audit.get('status')!='PASS' or class_audit.get('class_mismatches')!=0 or class_audit.get('flat_rows')!=reader.verified_flat_rows:
        fail('historical race-class authority audit missing')
    if sha256(paci_manifest)!=reader.paci_manifest_sha256:
        fail('target PACI manifest differs from reader snapshot')
    match=[x for x in json.loads(paci_manifest.read_text())['selected'] if x['race_date']==target_date]
    if (len(match)!=1 or match[0]['name']!=paci_path.name or match[0]['zip_sha256']!=expected_paci_sha256
            or match[0]['size']!=paci_path.stat().st_size):
        fail('target PACI not bound to verified reader snapshot')
    races, rosters=read_target_paci(paci_path,target_date=target_date,expected_sha256=expected_paci_sha256)
    if not race_keys or len(race_keys)!=len(set(race_keys)) or any(k not in races for k in race_keys):
        fail('empty, duplicate, or unknown requested race key')
    output=[]
    for key in sorted(race_keys):
        r=races[key]
        surface=r['surface_code']; cls=r['race_class_code']
        if surface not in SURFACES or cls not in CLASS_CODES or not r['distance_raw'].isdigit() or int(r['distance_raw'])<=0:
            fail('flat race with known competition class and distance required')
        dist=int(r['distance_raw']); venue=r['venue_code']; course=resolve_course(reader,r,target_date)
        horses=sorted(rosters[key].values(),key=lambda h:h['horse_no'])
        # Invalid scheduled jockey IDs are not guessed or joined by name.
        codes=sorted({validate_jockey(h['scheduled_jockey_code']) for h in horses})
        core=reader.rider_histories(target_date=target_date,jockey_codes=codes)['jockey_histories']
        raw=reader.rider_conditions(target_date=target_date,jockey_codes=codes)['jockey_conditions']
        phy=reader.rider_course_conditions(target_date=target_date,jockey_codes=codes)['jockey_conditions']
        scoped={'VENUE_SURFACE':{'venue_code':venue,'surface_code':surface}}
        if cls==NEWCOMER:
            scoped.update({'NEWCOMER_ALL_FLAT':{'race_class_code':NEWCOMER},
                'NEWCOMER_SURFACE':{'race_class_code':NEWCOMER,'surface_code':surface},
                'NEWCOMER_VENUE_SURFACE':{'race_class_code':NEWCOMER,'venue_code':venue,'surface_code':surface},
                'NEWCOMER_SURFACE_DISTANCE_EXACT':{'race_class_code':NEWCOMER,'surface_code':surface,'distance_m':dist}})
        else:
            scoped.update({'CLASS_ONLY':{'race_class_code':cls},
                           'CLASS_SURFACE':{'race_class_code':cls,'surface_code':surface}})
        cache={(w,dim):scoped_metrics(reader.db,dim,condition,codes,lower,target_date)
               for w,lower in _windows(day).items() for dim,condition in scoped.items()}
        for h in horses:
            code=h['scheduled_jockey_code']; no=h['horse_no']; h['windows']={}
            for w,lower in _windows(day).items():
                c=core[code]['windows'][w]; a=raw[code][w]; p=phy[code][w]
                entries=[]
                def add(dim,condition,metrics,group,scope):
                    entries.append(make_evidence(key,no,w,dim,condition,metrics,group,scope))
                add('ALL_FLAT',{},c['all_flat'],'JOCKEY_BASE','ALL_FLAT')
                add('SURFACE',{'surface_code':surface},c['by_surface'][SURFACES[surface]],'JOCKEY_CONDITION','TARGET_SURFACE')
                for dim,condition,scope,group in [
                    ('VENUE',{'venue_code':venue},'ALL_FLAT_AT_VENUE','JOCKEY_CONDITION'),
                    ('SURFACE_DISTANCE_EXACT',{'surface_code':surface,'distance_m':dist},'TARGET_SURFACE_EXACT_DISTANCE','JOCKEY_CONDITION'),
                    ('CLASS_GRADE_RAW',{'race_class_code':cls,'grade_code':r['grade_code']},'ALL_FLAT_CLASS_GRADE','JOCKEY_CLASS')]:
                    metrics=select_cell(a[dim],condition,target_date) if all(v not in ('',None) for v in condition.values()) else None
                    add(dim,condition,metrics,group,scope)
                add('GOING_RAW',{'surface_code':surface,'track_condition_code':None},None,'JOCKEY_CONDITION','TARGET_GOING_UNKNOWN')
                for dim,col in PHYSICAL.items():
                    condition={col:course[col]}
                    metrics=select_cell(p[dim],condition,target_date) if course[col] not in ('',None) else None
                    add(dim,condition,metrics,'JOCKEY_CONDITION','P2_PHYSICAL_ALL_FLAT')
                for dim,condition in scoped.items():
                    add(dim,condition,cache[w,dim][code],'JOCKEY_CLASS' if dim.startswith(('NEWCOMER','CLASS')) else 'JOCKEY_CONDITION',dim)
                h['windows'][w]={'period_from_inclusive':lower,'period_to_exclusive':target_date,'evidence':entries}
        output.append({'race_key_raw':key,'venue_code':venue,'surface_code':surface,'distance_m':dist,
                       'race_class_code':cls,'grade_code':r['grade_code'],'is_newcomer_race':cls==NEWCOMER,
                       'target_going_status':'UNKNOWN','physical_data_status':'PARTIAL', 'course':course,
                       'entry_count':r['field_size'],'horses':horses})
    return {'schema_version':VERSION,'target_date':target_date,'prediction_safe':False,
            'source':{'historical_generation':SOURCE_GENERATION,'historical_manifest_sha256':reader.manifest_sha256,
                      'daily_sed_manifest_sha256':reader.daily_manifest_sha256,
                      'daily_paci_bac_manifest_sha256':reader.paci_manifest_sha256,
                      'target_paci_sha256':expected_paci_sha256,'course_seed_sha256':{k:v[2] for k,v in COURSE_FILES.items()},
                      'asof_policy':POLICY,'strict_asof_certified':False,
                      'target_version_status':'OBSERVED_PACI_VERSION_NOT_TIME_ATTESTED',
                      'historical_jockey_role':'SED_ACTUAL','target_jockey_role':'PACI_KYI_SCHEDULED_IN_STORED_VERSION',
                      'population_filter_id':POPULATION,'historical_coverage_to_inclusive':reader.daily_coverage_to.isoformat(),
                      'class_authority':'BAC_SED_CLASS_EQUAL_FIXED_COHORT',
                      'interpretation_policy':'NO_ADDITIVE_VOTES_OR_CAUSAL_SKILL_LABELS'},
            'races':output}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for label in ('input-root','manifest','daily-root','daily-manifest','bac-root','paci-root','paci-manifest','course-root','output'):
        p.add_argument('--'+label,required=True,type=Path)
    for label in ('expected-manifest-sha256','expected-daily-manifest-sha256','expected-paci-manifest-sha256','target-date'):
        p.add_argument('--'+label,required=True)
    p.add_argument('--race-key',action='append',required=True)
    a=p.parse_args()
    if a.output.exists():
        raise FileExistsError('refusing to overwrite research output')
    day=_day(a.target_date)
    entries=[x for x in json.loads(a.paci_manifest.read_text())['selected'] if x['race_date']==a.target_date]
    if len(entries)!=1:
        fail('target date not uniquely present in pinned PACI manifest')
    entry=entries[0]
    with JPDBCourseMasterReader2026(input_root=a.input_root,manifest=a.manifest,daily_root=a.daily_root,
            daily_manifest=a.daily_manifest,bac_root=a.bac_root,paci_root=a.paci_root,paci_manifest=a.paci_manifest,
            course_root=a.course_root,expected_manifest_sha256=a.expected_manifest_sha256,
            expected_daily_manifest_sha256=a.expected_daily_manifest_sha256,
            expected_paci_manifest_sha256=a.expected_paci_manifest_sha256) as reader:
        audit=audit_history_class(reader,bac_root=a.bac_root,manifest=a.manifest,paci_root=a.paci_root,paci_manifest=a.paci_manifest)
        result=build(reader,target_date=day.isoformat(),paci_path=a.paci_root/entry['name'],
                     paci_manifest=a.paci_manifest,expected_paci_sha256=entry['zip_sha256'],race_keys=a.race_key,class_audit=audit)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'RESEARCH_PROFILE_GENERATED','races':len(result['races']),
                      'entries':sum(r['entry_count'] for r in result['races']), 'output_sha256':sha256(a.output)}))

if __name__=='__main__':
    main()
