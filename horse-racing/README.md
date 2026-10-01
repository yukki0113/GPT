# Horse Racing

中央競馬関連プロジェクトの入口です。

- `jrdb/` — 現行のJRDBデータ基盤、RaceNote、Core SQLite構築
- `eval/` — Eval表取得・JRA結果取得・検証支援
- `fetch_keibailuka_blog/` — keibailuka予想ブログの取得・解析。JRDB / Evalとは独立した予想支援ツール

現行作業では目的に応じて `jrdb/`、`eval/`、`fetch_keibailuka_blog/` を使い分けます。

## 1Rだけ予想する場合

「MM/DDの○○N Rを予想して」のような通常の中央競馬1R予想は、`jrdb/` のRaceNoteを標準データ入口とします。

```text
GPT Google Drive adapter
 -> current Analysis Lite / Stats Mart resolve
 -> [RACENOTE_REQUEST]
 -> authoritative RaceNote v1.0
 -> GPT-side Reader View
 -> GPT prediction layer
```

RaceNoteはJRDBデータをGPTが読みやすい形へ変換するサブシステムであり、予想ロジック自体はRaceNote converter/routerへ入れません。標準handoffは `jrdb/docs/RaceNote_Prediction_Handoff_v0_1.md`、Reader Viewは `jrdb/docs/RaceNote_Reader_View_v0_1.md` を参照してください。

## 共通 Parquet / DuckDB 実行基盤

`horse-racing` 配下でParquet / DuckDB / CSV→Parquet / schema・row-count・canonical-key監査を行う場合、project固有の代替実装を作る前にrepository共通の汎用CRUD / Data Storage Tool `tools/data-storage/` を確認します。

- Parquet/DuckDB依存が現在のPythonに無いだけでは処理を停止しない。
- rootの `.venv-data-storage` があれば再利用し、`check-deps` がPASSする場合は再installしない。
- 無い、または依存不足なら `tools/data-storage/requirements.txt` からbootstrapする。
- 汎用query / validation / conversionは共通CLIを使う。
- JRDB / Eval固有の意味論、schema、canonical key、生成contractは各project正本module/configを優先する。

詳細手順は repository root `.gpt/README.md` と `tools/data-storage/README.md` を正本とします。

各プロジェクトの作業開始時は `README.md` に加えて `.gpt/CONTEXT.md`、`.gpt/WORKFLOW.md`、存在する場合は `.gpt/MIGRATION_STATUS.md` を確認してください。
