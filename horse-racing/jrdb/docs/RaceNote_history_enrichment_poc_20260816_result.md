# RaceNote Analysis / Stats Mart enrichment PoC result — 2026-08-16 札幌11R

対象: 2026-08-16 札幌11R 札幌記念 16頭

入力:
- 既存RaceNote 1レースbundle
- `jrdb_analysis_2016_2026YTD_20260823_v1_2.sqlite`
- `jrdb_stats_mart_2016_2026YTD_20260823_v1_1.sqlite`

## as-of

過去レース再現時の未来情報混入を避けるため、Statsは対象年を含む5暦年を基本窓とし、2022-2025はStats Mart、2026はAnalysis Liteを `race_date < 2026-08-16` でその場集計した。実馬場状態は事前未確定のため `all_conditions` 集約。

## 実行結果

| 案 | UTF-8 bytes | 現行比増分 | 増加率 | older_runs |
|---|---:|---:|---:|---|
| 現行bundle | 267,759 | - | - | PACI recent_runs 最大5 |
| 8走案 | 316,116 | +48,357 | +18.1% | 全16頭で追加3走 |
| 10走案 | 327,383 | +59,624 | +22.3% | 13頭5走、1頭4走、2頭3走 |

警告は両案とも0。

10走案の追加情報59,624 bytesの内訳概算:
- Analysis `older_runs` 最大5走: 約32KB
- `historical_profile` + sire/jockey stats + frame trends: 約28KB

## 実データ確認

例: オニャンコポン
- career: 32戦3勝 / top3 7 / top3率21.9%
- 芝: 32戦3勝 / top3 7
- 2000m: 12戦3勝 / top3 5 / top3率41.7%
- 札幌: 0戦
- 父（札幌芝2000m、2022-2026YTD as-of）: 14戦 / top3 3 / 21.4%
- 騎手（同条件）: 16戦1勝 / top3 3 / 18.8%

枠傾向も1～8枠について実値取得できた。

## PoC実装修正

初回実行ではRaceNoteの `surface="芝"` とAnalysis/Martの `track_type="1"` のコード体系差を正規化しておらず、same_surface / Mart統計が0件になった。PoC側へ `芝->1 / ダート->2 / 障害->3` の正規化を追加して再実行し解消した。

## 情報量評価

- Analysisの6走目以降はPACI詳細5走と重複せず、長期履歴の補助として有効。
- historical_profileは少量でcareer / 芝ダ / 同距離 / 同場を圧縮でき、費用対効果が高い。
- sire/jockey/frame statsは有用だが、札幌芝2000mまで条件を絞るとサンプルが小さい組み合わせも多い。札幌記念16頭ではsire/jockeyとも約半数が `starts < 20`。`starts`を必須表示し、率単独では渡さない。
- 10走案は8走案より約11KB増える。まずは8走案を本命候補とし、6～8走目で判断材料が十分かを実予想比較してから10走化を判断する。

## 現時点の推奨

初期統合候補:
- PACI `recent_runs`: 最大5走・詳細
- Analysis `older_runs`: 最大3走（合計最大8走）
- Analysis `historical_profile`: career / same_surface / same_distance / same_venue
- Stats Mart: sire / jockey / frame、5暦年窓、`starts/wins/top3/win_rate/top3_rate`
- track condition: 初期はall_conditions
- payout/回収率: 初期は付加しない

本番RaceNoteへの統合前に、別タイプのレース（若駒戦・ダート・短距離等）でも同じPoCを1～2レース実行して情報量と欠損率を確認する。
