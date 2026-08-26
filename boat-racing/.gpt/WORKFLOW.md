# Boat racing GPT workflow

1. READMEと対象ツールのdocsを確認。
2. 公式サイト側の変更に注意し、既存CSV互換性を維持する。
3. 改修後は実日付または保存済みfixtureで回帰確認。
4. キャッシュ、日次成果物、ログはcommitしない。ただし継続台帳 `ledger/競艇note販売運用台帳.xlsx` はGit管理対象とする。
5. Pythonと対応READMEを同時に更新してcommitする。

## Chatでの日次取得実行

- まずGitHub `main` の `boat-racing/` を正本として確認する。
- Chatからの定型実行は、GitHub Issue経由を標準経路とする。
- 出走表取得は `.github/workflows/boatrace_racelist_issue.yml` を使用する。
- Issue title は `[BOATRACE_RACELIST_REQUEST] <request_id>`、Issue本文はraw JSONとする。
- Workflowは `main` の `boat-racing/src/fetch_boatrace_racelist.py` と `boat-racing/requirements.txt` をそのまま使用し、独自ロジックを別実装しない。
- Issueコメントの `BOATRACE_RACELIST_RESULT` JSONから `status` / `run_id` / `artifact_name` を取得し、artifactを回収する。
- artifact内の `resolved_request.json`、`run_status.txt`、`validation_report.json`、取得状況・ログ・CSVを確認してから日常成果物を受け渡す。
- Request Issueは処理終了後に自動Closeする。
- 失敗時もartifactとRESULTコメントを残し、診断可能にする。
- `.github/workflows/boatrace_racelist_manual.yml` は手動フォールバックとして残すが、Chatからの日常実行ではIssue経由を優先する。
- 日次成果物はGitへcommitしない。

## GitHubバイナリ正本の更新・取得

- 継続台帳 `ledger/競艇note販売運用台帳.xlsx` を更新する場合は、最新mainを基準にし、直接pushできなければ共通の `[gpt-git-binary-update]` Issue経路を使用する。
- GitHub `main` 上の台帳やその他バイナリ正本をChat / Workで実ファイルとして解析する必要がある場合、GitHub Connectorで読めないことを理由にユーザーへ再添付を依頼しない。
- 共通の `[gpt-git-binary-read]` Issue経路を使用し、Actions artifactとして対象ファイルを回収する。
- 詳細はルート `.gpt/GIT_BINARY_READ_ISSUE.md` を参照する。
- artifact回収後は `manifest.json` のSHA-256と実ファイルを照合し、ファイル形式に応じたツールで解析する。
- readback artifactは搬送用の一時物であり、正本はGitHub `main` 上の対象ファイルとする。
