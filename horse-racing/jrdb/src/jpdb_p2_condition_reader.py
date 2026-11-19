#!/usr/bin/env python3
"""JPDB P2 read-only candidate: grouped historical rider conditions.

Source is pinned 2023–25 SED Parquet and private 2026 daily SED ZIP. The 2026
condition projection is decoded only by jrdb_raw.Parser.sed. Descriptive stats,
not skill, geometry certification, or pre-race predictions.
"""
from __future__ import annotations

import csv
import json
import tempfile
import zipfile
from datetime import date
from pathlib import Path

from jpdb_history_reader import JPDBHistoryReaderError, POLICY, SOURCE_GENERATION, sha256
from jpdb_performance_reader_v11 import _checked_codes, _metrics, _windows, NORMAL
from jpdb_performance_reader_v12 import JPDBPerformanceReader2026, validate_extended_target
from jrdb_raw import Parser, BODY_LENGTHS

VERSION = 'jpdb-conditions-v0.1-candidate'
DIMENSIONS = {
    'VENUE': ('venue_code',),
    'SURFACE_DISTANCE_EXACT': ('surface_code', 'distance_m'),
    'CLASS_GRADE_RAW': ('race_class_code', 'grade_code'),
    'GOING_RAW': ('surface_code', 'track_condition_code'),
    'COURSE_RAW_CODE': ('venue_code','surface_code','course_code','turn_code','layout_code'),
}
EXTRA = ('distance_m', 'track_condition_code', 'race_class_code', 'grade_code',
         'course_code', 'turn_code', 'layout_code')
COUNTS = ('entries','normal_finishers','cancellations','exclusions','dnf',
          'demotion_review','unknown_codes','invalid_normal_finish','wins',
          'top2','top3')


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _read_conditions_2026(daily_root: Path, receipts: list[dict]):
    """Trust nothing except the source already pinned/verified by the P1.2 parent."""
    parser = Parser()
    for spec in receipts:
        path = daily_root/spec['name']
        # Parent verified the byte hash, CRC, record and member hashes. This
        # second read rechecks size/SHA to avoid accepting an intervening edit.
        if path.stat().st_size != spec['size'] or sha256(path) != spec['zip_sha256']:
            raise JPDBHistoryReaderError('2026 ZIP drift before P2 projection')
        with zipfile.ZipFile(path) as archive:
            payload=archive.read(spec['name'].replace('.zip','.txt'))
        record_len=BODY_LENGTHS['SED']+2
        for offset in range(0,len(payload),record_len):
            parsed=parser.sed(payload[offset:offset+record_len-2])
            key=parsed['race_key_raw']
            venue=key[:2] if key else None
            if venue not in {f'{i:02d}' for i in range(1,11)}:
                raise JPDBHistoryReaderError('2026 non-JRA venue in P2 input')
            yield (key,parsed['horse_no'],*tuple(parsed[x] for x in EXTRA))


class JPDBConditionReader2026(JPDBPerformanceReader2026):
    """Separate P2 API; original P1.1/P1.2 responses remain unchanged."""

    def __init__(self, *, input_root: Path, manifest: Path,
                 daily_root: Path, daily_manifest: Path,
                 expected_manifest_sha256: str | None = None,
                 expected_daily_manifest_sha256: str | None = None):
        super().__init__(input_root=input_root,manifest=manifest,
                         daily_root=daily_root,daily_manifest=daily_manifest,
                         expected_manifest_sha256=expected_manifest_sha256,
                         expected_daily_manifest_sha256=expected_daily_manifest_sha256)
        try:
            self.db.execute('CREATE TABLE jpdb_cond_2026 ('
                'race_key_raw VARCHAR,horse_no INTEGER,distance_m INTEGER,'
                'track_condition_code VARCHAR,race_class_code VARCHAR,'
                'grade_code VARCHAR,course_code VARCHAR,turn_code VARCHAR,'
                'layout_code VARCHAR)')
            with tempfile.TemporaryDirectory(prefix='jpdb-p2-') as td:
                path=Path(td)/'conditions.csv'
                with path.open('w',encoding='utf-8',newline='') as fp:
                    writer=csv.writer(fp)
                    writer.writerow(('race_key_raw','horse_no',*EXTRA))
                    for row in _read_conditions_2026(Path(daily_root),self.daily_sources):
                        writer.writerow(['\\N' if x is None else x for x in row])
                self.db.execute('COPY jpdb_cond_2026 FROM '+_quote(str(path))+
                                " (HEADER TRUE, DELIMITER ',', NULL '\\N')")
            n=self.db.execute('SELECT COUNT(*) FROM jpdb_cond_2026').fetchone()[0]
            if n!=self.daily_rows:
                raise JPDBHistoryReaderError('P2 2026 condition count != P1.2 rows')
            checks=self.db.execute('''SELECT
                (SELECT COUNT(*) FROM jpdb_cond_2026 c LEFT JOIN sed_2026 s
                  USING (race_key_raw,horse_no) WHERE s.race_key_raw IS NULL),
                (SELECT COUNT(*) FROM sed_2026 s LEFT JOIN jpdb_cond_2026 c
                  USING (race_key_raw,horse_no) WHERE c.race_key_raw IS NULL),
                (SELECT COUNT(*) FROM (SELECT race_key_raw,horse_no FROM
                  jpdb_cond_2026 GROUP BY 1,2 HAVING COUNT(*)!=1))''').fetchone()
            if any(checks):
                raise JPDBHistoryReaderError(f'P2 projection identity mismatch: {checks}')
            spec=json.loads(Path(manifest).read_text(encoding='utf-8'))
            paths=[str((Path(input_root)/f'sed_{year}'/
                        next(x for x in spec['artifacts'] if x['artifact_id']==f'sed_{year}')['expected_name']).resolve())
                   for year in (2023,2024,2025)]
            sql_paths=','.join(_quote(x) for x in paths)
            self.db.execute('''CREATE VIEW jpdb_condition_facts AS
                SELECT race_date, jockey_code, surface_code, abnormal_code,
                       finish, field_size, race_key_raw, horse_no,
                       venue_code, distance_m, track_condition_code,
                       race_class_code, grade_code,course_code,turn_code,layout_code
                FROM read_parquet(['''+sql_paths+'''],union_by_name=true)
                UNION ALL BY NAME
                SELECT s.race_date,s.jockey_code,s.surface_code,s.abnormal_code,
                       s.finish,s.field_size,s.race_key_raw,s.horse_no,
                       SUBSTR(s.race_key_raw,1,2) AS venue_code,
                       c.distance_m,c.track_condition_code,c.race_class_code,
                       c.grade_code,c.course_code,c.turn_code,c.layout_code
                FROM sed_2026 AS s JOIN jpdb_cond_2026 AS c
                  USING(race_key_raw,horse_no)''')
            total=self.db.execute('SELECT COUNT(*) FROM jpdb_condition_facts').fetchone()[0]
            base=self.db.execute('SELECT COUNT(*) FROM sed_all').fetchone()[0]
            if total!=base:
                raise JPDBHistoryReaderError('P2 join multiplied/lost source rows')
            disagreement=self.db.execute('''SELECT COUNT(*) FROM jpdb_condition_facts
                WHERE venue_code NOT IN ('01','02','03','04','05','06','07','08','09','10')
                   OR venue_code!=SUBSTR(race_key_raw,1,2)''').fetchone()[0]
            if disagreement:
                raise JPDBHistoryReaderError('P2 venue inconsistent with race key')
            self.condition_source_rows=total
        except Exception:
            self.close()
            raise

    def rider_conditions(self, *, target_date: str, jockey_codes: list[str]) -> dict:
        day=validate_extended_target(target_date,fresh_through=self.daily_coverage_to)
        codes=_checked_codes(jockey_codes)
        windows=_windows(day)
        marks=','.join('?' for _ in codes)
        # All groups including blank source codes are retained. No smoothing or
        # false-ability labels; low-sample threshold is exploratory only.
        select='''COUNT(*) AS entries,
          COUNT(*) FILTER (WHERE '''+NORMAL+''') AS normal_finishers,
          COUNT(*) FILTER (WHERE abnormal_code='1') AS cancellations,
          COUNT(*) FILTER (WHERE abnormal_code='2') AS exclusions,
          COUNT(*) FILTER (WHERE abnormal_code='3') AS dnf,
          COUNT(*) FILTER (WHERE abnormal_code='5') AS demotion_review,
          COUNT(*) FILTER (WHERE abnormal_code IS NULL OR
            abnormal_code NOT IN ('0','','1','2','3','5')) AS unknown_codes,
          COUNT(*) FILTER (WHERE abnormal_code IN ('0','') AND
            (finish IS NULL OR field_size IS NULL OR field_size<1 OR
             finish NOT BETWEEN 1 AND field_size)) AS invalid_normal_finish,
          COUNT(*) FILTER (WHERE '''+NORMAL+''' AND finish=1) AS wins,
          COUNT(*) FILTER (WHERE '''+NORMAL+''' AND finish<=2) AS top2,
          COUNT(*) FILTER (WHERE '''+NORMAL+''' AND finish<=3) AS top3,
          MIN(race_date) AS first_observed,MAX(race_date) AS last_observed'''
        result={code:{window:{} for window in windows} for code in codes}
        for window,lower in windows.items():
            for dim,columns in DIMENSIONS.items():
                dim_sql=','.join(columns)
                sql=f'''SELECT jockey_code,{dim_sql},{select}
                      FROM jpdb_condition_facts
                      WHERE race_date>=? AND race_date<?
                        AND surface_code IN ('1','2')
                        AND jockey_code IN ({marks})
                      GROUP BY jockey_code,{dim_sql}'''
                rows=self.db.execute(sql,[lower,day.isoformat(),*codes]).fetchall()
                for row in rows:
                    code=row[0]
                    values=row[1:1+len(columns)]
                    counts=dict(zip(COUNTS,row[1+len(columns):1+len(columns)+len(COUNTS)]))
                    start,last=row[-2:]
                    metric=_metrics(counts,start,last,day.isoformat())
                    raw={column:value for column,value in zip(columns,values)}
                    miss=any(v is None or v=='' for v in values)
                    if miss:
                        metric['sample_support_status']='REVIEW_REQUIRED'
                    result[code][window].setdefault(dim,[]).append({
                        'dimension_set_id':dim,
                        'dimension_value':raw,
                        'source_status':'MISSING_RAW_CODE' if miss else 'RAW_CODE_OBSERVED',
                        'physical_version_status':('NOT_VALIDATED' if dim=='COURSE_RAW_CODE' else 'NOT_APPLICABLE'),
                        'sample_n':metric['actual_starts_candidate'],
                        'metrics':metric,
                        'descriptive_only':True,
                    })
        for code in codes:
            for window in windows:
                population_n=self._flat_n(day,windows[window],code)
                for dim in DIMENSIONS:
                    cells=result[code][window].setdefault(dim,[])
                    cells.sort(key=lambda cell:tuple('' if v is None else str(v)
                        for v in cell['dimension_value'].values()))
                    if sum(c['metrics']['entries'] for c in cells)!=population_n:
                        raise JPDBHistoryReaderError(f'P2 {window}/{dim} partition count != flat')
                    for cell in cells:
                        metric=cell['metrics']
                        cell['population_n']=population_n
                        cell['coverage_ratio']=metric['entries']/population_n if population_n else None
                        cell['sample_support_status']=metric['sample_support_status']
                        cell['history_days']=(date.fromisoformat(metric['last_observed'])-date.fromisoformat(metric['first_observed'])).days if metric['first_observed'] is not None else None
                        cell['last_observed_date']=metric['last_observed']
                        cell['unclassified_n']=metric['unresolved_count']
        return {
            'schema_version':VERSION,'target_date':day.isoformat(),
            'asof_policy':POLICY,'strict_asof_certified':False,
            'assumption_based_backtest_eligible':True,
            'population_filter_id':'JPDB_FLAT_RIDE_START_V1_CANDIDATE',
            'source_generation':SOURCE_GENERATION+'+daily2026:'+self.daily_manifest_sha256[:16],
            'historical_source_manifest_sha256':self.manifest_sha256,
            'daily_source_manifest_sha256':self.daily_manifest_sha256,
            'source_rows_total':self.condition_source_rows,
            'dimension_contract':{'SURFACE_DISTANCE_EXACT':'exact metres; no unapproved distance bands',
                                  'COURSE_RAW_CODE':'source code only; physical Course Master validation pending'},
            'jockey_conditions':result,
            'prediction_safe':False,
        }

    def _flat_n(self,day:date,lower:str,code:str)->int:
        return self.db.execute('''SELECT COUNT(*) FROM sed_all
            WHERE race_date >=? AND race_date <? AND jockey_code=?
              AND surface_code IN ('1','2')''',[lower,day.isoformat(),code]).fetchone()[0]
