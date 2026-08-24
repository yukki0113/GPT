# JRDB PACI → RaceNote 1R 一体実行

`racenote_jrdb_pipeline.py` は、既存の `fetch_jrdb_paci.py` によるHTTPS取得・ZIP検証を実行し、取得済みPACIを `racenote_jrdb.py` で1レースだけJSON化します。

認証情報は取得Python側の既存仕様をそのまま使います。環境変数 `JRDB_USER` / `JRDB_PASSWORD` を優先し、未設定時のみ取得Pythonと同じフォルダの `jrdb_secret.py` を参照します。資格情報はパイプラインPython・ログ・JSONに書き出しません。

## 実行例

`fetch_jrdb_paci.py`、`racenote_jrdb.py`、`racenote_jrdb_pipeline.py`、`jrdb_codebooks.json` を同じフォルダに置く場合:

```bash
python racenote_jrdb_pipeline.py --date 20260816 --race 札幌11 --output ./output
```

取得Pythonが別の場所にある場合:

```bash
python racenote_jrdb_pipeline.py --date 20260816 --race 札幌11 --output ./output --fetch-script /path/to/fetch_jrdb_paci.py
```

出力例:

```text
output/
├─ PACI/PACI260816.zip
└─ RaceNote_20260816/
   ├─ race_bundle_20260816_札幌11R.json
   ├─ manifest.json
   └─ validation_report.json
```

HTTPSが既定です。HTTPは自動フォールバックしません。必要な場合だけ `--base-url` で明示指定してください。

`jrdb_codebooks.json` は公式のTOKKI・ASHIMOTOコード表を別体系のまま保持する同梱マスタです。公式表が更新された場合は `generate_jrdb_codebooks.py` で再生成します。
