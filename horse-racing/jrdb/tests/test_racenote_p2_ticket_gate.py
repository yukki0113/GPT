"""Isolated tests of P2 ticket research validator; no race results or market data."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from racenote_p2_ticket_gate import SCHEMA, validate


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


class P2TicketGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "BTDAY-9999" / "v056"
        self.draft = Path(self.tmp.name) / "draft.json"
        self.reader = {
            "race": {"venue": "東京", "race_no": 1},
            "horses": [
                {"identity": {"horse_no": no},
                 "evidence": {"ABILITY": {"P": {"idm": 30 + no}}}}
                for no in range(1, 7)
            ],
        }
        self.reader_sha = write(self.root / "reader" / "tokyo1.json", self.reader)
        manifest_sha = write(self.root / "reader_manifest.json", {
            "entries": [{"venue": "東京", "race_no": 1,
                         "derived_normal_filename": "tokyo1.json",
                         "derived_normal_sha256": self.reader_sha}]
        })
        pred = [{"venue": "東京", "race_no": 1, "reader_sha256": self.reader_sha,
                 "decision_core_sha256": "a" * 64,
                 "decision_core": {"marks": [1, 2, 3, 4, 5]}}]
        pred_sha = write(self.root / "frozen" / "records.json", pred)
        write(self.root / "frozen" / "day_handoff.json", {
            "status": "PREDICTION_FROZEN_CLEAN_BLIND", "market_blind": True,
            "result_opened": False, "target_market_opened": False,
            "selection_id": "BTDAY-9999", "target_date": "2025-01-01",
            "records_sha256": pred_sha, "reader_manifest_sha256": manifest_sha,
            "record_count": 1,
        })

        def ref(no):
            return f"/horses/{no - 1}/evidence/ABILITY/P/idm"

        self.record = {
            "venue": "東京", "race_no": 1, "marks": [1, 2, 3, 4, 5],
            "reader_sha256": self.reader_sha, "decision_core_sha256": "a" * 64,
            "five_roles": [
                {"horse_no": no, "win_path": "勝ち切る場合は前方を確保する",
                 "top2_path": "先行して連対圏内を維持する条件",
                 "top3_path": "他馬と比較した着内根拠を確認する",
                 "failure_path": "前半のペースが上がると失速する",
                 "evidence_refs": [ref(no)]}
                for no in range(1, 6)
            ],
            "outside_screen": [
                {"horse_no": 6, "classification": "THREAT",
                 "top3_path": "6番が展開次第で三着以内へ入る可能性",
                 "evidence_refs": [ref(6)]}
            ],
            "outside_summary": "6番の印外からの割込みを念頭において判断する",
            "cooccurrence_cases": [
                {"case_id": "wide12", "horse_nos": [1, 2], "bet_type": "WIDE",
                 "shared_scenario": "1と2が同時に先行して双方が3着に残る展開",
                 "conflict_scenario": "両馬が競り合って同時に失速する場合",
                 "evidence_refs": [ref(1), ref(2)]}
            ],
            "purchase_decision": "PROVISIONAL_BET",
            "tickets": [{"bet_type": "WIDE", "horse_nos": [1, 2],
                         "stake_yen": 100, "case_id": "wide12"}],
            "no_bet_reason": None, "market_available": False,
        }
        self.envelope = {
            "schema_version": SCHEMA, "selection_id": "BTDAY-9999",
            "target_date": "2025-01-01", "result_opened": False,
            "target_market_opened": False, "confidence_used": False,
            "records": [self.record],
        }

    def check(self, envelope=None):
        write(self.draft, envelope if envelope is not None else self.envelope)
        return validate(self.root, self.draft)

    def test_valid_provisional(self):
        summary = self.check()
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["totals"]["tickets"], 1)
        self.assertEqual(summary["totals"]["outside_threats"], 1)

    def test_valid_pass(self):
        d = copy.deepcopy(self.envelope)
        r = d["records"][0]
        r["purchase_decision"], r["tickets"] = "PASS", []
        r["no_bet_reason"] = "印外からの割込みリスクが大きく購入見送り"
        self.assertEqual(self.check(d)["totals"]["pass"], 1)

    def test_missing_outsider_rejected(self):
        d = copy.deepcopy(self.envelope)
        d["records"][0]["outside_screen"] = []
        with self.assertRaisesRegex(ValueError, "every non-marked"):
            self.check(d)

    def test_wrong_horse_pointer_rejected(self):
        d = copy.deepcopy(self.envelope)
        d["records"][0]["five_roles"][0]["evidence_refs"] = [
            "/horses/5/evidence/ABILITY/P/idm"
        ]
        with self.assertRaisesRegex(ValueError, "relevant horse"):
            self.check(d)

    def test_laundered_confidence_or_result_rejected(self):
        for field in ("confidence", "payout_yen", "result_opened", "odds"):
            d = copy.deepcopy(self.envelope)
            d["records"][0][field] = 123
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "forbidden"):
                self.check(d)

    def test_wrong_ticket_or_duplicate_rejected(self):
        d = copy.deepcopy(self.envelope)
        d["records"][0]["tickets"][0]["horse_nos"] = [1, 3]
        with self.assertRaisesRegex(ValueError, "matching cooccurrence"):
            self.check(d)
        d = copy.deepcopy(self.envelope)
        d["records"][0]["tickets"].append(copy.deepcopy(d["records"][0]["tickets"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate ticket"):
            self.check(d)

    def test_changed_reader_rejected(self):
        self.check()
        self.reader["horses"][0]["evidence"]["ABILITY"]["P"]["idm"] = 900
        write(self.root / "reader" / "tokyo1.json", self.reader)
        with self.assertRaisesRegex(ValueError, "Reader SHA"):
            validate(self.root, self.draft)

    def test_case_needs_both_horses_evidence(self):
        d = copy.deepcopy(self.envelope)
        d["records"][0]["cooccurrence_cases"][0]["evidence_refs"] = [
            "/horses/0/evidence/ABILITY/P/idm"
        ]
        with self.assertRaisesRegex(ValueError, "each case horse"):
            self.check(d)

    def test_draft_must_remain_blind(self):
        d = copy.deepcopy(self.envelope)
        d["confidence_used"] = True
        with self.assertRaisesRegex(ValueError, "blind status"):
            self.check(d)


if __name__ == "__main__":
    unittest.main()
