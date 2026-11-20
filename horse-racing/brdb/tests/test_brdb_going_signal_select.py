from __future__ import annotations
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import brdb_going_signal_select as mod


def obs(g_n,g_t,w_n,w_t):
    d=round(100*(w_t/w_n-g_t/g_n),2)
    return {'comparison_status':'OBSERVED','difference_top3_pp':d,
            'good':{'starts':g_n,'top3':g_t},'non_good':{'starts':w_n,'top3':w_t}}

def payload(scopes):
    return {'contract_version':'brdb-going-condition-comparison-v0.4-candidate',
            'release_status':'RESEARCH_ONLY','historical_profile_asof':'AS_OF_UNVERIFIED',
            'denominator':'NORMAL_FINISHERS_ONLY','as_of_exclusive':'2026-11-15',
            'race':{'race_key':'x'},'policy':{'prediction_safe':False,'production_authorized':False},
            'horses':[{'horse_id':'12345678','horse_no':1,'scopes':scopes}]}

class T(unittest.TestCase):
    def test_strong_positive(self):
        x=mod.classify_observation('ALL_VENUES_DISTANCE',obs(100,20,60,30))
        self.assertEqual(x['tier'],'STRONG_DESCRIPTIVE');self.assertTrue(x['wilson_intervals_separated'])
        self.assertEqual(x['direction'],'NON_GOOD_HIGHER')
    def test_notable_without_separation(self):
        x=mod.classify_observation('ALL_VENUES_DISTANCE',obs(100,25,30,10))
        self.assertEqual(x['tier'],'NOTABLE_DESCRIPTIVE');self.assertFalse(x['suitability_claim'])
    def test_low_sample_signal_preserved(self):
        x=mod.classify_observation('VENUE_DISTANCE',obs(40,8,5,3))
        self.assertEqual(x['tier'],'LOW_SAMPLE_SIGNAL');self.assertTrue(x['selectable'])
    def test_tiny_sample_not_selected(self):
        x=mod.classify_observation('VENUE_DISTANCE',obs(40,8,2,2))
        self.assertEqual(x['tier'],'ROUTINE_OBSERVATION');self.assertFalse(x['selectable'])
    def test_primary_prefers_closer_scope_not_larger_effect(self):
        p=payload([
          {'scope_key':'VENUE_DISTANCE','scope_status':'RESEARCH_OBSERVED','observation':obs(40,8,20,8)},
          {'scope_key':'ALL_VENUES_DISTANCE','scope_status':'RESEARCH_OBSERVED','observation':obs(100,20,60,30)}])
        x=mod.select(p);self.assertEqual(x['horses'][0]['primary']['scope_key'],'VENUE_DISTANCE')
    def test_mixed_direction_is_flagged(self):
        p=payload([
          {'scope_key':'VENUE_DISTANCE','scope_status':'RESEARCH_OBSERVED','observation':obs(40,8,20,8)},
          {'scope_key':'ALL_VENUES_DISTANCE','scope_status':'RESEARCH_OBSERVED','observation':obs(100,40,50,10)}])
        x=mod.select(p);self.assertEqual(x['horses'][0]['scope_direction_consistency'],'MIXED')
    def test_nested_not_independent(self):
        p=payload([{'scope_key':'ALL_VENUES_DISTANCE','scope_status':'RESEARCH_OBSERVED','observation':obs(100,20,60,30)}])
        x=mod.select(p);self.assertFalse(x['horses'][0]['nested_scopes_independent'])
    def test_prediction_policy_rejected(self):
        p=payload([]);p['policy']['prediction_safe']=True
        with self.assertRaises(ValueError):mod.select(p)
    def test_delta_tamper_rejected(self):
        o=obs(100,20,60,30);o['difference_top3_pp']=99
        with self.assertRaises(ValueError):mod.classify_observation('ALL_VENUES_DISTANCE',o)

if __name__=='__main__': unittest.main()
