"""Synthetic C2 graph checks: no private card text in the public repository."""
import copy
import hashlib
import unittest

from test_m5c_c0 import fixture
from engine_m5.combo_graph import validate_combo_routes

CARD = "konami:111"
OTHER = "konami:222"
BODY = "①：デッキから架空モンスター１体を特殊召喚する。"


def state(sid, hand=0, field=0, deck=0, grave=0, used=(), locks=None, normal=False):
    return {"state_id":sid,
            "locations_json":{"HAND":{CARD:hand},"FIELD":{CARD:field},"DECK":{CARD:deck},
                              "GRAVE":{CARD:grave}},
            "resources_json":{"once_per_turn_used":list(used)},
            "locks_json":locks or {}, "assumptions_json":{},
            "normal_summon_used":normal,"turn_phase":"MAIN1"}


def sample():
    x=fixture()
    x["resource_states"]=[
        state("start",deck=1),
        state("end",field=1,used=("konami:111#1",)),
    ]
    x["combo_routes"]=[{"route_id":"r1","profile_id":"p1","source_id":"s1",
       "route_version":1,"start_condition_id":"start","end_state_id":"end",
       "verification":"TEXT_CHECKED"}]
    x["combo_nodes"]=[{"node_id":"n1","route_id":"r1","sequence":1,
       "action_type":"EFFECT","actor_card_id":CARD,"effect_id":"konami:111#1",
       "effect_ref":"①","effect_anchor":"デッキから架空モンスター１体",
       "effect_text_sha256":hashlib.sha256(BODY.encode()).hexdigest(),
       "before_state_ref":"start","after_state_ref":"end","evidence_id":"c1",
       "transfers":[{"card_id":CARD,"from":"DECK","to":"FIELD","quantity":1}],
       "locks_added":{}}]
    return x


class ComboGraphTests(unittest.TestCase):
    def audit(self, bundle, props=None):
        return validate_combo_routes(bundle,{CARD:BODY},props)

    def test_single_route_text_anchor_and_transfer(self):
        x=sample()
        result=self.audit(x)
        self.assertEqual(1,result["route_count"])
        self.assertFalse(result["game_rules_verified"])
        self.assertFalse(result["independent_gameplay_tested"])

    def test_effect_number_and_actor_mismatch_rejected(self):
        x=sample()
        x["combo_nodes"][0]["effect_id"]="konami:111#2"
        with self.assertRaises(ValueError):
            self.audit(x)
        x=sample()
        x["combo_nodes"][0]["effect_id"]="konami:222#1"
        with self.assertRaises(ValueError):
            self.audit(x)

    def test_missing_text_and_wrong_hash_rejected(self):
        x=sample()
        with self.assertRaises(ValueError):
            validate_combo_routes(x,{CARD:"altered text"})
        x["combo_nodes"][0]["effect_anchor"]="fabricated"
        with self.assertRaises(ValueError):
            self.audit(x)

    def test_unexplained_resource_creation_rejected(self):
        x=sample();x["combo_nodes"][0]["transfers"]=[]
        with self.assertRaises(ValueError):
            self.audit(x)

    def test_once_per_turn_missing_rejected(self):
        x=sample()
        x["resource_states"][1]["resources_json"]["once_per_turn_used"]=[]
        with self.assertRaises(ValueError):
            self.audit(x)

    def test_lock_cannot_silently_disappear(self):
        x=sample()
        x["resource_states"][0]["locks_json"]={"EXTRA_SUMMON_ONLY":"FIEND"}
        with self.assertRaises(ValueError):
            self.audit(x)

    def test_random_branch_two_explicit_outcomes(self):
        x=sample()
        x["resource_states"].append(state("other_end",field=1,used=("konami:111#1",)))
        x["combo_routes"][0]["alternative_end_state_ids"]=["other_end"]
        x["combo_nodes"].append({"node_id":"n2","route_id":"r1","sequence":2,
          "action_type":"RANDOM_RESOLUTION","actor_card_id":None,
          "before_state_ref":"end","after_state_ref":"end",
          "transfers":[],"locks_added":{}})
        x["combo_nodes"].append({"node_id":"n3","route_id":"r1","sequence":3,
          "action_type":"RANDOM_RESOLUTION","actor_card_id":None,
          "before_state_ref":"end","after_state_ref":"other_end",
          "transfers":[],"locks_added":{}})
        x["combo_routes"][0]["end_state_id"]="end"
        x["combo_edges"]=[
          {"route_id":"r1","from_node":"n1","to_node":"n2",
           "branch_kind":"RANDOM_OUTCOME","branch_predicate":"A"},
          {"route_id":"r1","from_node":"n1","to_node":"n3",
           "branch_kind":"RANDOM_OUTCOME","branch_predicate":"B"},
        ]
        self.assertEqual(1,self.audit(x)["routes"][0]["branch_count"])
        x["combo_edges"].pop()
        with self.assertRaises(ValueError):
            self.audit(x)

    def test_wrong_branch_state_rejected(self):
        x=sample()
        x["combo_nodes"].append({"node_id":"n2","route_id":"r1","sequence":2,
          "action_type":"OPTIONAL_RESOLUTION","actor_card_id":None,
          "before_state_ref":"start","after_state_ref":"end",
          "transfers":[],"locks_added":{}})
        x["combo_edges"]=[{"route_id":"r1","from_node":"n1","to_node":"n2",
                            "branch_kind":"LINEAR"}]
        with self.assertRaises(ValueError):
            self.audit(x)

    def test_attribute_lock_rejects_wrong_summon(self):
        x=sample()
        x["resource_states"][1]["locks_json"]={"SPECIAL_SUMMON_ONLY":"WIND"}
        x["combo_nodes"][0]["locks_added"]={"SPECIAL_SUMMON_ONLY":"WIND"}
        with self.assertRaises(ValueError):
            self.audit(x, {CARD:{"attribute":"DARK"}})
        self.assertEqual(1,self.audit(x,{CARD:{"attribute":"WIND"}})["route_count"])

    def test_game_tested_without_evidence_rejected(self):
        x=sample();x["combo_routes"][0]["verification"]="GAME_TESTED"
        with self.assertRaises(ValueError):
            self.audit(x)

    def test_not_rerun_second_normal_summon(self):
        x=sample()
        x["combo_nodes"][0]["action_type"]="NORMAL_SUMMON"
        x["resource_states"][1]["normal_summon_used"]=True
        x["resource_states"][0]["normal_summon_used"]=True
        with self.assertRaises(ValueError):
            self.audit(x)


if __name__ == "__main__":
    unittest.main()
