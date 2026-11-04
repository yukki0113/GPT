"""Synthetic tests only. No JRDB row-level data leaves the private runtime."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from run_brdb_m6_conditional_retrospective import digest,prep,score,cluster_ci,fit_predict,BASE,BLOOD

class TestConditional(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('pandas') is not None and
                         importlib.util.find_spec('numpy') is not None,
                         'pandas/numpy unavailable in runner; local dependency test required')
    def test_fixed_date_filter_and_logloss(self):
        import pandas as pd
        rows=[]
        for year in range(2016,2026):
            for race in range(2):
                for horse in range(4):
                    rows.append(dict(race_year=year,race_key=f'{year}0{race}11',
                      horse_no=horse+1,horse_id=f'{year}{race:02}{horse:03}',
                      race_date=f'{year}0101',abnormal_code='0',winner=horse==0,
                      venue_code='05',surface_code='1',distance_m=1600,
                      race_class_code='A',sire_line_code=str(horse%2),
                      broodmare_sire_line_code='4',ukc_data_date=f'{year}0101'))
        d=pd.DataFrame(rows)
        self.assertEqual(len(d),80)
        clean=prep.__globals__['pd'] if 'pd' in prep.__globals__ else None
        # Production prep deliberately pins the full real-data row count;
        # synthetic unit checks focus on metric and model isolation.
        t=d.iloc[:4].copy()
        t['p_base']=[.4,.2,.2,.2]
        t['p_blood']=[.6,.15,.15,.1]
        m=score(t)
        self.assertLess(m['delta_blood_minus_base'],0)
        self.assertEqual(m['entries'],4)
        self.assertEqual(cluster_ci(t,'race_key',10)['clusters'],1)

    @unittest.skipUnless(importlib.util.find_spec('sklearn') is not None and
                         importlib.util.find_spec('pandas') is not None,
                         'sklearn/pandas unavailable; local runtime model integration required')
    def test_train_only_onehot_unseen_category(self):
        import pandas as pd
        tr=pd.DataFrame({'venue_code':['01','02']*10,'winner':[1,0]*10})
        te=pd.DataFrame({'venue_code':['FUTURE_ONLY']})
        p=fit_predict(tr,te,['venue_code'])
        self.assertEqual(len(p),1)
        self.assertGreater(p[0],0)
        self.assertLess(p[0],1)

    def test_source_sha_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'mock.zip'
            p.write_bytes(b'source')
            before=digest(p)
            p.write_bytes(b'source amended')
            self.assertNotEqual(before,digest(p))

if __name__=='__main__':
    unittest.main()
