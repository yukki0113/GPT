# JRDB Normalized Warehouse v1 運用手順

## 範囲

この資産は凍結済み `00_raw` のJRDB固定長ZIPを、family × yearのZSTD Parquetへ正規化するためのものです。PACI、consumer切替、PWA、Raw削除は含みません。

固定長の解釈は `src/jrdb_raw.py` のみが担います。WarehouseビルダーはそのParser出力をflattenし、Raw provenanceを付与します。

## 依存

Parquet生成・DuckDBによる再読込監査は共通 `tools/data-storage` を使用します。実行環境には同モジュールの依存を導入します。

```bash
python -m pip install -r tools/data-storage/requirements.txt
```

## ローカル生成

archive指定はinventoryで確定したfamily/yearだけを使用します。同じfamily/yearに複数の年次・日次ZIPがある場合は、同じfamily/yearとして複数指定します。

```bash
python horse-racing/jrdb/src/build_jrdb_normalized_warehouse.py \
  --archive BAC:2025:/data/00_raw/BAC/BAC_2025.zip \
  --archive KYI:2025:/data/00_raw/KYI/KYI_2025.zip \
  --output-root /data/warehouse/jrdb/v1 \
  --generation-id jrdb-warehouse-v1-20260918 \
  --source-git-commit <main_commit>
```

出力は以下です。

- `objects/<relation>/year=<YYYY>/<sha256>.parquet`
- `generations/<generation_id>/manifest.json`
- `generations/<generation_id>/audit.json`

HJCは `hjc_race` と `hjc_payout` の2 relationです。`hjc_payout`はblank/zeroを含む36 slotすべてを保持します。

## Gate

ビルダーは固定長不正、canonical key重複、key/provenance欠損で停止します。`current.json`は生成処理では一切更新しません。

実データの正本公開は、次の順序でのみ行います。

1. inventory確定
2. 小規模pilotの生成・監査
3. Full Build
4. Drive upload
5. Drive再取得後のSHA-256・サイズ・Parquet再読込検証
6. `current.json`更新

Raw ZIPおよびRawフォルダは削除・置換しません。
