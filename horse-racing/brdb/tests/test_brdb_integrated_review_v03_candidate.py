"""v0.3 candidate: attach D4 supplemental research without changing v0.2 semantics."""
from __future__ import annotations
import copy, json, pathlib, sys, unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from brdb_integrated_review_v03_candidate import merge, IntegratedV03Error

try:
    import jsonschema
except ImportError:
    jsonschema=None

BASE=json.loads((ROOT/'tests/fixtures/brdb_integrated_review_v0_2_candidate_example.json').read_text(encoding='utf-8'))
SCHEMA=json.loads((ROOT/'schema/brdb_integrated_review_v0_3_candidate.schema.json').read_text(encoding='utf-8'))
EXAMPLE_V03=json.loads((ROOT/'tests/fixtures/brdb_integrated_review_v0_3_candidate_example.json').read_text(encoding='utf-8'))


def sidecar():
    return {
      'schema_version':'brdb-d4-supplemental-research-v0.1',
      'base_review_contract':'brdb-review-v0.1 (FROZEN, NOT MODIFIED)',
      'integrated_review_contract':'brdb-integrated-blood-review-v0.2-candidate (NOT MODIFIED)',
      'research_only':True,'prediction_safe':False,'release_status':'RESEARCH_SIDECAR_ONLY',
      'historical_asof_status':'AS_OF_UNVERIFIED','no_forecast_or_score':True,
      'race':{'target_date':'2026-11-01','venue_code':'05','track_type':'1','distance':2000,'field_size':1,'track_condition_code':None},
      'source_generations':{'jrdb_analysis':'SYNTHETIC_GEN','top50_selection':'SYNTHETIC_TOP50'},
      'source_time_guard':'SYNTHETIC_AS_OF_UNVERIFIED',
      'aggregate_coverage':{'field_size':1,'reviewed_horses':1,'research_evidence_items':1},
      'provenance':{
        'd3_full_sha256':'1'*64,'d3_temporal_sha256':'2'*64,'d3_receipt_sha256':'3'*64,'research_field_sha256':'4'*64},
      'horses':[{
        'horse_id':'00000001','horse_no':1,'availability':'AS_OF_UNVERIFIED',
        'supplemental_insights':[{
          'source_lane':'SIRE','source_name_exact':'架空父','scope_key':'SURFACE_BAND',
          'condition':{'track_type':'1','distance_band':'MIDDLE'},
          'observations':{'starts':5,'distinct_horses':4,'wins':1,'top3':2,'win_rate':0.2,'top3_rate':0.4,
                          'wilson95_top3':[0.1176,0.7693],'baseline_starts':1900,'baseline_top3':437,
                          'baseline_top3_rate':0.23,'top3_delta_percentage_points':17.0,'sample_status':'LOW_SAMPLE'},
          'temporal_diagnostic':None,'interpretation_status':'OBSERVATION_ONLY_AS_OF_UNVERIFIED',
          'contribution_to_score':None}],
        'factors':{'positive':[],'negative':[],'unknown':[]},'summary':None,'confidence':'UNASSESSED'}]
    }


class TestIntegratedV03(unittest.TestCase):
    def validate_schema(self,payload):
        if jsonschema is not None:
            jsonschema.Draft202012Validator.check_schema(SCHEMA)
            jsonschema.Draft202012Validator(SCHEMA,format_checker=jsonschema.FormatChecker()).validate(payload)

    def test_fixture_is_valid(self):
        self.validate_schema(EXAMPLE_V03)

    def test_merge_matches_fixed_fixture(self):
        self.assertEqual(merge(copy.deepcopy(BASE),sidecar()), EXAMPLE_V03)

    def test_valid_merge_and_schema(self):
        out=merge(copy.deepcopy(BASE),sidecar())
        self.assertEqual(out['contract_version'],'brdb-integrated-blood-review-v0.3-candidate')
        self.assertEqual(out['horses'][0]['supplemental_status'],'AS_OF_UNVERIFIED')
        self.assertEqual(len(out['horses'][0]['supplemental_insights']),1)
        self.assertTrue(out['supplemental_research']['no_forecast_or_score'])
        self.validate_schema(out)

    def test_base_is_not_mutated(self):
        base=copy.deepcopy(BASE); before=copy.deepcopy(base); merge(base,sidecar())
        self.assertEqual(base,before)

    def test_full_field_identity_mismatch_fails(self):
        s=sidecar(); s['horses'][0]['horse_id']='99999999'
        with self.assertRaisesRegex(IntegratedV03Error,'identity mismatch'): merge(copy.deepcopy(BASE),s)

    def test_race_mismatch_fails(self):
        s=sidecar(); s['race']['distance']=1800
        with self.assertRaisesRegex(IntegratedV03Error,'race context mismatch'): merge(copy.deepcopy(BASE),s)

    def test_prediction_promotion_fails(self):
        s=sidecar(); s['prediction_safe']=True
        with self.assertRaisesRegex(IntegratedV03Error,'prediction-safe'): merge(copy.deepcopy(BASE),s)

    def test_factor_injection_fails(self):
        s=sidecar(); s['horses'][0]['factors']['positive']=[{'x':1}]
        with self.assertRaisesRegex(IntegratedV03Error,'factors'): merge(copy.deepcopy(BASE),s)

    def test_score_contribution_fails(self):
        s=sidecar(); s['horses'][0]['supplemental_insights'][0]['contribution_to_score']=1
        with self.assertRaisesRegex(IntegratedV03Error,'score contribution'): merge(copy.deepcopy(BASE),s)

    def test_zero_supplemental_evidence_is_valid(self):
        s=sidecar(); s['horses'][0]['supplemental_insights']=[]; s['aggregate_coverage']['research_evidence_items']=0
        out=merge(copy.deepcopy(BASE),s)
        self.assertEqual(out['horses'][0]['supplemental_insights'],[])
        self.validate_schema(out)

    def test_base_factors_summary_confidence_preserved(self):
        base=copy.deepcopy(BASE)
        before=(copy.deepcopy(base['horses'][0]['factors']),base['horses'][0]['summary'],base['horses'][0]['confidence'])
        out=merge(base,sidecar())
        after=(out['horses'][0]['factors'],out['horses'][0]['summary'],out['horses'][0]['confidence'])
        self.assertEqual(before,after)

    def test_d4_asof_promotion_fails(self):
        s=sidecar(); s['historical_asof_status']='VERIFIED'
        with self.assertRaisesRegex(IntegratedV03Error,'as-of promotion'): merge(copy.deepcopy(BASE),s)

if __name__=='__main__':
    unittest.main()
