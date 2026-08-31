# Eval全馬データ JRDB結果取込 — Chat運用手順

この手順は、Google Sheets正本 `Eval表集計・検証` の `全馬データ` へ、JRDB SED Rawから結果を追記するための標準Chat運用を定義する。

## 正本

Google Sheets:

```text
Eval表集計・検証
Spreadsheet ID: 1XBOYZrtJFLfY0Q3EmLfImJvughyXdAvdsLnmix8hgo0
対象タブ: 全馬データ
```

JRDB Raw:

```text
Google Drive上のSED保管フォルダ
日次: SEDyymmdd.zip
年次: SED_YYYY.zip
```

個別Raw File IDはGitへ固定せず、対象日とファイル名でDriveから解決する。

解析ロジック正本:

```text
horse-racing/jrdb/src/export_jrdb_eval_horse_results.py
horse-racing/jrdb/docs/README_export_jrdb_eval_horse_results.md
```

## 標準フロー

```text
ユーザー: 対象日を指定
  ↓
Chat: Google DriveのSEDフォルダを検索
  ↓
Chat: SEDyymmdd.zipをraw fileとして取得
  ↓
Git正本 export_jrdb_eval_horse_results.py
  ↓
1頭1行 result CSV + audit JSON
  ↓
Chat: Google Sheets「全馬データ」の対象日行を取得
  ↓
厳密キー照合 + 馬名監査
  ↓
正常行のみ H/J/K/M の必要セルを更新
  ↓
I列配列数式の再計算結果を確認
  ↓
更新後監査を報告
```

Google Drive Rawの取得とGoogle Sheets更新はChatのGoogle Drive / Sheetsネイティブ操作を使う。Raw ZIPや日次CSVをGitへcommitしない。

## 1. Raw解決

対象日 `YYYY-MM-DD` からファイル名を作る。

```text
SED + YYMMDD + .zip
```

例:

```text
2026-08-29 -> SED260829.zip
```

Drive上でSED保管フォルダを検索し、対象ファイル名が一意であることを確認してraw downloadする。

見つからない場合は別データで代替せず、`SED Raw未取得` として停止する。

## 2. Exporter実行

```bash
python horse-racing/jrdb/src/export_jrdb_eval_horse_results.py \
  --raw /tmp/SED260829.zip \
  --date 2026-08-29 \
  --output /tmp/eval_20260829_horse_results.csv \
  --audit-output /tmp/eval_20260829_horse_results.audit.json
```

正常条件:

```text
validation_status == success
duplicate_keys == 0
exported_rows > 0
```

`review_required_rows > 0` は日次全体を失敗にしない。該当馬だけ自動更新対象から外す。

## 3. Sheet対象行の取得

Google Sheets正本のメタデータを最初に読み、`全馬データ` の実 `sheetId` と列数・行数を確認する。

対象日の行だけを狭い範囲で取得する。全シートの無制限dumpは行わない。

現行列:

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

## 4. 結合

Sheetキー:

```text
開催日 + 場 + R + 馬番
```

JRDB CSVキー:

```text
race_date + venue_name + race_no + horse_no
```

日付は表示書式に依存せず実日付として正規化して比較する。

必須監査:

```text
input_target_rows
joined_rows
unmatched_sheet_rows
unmatched_jrdb_rows
duplicate_sheet_keys
duplicate_jrdb_keys
horse_name_mismatches
sheet_horse_name_blank_rows
review_required_rows
```

自動書込の必須条件:

```text
duplicate_sheet_keys == 0
duplicate_jrdb_keys == 0
horse_name_mismatches == 0
unmatched_sheet_rows == 0
```

`horse_name_mismatches` は、Sheet側とJRDB側の馬名が双方とも非空欄なのに一致しない行だけを数える。Sheet側馬名が空欄なら `sheet_horse_name_blank_rows` として警告監査し、完全キー一致を失敗扱いにしない。

馬名空欄を結果取込処理で補完してA～Gを変更してはいけない。馬名は照合用であり、非空欄同士の不一致時に推測結合しない。

`unmatched_jrdb_rows` は、Eval台帳側がJRDB全出走馬を収録していない運用では正常に発生し得るため、参考値とする。

## 5. 書込対象

### H 着順

```text
review_required == 0
  -> finish_position_eval を書く

review_required == 1
  -> 書かない
```

通常行は 1 / 2 / 3 / 4（4=4着以下）。

### I 3着内

**書かない。**

現行台帳は `I2` の配列数式でH列から自動計算する。

```text
H=1,2,3 -> ○
H=4     -> ×
H空欄    -> 空欄
```

I列への個別書込は配列数式を壊すため禁止する。

### J 複勝払戻(円)

```text
place_payout が非空欄 -> 数値を書込
place_payout が空欄   -> 空欄維持/既存結果更新時は空欄へ正規化
```

0円を非的中の意味で補完しない。

### K 最終複勝オッズ下限

```text
final_place_odds_lower が非空欄 -> 数値を書込
Raw空欄 -> 空欄
```

### L 最終複勝オッズ上限

**書かない。**

JRDB Raw上の正式な取得元が確認できるまで空欄維持。

### M 備考

通常行へ毎回冗長な文言を追加しない。

異常区分など監査情報が必要な行だけ、既存備考を壊さない形で追記候補とする。ただし `review_required=1` は原則として自動結果書込自体を保留し、ユーザーへ一覧報告する。

## 6. Sheets書込方法

対象行が連続している場合でも、A～GやI/Lを含む広い行全体を書き換えない。

書込セルだけをGoogle Sheets API `updateCells` 等で更新し、`userEnteredValue` のみを変更する。既存の表示書式・数式・validationは維持する。

更新直前に対象セルのlive状態を再読し、別更新が入っていないことを確認する。

## 7. 更新後監査

対象日について再読し、少なくとも以下を確認する。

```text
正常対象行のHが全件更新された
IがHに応じて自動再計算された
JがSED place_payoutと一致する
KがSED final_place_odds_lowerと一致する / Raw空欄なら空欄
Lは変更されていない
A～Gは変更されていない
review_required行は自動結果確定されていない
```

`レース分析` 等が `全馬データ` を参照する数式を持つ場合、対象日の主要集計がエラーになっていないことも確認する。

## 8. 再実行

同じ日付を再実行しても同じキーへ同じ値を設定するだけのidempotent運用とする。

既存H/J/Kに値がある場合は、書込前にJRDB値と比較する。

```text
同値 -> no-op
既存空欄 -> 書込
既存値とJRDB値が不一致 -> 自動上書きせず監査停止
```

これにより、別ソースによる過去転記を無条件に破壊しない。

## 9. 通常のユーザー依頼

例:

```text
8/29の結果を台帳に取り込んでください
```

この場合、ユーザーへSED ZIPや台帳ファイルの再添付を依頼せず、Drive正本を直接解決して上記フローを実行する。

複数日も同様に日付ごとにRawを解決し、1本の中間CSVへまとめるか日別に処理してから一括更新してよい。
