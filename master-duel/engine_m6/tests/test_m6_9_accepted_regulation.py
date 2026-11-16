"""Accepted MD baseline and in-app notice deltas: all cards fictional."""
from copy import deepcopy
import unittest
from engine_m6.accepted_regulation import canonical_sha, append_notice
from engine_m6.regulation_gate import validate_regulation_policy

PIN="c"*64


def baseline():
    entries={"konami:101":0,"konami:102":1,"konami:103":2}
    return {"schema":"md-regulation-accepted-baseline-v1",
            "format":"MD_STANDARD","master_sqlite_sha256":PIN,
            "baseline_snapshot_id":"synthetic-snapshot",
            "baseline_effective_on":"2026-11-05",
            "accepted_on":"2026-11-16",
            "acceptance":"USER_APPROVED_OPERATIONAL_BASELINE",
            "original_source_verification":"UNVERIFIED_SOURCE",
            "baseline_entries_sha256":canonical_sha(entries),
            "baseline_entries":entries,"events":[]}


def limits(policy,as_of="2026-11-16",cards=None):
    return validate_regulation_policy(policy,master_sha256=PIN,
        as_of=as_of,candidate_ids=cards or
        ["konami:101","konami:102","konami:103","konami:104"])


def event(eid,day,changes,kind="REGULATION_REVISION"):
    return {"event_id":eid,"kind":kind,"announced_on":"2026-11-16",
            "effective_on":day,
            "basis":"GAME_IN_APP_NOTICE" if kind=="REGULATION_REVISION"
                    else "GAME_IN_APP_OBSERVATION",
            "changes":[{"card_id":cid,"before":old,"after":new}
                       for cid,old,new in changes]}


class AcceptedRegulationTests(unittest.TestCase):
    def test_approved_original_unverified_source_is_usable(self):
        self.assertEqual({"konami:101":0,"konami:102":1,
                          "konami:103":2,"konami:104":3},limits(baseline()))

    def test_no_31_day_expiry_or_rescrape_requirement(self):
        self.assertEqual(0,limits(baseline(),"2030-12-01")["konami:101"])

    def test_prior_to_user_approval_is_not_accepted(self):
        with self.assertRaisesRegex(ValueError,"NOT_EFFECTIVE_YET"):
            limits(baseline(),"2026-11-15")

    def test_change_only_takes_effect_on_effective_date(self):
        p=append_notice(baseline(),event("2026-12-a","2026-12-01",
                       [("konami:102",1,0),("konami:104",3,1),
                        ("konami:103",2,3)]))
        self.assertEqual(1,limits(p,"2026-11-30")["konami:102"])
        self.assertEqual({"konami:101":0,"konami:102":0,
                          "konami:103":3,"konami:104":1},limits(p,"2026-12-01"))
        self.assertEqual(3,limits(p,"2027-05-01")["konami:103"])

    def test_correction_event_separate_from_regulation_revision(self):
        p=append_notice(baseline(),event("2026-11-fix","2026-11-16",
                        [("konami:101",0,2)],kind="DATA_CORRECTION"))
        self.assertEqual(2,limits(p)["konami:101"])
        self.assertEqual("DATA_CORRECTION",p["events"][0]["kind"])
        self.assertEqual(0,limits(baseline())["konami:101"])

    def test_bad_expected_prior_copies_fails(self):
        with self.assertRaisesRegex(ValueError,"BEFORE_MISMATCH"):
            append_notice(baseline(),event("2026-12-a","2026-12-01",
                                         [("konami:102",2,0)]))

    def test_cannot_replace_master_snapshot_or_unapprove(self):
        p=baseline();p["master_sqlite_sha256"]="d"*64
        with self.assertRaisesRegex(ValueError,"DB_SHA_MISMATCH"):limits(p)
        p=baseline();p["acceptance"]="UNVERIFIED_SOURCE"
        with self.assertRaisesRegex(ValueError,"NOT_USER_APPROVED"):limits(p)

    def test_immutable_baseline_entries_digest(self):
        p=baseline();p["baseline_entries"]["konami:101"]=3
        with self.assertRaisesRegex(ValueError,"ENTRIES_INVALID"):limits(p)
        p=baseline();p["baseline_entries"]["konami:101"]=1
        with self.assertRaisesRegex(ValueError,"ENTRIES_SHA_MISMATCH"):limits(p)

    def test_duplicate_event_and_same_card_rejected(self):
        e=event("2026-12-a","2026-12-01",[("konami:102",1,0)])
        p=append_notice(baseline(),e)
        with self.assertRaisesRegex(ValueError,"ID_DUPLICATE"):
            append_notice(p,e)
        e=event("2026-12-b","2026-12-01",
                [("konami:102",0,1),("konami:102",1,2)])
        with self.assertRaisesRegex(ValueError,"CHANGE_ID_INVALID"):
            append_notice(p,e)

    def test_future_in_game_notice_does_not_change_today(self):
        p=append_notice(baseline(),event("2026-12-a","2026-12-01",
                                        [("konami:104",3,1)]))
        self.assertEqual(3,limits(p,"2026-11-16")["konami:104"])
        self.assertEqual(1,limits(p,"2026-12-01")["konami:104"])

    def test_v1_game_verified_path_remains_supported(self):
        old={"schema":"md-m6-7-regulation-gate-v1","format":"MD_STANDARD",
             "master_sqlite_sha256":PIN,"effective_on":"2026-11-05",
             "checked_on":"2026-11-16","verification":"GAME_VERIFIED",
             "source_refs":["https://example.org/test"],
             "card_limits":{"konami:101":1}}
        self.assertEqual({"konami:101":1},limits(old,cards=["konami:101"]))

if __name__=="__main__":
    unittest.main()
