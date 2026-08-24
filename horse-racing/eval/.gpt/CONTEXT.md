# Eval project context

## Status

Active。Eval表の画像取得、結果取得、OCR/検証・台帳更新を支援する領域です。

## Source of truth

Python、README、作業手順、依存関係、GitHub Actions WorkflowはGitHub `yukki0113/GPT` の `main` を正本とします。

Eval画像、OCR途中成果物、Excel運用台帳、日次取得CSV、検証レポート、ログ等の運用成果物はGit外を正本とします。

## JRA結果取得

本体は `src/fetch_jra_daily_results.py`。取得後は `src/validate_jra_results.py` で検証します。

通常はChat/実行環境から直接実行し、Yahoo!スポーツへの外部通信が利用できない、または不安定な場合は `.github/workflows/jra_results_manual.yml` を代替実行経路として使用します。WorkflowはGit正本のPythonと `requirements.txt` を使用し、CSV・検証レポート・実行状態をartifact化します。

出走頭数は取消・競走除外前の枠順確定時の頭数を維持することが重要仕様です。

今後OCR・台帳取込等のモジュールが増えた場合も、このプロジェクト配下へ追加します。
