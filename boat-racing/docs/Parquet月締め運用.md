# Parquet月締め運用

## 正本と責務

- 当月の日次作業正本: Google Drive `data/<family>/` のCSV。
- 月締め後の長期保存正本: `Parquet + YYYYMM__parquet_manifest.json`。
- 分析エンジン: DuckDB。`.duckdb` は再生成可能な分析キャッシュであり長期正本ではない。
- family固定値: `predictions` / `prediction-rationales` / `results` / `sales-selection`。

## 保存契約

各monthは family × schema hash の単位でZSTD level 3 Parquetにする。

`<family>__<YYYYMM>__schema_<hash>.parquet`

schema hashは列名と列順から決定論的に算出する。異なるschemaをNULL補完・列変換して統合しない。全元CSV列はUTF-8 stringで保持し、`01`、`0.10`、日付文字列、空文字、`NA`を型推論・正規化しない。統合Parquetには元CSVの相対パスを持つ必須string列`source_csv`を追加する。

## 月締め順序（削除先行禁止）

1. 対象月CSV一覧と欠落を確認する。
2. schema分類・hash算出を行う。
3. `src/monthly_parquet_archive.py` でParquetと暫定manifestを生成する。
4. Parquet再読込で列名・列順・行・全セル値・UTF-8・空文字・string型・`source_csv`を検証する。
5. 予想/結果/販売選別は `日付+会場+R`、根拠明細は `日付+会場+R+艇番` の集合・重複・欠落を検証する。
6. `data/<family>/archive/`へParquet、`data/manifests/`へmanifestをuploadする。
7. Drive上の存在を確認し、Parquetを再取得してSHA-256・Parquet読込を確認する。
8. manifestにupload/retrieval結果を反映して再uploadする。
9. すべてPASSの`cleanup_ready=true`だけが、対象月の旧日次CSVと月次ZIPを削除できる。

いずれかがFAIL/PENDINGなら旧CSV/ZIPを削除しない。

## 実装コマンド

入力はDriveから回収した、読み取り専用の`<input>/<family>/*.csv`スナップショットとする。

```bash
python boat-racing/src/monthly_parquet_archive.py \
  --input-root ./month-input \
  --output-root ./month-output \
  --month YYYYMM \
  --generation 1
```

このmoduleはDrive I/Oおよび削除を持たない。Chat/Workはmanifestのcleanup gateを完全に満たしたことを確認してから、明示された月のDrive原本だけを削除する。

## 修正版

Parquetを行単位で編集しない。修正版CSVを含む対象月ソース全体から該当schema群を再生成し、`generation`を増やして`supersedes_generation`をmanifestに記録する。新generationのupload・再取得・Lossless Guardが成功してから旧generationを置換する。

## 月の状態

- `open`: 当月CSV作業中。Parquet化・削除しない。
- `closing`: 結果回収、修正版、欠落確認中。Parquet作成は可、cleanup不可。
- `closed`: manifest/remote verificationまで成功。cleanup可能。
