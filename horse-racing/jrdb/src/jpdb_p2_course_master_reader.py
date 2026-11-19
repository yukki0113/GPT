#!/usr/bin/env python3
"""JPDB P2 Course Master extension: BAC-grounded, physical-epoch-gated stats.

Read-only and research-only. The accepted Phase3 seed verifies a conservative
2023+ physical epoch, NOT a complete historical course_version registry.
JRDB SED's observed course_code is NOT authoritative for course identity: use
BAC by race_key_raw, Phase3 confirmed mapping, and Master+Geometry epochs.
"""
from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import zipfile
from datetime import date
from pathlib import Path

from jpdb_history_reader import JPDBHistoryReaderError, POLICY, sha256
from jpdb_performance_reader_v11 import _checked_codes, _metrics, _windows, NORMAL
from jpdb_p2_condition_reader import JPDBConditionReader2026, COUNTS, VERSION as CONDITION_VERSION, _quote
from jrdb_raw import Parser, BODY_LENGTHS, ymd

VERSION = 'jpdb-p2-course-physical-v0.1-candidate'
PACI_SCHEMA = 'jpdb-p2-paci-bac-pinned-v1'
COURSE_FILES = {
    'master':('course_master_seed_v0_1.jsonl',177,
              '4bf5039a7b9f42ef991ff3edf0cd2f11e461687c3d137a9b9a2418d191c5a97a'),
    'mapping':('course_jrdb_mapping_seed_v0_1.jsonl',433,
              '76563b141a5f5a4ff4981abee8f20881d8417f71772d7bb9718e719c2aec335f'),
    'geometry':('course_geometry_configuration_v0_1.jsonl',57,
              'd7ea198ffee104e8bf51b5c90e9a77d7426903132898e06f1acaef42bb2e418f'),
}
BAC_COUNTS = {2023:3456,2024:3454,2025:3455}
DIMENSIONS = {
    'COURSE_KEY':('course_key',),
    'GEOMETRY_KEY':('geometry_key',),
    'TURN_DIRECTION':('turn_direction',),
    'FINAL_SLOPE':('final_straight_slope_flag',),
    'COURSE_SIZE':('course_size_class',),
    'FINAL_STRAIGHT_M':('final_straight_m',),
}


def _load_course_seed(course_root:Path)->dict[str,list[dict]]:
    out={}
    for kind,(name,n,digest) in COURSE_FILES.items():
        path=Path(course_root)/name
        if sha256(path)!=digest:
            raise JPDBHistoryReaderError(f'unexpected Phase3 {kind} seed SHA')
        rows=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        if len(rows)!=n:
            raise JPDBHistoryReaderError(f'Phase3 {kind} cardinality changed')
        out[kind]=rows
    return out


def _validated_paci(paci_root:Path, manifest_path:Path,
                     daily_2026_dates:list[str], expected_sha:str|None):
    sha=sha256(Path(manifest_path))
    if expected_sha is not None and sha!=expected_sha:
        raise JPDBHistoryReaderError('P2 PACI manifest SHA mismatch')
    spec=json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    entries=spec.get('selected')
    if (spec.get('schema_version')!=PACI_SCHEMA or not isinstance(entries,list)
        or not entries or [x.get('race_date') for x in entries]!=daily_2026_dates
        or spec.get('expected_race_dates')!=daily_2026_dates
        or spec.get('coverage_to_inclusive')!=daily_2026_dates[-1]):
        raise JPDBHistoryReaderError('P2 PACI dates diverge from pinned SED dates')
    if sorted(x.name for x in Path(paci_root).glob('PACI26????.zip')) != sorted(x['name'] for x in entries):
        raise JPDBHistoryReaderError('P2 PACI local inventory diverges')
    parser=Parser()
    seen=set()
    total=0
    for x in entries:
        name=x['name']
        if not name.startswith('PACI26') or not name.endswith('.zip') or len(name)!=14:
            raise JPDBHistoryReaderError('P2 PACI unexpected archive name')
        p=Path(paci_root)/name
        if (p.stat().st_size!=x['size'] or sha256(p)!=x['zip_sha256']):
            raise JPDBHistoryReaderError('P2 PACI ZIP SHA/size changed')
        with zipfile.ZipFile(p) as archive:
            if archive.testzip() is not None:
                raise JPDBHistoryReaderError('P2 PACI bad CRC')
            member=name.replace('PACI','BAC').replace('.zip','.txt')
            raw=archive.read(member)
            if hashlib.sha256(raw).hexdigest()!=x['bac_member_sha256']:
                raise JPDBHistoryReaderError('P2 BAC member changed')
            size=BODY_LENGTHS['BAC']+2
            if len(raw)%size!=0 or len(raw)//size != x['bac_rows']:
                raise JPDBHistoryReaderError('P2 BAC record size/count changed')
            for i in range(0,len(raw),size):
                record=raw[i:i+size]
                if not record.endswith(b'\r\n'):
                    raise JPDBHistoryReaderError('P2 BAC bad record terminator')
                parsed=parser.bac(record[:-2])
                if ymd(parsed['date_raw'])!=x['race_date']:
                    raise JPDBHistoryReaderError('P2 BAC date differs from archive')
                key=parsed['race_key_raw']
                if key in seen or not key:
                    raise JPDBHistoryReaderError('P2 BAC duplicate/empty race key')
                seen.add(key)
                total+=1
                yield (key,x['race_date'],key[:2],parsed['surface_code'],
                       parsed['distance_raw'],parsed['turn_code'],
                       parsed['layout_code'],parsed['course_code'])
    if total!=sum(x['bac_rows'] for x in entries):
        raise JPDBHistoryReaderError('P2 BAC row total mismatch')


class JPDBCourseMasterReader2026(JPDBConditionReader2026):
    """Read-only physical features with fail-closed BAC/Phase3 source joins."""

    def __init__(self, *, bac_root:Path, paci_root:Path,
                 paci_manifest:Path, course_root:Path,
                 expected_paci_manifest_sha256:str|None=None, **p12_args):
        super().__init__(**p12_args)
        try:
            self.paci_manifest_sha256=sha256(Path(paci_manifest))
            src=json.loads(Path(p12_args['manifest']).read_text(encoding='utf-8'))
            hist=[]
            for year, expected_n in BAC_COUNTS.items():
                entry=next(x for x in src['artifacts'] if x['artifact_id']==f'bac_{year}')
                p=Path(bac_root)/f'bac_{year}'/entry['expected_name']
                if p.stat().st_size != entry['expected_size'] or sha256(p)!=entry['sha256']:
                    raise JPDBHistoryReaderError(f'P2 accepted historical BAC {year} SHA changed')
                hist.append(str(p.resolve()))
            hist_sql=','.join(_quote(s) for s in hist)
            self.db.execute('''CREATE VIEW jpdb_bac_historical AS
                SELECT race_key_raw,race_date,venue_code,surface_code,distance_raw,
                  turn_code,layout_code,course_code
                FROM read_parquet(['''+hist_sql+'''],union_by_name=true)''')
            count=self.db.execute("SELECT COUNT(*) FROM jpdb_bac_historical").fetchone()[0]
            if count != sum(BAC_COUNTS.values()):
                raise JPDBHistoryReaderError('P2 historical BAC count changed')
            self.db.execute('''CREATE TABLE jpdb_bac_2026 (
                race_key_raw VARCHAR,race_date VARCHAR,venue_code VARCHAR,
                surface_code VARCHAR,distance_raw VARCHAR,turn_code VARCHAR,
                layout_code VARCHAR,course_code VARCHAR)''')
            with tempfile.TemporaryDirectory(prefix='jpdb-p2-paci-') as td:
                path=Path(td)/'bac.csv'
                with path.open('w',encoding='utf-8',newline='') as fp:
                    writer=csv.writer(fp)
                    writer.writerow(('race_key_raw','race_date','venue_code','surface_code',
                        'distance_raw','turn_code','layout_code','course_code'))
                    dates=[x['race_date'] for x in self.daily_sources]
                    for row in _validated_paci(paci_root,paci_manifest,dates,
                                              expected_paci_manifest_sha256):
                        writer.writerow(['\\N' if x is None else x for x in row])
                self.db.execute('COPY jpdb_bac_2026 FROM '+_quote(str(path))+
                                " (HEADER TRUE, DELIMITER ',', NULL '\\N')")
            self.bac_2026_races=self.db.execute('SELECT COUNT(*) FROM jpdb_bac_2026').fetchone()[0]
            self.db.execute('''CREATE VIEW jpdb_bac_all AS
                SELECT * FROM jpdb_bac_historical
                UNION ALL BY NAME SELECT * FROM jpdb_bac_2026''')
            dup=self.db.execute('''SELECT COUNT(*) FROM (
                SELECT race_key_raw FROM jpdb_bac_all GROUP BY 1 HAVING COUNT(*)!=1)''').fetchone()[0]
            if dup:
                raise JPDBHistoryReaderError('P2 BAC race key fanout')
            bacs=self.db.execute('''SELECT COUNT(*) FROM jpdb_condition_facts s
                LEFT JOIN jpdb_bac_all b USING (race_key_raw)
                WHERE b.race_key_raw IS NULL OR b.race_date!=s.race_date
                  OR b.surface_code!=s.surface_code''').fetchone()[0]
            if bacs:
                raise JPDBHistoryReaderError(f'P2 BAC missing/mismatched SED rides: {bacs}')
            seeds=_load_course_seed(Path(course_root))
            self.db.execute('''CREATE TABLE jpdb_course_mapping (
                venue_code VARCHAR,surface_code VARCHAR,distance_m BIGINT,
                turn_code VARCHAR,layout_code VARCHAR,course_code VARCHAR,
                course_key VARCHAR,mapping_status VARCHAR)''')
            self.db.executemany('INSERT INTO jpdb_course_mapping VALUES (?,?,?,?,?,?,?,?)',[
                (x['venue_code'],x['surface_code'],x['distance_m'],x['turn_code'],
                 x['layout_code'],x.get('course_code'),x['course_key'],x['mapping_status'])
                for x in seeds['mapping']])
            self.db.execute('''CREATE TABLE jpdb_course_master (
                course_key VARCHAR,physical_data_status VARCHAR,
                physical_version_id VARCHAR,physical_valid_from VARCHAR,
                physical_valid_to_exclusive VARCHAR,final_straight_m DOUBLE,
                final_straight_slope_flag BOOLEAN,course_size_class VARCHAR,
                turn_direction VARCHAR)''')
            self.db.executemany('INSERT INTO jpdb_course_master VALUES (?,?,?,?,?,?,?,?,?)',[
                (x['course_key'],x['physical_data_status'],x.get('physical_version_id'),
                 x['physical_valid_from'],x.get('physical_valid_to_exclusive'),
                 x.get('final_straight_m'),x.get('final_straight_slope_flag'),
                 x.get('course_size_class'),x.get('turn_direction'))
                for x in seeds['master']])
            self.db.execute('''CREATE TABLE jpdb_course_geometry (
                venue_code VARCHAR,surface_code VARCHAR,layout_variant VARCHAR,
                jrdb_course_code VARCHAR,geometry_key VARCHAR,
                physical_version_id VARCHAR,physical_valid_from VARCHAR,
                physical_valid_to_exclusive VARCHAR)''')
            self.db.executemany('INSERT INTO jpdb_course_geometry VALUES (?,?,?,?,?,?,?,?)',[
                (x['venue_code'],x['surface_code'],x['layout_variant'],
                 x.get('jrdb_course_code'),x['geometry_key'],x['physical_version_id'],
                 x['physical_valid_from'],x.get('physical_valid_to_exclusive'))
                for x in seeds['geometry']])
            # BAC is authoritative here: never infer physical topology from
            # result SED's raw course code or silently fill physical NULLs.
            self.db.execute('''CREATE VIEW jpdb_course_facts AS
                SELECT f.*,m.course_key,m.mapping_status,c.physical_data_status,
                    c.physical_version_id,c.physical_valid_from,
                    c.physical_valid_to_exclusive,c.final_straight_m,
                    c.final_straight_slope_flag,c.course_size_class,c.turn_direction,
                    g.geometry_key,g.physical_version_id AS geo_version_id,
                    g.physical_valid_from AS geo_valid_from,
                    g.physical_valid_to_exclusive AS geo_valid_to
                FROM jpdb_condition_facts f JOIN jpdb_bac_all b USING(race_key_raw)
                LEFT JOIN jpdb_course_mapping m
                 ON b.venue_code=m.venue_code AND b.surface_code=m.surface_code
                  AND TRY_CAST(b.distance_raw AS BIGINT)=m.distance_m
                  AND b.turn_code=m.turn_code AND b.layout_code=m.layout_code
                  AND NULLIF(TRIM(b.course_code),'') IS NOT DISTINCT FROM m.course_code
                LEFT JOIN jpdb_course_master c ON m.course_key=c.course_key
                LEFT JOIN jpdb_course_geometry g
                 ON b.venue_code=g.venue_code AND b.surface_code=g.surface_code
                  AND split_part(c.course_key,':',5)=g.layout_variant
                  AND (b.course_code=g.jrdb_course_code OR
                       (b.surface_code='2' AND g.jrdb_course_code IS NULL))''')
            counts=self.db.execute('''SELECT COUNT(*),
                COUNT(*) FILTER (WHERE surface_code IN ('1','2')),
                COUNT(*) FILTER (WHERE surface_code IN ('1','2') AND (
                    mapping_status!='CONFIRMED' OR mapping_status IS NULL
                    OR course_key IS NULL OR geometry_key IS NULL
                    OR physical_version_id IS NULL OR geo_version_id IS NULL
                    OR physical_version_id IS DISTINCT FROM geo_version_id
                    OR physical_valid_from IS NULL OR geo_valid_from IS NULL
                    OR race_date<physical_valid_from OR race_date<geo_valid_from
                    OR (physical_valid_to_exclusive IS NOT NULL AND race_date>=physical_valid_to_exclusive)
                    OR (geo_valid_to IS NOT NULL AND race_date>=geo_valid_to))),
                COUNT(*) FILTER (WHERE surface_code IN ('1','2') AND
                    physical_data_status!='PARTIAL')
                FROM jpdb_course_facts''').fetchone()
            if counts!=(self.condition_source_rows,179436,0,0):
                raise JPDBHistoryReaderError(f'P2 BAC/CourseMaster join/temporal gate: {counts}')
            # Immutable, read-only in-memory snapshot avoids repeating the
            # same source joins for every rider/window/dimension query.
            self.db.execute('CREATE TEMP TABLE jpdb_course_fact_snapshot AS SELECT * FROM jpdb_course_facts')
            self.db.execute('DROP VIEW jpdb_course_facts')
            self.db.execute('ALTER TABLE jpdb_course_fact_snapshot RENAME TO jpdb_course_facts')
            self.verified_flat_rows=counts[1]
        except Exception:
            self.close()
            raise

    def rider_course_conditions(self, *, target_date:str, jockey_codes:list[str])->dict:
        day=__import__('jpdb_performance_reader_v12').validate_extended_target(
            target_date,fresh_through=self.daily_coverage_to)
        codes=_checked_codes(jockey_codes)
        windows=_windows(day)
        markers=','.join('?' for _ in codes)
        expr='''COUNT(*) AS entries,
          COUNT(*) FILTER (WHERE '''+NORMAL+''') AS normal_finishers,
          COUNT(*) FILTER (WHERE abnormal_code='1') AS cancellations,
          COUNT(*) FILTER (WHERE abnormal_code='2') AS exclusions,
          COUNT(*) FILTER (WHERE abnormal_code='3') AS dnf,
          COUNT(*) FILTER (WHERE abnormal_code='5') AS demotion_review,
          COUNT(*) FILTER (WHERE abnormal_code IS NULL OR abnormal_code NOT IN ('0','','1','2','3','5')) AS unknown_codes,
          COUNT(*) FILTER (WHERE abnormal_code IN ('0','') AND
             (finish IS NULL OR field_size IS NULL OR field_size<1 OR finish NOT BETWEEN 1 AND field_size)) AS invalid_normal_finish,
          COUNT(*) FILTER (WHERE '''+NORMAL+''' AND finish=1) AS wins,
          COUNT(*) FILTER (WHERE '''+NORMAL+''' AND finish<=2) AS top2,
          COUNT(*) FILTER (WHERE '''+NORMAL+''' AND finish<=3) AS top3,
          MIN(race_date) AS first_observed,MAX(race_date) AS last_observed'''
        result={code:{window:{} for window in windows} for code in codes}
        for window,lower in windows.items():
            for dim,columns in DIMENSIONS.items():
                col_sql=','.join(columns)
                sql=f'''SELECT jockey_code,{col_sql},{expr}
                      FROM jpdb_course_facts
                      WHERE race_date>=? AND race_date<? AND surface_code IN ('1','2')
                        AND jockey_code IN ({markers})
                      GROUP BY jockey_code,{col_sql}'''
                for row in self.db.execute(sql,[lower,day.isoformat(),*codes]).fetchall():
                    code=row[0]
                    vals=row[1:1+len(columns)]
                    metrics=_metrics(dict(zip(COUNTS,row[1+len(columns):1+len(columns)+len(COUNTS)])),
                                     row[-2],row[-1],day.isoformat())
                    missing=any(v is None or v=='' for v in vals)
                    if missing:
                        metrics['sample_support_status']='REVIEW_REQUIRED'
                    result[code][window].setdefault(dim,[]).append({
                        'dimension_set_id':dim,
                        'dimension_value':dict(zip(columns,vals)),
                        'metrics':metrics,'sample_n':metrics['actual_starts_candidate'],
                        'sample_support_status':metrics['sample_support_status'],
                        'physical_version_status':'PHYSICAL_2023PLUS_EPOCH_PARTIAL',
                        'source_status':'ATTRIBUTE_UNAVAILABLE' if missing else 'PHYSICAL_ATTRIBUTE_OBSERVED',
                        'descriptive_only':True,
                    })
        for code in codes:
            for window,lower in windows.items():
                n=self._flat_n(day,lower,code)
                for dim in DIMENSIONS:
                    cells=result[code][window].setdefault(dim,[])
                    cells.sort(key=lambda c:str(tuple(c['dimension_value'].values())))
                    if sum(c['metrics']['entries'] for c in cells)!=n:
                        raise JPDBHistoryReaderError(f'P2 physical {window}/{dim} partition mismatch')
                    for c in cells:
                        c['population_n']=n
                        c['coverage_ratio']=c['metrics']['entries']/n if n else None
                        c['history_days']=(date.fromisoformat(c['metrics']['last_observed'])-
                            date.fromisoformat(c['metrics']['first_observed'])).days if c['metrics']['first_observed'] else None
                        c['last_observed_date']=c['metrics']['last_observed']
                        c['unclassified_n']=c['metrics']['unresolved_count']
        return {
          'schema_version':VERSION,'target_date':day.isoformat(),
          'jockey_conditions':result,
          'source_rows_total':self.condition_source_rows,'flat_rows':self.verified_flat_rows,
          'historical_source_manifest_sha256':self.manifest_sha256,
          'daily_sed_manifest_sha256':self.daily_manifest_sha256,
          'daily_paci_bac_manifest_sha256':self.paci_manifest_sha256,
          'course_seed_sha256':{k:v[2] for k,v in COURSE_FILES.items()},
          'physical_epoch_verified_from':'2023-01-01',
          'historical_course_version_reconstruction_complete':False,
          'source_physical_data_status':'PARTIAL',
          'asof_policy':POLICY,'strict_asof_certified':False,
          'prediction_safe':False,
        }
