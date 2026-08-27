# JRDB PWA Fact Lite Builder v0.2

`build_jrdb_pwa_fact_lite.py` v0.2 は Analysis Lite から、スマホ PWA で自由な WHERE / GROUP BY 集計を行うための compact row-level SQLite を生成します。

## v0.2 additions

- `month` を fact へ保持し、月 From / To 検索を可能にする
- 距離は既存 `distance` を範囲検索で使用する
- `dim_race` を追加し、source Analysis に `race_name` がある場合はレース名を収録する
- `prev_distance_delta` を追加し、距離延長 / 同距離 / 短縮を派生可能にする
- `prev_class_code` を追加し、前走クラス集計を可能にする

## Compatibility

現行 Analysis Lite v1.2 には `race_name` がありません。その場合でも Fact Lite v0.2 は生成でき、月・距離範囲・前走距離差・前走クラスは利用できます。

`race_name` を持つ将来の Analysis を入力した場合は、同じ builder が自動的に `dim_race.race_name` を埋めます。PWA側は配布 manifest / SQLite内容からレース名検索可否を判定します。

## Previous-race derivation

Analysis の `prev_race_key_1` を同じ `fact_entry_result_lite` の race-level情報へ結合します。

### Distance change

`prev_distance_delta = current_distance - previous_distance`

- 正: 距離延長
- 0: 同距離
- 負: 距離短縮
- NULL: 前走レースをAnalysis内で解決できない

### Previous class code

`grade_code` を優先し、次に `race_condition_code` を分類します。

| code | label |
|---:|---|
| 1 | 新馬 |
| 2 | 未出走 |
| 3 | 未勝利 |
| 4 | 1勝 |
| 5 | 2勝 |
| 6 | 3勝 |
| 7 | オープン |
| 8 | L |
| 9 | G3 |
| 10 | G2 |
| 11 | G1 |
| 12 | その他重賞 |
| 13 | その他 |
| NULL | 前走不明 |

前走がrolling Analysisの対象外、地方・海外等でrace keyを解決できない場合は推測せずNULLとします。

## Schema

- `schema/jrdb_pwa_fact_lite_schema_v0_2.sql`
- fact grain: 1 race entry / row
- dictionaries: sire / broodmare sire / jockey / race

## Build

```bash
python src/build_jrdb_pwa_fact_lite.py \
  --analysis ./jrdb_analysis.sqlite \
  --db ./jrdb_pwa_fact_lite.sqlite
```

Builder は source / output row count equality、`PRAGMA integrity_check`、race count、race-name count、previous-distance/class populated rows、output size を検証します。
