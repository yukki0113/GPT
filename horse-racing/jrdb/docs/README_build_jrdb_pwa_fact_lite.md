# JRDB PWA Fact Lite Builder

`build_jrdb_pwa_fact_lite.py` は Analysis Lite から、スマホ PWA で自由な `WHERE / GROUP BY` 集計を行うための compact row-level SQLite を生成します。

現行仕様は **v0.2** です。詳細な追加仕様は `README_build_jrdb_pwa_fact_lite_v0_2.md` を参照してください。

## Position

```text
Analysis Lite
  ├─> Stats Mart       # 必要時の高速化補助
  └─> PWA Fact Lite    # 自由条件集計の主DB候補
```

2026-08-27 のiOS Chrome実機検証では、Fact Lite v0.1（約47.4 MiB）の初回読込は体感2〜3秒、全期間の種牡馬 / 母父 / 騎手集計は約310〜370ms、東京芝1600mでは約62〜65msでした。この結果から、自由条件集計は Fact Lite を主DBとし、Stats Mart は必要な重い処理だけ補助する方向を採用候補とします。

## Source / schema

- source: Analysis Lite v1.2 compatible
- current Fact Lite schema: `schema/jrdb_pwa_fact_lite_schema_v0_2.sql`
- builder: `src/build_jrdb_pwa_fact_lite.py`

現行 Analysis Lite v1.2 には `race_name` がないため、v0.2 は race name 列がなくても生成可能です。将来 source Analysis に `race_name` が追加された場合、同じbuilderが `dim_race` へ自動収録します。

## Grain

`fact_stats_entry` は 1 race entry / row。

繰り返し文字列は integer dictionary 化します。

- sire -> `dim_sire`
- broodmare sire -> `dim_bms`
- jockey -> `dim_jockey`
- race key / race name -> `dim_race`

## v0.2 additions

- `month`
- distance From / To filter support
- `dim_race` for race-name partial search
- `prev_distance_delta`
- `prev_class_code`

### Previous distance

`prev_distance_delta = current_distance - previous_distance`

- positive: 距離延長
- zero: 同距離
- negative: 距離短縮
- NULL: 前走不明

### Previous class

`prev_race_key_1` で同一Analysis内の前走レースを解決し、`grade_code` を優先して `race_condition_code` を分類します。

- 新馬
- 未出走
- 未勝利
- 1勝
- 2勝
- 3勝
- オープン
- L
- G3
- G2
- G1
- その他重賞
- その他
- 前走不明

Analysis期間外・地方・海外等で前走レースを解決できない場合は推測せずNULLとします。

## Index policy

配布サイズ増加を避け、利用頻度の高い絞り込みだけにindexを置きます。

- `ix_pwa_fact_course(year, month, venue_code, track_type, distance, track_condition_code)`
- `ix_pwa_fact_date(race_date_int)`
- `ix_pwa_fact_race(race_id)`

個別の sire / bms / jockey / popularity / style index は現時点では追加しません。

## Build

```bash
python src/build_jrdb_pwa_fact_lite.py \
  --analysis ./jrdb_analysis_2016_2026YTD_20260823_v1_2.sqlite \
  --db ./jrdb_pwa_fact_lite.sqlite
```

Builder は source / output row count equality、必須table/column、`PRAGMA integrity_check`、race count、race-name count、previous-distance/class populated rows、output size を確認します。

## Current v0.2 distribution

Current Analysis Lite v1.2から生成した初回v0.2配布物:

- rows: 513,512
- size: 59,449,344 bytes（約56.7 MiB）
- SHA-256: `7682358bc511463cfc22f117afc6859e07cf75783adb3f732ac67f4cc08672eb`
- Release tag: `jrdb-pwa-fact-lite-current`
- race-name search: source Analysis v1.2 に `race_name` がないため未有効

## Data policy

大容量Fact Lite SQLiteはGit管理しません。Gitにはschema / builder / workflow / docsだけを置き、生成物はRelease / Pages配布キャッシュとして扱います。
