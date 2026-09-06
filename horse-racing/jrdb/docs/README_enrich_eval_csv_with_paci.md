# Eval OCR CSV × JRDB PACI 事前エンリッチ

`src/enrich_eval_csv_with_paci.py` は、Eval表画像OCRの出力CSVへ、開催前に取得したJRDB `PACIyymmdd.zip` の正式馬名・レース条件・馬単位の事前情報を付与する日次用CLIです。

## 1. 目的

```text
Eval表画像
  -> Eval OCR 5列CSV
  -> enrich_eval_csv_with_paci.py
  -> PACI事前エンリッチCSV
  -> 当日分析 / 候補選定
```

このモジュールは **PACI ZIPを正本入力** とし、Analysis Lite / Core SQLite / SEDを必要としません。

開催後にしか確定しない着順、確定人気、確定オッズ、確定馬場状態、払戻等は出力しません。

## 2. 配置と既存ロジック再利用

```text
horse-racing/jrdb/src/enrich_eval_csv_with_paci.py
```

既存実装を再利用します。

- BAC: `export_jrdb_eval_race_conditions.py::parse_bac_record_full`
- 表示ラベル: `export_jrdb_eval_dataset.py::add_labels`
- KYI: `jrdb_raw.py::Parser.kyi`
- PACI固定長分割: `jrdb_raw.py::read_fixed_records`

固定長位置やコード定義をこのモジュールへ重複実装しません。

## 3. 入力

### Eval OCR CSV

正式契約は5列です。

```csv
date,venue,race_no,horse_no,eval
2026-08-29,札幌,1,3,91
2026-08-29,札幌,1,7,84
```

必須列:

```text
date
venue
race_no
horse_no
eval
```

`date` は `YYYY-MM-DD` / `YYYYMMDD` を許可します。

`venue` はJRA場名または01～10の場コードを許可します。

```text
札幌 / 01
函館 / 02
福島 / 03
新潟 / 04
東京 / 05
中山 / 06
中京 / 07
京都 / 08
阪神 / 09
小倉 / 10
```

旧移行CSVの

```text
date,venue,race_no,horse_no,horse_name_ocr,eval
```

も読み込めます。`horse_name_ocr` は結合にも出力にも使用せず、JRDB KYIの `horse_name` を正式馬名として出力します。

### JRDB PACI

```text
PACIyymmdd.zip
```

このモジュールが読むPACI内TYPEは以下だけです。

```text
BAC
KYI
```

PACI内に他TYPEが存在しても、このCLIは結果系TYPEを読みません。

## 4. 結合キー

馬名では結合しません。

内部でEval側の場名をJRDB場コードへ正規化し、以下4項目だけで結合します。

```text
normalized_date + venue_code + race_no + horse_no
```

馬名OCRの一致度などによる推測補完は行いません。

## 5. 使用方法

JRDBリポジトリ内から:

```bash
python horse-racing/jrdb/src/enrich_eval_csv_with_paci.py \
  --eval-csv /path/to/eval_ocr_20260829.csv \
  --paci /path/to/PACI260829.zip \
  --output /path/to/eval_20260829_enriched.csv
```

未結合をエラー扱いにする日次運用:

```bash
python horse-racing/jrdb/src/enrich_eval_csv_with_paci.py \
  --eval-csv /path/to/eval_ocr_20260829.csv \
  --paci /path/to/PACI260829.zip \
  --output /path/to/eval_20260829_enriched.csv \
  --audit-json /path/to/eval_20260829_enriched.audit.json \
  --fail-on-unmatched
```

## 6. 別プロジェクト / 別スレッドからの実行

カレントディレクトリはJRDBプロジェクトである必要はありません。

Git正本のJRDBリポジトリを取得済みであれば、スクリプトを絶対パス指定して実行できます。

```bash
python /path/to/GPT/horse-racing/jrdb/src/enrich_eval_csv_with_paci.py \
  --eval-csv /other-project/input/eval_ocr.csv \
  --paci /data/jrdb/PACI260829.zip \
  --output /other-project/output/eval_enriched.csv \
  --audit-json /other-project/output/eval_enriched.audit.json
```

Python実行時にスクリプト自身の `src` ディレクトリがimport pathになるため、別プロジェクト側へJRDB Pythonファイルをコピーする必要はありません。

外部プロジェクト側が知る必要のある契約は次だけです。

```text
入力1: Eval OCR 5列CSV
入力2: PACIyymmdd.zip
出力 : UTF-8 BOM付き、1頭1行のエンリッチCSV
結合 : date + venue + race_no + horse_no
```

## 7. 出力列

### Eval OCR由来

先頭5列を保持します。

```text
date
venue
race_no
horse_no
eval
```

### 結合監査

```text
venue_code
join_status
```

`join_status` は `MATCHED` / `UNMATCHED` です。

### KYI由来

```text
race_key
horse_name
frame_no
jockey_name
carried_weight
running_style
running_style_label
distance_aptitude
distance_aptitude_label
uptrend
uptrend_label
training_index
prev_result_key_1
prev_race_key_1
```

`carried_weight` はKYIの0.1kg単位値をkgへ変換した値です。

| 出力列 | PACI TYPE | 既存parser項目 |
|---|---|---|
| `horse_name` | KYI | `horse_name` |
| `frame_no` | KYI | `frame_no` |
| `jockey_name` | KYI | `jockey` |
| `carried_weight` | KYI | `carried_weight_tenths / 10` |
| `running_style` | KYI | `running_style_code` |
| `distance_aptitude` | KYI | `distance_fit_code` |
| `uptrend` | KYI | `improvement_code` |
| `training_index` | KYI | `training_index` |
| `prev_result_key_1` | KYI | `previous[0].result_key` |
| `prev_race_key_1` | KYI | `previous[0].race_key_raw` |

### BAC由来

```text
race_name
race_type_code
race_type_label
race_condition_code
class_label
grade_code
grade_label
track_type
track_label
distance
declared_field_size
race_symbol_code
sex_condition_label
is_filly_only
weight_condition_code
weight_condition_label
turn_direction_code
turn_direction_label
inner_outer_code
inner_outer_label
course_code
course_label
event_region_code
```

BAC固定長解析と表示ラベルは既存Eval Raw Exporterの共通ロジックを使用します。

## 8. 事前情報 / 事後情報の境界

このCSVは開催前分析用です。

使用するもの:

```text
PACI BAC
PACI KYI
```

使用しないもの:

```text
SED
対象レース着順
確定人気
確定オッズ
確定馬場状態
払戻
対象レース通過順
対象レース結果指数
```

KYIに含まれる事前評価・事前調教指数・前走参照キーは利用可能です。

前走キーは過去情報へ将来拡張するための参照値であり、このv1.0では別の履歴データソースを引いて前走距離等まで展開しません。

## 9. 馬名正規化

正式馬名は次の手順だけで決定します。

```text
date + venue + race_no + horse_no
        ↓
PACI KYI一致
        ↓
horse_name
```

`horse_name_ocr` の文字列一致、類似度判定、表記揺れ推測、手動補完は行いません。

## 10. 監査

正常実行時にstdoutへ以下を出します。

```text
eval_input_races
eval_input_horses
paci_target_races
paci_target_horses
joined_horses
unmatched_horses
duplicate_eval_keys
duplicate_paci_keys
duplicate_keys
race_headcount_mismatches
```

`--audit-json` を指定すると、同じsummaryに加えて `unmatched_keys` / `headcount_mismatches` の詳細をJSONへ保存します。

### 未結合

未結合行も出力CSVから落としません。`join_status=UNMATCHED` としてEval 5列を保持し、JRDB列を空欄にします。

日次処理で未結合を許可したくない場合は `--fail-on-unmatched` を指定してください。

### 重複キー

EvalまたはPACIの馬単位結合キーが重複した場合、推測で片方を採用せずエラー終了します。

### レース頭数

レース単位で以下を比較します。

```text
Eval入力のユニーク馬数
PACI KYIの対象馬数
BAC declared_field_size
```

差があれば `race_headcount_mismatches` として監査します。これは警告指標であり、デフォルトでは出力自体は継続します。

## 11. 依存関係

外部pip依存はありません。

Python標準ライブラリと、同じJRDB Git正本内の既存moduleだけを使います。Analysis Lite / Core SQLiteは不要です。

## 12. テスト

```bash
cd horse-racing/jrdb
python -m unittest tests/test_enrich_eval_csv_with_paci.py -v
```

検証対象:

```text
5列Eval CSV正常結合
旧6列CSV互換
JRDB正式馬名付与
BACレース条件付与
斤量・騎手・枠番等のKYI付与
存在しない馬番の未結合監査
Eval重複キー拒否
PACI重複キー拒否
レース頭数不一致監査
```

## 13. 日次運用の推奨形

```text
1. Eval画像をOCRして5列CSV生成
2. 開催日のPACIyymmdd.zipを用意
3. 本CLIを --fail-on-unmatched 付きで実行
4. audit summaryが
   unmatched_horses=0
   duplicate_keys=0
   race_headcount_mismatches=0
   であることを確認
5. enriched CSVを当日分析へ渡す
6. 開催後の結果付与は別工程で行う
```

この境界により、開催前CSVへ結果情報が混入することを防ぎます。
