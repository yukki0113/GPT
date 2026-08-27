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

- 継続台帳 `ledger/競艇note販売運用台帳.xlsx` のread/updateは、認証済み `gh` CLIを実行できる環境ではルート `.gpt/tools/gpt_git_binary_tool.py` を第一選択にする。
- 台帳を更新する場合は `update` サブコマンドを使用し、Base64化・Issueチャンク登録・確定コメント・完了待ちをツールへ任せる。
- GitHub `main` 上の台帳をChat / Workで実ファイルとして解析する場合は `read` サブコマンドを使用し、Issue作成・artifact取得・SHA-256照合をツールへ任せる。
- `gh` CLIを利用できないChat環境では、更新は `[gpt-git-binary-update]`、取得は `[gpt-git-binary-read]` Issue経路をフォールバックとして使用する。
- GitHub Connectorで `.xlsx` を直接読めないことを理由に、GitHub正本が存在する台帳の再添付をユーザーへ依頼しない。
- 詳細はルート `.gpt/GIT_BINARY_TOOL.md`、`.gpt/GIT_BINARY_UPDATE_ISSUE.md`、`.gpt/GIT_BINARY_READ_ISSUE.md` を参照する。
- readback artifactは搬送用の一時物であり、正本はGitHub `main` 上の対象ファイルとする。
