"""License-free synthetic regressions for the R3 research composition."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import racenote_r3_independent_evidence as m

D='2026-11-15'; KEY='05265401'; SHA='a'*64

def fixture():
    h={'horse_no':1,'horse_id':'00000001','scheduled_jockey_code':'00001','entry_cancel_flag_raw':'0'}
    source={'target_paci_sha256':SHA,'strict_asof_certified':False}
    h1={**h,'windows':{}};h2={**h,'axes':[]}
    axis={'condition':{},'dimension':'ALL_FLAT','redundancy_group_id':'JOCKEY_BASE','window_summary':{'same_condition_peers':{'status':'CONTEXTUAL','direction':'POSITIVE'}},'windows':{}}
    for w in m.WINDOWS:
        eid=f'{KEY}:01:{w}:ALL_FLAT';start='2026-01-01'
        metric={'actual_starts_candidate':40,'wins':4,'top2':8,'top3':12,'start_basis_win_rate_candidate':0.1,'start_basis_top3_rate_candidate':0.3,'unresolved_count':0,'first_observed':'2026-01-02','last_observed':'2026-10-01'}
        h1['windows'][w]={'period_from_inclusive':start,'period_to_exclusive':D,'evidence':[{'dimension':'ALL_FLAT','evidence_id':eid,'condition':{},'redundancy_group_id':'JOCKEY_BASE','metrics':metric,'status':'DESCRIPTIVE_ONLY','source_status':'OBSERVED'}]}
        group={'resolved_starts':40,'unresolved':0,'wins':4,'top3':12,'top3_rate_resolved':0.3}
        axis['windows'][w]={'r1_evidence_id':eid,'period_from_inclusive':start,'period_to_exclusive':D,'groups':{g:dict(group) for g in m.GROUPS},'comparisons':{'same_condition_peers':{'status':'CONTEXTUAL','direction':'POSITIVE','top3_delta_pp':6,'wins_delta_pp':1,'top3_unresolved_bounds_pp':[6,6],'wins_unresolved_bounds_pp':[1,1]}},'excluded_unknown_condition_entries_in_window':0,'excluded_invalid_jockey_entries_in_window':0}
    h2['axes']=[axis];race={'race_key_raw':KEY,'entry_count':1,'is_newcomer_race':False}
    a={'schema_version':'jpdb-r1-jockey-profile-v0.1-candidate','prediction_safe':False,'target_date':D,'source':source,'races':[{**race,'surface_code':'1','distance_m':1600,'venue_code':'05','race_class_code':'A3','horses':[h1]}]}
    b={'schema_version':'jpdb-r2-condition-context-v0.1-candidate','prediction_safe':False,'target_date':D,'source':copy.deepcopy(source),'policy':{'suggestive_allowed':False},'races':[{**race,'horses':[h2]}]}
    roster=({KEY:{'surface_code':'1','distance_raw':1600,'venue_code':'05','race_class_code':'A3','field_size':1,'course_code':'1'}},{KEY:{1:h}})
    return a,b,roster

def compose(a,b,roster):
    with patch.object(m,'read_target_paci',return_value=roster):return m.build(a,b,Path('synthetic'),SHA,source_assets={})

def blood():
    ident={'horse_no':1,'horse_id':'00000001'}
    o={'unique_horses':10,'starts':40,'wins':4,'top3':12,'win_rate':.1,'top3_rate':.3,'top3_wilson95':[.2,.4],'baseline_starts':100,'baseline_top3_rate':.25,'top3_delta_pp':5}
    e={'component':'sire','evidence_id':'SIRE_ALL_VENUES_BAND','scope_key':'ALL_VENUES_BAND','condition':{'surface_code':'1','distance_band':'MILE'},'evidence_kind':'OBSERVED_CONDITIONAL_RESULT','as_of_exclusive':D,'observations':o,'sample_status':'DESCRIPTIVE','overlap_group':'native'}
    pair={**e,'component':'pairing','evidence_id':'PAIR_SYNTHETIC'}
    h={**ident,'confidence':'UNASSESSED','summary':None,'factors':{'positive':[],'negative':[],'unknown':[]},'components':{'sire':{'availability':'AVAILABLE','evidence_ids':[e['evidence_id']]},'broodmare_sire':{'availability':'SOURCE_UNAVAILABLE','evidence_ids':[]},'pairing':{'availability':'AS_OF_UNVERIFIED','evidence_ids':[pair['evidence_id']]},'relatives':{'availability':'SOURCE_UNAVAILABLE','evidence_ids':[]}},'evidence':[e,pair],'supplemental_insights':[]}
    raw={**ident,'sire_evidence':{'scopes':{'ALL_VENUES_BAND':{**o,'horses':10,'status':'DESCRIPTIVE'}}}}
    return h,{**ident,'relatives':[]},raw

class TestR3(unittest.TestCase):
    def test_complete_and_missing_blood(self):
        a,b,roster=fixture();d=compose(a,b,roster);h=d['races'][0]['horses'][0]
        self.assertEqual(len(h['evidence']),3);self.assertEqual(h['brdb_status'],'SOURCE_UNAVAILABLE');self.assertTrue(all(v=='SOURCE_UNAVAILABLE' for v in h['brdb_components'].values()));self.assertFalse(d['prediction_safe'])
        self.assertEqual(m.encode(d),m.encode(compose(a,b,roster)))
    def test_roster_jockey_and_missing_identity(self):
        a,b,r=fixture();a['races'][0]['horses'][0]['scheduled_jockey_code']='00002'
        with self.assertRaisesRegex(ValueError,'scheduled jockey'):compose(a,b,r)
        a,b,r=fixture();b['races'][0]['horses']=[]
        with self.assertRaisesRegex(ValueError,'full-field'):compose(a,b,r)
    def test_duplicate_horse(self):
        a,b,r=fixture();a['races'][0]['horses']*=2
        with self.assertRaisesRegex(ValueError,'duplicate'):compose(a,b,r)
    def test_cutoff_and_future_observation(self):
        a,b,r=fixture();b['target_date']='2026-11-16'
        with self.assertRaisesRegex(ValueError,'source/cutoff'):compose(a,b,r)
        a,b,r=fixture();a['races'][0]['horses'][0]['windows']['ROLLING_3Y']['evidence'][0]['metrics']['last_observed']=D
        with self.assertRaisesRegex(ValueError,'future observation'):compose(a,b,r)
    def test_R1_R2_count_and_condition_drift(self):
        a,b,r=fixture();b['races'][0]['horses'][0]['axes'][0]['windows']['ROLLING_3Y']['groups']['own_match']['wins']=5
        with self.assertRaisesRegex(ValueError,'count mismatch'):compose(a,b,r)
        a,b,r=fixture();b['races'][0]['horses'][0]['axes'][0]['condition']={'surface_code':'2'}
        with self.assertRaisesRegex(ValueError,'evidence binding'):compose(a,b,r)
    def test_preview_conflict_and_reference(self):
        a,b,r=fixture();b['races'][0]['horses'][0]['axes'][0]['window_summary']['same_condition_peers']={'status':'CONFLICTED','direction':'UNCLASSIFIED'}
        d=compose(a,b,r);sha=hashlib.sha256(m.encode(d)).hexdigest();p=m.reader_preview(d,KEY,sha);h=p['horses'][0];row=dict(zip(p['columns']['jockey'],h['jockey'][0]))
        self.assertEqual(row['across_windows_status'],'CONFLICTED');self.assertEqual(row['across_windows_direction'],'UNCLASSIFIED');self.assertEqual(h['omitted_detail_count'],2);self.assertEqual(p['detail_sha256'],sha)
        with self.assertRaisesRegex(ValueError,'SHA'):m.reader_preview(d,KEY,'b'*64)
    def test_no_market_passthrough(self):
        a,b,r=fixture();a['races'][0]['horses'][0]['odds']=999;b['races'][0]['horses'][0]['finish']=1
        out=compose(a,b,r);self.assertNotIn('"odds"',m.encode(out).decode());self.assertNotIn('"finish"',m.encode(out).decode())
        with self.assertRaisesRegex(ValueError,'condition field'):m.condition({'odds':2})
    def test_unverified_blood_and_raw_count(self):
        h,rel,raw=blood();items,restricted,states=m.br_items(h,rel,raw,KEY,D,'1','2016-11-15')
        self.assertEqual(len(items),1);self.assertEqual(len(restricted),1);self.assertNotIn('observation',restricted[0]);self.assertEqual(states['pairing'],'AS_OF_UNVERIFIED')
        raw['sire_evidence']['scopes']['ALL_VENUES_BAND']['wins']=5
        with self.assertRaisesRegex(ValueError,'observation drift'):m.br_items(h,rel,raw,KEY,D,'1','2016-11-15')
    def test_unverified_promotion(self):
        h,rel,raw=blood();h['components']['pairing']['availability']='AVAILABLE'
        with self.assertRaisesRegex(ValueError,'promotion'):m.br_items(h,rel,raw,KEY,D,'1','2016-11-15')
    def test_zero_and_duplicate_json(self):
        with self.assertRaisesRegex(ValueError,'zero starts'):m.obs(0,0,0,top3_rate=0,denominator='BRDB_ACTUAL_STARTS')
        self.assertIsNone(m.obs(0,0,0,denominator='BRDB_ACTUAL_STARTS')['top3_rate'])
        with tempfile.TemporaryDirectory() as t:
            f=Path(t)/'a.json';f.write_text('{"x":1,"x":2}')
            with self.assertRaisesRegex(ValueError,'duplicate JSON'):m.load(f,m.digest(f))
            with self.assertRaisesRegex(ValueError,'SHA'):m.load(f,SHA)

if __name__=='__main__':unittest.main()
