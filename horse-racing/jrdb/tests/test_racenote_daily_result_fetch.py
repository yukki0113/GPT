from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import racenote_daily_result_fetch as subject  # noqa: E402


HTML = '''<html><body>
<h3>2026/10/03</h3><h3>レース結果</h3><div>東京</div><div>京都</div>
<a href="/race/20261003/2/1">1R 未勝利</a>
<table><tr><th>着順</th><th>枠番</th><th>馬番</th><th>馬名</th></tr>
<tr><td>1</td><td>3</td><td>5</td><td>A</td></tr>
<tr><td>2</td><td>7</td><td>13</td><td>B</td></tr>
<tr><td>3</td><td>1</td><td>1</td><td>C</td></tr></table>
<table><tr><th>単勝</th><td>760円</td><th>馬単</th><td>1,490円</td></tr>
<tr><th>複勝</th><td>150円 110円 810円</td><th>ワイド</th><td>220円 3,110円 1,310円</td></tr>
<tr><th>枠連</th><td>280円</td><th>三連複</th><td>6,200円</td></tr>
<tr><th>馬連</th><td>310円</td><th>三連単</th><td>40,080円</td></tr></table>
<a href="/race/20261003/3/1">1R 未勝利</a>
<table><tr><th>着順</th><th>枠番</th><th>馬番</th><th>馬名</th></tr>
<tr><td>1</td><td>3</td><td>5</td><td>D</td></tr>
<tr><td>2</td><td>8</td><td>15</td><td>E</td></tr>
<tr><td>3</td><td>7</td><td>13</td><td>F</td></tr></table>
<table><tr><th>単勝</th><td>450円</td><th>馬単</th><td>2,650円</td></tr>
<tr><th>複勝</th><td>130円 130円 110円</td><th>ワイド</th><td>470円 200円 230円</td></tr>
<tr><th>枠連</th><td>770円</td><th>三連複</th><td>920円</td></tr>
<tr><th>馬連</th><td>1,340円</td><th>三連単</th><td>6,860円</td></tr></table>
<a href="/race/20261003/2/2">2R 未勝利</a>
<table><tr><th>着順</th><th>枠番</th><th>馬番</th><th>馬名</th></tr></table>
<table><tr><th>単勝</th><td></td><th>馬単</th><td></td></tr></table>
<a href="/race/20261003/3/2">2R 未勝利</a>
<table><tr><th>着順</th><th>枠番</th><th>馬番</th><th>馬名</th></tr></table>
<table><tr><th>単勝</th><td></td><th>馬単</th><td></td></tr></table>
</body></html>'''


def test_parse_daily_page_builds_top3_and_all_payout_combinations() -> None:
    payload = subject.parse_sponichi_html(HTML, date(2026, 10, 3))

    assert payload["race_count"] == 4
    assert payload["official_race_count"] == 2
    assert payload["pending_race_count"] == 2
    assert payload["review_required_race_count"] == 0

    tokyo = next(r for r in payload["races"] if r["venue"] == "東京" and r["race_no"] == 1)
    assert [row["horse_no"] for row in tokyo["top3"]] == [5, 13, 1]
    assert tokyo["payouts"]["win"] == [{"combination": [5], "payout_jpy": 760}]
    assert tokyo["payouts"]["place"][2] == {"combination": [1], "payout_jpy": 810}
    assert tokyo["payouts"]["quinella"] == [{"combination": [5, 13], "payout_jpy": 310}]
    assert tokyo["payouts"]["wide"][1] == {"combination": [1, 5], "payout_jpy": 3110}
    assert tokyo["payouts"]["exacta"] == [{"combination": [5, 13], "payout_jpy": 1490}]
    assert tokyo["payouts"]["trio"] == [{"combination": [1, 5, 13], "payout_jpy": 6200}]
    assert tokyo["payouts"]["trifecta"] == [{"combination": [5, 13, 1], "payout_jpy": 40080}]


def test_partial_payout_posting_stays_pending_instead_of_becoming_zero_return() -> None:
    partial = HTML.replace(
        '<tr><th>馬連</th><td>310円</td><th>三連単</th><td>40,080円</td></tr>',
        '<tr><th>馬連</th><td>310円</td><th>三連単</th><td></td></tr>',
        1,
    )
    payload = subject.parse_sponichi_html(partial, date(2026, 10, 3))
    tokyo = next(r for r in payload["races"] if r["venue"] == "東京" and r["race_no"] == 1)

    assert tokyo["status"] == "pending"
    assert "trifecta" in tokyo["pending_reason"]


def test_dead_heat_shape_fails_closed_for_manual_review() -> None:
    dead_heat = HTML.replace(
        '<tr><td>2</td><td>7</td><td>13</td><td>B</td></tr>',
        '<tr><td>1</td><td>7</td><td>13</td><td>B</td></tr>',
        1,
    )
    payload = subject.parse_sponichi_html(dead_heat, date(2026, 10, 3))
    tokyo = next(r for r in payload["races"] if r["venue"] == "東京" and r["race_no"] == 1)

    assert tokyo["status"] == "review_required"
    assert tokyo["warnings"]
