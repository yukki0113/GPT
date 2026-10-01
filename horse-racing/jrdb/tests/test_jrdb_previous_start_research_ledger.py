"""Temporal boundary and missing-history contracts for the all-runner builder."""
import json
import sys
from pathlib import Path
import duckdb
import pandas as pd
import math

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from jrdb_previous_start_research_ledger import build_features


def test_future_and_target_same_date_cannot_change_features():
    con=duckdb.connect()
    con.execute('''CREATE TABLE hp(horse_id VARCHAR,horse_name VARCHAR,venue_code VARCHAR,horse_no INTEGER,
        race_date DATE,race_key VARCHAR,race_horse_key VARCHAR,finish INTEGER,time_sec DOUBLE,
        surface_code VARCHAR,distance_m INTEGER,field_size INTEGER,declared_class_group VARCHAR,
        horse_adjusted_delta_per_1000m DOUBLE,last3f_speed_percentile DOUBLE,corner4_frontness DOUBLE,pace_shape VARCHAR)''')
    con.execute("INSERT INTO hp VALUES ('00000001','馬','06',1,'2026-08-30','06263401','0626340101',6,90,'1',1600,10,'CLASS_1',-0.5,90,0.8,'VERY_FRONT_LOADED')")
    con.execute('''CREATE TABLE rc(race_key VARCHAR,first3f_reference_sec DOUBLE,last3f_reference_sec DOUBLE,
        pace_balance_sec DOUBLE,pace_balance_percentile DOUBLE,pace_shape VARCHAR,pace_sample_count INTEGER,pace_scope_level INTEGER)''')
    con.execute("INSERT INTO rc VALUES ('06263401',34,36,2,90,'VERY_FRONT_LOADED',100,1)")
    con.execute('''CREATE TABLE rr(race_key VARCHAR,standard_sample_start_date DATE,standard_sample_end_date DATE,
        standard_sample_count INTEGER,time_delta_basis VARCHAR)''')
    con.execute("INSERT INTO rr VALUES ('06263401','2020-01-01','2026-08-29',100,'LOO_DAY_ADJUSTED')")
    entrants=pd.DataFrame([dict(target_date='2026-09-05',target_race_horse_key='0626410101',horse_id='00000001'),
        dict(target_date='2026-09-05',target_race_horse_key='0626410102',horse_id='00000002')])
    rules={'frozen_rules':[{'rule_id':'HV01','track':'hidden_value','condition':'finish>=4 AND performance_signal>=0'}]}
    a=build_features(entrants,'hp','rc','rr',rules,con)
    assert len(a)==2
    assert a.iloc[1].has_previous_rrdb_start==0 and pd.isna(a.iloc[1].performance_signal)
    assert pd.isna(a.iloc[1].front_pace_opposition_raw)
    assert a.iloc[1].current_hv_matched_rules==''
    assert math.isclose(a.iloc[0].front_pace_opposition_raw,.72)
    for date in ['2026-09-05','2026-09-27']:
        con.execute(f"INSERT INTO hp SELECT horse_id,horse_name,venue_code,horse_no,DATE '{date}','06269999','0626999901',1,80,surface_code,distance_m,field_size,declared_class_group,-999,100,1,pace_shape FROM hp WHERE race_key='06263401'")
    b=build_features(entrants,'hp','rc','rr',rules,con)
    pd.testing.assert_frame_equal(a,b)


def test_payout_hit_is_not_finish_top3():
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
    from analyze_rrdb_time_pace import metrics
    df=pd.DataFrame(dict(target_place_hit=[False],target_place_payout_yen=[0],target_win_hit=[False],
        target_win_payout_yen=[0],target_finish=[3],target_popularity=[3],target_win_odds=[4.0],target_date=['2026-09-05']))
    m=metrics(df)
    assert m['top3_rate_pct']==100 and m['place_hit_rate_pct']==0 and m['place_roi_pct']==0


if __name__=="__main__":
    test_future_and_target_same_date_cannot_change_features()
    test_payout_hit_is_not_finish_top3()
    print("PASS: temporal boundaries, all-entrant preservation, NULL exposure, payout hit semantics")
