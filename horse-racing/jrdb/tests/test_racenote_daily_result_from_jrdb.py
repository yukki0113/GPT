from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import racenote_daily_result_from_jrdb as subject  # noqa: E402


def test_convert_jrdb_query_payload_to_racenote_schema() -> None:
    source = {
        "status": "success",
        "query": {"date": "2026-10-04"},
        "provenance": {"result_source": "SED", "payout_source": "HJC", "web_used": False},
        "races": [
            {
                "race_date": "2026-10-04",
                "venue_name": "東京",
                "race_no": 1,
                "top3": [
                    {"finish": 1, "horse_no": 3, "horse_name": "A"},
                    {"finish": 2, "horse_no": 12, "horse_name": "B"},
                    {"finish": 3, "horse_no": 4, "horse_name": "C"},
                ],
                "payouts": {
                    "win": [{"numbers": [3], "payout_yen": 220}],
                    "place": [
                        {"numbers": [3], "payout_yen": 120},
                        {"numbers": [12], "payout_yen": 170},
                        {"numbers": [4], "payout_yen": 160},
                    ],
                    "frame_quinella": [{"numbers": [2, 7], "payout_yen": 500}],
                    "quinella": [{"numbers": [3, 12], "payout_yen": 710}],
                    "wide": [{"numbers": [3, 12], "payout_yen": 300}],
                    "exacta": [{"numbers": [3, 12], "payout_yen": 1100}],
                    "trio": [{"numbers": [3, 4, 12], "payout_yen": 1800}],
                    "trifecta": [{"numbers": [3, 12, 4], "payout_yen": 4440}],
                },
                "result_status": "available",
                "payouts_status": "available",
                "cross_validation": {"review_required": False},
            }
        ],
    }

    got = subject.convert_jrdb_query_payload(source)

    assert got["status"] == "complete"
    assert got["source"]["web_used"] is False
    assert got["race_count"] == 1
    race = got["races"][0]
    assert [x["horse_no"] for x in race["top3"]] == [3, 12, 4]
    assert race["payouts"]["trifecta"] == [
        {"combination": [3, 12, 4], "payout_jpy": 4440}
    ]


def test_cross_validation_mismatch_fails_closed() -> None:
    source = {
        "status": "review_required",
        "query": {"date": "2026-10-04"},
        "provenance": {},
        "races": [
            {
                "race_date": "2026-10-04",
                "venue_name": "京都",
                "race_no": 12,
                "top3": [],
                "payouts": {},
                "result_status": "available",
                "payouts_status": "available",
                "cross_validation": {"review_required": True},
            }
        ],
    }
    got = subject.convert_jrdb_query_payload(source)
    assert got["status"] == "review_required"
    assert got["review_required_count"] == 1
