import unittest

from validate_racenote_forecast_decision_trace import audit_turn, validate_record


def good_record(race_no=1, main="アルファ", second="ベータ"):
    return {
        "schema_version": "RaceNote-Forecast-Research-Record-0.2",
        "identity": {
            "target_date": "2026-06-01",
            "venue": "東京",
            "race_no": race_no,
            "race_key": f"k{race_no}",
        },
        "research": {
            "evaluation_mode": "BLINDED_HISTORICAL",
            "turn_id": "BTDAY-X",
            "logic_version": "RaceNote-Baseline-Reader-0.2",
        },
        "source": {"racenote_identity": f"rn-{race_no}"},
        "prediction": {
            "axis": {"horse_no": 1, "horse_name": main},
            "marks": {
                "main": {"horse_no": 1, "horse_name": main},
                "second": {"horse_no": 2, "horse_name": second},
                "third": {"horse_no": 3, "horse_name": "ガンマ"},
                "others": [],
            },
            "axis_comment": f"{main}は先行力と距離適性を評価し、{second}より位置取りの再現性を上に取った。",
            "concern": f"{main}は終いの甘さが残り、早仕掛けでは差される懸念がある。",
        },
        "decision_trace": {
            "race_thesis": "先行馬が少なく、東京ダートでも前で運べる再現性を最重要論点とした。",
            "decisive_factors": [
                {
                    "lane": "Pace",
                    "observation": "先行候補が少なくアルファが前を取れる構成",
                    "interpretation": "位置取りを確保しやすく能力を出し切りやすい",
                    "source_ref": "pace",
                },
                {
                    "lane": "RecentForm",
                    "observation": "前走は同距離で先行して最後まで大きく崩れていない",
                    "interpretation": "今回条件での再現性を支持する材料と見た",
                    "source_ref": "recent",
                },
            ],
            "main_vs_second": {
                "main": {"horse_no": 1, "horse_name": main},
                "second": {"horse_no": 2, "horse_name": second},
                "why_main_over_second": f"{main}は自力で前を取れる一方、{second}は差し届く展開依存が大きいため前者を上位にした。",
            },
            "strongest_counter": f"{main}は早めにプレッシャーを受けると終いが甘くなる点が最大の不安。",
            "downweighted_evidence": [
                {
                    "evidence": "調教評価の小差",
                    "reason_downweighted": "上位候補間の差が小さく単独の決定打にはしなかった",
                }
            ],
            "reversal_condition": f"前が競り合って差し有利になれば{second}がアルファを逆転する。",
        },
        "audit": {
            "created_at": "x",
            "frozen_at": "y",
            "prediction_hash": "z",
            "pre_result_guard": "PASS",
            "result_visible_at_freeze": False,
            "decision_trace_guard": "PASS",
        },
    }


class DecisionTraceValidatorTest(unittest.TestCase):
    def test_good_record(self):
        self.assertEqual(validate_record(good_record()), [])

    def test_requires_direct_comparison_names(self):
        r = good_record()
        r["decision_trace"]["main_vs_second"]["why_main_over_second"] = "先行できる方を上位にしたためこちらを本命とする。"
        errors = validate_record(r)
        self.assertTrue(any("must explicitly name ◎" in x for x in errors))

    def test_requires_race_specific_counter(self):
        r = good_record()
        r["decision_trace"]["strongest_counter"] = "展開次第で順位が変わる可能性がある。"
        errors = validate_record(r)
        self.assertTrue(any("strongest_counter must explicitly refer" in x for x in errors))

    def test_turn_duplicate_gate(self):
        rows = [good_record(i, main=f"アルファ{i}", second=f"ベータ{i}") for i in range(1, 11)]
        for r in rows:
            r["decision_trace"]["race_thesis"] = "先行馬が少なく、東京ダートでも前で運べる再現性を最重要論点とした。"
        out = audit_turn(rows)
        self.assertEqual(out["status"], "FAIL")
        self.assertTrue(any("race_thesis unique ratio too low" in x for x in out["errors"]))


if __name__ == "__main__":
    unittest.main()
