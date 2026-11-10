"""Synthetic CP policy storage and dated selection tests."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from regulation_m3 import validate_cp_policy, resolve_cp_policy, load_cp_policy_file

CHECKED = "2026-11-10T13:03:00+09:00"

def item(effective="2026-11-10", verification="USER_CONFIRMED", policy_id="fake-user-confirmed"):
    return {
        "policy_id":policy_id, "effective_on":effective, "checked_at":CHECKED,
        "source":"USER_CONFIRMATION: synthetic fixture" if verification=="USER_CONFIRMED" else "SYNTHETIC_FIXTURE",
        "verification":verification,
        "cp_per_card":{"N":30,"R":30,"SR":30,"UR":30},
    }

class CPPolicyTests(unittest.TestCase):

    def test_four_rarities_exactly_thirty(self):
        result=validate_cp_policy(item())
        self.assertEqual(result["verification"],"USER_CONFIRMED")
        self.assertEqual(result["cp_per_card"],{"N":30,"R":30,"SR":30,"UR":30})

    def test_hashed_private_file_loader(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"policy.json"
            raw=json.dumps(item(),ensure_ascii=False,sort_keys=True).encode("utf-8")
            path.write_bytes(raw)
            loaded=load_cp_policy_file(path,expected_sha256=hashlib.sha256(raw).hexdigest())
            self.assertEqual(loaded,item())
            with self.assertRaisesRegex(ValueError,"SHA-256 mismatch"):
                load_cp_policy_file(path,expected_sha256="0"*64)
            with self.assertRaises(ValueError):
                load_cp_policy_file(path,expected_sha256="not-a-digest")

    def test_future_policy_is_never_applied(self):
        outcome=resolve_cp_policy([item()],as_of="2026-11-09")
        self.assertEqual(outcome["status"],"NO_APPLICABLE_POLICY")
        self.assertIsNone(outcome["policy"])

    def test_latest_same_day_ambiguity_fails_closed(self):
        policies=[item(policy_id="a"),item(policy_id="b")]
        self.assertEqual(resolve_cp_policy(policies,as_of="2026-11-10")["status"],"AMBIGUOUS_POLICY")

    def test_new_unverified_shadows_old_confirmed(self):
        old=item(effective="2026-10-01",policy_id="old")
        new=item(effective="2026-11-10",verification="UNVERIFIED_SOURCE",policy_id="new")
        got=resolve_cp_policy([old,new],as_of="2026-11-10")
        self.assertEqual(got["status"],"CANDIDATE_ONLY")
        self.assertEqual(got["policy"]["policy_id"],"new")
        self.assertEqual(resolve_cp_policy([old,new],as_of="2026-11-09")["status"],"USER_CONFIRMED")

    def test_invalid_policy_schema_or_source_rejected(self):
        for change in (
                {"verification":"OFFICIAL_UNVERIFIED"},
                {"effective_on":"2026/11/10"},
                {"source":"external blog"},
                {"checked_at":"2026-11-10"},
                {"cp_per_card":{"N":30,"R":30,"SR":30}},
                {"cp_per_card":{"N":30,"R":30,"SR":30,"UR":True}},
                {"cp_per_card":{"N":30,"R":30,"SR":30,"UR":0}}):
            p=item()
            p.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_cp_policy(p)

if __name__=="__main__":
    unittest.main()
