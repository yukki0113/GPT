"""D4 source guard, non-scoring sidecar, no future-outcome or ID guessing."""
from __future__ import annotations
import copy
import json
import pathlib
import sys
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from brdb_d4_supplemental_adapter import build,D4ContractError

def _evidence(lane, name):
    return {'lane':lane, 'name':name, 'scope':'SURFACE_BAND',
            'dimensions':{'track_type':'1','distance_band':'MIDDLE'},
            'starts':40,'distinct_horses':20,'wins':5,'top3':10,
            'win_rate':0.125,'top3_rate':0.25,'wilson95_top3':[0.14,0.40],
            'baseline_starts':400,'baseline_top3':100,
            'baseline_top3_rate':0.25,
            'top3_delta_percentage_points':0.0,
            'sample_status':'DESCRIPTIVE',
            'interpretation':'OBSERVED_ONLY_NOT_CAUSAL_NOT_PREDICTION'}


class D4IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d3={
            'schema_version':'brdb-d3-condition-research-v0.1',
            'research_only':True,'prediction_safe':False,
            'historical_asof_status':'AS_OF_UNVERIFIED',
            'source_snapshot_generation':'analysis-v1_4-postrace-20261101-01',
            'selection_generation':'5279af0bd8226cde',
            'as_of_exclusive':'2026-11-02','period_start':'2016-01-01',
            'source_sha256':{
                'top50':'89d01e2c05af27a929c8398ef9e94660f5f1e442362d458383db6e6a9bd7bdc0',
                'manifest':'1'*64},
            'population':{'historical_starts':400,
                          'source_subjects':[{'name':'ディープインパクト'},
                                             {'name':'キングカメハメハ'}]},
            'counts':{'evidence_by_lane':{'SIRE':1,'BMS':1},
                      'pair_observed_cells':0},
            'evidence_rows':[_evidence('SIRE','ディープインパクト'),
                             _evidence('BMS','キングカメハメハ')],
            'pair_rows':[],
        }
        cls.temporal={
            'schema_version':'brdb-d3-temporal-diagnostic-v0.1',
            'research_only':True,'prediction_safe':False,
            'source_sha256':{'top50':cls.d3['source_sha256']['top50'],
                             'train_current':'1'*64,'test_current':'1'*64},
            'counts':{'SAME_SIGN_DESCRIPTIVE_ONLY':1},
            'rows':[{'lane':'SIRE','name':'ディープインパクト',
                     'scope':'SURFACE_BAND',
                     'dimensions':{'track_type':'1','distance_band':'MIDDLE'},
                     'stability_status':'SAME_SIGN_DESCRIPTIVE_ONLY',
                     'train_starts':25,'test_starts':15}],
        }
        cls.receipt={
            'status':'PASS','research_only':True,'prediction_safe':False,
            'as_of':'AS_OF_UNVERIFIED',
            'source_generation':cls.d3['source_snapshot_generation'],
            'selection_generation':cls.d3['selection_generation'],
            'condition_evidence_by_lane':cls.d3['counts']['evidence_by_lane'],
            'pair_observed_cells':0,'historical_starts':400,
            'temporal_counts':cls.temporal['counts'],
        }

    def setUp(self):
        self.race={'target_date':'2026-11-16','track_type':'1',
                   'distance':2000,'venue_code':'05','field_size':2,'research_only':True}
        self.entrants=[{'horse_id':'00000001','horse_no':2,
                        'sire_name':'ディープインパクト',
                        'broodmare_sire_name':'キングカメハメハ'},
                       {'horse_id':'00000002','horse_no':1,
                        'sire_name':'不存在の種牡馬','broodmare_sire_name':None}]

    def make(self):
        return build(self.d3,self.temporal,self.receipt,self.race,self.entrants)

    def test_deterministic_and_field_complete(self):
        left=self.make();right=self.make()
        self.assertEqual(left,right)
        self.assertEqual(len(left['horses']),2)
        self.assertEqual([x['horse_no'] for x in left['horses']],[1,2])

    def test_only_sourced_exact_match(self):
        x=self.make()
        self.assertEqual(x['horses'][0]['supplemental_insights'],[])
        self.assertTrue(len(x['horses'][1]['supplemental_insights'])>=1)

    def test_never_creates_score_or_factors(self):
        x=self.make()
        self.assertFalse(x['prediction_safe'])
        self.assertEqual(x['release_status'],'RESEARCH_SIDECAR_ONLY')
        for horse in x['horses']:
            self.assertEqual(horse['factors'],{'positive':[],'negative':[],'unknown':[]})
            self.assertIsNone(horse['summary'])
            self.assertEqual(horse['confidence'],'UNASSESSED')
            for item in horse['supplemental_insights']:
                self.assertIsNone(item['contribution_to_score'])
                self.assertEqual(item['interpretation_status'],
                                 'OBSERVATION_ONLY_AS_OF_UNVERIFIED')

    def test_reject_future_outcome_relative_to_race(self):
        self.race['target_date']='2024-01-01'
        with self.assertRaisesRegex(D4ContractError,'future outcomes'):
            self.make()

    def test_require_source_manifest_consistency(self):
        changed=copy.deepcopy(self.temporal)
        changed['source_sha256']['train_current']='0'*64
        with self.assertRaisesRegex(D4ContractError,'temporal source drift'):
            build(self.d3,changed,self.receipt,self.race,self.entrants)

    def test_reject_unreviewed_asof_promotion(self):
        changed=copy.deepcopy(self.d3); changed['prediction_safe']=True
        with self.assertRaisesRegex(D4ContractError,'D3 promoted'):
            build(changed,self.temporal,self.receipt,self.race,self.entrants)

    def test_reject_duplicate_entry_id(self):
        self.entrants[1]['horse_id']='00000001'
        with self.assertRaisesRegex(D4ContractError,'duplicate field'):
            self.make()

    def test_reject_duplicate_group(self):
        changed=copy.deepcopy(self.d3)
        changed['evidence_rows'].append(copy.deepcopy(changed['evidence_rows'][0]))
        with self.assertRaisesRegex(D4ContractError,'duplicate D3'):
            build(changed,self.temporal,self.receipt,self.race,self.entrants)

    def test_reject_unqualified_descriptive(self):
        changed=copy.deepcopy(self.d3)
        row=next(r for r in changed['evidence_rows'] if r['sample_status']=='DESCRIPTIVE')
        row['starts']=29
        with self.assertRaisesRegex(D4ContractError,'unqualified DESCRIPTIVE'):
            build(changed,self.temporal,self.receipt,self.race,self.entrants)

    def test_going_absent_skips_going_scopes(self):
        for row in self.make()['horses']:
            self.assertFalse(any('GOING' in x['scope_key'] for x in row['supplemental_insights']))

    def test_scope_never_crosses_surface(self):
        for row in self.make()['horses']:
            self.assertTrue(all(i['condition']['track_type']=='1' for i in row['supplemental_insights']))


if __name__=='__main__':unittest.main()