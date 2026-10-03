from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import racenote_daily_settlement as subject  # noqa: E402


def forecast(main: int = 5, second: int = 13, third: int = 1) -> dict:
    return {
        "identity": {"target_date": "2026-10-03", "venue": "東京", "race_no": 1},
        "prediction": {
            "marks": {
                "main": {"horse_no": main, "horse_name": "A"},
                "second": {"horse_no": second, "horse_name": "B"},
                "third": {"horse_no": third, "horse_name": "C"},
                "others": [{"horse_no": 7, "horse_name": "D"}, {"horse_no": 9, "horse_name": "E"}],
            }
        },
    }


def results(status: str = "official") -> dict:
    return {
        "source": {"provider": "sponichi_keiba_web"},
        "races": [{
            "date": "2026-10-03", "venue": "東京", "race_no": 1, "status": status,
            "payouts": {
                "win": [{"combination": [5], "payout_jpy": 760}],
                "place": [{"combination": [5], "payout_jpy": 150}],
                "quinella": [{"combination": [5, 13], "payout_jpy": 310}],
                "exacta": [{"combination": [5, 13], "payout_jpy": 1490}],
                "trio": [{"combination": [1, 5, 13], "payout_jpy": 6200}],
                "trifecta": [{"combination": [5, 13, 1], "payout_jpy": 40080}],
            },
        }],
    }


def test_current_five_marks_build_24_fixed_100_yen_tickets() -> None:
    tickets = subject.build_tickets(forecast())
    counts = {code: sum(t.strategy == code for t in tickets) for code in subject.STRATEGIES}

    assert len(tickets) == 24
    assert counts == {
        "honmei_win": 1,
        "honmei_place": 1,
        "quinella_main": 2,
        "exacta_main": 2,
        "trio_flow": 6,
        "trifecta_flow": 12,
    }


def test_settlement_reports_requested_strategy_roi_and_top_payout() -> None:
    payload = subject.settle([forecast()], results(), top_n=3)
    by_code = {row["code"]: row for row in payload["strategies"]}

    assert by_code["honmei_win"]["stake_jpy"] == 100
    assert by_code["honmei_win"]["payout_jpy"] == 760
    assert by_code["honmei_win"]["return_rate_pct"] == 760.0
    assert by_code["honmei_place"]["payout_jpy"] == 150
    assert by_code["quinella_main"]["stake_jpy"] == 200
    assert by_code["quinella_main"]["payout_jpy"] == 310
    assert by_code["exacta_main"]["payout_jpy"] == 1490
    assert by_code["trio_flow"]["stake_jpy"] == 600
    assert by_code["trio_flow"]["payout_jpy"] == 6200
    assert by_code["trifecta_flow"]["stake_jpy"] == 1200
    assert by_code["trifecta_flow"]["payout_jpy"] == 40080
    assert by_code["trifecta_flow"]["top_payout_tickets"][0]["marks"] == "◎→○→▲"
    assert by_code["trifecta_flow"]["top_payout_tickets"][0]["ticket"] == "5→13→1"

    markdown = subject.render_markdown(payload, title_date="2026-10-03")
    assert "馬連 ◎－○▲" in markdown
    assert "40,080円" in markdown


def test_unordered_ticket_matching_keeps_mark_to_horse_display_order() -> None:
    record = forecast(main=13, second=5, third=1)
    ticket = next(
        t for t in subject.build_tickets(record)
        if t.strategy == "quinella_main" and t.marks == ("◎", "○")
    )

    assert ticket.horses == (13, 5)
    assert subject._ticket_text(ticket) == "13－5"
    race = results()["races"][0]
    assert subject.payout_for_ticket(ticket, race) == 310


def test_pending_race_is_not_counted_as_loss_or_stake() -> None:
    payload = subject.settle([forecast()], results(status="pending"))

    assert payload["settled_race_count"] == 0
    assert payload["pending_race_count"] == 1
    for row in payload["strategies"]:
        assert row["stake_jpy"] == 0
        assert row["payout_jpy"] == 0
        assert row["return_rate_pct"] is None
