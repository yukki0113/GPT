"""Focused synthetic and opt-in real-field negative tests for B5."""
import copy,json,os,unittest
from pathlib import Path
from unittest.mock import patch
from run_brdb_b5_local import read_field,individual_status,sample_cell,validate

class SyntheticTests(unittest.TestCase):
    def setUp(self):
        self.race={'race_key_raw':'05264b05','date_raw':'20261101','race_class_code':'A1','surface_code':'1','distance_raw':'2000','field_size':2}
        self.entries=[{'race_key_raw':'05264b05','horse_no':i,'blood_registration_no':f'2400000{i}'} for i in (1,2)]
        self.profile={'horse_id':'24000001','data_date':'20261101','birth_date':'20240101'}
    def read(self,entries=None,profiles=None,race=None):
        data={'BAC':[self.race if race is None else race],'KYI':self.entries if entries is None else entries,'UKC':[self.profile] if profiles is None else profiles}
        with patch('run_brdb_b5_local.sha',return_value='x'),patch('run_brdb_b5_local.Parser') as parser,patch('run_brdb_b5_local.iter_archive_records',side_effect=lambda p,k,a:[('fixture',v) for v in data[k]]):
            for kind in ('bac','kyi','ukc'):getattr(parser.return_value,kind).side_effect=lambda x:x
            return read_field(Path('PACI261101.zip'),'x',{'05264b05'})
    def test_missing_ukc_retains_whole_field(self):
        _,e,p,_,_=self.read();self.assertEqual(len(e),2);self.assertEqual(set(p),{'24000001'})
    def test_duplicate_or_wrong_count_rejected(self):
        for e in ([self.entries[0]]*2,self.entries[:1]):
            with self.assertRaises(ValueError):self.read(entries=e)
    def test_invalid_id_and_non_a1_rejected(self):
        with self.assertRaises(ValueError):self.read(entries=[{**self.entries[0],'blood_registration_no':'00000000'},self.entries[1]])
        with self.assertRaises(ValueError):self.read(race={**self.race,'race_class_code':'A3'})
    def test_future_conflicting_ukc_unavailable(self):
        for p in ([{**self.profile,'data_date':'20261102'}],[self.profile,{**self.profile,'birth_date':'20240102'}]):
            _,e,profiles,bad,_=self.read(profiles=p);self.assertEqual(len(e),2);self.assertEqual(profiles,{});self.assertIn('24000001',bad)
    def test_individual_status_not_race_class(self):
        h={'blood_registration_no':'24000001','previous':[]}
        self.assertEqual(individual_status(h,[],2,'2026-11-01')['status'],'NO_PRIOR_START_OBSERVED_HISTORY_INCOMPLETE')
        h['previous']=[{'result_key':'2400000120261018','race_key_raw':'04264205'}]
        self.assertEqual(individual_status(h,[],2,'2026-11-01')['status'],'PRIOR_HISTORY_UNRESOLVED')
        history=[{'race_key':'04264205','race_date':'2026-10-18','start_status':'STARTED_NORMAL'}]
        self.assertEqual(individual_status(h,history,2,'2026-11-01')['status'],'KNOWN_PRIOR_JRA_START')
        h['previous'][0]['result_key']='2400000120261101'
        self.assertEqual(individual_status(h,[],2,'2026-11-01')['prior_references'][0]['status'],'INVALID_OR_NONPRIOR_REFERENCE')
    def test_no_sample_distinct_from_unavailable(self):
        self.assertEqual(sample_cell(None,None,False)['starts'],None)
        self.assertEqual(sample_cell(None,None,False)['status'],'SOURCE_UNAVAILABLE')
        self.assertEqual(sample_cell(None,None,True)['starts'],0)
        self.assertEqual(sample_cell(None,None,True)['status'],'NO_SAMPLE')
        self.assertIsNone(sample_cell(None,None,True)['top3_rate'])

@unittest.skipUnless(os.environ.get('BRDB_B5_REVIEW'),'private real-review fixture not supplied')
class RealFieldNegativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.review=json.loads(Path(os.environ['BRDB_B5_REVIEW']).read_text())
    def reject(self,change):
        d=copy.deepcopy(self.review);change(d)
        with self.assertRaises(ValueError):validate(d)
    def test_unmodified(self):self.assertTrue(validate(self.review))
    def test_missing_and_duplicate_horse(self):
        self.reject(lambda d:d['horses'].pop())
        self.reject(lambda d:d['horses'].append(d['horses'][0]))
    def test_identity_and_scope_mismatch(self):
        self.reject(lambda d:d['horses'][0]['population_evidence'][0].update(key1='99999999'))
        self.reject(lambda d:d['horses'][0]['population_evidence'][0].update(dimension='WRONG'))
        self.reject(lambda d:d['horses'][0]['population_evidence'][0].update(evidence_id='WRONG'))
    def test_future_dates(self):
        self.reject(lambda d:d['horses'][0].update(profile_date='2026-11-02'))
        self.reject(lambda d:d['horses'][0]['population_evidence'][0].update(max_history_date='2026-01-01'))
        self.reject(lambda d:next(r for h in d['horses'] for r in h['relative_evidence']).update(max_history_date='2026-11-01'))
    def test_research_flags(self):
        self.reject(lambda d:d.update(prediction_safe=True))
        self.reject(lambda d:d.update(production_authorized=True))
    def test_invalid_zero_and_low_sample(self):
        self.reject(lambda d:next(r for h in d['horses'] for r in h['population_evidence'] if r['status']=='NO_SAMPLE').update(top3_rate=0.0))
        self.reject(lambda d:next(r for h in d['horses'] for r in h['population_evidence'] if r['status']=='LOW_SAMPLE').update(status='DESCRIPTIVE'))

if __name__=='__main__':unittest.main()
