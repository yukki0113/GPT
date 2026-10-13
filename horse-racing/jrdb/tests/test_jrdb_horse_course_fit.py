"""Leakage, physical validity, previous-start, and restart regression tests."""
from datetime import date, timedelta
import importlib.util
import json
from pathlib import Path
import sys

import duckdb
import pytest

SRC = Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0,str(SRC))
import jrdb_horse_course_fit as fit


def fixture_inputs(tmp):
    con = duckdb.connect()
    con.execute('''CREATE TABLE sed(race_date VARCHAR,race_key_raw VARCHAR,horse_no BIGINT,
      blood_registration_no VARCHAR,horse_name VARCHAR,venue_code VARCHAR,surface_code VARCHAR,
      distance_m BIGINT,turn_code VARCHAR,layout_code VARCHAR,course_code VARCHAR,
      track_condition_code VARCHAR,finish BIGINT,corner_4 BIGINT,first3f_sec DOUBLE,last3f_sec DOUBLE,
      race_pace_code VARCHAR,abnormal_code VARCHAR,source_member_date VARCHAR,
      source_record_ordinal BIGINT,source_record_sha256 VARCHAR)''')
    con.execute('''CREATE TABLE hp(race_date DATE,race_key VARCHAR,race_horse_key VARCHAR,
      horse_no BIGINT,horse_id VARCHAR,finish BIGINT,surface_code VARCHAR,distance_m BIGINT,
      first3f_sec DOUBLE,last3f_sec DOUBLE,horse_adjusted_delta_per_1000m DOUBLE)''')
    con.execute('CREATE TABLE rr(race_key VARCHAR,race_date DATE,standard_sample_end_date DATE,time_delta_basis VARCHAR)')
    # 2022 history produces baselines, but must never receive current physical attributes.
    dates = [date(2022,10,1)+timedelta(days=30*i) for i in range(16)]
    for i,d in enumerate(dates):
        key = f'0523{i:04d}'
        signal = float(i%3)-1
        con.execute('INSERT INTO sed VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    [str(d),key,1,'00000001','fixture','05','1',1600+(i%2)*200,'2','1','1',
                     '11' if i%2 else '21',1,2,35.,34.,'M','0',str(d),i,'fixture-hash'])
        con.execute('INSERT INTO hp VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    [d,key,key+'01',1,'00000001',1,'1',1600+(i%2)*200,35.,34.,-signal])
        con.execute('INSERT INTO rr VALUES (?,?,?,?)',[key,d,d-timedelta(days=1),'ASOF'])
    for name in ('sed','hp','rr'):
        con.execute(f"COPY {name} TO '{tmp/name}.parquet' (FORMAT PARQUET)")
    con.close()
    master = tmp/'master'; master.mkdir()
    # Test fixtures only; production Phase3 artifacts are verified separately against main.
    rows = []
    for distance in (1600,1800):
        rows.append(dict(course_key=f'JRA:05:T:{distance}:main',venue_code='05',surface_code='1',
            layout_variant='main',current_jra_official=True,physical_valid_from='2023-01-01',
            physical_valid_to_exclusive=None,physical_version_id='fixture-2023',final_straight_m=500.,
            final_straight_slope_flag=True,course_size_class='LARGE',elevation_difference_m=2.,turn_direction='left'))
    (master/'course_master_seed_v0_1.jsonl').write_text('\n'.join(json.dumps(r) for r in rows))
    geom=dict(venue_code='05',surface_code='1',layout_variant='main',jrdb_course_code='1',
        geometry_key='JRA-GEO:05:T:main:A',physical_valid_from='2023-01-01',physical_valid_to_exclusive=None,
        physical_version_id='fixture-2023',final_straight_m=500.,final_straight_slope_flag=True,
        course_size_class='LARGE',elevation_difference_m=2.)
    (master/'course_geometry_configuration_v0_1.jsonl').write_text(json.dumps(geom))
    return master,dates


def build(tmp,as_of='2024-02-01',out='out'):
    master,dates = fixture_inputs(tmp)
    pipeline=fit.Pipeline(tmp/out,as_of,{'fixture':True},'fixture-git-sha')
    pipeline.base([tmp/'sed.parquet'],[tmp/'hp.parquet'],[tmp/'rr.parquet'],master)
    pipeline.residual(); pipeline.features()
    return pipeline,dates


def test_physical_gate_both_sides_and_residual(tmp_path):
    p,dates=build(tmp_path)
    c=p.con
    assert c.execute("SELECT count(*) FROM ledger WHERE race_date<'2023-01-01' AND final_straight_m IS NOT NULL").fetchone()[0]==0
    assert c.execute("SELECT baseline_sample_count FROM residual ORDER BY race_date LIMIT 4").fetchall()==[(0,),(1,),(2,),(3,)]
    assert c.execute("SELECT MAX(baseline_sample_count) FROM residual").fetchone()[0]==10
    expected_mean=sum(float(i%3)-1 for i in range(5,15))/10
    assert c.execute("SELECT horse_baseline_performance FROM residual ORDER BY race_date DESC LIMIT 1").fetchone()[0]==pytest.approx(expected_mean)
    p.fits('ABSOLUTE');p.fits('TRANSITION');p.research()
    audit=p.reports(); assert audit['status']=='PASS'
    slope=c.execute("SELECT sample_count,source_min_date FROM candidate WHERE feature_type='FINAL_SLOPE_CHANGE'").fetchone()
    assert slope[1]>date(2023,1,1)
    expected=c.execute("SELECT count(*) FROM transitions WHERE previous_physical_valid AND physical_valid AND performance_residual IS NOT NULL").fetchone()[0]
    assert slope[0]==expected
    abs_fit=c.execute("SELECT sample_count,raw_delta,shrunk_delta FROM candidate WHERE feature_type='FINAL_SLOPE'").fetchone()
    assert abs_fit[2]==pytest.approx(abs_fit[1]*abs_fit[0]/(abs_fit[0]+5))
    p.con.close()


def test_window_target_exclusion_and_rolling_limit(tmp_path):
    p,dates=build(tmp_path,as_of='2023-04-29')
    c=p.con
    assert c.execute("SELECT MAX(race_date) FROM ledger").fetchone()[0]<date(2023,4,29)
    p.con.close()
    assert fit.three_years_before('2024-02-29')=='2021-02-28'
    # SQL used by baseline is calendar-year bounded and capped on actual starts, not valid signals.
    con=duckdb.connect()
    assert con.execute("SELECT DATE '2024-02-29'-INTERVAL '3 years'").fetchone()[0].date()==date(2021,2,28)
    con.close()


def test_restart_reuses_identical_artifacts(tmp_path):
    p,dates=build(tmp_path)
    p.fits('ABSOLUTE');p.fits('TRANSITION');p.research();p.reports();p.manifest()
    hashes={n:m['sha256'] for n,m in p.artifacts.items()};p.con.close()
    master=tmp_path/'master'
    q=fit.Pipeline(tmp_path/'out','2024-02-01',{'fixture':True},'fixture-git-sha')
    q.base([tmp_path/'sed.parquet'],[tmp_path/'hp.parquet'],[tmp_path/'rr.parquet'],master)
    q.residual();q.features();q.fits('ABSOLUTE');q.fits('TRANSITION');q.research();q.reports()
    assert {n:m['sha256'] for n,m in q.artifacts.items()}==hashes
    assert len(q.reused)==len(hashes)
    q.con.close()


def test_end_exclusive_masks_current_attributes(tmp_path):
    master,dates=fixture_inputs(tmp_path)
    path=master/'course_geometry_configuration_v0_1.jsonl';r=json.loads(path.read_text())
    r['physical_valid_to_exclusive']='2023-05-01';path.write_text(json.dumps(r))
    cm=master/'course_master_seed_v0_1.jsonl';rows=[json.loads(x) for x in cm.read_text().splitlines()]
    for r in rows:r['physical_valid_to_exclusive']='2023-05-01'
    cm.write_text('\n'.join(json.dumps(r) for r in rows))
    p=fit.Pipeline(tmp_path/'out','2024-02-01',{'fixture':True},'fixture')
    p.base([tmp_path/'sed.parquet'],[tmp_path/'hp.parquet'],[tmp_path/'rr.parquet'],master)
    assert p.con.execute("SELECT count(*) FROM ledger WHERE race_date>='2023-05-01' AND final_straight_m IS NOT NULL").fetchone()[0]==0
    p.con.close()


def test_corrected_rrdb_mismatch_fails_closed(tmp_path):
    master,dates=fixture_inputs(tmp_path)
    c=duckdb.connect();c.execute(f"COPY (SELECT * REPLACE (2 AS finish) FROM read_parquet('{tmp_path/'hp.parquet'}')) TO '{tmp_path/'bad_hp.parquet'}' (FORMAT PARQUET)");c.close()
    p=fit.Pipeline(tmp_path/'out','2024-02-01',{},'fixture')
    with pytest.raises(ValueError,match='correction or identity mismatch'):
        p.base([tmp_path/'sed.parquet'],[tmp_path/'bad_hp.parquet'],[tmp_path/'rr.parquet'],master)
    p.con.close()


def test_immediate_previous_null_performance_and_surface(tmp_path):
    master,dates=fixture_inputs(tmp_path)
    c=duckdb.connect()
    # Missing performance in an actual start must not cause transition LAG to skip it.
    c.execute(f"CREATE TABLE h AS SELECT * FROM read_parquet('{tmp_path/'hp.parquet'}')")
    c.execute("UPDATE h SET horse_adjusted_delta_per_1000m=NULL WHERE race_key='05230010'")
    c.execute(f"COPY h TO '{tmp_path/'hp2.parquet'}' (FORMAT PARQUET)");c.close()
    p=fit.Pipeline(tmp_path/'out','2024-02-01',{},'fixture')
    p.base([tmp_path/'sed.parquet'],[tmp_path/'hp2.parquet'],[tmp_path/'rr.parquet'],master)
    p.residual();p.features()
    assert p.con.execute("SELECT previous_race_key FROM transitions WHERE race_key='05230011'").fetchone()[0]=='05230010'
    p.con.close()


def test_three_year_old_sources_do_not_enter_baseline(tmp_path):
    master,dates=fixture_inputs(tmp_path)
    c=duckdb.connect()
    for name in ('sed','hp','rr'):
        c.execute(f"CREATE TABLE {name} AS SELECT * FROM read_parquet('{tmp_path/name}.parquet')")
    c.execute("UPDATE sed SET race_date='2000-01-01',source_member_date='2000-01-01' WHERE race_key_raw='05230000'")
    c.execute("UPDATE hp SET race_date=DATE '2000-01-01' WHERE race_key='05230000'")
    c.execute("UPDATE rr SET race_date=DATE '2000-01-01',standard_sample_end_date=DATE '1999-12-31' WHERE race_key='05230000'")
    for name in ('sed','hp','rr'):
        c.execute(f"COPY {name} TO '{tmp_path/(name+'2')}.parquet' (FORMAT PARQUET)")
    c.close()
    p=fit.Pipeline(tmp_path/'out','2026-01-01',{},'fixture')
    p.base([tmp_path/'sed2.parquet'],[tmp_path/'hp2.parquet'],[tmp_path/'rr2.parquet'],master)
    p.residual();p.features();p.fits('ABSOLUTE');p.fits('TRANSITION');p.research()
    assert p.con.execute("SELECT baseline_sample_count FROM residual WHERE race_key='05230003'").fetchone()[0]==2
    assert p.con.execute("SELECT MIN(source_min_date) FROM candidate").fetchone()[0]>=date(2023,1,1)
    p.con.close()


def test_going_cross_surface_excluded_distance_preserved(tmp_path):
    master,dates=fixture_inputs(tmp_path)
    c=duckdb.connect()
    for name in ('sed','hp'):
        c.execute(f"CREATE TABLE {name} AS SELECT * FROM read_parquet('{tmp_path/name}.parquet')")
        key='race_key_raw' if name=='sed' else 'race_key'
        c.execute(f"UPDATE {name} SET surface_code='2' WHERE {key} IN ('05230008','05230010','05230012','05230014')")
        c.execute(f"COPY {name} TO '{tmp_path/(name+'2')}.parquet' (FORMAT PARQUET)")
    c.close()
    p=fit.Pipeline(tmp_path/'out','2024-02-01',{},'fixture')
    p.base([tmp_path/'sed2.parquet'],[tmp_path/'hp2.parquet'],[tmp_path/'rr.parquet'],master)
    p.residual();p.features()
    p.fits('TRANSITION','GOING_CHANGE')
    assert p.con.execute('SELECT COUNT(*) FROM selected WHERE surface_changed').fetchone()[0]==0
    p.fits('TRANSITION','DISTANCE_CHANGE')
    assert p.con.execute('SELECT COUNT(*) FROM selected WHERE surface_changed').fetchone()[0]>0
    p.fits('ABSOLUTE','FINAL_SLOPE')
    absolute=duckdb.connect()
    rows=absolute.execute(f"SELECT surface_changed FROM read_parquet('{tmp_path/'out/absolute_fit/horse_final_slope_fit.parquet'}')").fetchall()
    assert rows==[(False,)]
    absolute.close()
    p.con.close()
