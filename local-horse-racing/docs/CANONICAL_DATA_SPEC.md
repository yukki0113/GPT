# NAR canonical data specification

## Purpose

NAR公式race ZIPの `racelist.csv` / `horselist.csv` / `payback.csv` を、バックテスト時に結果情報が特徴量へ混入しない形へ正規化する。

rawは不変原本、canonicalはrawから再生成可能な派生正本とする。バックテスト・特徴量生成はrawを直接参照しない。

## Field policy

raw fieldは `nar/canonical/field_catalog.py` で次の3区分へ分類する。

| availability_class | meaning | feature use |
| --- | --- | --- |
| `PRE_SAFE` | 発走前情報として利用し得る | stage制約を守って利用候補 |
| `PRE_ASOF_PENDING` | 発走前snapshot候補だが時点性を広期間検証中 | `PENDING` の間は利用禁止 |
| `POST_ONLY` | 結果・払戻等 | 特徴量利用禁止 |

pre-race情報のavailability stageは次を使う。

| stage | examples |
| --- | --- |
| `ENTRY` | 馬名、性齢、騎手、調教師、負担重量、距離、条件 |
| `RACE_DAY` | 天候、馬場 |
| `WEIGH_IN` | 馬体重、馬体重増減 |
| `POST` | 着順、タイム、人気、上がり、払戻 |

`horselist.人気` は結果確定前実測で不安定・placeholder的な値を確認しているため `POST_ONLY` とし、pre-race market featureとして扱わない。

## Canonical tables

### `pre_race`

race単位の発走前情報。

主な列:

- `race_id`
- `race_date`, `race_year`, `venue`, `race_no`
- `post_time`
- `race_type_name`, `race_name`, `prize_name_01..15`
- `surface`, `direction`, `distance_m`
- `weather`, `track_condition`
- `field_size`, `conditions`
- `prize_yen_1..5`
- `source_yyyymm`

`weather` / `track_condition` は `RACE_DAY`。entry-stage modelでは使用しない。

### `pre_runner`

runner単位の発走前情報。

主な列:

- `race_id`, `runner_id`, `horse_key`
- race key列
- `gate`, `cap_color`, `horse_no`
- `horse_name`, `sex`, `age`, `coat_color`, `birth_date`
- pedigree
- jockey / trainer / owner / breeder
- `assigned_weight_raw`, `assigned_weight`, `allowance_mark`
- `body_weight_raw`, `body_weight_kg`
- `body_weight_change_raw`, `body_weight_change_kg`

減量記号付き負担重量（例 `☆53`, `△52`, `▲51`）はrawを保持しつつ数値と記号へ分解する。

### `pre_runner_history_snapshot`

NARが当該出走行へ持たせている累積snapshotを隔離する。

- `jockey_record_raw`
- `overall_record_raw`
- `dirt_left_record_raw`
- `dirt_right_record_raw`
- `venue_record_raw`
- `venue_distance_record_raw`
- `best_time_raw`, `best_time_seconds`
- `best_time_good_raw`, `best_time_good_seconds`
- `leakage_status`

初期 `leakage_status` は常に `PENDING_VALIDATION`。このtableがpre側に置かれていることだけを理由にモデルへ渡さない。

### `post_race_result`

race結果側情報。

- `final_4f_raw`, `final_3f_raw`
- `furlong_time_01..15`
- `corner_name_01..08`
- `corner_order_01..08`

### `post_runner_result`

runner結果側情報。

- `finish_position_raw`, `finish_position`
- `finish_time_raw`, `finish_time_seconds`
- `margin`
- `final_3f_raw`, `final_3f_seconds`
- `popularity`

NARの `タイム` はMSSF形式として解析する。例: `591 -> 59.1 sec`, `1143 -> 74.3 sec`, `2045 -> 124.5 sec`。

### `post_payout`

payback 54列を券種long形式へ正規化する。

- `payback_row_no`
- `bet_type`
- `selection1..3`
- `payout_yen`
- `popularity`

券種は `WIN`, `PLACE`, `BRACKET_QUINELLA`, `BRACKET_EXACTA`, `QUINELLA`, `EXACTA`, `WIDE`, `TRIO`, `TRIFECTA`。

同着時に同一raceのpayback rowが複数存在し得るため、`race_id` 単独をprimary keyとしない。

### `control_race_status`

race結果の利用可否を結果欠損から分離する。

| status | model target | return target | rule |
| --- | --- | --- | --- |
| `NORMAL` | true | true | finishあり + paybackあり |
| `DATA_MISSING` | true | false | finishあり + paybackなし |
| `REFUNDED` | false | false | finishなし + selection空 + 払戻100円 |
| `CANCELLED` | false | false | finishなし + 非標準payback |
| `NO_RESULT` | false | false | finishなし + paybackなし |

出走取消・競走中止等で一部runnerのfinishが空欄でも、race自体に正常なfinish / paybackがある場合はraceを `NORMAL` とする。

## Canonical keys

- `race_id = YYYYMMDD:競馬場:RR`
- `runner_id = race_id:馬番`
- `horse_key = SHA256(馬名 + unit-separator + 生年月日 + unit-separator + 父馬名)` with prefix `narh:`

`horse_key` はNAR恒久IDではなく現段階のsurrogate。将来の完全名寄せIDとは区別する。

## As-of validation

`nar/canonical/leakage.py` はsnapshotを自動承認せず、evidence reportだけ生成する。

### 4値成績

`a-b-c-d` を `1着-2着-3着-その他` とみなし、前走snapshotから次走snapshotへの差分が前走結果1件分だけ増えるか確認する。

- `overall_record_raw`: horse単位
- `jockey_record_raw`: horse + jockey単位
- `venue_record_raw`: horse + venue単位
- `venue_distance_record_raw`: horse + venue + distance単位
- `dirt_left_record_raw`: horse時系列で前走がダート左なら結果分増加、それ以外は不変
- `dirt_right_record_raw`: horse時系列で前走がダート右なら結果分増加、それ以外は不変

### Best time

horse + venue + distance単位で、次走snapshotが `min(previous snapshot best, previous finish time)` と一致するか確認する。

`best_time_good_seconds` は前走馬場が `良` の場合のみ前走タイムを更新候補とする。

### Promotion rule

validatorの出力が良好でもfield catalogは自動更新しない。

`PENDING_VALIDATION -> VERIFIED_ASOF` 相当の昇格は、複数年を含む広期間auditを確認した後に明示的に行う。

## Parquet materialization

Project側はstaging CSVまでをNAR固有処理として生成し、Parquet writing / validationは共通 `tools/data-storage/` をimportする。

`nar/canonical/storage.py` が次のconfigを構成する。

- source: canonical staging CSV
- target: ZSTD Parquet
- partition: `race_year`
- key: table-specific canonical key
- validation: row count / schema / unique key / required non-null
- audit: machine-readable JSON

persistent `.duckdb` はcanonical正本にしない。DuckDBは共通toolでParquetを直接queryする。

## Staging

`nar.canonical.build` は公式月次race ZIPまたは年wrapper ZIPを入力できる。

生成staging:

~~~text
<staging>/
├─ pre_race.csv
├─ pre_runner.csv
├─ pre_runner_history_snapshot.csv
├─ post_race_result.csv
├─ post_runner_result.csv
├─ post_payout.csv
├─ control_race_status.csv
└─ control/
   ├─ field_catalog.json
   ├─ leakage_validation.json   # --validate-asof 時
   └─ build_summary.json
~~~

staging CSVは一時物であり長期正本ではない。

## Real-data smoke audit: 2016-01

2026-09にDriveへ保存した2016年race wrapper内のNAR公式 `201601` 月次ZIPでsmall real-data smokeを実施した。

row counts:

- pre_race: 1,108
- pre_runner: 10,911
- pre_runner_history_snapshot: 10,911
- post_race_result: 1,108
- post_runner_result: 10,911
- post_payout: 13,100
- control_race_status: 1,108

race status:

- NORMAL: 1,086
- REFUNDED: 22

as-of evidence:

| field | matched | mismatched | match rate |
| --- | ---: | ---: | ---: |
| overall_record_raw | 4,697 | 0 | 1.000 |
| jockey_record_raw | 3,101 | 0 | 1.000 |
| venue_record_raw | 4,155 | 0 | 1.000 |
| venue_distance_record_raw | 3,248 | 0 | 1.000 |
| dirt_left_record_raw | 3,603 | 0 | 1.000 |
| dirt_right_record_raw | 3,603 | 0 | 1.000 |
| best_time_seconds | 1,982 | 0 | 1.000 |
| best_time_good_seconds | 1,532 | 0 | 1.000 |

この1か月smokeはparser / splitter / validatorの整合性確認としては強いpositive evidenceだが、10年全体のas-of保証ではないため、snapshot fieldは引き続き `PENDING_VALIDATION` とする。
