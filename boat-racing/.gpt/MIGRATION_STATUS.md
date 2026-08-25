# Boat racing Git migration status

Updated: 2026-08-25
Status: COMPLETE

## Gitへ移行済み

- プロジェクトREADME
- `.gpt/CONTEXT.md`
- `.gpt/WORKFLOW.md`
- `.gpt/MIGRATION_STATUS.md`
- `requirements.txt`
- `requirements_直前情報取得.txt`
- `docs/README_出走表取得.md`
- `docs/README_直前情報取得.md`
- `docs/README_公式結果取得.md`
- `docs/出走表取得依頼_定型作業.txt`
- `docs/直前情報取得依頼_定型作業.txt`
- `docs/直前情報取得_GitHubActions運用.md`
- `docs/直前情報取得_GitHubIssue運用.md`
- `docs/結果照合取得依頼_定型作業.txt`
- `src/fetch_boatrace_racelist.py`
- `src/fetch_boatrace_pre_race_info.py`
- `src/fetch_boatrace_results.py`
- `.github/workflows/boatrace_racelist_manual.yml`
- `.github/workflows/boatrace_racelist_issue.yml`
- `.github/workflows/boatrace_pre_race_manual.yml`
- `.github/workflows/boatrace_pre_race_issue.yml`
- `.github/workflows/boatrace_results_manual.yml`
- `.github/workflows/boatrace_results_chat.yml`

## 移行状態

競艇取得運用に必要なPython本体、README、GPT向け運用資料、定型作業手順、Python依存関係、GitHub Actions実行経路はGitへ移行済み。

今後は `yukki0113/GPT` の `main` ブランチ配下 `boat-racing/` と `.github/workflows/` を正本として参照する。
過去の添付ZIPやWorkスレッド内の一時作業領域は、Git正本の代わりとして使用しない。

作業開始時は、少なくとも以下を確認する。

1. `boat-racing/README.md`
2. `boat-racing/.gpt/CONTEXT.md`
3. `boat-racing/.gpt/WORKFLOW.md`
4. `boat-racing/.gpt/MIGRATION_STATUS.md`
5. 対象作業の `docs/` と `src/` の対応ファイル
6. Chatから実行する場合は対応するIssue起動Workflow

## Python依存関係

取得ツール全体では `boat-racing/requirements.txt` を使用する。
直前情報取得を単独で扱う場合は `boat-racing/requirements_直前情報取得.txt` も使用できる。

現在の取得ツール3本で必要な外部パッケージ:

- `requests`
- `beautifulsoup4`
- `lxml`

## GitHub Issue経由の標準実行

ChatからGitHub Actionsの `workflow_dispatch` を直接起動できない事象があるため、Chat起点の定型実行ではGitHub Issueを実行要求キューとして使う方式を優先する。

現時点のIssue起動Workflow:

- 出走表取得: `.github/workflows/boatrace_racelist_issue.yml`
- 直前情報取得: `.github/workflows/boatrace_pre_race_issue.yml`
- 結果取得・予想照合: `.github/workflows/boatrace_results_chat.yml`

直前情報取得のIssue prefix:

`[BOATRACE_PRE_RACE_REQUEST]`

Issue本文は raw JSON とし、`date`・`venue`・`race`・`format` を渡す。
Workflow側でJSONを検証し、正本 `boat-racing/src/fetch_boatrace_pre_race_info.py` のCLI引数へ変換する。

成果物はartifactへ保存し、Issueコメントの `BOATRACE_PRE_RACE_RESULT` JSONから `status` / `run_id` / `artifact_name` / exit code / validation をChat側で取得する。
処理終了後はRequest IssueをCloseする。

`workflow_dispatch` のmanual Workflowは手動実行用の補助経路として残すが、Chat運用ではIssue経路を優先する。

## Git対象外

以下は引き続きGit管理対象外とする。

- 日次CSV / JSON
- HTMLキャッシュ
- 実行ログ
- Actionsの日次artifact内容
- `resolved_request.json`
- `validation_report.json`
- `run_status.txt`
- Excel運用台帳
- 予想・結果の運用成果物

これらはGit正本のソース・仕様の代わりとして参照しない。

## 運用上の注意

- ソース参照・改修時は、まずGitの `main` 最新状態を確認する。
- 公式サイト側の構造変更により改修が必要な場合は、既存出力互換性を維持する。
- 改修時はPythonと対応READMEを同時に更新する。
- Workflow変更時も正本PythonのCLI互換性を確認する。
- Issue本文をshellへ直接展開せず、JSON解析・型検証後に引数listとして実行する。
- 可能な限り実日付または保存済みfixtureで回帰確認する。
- 日次成果物、ログ、キャッシュ、台帳はcommitしない。
