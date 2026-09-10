# GPT collaboration rules

このリポジトリをGPT / Workから扱う際の共通入口です。

GitHubアクセス経路の上位正本は `.gpt/GITHUB_OPERATION_POLICY.md` です。2026-09-10以降、**Issue駆動を既定経路にしません**。

## 作業開始時の基本順序

1. `.gpt/GITHUB_OPERATION_POLICY.md` を確認する。
2. 対象プロジェクトを特定する。
3. 対象プロジェクトの `README.md`、`.gpt/CONTEXT.md`、`.gpt/WORKFLOW.md` を読む。
4. 最新 `main` と実際の対象source / test / docs / workflowを確認する。
5. A/B/C/Dのどの経路かを判定してから処理する。
6. 改修後は差分、必要なtest、README / WORKFLOW整合性を確認する。
7. `legacy/` は明示的な依頼がない限り現行実装として使用しない。

GitHub外を正本とするデータ・台帳・大容量成果物は、各プロジェクト文書の定義を優先します。上位共通文書では個別プロジェクトのfile IDやSpreadsheet IDを固定しません。

## GitHub作業の4系統

### A. Read / Audit

repository / file / commit / issue / workflow / run、コード検索、差分、SHA、artifact metadata等の確認はGitHubから直接行います。

```text
Chat / Work -> GitHub read / search / fetch
```

**Issue不要です。**

### B. Git Change

source / test / docs / config / workflow等のUTF-8テキスト変更は、原則GitHubへ直接remote commitします。

```text
latest main
-> path存在確認
-> 現在内容 / blob SHA確認
-> 必要差分
-> direct create / update / delete
-> remote commit確認
```

`create_file` / `update_file` / Git Data API等の成功時点でremote commit済みです。別途 `git push` は不要です。

**通常テキスト変更に `[gpt-git-update]` Issueを使いません。**

同一目的の複数ファイルを安全に1commitへまとめられるGit操作が利用可能なら、過度に細分化せず1commitを優先します。

### C. Pure Deterministic Execution

Secrets、Actions固有権限、artifact chain、長時間runner、immutable freeze、正式監査runを必要としない決定的処理は、GitHub正本moduleを取得してGPT側で実行します。

対象例:

- CSV / JSON整形・join・集計
- scoring / metrics
- SHA / schema / integrity確認
- focused unit test / regression
- 固定入力に対する変換・比較・監査

可能なら `source_commit` / source・input・output SHA / module version / generated_at を残し、再現性を確保します。

### D. Actions-Native Execution

次のようにActions環境そのものが必要な場合だけIssue / Actionsを使用します。

- GitHub Secretsが必要
- 認証付き外部取得
- Actions artifact chainが正式仕様
- 長時間・大容量処理
- runner環境そのものが仕様・検証対象
- immutable freeze / publication / release
- run ID / artifact / Actions履歴を正式監査証跡として固定する必要がある

Dを選んだ場合は `.gpt/ISSUE_REQUEST_CONTRACTS.md` のpreflight / retry規約を必ず適用します。

## Issue駆動Actionsのpreflight / retry

Issue作成前に最低限、次を確認します。

1. latest `main`
2. workflow request contract / parser
3. 必須項目・型・accepted values
4. upstream RESULTの `status=success`
5. `run_id` / `artifact_name` / file ID等の実在と完全一致
6. 必要SHA / dates / keys / freeze manifestの一致
7. requestを機械的にserialize
8. 全項目PASS後にIssueを1回だけ発行

retryではfailed stepを確認し、旧requestをblind rerunしません。必要なら新しい `request_id` を使います。

共通validator:

```bash
python .gpt/tools/gpt_issue_preflight.py \
  --title "[PREFIX] request" \
  --body-file /tmp/issue-body.md
```

`[gpt-git-update]` 等の互換フォールバックを使う場合も同じcontractを適用します。

## 互換・フォールバック経路

旧Issue/Actions経路は削除せず、直接経路が利用できない場合の互換手段として残します。

- text update fallback: `.gpt/GIT_UPDATE_ISSUE.md`
- binary read fallback: `.gpt/GIT_BINARY_READ_ISSUE.md`
- binary update fallback: `.gpt/GIT_BINARY_UPDATE_ISSUE.md`
- binary Issue wrapper CLI: `.gpt/GIT_BINARY_TOOL.md`

これらを「GitHubにmoduleがあるから」という理由だけで選びません。

GitHub正本バイナリは、まず現在のGitHub / connector /実行環境で直接取得・更新できるか確認し、直接扱えない場合だけbinary fallbackを使います。外部ストレージが正本なら外部正本へ直接アクセスします。

## run failedの分類

run failureは一律に減らしません。

- `REQUEST_INVALID`: request本文・必須項目・形式不正。preflightで削減
- `UPSTREAM_REF_INVALID`: upstream run/artifact/file参照不正
- `PATCH_INVALID_OR_STALE`: 互換patch経路の壊れた/stale diff
- `DOMAIN_VALIDATION_FAILED`: データ異常を正しく検出したfail。fail-closed維持
- `EXTERNAL_TRANSIENT`: 外部通信等。一時retry/backoff対象
- `IMPLEMENTATION_ERROR`: 実装・test不具合
- `PERMISSION_ERROR`: GitHub App / token / environment権限不備
- `CONCURRENCY_CONFLICT`: push / rebase / 同時実行競合

新規・改修workflowでは、可能ならfailure resultに `failure_class` / `error_code` / `failed_step` / `retryable` を含めます。

## 共通リファレンス

- GitHub運用上位方針: `.gpt/GITHUB_OPERATION_POLICY.md`
- Actions Issue preflight / retry: `.gpt/ISSUE_REQUEST_CONTRACTS.md`
- GitHub Actions job時間監査: `.gpt/GITHUB_ACTIONS_JOB_AUDIT.md`
- Google Drive標準経路: connected native Google Drive tools / connector。Actions Drive bridgeはdeferred（`tools/gpt_io/DRIVE_ROUTING_DECISION_v0_1.md`）

個別プロジェクトの `.gpt/WORKFLOW.md` に旧「Issueを標準経路とする」記述が残る場合は、Actions-nativeである理由を棚卸しし、本上位方針へ順次寄せます。
