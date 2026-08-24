# Eval表活用

中央競馬のEval表取得・検証運用を支援するPythonツール群です。

## Source of truth

GitHub `yukki0113/GPT` の `main` ブランチ配下 `horse-racing/eval/` をPython・README・作業手順の正本とします。

画像、OCR途中成果物、Excel運用台帳、日次CSV、ログ等の運用成果物はGit管理対象外です。

## Current tools

- `src/master_eval_media_collector.py` — X上のEval表メディア収集
- `src/fetch_jra_daily_results.py` — JRA日次結果・払戻取得
- `src/validate_jra_results.py` — JRA結果CSVの機械検証

各ツールの詳細は `docs/` を参照してください。

## JRA結果取得の実行経路

通常はChat/ローカル実行環境から `fetch_jra_daily_results.py` を直接実行します。

外部通信が利用できない、または不安定な場合は、常設GitHub Actions Workflow

```text
.github/workflows/jra_results_manual.yml
```

を `workflow_dispatch` で実行し、成果物をartifactから回収します。

依存関係は `horse-racing/eval/requirements.txt` を使用します。取得後は `validate_jra_results.py` で検証し、CSV・検証レポート・実行状態を確認します。

日次成果物はGitへcommitしません。
