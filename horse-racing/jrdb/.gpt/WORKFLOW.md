# JRDB GPT workflow

1. `README.md` と本ディレクトリのCONTEXTを確認。
2. 対象Pythonと対応README・schema/referenceを確認。
3. 既存仕様を壊さない範囲で改修。
4. 可能な範囲で実行テスト / 回帰確認。
5. 生成物・秘密情報・Rawデータが差分に入っていないことを確認。
6. README/仕様変更が必要なら同時更新。
7. Gitへcommitし、以後Git版を正本とする。

## GitHub routing standard — 2026-09-10

JRDBをChatGPTから扱う場合、処理開始時に「GitHub Actions実行環境が本当に必要か」を判定し、次の4経路を標準とする。Issue駆動を既定経路にはしない。

### A. Read / Audit

GitHub repository/file/commit/issue/workflow/run/artifact metadata、コード検索、main内容、差分、SHA、RESULT状態などの確認はGitHubのread/search/fetch機能から直接行う。確認だけのためにIssueを作成しない。

### B. Git Change

source/test/docs/config等のUTF-8テキスト変更は、原則としてGitHubのcreate/update/delete機能で最新mainへ直接remote commitする。

変更前に次を確認する。

1. 最新main
2. 対象pathの存在
3. 現在内容 / blob SHA
4. 必要差分

変更後は対象fileをreadbackし、必要なfocused test / regressionをCまたは既存CIで確認する。`[gpt-git-update]` Issueは標準経路としない。

### C. Pure Deterministic Execution

Secrets、Actions固有権限、Actions artifact chain、長時間・大容量runner、immutable freeze、正式監査runを必要としない決定的処理はChat実行環境のPython / shellで直接行う。

例:

- focused unit test / regression test
- 既取得artifactやSQLite/JSON/CSVの集計・監査
- SHA-256 / schema / row-count / integrity確認
- WATCH理由分解等のaudit-only処理
- 固定入力に対する変換・JOIN・レポート生成

同一処理を「Issueを投げるためだけ」にActionsへ送らない。

### D. Actions-Native Execution

以下はIssue / GitHub Actions経路を維持する。

- `JRDB_USER` / `JRDB_PASSWORD` 等のSecretsを使うJRDB取得・再構築
- upstream Actions artifactを正式入力としてchainする処理
- Full 2010-2025等の長時間・大容量build
- immutable freeze / publication / release等、GitHub runを不変証跡として必要とする処理
- 正式な監査run・再現性証跡としてrun ID / artifact / workflow RESULTを残す必要がある処理
- GitHub-hosted環境そのものを検証対象とする処理

Dを使う場合のみ、下記「Issue駆動Actionsのpreflight」を適用する。

### Edge Registryでの標準適用

- Registry/source/docs/configの参照、Issue/run/artifact/SHA確認: **A**
- Edge RegistryのPython/test/docs/config修正: **B**
- 既存Registry artifactに対するWATCH/statistical audit、focused tests: **C**
- 2025-only real-data smoke build（Raw取得を含む）: **D** — JRDB Secrets + artifact監査を使用
- Full 2010-2025 Registry rebuild: **D** — Secrets + 長時間/大容量 + publication artifact
- Current Facts / Matcherの固定済みローカル入力テスト: **C**
- PACI等の認証取得を伴うofficial current matching / artifact chain: **D**

RaceNote等の別subsystemは各専用contractを優先し、Edge Registry開発と文脈を混在させない。

## Issue駆動Actionsのpreflight

- JRDB / RaceNote系を含むIssue起点Actionsは、Issue作成前にルート `.gpt/ISSUE_REQUEST_CONTRACTS.md` を確認する。
- title prefix、必須body項目、upstream dependency、RESULT markerをworkflow / 対応docsから確認してからIssueを作成する。
- upstream `run_id` / `artifact_name` 等を使う場合、前工程RESULTが `status=success` であることを確認し、値を完全一致で転記する。推測値を使用しない。
- simple `key: value` bodyは `.gpt/tools/gpt_issue_preflight.py --protocol generic --required-key ...` で事前検証できる。
- retry時はfailed stepを確認し、必要に応じて最新 `main` / upstream RESULTからrequestを再構築する。同一requestの盲目的rerunを標準運用にしない。

## GitHubバイナリ正本の取得・更新

- GitHub `main` 上の `.xlsx`、`.sqlite`、`.zip` 等をChat / Workで実ファイルとして扱う必要がある場合、まず直接取得可能なGitHub/connector経路を確認する。
- 認証済み `gh` CLIを実行できる環境ではルート `.gpt/tools/gpt_git_binary_tool.py` を利用できるが、Issueを不要に経由させない。
- GitHub正本を実ファイルとして直接取得できない場合のみ、`[gpt-git-binary-read]` をフォールバックとする。
- Git管理対象バイナリを直接安全に更新できない場合のみ、`[gpt-git-binary-update]` をフォールバックとする。
- GitHub Connectorでバイナリを直接読めないことを理由に、GitHub正本が存在するファイルの再添付をユーザーへ依頼しない。
- 詳細はルート `.gpt/GIT_BINARY_TOOL.md`、`.gpt/GIT_BINARY_READ_ISSUE.md`、`.gpt/GIT_BINARY_UPDATE_ISSUE.md` を参照する。
- readback artifactは搬送用の一時物であり、正本はGitHub `main` 上の対象ファイルとする。
