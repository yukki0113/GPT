#!/usr/bin/env python3
"""P1-4: fail-closed BRDB pre-race feature provenance eligibility audit.

All P0-2 pedigree facts are retrospective selected static snapshots. This
routine NEVER promotes them to as-of safe even if a caller attaches a timestamp.
Only evidence-class counts are emitted; no licensed row-level records are exported.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
import duckdb

VERSION = 'brdb-p1-4-asof-gate-v0.1'
UNVERIFIED = 'STATIC_LATER_SELECTED_SNAPSHOT_NOT_ASOF_VERIFIED'
REQUIRED = {
    'race_year': 'INTEGER', 'race_key': 'VARCHAR', 'horse_no': 'BIGINT',
    'horse_id': 'VARCHAR', 'race_date': 'VARCHAR', 'normal_finisher': 'BOOLEAN',
    'pedigree_status': 'VARCHAR', 'pedigree_temporal_status': 'VARCHAR',
}

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()

def assess_status(status: str, observed_date: str | None = None, race_date: str | None = None,
                  *, signed_source_attestation: bool = False) -> str:
    """Classify a statement, never treat an asserted date as independent proof.

    Source attestation is intentionally not implemented: a self-declared boolean
    or timestamp cannot establish a source snapshot or actual pre-race release.
    """
    if status == UNVERIFIED:
        return 'STATIC_SNAPSHOT_NOT_ASOF_VERIFIED'
    if not observed_date or not race_date:
        return 'NO_INDEPENDENT_SOURCE_DATE'
    if not re.fullmatch(r'\d{8}', observed_date) or not re.fullmatch(r'\d{8}', race_date):
        return 'INVALID_OBSERVATION_DATE'
    if observed_date > race_date:
        return 'FUTURE_OBSERVATION'
    if observed_date == race_date:
        return 'SAME_DAY_PUBLICATION_TIME_UNKNOWN'
    # A date on its own, even with a truthy user-provided flag, cannot prove
    # that the specific feature values were present in the historical archive.
    return 'SOURCE_MEMBERSHIP_NOT_ATTESTED'

def run(mart: Path, out: Path, *, expected_sha: str, fail_on_ineligible: bool = False) -> dict:
    mart, out = Path(mart), Path(out)
    if not re.fullmatch(r'[0-9a-f]{64}', expected_sha) or sha256(mart) != expected_sha:
        raise ValueError('historical research mart SHA mismatch')
    con = duckdb.connect(database=':memory:')
    con.execute('SET threads=1')
    try:
        con.execute("CREATE VIEW mart AS SELECT * FROM read_parquet('" + str(mart).replace("'", "''") + "')")
        schema = dict(row[:2] for row in con.execute('DESCRIBE SELECT * FROM mart').fetchall())
        for col, typ in REQUIRED.items():
            if schema.get(col) != typ:
                raise ValueError(f'missing/wrong type required column: {col}')
        n = con.execute('SELECT COUNT(*) FROM mart').fetchone()[0]
        if n == 0:
            raise ValueError('empty cohort')
        checks = {
            'bad_or_duplicate_keys': "SELECT COUNT(*) FROM (SELECT race_key,horse_no FROM mart GROUP BY 1,2 HAVING COUNT(*)>1 OR race_key IS NULL OR horse_no IS NULL)",
            'invalid_years': "SELECT COUNT(*) FROM mart WHERE race_year NOT BETWEEN 2016 AND 2025 OR race_year IS NULL OR race_date IS NULL OR NOT regexp_full_match(race_date, '[0-9]{8}') OR try_strptime(race_date, '%Y%m%d') IS NULL OR TRY_CAST(substr(race_date,1,4) AS INT) IS DISTINCT FROM race_year",
            'missing_identity': "SELECT COUNT(*) FROM mart WHERE horse_id IS NULL OR NOT regexp_full_match(horse_id,'[0-9]{8}')",
            'unexpected_temporal_status': "SELECT COUNT(*) FROM mart WHERE pedigree_temporal_status IS NULL OR pedigree_temporal_status <> '" + UNVERIFIED + "'",
        }
        errors={name:con.execute(sql).fetchone()[0] for name,sql in checks.items()}
        if any(errors.values()):
            raise ValueError(f'input contract failed: {errors}')
        breakdown=con.execute('''SELECT race_year, count(*) entries,
            count(*) FILTER (WHERE normal_finisher) normal_finishers,
            count(*) FILTER (WHERE pedigree_status='STATIC_ONLY') static_pedigree,
            count(*) FILTER (WHERE pedigree_status <> 'STATIC_ONLY' OR pedigree_status IS NULL) missing_pedigree
            FROM mart GROUP BY 1 ORDER BY 1''').fetchall()
        if len(breakdown)!=10 or [int(x[0]) for x in breakdown]!=list(range(2016,2026)):
            raise ValueError('unexpected annual cohort coverage')
        annual=[dict(zip(('year','entries','normal_finishers','static_pedigree','missing_pedigree'),row)) for row in breakdown]
        static=sum(row['static_pedigree'] for row in annual)
        missing=sum(row['missing_pedigree'] for row in annual)
        assert static+missing==n
        result={
            'version':VERSION,'status':'PASS_AS_AUDIT_ONLY', 'prediction_safe':False,
            'source_mart_sha256':expected_sha,'total_entries':n,
            'static_unverified_entries':static,'missing_pedigree_entries':missing,
            'asof_proven_entries':0,'asof_proven_normal_finishers':0,
            'blocked_entries':n,'blocked_reason':'NO_HISTORICAL_PRE_RACE_PEDIGREE_PROVENANCE',
            'observed_status':UNVERIFIED, 'annual':annual,
            'future_release_time_attested':False,
            'gate':'BLOCK_P1_5_TO_P1_7_PREDICTIVE_EVALUATION',
            'required_next_input':(
                'Independently SHA-verified historical pre-race UKC or equivalent feature '
                'snapshots, observed/release time, horse ID, race ID and each feature '
                'value, with provenance membership and no future overwrite'),
        }
        out.mkdir(parents=True,exist_ok=True)
        # Serialize only aggregate counts, never horse rows or lineage results.
        dst=out/'asof_eligibility_audit.json'
        dst.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        if fail_on_ineligible and n:
            raise ValueError('all historical pedigree features withheld: no pre-race provenance')
        return result
    finally:
        con.close()

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--mart',required=True,type=Path)
    p.add_argument('--mart-sha256',required=True)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--require-prediction-safe',action='store_true')
    args=p.parse_args()
    print(json.dumps(run(args.mart,args.out,expected_sha=args.mart_sha256,
                         fail_on_ineligible=args.require_prediction_safe),sort_keys=True))
if __name__=='__main__':
    main()
