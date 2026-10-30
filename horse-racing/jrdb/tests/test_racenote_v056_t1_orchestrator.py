"""Regression: v056 NEXT must skip v055 historical selections."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import racenote_v056_t1_orchestrator as t1

class LegacyTransitionTest(unittest.TestCase):
    def test_legacy_latest_selection_does_not_abort_next(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)/"backtests";base.mkdir()
            sid="BTDAY-0144";day="20250102"
            path=base/sid;path.mkdir()
            (path/"selection.json").write_text(json.dumps({
                "selection_id":sid,"n":1,"dates":["2025-01-02"],
                "sources":[{"source_mode":"historical_warehouse"}]
            }),encoding="utf-8")
            d=path/day;d.mkdir()
            (d/"operation_handoff.json").write_text(json.dumps({
                "contract_revision":"v055-prediction-freeze-confidence-review-r6"
            }),encoding="utf-8")
            pool=Path(tmp)/"pool.json"
            pool.write_text(json.dumps({"selections":[{"selection_id":sid}], "days":[{"date":"2025-01-03","eligible":True}]}),encoding="utf-8")
            fresh={"selection_id":"BTDAY-0145","n":1,"dates":["2025-01-03"],
                   "sources":[{"source_mode":"historical_warehouse"}]}
            with patch.object(t1,"BASE",base),patch.object(t1,"POOL",pool),patch.object(t1,"pick_days",return_value=fresh) as picker:
                result,created=t1.choose_next()
                self.assertTrue(created)
                self.assertEqual(result["selection_id"],"BTDAY-0145")
                picker.assert_called_once()
                self.assertTrue((base/"BTDAY-0145"/"selection.json").is_file())
                self.assertEqual(json.loads((d/"operation_handoff.json").read_text())["contract_revision"],
                                 "v055-prediction-freeze-confidence-review-r6")

if __name__=="__main__": unittest.main()
