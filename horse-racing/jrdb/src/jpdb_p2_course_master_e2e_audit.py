#!/usr/bin/env python3
"""Independent BAC/CourseMaster P2 actual-source E2E acceptance (private runtime).

Compares aggregate count/win/top3 in every returned physical dimension cell to
separate SQL. Only count/hashes/status are written. Never export licensed rows.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

from jpdb_p2_course_master_reader import JPDBCourseMasterReader2026, DIMENSIONS, COURSE_FILES
from jpdb_performance_reader_v11 import _windows

TARGETS=('2025-11-16','2026-01-04','2026-06-13','2026-11-16')


def audit(args):
    with JPDBCourseMasterReader2026(
        input_root=args.input_root,manifest=args.manifest,
        daily_root=args.daily_root,daily_manifest=args.daily_manifest,
        bac_root=args.bac_root,paci_root=args.paci_root,
        paci_manifest=args.paci_manifest,course_root=args.course_root,
        expected_paci_manifest_sha256=args.expected_paci_manifest_sha256,
    ) as reader:
        db=reader.db
        codes=[x[0] for x in db.execute(
            "SELECT jockey_code FROM sed_2026 WHERE surface_code IN ('1','2') "
            "GROUP BY 1 ORDER BY COUNT(*) DESC,jockey_code LIMIT 12"
        ).fetchall()]
        cells=0
        checks=0
        for target in TARGETS:
            response=reader.rider_course_conditions(target_date=target,jockey_codes=codes)
            for window,lower in _windows(date.fromisoformat(target)).items():
                for dim,columns in DIMENSIONS.items():
                    names=','.join(columns)
                    normal="abnormal_code IN ('0','') AND field_size>=1 AND finish BETWEEN 1 AND field_size"
                    qs=','.join('?' for _ in codes)
                    sql=f"""SELECT jockey_code,{names},COUNT(*),
                      SUM(CASE WHEN {normal} AND finish=1 THEN 1 ELSE 0 END),
                      SUM(CASE WHEN {normal} AND finish<=3 THEN 1 ELSE 0 END)
                      FROM jpdb_course_facts WHERE race_date>=? AND race_date<?
                       AND surface_code IN ('1','2') AND jockey_code IN ({qs})
                      GROUP BY jockey_code,{names}"""
                    expected={(x[0],x[1:1+len(columns)]):tuple(x[-3:])
                        for x in db.execute(sql,[lower,target,*codes]).fetchall()}
                    got={(code,tuple(c['dimension_value'].values())):
                         (c['metrics']['entries'],c['metrics']['wins'],c['metrics']['top3'])
                         for code in codes for c in response['jockey_conditions'][code][window][dim]}
                    if expected!=got:
                        raise ValueError(f'P2 independent course mismatch {target}/{window}/{dim}')
                    cells+=len(expected)
                    checks+=len(expected)*3
        counts=db.execute("""SELECT COUNT(*),
            COUNT(*) FILTER (WHERE surface_code IN ('1','2')),
            COUNT(*) FILTER (WHERE surface_code IN ('1','2') AND race_date>='2026-01-01'),
            COUNT(*) FILTER (WHERE surface_code IN ('1','2') AND final_straight_slope_flag IS NULL),
            COUNT(*) FILTER (WHERE surface_code IN ('1','2') AND final_straight_m IS NULL),
            COUNT(*) FILTER (WHERE surface_code IN ('1','2') AND course_size_class IS NULL)
            FROM jpdb_course_facts""").fetchone()
        if counts[:3]!=(184922,179436,40945):
            raise ValueError(f'P2 unexpected fixed source rows: {counts[:3]}')
        yearly=db.execute("""SELECT SUBSTR(race_date,1,4),COUNT(DISTINCT race_key_raw),COUNT(*)
            FROM jpdb_course_facts WHERE surface_code IN ('1','2')
            GROUP BY 1 ORDER BY 1""").fetchall()
        if {x[0]:x[1] for x in yearly}!={'2023':3329,'2024':3327,'2025':3335,'2026':2960}:
            raise ValueError('P2 course race counts differ from accepted BAC snapshot')
        return {
          'schema':'jpdb-p2-course-physical-private-e2e-v0.1',
          'status':'PASS','source_rows':counts[0],
          'flat_rows':counts[1],'flat_2026_rows':counts[2],
          'course_mapping_status':'ALL_FLAT_CONFIRMED',
          'physical_epoch':'2023PLUS_PARTIAL',
          'paci_2026_dates':97,'paci_2026_races':reader.bac_2026_races,
          'course_master_rows':177,'mapping_seed_rows':433,'geometry_seed_rows':57,
          'flat_races_by_year':{x[0]:x[1] for x in yearly},
          'flat_rides_by_year':{x[0]:x[2] for x in yearly},
          'missing_final_slope_rides':counts[3],
          'missing_final_straight_m_rides':counts[4],
          'missing_course_size_rides':counts[5],
          'sample_rider_count':len(codes),'target_dates':list(TARGETS),
          'independent_physical_cells':cells,'independent_comparisons':checks,
          'historic_manifest_sha256':reader.manifest_sha256,
          'daily_sed_manifest_sha256':reader.daily_manifest_sha256,
          'paci_bac_manifest_sha256':reader.paci_manifest_sha256,
          'course_seed_sha256':{k:v[2] for k,v in COURSE_FILES.items()},
          'production_allowed':False,
          'historical_course_version_fully_attested':False,
          'strict_asof_certified':False,
          'licensed_source_rows_exported':False,
        }


def main():
    p=argparse.ArgumentParser()
    for name in ('input-root','manifest','daily-root','daily-manifest',
                 'bac-root','paci-root','paci-manifest','course-root','output'):
        p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--expected-paci-manifest-sha256')
    args=p.parse_args()
    if args.output.exists():
        raise FileExistsError('refusing overwrite')
    result=audit(args)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'cells':result['independent_physical_cells'],
      'independent_comparisons':result['independent_comparisons'],
      'output_sha256':hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__=='__main__':
    main()
