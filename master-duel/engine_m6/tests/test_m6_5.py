"""M6-5 synthetic-only private reporting and immutable storage tests."""
import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from engine_m6.report import compare_candidates, full_owned_dispositions, extra_gap_review
from engine_m6.proposal_store import (make_proposal_archive, verify_proposal_archive,
                                       save_new_private_proposal)
from test_m6_4 import base

SHA="a"*64

def fixture():
    candidate,_,_,_=base()
    candidate["lineage"]["source_master_sha256"]=SHA
    candidate["lineage"]["source_ref"]="M5C:FICTIONAL"
    candidates={x["card_id"] for x in candidate["cards"]}
    rows=[]
    for i,cid in enumerate(("konami:100","konami:101","konami:999","konami:998")):
        selected=cid in candidates
        rows.append({"card_id":cid,"known_state":"KNOWN_POSITIVE" if i!=3 else "KNOWN_ZERO",
                     "owned_quantity":2 if i!=3 else 0,"rarity":"SR",
                     "regulation_limit":None,"regulation_confidence":"UNKNOWN",
                     "disposition":"REVIEW_REQUIRED","decision_reason":"not yet assessed",
                     "main_or_extra":"UNKNOWN","selected_quantity":0})
    audit={"schema":"md-m6-v1","head_generation":3,"sqlite_sha":SHA,
           "inventory_total_registered":4,"inventory_rows_reviewed":4,
           "owned_inventory_decisions":rows,"preflight_status":"PARTIAL"}
    evaluation={"candidate_id":candidate["candidate_id"],"requested_mode_gate":"INDETERMINATE",
                "mode_gates":{"CORE_UR_ZERO":"INDETERMINATE","NEW_UR_CRAFT_ZERO":"PASS",
                              "STRICT_NO_UR":"PASS"},
                "required_cp_lower_by_rarity":{"N":0,"R":0,"SR":0,"UR":0},
                "required_cp_upper_by_rarity":{"N":60,"R":90,"SR":120,"UR":0},
                "new_needed_lower_by_rarity":{"N":0,"R":0,"SR":0,"UR":0},
                "new_needed_upper_by_rarity":{"N":2,"R":3,"SR":4,"UR":0},
                "extra_deck":{"used":7,"unused":8,"suitability":"NOT_ASSESSED"},
                "warnings":["EXTRA_DECK_UNUSED_SLOTS_NOT_OPTIMIZED"],
                "blocking_reasons":[],"recommendation_eligible":False}
    option={"card_id":"konami:999","section":"EXTRA","rarity":"SR",
            "evidence_id":"M4:synthetic-effect-sha","role":"rank4-maybe",
            "effect_verification":"TEXT_CHECKED","regulation_verification":"UNKNOWN",
            "compatibility_review":"PENDING"}
    return {"candidate":candidate,"evaluation":evaluation,"owned_audit":audit,
            "sourced_extra_options":[option]}

class M65Tests(unittest.TestCase):
    def test_full_inventory_includes_unselected_rows(self):
        f=fixture();r=full_owned_dispositions(f["candidate"],f["owned_audit"])
        self.assertEqual(4,r["decision_count"])
        self.assertEqual(2,r["counts"]["ADOPT"])
        self.assertEqual(2,r["counts"]["EXCLUDE"])
        self.assertGreater(len(r["unregistered_selected_cards"]),0)
        self.assertFalse(r["unregistered_cards_are_known_zero"])

    def test_sourced_extra_is_consider_not_auto_adopt(self):
        f=fixture();r=full_owned_dispositions(f["candidate"],f["owned_audit"],
                                              eligible_extra=f["sourced_extra_options"])
        x=next(x for x in r["decisions"] if x["card_id"]=="konami:999")
        self.assertEqual("CONSIDER",x["disposition"])
        self.assertEqual(0,x["selected_quantity"])

    def test_empty_ex_evidence_keeps_8_gap(self):
        f=fixture();r=extra_gap_review(f["candidate"],f["evaluation"])
        self.assertEqual(8,r["unused"])
        self.assertEqual([],r["options"])
        self.assertFalse(r["role_coverage_verified"])

    def test_ex_sourced_option_is_not_auto_filled(self):
        f=fixture();r=extra_gap_review(f["candidate"],f["evaluation"],
                                       sourced_options=f["sourced_extra_options"])
        self.assertEqual(1,r["options_without_ur"])
        self.assertFalse(r["options"][0]["automatically_added"])
        self.assertFalse(r["role_coverage_verified"])

    def test_ur_ex_option_does_not_count_for_ur0(self):
        f=fixture();f["sourced_extra_options"][0]["rarity"]="UR"
        r=extra_gap_review(f["candidate"],f["evaluation"],sourced_options=f["sourced_extra_options"])
        self.assertEqual(0,r["options_without_ur"])

    def test_uncited_extra_rejected(self):
        f=fixture();f["sourced_extra_options"][0]["evidence_id"]=""
        with self.assertRaises(ValueError):
            extra_gap_review(f["candidate"],f["evaluation"],sourced_options=f["sourced_extra_options"])

    def test_wrong_ex_section_rejected(self):
        f=fixture();f["sourced_extra_options"][0]["section"]="MAIN"
        with self.assertRaises(ValueError):
            extra_gap_review(f["candidate"],f["evaluation"],sourced_options=f["sourced_extra_options"])

    def test_wrong_candidate_evaluation_rejected(self):
        f=fixture();f["evaluation"]["candidate_id"]="other"
        with self.assertRaises(ValueError):
            compare_candidates([f])

    def test_cross_generation_owned_audit_rejected(self):
        f=fixture();f["owned_audit"]["sqlite_sha"]="b"*64
        with self.assertRaises(ValueError):
            compare_candidates([f])

    def test_partial_inventory_coverage_rejected(self):
        f=fixture();f["owned_audit"]["owned_inventory_decisions"].pop()
        with self.assertRaises(ValueError):
            compare_candidates([f])

    def test_recommendation_upgrade_rejected(self):
        f=fixture();f["evaluation"]["recommendation_eligible"]=True
        with self.assertRaises(ValueError):
            compare_candidates([f])

    def test_reproducible_comparison_hash(self):
        a=fixture();b=fixture();b["candidate"]["candidate_id"]="other-fake"
        b["evaluation"]["candidate_id"]="other-fake"
        r=compare_candidates([b,a]);r2=compare_candidates([a,b])
        self.assertEqual(r,r2)
        self.assertEqual(2,r["candidate_count"])

    def test_duplicate_candidate_rejected(self):
        with self.assertRaises(ValueError):
            compare_candidates([fixture(),fixture()])

    def test_zip_is_bitwise_deterministic(self):
        c=compare_candidates([fixture()]);a,m=make_proposal_archive(c,source_master_sha256=SHA)
        self.assertEqual((a,m),make_proposal_archive(c,source_master_sha256=SHA))
        opened=verify_proposal_archive(a,m,expected_archive_sha256=hashlib.sha256(a).hexdigest(),
             expected_manifest_sha256=hashlib.sha256(m).hexdigest(),expected_master_sha256=SHA)
        self.assertEqual(c,opened["comparison.json"])

    def test_zip_sha_tampering_rejected(self):
        c=compare_candidates([fixture()]);a,m=make_proposal_archive(c,source_master_sha256=SHA)
        with self.assertRaisesRegex(ValueError,"archive external SHA"):
            verify_proposal_archive(a+b"X",m,expected_archive_sha256=hashlib.sha256(a).hexdigest(),
                expected_manifest_sha256=hashlib.sha256(m).hexdigest(),expected_master_sha256=SHA)

    def test_manifest_external_sha_tampering_rejected(self):
        c=compare_candidates([fixture()]);a,m=make_proposal_archive(c,source_master_sha256=SHA)
        with self.assertRaisesRegex(ValueError,"manifest external SHA"):
            verify_proposal_archive(a,m,expected_archive_sha256=hashlib.sha256(a).hexdigest(),
                expected_manifest_sha256="0"*64,expected_master_sha256=SHA)

    def test_master_sha_pin_rejected(self):
        c=compare_candidates([fixture()]);a,m=make_proposal_archive(c,source_master_sha256=SHA)
        with self.assertRaisesRegex(ValueError,"manifest source pins"):
            verify_proposal_archive(a,m,expected_archive_sha256=hashlib.sha256(a).hexdigest(),
                expected_manifest_sha256=hashlib.sha256(m).hexdigest(),expected_master_sha256="b"*64)

    def test_snapshot_is_never_overwritten(self):
        c=compare_candidates([fixture()]);a,m=make_proposal_archive(c,source_master_sha256=SHA)
        with TemporaryDirectory() as d:
            paths=save_new_private_proposal(d,"fake-v1",a,m)
            with self.assertRaises(FileExistsError):
                save_new_private_proposal(d,"fake-v1",a,m)
            self.assertEqual(a,Path(paths[0]).read_bytes())
            self.assertEqual(m,Path(paths[1]).read_bytes())

    def test_invalid_archive_destination_rejected(self):
        c=compare_candidates([fixture()]);a,m=make_proposal_archive(c,source_master_sha256=SHA)
        with TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                save_new_private_proposal(d,"../escape",a,m)

    def test_compare_does_not_mutate_inputs(self):
        f=fixture();old=copy.deepcopy(f)
        compare_candidates([f])
        self.assertEqual(old,f)

if __name__=="__main__":unittest.main()
