"""Offline official M6-8 wrapper; fictional regression only."""
from copy import deepcopy
import unittest
from engine_m6.runtime_recompose import canonical_sha, run_bundle
from test_m6_5c import sample
from test_m6_7_competitive import regulation
from test_m6_8_build_policy import v2


def bundle():
    teacher,req,d,a,s,p=sample()
    return {"request":req,"teacher_candidate":teacher,
            "discovery_results":d,"annotations":a,
            "material_screen":s,"engine_packages":p,
            "decision_policy":v2(a),
            "regulation_policy":regulation(a)}


class OfflineRuntimeTests(unittest.TestCase):
    def test_official_recomposer_is_used_unchanged(self):
        b=bundle()
        sha=canonical_sha(b["decision_policy"])
        result=run_bundle(b,expected_policy_sha=sha)
        self.assertGreater(result["solution_count"],0)
        self.assertEqual(sha,result["decision_policy_sha256"])

    def test_modified_policy_is_not_silently_refrozen(self):
        b=bundle()
        sha=canonical_sha(b["decision_policy"])
        b["decision_policy"]["assessments"][0]["copy_adjustments"][0]-=1
        with self.assertRaisesRegex(ValueError,"PRECOMMITTED_SHA_MISMATCH"):
            run_bundle(b,expected_policy_sha=sha)

    def test_legacy_local_shape_not_auto_accepted(self):
        b=bundle()
        b["decision_policy"]={"schema":"md-m6-8-evidence-build-policy-v2",
                               "candidates":[]}
        with self.assertRaisesRegex(ValueError,"V2_POLICY_SHAPE"):
            run_bundle(b,expected_policy_sha=canonical_sha(b["decision_policy"]))

    def test_missing_material_screen_fails_closed(self):
        b=bundle();del b["material_screen"]
        with self.assertRaisesRegex(ValueError,"INPUT_BUNDLE_REQUIRED"):
            run_bundle(b,expected_policy_sha=canonical_sha(b["decision_policy"]))


if __name__=="__main__": unittest.main()
