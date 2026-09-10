# GPT Git Binary Tool — Compatibility Wrapper

`.gpt/tools/gpt_git_binary_tool.py` は、GitHub正本バイナリのread / updateを既存Issue / Actions経路で自動化する互換CLIです。

2026-09-10以降、このCLIは**バイナリ操作の無条件な第一選択ではありません**。上位方針 `.gpt/GITHUB_OPERATION_POLICY.md` に従い、まずdirect経路の可否を判定します。

## Routing

```text
GitHub binary read/update
  -> 現在のGitHub / connector / Git環境で直接扱えるか確認
  -> 直接可能: direct経路
  -> 直接不可能: このCLIまたはbinary Issue fallback
```

外部ストレージが正本と定義されたファイルには使用しません。正本所在は各プロジェクトのREADME / `.gpt/CONTEXT.md` / `.gpt/WORKFLOW.md` を確認します。

## Source

```text
.gpt/tools/gpt_git_binary_tool.py
```

必要条件:

- Python 3.10+
- GitHub CLI `gh`
- `gh auth status` が成功する認証済み環境

Python側は標準ライブラリのみを使用します。

## Read

```bash
python .gpt/tools/gpt_git_binary_tool.py read \
  --path "example-project/data/example.sqlite" \
  --output "/tmp/example.sqlite"
```

内部では次を行います。

1. `[gpt-git-binary-read]` Issue作成
2. Actions完了待ち
3. `GIT_BINARY_READ_RESULT` 解析
4. artifact取得・展開
5. `manifest.json` 読み込み
6. size / SHA-256照合
7. 検証済み実ファイルを `--output` へ配置

つまり、**このCLIのread自体もActionsを使います**。direct download / materializeが可能ならそちらを優先します。

既存出力を上書きする場合は `--force` を指定します。

## Update

```bash
python .gpt/tools/gpt_git_binary_tool.py update \
  --file "/tmp/example.xlsx" \
  --path "example-project/data/example.xlsx" \
  --message "chore: update example binary"
```

内部では次を行います。

1. local size / SHA-256計算
2. Base64化・分割
3. `[gpt-git-binary-update]` Issue作成
4. chunk comments登録
5. `[gpt-git-binary-commit]` 投稿
6. Actions完了待ち
7. RESULT / SHA確認
8. main反映commit SHA返却

これもdirect binary writeが利用できない場合のフォールバックです。

## Output

成功時はJSONを返します。代表field:

Read:

```json
{
  "status": "success",
  "operation": "read",
  "repository_path": "example-project/data/example.sqlite",
  "local_path": "/tmp/example.sqlite",
  "issue_number": 123,
  "run_id": 456,
  "artifact_name": "...",
  "size_bytes": 1234,
  "sha256": "...",
  "source_commit": "..."
}
```

Update:

```json
{
  "status": "success",
  "operation": "update",
  "repository_path": "example-project/data/example.xlsx",
  "issue_number": 124,
  "commit_sha": "...",
  "size_bytes": 1234,
  "sha256": "...",
  "chunks": 1
}
```

失敗時は `status=failure` のJSONを標準エラーへ返し、終了コード1です。

## Related protocols

- read fallback: `.gpt/GIT_BINARY_READ_ISSUE.md`
- update fallback: `.gpt/GIT_BINARY_UPDATE_ISSUE.md`
- Issue preflight: `.gpt/ISSUE_REQUEST_CONTRACTS.md`

## GPT / Work rule

このCLIを使う前に、次の2点を確認します。

1. そのファイルは本当にGitHub正本か。
2. 現在の環境ではdirect read / updateが本当に不可能か。

両方を満たす場合にのみ、Issue手順を手作業で組み立てるよりこのCLIを優先します。

## Tests

```bash
python -m unittest .gpt/tools/tests/test_gpt_git_binary_tool.py
```

このCLIは既存互換経路を廃止せず保守するためのものです。新規設計では、Issue / Actionsをバイナリ搬送のためだけに当然視しません。
