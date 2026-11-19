#!/usr/bin/env python3
"""JPDB P2 independent real-source acceptance; aggregate receipts only.

This script must run inside an approved private context holding SHA-pinned
historical Parquet and selected daily SED ZIPs. Never publish source rows.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from jpdb_p2_condition_reader import JPDBConditionReader2026, DIMENSIONS
from jpdb_performance_reader_v11 import _windows

TARGETS=('2025-11-16','2026-01-04','2026-06-13','2026-11-16')


def audit(args):
    with JPDBConditionReader2026(
        input_root=args.input_root,manifest=args.manifest,
        daily_root=args.daily_root,daily_manifest=args.daily_manifest,
        expected_daily_manifest_sha256=args.expected_daily_manifest_sha256,
    ) as reader:
        codes=[x[0] for x in reader.db.execute(
            "SELECT jockey_code FROM sed_2026 WHERE surface_code IN ('1','2') "
            "GROUP BY 1 ORDER BY COUNT(*) DESC,jockey_code LIMIT 12").fetchall()]
        checks=0
        groups=0
        for target in TARGETS:
            actual=reader.rider_conditions(target_date=target,jockey_codes=codes)
            for window,lower in _windows(date.fromisoformat(target)).items():
                for dim,columns in DIMENSIONS.items():
                    names=','.join(columns)
                    qs=','.join('?' for _ in codes)
                    normal="abnormal_code IN ('0','') AND field_size>=1 AND finish BETWEEN 1 AND field_size"
                    sql=f"""SELECT jockey_code,{names},COUNT(*),
                      SUM(CASE WHEN {normal} AND finish=1 THEN 1 ELSE 0 END),
                      SUM(CASE WHEN {normal} AND finish<=3 THEN 1 ELSE 0 END)
                      FROM jpdb_condition_facts
                      WHERE surface_code IN ('1','2')
                        AND race_date>=? AND race_date<?
                        AND jockey_code IN ({qs})
                      GROUP BY jockey_code,{names}"""
                    expected={(r[0],r[1:1+len(columns)]):tuple(r[-3:])
                        for r in reader.db.execute(sql,[lower,target,*codes]).fetchall()}
                    observed={(code,tuple(cell['dimension_value'].values())):
                        (cell['metrics']['entries'],cell['metrics']['wins'],cell['metrics']['top3'])
                        for code in codes for cell in actual['jockey_conditions'][code][window][dim]}
                    if expected!=observed:
                        raise ValueError(f'independent comparison mismatch {target}/{window}/{dim}')
                    checks+=len(expected)*3
                    groups+=len(expected)
        rows=reader.db.execute("""SELECT
            COUNT(*),
            COUNT(*) FILTER (WHERE surface_code IN ('1','2')),
            COUNT(*) FILTER (WHERE surface_code IN ('1','2') AND race_date>='2026-01-01')
            FROM jpdb_condition_facts""").fetchone()
        if rows!=(184922,179436,40945):
            raise ValueError(f'Unexpected real source population: {rows}')
        catalog={}
        for dim,columns in DIMENSIONS.items():
            names=','.join(columns)
            distinct=reader.db.execute(f"""SELECT COUNT(*) FROM (
                SELECT {names} FROM jpdb_condition_facts
                WHERE surface_code IN ('1','2') GROUP BY {names})""").fetchone()[0]
            missing_condition=" OR ".join(
                f"({c} IS NULL" + (f" OR {c}=''" if c!='distance_m' else '')+")"
                for c in columns)
            missing=reader.db.execute(f"""SELECT COUNT(*) FROM jpdb_condition_facts
                WHERE surface_code IN ('1','2') AND race_date>='2026-01-01'
                AND ({missing_condition})""").fetchone()[0]
            catalog[dim]={'unique_raw_condition_values_all_years':distinct,
                          '2026_missing_component_rows':missing}
        return {
            'schema':'jpdb-p2-conditions-private-e2e-v0.1',
            'status':'PASS',
            'scope':'2023-2025 accepted SED Parquet + 2026 selected real daily SED ZIP',
            'source_rows':rows[0],'flat_rows':rows[1],'flat_2026_rows':rows[2],
            'riders_compared':len(codes),'target_dates':list(TARGETS),
            'independent_comparisons':checks,'independent_condition_cells':groups,
            'dimension_catalog':catalog,
            'historical_manifest_sha256':reader.manifest_sha256,
            'daily_manifest_sha256':reader.daily_manifest_sha256,
            'course_physical_validity_certified':False,
            'prediction_safe':False,'licensed_rows_exported':False,
        }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--input-root',required=True,type=Path)
    ap.add_argument('--manifest',required=True,type=Path)
    ap.add_argument('--daily-root',required=True,type=Path)
    ap.add_argument('--daily-manifest',required=True,type=Path)
    ap.add_argument('--expected-daily-manifest-sha256')
    ap.add_argument('--output',required=True,type=Path)
    args=ap.parse_args()
    if args.output.exists():
        raise FileExistsError('refusing overwrite')
    result=audit(args)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,
        sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'cells':result['independent_condition_cells'],
                      'independent_comparisons':result['independent_comparisons'],
                      'output_sha256':hashlib.sha256(args.output.read_bytes()).hexdigest()}))


if __name__=='__main__':
    main()
