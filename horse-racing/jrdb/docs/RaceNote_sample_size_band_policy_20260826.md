# RaceNote sample size band PoC policy - 2026-08-26

RaceNoteのAnalysis Lite / Stats Mart enrichmentでは、`starts` が小さい統計の率をGPTが過大評価しないよう、母数の大きさを補助ラベルとして明示する。

初期PoCでは以下を採用する。

```text
0       -> none
1-19    -> small
20-49   -> moderate
50+     -> sufficient
```

JSONキーは `sample_size_band` とする。

## 意味

このラベルは統計的有意性、有効性、信頼区間を表すものではない。
単純に `starts` の件数帯を表す表示補助情報であり、`starts / wins / top3 / win_rate / top3_rate` の値自体は削除しない。

## 適用対象

`summary()` を通る以下の集計へ共通付与する。

- `historical_profile` の career / same_surface / same_distance / distance_ranges / same_venue
- `horses[].stats.sire` の完全一致距離とdistance_ranges
- `horses[].stats.jockey` の完全一致距離とdistance_ranges
- `race.race_trends.frame` の完全一致距離とdistance_ranges

## 判定方針

万葉Sのような希少距離では、`top3_rate=100.0` でも `starts=1` の可能性がある。率は保持したまま `sample_size_band=small` を併記し、GPTが母数を同時に読める構造とする。

距離レンジに広げても長距離条件ではsmallが残る場合があるため、距離レンジとsample size bandは別々の役割として扱う。
