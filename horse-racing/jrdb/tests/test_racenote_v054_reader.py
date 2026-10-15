from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import racenote_reader_v054 as v054
from racenote_save_venue_batch_v046 import load_clean


def base_candidate(rrdb_version: str):
    return {
        "normal_view": {
            "race": {"date": "2025-07-12"},
            "horses": [{
                "identity": {"horse_no": 3},
                "evidence": {},
                "other_context": {
                    "racereview": {
                        "history_status": "AVAILABLE",
                        "recommendation": {
                            "contract_version": rrdb_version,
                            "status": "NO_MATCH",
                            "signals": [],
                        },
                        "next_watch": {"status": "DEPRECATED"},
                    }
                }
            }]
        },
        "provenance": {"horses": []},
    }


class V054ReaderTest(unittest.TestCase):
    def test_canonical_v05_is_promoted_without_duplicate_old_signal(self):
        result = base_candidate("rrdb-recommendation-signals-v0.5")
        with patch.object(v054.v053, "transform", return_value=copy.deepcopy(result)):
            projected = v054.transform({"not": "used"}, {})
        h = projected["normal_view"]["horses"][0]
        self.assertEqual(h["rrdb_v05"]["contract_version"], "rrdb-recommendation-signals-v0.5")
        self.assertEqual(h["rrdb_v05"]["status"], "NO_MATCH")
        self.assertNotIn("recommendation", h["other_context"]["racereview"])
        self.assertNotIn("next_watch", h["other_context"]["racereview"])

    def test_legacy_v04_does_not_masquerade_as_v05(self):
        result = base_candidate("rrdb-recommendation-signals-v0.4")
        with patch.object(v054.v053, "transform", return_value=copy.deepcopy(result)):
            projected = v054.transform({"not": "used"}, {})
        h = projected["normal_view"]["horses"][0]
        self.assertEqual(h["rrdb_v05"]["status"], "UNAVAILABLE")

    def test_supplied_v05_replaces_legacy_no_double_counting(self):
        result = base_candidate("rrdb-recommendation-signals-v0.4")
        with patch.object(v054.v053, "transform", return_value=copy.deepcopy(result)):
            projected = v054.transform({"not": "used"}, {}, rrdb_by_horse={
                3: {
                    "contract_version": "rrdb-recommendation-signals-v0.5",
                    "status": "MATCHED",
                    "signals": [{"signal_id": "TIME_CLASS_PLUS1"}],
                },
            })
        h = projected["normal_view"]["horses"][0]
        self.assertEqual(len(h["rrdb_v05"]["signals"]), 1)
        self.assertNotIn("recommendation", h["other_context"]["racereview"])

    def test_lap_reader_needs_target_date(self):
        result = base_candidate("rrdb-recommendation-signals-v0.5")
        with patch.object(v054.v053, "transform", return_value=copy.deepcopy(result)):
            with self.assertRaisesRegex(ValueError, "target_date"):
                v054.transform({"not": "used"}, {}, race_lap_reader=object())


class RRDBContractLoaderTest(unittest.TestCase):
    def _prep(self, contract: str) -> Path:
        root = Path(self._tmp.name)
        reader_dir = root / "reader"
        reader_dir.mkdir(parents=True)
        reader = {
            "view_version": "0.1",
            "source_semantic_sha256": "x",
            "race": {"date": "2025-07-12", "venue": "函館", "race_no": 1},
            "horses": [],
        }
        raw_reader = (json.dumps(reader, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
        rp = reader_dir / "r1.json"
        rp.write_bytes(raw_reader)
        manifest = {
            "market_blind": True,
            "result_opened": False,
            "selection_id": "BTDAY-X",
            "target_date": "2025-07-12",
            "race_count": 1,
            "reader_sha256": {"r1.json": hashlib.sha256(raw_reader).hexdigest()},
        }
        raw_manifest = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
        (root / "reader_stripped_manifest.json").write_bytes(raw_manifest)
        handoff = {
            "selection_id": "BTDAY-X",
            "target_date": "2025-07-12",
            "race_count": 1,
            "market_blind": True,
            "result_opened": False,
            "target_market_opened": False,
            "rrdb_contract": contract,
            "reader_stripped_manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
        }
        (root / "day_prep_handoff.json").write_text(json.dumps(handoff), encoding="utf-8")
        return root

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def test_legacy_default_still_accepts_v04(self):
        handoff, _, _ = load_clean(self._prep("rrdb-recommendation-signals-v0.4"))
        self.assertEqual(handoff["rrdb_contract"], "rrdb-recommendation-signals-v0.4")

    def test_v054_can_explicitly_require_v05(self):
        handoff, _, _ = load_clean(
            self._prep("rrdb-recommendation-signals-v0.5"),
            expected_rrdb_contract="rrdb-recommendation-signals-v0.5",
        )
        self.assertEqual(handoff["rrdb_contract"], "rrdb-recommendation-signals-v0.5")

    def test_v05_is_rejected_by_legacy_default(self):
        with self.assertRaisesRegex(ValueError, "expected rrdb-recommendation-signals-v0.4"):
            load_clean(self._prep("rrdb-recommendation-signals-v0.5"))


if __name__ == "__main__":
    unittest.main()
