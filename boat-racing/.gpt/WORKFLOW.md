# Boat racing GPT workflow

1. READMEと対象ツールのdocsを確認。
2. 公式サイト側の変更に注意し、既存CSV互換性を維持する。
3. 改修後は実日付または保存済みfixtureで回帰確認。
4. キャッシュ、日次成果物、ログ、継続台帳はcommitしない。継続台帳 `競艇note販売運用台帳.xlsx` はGoogle Drive `GPT/ledger/競艇note販売運用台帳.xlsx` を正本とする。
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

## Google Drive台帳正本の更新・取得

- 継続台帳 `競艇note販売運用台帳.xlsx` はGoogle Drive `GPT/ledger/競艇note販売運用台帳.xlsx` を正本とする。
- Chat / Workで台帳を解析する場合はDrive上の正本を取得し、更新時は同一Driveファイルへ反映する。
- GitHub `boat-racing/ledger/競艇note販売運用台帳.xlsx` に同名ファイルが残っていてもDrive移行前の旧スナップショットとして扱い、通常運用では参照・更新しない。
- `.gpt/tools/gpt_git_binary_tool.py`、`[gpt-git-binary-read]`、`[gpt-git-binary-update]` はGit管理バイナリ用の共通補助経路として残すが、この台帳の同期には使用しない。
- Drive上の正本へアクセスできない場合はGitHub旧スナップショットを最新と推定せず、正本取得不能として扱う。
