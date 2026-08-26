# JRDB PWA Fact Lite Builder v0.1

`build_jrdb_pwa_fact_lite.py` は Analysis Lite v1.2 から、スマホ PWA で自由な WHERE / GROUP BY 集計を行うための compact row-level SQLite を生成する PoC builder です。

## Position

```text
Analysis Lite
  ├─> Stats Mart       # pre-aggregated acceleration cache
  └─> PWA Fact Lite    # flexible row-level aggregation
```

Stats Mart を置き換えることはまだ確定していません。Fact Lite v0.1 は iOS 実機で速度・メモリ・同期を検証するための PoC です。

## Source

- Analysis schema: `schema/jrdb_analysis_schema_v1_2.sql`
- Fact Lite schema: `schema/jrdb_pwa_fact_lite_schema_v0_1.sql`
- Builder: `src/build_jrdb_pwa_fact_lite.py`

## Grain

`fact_stats_entry` は 1 race entry / row。

Analysis から集計に不要な horse name / race key / previous key 等を落とし、繰り返し文字列の大きい次の項目を integer dictionary 化します。

- sire -> `dim_sire`
- broodmare sire -> `dim_bms`
- jockey -> `dim_jockey`

## Fact fields

- race_date_int
- year
- venue_code
- race_no
- track_type
- distance
- race_condition_code
- track_condition_code
- grade_code
- frame_no
- sex_code
- age
- sire_id
- bms_id
- sire_line_code
- bms_line_code
- jockey_id
- running_style
- distance_aptitude
- uptrend
- training_index
- final_win_popularity
- finish
- win_payout
- place_payout

## Index policy

v0.1 は index 過多による配布サイズ増加を避けます。

- `ix_pwa_fact_course(year, venue_code, track_type, distance, track_condition_code)`
- `ix_pwa_fact_date(race_date_int)`

sire / bms / jockey / popularity / style 個別 index は v0.1 では作りません。

実測では、それらを追加すると約25 MiB増える一方、代表的な course-specific aggregation は course index だけでも十分高速でした。

## Build

```bash
python src/build_jrdb_pwa_fact_lite.py \
  --analysis ./jrdb_analysis_2016_2026YTD_20260823_v1_2.sqlite \
  --db ./jrdb_pwa_fact_lite_2016_2026YTD_20260823_v0_1.sqlite
```

既存出力は上書きしません。

Builder は次を確認します。

- source exists
- `fact_entry_result_lite` exists
- source `PRAGMA integrity_check = ok`
- source / output row count equality
- output `PRAGMA integrity_check`
- period / dictionary counts / output size

最後に `VACUUM` して配布サイズを確定します。

## Prototype measurement

2026-08-26 に現行 Analysis Lite v1.2 を用いて同一設計の prototype を作成しました。

Source:

- file: `jrdb_analysis_2016_2026YTD_20260823_v1_2.sqlite`
- rows: 513,512
- size: 197,492,736 bytes
- integrity_check: ok

Prototype Fact Lite:

- rows: 513,512
- approximate size: **47.4 MiB**
- course + date indexes only

Desktop SQLite timing reference:

- 2017-2026 sire ranking: ~429 ms median
- 2017-2026 broodmare sire ranking: ~380 ms median
- Tokyo turf 1600 / good sire ranking: ~35 ms median
- Tokyo turf 1600 + popularity 1-3 + male + age 3 sire ranking: ~37 ms median

Desktop 値は採用判定ではありません。次段階で現行 PWA の OPFS / auto-sync 基盤へ Fact Lite を載せ、iOS Chrome 実機値を取ります。

## Why this PoC exists

軸別 Stats Mart を増やすだけなら容量増加は比較的小さい一方、age / sex / popularity / running style 等を他軸の filter として自由に組み合わせるには、それらを各 Mart grain へ追加する必要があります。

Fact Lite が実機で十分速ければ、約50 MiB級の単一 row-level DB で自由な cross-filter を維持できます。

詳細は `JRDB_PWA_Legacy_Feature_Inventory.md` を参照してください。
