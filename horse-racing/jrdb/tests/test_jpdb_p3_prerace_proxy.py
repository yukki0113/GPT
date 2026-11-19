"""No-leak tests for JPDB P3 pre-entry proxy baseline. No licensed sources."""
import importlib.util
import pathlib
import unittest
import pandas as pd
from jpdb_p3_prerace_proxy_experiment import FIELDS, make_features, valid_cohort


def entry(date,key,horse,number,finish,*,surface='1',abnormal='0'):
 return dict(race_date=date,race_key_raw=key,horse_no=number,
             blood_registration_no=horse,actual_jockey_code='00001',
             abnormal_code=abnormal,finish=finish,field_size=2,
             race_surface=surface,race_venue='01',race_distance_m=1600,
             frame_no=1,carried_weight_tenths=550,rotation_interval=4)


class P3PreEntryTests(unittest.TestCase):
 def test_same_day_result_is_never_feature_even_later_race(self):
  df=pd.DataFrame([
   entry('2024-01-01','01240101','00000001',1,1),
   entry('2024-01-01','01240101','00000002',2,2),
   entry('2024-01-01','01240102','00000001',1,2),
   entry('2024-01-01','01240102','00000003',2,1),
   entry('2024-01-02','01240103','00000001',1,1),
   entry('2024-01-02','01240103','00000004',2,2),
  ])
  feat=make_features(df,expected_rows=6)
  a=feat.loc[(feat.race_date=='2024-01-01')&(feat.blood_registration_no=='00000001')]
  self.assertEqual(a['horse_starts_3y'].tolist(),[0,0])
  self.assertEqual(a['horse_starts_365'].tolist(),[0,0])
  nextday=feat.loc[(feat.race_date=='2024-01-02')&(feat.blood_registration_no=='00000001')].iloc[0]
  self.assertEqual(nextday.horse_starts_365,2)
  self.assertEqual(nextday.horse_wins_365,1)
  self.assertEqual(nextday.horse_days_since_last,1)

 def test_three_calendar_year_cutoff_excludes_older_history(self):
  df=pd.DataFrame([
   entry('2023-01-01','01230101','00000001',1,1),
   entry('2023-01-01','01230101','00000002',2,2),
   entry('2026-01-02','01260101','00000001',1,2),
   entry('2026-01-02','01260101','00000003',2,1),
  ])
  feat=make_features(df,expected_rows=4)
  target=feat.loc[(feat.race_date=='2026-01-02')&(feat.blood_registration_no=='00000001')].iloc[0]
  self.assertEqual(target.horse_starts_3y,0)
  self.assertTrue(pd.isna(target.horse_days_since_last))

 def test_ambiguous_race_excluded_entirely(self):
  df=pd.DataFrame([
   entry('2025-01-01','01250101','00000001',1,1),
   entry('2025-01-01','01250101','00000002',2,2),
   entry('2025-01-02','01250102','00000003',1,1),
   entry('2025-01-02','01250102','00000004',2,2,abnormal='5'),
  ])
  feat=make_features(df,expected_rows=4)
  cohort,audit=valid_cohort(feat)
  self.assertEqual(audit['eligible_races'],1)
  self.assertEqual(cohort.race_key_raw.nunique(),1)

 def test_all_features_whitelisted_and_no_jockey_or_market(self):
  for banned in ('jockey_code','actual_jockey_code','final_win_odds','final_popularity',
                 'finish','abnormal_code','horse_name','blood_registration_no'):
   self.assertNotIn(banned,FIELDS)
  self.assertEqual(len(FIELDS),len(set(FIELDS)))

 def test_fail_closed_duplicate_runners(self):
  row=entry('2025-01-01','01250101','00000001',1,1)
  with self.assertRaisesRegex(ValueError,'runner duplicate'):
   make_features(pd.DataFrame([row,row]),expected_rows=2)


if __name__=='__main__':unittest.main()