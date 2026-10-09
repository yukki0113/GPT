"""Boundary tests for the 2010-2025 historical v0.5.2 acceptance gate."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from racenote_v052_equivalence import compare


DATE = "2025-12-28"


def write(path: Path, value: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def side(root: Path, *, target_run: bool = False, market: bool = False,
         normal_value: int = 1, clean: bool = True) -> None:
    daily = root / "day_prep" / "RaceNote_20251228"
    bundle = {
        "schema_version": "1.0", "metadata": {"generated_at": "time"},
        "race": {"venue": "中山", "race_no": 1, "date": DATE},
        "horses": [{"basic": {"horse_no": 1}, "recent_runs": [{
            "race": {"date": DATE if target_run else "2025-12-01"},
        }]}],
    }
    write(daily / "authoritative" / "race_bundle_1.json", bundle)
    write(daily / "manifest.json", {"status": "PASS", "target_date": DATE})
    write(daily / "validation_report.json", {
        "status": "PASS", "firewall": {
            "target_result_exposed": not clean,
            "analysis_as_of_violations": 0,
            "rrdb_as_of_violations": 0,
        },
    })
    write(root / "forecast_prep" / "day_prep_handoff.json", {
        "market_blind": True, "result_opened": False,
        "target_market_opened": False,
    })
    write(root / "v052" / "session.json", {
        "status": "SESSION_SEALED", "target_date": DATE,
        "logic_version": "RaceNote-Human-Context-Reader-0.5.2-candidate",
        "market_blind": True, "result_opened": False,
        "target_market_opened": False,
    })
    normal = {"evidence": normal_value}
    if market:
        normal["market"] = {"odds": 1.1}
    digest = write(root / "v052" / "reader" / "one.json", normal)
    write(root / "v052" / "reader_manifest.json", {
        "target_date": DATE, "model_input": "normal_view_only",
        "logic_version": "RaceNote-Human-Context-Reader-0.5.2-candidate",
        "projection_equivalent_to": "RaceNote-Human-Context-Reader-0.5.0-candidate",
        "entries": [{
            "venue": "中山", "race_no": 1, "horse_nos": [1],
            "candidate_version": "RaceNote-Human-Context-Reader-0.5.2-candidate",
            "derived_normal_filename": "one.json",
            "derived_normal_sha256": digest,
            "source_semantic_sha256": "source",
        }],
    })


class EquivalenceGateTest(unittest.TestCase):
    def test_identical_inputs_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a", Path(tmp) / "b"
            side(a)
            side(b)
            self.assertEqual(compare(a, b, DATE)["status"], "PASS")

    def test_model_input_difference_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a", Path(tmp) / "b"
            side(a)
            side(b, normal_value=2)
            result = compare(a, b, DATE)
            self.assertEqual(result["status"], "FAIL")
            self.assertFalse(result["normal_view_semantic_equal"])

    def test_target_result_and_market_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a", Path(tmp) / "b"
            side(a)
            for kwargs in ({"target_run": True}, {"market": True}, {"clean": False}):
                side(b, **kwargs)
                self.assertEqual(compare(a, b, DATE)["status"], "FAIL", kwargs)


if __name__ == "__main__":
    unittest.main()
