# JRDB PWA Fact Lite Builder

`build_jrdb_pwa_fact_lite.py` は Analysis Lite から、スマホ PWA で自由な `WHERE / GROUP BY` 集計を行うための compact row-level SQLite を生成します。

現行builder/schema仕様は **v0.3** です。v0.2までの履歴仕様は `README_build_jrdb_pwa_fact_lite_v0_2.md` を参照してください。

## Position

```text
Analysis Lite
  ├─> Stats Mart       # 必要時の高速化補助
  └─> PWA Fact Lite    # 自由条件集計の主DB候補
```

2026-08-27 のiOS Chrome実機検証では、Fact Lite v0.1（約47.4 MiB）の初回読込は体感2〜3秒、全期間の種牡馬 / 母父 / 騎手集計は約310〜370ms、東京芝1600mでは約62〜65msでした。この結果から、自由条件集計は Fact Lite を主DBとし、Stats Mart は必要な重い処理だけ補助する方向を採用候補とします。

## Source / schema

- source: Analysis Lite v1.3 compatible
- current Fact Lite schema: `schema/jrdb_pwa_fact_lite_schema_v0_3.sql`
- builder: `src/build_jrdb_pwa_fact_lite.py`

v0.3ではAnalysis `fact_entry_result_lite.win5_leg_no` をそのままFact Lite `fact_stats_entry.win5_leg_no` へ引き継ぎます。値は `NULL` または `1..5` とし、PWAの「WIN5対象レースのみ」検索は `win5_leg_no IS NOT NULL` で絞り込みます。

`race_name` はAnalysis側に存在すれば `dim_race` へ収録し、存在しない場合も任意のrace-name lookup SQLiteで補完できます。

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

## v0.3 addition

- `win5_leg_no`
- PWA「WIN5対象レースのみ」filter support
- partial index `ix_pwa_fact_win5` for non-NULL WIN5 rows

### WIN5

Analysis v1.3のBAC由来 `win5_leg_no` を推測せず伝播します。

- `NULL`: WIN5対象外
- `1..5`: 当日のWIN5何レース目か

PWAはFact Lite v0.2 / v0.3の読み込み互換を持ちます。v0.2配布DBではWIN5 checkboxを無効化し、v0.3同期後に自動的に利用可能とします。

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
- `ix_pwa_fact_win5(win5_leg_no) WHERE win5_leg_no IS NOT NULL`

個別の sire / bms / jockey / popularity / style index は現時点では追加しません。

## Build

```bash
python src/build_jrdb_pwa_fact_lite.py \
  --analysis ./jrdb_analysis_v1_3.sqlite \
  --db ./jrdb_pwa_fact_lite.sqlite
```

Builder は source / output row count equality、必須table/column、`win5_leg_no` 値域、`PRAGMA integrity_check`、race count、race-name count、previous-distance/class populated rows、WIN5 populated rows、output size を確認します。

## Distribution transition

既存のFact Lite v0.2配布物はPWA側で読み込み互換を維持します。Analysis v1.3を入力として次回Fact Lite publishを行うとv0.3へ切り替わり、WIN5検索が有効になります。

直近のv0.2配布実績:

- rows: 513,512
- size: 62,230,528 bytes（約59.3 MiB）
- SHA-256: `b5ba7a645f134bec03538fc9d255fc30d626908af4ce939416cea8ac735cd29d`
- Release tag: `jrdb-pwa-fact-lite-current`

## Data policy

大容量Fact Lite SQLiteはGit管理しません。Gitにはschema / builder / workflow / docsだけを置き、生成物はRelease / Pages配布キャッシュとして扱います。
