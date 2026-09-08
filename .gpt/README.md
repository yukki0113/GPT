# GPT collaboration rules

このリポジトリをGPT / Workから扱う際の共通入口です。

1. 対象プロジェクトを特定する。
2. そのプロジェクトの `README.md`、`.gpt/CONTEXT.md`、`.gpt/WORKFLOW.md` を読む。
3. Git上の内容をソース正本として扱う。
4. 認証情報・有料原データ・大容量成果物をcommitしない。
5. 改修後はテスト、差分確認、必要なREADME更新を行ってからcommitする。
6. `legacy/` は明示的な依頼がない限り現行実装として使用しない。

## 共通Git搬送経路

GPT / Workから通常のソース・Markdownを反映する際、直接`git push`が認証不可なら、必ず`[gpt-git-update]` Issueを作成する。最新main基準のunified diffと`commit_message`をIssue本文へ入れ、Actionsの検証・commit・push・Issue closeを確認する。ローカルcommitをそのままpushしない。バイナリはbinary update経路を使用する。

- 通常テキストの更新: `.gpt/GIT_UPDATE_ISSUE.md` / `[gpt-git-update]`
- バイナリの更新: `.gpt/GIT_BINARY_UPDATE_ISSUE.md` / `[gpt-git-binary-update]`
- GitHub上のバイナリをChat / Workへ実ファイルとして取得: `.gpt/GIT_BINARY_READ_ISSUE.md` / `[gpt-git-binary-read]`
- バイナリread/updateの1コマンド操作: `.gpt/GIT_BINARY_TOOL.md` / `.gpt/tools/gpt_git_binary_tool.py`
- Issue作成前preflight / retry規約: `.gpt/ISSUE_REQUEST_CONTRACTS.md` / `.gpt/tools/gpt_issue_preflight.py`
- Google Drive: connected native Google Drive tools / connectorを第一選択とする。Google native Docs/Sheets/Slidesもnative toolsで扱う。Actions Drive bridgeはdeferredであり、標準経路ではない（`tools/gpt_io/DRIVE_ROUTING_DECISION_v0_1.md`）。

認証済み `gh` CLIを実行できる環境では、バイナリread/updateは `.gpt/tools/gpt_git_binary_tool.py` を第一選択とし、Issue本文・Base64チャンク・artifact回収手順をGPTが手作業で組み立てない。

`gh` CLIを利用できないChat環境では、GitHub Connector + `[gpt-git-binary-read]` / `[gpt-git-binary-update]` をフォールバックとして使用する。

GitHub Connectorが `.xlsx` 等の中身を直接展開できない場合でも、GitHub `main` が正本として定義されているファイルについては、ユーザーへ再添付を依頼する前にバイナリread経路を使用する。

各プロジェクトのREADME / `.gpt/CONTEXT.md` / `.gpt/WORKFLOW.md` でGoogle Drive等の外部ストレージが正本と明示されている運用ファイルは、このGitバイナリ搬送ルールの対象外とする。外部正本を優先し、GitHubに残る旧コピーを最新と推定しない。

現在、競艇継続台帳の正本はネイティブGoogleスプレッドシート `競艇note販売運用台帳`（Spreadsheet ID `1gEAYJ90Zv3HDi5gh_at0jDWEQrgCSB5tIywJFZjXcFM`）とする。旧Google Drive Excel版およびGitHub上の `boat-racing/ledger/競艇note販売運用台帳.xlsx` は移行前スナップショットであり、正本として扱わない。

中央競馬Eval継続台帳は各プロジェクト側README / `.gpt/WORKFLOW.md` に定義された外部正本を優先する。

## Issue駆動Actionsのpreflight / retry必須ルール

Issue起点のActionsは、Issue作成前に検出できる失敗をrunnerへ送らないことを原則とします。詳細contractは `.gpt/ISSUE_REQUEST_CONTRACTS.md` を正本とします。

Issue作成前に必ず以下を確認します。

1. 最新 `main` と対象workflow / project workflow docsを確認する。
2. title prefix、必須項目、値の型、upstream依存を確認する。
3. chained workflowではupstreamの最終RESULTが `status=success` であることを確認する。
4. `run_id` / `artifact_name` / `file_id` 等はRESULTから完全一致で転記し、推測しない。
5. 可能な環境では `.gpt/tools/gpt_issue_preflight.py` を実行してからIssueを作る。
6. `[gpt-git-update]` は最新mainからpatchを生成し、`git apply --check` が使える環境では必ず通す。
7. retry時は旧request / patchをそのまま再実行せず、failed stepを確認して最新main基準でrequestを再構築する。
8. request_idを持つprotocolではretryごとに新しいrequest_idを使用する。
9. domain validation failureは盲目的にretryしない。異常を正しく検出したfailは維持する。

共通preflight例:

```bash
python .gpt/tools/gpt_issue_preflight.py \
  --title "[gpt-git-update] update docs" \
  --body-file /tmp/issue-body.md \
  --repo-root .
```

project-specificなsimple `key: value` requestは `--protocol generic --required-key <name>` を繰り返して最低限の必須項目をIssue作成前に検証できます。

## run failedの分類

run failureは一律に減らしません。少なくとも以下を区別します。

- `REQUEST_INVALID`: Issue本文・必須項目・形式不正。preflightで削減対象。
- `UPSTREAM_REF_INVALID`: upstream run/artifact/file参照不正。RESULT確認で削減対象。
- `PATCH_INVALID_OR_STALE`: 壊れたdiff / stale patch。最新mainから再生成。
- `DOMAIN_VALIDATION_FAILED`: データ異常を正しく検出したfail。fail-closedを維持。
- `EXTERNAL_TRANSIENT`: 外部通信等。一時retry/backoff対象。
- `IMPLEMENTATION_ERROR`: 実装・テスト不具合。コード修正対象。
- `PERMISSION_ERROR`: GitHub App / token / environment権限不備。
- `CONCURRENCY_CONFLICT`: push / rebase / 同時実行競合。

新規・改修workflowでは、可能ならfailure resultへ `failure_class` / `error_code` / `failed_step` / `retryable` を含め、後から機械集計できる形を優先します。

## GitHub Actions実行時間監査

- job時間 / Private化時のGitHub-hosted runner分数の監査: `.gpt/GITHUB_ACTIONS_JOB_AUDIT.md`
- CLI: `.gpt/tools/github_actions_job_audit.py`

月次確認は `python .gpt/tools/github_actions_job_audit.py --month YYYY-MM` を基本とする。
