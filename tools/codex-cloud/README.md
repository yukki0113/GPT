# Codex Cloud 運用ガイド

Status: ACTIVE  
Updated: 2026-10-30  
Repository: `yukki0113/GPT`

## 目的

この文書は、`yukki0113/GPT` を Codex Cloud から安全かつ再現可能に扱うための共通運用ルールを定める。

主な用途は以下。

- 実装、修正、テスト
- DuckDB / Parquet を用いた集計・バックテスト
- Google Drive 上の研究データを使った分析
- 作業結果・監査結果の Markdown 化
- GitHub への branch / commit 相当反映 / PR 作成

ChatGPT は設計・壁打ち・研究判断・最終監査を主担当とし、Codex Cloud は決定済みの指示に基づく実装・集計・検証を主担当とする。

---

## 1. 標準 Cloud Environment

公開済みの `GPT` Cloud Environment を使用する。

確認済みの基盤:

- repository: `yukki0113/GPT`
- Python 3.12 系
- DuckDB
- PyArrow / Parquet
- pandas
- repository 内の既存テスト
- Google Drive connector
- GitHub built-in connector
- PWA 確認用ネットワーク許可

Cloud Environment の依存関係を理由なくプロジェクトごとに再構築しない。

---

## 2. ChatGPT → Codex の正式な受け渡し

原則として、作業指示は Git 上の Markdown を正本とする。

推奨フロー:

```text
ChatGPT
  ↓ 設計・研究判断
instruction.md を Git に保存
  ↓
main へ反映
  ↓
新しい Codex Cloud task を開始
  ↓
instruction.md を読んで実装・集計・検証
  ↓
GitHub built-in connector で branch / PR 作成
  ↓
RESULT.md / REPORT.md を Git に保存
  ↓
ChatGPT が監査・次工程判断
```

### 重要: 指示書は task 開始前に Git へ反映する

Codex Cloud の workspace は task 開始時点の repository snapshot を基準にする。

現在の Cloud 実行環境では、shell からの `git fetch` / `git pull` は Codex Cloud 基盤の proxy 経路に依存し、`proxy:8080` への接続失敗が確認されている。

従来はtask開始後のshell Git更新を一律禁止していたが、これは2026-10-05時点の接続障害への回避策である。現在も常に通信不能とは断定せず、作業状態を保護しながら安全な同期可否を確認する。

新しい指示書・基準 commit を使う作業は、原則として:

1. 指示書を Git へ反映
2. 必要なら main へ merge
3. その後、新しい Cloud task を開始

の順にする。

同一 task 内の一時成果物や未反映変更を引き継ぐ必要がある場合は、既存 task を継続する。

### 未 merge / PR 待ち資産も確認対象にする

Codex Cloud の作業開始時に、`main` だけを「Git の全状態」とみなしてはいけない。

対象領域に **open PR / merge 待ち branch / commit 済みだが main 未反映の instruction・result・code** がある場合、それらも必ず確認対象に含める。

作業開始前の preflight では、GitHub built-in connector を使って少なくとも以下を確認する。

1. 対象領域に関連する open PR があるか
2. 指定された instruction / result / code が `main` にあるか、open PR / branch にのみ存在するか
3. 既存 PR に後続作業の前提となる変更が含まれていないか
4. 新規作業が既存の merge 待ち変更と競合・重複しないか

ファイルが workspace や `main` に見つからない場合、直ちに「存在しない」と結論しない。まず GitHub connector で open PR / branch / commit を確認する。

#### merge 待ち資産を使う場合

原則として、再現性を優先し、必要な前提 PR を main へ merge してから新しい Cloud task を開始する。

ただし、研究・監査上の理由で未 merge の内容を参照する必要がある場合は、GitHub connector 経由で対象 PR / branch / commit を明示的に読み、次を RESULT / REPORT に記録する。

- PR番号
- branch名
- commit SHA
- main 未反映であること
- その未 merge 資産を参照した理由
- 後続で merge が必要かどうか

未 merge の複数 branch を暗黙に混ぜて作業しない。どの基準状態を使ったかを必ず明示する。

#### 作業完了時の pending merge 記録

RESULT / REPORT には、作業成果そのものだけでなく、その時点で後続工程に関係する **merge 待ち PR / branch** も記載する。

推奨セクション:

```text
## Pending merge / GitHub state

- PR #NNNN: <title>
  - branch: ...
  - status: OPEN / MERGEABLE / BLOCKED
  - relevance: この後続工程で何に必要か
```

静的な README に全 open PR の一覧を恒久保存するのではなく、各 task の RESULT / REPORT に、その作業に関連する pending merge を記録する。README は「必ず確認・記録する」という運用契約を保持する。

---

## 2.1 作業開始時の最新性確認と安全な同期（必須）

最新mainを確認し、必要な基準コミットを実行workspaceへ確実に反映する。ただし実行中の変更を無条件にmainへ追従させず、再現可能な基準SHAを固定する。

1. GitHub built-in connectorでremote mainの最新SHA、関連open PR、指定の最低基準commitを確認する。localの`git rev-parse HEAD`、`git status --porcelain`、現在branchと比較する。
2. 不足する指示書やコードがあっても、古いHEADだけを理由に終了しない。未コミット変更・未追跡ファイル・進行中の作業を保護する。
3. shell Git通信が可能なら`git fetch origin main`を許可する。作業ツリーがcleanで、現在branchがfast-forward可能であり、意図する基準が確認できた場合のみ`git pull --ff-only origin main`または同等のfast-forward同期を許可する。detached HEAD、diverged履歴、変更ありの場合は無条件pull禁止。安全な新規worktree/branchまたは新規taskで対応する。
4. proxy接続エラーが起きたら強行・連続再試行しない。connector経由で最新仕様を確認し、安全なworkspace再構築または新規taskを検討する。**connectorで最新ファイルを読めることと、local実行コードが更新されたことは別**である。
5. 同期後はlocal HEAD・必要ファイル・基準SHAを検証する。PR提出前にもremote mainと差分・競合を確認し、必要な再テストを実施する。
6. 同期不能時も可能な監査・準備・fixtureテストは継続する。ただし必要な実行資産が欠けている場合は完了やPASSを宣言しない。REPORTにblockerと再開経路を記載する。

`git reset --hard`、強制push、未確認merge/rebase、作業変更の破棄は禁止。同期の許可はshellによるGitHub成果反映の許可ではない。

---

## 3. GitHub 反映ルール

### 正式経路

GitHub への書き込みは **GitHub built-in connector** を使用する。

確認済みの利用可能操作:

- branch 作成
- Git blob / tree / commit 相当の作成
- branch ref 更新
- PR 作成
- PR の task への関連付け

### 禁止事項

Codex Cloud では成果反映のために以下を使用しない。

```bash
git add
git commit
git push
```

特に shell `git push` は標準反映経路としない。

shell Git は読み取り中心とするが、第2.1節の安全条件を満たす場合に限りfetchおよびfast-forward-only pullを例外的に許可する。GitHubへの成果反映は引き続きbuilt-in connectorを正式経路とする。

例:

```bash
git status
git diff
git log
git show
```

remote最新状態の確認はbuilt-in GitHub connectorを優先し、同期後はlocal HEADとの一致を検証する。

### 理由

Cloud task では `HTTP_PROXY` / `HTTPS_PROXY` 等に `http://proxy:8080` が設定されることがあり、shell の GitHub 通信が proxy 接続エラーになることを確認済み。

GitHub built-in connector は shell proxy と別経路で動作し、実際に branch 作成から PR 作成まで成功している。

### 標準 PR

作業完了時は原則として:

1. main の最新状態を基準に作業 branch を作成
2. 今回の対象ファイルだけを反映
3. commit 相当の変更を作成
4. PR を作成
5. PR 本文に以下を記載
   - 実施内容
   - テスト結果
   - 監査結果
   - 未解決事項
   - production 影響の有無

main への直接書き込みは、明示的な指示がない限り行わない。

---

## 4. 自動承認レビューで停止した場合

Codex Cloud の shell から Git index への書き込み等を行おうとすると、自動承認レビューが発生する場合がある。

承認側モデルの capacity error により、自動承認が複数回失敗した事例を確認済み。

この場合:

- 危険判定と capacity error を混同しない
- 同じ承認を何度も再試行しない
- 実装・検証済みの workspace 変更を失わない
- GitHub 反映は built-in connector に切り替える
- shell `git add / commit / push` を続行しない

承認レビュー障害のためだけに実装やパイプラインを最初からやり直さない。

---

## 5. Google Drive 運用

通常の Drive 利用は **接続済み Google Drive connector** を使用する。

標準フロー:

```text
Google Drive connector
  ↓
必要なファイルを読み取り
  ↓
Cloud workspace の一時領域へ materialize
  ↓
Python / pandas / DuckDB / PyArrow で処理
  ↓
必要な成果物だけ保存先へ反映
```

確認済み:

- Drive 内検索 / 一覧取得
- connector 経由の実ファイル取得
- Cloud 一時領域への materialize
- CSV の pandas 読み込み

### 通常運用で使用しない経路

明示的な指示がない限り、以下へ fallback しない。

- 旧 Drive API adapter
- service account
- `GPT_GDRIVE_SERVICE_ACCOUNT_JSON`
- `gdown`
- 公開 URL を通常認証経路の代替として使用すること

repository の既存方針を優先し、Google credential を Cloud Environment に新設しない。

---

## 6. DuckDB / Parquet

共通 `GPT` Environment の既存依存を使用する。

確認済み例:

- DuckDB
- PyArrow
- pandas
- `tools/data-storage/tests`
- 各 domain の既存 tests

大量集計では、LLM 自身が行単位・レース単位で手作業ループを行うのではなく、既存モジュールまたは再利用可能な決定論的バッチを実装し、そのコードに処理させる。

### 大容量データ

大容量 CSV / Parquet / SED / 原本を Git に commit しない。

原則:

- コード・仕様・指示・RESULT / REPORT: GitHub
- 大容量原本・Parquet・SED・集計データ: Google Drive
- Cloud workspace: 一時処理領域

数百万行の候補など、再生成可能な巨大中間成果を Git に保存しない。

---

## 7. PWA / 外部 HTTP

PWA の公開確認に使用する代表的な許可済みドメイン:

- `yukki0113.github.io`
- `cdn.jsdelivr.net` （必要なビルド依存がある場合）

外部ドメインは必要最小限を原則とし、作業のために無条件で全インターネットアクセスへ広げない。

PWA の source 修正は GitHub 上の source を正本とし、公開サイトは deployment / smoke check の確認対象として扱う。

---

## 8. Cloud task の使い分け

### 同じ task を継続する

以下の場合は既存 task を続ける。

- 直前の実装・一時ファイルを引き継ぐ
- 同じ指示の追加調査
- 同じ作業のエラー切り分け
- PR 作成前の最終修正

### 新しい task を開始する

以下の場合は新しい task を開始する。

- 新しい instruction.md が main に入った
- 新しい基準 commit を確実に workspace へ取り込みたい
- Cloud Environment を変更・再公開した
- 別テーマ / 別工程へ移る
- 古い workspace snapshot に依存したくない

「次のターン」と「新しい task」を混同しない。

Environment を変更していない単なる続きは、同じ task の次のメッセージでよい。

---

## 9. PC / iPhone 間の利用

Cloud task はローカル Windows PC 上ではなく Cloud で実行する。

そのため、Cloud task の実行継続に PC の電源維持は不要。

同じ Codex Cloud task を PC / Web / iPhone から開き、以下を行える。

- 進捗確認
- 追加指示
- Codex からの質問への回答
- 実行結果・差分・PR の確認
- エラー時の方針変更

途中状態を継続したい場合は、新規 task を作らず同じ task を開く。

---

## 10. 作業結果の保存

後続の ChatGPT / Codex が会話履歴なしでも判断できるよう、重要な作業は Git に結果文書を残す。

推奨:

```text
collab/
  instructions/
    YYYYMMDD_NNN_<task>_instruction.md
  results/
    YYYYMMDD_NNN_<task>_result.md
```

RESULT / REPORT には最低限以下を含める。

- Status: DONE / BLOCKED
- 実施内容
- 使用した入力
- 変更ファイル
- 実行コマンドまたは entrypoint
- テスト結果
- 集計・監査結果
- GitHub branch / commit 相当 SHA / PR
- 関連する pending merge PR / branch と status
- 未解決事項
- 推奨 next action

巨大ログをそのまま貼らず、意思決定に必要な compact summary を優先する。

---

## 11. Codex 向け標準 footer

Cloud 用 instruction.md には、必要に応じて以下を付与する。

```text
## Codex Cloud execution rules

- Use the published GPT Cloud Environment.
- Treat the instruction file and repository docs as canonical.
- Before concluding that a file or prerequisite is missing, inspect relevant open PRs / pending branches with the built-in GitHub connector.
- Record relevant pending-merge PRs/branches in the requested RESULT/REPORT.
- Verify remote main SHA and local HEAD before work; permit safe fetch and fast-forward-only pull on a clean, compatible workspace. Preserve existing changes and use connector plus a fresh task/safe workspace reconstruction if shell Git networking fails.
- Do not use shell git push for publication.
- For GitHub writes, use the built-in GitHub connector.
- Create a working branch and PR unless explicitly instructed otherwise.
- Do not write directly to main unless explicitly authorized.
- Use the connected Google Drive connector for normal Drive access.
- Do not fall back to legacy Drive API adapters, service accounts, or gdown unless explicitly authorized.
- Keep large source/intermediate datasets out of Git.
- Preserve reproducible commands, tests, audit results, and unresolved issues in the requested RESULT/REPORT Markdown.
- If an approval reviewer fails because of model capacity, do not repeatedly retry shell Git writes; preserve the completed work and switch GitHub reflection to the built-in connector.
```

---

## 12. 作業開始チェックリスト

Codex Cloud task を開始する前に確認する。

- [ ] 対象 instruction.md は Git に保存済み
- [ ] 対象領域の関連 open PR / merge 待ち branch を GitHub connector で確認済み
- [ ] instruction / 前提資産が main と pending PR のどちらにあるか確認済み
- [ ] 必要なら main へ反映済み
- [ ] `GPT` Cloud Environment を選択
- [ ] remote main SHA、local HEAD、作業ツリー状態、最低基準SHAを照合済み
- [ ] 必要資産を安全に同期または新規環境で取り込み、実行コードを確認済み
- [ ] Drive 利用は connector 経路
- [ ] 大容量成果物の保存先は Drive
- [ ] GitHub 反映は built-in connector
- [ ] shell git push を前提にしていない
- [ ] 完了時の RESULT / REPORT 保存先が指定されている

---

## 13. 既知の注意点

- Cloud workspace は task 開始時点の repository snapshot と一致するとは限らず、特に task 開始後に追加された commit は自動追従しない。
- `main` にない資産でも open PR / pending branch に存在する場合があるため、GitHub connector での確認を省略しない。
- shell Git の GitHub 通信は Cloud proxy 障害の影響を受ける場合がある。過去の接続障害を恒久的な通信不能の証明とせず、現在の環境で安全に検証する。
- GitHub connector と shell Git の通信経路・認証は別物として扱う。
- Drive connector と repository 内の旧 Drive API adapter も別物として扱う。
- Cloud workspace の一時状態だけを唯一の成果物にしない。重要結果は GitHub または Drive の正式保存先へ残す。

この文書は、Codex Cloud の実運用で新しい制約・安定経路が判明した場合に更新する。
