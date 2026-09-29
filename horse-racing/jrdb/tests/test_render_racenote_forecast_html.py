import unittest

from render_racenote_forecast_html import render_daily_html


def record(race_no, venue="中山", horse_no=1):
    return {
        "schema_version": "RaceNote-Forecast-Research-Record-0.1",
        "identity": {
            "target_date": "2026-01-04",
            "venue": venue,
            "race_no": race_no,
            "race_key": f"key-{venue}-{race_no}",
            "race_name": f"Race {race_no}",
            "surface": "芝",
            "distance_m": 1600,
            "class": "1勝クラス",
        },
        "research": {
            "evaluation_mode": "BLINDED_HISTORICAL",
            "turn_id": "BTDAY-0001",
            "logic_version": "BASELINE-0.1",
        },
        "source": {
            "racenote_identity": f"rn-{race_no}",
            "racenote_semantic_sha256": "a" * 64,
        },
        "prediction": {
            "axis": {"horse_no": horse_no, "horse_name": f"本命{race_no}"},
            "marks": {
                "main": {"horse_no": horse_no, "horse_name": f"本命{race_no}"},
                "second": {"horse_no": 2, "horse_name": "対抗"},
                "third": {"horse_no": 3, "horse_name": "単穴"},
                "others": [{"horse_no": 4, "horse_name": "連下"}],
            },
            "axis_comment": "短い本命コメント",
            "concern": "展開次第",
        },
        "audit": {
            "created_at": "2026-09-29T00:00:00Z",
            "frozen_at": "2026-09-29T00:01:00Z",
            "prediction_hash": "b" * 64,
            "pre_result_guard": "PASS",
            "result_visible_at_freeze": False,
        },
    }


class ForecastHtmlTest(unittest.TestCase):
    def test_render_contains_marks_and_comment(self):
        out = render_daily_html([record(1), record(2)])
        self.assertIn("2026-01-04 RaceNote予想", out)
        self.assertIn("1R", out)
        self.assertIn("1 本命1", out)
        self.assertIn("短い本命コメント", out)
        self.assertIn("BTDAY-0001", out)

    def test_mixed_dates_fail(self):
        a = record(1)
        b = record(2)
        b["identity"]["target_date"] = "2026-01-05"
        with self.assertRaises(ValueError):
            render_daily_html([a, b])

    def test_unfrozen_record_fails(self):
        a = record(1)
        a["audit"]["result_visible_at_freeze"] = True
        with self.assertRaises(ValueError):
            render_daily_html([a])


if __name__ == "__main__":
    unittest.main()
