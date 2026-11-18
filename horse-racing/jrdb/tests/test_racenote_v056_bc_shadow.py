#!/usr/bin/env python3
"""Hermetic checks of the v056 Shadow boundary; no real BTDay mutation."""
from __future__ import annotations
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from racenote_v056_bc_shadow import ShadowError, seal, validate

CONTRACT = "v056-prediction-confidence-audit-newspaper-v1"
FIELDS = {
    "axis_positive_case": "今回条件と走法の一致を根拠に軸にできる。",
    "relative_axis_case": "○にも勝機はあるが◎の条件実績を上位に評価。",
    "unverified_assumptions": "当日の極端な隊列変化は前提として未検証。",
    "axis_failure_scenario": "序盤の位置取り悪化で◎の軸価値が下がる。",
    "final_reason": "比較根拠があるためShadow Bとする。",
}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ShadowBC(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.root = self.home / "BTDAY-9999" / "20250101" / "v056"
        self.root.mkdir(parents=True)
        self.pred = [
            {"venue": "東京", "race_no": 1, "decision_core": {"marks": [3, 7, 9, 11, 14]}},
            {"venue": "東京", "race_no": 2, "decision_core": {"marks": [4, 8, 12, 13, 15]}},
            {"venue": "東京", "race_no": 3, "decision_core": {"marks": [1, 5, 6, 7, 9]}},
            {"venue": "東京", "race_no": 4, "decision_core": {"marks": [2, 4, 6, 8, 10]}},
        ]
        self.conf = [
            {"venue": "東京", "race_no": 1, "honmei": 3, "confidence": "B", "reason": "比較上の理由があるためB"},
            {"venue": "東京", "race_no": 2, "honmei": 4, "confidence": "C", "reason": "序列が不確実なのでC"},
            {"venue": "東京", "race_no": 3, "honmei": 1, "confidence": "A", "reason": "勝ち切り根拠があるA"},
            {"venue": "東京", "race_no": 4, "honmei": 2, "confidence": "Z", "reason": "対象外なのでZ"},
        ]
        self.session = {"contract_revision": CONTRACT, "session_id": "S-TEST", "selection_id": "BTDAY-9999",
                        "target_date": "2025-01-01", "race_roster": [{"venue": "東京", "race_no": x} for x in range(1,5)]}
        self.draft = [
            {"venue": "東京", "race_no": 1, "honmei": 3, "shadow_grade": "C", "strongest_rival": 7, **FIELDS},
            {"venue": "東京", "race_no": 2, "honmei": 4, "shadow_grade": "B", "strongest_rival": 8, **FIELDS},
        ]
        self.input = self.home / "shadow_draft.json"
        self.output = self.home / "shadow_output.json"
        self.save_sources()

    def save_sources(self):
        write(self.root / "session.json", self.session)
        write(self.root / "frozen/records.json", self.pred)
        write(self.root / "confidence_frozen/records.json", self.conf)
        p_sha=sha(self.root/"frozen/records.json")
        c_sha=sha(self.root/"confidence_frozen/records.json")
        shared={"session_id":"S-TEST","selection_id":"BTDAY-9999","target_date":"2025-01-01",
                "contract_revision":CONTRACT,"result_opened":False,"target_market_opened":False}
        write(self.root/"frozen/day_handoff.json",{**shared,"status":"PREDICTION_FROZEN_CLEAN_BLIND",
              "records_sha256":p_sha})
        write(self.root/"confidence_frozen/day_handoff.json",{**shared,
              "status":"CONFIDENCE_FROZEN_CLEAN_BLIND","confidence_records_sha256":c_sha,
              "prediction_records_sha256":p_sha})
        write(self.root/"turn2_summary.json",{**shared,"status":"TURN2_COMPLETE",
              "prediction_records_sha256":p_sha,"confidence_records_sha256":c_sha})
        write(self.input,self.draft)

    def check_reject(self):
        with self.assertRaises((ShadowError,ValueError)):
            validate(self.root,self.input,asserted_unopened=True)

    def test_valid_and_canonical_a_unchanged(self):
        data=validate(self.root,self.input,asserted_unopened=True)
        self.assertEqual(data["record_count"],2)
        self.assertEqual(data["grade_transitions"],{"B->C":1,"C->B":1})
        self.assertEqual({x["canonical_confidence"] for x in data["records"]},{"B","C"})
        result=seal(self.root,self.input,self.output,asserted_unopened=True)
        self.assertEqual(result["record_count"],2)
        with self.assertRaises(FileExistsError):
            seal(self.root,self.input,self.output,asserted_unopened=True)

    def test_requires_current_blind_assertion(self):
        with self.assertRaises(ShadowError):
            validate(self.root,self.input,asserted_unopened=False)

    def test_missing_bc_rejected(self):
        write(self.input,self.draft[:1])
        self.check_reject()

    def test_duplicate_bc_rejected(self):
        write(self.input,[self.draft[0],self.draft[0]])
        self.check_reject()

    def test_a_intrusion_rejected(self):
        item=dict(self.draft[1],race_no=3,honmei=1,strongest_rival=5)
        write(self.input,[self.draft[0],item])
        self.check_reject()

    def test_changed_honmei_rejected(self):
        self.draft[0]["honmei"]=9
        write(self.input,self.draft)
        self.check_reject()

    def test_unfrozen_rival_rejected(self):
        self.draft[0]["strongest_rival"]=99
        write(self.input,self.draft)
        self.check_reject()

    def test_result_field_rejected(self):
        self.draft[0]["finish"]=1
        write(self.input,self.draft)
        self.check_reject()

    def test_missing_reason_rejected(self):
        self.draft[0]["axis_positive_case"]="短い"
        write(self.input,self.draft)
        self.check_reject()

    def test_sha_tamper_rejected(self):
        self.conf[0]["honmei"]=11
        write(self.root/"confidence_frozen/records.json",self.conf)
        self.check_reject()

    def test_reject_output_into_canonical_root(self):
        with self.assertRaises(ShadowError):
            seal(self.root,self.input,self.root/"shadow.json",asserted_unopened=True)

    def test_unlocked_handoff_rejected(self):
        p=self.root/"confidence_frozen/day_handoff.json"
        obj=json.loads(p.read_text(encoding="utf-8"))
        obj["result_opened"]=True
        write(p,obj)
        self.check_reject()

    def test_non_v056_contract_rejected(self):
        self.session["contract_revision"]="v055-prediction-freeze-confidence-review-r6"
        write(self.root/"session.json",self.session)
        self.check_reject()


if __name__ == "__main__":
    unittest.main(verbosity=2)
