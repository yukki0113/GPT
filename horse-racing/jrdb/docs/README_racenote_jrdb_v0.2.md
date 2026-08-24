# RaceNote JRDB変換 v0.2

JRDBの `PACIyyMMdd.zip` を直接入力し、前日情報だけをRaceNote JSONへ正規化します。

## 実行

```bash
python racenote_jrdb.py PACI260815.zip
python racenote_jrdb.py PACI260815.zip --race 札幌1
python racenote_jrdb.py PACI260815.zip --output ./output --format json
```

出力先は `<output>/RaceNote_YYYYMMDD/` です。

- `race_bundle_YYYYMMDD_競馬場nR.json` — 1レース1JSON
- `manifest.json` — 生成件数・会場別件数・警告
- `validation_report.json` — レコード数、結合率、固定長異常、未知コード等

## 対象ファイル

PACI内の `BAC / KYI / CHA / CYB / ZED / ZKB` をプレフィックスで検出します。
そのほかのPACIファイルは無視します。

- Parser: CP932のraw bytesをBYTE位置で固定長slice
- Normalizer: コードを日本語へ変換し、未知コードは警告へ記録
- Bundle Builder: KYIの前走1〜5キー順でZED/ZKBをLEFT JOIN

`ZED` は `SED`、`ZKB` は `SKB` の同一フォーマットとして実装しています。

## 安全性・欠損

- 出力は `data_phase: "pre_race"` 固定です。
- 対象レースの結果は参照せず、KYIの前走キーでリンクされた対象日より前のZEDだけを出力します。
- 単値欠損は `null`、配列欠損は `[]` です。
- 内部のrace key、result key、コード値はGPT向けJSONへ出しません。
- CHA/CYB/ZKBの欠損は許容し、検証報告に結合率を出します。

## 現時点の未解決・設計上の扱い

- JRDBコード表で意味が確認できない値は推測せず、対象フィールドを `null` または除外し、`validation_report.json` の `unknown_codes` に記録します。
- CYBの調教タイプ・コース種別・仕上指数変化は公式説明資料が必要なため、生コードをGPT JSONへ出していません。
- `pace.ranks` はKYIに対応する明示的な4分類順位がないため `null` としています（予測順位は `forecast_positions`）。
