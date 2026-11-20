# BRDB going multi-lane discovery v0.6 candidate — 2026-11-20

**RESEARCH ONLY / NO DISPLAY, PREDICTION OR PRODUCTION AUTHORIZATION**

## Scope

JRDB Analysis v1.4 の同一履歴から、良・稍重・重・不良を分離し、対象馬ごとに父、母父、父系×母父系配合を同一surface・同一scopeで集計する。良を基準として稍重/重/不良をそれぞれ比較する。v0.5と同じく母数・複勝率差・Wilson 95%区間を用いるが、閾値は研究用トリアージであり適性判定ではない。

## Lanes

- sire: `sire_name`
- broodmare_sire: `broodmare_sire_name`
- pairing: `sire_line_code × broodmare_sire_line_code`
- relatives: v0.3 `relatives_condition` を別入力として接続。現行M7近親詳細は馬場状態別ではないため、親系統の馬場signalと近親の同条件実績を「並列観測」としてのみ結ぶ。近親が同じ馬場状態で好走したとは推定しない。

## Cross-lane rule

同一馬場状態で2レーン以上が同方向のselected observationを持つ場合、`MULTILANE_GOING_DIRECTION_ALIGNMENT` を出す。ただし父・母父・配合は履歴populationが重複し、配合は両親系統と構造的に従属するため `independent_support=false` を固定する。近親との接続も独立支持、因果、距離補完、適性の証拠に昇格させない。

## Source-real CI

公開CIではSHA固定済みAnalysis v1.4 2016–2026と対象PACIのみを使用し、父/母父/配合の実再演を行う。M7近親詳細はprivate研究入力のためpublic CIへ投入せず、近親レーンの実データ接続はprivate replay gateとして残す。Actions artifactは集計監査のみで、馬名・horse_id・父名・個別統計を出力しない。
