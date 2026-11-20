"""Synthetic no-leak and identity tests for the KYI research sensitivity branch."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from jpdb_p3_kyi_proxy_sensitivity import EXTRA,make_baseline,predict_year,summarize_effect
import jpdb_p3_prerace_proxy_experiment as base

class TestP3ProxySensitivity(unittest.TestCase):
 def fixture(self):
  rows=[]
  for year in (2023,2024,2025):
   for race in (1,2):
    key=f'{year}{race:04d}'
    for horse in (1,2,3):
     row={col:float(horse+race) for col in base.NUM+EXTRA}
     row.update({'race_surface':'1','race_venue':'05','race_key_raw':key,
                 'horse_no':horse,'actual_jockey_code':str(horse).zfill(5),
                 'win':int(horse==race),'year':year})
     rows.append(row)
  return pd.DataFrame(rows)

 def test_forbidden_current_outcomes_and_rider_variables_not_in_predictors(self):
  self.assertEqual(set(EXTRA),{'idm','info_index','training_index','stable_index','base_win_odds'})
  forbidden={'jockey_index','jockey_code','actual_jockey_code','final_win_odds',
             'final_popularity','win','finish','trainer_code','blood_registration_no'}
  self.assertFalse(forbidden & set(base.FIELDS+EXTRA))

 def test_2024_train_is_2023_and_future_years_ignored(self):
  df=self.fixture()
  one,brier1,_=predict_year(df,EXTRA,2024)
  modified=df.copy()
  modified.loc[modified.year==2025,'win']=1-modified.loc[modified.year==2025,'win']
  two,brier2,_=predict_year(modified,EXTRA,2024)
  self.assertTrue(np.allclose(one.prob,two.prob))
  self.assertAlmostEqual(brier1,brier2)
  self.assertTrue((one.groupby('race_key_raw').prob.sum().sub(1).abs()<1e-10).all())

 def test_ablation_feature_dimensions_are_explicit(self):
  self.assertEqual(len(make_baseline([]).named_steps['pre'].transformers[0][2]),len(base.NUM))
  self.assertEqual(len(make_baseline(EXTRA).named_steps['pre'].transformers[0][2]),len(base.NUM)+5)

 def test_rider_stability_has_no_personal_ranking_output(self):
  frame=pd.DataFrame({'actual_jockey_code':['10001']*100,'race_surface':['1']*100,
                      'win':[1]*20+[0]*80,'prob':[.2]*100})
  stats=summarize_effect({2024:frame,2025:frame.copy(),2026:frame.copy()})
  self.assertEqual(stats[0]['n'],1)
  self.assertEqual(stats[1]['n'],1)
  self.assertNotIn('jockey_code',stats[0])

if __name__=='__main__':unittest.main()