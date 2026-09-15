import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fetch_boatrace_results import (
    FetchData,
    OfficialResult,
    expected_ordered_finish_bets,
    fill_result,
    official_url,
    parse_official_html,
    result_status,
    serialize_finish_order,
)


def payout_row(ticket_type, boats, payout):
    numbers = "".join(
        f'<span class="numberSet1_number">{boat}</span>' for boat in boats
    )
    return (
        f"<tr><td>{ticket_type}</td><td>{numbers}</td>"
        f'<td><span class="is-payout1">{payout}円</span></td></tr>'
    )


def heiwayima_0914_6r_html():
    finish_rows = "".join([
        "<tr><td>１</td><td>3</td><td>選手A</td></tr>",
        "<tr><td>２</td><td>6</td><td>選手B</td></tr>",
        "<tr><td>３</td><td>1</td><td>選手C</td></tr>",
        "<tr><td>３</td><td>2</td><td>選手D</td></tr>",
        "<tr><td>５</td><td>4</td><td>選手E</td></tr>",
        "<tr><td>６</td><td>5</td><td>選手F</td></tr>",
    ])
    payout_rows = "".join([
        payout_row("3連単", ["3", "6", "1"], "2,400"),
        payout_row("3連単", ["3", "6", "2"], "1,290"),
        payout_row("3連複", ["1", "3", "6"], "350"),
        payout_row("3連複", ["2", "3", "6"], "240"),
        payout_row("2連単", ["3", "6"], "820"),
        payout_row("2連複", ["3", "6"], "410"),
        payout_row("拡連複", ["3", "6"], "170"),
        payout_row("拡連複", ["1", "3"], "130"),
        payout_row("拡連複", ["1", "6"], "150"),
        payout_row("単勝", ["3"], "220"),
        payout_row("複勝", ["3"], "120"),
        payout_row("複勝", ["6"], "140"),
    ])
    return f"""
    <html><head><meta charset="utf-8"></head><body>
      <div class="heading2_area"><img alt="平和島"></div>
      <div class="is-active2">9月14日</div>
      <div><a href="/owpc/pc/race/raceresult?rno=6&jcd=04&hd=20260914">6R</a></div>
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


class FetchBoatRaceResultsDeadHeatTest(unittest.TestCase):
    def test_0914_heiwayima_third_place_dead_heat_is_success(self):
        race_date = datetime(2026, 9, 14)
        url = official_url(race_date, "04", 6)
        result = parse_official_html(
            heiwayima_0914_6r_html(), "平和島", race_date, 6, url
        )

        self.assertEqual(serialize_finish_order(result), "3-6-1=2-4-5")
        self.assertEqual(
            expected_ordered_finish_bets(result, "3連単"),
            {"3-6-1", "3-6-2"},
        )
        self.assertEqual(
            [row["combination"] for row in result.payouts["3連単"]],
            ["3-6-1", "3-6-2"],
        )
        self.assertEqual(result_status(result), "取得成功")

    def test_fill_result_keeps_multiple_dead_heat_payouts_and_hits(self):
        race_date = datetime(2026, 9, 14)
        url = official_url(race_date, "04", 6)
        result = parse_official_html(
            heiwayima_0914_6r_html(), "平和島", race_date, 6, url
        )
        row = {
            "日付": "2026-09-14",
            "会場": "平和島",
            "R": "6R",
            "判定": "A",
            "主推奨券種": "3連単",
            "主推奨買い目展開後": "3→6→1／3→6→2",
            "主推奨点数": "2",
            "保険券種": "",
            "保険買い目": "",
            "保険点数": "",
            "参考券種": "",
            "参考買い目": "",
        }
        output = {key: "" for key in [
            "日付", "会場", "R", "判定", "確定着順", "着順詳細",
            "返還艇", "欠場艇", "失格艇", "事故艇", "中止", "不成立",
            "備考", "HTTPステータス", "HTTP取得日時", "HTML_SHA256",
            "公式3連単", "公式3連単払戻", "公式3連複", "公式3連複払戻",
            "公式2連単", "公式2連単払戻", "公式2連複", "公式2連複払戻",
            "公式拡連複", "公式単勝", "公式複勝", "主推奨購入予定額",
            "主推奨返還額", "主推奨返還後投資額", "主推奨的中",
            "主推奨的中買い目", "主推奨払戻", "保険購入予定額",
            "保険返還額", "保険返還後投資額", "保険的中", "保険的中買い目",
            "保険払戻", "参考購入予定額", "参考返還額", "参考返還後投資額",
            "参考的中", "参考的中買い目", "参考払戻", "取得状態", "エラー内容",
        ]}
        fetched = FetchData(
            content=b"", url=url, fetched_at="2026-09-14T21:00:00+09:00",
            http_status=200, sha256="dummy", source="cache"
        )

        fill_result(output, row, fetched, result, SimpleNamespace(unit_stake=100))

        self.assertEqual(output["確定着順"], "3-6-1=2-4-5")
        self.assertEqual(output["公式3連単"], "3-6-1／3-6-2")
        self.assertEqual(output["公式3連単払戻"], "2400／1290")
        self.assertEqual(output["公式3連複"], "1=3=6／2=3=6")
        self.assertEqual(output["主推奨的中"], "的中")
        self.assertEqual(output["主推奨的中買い目"], "3-6-1／3-6-2")
        self.assertEqual(output["主推奨払戻"], "3690")
        self.assertEqual(output["取得状態"], "取得成功")
        self.assertEqual(output["エラー内容"], "")

    def test_first_place_dead_heat_generates_all_ordered_winners(self):
        result = OfficialResult(
            finish_rows=[
                {"rank": "1", "boat": "1"},
                {"rank": "1", "boat": "2"},
                {"rank": "3", "boat": "3"},
                {"rank": "4", "boat": "4"},
                {"rank": "5", "boat": "5"},
                {"rank": "6", "boat": "6"},
            ]
        )
        self.assertEqual(
            expected_ordered_finish_bets(result, "2連単"),
            {"1-2", "2-1"},
        )
        self.assertEqual(
            expected_ordered_finish_bets(result, "3連単"),
            {"1-2-3", "2-1-3"},
        )
        self.assertEqual(serialize_finish_order(result), "1=2-3-4-5-6")


if __name__ == "__main__":
    unittest.main()
