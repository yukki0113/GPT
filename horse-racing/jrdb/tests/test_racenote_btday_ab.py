import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
from audit_racenote_btday_ab import audit
from racenote_prepare_forecast_input import bind
from validate_racenote_forecast_human_context import audit_turn

SHA = "a" * 40
DATE = "2026-06-21"
SELECTION = "BTDAY-0035"


def record(logic, changed=False):
    names = ["一号", "二号", "三号", "四号", "五号"]
    def horse(n):
        return {"horse_no": n, "horse_name": names[n-1]}
    marks = [horse(n) for n in ((2, 1, 3, 4, 5) if changed else (1, 2, 3, 4, 5))]
    research = {"logic_version": logic, "reader_facing_prose_contract": "FORECAST_READER_FACING_PROSE_v0_1",
                "authoring_mode": "MODEL_RACE_BY_RACE_REASONING", "prose_origin": "MODEL_AUTHORED_NOT_SCRIPT_GENERATED"}
    trace = {"race_model": "隊列と脚質の噛み合いから前半の位置を読み、末脚を使える位置を比較する。",
             "mainline_cases": [{"horse": horse(n)} for n in (1, 2, 4)],
             "single_shot_case": {"horse": horse(3), "selected_independently_from_mainline": True},
             "mark_reason": {"main": "展開を踏まえて比較した。"},
             "rrdb_evidence": {"available": False, "reviewed": True, "used_in_decision": False,
                               "horse_refs": [], "reason_not_used": "参照できる根拠が不足するため。"}}
    schema = "RaceNote-Forecast-Research-Record-0.4.2"
    if logic.endswith("0.4.3-candidate"):
        schema = "RaceNote-Forecast-Research-Record-0.4.3"
        research.update(independent_forecast=True, baseline_marks_used_as_input=False)
        trace["consistency_pass"] = {
            "hierarchy_reviewed": True, "hierarchy_changed": changed,
            "hierarchy_reason": "一号より二号の勝ち切りを評価した。" if changed else None,
            "single_shot_promotion_reviewed": True, "single_shot_promoted": False,
            "single_shot_promotion_reason": None, "coverage_challenger_reviewed": True,
            "coverage_challenger": None, "coverage_changed": False, "coverage_reason": None,
            "change_attribution": "HIERARCHY_CONSISTENCY" if changed else "UNCHANGED_AFTER_INDEPENDENT_REVIEW"}
    return {"schema_version": schema, "identity": {"target_date": DATE, "venue": "東京", "race_no": 1},
            "research": research,
            "source": {"racenote_semantic_sha256": "reader-hash",
                       "racenote_identity": f"{SELECTION}/東京1R",
                       "reader_input_policy": "TARGET_DAY_MARKET_OBJECT_REMOVED_BEFORE_FORECAST"},
            "prediction": {"axis": marks[0], "marks": {"main": marks[0], "second": marks[1],
                "third": marks[2], "others": marks[3:]},
                "reader_facing_reason": "隊列が落ち着けば先行できる一頭を軸とし、直線で伸びる相手との比較から今回の条件に合う順序を選んだ。"},
            "decision_trace": trace, "audit": {"pre_result_guard": "PASS", "result_visible_at_freeze": False}}


class ABFreezeTest(unittest.TestCase):
    def test_freeze_and_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw_prep = root / "raw-prep"
            (raw_prep / "reader").mkdir(parents=True)
            reader = {"race": {"date": DATE, "venue": "東京", "race_no": 1}, "source_semantic_sha256": "reader-hash",
                      "horses": [{"basic": {"horse_no": i, "horse_name": n}}
                                 for i, n in enumerate(("一号", "二号", "三号", "四号", "五号"), 1)]}
            reader["horses"][0]["market"] = {"odds": 2.0}
            (raw_prep / "reader" / "race.json").write_text(json.dumps(reader), encoding="utf-8")
            (raw_prep / "manifest.json").write_text(json.dumps({"status": "PASS", "target_date": DATE,
                "sources": {"rrdb_recommendation": {"contract_version": "rrdb-recommendation-signals-v0.3", "grade_status": "DISABLED"}},
                "counts": {"races_built": 1, "reader_views": 1}}), encoding="utf-8")
            (raw_prep / "validation_report.json").write_text(json.dumps({"status": "PASS",
                "firewall": {"target_result_exposed": False}}), encoding="utf-8")
            prep = root / "forecast-input"
            handoff = bind(raw_prep, prep, SELECTION, DATE, SHA)
            self.assertEqual(handoff["race_count"], 1)
            self.assertNotIn("market", (prep / "reader" / "race.json").read_text(encoding="utf-8"))
            roots = []
            for version, changed in (("0.4.2", False), ("0.4.3", True)):
                logic = f"RaceNote-Human-Context-Reader-{version}-candidate"
                prepared = root / f"{version}.json"
                prepared.write_text(json.dumps([record(logic, changed)], ensure_ascii=False), encoding="utf-8")
                frozen = root / f"frozen-{version}"
                proc = subprocess.run([sys.executable, str(SRC / "racenote_freeze_prepared_forecast.py"),
                    "--prep-root", str(prep), "--prepared-records", str(prepared), "--output-root", str(frozen),
                    "--selection-id", SELECTION, "--date", DATE, "--main-sha", SHA, "--logic-version", logic],
                    capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                again = subprocess.run([sys.executable, str(SRC / "racenote_freeze_prepared_forecast.py"),
                    "--prep-root", str(prep), "--prepared-records", str(prepared), "--output-root", str(frozen),
                    "--selection-id", SELECTION, "--date", DATE, "--main-sha", SHA, "--logic-version", logic],
                    capture_output=True, text=True)
                self.assertNotEqual(again.returncode, 0)
                self.assertIn("already exists", again.stderr)
                roots.append(frozen)
            report, manifest = audit(prep, *roots, SHA)
            self.assertEqual(report["status"], "PASS", report)
            self.assertEqual(report["changed_race_count"], 1)
            self.assertEqual(report["difference_counts"]["main"], 1)
            self.assertTrue(manifest["same_reader_input_required"])
            frozen_file = roots[1] / "day_merge" / "forecast_20260621_all.json"
            rows = json.loads(frozen_file.read_text(encoding="utf-8"))
            self.assertEqual(audit_turn(rows)["status"], "PASS")
            original = copy.deepcopy(rows)
            rows[0]["source"]["racenote_semantic_sha256"] = "wrong"
            frozen_file.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(audit(prep, *roots, SHA)[0]["status"], "FAIL")
            rows = copy.deepcopy(original)
            rows[0]["prediction"]["marks"]["others"][1] = rows[0]["prediction"]["marks"]["main"]
            frozen_file.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(audit(prep, *roots, SHA)[0]["status"], "FAIL")
            rows = copy.deepcopy(original)
            rows[0]["decision_trace"]["consistency_pass"]["change_attribution"] = "UNCHANGED_AFTER_INDEPENDENT_REVIEW"
            self.assertEqual(audit_turn(rows)["status"], "FAIL")
            frozen_file.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            failed, absent = audit(prep, *roots, SHA)
            self.assertEqual(failed["status"], "FAIL")
            self.assertIsNone(absent)
            frozen_file.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
            (prep / "reader" / "race.json").write_text(json.dumps(reader), encoding="utf-8")
            self.assertEqual(audit(prep, *roots, SHA)[0]["status"], "FAIL")
            contaminated_out = root / "contaminated-freeze"
            proc = subprocess.run([sys.executable, str(SRC / "racenote_freeze_prepared_forecast.py"),
                "--prep-root", str(prep), "--prepared-records", str(root / "0.4.3.json"),
                "--output-root", str(contaminated_out), "--selection-id", SELECTION,
                "--date", DATE, "--main-sha", SHA,
                "--logic-version", "RaceNote-Human-Context-Reader-0.4.3-candidate"],
                capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertFalse(contaminated_out.exists())

    def test_freeze_rejects_market_and_tampered_reader_before_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            prep = root / "prep"
            (prep / "reader").mkdir(parents=True)
            reader = {"race": {"venue": "東京", "race_no": 1}, "source_semantic_sha256": "reader-hash",
                      "horses": [{"basic": {"horse_no": i, "horse_name": n}} for i, n in enumerate(
                          ("一号", "二号", "三号", "四号", "五号"), 1)]}
            reader["horses"][0]["market"] = {"odds": 2.0}
            (prep / "reader" / "race.json").write_text(json.dumps(reader), encoding="utf-8")
            (prep / "day_prep_handoff.json").write_text(json.dumps({
                "selection_id": SELECTION, "target_date": DATE, "result_opened": False, "race_count": 1}), encoding="utf-8")
            prepared = root / "prepared.json"
            prepared.write_text(json.dumps([record("RaceNote-Human-Context-Reader-0.4.3-candidate")], ensure_ascii=False), encoding="utf-8")
            out = root / "frozen"
            cmd = [sys.executable, str(SRC / "racenote_freeze_prepared_forecast.py"),
                   "--prep-root", str(prep), "--prepared-records", str(prepared), "--output-root", str(out),
                   "--selection-id", SELECTION, "--date", DATE, "--main-sha", SHA,
                   "--logic-version", "RaceNote-Human-Context-Reader-0.4.3-candidate"]
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
