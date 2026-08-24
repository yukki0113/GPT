# Eval GPT workflow

1. GitHub `main` の最新状態を確認する。
2. `horse-racing/eval/README.md`、`.gpt/CONTEXT.md`、本ファイル、対象モジュールのdocs、対象Pythonを確認する。
3. 既存入出力仕様と重要な業務仕様を維持して実行・改修する。
4. JRA結果取得では、通常はChat/実行環境から `src/fetch_jra_daily_results.py` を直接実行する。
5. 外部通信が利用できない、または不安定な場合は `.github/workflows/jra_results_manual.yml` を `workflow_dispatch` で実行し、artifactを回収する。
6. JRA結果CSV取得後は `src/validate_jra_results.py` で機械検証し、全行成功、キー重複なし、出走頭数、1〜3着、単勝・複勝等を確認する。
7. 出走頭数は取消・競走除外前の枠順確定時の頭数を維持する。着順が数値の行だけで数えない。
8. 画像、Excel、日次CSV、検証レポート、ログ等の運用成果物はcommitしない。
9. Pythonを改修した場合はサンプル日付で取得・整合性を確認し、対応READMEも同時に更新してcommitする。
