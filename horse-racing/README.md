# Horse Racing

中央競馬関連プロジェクトの入口です。

- `jrdb/` — 現行のJRDBデータ基盤、RaceNote、Core SQLite構築
- `eval/` — Eval表取得・JRA結果取得・検証支援
- `fetch_keibailuka_blog/` — keibailuka予想ブログの取得・解析。JRDB / Evalとは独立した予想支援ツール
- `legacy/` — 旧JRA-VAN / 検証ラボ等の凍結資産

現行作業では目的に応じて `jrdb/`、`eval/`、`fetch_keibailuka_blog/` を使い分けます。`legacy/` は明示的な参照依頼がある場合を除いて改修対象にしません。

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

各プロジェクトの作業開始時は `README.md` に加えて `.gpt/CONTEXT.md`、`.gpt/WORKFLOW.md`、存在する場合は `.gpt/MIGRATION_STATUS.md` を確認してください。
