# GitHub Issue Request Preflight / Retry Contract

GPT / Work が Issue を起点に GitHub Actions を実行する際の共通契約です。
目的は、Issue 本文の不足・誤記、upstream 参照の取り違え、壊れた / stale patch など、Actions を起動する前に検出できる失敗を減らすことです。

## 1. 基本原則

Issue を作成する前に、次の順序を必須とします。

1. 最新 `main` を確認する。
2. 対象 Issue の title prefix と request contract を確認する。
3. 必須項目を全て揃える。
4. chained workflow の場合は upstream の最終 RESULT が `status=success` であることを確認する。
5. `run_id` / `artifact_name` / `file_id` 等は upstream RESULT から完全一致で転記し、推測しない。
6. 可能な環境では preflight tool を実行し、成功してから Issue を作成する。
7. retry では失敗した request をそのまま再利用せず、失敗原因を確認して最新 `main` 基準で request を再構築する。

「Issue を先に作り、不足していた項目を後から補って再実行」は標準運用にしません。

## 2. 共通 preflight tool

```bash
python .gpt/tools/gpt_issue_preflight.py \
  --title "[gpt-git-update] update docs" \
  --body-file /tmp/issue-body.md \
  --repo-root .
```

実体は `tools/gpt_io/git/issue_preflight.py` です。

### 対応プロトコル

- `[gpt-git-update]`
- `[gpt-git-binary-read]`
- `[gpt-git-binary-update]`
- project-specific simple key/value body (`--protocol generic --required-key ...`)

`[gpt-git-update]` で `--repo-root` を指定した場合は `git apply --check` まで行います。最新 `main` を checkout / pull 済みの working tree を渡してください。

### 終了コード

- `0`: preflight success
- `2`: request contract failure

失敗時は machine-readable JSON を返します。

```json
{
  "status": "failure",
  "failure_class": "REQUEST_INVALID",
  "error_code": "MISSING_REQUIRED_FIELD",
  "message": "missing required field(s): artifact_name",
  "retryable": false
}
```

## 3. `[gpt-git-update]` contract

Issue title prefix:

```text
[gpt-git-update]
```

Issue body requires:

- `commit_message:`
- exactly one fenced `diff` block
- valid unified diff file headers
- at least one `@@` hunk

作成前ルール:

1. 必ず最新 `main` から patch を作る。
2. `@@ -a,b +c,d @@` の行数を手編集しない。
3. patch の前後 context を削り過ぎない。
4. `git apply --check` が使える環境では必ず通す。
5. patch failure 後は旧 patch を継ぎ足し修正せず、最新 `main` から再生成する。

protected path / credential rule は `.gpt/GIT_UPDATE_ISSUE.md` を正本とします。

## 4. `[gpt-git-binary-read]` contract

Required:

```text
path: <repository-relative path>
```

Optional:

```text
request_id: <unique request id>
```

`request_id` を明示する場合は、retry ごとに新しい値を使用します。同一 request の再実行と新しい retry を混同しないためです。

## 5. `[gpt-git-binary-update]` contract

Required:

```text
target_path: <repository-relative path>
commit_message: <message>
sha256: <64 hex>
size_bytes: <integer>
chunks: <positive integer>
encoding: base64
```

全 chunk を投稿してから `[gpt-git-binary-commit]` を投稿します。chunk 数、順序、SHA-256、size はローカル実ファイルから算出し、推測しません。

認証済み `gh` CLI がある環境では `.gpt/tools/gpt_git_binary_tool.py update` を優先し、Issue / chunk を手組みしません。

## 6. Project-specific Issue contract

プロジェクト固有 Issue は workflow ファイルだけに暗黙の contract を置かないことを推奨します。新規・改修時は、対象プロジェクトの README / `.gpt/WORKFLOW.md` に最低限以下を明記します。

- title prefix
- body format
- required fields
- optional fields and defaults
- upstream dependency fields
- accepted value / type constraints
- success RESULT marker
- failure RESULT marker
- retry policy

simple `key: value` body であれば、共通 preflight tool を次のように使用できます。

```bash
python .gpt/tools/gpt_issue_preflight.py \
  --title "[PROJECT_REQUEST] example" \
  --body-file /tmp/request.txt \
  --protocol generic \
  --required-key run_id \
  --required-key artifact_name
```

JSON body や複雑な条件分岐がある workflow は、そのプロジェクト側で専用 validator を用意するか、共通 tool の contract を拡張します。

## 7. Chained workflow rule

前工程 artifact / file を参照する Issue は、前工程の「run が終了した」だけでは作成しません。

必ず以下を確認します。

1. upstream RESULT が存在する。
2. `status=success` である。
3. 必須 ID / artifact 名 / file ID が RESULT に存在する。
4. downstream request へ値を完全一致で転記する。
5. upstream が失敗・cancel・superseded の場合は downstream を起動しない。

## 8. Retry contract

retry の標準手順:

1. failed step / result comment / log を確認する。
2. failure class を判定する。
3. request-side failure なら request を修正する。
4. patch 系なら最新 `main` を再取得して patch を再生成する。
5. upstream reference 系なら upstream RESULT を再確認する。
6. 新しい request_id が必要な protocol では新規 ID を使用する。
7. 同一内容を盲目的に rerun しない。

## 9. Failure taxonomy

run failure は全て同じ意味ではありません。

| failure_class | 意味 | 基本対応 |
| --- | --- | --- |
| `REQUEST_INVALID` | Issue 本文・必須項目・型・形式が不正 | Issue 作成前 preflight で削減 |
| `UPSTREAM_REF_INVALID` | run_id / artifact / file ID が不足・不一致 | upstream RESULT 再確認 |
| `PATCH_INVALID_OR_STALE` | unified diff が壊れている、または最新 main に適用不能 | 最新 main から再生成 |
| `DOMAIN_VALIDATION_FAILED` | データ内容が業務 validation に違反 | fail-closed を維持。盲目的 retry 禁止 |
| `EXTERNAL_TRANSIENT` | 通信・外部サイト等の一時障害 | retry/backoff |
| `IMPLEMENTATION_ERROR` | コード・テスト・Workflow 実装の不具合 | 実装修正 |
| `PERMISSION_ERROR` | token / GitHub App / environment 権限 | 権限・経路修正 |
| `CONCURRENCY_CONFLICT` | push/rebase/同時実行競合 | concurrency / rebase 改善 |

`DOMAIN_VALIDATION_FAILED` のように、異常を正しく検出して止まった run は「減らすべき赤」とは扱いません。

## 10. Workflow 実装時の推奨 RESULT

新規・改修 workflow では、可能な範囲で最終 failure comment / JSON に以下を含めます。

```json
{
  "status": "failure",
  "failure_class": "REQUEST_INVALID",
  "error_code": "MISSING_SOURCE_ARTIFACT",
  "failed_step": "validate_request",
  "retryable": false
}
```

これにより、後から run failed を機械集計し、「正常な fail」と「運用で削減できる fail」を分離できます。
