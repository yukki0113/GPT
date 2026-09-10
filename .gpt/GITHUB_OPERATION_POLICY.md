# GitHub Operation Policy — 2026-09-10

この文書は、ChatGPT / Work から本リポジトリを扱う際の**リポジトリ横断のGitHub運用正本**です。
個別プロジェクトの業務仕様・データ正本・実行条件は各 `README.md` / `.gpt/CONTEXT.md` / `.gpt/WORKFLOW.md` を優先しますが、GitHubへのアクセス経路・更新経路・Actions利用判定は本書を共通上位方針とします。

## 1. 最初に判定すること

処理開始時に、まず次を判定します。

> **この処理は本当にGitHub Actions環境でなければならないか。**

「GitHubにmoduleがある」ことと「Issue / Actionsで実行すべき」ことは同義ではありません。
最短かつ再現可能な経路を選びます。

## 2. 4系統の標準ルーティング

### A. Read / Audit

対象:

- repository / file / commit / issue / workflow / run の確認
- コード検索、差分確認、最新 `main` 確認
- upstream RESULT、artifact名、SHA、run状態の監査

標準経路:

```text
Chat / Work -> GitHub read / search / fetch
```

**Issue不要。** 確認だけのためにActionsを起動しません。

### B. Git Change

対象:

- source
- test
- docs
- config
- workflow
- その他UTF-8テキストファイル

標準経路:

```text
latest main確認
-> path存在確認
-> 現在内容 / blob SHA確認
-> 必要差分だけ作成
-> GitHub direct create / update / delete
-> remote commit確認
```

GitHub Contents API / Git Data API等によるdirect write成功時点でremote branchへcommit済みです。別途 `git push` は不要です。

**`[gpt-git-update]` Issueは標準経路ではありません。**
同一目的で相互依存する複数ファイル変更は、利用可能なGit操作で安全に1commitへまとめられる場合はまとめます。

### C. Pure Deterministic Execution

対象例:

- CSV / JSON整形、join、集計
- scoring / metrics計算
- SHA-256、schema、row-count、integrity確認
- 既存成果物の比較・監査
- repo内Pythonだけで完結するfocused test / regression
- 固定入力に対する決定的変換・レポート生成

次をすべて満たす場合はGPTローカル実行を優先します。

- GitHub上の正本moduleを取得可能
- 必要入力をGPT側で取得可能
- secret不要
- 特殊runner環境不要
- 計算量が現実的
- Actions artifact / run IDを正式監査証跡として残す必然性がない

標準経路:

```text
GitHub正本module取得
-> GPTローカル実行
-> 成果物 / test結果確認
-> 必要ならBでGitHubへ直接反映
```

可能な限り、成果物またはmanifestに次を残します。

- `source_commit`
- `source_file_sha256`
- `input_sha256`
- module / runner version
- `generated_at`
- `output_sha256`

正本moduleと同等の処理を独自に再実装して置き換えないことを原則とします。

### D. Actions-Native Execution

Issue / GitHub Actionsを維持する対象:

- GitHub Secretsが必要
- 外部サービスへの認証付きアクセス
- upstream / downstream Actions artifact chainが仕様に含まれる
- 大容量・長時間処理
- runner環境そのものが仕様・検証対象
- immutable freeze / publication / release
- settlement等でrun ID / artifact / Actions履歴を正式監査証跡として固定する必要がある
- GitHub上での再実行性を正規仕様として保持する必要がある

標準経路:

```text
Chat / Work
-> fully validated request
-> Issue
-> GitHub Actions
-> RESULT / artifact / run監査
```

**Issueは原則としてこの系統に限定します。**

## 3. Actions Issue発行前Preflight

Dを選んだ場合、Issue作成前に以下を確認します。

1. latest `main`
2. 対象workflowのrequest contract / parser
3. 必須キー・型・accepted value
4. upstream runの成功
5. artifact名の実在
6. 必要SHAの実値一致
7. dates / results keys / IDsの一致
8. freeze commit / manifest等の存在
9. request JSON / bodyの機械的serialize
10. 全項目PASS後にIssueを1回だけ発行

禁止:

- diff hunk行数を手作業で推測する
- Markdown fenceや余計な文字を混ぜたpatch Issueを作る
- upstream未確認でIssueを発行する
- failed step未確認でblind rerunする
- 同一 `request_id` を安易に再利用する

詳細は `.gpt/ISSUE_REQUEST_CONTRACTS.md` を参照します。

## 4. Retry

失敗時は、まずfailed step / result comment / job logを確認します。

- request不備: requestを再構築
- upstream参照不備: upstream RESULTを再確認
- stale patch: latest mainから再生成
- external transient: retry / backoff
- domain validation: 原因確認。正常なfail-closedを成功扱いに変えない
- implementation error: 実装修正

同じrequestを理由確認なしでrerunしません。

## 5. Binary fileの扱い

`.xlsx` / `.sqlite` / `.db` / `.zip` 等は、まず対象プロジェクトの正本所在を確認します。GitHub外が正本なら外部正本へ直接アクセスし、GitHub旧コピーを最新と推定しません。

GitHub正本バイナリについては、現在の環境で直接read / write / materialize可能な経路を先に確認します。直接扱えない場合に限り、既存のbinary Issue / Actions経路を互換フォールバックとして利用できます。

- `.gpt/GIT_BINARY_READ_ISSUE.md`
- `.gpt/GIT_BINARY_UPDATE_ISSUE.md`
- `.gpt/GIT_BINARY_TOOL.md`

これらは**通常テキスト変更の標準経路ではなく、バイナリ搬送の補助・フォールバック**です。

## 6. `[gpt-git-update]` の位置づけ

`.gpt/GIT_UPDATE_ISSUE.md` と `.github/workflows/gpt_git_update_issue.yml` は互換性・非常時のため残します。

ただし通常のsource / test / docs / config / workflow更新でdirect GitHub writeが利用できる場合、`[gpt-git-update]` を使いません。

## 7. 複数ファイル変更

同一目的のdriver / test / workflow / docs等は、過度に細分化しません。

```text
実装 + test + docs / workflow
-> 可能なら1commit
-> Actions-native検証が必要な場合のみIssue 1回
```

branch protection、権限、競合、API制約で安全にまとめられない場合は無理に統合しません。

## 8. 並列スレッド / concurrent write の安全ルール

複数のChat / Workスレッドが同じ `main` にほぼ同時に変更を反映することを通常状態として想定します。担当プロジェクトや対象ファイルが異なる場合でも、branch HEADは共有されるためcommit競合は起こり得ます。

### 共通原則

- **force push / force ref updateを行わない。**
- Contents APIで既存ファイルを更新する場合は、変更開始時に取得した対象fileのblob SHAを条件として使用する。
- Git Data API等で複数ファイルを1commitにまとめる場合は、取得したlatest `main` を親commitとして作成し、branch ref更新はfast-forwardのみとする。
- commit反映時に `409 Conflict`、non-fast-forward、stale SHA等を検出した場合、既存変更を上書きして解決しない。
- conflict時はlatest `main` を再取得し、自スレッドの未反映差分だけを最新main上へ再構築してから再試行する。
- 同一ファイルが他スレッドで更新済みの場合は、最新内容を読み直し、双方の変更意図を保持できることを確認してから更新する。自動的な全置換で他スレッドの変更を消さない。

標準手順:

```text
変更開始
-> latest main確認
-> 対象path / blob SHA / 現在内容確認
-> 自スレッドの変更作成
-> 反映
   -> success: remote commit確認
   -> conflict / stale: latest main再取得
      -> 自分の差分だけ再構築
      -> 再反映
```

### 別ファイルを変更している場合

内容上のmerge conflictがなくても、別スレッドが先に `main` を進めることがあります。複数ファイルcommitのparentが古くなった場合は、最新mainを親として同じ論理変更を再構築します。古いbranch HEADをforceで戻しません。

### 同一ファイルを変更している場合

古いblob SHAを使った更新が拒否された場合、それは安全装置として扱います。最新fileを再取得して差分を再評価し、先行commitを保持したうえで自分の変更を載せ直します。機械的に旧全文を再送して上書きしません。

### 共通上位層

`.gpt/README.md`、`.gpt/GITHUB_OPERATION_POLICY.md`、共通 `tools/`、共通workflow等は複数プロジェクトから参照されるため、特に競合しやすい共有領域です。個別プロジェクトから変更する必要がある場合も、本節のlatest-main再確認・stale検出・force禁止を必須とします。

競合は「失敗」ではなく、並列変更を安全に直列化するための再読込シグナルとして扱います。

## 9. Source of truth境界

- GitHub: source / test / docs / config / schema等、各プロジェクトがGit正本と定義した資産
- Google Drive等: 各プロジェクトが外部正本と定義したデータ、台帳、大容量成果物
- Actions artifact: 原則一時成果物。ただし個別仕様でimmutable freeze /監査証跡と定義されたものはその仕様を優先

上位共通文書に個別プロジェクトのfile ID / Spreadsheet ID /日次データ配置を固定しません。正本の具体的所在は各プロジェクト文書を参照します。

## 10. 作業開始時の読み順

1. 本書 `.gpt/GITHUB_OPERATION_POLICY.md`
2. ルート `.gpt/README.md`
3. 対象プロジェクト `README.md`
4. 対象プロジェクト `.gpt/CONTEXT.md`
5. 対象プロジェクト `.gpt/WORKFLOW.md`
6. 対象source / test / workflow / docs

個別プロジェクト文書に旧Issue標準運用が残っている場合は、業務上Actions-nativeである理由がない限り、本書のA/B/C/Dへ棚卸しして更新します。

## 11. 標準原則

> **Git更新には原則Issueを使わない。**
>
> **GitHubにmoduleがあるだけではActionsを使わない。**
>
> **pure deterministic処理はGPTローカル実行を第一候補とする。**
>
> **IssueはActions-native処理に限定する。**
>
> **Issue発行前にrequestを完全検証する。**
>
> **同一目的の変更は、可能なら1commitにまとめる。**
>
> **並列更新ではforceせず、競合時はlatest main上へ自分の差分だけ再構築する。**
>
> **作業分割はIssue単位ではなく、論理的な完了点・監査点単位で行う。**
