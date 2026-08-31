# JRDB SED -> Eval 全馬データ結果Exporter

`src/export_jrdb_eval_horse_results.py` は、JRDB SED RawからGoogle Sheets正本 `Eval表集計・検証` の `全馬データ` へ結果を取り込むための **1レース×1頭** 中間CSVと監査JSONを生成する。

Analysis Lite / Core SQLiteは中間入力にせず、SED Rawを直接読む。Raw探索・ZIP/TXT読込は既存 `export_jrdb_eval_dataset.py` の共通処理を再利用する。

## 入力

対応Raw:

```text
SEDyymmdd.zip
SED_YYYY.zip
SEDyymmdd.txt
```

上記を含むディレクトリも `--raw` で指定できる。

通常のChat運用では、Google Drive上の `SED` フォルダを検索し、対象日の `SEDyymmdd.zip` を取得してローカル作業領域へ置いてからExporterへ渡す。変動し得る個別Drive File IDはGitへ固定しない。

## 出力CSV

```text
race_date
venue_code
venue_name
race_no
horse_no
horse_name
blood_registration_no
finish_position_raw
finish_position_eval
abnormality_code
abnormality_label
review_required
review_reason
in_top3
place_payout
final_place_odds_lower
final_place_odds_upper
source_kind
source_file
source_member
source_record_no
```

外部結合キー:

```text
race_date + venue_code + race_no + horse_no
```

馬名は照合用であり、表記差による推測結合には使用しない。

## SED項目

固定長仕様の主な使用位置（仕様書上の相対位置は1始まり、Python offsetは0始まり）:

| 項目 | 仕様相対 | BYTE | Python offset |
|---|---:|---:|---:|
| 場コード | 1 | 2 | 0 |
| R | 7 | 2 | 6 |
| 馬番 | 9 | 2 | 8 |
| 血統登録番号 | 11 | 8 | 10 |
| 年月日 | 19 | 8 | 18 |
| 馬名 | 27 | 36 | 26 |
| 着順 | 141 | 2 | 140 |
| 異常区分 | 143 | 1 | 142 |
| 確定複勝オッズ下 | 291 | 6 | 290 |
| 複勝払戻 | 349 | 7 | 348 |

`splitlines()` 後のSEDレコード本体は改行2 BYTEを除く374 BYTEとして検証する。

## 台帳用着順

異常区分 `0` の通常完走馬だけを自動派生する。

```text
SED着順 1 -> finish_position_eval = 1
SED着順 2 -> finish_position_eval = 2
SED着順 3 -> finish_position_eval = 3
SED着順 4以上 -> finish_position_eval = 4
```

`in_top3` は通常行についてだけ、1～3=`○`、4=`×` とする。

異常区分:

```text
0 異常なし
1 取消
2 除外
3 中止
4 失格
5 降着
6 再騎乗
```

`1～6` は通常4着以下へ潰さず、次の形で保留する。

```text
finish_position_raw  = SED生値を保持
finish_position_eval = 空欄
in_top3              = 空欄
review_required      = 1
review_reason        = 異常区分名を記録
```

Google Sheets更新側は `review_required=1` の行を自動更新せず、監査対象として報告する。

## 複勝払戻

`place_payout` はSEDの馬単位 `複勝` 払戻をそのまま使用する。Rawが空欄なら空欄を維持する。

複勝は出走頭数により払戻対象着順が変わるため、`finish_position_eval <= 3` を理由に払戻を推測生成しない。

## 最終複勝オッズ

`final_place_odds_lower` はSED `確定複勝オッズ下` を使用する。ただしRawが空欄なら空欄を維持する。

現行SED仕様では正式な `確定複勝オッズ上` の取得元を確認できていないため、`final_place_odds_upper` は常に空欄とする。払戻等から逆算しない。

## CLI

単日:

```bash
python horse-racing/jrdb/src/export_jrdb_eval_horse_results.py \
  --raw /path/to/SED260829.zip \
  --date 2026-08-29 \
  --output /tmp/eval_20260829_horse_results.csv \
  --audit-output /tmp/eval_20260829_horse_results.audit.json
```

複数日:

```bash
python horse-racing/jrdb/src/export_jrdb_eval_horse_results.py \
  --raw /path/to/raw-dir \
  --date 2026-08-29 \
  --date 2026-08-30 \
  --output /tmp/eval_20260829_20260830_horse_results.csv
```

期間指定:

```bash
python horse-racing/jrdb/src/export_jrdb_eval_horse_results.py \
  --raw /path/to/SED_2025.zip \
  --start-date 2025-08-01 \
  --end-date 2025-08-31 \
  --output /tmp/eval_202508_horse_results.csv
```

既定ではJRA場コード `01～10` だけを出力する。地方・海外を含める場合のみ `--include-non-jra` を明示する。

異常区分が1件でもあればCLIを失敗扱いにしたい検証時は `--fail-on-review-required` を付ける。通常の日次運用では異常行を監査対象としてCSVへ残し、正常行の取込まで止めない。

## audit JSON

最低限、以下を記録する。

```text
validation_status
source_files_discovered
sed_records_read
selected_records
exported_rows
duplicate_keys
identical_duplicates_collapsed
review_required_rows
abnormality_counts
final_place_odds_lower_blank_rows
place_payout_nonblank_rows
date_counts
output_sha256
```

同一キーで内容が一致するRaw重複はcollapseする。内容が異なる同一キーはエラーで停止する。

## Google Sheets更新契約

対象正本:

```text
Eval表集計・検証
全馬データ
```

列契約:

```text
A 開催日
B 場
C R
D 馬番
E 馬名
F Eval馬券内率(%)
G Eval順位
H 着順
I 3着内
J 複勝払戻(円)
K 最終複勝オッズ下限
L 最終複勝オッズ上限
M 備考
```

Chat側の通常書込対象:

```text
H <- finish_position_eval
J <- place_payout
K <- final_place_odds_lower（Raw非空欄時のみ）
M <- 必要な監査情報
```

**I列は書き込まない。** 現行台帳では `I2` の配列数式がH列から `○/×` を自動算出しているため、H更新後の計算結果を確認する。

**L列は書き込まない。** 正式なJRDB取得元が確認できるまで空欄を維持する。

A～Gは結果取込処理で変更しない。

## Sheets更新前の監査

対象日のSheet行とCSVを次のキーで厳密結合する。

```text
開催日 + 場 + R + 馬番
```

場は `venue_code -> venue_name` の正式対応を使う。

必須確認:

```text
duplicate_sheet_keys == 0
duplicate_jrdb_keys == 0
horse_name_mismatches == 0
unmatched_sheet_rows == 0
```

`unmatched_jrdb_rows` は、Sheet側がEval対象範囲だけの場合は正常に発生し得るため、参考監査とする。

馬名不一致を理由に別馬へ推測結合してはいけない。

## 2026-08-29 実データ試験

Google Drive正本 `SED260829.zip` を使った初期試験:

```text
SED rows read:                  494
selected/exported rows:         494 / 494
duplicate keys:                 0
normal rows:                    489
review_required rows:           5
  abnormality 2 (除外):         4
  abnormality 3 (中止):         1
place_payout nonblank:          108
final_place_odds_lower nonblank: 0
validation_status:              success
```

異常5頭はいずれもSED着順生値 `00` で、通常の `4=4着以下` へ丸めない設計が実データでも確認できた。
