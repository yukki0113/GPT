"""Synthetic pre-cutoff contract and fail-closed regression tests."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator
import racenote_r3_brdb_base_only as m

KEY='05263305'

def prior():
    return {'contract_version':m.r3.VERSION,'research_only':True,'prediction_safe':False,
            'production_authorized':False,'target_date':'2026-06-13','as_of_exclusive':'2026-06-13',
            'races':[{'race_key_raw':KEY,'is_newcomer_race':True,'race_class_code':'A1',
                      'coverage_status':'JPDB_ONLY_BRDB_UNAVAILABLE'}]}

class TestBaseOnly(unittest.TestCase):
    def test_valid_prior(self):
        self.assertEqual(m.target_race(prior(),KEY)['race_key_raw'],KEY)
    def test_cutoff(self):
        for d in ('2026-11-02','2026-11-15'):
            a=prior();a['target_date']=a['as_of_exclusive']=d
            with self.assertRaisesRegex(ValueError,'cutoff'):m.target_race(a,KEY)
    def test_wrong_cohort_or_already_joined(self):
        for k,v in [('race_class_code','A3'),('is_newcomer_race',False),('coverage_status','DUAL_SOURCE_RESEARCH')]:
            a=prior();a['races'][0][k]=v
            with self.assertRaisesRegex(ValueError,'unjoined A1'):m.target_race(a,KEY)
    def test_unsafe_prior(self):
        for k,v in [('prediction_safe',True),('production_authorized',True),('research_only',False),('as_of_exclusive','2026-06-14')]:
            a=prior();a[k]=v
            with self.assertRaisesRegex(ValueError,'unsafe prior'):m.target_race(a,KEY)
    def test_manifest_pin_and_required_assets(self):
        with tempfile.TemporaryDirectory() as t:
            f=Path(t)/'m.json';f.write_text(json.dumps({'schema_version':'racenote-r3-base-only-input-v1','assets':{}}))
            with self.assertRaisesRegex(ValueError,'SHA'):m.run(f,'0'*64,Path(t)/'out')
            with self.assertRaisesRegex(ValueError,'invalid input assets'):m.run(f,m.r3.digest(f),Path(t)/'out')
    def test_distinct_schema_versions(self):
        for name,version in [('racenote_independent_evidence_base_only_v0_1_candidate.schema.json',m.VERSION),('racenote_independent_evidence_base_only_preview_v0_1_candidate.schema.json',m.PREVIEW_VERSION)]:
            s=json.loads((m.SCHEMA/name).read_text());Draft202012Validator.check_schema(s)
            self.assertEqual(s['properties']['contract_version']['const'],version)
            self.assertFalse(s['properties']['prediction_safe']['const']);self.assertFalse(s['properties']['production_authorized']['const'])
    def test_explicit_unavailable_supplement(self):
        s=json.loads((m.SCHEMA/'racenote_independent_evidence_base_only_v0_1_candidate.schema.json').read_text())
        self.assertIn(m.D4_STATUS,json.dumps(s));self.assertIn(m.POPULATION,json.dumps(s))

if __name__=='__main__':unittest.main()
