# GitHub Issue Request Preflight / Retry Contract

この文書は、`.gpt/GITHUB_OPERATION_POLICY.md` の判定で **D. Actions-Native Execution** または明示的な互換Issue fallbackを選んだ後に適用する共通contractです。

**この文書はIssue利用そのものを推奨するものではありません。**
A. Read / Audit、B. Git Change、C. Pure Deterministic Executionで完結する処理にIssueを追加しないでください。

目的は、Issue本文の不足・誤記、upstream参照の取り違え、壊れた / stale requestなど、Actions起動前に検出できる失敗をrunnerへ送らないことです。

## 1. Issue発行前の必須確認

1. latest `main` を確認する。
2. 対象workflowのrequest contract / parserを確認する。
3. title prefixを確認する。
4. 必須key、型、accepted value、defaultを確認する。
5. chained workflowではupstream RESULTが `status=success` であることを確認する。
6. `run_id` / `artifact_name` / file ID等は実在を確認し、RESULTから完全一致で転記する。
7. 必要SHA、dates、results keys、IDs、freeze commit / manifestを実値と照合する。
8. request JSON / bodyを可能な限り機械的にserializeする。
9. 利用可能ならpreflight validatorを実行する。
10. 全項目PASS後にIssueを1回だけ発行する。

「Issueを先に作り、不足項目を後から補って再実行」は標準運用にしません。

## 2. 共通preflight tool

```bash
python .gpt/tools/gpt_issue_preflight.py \
  --title "[PREFIX] request" \
  --body-file /tmp/issue-body.md
```

実体:

```text
tools/gpt_io/git/issue_preflight.py
```

対応済みprotocol:

- `[gpt-git-update]` compatibility fallback
- `[gpt-git-binary-read]` compatibility fallback
- `[gpt-git-binary-update]` compatibility fallback
- project-specific simple key/value body (`--protocol generic --required-key ...`)

終了code:

- `0`: success
- `2`: contract failure

失敗時はmachine-readable JSONを返します。

```json
{
  "status": "failure",
  "failure_class": "REQUEST_INVALID",
  "error_code": "MISSING_REQUIRED_FIELD",
  "message": "missing required field(s): artifact_name",
  "retryable": false
}
```

## 3. Project-specific Actions Issue contract

Actions-nativeなproject-specific Issueは、workflowファイルだけに暗黙contractを置かないことを推奨します。対象projectのREADME / `.gpt/WORKFLOW.md` に少なくとも次を明記します。

- なぜD. Actions-Nativeであるか
- title prefix
- body format
- required fields
- optional fields / defaults
- upstream dependency fields
- accepted values / type constraints
- success RESULT marker / success condition
- failure RESULT marker
- artifact contract
- retry policy

simple `key: value` bodyなら共通validatorを利用できます。

```bash
python .gpt/tools/gpt_issue_preflight.py \
  --title "[PROJECT_REQUEST] example" \
  --body-file /tmp/request.txt \
  --protocol generic \
  --required-key run_id \
  --required-key artifact_name
```

JSON bodyや複雑な条件分岐はproject専用validatorを用意するか、共通tool contractを拡張します。

## 4. Chained workflow rule

upstream artifact / fileを参照するIssueは、upstream runが「終了した」だけでは発行しません。

必ず以下を確認します。

1. upstream RESULTが存在する。
2. `status=success` である。
3. 必須run ID / artifact名 / file IDがRESULTに存在する。
4. artifact等が実際に存在する。
5. downstream requestへ値を完全一致で転記する。
6. upstreamがfailure / cancelled / supersededならdownstreamを起動しない。

## 5. Retry contract

retryの標準手順:

1. failed step / result comment / job logを確認する。
2. failure classを判定する。
3. request-side failureならrequestを再構築する。
4. upstream reference系ならupstream RESULT / artifact実在を再確認する。
5. patch fallbackならlatest `main` を再取得してpatchを再生成する。
6. external transientなら必要なbackoffを置く。
7. 新しい `request_id` が必要なprotocolでは新規IDを使う。
8. 同一内容をblind rerunしない。

## 6. Failure taxonomy

| failure_class | 意味 | 基本対応 |
| --- | --- | --- |
| `REQUEST_INVALID` | Issue本文・必須項目・型・形式不正 | Issue作成前preflightで削減 |
| `UPSTREAM_REF_INVALID` | run ID / artifact / file ID不足・不一致 | upstream RESULT /実在再確認 |
| `PATCH_INVALID_OR_STALE` | 互換patchが壊れている、またはlatest mainに適用不能 | latest mainから再生成 |
| `DOMAIN_VALIDATION_FAILED` | データ内容が業務validation違反 | fail-closed維持、blind retry禁止 |
| `EXTERNAL_TRANSIENT` | 通信・外部サービス等の一時障害 | retry / backoff |
| `IMPLEMENTATION_ERROR` | code / test / workflow実装不具合 | 実装修正 |
| `PERMISSION_ERROR` | token / GitHub App / environment権限 | 権限・経路修正 |
| `CONCURRENCY_CONFLICT` | push / rebase /同時実行競合 | concurrency / commit設計改善 |

`DOMAIN_VALIDATION_FAILED` のような、異常を正しく検出したfailは「減らすべき赤」とは扱いません。

## 7. Workflow RESULT推奨形式

新規・改修workflowでは、可能ならfailure result / commentに以下を含めます。

```json
{
  "status": "failure",
  "failure_class": "REQUEST_INVALID",
  "error_code": "MISSING_SOURCE_ARTIFACT",
  "failed_step": "validate_request",
  "retryable": false
}
```

これにより正常なfailと運用で削減できるfailを後から機械集計できます。

## 8. Compatibility GPT-Git Issue contracts

以下は通常経路ではなくfallbackです。

### `[gpt-git-update]`

Required:

- `commit_message:`
- exactly one fenced `diff` block
- valid unified diff headers / hunk

`--repo-root` 指定時は `git apply --check` を行います。hunk行数を手編集せず、failure後はlatest mainからpatchを再生成します。

詳細: `.gpt/GIT_UPDATE_ISSUE.md`

### `[gpt-git-binary-read]`

Required:

```text
path: <repository-relative path>
```

Optional:

```text
request_id: <unique request id>
```

詳細: `.gpt/GIT_BINARY_READ_ISSUE.md`

### `[gpt-git-binary-update]`

Required:

```text
target_path: <repository-relative path>
commit_message: <message>
sha256: <64 hex>
size_bytes: <integer>
chunks: <positive integer>
encoding: base64
```

詳細: `.gpt/GIT_BINARY_UPDATE_ISSUE.md`

## 9. 禁止事項

- A/B/Cで完結するのに監査理由なくIssue / Actionsへ送る
- diff hunk行数を手作業で推測する
- Markdown fenceや余計な文字を混ぜたpatch Issueを発行する
- upstream未確認でdownstream Issueを発行する
- run ID / artifact名 / SHA等を推測する
- failed reason未確認で同じrequestをrerunする
- 同一 `request_id` を安易に再利用する
- domain validationを成功扱いに変えて見かけのfailure率だけ下げる

Issue数やActions run数を作業単位として考えず、論理的な完了点・監査点を作業単位にします。
