"""Synthetic regressions for P3 observed previous-rider vs same-rider cohort."""
import unittest
import pandas as pd
from jpdb_p3_same_horse_switch_research import consecutive_pairs, weighted_match, classify


def row(day,race,horse,jockey,finish,surface='1',distance=1600,abnormal='0'):
    return dict(race_date=day,race_key_raw=race,horse_no=1,
      blood_registration_no=horse,actual_jockey_code=jockey,
      race_surface=surface,race_distance_m=distance,abnormal_code=abnormal,
      finish=finish,field_size=2)

class TestSwitch(unittest.TestCase):
    def test_consecutive_actual_riders_and_outcome(self):
        facts=pd.DataFrame([
          row('2023-12-01','01010101','A','00001',1),
          row('2023-12-01','01010101','B','00002',2),
          row('2024-01-10','01020101','A','00003',2),
          row('2024-01-10','01020101','B','00002',1),
        ])
        # Horse number must reflect two different runners within each race.
        facts.loc[facts.blood_registration_no=='B','horse_no']=2
        p,cohort=consecutive_pairs(facts)
        self.assertEqual(cohort['eligible_races'],2)
        self.assertEqual(len(p),2)
        self.assertEqual(p.sort_values('blood_registration_no').switched.tolist(),[1,0])
        self.assertEqual(p.sort_values('blood_registration_no').prior_top3.tolist(),[1,1])
        self.assertEqual(p.sort_values('blood_registration_no').horse_starts_365.tolist(),[1,1])

    def test_no_future_same_day_or_ambiguous_prior(self):
        f=pd.DataFrame([
          row('2024-01-01','01020101','A','00001',1),
          row('2024-01-01','01020101','B','00002',2),
          row('2024-01-01','01020102','A','00003',2),
          row('2024-01-01','01020102','C','00004',1),
          row('2024-01-02','01020103','A','00004',1),
          row('2024-01-02','01020103','D','00005',2),
        ])
        f.loc[f.blood_registration_no.isin(['B','C','D']),'horse_no']=2
        p,_=consecutive_pairs(f)
        self.assertEqual(len(p),1)
        self.assertEqual(p.iloc[0].race_date,'2024-01-02')
        self.assertEqual(p.iloc[0].days_since_prior,1)

    def test_reject_abnormal_previous_whole_race(self):
        f=pd.DataFrame([
          row('2023-12-01','01010101','A','00001',1,abnormal='5'),
          row('2023-12-01','01010101','B','00002',2),
          row('2024-01-10','01020101','A','00003',2),
          row('2024-01-10','01020101','B','00002',1),
        ])
        f.loc[f.blood_registration_no=='B','horse_no']=2
        p,_=consecutive_pairs(f)
        self.assertEqual(len(p),0)

    def test_restrict_rider_switch_180_days_surface_and_distance(self):
        f=pd.DataFrame([
          row('2023-01-01','01010101','A','00001',1),
          row('2023-01-01','01010101','B','00002',2),
          row('2024-01-01','01020101','A','00003',2),
          row('2024-01-01','01020101','B','00002',1),
        ])
        f.loc[f.blood_registration_no=='B','horse_no']=2
        p,_=consecutive_pairs(f)
        self.assertEqual(len(p),0)

    def test_matching_no_overlap_fails_closed(self):
        f=pd.DataFrame([
          dict(year='2025',race_surface='1',distance_band='MILE',prior_top3=1,history_band='1-2',gap_band='31-90',switched=1,win=1,top3=1),
          dict(year='2025',race_surface='1',distance_band='MILE',prior_top3=0,history_band='1-2',gap_band='31-90',switched=0,win=0,top3=0)
        ])
        with self.assertRaises(ValueError):weighted_match(f,min_per_arm=1)

    def test_matching_weighted_contrast(self):
        f=pd.DataFrame([
          dict(year='2025',race_surface='1',distance_band='MILE',prior_top3=1,history_band='1-2',gap_band='31-90',switched=arm,win=arm,top3=arm)
          for arm in [1,0,1,0]
        ])
        result=weighted_match(f,min_per_arm=2)
        self.assertEqual(result['strata_with_overlap'],1)
        self.assertEqual(result['descriptive_win_difference_pp'],100.0)
        self.assertFalse(result['balance_not_certified'] is False)

if __name__=='__main__':unittest.main()