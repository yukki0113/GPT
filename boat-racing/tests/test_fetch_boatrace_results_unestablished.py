import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fetch_boatrace_results import (
    evaluate_section,
    official_url,
    parse_official_html,
    result_status,
    serialize_payouts,
)


def payout_row(ticket_type, boats, payout):
    numbers = "".join(
        f'<span class="numberSet1_number">{boat}</span>' for boat in boats
    )
    return (
        f"<tr><td>{ticket_type}</td><td>{numbers}</td>"
        f'<td><span class="is-payout1">{payout}円</span></td></tr>'
    )


def unestablished_row(ticket_type, payout="100"):
    return (
        f"<tr><td>{ticket_type}</td>"
        '<td><img alt="不成立"></td>'
        f'<td><span class="is-payout1">{payout}円</span></td></tr>'
    )


def partial_unestablished_html():
    finish_rows = "".join([
        "<tr><td>１</td><td>6</td><td>選手A</td></tr>",
        "<tr><td>２</td><td>5</td><td>選手B</td></tr>",
        "<tr><td>３</td><td>1</td><td>選手C</td></tr>",
        "<tr><td>４</td><td>3</td><td>選手D</td></tr>",
        "<tr><td>５</td><td>2</td><td>選手E</td></tr>",
        "<tr><td>６</td><td>4</td><td>選手F</td></tr>",
    ])
    payout_rows = "".join([
        payout_row("3連単", ["6", "5", "1"], "35,940"),
        payout_row("3連複", ["1", "5", "6"], "1,520"),
        payout_row("2連単", ["6", "5"], "7,670"),
        unestablished_row("2連複"),
        payout_row("拡連複", ["5", "6"], "2,210"),
        payout_row("", ["1", "6"], "290"),
        payout_row("", ["1", "5"], "870"),
        payout_row("単勝", ["6"], "1,390"),
        payout_row("複勝", ["6"], "1,200"),
        payout_row("", ["5"], "1,200"),
    ])
    return f"""
    <html><head><meta charset="utf-8"></head><body>
      <div class="heading2_area"><img alt="江戸川"></div>
      <div class="is-active2">9月18日</div>
      <div><a href="/owpc/pc/race/raceresult?rno=11&jcd=03&hd=20260918">11R</a></div>
      <table>
        <thead><tr><th>着</th><th>枠</th><th>ボートレーサー</th></tr></thead>
        <tbody>{finish_rows}</tbody>
      </table>
      <table>
        <thead><tr><th>勝式</th><th>組番</th><th>払戻金</th></tr></thead>
        <tbody>{payout_rows}</tbody>
      </table>
    </body></html>
    """.encode("utf-8")


class FetchBoatRaceResultsPartialUnestablishedTest(unittest.TestCase):
    def test_ticket_level_unestablished_does_not_invalidate_race(self):
        race_date = datetime(2026, 9, 18)
        url = official_url(race_date, "03", 11)
        result = parse_official_html(
            partial_unestablished_html(), "江戸川", race_date, 11, url
        )

        self.assertEqual(result_status(result), "取得成功")
        self.assertFalse(result.invalid)
        self.assertIn("2連複", result.unestablished_ticket_types)
        self.assertEqual(result.unestablished_payouts["2連複"], 100)
        self.assertEqual(serialize_payouts(result, "2連複"), ("不成立", "100"))

    def test_unestablished_ticket_refunds_only_that_ticket(self):
        race_date = datetime(2026, 9, 18)
        url = official_url(race_date, "03", 11)
        result = parse_official_html(
            partial_unestablished_html(), "江戸川", race_date, 11, url
        )

        evaluated = evaluate_section("2連複", "5=6", "1", result, 100)

        self.assertEqual(evaluated["planned"], 100)
        self.assertEqual(evaluated["refund"], 100)
        self.assertEqual(evaluated["net_investment"], 0)
        self.assertEqual(evaluated["hit"], "返還")
        self.assertEqual(evaluated["payout"], 0)

    def test_other_ticket_types_remain_settled_normally(self):
        race_date = datetime(2026, 9, 18)
        url = official_url(race_date, "03", 11)
        result = parse_official_html(
            partial_unestablished_html(), "江戸川", race_date, 11, url
        )

        evaluated = evaluate_section("2連単", "6→5", "1", result, 100)

        self.assertEqual(evaluated["refund"], 0)
        self.assertEqual(evaluated["hit"], "的中")
        self.assertEqual(evaluated["payout"], 7670)


if __name__ == "__main__":
    unittest.main()
